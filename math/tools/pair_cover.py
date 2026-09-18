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
from paircover import (cover_scores, harvest, joint_key,               # noqa: E402
                       last_level_scores, pool_matrix, split_matrix, ssq_of)
from wordle import load_words, pattern_row, to_codes                      # noqa: E402

PAIR_COLUMNS = "word1,word2,count"
ROUND_COLUMNS = "round,opening,unsolved,ssq,harvested,new_pairs,total_pairs,secs"


def parse_args(argv):
    a = {"pool": None, "words": 4, "topk": None, "rounds": None, "cap": 6,
         "seed_from": None, "seed_top": 1000, "out": None, "max_pairs": 0,
         "show": 8, "final_top": 0}
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
        a[k] = (int(v) if k in ("topk", "words", "rounds", "cap", "seed_top",
                                "max_pairs", "show", "final_top") else v)
        i += 2
    for req in ("pool", "topk", "rounds"):
        if a[req] is None:
            raise SystemExit("--%s is required" % req.replace("_", "-"))
    if a["seed_from"] is None:
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
    """Recurse into the K best coverage choices; decide the LAST word exactly.

    THE LAST WORD IS RANKED BY THE REAL OBJECTIVE OVER EVERY CANDIDATE (user's
    design), not shortlisted by coverage first.  `paircover.last_level_scores`
    prices the whole pool in one pass -- MEASURED 0.9-2.2 s against 48 s one at
    a time -- by grouping candidates on the PARTITION they induce rather than on
    their replies, which is what made the exhaustive form affordable at all.

    Coverage still chooses words 1..k-1, where it is informative and where a
    full evaluation would multiply.  It chooses NOTHING at the last word, which
    is where it was weakest: fewest pairs left, most candidates tied.

    `final_top` N restores the old shortlist -- the N best by coverage, then
    ranked -- for when the exhaustive level is not wanted.  0 means exhaustive.
    """
    M, S, weights, nwords, memo = ctx["M"], ctx["S"], ctx["w"], ctx["nwords"], {}
    big = np.iinfo(np.int32).max

    def rec(chosen, alive):
        key = tuple(sorted(chosen))
        if key in memo:
            return memo[key]
        banned = np.zeros(S.shape[0], dtype=bool)
        banned[list(chosen)] = True
        if len(chosen) == nwords - 1:
            uns, ssq = last_level_scores(ctx["full"], ctx["cols"], M,
                                         list(chosen), ctx["ans"])
            uns = uns.astype(np.int64)
            if final_top:
                sc = cover_scores(S, weights, alive, banned)
                keep = np.zeros(len(uns), dtype=bool)
                keep[best_k(sc, final_top, M, chosen)] = True
                uns = np.where(keep, uns, big)
            uns[banned] = big              # a word cannot be played twice
            c = int(np.lexsort((ssq, uns))[0])
            st["leaves"] += int((uns < big).sum())
            out = (int(uns[c]), int(ssq[c]), tuple(chosen) + (c,))
            memo[key] = out
            return out
        sc = cover_scores(S, weights, alive, banned)
        best = None
        for c in best_k(sc, k, M, chosen):
            st["nodes"] += 1
            r = rec(chosen + (int(c),), alive & ~S[int(c)])
            if best is None or r[:2] < best[:2]:
                best = r
        memo[key] = best
        return best

    return rec((), np.ones(S.shape[1], dtype=bool))


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

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    codes = to_codes(pool)
    ans = np.array([ppos[w] for w in answers])
    M = pool_matrix(full, cols)
    budget = a["cap"] - a["words"]

    pair_path = round_path = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        pair_path = a["out"] + "_pairs.csv"
        round_path = a["out"] + "_rounds.csv"

    pairs = read_pairs(pair_path, ppos)
    resumed = len(pairs)
    # `seeded` says the CURRENT set is the proxy rather than real failures, so
    # the first harvest must REPLACE it.  A resumed run is already past that
    # point -- its file holds harvested pairs -- so it never re-seeds.
    seeded = not resumed
    if seeded:
        pairs = seed_pairs(a["seed_from"], a["seed_top"], ppos)

    print("pair cover: pool %s (%d)  answers %d  words %d  cap %d (budget %d)"
          % (a["pool"], len(pool), len(answers), a["words"], a["cap"], budget))
    print("  search   branch, k=%d -- recurse into the K best coverage choices"
          % a["topk"])
    print("  pairs    %d %s" % (len(pairs), "resumed from %s" % pair_path
                                if resumed else "seeded from %s (top %d)"
                                % (a["seed_from"], a["seed_top"])))
    print("  rounds   %d" % a["rounds"])

    # WHAT A ROUND WILL COST -- A ROUGH FIGURE, AND SAID TO BE.  The last level
    # dominates and its cost is machine- AND prefix-specific, so it is timed
    # here rather than carried as a literal.  But it is timed on a RANDOM
    # prefix, and the search's own prefixes are far from random: they shatter
    # the pool, which leaves fewer live buckets and a cheaper last level.
    # MEASURED, three consecutive rounds at k=2 against a 104 s projection:
    # 35 s, 8 s, 42 s.  So it is an order-of-magnitude guide, NOT a bound in
    # either direction, and calling it one would be the wrong claim.  A round runs one last
    # level per three-word state, and the memo collapses almost nothing (the
    # candidates offered at each level depend on the level above), so the state
    # count is k ** (words - 1).
    t0 = time.time()
    rng = np.random.default_rng(0)
    pre = [int(x) for x in rng.integers(len(pool), size=a["words"] - 1)]
    last_level_scores(full, cols, M, pre, ans)
    per_level = time.time() - t0
    states = a["topk"] ** (a["words"] - 1)
    print("  last word %s"
          % ("EXHAUSTIVE -- every candidate ranked by unsolved"
             if not a["final_top"] else
             "the %d best by coverage, then ranked by unsolved" % a["final_top"]))
    print("  cost     %d three-word states x ~%.1f s = ~%.0f s per round, "
          "~%.1f h for %d" % (states, per_level, states * per_level,
                              states * per_level * a["rounds"] / 3600.0,
                              a["rounds"]))
    print("           (ROUGH: timed on a RANDOM prefix, and a real one varies "
          "several-fold either way --")
    print("            a greedy prefix shatters the pool better, so its last "
          "level is cheaper)")

    rh = None
    if round_path:
        fresh = not os.path.exists(round_path)
        rh = open(round_path, "a")
        if fresh:
            rh.write("# pair-cover loop (see math/paircover.py)\n")
            rh.write("# settings pool=%s words=%d topk=%d cap=%d seed=%s seed_top=%d\n"
                     % (a["pool"], a["words"], a["topk"], a["cap"],
                        a["seed_from"], a["seed_top"]))
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
        uns, ssq, chosen = build_opening(ctx, a["topk"], st, a["final_top"])
        words = [pool[c] for c in chosen]
        print("  opening  %s" % " ".join(words))
        print("           unsolved %d of %d,  ssq %d   (%d nodes, %d complete, %.0fs)"
              % (uns, len(answers), ssq, st["nodes"], st["leaves"],
                 time.time() - t0))

        got, losers = harvest(M, chosen, ans, budget)
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
