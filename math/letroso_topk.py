"""A top-K Letroso solver, ranking guesses by expected candidates left alive.

THE OBJECTIVE, stated exactly: the EXPECTED NUMBER OF GUESSES to finish, over
the answer list under the chosen LENGTH PRIOR.  There is NO GUESS CAP -- Letroso
gives you unlimited attempts -- so this is expected guesses OUTRIGHT, never
"subject to a guarantee".  That is the same footing as the nerdle_topk,
multiwordle and adversarial numbers, and NOT the footing of any
optturns/hardturns/ansall total.  Never put the two in one table.

THE LENGTH PRIOR IS PART OF THE OBJECTIVE and has NO DEFAULT.  Letroso's answer
length varies and we do not know how the game picks it, so the two readings give
genuinely different optima and the caller must say which:

    lengths -- pick a LENGTH uniformly, then a word uniformly within it.  Each
               of the 8 lengths carries 1/8 of the mass, so the 707 three-letter
               answers weigh as much as the 5327 eight-letter ones.
    words   -- pick a WORD uniformly from the pooled list.  Length weight is
               then whatever each length happens to contribute, 3.2% at L=3.

THE STRATEGY, stated exactly.  At every node each legal guess is scored by

    score(g) = SUM over feedback bins b != the winning bin of  n_b * W_b

ascending, ties broken on the LOWEST GUESS INDEX -- n_b the number of candidates
in the bin and W_b their summed weight, so this is the expected number of
candidate WORDS still alive.  That is topk.py's rule, the one the adversarial
hill-climb uses, chosen deliberately over sum-of-squared-bin-sizes because the
answers here are NOT equally likely.  It reduces to the familiar count rule when
the weights are uniform.  The solver then recurses into the K best and keeps
whichever actually minimises the total, so K=1 is no lookahead at all.

IT IS A BEAM, NOT AN OPTIMUM.  `-k K` restricts the ROOT too, so the opener is
the best of the K examined, not the best of all 139072.  Each K is a different
strategy and gets its own file.  Same caveat strturns and nerdle_topk carry.

WHY MAXD CANNOT BIND.  Every answer is a legal guess (build_letroso_lists.py
enforces it), so at any node the solver may play a candidate, which wins that
candidate and splits the rest; such a guess outranks any that fails to split, so
the beam always holds one and every child is strictly smaller.  MAXD is a guard
against that reasoning being wrong, not a cap on the search.

THE FEEDBACK IS THE EXPENSIVE PART.  There is no pattern matrix -- 139072 x
30403 int32 would be 17 GB -- so feedback is computed in the kernel, and a level
costs the guess count times the candidates alive at that level.  The ROOT
RANKING is therefore computed ONCE and cached; see save_ranking/load_ranking and
solver/run-letroso-rank.sh.  Measured 15.9 us/pair, so a full root scan is ~19
core-hours.
"""

from __future__ import annotations

import gzip
import os

import numpy as np

import letroso
from letroso_kernel import MAXLEN, encode_words, fb_code, scratch

try:
    from numba import njit, prange
    _HAVE_NUMBA = True
except ImportError:                                    # pragma: no cover
    _HAVE_NUMBA = False

    def njit(*a, **k):
        def deco(f):
            return f
        return deco if not a or not callable(a[0]) else a[0]
    prange = range

MAXD = 32              # recursion guard; see the docstring -- NOT a cap
PRIORS = ("lengths", "words")
_HSIZE = 1 << 17       # open-addressed bin table; > 2x the answer count
_CHUNK = 256           # guesses per parallel chunk, so scratch is per chunk

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "data", "shared", "letroso")


def weights(answers, prior):
    """Per-answer probability under the named prior.  Sums to 1."""
    if prior not in PRIORS:
        raise SystemExit("--length-prior must be one of %s, not %r"
                         % (", ".join(PRIORS), prior))
    w = np.empty(len(answers), np.float64)
    if prior == "words":
        w[:] = 1.0 / len(answers)
        return w
    byline = {}
    for a in answers:
        byline[len(a)] = byline.get(len(a), 0) + 1
    share = 1.0 / len(byline)
    for i, a in enumerate(answers):
        w[i] = share / byline[len(a)]
    return w


@njit(cache=True)
def _score_chunk(Wg, Lg, Wa, La, w, lo, hi, out):
    """Score guesses [lo, hi) against every answer.  One chunk, one scratch set."""
    NA = Wa.shape[0]
    best = np.empty((MAXLEN + 1, MAXLEN + 1, MAXLEN + 2), np.int32)
    stack = np.empty((256, 6), np.int64)
    left = np.empty(26, np.int32)
    keys = np.full(_HSIZE, -1, np.int64)
    cnt = np.zeros(_HSIZE, np.int64)
    wsum = np.zeros(_HSIZE, np.float64)
    touched = np.empty(NA, np.int64)

    for gi in range(lo, hi):
        G = Lg[gi]
        # The winning bin is the reply a guess gives against ITSELF: the whole
        # guess aligned as one block, reaching both ends.  Only the guess word
        # can produce it, so excluding it is exactly topk.py's `p != ALL_GREEN`.
        win = fb_code(Wg[gi], G, Wg[gi], G, best, stack, left)
        nt = 0
        for ai in range(NA):
            code = fb_code(Wa[ai], La[ai], Wg[gi], G, best, stack, left)
            h = (code * 0x9E3779B1) & (_HSIZE - 1)
            while keys[h] != -1 and keys[h] != code:
                h = (h + 1) & (_HSIZE - 1)
            if keys[h] == -1:
                keys[h] = code
                touched[nt] = h
                nt += 1
            cnt[h] += 1
            wsum[h] += w[ai]
        score = 0.0
        for t in range(nt):
            h = touched[t]
            if keys[h] != win:
                score += cnt[h] * wsum[h]
            keys[h] = -1
            cnt[h] = 0
            wsum[h] = 0.0
        out[gi] = score


@njit(parallel=True, cache=True)
def _score_all(Wg, Lg, Wa, La, w, out, c0, c1):
    """Score chunks [c0, c1) in parallel.

    TAKES A RANGE, NOT A COUNT.  It used to prange(nchunk) from zero while the
    driver passed the running total, so every call re-scored every chunk from
    the beginning -- quadratic work, 136x over a full 139072-opener run, and the
    tell was an ETA that CLIMBED instead of holding steady.
    """
    for c in prange(c0, c1):
        lo = c * _CHUNK
        hi = lo + _CHUNK
        if hi > Wg.shape[0]:
            hi = Wg.shape[0]
        _score_chunk(Wg, Lg, Wa, La, w, lo, hi, out)


def rank_root(guesses, answers, w, progress=None, checkpoint=None, fp=None):
    """Score every guess against every answer.  Returns the score array.

    THE SLOW STEP, and deliberately chunked for two reasons.  A njit call never
    returns to the interpreter, so a single call over all 139072 guesses would
    make Ctrl-C do nothing for hours and report no progress.  And at ~19
    core-hours this job MUST survive an interruption -- a Ctrl-C, or the Windows
    Update reboot the machine takes on its own -- so it CHECKPOINTS.

    `checkpoint` is a .npz path under data/local/ (regenerable bulk).  It holds
    the partial scores, how many chunks are done, and the fingerprint; a
    checkpoint whose fingerprint does not match is IGNORED, never resumed from,
    for the same reason a foreign ranking is refused.  It is written atomically
    via a temp file and rename, so a crash mid-write cannot corrupt it, and is
    removed once the full ranking is saved.
    """
    Wg, Lg = encode_words(guesses)
    Wa, La = encode_words(answers)
    out = np.zeros(len(guesses), np.float64)
    nchunk = (len(guesses) + _CHUNK - 1) // _CHUNK
    done = 0

    if checkpoint and os.path.exists(checkpoint):
        try:
            z = np.load(checkpoint)
            if fp is not None and str(z["fp"]) == fp and z["scores"].shape == out.shape:
                out = z["scores"]
                done = int(z["done"])
                print("resuming from checkpoint: %d/%d chunks already scored"
                      % (done, nchunk))
            else:
                print("checkpoint %s does not match this fingerprint -- ignoring it"
                      % checkpoint)
        except Exception as exc:                      # pragma: no cover
            print("unreadable checkpoint %s (%s) -- starting over"
                  % (checkpoint, exc))


    step = max(1, nchunk // 200)
    # Counts chunk-scorings so the gate can prove no chunk is scored twice --
    # see the note on _score_all.
    chunks_scored = [0]
    while done < nchunk:
        end = min(nchunk, done + step)
        _score_all(Wg, Lg, Wa, La, w, out, done, end)
        chunks_scored[0] += end - done
        # Published per iteration, not at the end, so it is still readable after
        # an interrupt -- which is exactly when it is worth reading.
        rank_root.chunks_scored = chunks_scored[0]
        rank_root.nchunk = nchunk
        done = end
        if checkpoint:
            os.makedirs(os.path.dirname(checkpoint), exist_ok=True)
            # np.savez appends .npz itself, so name the temp file with it and
            # rename that -- the rename is what makes the write atomic.
            tmp = checkpoint + ".tmp.npz"
            np.savez(tmp, scores=out, done=done, fp=(fp or ""))
            os.replace(tmp, checkpoint)
        if progress:
            progress(min(done * _CHUNK, len(guesses)), len(guesses))
    rank_root.chunks_scored = chunks_scored[0]
    rank_root.nchunk = nchunk
    return out


def clear_checkpoint(path):
    """Drop a checkpoint once the full ranking is safely saved."""
    if path and os.path.exists(path):
        os.remove(path)


def fingerprint(guesses, answers, prior):
    """Identify the lists AND the prior a cached ranking was built under.

    A mismatch must be REFUSED, never used: reusing a foreign ranking would make
    every score confidently wrong rather than missing -- the same hazard a
    foreign tt.bin carries next door.
    """
    import hashlib
    h = hashlib.sha256()
    h.update(("%s|%d|%d|" % (prior, len(guesses), len(answers))).encode())
    h.update("".join(guesses).encode())
    h.update("".join(answers).encode())
    return h.hexdigest()[:16]


def save_ranking(path, guesses, scores, fp, prior):
    order = np.argsort(scores, kind="stable")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write("# letroso root ranking -- a RANKING, NOT A RESULT.\n")
        f.write("# A good first-guess score says nothing about what happens\n")
        f.write("# after the reply; quote the solver's number, not this one.\n")
        f.write("# fingerprint=%s prior=%s\n" % (fp, prior))
        f.write("rank,guess,score\n")
        for i, gi in enumerate(order):
            f.write("%d,%s,%.6f\n" % (i + 1, guesses[gi], scores[gi]))


def load_ranking(path, fp):
    """Return (guesses, scores) or None when the file is absent or foreign."""
    if not os.path.exists(path):
        return None
    words, scores, ok = [], [], False
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                if "fingerprint=%s" % fp in line:
                    ok = True
                continue
            if line.startswith("rank,"):
                continue
            _, wd, sc = line.rstrip("\n").split(",")
            words.append(wd)
            scores.append(float(sc))
    if not ok:
        return None
    return words, np.array(scores)


@njit(cache=True)
def _partition(Wg, Lg, Wa, La, w, gi, cand, out_codes, best, stack, left):
    """Feedback code for each live candidate against guess gi."""
    G = Lg[gi]
    for t in range(cand.shape[0]):
        ai = cand[t]
        out_codes[t] = fb_code(Wa[ai], La[ai], Wg[gi], G, best, stack, left)
    return fb_code(Wg[gi], G, Wg[gi], G, best, stack, left)


@njit(cache=True)
def _score_node(Wg, Lg, Wa, La, w, cand, out, keys, cnt, wsum, touched,
                best, stack, left):
    """score(g) over the live candidates, for every guess.  See the module docstring."""
    NG = Wg.shape[0]
    n = cand.shape[0]
    for gi in range(NG):
        G = Lg[gi]
        win = fb_code(Wg[gi], G, Wg[gi], G, best, stack, left)
        nt = 0
        for t in range(n):
            ai = cand[t]
            code = fb_code(Wa[ai], La[ai], Wg[gi], G, best, stack, left)
            h = (code * 0x9E3779B1) & (_HSIZE - 1)
            while keys[h] != -1 and keys[h] != code:
                h = (h + 1) & (_HSIZE - 1)
            if keys[h] == -1:
                keys[h] = code
                touched[nt] = h
                nt += 1
            cnt[h] += 1
            wsum[h] += w[ai]
        score = 0.0
        for t in range(nt):
            h = touched[t]
            if keys[h] != win:
                score += cnt[h] * wsum[h]
            keys[h] = -1
            cnt[h] = 0
            wsum[h] = 0.0
        out[gi] = score


class Solver:
    """The beam.  `solve()` is CACHED: the total and the opener come from ONE
    walk, so asking for them separately must not run the search twice."""

    def __init__(self, guesses, answers, prior, k=1, root_scores=None):
        self.guesses = guesses
        self.answers = answers
        self.prior = prior
        self.k = k
        self.w = weights(answers, prior)
        self.Wg, self.Lg = encode_words(guesses)
        self.Wa, self.La = encode_words(answers)
        self.g2i = {g: i for i, g in enumerate(guesses)}
        self.ans2g = np.array([self.g2i[a] for a in answers], np.int64)
        self.root_scores = root_scores
        self._cache = None
        self._best = np.empty((MAXLEN + 1, MAXLEN + 1, MAXLEN + 2), np.int32)
        self._stack = np.empty((256, 6), np.int64)
        self._left = np.empty(26, np.int32)
        self._keys = np.full(_HSIZE, -1, np.int64)
        self._cnt = np.zeros(_HSIZE, np.int64)
        self._wsum = np.zeros(_HSIZE, np.float64)
        self._touched = np.empty(len(answers), np.int64)
        self._scores = np.empty(len(guesses), np.float64)

    def _rank(self, cand, at_root):
        if at_root and self.root_scores is not None:
            scores = self.root_scores
        else:
            _score_node(self.Wg, self.Lg, self.Wa, self.La, self.w, cand,
                        self._scores, self._keys, self._cnt, self._wsum,
                        self._touched, self._best, self._stack, self._left)
            scores = self._scores
        return np.argsort(scores, kind="stable")[:self.k]

    def _solve(self, cand, depth, at_root=False):
        """(weighted cost, best guess index) for this candidate set."""
        if cand.shape[0] == 1:
            return self.w[cand[0]], self.ans2g[cand[0]]
        if depth >= MAXD:
            raise RuntimeError("MAXD hit -- see the docstring; this should be "
                               "impossible while answers are legal guesses")
        total_w = self.w[cand].sum()
        best_cost, best_g = None, -1
        for gi in self._rank(cand, at_root):
            gi = int(gi)
            codes = np.empty(cand.shape[0], np.int64)
            win = _partition(self.Wg, self.Lg, self.Wa, self.La, self.w, gi,
                             cand, codes, self._best, self._stack, self._left)
            cost = total_w
            for code in np.unique(codes):
                if code == win:
                    continue
                sub = cand[codes == code]
                cost += self._solve(sub, depth + 1)[0]
            if best_cost is None or cost < best_cost:
                best_cost, best_g = cost, gi
        return best_cost, best_g

    def solve(self):
        if self._cache is None:
            cand = np.arange(len(self.answers), dtype=np.int64)
            cost, gi = self._solve(cand, 0, at_root=True)
            self._cache = (cost, self.guesses[gi])
        return self._cache
