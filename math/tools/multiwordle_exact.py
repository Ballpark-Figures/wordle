"""EXACT expected guesses per opener -- no sampling, where sampling is unnecessary.

    bash solver/run-multiwordle-exact.sh --strategy minavg     # from math/

At k=1 the game has ONE hidden answer drawn uniformly from the 2315 mystery
words, so "expected guesses" is an average over 2315 equally likely games and
nothing more.  If the strategy is DETERMINISTIC, those 2315 games are the entire
population: playing every one of them gives the exact mean, not an estimate.

WHAT THAT BUYS, and it is the whole reason this file exists.  A race over 12972
openers spends its whole life managing the fact that it is comparing noisy
estimates -- standard errors, a 5-sigma cut, the winner's curse, a leader that
moves because it got lucky.  None of that applies here.  Every number below is
the true value of the quantity, so the best opener is THE best opener among the
12972, and it is a fact rather than a screen.  2315 games per opener is also
cheaper than the race would have been: about 0.24 s per opener, so under an hour
for the whole guess list.

WHY IT REFUSES EVERYTHING ELSE, rather than quietly doing something weaker:

  * A RANDOMISED strategy (`greedy`, `srank`) has a distribution over the
    strategy's own coin flips as well as over the answer, so enumerating the 2315
    answers once does NOT give its mean -- it gives one sample of it.  Those
    belong in the race, which is honest about being a sample.
  * k > 1 draws k answers WITHOUT replacement, so the population is C(2315, k):
    2.7 million at k=2 and past 10^18 by k=8.  Enumeration is not available and
    the race is the right tool.

So this covers exactly one cell -- `minavg` at k=1 -- and says so rather than
generalising into an approximation wearing an exact name.  Each row is the true
mean; there is no standard error column because there is no error.
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
from multiwordle_race import load_openings, list_name           # noqa: E402
from multiwordle_sweep import load_done                         # noqa: E402
from wordle import load_words                                   # noqa: E402

COLUMNS = "word,answers,total,mean,min,max,is_answer,seconds"

# Deterministic rules only: see the module docstring.  This is a list rather than
# a flag because it is a property of the RULE, not a thing to be overridden.
DETERMINISTIC = (mw.MINAVG,)


def parse_args(argv):
    a = {"strategy": None, "k": 1, "openings": "guess", "top": None,
         "out": None, "progress": 100, "dry_run": False}
    i = 0
    while i < len(argv):
        f = argv[i]
        if f == "--strategy":
            a["strategy"] = argv[i + 1]; i += 2
        elif f in ("-k", "--boards"):
            a["k"] = int(argv[i + 1]); i += 2
        elif f in ("--openings", "--words", "--openings-from"):
            a["openings"] = argv[i + 1]; i += 2
        elif f == "--top":
            a["top"] = int(argv[i + 1]); i += 2
        elif f == "--out":
            a["out"] = argv[i + 1]; i += 2
        elif f == "--no-out":
            a["out"] = False; i += 1
        elif f == "--progress":
            a["progress"] = int(argv[i + 1]); i += 2
        elif f == "--dry-run":
            a["dry_run"] = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % f)
    if a["strategy"] not in mw.STRATEGIES:
        raise SystemExit("--strategy is required: one of %s"
                         % ", ".join(mw.STRATEGIES))
    if a["strategy"] not in DETERMINISTIC:
        raise SystemExit(
            "%r is randomised, so enumerating the 2315 answers gives ONE SAMPLE "
            "of its mean, not the mean.\nUse the race, which is honest about "
            "sampling: bash solver/run-multiwordle-race.sh --strategy %s"
            % (a["strategy"], a["strategy"]))
    if a["k"] != 1:
        raise SystemExit(
            "k=%d draws %d answers without replacement, so the population is "
            "C(2315, %d) and cannot be enumerated.\nExact evaluation exists only "
            "at k=1; use the race for k>1."
            % (a["k"], a["k"], a["k"]))
    if a["out"] is None:
        raise SystemExit("--out is required (or --no-out).\nUse the wrapper: "
                         "bash solver/run-multiwordle-exact.sh")
    return a


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    answer_set = set(answers)
    na = len(answers)

    field = load_openings(a["openings"], a["top"], guesses)
    if any(len(o) != 1 for o in field):
        raise SystemExit("exact evaluation takes one-word openings only")
    bad = sorted({w for o in field for w in o if w not in guesses})
    if bad:
        raise SystemExit("%d openings are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))

    print("exact: %s at k=1 over %d openings from %s"
          % (a["strategy"], len(field), a["openings"]))
    print("  every opener plays all %d answers -- these are TRUE means, not "
          "estimates" % na)
    if a["out"]:
        print("  out %s" % a["out"])
    if a["dry_run"]:
        print("\n--dry-run: stopping before any game is played")
        return

    pat = np.array(load_patterns())
    pool = np.arange(len(guesses), dtype=np.int64)
    # every answer, once each: the whole population, in answer-list order
    every = np.arange(na, dtype=np.int64).reshape(na, 1)

    done = load_done(a["out"]) if a["out"] else set()
    todo = [o for o in field if o[0] not in done]
    fh = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        fresh = not os.path.exists(a["out"])
        fh = open(a["out"], "a")
        if fresh:
            fh.write("# multiwordle EXACT expected guesses, %s at k=1\n"
                     % a["strategy"])
            fh.write("# settings strategy=%s boards=1 answers=%d openings=%s "
                     "top=%s\n" % (a["strategy"], na, a["openings"], a["top"]))
            fh.write("# every opener plays all %d answers once, so mean is the "
                     "TRUE expected guesses -- no sampling, no standard error, "
                     "and the best row is the best opener rather than a screen\n"
                     % na)
            fh.write(COLUMNS + "\n")
        fh.flush()
    if done:
        print("  resuming: %d openers already in the file" % len(done))

    scores = np.empty(na, dtype=np.int64)
    best = []
    t0 = time.time()
    for i, o in enumerate(todo):
        w0 = time.time()
        og = np.array([guesses.index(o[0])], dtype=np.int64)
        t2 = mf.turn2_table(pat, int(og[0]), pool)
        mf.run_minavg_games(pat, every, og, pool, t2, True, scores)
        assert (scores > 0).all(), "a game returned no score"
        total = int(scores.sum())
        dt = time.time() - w0
        if fh:
            fh.write("%s,%d,%d,%.6f,%d,%d,%d,%.3f\n"
                     % (o[0], na, total, total / na, int(scores.min()),
                        int(scores.max()), int(o[0] in answer_set), dt))
            fh.flush()
        best.append((total / na, o[0]))
        if a["progress"] and (i + 1) % a["progress"] == 0:
            rate = (i + 1) / (time.time() - t0)
            print("  %d/%d  %-8s %.4f   best so far %s %.4f   %.1f/s  "
                  "eta %.1f min"
                  % (i + 1, len(todo), o[0], total / na, min(best)[1],
                     min(best)[0], rate, (len(todo) - i - 1) / rate / 60))

    print("\n%d openers in %.1fs" % (len(todo), time.time() - t0))
    if best:
        print("best %d of the openers evaluated THIS RUN (exact means):"
              % min(20, len(best)))
        for m, w in sorted(best)[:20]:
            print("  %-8s %.4f%s" % (w, m, "  (an answer word)"
                                     if w in answer_set else ""))
    if fh:
        fh.close()
        print("wrote %s" % a["out"])


if __name__ == "__main__":
    main(sys.argv[1:])
