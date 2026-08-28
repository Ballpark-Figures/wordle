"""Compare two screen outputs — pair or triple CSVs — and say how much they differ.

The question this answers: when a screen is widened (more parent pairs, a bigger
--top), does the extra work surface anything NEAR THE TOP, or does it only pad
the tail? If the entries unique to the wider run all sit at rank 90,000+, the
narrower screen was adequate for anything you would actually report. If they
appear in the first hundred, it was not — and neither run can be trusted as
"best of N" without widening further.

Rows are canonicalised as SORTED word tuples, because both screens score
unordered sets: a pair's or triple's joint partition cannot depend on play order,
so {a,b,c} is one entry however the columns happen to be arranged.

Run:  python3 tools/compare_screens.py A.csv B.csv --labels 10k 20k   # from math/
"""

import argparse
import csv
import os
import sys


def load(path):
    """Return [(canonical tuple, ssq)] in file order, which is rank order."""
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            words = tuple(sorted(v for k, v in r.items()
                                 if k.startswith("word") and v))
            rows.append((words, int(r["ssq"])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--labels", nargs=2, default=None)
    args = ap.parse_args()
    la, lb = args.labels or (os.path.basename(args.a), os.path.basename(args.b))

    A, B = load(args.a), load(args.b)
    sa = {w for w, _ in A}
    sb = {w for w, _ in B}
    rank_b = {w: i for i, (w, _) in enumerate(B, start=1)}
    rank_a = {w: i for i, (w, _) in enumerate(A, start=1)}

    print(f"{la}: {len(A)} rows, ssq {A[0][1]} .. {A[-1][1]}")
    print(f"{lb}: {len(B)} rows, ssq {B[0][1]} .. {B[-1][1]}")
    print()
    print(f"in both      : {len(sa & sb)}")
    print(f"only in {la:<8}: {len(sa - sb)}")
    print(f"only in {lb:<8}: {len(sb - sa)}")
    print(f"Jaccard      : {len(sa & sb) / len(sa | sb):.4f}")

    print(f"\ntop-of-list agreement (prefix overlap):")
    print(f"  {'depth':>8} {'shared':>8} {'of':>8}")
    for n in (1, 10, 100, 1000, 10000, 100000):
        if n > min(len(A), len(B)):
            continue
        pa = {w for w, _ in A[:n]}
        pb = {w for w, _ in B[:n]}
        print(f"  {n:>8} {len(pa & pb):>8} {n:>8}")

    if A[0][0] == B[0][0]:
        print(f"\nsame winner: {' + '.join(A[0][0])}  ssq={A[0][1]}")
    else:
        print(f"\nDIFFERENT winners:")
        print(f"  {la}: {' + '.join(A[0][0])}  ssq={A[0][1]}")
        print(f"  {lb}: {' + '.join(B[0][0])}  ssq={B[0][1]}")

    # The decisive question: WHERE do the newcomers land?
    new = sb - sa
    if new:
        ranks = sorted(rank_b[w] for w in new)
        print(f"\nwhere the {len(new)} {lb}-only entries sit in {lb}'s ranking:")
        print(f"  best rank {ranks[0]}, median {ranks[len(ranks)//2]}, worst {ranks[-1]}")
        for cut in (100, 1000, 10000):
            k = sum(1 for r in ranks if r <= cut)
            print(f"  in {lb}'s top {cut:>6}: {k}")
        best = min(new, key=lambda w: rank_b[w])
        print(f"  highest-ranked newcomer: {' + '.join(best)} at rank {rank_b[best]}")

    lost = sa - sb
    if lost:
        ranks = sorted(rank_a[w] for w in lost)
        print(f"\n{len(lost)} entries fell OUT of the top {len(B)} when widening:")
        print(f"  they held ranks {ranks[0]} .. {ranks[-1]} in {la}")
        print(f"  (expected: a wider screen pushes the weakest of the old list off"
              f" the end, so these should cluster at the TAIL)")


if __name__ == "__main__":
    main()
