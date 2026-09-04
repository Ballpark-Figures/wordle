"""Find small sets of opening words that split the answers, Rusin's way.

Two answers are told apart by a word when it gives them different feedback, so
"every answer ends up alone" is exactly "every PAIR of answers is separated by
some chosen word" -- a set cover over C(2315, 2) = 2,678,455 pairs.

WHY NOT SEARCH IT DIRECTLY.  Our own tree search (solver/cover.c) prunes locally
at every node and still cannot close a three-word prefix in 25 seconds.  Rusin's
method does not search the space at all: it SHRINKS it first, with a linear
program, and only then hunts inside what is left.  This reproduces that.

  stage 1 (--lp)      the tough pairs, the LP bound, and the shortlist
  stage 2 (--search)  randomised sampling plus meander, over the shortlist

STAGE 1.  Nearly every word separates nearly every pair -- the median pair over
the 2315 answers is separated by 2151 of them -- so almost all of the 2.7M
constraints are slack and only a tail matters.  Constraining just the toughest
few hundred keeps the LP small AND keeps the bound valid, since dropping
constraints can only lower the optimum.  Relaxing x to non-negative reals then
gives a lower bound on how many words are needed; Rusin got 5.4 this way, which
is what proves 6 is the minimum.

The DUAL is the part that earns its keep.  Its non-zero entries name the pairs
that actually bind, and their separators form a shortlist -- 74 words in Rusin's
run -- which is what turns an intractable search into a small one.

STAGE 2.  Sample (k-1)-word subsets from the shortlist, weighted toward the
words the LP liked; for a promising one, try every legal word as the last;
keep the best; then meander -- replace one word at a time while the score
improves.  Scored by SINGLETONS, the count of answers left alone.

    python3 tools/lpcover.py --lp
    python3 tools/lpcover.py --lp --openers guess --tough 2000
    python3 tools/lpcover.py --search --k 6 --seconds 600
    python3 tools/lpcover.py --search --k 4 --openers guess
"""

import argparse, json, os, random, sys, time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from build_patterns import load_patterns          # noqa: E402
from wordle import load_words                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "shared", "singletons")


def setup(openers):
    G = load_words("guess")
    A = load_words("mystery")
    idx = {w: i for i, w in enumerate(G)}
    words = A if openers == "answers" else G
    rows = np.array([idx[w] for w in words], dtype=np.int64)
    PAT = np.asarray(load_patterns())
    return G, A, words, rows, PAT


def separator_counts(PAT, rows, NA):
    """For every pair, how many openers separate it.

    Counted from the cheap side: for each opener the pairs INSIDE one of its
    buckets are the ones it misses -- about 15k per word rather than 2.7M.
    """
    fail = np.zeros(NA * (NA - 1) // 2, dtype=np.int32)
    for g in rows:
        row = PAT[g]
        order = np.argsort(row, kind="stable")
        srt = row[order]
        starts = np.flatnonzero(np.r_[True, srt[1:] != srt[:-1]])
        ends = np.r_[starts[1:], NA]
        for s, e in zip(starts, ends):
            if e - s < 2:
                continue
            b = np.sort(order[s:e]).astype(np.int64)
            ii, jj = np.triu_indices(len(b), 1)
            i, j = b[ii], b[jj]
            np.add.at(fail, i * NA - i * (i + 1) // 2 + (j - i - 1), 1)
    return len(rows) - fail


def unrank(k, NA):
    cs = np.cumsum(np.arange(NA - 1, 0, -1))
    i = int(np.searchsorted(cs, k, side="right"))
    prev = 0 if i == 0 else int(cs[i - 1])
    return i, i + 1 + (int(k) - prev)


def singles_of(PAT, rows_for, words, wordset):
    """Singleton buckets produced by a set of words."""
    key = np.zeros(PAT.shape[1], dtype=np.int64)
    for w in wordset:
        key = key * 243 + PAT[rows_for[w]]
    sz = np.bincount(np.unique(key, return_inverse=True)[1])
    return int((sz == 1).sum())


def sep_cached(PAT, rows, NA, openers):
    """The separator table takes ~60s to build and is a pure function of the
    dictionary, so it is kept rather than recomputed each run."""
    path = os.path.join(OUT, "sepcount_%s.npy" % openers)
    if os.path.exists(path):
        return np.load(path)
    sep = separator_counts(PAT, rows, NA)
    os.makedirs(OUT, exist_ok=True)
    np.save(path, sep)
    return sep


def violated_pairs(PAT, rows_for, chosen, NA):
    """Pairs the chosen words leave sharing a bucket."""
    key = np.zeros(NA, dtype=np.int64)
    for w in chosen:
        key = key * 243 + PAT[rows_for[w]]
    order = np.argsort(key, kind="stable")
    srt = key[order]
    starts = np.flatnonzero(np.r_[True, srt[1:] != srt[:-1]])
    ends = np.r_[starts[1:], NA]
    out = []
    for st, en in zip(starts, ends):
        if en - st < 2:
            continue
        b = np.sort(order[st:en])
        for x in range(len(b)):
            for y in range(x + 1, len(b)):
                out.append((int(b[x]), int(b[y])))
    return out


def stage_mip(args):
    """Exact cover by integer programming, pair constraints generated lazily.

    All 2,678,455 pair constraints cannot be instantiated: nearly every word
    separates nearly every pair, so the matrix would carry billions of non-zeros
    and be almost entirely slack. Instead solve over a small set, check the
    answer against EVERY pair, add the ones it violates, repeat. It settles fast
    because only the hard tail ever binds.

    This is the part a randomised search cannot do -- prove there is nothing
    smaller, or nothing else. --unique forbids the solution found and re-solves;
    infeasibility then means it is the only one of that size.
    """
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import csr_matrix, vstack

    G, A, words, rows, PAT = setup(args.openers)
    NA = len(A)
    rows_for = {words[i]: rows[i] for i in range(len(words))}
    sep = sep_cached(PAT, rows, NA, args.openers)
    cons = [unrank(k, NA) for k in np.argsort(sep)[: args.tough]]
    print("%d openers, seeding with the %d toughest pairs" % (len(rows), len(cons)))

    nogood, t0 = [], time.time()
    trace, solved, verdict = [], [], "incomplete"
    for round_ in range(1, args.rounds + 1):
        prow, pcol = [], []
        for r, (i, j) in enumerate(cons):
            seps = np.flatnonzero(PAT[rows, i] != PAT[rows, j])
            prow.extend([r] * len(seps)); pcol.extend(seps.tolist())
        mats = [csr_matrix((np.ones(len(prow)), (prow, pcol)),
                           shape=(len(cons), len(rows)))]
        lbs = [np.ones(len(cons))]; ubs = [np.full(len(cons), np.inf)]
        for idxs in nogood:
            mats.append(csr_matrix((np.ones(len(idxs)),
                                    (np.zeros(len(idxs)), idxs)), shape=(1, len(rows))))
            lbs.append(np.array([0.0])); ubs.append(np.array([float(len(idxs) - 1)]))
        if args.size:
            mats.append(csr_matrix(np.ones((1, len(rows)))))
            lbs.append(np.array([0.0])); ubs.append(np.array([float(args.size)]))
        M = vstack(mats).tocsr()
        res = milp(c=np.ones(len(rows)),
                   constraints=LinearConstraint(M, np.concatenate(lbs),
                                                np.concatenate(ubs)),
                   integrality=np.ones(len(rows)), bounds=Bounds(0, 1),
                   options={"time_limit": args.time_limit, "disp": False})
        if not res.success or res.x is None:
            print("round %d: %s" % (round_, res.message))
            return
        chosen = [words[i] for i in np.flatnonzero(res.x > 0.5)]
        bad = violated_pairs(PAT, rows_for, chosen, NA)
        trace.append({"round": round_, "constraints": len(cons),
                      "words": sorted(chosen), "uncovered": len(bad),
                      "seconds": round(time.time() - t0, 1),
                      "status": int(res.status)})

        # THE PROOF, and the run used to walk straight past it. The constraint
        # set is a SUBSET of all 2678455 pairs, so this problem is a relaxation
        # and its optimum lower-bounds the true one. Once the optimum exceeds
        # the size of a solution already in hand, nothing else that small can
        # cover everything -- there is nothing left to search for.
        if solved and len(chosen) > len(solved[0]):
            print("\nUNIQUE: excluding it, the relaxation already needs %d words,"
                  % len(chosen))
            print("so no other %d-word set can cover every pair." % len(solved[0]))
            verdict = "unique"
            break
        print("[%5.0fs] round %2d: %d constraints -> %d words, %d pairs uncovered  %s"
              % (time.time() - t0, round_, len(cons), len(chosen), len(bad),
                 " ".join(sorted(chosen))))
        sys.stdout.flush()
        if not bad:
            print("\nPERFECT SPLIT with %d words: %s"
                  % (len(chosen), " ".join(sorted(chosen))))
            solved.append(sorted(chosen))
            verdict = "found"
            if not args.unique:
                break
            nogood.append([int(i) for i in np.flatnonzero(res.x > 0.5)])
            print("forbidding it and re-solving to test uniqueness...")
            continue
        cons.extend(bad[: args.add])
    if verdict == "incomplete":
        print("stopped after %d rounds -- a budget I set, not a conclusion" % args.rounds)

    # HiGHS status 0 is a proven optimum; anything else (a time limit, say) makes
    # the round an incumbent rather than a bound, and the proof above would not
    # hold. Recorded per round so a reader can check rather than assume.
    out = {"openers": args.openers, "tough": int(args.tough),
           "size_limit": int(args.size), "verdict": verdict,
           "solutions": solved, "singletons": [
               singles_of(PAT, rows_for, words, sset) for sset in solved],
           "answers": int(NA), "rounds": trace,
           "all_rounds_proven_optimal": all(t["status"] == 0 for t in trace)}
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "mipcover_%s.json" % args.openers)
    json.dump(out, open(path, "w"), indent=1)
    print("wrote %s" % os.path.relpath(path, os.path.join(HERE, "..")))
    if solved:
        csv = os.path.join(OUT, "perfect_split_%s.csv" % args.openers)
        with open(csv, "w") as f:
            f.write(",".join("word%d" % (i + 1) for i in range(len(solved[0]))))
            f.write(",singletons,answers,verdict\n")
            for sset in solved:
                f.write("%s,%d,%d,%s\n" % (",".join(sset),
                        singles_of(PAT, rows_for, words, sset), NA, verdict))
        print("wrote %s" % os.path.relpath(csv, os.path.join(HERE, "..")))
    from scipy.optimize import linprog
    from scipy.sparse import csr_matrix

    G, A, words, rows, PAT = setup(args.openers)
    NA = len(A)
    t0 = time.time()
    sep = separator_counts(PAT, rows, NA)
    print("separator counts in %.0fs: min %d, median %d, max %d"
          % (time.time() - t0, sep.min(), int(np.median(sep)), sep.max()))

    tough = np.argsort(sep)[: args.tough]
    print("constraining the %d toughest pairs (separators %d..%d)"
          % (len(tough), sep[tough].min(), sep[tough].max()))

    # one row per tough pair, one column per opener; 1 where the word separates
    prow, pcol = [], []
    for r, k in enumerate(tough):
        i, j = unrank(k, NA)
        seps = np.flatnonzero(PAT[rows, i] != PAT[rows, j])
        prow.extend([r] * len(seps)); pcol.extend(seps.tolist())
    Aub = csr_matrix((-np.ones(len(prow)), (prow, pcol)),
                     shape=(len(tough), len(rows)))
    res = linprog(c=np.ones(len(rows)), A_ub=Aub, b_ub=-np.ones(len(tough)),
                  bounds=(0, 1), method="highs")
    if not res.success:
        raise SystemExit("LP failed: %s" % res.message)
    print("\nLP lower bound: %.4f  ->  at least %d words are needed"
          % (res.fun, int(np.ceil(res.fun - 1e-9))))

    # the binding pairs, and the words that serve them
    duals = np.abs(res.ineqlin.marginals)
    binding = np.flatnonzero(duals > 1e-9)
    print("%d of %d tough pairs bind" % (len(binding), len(tough)))
    # THE SUPPORT, not the union of the binding pairs' separators. Those pairs
    # each have hundreds of separators, so their union is the whole dictionary
    # and shrinks nothing. The words the LP actually SPENDS weight on are the
    # few it considers load-bearing -- Rusin's 74.
    lpx = res.x
    short = sorted(np.flatnonzero(lpx > args.support).tolist(), key=lambda s: -lpx[s])
    print("shortlist: %d words" % len(short))
    print("  top 25 by LP weight: %s" % " ".join(words[s] for s in short[:25]))

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "shortlist_%s.json" % args.openers)
    json.dump({"openers": args.openers, "tough": int(args.tough),
               "lp_bound": float(res.fun),
               "shortlist": [words[s] for s in short],
               "lp_weight": [float(lpx[s]) for s in short]},
              open(path, "w"), indent=1)
    print("wrote %s" % os.path.relpath(path, os.path.join(HERE, "..")))


def partition_of(PAT, rows_for, chosen, NA):
    key = np.zeros(NA, dtype=np.int64)
    for w in chosen:
        key = key * 243 + PAT[rows_for[w]]
    return key


def stage_best(args):
    """The most SINGLETONS obtainable from exactly k words -- and a proof.

    x_g picks the words, z_a says answer a ends up alone. For every pair (a, b),
    a can only be alone if some chosen word separates it from b:

        z_a <= sum of x_g over words g that separate (a, b)

    maximise sum z_a subject to sum x_g = k.

    THE PAIRS ARE GENERATED LAZILY, for the same reason the n=6 cover was: all
    2,678,455 of them cannot be instantiated, and nearly none bind. Leaving a
    pair out lets the solver ASSUME it is separated, which can only overstate the
    singleton count -- so the relaxed optimum is an UPPER BOUND. Solve, compute
    the real partition, add constraints for answers the solver called singletons
    that are not, repeat. When the real count matches the bound, the bound is
    attained and the answer is optimal, not merely the best found.
    """
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import csr_matrix, vstack

    G, A, words, rows, PAT = setup(args.openers)
    NA, NW = len(A), len(rows)
    rows_for = {words[i]: rows[i] for i in range(len(words))}
    sep = sep_cached(PAT, rows, NA, args.openers)
    modelled = set(tuple(unrank(k, NA)) for k in np.argsort(sep)[: args.tough])
    print("%d openers, %d answers, exactly %d words, maximising singletons"
          % (NW, NA, args.k))

    # variables: x_0..x_{NW-1} (words), then z_0..z_{NA-1} (answers alone)
    t0, trace = time.time(), []
    for round_ in range(1, args.rounds + 1):
        rr, cc, vv = [], [], []
        rhs_lo, rhs_hi, r = [], [], 0
        for (i, j) in modelled:
            seps = np.flatnonzero(PAT[rows, i] != PAT[rows, j])
            for a_end in (i, j):
                # z_a - sum x_g <= 0
                rr.append(r); cc.append(NW + a_end); vv.append(1.0)
                for g in seps:
                    rr.append(r); cc.append(int(g)); vv.append(-1.0)
                rhs_lo.append(-np.inf); rhs_hi.append(0.0); r += 1
        rr.extend([r] * NW); cc.extend(range(NW)); vv.extend([1.0] * NW)
        rhs_lo.append(float(args.k)); rhs_hi.append(float(args.k)); r += 1
        M = csr_matrix((vv, (rr, cc)), shape=(r, NW + NA))
        c = np.zeros(NW + NA); c[NW:] = -1.0            # maximise sum z
        res = milp(c=c, constraints=LinearConstraint(M, np.array(rhs_lo), np.array(rhs_hi)),
                   integrality=np.ones(NW + NA), bounds=Bounds(0, 1),
                   options={"time_limit": args.time_limit, "disp": False})
        if not res.success or res.x is None:
            print("round %d: %s" % (round_, res.message)); return
        chosen = [words[i] for i in np.flatnonzero(res.x[:NW] > 0.5)]
        bound = int(round(-res.fun))
        actual = singles_of(PAT, rows_for, words, chosen)
        trace.append({"round": round_, "pairs_modelled": len(modelled),
                      "bound": bound, "actual": actual, "words": sorted(chosen),
                      "seconds": round(time.time() - t0, 1), "status": int(res.status)})
        print("[%5.0fs] round %2d: %d pairs modelled, bound %d, actual %d  %s"
              % (time.time() - t0, round_, len(modelled), bound, actual,
                 " ".join(sorted(chosen))))
        sys.stdout.flush()
        if actual >= bound:
            print("\nOPTIMAL: %d singletons of %d with %d words -- the relaxation "
                  "could not do better, and this attains it" % (actual, NA, args.k))
            break
        # the solver called some answers alone that are not; teach it those pairs
        key = partition_of(PAT, rows_for, chosen, NA)
        order = np.argsort(key, kind="stable"); srt = key[order]
        starts = np.flatnonzero(np.r_[True, srt[1:] != srt[:-1]])
        ends = np.r_[starts[1:], NA]
        added = 0
        for st, en in zip(starts, ends):
            if en - st < 2: continue
            b = np.sort(order[st:en])
            for x in range(len(b)):
                for y in range(x + 1, len(b)):
                    pr = (int(b[x]), int(b[y]))
                    if pr not in modelled:
                        modelled.add(pr); added += 1
                        if added >= args.add: break
                if added >= args.add: break
            if added >= args.add: break
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "bestmip_k%d_%s.json" % (args.k, args.openers))
    json.dump({"openers": args.openers, "k": args.k, "answers": NA,
               "rounds": trace,
               "best": trace[-1]["words"], "singletons": trace[-1]["actual"],
               "proven_optimal": bool(trace and trace[-1]["actual"] >= trace[-1]["bound"]),
               "all_rounds_proven_optimal": all(t["status"] == 0 for t in trace)},
              open(path, "w"), indent=1)
    print("wrote %s" % os.path.relpath(path, os.path.join(HERE, "..")))


def stage_search(args):
    """Maximise SINGLETONS for a fixed number of words.

    The objective is the count of answers left alone, not a cover. Below six
    words the best set routinely abandons the hardest pairs and splits
    everything else instead -- the optimal three, blimp dance short, does not
    separate booby/boozy at all -- so anything that steers toward covering the
    hard tail steers away from the answer here. Seeding from the sextet LP
    shortlist cost 45 singletons at k=3; seeds now come from the whole
    dictionary, with --shortlist to opt back in.
    """
    G, A, words, rows, PAT = setup(args.openers)
    rows_for = {words[i]: rows[i] for i in range(len(words))}
    pool = list(words)
    if args.shortlist:
        pool = json.load(open(os.path.join(
            OUT, "shortlist_%s.json" % args.openers)))["shortlist"]
        print("seeding from the %d-word LP shortlist" % len(pool))
    print("%d openers, %d answers, best %d words by singletons"
          % (len(words), len(A), args.k))

    rng = random.Random(args.seed)
    best, best_set, tries = -1, None, 0
    t0 = time.time()
    while time.time() - t0 < args.seconds:
        tries += 1
        cur = meander(rng.sample(pool, args.k), words, rows_for, PAT, rng, args)
        sc = singles_of(PAT, rows_for, words, cur)
        if sc > best:
            best, best_set = sc, list(cur)
            print("[%5.0fs] %d singletons  %s"
                  % (time.time() - t0, sc, " ".join(sorted(cur))))
            sys.stdout.flush()
    print("\n%d restarts, best %d of %d: %s"
          % (tries, best, len(A), " ".join(sorted(best_set or []))))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "best_k%d_%s.csv" % (args.k, args.openers))
    with open(path, "w") as f:
        f.write(",".join("word%d" % (i + 1) for i in range(args.k)))
        f.write(",singletons,answers,restarts\n")
        f.write("%s,%d,%d,%d\n" % (",".join(sorted(best_set or [])), best,
                                    len(A), tries))
    print("wrote %s" % os.path.relpath(path, os.path.join(HERE, "..")))


def meander(cur, words, rows_for, PAT, rng, args):
    """Replace one word at a time while the score improves."""
    cur = list(cur)
    if len(cur) < args.k:
        cur.append(words[0])
    best = singles_of(PAT, rows_for, words, cur)
    improved = True
    while improved:
        improved = False
        for slot in range(len(cur)):
            keep = cur[slot]
            trial = list(cur)
            for w in words:
                if w in cur:
                    continue
                trial[slot] = w
                s = singles_of(PAT, rows_for, words, trial)
                if s > best:
                    best, keep, improved = s, w, True
            cur[slot] = keep
    return cur


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lp", action="store_true")
    ap.add_argument("--mip", action="store_true")
    ap.add_argument("--best", action="store_true",
                    help="most singletons with exactly --k words, with a proof")
    ap.add_argument("--rounds", type=int, default=40)
    ap.add_argument("--add", type=int, default=400)
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--unique", action="store_true")
    ap.add_argument("--time-limit", type=float, default=600.0)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--openers", choices=("answers", "guess"), default="answers")
    ap.add_argument("--tough", type=int, default=916)
    ap.add_argument("--support", type=float, default=1e-6,
                    help="LP weight above which a word joins the shortlist")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--shortlist", action="store_true",
                    help="seed from the LP shortlist instead of the whole list")
    a = ap.parse_args()
    if a.best:
        stage_best(a)
    elif a.mip:
        stage_mip(a)
    elif a.lp:
        stage_lp(a)
    elif a.search:
        stage_search(a)
    else:
        ap.error("pass --lp, --mip or --search")
