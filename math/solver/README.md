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
