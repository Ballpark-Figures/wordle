# Two-word openers

What it costs to commit to TWO opening words up front, instead of choosing the
second in response to the first one's feedback.

All figures are over the standard 5-letter problem — 2315 answers, depth cap 6 —
and are TOTAL guesses summed over all answers, subject to that cap. Divide by
2315 for the expected figure.

## Reference: one opener, adaptive play throughout

| guesses allowed | best opener | total | avg | status |
|---|---|---|---|---|
| all 12972 | `salet` | 7920 | 3.42117 | Bertsimas & Paskov, reproduced |
| answers only (2315) | `slate` | 7973 | 3.44406 | complete 2315-opener sweep |

## The rule: `--pair-adaptive N`

Both words are played BLIND — the second is fixed in advance, not chosen from the
first one's feedback — EXCEPT that when the first word alone has already cut the
field to `N` or fewer answers, the blind word is abandoned and play continues
optimally.

| N | behaviour | a bucket of that size costs |
|---|---|---|
| 0 | pure blind, `g2` always played | — |
| 1 | one answer left: say it | 2 |
| 2 | two left: guess them in order | 2 + 3 |

`N` IS PART OF THE OBJECTIVE, not a tuning knob: 0, 1 and 2 are three different
games and their totals are not comparable to each other. N stops at 2 because at
N = 3 the objective goes indifferent — guessing three candidates in order costs
1+2+3 = 6, and a perfect three-way split costs 2+2+2 = 6, so minimising the total
no longer picks the strategy and only VARIANCE separates them.

ORDER MATTERS, and increasingly so with N. Every pair is evaluated in both
orders. At N=0 the gap is exactly 1 whenever one word is an answer (it wins at
guess 1 instead of guess 2); by N=2 the gap for `parse`/`clint` is 19, because
the rule keys on singleton buckets of the FIRST word's partition.

## Results

### All 12972 words legal — best of 100,000 screened pairs

| N | best pair | total | avg | vs `salet` |
|---|---|---|---|---|
| 0 | `parse` + `clint` | 8325 | 3.59611 | +405 (+0.175/answer) |
| 1 | `parse` + `clint` | 8290 | 3.58099 | +370 (+0.160) |
| 2 | `parse` + `clint` | 8269 | 3.57192 | +349 (+0.151) |

**PROVISIONAL — "best of the pairs screened", not the optimal pair.** The screen
ranks by joint sum of squares, which proves nothing (unlike the solver's root
lower bound), so a better pair can sit outside the list. Two things temper that:
widening the screen from 10,000 to 100,000 changed neither the winner nor the
total, and the winner sits at ssq rank 999 — comfortably inside, though that is
not evidence the cut was wide enough.

### Answers only (2315 legal guesses) — EXHAUSTIVE over all 2,678,455 pairs

| N | best pair | total | avg | vs `slate` |
|---|---|---|---|---|
| 0 | `crane` + `spilt` (ties `spilt` + `crane`) | 8350 | 3.60691 | +377 (+0.163) |
| 1 | `spilt` + `crane` | 8312 | 3.59050 | +339 (+0.146) |
| 2 | `crane` + `spilt` | 8299 | 3.58488 | +326 (+0.141) |

**These are PROVEN optima over answer-word pairs**, not screened results:
`C(2315,2) = 2678455` and the screen kept all of them, so every pair was
evaluated in both orders. The solver still prints its boilerplate "best of the
pairs SCREENED ... which is a heuristic" line, which is WRONG for this case — the
program cannot tell an exhaustive list from a truncated one. Ignore it here.

## What the numbers say

- **Committing to two blind words costs about 0.175 guesses per answer** against
  optimal adaptive play (3.596 vs 3.421). The adaptive rules claw back roughly a
  seventh of that: 0.175 → 0.160 → 0.151.
- **Restricting to answer words is nearly free for pairs** — 8350 against 8325,
  25 guesses or 0.011 per answer. The pairs that win are ordinary words anyway.
  For a single opener the same restriction costs 53 (7973 vs 7920).
- **Two words cut the field far harder than one.** Expected survivors after the
  opening: 60.4 for the best single word (`roate`), 4.3 for the best pair
  (`carse` + `doilt`). That is a screen statistic, not a solve result.
- **The winner never moved with N.** `parse`+`clint` wins every unrestricted
  variant and the `crane`/`spilt` pair every answers-only one; the rules changed
  the totals, not the choice. The ORDER does move, though: the two tie at N=0,
  `spilt` first wins at N=1, and `crane` first wins at N=2 — the adaptive rule
  rewards whichever word isolates more answers on its own, and that is not the
  word that wins the blind race.

## Reproducing

    ./solver/pairsplit --top 100000 --threads 18 \
        --out data/shared/pairs/top100000_ssq.csv          # ~21s for all 84M pairs

    ./solver/optturns --pair-list data/shared/pairs/top100000_ssq.csv \
        --pair-adaptive 2 --depth 6 --tt-bits 28 --threads 18 \
        --out data/shared/pairs/pair_totals_100k_adapt2.csv

Add `--guess-list data/shared/words/mystery.txt` to both for the answers-only
variant. Stage 2 runs in seconds: the incumbent tightens almost immediately, so
roughly 28 of 200,000 ordered candidates are ever searched and the rest are cut.
