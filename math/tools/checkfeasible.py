"""The gate for `optturns --feasible`.

--feasible DECIDES "can this opener resolve every answer within --depth" instead
of MINIMISING the total.  The claim being checked is that it is EXACT IN BOTH
DIRECTIONS -- unlike --topk, which can only ever prove the yes:

    --feasible says INFEASIBLE   <=>   the exact search says INFEASIBLE

and that the number it reports alongside a yes is a WITNESS total, i.e. an
upper bound on the optimum rather than the optimum.

The oracle is the exact solver itself, on the same miniature `--data` problem
`checkweighted.py` builds.  That is the right oracle precisely because the two
share the recursion: the ONLY difference is when the guess loop stops, so a
disagreement isolates the stopping rule rather than the search.

TWO PROBLEMS, AND THE SECOND IS NOT OPTIONAL.  On the 24x16 problem the first
guess the search tries (the lowest lower bound) is ALWAYS already optimal, so
both stopping rules fire in the same place and the witness total never differs
from the optimum -- a "pass" there is the exact search run twice.  Measured:
0 of 72 solvable cells were loose.  The 60x600 problem drawn from the real
lists is where the short-circuit actually bites.  Same lesson, same shape, as
checkwturnsobjective.py's note about the beam.

COVERAGE IS ASSERTED across both problems: the yes direction, the no direction,
and -- load-bearing -- that the witness was somewhere strictly looser than the
optimum, which is the only evidence the short-circuit ever fired.

    python3 tools/checkfeasible.py
"""
import os
import shutil
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

from checkweighted import (MINI_GUESSES, WEIGHT_SETS,          # noqa: E402
                           make_mini_data, ordered_answers, run)
from topk import read_words                                    # noqa: E402
from wordle import pattern                                     # noqa: E402

MATH = os.path.dirname(_HERE)
BIN = os.path.join(MATH, "solver", "optturns")

SEED = 20260919
BIG_NA, BIG_NG, BIG_OPENERS = 60, 600, 40


def verdict(text):
    """(total, infeasible) from a single-opener run's output."""
    for line in text.splitlines():
        if "INFEASIBLE" in line:
            return None, True
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("total="):
            return int(parts[1].split("=", 1)[1]), False
    return None, None            # said nothing -- a failure, not a verdict


def compare(data, openers, depths, label):
    """Run both stopping rules over every (opener, depth) and diff the verdicts."""
    yes = no = loose = 0
    bad = []
    for d in depths:
        for w in openers:
            args = ["--opener", w, "--depth", str(d), "--depth-max", str(d)]
            ex = run(BIN, args, data)
            fe = run(BIN, args + ["--feasible"], data)
            et, einf = verdict(ex.stdout)
            ft, finf = verdict(fe.stdout)

            if einf is None or finf is None:
                bad.append("%s %s d=%d: no verdict (exact rc/err %r)"
                           % (label, w, d, ex.stderr.strip()[:70]))
                continue
            if einf != finf:
                bad.append("%s %s d=%d: exact %s but --feasible %s"
                           % (label, w, d, "INFEASIBLE" if einf else "solvable",
                              "INFEASIBLE" if finf else "solvable"))
                continue
            if einf:
                no += 1
                continue
            yes += 1
            if ft < et:
                bad.append("%s %s d=%d: witness %d BELOW the optimum %d"
                           % (label, w, d, ft, et))
            elif ft > et:
                loose += 1

    print("  %-6s %d cells: solvable %d, INFEASIBLE %d, witness loose %d"
          % (label, len(depths) * len(openers), yes, no, loose))
    return yes, no, loose, bad


def build_big():
    """A deterministic sub-problem from the REAL lists -- real words, real
    feedback -- sized so the lowest-bound guess is not always the optimum."""
    rng = np.random.default_rng(SEED)
    words = os.path.join(MATH, "data", "shared", "words")
    ans_all = read_words(os.path.join(words, "custom.txt"))
    gue_all = read_words(os.path.join(words, "guess.txt"))
    ans = sorted(rng.choice(ans_all, BIG_NA, replace=False).tolist())
    gue = sorted(set(rng.choice(gue_all, BIG_NG, replace=False).tolist()) | set(ans))
    return ans, gue


REAL_CSV = os.path.join(MATH, "data", "shared", "optturns", "opener_totals.csv")
REAL_WORDS = ("salet", "reast", "trace", "crate", "slate")


def check_real():
    """--feasible on the real lists at depth 6, against the committed optima.

    Every one of these is known solvable within 6, and its exact total is in
    opener_totals.csv -- so the decision and the upper-bound property are both
    checkable without running the exact search at all."""
    if not os.path.exists(os.path.join(MATH, "data", "local", "patterns",
                                       "patterns.npy")):
        print("  real   SKIPPED: no data/local/patterns/patterns.npy "
              "(run 'python3 build_patterns.py' from math/)")
        return 0, 0, 0, ["real-lists check could not run"]

    exact = {}
    with open(REAL_CSV) as f:
        next(f)
        for line in f:
            p = line.split(",")
            if len(p) > 1 and p[1]:
                exact[p[0]] = int(p[1])

    yes = loose = 0
    bad = []
    for w in REAL_WORDS:
        if w not in exact:
            bad.append("real %s: no committed depth-6 total to check against" % w)
            continue
        r = run(BIN, ["--opener", w, "--depth", "6", "--depth-max", "6",
                      "--feasible", "--tt-bits", "24"])
        ft, finf = verdict(r.stdout)
        if finf is None:
            bad.append("real %s: no verdict (%r)" % (w, r.stderr.strip()[:70]))
        elif finf:
            bad.append("real %s: --feasible says INFEASIBLE at depth 6, but the "
                       "committed sweep solved it at %d" % (w, exact[w]))
        else:
            yes += 1
            if ft < exact[w]:
                bad.append("real %s: witness %d BELOW the committed optimum %d"
                           % (w, ft, exact[w]))
            elif ft > exact[w]:
                loose += 1
    print("  real   %d openers at depth 6: solvable %d, witness loose %d"
          % (len(REAL_WORDS), yes, loose))
    return yes, 0, loose, bad


def main():
    if not os.path.exists(BIN):
        print("no solver binary -- run 'sh build.sh' in solver/")
        return 1

    tmp = tempfile.mkdtemp(prefix="checkfeas-")
    try:
        yes = no = loose = 0
        bad = []

        # 1. the 24x16 problem: cheap, and the only place INFEASIBLE is common
        small = tempfile.mkdtemp(prefix="small-", dir=tmp)
        answers, _ = ordered_answers(WEIGHT_SETS["uniform"])
        make_mini_data(small, answers)
        y, n, l, b = compare(small, MINI_GUESSES, (2, 3, 4, 5), "24x16")
        yes, no, loose, bad = yes + y, no + n, loose + l, bad + b

        # 2. the 60x600 problem: real words, real feedback, a middle scale
        big = tempfile.mkdtemp(prefix="big-", dir=tmp)
        ans, gue = build_big()
        make_mini_data(big, ans, gue)
        y, n, l, b = compare(big, gue[:BIG_OPENERS], (3, 4), "60x600")
        yes, no, loose, bad = yes + y, no + n, loose + l, bad + b

        # 3. THE REAL LISTS, against the COMMITTED depth-6 optima.  This is the
        # only check where the short-circuit actually fires: the buckets below
        # a real opener stay large enough for the guess loop to run, where both
        # mini problems fall into the n<=2 and d==2 closed forms almost at
        # once.  It costs no exact search -- the oracle is already on disk.
        y, n, l, b = check_real()
        yes, no, loose, bad = yes + y, no + n, loose + l, bad + b

        for x in bad:
            print("  FAIL", x)

        cov = []
        if not yes:
            cov.append("nothing was solvable -- the yes direction went untested")
        if not no:
            cov.append("nothing was INFEASIBLE -- the no direction went untested")
        if not loose:
            cov.append("the witness total NEVER differed from the optimum -- the "
                       "short-circuit never fired, so this run proves nothing")
        for c in cov:
            print("  FAIL coverage:", c)

        if bad or cov:
            print("FAILED")
            return 1
        print("OK")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
