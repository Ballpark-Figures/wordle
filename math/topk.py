"""The guesser the adversarial search plays against: a top-K Wordle solver that
SEES the answer weights.

Model, stated exactly. A fixed CANDIDATE list (`words/custom.txt` by default)
carries a non-normalised WEIGHT per word; a weight of 0 means the word cannot be
the answer and the guesser knows it, so zero-weight words are dropped from the
candidate set before any search. The guesser may play ANY legal guess
(`words/guess.txt`, all 12972), candidate or not.

At every node the guesser ranks all legal guesses by

    score(g) = SUM over patterns p != all-green of  n_p * (W_p / W)

    n_p = how many candidates fall in pattern p,  W_p = their summed weight,
    W = the node's total weight (constant across g, so it is dropped)

ascending -- the expected number of candidate WORDS still alive after the guess,
with the winning bin excluded so a guess that could BE the answer beats an
equally-splitting outside word. Ties break on lowest guess index. It then
recurses into the K best-ranked guesses and keeps whichever actually minimises
expected guesses (K=1 = no lookahead, take the top-ranked guess).

Cost. Every candidate alive at a node pays for the guess played there; the
candidate equal to that guess is finished by it. THERE IS NO DEPTH CAP -- the
objective is expected guesses outright, not expected guesses subject to a
6-guess guarantee (which is what `optturns`/`hardturns` compute). `MAXD` is a
recursion guard against a non-splitting guess, not a modelling limit; it cannot
bind while the candidate set is a subset of the guess list, since a candidate
guess always outranks any guess that fails to split.

Speed. The frequency-INDEPENDENT structure (the pattern matrix) is built once;
each solve is a numba kernel over it, so the "tweak the weights, re-solve" loop
pays only the solve. A pure-numpy reference path (`use_numba=False`) implements
the identical rules and is the differential oracle -- see tools/checktopk.py.
"""

from __future__ import annotations

import os

import numpy as np

from build_patterns import load_patterns
from wordle import ALL_GREEN, load_words

MAXD = 32          # recursion guard; see the docstring -- NOT a modelling cap

_HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM = os.path.join(_HERE, "data", "shared", "words", "custom.txt")

try:
    from numba import njit
    _HAVE_NUMBA = True
except Exception:                       # numba absent -- the numpy path still runs
    _HAVE_NUMBA = False


def read_words(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


if _HAVE_NUMBA:

    @njit(cache=True)
    def _best_guesses(P, S, w, k, cnt, wsum, touched, out_g, out_s):
        """Fill out_g/out_s with the k best-ranked guesses (ascending score).

        cnt/wsum are scratch accumulators of length NPAT, left zeroed on exit;
        only the patterns actually touched are cleared, so the per-node cost is
        O(NG * n) and does not carry the 243-wide reset.
        """
        NG, n = P.shape[0], S.shape[0]
        nk = 0
        for g in range(NG):
            nt = 0
            for j in range(n):
                p = P[g, S[j]]
                if cnt[p] == 0:
                    touched[nt] = p
                    nt += 1
                cnt[p] += 1
                wsum[p] += w[S[j]]
            score = 0.0
            for t in range(nt):
                p = touched[t]
                if p != ALL_GREEN:
                    score += cnt[p] * wsum[p]
                cnt[p] = 0
                wsum[p] = 0.0
            # insertion into the running top-k; ties keep the lower guess index
            if nk < k or score < out_s[nk - 1]:
                pos = nk if nk < k else k - 1
                while pos > 0 and out_s[pos - 1] > score:
                    out_s[pos] = out_s[pos - 1]
                    out_g[pos] = out_g[pos - 1]
                    pos -= 1
                out_s[pos] = score
                out_g[pos] = g
                if nk < k:
                    nk += 1
        return nk

    @njit(cache=True)
    def _solve(P, S, w, k, depth, cnt, wsum, touched, ans2g):
        """(weighted cost of this subtree, the GUESS index chosen at its root).

        The second element indexes the GUESS list, never the candidate list --
        `ans2g` maps the lone survivor to the guess that plays it.
        """
        n = S.shape[0]
        W = 0.0
        for j in range(n):
            W += w[S[j]]
        if n == 1:
            return W, ans2g[S[0]]       # play it: one guess (answers are legal guesses)
        if depth >= MAXD:
            return np.inf, -1
        out_g = np.empty(k, dtype=np.int64)
        out_s = np.empty(k, dtype=np.float64)
        nk = _best_guesses(P, S, w, k, cnt, wsum, touched, out_g, out_s)
        best_cost, best_g = np.inf, -1
        for t in range(nk):
            g = out_g[t]
            cost = W                    # every live candidate pays for this guess
            order = np.argsort(P[g][S], kind="mergesort")
            start = 0
            while start < n:
                pv = P[g, S[order[start]]]
                end = start + 1
                while end < n and P[g, S[order[end]]] == pv:
                    end += 1
                if pv != ALL_GREEN:     # the all-green bin is finished by this guess
                    sub = np.empty(end - start, dtype=S.dtype)
                    for q in range(end - start):
                        sub[q] = S[order[start + q]]
                    c, _ = _solve(P, sub, w, k, depth + 1, cnt, wsum, touched, ans2g)
                    cost += c
                start = end
                if cost >= best_cost:
                    break
            if cost < best_cost:
                best_cost, best_g = cost, g
        return best_cost, best_g


class TopKGame:
    """Top-K guesser over one candidate list. Build once, re-solve per weight
    vector: ``expected_guesses(w)`` is the adversarial search's objective."""

    def __init__(self, *, answers: str | list[str] = CUSTOM,
                 guesses: str | list[str] | None = None, k: int = 1,
                 use_numba: bool = True, patterns: np.ndarray | None = None):
        if k < 1:
            raise ValueError(f"k must be at least 1, got {k}")
        self.k = k
        self._given_P = patterns
        self.use_numba = use_numba and _HAVE_NUMBA
        self.guess_words = (load_words("guess") if guesses is None else
                            guesses if isinstance(guesses, list) else read_words(guesses))
        self.words = (answers if isinstance(answers, list) else read_words(answers))
        playable = set(self.guess_words)
        missing = [a for a in self.words if a not in playable]
        if missing:
            raise ValueError(f"{len(missing)} candidates are not legal guesses, "
                             f"e.g. {missing[:5]} -- the recursion guard relies on "
                             f"every candidate being playable")
        self.N, self.NG = len(self.words), len(self.guess_words)
        self.P = self._patterns()
        # candidate index -> the guess index that PLAYS it. The two lists differ,
        # so a lone survivor must be translated before it is used as a guess.
        gpos = {g: i for i, g in enumerate(self.guess_words)}
        self.ans2g = np.array([gpos[a] for a in self.words], dtype=np.int64)
        self._cnt = np.zeros(ALL_GREEN + 1, dtype=np.int64)
        self._wsum = np.zeros(ALL_GREEN + 1, dtype=np.float64)
        self._touched = np.zeros(ALL_GREEN + 1, dtype=np.int64)

    def _patterns(self) -> np.ndarray:
        """[NG, N] uint8 of pattern(guess, candidate), sliced from the committed
        square all-words matrix. That matrix is indexed by the CANONICAL guess.txt
        order on BOTH axes, so rows/columns are looked up there, not in this
        game's own (possibly narrowed) lists.

        A caller whose words are NOT in that matrix -- the other-language lists,
        whose letters need not even be a..z -- supplies its own via
        ``patterns=``; the English callers pass nothing and are unaffected."""
        if self._given_P is not None:
            P = np.ascontiguousarray(self._given_P)
            if P.shape != (self.NG, self.N):
                raise ValueError(f"patterns has shape {P.shape}, expected "
                                 f"{(self.NG, self.N)} (guesses x candidates)")
            return P
        full = load_patterns(full=True)
        canon = {w: i for i, w in enumerate(load_words("guess"))}
        if full.shape[0] != len(canon):
            raise ValueError(f"patterns_full.npy has {full.shape[0]} rows, "
                             f"guess.txt has {len(canon)} words")
        rows = np.array([canon[g] for g in self.guess_words], dtype=np.int64)
        cols = np.array([canon[a] for a in self.words], dtype=np.int64)
        return np.ascontiguousarray(full[np.ix_(rows, cols)])

    # ---- the objective -----------------------------------------------------
    def _coerce(self, weights) -> np.ndarray:
        if weights is None:
            return np.ones(self.N, dtype=np.float64)
        w = np.asarray(weights, dtype=np.float64)
        if w.shape != (self.N,):
            raise ValueError(f"weights must have shape ({self.N},), got {w.shape}")
        if (w < 0).any():
            raise ValueError("weights must be non-negative")
        return w

    def total_cost(self, weights=None) -> float:
        """Weight-summed guesses over the live (weight > 0) candidates."""
        w = self._coerce(weights)
        S = np.flatnonzero(w > 0).astype(np.int64)
        if S.size == 0:
            return 0.0
        if self.use_numba:
            cost, _ = _solve(self.P, S, w, self.k, 0,
                             self._cnt, self._wsum, self._touched, self.ans2g)
            return float(cost)
        return float(self._ref_solve(S, w, 0)[0])

    def expected_guesses(self, weights=None) -> float:
        """Weighted average guesses over the live candidates -- what the
        adversarial search maximises. NO depth cap (see the module docstring)."""
        w = self._coerce(weights)
        total = w.sum()
        if total == 0:
            return 0.0
        return self.total_cost(w) / total

    # ---- reference implementation (the oracle; identical rules, plain numpy)
    def _ref_rank(self, S, w):
        """The k best-ranked guesses at node S, ascending score, ties on index."""
        sub = self.P[:, S]
        wS = w[S]
        scores = np.empty(self.NG, dtype=np.float64)
        for g in range(self.NG):
            row = sub[g]
            cnt = np.bincount(row, minlength=ALL_GREEN + 1).astype(np.float64)
            wsum = np.bincount(row, weights=wS, minlength=ALL_GREEN + 1)
            cnt[ALL_GREEN] = 0.0
            scores[g] = float((cnt * wsum).sum())
        return np.argsort(scores, kind="stable")[:self.k]

    def _ref_solve(self, S, w, depth):
        n = S.size
        W = float(w[S].sum())
        if n == 1:
            return W, int(self.ans2g[S[0]])     # the GUESS that plays it
        if depth >= MAXD:
            return np.inf, -1
        best_cost, best_g = np.inf, -1
        for g in self._ref_rank(S, w):
            g = int(g)
            cost = W
            pats = self.P[g][S]
            for pv in np.unique(pats):
                if pv == ALL_GREEN:
                    continue
                cost += self._ref_solve(S[pats == pv], w, depth + 1)[0]
            if cost < best_cost:
                best_cost, best_g = cost, g
        return best_cost, best_g

    # ---- reporting ---------------------------------------------------------
    def per_word_guesses(self, weights=None) -> np.ndarray:
        """Guesses spent on each candidate (0 for weight-0 words, which are not
        in the game). Replays the search node by node, so it costs a solve per
        node at k > 1 -- for reporting, not for the search loop."""
        w = self._coerce(weights)
        out = np.zeros(self.N, dtype=np.float64)
        S = np.flatnonzero(w > 0).astype(np.int64)
        if S.size:
            self._walk(S, w, 0, out)
        return out

    def _walk(self, S, w, depth, out) -> None:
        out[S] += 1                                   # everyone pays for this guess
        if S.size == 1:
            return
        g = self._chosen(S, w, depth)
        pats = self.P[g][S]
        for pv in np.unique(pats):
            if pv != ALL_GREEN:
                self._walk(S[pats == pv], w, depth + 1, out)

    def _chosen(self, S, w, depth) -> int:
        if self.use_numba:
            _, g = _solve(self.P, S, w, self.k, depth,
                          self._cnt, self._wsum, self._touched, self.ans2g)
            return int(g)
        return int(self._ref_solve(S, w, depth)[1])

    def trace(self, word: str, weights=None) -> list[tuple[str, int]]:
        """The guess sequence the guesser plays for ``word``: [(guess, pattern)]."""
        w = self._coerce(weights)
        i = self.words.index(word)
        if w[i] <= 0:
            raise ValueError(f"{word!r} has weight 0 -- it is not in the game")
        S = np.flatnonzero(w > 0).astype(np.int64)
        out, depth = [], 0
        while depth < MAXD:
            g = int(self.ans2g[S[0]]) if S.size == 1 else self._chosen(S, w, depth)
            pv = int(self.P[g, i])
            out.append((self.guess_words[g], pv))
            if pv == ALL_GREEN:
                return out
            S = S[self.P[g][S] == pv]
            depth += 1
        raise RuntimeError(f"trace of {word!r} did not finish within MAXD={MAXD} "
                           f"guesses: {[gw for gw, _ in out]}")


def _demo(k: int = 1) -> None:
    """Mirrors hangman's `strategy.py` demo: build, solve, time each step."""
    import time
    t0 = time.perf_counter()
    g = TopKGame(k=k)
    t_build = time.perf_counter() - t0

    t0 = time.perf_counter()
    avg = g.expected_guesses()
    t_a = time.perf_counter() - t0

    print(f"topk {k}: {g.N:,} candidates, {g.NG:,} legal guesses  "
          f"(build {t_build*1e3:.0f} ms)")
    print(f"opens with '{g.trace(g.words[0])[0][0]}'")
    print(f"expected guesses = {avg:.4f}   ({t_a*1e3:.0f} ms)")


if __name__ == "__main__":
    import sys
    _demo(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
