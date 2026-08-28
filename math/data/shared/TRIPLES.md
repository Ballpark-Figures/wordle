# Three-word openers

The screen for THREE opening words committed up front. Companion to `PAIRS.md`;
same problem (2315 answers, depth cap 6) and same score.

## How the screen works, and what it cannot do

`pairsplit --extend PAIRS.csv` takes each pair in a file and adds every allowed
word as a third, scoring the triple by `sum |joint bucket|^2` — same bucket iff
the same pattern to all three words.

**This is GREEDY, and that is the binding limitation.** A triple is reachable
only if at least one of its three constituent PAIRS is in the parent list. A
triple whose every 2-word prefix is mediocre cannot be found at any `--top`,
so no run of this shape can prove a best triple. Exhausting the space is not an
option either: `C(12972,3)` is 3.6e11, and extending from all 84M pairs would be
~100 hours against the 73 minutes 1M took.

Two properties make it tractable and honest:

- **Each distinct triple is emitted exactly once.** A triple has up to three
  parent pairs in the list; it is emitted only from the first present one. This
  replaces generating duplicates and filtering them afterwards, which needs a
  guessed over-collection factor and silently under-delivers if the guess is low.
- **`minparent` is recorded per triple** — the best rank among its parent pairs,
  i.e. the smallest cut at which it becomes reachable. Filtering one large run to
  `minparent <= N` reconstructs EXACTLY what an N-pair run would have produced.
  Verified against real runs: identical down to tie-ordering. So the series below
  is one run, not nine. `tools/parent_series.py` reads it out and FLAGS
  truncation rather than assuming none.

## The series (all 12972 words legal)

One run: top 1,000,000 pairs, extended by every word, 4385 s.

| parent cut | eligible | best ssq | ssq@100 | top-10 new | top-100 new |
|---|---|---|---|---|---|
| 10,000 | 28552 | 3293 | 3449 | — | — |
| 20,000 | 53614 | 3293 | 3419 | 1 | 42 |
| 30,000 | 76496 | 3293 | 3405 | 1 | 27 |
| 50,000 | 119026 | 3293 | 3383 | 7 | 47 |
| 100,000 | 211811 | **3281** | 3369 | 5 | 43 |
| 200,000 | 366866 | 3281 | 3361 | 2 | 26 |
| 300,000 | 495264 | 3281 | 3357 | 2 | 18 |
| 500,000 | 697694 | 3281 | 3351 | 2 | 15 |
| 1,000,000 | 1000000 | 3281 | 3347 | **0** | 10 |

No cut was truncated. The 10k–50k rows reproduce four earlier standalone runs
exactly (42, 27, 47), which is what validates the reconstruction.

### Best found

    1  ginch robed spalt   3281
    2  chimp robed slant   3293
    3  ginch plast robed   3297
    4  blind compt sarge   3303
    5  boned clasp right   3303

## Reading the series

Rank 1 held at 3281 across a 10x widening (100k to 1M), top-10 churn reached
zero, and top-100 churn decayed monotonically after the 50k/100k disruption:
47, 43, 26, 18, 15, 10. The top 10 also stopped being one family — at 30k it was
all `chimp`/`chimb`/`chomp` variants; by 1M it is many independent stems
(`ginch`, `blind`+`compt`+`sarge`, `clomb`+`giant`+`spred`), which is what
saturation looks like rather than one family being mined out.

**CONVERGENCE WAS CALLED TWICE BEFORE AND WAS WRONG BOTH TIMES.** After 20k->30k
the churn fell 42 to 27 and that looked like convergence; it was one family being
exhausted, and 30k->50k jumped back to 47 as new families became reachable. Then
50k->100k moved rank 1 itself. What is different now is the weight of evidence —
a 10x widening with rank 1 fixed, zero top-10 churn, monotone decay in both
measures — not a new kind of argument.

So: **"3281, `ginch`+`robed`+`spalt`, stable across a 10x widening"** is the
defensible claim. Not "the optimal triple". The greedy prefix requirement is
untouched by any of this, and the exhaustive-and-therefore-proven result that
answers-only pairs enjoy has no counterpart here.

## Reproducing

    ./solver/pairsplit --top 1000000 --threads 18 \
        --out data/shared/pairs/top1000000_ssq.csv                    # ~21 s

    ./solver/pairsplit --extend data/shared/pairs/top1000000_ssq.csv \
        --top 1000000 --threads 18 \
        --out data/shared/pairs/triples_from1m_ssq.csv                # ~73 min

    python3 tools/parent_series.py data/shared/pairs/triples_from1m_ssq.csv \
        --cuts 10000 20000 30000 50000 100000 200000 300000 500000 1000000

The extend's `--top` must be far larger than the top-K you intend to reconstruct:
rebuilding the top-100k at cut 200k needs those triples still present even though
better ones outrank them at cut 1M. 1,000,000 gave ample headroom at every cut.

Add `--guess-list data/shared/words/mystery.txt` to BOTH commands for the
answers-only variant.
