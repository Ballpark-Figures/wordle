"""The numba feedback kernel for Letroso -- the fast path, nothing else.

letroso.py states the rules and holds both the reference port (the oracle) and a
pure-python exact implementation.  This module is the same function again in a
form numba can compile: fixed-size arrays, an explicit DFS stack instead of
recursion, and the pattern carried down as a packed integer so backtracking
needs no mutable state.

PACKING.  Guess position 0 goes in the HIGH bits, so plain integer `>` IS the
lexicographic left-to-right comparison the game's tie-break uses.  Two bits per
position plus the two flags; at MAXLEN=10 a code fits in 22 bits.

tools/checkletroso.py differential-tests this against letroso.feedback_ref over
every pair of a small alphabet, which is the only reason to trust it.
"""

import numpy as np

try:
    from numba import njit
except ImportError:                                    # pragma: no cover
    def njit(*a, **k):
        def deco(f):
            return f
        return deco if not a or not callable(a[0]) else a[0]

_BIG = 1000
MAXLEN = 10
_STACK = 256


@njit(cache=True, inline="always")
def _pack(digit, j, G):
    return digit << (2 * (G - 1 - j))


@njit(cache=True)
def fb_code(n, A, r, G, best, stack, leftover):
    """Feedback code for guess r[:G] against answer n[:A].

    `best`, `stack`, `leftover` are caller-owned scratch, so the hot loop does
    no allocation.  Returns the packed pattern with the two flags on top.
    """
    U = A if A < G else G

    # ---- backward DP: best[i, j, u] = max achievable m*_BIG + d from here ----
    for i in range(A, -1, -1):
        for j in range(G, -1, -1):
            match = 0
            b = 0
            if i < A and j < G and n[i] == r[j]:
                match = 1
                if i == 0 and j == 0:
                    b += 1
                if i == A - 1 and j == G - 1:
                    b += 1
            for u in range(U, -1, -1):
                if i == A and j == G:
                    best[i, j, u] = 0
                    continue
                v = -1
                if i < A and best[i + 1, j, 0] > v:
                    v = best[i + 1, j, 0]
                if j < G and best[i, j + 1, 0] > v:
                    v = best[i, j + 1, 0]
                if match == 1 and u < U:
                    x = _BIG + 3 * (u + 1) + b + best[i + 1, j + 1, u + 1]
                    if x > v:
                        v = x
                best[i, j, u] = v

    # ---- DFS over the OPTIMAL alignments only, carrying the pattern packed ----
    best_pat = -1
    best_en = 0
    best_st = 0

    sp = 0
    stack[sp, 0] = 0    # i
    stack[sp, 1] = 0    # j
    stack[sp, 2] = 0    # u
    stack[sp, 3] = 0    # start
    stack[sp, 4] = 0    # end
    stack[sp, 5] = 0    # packed pattern so far
    sp = 1

    while sp > 0:
        sp -= 1
        i = stack[sp, 0]
        j = stack[sp, 1]
        u = stack[sp, 2]
        st = stack[sp, 3]
        en = stack[sp, 4]
        pcode = stack[sp, 5]
        cur = best[i, j, u]

        if i == A and j == G:
            # ---- leaf: apply the `present` pass, then compare ----
            for c in range(26):
                leftover[c] = 0
            for k in range(A):
                leftover[n[k]] += 1
            nmatch = 0
            last_m = -1
            for k in range(G):
                d = (pcode >> (2 * (G - 1 - k))) & 3
                if d != 0:
                    leftover[r[k]] -= 1
                    nmatch += 1
                    last_m = k
            full = pcode
            for k in range(G):
                d = (pcode >> (2 * (G - 1 - k))) & 3
                if d == 0 and leftover[r[k]] > 0:
                    full |= _pack(1, k, G)
                    leftover[r[k]] -= 1
            if nmatch == 1 and st == 0 and en == 0:
                full &= ~(3 << (2 * (G - 1 - last_m)))
                full |= _pack(1, last_m, G)
            if full > best_pat or (full == best_pat and
                                   (en > best_en or (en == best_en and st > best_st))):
                best_pat = full
                best_en = en
                best_st = st
            continue

        if i < A and best[i + 1, j, 0] == cur:
            stack[sp, 0] = i + 1
            stack[sp, 1] = j
            stack[sp, 2] = 0
            stack[sp, 3] = st
            stack[sp, 4] = en
            stack[sp, 5] = pcode
            sp += 1
        if j < G and best[i, j + 1, 0] == cur:
            stack[sp, 0] = i
            stack[sp, 1] = j + 1
            stack[sp, 2] = 0
            stack[sp, 3] = st
            stack[sp, 4] = en
            stack[sp, 5] = pcode
            sp += 1
        if i < A and j < G and n[i] == r[j] and u < U:
            b = 0
            if i == 0 and j == 0:
                b += 1
            if i == A - 1 and j == G - 1:
                b += 1
            if best[i + 1, j + 1, u + 1] + _BIG + 3 * (u + 1) + b == cur:
                stack[sp, 0] = i + 1
                stack[sp, 1] = j + 1
                stack[sp, 2] = u + 1
                stack[sp, 3] = 1 if (st == 1 or (i == 0 and j == 0)) else 0
                stack[sp, 4] = 1 if (en == 1 or (i == A - 1 and j == G - 1)) else 0
                stack[sp, 5] = pcode | _pack(3 if u > 0 else 2, j, G)
                sp += 1

    return best_pat | (best_st << (2 * G)) | (best_en << (2 * G + 1))


def scratch():
    """Per-thread scratch for fb_code: (best, stack, leftover)."""
    return (np.empty((MAXLEN + 1, MAXLEN + 1, MAXLEN + 2), np.int32),
            np.empty((_STACK, 6), np.int64),
            np.empty(26, np.int32))


def encode_words(words):
    """(codes, lengths) -- letters as 0..25, right-padded."""
    W = np.zeros((len(words), MAXLEN), np.int8)
    L = np.empty(len(words), np.int8)
    for i, w in enumerate(words):
        L[i] = len(w)
        for j, ch in enumerate(w):
            W[i, j] = ord(ch) - 97
    return W, L
