"""Race every opening against every other one, eliminating as the evidence lands.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-multiwordle-race.sh --strategy srank  -k 16
    bash solver/run-multiwordle-race.sh --strategy minavg -k 4
    bash solver/run-multiwordle-race.sh --strategy srank  -k 16 \\
        --openings-from data/shared/singletons/pair_singletons.csv --top 10000

WHAT THIS REPLACES.  The old way to find a good opening was a CASCADE: sweep every
word at 100 trials, cut to those within N standard errors of the best, re-sweep the
survivors at 1000 with a fresh seed, cut again, and so on -- one command and one
file per stage, with the trial ladder and the seed advanced by hand.  This is the
same statistics run as ONE resumable process: every opening starts on 100 games,
anything more than `--sigma` standard errors behind the leader is dropped THE MOMENT
that becomes true, and the survivors just keep playing.  Halt it whenever you like;
it checkpoints continuously and resumes where it stopped.

PAIRED FROM THE FIRST GAME, which is the reason it can cut at all this early.
Every opening plays the IDENTICAL games -- the same k answers drawn from the same
per-game seed, and the same coin flips, one float per decision so that two openings
whose live sets differ in size cannot fall out of step (`multiwordle.CoupledRng`
says why).  So an opening is judged on `d_i = score_it - score_leader` game by game,
and the error on that DIFFERENCE is much smaller than either opening's own standard
error: anagram-ish openings play nearly identical games and almost all the variance
cancels.  A run reports both, and the paired sigma is the one the cut uses.

  A CONSEQUENCE WORTH STATING: a race cell will not match a `run-multiwordle.sh`
  run at the same seed.  The coupling is a different sampler, deliberately, and
  `multiwordle_sim.py` draws answers and picks from one stream.  Same quantity,
  different sample.

WHAT A RACE CAN GET WRONG.  It eliminates against a MOVING LEADER, so an opening
that draws a lucky first hundred games can push a genuinely better one out.  The
mitigation is the generous cut -- 5 paired sigma is a strong statement, not a close
call -- but it is a mitigation and not a proof, and it is why `--sigma` is a flag.
A race is still a SCREEN: its winner is the best of the openings entered, judged on
the games actually played.

TWO PHASES, one exact answer.  While many openings are live the per-game scores are
kept as a (live x games) int16 history, which makes any pairwise comparison exact
even as the leader changes.  Once the field is small enough (`--pair-at`) the
pairwise sums are computed FROM that history, once, and the history is dropped: from
then on only sum(d) and sum(d^2) per pair are carried, which is O(live^2) memory
independent of the game count, so the survivors can run to hundreds of millions of
games.  The switch is exact -- nothing is estimated across it.

THE STRATEGY IS AN INPUT AND IS NEVER DEFAULTED (`--strategy`), and so is the
opening list.  Both name the output file: `srank` at k=16 over the guess list and
`minavg` at k=16 over the same list are different experiments, and a file that did
not say which produced it would be ambiguous forever.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import multiwordle as mw                                        # noqa: E402
import multiwordle_fast as mf                                   # noqa: E402
from build_patterns import load_patterns                        # noqa: E402
from race_stats import (accumulate_pairwise, block_targets,     # noqa: E402
                        eliminate, history_paired, history_sums, own_error,
                        paired_error, pairwise_from_history)
from opening_list import read_openings                          # noqa: E402
from wordle import load_words                                   # noqa: E402

COLUMNS = ("opening,status,games,mean,stderr,diff_vs_leader,paired_stderr,"
           "sigma,is_answer")
ELIM_COLUMNS = "opening,games,mean,diff_vs_leader,paired_stderr,sigma,leader"

# Kept apart from the answer-draw stream so one opening's coin flips can never
# shift another opening's answers.  Same constant, same reason, as the sweeps.
PICK_OFFSET = 1 << 20

# A game chunk should do at least this much work, so that checkpointing and the
# Python round trip are never the job.  Only a floor: the real driver of the chunk
# size is amortising per-opening setup (see Player.calibrate).
MIN_CHUNK_SECONDS = 1.0


def parse_args(argv):
    a = {
        "strategy": None, "k": None, "seed": 0, "sigma": 5.0,
        "block": 100, "growth": 2.0, "openings": "guess", "top": None,
        "out": None, "max_games": None, "pair_at": 2000, "chunk": 0,
        "max_mem": 2.0, "report": 60.0, "dry_run": False,
        "memo_overhead": 0.10, "checkpoint": 30.0,
    }
    i = 0
    while i < len(argv):
        f = argv[i]
        if f == "--strategy":
            a["strategy"] = argv[i + 1]; i += 2
        elif f in ("-k", "--boards"):
            a["k"] = int(argv[i + 1]); i += 2
        elif f == "--seed":
            a["seed"] = int(argv[i + 1]); i += 2
        elif f == "--sigma":
            a["sigma"] = float(argv[i + 1]); i += 2
        elif f == "--block":
            a["block"] = int(argv[i + 1]); i += 2
        elif f == "--growth":
            a["growth"] = float(argv[i + 1]); i += 2
        elif f in ("--openings", "--words"):
            a["openings"] = argv[i + 1]; i += 2
        elif f == "--openings-from":
            a["openings"] = argv[i + 1]; i += 2
        elif f == "--top":
            a["top"] = int(argv[i + 1]); i += 2
        elif f == "--out":
            a["out"] = argv[i + 1]; i += 2
        elif f == "--no-out":
            a["out"] = False; i += 1
        elif f == "--max-games":
            a["max_games"] = int(argv[i + 1]); i += 2
        elif f == "--pair-at":
            a["pair_at"] = int(argv[i + 1]); i += 2
        elif f == "--chunk":
            a["chunk"] = int(argv[i + 1]); i += 2
        elif f == "--memo-overhead":
            a["memo_overhead"] = float(argv[i + 1]); i += 2
        elif f == "--checkpoint":
            a["checkpoint"] = float(argv[i + 1]); i += 2
        elif f == "--max-mem":
            a["max_mem"] = float(argv[i + 1]); i += 2
        elif f == "--report":
            a["report"] = float(argv[i + 1]); i += 2
        elif f == "--dry-run":
            a["dry_run"] = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % f)
    if a["strategy"] not in mw.STRATEGIES:
        raise SystemExit(
            "--strategy is required and names the experiment: one of %s.\n"
            "Use the wrapper, which passes one: "
            "bash solver/run-multiwordle-race.sh" % ", ".join(mw.STRATEGIES))
    if a["k"] is None or a["k"] < 1:
        raise SystemExit("-k (number of boards) is required and must be >= 1")
    if a["sigma"] <= 0:
        raise SystemExit("--sigma must be positive")
    if a["out"] is None:
        # The strturns lesson: a run that prints its answer and saves nothing is
        # a run lost -- and this one can run for days.  Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: "
            "bash solver/run-multiwordle-race.sh")
    return a


def load_openings(spec, top, guesses):
    """The field: one opening per entry, each a list of words, in the source's
    own order.  A word list gives one-word openings; a ranking CSV gives whatever
    its `word*` columns hold."""
    if spec in ("guess", "mystery"):
        if top is not None:
            raise SystemExit("--top applies to a ranking file, not %r" % spec)
        return [[w] for w in load_words(spec)]
    if spec.endswith(".csv"):
        return read_openings(spec, top)
    with open(spec) as f:
        out = [ln.split() for ln in f if ln.strip()]
    if not out:
        raise SystemExit("%s is empty" % spec)
    return out


def list_name(spec, top):
    if spec in ("guess", "mystery"):
        return spec
    stem = os.path.basename(spec)
    for ext in (".csv", ".txt"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    return stem + ("_top%d" % top if top else "")


# --- the games -------------------------------------------------------------

def make_games(na, k, seed, g0, g1, nf):
    """Games g0..g1: the answers and the coin flips, identical for every opening.

    Seeded PER GAME rather than per opening, which is what makes the comparison
    paired.  `Generator.random(n)` is prefix-consistent, so regrowing `nf` after an
    overflow extends the same stream and replays the same game.
    """
    n = g1 - g0
    ans = np.empty((n, k), dtype=np.int64)
    fl = np.empty((n, nf), dtype=np.float64)
    for i in range(n):
        gi = g0 + i
        ans[i] = mw.draw_answers(na, k, np.random.default_rng([seed, gi]))
        fl[i] = np.random.default_rng([seed, gi, PICK_OFFSET]).random(nf)
    return ans, fl


class Player:
    """Plays a block of games for a set of openings, by strategy."""

    def __init__(self, strategy, pat, ans2g, guesses, k):
        self.strategy = strategy
        self.pat = pat
        self.ans2g = ans2g
        self.k = k
        self.pool = np.arange(pat.shape[0], dtype=np.int64)
        if strategy == mw.SRANK:
            self.rankval = mf.ranking_table(mw.load_singleton_ranking())
            self.letters = mf.guess_letter_table(guesses)
            self.mode = mf.PICK_SRANK
        else:
            self.rankval = np.zeros((1, 1))
            self.letters = np.zeros((1, 1), dtype=np.int8)
            self.mode = mf.PICK_GREEDY
        self._turn2 = {}

    def needs_floats(self):
        return self.strategy != mw.MINAVG

    def calibrate(self, opening, ans, fl):
        """(per-opening SETUP seconds, per-opening PER-GAME seconds).

        The race plays GAMES in the outer loop so that a halt always leaves every
        live opening level, which is the state you can actually rank and cut.
        That costs one pass of per-opening SETUP per game chunk -- for `minavg`,
        rebuilding each opening's 25 MB turn-2 table -- so the chunk has to be big
        enough to amortise it.  How big depends on the strategy AND on k, so it is
        MEASURED on one opening rather than guessed: `srank` has no setup at all
        and can chunk as finely as it likes, while `minavg` at k=2 has to take a
        whole block at a time and at k=16 can afford about twenty chunks.
        """
        op = np.asarray(opening, dtype=np.int64).reshape(1, -1)
        n = max(1, min(len(ans), 8))
        self._turn2.pop("key", None)               # force a real build, not a hit
        t0 = time.time()
        if self.strategy == mw.MINAVG and op.shape[1] == 1:
            self._turn2_for(int(op[0, 0]))
        setup = time.time() - t0
        t0 = time.time()
        # the table just built is cached, so this times the GAMES alone
        self.play(op, ans[:n], fl[:n])
        play = (time.time() - t0) / n
        return max(setup, 0.0), max(play, 1e-9)

    def play(self, openings, ans, fl):
        """(n_openings, n_games) scores; -1 where the float array ran out."""
        if self.strategy == mw.MINAVG:
            out = np.empty((len(openings), len(ans)), dtype=np.int64)
            for c in range(len(openings)):
                op = openings[c]
                # the turn-2 memo is keyed on the OPENER, so it only exists for a
                # one-word opening; with a longer opening guess 2 is still blind
                use = op.shape[0] == 1
                t2 = self._turn2_for(int(op[0])) if use else self._empty_turn2()
                mf.run_minavg_games(self.pat, self.ans2g, ans, op, self.pool,
                                    t2, use, out[c])
            return out
        out = np.empty((len(openings), len(ans)), dtype=np.int64)
        mf.run_pick_block(self.pat, self.ans2g, ans, openings, self.mode,
                          self.rankval, self.letters, fl, out)
        return out

    def _empty_turn2(self):
        if "empty" not in self._turn2:
            self._turn2["empty"] = np.zeros((1, len(self.pool)))
        return self._turn2["empty"]

    def _turn2_for(self, opener):
        # one opener at a time: the table is 243 x 12972 doubles (25 MB), so it is
        # built, used for that opener's whole block, and dropped
        if self._turn2.get("key") != opener:
            self._turn2["key"] = opener
            self._turn2["tab"] = mf.turn2_table(self.pat, opener, self.pool)
        return self._turn2["tab"]


# --- the statistics --------------------------------------------------------
#
# Everything below reduces over the game axis in COLUMN CHUNKS.  The history is
# int16 and the arithmetic is float64, so a whole-array cast would cost four
# times the stored size at exactly the moment the race is widest; chunking keeps
# the working set to a few megabytes however long the race runs.

# --- the race --------------------------------------------------------------
#
# THE ESTIMATOR AND THE CUT LIVE IN tools/race_stats.py, shared with the
# wordlesim race, because they are the one thing that must not differ between two
# races: the paired difference, both standard errors, the block schedule and what
# "sigma behind" means.  The LOOP below stays here -- it has to amortise minavg's
# per-opening turn-2 table, which the wordlesim race has no equivalent of, so one
# loop serving both would be the shared-helper failure rather than reuse.
#
# The names are imported into this module, so `multiwordle_race.paired_error` is
# still the same function it always was and every caller is unchanged.


def game_chunk(m):
    """Games per checkpoint once the race is on pairwise sums.

    Sized so the block's scores stay around 64 MB.  It matters for `minavg`,
    which rebuilds its 25 MB turn-2 table once per opening per chunk: too small a
    chunk and that rebuild costs more than the games it serves.
    """
    return max(4096, 8_000_000 // max(1, m))


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    answer_set = set(answers)
    na = len(answers)
    if a["k"] > na:
        raise SystemExit("k=%d exceeds the %d answer words" % (a["k"], na))

    field = load_openings(a["openings"], a["top"], guesses)
    sizes = {len(o) for o in field}
    if len(sizes) != 1:
        raise SystemExit(
            "the field mixes opening sizes %s -- ranking a one-word opening "
            "against a two-word one compares two different strategies"
            % sorted(sizes))
    bad = sorted({w for o in field for w in o if w not in guesses})
    if bad:
        raise SystemExit("%d opening words are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))
    if len(field) != len({tuple(o) for o in field}):
        raise SystemExit("the field repeats an opening")

    names = [" ".join(o) for o in field]
    # An "answer opening" is built entirely of mystery words.  The field is every
    # legal guess, so this subset is reported separately: the best one is named in
    # every status line and the moment the LAST one falls is called out.
    is_answer = np.array([all(w in answer_set for w in o) for o in field])
    nopen = len(field[0])
    openings = np.array([[guesses.index(w) for w in o] for o in field],
                        dtype=np.int64)

    stem = "race_%s_k%d_%s_sig%g_s%d" % (
        a["strategy"], a["k"], list_name(a["openings"], a["top"]),
        a["sigma"], a["seed"])
    out = a["out"]
    elim_path = ck_path = None
    if out:
        base = out[:-4] if out.endswith(".csv") else out
        elim_path = base + "_eliminations.csv"
        ck_path = os.path.join("data", "local", "multiwordle",
                               os.path.basename(base) + ".npz")

    print("race: %s at k=%d over %d openings of %d word(s) from %s"
          % (a["strategy"], a["k"], len(field), nopen, a["openings"]))
    print("  cut %.4g PAIRED sigma behind the leader; blocks of %d then x%g; "
          "seed %d" % (a["sigma"], a["block"], a["growth"], a["seed"]))
    print("  %d openings are built entirely of answer words"
          % int(is_answer.sum()))
    if out:
        print("  standings   %s" % out)
        print("  eliminations %s" % elim_path)
        print("  checkpoint  %s" % ck_path)
    if a["dry_run"]:
        print("\n--dry-run: resolved everything, stopping before any game is "
              "played")
        return

    pat = np.array(load_patterns())
    ans2g = mw.answer_to_guess(answers, guesses)
    player = Player(a["strategy"], pat, ans2g, guesses, a["k"])

    live = np.arange(len(field))
    n_games = 0                # games every live opening has completed
    hist = np.zeros((len(field), 0), dtype=np.int16)
    paired = None              # (sum_d, sumsq_d, tot, sq) once switched
    status = ["live"] * len(field)
    elim_at = np.zeros(len(field), dtype=np.int64)
    nf = 64 + 8 * a["k"]

    if ck_path and os.path.exists(ck_path):
        z = np.load(ck_path, allow_pickle=False)
        if int(z["field"]) != len(field):
            raise SystemExit(
                "%s was written for a field of %d openings, not %d -- a "
                "checkpoint from a different race must never be resumed into "
                "this one" % (ck_path, int(z["field"]), len(field)))
        live = z["live"]
        n_games = int(z["n_games"])
        status = [s.decode() for s in z["status"]]
        elim_at = z["elim_at"]
        if bool(z["paired"]):
            paired = (z["sum_d"], z["sumsq_d"], z["tot"], z["sq"])
        else:
            hist = z["hist"]
        if "filled" in z and int(z["filled"]):
            # written by the openings-outer version, which could leave a block
            # part-played: those extra games belong to some openings and not
            # others, so they are DISCARDED rather than mixed into a comparison
            print("  (checkpoint holds a part-played block from the older "
                  "openings-outer loop; discarding it and resuming from %d "
                  "complete games)" % n_games)
        if hist.shape[1] > n_games:
            hist = hist[:, :n_games].copy()
        print("\nresuming: %d live, every one level at %d games"
              % (len(live), n_games))

    os.makedirs(os.path.join("data", "local", "multiwordle"), exist_ok=True)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        if not os.path.exists(elim_path):
            with open(elim_path, "w") as f:
                f.write("# %s -- one row per opening as it leaves the race\n"
                        % stem)
                f.write(ELIM_COLUMNS + "\n")

    def checkpoint(force=False):
        """Save the race state.  Cheap to call: it writes at most every
        --checkpoint seconds, because the history grows with the game count and
        the chunks are deliberately short.  The state is consistent at EVERY
        chunk boundary (all live openings level at n_games), so a skipped write
        costs at most that many seconds of games, never correctness."""
        if not ck_path:
            return
        if not force and time.time() - last_ck[0] < a["checkpoint"]:
            return
        last_ck[0] = time.time()
        kw = dict(field=len(field), live=live, n_games=n_games, elim_at=elim_at,
                  status=np.array([s.encode() for s in status]),
                  paired=paired is not None)
        if paired is None:
            kw["hist"] = hist
        else:
            kw.update(sum_d=paired[0], sumsq_d=paired[1], tot=paired[2],
                      sq=paired[3])
        # atomic: a checkpoint half-written by a Ctrl-C would lose the whole race
        np.savez(ck_path + ".tmp", **kw)
        os.replace(ck_path + ".tmp.npz", ck_path)

    last_report = time.time()
    said_step = [0]
    warmed = [False]
    last_ck = [0.0]
    for target in block_targets(a["block"], a["growth"], a["max_games"]):
        if len(live) <= 1:
            break
        if target <= n_games:
            continue

        # GAMES ARE THE OUTER LOOP, so every live opening is always level: stop
        # whenever you like and the standings are a real ranking of the whole
        # field at n_games, not a complete answer for an alphabetical prefix and
        # nothing for the rest.  The chunk is sized from a measured calibration so
        # that per-opening setup (minavg's turn-2 table) stays a small share of
        # the work -- see Player.calibrate.
        if paired is None and hist.shape[1] < target:
            grown = np.zeros((len(live), target), dtype=np.int16)
            grown[:, :hist.shape[1]] = hist
            hist = grown
        # Calibrated ONCE per block, not per chunk: the measurement itself costs a
        # setup, and the per-game cost barely moves.  The first one is preceded by
        # a throwaway call because otherwise it times numba's JIT and asks for a
        # one-game chunk.
        if a["chunk"]:
            step = a["chunk"]
        else:
            probe_a, probe_f = make_games(na, a["k"], a["seed"], n_games,
                                          min(target, n_games + 8), nf)
            if not warmed[0]:
                player.play(openings[live[:1]], probe_a[:1], probe_f[:1])
                warmed[0] = True
            setup, per_game = player.calibrate(openings[live[0]], probe_a,
                                               probe_f)
            # big enough that setup stays under --memo-overhead of the work, and
            # that a chunk is at least a second so checkpointing is not the job
            step = max(1,
                       int(np.ceil(setup / (a["memo_overhead"] * per_game))),
                       int(np.ceil(MIN_CHUNK_SECONDS
                                   / (per_game * len(live)))))
            if step != said_step[0]:
                said_step[0] = step
                print("  game chunk %d for %d openings (setup %.4gs, %.4gs per "
                      "game per opening, so setup is %.0f%% of a chunk)"
                      % (step, len(live), setup, per_game,
                         100 * setup / (setup + step * per_game)))
        while n_games < target:
            hi = min(target, n_games + step)
            ans, fl = make_games(na, a["k"], a["seed"], n_games, hi, nf)
            sc = player.play(openings[live], ans, fl)
            while (sc < 0).any():
                nf *= 2
                print("  (coin-flip array regrown to %d)" % nf)
                ans, fl = make_games(na, a["k"], a["seed"], n_games, hi, nf)
                sc = player.play(openings[live], ans, fl)
            if paired is None:
                hist[:, n_games:hi] = sc
            else:
                paired = accumulate_pairwise(paired, sc)
            # n_games advances WITH the scores, in both phases, so a resume never
            # replays a chunk and never leaves the field ragged
            n_games = hi
            checkpoint()
            if time.time() - last_report > a["report"]:
                print("  %d/%d games of this block, %d openings each"
                      % (n_games, target, len(live)))
                last_report = time.time()

        # --- the cut, on the paired difference against the leader
        if paired is None:
            tot, sq = history_sums(hist, n_games)
            lead = int(np.argmin(tot))
            tot, sq, sum_d_l, sumsq_d_l = history_paired(hist, n_games, lead)
        else:
            sum_d, sumsq_d, tot, sq = paired
            lead = int(np.argmin(tot))
            sum_d_l, sumsq_d_l = sum_d[:, lead], sumsq_d[:, lead]
        md, se = paired_error(sum_d_l, sumsq_d_l, n_games)
        mean, ose = own_error(tot, sq, n_games)

        drop = eliminate(md, se, a["sigma"], lead)
        keep = ~drop
        rows = []
        for pos in np.flatnonzero(drop):
            c = int(live[pos])
            status[c] = "out"
            elim_at[c] = n_games
            sig = md[pos] / se[pos] if se[pos] > 0 else float("inf")
            rows.append((c, "%s,%d,%.6f,%.6f,%.6f,%.3f,%s"
                         % (names[c], n_games, mean[pos], md[pos], se[pos],
                            sig, names[int(live[lead])])))
            print("  OUT  %-14s %9.4f   %+.4f +/- %.4f  (%.1f sigma behind %s)"
                  % (names[c], mean[pos], md[pos], se[pos], sig,
                     names[int(live[lead])]))
        if rows and elim_path:
            with open(elim_path, "a") as f:
                f.write("\n".join(r[1] for r in rows) + "\n")
        if rows and is_answer[[c for c, _ in rows]].any() \
                and not is_answer[live[keep]].any():
            last = min((c for c, _ in rows if is_answer[c]),
                       key=lambda c: mean[int(np.flatnonzero(live == c)[0])])
            print("  ^^ %s was the LAST opening made only of answer words, "
                  "out at %d games" % (names[last], n_games))

        mean, ose, md, se = mean[keep], ose[keep], md[keep], se[keep]
        live = live[keep]
        lead = int(np.argmin(mean))
        if paired is None:
            hist = hist[keep]
        else:
            paired = tuple(x[np.ix_(keep, keep)] if x.ndim == 2 else x[keep]
                           for x in paired)

        order = np.argsort(mean, kind="stable")
        gap = sig2 = float("nan")
        if len(order) > 1:
            j = int(order[1])
            gap = mean[j] - mean[int(order[0])]
            sig2 = md[j] / se[j] if se[j] > 0 else float("inf")
        best_ans = [int(live[p]) for p in order if is_answer[int(live[p])]]
        print("%9d games  %6d live  leader %-14s %.4f (own se %.4f)  "
              "2nd is %.4f = %.1f paired sigma back  |  %s"
              % (n_games, len(live), names[int(live[lead])], mean[lead],
                 ose[lead], gap, sig2,
                 ("best answer opening %s" % names[best_ans[0]]) if best_ans
                 else "NO answer openings left"))

        if paired is None:
            mem = len(live) * n_games * 8 / 1e9
            if len(live) <= a["pair_at"] or mem > a["max_mem"]:
                paired = pairwise_from_history(hist, n_games)
                hist = np.zeros((0, 0), dtype=np.int16)
                print("  (switched to pairwise sums over %d openings -- memory "
                      "is now independent of the game count)" % len(live))
        checkpoint(force=True)
        write_standings(out, stem, a, names, status, elim_at, live, mean, ose,
                        md, se, is_answer, n_games, lead)
        if len(live) <= 1:
            break

    print("\n%d openings still live at %d games:" % (len(live), n_games))
    for c in live[:20]:
        print("   %s" % names[int(c)])


def write_standings(out, stem, a, names, status, elim_at, live, mean, ose, md,
                    se, is_answer, n_games, lead):
    """Every opening, live and eliminated, rewritten whole after each block."""
    if not out:
        return
    pos = {int(c): i for i, c in enumerate(live)}
    rows = []
    for c in range(len(names)):
        if c in pos:
            i = pos[c]
            sig = md[i] / se[i] if se[i] > 0 else 0.0
            rows.append((0, mean[i], "%s,live,%d,%.6f,%.6f,%.6f,%.6f,%.3f,%d"
                         % (names[c], n_games, mean[i], ose[i], md[i], se[i],
                            sig, int(is_answer[c]))))
        else:
            rows.append((1, -float(elim_at[c]), "%s,out,%d,,,,,,%d"
                         % (names[c], elim_at[c], int(is_answer[c]))))
    rows.sort(key=lambda r: (r[0], r[1]))
    with open(out + ".tmp", "w") as f:
        f.write("# %s\n" % stem)
        f.write("# settings strategy=%s boards=%d sigma=%g block=%d growth=%g "
                "seed=%d openings=%s top=%s\n"
                % (a["strategy"], a["k"], a["sigma"], a["block"], a["growth"],
                   a["seed"], a["openings"], a["top"]))
        f.write("# mean/stderr are the opening's OWN numbers; diff_vs_leader, "
                "paired_stderr and sigma are PAIRED against %s, and the cut uses "
                "the paired sigma\n" % names[int(live[lead])])
        f.write("# the leader is the best of the openings ENTERED, judged on the "
                "games actually played -- a screen, not a proof\n")
        f.write(COLUMNS + "\n")
        f.write("\n".join(r[2] for r in rows) + "\n")
    os.replace(out + ".tmp", out)


if __name__ == "__main__":
    main(sys.argv[1:])
