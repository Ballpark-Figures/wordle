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
  - **`#define MAXD`** (`optturns.c`) sizes the per-depth arrays and bounds `--depth`.
    **It is 20, not 7** — raised when hard mode began escalating its cap per opener
    (this bullet said 7 until 2026-08-25; do not re-derive the old limit from memory).
    So depth is NOT the binding constraint it once was: 7, 8 or more needs no rebuild.
    A truly unconstrained run is still `depth = n`, which the sizing can't express, so
    a cap remains part of the objective — but choosing a higher one is now free.
  - **`#define MAXA` is 13000, not 2315** — the ANSWER set is no longer always the
    2315 mystery words (`--answer-list` can make every legal guess an answer). Sizing
    it up cannot change an existing result: `LBTAB` is read only at `n <= NA` and the
    Zobrist values are drawn for `a < NA`, so the first `NA` are identical whatever
    `MAXA` is — confirmed by `validate.sh` still reproducing all five totals.
  - **In HARD mode the cap BINDS HARD** — `INFEASIBLE` rows are common (3 of the first 15
    openers), so those openers yield no number at all. Carrying `--depth 6` into hard mode
    was an unflagged modelling decision; if the goal is expected guesses, the cap needs
    revisiting before the hard results mean anything.
- `math/solver/` is the C solver computing the exact minimum expected turns for
  every one of the 12972 openers, plus each one's optimal tree. **Read
  `math/solver/README.md` first** — build, flags, output format, gotchas.
- **On a FRESH CLONE the solver needs TWO bootstrap steps before it runs at all, and
  BOTH fail confusingly (2026-08-25).** Neither is done by `/sync-videos`, and a clone
  looks complete without them because the committed results are all in `shared/`:
  1. **`python3 build_patterns.py` (from `math/`)** — regenerates
     `math/data/local/patterns/patterns.npy` (30 MB, ~2s). It lives under `local/`, so
     it is gitignored BY DESIGN and never arrives with a clone. Without it every solver
     invocation dies instantly with `cannot open data/local/patterns/patterns.npy` — and
     because `validate.sh` sends stderr to `/dev/null`, that surfaces as five silent
     `FAIL <word> = <none>` lines in under a second. **A validate.sh run that finishes
     in well under a second did not solve anything** — check for the missing patterns
     file before suspecting the solver.
  2. **`brew install libomp` on a Mac** — see the Brewfile / private notes. `build.sh`
     probes for OpenMP support and wires libomp's keg-only paths itself, so once it is
     installed the same script works unchanged on both machines.
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

## Feedback patterns: 243 encodings, but only 238 are POSSIBLE
- **`3^5 = 243` is the ENCODING space; only 238 patterns can ever occur.** The five
  impossible ones are **4 greens + 1 yellow** (one per position of the yellow): if four
  positions are green, the fifth letter is either in that position — green — or not in
  the word at all — grey. Yellow cannot happen there. `243 - 5 = 238`.
- `NPAT 243` and `ALL_GREEN 242` are both CORRECT and should not be "fixed": they are
  the base-3 encoding (`ggggg` = 242) and its array size. The 5 unreachable codes are
  just slots that never fill.
- **Where it actually matters is the LOWER BOUND.** `build_lb` uses `cap *= 242` and the
  file header says "at most 242^(k-1) words can be resolved at [level k]". The true
  branching is **237** (238 attainable minus the winning one). 242 OVER-states the
  branching, which UNDER-states the total, so the bound stays VALID — it is merely
  slacker than it needs to be. Using 237 is also valid and strictly tighter.
- **The gain is real but small: root LB for n=2315, d=6 goes 6701 to 6706 (+5, 0.07%).**
  Against a true optimum of 7920 the bound is ~14% loose either way, so this does NOT
  fix the pruning weakness in `--optimal-only` — do not expect it to.

## Answers-only + all-words sweeps (same solver, different word sets)
Two more variants of the SAME objective, both driven by flags on `optturns`
rather than new binaries. **`math/solver/README.md` has the full detail.**
- **Answers-only** — every guess (opener and follow-ups) must itself be one of the
  2315 answers: `bash solver/run-ans-sweep.sh`. `--guess-list mystery.txt` shrinks
  `NG`, and since every guess loop AND `--sweep` enumerate `0..NG-1`, that restricts
  the follow-ups and the swept openers in one move — no hot-loop change. Data in
  `math/data/{shared,local}/ansturns/`.
- **All-words** — every one of the 12972 legal words is BOTH answer and guess:
  `bash solver/run-allwords-sweep.sh`. Needs `python3 build_patterns.py --full`
  first (the SQUARE 12972x12972 matrix, ~18s/168 MB, a SEPARATE file — the default
  12972x2315 one is what the other three sweeps read). Data in
  `math/data/{shared,local}/allwords/`.
- **`--optimal-only` reports THE optimal opener, not a total per opener** (that is
  what makes all-words tractable). Openers are screened by a root lower bound —
  O(NA), no search — sorted ASCENDING, then walked against a running incumbent;
  an opener whose LB exceeds the incumbent is skipped, and because the order is
  ascending that proves the whole tail is worse. **Ties are kept** (every cut tests
  `> incumbent`, never `>=`). The bound NEVER enters `solve()` — those values are
  memoised and must stay exact.
- **THE CAP BINDS IN BOTH, AND IS PART OF THE OBJECTIVE.** Normal mode's
  "any opener can follow SALET's tree" argument is unavailable in answers-only
  (**SALET and REAST are not answer words**) and says nothing about the 12972-answer
  problem. `INFEASIBLE` is an expected result in both; report their numbers as
  optima **subject to a 6-guess guarantee**, never as minimum expected guesses.
- **The TT salt covers the guess set AND the answer set**, and is zero only when both
  are the defaults (so existing `tt.bin` stays valid). The answer half matters most:
  Zobrist values are indexed by ANSWER INDEX, so a different answer list makes every
  key silently mean something else — a foreign snapshot would return confidently
  wrong values rather than missing.
- **`WORDLE_SOLVER=ansturns`** reads the answers-only results. It is the one name
  that is NOT a binary (the process is still `optturns`), so the `tt*` tools, which
  attach by process name, cannot find it.
- **On macOS `sh build.sh` does NOT fail with `Text file busy` while a sweep runs**
  (the README describes Linux behaviour). The linker unlinks and recreates, so the
  live process keeps its old inode and is unaffected — but the safety net is absent.

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
