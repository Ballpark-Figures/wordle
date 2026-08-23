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
| `phase1` | 12 | none (`--tt-bits 0`) | `nice -n 19` |
| `phase2` | 20 | `--tt-bits 29`, warm from `tt.bin` | normal |

`phase1` runs nice'd so the normal sweep keeps every core it actually wants and
hardturns only fills idle capacity, and takes no table by default because
optturns is holding ~17 GB. Both are overridable:

```sh
bash solver/run-hard-sweep.sh phase1 --threads 8 --tt-bits 24
```

**`--tt-bits 0` means literally no memoisation** — every recurrence of a deep
state is recomputed from scratch, which is orders of magnitude slower than even
a small table. `--tt-bits 24` costs 0.5 GB and buys most of it back. Prefer the
smallest table that fits over none at all.

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
