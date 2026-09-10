"""Sweep OPENINGS: the same fixed number of single-board games for every one.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-wordle-sweep.sh --fallback answer -t 100      # from math/
    bash solver/run-wordle-sweep.sh --fallback guess  -t 100

Every entry of the list opens `-t` games, played out by the FOLLOW-UP named by
--fallback (math/wordlesim.py has the protocol; the rule is `FixedOpening`, which
plays the entry's words in order and declines thereafter).  Each gets a row with
its mean guesses AND its win rate, both with standard errors.

AN ENTRY MAY BE SEVERAL WORDS.  A line of the `--words` file holding more than one
word is an OPENING played BLIND in order -- so the same sweep ranks single openers
and two-word openings, and the CSV's `word` column simply holds the whole opening,
space separated.  The shortlist writes those lines back out verbatim, so every
later pass reads them the same way and the cascade is identical either way.

WHERE A LIST OF PAIRS COMES FROM, and the blind spot in it.  There are 84,129,906
pairs, far too many to sweep, so a pair run screens the top N of an EXISTING
ranking (`tools/opening_list.py`, over data/shared/singletons/*.csv).  That
ranking answers a DIFFERENT question -- how many answers a blind opening isolates
to a singleton -- so the best pair for THIS objective need not be near its head,
and a pair outside the top N is never examined at all.  Say "the best of the N
screened", never "the best pair".

--second-from SWEEPS A DIFFERENT RULE, and it is opt-in.  Given a second-word
table (math/secondword.py, built by solver/run-second-word.sh) every swept opener
is played under `SecondWordOnGrays` instead of `FixedOpening`: the opener, then
THAT opener's predetermined word whenever the reply shows the table's threshold
worth of greys, then the follow-up.  It is a different strategy, so it lands in
the stem and in the `# settings` line, and a later pass INHERITS it from its
source -- the scar that split the win-rate cascade into two strategies spliced
together.  The table's own opener pool is checked against the list being swept,
so a `mystery` table cannot be swept over the 12972 by accident.

THE FOLLOW-UP IS PART OF THE QUESTION, not a detail: "which opener is best" has a
different answer under a random compatible ANSWER than under a random compatible
GUESS, because the opener is feeding a different player.  So it is required, it
is in the filename, and two sweeps that differ in it are two different screens.

COMMON RANDOM NUMBERS, and why a cell differs slightly from a standalone run.
Every opener faces the IDENTICAL sequence of `-t` answers: the draw stream is
re-seeded per word and kept SEPARATE from the stream the follow-up's random picks
consume, so one opener's picks cannot shift another's answers.  Each word's mean
is still an unbiased estimate of the same quantity, but the DIFFERENCE between
two words is far less noisy than their two standard errors suggest, because they
saw the same games.  tools/wordle_sim.py draws both from one stream, so a sweep
cell and a run-wordle-sim.sh run at the same seed are different samples and will
not match to the last digit.

THE WINNER'S CURSE IS REAL HERE, so read the head of the ranking carefully.  With
12972 words estimated at `-t` trials each, the best-looking mean is biased
optimistic: it belongs to whichever word got the kindest sample, and at small `-t`
the spread of pure noise across 12972 words is many times one word's standard
error.  **The head of a sweep is a SHORTLIST, not a winner.**  The sound use is
two-stage: sweep wide at small `-t` to screen, cut a generous shortlist
(tools/sweep_shortlist.py; the wrapper's default is 5 standard errors, measured
against the alternative -- 10 kept 95% of the field at t=100), then re-run the
survivors at larger `-t` and a FRESH SEED, repeating until the field is small
enough to separate.  A word that leads every stage is a finding; a word that leads only the
screen is a coin flip.

TWO NUMBERS MEANS TWO POSSIBLE SHORTLISTS.  The mean and the win rate are ranked
by different columns and need not agree, so the cut names which one it used
(--value on the shortlist tool) and that lands in the stage-2 filename.  Do not
cut on one and report the other.

ORDER.  Entries are visited in the LIST'S OWN ORDER -- alphabetical for the word
lists, best-first for a shortlist -- so --limit takes a prefix of that, never a
sample.  Nothing about the order favours any word: every one gets the same trials
and the same games.

RESUMABLE.  One CSV row per word, flushed as it is finished, and a re-run skips
words already in the file -- so a Ctrl-C costs at most the word in flight.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402
from wordle_sim import summarise  # noqa: E402
from secondword import read_table  # noqa: E402
from wordlesim import (WIN_WITHIN, answer_to_guess, draw_answer,  # noqa: E402
                       make_opening_rule, make_tail, play_game,
                       second_rule_for)

COLUMNS = ("word,trials,mean,stderr,sd,min,median,max,"
           "win_rate,win_rate_stderr,wins,seconds")
# Offset for the pick stream so it cannot be the draw stream by another name.
PICK_OFFSET = 1 << 20


def parse_args(argv):
    t = None
    fallback = None
    adapt = 0
    second_from = ""
    root = ""
    passno = 1
    source = ""
    rank = "mean"
    seed = 0
    words = "guess"
    limit = None
    win_within = WIN_WITHIN
    out = None
    progress = 100          # --progress 1 prints a line per word
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--rank":
            rank = argv[i + 1]; i += 2
        elif a == "--root":
            root = argv[i + 1]; i += 2
        elif a == "--pass":
            passno = int(argv[i + 1]); i += 2
        elif a == "--source":
            source = argv[i + 1]; i += 2
        elif a == "--pair-adaptive":
            adapt = int(argv[i + 1]); i += 2
        elif a == "--second-from":
            second_from = argv[i + 1]; i += 2
        elif a == "--fallback":
            fallback = argv[i + 1]; i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--words":
            words = argv[i + 1]; i += 2
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 2
        elif a == "--win-within":
            win_within = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if t is None or t < 1:
        raise SystemExit("-t (trials per word) is required and must be >= 1")
    if not fallback:
        raise SystemExit(
            "--fallback is required: the opener feeds a different player under "
            "each follow-up, so it is part of the question.\n"
            "Use the wrapper: bash solver/run-wordle-sweep.sh --fallback answer -t 100")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-wordle-sweep.sh")
    if rank not in ("mean", "win_rate"):
        raise SystemExit("--rank must be 'mean' or 'win_rate'")
    if second_from and adapt:
        # Two rules for the same turn.  --pair-adaptive abandons a blind opening
        # once the field is tiny; this plays a fixed word off the opener's reply.
        # Whatever the combination would mean, it is a THIRD strategy and would
        # need its own name and its own filename.
        raise SystemExit("--second-from and --pair-adaptive are two different "
                         "rules for the second word; pick one")
    return (t, fallback, adapt, seed, words, limit, win_within, out, progress,
            root, passno, source, rank, second_from)


def load_done(path):
    """Words already recorded in an existing CSV, so a re-run resumes."""
    done = set()
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("word,"):
                    continue
                w = line.split(",", 1)[0].strip()
                if w:
                    done.add(w)
    return done


def sweep_word(pat, ans2g, na, t, seed, opening_g, tail, win_within, adapt=0,
               make_rule=None):
    """One opening's t games, against the seed's fixed sequence of answer draws.

    `opening_g` is a list of guess indices -- one for a plain opener sweep, more
    for an opening.  The draw stream is re-seeded here, so every entry of the
    sweep faces the identical games however many words it plays.

    `make_rule` swaps in a DIFFERENT rule for the same opening -- what
    --second-from does -- and is built once in main() so this loop does not know
    which strategy is being swept.  Left out, it is the blind/adaptive opening
    every earlier sweep here ran, unchanged.
    """
    draw_rng = np.random.default_rng(seed)
    pick_rng = np.random.default_rng(seed + PICK_OFFSET)
    rule = (make_rule(opening_g) if make_rule
            else make_opening_rule(opening_g, tail=tail, adapt=adapt))
    scores = []
    for _ in range(t):
        answer_idx = draw_answer(na, draw_rng)
        played, _ = play_game(pat, ans2g, answer_idx, rule, tail, pick_rng)
        scores.append(len(played))
    return summarise(scores, win_within)


def main(argv):
    (t, fallback, adapt, seed, words, limit, win_within, out, progress,
     root, passno, source, rank, second_from) = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    if words in ("guess", "mystery"):
        sweep_words = load_words(words)
    else:
        with open(words) as f:
            sweep_words = [ln.strip() for ln in f if ln.strip()]
    # An entry is an OPENING: one word, or several played blind in order.  Kept as
    # the space-joined string it arrived as, which is what the CSV records and
    # what a shortlist writes back, so a pass reads exactly what the last wrote.
    openings = [w.split() for w in sweep_words]
    pos = {w: i for i, w in enumerate(guesses)}
    bad = [w for o in openings for w in o if w not in pos]
    if bad:
        raise SystemExit("%d swept words are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))
    dup = [" ".join(o) for o in openings if len(set(o)) != len(o)]
    if dup:
        raise SystemExit("%d openings repeat a word, e.g. %s"
                         % (len(dup), dup[0]))
    sizes = sorted({len(o) for o in openings})
    if len(sizes) > 1:
        # Mixing them would rank a 1-word opening against a 2-word one, which is
        # a comparison between two different strategies rather than a sweep.
        raise SystemExit("the list mixes openings of %s words; a sweep ranks "
                         "openings of ONE size" % " and ".join(map(str, sizes)))

    if adapt and sizes[0] < 2:
        raise SystemExit("--pair-adaptive needs an opening of at least 2 words: "
                         "there is no later word to abandon")

    # --second-from: the rule is built per opener from the TABLE, and the table
    # is read once.  second_rule_for refuses an opener it has no row for, which
    # is what stops one variant's table being swept over the other's word list.
    table = make_rule = None
    if second_from:
        if sizes[0] != 1:
            raise SystemExit("--second-from sweeps ONE opener per entry; this "
                             "list holds openings of %d words" % sizes[0])
        table = read_table(second_from)
        make_rule = lambda opening_g: second_rule_for(opening_g, table, guesses)

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    tail = make_tail(fallback, guesses, answers, ans2g)
    na = len(answers)

    if limit is not None:
        sweep_words = sweep_words[:limit]
    if table:
        # UP FRONT, not when the sweep reaches the first opener with no row: a
        # table built over one pool and swept over another would otherwise write
        # rows for a while and then die, leaving a partial CSV that looks like a
        # run someone killed.
        missing = [w for w in sweep_words if w.split()[0] not in table.rows]
        if missing:
            raise SystemExit(
                "%d of the %d openings have no row in %s (e.g. %s).\n"
                "It was built over the %s opener pool -- sweep the matching word "
                "list, or build the table for this one."
                % (len(missing), len(sweep_words), second_from,
                   " ".join(missing[:5]), table.openers))
    done = load_done(out)
    todo = [w for w in sweep_words if " ".join(w.split()) not in done]

    fh = None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fresh = not os.path.exists(out)
        fh = open(out, "a")
        if fresh:
            fh.write("# wordle opener sweep: %d trials per word, follow-up %s, "
                     "seed %d\n" % (t, fallback, seed))
            # THE LINEAGE, in the file rather than in the filename.  Each pass
            # used to nest its whole ancestry into the name, which grew without
            # bound and died at macOS's 255-byte limit on pass 6.  Root plus pass
            # number is the same information in constant size, and `source` names
            # the immediate parent, whose own header names ITS parent -- so the
            # chain is still walkable, one file at a time.
            fh.write("# lineage root=%s pass=%d source=%s\n"
                     % (root or "(first)", passno, source or "(none)"))
            # MACHINE-READABLE, beside the prose.  Everything a later tool needs
            # to reproduce this run's STRATEGY, in one line that no rewording of
            # the paragraphs below can break.
            fh.write("# settings follow_up=%s pair_adaptive=%d win_within=%d "
                     "trials=%d seed=%d words=%d rank=%s second_table=%s "
                     "fire=%s\n"
                     % (fallback, adapt, win_within, t, seed, len(sweep_words),
                        rank, second_from or "-",
                        table.fire if table else "-"))
            if table:
                fh.write("# each opener plays the PREDETERMINED second word from "
                         "%s whenever its\n# reply fires %s, and declines to the "
                         "follow-up otherwise\n"
                         "# (math/secondword.py; pools openers=%s seconds=%s)\n"
                         % (second_from, table.fire, table.openers,
                            table.seconds))
            if table:
                pass                       # the table's own lines above say it
            elif adapt:
                fh.write("# %d-word openings, played in order but ABANDONED once "
                         "the follow-up is down to %d\n# or fewer words "
                         "(--pair-adaptive, the rule in data/shared/PAIRS.md); "
                         "ORDER MATTERS, so\n# a b and b a are different rows\n"
                         % (sizes[0], adapt))
            else:
                fh.write("# %d-word openings, played BLIND in order; the follow-up "
                         "plays the rest (math/wordlesim.py)\n" % sizes[0])
            fh.write("# every opening faces the SAME %d answers, drawn from the "
                     "2315 mystery words (common random numbers)\n" % t)
            if sizes[0] > 1:
                fh.write("# the candidate openings came from %s -- a screen of an "
                         "existing ranking, so this is\n# the best of those "
                         "examined, never the best opening\n" % words)
            fh.write("# NO guess cap: win_rate is the fraction of untruncated "
                     "scores at %d guesses or fewer\n" % win_within)
            fh.write("# the head is a SHORTLIST, not a winner -- see the "
                     "winner's-curse note in tools/wordle_sweep.py\n")
            fh.write(COLUMNS + "\n")
        fh.flush()

    print("ranking on %s" % ("WIN RATE" if rank == "win_rate" else "mean guesses"))
    print("sweep: %d %s x %d trials, follow-up %s, seed %d%s"
          % (len(todo), "openings of %d words" % sizes[0] if sizes[0] > 1 else "words",
             t, fallback, seed,
             ", second word firing on %s from %s" % (table.fire, second_from)
             if table else (", pair-adaptive %d" % adapt if adapt else ", blind")))
    if done and not todo:
        # SAY SO PLAINLY.  This used to print "resuming: N words already in ..."
        # and then "0 words in 0.0s", which reads like a failed run rather than a
        # finished one -- and a re-run of an already-finished pass is the single
        # easiest mistake to make when several cascades are in flight.
        print("ALREADY COMPLETE: all %d openings are in %s" % (len(done), out))
        print("  nothing to do.  The next pass reads THIS file with "
              "--shortlist-from.")
        return
    if done:
        print("  resuming: %d of %d openings already in %s"
              % (len(done), len(sweep_words), out))

    t0 = time.time()
    best = []
    for i, w in enumerate(todo):
        w0 = time.time()
        st = sweep_word(pat, ans2g, na, t, seed, [pos[x] for x in w.split()],
                        tail, win_within, adapt, make_rule)
        dt = time.time() - w0
        if fh:
            fh.write("%s,%d,%.6f,%.6f,%.6f,%d,%.1f,%d,%.6f,%.6f,%d,%.3f\n"
                     % (" ".join(w.split()), t,
                        st["mean_guesses"], st["stderr"], st["sd"],
                        st["min"], st["median"], st["max"],
                        st["win_rate"], st["win_stderr"], st["wins"], dt))
            fh.flush()
        best.append((st["mean_guesses"], st["win_rate"], w))
        if progress and (i + 1) % progress == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            # the LEADER is whichever the run is ranking on -- the other number is
            # still recorded, but a run that cuts on win rate must not print a
            # leader chosen by the mean
            if rank == "win_rate":
                bw, bm, bword = max((w_, -m_, x) for m_, w_, x in best)
                bm = -bm
            else:
                bm, bw, bword = min(best)
            print("  %d/%d  %-12s %.4f  %5.1f%%   best %s %.4f  %5.1f%%   "
                  "%.1f/s  eta %.1f min"
                  % (i + 1, len(todo), w, st["mean_guesses"],
                     100.0 * st["win_rate"], bword, bm, 100.0 * bw, rate,
                     (len(todo) - i - 1) / rate / 60))

    print("\n%d words in %.1fs" % (len(todo), time.time() - t0))
    if best:
        print("best %d by mean of the words swept THIS RUN (a shortlist, not a "
              "winner -- see the module docstring):" % min(20, len(best)))
        for mean, wr, w in sorted(best)[:20]:
            print("  %-12s mean %.4f   win %6.2f%%" % (w, mean, 100.0 * wr))
        print("best %d by win rate (a DIFFERENT ranking of the same games):"
              % min(20, len(best)))
        for mean, wr, w in sorted(best, key=lambda r: (-r[1], r[0]))[:20]:
            print("  %-12s win %6.2f%%   mean %.4f" % (w, 100.0 * wr, mean))
    if fh:
        fh.close()
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
