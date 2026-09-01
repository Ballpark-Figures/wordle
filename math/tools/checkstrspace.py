"""Verify the constraint representation in `strspace.py` against brute force.

`strspace` claims a candidate set over every length-L string can be carried as
per-position letter masks plus per-letter count bounds, refined by a (guess,
pattern) pair, and SIZED without enumerating. Each of those is checkable
exactly, and this checks them exhaustively rather than by sampling:

  1. EXHAUSTIVE, small alphabet. For alpha=4/length=3 and alpha=3/length=4,
     walk EVERY guess and EVERY reachable state to depth 2 and compare
     `count(st)` with `len(enumerate_strings(st))`, and each partition against
     an explicit filter of the whole string space. Small enough that "every"
     is literal, which is the only way to be sure the repeated-letter cases are
     all covered.

  2. AGREEMENT WITH `wordle.pattern`. The refinement is derived from the tile
     codes; the repo's own feedback function is the independent authority on
     what those codes mean. A string survives `refine(st, g, p)` if and only if
     `pattern(g, s) == p`. Checked over the full small space.

  3. THE REAL SPACE, alpha=26/length=5. 11,881,376 strings is enumerable ONCE
     in numpy, so the production-sized counts are checked against an actual
     filter of the actual space -- not extrapolated from the small cases.

Exit status is nonzero if anything failed, so it works as a gate. Run it
alongside `solver/validate.sh` and `tools/checkpatterns.py`.
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wordle import pattern
import strspace

fails = []


def _letters(codes):
    return "".join(chr(ord("a") + c) for c in codes)


def exhaustive(alpha, length, depth=2):
    """Every guess, every reachable state, to `depth`. Checks 1 and 2."""
    space = list(itertools.product(range(alpha), repeat=length))
    guesses = space
    checked = 0

    def walk(st, alive, d):
        nonlocal checked
        # 1. the count must equal the brute-force size
        n = strspace.count(st)
        if n != len(alive):
            fails.append("a=%d L=%d: count %d != brute force %d for %r"
                         % (alpha, length, n, len(alive), st))
        # ... and the state's own enumeration must be that same set
        if set(strspace.enumerate_strings(st)) != set(alive):
            fails.append("a=%d L=%d: enumerate_strings disagrees for %r" % (alpha, length, st))
        checked += 1
        if d == 0:
            return
        for g in guesses:
            parts = strspace.partition(st, g)
            # 2. refine must agree with wordle.pattern, part by part
            buckets = {}
            for s in alive:
                buckets.setdefault(pattern(_letters(g), _letters(s)), []).append(s)
            if set(parts) != set(buckets):
                fails.append("a=%d L=%d: guess %s partition keys differ (%d vs %d)"
                             % (alpha, length, _letters(g), len(parts), len(buckets)))
                continue
            if sum(c for _, c in parts.values()) != len(alive):
                fails.append("a=%d L=%d: guess %s parts do not sum to the whole"
                             % (alpha, length, _letters(g)))
            for code, (sub, c) in parts.items():
                if c != len(buckets[code]):
                    fails.append("a=%d L=%d: guess %s code %d: %d != %d"
                                 % (alpha, length, _letters(g), code, c, len(buckets[code])))
                walk(sub, buckets[code], d - 1)

    walk(strspace.initial(length, alpha), space, depth)
    print("  alpha=%d length=%d depth=%d: %d states checked against brute force"
          % (alpha, length, depth, checked))


def real_space(guesses, length=5, alpha=26):
    """Check 3: production-sized counts against an actual filter of 26**5."""
    n = alpha ** length
    print("  materialising all %d strings ..." % n)
    cols = []
    for i in range(length):
        rep = alpha ** (length - 1 - i)
        cols.append(np.tile(np.repeat(np.arange(alpha, dtype=np.uint8), rep),
                            n // (rep * alpha)))
    space = np.stack(cols, axis=1)
    assert space.shape == (n, length)

    st0 = strspace.initial(length, alpha)
    if strspace.count(st0) != n:
        fails.append("root count %d != %d" % (strspace.count(st0), n))

    for gw in guesses:
        g = [ord(ch) - ord("a") for ch in gw]
        parts = strspace.partition(st0, g)
        if sum(c for _, c in parts.values()) != n:
            fails.append("%s: parts sum to %d, not %d"
                         % (gw, sum(c for _, c in parts.values()), n))
        # brute-force the same partition over the whole space
        pats = np.zeros(n, dtype=np.int32)
        garr = np.array(g, dtype=np.uint8)
        greens = np.zeros((n, length), dtype=bool)
        for i in range(length):
            greens[:, i] = space[:, i] == garr[i]
        used = greens.copy()
        tiles = greens.astype(np.int8) * 2
        for i in range(length):
            need = tiles[:, i] == 0
            for j in range(length):
                hit = need & ~used[:, j] & (space[:, j] == garr[i])
                tiles[hit, i] = 1
                used[hit, j] = True
                need = need & ~hit
        for i in range(length):
            pats = pats * 3 + tiles[:, i]
        codes, counts = np.unique(pats, return_counts=True)
        brute = dict(zip(codes.tolist(), counts.tolist()))
        mine = {k: c for k, (_, c) in parts.items()}
        if mine != brute:
            only = set(mine) ^ set(brute)
            bad = [k for k in set(mine) & set(brute) if mine[k] != brute[k]]
            fails.append("%s: %d key(s) differ, %d count(s) differ"
                         % (gw, len(only), len(bad)))
        else:
            print("  %s: %d non-empty patterns, all counts match brute force"
                  % (gw, len(mine)))
        # the 5 unreachable codes must be exactly the L-1 greens + 1 yellow ones
        missing = [c for c in range(3 ** length) if c not in mine]
        if len(set(gw)) == length and len(missing) != length:
            fails.append("%s: %d unreachable codes, expected %d"
                         % (gw, len(missing), length))


print("exhaustive small-alphabet check")
exhaustive(4, 3, depth=2)
exhaustive(3, 4, depth=2)

print("\nreal space (26**5)")
real_space(["salet", "abbey", "esses"])

print("\n%d failure(s)" % len(fails))
for f in fails[:20]:
    print("  " + f)
sys.exit(1 if fails else 0)
