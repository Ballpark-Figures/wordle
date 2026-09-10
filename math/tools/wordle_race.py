"""Race every opener against every other one, eliminating as the evidence lands.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-wordle-race.sh --fallback answer
    bash solver/run-wordle-race.sh --fallback answer \\
        --second-from data/shared/secondword/second_guess_g3.csv

WHAT THIS REPLACES.  The old way to find a good opener here was a CASCADE: sweep
every word at 100 games, cut to those within 5 standard errors of the best,
re-sweep the survivors at the next rung with a fresh seed, cut again, and finish
with a paired comparison -- one command and one file per pass, with the ladder
and the seed advanced by hand.  This is the same statistics run as ONE resumable
process: every opener starts on 100 games, anything more than `--sigma` PAIRED
standard errors behind the leader is dropped THE MOMENT that becomes true, and
the survivors just keep playing on a doubling schedule.  Halt it whenever you
like; it checkpoints continuously and resumes where it stopped.

IT IS THE SAME RACE AS `tools/multiwordle_race.py`, not a second one.  The whole
driver -- the block schedule, the chunking, the two phases, the checkpoint, the
cut, the elimination lines and the status line -- is `race_stats.run`, shared with
it.  What lives in THIS file is only what is genuinely single-board: how a game is
played, and how the standings are written.  Everything else has one definition, so
a fix to the race is a fix to both races.

PAIRED FROM THE FIRST GAME, which is the reason it can cut this early.  Every
opener plays the IDENTICAL games -- the same answer from the same per-game seed,
and the same coin flips, ONE FLOAT PER DECISION (`wordlesim.CoupledDraw` says
why) so that two openers whose live sets differ in size cannot fall out of step.
So an opener is judged on `d_i = score_it - score_leadt` game by game, and the
error on that DIFFERENCE is much smaller than either opener's own standard error.
A run reports both; the paired one decides.

  A CONSEQUENCE WORTH STATING: a race cell will not match a sweep cell or a
  run-wordle-sim.sh run at the same seed.  The coupling is a different sampler,
  deliberately -- the sweep couples the ANSWERS only and draws its picks with
  `integers`.  Same quantity, different sample.

WHAT A RACE CAN GET WRONG.  It eliminates against a MOVING LEADER, so an opener
that draws a lucky first hundred games can push a genuinely better one out.  The
generous cut is a mitigation, not a proof, and it is why `--sigma` is a flag.  A
race is still a SCREEN: its winner is the best of the openers ENTERED, judged on
the games actually played.

IT RANKS ON THE MEAN, and only on the mean.  The sweep's parallel `--rank
win_rate` has no analogue here and is deliberately absent rather than
half-built: the win rate is still reported per opener in the standings, but
nothing cuts on it.

THE FOLLOW-UP IS AN INPUT AND IS NEVER DEFAULTED, as everywhere else in
wordlesim: `--fallback answer` and `--fallback guess` feed the opener to two
different players, so they are two different races and the file says which.
`--second-from` is the other half of the strategy -- with it every opener plays
its own predetermined second word whenever the reply shows enough greys
(math/secondword.py), without it the opener is played and the follow-up takes
over.  Both land in the filename.

THE SCORE IS EXPECTED GUESSES OUTRIGHT.  Play is never truncated, so these means
sit with the rest of wordlesim and NOT with any optturns-family total, which is
an optimum subject to a 6-guess guarantee.  Six enters only as the threshold the
reported win rate is read off.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                        # noqa: E402
from opening_list import read_openings                          # noqa: E402
import race_stats as rs                                          # noqa: E402
from secondword import read_table                               # noqa: E402
from wordle import load_words                                   # noqa: E402
from wordlesim import (WIN_WITHIN, CoupledDraw, answer_to_guess,  # noqa: E402
                       draw_answer, make_opening_rule, make_tail, play_game,
                       second_rule_for)

COLUMNS = ("word,trials,mean,stderr,diff_vs_leader,paired_stderr,sigma,"
           "win_rate,status,is_answer")
ELIM_COLUMNS = "word,trials,mean,diff_vs_leader,paired_stderr,sigma,leader"

# Kept apart from the answer-draw stream so one opener's coin flips can never
# shift another opener's answers.  Same constant, same reason, as the sweeps.
PICK_OFFSET = 1 << 20

# Coin flips drawn per game to start with.  A game needs one per follow-up draw,
# so this is generous; a game that exhausts it regrows the array and replays,
# and `Generator.random(n)` is prefix-consistent so the replay is the same game.
FLIPS = 64


class FloatCursor:
    """One game's coin flips, consumed in order -- what CoupledDraw draws from.

    A Generator per (opener, game) would cost more than the game does at this
    field size, and would not be reproducible across a resume without re-seeding
    anyway.  A pre-drawn row indexed in order is both cheaper and exactly the
    coupling: every opener in this game reads the same floats in the same order,
    and diverges only where the game itself diverges.
    """

    __slots__ = ("row", "i")

    def __init__(self, row):
        self.row = row
        self.i = 0

    def random(self):
        if self.i >= len(self.row):
            raise rs.Regrow
        v = self.row[self.i]
        self.i += 1
        return v


def parse_args(argv):
    a = {
        "fallback": None, "words": "guess", "openings_from": None, "top": None,
        "second_from": "", "seed": 0, "sigma": 5.0, "block": 100, "growth": 2.0,
        "out": None, "max_games": None, "pair_at": 2000, "chunk": 0,
        "max_mem": 2.0, "report": 60.0, "checkpoint": 30.0, "dry_run": False,
        "win_within": WIN_WITHIN,
    }
    ints = {"seed", "block", "pair_at", "chunk", "top", "max_games", "win_within"}
    floats = {"sigma", "growth", "max_mem", "report", "checkpoint"}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k in ("dry_run",):
            a["dry_run"] = True
            i += 1
            continue
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k == "print_stem":
            # The wrapper asks HERE what the file should be called, so the
            # derivation lives in stem_for() alone rather than being
            # re-implemented in shell -- the paired comparison's precedent.
            a["out"] = "--print-stem"
            i += 1
            continue
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = int(v) if k in ints else float(v) if k in floats else v
        i += 2
    if a["fallback"] not in ("answer", "guess"):
        raise SystemExit(
            "--fallback is required: 'answer' or 'guess', which random word the "
            "opener hands the rest of the game to.\nIt is part of the question, "
            "and it is in the result filename.\n"
            "Use the wrapper: bash solver/run-wordle-race.sh --fallback answer")
    if a["out"] == "--print-stem":
        return a
    if a["out"] is None:
        raise SystemExit(
            "--out is required (or --no-out to discard the race deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-wordle-race.sh")
    if a["sigma"] <= 0:
        raise SystemExit("--sigma must be positive: it is how many paired "
                         "standard errors behind the leader is fatal")
    if a["block"] < 2:
        raise SystemExit("--block must be at least 2 games (a standard error "
                         "needs two)")
    if a["growth"] <= 1.0:
        raise SystemExit("--growth must be above 1, or the blocks never grow")
    return a


def load_field(a, guesses):
    """The openers to race, as lists of words, plus a name for the file stem."""
    if a["openings_from"]:
        field = read_openings(a["openings_from"], a["top"])
        name = os.path.basename(a["openings_from"])
        name = name[:-4] if name.endswith(".csv") else name
        if a["top"]:
            name += "_top%d" % a["top"]
        return field, name
    if a["words"] in ("guess", "mystery"):
        words = load_words(a["words"])
        name = a["words"]
    else:
        with open(a["words"]) as f:
            words = [ln.strip() for ln in f if ln.strip()]
        name = os.path.basename(a["words"])
        name = name[:-4] if name.endswith(".txt") else name
    field = [w.split() for w in words]
    if a["top"]:
        field = field[:a["top"]]
        name += "_top%d" % a["top"]
    return field, name


def make_games(na, seed, g0, g1, nf):
    """Games g0..g1: the hidden answers and the coin flips, one row per game.

    Seeded PER GAME rather than per opener, which is what makes the comparison
    paired: every opener in the race plays game 5000 against the same answer with
    the same flips, whenever it happens to get there and whoever else is left.
    That is also what makes a resume exact -- the games are a function of (seed,
    game index) alone, so nothing about the field or the chunking can move them.
    """
    n = g1 - g0
    ans = np.empty(n, dtype=np.int64)
    fl = np.empty((n, nf), dtype=np.float64)
    for i in range(n):
        gi = g0 + i
        ans[i] = draw_answer(na, np.random.default_rng([seed, gi]))
        fl[i] = np.random.default_rng([seed, gi, PICK_OFFSET]).random(nf)
    return ans, fl


class Player:
    """How a single-board game is played -- the race driver's adapter.

    It holds no race state: the driver owns the field, the blocks and the
    checkpoint, and calls in here for a chunk of scores.  `wins` is carried in
    the checkpoint by the driver's `extra` and accumulated here, because the win
    rate is REPORTED per opener even though nothing cuts on it.
    """

    def __init__(self, pat, ans2g, rules, tail, na, win_within, wins, chunk):
        self.pat = pat
        self.ans2g = ans2g
        self.rules = rules
        self.tail = tail
        self.na = na
        self.win_within = win_within
        self.wins = wins
        self.chunk = chunk
        self.nf = FLIPS

    def make_games(self, seed, g0, g1):
        return make_games(self.na, seed, g0, g1, self.nf)

    def play(self, ids, games):
        return play_chunk(self.pat, self.ans2g, [self.rules[i] for i in ids],
                          self.tail, games[0], games[1])

    def regrow(self):
        self.nf *= 2
        print("  (coin-flip array regrown to %d)" % self.nf)

    def record(self, ids, sc, g0, g1):
        self.wins[ids] += (sc <= self.win_within).sum(axis=1)

    def chunk_size(self, ids, n_games, target, seed):
        """None: use the driver's measured default.

        There is no per-opener setup to amortise here -- no table to rebuild, no
        JIT to warm -- so nothing in this game has an opinion about how many
        games a chunk should hold, and the driver's "about two seconds" is
        exactly right.  That is the one place multiwordle's race genuinely
        differs, and it is why the driver asks rather than assumes.
        """
        return self.chunk or None


def play_chunk(pat, ans2g, rules, tail, ans, fl):
    """Scores for every live opener over one chunk of games: (openers, games).

    Games are the OUTER loop, so a halt always leaves the field LEVEL -- every
    live opener has played exactly the same games, which is the state you can
    rank and cut.  Raises race_stats.Regrow if any game wanted more coin flips
    than the row held; the driver regrows and replays.
    """
    m, n = len(rules), len(ans)
    sc = np.empty((m, n), dtype=np.int16)
    for j in range(n):
        answer_idx = int(ans[j])
        row = fl[j]
        for i, rule in enumerate(rules):
            played, _ = play_game(pat, ans2g, answer_idx, rule, tail,
                                  FloatCursor(row))
            sc[i, j] = len(played)
    return sc


def build_rules(field, guesses, table, tail):
    """One rule per opener: the gray-second rule under a table, else the opener.

    Both come from wordlesim's own constructors, so a race runs exactly the
    strategy the sweep and the paired comparison run -- there is no third
    definition of either rule here.
    """
    pos = {w: i for i, w in enumerate(guesses)}
    out = []
    for o in field:
        gi = [pos[w] for w in o]
        out.append(second_rule_for(gi, table, guesses) if table
                   else make_opening_rule(gi, tail=tail, adapt=0))
    return out


def stem_for(a, list_name, table):
    stem = "race_%s_%s_sig%g_s%d" % (a["fallback"], list_name, a["sigma"],
                                     a["seed"])
    if table:
        # THE TABLE'S OWN POOLS GO IN THE NAME, not just the threshold.  The
        # opener list is already in the stem, but the SECOND-WORD pool is the
        # other half of the variant -- racing the 2315 openers against the
        # 12972-word table is a different experiment from racing them against
        # the answers-only one, and without this they would share a filename,
        # which means sharing a checkpoint and resuming into each other.
        stem += "_%s-%s" % (table.fire, table.seconds)
    if a["win_within"] != WIN_WITHIN:
        stem += "_w%d" % a["win_within"]
    return stem


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    answer_set = set(answers)
    na = len(answers)

    field, list_name = load_field(a, guesses)
    sizes = {len(o) for o in field}
    if len(sizes) != 1:
        raise SystemExit(
            "the field mixes opening sizes %s -- ranking a one-word opening "
            "against a two-word one compares two different strategies"
            % sorted(sizes))
    bad = sorted({w for o in field for w in o if w not in answer_set
                  and w not in set(guesses)})
    if bad:
        raise SystemExit("%d opening words are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))
    names = [" ".join(o) for o in field]
    if len(names) != len(set(names)):
        raise SystemExit("the field repeats an opening")

    table = None
    if a["second_from"]:
        table = read_table(a["second_from"])
        if sizes != {1}:
            raise SystemExit("--second-from races ONE opener per entry; this "
                             "field holds openings of %d words" % sizes.pop())
        missing = [n for n in names if n.split()[0] not in table.rows]
        if missing:
            # UP FRONT: a table built over one pool and raced over another would
            # otherwise die partway through a block, leaving a checkpoint and a
            # standings file for a race that never really started.
            raise SystemExit(
                "%d of the %d openers have no row in %s (e.g. %s).\nIt was built "
                "over the %s opener pool -- race the matching word list, or "
                "build the table for this one."
                % (len(missing), len(names), a["second_from"],
                   " ".join(missing[:5]), table.openers))

    # An "answer opener" is built entirely of mystery words.  The field is every
    # legal guess, so this subset is reported separately: the best one is named in
    # every status line and the moment the LAST one falls is called out.
    is_answer = np.array([all(w in answer_set for w in o) for o in field])

    stem = stem_for(a, list_name, table)
    if a["out"] == "--print-stem":
        print(stem)
        print(len(field))
        return
    out = a["out"]
    elim_path = ck_path = None
    if out:
        base = out[:-4] if out.endswith(".csv") else out
        elim_path = base + "_eliminations.csv"
        ck_path = os.path.join("data", "local", "wordlesim",
                               os.path.basename(base) + ".npz")

    print("race: %d openers of %d word(s) from %s, follow-up %s"
          % (len(field), sizes.copy().pop(), list_name, a["fallback"]))
    if table:
        print("  each opener plays its own second word from %s, firing on %s"
              % (a["second_from"], table.fire))
    else:
        print("  each opener is played blind, then the follow-up takes over")
    print("  cut %.4g PAIRED sigma behind the leader; blocks of %d then x%g; "
          "seed %d" % (a["sigma"], a["block"], a["growth"], a["seed"]))
    print("  %d openers are answer words" % int(is_answer.sum()))
    if out:
        print("  standings    %s" % out)
        print("  eliminations %s" % elim_path)
        print("  checkpoint   %s" % ck_path)
    if a["dry_run"]:
        print("\n--dry-run: resolved everything, stopping before any game is "
              "played")
        return

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    tail = CoupledDraw(make_tail(a["fallback"], guesses, answers, ans2g))
    rules = build_rules(field, guesses, table, tail)

    wins = np.zeros(len(field), dtype=np.int64)
    player = Player(pat, ans2g, rules, tail, na, a["win_within"], wins,
                    a["chunk"])
    extra = {"wins": wins}

    def writer(status, elim_at, live, mean, ose, md, se, n_games, lead):
        write_standings(out, stem, a, names, status, elim_at, live, mean, ose,
                        md, se, extra["wins"], is_answer, n_games, lead,
                        list_name, table)

    rs.run({k: a[k] for k in ("sigma", "block", "growth", "max_games",
                              "pair_at", "max_mem", "report", "checkpoint",
                              "chunk", "seed")},
           player, names, is_answer, writer, elim_path, ck_path, ELIM_COLUMNS,
           noun="opener", extra=extra, stem=stem)


def write_standings(out, stem, a, names, status, elim_at, live, mean, ose, md,
                    se, wins, is_answer, n_games, lead, list_name, table):
    """The standings, rewritten in full at every block.

    SWEEP-SHAPED LEADING COLUMNS -- word, trials, mean, stderr -- plus the same
    `# settings` and `# lineage` lines a sweep writes, so tools/sweep_shortlist.py
    and tools/paired_compare.py read a race's standings exactly as they read a
    sweep's.  That is what lets a finished race hand its survivors straight to a
    paired round without anything in between re-implementing the format.
    """
    if not out:
        return
    order = np.argsort(mean, kind="stable")
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        f.write("# %s -- single-board wordle opener RACE (tools/wordle_race.py)\n"
                % stem)
        f.write("# %d openers entered, %d still live at %d games each\n"
                % (len(names), len(live), n_games))
        f.write("# every opener plays the IDENTICAL games and the identical coin "
                "flips, so the cut\n# uses the PAIRED error against the leader; "
                "`stderr` is each opener's own, reported only\n")
        f.write("# cut: more than %g paired sigma behind the leader leaves.  A "
                "race is a SCREEN --\n# it eliminates against a MOVING leader, so "
                "its head is the best of the openers\n# entered, judged on the "
                "games actually played, never 'the best opener'\n" % a["sigma"])
        f.write("# NO guess cap: the mean is expected guesses OUTRIGHT, and "
                "win_rate is the fraction\n# of those untruncated scores at %d "
                "guesses or fewer\n" % a["win_within"])
        if table:
            f.write("# each opener plays the predetermined second word from %s "
                    "whenever its\n# reply fires %s (math/secondword.py; pools "
                    "openers=%s seconds=%s)\n"
                    % (a["second_from"], table.fire, table.openers,
                       table.seconds))
        f.write("# settings follow_up=%s pair_adaptive=0 win_within=%d "
                "trials=%d seed=%d words=%d rank=mean second_table=%s "
                "fire=%s\n"
                % (a["fallback"], a["win_within"], n_games, a["seed"],
                   len(names), a["second_from"] or "-",
                   table.fire if table else "-"))
        f.write("# lineage root=%s pass=1 source=(race)\n" % list_name)
        f.write(COLUMNS + "\n")
        for k in order:
            c = int(live[k])
            sig = md[k] / se[k] if se[k] > 0 else 0.0
            f.write("%s,%d,%.6f,%.6f,%.6f,%.6f,%.3f,%.6f,%s,%d\n"
                    % (names[c], n_games, mean[k], ose[k], md[k], se[k], sig,
                       wins[c] / n_games, status[c], int(is_answer[c])))
        for c in np.flatnonzero(np.array(status) == "out"):
            f.write("%s,%d,,,,,,%.6f,out,%d\n"
                    % (names[int(c)], int(elim_at[c]),
                       wins[c] / max(1, elim_at[c]), int(is_answer[int(c)])))
    os.replace(tmp, out)


if __name__ == "__main__":
    main(sys.argv[1:])
