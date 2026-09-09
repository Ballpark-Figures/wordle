# Exact optimal-turns solver

Computes, for **every one of the 12,972 legal Wordle openers**, the exact
minimum expected number of turns under optimal play — plus the full optimal
decision tree for each. Reproduces and extends Bertsimas & Paskov, *An Exact
and Interpretable Solution to Wordle*.

`optturns.c` builds **two binaries**, one per ruleset:

| binary | ruleset | data directory |
|---|---|---|
| `optturns` | normal Wordle | `data/{shared,local}/optturns/` |
| `hardturns` | **hard mode** — revealed hints must be reused | `data/{shared,local}/hardturns/` |

They are the same source with `HARD` as a compile-time constant (`-DHARDMODE`),
so each keeps its hot loops free of the other's branches while both stay one
source of truth. Two output names also mean `hardturns` can be built and run
while an `optturns` sweep is in flight. Everything below applies to both;
`## Hard mode` covers what differs.

## The key idea

The objective is an **integer**: total guesses summed over all 2315 answers.
The paper's Table 1 averages are exactly integers over 2315, so the solver works
in integers throughout and comparisons are exact.

| word | total | expected |
|---|---|---|
| SALET | 7920 | 3.42117 |
| REAST | 7923 | 3.42246 |
| TRACE | 7926 | 3.42376 |
| CRATE | 7926 | 3.42376 |
| SLATE | 7928 | 3.42462 |

`bash solver/validate.sh` (run from `math/`) reproduces all five. **Always run
it after touching the solver** — a pass means bit-for-bit agreement with the
published result, not a rounding coincidence.

## Build

```sh
cd math/solver && sh build.sh          # builds optturns AND hardturns
```

`build.sh` writes both binaries. It will fail on `optturns` with `Text file
busy` if a sweep is running — that is the kernel refusing to overwrite a live
executable, and it is a feature. To build just the other one:

```sh
gcc -O3 -march=native -funroll-loops -fopenmp -DHARDMODE -o hardturns optturns.c
```

Requires `math/data/local/patterns/patterns.npy` (`python3 build_patterns.py`
in `math/`, ~4s). That file is gitignored and regenerable.

## Run

```sh
# from math/
./solver/optturns --opener salet                    # one word
./solver/optturns --sweep --out data/shared/optturns/opener_totals.csv \
    --trees data/local/optturns/trees --tt-bits 29 --threads 20
```

Outputs follow the repo's shared/local data split:

| path | git | what |
|---|---|---|
| `data/shared/optturns/opener_totals.csv` | committed | the results — syncs between machines |
| `data/local/optturns/trees/` | ignored | ~1 GB of gzipped optimal trees |
| `data/local/optturns/tt.bin` | ignored | transposition-table snapshot |
| `data/local/optturns/sweep.log` | ignored | run log |
| `data/local/optturns/archive/` | ignored | superseded runs |

Two wrappers set those flags for you. Both warm-start from `tt.bin` and append
to `sweep.log`; they differ only in whether the sweep is attached to a terminal.

```sh
bash solver/run-sweep.sh        # DEFAULT when you are at the machine
```

Runs in the FOREGROUND, output tee'd so completions scroll in your terminal AND
land in `sweep.log`. Ctrl-C stops it; the CSV is safe (flushed per word) but the
table is lost, so snapshot first if you want to keep it (see below).

`bash ~/bin/resume-jobs.sh` is the other path: same flags, but detached via
`nohup` with output only to `sweep.log`. It is wired to a Windows Scheduled Task
so a forced reboot self-recovers unattended. Watch it with
`tail -F data/local/optturns/sweep.log`.

Do NOT run the bare binary without a tee or redirect: `tools/report.py` and
`tools/inflight.py` PARSE `sweep.log` for the run's start, resume count and
elapsed time, so a run that never reaches the log makes the IN FLIGHT section
silently report the PREVIOUS run's numbers.

| flag | meaning |
|---|---|
| `--sweep` | all openers, best-heuristic-first, resumable |
| `--out FILE` | CSV: `word,total,expected,seconds`; flushed per word |
| `--trees DIR` | one `<word>.txt.gz` per opener, written before the CSV row |
| `--tt-bits N` | 2^N entries x 32 B. 29 = 17.2 GB, 28 = 8.6 GB, 24 = 0.5 GB. **0 disables the table entirely** — see Hard mode |
| `--tt-load F` | warm-start the table from a snapshot |
| `--tt-save F` | dump the table on normal completion |
| `--threads N` | OpenMP threads |

**Resume is automatic**: rerunning reads the CSV and skips finished openers.
Killing mid-word is safe — the CSV row is written only after that word's tree
file is complete, so an interrupted word is simply redone.

## Hard mode

`hardturns` solves the same problem under hard mode: **any revealed hint must be
used in subsequent guesses**. That is the NYT rule — a green must be repeated in
its position, a yellow letter must appear *somewhere* in the guess (legally
including the square it was yellow on), and greys constrain nothing, so an
all-black pattern imposes no restriction at all.

**The constraint is real extra state, not a function of the candidate set.**
This is the one thing to understand before touching the code. The accumulated
requirement is a pair — the letter each position is pinned to, and the minimum
number of copies of each letter — and the candidate set `S` only bounds it from
above: a green at position *i* means every word in `S` has that letter there,
but the converse fails. The words in `S` can happen to share a letter that was
never revealed, and hard mode does not pin an unrevealed letter. Two lines of
play reaching the same `S` with different revealed hints genuinely have
different legal-guess sets, so the constraint is hashed into the TT key
alongside `S` and the depth.

The legal set is a pure function of the constraint, materialised on demand by
intersecting precomputed bitsets — and only on a TT **miss**, since a hit never
needs it. Candidates are always legal (a word consistent with all feedback
necessarily has the greens in place and at least the revealed counts), which is
what keeps the `n == 1`, `n == 2` and depth-normalisation shortcuts valid.

The TT key also carries a hard-mode salt, so a `tt.bin` loaded into the wrong
binary fails verification and costs a recompute rather than returning a wrong
value. The two tables still must not be *resident* at once — 17.2 GB each.

**`INFEASIBLE` can actually fire here.** In normal mode no opener ever fails,
because you can always follow SALET's tree afterwards; that argument does not
survive hard mode, where the follow-up is restricted to guesses reusing the
hints. A `word,,,seconds` row (no total) is therefore a real, expected result,
not a bug. `tools/report.py` counts those separately.

### Running the hard sweep

```sh
# from math/
bash solver/run-hard-sweep.sh phase1     # share a machine with a live optturns
bash solver/run-hard-sweep.sh phase2     # take the machine once optturns is done
```

Two phases because the hard sweep is designed to start *while* the normal sweep
still owns the machine, then take over from it:

| | threads | table | niceness |
|---|---|---|---|
| `phase1` | 14 | `--tt-bits 24` (0.54 GB) | `nice -n 19` |
| `phase2` | 20 | `--tt-bits 29` (17.2 GB), warm from `tt.bin` | normal |

Both are overridable: `bash solver/run-hard-sweep.sh phase1 --threads 8 --tt-bits 26`.

**Sizing phase 1** (measured 2026-08-23, optturns on its last 6 openers):

- **14 threads.** optturns was using 586% CPU — 5.9 cores for its 6 in-flight
  openers — leaving ~13.7 genuinely idle; its finished threads *sleep* at the
  OpenMP barrier rather than spinning. 6 + 14 = 20, so the two do not actually
  contend. **Measure with `top -b -n 2 -d 3`, not `ps`**: `ps` `%CPU` is a
  lifetime average and read 1859% here, which would size this badly wrong.
- **`nice -n 19`** is CPU scheduling weight *only* (−20 highest … +19 lowest, 0
  default). It decides who wins when two processes want the **same core**, and
  costs nothing when cores are idle. It does **not** limit memory — RAM is
  governed entirely by `--tt-bits`.
- **`--tt-bits 24`** takes 0.54 GB of the 4.9 GiB available, leaving ~4.4 GiB.
  The thing to protect is optturns' **16 GiB resident table**: push that into
  swap and its throughput collapses. `--tt-bits 26` (2.15 GB) leaves ~2.8 GiB
  against optturns' ~1.4 GiB of still-unfaulted table — too thin while the
  normal sweep is the priority.

**`--tt-bits 0` means literally no memoisation** — every recurrence of a deep
state is recomputed from scratch. Measured on SALET, the *easiest* opener: 119 s
with the 0.54 GB table, still unfinished after 5.5 minutes with none. The hard
openers, where the table matters most, are far worse. Prefer the smallest table
that fits over no table at all.

`phase2` refuses to start while `optturns` is still running, since the two
17.2 GB tables do not fit at once. Resume is automatic across the switch:
finished openers come from the CSV, so stopping phase 1 and starting phase 2
simply continues the sweep.

### Reading hard-mode results

Every tool takes `WORDLE_SOLVER` to choose which sweep it reads (default
`optturns`). The name doubles as the binary name, so the tt* tools also use it
to pick which process to attach to.

```sh
WORDLE_SOLVER=hardturns python3 tools/report.py
WORDLE_SOLVER=hardturns python3 tools/lookup.py
tail -F data/local/hardturns/sweep.log
```

### Verifying the trees

`tools/checktrees.py` replays every line of an emitted tree against the repo's
own `wordle.pattern` and re-derives the hard-mode constraint from scratch, so a
bug in the solver's constraint handling surfaces as a legality failure rather
than a plausible-looking wrong number. It checks answer coverage, guess counts,
pattern consistency, hint reuse, and that the tree sums to the CSV total.

```sh
WORDLE_SOLVER=hardturns python3 tools/checktrees.py           # 20-tree sample
WORDLE_SOLVER=hardturns python3 tools/checktrees.py salet     # named openers
WORDLE_SOLVER=hardturns python3 tools/checktrees.py --all     # everything
```

It exits nonzero on any failure, so it works as a gate. Run it against a normal
tree too (`python3 tools/checktrees.py salet`) — the hard-mode legality check is
skipped there, and the same tree fails ~1450 of 2315 lines if you force it on,
which is what confirms the check actually fires.

## Ultra hard mode (`ultraturns`)

`ultraturns` is the fourth compile-time mode of `optturns.c` (`-DULTRA`). Same
word lists, same objective shape, **a stricter legal-guess rule than hard mode**:

> Minimise the **total guesses summed over all 2315 answers**, where every guess
> — the opener and every follow-up — must itself be **consistent with every clue
> seen so far** (a word the answer could still be), subject to resolving every
> answer within `--depth` guesses.

So the legal guess set at any node is exactly the set of the 12972 words still
consistent with the accumulated feedback. That is strictly smaller than hard
mode's: hard mode only forces greens to be repeated in place and yellow letters
to reappear *somewhere*, and lets any grey-satisfying word through; ultra mode
also honours **greys** (exact letter counts, forbidden positions) and **yellow
position exclusions**. A word you guessed and missed is illegal thereafter,
because its own greys/yellows rule it out.

**Do not put an `ultraturns` total in a table with a `hardturns` or `optturns`
one.** A strictly smaller legal set can only raise the total, so
`ultra ≥ hard ≥ normal` — three different objectives, not one game at three
difficulty settings. Same trap as mixing a capped optimum with an
expected-guesses one.

**The constraint is REAL EXTRA STATE, exactly as in hard mode.** Two lines
reaching the same candidate set `S` can have eliminated different guess-only
words, so their legal sets differ; the accumulated constraint is hashed into the
TT key. It is carried as **per-position allowed-letter masks plus per-letter
`lo`/`hi` count bounds** — the same representation `strspace.py` uses — which is
**exact for filtering words** (against a clue `(g, p)`, `pattern(g, w) == p` iff
`w` matches at greens, differs elsewhere, and holds the count implied by the
green/yellow/grey split; the conjunction of clues is the intersection). The
"repeated-letter trap" `strspace.py` guards is a fact about *enumerating*
reachable patterns, not about filtering, and does not arise here — the real
answers are still partitioned by the real pattern matrix. `cons_apply` /
`cons_legal` / `cons_hash` have an `#if ULT` branch beside hard mode's; the
bitset machinery (`BS_POS` / `BS_CNT` / `BS_ALL`) is shared.

**Candidates are always legal** (an answer consistent with the clues trivially
satisfies its own constraint), so the `n == 1`, `n == 2` and `d > n` shortcuts
hold unchanged, exactly as in hard mode.

**`--depth` is REQUIRED and it BINDS.** Like hard mode and Mastermind, ultra
mode has genuine `INFEASIBLE` openers — "follow SALET's tree afterwards" is
illegal when the follow-up must stay consistent — so the cap is part of the
objective and each depth is a different quantity with its own CSV. Unlike hard
mode this does **not** escalate the cap; it is pinned to `--depth`.

**`ULTRA` is in the TT salt** (a distinct constant from hard mode's), so an
`optturns`/`hardturns`/`mmturns` `tt.bin` fails verification in `ultraturns`
instead of answering, and vice versa.

```sh
# from math/
bash solver/run-ultra-sweep.sh --depth 6 -k 100     # best opener, top-k 100
./solver/ultraturns --opener salet --depth 6 --topk 100 \
    --trees data/shared/ultraturns/trees            # one opener, with its tree
```

`--topk` is the intended mode: the exact solver is correct but slow here,
because the legal set is large near the root. The wrapper requires it, mirrors
`run-mm-sweep.sh` (`--optimal-only`, `--print-openers`, per-`(depth, K)` CSV
under `data/{shared,local}/ultraturns/`), and emits no trees — the winner's tree
needs a follow-up `--opener <winner>` run at the same depth and K, exactly as
Mastermind does. The result is an **upper bound**, best of the K openers
examined, and `INFEASIBLE` under `--topk` says nothing about the problem, only
about the restricted branching.

**No dedicated gate yet.** `checktrees.py` verifies hard-mode legality, not the
stricter ultra rule, so it does not fully validate an ultra tree. The property
to check independently is that **every guess after the opener reproduces every
prior clue** (`pattern(g_i, g_j) == p_i` for all `i < j`), which the smoke test
that shipped this mode confirmed on `salet`'s full tree (2315 answers, all lines
legal). Building that into a real gate is the open follow-up.

## Mastermind feedback (`mmturns`)

`mmturns` is the third compile-time mode of `optturns.c` (`-DMASTERMIND`,
alongside `-DHARDMODE`). Same word lists, same objective shape, **different
feedback**: the codebreaker is told Mastermind's **peg counts** — how many
letters are right *in place* (blacks) and how many are right *in the wrong
place* (whites) — and never which positions those were.

> Minimise the **total guesses summed over all 2315 answers**, where the reply
> to each guess is its **(blacks, whites) peg counts**, subject to resolving
> every answer within `--depth` guesses.

**Do not put an `mmturns` total in a table with an `optturns` one.** Peg feedback
is strictly coarser — 20 outcomes against Wordle's 238 — so these are optima of
two different games, not two difficulty settings of one.

**No new feedback code, and that is the point.** The peg counts are a *function*
of the stored Wordle pattern: `blacks` is the number of greens and `whites` the
number of yellows, because Wordle's yellow rule hands out exactly
`min(guess_c, answer_c) − green_c` copies of each letter and that sums to the
white-peg count. So `-DMASTERMIND` is one remap of the loaded matrix
(`mm_remap`) plus a narrowed `NPAT`; every hot loop is untouched, and
`solver/validate.sh` still reproduces all five totals with identical node counts
(salet 16672) because `optturns` compiles exactly as before.

**The feedback space is 20 codes at 5 letters**: every `(blacks, whites)` with
`blacks + whites ≤ 5`, less the single impossible pair `(4, 1)`. With four exact
matches the two words differ in one position only, so the odd guess letter is
matched against a different answer letter while every other copy of it is already
consumed by an exact match — `whites` is forced to 0. `mm_code` enumerates blacks
ascending, which puts the win `(5, 0)` last, so `ALL_GREEN == NPAT − 1` keeps its
meaning and nothing that tests `p == ALL_GREEN` changes.

**`--depth` is REQUIRED and it BINDS.** `optturns`' default of 6 is slack because
238 outcomes branch fast; at 20 they do not, so a depth-7 pass and a depth-9 pass
are different quantities and get different CSVs. The binary refuses to start
without an explicit `--depth` rather than inherit a cap nobody chose.
**The minimum feasible depth is an OPEN QUESTION** — the counting bound only
gives `≥ 4`, which is not restrictive, so settling it needs a real run.
`INFEASIBLE` is an expected result here, not a bug.

`MASTERMIND` is in the TT salt **unconditionally**, and that matters more here
than anywhere else: the word lists are identical, so a colour-feedback table and
a peg-feedback table would agree on every key while meaning different games. An
`optturns` `tt.bin` therefore fails verification in `mmturns` instead of
answering.

Hard mode and Mastermind cannot be combined (`#error`): hard mode's rule is
stated in per-tile colours, which peg counts do not report.

```sh
# from math/
bash solver/run-mm-sweep.sh --depth 8            # the top-k 1 run
bash solver/run-mm-sweep.sh --depth 8 -k 20
bash solver/run-mm-sweep.sh --depth 8 --guesses mystery   # answers-only guesses
```

`--topk K` restricts branching at every branching point **including the root**,
so `-k 1` examines exactly one opener — the best of the 12972 by root sum of
squared bin sizes — and the total is an upper bound, the best of the K examined.
The run prints the measured `BRANCH` and the opener it picked in its first lines.

**Every opener gets a terminal line**, because the wrapper passes
`--print-openers`. An opener examined by `--optimal-only` ends in one of five
states, and by default only three of them printed:

| outcome | CSV row | default | with `--print-openers` |
|---|---|---|---|
| `NEW BEST` — beat the incumbent | yes | printed | printed |
| `TIED` — equalled it | yes | printed | printed |
| solved, but *worse* than the incumbent | **yes** | **silent** | printed |
| `CUT` — search abandoned, cannot beat the incumbent | no | **silent** | printed |
| `LB-SKIP` — root bound exceeds the incumbent, never searched | no | **silent** | printed |
| `INFEASIBLE` — cannot fit the cap | no | printed | printed |

The third row is why a k=10 run wrote 10 CSV rows and showed only a handful in
the terminal. `LB-SKIP` is the quietest of the lot — no row, no line, and easily
mistaken for an opener that was never examined at all, when in fact its bound is
a real result about it: *cannot beat the incumbent, proved without searching*.

`--print-openers` is **off by default** so the `allwords` and `ansall` logs stay
byte-identical, and it is a no-op (with a note) outside `--optimal-only`, since
the plain sweep already prints every opener.

`--optimal-only` emits **no trees**, so the winner's tree needs a follow-up
`./solver/mmturns --opener <winner> --depth <D> --trees <dir>` at the same depth.
Data lands in `math/data/{shared,local}/mmturns/`, one file set per (depth, K).

**The gate is `python3 tools/checkmastermind.py`** (`--wide` adds the full
matrix). It checks the encoding against a Python mirror of `mm_code`, the
blacks/whites identity against peg counts recomputed **from the strings** by the
textbook rule (exhaustively on small alphabets, and over all 30,030,180 real
guess × answer pairs under `--wide`), that `(4, 1)` really is the only hole, and
— the one that exercises the search itself — `mmturns` against a brute-force
memoised solver on a miniature 24 × 16 data directory, at two depths so both the
solved and `INFEASIBLE` branches are compared. Run it alongside
`solver/validate.sh` and `tools/checkpatterns.py`.

## Answers-only (`--guess-list`)

`--guess-list FILE` restricts the **legal guesses** to the words in `FILE`. The
answers are untouched — the objective is still the total over all 2315 answers,
only what may be *played* changes. Pointing it at `mystery.txt` gives the
answers-only variant:

> Minimise the **total guesses summed over all 2315 answers**, where **every
> guess — the opener and every follow-up — must itself be one of the 2315 answer
> words**, subject to resolving every answer within `--depth` guesses.

```sh
# from math/
bash solver/run-ans-sweep.sh                        # the sweep, attached
bash solver/run-ans-sweep.sh --threads 12 --tt-bits 26
./solver/optturns --guess-list data/shared/words/mystery.txt \
    --opener crate --depth 6 --tt-bits 26           # one opener
```

**No hot loop changed.** Every guess enumeration in `solve()` walks `0..NG-1`,
and `--sweep` walks the same range, so compacting `GWORD` and the pattern matrix
down to the listed words restricts the follow-up guesses AND the set of openers
swept, in one move. The sweep therefore covers **2315 openers, not 12972**.

**The TT key is salted with the guess set** (`GSALT`). The same candidate set has
a genuinely different optimum when the legal guesses differ, so a shared key
would return a wrong value. The salt is **0 for the full list**, leaving those
hashes bit-identical to what they have always been — verified by `validate.sh`
reproducing all five totals *and* their TT hit rates unchanged, so existing
`tt.bin` snapshots stay valid.

**THE DEPTH CAP BINDS HERE — that is the whole point, not an oversight.** Normal
mode justifies `--depth 6` with "any opener can follow SALET's tree afterwards".
**SALET is not an answer word, and neither is REAST** (`grep -cx salet
mystery.txt` → 0). That escape is illegal under these rules, so the feasibility
argument does not transfer, exactly as it fails to transfer into hard mode.
`INFEASIBLE` rows are an **expected result** here: a `word,,,,secs` CSV row is
data, not a bug. Report these as optima **subject to a 6-guess guarantee** —
never as "minimum expected guesses".

**Proving INFEASIBLE is the expensive case.** Restricting to answer words removes
the pure probe guesses (SALET, REAST — words played to split the field, never to
win), so partitions are coarser and `LBTAB` is weaker. Under a strict cap that
means much more search, and an opener with no ≤6 solution must exhaust the space
before it can say so. Expect this variant to be *slower per opener* than the full
sweep, not faster, despite the smaller guess set.

The per-word terminal line drops `exp=` (it is just `total/2315`); the CSV still
carries it so `tools/report.py` is unaffected. The trailing `tt <hit>%/<occ>%` is
load-bearing — `report.py` and `ttscan.py` parse it.

**Tooling caveat:** the data lives in `data/{shared,local}/ansturns/`, so
`WORDLE_SOLVER=ansturns python3 tools/report.py` reads it. But the *process* is
still named `optturns`, so the `tt*` tools — which attach by process name —
cannot find it under that name, and `run-sweep.sh`'s `pgrep -x optturns` guard
will also fire on a running answers-only sweep.

## All-words (`--answer-list` + `--optimal-only`)

`--answer-list FILE` replaces the ANSWER set — the thing the total is summed
over. Pointed at `guess.txt` it makes every legal word both a possible answer
and a legal guess:

> Minimise the **total guesses summed over all 12972 legal words**, every one of
> which is **both a possible answer and a legal guess**, subject to resolving
> every answer within `--depth` guesses.

```sh
# from math/
python3 build_patterns.py --full          # PREREQUISITE, ~18s, 168 MB
bash solver/run-allwords-sweep.sh
```

**It needs the SQUARE pattern matrix.** `--answer-list guess.txt` makes the
matrix 12972 x 12972, not 12972 x 2315, so `--patterns` must point at
`patterns_full.npy`. That is a separate file — the default the normal, hard and
answers-only sweeps read is left untouched. The shape check catches a mismatch.

`MAXA` is 13000 rather than 2315 to allow this. Sizing it up cannot change an
existing result: `LBTAB` is only read at `n <= NA` and the Zobrist values are
drawn for `a < NA`, so the first `NA` of them are identical whatever `MAXA` is —
which `validate.sh` reproducing all five totals confirms.

### `--optimal-only`: prove the winner, bound everyone else

Reports **the optimal opener only**, not a total per opener. A full sweep spends
nearly all its time proving exact totals for openers that were never going to
win; this proves the winner and merely bounds the rest.

Each opener has a **root lower bound** — `NA` plus `LBTAB[d-1][|P|]` for every
surviving partition `P` — computable in O(NA) with no search. The run screens all
openers by it, sorts ASCENDING, and walks them against a running incumbent:

1. **LB skip.** If an opener's LB exceeds the incumbent, skip it — and because
   the order is ascending, that proves every opener after it is worse too.
2. **Partition cutoff.** Within an opener, partitions are solved largest-first
   and abandoned as soon as `(solved so far + LB of the rest)` exceeds the
   incumbent.

**TIES SURVIVE.** Both tests are `> incumbent`, never `>=`. An opener whose true
total equals the incumbent always satisfies `partial + lbrest <= true total <=
bound`, so it is never cut, and every opener attaining the optimum is reported.

**The bound never enters `solve()`.** It applies only between the root's
partitions. Subproblem values are memoised and must stay exact — see the
exactness note at the top of `optturns.c` — so a beta inherited from a parent
would store a bound where an exact value belongs and poison every later query.
Cutting between root partitions changes nothing that is stored.

Resume re-seeds the incumbent from the CSV's best total, so a restarted run
prunes at full strength immediately instead of rediscovering the bound.

### The TT salt covers BOTH lists

`GSALT` is derived from the guess set AND the answer set, and is **zero only when
both are the defaults** — which keeps existing hashes bit-identical and existing
`tt.bin` snapshots valid. Both halves are load-bearing: a different guess set
gives the same candidate set a different optimum, and a different ANSWER set is
worse still, because the Zobrist values are indexed by ANSWER INDEX — index 7 is
simply a different word, so every key silently means something else. Without the
salt a foreign `tt.bin` returns confidently wrong values rather than missing.

### The cap is part of the objective here too

`--depth 6` over 12972 answers is a far stronger demand than over 2315, and
normal mode's "any opener can follow SALET's tree" argument establishes
feasibility for the **2315-answer** problem only — it says nothing about this
one. If no opener solves all 12972 words within 6, the run says so explicitly
rather than returning a number. Report any result as optimal **subject to a
6-guess guarantee**.

## Unguessable answers (`--phantom-final`) — the `ansall` cell

    bash solver/run-ansall-sweep.sh --depth 7                  # from math/
    bash solver/run-ansall-sweep.sh --depth 7 --optimal-only -k 50

The mirror image of the answers-only sweep: the **2315 answers are the only legal
guesses**, and **all 12972 words are possible answers**. It is the one
configuration where the answer set is the LARGER of the two, so 10657 answers can
never be played.

**The scoring rule.** An answer outside the guess list is charged *narrow the
candidate set down to that one word, then add one* — a PHANTOM final guess
standing in for the naming move. An answer inside the guess list is charged
normally: it must actually be played to be won. The two coincide arithmetically
at a singleton (`solve` returns 1 for `n == 1` either way), so the recursion needs
no new accounting. What needed guarding is the handful of shortcuts that assumed
`ANS2G[a] >= 0`:

* `n == 2` returns 3 ("guess one: 1 + 2") only while at least one of the pair is
  playable. When **neither** is, the pair has to be SPLIT and each half then costs
  its own phantom move: **4**. No guess can do better — one guess cannot resolve
  either candidate when neither can be named — so the first separating guess
  proves the value and there is nothing to search.
* The candidate-first guess orderings (the `d == 2` closed form, `--topk`'s
  below-cutoff top-up, `best_move`'s rescan) skip unplayable candidates.
* `best_move` takes whichever of a pair IS legal; at `n == 1` with none legal it
  returns -1 and `emit_tree` writes the phantom line itself.
* Depth normalisation (`d = min(d, n)`) still holds: any splitting guess drops the
  largest bucket to `n-1`, so `f(n) <= 1 + f(n-1) = n`, and a state with no
  splitting guess at all is INF at every depth.

**`--phantom-final` is opt-in and inert when answers ⊆ guesses.** It relaxes the
`answer %s not a legal guess` check — the guard that catches a mistyped
`--answer-list` — so it has to be asked for. It is deliberately **not** in the TT
salt, because it provably changes nothing when every answer is playable. Verified
both ways: `solver/validate.sh` still reproduces all five totals with identical
node counts, and the answers-only cell run WITH the flag still returns
`slate 7973`, the committed `ansturns` value.

**The cap binds and is part of the objective**, so `--depth` is required and every
depth gets its own CSV. Depth 7 is confirmed feasible (`slate` 54892 / 4.23158
under `--topk 30`, an upper bound); whether 6 is feasible is unresolved — the
counting bound does not rule it out, so only a real search settles it.

**Prerequisite: the SQUARE matrix** (`python3 build_patterns.py --full`). The
answer set is `guess.txt`, so the matrix must be 12972x12972 before
`--guess-list` compacts its rows down to the 2315.

**Trees carry the phantom.** `emit_tree` writes the answer itself as the final,
unplayable naming move, which keeps every line a complete replay ending
all-green. `tools/checktrees.py` now checks guess LEGALITY against the sweep's
guess list and exempts exactly that case — last move of the line, equal to the
answer, answer not in the guess list.

## `--topk K`: trade exactness for tractability

At every branching point, rank the legal guesses by **sum of squared bin sizes**
(ascending — the evenest split first) and search only the best `K`. `K = 0` is
unlimited and is the exact solver.

```sh
# from math/
bash solver/run-allwords-sweep.sh -k 50
./solver/optturns --opener salet --depth 6 --topk 100
```

**THE ROOT IS A BRANCHING POINT TOO.** `--topk` applies at EVERY branching point
including the first, so the sweep examines **K openers, not all 12972** — `-k 1`
checks exactly one starting word. The opener list is in sum-of-squares order and
is NOT re-sorted by lower bound: the selection rule and the visit order are the
same thing here. So the winner is the best of the **K openers examined**, not the
best of all NG, which is a weaker claim than the exact sweep makes and is exactly
what lets a small K finish.

(The exact path, `K = 0`, still ranks all NG openers by ascending root LB, where
that ordering is what makes the "everything after this is worse" exit sound.)

**THE RESULT IS AN UPPER BOUND, NOT AN OPTIMUM.** The search space is a strict
subset, so what comes back is a real, achievable strategy that may not be the
best one. It is weakly monotone in `K` — larger `K` can only match or improve the
total — and `K = 0` recovers exactness. Report as **"best found within top-K
branching"**, never as "the optimum".

Measured end-to-end on the 2315-answer problem (exact answer: SALET 7920):

| K | winner | total | avg | time |
|---|---|---|---|---|
| 1 | roate | 8204 | 3.54384 | 0.2s |
| 5 | soare | 8016 | 3.46263 | 1s |
| 20 | snare | 7981 | 3.44752 | 2s |
| 100 | **salet** | **7920** | **3.42117** | 18s |

K=100 recovers the true optimum in 18 seconds, against 5540 CPU-hours for the
exhaustive sweep. It FINDS it; it does not PROVE it.

Measured on SALET (2315 answers, depth 6; exact = 7920 in 16672 nodes):

| K | total | nodes |
|---|---|---|
| 1 | 8124 | 303 |
| 5 | 7962 | 480 |
| 20 | 7927 | 850 |
| 50 | 7927 | 1366 |
| 100 | **7920** | 1945 |
| 200 | 7920 | 4199 |

K=100 FINDS the optimum at ~1/9 the nodes — but finding is not proving, and the
value is still formally an upper bound.

**`INFEASIBLE` is weaker here too**: it means "not solvable within the depth cap
USING ONLY THESE K GUESSES PER NODE", which is not evidence about the problem.

**Candidates are added when `n <= K`** — every word still in `S` joins the
survivors, so the answer is always playable in a small state and a tight `K`
degrades the total gracefully instead of manufacturing spurious infeasibility.

**`K` is part of the TT salt.** Stored values under `--topk` are best-found-
within-K, not exact optima, so a table from one `K` read by another (or by the
exact solver) would return a confidently wrong value. Each `K` gets its own key
space, and the wrapper gives each `K` its own CSV and `tt.bin`.

### Depth is MEASURED, not assumed

Under `--optimal-only` the first opener (lowest root LB) is solved at an
ESCALATING cap starting from `--depth`; whatever cap it needed becomes the fixed
depth for every remaining opener, with `--depth` as the floor. This replaces
guessing whether 6 is satisfiable — under `--topk` an INFEASIBLE at a fixed 6
would mostly be an artifact of the restricted branching — and keeps every opener
under the SAME constraint, which a per-opener escalation would not.

## Other word lengths (`--length`, `optturns<L>`)

Wordle is 5 letters, but the same solver runs any length from 4 to 11 against the
**hello wordl** lists (`build_wordlists.py`; provenance and results in
`math/data/shared/LENGTHS.md`). These do NOT touch the Wordle problem: the
top-level `words/{guess,mystery}.txt` and `patterns.npy` are untouched, and
`validate.sh` still reproduces all five published totals.

```sh
# from math/
python3 build_wordlists.py                    # once, all lengths
python3 build_patterns.py --length 6          # per length -- SEPARATE matrix file
cd solver && sh build.sh 6                    # per length -- SEPARATE binary
bash solver/run-length-sweep.sh --length 6 --depth 5
```

**WORDLEN is compile-time, like HARD.** Every array bound derives from
`NPAT = 3**WORDLEN` (243 at 5 letters, 177147 at 11); as a literal those fold into
the addressing, as a runtime variable they would cost an indirection in the
innermost partition loop. So `sh build.sh 7` emits `optturns7`, and `--length 7`
merely asserts the binary matches and picks the right lists. `MAXG`/`MAXA` are
sized from the actual lists by `build.sh`.

Three things change with length beyond the array sizes:

| | 5 letters | 11 letters |
|---|---|---|
| `pat_t` (one pattern code) | `uint8_t` | `uint32_t` — uint16 from 6 |
| word buffer | `char[8]` | `char[16]` — from 8 |
| pattern-indexed scratch | 972 B, on the stack | 692 KB, so on the HEAP |

That last one is why `emit_tree`/`root_lb`/`solve_opener_bounded` call
`pat_scratch()` instead of declaring arrays: three `int[NPAT]` inside a RECURSIVE
function is fine at 243 and fatal at 177147. The dense `for (p = 0; p < NPAT; p++)`
loops were deliberately left alone — that loop order fixes the ORDER OF LINES in an
emitted tree, so sparsifying it would rewrite committed 5-letter trees.

### The cap is PINNED, and it is the objective

`run-length-sweep.sh` requires `--depth` and runs exactly that cap. A depth-4 pass
and a depth-5 pass are two different quantities, not two attempts at one — a
tighter cap can only raise the total. Each gets its own CSV for that reason:
seeding a depth-4 run's incumbent from a depth-5 total would cut every candidate
and report nothing found.

Pinning is what keeps `depth == depth_floor`, which is what keeps the per-opener
LB skip live. In normal mode `--depth-max` defaults to `--depth`, and the
escalation probe is skipped entirely when they are equal — without that skip, an
infeasible FIRST opener would abort the whole run at a pinned cap.

### `--order ssq` vs `--order lb` vs `--order bisect`

All three examine every opener, so all three are exact and give IDENTICAL totals;
only the visit order differs, and with it what a STOPPED run is worth and how
early the incumbent starts pruning.

- `lb` — ascending root lower bound. Buys one extra thing: when an opener's bound
  exceeds the incumbent, every opener AFTER it is worse too, so the tail is free.
  **`--optimal-only` only** — the plain `--sweep` has no such walk, and says so
  rather than silently ignoring the flag.
- `ssq` — ascending split score, the evenest splitters first. **The default.** No
  tail proof, but it front-loads the openers that can actually win. In `wturns`
  the score is the WEIGHTED one, so the flag name is a misnomer there.
- `bisect` — the `ssq` sort with the dispatch BISECTED (ends, median, quartiles,
  odd eighths), so a stopped run is a stratified sample of the whole difficulty
  range rather than a prefix of the easy end. **Opt-in, and only the hard-mode
  sweep asks for it.** It costs real throughput — the SECOND opener dispatched is
  the worst-partitioned word in the list (`immix`) — so it is worth having only
  while somebody is reading the partial distribution as the run goes. Refused
  alongside `--topk`, which wants the K best rather than a spread.

**It was not always opt-in, and that is the reason this section is explicit.**
From 2026-08-26 the bisection was hardcoded into both `sweep_order()` call sites
for the hard sweep's benefit, so every other sweep silently paid for it while
this section, `run-wturns-sweep.sh` and `run-length-sweep.sh` all described
ascending order. Totals were never affected; the claim about what a halted run
holds was. `tools/checkorder.py` now gates the whole thing — including that the
DEFAULT is not the bisection.

Every run states its own order in the log (`order: NAME`, beside `threads:`), and
`inflight.py` / `passes.py` read it: they reproduce the dispatch to name which
opener each thread is on, so an assumed order would name the WRONG WORDS rather
than fail. A log without that line predates the flag and was bisected.

**Why `ssq` is the wrapper's default.** The tail proof is only worth having if the
bound fires, and it does not: it is a counting bound running 8–14% under the true
optimum, so nearly every opener bounds below the incumbent. Measured at length 6:
**0 skips in 3596 openers.**

Worse, in the regime that matters the bound is not even a proxy for split quality.
With `d-1` guesses left and every bucket at or under `1 + BRANCH`, each bucket
costs `2n - 1`, the `Σ n` term is a constant, and the whole bound collapses to

    root LB  ==  3*NA  -  2*(opener is itself an answer)  -  (number of bins)

— exact for every opener in that regime, and all of the LB top-200 are in it. So
ascending-LB order is **descending BIN COUNT**, blind to how the mass is spread.
At length 6 `satire` (405 bins, biggest bucket 210) outranks `salter` (395 bins,
biggest bucket 151) despite splitting far less evenly. Sum of squares measures
exactly what the bound discards.

### Stopping early

Ctrl-C is safe and expected: the CSV is flushed per improvement, so every opener
that ever held the lead is on disk, and re-running resumes from it. What a stopped
run does NOT give you is a proof — the leader is "best of those examined, in a
heuristic order". Record it that way; `LENGTHS.md` marks such rows PROVISIONAL.

**`--optimal-only` does not emit trees.** `write_tree` is called only from the
single-opener and plain `--sweep` paths, so `--trees` under `--optimal-only`
creates an empty directory. Getting the winner's tree currently means a follow-up
`--opener <winner> --trees <dir>` run at the same depth.

## Singleton rankings (`pairsplit --metric singles`, `run-singles.sh`)

A different question from everything above, and it does **not** run the solver: a
feedback pattern is a **singleton** when exactly one answer produces it, so seeing
it names the answer outright. This ranks openers by how many they have.

```sh
# from math/
bash solver/run-singles.sh              # words + pairs
bash solver/run-singles.sh words        # 12972 single words   (~0.1s)
bash solver/run-singles.sh pairs        # 84129906 blind pairs (~22s)
bash solver/run-singles.sh triples      # extend the top pairs (~11 min)
bash solver/run-singles.sh all          # all three
bash solver/run-singles.sh triples --pairs-top 20000

bash solver/run-singles.sh all --answers                  # answer words only
bash solver/run-singles.sh pairs   --answers --exhaustive # ~1s
bash solver/run-singles.sh triples --answers --exhaustive # ~40-45 min
```

**`--answers` restricts which words may OPEN** to the 2315 answers — the same
restriction `--guess-list mystery.txt` applies to the solver — and writes to its
own `*_answers.csv` files, never over the unrestricted ones. The answer set is
unchanged, so the counts mean the same thing; there are just
C(2315, 2) = 2,678,455 pairs instead of 84M, which the pair stage clears in about
a second.

**`--disjoint`** keeps only openers whose words share no letter and repeat none —
10 distinct letters for a pair, 15 for a triple. 8322 of the 12972 guesses
qualify, forming 5,020,842 disjoint pairs (6% of 84M) and roughly 139M disjoint
triples against 3.6e11 unrestricted, which is what makes an exhaustive triple
sweep over the *full* guess list feasible at all. The result is the best
*15-distinct-letter* triple — a smaller claim than the best triple, since nothing
shows the unrestricted optimum is disjoint. Composes with `--answers`.

**Every parent width gets its own triple file**, the same rule the all-words
sweep applies to its `-k` values and for the same reason: the width decides which
triples were reachable, so two widths are different searches. A 1000-parent run
writes `triple_singletons_p1000.csv`, an exhaustive one writes
`triple_singletons_exhaustive.csv`. A narrow rerun therefore cannot quietly
replace a wide result with a weaker one that looks identical from the outside.

**Every run writes a `<out>.meta` sidecar** recording candidates scored, rows
written, and whether the two match. That cannot be recomputed from the inputs —
`--disjoint` and the canonical-parent filter drop candidates by a rule, not a
count — so without it a truncated ranking is indistinguishable from a complete
one. `--exhaustive` reads it and refuses a truncated parent file.

**`--answers --exhaustive` makes the triple stage a PROOF, not a screen.** It
feeds *every* answer pair to the extension, so all
C(2315, 3) = 2,067,969,935 answer triples are reached and the head of
`triple_singletons_answers.csv` is the true maximum. This is the one
configuration here where the greedy caveat does not apply. The full parent list
is ~70 MB, so it goes to `data/local/`; only the triple ranking is committed.

Writes `guess_singletons.csv`, `pair_singletons.csv` and
`triple_singletons.csv` under `data/shared/singletons/`, log in
`data/local/singletons/`. The word stage is `tools/singletons.py` (numpy); the
pair and triple stages are `pairsplit` with `--metric singles`, which counts
joint buckets of size 1 in the same pass that computes `ssq` — the flag picks the
sort key and the output columns, nothing else.

**Words and pairs are EXHAUSTIVE, unlike the ssq screen.** Every word and every
unordered pair is evaluated, so the head of those two files is the exact top of
the ranking, not a heuristic shortlist feeding a later exact stage. The `--top N`
cut only bounds what is written.

**Triples are NOT, and cannot be.** C(12972, 3) is 3.6e11, so the triple stage
extends only the top `--pairs-top` pairs by every third word — the same greedy
construction as the ssq triple screen, and it carries the same caveat: a triple
is reachable only if one of its three word *pairs* ranks inside the cut, so a
strong triple built from three individually mediocre pairs cannot be found at any
width. Report its head as "best of the triples screened". `minparent` is the best
rank among the triple's parent pairs in this ranking, so filtering one wide run
to `minparent <= N` reconstructs exactly what an N-pair run would have produced.

**It is not a claim about guesses-to-solve.** An opener can lead this ranking and
lose badly on total guesses — singling out many answers says nothing about how
the rest of the field splits. `clint`+`soare` tops the pair ranking at 642
singletons, which is a fact about singletons and nothing else.

**Two counts per row.** A word that is itself an answer always produces an
all-green bucket of size one — a singleton that tells you nothing you did not know
by winning. `singles` counts every size-1 bucket, `singles_nowin` excludes the
all-green ones; which is the right denominator is a modelling choice, so both are
emitted. Both stages count over the 2315 mystery answers;
`tools/singletons.py --full` counts over all 12972 words instead, which is a
different question.

## Sea of Greens (`greens`) — a DIFFERENT objective, not another sweep

`greens.c` is its own binary because the objective is a MAXIMUM with a hard
feasibility side-condition, not a minimum of a sum. It shares the loader, the
transposition table and the arena with `optturns` and none of the search. The
rules and the value function are stated in `math/greens.py`, which is also the
reference implementation the gate diffs it against.

```sh
# from math/
bash solver/run-greens.sh                      # screen every opener, report THE best
bash solver/run-greens.sh --opener salet       # one named opener, plus its tree
python3 tools/checkgreens.py                   # the GATE — run it after any change
```

**The objective, exactly.** Maximise the number of the 2315 answers won with NO
YELLOW TILE anywhere in the game, SUBJECT TO the strategy still winning every
one of them within `--depth` guesses. Lexicographic: the win is absolute, the
badge is maximised among strategies that never lose. Once a yellow appears the
badge is gone for that answer and the play is only required to finish the game,
so a yellow bucket is held to feasibility alone — which is much cheaper than the
badge value, since it early-exits on the first witness guess.

**The cap is the game.** `--depth 6` here is not an inherited tuning knob: it is
what "do not lose" means. Report the result as an optimum *subject to a 6-guess
guarantee*, never as an unconstrained maximum. Each depth is a different
quantity and gets its own CSV, with the depth in the filename.

**The badge rule is UNVERIFIED.** "Complete a puzzle with no yellow tiles" comes
from player reports read via web search, not from the NYT and not from a badge
screen of ours. Two clauses are inferred rather than observed: that a failed
game with no yellows does not earn it, and that a lucky 1/6 does. See the
provenance note in `math/greens.py`.

**Its `tt.bin` is not interchangeable with anything.** The salt is
unconditional, because `optturns` keys states the same way over the same words
while meaning something entirely different — a total of guesses against a count
of badges. A foreign snapshot fails verification instead of answering.

**How the screen prunes.** Openers are ordered by an upper bound and the first
whose bound falls below the incumbent proves the whole tail is worse, so the
bound's tightness is the entire pruning budget. The obvious bound — count the
answers that survive the opener yellow-free — is loose, because surviving ONE
guess is not surviving the game, and at a 6-guess cap the counting term is
saturated so nothing else tightens it. So the bound carries **one more ply**:
for each surviving bucket it asks how many of it the best SECOND guess could
keep alive, which is still sound (`badge(P,d) <= max over h of the answers of P
surviving h`) and typically a fraction of the first. It costs NG times the
surviving answers per opener, ~1e7 — a startup minute against searches that run
far longer — and it is computed for every opener up front, so it both ORDERS and
CUTS and the tail proof still holds. Watch the `root UB quartiles` line: the gap
between the top of that list and the first opener's actual badge count is how
much the screen can throw away.

Two hot loops are shaped by the same concern. `solve_badge` counting-sorts its
guesses by the integer bound rather than calling `qsort` — at n=3 the sort was
~0.9 ms against a pass-1 of 0.04 ms, so the sort *was* the search — and `feas`
tries only the evenest few splitters before falling back to a full sorted scan,
since a witness settles the question and the fallback keeps it exhaustive.
Neither can change an answer, and `checkgreens.py` compares against an
exhaustive scan of every opener to prove it.

**The CSV** is `word,badges,prob,depth,status,seconds`, where `status` is
`exact`, `cut` (bounded below the incumbent, never searched — a bound, not a
number) or `infeasible`. It is deliberately NOT readable by `tools/paths.py`:
badges and total guesses are incomparable quantities and must not land in one
report.

## Lingo (`run-lingo-sweep.sh`) — Wordle with the first letter given

Lingo (the game show) shows you the opening letter, then you guess whole words
that begin with it. We model one INDEPENDENT game per starting letter: for each
letter L, both the answer pool and the legal guesses are restricted to words
starting with L. Because every word shares position 0, that tile is always green
and the FEEDBACK FUNCTION IS WORDLE'S, UNCHANGED — the whole restriction lives in
the WORD LISTS, so there is **no new solver code**. It is three existing flags:

> For each starting letter L, minimise the TOTAL guesses summed over L's answers,
> where every guess — opener and follow-ups — is a legal guess STARTING WITH L,
> subject to resolving every answer within `--depth` guesses.

```sh
# from math/
python3 build_lingo_lists.py --length 5          # once: per-letter word lists
bash solver/run-lingo-sweep.sh --depth 5         # all letters
bash solver/run-lingo-sweep.sh --depth 5 --letter s
bash solver/run-lingo-sweep.sh --depth 5 --length 6   # needs 'sh build.sh 6'
bash solver/run-lingo-sweep.sh --depth 5 --answers-only   # guess ANSWER words only
python3 tools/lingo_report.py --length 5 --depth 5    # best opener per letter
```

**`--answers-only`** restricts the legal guesses to the letter's own answer words
(`--guess-list` points at `mystery.txt` instead of `guess.txt`), so every guess —
opener and follow-ups — must itself be a possible answer. It is the per-letter
analogue of the repo's answers-only (`ansturns`) sweep, and a DIFFERENT objective:
it reuses the SAME per-letter matrix (answers ⊆ guesses, so those rows already
exist) and changes only the guess list. Results land in a separate `_ans`
directory and the solver salts its TT on the guess set, so the two never mix; read
them with `tools/lingo_report.py … --answers-only`. NB the real game show lets you
guess any valid word, so this is an analytical variant, not Lingo's rule — and the
cap binds harder (fewer words to probe with), so `INFEASIBLE` openers are more
likely and are an expected result.

The wrapper drives the plain solver per letter with:

* `--guess-list len<L>/<letter>/guess.txt` — restricts follow-ups AND the swept
  openers to words starting with the letter (README "Answers-only" mechanics).
* `--answer-list len<L>/<letter>/mystery.txt` — makes the total run over just
  that letter's answers.
* `--patterns len<L>/<letter>.npy` — the matrix built for exactly those columns
  (`build_patterns.py --answer-list`), auto-built by the wrapper on first use.

**The answer pool is the CURATED list.** Length 5 uses the NYT lists (the 2315
mystery answers filtered by letter, guesses from the 12972), the same lists the
committed `patterns.npy` is built from. Length 6 has no NYT set, so it falls back
to the hello wordl 6-letter lists like the length sweeps — a different, not
comparable curation. A Lingo number describes THIS game on THESE lists.

**THE FEEDBACK RULE IS UNVERIFIED** against the real show: we assume Lingo's
marks are Wordle's green/yellow/grey with Wordle's duplicate-letter handling
(the user confirmed this modelling). A real Lingo board would settle it — the
same standing as the Absurdle and Sea-of-Greens rules.

**THE CAP IS PART OF THE OBJECTIVE.** Lingo gives five guesses (the given first
letter is not one), so `--depth 5` is the game; `--depth` is required and each
depth gets its own results directory. `INFEASIBLE` openers are an expected
result — report totals as optima SUBJECT TO the guarantee, never as unconstrained
minimum expected guesses. (Feasibility is not proven a priori here: normal-mode
Wordle's "follow SALET's tree" escape needs SALET, which does not start with most
letters, so an `INFEASIBLE` row is real data.)

Output per (length, depth, letter): `data/shared/lingo/len<L>_d<D>/<letter>_
totals.csv` committed (the product), trees/tt/log under `data/local/lingo/...`.
Resume is automatic per letter from the CSV. Per-letter matrices live in
`data/local/lingo/patterns/` (regenerable, gitignored).

**The gate is `python3 tools/checklingo.py`.** The one new artifact is the
per-letter matrix, so the load-bearing check diffs every column of it
BIT-IDENTICAL against the corresponding column of the shared length matrix
(which `checkpatterns.py` validates against `wordle.pattern`) — proving true
feedback AND correct column order. It also checks the lists are exactly the
filtered full lists, and replays any emitted trees length-generally (coverage,
legality, `wordle.pattern` agreement, one next guess per prefix, tree-sum vs
CSV). Run it alongside `solver/validate.sh` and `tools/checkpatterns.py`.

## Output format

Each tree line is a complete replay of one game:

```
aback 4 salet bbbbb crony bbbbb ... aback
<answer> <nguesses> <guess1> <pattern1> <guess2> <pattern2> ... <answer>
```

Patterns are `b`/`y`/`g`. Summing column 2 must equal the word's total — the
cheapest end-to-end correctness check there is.

## Saving / restoring the table

The table is a pure cache; losing it costs only speed. But a cold start is
expensive — the first words after a restart can take hours each.

```sh
# from math/ -- these paths are cwd-sensitive, cd first or they will not resolve
cd ~/projects/ballpark-figures/wordle/math

# snapshot a RUNNING solver (needs sudo for ptrace; ~16 GiB, a few minutes)
sudo env PYTHONPATH=$HOME/.local/lib/python3.10/site-packages \
  python3 tools/ttdump.py 29 data/local/optturns/tt2.bin

# verify BEFORE replacing the known-good snapshot -- must print PASS
python3 tools/ttverify.py data/local/optturns/tt2.bin 29

# ONLY if that printed PASS
sudo mv data/local/optturns/tt2.bin data/local/optturns/tt.bin
```

Then stop the solver with a plain `kill <pid>` (never `-9`) and commit the CSV.
If the verify does NOT print PASS, leave `tt.bin` alone and just kill: you lose
the newer table but keep a known-good one. That is the whole point of dumping to
`tt2.bin` first.

Snapshotting a live process is safe: entries carry `h1x = h1 XOR payload`, so
anything caught mid-write fails verification on lookup and is treated as a miss,
never a wrong value. Always dump to a new file and verify before replacing a
known-good one.

## Notes for whoever picks this up

- **Every opener can win within 6 guesses**, provably: play your opener, then
  follow SALET's optimal tree, which resolves any answer in ≤5 more. So the
  `INFEASIBLE` path exists but can never fire. **Normal mode only** — the
  follow-up is illegal in hard mode, where INFEASIBLE openers are expected.
- **Only SALET finishes within 5.** Even `crane` (6th best) needs a 6th guess
  on 3 answers. The paper's "never needs all six" is a property of the optimal
  opener, not of good play generally.
- **Cost and quality are uncorrelated.** `suers` took 38 h to solve with a
  wholly unremarkable value; many bad openers solve in seconds.
- **The `tt xx%/yy%` occupancy in the log under-reports.** Thread-local fill
  counters fold into the global only when a word *completes*, so while long
  words are in flight the real figure is higher — sometimes 3x. Use
  `tools/ttscan.py` against the live process for the truth.
- Saturating the table is survivable: measured ~9% slowdown at 3x
  oversubscription (see `tools/` benchmark history), because the 2-way buckets
  keep the expensive entries and evict cheap leaves.
