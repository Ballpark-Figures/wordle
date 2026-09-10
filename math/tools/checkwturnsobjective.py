"""GATE: `WturnsGame` must compute the SAME objective as `topk.py`.

    python3 tools/checkwturnsobjective.py        # from math/

`math/wturns_objective.py` swaps the adversarial search's objective from
`topk.py`'s numba kernels to `solver/wturns --topk K`. That is only sound if the
two are the same guesser -- and they are by construction: wturns ranks guesses by
ascending sum over LOSING bins of (bin size x bin weight), which is topk.py's
rule, and at K=1 neither minimises anything, both just play the top-ranked guess.

"By construction" is exactly the sort of claim that quietly stops being true, so
this diffs them EXACTLY -- on the weighted totals, never on the CSV's 5-decimal
`expected`. A hill-climb compares improvements far finer than 1e-5, so agreeing
to five decimals would not be agreement at all.

THE PROBLEM IS SIZED SO THE BEAM ACTUALLY MATTERS, and that took measuring.
checkweighted.py's 24x16 problem is solved optimally by the greedy, so k=1, 2, 3
and 5 all give the same number there and a "passing" comparison would have been
k=1 four times over. At 60 answers x 600 guesses the beam changes the answer for
every weight vector below, which is what makes the k>1 path meaningful.

COVERAGE IS ASSERTED: it FAILS if K never changed the answer, and if a zero
weight was never dropped.
"""
import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

from checkweighted import make_mini_data        # noqa: E402
from topk import TopKGame, read_words           # noqa: E402
from wordle import pattern                      # noqa: E402
import wturns_objective                         # noqa: E402

NA, NG, SEED = 60, 600, 7          # measured to make the beam bite; see above
KS = (1, 2, 3)

FAILURES = []


def bad(m):
    FAILURES.append(m)
    print("FAIL: %s" % m)


def ok(m):
    print("ok: %s" % m)


def build():
    """A deterministic sub-problem drawn from the REAL lists, so every word is a
    real 5-letter word and the feedback is the real feedback."""
    rng = np.random.default_rng(SEED)
    ans_all = read_words(os.path.join(os.path.dirname(_HERE),
                                      "data", "shared", "words", "custom.txt"))
    gue_all = read_words(os.path.join(os.path.dirname(_HERE),
                                      "data", "shared", "words", "guess.txt"))
    ans = sorted(rng.choice(ans_all, NA, replace=False).tolist())
    gue = sorted(set(rng.choice(gue_all, NG, replace=False).tolist()) | set(ans))
    P = np.array([[pattern(g, a) for a in ans] for g in gue], dtype=np.uint8)
    return ans, gue, P


def main():
    ans, gue, P = build()
    tmp = tempfile.mkdtemp(prefix="checkwt-")
    data_dir = tempfile.mkdtemp(prefix="data-", dir=tmp)
    make_mini_data(data_dir, ans, gue)

    # Every weight is dyadic: the solver is exact in integers and REFUSES a weight
    # it cannot scale, so a non-dyadic vector would fail the run, not the check.
    vectors = {
        "uniform": [1.0] * NA,
        "spiky":   [float(2 ** (-(i % 7))) for i in range(NA)],
        "zeroed":  [0.0 if i % 9 == 0 else 1.0 for i in range(NA)],
    }

    seen_k_effect = False
    seen_zero_drop = False

    for wname, w in vectors.items():
        if any(x == 0 for x in w):
            seen_zero_drop = True
        per_k = {}
        for k in KS:
            py = TopKGame(answers=ans, guesses=gue, k=k, patterns=P).total_cost(w)
            c_game = wturns_objective.WturnsGame(
                answers=ans, guesses=gue, patterns=P, data=data_dir,
                k=k, depth=9, threads=1, tt_bits=20,
                workdir=tempfile.mkdtemp(prefix="wt-", dir=tmp))
            try:
                c = c_game.total_cost(w)
            except Exception as e:                        # noqa: BLE001
                bad("%s k=%d: wturns objective raised: %s" % (wname, k, e))
                continue
            per_k[k] = py
            if abs(c - py) > 1e-9:
                bad("%s k=%d: topk.py %.10f vs wturns %.10f -- the two objectives "
                    "have parted company" % (wname, k, py, c))
            else:
                ok("%s k=%d: identical total (%.4f)" % (wname, k, py))
        if len(set(per_k.values())) > 1:
            seen_k_effect = True
            ok("  %s: K changes the answer (%s), so the beam was exercised"
               % (wname, " -> ".join("%g" % per_k[k] for k in sorted(per_k))))

    if not seen_k_effect:
        bad("COVERAGE: no weight vector made K change the answer, so every "
            "comparison above was k=1 in disguise and the beam is untested")
    if not seen_zero_drop:
        bad("COVERAGE: no zero weight appeared, so the drop path is untested")

    print()
    if FAILURES:
        print("FAILED (%d)" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("ALL wturns-objective CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
