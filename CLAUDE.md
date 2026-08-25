# wordle video — specifics

wordle-only conventions. The shared cross-video rules (`bpkfigures/CLAUDE.md`)
and private operational notes (`dotclaude/CLAUDE.md`) load via the two imports
below. Those two names are **real files inside this repo** — gitignored copies,
refreshed at every session start by `dotclaude/hooks/refresh-claude-imports.py`.
They cannot be symlinks: a CLAUDE.md `@import` will not resolve to a target
outside the project directory, by any route. See `yahtzee/CLAUDE.md` "Config
loading" for the measurements and the full cross-machine history.

@CLAUDE.shared.md
@CLAUDE.private.md

> **Import canary — check this first.** If you cannot see the tokens
> `SHARED-RULES-LOADED` and `PRIVATE-RULES-LOADED` in your context, the imports
> above **silently failed** and you are missing every shared and private
> convention. The copies are machine-local and gitignored, so the usual cause is
> a repo where they were never created — a fresh clone that has not had
> `/sync-videos` run in it, so `.claude/settings.local.json` (and therefore the
> refreshing hook) does not exist yet. Recover by reading `bpkfigures/CLAUDE.md`
> and `dotclaude/CLAUDE.md` directly for this session, then regenerate the copies
> with `python3 ../../dotclaude/hooks/refresh-claude-imports.py .` and tell the
> user to run `/sync-videos`.
>
> Do **not** trust a hook that claims to inject the rules as context: a
> SessionStart hook emitting the full ~121KB gets capped by the harness, saved to
> a file, and replaced with a ~2KB preview — which contains
> `SHARED-RULES-LOADED` and so reads as success while almost everything is
> missing. The tokens only mean anything when they come from the imports.

## Script
- `animations/Script.md` is the video script. Scenes become
  `scenes/NN<name>.py`. (Fill in this video's script/scene conventions.)

## Math / data
- `math/data/` holds source data & pipeline outputs; `math/notebooks/` holds
  Jupyter exploration. NEW data files go here, NOT `animations/assets/` (that's
  render-time scene data caches + visuals).
- Split solver outputs by git status: `math/data/shared/<solver>/` is
  **committed** (final results/trees, meant to sync between machines);
  `math/data/local/<solver>/` is **gitignored** (resume checkpoints / memo
  pickles — regenerable, can be GBs). `math/data/local/` is in `.gitignore`.

## Solver (exact optimal turns per opener)
- **THE OBJECTIVE IS CONSTRAINED — say this precisely, never loosely.** The solver
  minimises TOTAL guesses over the 2315 answers **subject to resolving every answer
  within `--depth` (default 6)**. That is NOT the same as "minimum expected guesses":
  a strategy that spent a 7th guess on one answer to save two elsewhere is outside the
  search space entirely, and would never be found. So
  `math/data/shared/optturns/opener_totals.csv` holds **CONSTRAINED optima**, and must
  be described that way unless and until the cap is shown non-binding.
  - The README's "every opener can win within 6 by following SALET's tree" proves
    **FEASIBILITY only** — that the ≤6 strategy set is non-empty, hence no `INFEASIBLE`
    rows. It does NOT prove the unconstrained optimum lies inside that set. Do not
    repeat it as if it did (that error is why the § bound/cap rule exists in the shared
    CLAUDE.md).
  - **Whether the cap binds for the normal sweep is an OPEN QUESTION**, unresolved as of
    2026-08-23. Settling it needs all 12972 openers re-checked at a relaxed depth, not a
    spot check. Cheapest sound route discussed: a "certificate" run at `--depth 7` seeded
    with each opener's known `T6` as the incumbent, asking only "does anything beat this?"
    — a decision problem, so far cheaper than a cold re-solve. Unbuilt and unmeasured.
  - **`#define MAXD 7`** (`optturns.c`) sizes the per-depth arrays, so `--depth` cannot
    exceed 7 without raising it and rebuilding. Depth 7 may not be enough to be
    non-binding; a truly unconstrained run is `depth = n`, which the sizing can't express.
  - **In HARD mode the cap BINDS HARD** — `INFEASIBLE` rows are common (3 of the first 15
    openers), so those openers yield no number at all. Carrying `--depth 6` into hard mode
    was an unflagged modelling decision; if the goal is expected guesses, the cap needs
    revisiting before the hard results mean anything.
- `math/solver/` is the C solver computing the exact minimum expected turns for
  every one of the 12972 openers, plus each one's optimal tree. **Read
  `math/solver/README.md` first** — build, flags, output format, gotchas.
- The objective is an INTEGER (total guesses over all 2315 answers), so results
  are exact, not float-compared. Validate any solver change with
  `bash solver/validate.sh` from `math/`: SALET 7920, REAST 7923, TRACE/CRATE
  7926, SLATE 7928 (Bertsimas & Paskov Table 1, reproduced exactly).
- **The DEFAULT way to start the sweep is ATTACHED, in a terminal:
  `bash solver/run-sweep.sh` (from `math/`).** The user watches completions
  scroll live; output is tee'd so `sweep.log` gets every line too. Do NOT
  substitute a detached launch, and do NOT hand-roll the `optturns` command line
  -- both wrappers already carry the right flags, and a bare run that misses
  `sweep.log` makes `report.py`/`inflight.py` report the PREVIOUS run's numbers.
- `bash ~/bin/resume-jobs.sh` is the UNATTENDED path only: same flags, detached
  via `nohup`, wired to a Windows Scheduled Task so a forced Windows Update
  restart self-recovers. Watch it with `tail -F` on `sweep.log`.
- Both skip finished openers via the CSV and warm-start the table from `tt.bin`.
  Before stopping the solver deliberately, snapshot the table while it is still
  LIVE -- `ttdump.py`, then `ttverify.py` must print PASS, then swap it in; the
  full sequence is in `math/solver/README.md`. Ctrl-C/kill does NOT save it.
- Outputs follow the shared/local split: **`math/data/shared/optturns/opener_totals.csv`**
  is the committed result that syncs between machines;
  `math/data/local/optturns/` holds the regenerable bulk (`tt.bin`, `sweep.log`,
  `archive/`).
- **The emitted TREES are COMMITTED, under `math/data/shared/<solver>/trees/`** — the
  laptop runs no data generation, so it cannot regenerate them. As of 2026-08-24 these
  are **COPIES**: the running solvers still write to `math/data/local/<solver>/trees/`
  via their `--trees` flag (a live process's flag cannot be changed), so `local/` stays
  the WORKING location and `shared/` is a snapshot that has to be re-copied to pick up
  newly-finished openers. **Planned: reroute `--trees` at `shared/` once the regular
  sweep finishes and before hard mode switches to phase 2**, which collapses the two
  into one location and ends the duplication.
- **`paths.TREES` RESOLVES between the two locations** — it prefers
  `local/<solver>/trees/` whenever that actually holds trees, and falls back to
  `shared/<solver>/trees/`. So a sweep machine reads the LIVE set its solver is writing,
  while a machine with only the committed copies reads those. The precedence matters in
  that direction: preferring `shared/` would make this machine silently report on a stale
  snapshot. `WORDLE_TREES=<path>` overrides explicitly. Both tree readers
  (`checktrees.py`, `depths.py`) import the constant, so they follow it.
## Hard-mode solver (same sweep, hard-mode rules)
- **`optturns.c` builds TWO binaries** — `optturns` (normal) and `hardturns`
  (hard mode), via a compile-time `-DHARDMODE`. One source of truth, no runtime
  branch in either hot loop, and `hardturns` can be built while an `optturns`
  sweep is live (the kernel refuses to overwrite the running one). `sh build.sh`
  makes both.
- **Hard mode = the NYT rule**: greens must be repeated in place, a yellow
  letter must appear somewhere in the guess (the same square is legal), greys
  constrain nothing. The accumulated constraint is REAL EXTRA STATE — the
  candidate set `S` bounds it but does not determine it, so it is hashed into
  the TT key. **`INFEASIBLE` openers are expected here** (normal mode's "follow
  SALET's tree afterwards" escape is illegal in hard mode), so a `word,,,secs`
  CSV row is a result, not a bug.
- Data mirrors the normal sweep under its own name:
  **`math/data/shared/hardturns/opener_totals.csv`** committed, **`math/data/shared/hardturns/trees/`**
  committed (see the trees bullet above — currently copies), `math/data/local/hardturns/`
  (`tt.bin`, `sweep.log`) gitignored.
- **Launch it with `bash solver/run-hard-sweep.sh phase1|phase2`** (from `math/`),
  attached, same tee'd-log rules as `run-sweep.sh`. `phase1` shares the machine
  with a running `optturns` (nice'd, 12 threads, no table); `phase2` takes the
  whole machine (20 threads, `--tt-bits 29`, warm from `tt.bin`) and REFUSES to
  start while `optturns` still holds its 17.2 GB. Resume is automatic across the
  switch, so stopping phase 1 and starting phase 2 just continues.
- **`--tt-bits 0` disables memoisation entirely** — orders of magnitude slower
  than even a small table. `--tt-bits 24` is 0.5 GB; prefer the smallest table
  that fits over none.
- **Every tool takes `WORDLE_SOLVER=hardturns`** to read the hard sweep instead
  of the normal one (`report.py`, `lookup.py`, `inflight.py`, and the `tt*`
  tools, which also use it to pick which process to attach to). Default stays
  `optturns`, so existing invocations are unchanged.
- **`python3 math/tools/checktrees.py` verifies emitted trees independently** —
  replays every line against `wordle.pattern`, re-derives the hard-mode
  constraint from scratch, and checks answer coverage, guess counts, hint reuse
  and tree-sum-vs-CSV. Exits nonzero, so it works as a gate. Run it after any
  solver change, alongside `solver/validate.sh`.

- `math/tools/` holds the analysis scripts, all importing `paths.py` for
  locations. **`python3 math/tools/report.py`** is the standing status report
  (progress, best/worst, 0.01-bin histogram with percentiles, slowest solves,
  and the current run's in-flight openers); also `lookup.py` (rank named
  openers — its default word list is a set of POPULAR real-world openers, not
  anything the sweep tracks), `inflight.py` (which openers the running sweep
  picked up at t=0 and which are still going — `report.py` imports it),
  `vowels.py`, `depths.py` (tree depth + tree-vs-CSV check),
  `ttdump.py`/`ttverify.py`/`ttscan.py` (table snapshots).

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
