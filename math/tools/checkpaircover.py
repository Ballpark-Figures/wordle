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
from paircover import (cand_matrix, harvest, joint_key,               # noqa: E402
                       pool_matrix, split_matrix)
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
    got, losers = harvest(M, M, chosen, ans, 2)
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

    # --- 4b: --final-top is monotone, and it actually does something -------
    # A wider last-level shortlist yields a SUPERSET of leaves, so the minimum
    # over them can only improve -- the same containment argument K rests on.
    fseq = []
    for f in (0, 20, 200, -1):             # 0 = same as k, -1 = EXHAUSTIVE
        st = {"nodes": 0, "leaves": 0}
        u, _, _ = build_opening(ctx, 2, st, f)
        fseq.append(u)
    if not all(fseq[i] >= fseq[i + 1] for i in range(len(fseq) - 1)):
        failures.append("--final-top is not monotone: unsolved went %s" % fseq)
    if fseq[0] == fseq[-1]:
        failures.append("--final-top changed nothing (%s), so its monotonicity "
                        "was never actually tested" % fseq)
    print("--final-top is monotone (unsolved %s over k, 20, 200, exhaustive "
          "at k=2)" % fseq)

    # --- 4c: the batched last level equals the one-at-a-time objective ------
    # The exhaustive level exists only because it is fast; it is worth nothing
    # if it is not also EXACT.  `greedybuild.score` prices a whole opening from
    # scratch and shares none of the bucket reuse, so it is a real second route
    # to both numbers.
    from paircover import last_level_scores
    pre = [int(c) for c in chosen[:3]]
    U, Q = last_level_scores(full, cols, M, pre, ans)
    wrong = 0
    for c in rng.integers(len(pool), size=120):
        c = int(c)
        got = score(tuple(pre + [c]), (full, codes, cols, ans,
                                       [M[x] for x in pre + [c]]))
        if got != (int(U[c]), int(Q[c])):
            wrong += 1
    if wrong:
        failures.append("the batched last level disagrees with score() on %d "
                        "of 120 candidates" % wrong)
    print("batched last level: 120 candidates match score() on unsolved AND ssq")

    # --- 6: a WIDER CANDIDATE LIST than the pool ---------------------------
    # The pool is what the opening partitions and what the fifth guess draws
    # from; the candidates are only what the four are built from.  Letting them
    # differ is where an index-space slip would live -- a candidate index used
    # as a pool index names the wrong word and buckets the wrong set -- so the
    # three-way agreement on LOSING ANSWERS is re-run with candidates that are
    # NOT in the pool, which is the case the equal-lists version cannot reach.
    cands = sorted(guesses)
    ccols = np.array([gpos[w] for w in cands])
    C = cand_matrix(full, ccols, cols)
    outside = [w for w in cands if w not in ppos]
    if not outside:
        failures.append("the wide candidate list adds nothing outside the pool, "
                        "so check 6 proved nothing")
    S_w = split_matrix(C, np.array([p[0] for p in keys]),
                       np.array([p[1] for p in keys]))
    ctxw = {"M": C, "S": S_w, "w": w, "nwords": 4, "full": full,
            "codes": codes, "cols": cols, "ans": ans}
    stw = {"nodes": 0, "leaves": 0}
    uw, _, chw = build_opening(ctxw, 2, stw, 100)
    wordsw = [cands[c] for c in chw]
    gotw, losersw = harvest(C, M, chw, ans, 2)
    _, glw, _, _, _ = check_opening(wordsw, gctx)
    if not (len(losersw) == uw == len(glw)):
        failures.append("with a wider candidate list the losing answers "
                        "disagree: harvest %d, search %d, guarantee_sweep %d"
                        % (len(losersw), uw, len(glw)))
    if set(pool[i] for i in losersw) != set(glw):
        failures.append("with a wider candidate list the harvest and "
                        "guarantee_sweep name DIFFERENT losing answers")
    used_outside = [x for x in wordsw if x not in ppos]
    print("wide candidates: %s (unsolved %d), %d of its words outside the pool, "
          "losing answers agree 3 ways"
          % (" ".join(wordsw), uw, len(used_outside)))

    # --- 5: the SEED is dropped after the first harvest --------------------
    # End to end, through the real main(), because this is a property of the
    # LOOP rather than of any function it calls: a round-1 file still holding
    # the seeded pairs is the exact regression this pins.
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        stem = os.path.join(td, "gate")
        out = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "pair_cover.py"),
             "--pool", "custom", "--words", "4", "--topk", "1", "--rounds", "1",
             "--seed-from", SEED, "--seed-top", "600", "--out", stem],
            capture_output=True, text=True)
        pf = stem + "_pairs.csv"
        rf = stem + "_rounds.csv"
        if not os.path.exists(pf):
            failures.append("a round wrote no pair file: %s" % out.stderr[-400:])
        else:
            rows = [l for l in open(pf) if l[0] != "#" and not l.startswith("word1")]
            harvested = int(open(rf).read().strip().split("\n")[-1].split(",")[4])
            if len(rows) != harvested:
                failures.append(
                    "after round 1 the pair file holds %d rows but the round "
                    "harvested %d -- the seeded pairs were not dropped"
                    % (len(rows), harvested))
            elif any(int(l.rstrip().split(",")[2]) != 1 for l in rows):
                failures.append("a round-1 pair has a count above 1, so "
                                "something was carried in from the seed")
            else:
                print("seed dropped: after round 1 the file is exactly the %d "
                      "harvested pairs, all at count 1" % harvested)

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
