"""A top-K Nerdle solver, ranking guesses by the sum of squared bin sizes.

THE OBJECTIVE, stated exactly: the EXPECTED NUMBER OF GUESSES to finish, over
the answer list taken UNIFORMLY.  There is NO DEPTH CAP -- this is expected
guesses outright, not expected guesses subject to a guarantee, which is what
optturns/hardturns/ansall compute next door.  Never put the two in one table.
`MAXD` is a recursion guard, not a modelling limit; see the note on it below.

THE STRATEGY, stated exactly.  At every node the solver scores each legal guess
by the SUM OF SQUARED BIN SIZES of the partition it induces on the live
candidates, ascending -- the evenest splitter first -- with ties broken on the
LOWEST GUESS INDEX.  It then recurses into the K best and keeps whichever
actually minimises the total, so K=1 is no lookahead at all and larger K is a
beam.  This is the ranking rule solver/strturns.c uses, and the reasons behind
it transfer verbatim: it is ONE rule shared by every call site, and the key is
never packed beside the guess index (doing that forced a shift, which made every
guess tie at small nodes and silently turned --topk into alphabetical order).

WHAT MAKES THIS NOT A WORDLE SOLVER, and the reason it could not be borrowed
from topk.py wholesale:

  * A GUESS WINS AGAINST ITS WHOLE COMMUTATIVE CLASS AT ONCE.  Nerdle accepts a
    rearrangement of the day's answer (a setting, on by default), so playing
    `34+12=46` finishes `12+34=46` as well.  The winning bin is therefore the
    class, NOT the all-green pattern, and one guess can resolve several
    candidates simultaneously -- which never happens in Wordle.  The all-green
    bin is a subset of it (an identical string is trivially in the same class),
    so nothing needs special-casing once the class-mates are removed.
  * A GUESS NEED NOT BE A POSSIBLE ANSWER.  All 374246 legal guesses are
    available and only 17723 of them are answers; a non-answer guess has no
    class and can never win, however good a splitter it is.
  * THERE IS NO PATTERN MATRIX.  374246 x 17723 is 13.3 GB, so patterns are
    computed inside the kernel instead.  The cost of a level is the guess count
    times the candidates alive at that level, so every level costs about what
    the root does rather than decaying -- budget accordingly.

WHY MAXD CANNOT BIND.  Every answer is a legal guess, so at any node the solver
may play a candidate, which wins at least one candidate and splits the rest;
such a guess scores better than any that fails to split, so the beam always
holds one and every child is strictly smaller.  MAXD (32) is a guard against
that reasoning being wrong, not a cap on the search.

GUESS ORDER IS PART OF THE STRATEGY.  Ties break on the lowest guess index, so
the list is put in canonical SYMBOL order on construction -- see
canonical_order().  Without that the total depends on which enumerator wrote the
file, which is how a width-6 run gave 526 one way and 528 the other.

SPEED.  The numba kernel is the fast path and `use_numba=False` selects a plain
numpy implementation of the identical rules, which is the differential oracle --
see tools/checknerdletopk.py.  A `width` parameter runs the whole thing on the
smaller boards, which is what lets the oracle check it exhaustively.
"""

from __future__ import annotations

import gzip
import os

import numpy as np

from nerdle import SYMBOLS, WIDTH, commutative_key

MAXD = 32          # recursion guard; see the docstring -- NOT a modelling cap

NSYM = len(SYMBOLS)
_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "data", "shared", "nerdle")

try:
    from numba import njit
    _HAVE_NUMBA = True
except Exception:                       # numba absent -- the numpy path still runs
    _HAVE_NUMBA = False


def load_list(kind, width=WIDTH):
    """The committed guess or answer list for this width, as a list of strings."""
    path = os.path.join(_DATA, "%s_w%d.txt.gz" % (kind, width))
    if not os.path.exists(path):
        raise SystemExit(
            "no %s list at %s -- run solver/run-nerdle-%s.sh --width %d"
            % (kind, path, "enumerate" if kind == "guesses" else "answers", width))
    with gzip.open(path, "rt") as f:
        return [line.strip() for line in f if line.strip()]


def canonical_order(words):
    """Sort by SYMBOL ORDER -- digits, then `+ - * /`, then `=`.

    THIS IS LOAD-BEARING, not tidiness.  Ties in the ranking break on the lowest
    guess INDEX, so the index order is part of the strategy: two lists holding
    the same guesses in different orders give different totals.  The enumerators
    emit different orders (the DFS walks the string, the split walks by `=`
    position), so taking a list in file order would make the answer depend on
    which one happened to write the file.  Sorting here keeps the result a
    function of the guess SET alone.

    Not Python's string order, which puts the operators below the digits by
    ASCII; SYMBOLS order is the one the rest of this code means by "first".
    """
    rank = {c: i for i, c in enumerate(SYMBOLS)}
    return sorted(words, key=lambda w: tuple(rank[c] for c in w))


def encode(words, width):
    """[n, width] uint8 of symbol indices."""
    idx = {c: i for i, c in enumerate(SYMBOLS)}
    out = np.empty((len(words), width), dtype=np.uint8)
    for r, w in enumerate(words):
        for c, ch in enumerate(w):
            out[r, c] = idx[ch]
    return out


if _HAVE_NUMBA:

    @njit(cache=True, inline="always")
    def _pattern(G, g, A, a, width, cnt):
        """Base-3 feedback code for guess row g against answer row a.

        Greens first, then the answer's spare copies handed out to yellows left
        to right -- the same rule as Wordle, which is why wordle.pattern
        reproduces it.  `cnt` is scratch: the entries this call touches are put
        back to zero before returning, so it stays clean for the next call
        without a 15-wide reset.
        """
        for i in range(width):
            if G[g, i] != A[a, i]:
                cnt[A[a, i]] += 1
        code = 0
        for i in range(width):
            if G[g, i] == A[a, i]:
                t = 2
            elif cnt[G[g, i]] > 0:
                t = 1
                cnt[G[g, i]] -= 1
            else:
                t = 0
            code = code * 3 + t
        for i in range(width):
            if G[g, i] != A[a, i]:
                cnt[A[a, i]] = 0
        return code

    @njit(cache=True)
    def _rank(G, A, S, gclass, aclass, width, k, cnt, bins, touched, out_g, out_s):
        """Fill out_g/out_s with the k best-scoring guesses, ascending.

        The score is the sum of squared bin sizes over the candidates NOT won by
        the guess.  `bins` is a scratch counter left zeroed on exit; only the
        patterns actually touched are cleared, so a node costs O(NG * n) and
        never carries the 6561-wide reset.
        """
        NG, n = G.shape[0], S.shape[0]
        nk = 0
        for g in range(NG):
            gc = gclass[g]
            nt = 0
            for j in range(n):
                a = S[j]
                if aclass[a] == gc:
                    continue            # won outright -- not in any bin
                p = _pattern(G, g, A, a, width, cnt)
                if bins[p] == 0:
                    touched[nt] = p
                    nt += 1
                bins[p] += 1
            score = 0
            for t in range(nt):
                p = touched[t]
                score += bins[p] * bins[p]
                bins[p] = 0
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
    def _solve(G, A, S, gclass, aclass, width, k, depth, cnt, bins, touched):
        """(total guesses over the candidates in S, the guess index chosen)."""
        n = S.shape[0]
        if n == 0:
            return 0, -1
        # One class left: play any member and every candidate is finished.  No
        # guess can beat that, so the scan is skipped -- which is what keeps the
        # deep, tiny nodes from each costing a full pass over 374246 guesses.
        one = True
        for j in range(1, n):
            if aclass[S[j]] != aclass[S[0]]:
                one = False
                break
        if one:
            return n, -1
        if depth >= MAXD:
            return 1 << 60, -1

        out_g = np.empty(k, dtype=np.int64)
        out_s = np.empty(k, dtype=np.int64)
        nk = _rank(G, A, S, gclass, aclass, width, k, cnt, bins, touched, out_g, out_s)

        best_cost, best_g = 1 << 60, -1
        for t in range(nk):
            g = out_g[t]
            gc = gclass[g]
            codes = np.empty(n, dtype=np.int64)
            live = 0
            for j in range(n):
                if aclass[S[j]] == gc:
                    codes[j] = -1                 # won by this guess
                else:
                    codes[j] = _pattern(G, g, A, S[j], width, cnt)
                    live += 1
            cost = n                              # every live candidate pays for it
            order = np.argsort(codes, kind="mergesort")
            start = 0
            while start < n and codes[order[start]] < 0:
                start += 1                        # skip the won block
            while start < n:
                pv = codes[order[start]]
                end = start + 1
                while end < n and codes[order[end]] == pv:
                    end += 1
                sub = np.empty(end - start, dtype=S.dtype)
                for q in range(end - start):
                    sub[q] = S[order[start + q]]
                c, _ = _solve(G, A, sub, gclass, aclass, width, k, depth + 1,
                              cnt, bins, touched)
                cost += c
                start = end
                if cost >= best_cost:
                    break
            if cost < best_cost:
                best_cost, best_g = cost, g
        return best_cost, best_g


class NerdleTopK:
    """Top-K Nerdle solver over one (guess list, answer list) pair.

    Build once, then `expected_guesses()`.  `k` is the beam width and is the
    ONLY approximation: at every node, including the root, exactly the k
    best-scoring guesses are explored, so the answer is the best of the k
    examined and NOT an optimum over all 374246.
    """

    def __init__(self, *, width=WIDTH, k=1, guesses=None, answers=None,
                 use_numba=True):
        if k < 1:
            raise ValueError("k must be at least 1, got %d" % k)
        self.width, self.k = width, k
        self.use_numba = use_numba and _HAVE_NUMBA
        self.guess_words = canonical_order(
            guesses if guesses is not None else load_list("guesses", width))
        self.answer_words = canonical_order(
            answers if answers is not None else load_list("answers", width))

        # A guess wins against its whole class, so every guess needs the class
        # id it would win -- and -1 when it is not an answer at all and can
        # therefore never win, however well it splits.
        ids, self.aclass = {}, []
        for a in self.answer_words:
            key = commutative_key(a)
            if key not in ids:
                ids[key] = len(ids)
            self.aclass.append(ids[key])
        self.aclass = np.array(self.aclass, dtype=np.int64)
        by_word = dict(zip(self.answer_words, self.aclass))
        self.gclass = np.array([by_word.get(g, -1) for g in self.guess_words],
                               dtype=np.int64)
        self.nclasses = len(ids)

        self.G = encode(self.guess_words, width)
        self.A = encode(self.answer_words, width)
        self.NG, self.NA = len(self.guess_words), len(self.answer_words)
        self.NPAT = 3 ** width
        self._cnt = np.zeros(NSYM, dtype=np.int64)
        self._bins = np.zeros(self.NPAT, dtype=np.int64)
        self._touched = np.zeros(self.NPAT, dtype=np.int64)

    # ---- the objective -----------------------------------------------------
    def total_guesses(self):
        """Guesses summed over every answer -- an integer, so exactly comparable."""
        S = np.arange(self.NA, dtype=np.int64)
        if self.use_numba:
            cost, _ = _solve(self.G, self.A, S, self.gclass, self.aclass,
                             self.width, self.k, 0, self._cnt, self._bins,
                             self._touched)
            return int(cost)
        return int(self._ref_solve(S, 0)[0])

    def expected_guesses(self):
        """Average guesses over the answer list, taken UNIFORMLY.

        Uniform over ANSWERS, not over classes: the hidden equation is drawn
        from the answer list, and two answers sharing a class are two different
        days that happen to be won by the same guess.
        """
        return self.total_guesses() / self.NA

    def opener(self):
        """The guess the beam plays first, as a word."""
        S = np.arange(self.NA, dtype=np.int64)
        if self.use_numba:
            _, g = _solve(self.G, self.A, S, self.gclass, self.aclass, self.width,
                          self.k, 0, self._cnt, self._bins, self._touched)
        else:
            _, g = self._ref_solve(S, 0)
        return self.guess_words[g] if g >= 0 else None

    # ---- reference implementation (the oracle; identical rules, plain numpy)
    def _ref_patterns(self, g, S):
        """Feedback codes for guess g against the candidates in S, from numpy."""
        from wordle import pattern
        return np.array([pattern(self.guess_words[g], self.answer_words[a])
                         for a in S], dtype=np.int64)

    def _ref_rank(self, S):
        scores = np.empty(self.NG, dtype=np.int64)
        for g in range(self.NG):
            keep = S[self.aclass[S] != self.gclass[g]]
            codes = self._ref_patterns(g, keep)
            counts = np.bincount(codes) if codes.size else np.zeros(0, dtype=np.int64)
            scores[g] = int((counts.astype(np.int64) ** 2).sum())
        return np.argsort(scores, kind="stable")[:self.k]

    def _ref_solve(self, S, depth):
        n = S.size
        if n == 0:
            return 0, -1
        if len(set(self.aclass[S].tolist())) == 1:
            return n, -1
        if depth >= MAXD:
            return 1 << 60, -1
        best_cost, best_g = 1 << 60, -1
        for g in self._ref_rank(S):
            keep = S[self.aclass[S] != self.gclass[g]]
            cost = n
            if keep.size:
                codes = self._ref_patterns(g, keep)
                for pv in np.unique(codes):
                    c, _ = self._ref_solve(keep[codes == pv], depth + 1)
                    cost += c
                    if cost >= best_cost:
                        break
            if cost < best_cost:
                best_cost, best_g = cost, int(g)
        return best_cost, best_g
