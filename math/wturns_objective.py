"""Evaluate the adversarial objective with the C solver instead of `topk.py`.

`freq_search.py` maximises what a top-K guesser spends against a weight vector.
That guesser exists twice: as `topk.py`'s numba kernels, and -- this is the part
that is easy to miss -- as `solver/wturns` under `--topk K`, whose ranking rule
IS `topk.py`'s (ascending sum over LOSING bins of bin size x bin weight, ties on
the lowest guess index).  At K=1 the beam does no minimising at all, so both
simply play the top-ranked guess at every node.  MEASURED on the real lists: the
k=1 hill-climb's final value is 3.978171252747317 and `wturns --topk 1` on those
same weights reports 3.97817.  They are the same guesser.

WHY BOTHER.  The C one has a transposition table and OpenMP; the Python one has
neither ("no transposition table yet"), and runs on one core.  MEASURED at k=10
on the real problem: one `topk.py` evaluation takes ~370 s single-threaded, while
`wturns --topk 10` solves its ten openers in 4.3-5.3 s each across 18 threads.
Same search, ~8x the CPU efficiency and ~18x the parallelism.

THE INTERFACE IS TopKGame's, DELIBERATELY.  `FrequencySearch` already accepts
`game=`, and `_score` only ever calls `expected_guesses(w)`, so this drops in
with no change to the search.  Two implementations of one objective, and the
gate (`tools/checkwturnsobjective.py`) requires them to agree EXACTLY.

READ THE INTEGER `total`, NEVER THE PRINTED `expected`.  The CSV rounds expected
to 5 decimals; a hill-climb comparing improvements finer than 1e-5 would be blind
to them, and would silently stop climbing.  `total` is exact in scaled integer
units and `total_scaled` is its denominator.

THE CAP MUST NOT BIND.  `topk.py` has NO depth cap; `wturns` always has one.  If
the cap bound, an opener `topk.py` would have used comes back INFEASIBLE and the
solver picks a different one -- a different objective under the same name.  So
any INFEASIBLE row RAISES rather than being averaged over or skipped.

PER-EVALUATION COST is one sort of the live words plus one column permutation of
the pattern matrix, MEASURED at ~1.35 s for 12972 x 4229.  That is a CONSTANT,
independent of K: negligible beside a k>=2 evaluation, and larger than a k=1
evaluation, which is why this is worth using for the beam and not for the greedy.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "tools"))

from build_patterns import load_patterns          # noqa: E402
from topk import CUSTOM, read_words               # noqa: E402
from wordle import load_words                     # noqa: E402

import freqweights                                # noqa: E402

BINARY = os.path.join(_HERE, "solver", "wturns")


class WturnsGame:
    """`TopKGame`'s objective interface, computed by `solver/wturns`.

    Only what `FrequencySearch` actually touches is implemented: `words`, `N`,
    `NG` and `expected_guesses(w)`.  It is NOT a drop-in for `TopKGame`'s tracing
    or ranking helpers -- those have no C equivalent to call.
    """

    def __init__(self, *, answers: str | list[str] = CUSTOM,
                 guesses: str | list[str] | None = None,
                 patterns: np.ndarray | None = None,
                 data: str | None = None, k: int = 1,
                 depth: int = 9, threads: int = 18, tt_bits: int = 24,
                 workdir: str | None = None):
        """`guesses`/`patterns`/`data` mirror TopKGame's own escape hatch, which
        exists so a caller whose words are not in the committed square matrix can
        supply its own. Here `data` additionally points the SOLVER at those lists,
        since it reads its guess list off disk rather than from this object --
        that is what lets the gate diff the two on a miniature problem through the
        ordinary code path rather than a special one."""
        if k < 1:
            raise ValueError(f"k must be at least 1, got {k}")
        if not os.path.exists(BINARY):
            raise SystemExit(f"no {BINARY} -- run 'sh build.sh' in solver/")
        self.k, self.depth, self.threads, self.tt_bits = k, depth, threads, tt_bits
        self.words = (answers if isinstance(answers, list) else read_words(answers))
        self.guess_words = (load_words("guess") if guesses is None else
                            guesses if isinstance(guesses, list) else read_words(guesses))
        gpos = {g: i for i, g in enumerate(self.guess_words)}
        missing = [a for a in self.words if a not in gpos]
        if missing:
            raise ValueError(f"{len(missing)} candidates are not legal guesses, "
                             f"e.g. {missing[:5]}")
        self.N, self.NG = len(self.words), len(self.guess_words)
        self.data = data
        if patterns is not None:
            P = np.ascontiguousarray(patterns)
            if P.shape != (self.NG, self.N):
                raise ValueError(f"patterns has shape {P.shape}, expected "
                                 f"{(self.NG, self.N)} (guesses x candidates)")
            self._base = P
        else:
            # Columns of the SQUARE matrix, in THIS list's order -- the same slice
            # topk.py takes, so both objectives read identical feedback.
            full = load_patterns(full=True)
            cols = np.array([gpos[a] for a in self.words], dtype=np.int64)
            self._base = np.ascontiguousarray(full[:, cols])
        self._dir = workdir or tempfile.mkdtemp(prefix="wturns-obj-")
        self.calls = 0

    # ---- the objective -----------------------------------------------------
    def total_cost(self, weights=None) -> float:
        """Weight-summed guesses, in the SAME units topk.py reports."""
        info = self._run(weights)
        return info["total"] / info["scale"]

    def expected_guesses(self, weights=None) -> float:
        """Weighted average guesses over the live candidates. NO depth cap in the
        objective -- `--depth` is set generously and a binding cap RAISES."""
        w = np.ones(self.N) if weights is None else np.asarray(weights, float)
        if w.shape != (self.N,):
            raise ValueError(f"weights must have shape ({self.N},), got {w.shape}")
        if (w < 0).any():
            raise ValueError("weights must be non-negative")
        if not (w > 0).any():
            return 0.0
        info = self._run(w)
        # total and total_scaled are both in scaled integer units, so this is the
        # exact ratio -- never the CSV's 5-decimal `expected`.
        return info["total"] / info["total_scaled"]

    # ---- driving the solver ------------------------------------------------
    def _run(self, weights) -> dict:
        w = np.ones(self.N) if weights is None else np.asarray(weights, float)
        # Zero-weight words are DROPPED, exactly as topk.py drops them: a weight
        # of 0 means the word cannot be the answer and the guesser knows it, and
        # leaving it in would also steer the word-COUNTING half of the ranking.
        live = [i for i in range(self.N) if w[i] > 0]
        # Weight-DESCENDING, ties on the word: the solver refuses any other order
        # because its lower bound assigns the shallowest levels to the heaviest
        # answers and gets each bucket in that order for free.
        live.sort(key=lambda i: (-w[i], self.words[i]))

        stem = os.path.join(self._dir, "w")
        pairs = [(self.words[i], float(w[i])) for i in live]
        info = freqweights._write(pairs, stem, "freq_search evaluation")

        pats = stem + ".patterns.npy"
        np.save(pats, np.ascontiguousarray(self._base[:, np.array(live, dtype=np.int64)]))

        out = stem + ".csv"
        if os.path.exists(out):
            os.remove(out)
        cmd = [BINARY]
        if self.data:
            cmd += ["--data", self.data]
        cmd += ["--weights", stem + ".weights", "--answer-list", stem + ".txt",
               "--patterns", pats, "--depth", str(self.depth), "--sweep",
               "--optimal-only", "--topk", str(self.k), "--out", out,
               "--tt-bits", str(self.tt_bits), "--threads", str(self.threads)]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=_HERE)
        if r.returncode != 0:
            raise RuntimeError("wturns failed:\n" + r.stderr[-1500:])
        self.calls += 1

        best = None
        infeasible = []
        for line in open(out):
            if line.startswith("word,"):
                continue
            f = line.rstrip("\n").split(",")
            if len(f) < 2 or not f[1]:
                infeasible.append(f[0])
                continue
            t = int(f[1])
            best = t if best is None else min(best, t)
        if infeasible:
            # The cap bound. topk.py has no cap, so the two objectives have parted
            # company and the number would be wrong under a right-looking name.
            raise RuntimeError(
                "--depth %d BOUND on %d opener(s) (e.g. %s): topk.py has no depth "
                "cap, so this is no longer the same objective. Raise depth."
                % (self.depth, len(infeasible), ", ".join(infeasible[:5])))
        if best is None:
            raise RuntimeError("wturns wrote no result row to %s" % out)
        info["total"] = best
        return info
