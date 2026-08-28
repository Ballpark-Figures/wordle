"""Compare the two opener orderings, and ask what the ROOT-LB walk has not reached yet.

--optimal-only walks openers by ASCENDING ROOT LOWER BOUND. That bound is a pure
counting bound (see build_lb in optturns.c) and runs ~11-14% under the true
optimum, so being early in it is suggestive rather than decisive. The natural
question when a run is only part-way through: of the openers it has NOT reached,
how good is the best one by the OTHER ordering -- sum of squared bin sizes, the
split-quality heuristic --sweep and --topk use?

If the best unreached sum-of-squares rank is deep (say 4000th), the walk has
already covered everything either heuristic likes. If it is shallow (say 5th),
there is an opener both plausible and untested, and the provisional answer is
worth less.

Run:  python3 tools/orderdiag.py --length 6 --depth 5 --done 1535   # from math/

--done is the completed-opener count from the sweep.log progress line at the
moment of interest. NOTE the walk is threaded, so "the first N by root LB" is an
approximation of "the N that finished" -- close, but not exact.

This RE-DERIVES the solver's own definitions in numpy rather than reading them
out of the C. BRANCH is read from the run's log line if given, else measured the
same way the solver measures it.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import all_green, load_words  # noqa: E402


def build_lbtab(depth, n_max, branch, maxa):
    """LBTAB[d][n] exactly as build_lb() does it: fill candidates into the
    shallowest levels a branching factor of `branch` allows, and sum count*depth.
    INF (here: -1) when they cannot all fit within d guesses."""
    INF = -1
    tab = np.full((depth + 1, n_max + 1), INF, dtype=np.int64)
    for d in range(depth + 1):
        tab[d][0] = 0
        for n in range(1, n_max + 1):
            rem, total, cap, ok = n, 0, 1, False
            for k in range(1, d + 1):
                take = min(rem, cap)
                total += take * k
                rem -= take
                if rem == 0:
                    ok = True
                    break
                if cap < maxa:
                    cap *= branch
            tab[d][n] = total if ok else INF
    return tab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, required=True)
    ap.add_argument("--depth", type=int, required=True,
                    help="the cap in force when the openers of interest were walked")
    ap.add_argument("--done", type=int, required=True,
                    help="openers completed at the moment of interest")
    ap.add_argument("--branch", type=int, default=None,
                    help="override the measured branching factor (from the log line)")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    guesses = load_words("guess", args.length)
    answers = load_words("mystery", args.length)
    pat = load_patterns(length=args.length)
    ng, na = len(guesses), len(answers)
    assert pat.shape == (ng, na), f"{pat.shape} vs {(ng, na)}"
    win = all_green(args.length)
    npat = win + 1

    # Per-opener bin counts, and from them both orderings at once.
    ssq = np.empty(ng, dtype=np.int64)
    bins = np.empty((ng, 0), dtype=np.int32)
    counts = []
    branch_seen = 1
    for g in range(ng):
        c = np.bincount(np.asarray(pat[g]), minlength=npat)
        counts.append(c)
        ssq[g] = int((c.astype(np.int64) ** 2).sum())   # sweep_order(): ALL bins
        k = int((c > 0).sum()) - (1 if c[win] > 0 else 0)
        branch_seen = max(branch_seen, k)
    branch = args.branch if args.branch else branch_seen
    print(f"length {args.length}: {ng} guesses x {na} answers, "
          f"BRANCH={branch}{' (measured)' if not args.branch else ' (given)'}")

    lbtab = build_lbtab(args.depth, na, branch, na + 16)
    row = lbtab[args.depth - 1]
    lb = np.empty(ng, dtype=np.int64)
    for g in range(ng):
        c = counts[g]
        nz = np.nonzero(c)[0]
        nz = nz[nz != win]
        vals = row[c[nz]]
        lb[g] = -1 if (vals < 0).any() else na + int(vals.sum())

    # The solver packs (lb << 20 | g) and qsorts, so ties break by guess index.
    finite = lb >= 0
    lb_order = np.array(sorted(np.nonzero(finite)[0], key=lambda g: (lb[g], g)))
    ssq_rank = {g: r for r, g in enumerate(np.argsort(ssq, kind="stable"), start=1)}

    walked = set(lb_order[:args.done].tolist())
    print(f"walked (approx): first {args.done} of {len(lb_order)} by ascending root LB")

    unreached = [g for g in np.argsort(ssq, kind="stable") if g not in walked]
    print(f"\nbest UNREACHED openers by sum of squares (lower = evener split):")
    print(f"  {'ssq rank':>9} {'word':<14} {'ssq':>12} {'root LB':>9} {'LB rank':>8}")
    lb_rank = {g: r for r, g in enumerate(lb_order, start=1)}
    for g in unreached[:args.top]:
        print(f"  {ssq_rank[g]:>9} {guesses[g]:<14} {ssq[g]:>12} "
              f"{lb[g] if lb[g] >= 0 else 'INF':>9} {lb_rank.get(g, '-'):>8}")

    covered = [ssq_rank[g] for g in walked]
    print(f"\nof the {args.done} walked, sum-of-squares ranks: "
          f"best {min(covered)}, median {int(np.median(covered))}, worst {max(covered)}")
    top_n = args.done
    hit = sum(1 for g in walked if ssq_rank[g] <= top_n)
    print(f"overlap: {hit}/{top_n} of the sum-of-squares top {top_n} were walked "
          f"({100.0 * hit / top_n:.1f}%)")


if __name__ == "__main__":
    main()
