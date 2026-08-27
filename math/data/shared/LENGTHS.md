# Optimal play at other word lengths

Wordle is 5 letters, so a length sweep needs a source that curates BOTH a guess
list and an answer list at every length under one rule. That source is **hello
wordl** ([lynn/hello](https://github.com/lynn/hello), MIT), pinned at commit
`835db051e78d0dba4e38bc4b19ae5560b8efbbc3` and rebuilt by `build_wordlists.py`.

**These are NOT the Wordle numbers and are not comparable to them.** The top-level
`words/{guess,mystery}.txt` (12972 / 2315, NYT) are untouched and remain the
canonical 5-letter problem. hello's answer list is a looser curation — at 5
letters it holds 3238 words, only 2077 of which are among the NYT 2315.

One inconsistency is inherited from the source and worth knowing: hello's
dictionary is a North-American Scrabble list (TWL/NWL family) at every length
EXCEPT 5, where it is Wordle's own 12972 — a Collins list. So a cross-length
comparison that includes hello's length 5 is comparing two Scrabble dialects.

## The objective

    Minimise the TOTAL guesses summed over all answers, SUBJECT TO resolving
    every answer within the depth cap.

The cap is part of the objective, not a tuning knob. A depth-4 total and a
depth-5 total are DIFFERENT QUANTITIES and must never be compared as if one
beat the other — a tighter cap can only raise the total. Report every number
below as "optimal subject to a d-guess guarantee", never as minimum expected
guesses.

## Results

COMPLETE = every opener examined; the run's own accounting balances
(searched + cut + infeasible = the full guess list).

| L | guesses | answers | depth | total | avg | optimal opener | status |
|---|---|---|---|---|---|---|---|
| 7 | 24028 | 5137 | 4 | 14873 | 2.89527 | `saltine` | COMPLETE (306 s) |
| 8 | 29765 | 5327 | 4 | 14480 | 2.71823 | `ceratins` | COMPLETE (37 s) |
| 9 | 29150 | 5056 | 3 | 12882 | 2.54786 | `saprolite` | COMPLETE (4 s) |
| 10 | 22326 | 4030 | 3 | 9631 | 2.38983 | `mercantile` | COMPLETE (5 s) |
| 11 | 16165 | 3022 | 3 | 6823 | 2.25778 | `meteoritics` | COMPLETE (9 s) |
| 6 | 15787 | 4561 | 5 | 14482 | 3.17518 | `carnet` | **PROVISIONAL** (819/15787) |
| 6 | 15787 | 4561 | 4 | 14961 | 3.28020 | `distal` | **PROVISIONAL** (2821/15787) |
| 4 | 4030 | 2347 | — | — | — | — | not run |

For 7–11 the depth shown is also the MINIMUM achievable depth: those runs
escalated from a floor of 2 and stopped at the first cap any opener could meet,
so the result is lexicographic — fewest worst-case guesses first, then lowest
total within that.

### Length 6 is provisional — say so on screen

Stopped deliberately, not finished. `carnet` is **the best of the first 819 of
15787 openers** (5.2%), visited in ascending sum-of-squares order. It is not a
proven optimum, and the honest phrasing is "probably the result".

What supports it: the visit order front-loads the evenest splitters, and
`carnet` is 19th in it. When the earlier root-LB-ordered run was stopped, the
entire sum-of-squares top 118 had already been examined, so `carnet` survived
the head of BOTH heuristics, not just the one being sorted on.

What does not: the orderings are heuristics, and 5% of a field is 5% of a field.

`distal` at depth 4 is provisional in the same way, from a pinned depth-4 pass
stopped at 2821 of 15787. Its evidence is a different shape and arguably stronger:
of those 2821 openers, **2820 were proven INFEASIBLE at depth 4** and `distal` is
the only one that solved at all. Depth 4 is a severe constraint at this length —
nearly no opener can resolve all 4561 answers within four guesses — so the
question there is less "is 14961 the lowest total" than "how many openers can do
it at all", and so far the answer is one in 2821.

Note the two length-6 rows are NOT comparable as totals: 14961 at depth 4 is worse
than 14482 at depth 5 only because the cap is tighter, which is exactly what the
cap being part of the objective means.

## Reproducing

    python3 build_wordlists.py                       # once, all lengths
    python3 build_patterns.py --length 6             # per length
    cd solver && sh build.sh 6                       # per length
    bash solver/run-length-sweep.sh --length 6 --depth 5

Full detail — the ordering choice, why the cap is pinned, what a stopped run
does and does not prove — is in `solver/README.md`.
