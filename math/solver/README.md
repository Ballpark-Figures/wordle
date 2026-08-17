# Exact optimal-turns solver

Computes, for **every one of the 12,972 legal Wordle openers**, the exact
minimum expected number of turns under optimal play — plus the full optimal
decision tree for each. Reproduces and extends Bertsimas & Paskov, *An Exact
and Interpretable Solution to Wordle*.

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
cd math/solver && sh build.sh          # gcc -O3 -march=native -fopenmp
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

Or just `bash ~/bin/resume-jobs.sh`, which wraps the sweep with the right flags
and is wired to a Windows Scheduled Task so a forced reboot self-recovers.

| flag | meaning |
|---|---|
| `--sweep` | all openers, best-heuristic-first, resumable |
| `--out FILE` | CSV: `word,total,expected,seconds`; flushed per word |
| `--trees DIR` | one `<word>.txt.gz` per opener, written before the CSV row |
| `--tt-bits N` | 2^N entries x 32 B. 29 = 17.2 GB, 28 = 8.6 GB |
| `--tt-load F` | warm-start the table from a snapshot |
| `--tt-save F` | dump the table on normal completion |
| `--threads N` | OpenMP threads |

**Resume is automatic**: rerunning reads the CSV and skips finished openers.
Killing mid-word is safe — the CSV row is written only after that word's tree
file is complete, so an interrupted word is simply redone.

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
# snapshot a RUNNING solver (needs sudo for ptrace)
sudo env PYTHONPATH=$HOME/.local/lib/python3.10/site-packages \
  python3 ../tools/ttdump.py 29 ../data/local/optturns/tt2.bin
python3 ../tools/ttverify.py ../data/local/optturns/tt2.bin 29   # must print PASS
sudo mv ../data/local/optturns/tt2.bin ../data/local/optturns/tt.bin
```

Snapshotting a live process is safe: entries carry `h1x = h1 XOR payload`, so
anything caught mid-write fails verification on lookup and is treated as a miss,
never a wrong value. Always dump to a new file and verify before replacing a
known-good one.

## Notes for whoever picks this up

- **Every opener can win within 6 guesses**, provably: play your opener, then
  follow SALET's optimal tree, which resolves any answer in ≤5 more. So the
  `INFEASIBLE` path exists but can never fire.
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
