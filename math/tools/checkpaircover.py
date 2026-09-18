"""Gate for math/paircover.py -- the loop, against what it claims.

    python3 tools/checkpaircover.py

FOUR CHECKS, each against a route that shares no machinery with the thing it
checks:

  1  the SPLIT MATRIX against `wordle.pattern` recomputed from the STRINGS;
  2  the LOSING ANSWERS three ways -- the harvest's own walk, `greedybuild`'s
     objective, and `guarantee_sweep.check_opening` -- which must agree
     exactly, since they are three implementations of one number;
  3  every HARVESTED PAIR replayed from the strings: the two words must share a
     bucket AND some live draw must fail to separate them, or the pair is not a
     failure and would steer the next round at nothing;
  4  BRANCH MONOTONICITY in k, with coverage ASSERTED -- it fails if a wider K
     never changed the answer, so a pass cannot mean it went untested.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                                  # noqa: E402
from greedybuild import score                                             # noqa: E402
from guarantee import stop_levels                                         # noqa: E402
from opening_list import resolve_word_set                                 # noqa: E402
from paircover import harvest, joint_key, pool_matrix, split_matrix       # noqa: E402
from wordle import load_words, pattern, to_codes                          # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guarantee_sweep import check_opening                                 # noqa: E402
from pair_cover import build_opening, seed_pairs                          # noqa: E402

SEED = "data/shared/answerpairs/pairsplit_mystery_by-custom.csv"


def main(argv):
    failures = []
    rng = np.random.default_rng(0)
    guesses, answers = load_words("guess"), load_words("mystery")
    pool = sorted(resolve_word_set("custom"))
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(pool)}
    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    codes = to_codes(pool)
    ans = np.array([ppos[w] for w in answers])
    M = pool_matrix(full, cols)

    # --- 1: the split matrix, from the strings -----------------------------
    ia = rng.integers(len(pool), size=40)
    ib = rng.integers(len(pool), size=40)
    S = split_matrix(M, ia, ib)
    cand = rng.integers(len(pool), size=25)
    for c in cand:
        for p in range(len(ia)):
            want = pattern(pool[c], pool[ia[p]]) != pattern(pool[c], pool[ib[p]])
            if bool(S[c, p]) != want:
                failures.append("split matrix: %s on %s/%s is %s, strings say %s"
                                % (pool[c], pool[ia[p]], pool[ib[p]],
                                   S[c, p], want))
                break
    print("split matrix: %d candidates x %d pairs match the strings"
          % (len(cand), len(ia)))

    # --- build one real opening to check against ---------------------------
    seed = seed_pairs(SEED, 400, ppos)
    keys = sorted(seed)
    S_all = split_matrix(M, np.array([p[0] for p in keys]),
                         np.array([p[1] for p in keys]))
    w = np.ones(len(keys), dtype=np.int64)
    ctx = {"M": M, "S": S_all, "w": w, "nwords": 4, "full": full,
           "codes": codes, "cols": cols, "ans": ans}

    seq = []
    for k in (1, 2, 3):
        st = {"nodes": 0, "leaves": 0}
        uns, ssq, chosen = build_opening(ctx, k, st)
        seq.append(uns)
        if k == 1:
            first = (uns, ssq, chosen)
    uns, ssq, chosen = first
    words = [pool[c] for c in chosen]
    print("opening at k=1: %s (unsolved %d)" % (" ".join(words), uns))

    # --- 2: the losing answers, three ways ---------------------------------
    got, losers = harvest(M, chosen, ans, 2)
    rows = [M[c] for c in chosen]
    obj, _ = score(tuple(chosen), (full, codes, cols, ans, rows))
    gctx = (full, cols, pool, ans, answers, 2, 6, gpos)
    _, gl, _, _, _ = check_opening(words, gctx)
    if not (len(losers) == obj == len(gl)):
        failures.append("losing answers disagree: harvest %d, greedybuild %d, "
                        "guarantee_sweep %d" % (len(losers), obj, len(gl)))
    if set(pool[i] for i in losers) != set(gl):
        failures.append("harvest and guarantee_sweep name DIFFERENT losing "
                        "answers, though they agree on the count")
    print("losing answers: harvest %d == greedybuild %d == guarantee_sweep %d, "
          "same words" % (len(losers), obj, len(gl)))

    # --- 3: every harvested pair really is a failure, from the strings -----
    key = joint_key(M, chosen)
    bad = 0
    for (i, j) in list(got)[:150]:
        a, x = pool[i], pool[j]
        if key[i] != key[j]:
            failures.append("%s/%s are in DIFFERENT buckets, so the opening "
                            "already separated them" % (a, x))
            bad += 1
            continue
        mem = np.flatnonzero(key == key[i])
        # At budget 2 the whole failure is one draw: a and x survive it together
        # exactly when some live word replies the same to both.
        if not any(pattern(pool[g], a) == pattern(pool[g], x)
                   for g in mem if pool[g] != a):
            failures.append("%s/%s: every live word separates them, so it is "
                            "not a failure pair" % (a, x))
            bad += 1
    if not got:
        failures.append("no pair was harvested at all, so check 3 proved nothing")
    print("harvested pairs: %d checked from the strings, %d bad"
          % (min(len(got), 150), bad))

    # --- 4: branch monotonicity, with coverage asserted --------------------
    if not all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1)):
        failures.append("branch is not monotone in K: unsolved went %s" % seq)
    if seq[0] == seq[-1]:
        failures.append("K changed nothing (%s), so monotonicity was never "
                        "actually tested" % seq)
    print("branch is monotone in K (unsolved %s over k=1,2,3)" % seq)

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
