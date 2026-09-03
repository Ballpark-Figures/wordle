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
import sys

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

    @njit(cache=True, inline="always")
    def _score(G, g, A, S, gclass, aclass, width, cnt, bins, touched):
        """Sum of squared bin sizes for guess g over the candidates in S.

        THE scoring rule, defined once.  Both the per-node top-k ranking and the
        whole-root scoring call this, so "what does the beam rank by" has one
        answer rather than one per call site -- the same discipline strturns
        keeps with its single GuessKey comparator.

        Candidates the guess WINS are excluded: they are resolved, not binned.
        `bins` is scratch, left zeroed on exit by clearing only the patterns
        actually touched, so a node costs O(n) and never the 6561-wide reset.
        """
        gc = gclass[g]
        nt = 0
        for j in range(S.shape[0]):
            a = S[j]
            if aclass[a] == gc:
                continue
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
        return score

    @njit(cache=True)
    def _scores(G, A, S, gclass, aclass, width, cnt, bins, touched, out, lo, hi):
        """Score guesses [lo, hi) into `out`.

        The top-k insertion in _rank is O(k) per guess, fine for a beam of a few
        but quadratic when k is the whole guess list.  Scoring into an array and
        sorting afterwards is what makes the full root ranking affordable, and it
        gives the identical order: a stable argsort breaks ties on the lower
        index, exactly as the insertion does.

        IT TAKES A RANGE SO THE CALLER CAN CHUNK IT, and that is not a
        performance knob.  A njit function never returns to the interpreter, so
        Python cannot run its SIGINT handler while one is executing: scoring all
        374246 guesses in a single call made Ctrl-C do nothing for nearly two
        minutes.  Returning between blocks is what makes the slow step
        interruptible, and what lets it report progress at all.
        """
        for g in range(lo, hi):
            out[g] = _score(G, g, A, S, gclass, aclass, width, cnt, bins, touched)

    @njit(cache=True)
    def _rank(G, A, S, gclass, aclass, width, k, cnt, bins, touched, out_g, out_s):
        """Fill out_g/out_s with the k best-scoring guesses, ascending.

        The score is the sum of squared bin sizes over the candidates NOT won by
        the guess.  `bins` is a scratch counter left zeroed on exit; only the
        patterns actually touched are cleared, so a node costs O(NG * n) and
        never carries the 6561-wide reset.
        """
        NG = G.shape[0]
        nk = 0
        for g in range(NG):
            score = _score(G, g, A, S, gclass, aclass, width, cnt, bins, touched)
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
    def _codes(G, g, A, S, gclass, aclass, width, cnt, out):
        """Feedback code per candidate for guess g; -1 for the ones it WINS.

        Exists so the ROOT can be driven from Python -- see NerdleTopK.solve.
        The recursion below does the same thing inline; both must agree, which
        the gate checks by running the two root paths against each other.
        """
        gc = gclass[g]
        for j in range(S.shape[0]):
            if aclass[S[j]] == gc:
                out[j] = -1
            else:
                out[j] = _pattern(G, g, A, S[j], width, cnt)

    @njit(cache=True)
    def _rows(G, gs, A, S, gclass, aclass, width, cnt, out):
        """Feedback per (chosen guess, candidate); -1 where that guess WINS."""
        for r in range(gs.shape[0]):
            g = gs[r]
            gc = gclass[g]
            for j in range(S.shape[0]):
                if aclass[S[j]] == gc:
                    out[r, j] = -1
                else:
                    out[r, j] = _pattern(G, g, A, S[j], width, cnt)

    @njit(cache=True)
    def _pair_row(rows, i, npat, buf, out, off):
        """Sum of squared JOINT bin sizes for every pair of the given rows.

        The joint bin of an answer is the pair of feedbacks the two guesses give
        it, so this is the partition you hold after playing both BLIND.  An
        answer that either guess WINS is resolved and joins no bin, which is the
        convention the single-guess ranking already uses.

        `buf` is a npat*npat counter touched sparsely and cleared by walking the
        same answers again -- never by zeroing 43 million entries per pair.

        ONE ROW AT A TIME -- every pair (i, j) with j > i -- so the caller can
        drive it from Python.  As with the root scoring, a njit call does not
        return to the interpreter, so doing every pair in one call swallows
        Ctrl-C for the whole run, which at --top-n 10000 is 49,995,000 pairs and
        the better part of an hour.
        """
        n, NA = rows.shape
        t = off
        for j in range(i + 1, n):
            for a in range(NA):
                p1 = rows[i, a]
                p2 = rows[j, a]
                if p1 >= 0 and p2 >= 0:
                    buf[np.int64(p1) * npat + p2] += 1
            ss = 0
            for a in range(NA):
                p1 = rows[i, a]
                p2 = rows[j, a]
                if p1 >= 0 and p2 >= 0:
                    q = np.int64(p1) * npat + p2
                    c = buf[q]
                    if c > 0:
                        ss += np.int64(c) * c
                        buf[q] = 0
            out[t] = ss
            t += 1
        return t

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


def save_ranking(path, game):
    """Write the root ranking, best first, with the fingerprint it belongs to.

    One guess per line: rank, guess, score.  The fingerprint sits in the
    accompanying .meta and covers the width and BOTH word lists, so a ranking
    cannot be silently reused after the answer list changes -- which would
    reorder every score while leaving the file looking perfectly valid.
    """
    scores, order = game.root_ranking()
    with gzip.open(path, "wt") if path.endswith(".gz") else open(path, "w") as f:
        f.write("rank,guess,sum_of_squares\n")
        for r, g in enumerate(order):
            f.write("%d,%s,%d\n" % (r + 1, game.guess_words[g], scores[g]))
    with open(path + ".meta", "w") as m:
        m.write("kind=root-ranking\n")
        m.write("width=%d\n" % game.width)
        m.write("score=ascending-sum-of-squared-bins\n")
        m.write("ties=lowest-guess-index-in-canonical-symbol-order\n")
        m.write("guesses=%d\nanswers=%d\nclasses=%d\n"
                % (game.NG, game.NA, game.nclasses))
        m.write("fingerprint=%s\n" % game.fingerprint())


def load_ranking(path, game):
    """Read a stored ranking for `game`, or None if it is absent or foreign.

    Returns None rather than raising, so a caller can fall back to computing --
    but NEVER returns a ranking whose fingerprint disagrees, because a mismatched
    one is worse than none: every score would be confidently wrong rather than
    missing.
    """
    if not os.path.exists(path) or not os.path.exists(path + ".meta"):
        return None
    want = game.fingerprint()
    got = None
    with open(path + ".meta") as m:
        for line in m:
            if line.startswith("fingerprint="):
                got = line.split("=", 1)[1].strip()
    if got != want:
        return None
    pos = {w: i for i, w in enumerate(game.guess_words)}
    scores = np.empty(game.NG, dtype=np.int64)
    order = np.empty(game.NG, dtype=np.int64)
    n = 0
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 3 or parts[0] == "rank":
                continue
            g = pos.get(parts[1])
            if g is None:
                return None                  # a guess the list does not hold
            order[n] = g
            scores[g] = int(parts[2])
            n += 1
    if n != game.NG:
        return None                          # truncated
    return scores, order


def ranking_path(width, data_dir=None):
    """The canonical place the root ranking for a width is stored."""
    return os.path.join(data_dir or _DATA, "root_rank_w%d.csv.gz" % width)


def progress_printer(every=10.0):
    """A progress callback that prints at most one line per `every` seconds.

    Shared by every long step here rather than reimplemented per tool: a step
    can have thousands of reports and most arrive instantly, so a line each is
    noise.  The signature is the one root_ranking and solve both call.
    """
    state = {"last": 0.0}

    def report(done, total, elapsed, note):
        if elapsed - state["last"] < every and done < total:
            return
        state["last"] = elapsed
        frac = done / total if total else 1.0
        eta = (elapsed / frac - elapsed) if frac > 0 else 0.0
        print("  %6.1f%%  %8d/%d  %7.1fs elapsed  ~%.0fs left   %s"
              % (100 * frac, done, total, elapsed, eta, note))
        sys.stdout.flush()

    return report


def safe_name(word):
    """A filename-safe spelling of an equation, reversibly.

    `/` cannot appear in a path and the rest read badly, so the operators map to
    letters: + p, - m, * t, / d, = e.  Digits and letters are disjoint, so the
    mapping is injective and `48-32=16` becomes `48m32e16` with no collisions.
    """
    return word.translate(str.maketrans("+-*/=", "pmtde"))


def attach_ranking(game, note=print, progress=None, compute=True):
    """Give `game` its root ranking: from disk if usable, else compute and store.

    ONE place decides that, so the solver and the pair screen cannot drift on
    when a stored ranking is trusted.  A ranking whose fingerprint disagrees is
    ignored and rebuilt -- never used -- and `note` says which happened, because
    a silent 110-second recompute looks like a hang.
    """
    path = ranking_path(game.width)
    stored = load_ranking(path, game)
    if stored is not None:
        game.set_root_ranking(*stored)
        note("root ranking: read %d guesses from %s" % (game.NG, path))
        return path, True
    if not compute:
        # A fixed opening never consults the root ranking -- the beam only starts
        # below it -- so there is no reason to spend 110s building one.
        note("root ranking: not stored, and not needed for a fixed opening")
        return path, False
    if os.path.exists(path):
        note("root ranking: %s does not match this guess and answer list "
             "(fingerprint %s) -- recomputing" % (path, game.fingerprint()))
    else:
        note("root ranking: %s not found -- computing it now (the slow step)"
             % path)
    game.root_ranking(progress=progress)
    save_ranking(path, game)
    note("root ranking: wrote %s" % path)
    return path, False


class NerdleTopK:
    """Top-K Nerdle solver over one (guess list, answer list) pair.

    Build once, then `expected_guesses()`.  `k` is the beam width and is the
    ONLY approximation: at every node, including the root, exactly the k
    best-scoring guesses are explored, so the answer is the best of the k
    examined and NOT an optimum over all 374246.
    """

    def __init__(self, *, width=WIDTH, k=1, guesses=None, answers=None,
                 use_numba=True, ranking=None):
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
        self._solved = None                  # (total, guess index), filled by solve()
        self._root = None                    # (scores, order), filled by root_ranking()
        if ranking is not None:
            self.set_root_ranking(*ranking)

    # ---- the root ranking, computed once ------------------------------------
    def root_ranking(self, progress=None, block=2000):
        """(score per guess, guess indices best first) over the whole answer set.

        MEMOISED, and the single source of the ranking for everything here: the
        beam's root, the pair screen and the printed table all read it.  It used
        to be recomputed at each, which at width 8 is about 110 seconds a time --
        a single solve paid it twice.

        SCORED IN BLOCKS OF `block` GUESSES so the run stays interruptible: a
        njit call does not return to the interpreter, so a single whole-list call
        swallows Ctrl-C for the entire two minutes.  `progress(done, total,
        elapsed, note)` is called between blocks.

        Ties break on the lower guess index, via a STABLE argsort over a list
        already in canonical symbol order.
        """
        if self._root is None:
            import time
            t0 = time.time()
            S = np.arange(self.NA, dtype=np.int64)
            scores = np.empty(self.NG, dtype=np.int64)
            if self.use_numba:
                for lo in range(0, self.NG, block):
                    hi = min(lo + block, self.NG)
                    _scores(self.G, self.A, S, self.gclass, self.aclass,
                            self.width, self._cnt, self._bins, self._touched,
                            scores, lo, hi)
                    if progress is not None:
                        progress(hi, self.NG, time.time() - t0, "scoring guesses")
            else:
                for g in range(self.NG):
                    keep = S[self.aclass[S] != self.gclass[g]]
                    codes = self._ref_patterns(g, keep)
                    counts = (np.bincount(codes) if codes.size
                              else np.zeros(0, dtype=np.int64))
                    scores[g] = int((counts.astype(np.int64) ** 2).sum())
            order = np.argsort(scores, kind="stable")
            self._root = (scores, order)
        return self._root

    def set_root_ranking(self, scores, order):
        """Install a ranking computed elsewhere -- see load_ranking().

        Only ever pass one built for THIS guess and answer list; the caller is
        responsible for that, and the disk format carries a fingerprint so the
        tools can check it rather than trusting a filename.
        """
        if len(scores) != self.NG or len(order) != self.NG:
            raise ValueError("a ranking of %d does not fit %d guesses"
                             % (len(order), self.NG))
        self._root = (np.asarray(scores, dtype=np.int64),
                      np.asarray(order, dtype=np.int64))

    def fingerprint(self):
        """What a stored ranking must match to be reusable."""
        import hashlib
        h = hashlib.sha1()
        for words in (self.guess_words, self.answer_words):
            h.update(("\n".join(words) + "\n").encode())
        return "%d:%d:%d:%d:%s" % (self.width, self.NG, self.NA, self.nclasses,
                                   h.hexdigest()[:16])

    # ---- the objective -----------------------------------------------------
    def solve(self, progress=None):
        """(total guesses over every answer, the opening guess).

        THE RESULT IS CACHED, because the search is minutes long and the total
        and the opener come out of the same walk.  Asking for them separately
        used to run it twice.

        THE ROOT IS DRIVEN FROM PYTHON so the run can report progress: the
        kernel handles each subtree, and this loop sees them completed one at a
        time.  It reproduces the recursion's root exactly -- same ranking, same
        bucket order, same running-cost cut -- and the gate checks the two
        against each other rather than trusting that.

        `progress(done, total, elapsed, note)` is called as buckets finish, with
        `done` the answers resolved so far out of `total`.  It is a real
        completion fraction, not a heartbeat, because the answer count is known
        before the walk starts.
        """
        if self._solved is None:
            self._solved = self._solve_root(progress)
        return self._solved

    def total_guesses(self, progress=None):
        """Guesses summed over every answer -- an integer, so exactly comparable."""
        return self.solve(progress)[0]

    def expected_guesses(self, progress=None):
        """Average guesses over the answer list, taken UNIFORMLY.

        Uniform over ANSWERS, not over classes: the hidden equation is drawn
        from the answer list, and two answers sharing a class are two different
        days that happen to be won by the same guess.
        """
        return self.total_guesses(progress) / self.NA

    def opener(self, progress=None):
        """The guess the beam plays first, as a word."""
        g = self.solve(progress)[1]
        return self.guess_words[g] if g >= 0 else None

    def _root_codes(self, g, S):
        """Feedback per candidate for root guess g; -1 where the guess WINS."""
        out = np.empty(S.shape[0], dtype=np.int64)
        if self.use_numba:
            _codes(self.G, g, self.A, S, self.gclass, self.aclass, self.width,
                   self._cnt, out)
            return out
        from wordle import pattern
        gc = self.gclass[g]
        for j, a in enumerate(S):
            out[j] = -1 if self.aclass[a] == gc else pattern(
                self.guess_words[g], self.answer_words[a])
        return out

    def _subtree(self, sub):
        return self._subtree_at(sub, 1)

    def solve_from(self, openers, progress=None):
        """(total guesses, the openers) with the opening FIXED and played BLIND.

        Each opener is played in order whatever the feedback says, exactly as a
        multiwordle opening is: an answer still alive pays for every opener up to
        and including the one that WINS it, and the beam takes over below them.

        SO A BLIND OPENING CAN WASTE A GUESS, and measuring that is the point.  A
        free beam adapts after the first reply; a fixed pair plays its second
        word even when the first already narrowed the answer to one class.
        Whether the pair's finer split repays that is exactly what this number
        answers, and it may well not.

        The openers must be legal guesses.  They need not be answers, and one
        that is not can never win -- only split.
        """
        import time
        t0 = time.time()
        gs = []
        for w in openers:
            try:
                gs.append(self.guess_words.index(w))
            except ValueError:
                raise ValueError("%r is not a legal guess" % w)

        alive = np.arange(self.NA, dtype=np.int64)
        keys = {int(a): [] for a in alive}
        cost = 0
        for step, g in enumerate(gs):
            cost += alive.size                # everyone still playing pays for it
            codes = self._root_codes(g, alive)
            live = codes >= 0                 # the rest are WON here and stop
            for a, c in zip(alive[live], codes[live]):
                keys[int(a)].append(int(c))
            alive = alive[live]
            if progress is not None:
                progress(self.NA - alive.size, self.NA, time.time() - t0,
                         "opener %d/%d (%s)" % (step + 1, len(gs),
                                                self.guess_words[g]))
            if alive.size == 0:
                break

        groups = {}
        for a in alive:
            groups.setdefault(tuple(keys[int(a)]), []).append(int(a))
        done = self.NA - alive.size
        for i, members in enumerate(sorted(groups.values())):
            sub = np.array(members, dtype=np.int64)
            cost += self._subtree_at(sub, len(gs))
            done += sub.size
            if progress is not None:
                progress(done, self.NA, time.time() - t0,
                         "bucket %d/%d" % (i + 1, len(groups)))
        return int(cost), list(openers)

    def _subtree_at(self, sub, depth):
        if self.use_numba:
            c, _ = _solve(self.G, self.A, sub, self.gclass, self.aclass,
                          self.width, self.k, depth, self._cnt, self._bins,
                          self._touched)
            return int(c)
        return int(self._ref_solve(sub, depth)[0])

    def _solve_root(self, progress=None):
        import time
        t0 = time.time()
        S = np.arange(self.NA, dtype=np.int64)
        _, ranked = self.root_ranking()
        order = [int(g) for g in ranked[:self.k]]

        best_cost, best_g = 1 << 60, -1
        for t, g in enumerate(order):
            codes = self._root_codes(g, S)
            keep = codes >= 0
            cost = self.NA                    # every answer pays for this guess
            done = int((~keep).sum())         # the ones this guess already won
            vals = np.unique(codes[keep])
            for i, pv in enumerate(vals):
                sub = S[codes == pv]
                cost += self._subtree(sub)
                done += sub.size
                if progress is not None:
                    # Reported across the WHOLE beam, not per root guess: with
                    # k > 1 a per-guess fraction runs to 100% and starts over,
                    # which reads as a stall or a restart.  A root guess cut
                    # short by the running-cost break makes the total jump
                    # forward, which is honest -- that work really is skipped.
                    progress(t * self.NA + done, len(order) * self.NA,
                             time.time() - t0, "root guess %d/%d, bucket %d/%d"
                             % (t + 1, len(order), i + 1, len(vals)))
                if cost >= best_cost:
                    break                     # the same cut the recursion makes
            if cost < best_cost:
                best_cost, best_g = int(cost), g
        return best_cost, best_g

    # ---- pair openers ------------------------------------------------------
    def pair_scores(self, top_n, progress=None):
        """Every pair drawn from the top_n single guesses, by joint sum of squares.

        Returns (the top_n guess indices, [(score, i, j)] sorted best first),
        where i and j index INTO that returned array.

        THIS IS A SCREEN, NOT A SEARCH.  Restricting to the best singles can miss
        the best pair outright: two guesses that split poorly alone may cover
        each other's blind spots, and nothing here would ever look at them.  The
        result is "the best pair among the top_n" -- a weaker claim than "the
        best pair", and it must be reported that way.

        The score is a heuristic for how well the pair SPLITS, exactly as the
        single-guess score is.  It is not expected guesses, and it does not know
        that an answer won by the first guess is cheaper than one won by the
        second -- both simply leave the partition.
        """
        S = np.arange(self.NA, dtype=np.int64)
        _, order = self.root_ranking()
        gs = order[:top_n].copy()
        nk = gs.size

        # int16 holds every pattern code (6560 at width 8) and the -1 marker, and
        # halves what is a 354 MB table at --top-n 10000.
        rows = np.empty((nk, self.NA), dtype=np.int16)
        if self.use_numba:
            import time
            t0 = time.time()
            npairs = nk * (nk - 1) // 2
            for lo in range(0, nk, 256):
                hi = min(lo + 256, nk)
                _rows(self.G, gs[lo:hi], self.A, S, self.gclass, self.aclass,
                      self.width, self._cnt, rows[lo:hi])
                if progress is not None:
                    progress(0, npairs, time.time() - t0,
                             "feedback rows %d/%d" % (hi, nk))
            out = np.zeros(npairs, dtype=np.int64)
            # npat*npat counters -- 172 MB at width 8.  Allocated once for the
            # whole sweep, not per pair.
            buf = np.zeros(self.NPAT * self.NPAT, dtype=np.int32)
            off = 0
            for i in range(nk):
                off = _pair_row(rows, i, np.int64(self.NPAT), buf, out, off)
                if progress is not None:
                    progress(off, npairs, time.time() - t0,
                             "first guess %d/%d" % (i + 1, nk))
        else:
            for r, g in enumerate(gs):
                rows[r] = self._root_codes(int(g), S)
            out = self._ref_pair_scores(rows)

        scored, t = [], 0
        for i in range(nk):
            for j in range(i + 1, nk):
                scored.append((int(out[t]), i, j))
                t += 1
        scored.sort()
        return gs, scored

    def _ref_pair_scores(self, rows):
        """The pair scores again, from numpy -- the oracle for _pair_scores."""
        n = rows.shape[0]
        out = np.zeros(n * (n - 1) // 2, dtype=np.int64)
        t = 0
        for i in range(n):
            for j in range(i + 1, n):
                keep = (rows[i] >= 0) & (rows[j] >= 0)
                joint = rows[i][keep].astype(np.int64) * self.NPAT + rows[j][keep]
                _, counts = np.unique(joint, return_counts=True)
                out[t] = int((counts.astype(np.int64) ** 2).sum())
                t += 1
        return out

    def _ref_rank_n(self, S, n):
        """The n best-ranked guesses from the numpy path (self.k is the beam)."""
        keep_k, self.k = self.k, n
        try:
            return list(self._ref_rank(S))
        finally:
            self.k = keep_k

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
