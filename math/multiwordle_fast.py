"""Numba kernels for the multiwordle rules.  `multiwordle.py` is the SPEC.

Nothing here decides anything: every rule is stated, argued and implemented in
`multiwordle.py`, and this module exists only because the opener race plays
billions of games and the reference implementation is a Python loop.  Whenever
the two disagree the reference is right.  `tools/checkmultiwordle.py` diffs them
guess for guess and is the reason to trust either.

TWO DELIBERATE DEPARTURES from the reference, both documented where they bite:

  * RANDOM DRAWS COME FROM A PRE-GENERATED FLOAT ARRAY, one array per GAME,
    shared by every candidate the race is comparing.  That is the coupling: two
    openings play the same game against the same coin flips, so the DIFFERENCE
    between their scores is far less noisy than either score.  It matches
    `multiwordle.CoupledRng` exactly -- one float per decision, indexed rather
    than rejection-sampled -- and is therefore a DIFFERENT SAMPLER from a bare
    numpy Generator.  A coupled run will not reproduce an uncoupled one.

  * THE RANKING IS A (6, 6) FLOAT TABLE rather than exact Fractions.  Safe, and
    checked rather than assumed: the pooled ratios have denominators under 4e6,
    so two DISTINCT ones differ by at least ~6e-14 against magnitudes of at most
    1, four orders above the double epsilon -- floats cannot merge two distinct
    compositions, and cannot split a genuinely tied pair either.  The gate
    asserts the float table induces the same order AND the same tie classes as
    the Fractions.

`turn2_table` is pure MEMOISATION and changes no answer: the second guess of
every game depends on the boards only through which of the opener's reply
buckets each fell into, so the whole (243, pool) table is a function of the
opener alone.  Building it once per opener replaces the single most expensive
search in a `minavg` game -- the one where the candidate sets are still large.
"""

import numpy as np

from wordle import ALL_GREEN, N_PATTERNS, WORD_LEN

try:
    from numba import njit, prange
    HAVE_NUMBA = True
except ImportError:                                   # pragma: no cover
    HAVE_NUMBA = False

    def njit(*a, **k):
        def wrap(f):
            return f
        return wrap(a[0]) if a and callable(a[0]) else wrap

    prange = range

# Rule codes for the kernels.  `minavg` has its own kernel; these two share one,
# differing only in how the board is chosen.
PICK_GREEDY = 0
PICK_SRANK = 1

_POW3 = np.array([3 ** (WORD_LEN - 1 - i) for i in range(WORD_LEN)],
                 dtype=np.int64)


@njit(cache=True)
def turn_bound(k, nopen):
    """Runaway ASSERTION bound on a game's length -- not a cap, and not the cap.

    The real bound from the termination arguments in `multiwordle.py` is
    `nopen + k * 2315`, which is far too large to size a per-game buffer with (a
    k=16 game would want 296 KB of scratch, allocated per parallel iteration, for
    a game that actually runs about 20 turns).  This is a generous safety net
    instead: 32 guesses per board plus 64.  Exceeding it means an invariant broke,
    and the kernel RAISES rather than truncating -- a truncated game would return
    a wrong score silently, which is the one outcome worth spending a bound to
    avoid.
    """
    return nopen + 32 * k + 64


def ranking_table(ranking):
    """The pooled singleton ranking as a (WORD_LEN+1, WORD_LEN+1) float array.

    Missing compositions get -1.0, which ranks below any real rate -- the same
    "rank last" convention `multiwordle.SingletonRank.value` uses.
    """
    tab = np.full((WORD_LEN + 1, WORD_LEN + 1), -1.0, dtype=np.float64)
    for (g, y), v in ranking.items():
        tab[g, y] = float(v)
    return tab


def guess_letter_table(guesses):
    """(n_guess, WORD_LEN) int8 of letter indices, for the composition update."""
    out = np.empty((len(guesses), WORD_LEN), dtype=np.int8)
    for i, w in enumerate(guesses):
        for j, c in enumerate(w):
            out[i, j] = ord(c) - 97
    return out


# --- average answers remaining --------------------------------------------

@njit(cache=True)
def _avg_row(pat, g, cand, lo, hi, counts, touched):
    """`a(g)` for one guess against candidates cand[lo:hi].

    Counts buckets with a scratch array reset only where it was touched, so the
    cost is O(number of candidates) rather than O(243) -- which matters, because
    late-game boards hold a handful of candidates and a 243-wide clear would then
    dominate the count it precedes.  The all-green bucket is skipped, so a solved
    board contributes nothing: see `multiwordle.average_remaining`.
    """
    m = hi - lo
    nt = 0
    for t in range(lo, hi):
        p = pat[g, cand[t]]
        if counts[p] == 0:
            touched[nt] = p
            nt += 1
        counts[p] += 1
    s = 0.0
    for u in range(nt):
        p = touched[u]
        if p != ALL_GREEN:
            c = np.float64(counts[p])
            s += c * c
        counts[p] = 0
    return s / m


@njit(cache=True, parallel=True)
def _turn2_kernel(pat, opener, pool, order, starts, out):
    """out[p, :] = a(g) for a board sitting in the opener's bucket p."""
    npool = pool.shape[0]
    nb = starts.shape[0] - 1
    for pi in prange(npool):
        g = pool[pi]
        counts = np.zeros(N_PATTERNS, dtype=np.int64)
        touched = np.empty(N_PATTERNS, dtype=np.int64)
        for b in range(nb):
            lo = starts[b]
            hi = starts[b + 1]
            if hi > lo:
                v = _avg_row(pat, g, order, lo, hi, counts, touched)
                out[b, pi] = v


def turn2_table(pat, opener, pool):
    """(243, len(pool)) table of `a(g)` per opener reply bucket.  Memoisation.

    Rows for patterns the opener cannot produce are left at zero and are never
    read: a board only ever sits in a bucket some answer actually produced.
    """
    na = pat.shape[1]
    row = pat[opener]
    order = np.argsort(row, kind="stable").astype(np.int64)
    counts = np.bincount(row, minlength=N_PATTERNS)
    starts = np.zeros(N_PATTERNS + 1, dtype=np.int64)
    np.cumsum(counts, out=starts[1:])
    out = np.zeros((N_PATTERNS, len(pool)), dtype=np.float64)
    _turn2_kernel(pat, opener, np.asarray(pool, dtype=np.int64), order,
                  starts, out)
    assert starts[-1] == na
    return out


# --- the lexicographic choice ---------------------------------------------

@njit(cache=True)
def _lex_argmin(vals, nb, npool, cur, best):
    """Column whose SORTED values are lexicographically smallest; ties on index.

    `vals` is (nb, npool) but only rows 0..nb-1 and columns 0..npool-1 are read,
    so the caller can hand in an oversized scratch buffer.
    """
    bestpi = -1
    for pi in range(npool):
        for b in range(nb):
            cur[b] = vals[b, pi]
        # insertion sort: nb is the board count, at most a couple of dozen
        for i in range(1, nb):
            v = cur[i]
            j = i - 1
            while j >= 0 and cur[j] > v:
                cur[j + 1] = cur[j]
                j -= 1
            cur[j + 1] = v
        if bestpi < 0:
            for b in range(nb):
                best[b] = cur[b]
            bestpi = pi
        else:
            for b in range(nb):
                if cur[b] < best[b]:
                    for c in range(nb):
                        best[c] = cur[c]
                    bestpi = pi
                    break
                elif cur[b] > best[b]:
                    break
    return bestpi


# --- the game loops --------------------------------------------------------

@njit(cache=True)
def _apply_guess(pat, g, answer_idx, cand, cnt, solved, k):
    """Play g on every unsolved board; returns the number newly solved.

    Filters each board's candidate list IN PLACE, which keeps it ascending (the
    reference gets the same order from flatnonzero, so the random pick indexes
    the same word) and costs O(candidates) rather than O(2315).
    """
    nsolved = 0
    for j in range(k):
        if solved[j]:
            continue
        fb = pat[g, answer_idx[j]]
        if fb == ALL_GREEN:
            solved[j] = True
            nsolved += 1
            continue
        w = 0
        for t in range(cnt[j]):
            a = cand[j, t]
            if pat[g, a] == fb:
                cand[j, w] = a
                w += 1
        cnt[j] = w
    return nsolved


@njit(cache=True)
def _update_composition(pinned, known, letters, code, j):
    """Fold one reply into board j's cumulative state (the reference's rule).

    A green PINS its position for good.  A letter's known count is the most any
    SINGLE reply proved, never a sum across replies -- and one reply proves
    exactly its number of non-gray tiles of that letter, since Wordle hands out
    min(copies in guess, copies in answer) of them.
    """
    for i in range(WORD_LEN):
        if (code // _POW3[i]) % 3 == 2:
            pinned[j, i] = letters[i]
    for i in range(WORD_LEN):
        if (code // _POW3[i]) % 3 == 0:
            continue
        c = letters[i]
        n = 0
        for i2 in range(WORD_LEN):
            if (code // _POW3[i2]) % 3 != 0 and letters[i2] == c:
                n += 1
        if n > known[j, c]:
            known[j, c] = n


@njit(cache=True)
def _composition(pinned, known, j, pc):
    greens = 0
    for c in range(26):
        pc[c] = 0
    for i in range(WORD_LEN):
        c = pinned[j, i]
        if c >= 0:
            pc[c] += 1
            greens += 1
    yellows = 0
    for c in range(26):
        extra = known[j, c] - pc[c]
        if extra > 0:
            yellows += extra
    return greens, yellows


@njit(cache=True)
def play_pick(pat, ans2g, answer_idx, openers, mode, rankval, letters,
              floats, played):
    """One game under `greedy` (mode 0) or `srank` (mode 1).

    Returns the number of guesses, or -1 if `floats` ran out (the caller regrows
    it and replays -- `Generator.random(n)` is prefix-consistent, so a longer
    array starts with the same values and the replayed game is the same game).

    DRAW DISCIPLINE: greedy consumes exactly ONE float per turn past the opening
    (the candidate pick); srank consumes exactly TWO (the board tie-break, always
    drawn even when nothing is tied, then the candidate pick).  Fixed per turn,
    so two coupled candidates stay in step.
    """
    k = answer_idx.shape[0]
    na = pat.shape[1]
    cand = np.empty((k, na), dtype=np.int32)
    cnt = np.empty(k, dtype=np.int64)
    for j in range(k):
        for a in range(na):
            cand[j, a] = a
        cnt[j] = na
    solved = np.zeros(k, dtype=np.bool_)
    pinned = np.full((k, WORD_LEN), -1, dtype=np.int8)
    known = np.zeros((k, 26), dtype=np.int8)
    pc = np.zeros(26, dtype=np.int8)
    nsolved = 0
    nplayed = 0
    fi = 0
    nf = floats.shape[0]
    nopen = openers.shape[0]
    max_turns = played.shape[0] - 1

    while True:
        if nplayed < nopen:
            g = openers[nplayed]
        elif mode == PICK_GREEDY:
            bestj = -1
            bestn = na + 1
            for j in range(k):
                if not solved[j] and cnt[j] < bestn:
                    bestn = cnt[j]
                    bestj = j                      # ties on the lowest index
            if fi >= nf:
                return -1
            u = floats[fi]
            fi += 1
            pick = int(u * cnt[bestj])
            if pick >= cnt[bestj]:
                pick = cnt[bestj] - 1
            g = ans2g[cand[bestj, pick]]
        else:
            bestv = -2.0
            ntied = 0
            for j in range(k):
                if solved[j]:
                    continue
                gr, ye = _composition(pinned, known, j, pc)
                v = rankval[gr, ye]
                if v > bestv:
                    bestv = v
                    ntied = 1
                elif v == bestv:
                    ntied += 1
            if fi + 1 >= nf:
                return -1
            u = floats[fi]
            fi += 1
            want = int(u * ntied)
            if want >= ntied:
                want = ntied - 1
            bestj = -1
            seen = 0
            for j in range(k):
                if solved[j]:
                    continue
                gr, ye = _composition(pinned, known, j, pc)
                if rankval[gr, ye] == bestv:
                    if seen == want:
                        bestj = j
                        break
                    seen += 1
            u = floats[fi]
            fi += 1
            pick = int(u * cnt[bestj])
            if pick >= cnt[bestj]:
                pick = cnt[bestj] - 1
            g = ans2g[cand[bestj, pick]]

        played[nplayed] = g
        nplayed += 1
        if nplayed > max_turns:
            raise AssertionError("game exceeded its turn bound")
        if mode == PICK_SRANK:
            for j in range(k):
                if not solved[j]:
                    _update_composition(pinned, known, letters[g],
                                        pat[g, answer_idx[j]], j)
        nsolved += _apply_guess(pat, g, answer_idx, cand, cnt, solved, k)
        if nsolved == k:
            return nplayed


@njit(cache=True)
def play_minavg(pat, answer_idx, openers, pool, turn2, use_turn2, played,
                vals, cur, best):
    """One deterministic `minavg` game.  Returns the number of guesses.

    `vals`, `cur` and `best` are caller-owned scratch, so the kernel allocates
    nothing per turn.  `turn2` is used only on the second guess, where every
    board's candidate set is exactly one of the opener's buckets.
    """
    k = answer_idx.shape[0]
    na = pat.shape[1]
    npool = pool.shape[0]
    cand = np.empty((k, na), dtype=np.int32)
    cnt = np.empty(k, dtype=np.int64)
    for j in range(k):
        for a in range(na):
            cand[j, a] = a
        cnt[j] = na
    solved = np.zeros(k, dtype=np.bool_)
    counts = np.zeros(N_PATTERNS, dtype=np.int64)
    touched = np.empty(N_PATTERNS, dtype=np.int64)
    nsolved = 0
    nplayed = 0
    nopen = openers.shape[0]
    max_turns = played.shape[0] - 1

    while True:
        if nplayed < nopen:
            g = openers[nplayed]
        else:
            nb = 0
            for j in range(k):
                if solved[j]:
                    continue
                if use_turn2 and nplayed == 1:
                    p = pat[openers[0], cand[j, 0]]
                    for pi in range(npool):
                        vals[nb, pi] = turn2[p, pi]
                else:
                    for pi in range(npool):
                        vals[nb, pi] = _avg_row(pat, pool[pi], cand[j], 0,
                                                cnt[j], counts, touched)
                nb += 1
            g = pool[_lex_argmin(vals, nb, npool, cur, best)]

        played[nplayed] = g
        nplayed += 1
        if nplayed > max_turns:
            raise AssertionError("game exceeded its turn bound")
        nsolved += _apply_guess(pat, g, answer_idx, cand, cnt, solved, k)
        if nsolved == k:
            return nplayed


# --- batch drivers ---------------------------------------------------------

@njit(cache=True, parallel=True)
def run_pick_block(pat, ans2g, answers, openings, mode, rankval, letters,
                   floats, scores):
    """Every opening x every game, parallel over OPENINGS.

    `answers` is (ngames, k) and `floats` is (ngames, nf): every opening faces
    the identical games AND the identical coin flips, which is the whole point.
    A score of -1 means that game ran out of floats.
    """
    ncand = openings.shape[0]
    ngames = answers.shape[0]
    maxlen = turn_bound(answers.shape[1], openings.shape[1])
    for c in prange(ncand):
        played = np.empty(maxlen, dtype=np.int64)
        for i in range(ngames):
            n = play_pick(pat, ans2g, answers[i], openings[c], mode, rankval,
                          letters, floats[i], played)
            scores[c, i] = n


@njit(cache=True, parallel=True)
def run_minavg_games(pat, answers, opening, pool, turn2, use_turn2, scores):
    """One opening's games, parallel over GAMES.

    `minavg` parallelises over games rather than openings because its memoised
    turn-2 table is a function of the OPENING: a batch over openings would need
    one table each, and at 243 x 12972 doubles that is 25 MB apiece.
    """
    ngames = answers.shape[0]
    k = answers.shape[1]
    npool = pool.shape[0]
    maxlen = turn_bound(k, opening.shape[0])
    for i in prange(ngames):
        played = np.empty(maxlen, dtype=np.int64)
        vals = np.empty((k, npool), dtype=np.float64)
        cur = np.empty(k, dtype=np.float64)
        best = np.empty(k, dtype=np.float64)
        scores[i] = play_minavg(pat, answers[i], opening, pool, turn2,
                                use_turn2, played, vals, cur, best)
