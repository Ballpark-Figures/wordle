"""Cover the hard pairs, harvest the failures, repeat.  math/paircover.py states
the rule and IS the source of truth.

    bash solver/run-pair-cover.sh -k 5 --rounds 10

THE LOOP, one round at a time:

  1  score every candidate by the WEIGHTED pairs it splits;
  2  build an opening of `--words` words, recursing into the K best at each
     step (`branch`, the repo's --topk everywhere else);
  3  rank the finished openings by UNSOLVED ANSWERS -- the real objective, not
     coverage;
  4  harvest the pairs the winner actually failed on;
  5  add them to the set, incrementing the count of any already there;
  6  print, flush, and go again.

THE SEED IS SCAFFOLDING FOR ROUND 1 ONLY (user's call, 2026-09-18).  The first
harvest REPLACES the seeded pairs rather than joining them: the seed is the
hardest-pairs PROXY and it over-demands -- a bucket of two is safe, so some of
those pairs were never a problem -- while a harvested pair is by construction a
set that ran out of budget with company.  Carrying the seed on would keep
spending coverage on constraints that may not exist.  A RESUMED run is already
past that point and never re-seeds.

THE COUNT IS THE WEIGHT.  A pair that has failed five rounds counts five times
in step 1, so the search is pushed hardest at whatever keeps beating it.

BRANCH, NOT BEAM (user's call, 2026-09-18), matching `greedy_build.py` and every
other `--topk` here: K=1 is the leftmost path of the K=2 tree, so a wider K
contains a narrower one and can never return worse.  Memoised on the word SET,
since the ORDER words are chosen in does not change the opening.

TIES ON COVERAGE ARE BROKEN ON SSQ, and that is load-bearing rather than tidy.
Early in a round -- and always once the tracked pairs are all split -- many
candidates split exactly the same weight, and with no second key the choice
falls to whichever word sits lowest in the list.  `greedybuild` measured the
same hazard from the other side: where the objective is flat the TIE-BREAK is
choosing the whole construction.  Ssq is computed only across the tied head, so
it costs nothing when there is no tie.

EVERY ROUND IS FLUSHED, so a Ctrl-C keeps the pair set and every round already
played.  Re-running the same command CONTINUES from the pair file on disk, which
is what makes the loop resumable across sessions as well as inside one.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                                  # noqa: E402
from greedybuild import score                                             # noqa: E402
from opening_list import resolve_word_set                                 # noqa: E402
from paircover import (cand_matrix, cover_scores, harvest, joint_key,  # noqa: E402
                       last_level_scores, pool_matrix, split_matrix, ssq_of)
from wordle import load_words, pattern_row, to_codes                      # noqa: E402

PAIR_COLUMNS = "word1,word2,count"
ROUND_COLUMNS = "round,opening,unsolved,ssq,harvested,new_pairs,total_pairs,secs"


def parse_args(argv):
    a = {"pool": None, "words": 4, "topk": None, "rounds": None, "cap": 6,
         "seed_from": None, "seed_top": 1000, "out": None, "max_pairs": 0,
         "show": 8, "final_top": 0, "candidates": None,
         "pairs_from": None, "search": "branch"}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k in ("k", "topk"):
            k = "topk"
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        if k == "final_top" and v == "all":
            a[k] = -1                      # exhaustive; 0 still means "same as k"
        else:
            a[k] = (int(v) if k in ("topk", "words", "rounds", "cap", "seed_top",
                                    "max_pairs", "show", "final_top") else v)
        i += 2
    for req in ("pool", "topk", "rounds"):
        if a[req] is None:
            raise SystemExit("--%s is required" % req.replace("_", "-"))
    if a["search"] not in ("branch", "beam"):
        raise SystemExit(
            "--search must be branch or beam.  They are different searches:\n"
            "  branch  recurse into the K best at EVERY state -- k ** words "
            "complete openings;\n"
            "  beam    carry K states forward -- k * k openings, so a much "
            "wider K for the money.")
    if a["seed_from"] is None and a["pairs_from"] is None:
        raise SystemExit(
            "--seed-from FILE is required: the answer-pair ranking the first "
            "round starts from.\n  Build it with solver/run-answer-pairs.sh.")
    if a["out"] is None:
        raise SystemExit("--out STEM is required (or --no-out).  Use the "
                         "wrapper: bash solver/run-pair-cover.sh")
    if a["cap"] - a["words"] < 1:
        raise SystemExit("--cap %d leaves no guesses after %d opening words"
                         % (a["cap"], a["words"]))
    return a


def read_pairs(path, ppos):
    """Existing pair set, so a re-run continues instead of starting over."""
    pairs = {}
    if not path or not os.path.exists(path):
        return pairs
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or line.startswith("word1"):
                continue
            w1, w2, n = line.rstrip("\n").split(",")
            if w1 not in ppos or w2 not in ppos:
                continue
            i, j = ppos[w1], ppos[w2]
            pairs[(i, j) if i < j else (j, i)] = int(n)
    return pairs


def seed_pairs(path, top, ppos):
    """The `top` hardest rows of an answer-pair ranking, each weight 1."""
    pairs = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or line.startswith("word1"):
                continue
            w1, w2 = line.split(",")[:2]
            if w1 not in ppos or w2 not in ppos:
                continue
            i, j = ppos[w1], ppos[w2]
            pairs[(i, j) if i < j else (j, i)] = 1
            if len(pairs) >= top:
                break
    if not pairs:
        raise SystemExit("no usable rows in %s -- are its words in the pool?"
                         % path)
    return pairs


def best_k(sc, k, M, chosen):
    """The K best candidates under (coverage DESC, ssq ASC), as pool indices.

    THE K BEST, NOT THE K TIED AT THE TOP -- and the difference is the whole
    flag.  Selecting only among the candidates sharing the maximum meant that a
    single decisive coverage word left nothing for K to branch on, so every K
    returned the identical opening; `checkpaircover.py`'s monotonicity check
    fails on exactly that, which is how it was found.

    Ssq prices only the group STRADDLING the cut.  A tie group entirely inside
    the K is taken whole however it is ordered, and one entirely outside is not
    taken at all, so those never need the key -- which keeps a decisive choice
    free while a flat one still gets a real second key rather than falling to
    the lowest index.
    """
    live = np.flatnonzero(sc >= 0)
    if len(live) <= k:
        return live[np.argsort(-sc[live], kind="stable")]
    order = live[np.argsort(-sc[live], kind="stable")]
    cut = sc[order[k - 1]]
    firm = [int(c) for c in order[:k] if sc[c] > cut]
    grp = np.flatnonzero(sc == cut)
    need = k - len(firm)
    if len(grp) > need:
        base = joint_key(M, chosen)
        grp = grp[np.argsort([ssq_of(base * 243 + M[c]) for c in grp],
                             kind="stable")]
        grp = grp[:need]
    return firm + [int(c) for c in grp]


def build_opening(ctx, k, st, final_top=0):
    """Recurse into the K best coverage choices; rank the leaves by UNSOLVED.

    `final_top` sets how wide the LAST word's shortlist is, and it is the one
    place the two costs trade off:

      N   the N best by coverage, each priced on its own.  THE DEFAULT, and the
          user's call (2026-09-18) after running both: the exhaustive level is
          not worth its slowdown.
      0   the same K as every other level -- the behaviour before the flag.
      -1  (`--final-top all`) EXHAUSTIVE: every candidate ranked by the real
          objective, via `paircover.last_level_scores`, which prices the whole
          pool in one pass instead of one candidate at a time.

    MONOTONE ACROSS ALL THREE, since each is a superset of the one above it: a
    wider shortlist can only find a better leaf.  The gate checks that rather
    than assuming it.
    """
    M, S, weights, nwords, memo = ctx["M"], ctx["S"], ctx["w"], ctx["nwords"], {}
    big = np.iinfo(np.int32).max

    def rec(chosen, alive):
        if len(chosen) == nwords:
            st["leaves"] += 1
            rows = [M[c] for c in chosen]
            uns, ssq = score(tuple(chosen), (ctx["full"], ctx["codes"],
                                             ctx["cols"], ctx["ans"], rows))
            return (uns, ssq, tuple(chosen))
        key = tuple(sorted(chosen))
        if key in memo:
            return memo[key]
        banned = np.zeros(S.shape[0], dtype=bool)
        banned[list(chosen)] = True
        if final_top < 0 and len(chosen) == nwords - 1:
            # The whole pool at once: only worth it when EVERY candidate is
            # wanted, since it prices all 4282 however few are asked for.
            uns, ssq = last_level_scores(ctx["full"], ctx["cols"], M,
                                         list(chosen), ctx["ans"])
            uns = uns.astype(np.int64)
            uns[banned] = big
            c = int(np.lexsort((ssq, uns))[0])
            st["leaves"] += int((uns < big).sum())
            memo[key] = (int(uns[c]), int(ssq[c]), tuple(chosen) + (c,))
            return memo[key]
        sc = cover_scores(S, weights, alive, banned)
        wide = max(k, final_top) if len(chosen) == nwords - 1 else k
        best = None
        for c in best_k(sc, wide, M, chosen):
            st["nodes"] += 1
            r = rec(chosen + (int(c),), alive & ~S[int(c)])
            if best is None or r[:2] < best[:2]:
                best = r
        memo[key] = best
        return best

    return rec((), np.ones(S.shape[1], dtype=bool))


def run_beam(ctx, k, st, final_top=0):
    """Carry K states forward at each level, instead of recursing into K.

    THE COST IS THE POINT.  Branching visits `k ** words` complete openings;
    a beam pools `k * k` children per level and keeps K, so only `k * k` ever
    reach the objective.  At k=20 that is 400 against 160000.  It buys a much
    wider K for the same money, which is what a good weight set deserves.

    STATES ARE RANKED BY WEIGHT COVERED SO FAR, which is the one quantity
    comparable ACROSS states: each carries its own set of still-unsplit pairs,
    so their per-candidate coverage scores are not on the same scale, but
    "weight removed since the start" is.  Ties break on ssq, as everywhere here.

    THE SELECTION IS NESTED, NOT TOP-K OVERALL -- slot `i` is filled from the
    children of slots `0..i` -- which makes `beam_K`'s first K-1 slots identical
    to `beam_{K-1}` by induction, so a wider K is never worse.  Plain top-K is
    NOT monotone: slot 1's best child can rank third once slot 2's children join
    the pool, evicting the K=1 trajectory.  `greedybuild` MEASURED exactly that
    (k=2 came back worse than k=1) before its beam was nested; the same trap
    applies here and this avoids it the same way.
    """
    M, S, weights, nwords = ctx["M"], ctx["S"], ctx["w"], ctx["nwords"]
    total_w = int(weights.sum())
    beam = [((), np.ones(S.shape[1], dtype=bool))]
    for step in range(nwords):
        last = step == nwords - 1
        wide = max(k, final_top) if last else k
        pool_c, seen = [], set()
        for slot, (chosen, alive) in enumerate(beam):
            banned = np.zeros(S.shape[0], dtype=bool)
            banned[list(chosen)] = True
            sc = cover_scores(S, weights, alive, banned)
            for c in best_k(sc, wide, M, chosen):
                nxt = chosen + (int(c),)
                key = tuple(sorted(nxt))
                if key in seen:
                    continue        # two parents, one word SET: the same opening
                seen.add(key)
                pool_c.append((nxt, alive & ~S[int(c)], slot))
        if not pool_c:
            raise SystemExit("step %d: no candidate left to place" % (step + 1))
        st["nodes"] += len(pool_c)
        if last:
            best = None
            for chosen, _, _ in pool_c:
                st["leaves"] += 1
                rows = [M[c] for c in chosen]
                uns, ssq = score(tuple(chosen), (ctx["full"], ctx["codes"],
                                                 ctx["cols"], ctx["ans"], rows))
                if best is None or (uns, ssq) < best[:2]:
                    best = (uns, ssq, tuple(chosen))
            return best
        covered = np.array([total_w - int(weights[al].sum())
                            for _, al, _ in pool_c])
        ssqs = np.array([ssq_of(joint_key(M, ch)) for ch, _, _ in pool_c])
        order = np.lexsort((ssqs, -covered))
        picked, taken = [], set()
        for i in range(min(k, len(order))):
            for idx in order:
                if idx not in taken and pool_c[idx][2] <= i:
                    picked.append(int(idx))
                    taken.add(int(idx))
                    break
        beam = [(pool_c[i][0], pool_c[i][1]) for i in picked]
    raise AssertionError("the loop returns at its last step")


def main(argv):
    a = parse_args(argv)
    guesses, answers = load_words("guess"), load_words("mystery")
    pool = sorted(resolve_word_set(a["pool"]))
    pset, gpos = set(pool), {w: i for i, w in enumerate(guesses)}
    missing = [w for w in answers if w not in pset]
    if missing:
        raise SystemExit("the pool is missing %d answer(s): %s"
                         % (len(missing), ", ".join(missing[:5])))
    ppos = {w: i for i, w in enumerate(pool)}

    # THE CANDIDATES ARE A SEPARATE LIST FROM THE POOL.  The pool is what the
    # opening partitions and what the fifth guess draws from, so it is what
    # `unsolved` is measured over; the candidates are only the words the four
    # may be built from.  They default to the pool, which is how this ran before
    # the split, and they need not contain the answers.
    cands = pool if a["candidates"] is None else sorted(
        resolve_word_set(a["candidates"]))
    bad = [w for w in cands if w not in gpos]
    if bad:
        raise SystemExit("--candidates has %d word(s) that are not legal "
                         "guesses: %s" % (len(bad), ", ".join(bad[:5])))

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    ccols = np.array([gpos[w] for w in cands])
    codes = to_codes(pool)
    ans = np.array([ppos[w] for w in answers])
    Mpool = pool_matrix(full, cols)
    same = cands == pool
    M = Mpool if same else cand_matrix(full, ccols, cols)
    budget = a["cap"] - a["words"]

    pair_path = round_path = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        pair_path = a["out"] + "_pairs.csv"
        round_path = a["out"] + "_rounds.csv"

    # WHERE THE PAIRS COME FROM, in precedence order.  `seeded` says the current
    # set is the PROXY rather than real failures, and only a proxy is dropped
    # after the first harvest.
    pairs = read_pairs(pair_path, ppos)
    resumed = len(pairs)
    source = "resumed from %s" % pair_path
    seeded = False
    if not pairs and a["pairs_from"]:
        # WEIGHTS FROM ANOTHER RUN.  These are HARVESTED failures with the
        # counts another loop earned, not a proxy, so they are NOT dropped after
        # round 1 -- that rule exists for the hardest-pairs seed, which
        # over-demands, and these do not.  Any file of `word1,word2,count` does:
        # the format is the one this loop writes, so runs compose.
        pairs = read_pairs(a["pairs_from"], ppos)
        if not pairs:
            raise SystemExit("--pairs-from %s held no usable pairs -- are its "
                             "words in the pool?" % a["pairs_from"])
        source = "loaded from %s (weights kept)" % a["pairs_from"]
    elif not pairs:
        pairs = seed_pairs(a["seed_from"], a["seed_top"], ppos)
        seeded = True
        source = "seeded from %s (top %d)" % (a["seed_from"], a["seed_top"])

    print("pair cover: pool %s (%d)  answers %d  words %d  cap %d (budget %d)"
          % (a["pool"], len(pool), len(answers), a["words"], a["cap"], budget))
    print("  words    the 4 come from %s (%d)%s"
          % (a["candidates"] or a["pool"], len(cands),
             "" if same else "  -- a DIFFERENT list from the pool"))

    print("  pairs    %d, %s" % (len(pairs), source))
    print("  search   %s, k=%d -- %s"
          % (a["search"].upper(), a["topk"],
             "K states carried forward" if a["search"] == "beam" else
             "recurse into the K best at every state"))
    print("  rounds   %d" % a["rounds"])

    # WHAT A ROUND WILL COST -- A ROUGH FIGURE, AND SAID TO BE.  The last level
    # dominates, and its cost is machine- and prefix-specific, so it is timed
    # here rather than carried as a literal.  It is only ever an
    # order-of-magnitude guide: MEASURED, three consecutive k=2 rounds against
    # one projection came in at 35 s, 8 s and 42 s, and when the pair set is
    # small the ssq tie-break adds more on top.  Not a bound in either direction.
    rng = np.random.default_rng(0)
    t0 = time.time()
    for _ in range(10):
        ch = tuple(int(x) for x in rng.integers(len(cands), size=a["words"]))
        score(ch, (full, codes, cols, ans, [M[c] for c in ch]))
    per_leaf = (time.time() - t0) / 10
    wide = max(a["topk"], a["final_top"])
    # THE TWO SEARCHES HAVE DIFFERENT LEAF COUNTS, and quoting branch's for a
    # beam over-states it by orders of magnitude -- k**words against k*k.
    if a["search"] == "beam":
        leaves = a["topk"] * wide
    else:
        leaves = a["topk"] ** (a["words"] - 1) * wide
    if a["final_top"] < 0:
        print("  last word EXHAUSTIVE -- every candidate ranked by unsolved")
    elif a["final_top"]:
        print("  last word the %d best by coverage, ranked by unsolved" % wide)
    else:
        print("  last word no special case -- the same k as every other level")
    if a["final_top"] >= 0:
        print("  cost     %d leaves x ~%.1f ms = ~%.0f s per round, ~%.1f h for %d"
              % (leaves, per_leaf * 1000, leaves * per_leaf,
                 leaves * per_leaf * a["rounds"] / 3600.0, a["rounds"]))
    print("           (ROUGH -- timed on random openings; a real prefix varies)")

    rh = None
    if round_path:
        fresh = not os.path.exists(round_path)
        rh = open(round_path, "a")
        if fresh:
            rh.write("# pair-cover loop (see math/paircover.py)\n")
            rh.write("# settings pool=%s candidates=%s words=%d topk=%d cap=%d "
                     "search=%s final_top=%d source=%s\n"
                     % (a["pool"], a["candidates"] or a["pool"], a["words"],
                        a["topk"], a["cap"], a["search"], a["final_top"],
                        a["pairs_from"] or a["seed_from"]))
            rh.write(ROUND_COLUMNS + "\n")

    st = {"nodes": 0, "leaves": 0}
    best_ever = None
    for rnd in range(1, a["rounds"] + 1):
        t0 = time.time()
        if a["max_pairs"] and len(pairs) > a["max_pairs"]:
            # HEAVIEST FIRST: a pair that keeps failing is the constraint the
            # search most needs, and the cut has to say so rather than dropping
            # by arrival order.
            keep = sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
            pairs = dict(keep[:a["max_pairs"]])
        keys = sorted(pairs)
        ia = np.array([p[0] for p in keys])
        ib = np.array([p[1] for p in keys])
        weights = np.array([pairs[p] for p in keys], dtype=np.int64)
        S = split_matrix(M, ia, ib)
        print("\nround %d   %d pairs (weight %d)   split matrix %d x %d (%.1f MB)"
              % (rnd, len(keys), int(weights.sum()), S.shape[0], S.shape[1],
                 S.nbytes / 1e6), flush=True)

        ctx = {"M": M, "S": S, "w": weights, "nwords": a["words"],
               "full": full, "codes": codes, "cols": cols, "ans": ans}
        st["nodes"] = st["leaves"] = 0
        go = run_beam if a["search"] == "beam" else build_opening
        uns, ssq, chosen = go(ctx, a["topk"], st, a["final_top"])
        words = [cands[c] for c in chosen]
        print("  opening  %s" % " ".join(words))
        print("           unsolved %d of %d,  ssq %d   (%d nodes, %d complete, %.0fs)"
              % (uns, len(answers), ssq, st["nodes"], st["leaves"],
                 time.time() - t0))

        got, losers = harvest(M, Mpool, chosen, ans, budget)
        if len(losers) != uns:
            raise SystemExit(
                "GATE FAILED: the harvest found %d losing answers and the "
                "objective counts %d unsolved -- two routes to one number that "
                "must agree" % (len(losers), uns))
        new = sum(1 for p in got if p not in pairs)
        print("  harvest  %d pair(s) from %d losing answer(s): %d new, %d repeat"
              % (len(got), len(losers), new, len(got) - new))
        if seeded:
            # THE SEED IS SCAFFOLDING FOR ROUND 1 ONLY (user's call): it is the
            # hardest-pairs PROXY, which over-demands -- a bucket of two is safe
            # -- so carrying it on would keep spending coverage on pairs that may
            # never have been a problem.  From here the set is exactly what the
            # openings have actually FAILED on, which has no such slack.
            dropped = len(pairs)
            pairs = {p: 1 for p in got}
            seeded = False
            print("  seed     dropped all %d seeded pairs -- the set is now the "
                  "%d harvested" % (dropped, len(pairs)))
        else:
            for p in got:
                pairs[p] = pairs.get(p, 0) + 1
        print("  tracked  %d pairs" % len(pairs))
        heavy = sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0]))[:a["show"]]
        if heavy and heavy[0][1] > 1:
            print("  heaviest " + ",  ".join(
                "%s/%s x%d" % (pool[p[0]], pool[p[1]], n) for p, n in heavy
                if n > 1))
        if best_ever is None or (uns, ssq) < best_ever[:2]:
            best_ever = (uns, ssq, words, rnd)
            print("  NEW BEST across rounds")
        else:
            print("  best so far: round %d, unsolved %d (%s)"
                  % (best_ever[3], best_ever[0], " ".join(best_ever[2])))

        if rh:
            rh.write("%d,%s,%d,%d,%d,%d,%d,%.1f\n"
                     % (rnd, " ".join(words), uns, ssq, len(got), new,
                        len(pairs), time.time() - t0))
            rh.flush()
        if pair_path:
            tmp = pair_path + ".tmp"
            with open(tmp, "w") as fh:
                fh.write("# pairs the opening could not guarantee splitting\n")
                fh.write("# settings pool=%s words=%d cap=%d\n"
                         % (a["pool"], a["words"], a["cap"]))
                fh.write(PAIR_COLUMNS + "\n")
                for p, n in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0])):
                    fh.write("%s,%s,%d\n" % (pool[p[0]], pool[p[1]], n))
            os.replace(tmp, pair_path)     # atomic: a Ctrl-C never half-writes it

        if not pairs:
            # Nothing left to cover.  With unsolved 0 that is the whole point of
            # the exercise; otherwise the harvest found nothing to add and the
            # loop has no constraint to work from, which is a result either way.
            print("\n  no pairs left to cover -- %s"
                  % ("THIS OPENING IS GUARANTEED" if uns == 0 else
                     "the harvest added nothing, so the loop stops here"))
            break

    print("\nbest over %d round(s): %s" % (rnd, " ".join(best_ever[2])))
    print("  unsolved %d of %d,  ssq %d   (round %d)"
          % (best_ever[0], len(answers), best_ever[1], best_ever[3]))
    if rh:
        rh.close()
    if a["out"]:
        print("wrote %s and %s" % (pair_path, round_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
