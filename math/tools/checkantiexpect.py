"""Gate for `solver/antiexpect` — the C expectimax against the Python reference.

`antiwordle_expect.py` is the ORACLE: slower by orders of magnitude, but checked in
its own right by tools/checkantiwordleexpect.py (against an independently written
brute force, against replaying its own strategy, and for monotonicity in K). That
makes it exactly what a port needs — a second implementation whose answers are
already trusted.

WHAT IS DIFFED, on the SAME problem: same 12972-word guess list, the same first N
answers, the same ranking, the same K.

  THE VALUE, to full precision. An expected-turns figure that agrees to six decimals
  and no further is not evidence of much; the C prints ten so the comparison is
  limited by the computation rather than the printout. (It was limited by the
  printout at first, and a passing case looked like a failure.)

  THE OPENER. Not required to match if two guesses tie, but with a deterministic
  ranking and lowest-index tie-breaks on both sides it should, and a divergence means
  the two are exploring different guesses even where they agree on the number.

  MONOTONICITY IN K, on the C alone. Top-K examines the K best-scoring legal words,
  and the top-5 contains the top-3, so a larger K searches a superset and the value
  can only rise. A drop means the restriction is not nested — the failure that a
  value-only diff at one K would sail straight past.

THE PROBLEM IS KEPT TINY (a handful of answers) because the reference is a plain
recursive Python expectimax. That is enough: the bug this caught in the C was
shared partition scratch, which corrupts any problem with more than one branch.

    python3 tools/checkantiexpect.py [--cases N]
"""
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import GuessSpace
from antiwordle_expect import expected_turns
from build_patterns import load_patterns
from wordle import load_words

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(MATH, "solver", "antiexpect")
ROW = re.compile(r"expected turns = ([\d.]+)\s+opener (\w+)")

FAILS = []


def run_c(nans, k, extra=()):
    """(value, opener) from the C binary on the first `nans` answers."""
    cmd = [BINARY, "-k", str(k), "--rank-none", "--no-out", "--answers", str(nans),
           "--data", "data", "--tt-bits", "20"] + list(extra)
    p = subprocess.run(cmd, cwd=MATH, capture_output=True, text=True)
    m = ROW.search(p.stdout)
    if not m:
        raise SystemExit("antiexpect gave no result:\n%s%s" % (p.stdout, p.stderr))
    return float(m.group(1)), m.group(2)


def main():
    argv = sys.argv[1:]
    cases = int(argv[argv.index("--cases") + 1]) if "--cases" in argv else 4

    guesses = load_words("guess")
    space = GuessSpace(guesses)
    pat = np.asarray(load_patterns())
    # --rank-none in the C is SCORE[g] = NG - g: alphabetical preference. Mirrored
    # here so both sides examine the same K guesses at every node.
    score = np.arange(len(guesses))[::-1].astype(float)

    print("antiexpect gate: C vs antiwordle_expect.py, same lists and ranking\n")
    plan = [(3, 2), (4, 2), (5, 3), (6, 2), (7, 2), (5, 4)][:cases]
    for nans, k in plan:
        cval, copener = run_c(nans, k)
        legal = np.ones(space.n, dtype=bool)
        alive = np.zeros(pat.shape[1], dtype=bool)
        alive[:nans] = True
        pval, pg = expected_turns(space, pat, legal, alive, score, k, "static", {})
        same_val = abs(cval - pval) < 1e-9
        same_open = copener == guesses[pg]
        ok = same_val and same_open
        print("  %s  answers=%d k=%d: C=%.9f (%s)  py=%.9f (%s)"
              % ("PASS" if ok else "FAIL", nans, k, cval, copener, pval, guesses[pg]))
        if not ok:
            FAILS.append("answers=%d k=%d: %s" % (
                nans, k, "value" if not same_val else "opener"))

    print("\n  monotone in K (C alone, answers=6):")
    vals = []
    for k in (1, 2, 3, 5):
        v, w = run_c(6, k)
        vals.append((k, v, w))
    bad = any(vals[i][1] > vals[i + 1][1] + 1e-9 for i in range(len(vals) - 1))
    print("    " + "  ".join("k=%d:%.6f" % (k, v) for k, v, _ in vals)
          + ("   NOT MONOTONE" if bad else "   ok"))
    if bad:
        FAILS.append("value fell as K rose")

    print()
    if FAILS:
        print("FAILED: %d case(s): %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("C port agrees with the reference on every case")
    return 0


if __name__ == "__main__":
    sys.exit(main())
