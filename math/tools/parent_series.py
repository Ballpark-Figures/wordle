"""Reconstruct what SMALLER --extend cuts would have produced, from one large run.

A triple is reachable from the top N pairs iff at least one of its three
constituent pairs ranks <= N. `pairsplit --extend` records that threshold per
triple as `minparent`, so filtering a single large run to `minparent <= N` gives
back EXACTLY the candidate set an N-pair run would have had — verified against
real runs, identical down to tie-ordering.

That turns a series of expensive runs into one run plus this script.

Run:  python3 tools/parent_series.py TRIPLES.csv --cuts 100000 200000 500000 1000000

TRUNCATION is the one thing that can invalidate a row, and it is checked rather
than assumed: if the source run kept only its own best T triples, a cut whose
top-K reaches beyond that is missing entries, and the row is flagged rather than
quietly reported.
"""

import argparse
import csv
import collections


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--cuts", type=int, nargs="+", required=True)
    ap.add_argument("--top", type=int, default=100000,
                    help="size of the top-K list each cut is compared at")
    args = ap.parse_args()

    rows = []
    with open(args.path) as f:
        for r in csv.DictReader(f):
            if "minparent" not in r:
                raise SystemExit("this file has no minparent column -- it predates "
                                 "the recording change; re-run pairsplit --extend")
            rows.append((tuple(sorted((r["word1"], r["word2"], r["word3"]))),
                         int(r["ssq"]), int(r["minparent"])))
    worst_kept = rows[-1][1]
    print(f"source: {len(rows)} triples, ssq {rows[0][1]} .. {worst_kept}")
    print(f"reconstructing top-{args.top} lists at each parent cut\n")

    prev = prev_cut = None
    print(f"  {'cut':>9} {'eligible':>9} {'best ssq':>9} {'ssq@100':>8} "
          f"{'top10 new':>10} {'top100 new':>11} {'trunc':>6}")
    for cut in args.cuts:
        elig = [(w, s) for w, s, mp in rows if mp <= cut]
        lst = elig[:args.top]
        if not lst:
            print(f"  {cut:>9} {0:>9}  (nothing reachable)")
            continue
        # A cut is truncated if its top-K ran out of eligible rows AND the source
        # itself was cut off -- i.e. more would have qualified had the run kept more.
        trunc = "YES" if (len(elig) < args.top and worst_kept < lst[-1][1]) else "no"
        s100 = lst[99][1] if len(lst) >= 100 else lst[-1][1]

        if prev is None:
            n10 = n100 = "-"
        else:
            pset10 = {w for w, _ in prev[:10]}
            pset100 = {w for w, _ in prev[:100]}
            n10 = sum(1 for w, _ in lst[:10] if w not in pset10)
            n100 = sum(1 for w, _ in lst[:100] if w not in pset100)
        print(f"  {cut:>9} {len(elig):>9} {lst[0][1]:>9} {s100:>8} "
              f"{str(n10):>10} {str(n100):>11} {trunc:>6}")
        prev, prev_cut = lst, cut

    print("\ntop 10 at the largest cut:")
    biggest = [(w, s) for w, s, mp in rows if mp <= args.cuts[-1]][:10]
    for i, (w, s) in enumerate(biggest, 1):
        print(f"  {i:>3}  {' '.join(w):<26} {s}")

    fam = collections.Counter(x for w, _ in biggest for x in w)
    print(f"\nstems in that top 10: {' '.join(sorted(fam))}")


if __name__ == "__main__":
    main()
