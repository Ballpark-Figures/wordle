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
- **A PINNED CAP IS A DIFFERENT QUANTITY AND GETS ITS OWN FILES:
  `bash solver/run-sweep.sh --depth 5 --depth-max 5`** (added 2026-09-19, the
  hard wrapper's rule ported verbatim). `opener_totals_d<D>.csv` +
  `trees_d<D>`, read with `WORDLE_CSV=`/`WORDLE_TREES=`; depth 6 keeps the
  historic unsuffixed names, so every earlier run and resume is untouched.
  - **THE ROUTING IS LOAD-BEARING BECAUSE THE DEPTH-6 SWEEP IS FINISHED.**
    Resume reads the CSV to skip openers already done, so a pinned run pointed
    at `opener_totals.csv` would find all 12972 present, skip every one and
    exit having measured NOTHING — while its trees overwrote the committed
    depth-6 set. That is why the wrapper needed changing rather than the
    command line being hand-rolled.
  - **NORMAL MODE DOES NOT ESCALATE, so `--depth 5` alone already pins it** —
    `optturns.c`: `if (depthmax < 0) depthmax = HARD ? MAXD - 1 : depth;`.
    `--depth-max` is accepted and forwarded only so the command reads the same
    as the hard-mode one. **The BINARY needed no change**: the sweep loop's
    `INFEASIBLE` path has no hard-mode guard and writes the same `word,,,,secs`
    rows. INFEASIBLE is an expected result at a pinned cap.
  - **`--dry-run` resolves everything and stops**, before the solver and before
    the log header (which would move the run boundary `inflight.py` reads). Use
    it for every wrapper change here. The `mkdir` sits AFTER it — placed before,
    it silently created `trees_d5` under a "nothing written" banner.
  - The GNU-only `date -Is` is fixed here too (`%z`, matching
    `run-hard-sweep.sh`); `run-ans-sweep.sh` still carries the broken form.
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
## `mmturns` — MASTERMIND PEG FEEDBACK, a DIFFERENT GAME from every other cell
Same word lists (12972 guesses, 2315 answers), same objective shape, but the reply
to a guess is Mastermind's **(blacks, whites) PEG COUNTS** — how many letters are
right in place and how many are right in the wrong place — and NEVER which
positions those were. `solver/README.md` "Mastermind feedback (`mmturns`)" has the
detail. Run it with **`bash solver/run-mm-sweep.sh --depth D [-k K]`** (from `math/`).
- **NEVER put an `mmturns` total in a table with an `optturns` one.** Peg feedback is
  strictly COARSER — **20 outcomes against Wordle's 238** — so these are optima of two
  different GAMES, not two difficulty settings of one. Same trap as putting a capped
  optimum beside an expected-guesses one.
- **The feedback is a FUNCTION of the stored Wordle pattern, which is why there is no
  new feedback code**: `blacks` = the number of GREENS, `whites` = the number of
  YELLOWS. Wordle's yellow rule hands out exactly `min(guess_c, answer_c) − green_c`
  copies of each letter, and that sums to the white-peg count. So `-DMASTERMIND` is one
  remap of the loaded matrix (`mm_remap`) plus a narrowed `NPAT` — a THIRD compile-time
  mode of `optturns.c` beside `-DHARDMODE`, not a program of its own. VERIFIED inert for
  everything else: `solver/validate.sh` still reproduces all five totals with identical
  node counts (salet 16672).
- **20 codes, and the hole is `(4, 1)` — the ONLY impossible pair.** With four exact
  matches the two words differ in one position only, so the odd guess letter is matched
  against a different answer letter while every other copy of it is already consumed by
  an exact match; `whites` is forced to 0. `mm_code` enumerates blacks ascending, which
  puts the win `(5,0)` LAST, so `ALL_GREEN == NPAT − 1` keeps its meaning and nothing
  testing `p == ALL_GREEN` changes. **Do not "fix" `NPAT` to 21.**
- **`--depth` IS REQUIRED AND IT BINDS — the binary refuses to start without it.**
  optturns' default 6 is slack because 238 outcomes branch fast; at 20 they do not, so a
  depth-7 pass and a depth-9 pass are DIFFERENT QUANTITIES and get different CSVs.
  Carrying the inherited default would have made that choice silently. **The minimum
  feasible depth is an OPEN QUESTION** — the counting bound only gives `>= 4`, which is
  not restrictive, so settling it needs a real run. `INFEASIBLE` is an expected result.
- **`MASTERMIND` is in the TT salt UNCONDITIONALLY**, and it matters more here than
  anywhere else: the word lists are IDENTICAL, so a colour-feedback table and a
  peg-feedback table would agree on every key while meaning different games. An
  `optturns` `tt.bin` fails verification in `mmturns` instead of answering.
- **Hard mode and Mastermind cannot be combined (`#error`)** — hard mode's rule is stated
  in per-tile colours, which peg counts do not report.
- `-k 1` restricts the ROOT too, so it examines exactly ONE opener (best of 12972 by root
  sum of squared bins) and the total is an UPPER BOUND, best of the K examined — the same
  caveat `strguess`/`strturns` carry. `--optimal-only` emits NO TREES, so the winner's
  tree needs a follow-up `--opener <winner> --trees <dir>` at the same depth. Data under
  `math/data/{shared,local}/mmturns/`, one file set per (depth, K).
- **`--print-openers` prints EVERY opener `--optimal-only` examines, and the wrapper
  passes it.** An examined opener ends in one of SIX states and by default only three
  printed: `NEW BEST`, `TIED` and `INFEASIBLE` did; **solved-but-worse-than-incumbent**
  (writes a CSV row, printed nothing — why the k=10 run wrote 10 rows and showed a
  handful), **`CUT`** (no row, no line) and **`LB-SKIP`** (no row, no line) did not.
  `LB-SKIP` is the quietest and the one to know about: it `continue`s before the critical
  section, so an opener whose root bound exceeds the incumbent looks like one that was
  never examined, when its bound IS a result about it. **OFF by default**, so the
  `allwords`/`ansall` logs stay byte-identical; a no-op with a note outside
  `--optimal-only`, since the plain sweep already prints every opener.
  - **The gate asserts the COUNT, not the presence of a line** — `checkmastermind.py`
    runs the mini sweep at `-k 5` and fails unless all 5 openers are named. That is what
    caught `LB-SKIP`: the first version of the flag printed 1 of 5 and looked fine.
- **The `attainable` figure in the `branching:` line is MODE-SPECIFIC — do not re-derive
  it as `NPAT - WORDLEN`.** That subtraction is the base-3 COLOUR fact (5 of 243 codes are
  unreachable) and does not carry: peg feedback's one impossible pair `(4,1)` is already
  excluded when the codes are enumerated, so all 20 are attainable. Carrying the formula
  across made mmturns print "15 attainable of 20" beside a measured branching of 19 — a
  self-contradiction, and a textbook case of the "copying the shape of an existing
  program" tell in the shared rules. Diagnostic only; no result was affected.
- **`python3 tools/checkmastermind.py` is the GATE** (`--wide` adds the full matrix): the
  encoding against a Python mirror of `mm_code`, the blacks/whites identity against peg
  counts recomputed FROM THE STRINGS by the textbook rule (exhaustive on small alphabets,
  and all 30030180 real guess x answer pairs under `--wide`), that `(4,1)` is the only
  hole, and — the one that exercises the SEARCH — `mmturns` against a brute-force memoised
  solver on a miniature 24x16 `--data` directory at two depths, so both the solved and
  `INFEASIBLE` branches are compared. Run it alongside `solver/validate.sh` and
  `tools/checkpatterns.py`.

## Hard-mode solver (same sweep, hard-mode rules)
- **`optturns.c` builds THREE binaries** — `optturns` (normal), `hardturns`
  (hard mode) and `mmturns` (Mastermind peg feedback, see above), via compile-time
  `-DHARDMODE` / `-DMASTERMIND`. One source of truth, no runtime
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
  solver change, alongside `solver/validate.sh`. **It does NOT know the ULTRA
  rule** (see below) — it checks hard-mode legality, so it cannot fully validate
  an ultra tree.

## `--order` — the opener DISPATCH ORDER, and why bisection is OPT-IN
Three values, and they change **WHEN** a result lands, never **WHAT** it is —
every opener is examined either way and the totals are identical. What the order
decides is what a STOPPED run holds and how early the incumbent starts pruning.
- **`ssq` — the DEFAULT everywhere: ascending split score, best splitters first.**
  In `wturns` that score is the WEIGHTED one (`sum over LOSING bins of bin size x
  bin weight`, win excluded); elsewhere it is the sum of squared bin sizes. **The
  flag NAME is inherited and is wrong in the weighted binary** — it is not a sum
  of squares there — but the behaviour is as documented in the `wturns` section.
- **`lb` — ascending root lower bound. `--optimal-only` ONLY.** It is the one
  order under which the first opener bounding above the incumbent proves the
  whole TAIL is worse. On the plain `--sweep` there is no such walk, so `lb` is a
  no-op and the binary now SAYS SO rather than accepting it silently.
- **`bisect` — the ssq sort with a BISECTION dispatch** (ends, median, quartiles,
  odd eighths), so a stopped run is a stratified sample of the whole difficulty
  range instead of a prefix of the easy end. **That is the only thing it buys,
  and it is worth buying only while somebody is READING the partial distribution
  as the run goes.** It costs real time: the SECOND opener dispatched is the
  worst-partitioned word in the list (`immix` on the full guess list), so the
  incumbent driving every lower-bound cutoff arrives late.
- **IT IS OPT-IN AND MUST STAY OPT-IN — `run-hard-sweep.sh` is the ONLY wrapper
  that passes it** (user's call, 2026-09-09). It was written FOR the hard sweep,
  where the in-flight distribution is the thing being watched, and then hardcoded
  into BOTH `sweep_order()` call sites — so from 2026-08-26 every other sweep
  silently paid its cost, and `run-wturns-sweep.sh`, `run-length-sweep.sh` and
  the solver's own `optimal-only:` banner all went on describing ascending order
  while the code bisected. **Textbook § shared-helper failure: one caller's need
  became every caller's behaviour**, and it is the same shape as the `--tt-save`
  sweep. Do NOT hardcode `sweep_order(1)` again; pass the caller's own choice.
- **It is REFUSED alongside `--topk`**, which means the K BEST splitters —
  bisection would hand it a spread across the difficulty range instead. That
  exact combination shipped once and at `-k 2` examined the single WORST opener.
- **The run STATES its order in the log (`order: NAME`, beside `threads:`), and
  the name is the order that will actually RUN, not the flag as typed** (the two
  paths do not offer the same choice). `inflight.py` and `passes.py` READ that
  line, because they reproduce the dispatch to name which opener each thread is
  on — a divergence there reports the wrong WORDS rather than failing. **A log
  with no `order:` line predates the flag and WAS bisected**; both tools assume
  that and say so, and `passes.py` (which is entirely bisection levels) refuses a
  straight-sorted run instead of inventing levels for it.
- **`python3 math/tools/checkorder.py` is the GATE** — runs the mini `--data`
  problem single-threaded, so the CSV append order IS the dispatch order, and
  checks: the DEFAULT is not the bisection, `ssq` walks the re-derived sort,
  the C bisection matches `inflight.py`'s Python mirror index for index, the
  logged `order:` name matches the sequence actually produced, and — the free
  oracle — that all three orders give byte-identical totals for every opener and
  the same `--optimal-only` winner. **Coverage is asserted**: it FAILS if the
  orders never actually differed. Run it alongside `solver/validate.sh`.

## `ultraturns` — ULTRA HARD MODE, stricter than hard mode
- **`optturns.c` now builds a FOURTH binary, `ultraturns` (`-DULTRA`)** — a legal
  guess must itself be **CONSISTENT with every clue so far** (a word the answer
  could still be), not merely hard-mode-legal. So a word you guessed and missed is
  illegal thereafter, because its own greys/yellows rule it out. The legal set at
  any node is exactly the 12972 words still consistent. `sh build.sh` builds it.
- **The objective is `ultra >= hard >= normal`, THREE DIFFERENT GAMES.** A strictly
  smaller legal set can only raise the total. **Never put an `ultraturns` total in a
  table with a `hardturns` or `optturns` one** — same trap as a capped optimum beside
  an expected-guesses one.
- **The constraint is REAL EXTRA STATE, exactly as hard mode**, so it is hashed into
  the TT key (a DISTINCT ultra salt, so a foreign `tt.bin` fails verification). It
  rides as **per-position allowed-letter masks + per-letter `lo`/`hi` counts** — the
  `strspace.py` representation, which is **EXACT for FILTERING words** (the
  repeated-letter trap is about ENUMERATING patterns and does not arise; the real
  answers are still partitioned by the real pattern matrix). `cons_apply`/
  `cons_legal`/`cons_hash` have an `#if ULT` branch beside hard mode's; the search
  paths generalize hard mode's `HARD ?` to a shared **`USE_CONS` = `HARD || ULT`**
  macro (folds to 0 in normal/mm, so those binaries stay bit-identical —
  `validate.sh` still reproduces all five totals).
- **Candidates are always legal**, so the `n==1`/`n==2`/`d>n` shortcuts hold unchanged.
- **`--depth` is REQUIRED and it BINDS** (INFEASIBLE is expected, like hard mode), and
  it does NOT escalate — pinned to `--depth`, each depth its own CSV.
- **Run it with `bash solver/run-ultra-sweep.sh --depth D -k K`** (from `math/`),
  attached — mirrors `run-mm-sweep.sh` (`--optimal-only`, `--print-openers`, per-(depth,K)
  CSV `optimal_dD_kK.csv` under `data/{shared,local}/ultraturns/`, tt save/load). **topk
  is the intended mode** (the exact solver is slow — the legal set is large near the
  root), so the wrapper REQUIRES `-k`; the result is an UPPER BOUND, best of the K openers
  examined. No trees from the sweep — the winner's tree needs a follow-up
  `./solver/ultraturns --opener <winner> --depth D --topk K --trees <dir>`.
- **Like `mmturns`, it is NOT in `paths.py`** — its output is `optimal_*.csv`, read
  directly, and its tt snapshot is the binary's own `--tt-save`, so `WORDLE_SOLVER=
  ultraturns` is not a thing.
- **NO DEDICATED GATE YET.** The ultra legality property to check independently is that
  **every guess after the opener reproduces every prior clue** (`pattern(g_i,g_j)==p_i`
  for all `i<j`). A one-off replay verifier confirmed it on `salet`'s full tree (2315
  answers, all lines legal, tree summed to the reported total) when the mode shipped;
  building that into `checktrees.py` (or its own `checkultra.py`) is the open follow-up.

- `math/tools/` holds the analysis scripts, all importing `paths.py` for
  locations. **`python3 math/tools/report.py`** is the standing status report
  (progress, best/worst, 0.01-bin histogram with percentiles, slowest solves,
  and the current run's in-flight openers); also `lookup.py` (rank named
  openers — its default word list is a set of POPULAR real-world openers, not
  anything the sweep tracks), `inflight.py` (which openers the running sweep
  picked up at t=0 and which are still going — `report.py` imports it),
  `vowels.py`, `depths.py` (tree depth + tree-vs-CSV check),
  `ttdump.py`/`ttverify.py`/`ttscan.py` (table snapshots).

### Sweep status summaries (the standing format)
When the user asks for an update / report / status on a sweep, run
`python3 math/tools/report.py` (prefix `WORDLE_SOLVER=hardturns` for hard mode)
and write it up in THIS shape. The tool already emits the sections in order;
the write-up mirrors it. Both sweeps use the same format.

**Section order — the tail is what shows without scrolling, so the most-read
things come last.** Progress → slowest → histogram → remaining → worst →
in flight → pace.

1. **Progress** — `N / 12972 solved (X%)`, completions since the last update and
   over what span, how many remain, run elapsed, the solver's own ETA. Second
   line: `range lo .. hi`, spread in turns AND in total guesses. (Hard mode also
   has INFEASIBLE openers — count them via `load_infeasible()`; progress is
   solved + infeasible, and say so, since normal Wordle has none by construction.)
2. **Slowest to solve** — markdown table, 10 rows, `word | time | expected`.
   Note the solve time of anything that just landed even when it misses the list.
3. **Histogram** — the FULL 0.01-bin table verbatim in a code block, every bin
   from the best to the worst, every update. Do not trim it to the tail: the
   whole distribution is the point, and the user reads the shape. Follow it with
   a sentence naming which bins moved and by how much.
4. **Remaining** — the dispatch-order queue in a code block, 10 per row, with
   `<-- in flight` on the rows that hold threads. DROP this section once the
   queue fits inside the thread count (report.py suppresses it automatically).
5. **Worst words** — code block, **worst LAST** (ranks still count 1 = worst, so
   they read bottom-up). Mark new entries, say who dropped off, and report where
   the 10th-place CUTOFF moved.
6. **In flight** — every running opener with its current runtime, longest first.
7. **Pace** — the trailing-window table verbatim in a code block.

**Content rules, learned the hard way:**
- **Report measured values and DELTAS only.** What changed since the last update,
  by how much. No forecasts about what will move next, nothing about what is
  "likely final" or "won't hold".
- **Never extrapolate from the ETA or a pace window to bound an INDIVIDUAL word.**
  Throughput says nothing about how long one opener takes, and the sweep ends when
  the LAST word lands. (`uhuru` ran 64.4 h alone at the end of the normal sweep.)
- **Short pace windows are noise** — they swing by 3-8x between updates. Don't
  narrate a trend from them.
- **No letter-pattern theories** ("doubled letters are bad", "z words cluster")
  unless actually computed over the full result set. A top-ten list is ten points.
- **Lead with a one-line headline ONLY when something genuinely moved** — a new
  worst opener, a percentage milestone, a record solve. Otherwise open with
  Progress and let the numbers carry it.
- Exact TIES are real (the objective is an integer): call them out rather than
  letting them look like a rounding artifact.

### Auto-update on every completion
When the user asks for an update each time a word lands, do NOT poll and do NOT
set an interval — the sweep log is an event stream. Arm a persistent Monitor on
it and write a full summary on each event:

    Monitor(command="tail -f -n 0 <math>/data/local/<solver>/sweep.log",
            description="<solver> sweep completions",
            persistent=True, timeout_ms=3600000)

Why this works and what to know:
- **The line lands the instant a word finishes.** `optturns` calls `fflush(stdout)`
  right after each completion's printf (inside the same critical section that
  writes the CSV row), and `run-sweep.sh` tees stdout to the log — so there is no
  buffering lag and nothing to poll.
- **No grep filter.** The log contains ONLY completion lines and run headers, so
  every line is an event worth seeing. That also covers the two non-completion
  cases for free: the final `12972/12972` line, and a `resuming` header if the
  machine reboots and the Scheduled Task restarts the sweep.
- **`-n 0`** so it streams from the current end instead of replaying the file.
- **Several completions inside 200 ms batch into ONE notification.** Run the
  report on the event, not once per word — the report reflects all of them.
- **Silence is ambiguous.** `tail -f` on a dead writer looks exactly like a quiet
  stretch, so a long gap warrants checking `pgrep -x <solver>` rather than
  assuming nothing happened. (Late in a sweep a genuine 12 h gap is normal — one
  holdout can run for days.)
- **Each event costs a full summary**, so only arm this when asked, and note that
  N words remaining means up to N more reports. `TaskStop` ends the watch.

## Other word lengths (4-11) — a DIFFERENT problem, not an extension
- **The word lists are `hello wordl`'s, not the NYT's, and the two are NOT
  comparable.** `math/data/shared/words/hello/len<L>/{guess,mystery}.txt`, built by
  `math/build_wordlists.py` from [lynn/hello](https://github.com/lynn/hello) (MIT,
  pinned SHA). The top-level `words/{guess,mystery}.txt` (12972/2315) are untouched.
  hello's ANSWER list is a much looser curation — at 5 letters it is 3238 words, of
  which only 2077 are among the NYT 2315 — so **`load_words("mystery", 5)` is NOT the
  2315**. Inherited quirk worth knowing: hello's dictionary is North-American Scrabble
  (TWL/NWL) at every length EXCEPT 5, where it is Wordle's Collins-derived 12972.
- **Results live in `math/data/shared/LENGTHS.md`** with a PROVISIONAL/COMPLETE column.
  7-11 are complete and exact; 6 is provisional; 4 is unrun. **Never quote a PROVISIONAL
  row as an optimum** — it is "best of the first N openers examined, in a heuristic
  order". Say "probably the result".
- **One binary per length: `sh build.sh 7` emits `optturns7`.** `WORDLEN` is
  compile-time (like `HARD`) because every array bound derives from `NPAT = 3**WORDLEN`
  — 243 at 5 letters, 177147 at 11. `--length L` does not set the length; it asserts the
  binary matches and selects that length's lists + matrix. `sh build.sh` with no args
  still builds the 5-letter `optturns`/`hardturns` exactly as before.
- Per length you need THREE things, and each is a separate file: the word lists
  (`build_wordlists.py`), the matrix (`build_patterns.py --length L` -> `patterns_len<L>.npy`),
  and the binary. **The matrix dtype is NOT always uint8** — `3**L` outgrows it at L=6
  and uint16 at L=11 — and the solver rejects a mismatch rather than misreading it.
- **Run it with `bash solver/run-length-sweep.sh --length L --depth D` (from `math/`),
  attached, same tee'd-log rules as the other sweeps.** `--depth` is REQUIRED: the cap
  is pinned and IS the objective, so a depth-4 pass and a depth-5 pass are different
  quantities and get separate CSVs. Seeding one from the other's incumbent would cut
  every candidate and report nothing found.
- **`--order ssq` (the wrapper default) vs `--order lb`.** Both exact; only the visit
  order differs. `lb` alone makes an LB skip prove the whole TAIL is worse — but the
  bound never fires here (0 skips in 3596 openers at length 6), because in the regime
  that matters it collapses to `3*NA - 2*(opener is an answer) - (number of bins)` and
  is therefore blind to bin SIZES. `ssq` sorts by the evenness the bound discards, which
  is what matters when the run will be stopped early. Measured, not assumed.
- **`--optimal-only` emits NO TREES.** `write_tree` is only called from the
  single-opener and plain `--sweep` paths, so `--trees` here silently creates an empty
  directory. The winner's tree needs a follow-up `--opener <winner> --trees <dir>` run
  at the same depth. (Open gap as of 2026-08-27.)
- **`tt.bin` is 8.6 GB per length at `--tt-bits 28`, and is saved only on NORMAL
  completion** — a Ctrl-C loses it. The CSV is flushed per improvement and always
  survives.
- **`python3 tools/checkpatterns.py`** verifies the length-general pattern primitives,
  including a bit-identical regression of L=5 against the committed `patterns.npy`. Run
  it alongside `solver/validate.sh` after any change to `wordle.py`/`build_patterns.py`.
  `tools/orderdiag.py` compares the two visit orderings and asks what a part-finished
  run has not reached yet.

## Feedback patterns: 243 encodings, but only 238 are POSSIBLE
- **`3^5 = 243` is the ENCODING space; only 238 patterns can ever occur.** The five
  impossible ones are **4 greens + 1 yellow** (one per position of the yellow): if four
  positions are green, the fifth letter is either in that position — green — or not in
  the word at all — grey. Yellow cannot happen there. `243 - 5 = 238`.
- `NPAT 243` and `ALL_GREEN 242` are both CORRECT and should not be "fixed": they are
  the base-3 encoding (`ggggg` = 242) and its array size. The 5 unreachable codes are
  just slots that never fill.
- **Where it matters is the LOWER BOUND, and 237 is not the right number either.**
  `build_lb` used `cap *= 242`. 237 (238 attainable minus the win) is the theoretical
  ceiling, but **no real guess comes close**: MEASURED, the widest splitter manages
  **149** non-winning bins against the 2315 mystery answers and **211** against all
  12972 words (means 86 and 133). Over-stating branching under-states the bound, so 242
  was VALID, merely slack; the measured max is the tightest sound value.
- **`BRANCH` is now MEASURED at startup** (`measure_branching()`), not hardcoded — the
  right constant depends on the ANSWER SET, so any literal is wrong for one of them.
  Sound for sub-states too: for `S` within `A`, a guess's patterns on `S` are a subset
  of its patterns on `A`, so `bins(g,S) <= bins(g,A) <= BRANCH`.
- **MEASURED EFFECT, so nobody re-litigates it (2026-08-26):**
  - root LB (n=2315, d=6): 6701 to **6794**. True optimum 7920, so still ~14% loose.
  - ordinary solving: **NO effect at all** — validate.sh node counts bit-identical
    (salet 16672 before and after). Reason: `LBTAB[d][n] = 2n-1` for every `n <= BRANCH+1`,
    so the table only changes above n=150, and the search lives in deep states far
    smaller than that. Every hot-path lookup returns what it always did.
  - `--optimal-only`: **~17% faster** (1.8 to 2.1 openers/min; ETA 122.9h to 100.8h at
    6 threads). Real, because the root cutoff sums LBTAB over ROOT partition sizes,
    which are exactly the large bins that changed.
  - **It does NOT make the all-words sweep tractable.** For n=12972 the gain is
    38672 to 38703 (+31, 0.08%), because 211 is close to 242.
- **Why the ceiling is low:** the counting bound collapses to `LB = 1 + 2B + 3(n-1-B)`
  = `6943 - B` at n=2315, d=6 — `B^2` already exceeds `n` by level 3, so the branching
  constant only ever moves the DEPTH-2 term. Tightening `B` cannot attack the
  `3(n-1-B)` term that dominates; only a bound that constrains depth-3 capacity can.

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

## `ansall`: 2315 guesses, ALL 12972 words as answers (`--phantom-final`)
The one sweep whose ANSWER set is the LARGER of the two — the mirror image of
`ansturns`. `bash solver/run-ansall-sweep.sh --depth D` (from `math/`).
- **The scoring rule, stated exactly.** 10657 of the 12972 answers are not legal
  guesses, so they can never be PLAYED. Those are charged **narrow the candidates
  to that one word, then add one** — a PHANTOM final guess standing in for the
  naming move. The 2315 answers that ARE legal guesses are charged normally: they
  must actually be played to be won. The two rules coincide arithmetically at a
  singleton (`n == 1` returns 1 either way), which is why the recursion needs no
  new accounting — only a handful of `ANS2G[a] >= 0` shortcuts needed guarding.
- **`--phantom-final` is OPT-IN, and inert when answers ⊆ guesses.** It relaxes the
  `answer %s not a legal guess` check, which is the guard that catches a mistyped
  `--answer-list`, so it must be asked for. VERIFIED inert: with it on, the
  answers-only cell still returns `slate 7973`, the committed `ansturns` value, and
  `solver/validate.sh` still reproduces all five totals with identical node counts
  (salet 16672). It is deliberately NOT in the TT salt for that reason.
- **The one shortcut that genuinely changes is `n == 2`.** It returns 3 ("guess
  one: 1 + 2") only while at least one of the pair is playable. When NEITHER is,
  the pair must be SPLIT and each half then costs its own phantom move: **4**,
  proven by the first separating guess — there is nothing to search.
- **THE CAP BINDS AND IS PART OF THE OBJECTIVE, so `--depth` is REQUIRED and every
  depth gets its OWN CSV** (`opener_totals_d7.csv`, `optimal_d7_k50.csv`, …).
  Normal mode's "any opener can follow SALET's tree" escape is unavailable twice
  over here — the answer set is the 12972, and SALET is not even a legal guess.
  **Depth 7 is CONFIRMED feasible** (`slate` 54892 / 4.23158 under `--topk 30`, an
  upper bound). **Whether depth 6 is feasible is UNRESOLVED** — the counting bound
  does not rule it out, so settling it needs a real search, not an argument.
- Data under `math/data/{shared,local}/ansall/`. **`WORDLE_SOLVER=ansall`** reads
  it, but because the cap is in the filename it needs **`WORDLE_CSV=<path>`** too;
  like `ansturns` the name is not a binary, so the `tt*` tools cannot attach to it.
- **`checktrees.py` now verifies guess LEGALITY** against the sweep's guess list —
  new coverage for every sweep, and the load-bearing check here. A phantom final is
  the sole exemption: last move of the line, equal to the answer, answer not in the
  guess list. Verified on `slate`'s tree: 12972 answers covered once each, exactly
  2315 lines won by a real play and 10657 by a phantom, tree summing to the CSV.

## All 26^5 strings as a candidate set — `strspace.py` (CONSTRAINTS, not lists)
The strategy grid is (guess set) x (answer set) over A=2315, W=12972, S=26^5=11881376.
The four cells avoiding S are solvable by `optturns` flags; **the five involving S are
NOT reachable by any flag, `--topk` included** — `--topk` limits BRANCHING, and every
blocker is REPRESENTATION: candidate indices are `uint16_t`, guess indices are packed
into 20 bits (`(lb << 20) | g`, `& 0xFFFFF`), the per-thread arena is sized by
`MAXA`/`MAXG` (~1.9 GB/thread at S), and `PAT` is a dense NG x NA matrix (27.5 GB for
S x A, 154 GB for W x S, ~141 TB for S x S).
- **`math/strspace.py` is the answer-side fix: carry the candidate set as CONSTRAINTS.**
  Per-position allowed-letter masks + per-letter `lo`/`hi` counts — ~72 bytes whatever
  the candidate count, hashable as-is (so it doubles as a TT key), refined once per
  pattern to split, and SIZED by a DP over positions carrying only the CONSTRAINED
  letters' counts. Never enumerates. `alpha` and `length` are parameters so it can be
  checked exhaustively on a small alphabet.
- **THE REPEATED-LETTER TRAP, and why a spot check misses it.** Yellows are a PREFIX of
  a letter's non-green copies — `wordle.pattern` marks greens, then hands out the
  answer's spare copies LEFT TO RIGHT — so for one letter the non-green copies read
  yellow…yellow, grey…grey. A grey followed by a yellow of the SAME letter is
  UNREACHABLE, not merely empty. The count bounds cannot see this (both orders give
  identical `lo`/`hi`), so omitting the test makes `abb` report 8 non-empty patterns
  where 7 exist. **A distinct-letter guess like `salet` never exercises it** — the 26^5
  check passed while `abb` was broken.
- **`python3 tools/checkstrspace.py` is the gate.** Exhaustive at alpha=4/L=3 and
  alpha=3/L=4 (every guess, every reachable state to depth 2, ~682k states) against
  brute force AND against `wordle.pattern`; plus the real 26^5 space checked against an
  actual numpy filter. Run it alongside `solver/validate.sh` and `checkpatterns.py`.
- **ROOT SYMMETRY collapses the guess side, and it is a PROOF, not a heuristic.** With
  no constraints 26^5 is invariant under any alphabet permutation, so two guesses with
  the same POSITIONAL SHAPE (the set partition of positions induced by equal letters)
  have isomorphic partitions. Measured: all 11881376 root probes fall into **52 classes**
  (Bell(5)) giving just **7 distinct partition profiles** — 52.3 hours of naive Python
  root sweep down to 0.23 s. **This is exact only at the ROOT**; deeper, symmetry is
  broken by the letters already mentioned, though unmentioned letters stay
  interchangeable. Do not assume the full collapse below the root without re-deriving it.

## `strturns` — the W to S cell (12972 word guesses, all 26^5 strings as answers)
`solver/strturns.c`, built by `sh build.sh`. Carries the candidate set as CONSTRAINTS
(`strspace.py` is the reference implementation and the oracle), precomputes one ATOM per
(word, pattern), and counts by DP rather than enumerating. `tools/checkstrturns.py` diffs
its state arithmetic against `strspace.py` over a shared deterministic walk — run it and
`checkstrspace.py` after touching either.
- **RUN IT WITH `bash solver/run-strturns-sweep.sh --depth D` (from `math/`), NEVER a bare
  `./solver/strturns`.** The binary writes a CSV only when given `--out`, so a bare run
  prints its answer and saves NOTHING — a full day of multi-hour runs was lost that way
  (2026-09-01) because the wrapper did not exist and every handover hand-rolled the
  command line, which the shared CLAUDE.md forbids for exactly this reason. The binary now
  REFUSES to start without `--out` or an explicit `--no-out`. The wrapper sets `--out`,
  tees `sweep.log`, saves/reloads `tt.bin`, resumes from the CSV, and refuses to start a
  second copy. Data under `math/data/{shared,local}/strturns/`, one file set per
  (depth, K, mode) since each is a different objective.
- **DEPTH IS AT LEAST 9, and that is PUBLISHED, not a guess.** Li & Zhu, *Playing
  Mastermind with Wordle-like Feedback* (Amer. Math. Monthly 131(5) 2024,
  arXiv:2209.13147) define "Clear Mastermind" = Mastermind with EXACTLY Wordle's feedback
  (including the left-to-right yellow rule) over all k^n strings — the S→S cell verbatim —
  and prove `floor(k/n) + n - 1 <= F(k,n) <= floor(k/n) + n` when `n` does not divide `k`.
  At k=26, n=5 that gives **9 <= F(26,5) <= 10**. Their codebreaker may play ANY string, and
  restricting guesses to words can only make it worse, so **W→S below depth 9 is provably
  infeasible** — the depth 4/6/7/8 runs were all doomed before they started. F is WORST-CASE;
  the paper says NOTHING about averages, and its depth-optimal constructions (probe the
  alphabet in blocks) are terrible for the total. Table 1 also gives exact small values —
  F(3,2)=3, F(4,3)=3, F(5,3)=4, F(5,4)=F(6,4)=F(7,4)=4, F(6,5)…F(9,5)=5 — **which are the
  oracle for the unbuilt `ALPHA`/`L` verification gate.**
- **`--allow-unsolved` CHANGES THE OBJECTIVE and is opt-in for that reason.** By default,
  missing the `--depth` cap is fatal and the opener reports INFEASIBLE. Under the flag it
  becomes a COUNTED violation and the objective is LEXICOGRAPHIC: fewest unsolved answers
  first, then fewest guesses. **A total from such a run is NOT comparable with a default
  run or with any other cell** — it is "best coverage at this cap, cheapest way to get it".
  Every line printing it carries `unsolved=`, and the CSV gains an `unsolved` column, so
  the two can never be mistaken for each other.
  - Both halves ride in one `long long` as `unsolved * 1e9 + guesses`; guesses cannot
    reach 1e9 (at most `NSTR * MAXD`, ~3.8e8), so the fields never carry and plain integer
    add/compare give the lexicographic order for free.
  - **The COUNT is free** (it is in the packed value); only EXAMPLES need a tree walk, and
    that walk stops as soon as it has `--list-unsolved` of them (default 100). So listing
    is affordable even when millions are unsolved.
  - `avg-played` divides by ALL 11881376 answers, not the solved ones: every answer was
    charged for each guess actually played on its path, including ones that ran out of
    budget. Dividing by the solved count would attribute their guesses to somebody else.
- **`MAXD` is an ARRAY BOUND, not a modelling limit** — it sizes the per-thread arena,
  which is indexed BY DEPTH so recursion levels cannot clobber each other. ~0.23 MB per
  thread per level, so raising it is cheap; it is 32, not optturns' 20.
- **`--by-class` collapses guesses the STATE cannot distinguish** (needs `--topk K >= 1`).
  Letters are interchangeable when they share `(lo, hi)` and their allowed-position set;
  positions when their `allow` masks match. Each is an exact automorphism, so an orbit's
  guesses have ISOMORPHIC partitions — same bucket sizes, so same sum of squares and same
  lower bound. MEASURED collapse: **12972 to 5 classes at the root** (the integer
  partitions of 5 that any word realises) and **16 in the all-grey child of `abers`**.
  Greens/yellows/greys separate automatically — different `(lo, hi, positions)` triples.
  - **SOUND FOR PROFILES, NOT FOR VALUES.** The answer set is symmetric under letter
    permutation; **the WORD LIST is not**. Orbit-mates' children differ by a letter
    permutation, and a child's value depends on which words are legal guesses inside it.
    So a representative's VALUE never transfers to its class — hence the `--topk 0` refusal.
  - **At K = 1 it is not an approximation at all**, and that is its own oracle: the beam
    ties across a class and breaks on lowest index, so the representative IS what plain
    `--topk 1` picks. VERIFIED: `salet` d3 gives 23765539/11878555 both ways, 45s vs 5s.
    **Differential-test any change to it that way.** At K > 1 it differs deliberately —
    K distinct CLASSES rather than K arbitrary members of one tied class.
  - The canonical key packs L fields of 8 bits, so it is under 2^40 and always positive.
    **Never shift it right "for the sign bit"** — a `>> 1` drops the low bit of the last
    field and silently MERGES two classes. That shipped once; the comment now says so.
- **Sum of squares is BLIND WITHIN A SYMMETRY CLASS, by construction** — it is a function
  of the partition profile alone. At the root all 8322 five-distinct words are one class,
  so `-k 1` is not choosing `abers` on merit; it takes an arbitrary (lowest-index) member
  of the best class. That is the explanation for ties in the ranking, not a coincidence.
- **THE ROOT IS A BRANCHING POINT LIKE ANY OTHER — `--topk` restricts OPENERS too.**
  `-k 1` examines exactly ONE opener, the best by the same ascending sum-of-squares rule
  every other level uses; it does NOT sweep 12972. The winner is then the best of the K
  openers EXAMINED, a deliberately weaker claim than the exact sweep's, and it is what
  lets a small K finish. `solver/README.md` states this for `optturns`; strturns follows
  it. (Written down because strturns was built swept-everything and had to be corrected.)
- **ONE ranking rule, in `GuessKey` + `cmp_guesskey`, used by the per-node loop, the
  `d == 2` form AND the sweep.** `--topk` ranks by ascending sum of squared bin sizes
  (evenest split first); the exact search ranks by lower bound; ties ALWAYS break on the
  lowest guess index. Do not add a fourth ordering — extend this one.
  - **Never pack the key beside the guess index.** Doing so forced a `ss >> 12`, which
    made every guess TIE at any node under ~64 candidates — i.e. almost all of them —
    silently turning `--topk` into alphabetical order. Same bug shape as an
    `lb * MAXG + g` overflow in the sweep. Use the comparator.
- **`--topk` limits which guesses are RECURSED INTO, not which are PROFILED.** Pass 1
  scans all 12972 guesses x 243 patterns at EVERY node whatever `n` is, so a 3-candidate
  state costs the same ~10 ms as a big one. MEASURED at depth 19: ~95 nodes/s with almost
  every node holding 3-85 candidates. **A small-`n` path (enumerate and use direct pattern
  computation below a few hundred candidates) is the outstanding optimisation.**
- **INFEASIBLE under `--topk` says NOTHING about the cap** — a single bad guess returns INF
  for the whole tree. Worse here than elsewhere: the beam ranks by split EVENNESS while the
  binding constraint is letter COVERAGE (the all-grey branch survives as strings over the
  unguessed letters), so the beam systematically discards the guesses that make progress.
- **Depth 6 is IMPOSSIBLE for `salet`, provably and without running anything.** All-grey
  feedback leaves exactly the strings over the unguessed letters, `(26-|L|)**5`, so
  isolating one needs 25 letters seen — 5 pairwise letter-disjoint words including the
  opener. 432 words are disjoint from `salet` and **no 4 of them are mutually disjoint**
  (4 disjoint words would need 20 of the 21 remaining letters). So coverage caps at 24,
  leaving >= 2**5 = 32 candidates, needing a 6th guess to split and a 7th to name:
  **depth >= 7 for `salet`**. Measured chain confirms the mechanism: 21**5, 16**5, 11**5,
  6**5, 1.
- **THE SEARCH IS NOT YET VERIFIED.** The state arithmetic is checked exhaustively; the
  objective accounting, phantom rule and bounds are not. The gate to build is `ALPHA`/`L`
  as compile-time constants (like `WORDLEN` in optturns) so a build at alpha=4/length=3
  can be diffed against a brute-force Python solver. Until then treat every total it
  prints as provisional.

## Sea of Greens (`greens`) — the badge, and a LEXICOGRAPHIC objective
`math/greens.py` states the rule and the value function and IS the source of truth;
`solver/greens.c` is the solver. Run it with **`bash solver/run-greens.sh [--depth D]
[--opener W]`** (from `math/`), attached, same tee'd-log rules as the sweeps.
- **THE BADGE RULE IS UNVERIFIED, and say so with every number.** "Complete a puzzle
  with NO YELLOW TILE anywhere in the game" was read from player reports via web
  search (2026-09-03), not from the NYT and not from a badge screen of ours — the
  same standing as the Absurdle tie-break rules. Two clauses are INFERRED, not
  observed: that a FAILED game (X/6) with no yellows does not earn it, and that a
  lucky 1/6 does. **A single real badge would settle both.**
- **TWO OBJECTIVES, AND THEY ARE DIFFERENT QUANTITIES.** Never quote one as the other
  or put them in one table.
  - **`--may-lose` — THE BADGE QUESTION** (user's correction 2026-09-04): maximise the
    answers **WON WITHIN 6 WITH NO YELLOW**. ONE EVENT per answer — it counts iff the play both
    stays yellow-free AND finishes inside the cap. An answer that draws a yellow is
    simply LOST and **the strategy owes it nothing afterwards; it may abandon that
    game.** So yellow branches are never searched, no state is ever INFEASIBLE, and
    this is much the cheaper of the two.
  - **THE BINARY HAS NO DEFAULT OBJECTIVE — one of the two flags is REQUIRED**, and
    that is a scar. It had one, and the wrapper forwarded the flag only in the must-win
    case, letting the binary's default cover the other; when the default moved,
    `--may-lose` silently ran a MUST-WIN search and wrote it under a may-lose FILENAME.
    **Never let two places own one decision.** A defaulted objective is a domain ANSWER
    hiding in configuration, so refusing to run is the only safe default. The WRAPPER
    keeps a default (must-win) and forwards it explicitly — a default a human reads, not
    one a program falls back on. The gate passes it explicitly in both directions too.
  - **`--must-win` — the WRAPPER's default:** the same maximisation SUBJECT TO still winning EVERY
    answer within 6. A strictly smaller strategy space, so **its value is always <=
    `--may-lose`'s**. **IT IS THE DEFAULT ONLY BECAUSE RUNS WERE QUEUED AGAINST IT**
    (user, 2026-09-04) — not because it is the headline quantity, which it is not. A
    silent change of meaning under an unchanged command line is the worst thing a flag
    can do, which is why the polarity went this way and why the gate now passes the
    objective EXPLICITLY in both directions rather than leaning on the default.
  - **THE DISTINCTION IN ONE LINE:** `--may-lose` asks "how often can I win in 6 with all
    greens?"; the default asks "if I refuse to ever lose a game, how often can I win in 6
    with all greens?". **Only the first is the badge question.**
  - **HOW THIS WAS GOT WRONG, so it is not repeated:** the user's answer was "Max badge,
    requiring that we win. Once we get a yellow, we stop checking." That was read as
    "stop checking for badges but keep checking the win", and the win was made a hard
    constraint on every answer. It meant stop checking, FULL STOP. When an answer
    describes what happens after a failure, establish whether the failed cases are still
    CONSTRAINED or simply OUT OF SCOPE — the two give different numbers.
  - **THEY MEASURABLY DIFFER**, so neither is dead code: on the small case `moobs` at
    d=3 scores 4 plain against 3 must-win, and at d=2 every opener is plain-positive but
    must-win INFEASIBLE.
- **THE CAP IS THE GAME, not an inherited knob.** `--depth 6` IS clause 1. Each depth
  is still a different quantity and gets its own CSV (`best_opener_d6.csv`).
- **`if (d > n) d = n` DOES NOT TRANSFER from optturns, and that is the trap.** There,
  extra budget past `n` cannot help. Here it buys SAFE PROBES — words whose letters
  are all absent or already green — which can separate candidates that could
  otherwise only be separated by risking a yellow. So the badge value keeps rising
  past `d = n` and collapsing the key would silently answer a smaller question. The
  full porting audit (what transfers from `optturns.c` and what does not) is the
  header comment of `greens.c`; read it before changing anything there.
- **`greens` is a SEPARATE BINARY, like `antistall` and unlike `hardturns`.** A
  compile-time mode of `optturns.c` is for the same objective under different rules;
  this is a maximum with a hard feasibility side-condition, so it shares the loader,
  the TT and the arena and none of the search. `sh build.sh` builds it.
- **The TT salt is UNCONDITIONAL** — `optturns` keys the same states over the same
  words while meaning a total of guesses rather than a count of badges, so a foreign
  `tt.bin` must fail verification rather than answer.
- **The ask was THE BEST OPENER, so `--sweep` is a bounded SCREEN, not a per-opener
  table.** Openers are visited in descending badge upper bound (the answers landing in
  a guess's yellow-free buckets are the only ones that can still earn it), and the
  first whose bound falls below the incumbent proves the whole tail is worse. Ties
  survive (every cut is strict). A `cut` row is a BOUND, never a number — the CSV's
  `status` column says which, and `tools/paths.py` deliberately cannot read this file.
- **THE EXACT SWEEP IS NOT VIABLE, AND THE BOUND IS WHY (MEASURED 2026-09-03).** The
  screen orders openers by how many answers survive YELLOW-FREE, so the least
  informative word in the list sorts FIRST: **`bubby`** (3 distinct letters) leaves
  **1978 of 2315** answers yellow-free, **1338 of them in one all-grey bucket**. Its bound
  therefore exceeds any achievable badge count, so it can never be cut — and descending
  order means the walk spends its first hours on exactly the most expensive and least
  promising openers. **The second ply cannot fix this**: its maximiser is always a guess
  that learns nothing (for `bubby`'s all-grey bucket the best second guess is `bubby`
  AGAIN, keeping all 1338), so excluding no-op splits recovers 6 of 1978 — 0.3% on the
  worst openers, **0% on `crane`/`salet`/`raise`**. And no counting bound will do it
  either: that bucket admits up to **32 yellow-free bins**, so the geometric cap over 5
  guesses is ~1.08M against 1338 answers, vacuous by three orders of magnitude.
- **SO THE WORKING MODE IS `--topk` (user's call, 2026-09-03), RANKED BY SUM OF SQUARES.**
  `bash solver/run-greens.sh -k K`. Ascending sum of squared bin sizes, ties
  on the lowest guess index — the repo's one ranking rule, and it measures the SPLIT the
  survivor bound is blind to. State the claim precisely:
  - **Every value is ACHIEVABLE, so it is a LOWER bound on the true optimum** — the
    opposite direction from every other bound in this solver. It finds strategies; it
    never proves one best.
  - **The ROOT is beamed too**, so it is the best of the K openers EXAMINED, not of 12972.
    **ONE K GOVERNS BOTH** beam width and opener count, as in every other solver here. A
    separate opener-count flag was proposed and REJECTED (user, 2026-09-03) — do not
    re-add one.
  - **IT NEVER MAKES A STATE LOOK UNWINNABLE.** If no guess in the beam keeps everything
    winnable the scan continues PAST the beam until one does, and `feas()` is never beamed
    at all. **So clause 1 stays EXACT and only clause 2 is approximated** — an INFEASIBLE
    under `--topk` still means genuinely infeasible, unlike `strturns`, where it says
    nothing.
  - **TOPK is in the TT salt and in every filename.** Each K is a different strategy;
    a table or a CSV from one K read as another would be a confidently wrong value that
    is merely a lower bound.
  - **The beam is CHECKED, not trusted:** `checkgreens.py` mirrors the identical rule in
    `greens.py` and demands exact agreement at several K, that the beam never EXCEEDS the
    exact value and sometimes falls below it (or it is not restricting anything), and that
    K past the guess count reproduces the exact answer.
- **The two-ply bound (exact mode only; `--topk` skips it).** "Answers
  surviving the opener yellow-free" is loose — surviving one guess is not surviving the
  game, and at depth 6 the counting term is saturated, so nothing else tightens it. So
  for each surviving bucket the bound also asks what the best SECOND guess could keep
  alive (sound: `badge(P,d) <= max over h of the answers of P surviving h`). Computed
  for EVERY opener up front (~1 startup minute), so it both orders and cuts and the
  descending order still proves the whole tail is worse. **The `root UB quartiles` line
  against the first opener's real count is the pruning budget** — read it before
  deciding whether a run will finish.
- **The sorts were the search, so both are gone.** `solve_badge` COUNTING-SORTS its
  guesses by the integer bound (at n=3 a `qsort` of 12972 cost ~0.9 ms against a pass-1
  of 0.04 ms); `feas` tries only the evenest `FEAS_TRY` splitters before falling back to
  a full sorted scan, which is sound because a witness settles feasibility and the
  fallback stays exhaustive. Neither may change an answer — an explicit abort fires if
  the guess list is ever not descending, since a mis-sort would silently cut winners
  instead of failing.
- **IT IS SILENT BY CONSTRUCTION UNLESS TOLD NOT TO BE, so every phase narrates.** The
  walk only has something to SAY when the incumbent improves, and an improvement may
  never come — so silence is the normal state and says nothing about whether the solver
  is working. Three heartbeats cover it: the root screen counts openers as it bounds
  them, the serial probe narrates its root branches (yellow ones every 16, badge ones
  each) plus a node-count line every `--report` seconds inside the big all-grey branch,
  and the walk reports openers done / cut / infeasible with the current leader. **The
  root trace is single-threaded ONLY** (`TRACE_ROOT`, cleared before the parallel walk) —
  18 threads narrating one `d == ROOT_D` test would interleave into noise.
- **MEASURED 2026-09-03, first real launch:** the two-ply screen over all 12972 openers
  takes **21 s**, rejects nothing outright, and its bounds run **1972 / 1040 / 858 / 714
  / 328** (max, quartiles, min, of 2315). So the pruning budget is entirely a question of
  where the true optimum lands in that spread. The first opener had NOT finished after
  ~3 minutes.
- **`date -Is` IS GNU-ONLY and prints NOTHING on macOS**, so a wrapper header came out as
  `[] greens: ...`. `run-greens.sh` uses `date -u +%Y-%m-%dT%H:%M:%SZ` instead.
  `run-sweep.sh`, `run-hard-sweep.sh` and `run-ans-sweep.sh` still carry the broken form
  — harmless there unless `inflight.py` is asked to find a run boundary on this machine.
- **A RESUMED run rebuilds the tie list from the CSV**, or it would report only the ties
  found since restarting and read as a complete answer.
- **`python3 math/tools/checkgreens.py` is the GATE**, ~2s: the yellow predicate
  against tiles recomputed from the STRINGS by a second implementation; the badge
  count against `greens.py`'s slow string-based reference, exactly, at several depths
  and openers; **feasibility against `optturns`**, which answers the identical
  question and is validated against Bertsimas & Paskov; and the emitted tree replayed
  from the strings (coverage, the cap per answer, every pattern field, the last guess
  equal to the answer, ONE next guess per prefix so it is a strategy and not a
  per-answer fabrication, and the yellow-free line count equal to the reported
  badges). **It also scans EVERY opener exhaustively and demands the bounded screen
  find the same winner AND the same tie list** — the only check that covers the pruning,
  which is otherwise invisible to the `--opener` path — and it re-runs a sweep from a
  half-written CSV to pin the resume. It ends with a COVERAGE TALLY that FAILS if a
  yellow, a yellow-free line, an infeasible opener, a binding win-constraint or a set of
  tied openers never occurred. Run it alongside `solver/validate.sh` and
  `tools/checkpatterns.py`.
- **A SWEEP KEEPS THE BEST TREE**, written on every improvement to
  `shared/greens/trees_<settings>/<opener>.txt.gz` — so an interrupted run leaves the
  best STRATEGY and not merely its score, which was the gap `optturns --optimal-only`
  still has. Superseded openers keep their files, making the directory a record of how
  the incumbent improved; the final report names the winner. It is written OUTSIDE the
  critical section (per-thread arena, self-verifying table, one file per opener), so a
  slow tree walk cannot stall the other threads.
- **WHAT IS IN A TREE DEPENDS ON THE OBJECTIVE.** Under `--may-lose` it is the
  **badge-alive part only**: a yellow ends the branch, so the file holds exactly one
  line per BADGED answer and its line count IS the reported score. Under must-win it
  covers EVERY answer, post-yellow play included — which is what lets `checkgreens.py`
  verify the guarantee independently. **The tree directory is per (depth, K, objective)**
  for the same reason the CSV is: one opener's tree differs between them and a shared
  directory would have them clobbering each other.
- **THE CSV SELF-DESCRIBES, AND A RESUME REFUSES A FOREIGN ONE.** Its first line is
  `# greens objective=... topk=... depth=... guesses=... answers=...`, and a run whose
  stamp disagrees EXITS instead of resuming. **This is a scar**: every result from
  before the two objectives existed (2026-09-03 evening through 09-04 13:50, k1 to
  k13000 plus the live k10000) was written under a name that later came to mean the
  OTHER objective, so a `--may-lose` resume silently continued a MUST-WIN search and
  reported it as its own — under the correct may-lose banner, which is what made it
  invisible. Depth was in every row; the objective and K were in the PATH ALONE, and a
  filename cannot check itself. Those files are renamed `*_mustwin.csv` with the stamp
  backfilled. **A file with no stamp is REFUSED, not trusted.**
- **NOTHING SAVES THE TT ANY MORE.** `tt_save` sits at the end of `main`, so it fired
  only on NORMAL COMPLETION — exactly when the table is worthless, since a finished
  run's CSV marks every opener done and a resume then exits without reading it. The
  case that would pay, an interrupted run, saved nothing because Ctrl-C never reaches
  that line. Backwards, and 8.6 GB per settings combination (~160 GB) to be so. It was
  copied from `run-ans-sweep.sh`, where a snapshot IS load-bearing. `--tt-load` stays
  for a table made deliberately.
- **RUNS WITH DIFFERENT SETTINGS GO SIDE BY SIDE.** The wrapper guards on the OUTPUT
  FILE, not the process name: two runs appending to one CSV would each resume from it
  and read the other's rows as work already done, silently skipping openers neither
  solved. Different (depth, K, objective) means different CSV, table and log, so it is
  allowed and merely warns about the table GB and threads it adds. The check reads live
  COMMAND LINES, so it also catches a run started before the guard existed.
- Data under `math/data/{shared,local}/greens/`; trees in `shared/greens/trees/`.
  **Depth, K and the objective are all in the filename** — three different quantities
  must never share a file.
- **COST IS UNMEASURED as of 2026-09-03.** Price it with one named opener before
  launching the screen.

## Absurdle (adversarial Wordle) — OUR word lists, NOT Absurdle's
- **The host never commits to a word.** It holds a CANDIDATE SET (initially the answer
  list), buckets it by the feedback each remaining candidate would give for your guess,
  answers with the pattern of the **largest** bucket, and that bucket becomes the new
  candidate set. Ties between equal-sized buckets break by: fewest GREENS, then fewest
  YELLOWS, then the lowest number when the pattern is read left-to-right as digits
  (grey 0, yellow 1, green 2). Unlimited guesses, and no depth cap in the rules, so any
  cap we impose is OURS and is part of the objective.
  - **Consequence that drives everything: all-green loses every tie-break** (it is the
    most-green pattern), so the host hands you the win only when it has no choice. You
    win **iff** the candidate set is already down to ONE word and you guess that word.
  - **PROVENANCE: this rule is from qntm's Absurdle FAQ, read via search snippets, not
    from source** (Absurdle is closed-source) and NOT yet checked against the live game.
    Before any number ships, play a few openers on the real site and diff.
- **WE USE OUR OWN LISTS, AND THEY ARE NOT VERIFIED TO BE ABSURDLE'S — say so whenever
  a number is quoted.** Candidates are `math/data/shared/words/mystery.txt` (2315),
  guesses are `guess.txt` (12972): the ORIGINAL Wordle lists, the same ones every other
  sweep in this video uses. qntm describes Absurdle's lists as "very similar" to
  Wordle's, not identical, and the NYT edited Wordle's lists after both were built. So a
  sequence that wins here is **not guaranteed to win on absurdle.com**. Deliberate call
  by the user (2026-09-02): consistency with the rest of the video beats matching a list
  we cannot read.
- **It is DETERMINISTIC and fully known, so this is NOT an adversarial search.** The
  response is a pure function of (candidate set, guess), so a game is a single LINE of
  play, not a tree, and a "strategy" is just a sequence of guesses. None of the
  expected-turns machinery transfers — no averaging over 2315 answers, no minimax.
- **THE FLOOR IS 4 GUESSES, AND IT IS PROVED ON OUR LISTS (2026-09-02).** A win needs
  the set to be a SINGLETON before the naming guess, and one guess can shatter a set
  into singletons only if every candidate gets a DISTINCT pattern — so at most 238, the
  attainable-pattern count. The best opener leaves **168** candidates (`aesir`/`arise`/
  `raise`/`reais`/`serai`, all on the all-grey reply); only **277** of the 12972 openers
  leave 238 or fewer, and an exhaustive check of all 12972 second guesses against each of
  those 277 states finds none reaching a singleton. So a 3-guess win is impossible and 4
  is optimal — no longer "believed impossible", though still only for OUR lists.
  Witness: **`aesir yauld tench whoop`**, 2315 to 168 to 15 to 1 to win.
- **The pieces.** `math/absurdle.py` — host primitives (`respond`, `respond_all` ranks all
  12972 continuations in one bincount pass, `play`). `tools/checkabsurdle.py` — the GATE,
  fast path vs a brute-force reference plus the tie-break shortcuts; run it with
  `solver/validate.sh` and `tools/checkpatterns.py`. `tools/absurdle_shortest.py` — the
  floor proof plus one witness, 4 seconds end to end. `tools/absurdle_play.py` — a slow
  replay sharing NO code with the rest, and the thing to diff against a game played on
  the live site. Result in `math/data/shared/absurdle/`.
- **TIES ARE NOT ENUMERATED YET.** Stage 1 stops at the FIRST witness, in ascending
  resulting-size order, so `aesir yauld tench whoop` is one optimum, not the optimum.
  **Stage 2 is BUILT AND UNRUN**: `bash solver/run-absurdle-openers.sh` (from `math/`)
  asks, for every one of the 12972 openers, whether a 4-guess win exists after it — the
  yes rows are exactly the tied openers. Exact, not a screen: a win needs a singleton
  after three guesses, so only second guesses leaving 238 or fewer candidates can finish,
  and each such state is tested against all 12972 third guesses. Resumable per opener,
  and states are memoised by content, so anagram openers share a continuation. Stage 3
  (every tied SEQUENCE, not one witness each) is still outstanding, and is the expensive
  one — it is the same scan with the early exit removed.

## Adversarial Wordle — the custom wordlist + the weight hill-climb
The hangman video's adversarial search, ported. **A DIFFERENT OBJECTIVE from every
other solver in this repo**: expected guesses OUTRIGHT, with NO depth cap — never
comparable with an `optturns`/`hardturns`/`ansall` total, which are all optima
subject to a guarantee. Do not put the two in one table.
- **The word lists.** `math/build_freq_wordlist.py` ranks all 12972 guess words by
  `wordfreq` 3.1.1's "large" English list — the SAME package and list hangman's
  wordlist is built from, so a zipf means the same thing in both videos. Two committed
  outputs: `words/guess_by_freq.txt` (every word + its zipf, no cutoff, so the cutoff
  can move without regenerating) and **`words/custom.txt`, the candidate list: zipf
  >= 2.5 PLUS every NYT answer word regardless of frequency — 4282 words.** 2.5 is
  hangman's `DEFAULT_ZIPF`; the answer floor exists because 216 of the 2315 sit below
  it and the game itself can pick them. NB hangman applies that cutoff on top of a
  hunspell spellcheck and curated block/allow lists — **this list has NO such
  curation**, only the frequency bar and the answer floor.
- **`custom.txt` IS ONE MEMBER OF A FAMILY, and the whole family is now committed**
  (user's call, 2026-09-18): answers plus every guess word at or above a bar, at
  every multiple of 0.25 up to 2.50. **`build_freq_wordlist.py --from-ranked
  --cutoff C` (repeatable)** builds them from the COMMITTED `guess_by_freq.txt` —
  nothing is re-ranked, the ranking file is NOT rewritten, and `wordfreq` is never
  imported, so a new list cannot disagree with `custom.txt` about a word's zipf.
  They are ordinary word-list stems (`--candidates zipf200`, `--pool …`).
  - **The name is HUNDREDTHS, zero-padded to three** — `zipf025` is 0.25 and
    `zipf250` is 2.50 — because `custom25` reads as either. Derived by
    `list_name`, the one place that rule lives.
  - **`zipf250.txt` IS `custom.txt`, byte for byte** (verified), which is the free
    check that the family is built the same way as the original.
  - **THERE ARE SEVEN DISTINCT SETS, NOT TEN, and that is a fact about wordfreq.**
    The lowest NON-ZERO zipf in the whole 12972 is **1.01**, and 4046 words sit at
    exactly 0.00 (absent from wordfreq's "large" list) — nothing lies between. So
    every bar at or below 1.00 selects the same 8926 words, and `zipf025`,
    `zipf050`, `zipf075` and `zipf100` are identical files.
  - Sizes, with the answer words the bar would have dropped and kept anyway:

        zipf025/050/075/100   8926   (+0 answers rescued)
        zipf125               8121   (+2)
        zipf150               7272   (+5)
        zipf175               6381   (+17)
        zipf200               5597   (+40)
        zipf225               4866   (+89)
        zipf250 = custom      4282   (+216)
- **`math/topk.py` is the guesser the adversary plays against.** The candidate list
  carries non-normalised WEIGHTS; **all 12972 words are legal guesses**, candidate or
  not. At each node it ranks guesses by `sum over p != all-green of n_p * (W_p / W)`
  ascending — the expected number of candidate WORDS still alive — then recurses into
  the K best and keeps whichever actually minimises expected guesses. Ties break on
  lowest guess index.
  - **The guesser SEES THE WEIGHTS, and that is load-bearing.** Against a fixed
    weight-blind strategy the adversary's best move is to pile all weight on the single
    hardest word, and the search is degenerate. Same as hangman's greedy.
  - **A weight of 0 REMOVES a word from the game** — it is dropped before the search,
    so it is not counted in `n_p` either. That matters BECAUSE the ranking rule counts
    words: a zero-weight word left in the set would steer the guesser.
  - **`MAXD` (32) is a recursion guard, NOT a modelling cap.** It cannot bind while
    candidates are a subset of the guess list: a candidate guess always outranks a
    non-splitting one, so every child is strictly smaller.
  - **A lone survivor's index must be mapped through `ans2g` before it is used as a
    GUESS.** The candidate and guess lists are different, so the raw index reads the
    wrong pattern row — that bug hung the trace and is what `checktopk.py` caught.
- **`math/freq_search.py` is hangman's `freq_search.py`, phase for phase.** Per
  (letter, non-empty position-pattern) multiplier, start 1; a word's weight is the
  PRODUCT of its patterns' multipliers (`salet` -> `s____ _a___ __l__ ___e_ ____t`).
  Sequential Gauss-Seidel over ① x2 / /2 with a 0.125 floor and `0.125 <-> 0`,
  ② +/- powers of two from the top scale down to 1, ③ +/- 0.5 / 0.25 / 0.125. **The
  console lines and the per-change CSV match hangman's deliberately** — same
  `pattern ->xM (move) avg=` format, same `loop N: C changes`, same replay via
  `reconstruct`. Keep it that way. **281 knobs occur** on `custom.txt` (254 on the 2315).
- **RUN IT WITH `bash solver/run-freq-search.sh -k K` (from `math/`), never a bare
  `freq_search.py`** — the wrapper sets `--out` and tees the log, and the script
  REFUSES to start without `--out` or an explicit `--no-out`. Each K is a different
  guesser, so a different objective: its own CSV (`data/shared/freqsearch/topk<K>.csv`)
  and its own log. There is no resume; a re-run restarts from all-ones.
- **MEASURED COST (2026-09-02):** one k=1 objective evaluation over 4282 candidates x
  12972 guesses is **~0.9 s** (uniform weights; it gets cheaper as the adversary zeroes
  words). A phase loop is ~2 evaluations per knob, so ~9 min/loop at 281 knobs. Larger K
  is exponential in depth and has no transposition table yet.
- **NUMBA IS A REAL DEPENDENCY OF THIS CELL, AND ITS ABSENCE IS SILENT.** `topk.py`
  wraps the import in `try/except` and `TopKGame` sets `use_numba = use_numba and
  _HAVE_NUMBA`, so without numba every solve quietly runs `_ref_solve` — the pure-numpy
  REFERENCE path, which exists to be the differential ORACLE, not the fast one. Nothing
  warns. **MEASURED 2026-09-10**: a k=1 uniform evaluation over 4282 x 12972 took ~35 s
  on the reference path against the ~0.9 s documented with numba, and the `ca` language
  solve took 21.7 s. It also silently disables the sharpest check in
  `tools/checktopk.py`, which reports `FAIL numba available` and cannot diff the kernel
  against the reference at all.
  - **It is now pinned in the repo `requirements.lock` as `numba==0.67.0 ;
    python_version < "3.14"`** (plus `llvmlite==0.49.0` under the same marker). numpy
    2.5.1 already satisfies numba's `numpy<2.6`, so nothing was downgraded.
  - **THE MARKER IS NOT COSMETIC: there is NO stable numba wheel for Python 3.14**, which
    is what both Macs run — the only cp314 wheel is `0.63.0b1`, a beta pip will not take
    without `--pre`. So an unmarked pin would BREAK the Mac venv builds, and with the
    marker the Macs simply have no numba and silently get the reference path. **A slow
    `topk`/`lang_solve`/`freq_search` run on a Mac is this, not the problem.**
- **THE OBJECTIVE HAS TWO IMPLEMENTATIONS, AND `--objective wturns` PICKS THE
  FAST ONE** (added 2026-09-10). The guesser exists twice: `topk.py`'s numba
  kernels (`--objective topk`, the DEFAULT), and **`solver/wturns --topk K`**,
  whose ranking rule IS `topk.py`'s — ascending `sum over LOSING bins of (bin size
  x bin weight)`, ties on the lowest guess index. At K=1 neither minimises
  anything; both play the top-ranked guess. **They are the same guesser, not two
  approximations of one.**
  - **VERIFIED ON THE REAL PROBLEM, twice.** The k=1 hill-climb ends at
    **3.978171252747317** and `wturns --topk 1` on those weights reports
    **3.97817**; at k=10 uniform, `wturns` gives **3.623073** against
    `freq_search`'s own `start avg = 3.6231`.
  - **MEASURED SPEEDUP at k=10: ~370 s per evaluation to 12.0 s** (~31x). `topk.py`
    has no transposition table and runs on ONE core (CPU/wall measured 1.0);
    `wturns` has a table (92% hit rates observed) and 18 threads.
  - **THE PER-EVALUATION OVERHEAD IS CONSTANT IN K** — one sort of the live words
    plus one column permutation of the pattern matrix, **measured 1.35 s** for
    12972 x 4229. Noise beside a k>=2 evaluation, MORE than a k=1 evaluation
    (0.9 s) — which is exactly why `topk` stays the default and this is for the
    beam. Do not switch the default.
  - **THE CAP IS THE ONE REAL DIFFERENCE, and `--depth 6` is enough.**
    **FEASIBILITY DOES NOT DEPEND ON THE WEIGHTS** (user's correction, 2026-09-10):
    whether a strategy resolving every answer within D exists is a fact about the
    ANSWER SET and the GUESS SET; weights change what a line COSTS, never whether
    one exists, and zeroing a word only shrinks the answer set. So the cap needs no
    slack for the hill-climb to move weights around — and a looser cap is **not
    free**, it weakens the lower bound and prunes less: MEASURED at k=10, depth 6
    takes **12.0 s** against depth 9's **15.9 s**, for the identical 3.623073.
    A binding cap still **RAISES** — under `--topk` that may be the BEAM failing to
    find a line rather than none existing, but either way `topk.py` would have
    returned a number and this would not, so the two have parted company.
  - **`python3 math/tools/checkwturnsobjective.py` is the GATE**: it diffs the two
    EXACTLY, on integer totals, never on the CSV's 5-decimal `expected` (a
    hill-climb compares improvements far finer than 1e-5, so five decimals is not
    agreement). **The problem is SIZED so the beam bites** — `checkweighted.py`'s
    24x16 problem is solved optimally by the greedy, so every K gives the same
    number there and a pass would have been k=1 four times over; at 60 answers x
    600 guesses K genuinely moves the answer, and coverage FAILS if it did not.
- **The gates: `python3 math/tools/checktopk.py` and `math/tools/checkfreqsearch.py`.**
  The first diffs the numba kernel against a pure-numpy reference implementing the
  identical rules (k=1/2/3, exact agreement), checks the pattern slice against
  `wordle.pattern` recomputed from the strings, the cost accounting against an
  independent replay, every trace against the strings, and that zeroed words are
  identical to removed ones. The second checks the weight product from strings, a
  monotone log, and an exact CSV replay. Run both after any change to either file.

## `wturns` — WEIGHTED answers: what an OPTIMAL guesser spends against the weights
The exact companion to the adversarial hill-climb above. `math/freq_search.py` tunes
the weights against the GREEDY guesser (`topk.py` at k=1); this asks what an OPTIMAL
guesser spends against those same weights. **A FIFTH compile-time mode of
`optturns.c` (`-DWEIGHTED`)**, beside `hardturns`/`mmturns`/`ultraturns` — the same
search under a different COST, not a program of its own. `sh build.sh` builds it.
- **The objective, stated exactly:** minimise `sum over answers of w_a * (guesses
  spent on a)`, **SUBJECT TO resolving every answer within `--depth`**. Reported
  `expected` is that total over the summed weight. **`--depth` is REQUIRED and it
  BINDS** — a weighted optimum may deliberately spend a deeper line on a LIGHT answer
  to shorten a HEAVY one, so a depth-6 pass and a depth-7 pass are DIFFERENT
  QUANTITIES with different CSVs, and `INFEASIBLE` is an expected result. Report a
  total as an optimum **subject to a `<depth>`-guess guarantee**, never as minimum
  expected guesses.
- **THREE OBJECTIVES, THREE TABLES — never put them in one.** `optturns` minimises a
  COUNT over a different answer set; `topk.py` reports expected guesses OUTRIGHT with
  no cap; this is a capped WEIGHTED total. A `wturns` number and the greedy's 3.9782
  are comparable ONLY once the cap is shown non-binding (solve at 6, then 7, then 8
  and show the value stops moving) — **feasibility is not optimality**, and the fact
  that the greedy finishes every word within 6 proves only the former.
- **WHAT THE ANSWER MEANS.** The weights were tuned AGAINST THE GREEDY, so this
  measures how much the greedy leaves on the table. **It is NOT the value of the
  adversarial game** — that is a max-min needing the optimal guesser inside the
  hill-climb loop, and nothing computes it.
- **IT IS STILL AN INTEGER OBJECTIVE.** Weights must be DYADIC (`k / 2^m`) and are
  scaled by their common denominator on load, so every total is exact and no
  comparison is a float comparison. A non-dyadic weight is **REFUSED, not rounded** —
  rounding would silently change the objective. `freq_search`'s moves are x2, /2 and
  +/- powers of two down to 0.125, so its output is always dyadic (measured: max
  denominator 4096, scale 4096, total 13679255 for the k=1 run).
- **THE ANSWER LIST MUST BE SORTED BY WEIGHT DESCENDING, and the loader REFUSES one
  that is not.** This is load-bearing, not cosmetic: the lower bound assigns the
  shallowest levels to the heaviest answers, and it gets every bucket already in that
  order for free ONLY because the answer INDEX order is weight-descending and every
  partition in the solver is stable.
- **`LBTAB` DOES NOT TRANSFER, and its replacement is the one real piece of new
  math.** The uniform table is indexed by a COUNT; weighted, the bound depends on
  WHICH weights. `build_lvl` unrolls the same capacity schedule per RANK —
  `LVL[d][r]` is the level the r-th HEAVIEST answer gets — so a bucket's bound
  accumulates DURING the counting pass and the hot loop stays O(n). Sound by a
  rearrangement argument (among capacity-feasible depth assignments the cheapest puts
  the largest weights at the smallest depths). **The startup check asserts the uniform
  identity** `sum over r < n of LVL[d][r] == LBTAB[d][n]` at every depth, so a
  mis-built schedule fails at startup rather than by quietly cutting a real optimum.
- **The weight VECTOR is in the TT salt, unconditionally.** A state's value is a
  function of its candidate SET given fixed weights, so the set is still a sufficient
  key WITHIN a run — but two runs with different weights agree on every key while
  meaning different objectives. Same hazard MASTERMIND's salt exists for.
- **`--phantom-final`, `--pair-list` and `--triple-list` are REFUSED in weighted
  mode** — their cost accounting is still unweighted, so a wrong number under a
  right-looking name is the alternative.
- **THE OPENER ORDER IS THE WEIGHTED SPLIT SCORE.** `--order ssq` in this binary means
  ascending `sum over LOSING bins of (bin size x bin weight)` — the expected number of
  candidate WORDS still alive, which is **`topk.py`'s own ranking rule**, so the sweep
  is ordered by the same measure the guesser it is compared against uses. The WIN bin
  is EXCLUDED (unweighted `ssq` includes it), so an opener that could BE the answer is
  not penalised. Every opener is still examined and the result is still exact; the
  order only decides WHEN.
  - **IT ORDERS, IT DOES NOT PROVE.** Only the ascending LOWER-BOUND order
    (`--order lb`) lets the first opener bounding above the incumbent prove the whole
    TAIL is worse. Under `ssq` a stopped run holds **"the best of those examined so
    far"** — probably the optimum, never proved to be. Say it that way.
  - **THIS WAS NOT TRUE UNTIL 2026-09-09**: the shared `sweep_order()` bisected
    unconditionally, so the sweep dispatched {easiest, HARDEST, median, ...} while
    this bullet and the wrapper header both claimed ascending. Nothing was wrong
    with any TOTAL — the order cannot change one — but "a halted run probably
    already holds the optimum" was false, and the second opener examined was the
    worst splitter in the list. See § `--order`.
- **Run it with `bash solver/run-wturns-sweep.sh --weights <stem> --depth D`** (from
  `math/`), attached, tee'd log. `--opener W` (repeatable) prices ONE opener exactly
  instead of sweeping — much cheaper, exact for that opener, an upper bound on the
  optimum, and **the way to price the full sweep before launching it**.
  - **`-k K` is a BEAM, and it restricts the ROOT too** (added 2026-09-09), so it
    examines K OPENERS rather than 12972: the total is an **UPPER BOUND** and the
    winner is **the best of the K examined**, never the optimal opener. Same caveat
    every `--topk` sweep here carries. On the `--opener` path it beams only the
    branching BELOW the named opener, so it bounds that opener's price instead —
    the wrapper's warning says which, because the two are different claims.
  - **Each K is a different strategy and gets its own CSV, log and table**
    (`optimal_<stem>_d<D>_k<K>.csv`), exactly as each depth does. **K is in the TT
    salt**, so a beam's table can never be read by another K or by the exact solver
    — under `-k` the stored values are the best found within the restricted
    branching, NOT exact optima. `K=0` is the exact sweep and keeps the unsuffixed
    filenames, so runs made before the flag existed are untouched.
  - **`--dry-run` resolves everything and stops before the solver starts**, printing
    the files it WOULD write. Use it for every wrapper change: a partial CSV from a
    "quick check" is indistinguishable from a real result that died.
  - **THE UNWEIGHTED COMPARISON RUN IS THIS SAME BINARY WITH EVERY WEIGHT 1** —
    `python3 tools/freqweights.py --uniform data/shared/words/custom.txt --stem
    data/shared/freqsearch/uniform_custom`, then the ordinary wrapper. **It is NOT a
    different program and NOT `topk.py`**: with all weights equal the weighted
    objective IS the plain guess count, so this computes exactly what `optturns`
    computes over the same answer list — the identity `checkweighted.py` asserts,
    which makes the baseline a free cross-check on the weighted machinery too.
    - The uniform stem is the **4282-word `custom.txt`** (user's call, 2026-09-10),
      i.e. the frequency-cut list BEFORE the adversary zeroed 53 words — so its
      answer SET differs from `adv_topk1`'s 4229 and the two averages have
      different denominators. Comparable in the loose sense, not a strict A/B.
    - `freqweights.py` is still the ONLY place a weight stem is made, and both
      sources now go through one gated writer — verified by re-exporting
      `adv_topk1` and diffing it byte-for-byte against the committed stem.
  - **`--weights` takes a STEM, not a file:** `<stem>.txt` (the answer list) and
    `<stem>.weights`, both written together by **`python3 tools/freqweights.py --from
    <freqsearch csv> --stem <stem>`** so their ORDER cannot drift apart. The pattern
    matrix for those answer columns is built on first run and cached under
    `data/local/wturns/` (regenerable bulk, so it follows the shared/local split).
  - Zero-weight words are DROPPED by `freqweights.py`, matching `topk.py`: a
    zero-weight answer would cost nothing yet still branch the search. The k=1 run's
    4282 candidates become **4229** answers that way.
  - Data: `data/shared/wturns/optimal_<stem>_d<D>.csv` (sweep) or
    `openers_<stem>_d<D>.csv` (named openers); log + matrix + tt under
    `data/local/wturns/`. No `--tt-save` (see the note below).
  - **NO TREES FROM THE SWEEP** — `--optimal-only` never calls `write_tree`, so the
    winner's tree needs a follow-up `--opener <winner>` run at the SAME depth and
    weights. The wrapper's header carries the command.
- **A RESUMED `--optimal-only` RUN REBUILDS ITS TIE LIST FROM THE CSV** (fixed
  2026-09-10). It did not, and the failure was invisible in the worst way: a resume
  seeds the incumbent off disk, cuts every remaining opener against it, searches
  nothing — and then printed **`0 openers attain it`** for the very value the same
  line reported as best. The number was right and the LIST was a lie. MEASURED on a
  resumed `wturns -k 100`: 76 cut, 0 searched, best 49036860, 0 attaining. Same scar
  `greens.c` already carried; this path did not. The rebuild uses the in-run
  precedence (**shallower depth wins outright, then lower total**), or the restored
  ties could be those of a row the live search would not have led with. **Still NOT
  done: a resumed run does not adopt a shallower depth as its new cap** — inert
  wherever `--depth` is pinned, which is every `--optimal-only` sweep today.
  Gated by `tools/checkorder.py` (a resumed run must report the same tie list as a
  fresh one), and that check is MUTATION-TESTED — zeroing the rebuild reproduces the
  `0 openers` symptom exactly.
- **`python3 tools/checkweighted.py` is the GATE**, and its strongest check is free:
  **with every weight 1 the objective IS the guess count, so `wturns` must reproduce
  `optturns`** — measured, same totals AND same node counts (salet 16672, reast 29780),
  i.e. the same search tree and not merely the same answer; `--full` adds salet on the
  real lists at 7920. That cannot catch an error symmetric in the weights, so it also
  diffs the search against a brute-force weighted recursion (no bound, no ordering, no
  closed forms) on a 24x16 mini `--data` directory across four weight vectors and
  depths 2-5, replays the emitted tree from the STRINGS and checks its weighted sum
  against the reported total, and pins all six refusals. **Coverage is ASSERTED**: it
  FAILS unless the weighted optimum actually DIFFERED from the unweighted one, unless
  an `INFEASIBLE` actually occurred, and unless the `n == 2` and `d == 2` closed forms
  actually fired — a weighted check that never exercised the weights proves nothing.
  Run it alongside `solver/validate.sh` and `tools/checkpatterns.py`.
- **COST IS UNMEASURED for the full sweep.** Reference point: the uniform 2315-answer
  depth-6 problem runs a median 58s per opener, p99 7.8h, max 86h. This is 4229
  answers with a weaker bound. **Price one opener before launching the sweep.**

## `--kth-random` — the price of ONE random guess at turn k
The exact cost of a single blunder in an otherwise perfect game. Guesses 1..k-1
follow the committed OPTIMAL TREE of an opener (salet); guess k is a word drawn
UNIFORMLY FROM ALL 12972 LEGAL WORDS; from k+1 the exact search plays optimally
again. **Run it with `bash solver/run-kth-random.sh --depth 6 -k K` (or `--all`)**
from `math/`, attached, tee'd log; `--dry-run` resolves and stops.
- **A RUNTIME MODE OF `optturns`, NOT A NEW BINARY, and that is deliberate.** The
  objective is optturns' own — minimum total guesses subject to a depth cap — so
  the search, the TT, the lower bounds and the loader are all identical and a
  separate file would duplicate the ONE thing that must stay single-sourced.
  (`greens.c`/`antistall.c`/`eldrowmax.c` are separate because their SEARCH
  differs; this one's does not.) VERIFIED inert: `solver/validate.sh` still
  reproduces all five totals with identical node counts (salet 16672, reast 29780).
- **IT IS EXACT, NOT SAMPLED — that is why it is NOT a `wordlesim` strategy.**
  Every (answer, random word) pair is enumerated, 2315 x 12972 = **30030180** of
  them, so the result is an INTEGER total over that grid with no seed and no
  standard error, and a re-run reproduces the file. The user's call, 2026-09-10.
- **THE CAP IS COUNTED FROM THE START OF THE GAME** (user's call): the
  continuation gets `depth - k` further guesses, so the whole game fits in
  `--depth`. **`--depth` is REQUIRED**, each depth is its own quantity, and
  **INFEASIBLE IS AN EXPECTED RESULT** in a way it is not for the plain sweep — a
  random guess spends a turn without necessarily buying anything.
  - **An infeasible pair has NO OPTIMUM AT ALL, not a large one.** Those pairs are
    counted, EXCLUDED from the mean, and reported. So `mean` is "optimal expected
    guesses CONDITIONAL on the game being winnable within `--depth`"; `lb_mean`
    charges every infeasible pair `depth + 1` and is a SOUND LOWER BOUND on the
    unconditional mean. When `infeasible_pairs` is 0 they coincide. **Never quote
    `mean` as the expected guesses while `infeasible_pairs` is non-zero.**
  - Like every optturns-family total this is an optimum SUBJECT TO a guarantee, so
    it must never be tabled beside `wordlesim`/`multiwordle`/`foximax` means, which
    are expected guesses OUTRIGHT.
- **`--random-pool` SAYS WHAT "AT RANDOM" MEANS AND IS PART OF THE OBJECTIVE** —
  no default in the binary, a human-readable one in the wrapper, and it is in every
  filename. Two different experiments, both live (user's calls, 2026-09-10):
  - **`all`** — uniform over ALL 12972 legal words, consistent with the replies or
    not. k=1 is then the average over every possible starting word: **3.62590**.
  - **`compatible`** — uniform over the words still CONSISTENT with every reply,
    i.e. the candidate set itself, which at k=1 is all 2315 answer words. k=1 is
    then the same sweep averaged over just the answer words: **3.60730**.
  - **`compatible` IS ~830x CHEAPER at k=2** and seconds everywhere: the random
    guess ranges over the state (at most 221 words) rather than over 12972.
    MEASURED: k=2 at depth 6 takes **4.7 s** on 8 threads, against the k=2 `all`
    cell being the only expensive one in the whole grid.
  - **`compatible` MAKES THE OBJECTIVE RATIONAL, NOT INTEGER, and that is real.**
    Under `all` every answer draws from the same 12972 words, so the experiment is
    a RECTANGLE and the total is an integer over 2315 x 12972. Under `compatible`
    each answer draws from ITS OWN state and states differ in size, so answer `a`
    carries weight `1/|S_a|` and the mean is a sum of fractions with no small
    common denominator — MEASURED at k=2 the reduced fraction has a **27-digit**
    numerator and denominator. So the summary CSV's `mean` is a long double (good
    to ~1e-13), its integer grid columns are left **BLANK** under `compatible`
    rather than filled with a number of a different kind, and the per-state file
    `states_<opener>_d<D>_k<K>_<pool>.csv` — n, m, u, infeasible, all integers —
    is the EXACT record the value can be rebuilt from. `checkkthrandom.py` does
    exactly that rebuild and requires it to equal the reference's own Fraction.
  - **Under `all` the C computes the mean BOTH ways and refuses to report if they
    disagree** — the rectangle's exact integer total against the same weighted sum
    the rational path uses — so the cheap case is a standing check on the general
    one.
- **TWO ROWS ARE KNOWN IN ADVANCE AND ARE THE GATE'S ORACLES.**
  - **k=1 IS the opener sweep averaged**, over the opener set the POOL implies:
    all 12972 under `all` (mean **3.62590**, mean total 8393.9652), the 2315 answer
    words under `compatible` (mean **3.60730**). Quoting one for the other is the
    mistake gate check F exists to catch. So k=1 needs no tree and **REFUSES
    `--tree-file`**:
    the number is opener-independent, and accepting one would file it under an
    opener's name. Its CSV row records the opener as `-`.
    - **`--all` DELIBERATELY SKIPS k=1 and says so.** Computing it means solving
      all 12972 openers at depth 6 — that IS `run-sweep.sh`, which took this
      machine weeks — for a number already committed in `opener_totals.csv`. `-k 1`
      still runs it, and doing so is the end-to-end validation of the whole
      pipeline against 12972 committed totals, which is what `checkkthrandom.py`
      check F then compares. Do not let `--all` launch it by accident.
  - **k past the tree's own depth reproduces the opener itself.** salet's tree is
    depth 5, so k>=6 leaves no live game to spoil: total = 7920 x 12972, mean
    **3.42117**. Instant, and it exercises the real tree reader.
- **WHICH TREE MATTERS AT k>=3 — the quantity is tied to ONE optimal tree.** At
  k=2 the states are the opener's own partition and nothing else can vary. Deeper,
  they are the nodes of one optimal tree, and **an optimal tree is NOT UNIQUE**. So
  the tree is an explicit INPUT read from the committed artifact rather than
  re-derived: a fresh `best_move()` walk consults the TT and can legitimately
  return a different, equally optimal guess, which would make the answer depend on
  search history. The wrapper logs the tree path and its sha.
- **THE TREE READER CHECKS ITSELF, ALWAYS, three ways** — a misread prefix gives a
  PLAUSIBLE state, never an error. Every line must play the same opener; every line
  in a group must play the same guess at every ply (i.e. the file is one STRATEGY);
  and each group must EQUAL the set of answers consistent with its prefix,
  recomputed by filtering all 2315 through the pattern matrix.
- **MEASURED SHAPE of salet's tree, which is what prices the whole thing**: states
  at ply k-1 number 1 / 148 / 1253 / 908 / 81 for k = 1..5, largest 2315 / 221 / 21
  / 6 / 1, with 2315 / 2315 / 2220 / 989 / 81 answers still live. So **k=2 is the
  only expensive cell** (289636 distinct residual states of up to 221 candidates at
  a 4-guess cap); k=4 runs in **0.2 s**, k=5 and k=6 are instant, and k=1 is the
  full 12972-opener problem. Price a run by its first per-state progress line.
- Data: `math/data/shared/kthrandom/<opener>_d<D>.csv`, one row per k, resumable
  (a k already on file is skipped, not appended twice); log under
  `math/data/local/kthrandom/`. Nothing writes a `tt.bin` — see § `--tt-save`.
- **`python3 tools/checkkthrandom.py` is the GATE**, and it is MUTATION-TESTED (an
  infeasible pair still charged its k, a forgotten all-green bucket, an off-by-one
  in the cap, and an ANSWER index used as a GUESS index in the `compatible` pool
  were each caught). It diffs the C against a reference that
  recomputes every pattern FROM THE STRINGS, re-derives each state by FILTERING
  rather than grouping, and plays **PER PAIR** where the C sums **PER BUCKET** — two
  routes to one integer. Plus the real-list k=6 oracle, the seven refusals, four
  deliberately broken trees, and a **COVERAGE TALLY that FAILS** unless an
  infeasible pair, an early finish, a random word that WAS the answer and a
  multi-candidate state all actually occurred — **and unless the two pools actually
  gave different answers**, since twenty passing diffs would otherwise say nothing
  about which pool the C drew from. Run it alongside `solver/validate.sh` and
  `tools/checkpatterns.py`.

## Multiwordle (k boards at once) — a SIMULATION, not a solver
k hidden answers, one per board, every guess played on every unsolved board at once.
**Nothing here searches or optimises** — it MEASURES one named heuristic by Monte
Carlo, so its numbers carry a standard error and are not comparable with any
`optturns`-family optimum.
- **THREE RULES, AND THEY ARE THREE DIFFERENT STRATEGIES** (`math/multiwordle.py`
  states each exactly and is the source of truth). All three play the OPENING blind;
  they differ only in what happens after it. `--strategy` is required by every tool
  and lands in every filename; the WRAPPERS carry a default a human reads (`greedy`)
  and forward it explicitly. Their numbers ARE comparable with each other (same game,
  same lists, same unconstrained expected-guess quantity) and must still never be
  tabled beside an `optturns`-family optimum.
  - **`greedy`** — the original, unchanged and still the wrapper default: fewest
    candidates, ties by BOARD INDEX, uniform random candidate.
  - **`srank`** — pick the board by TILE COLOUR, not by a candidate count, which is
    the whole point (a human can see greens and yellows and cannot count candidates).
    Rank the unsolved boards by the singleton chance of the cumulative
    `(greens, yellows)` composition they show — the **tree-states** reading, so the
    ranking is indexed by the quantity it was tabulated under — take the best, break
    ties UNIFORMLY AT RANDOM, then guess one of that board's candidates at random.
    **It ignores candidate counts entirely**: 300 candidates with two greens outranks
    two candidates with none. **At k=1 it IS `greedy`** (one board is trivially both),
    so a k=1 `srank` run re-measures the committed k=1 `greedy` sweep — the gate uses
    that as a differential instead.
  - **`minavg`** — no board is targeted; a WORD is chosen. Minimise the sorted vector
    of average answers remaining over the unsolved boards, lexicographically: smallest
    first, then second smallest, and so on, final tie on the lowest guess index.
    Pool is all 12972 guesses, unfiltered. **DETERMINISTIC** — a game is a function of
    the k answers alone, so all the Monte Carlo variance is the answer draw.
  - **`minavg`'s TERMINATION HAS A PRECONDITION the others do not**: the pool must
    contain every answer word. `greedy`/`srank` always play a candidate of the board
    they target, so that board strictly shrinks; `minavg` need not, and on a pool that
    splits no board the state is unchanged and a deterministic rule replays one guess
    FOREVER. Shipped pools are fine (every answer is a legal guess) and `MinAvg`
    REFUSES an uncovered pool, but do not restrict that pool casually.
  - **THE `srank` RANKING IS A FIXED EXTERNAL TABLE, pooled across levels**:
    `data/shared/treestates/states_optturns_top1000.csv`, summing `singles` and
    `cases` over every level per composition and ranking on the pooled ratio, as an
    exact `Fraction` so a tie is a real tie (`(4,1)` and `(5,0)` are both exactly 1
    and DO tie). Read by column NAME, so added columns are harmless. Note it carries
    **21 compositions, not 20** — `(4 green, 1 yellow)` is unreachable as one reply but
    reachable cumulatively. It was tabulated under single-board OPTIMAL TREES, so using
    it to steer multiwordle is a modelling choice, not a derived optimum.
- **The original strategy, exactly** — now `--strategy greedy`:
  a fixed OPENING SEQUENCE of one or more words played BLIND in order; then each
  turn take the unsolved board with the FEWEST remaining candidates (ties by BOARD
  INDEX), and guess one of its candidates UNIFORMLY AT RANDOM. A board is solved
  only when its answer is actually PLAYED — narrowing it to one word still costs the
  naming guess — and a word played for one board solves any other board it happens
  to match (**incidental solves count**). Score = total guesses until all k are
  solved, opening included.
- **BLIND MEANS BLIND**: every word of a multi-word opening is played whatever the
  boards look like, stopping early only if all k are already solved. That matches
  how the singleton ranking for pairs/triples is defined (two answers share a bucket
  iff they reply identically to EVERY word), so the partition the greedy inherits
  does not depend on the order — only an incidental solve can.
- **THERE IS NO GUESS CAP, and none is needed** — the targeted board shrinks every
  turn (an all-green reply solves it; any other reply eliminates the word just
  played), so the game terminates on its own. **So this is expected guesses
  OUTRIGHT** — the same footing as the adversarial hill-climb, and NOT the "optimum
  subject to a guarantee" every optturns/hardturns/ansall total reports. Never put
  the two in one table. `_MAX_TURNS` in `play_game` is a runaway ASSERTION derived
  from that bound, not a modelling cap.
- **THE OPENING IS AN INPUT, NOT A RESULT, and the code never defaults it.** The
  wrapper supplies `laten` — rank 1 of `tools/singletons.py` over the 2315 (user's
  choice, 2026-09-02) — but that is a SINGLE-BOARD quantity that optimises nothing
  about the k-board total, and it is not even unique (`rotan` also scores 41; among
  answer words `brute`/`chant` tie at 40). The user knows and chose it deliberately.
  Say "the singleton-ranked opening", never "the best opening".
  - **`-n N` (default 1) names the SIZE of the opening** and resolves it against that
    size's singletons ranking — `guess_`/`pair_`/`triple_singletons.csv` for 1/2/3 —
    so **no opening word is hardcoded anywhere**; the words it resolved to are echoed,
    recorded in the CSV header with their source path, and land in the filename.
    `--openers-from FILE` is the same mechanism pointed at any ranking CSV (first data
    row, every leading `word*` column).
  - **`-n 4` and up REFUSE, and that is deliberate.** Every quad/quint run is written
    under a name recording its own restriction (`--disjoint`, `--min-letters`,
    exhaustive vs truncated) and those are DIFFERENT QUESTIONS, not variants of one —
    so the wrapper lists what is on disk and makes the user pick with `--openers-from`
    rather than guessing. Settle which quad ranking is canonical before wiring one in.
  - **`--words <list>` RESTRICTS WHICH WORDS MAY OPEN, at every stage** (added
    2026-09-17, user's call) — a stem in `data/shared/words` or a path, on
    `run-singles.sh` and (as `--word-list`) on `tools/singletons.py`. **The
    mechanism always existed**: `pairsplit` has taken `--guess-list` all along
    and the wrapper simply limited it to two lists. `--answers` is exactly
    `--words mystery` and KEEPS ITS OWN `_answers` file names, because every
    committed file is named by it; passing both is refused. Every other list
    gets `_<stem>`, which flows through the pair, triple, quad and quint
    filenames, so a restricted chain cannot overwrite or be mistaken for the
    unrestricted one.
    - **THIS IS THE DIFFERENCE BETWEEN A TOP-N OF QUALIFYING OPENINGS AND A
      FILTERED TOP-N.** Restricting at screen time spends the whole `--top` cap
      on openings that qualify; filtering the committed ranking afterwards
      cannot exceed what survived ITS cap (3230 all-custom quads, of 100000
      written from 1.76 billion scored).
    - VERIFIED at the C level: `--guess-list custom.txt` ranks **9165621**
      unordered pairs, exactly `C(4282, 2)`, against 84129906 unrestricted — a
      9.2x smaller pair space. The unrestricted `guess_singletons.csv` is
      byte-identical after the change, so the generalisation is inert.
  - **`--buckets <list>` SCORES THE SPLIT OVER A DIFFERENT LIST** (added
    2026-09-17). Every metric here counts BUCKETS OF THE PATTERN MATRIX'S
    COLUMNS, and those are the 2315 answers by default — so `singles` means
    "answers alone in their bucket". **That is the wrong quantity whenever the
    thing being screened for is about a LARGER pool**: a random-compatible
    follow-up drawing from `custom.txt` is choosing between the CUSTOM words
    still live, and a bucket can pin the answers while leaving three custom
    words alive — which is exactly how the race leader loses (§ `guarantee`).
    - **NO SOLVER CHANGE WAS NEEDED**: `pairsplit` reads its answer count from
      the matrix (`NA = c`) and already took `--patterns`; this wrapper simply
      never passed one. The derived 12972 x N matrix is built on demand under
      `data/local/patterns/patterns_cols_<list>.npy` (MEASURED 3.65 s, 55 MB for
      custom's 4282), additive and off the shared matrix paths like Lingo's.
    - It is a DIFFERENT QUESTION, so `_over-<list>` joins the suffix **with the
      others, before any output name is derived** — appending it later left the
      pair file alone unmarked, which is the exact collision the suffix exists
      to prevent.
    - **The WORD stage still scores over the 2315** (`singletons.py` has no
      `--patterns`), and the run SAYS so. Nothing downstream reads that stage —
      the pair stage enumerates pairs itself — so it is a labelling matter, not
      a wrong parent.
  - **`--top all` IS RIGHT FOR PAIRS AND RUINOUS ONE LEVEL DOWN, and `pairsplit`
    now REFUSES rather than discovering it in hour five** (2026-09-17). Under
    `--top all` every scored candidate is RETAINED — the per-thread heaps double
    without bound — so the memory is the candidate count times `sizeof(Pair)`
    (56 bytes), and that is knowable from numbers the run already prints.
    - **MEASURED, which is why the guard exists**: a triples run extending
      1000000 pairs by 4282 words = **4.28e9 candidates = 239.8 GB of kept rows**
      on a **25.8 GB** machine with a 3 GB swap file. It estimated 50 minutes,
      decayed from **372 parents/s to 2/s** as it swapped, and died at **62.8%
      after 4.75 hours having WRITTEN NOTHING**. The program's own
      out-of-memory check never fired: macOS overcommits, so `realloc` kept
      succeeding while the machine drowned, and there is no crash report or
      jetsam entry to find afterwards.
    - **THE POINT IS NOT JUST THAT IT DIED — IT WAS POINTLESS WORK** (user,
      2026-09-17): the quad stage only ever reads the top `--triples-top` of
      that file, so nothing was ever going to store 4.28 billion rows. Keeping
      them in memory bought nothing at any stage.
    - **`--top N` is the bounded-memory mode**, since the heaps then cap at N:
      `N x 56 bytes x 18 threads`, so 100000 costs ~101 MB and 1000000 ~1.0 GB.
      Every committed triple ranking was made with `--top 100000` — their metas
      say `scored=1288653393 written=100000`.
    - The guard fires at the count the run announces, refuses only what could not
      have worked (the pair sweep's 9165621 rows are 513 MB and still pass), and
      is VERIFIED INERT — regenerating the custom pair ranking after it was added
      gives a byte-identical file.
    - **The cap is NOT defaulted away**, deliberately: how many rows survive IS
      the experiment's coverage, the same reason `opening_list.py` requires
      `--top`. The wrapper still defaults `TOP=all`; the refusal names the flag.
    - **THE MERGE FREES EACH HEAP AS IT DRAINS, and that is what makes a large
      `--top` runnable** (added 2026-09-18). At the triple and quad stages every
      thread's bounded heap FILLS, so the merge array is the same size again and
      holding both is `2 x top x 56 x threads` — **20.2 GB at `--top 10000000`
      on 18 threads**, on a 25.8 GB machine. Freeing as it drains makes the
      RESIDENT high-water mark one copy plus one heap (~10.6 GB there).
      - **RESIDENT, not reserved, and the distinction IS the mechanism**: `all`
        is still malloc'd at full size, so the address space is 2x either way —
        but its pages fault in only as they are written, and a heap that size is
        mmap'd directly so `free` returns it to the OS at once. Resident is what
        swaps.
      - **THE TIMING is why it mattered more than the number suggests**: the
        merge is the LAST thing a run does, so the old peak arrived AFTER the
        whole search. A 30-hour triple stage would have died at the allocation
        having written nothing — the same shape as the `--top all` death, with a
        30-hour fuse instead of a 4.75-hour one.
      - **VERIFIED INERT TWO WAYS**: the committed
        `pair_singletons_answers_disjoint_exhaustive.csv` regenerates
        byte-identical, and an `--extend` run (5000-row cap over 4605777
        candidates, so the heaps genuinely fill) is byte-identical between the
        pre-change and post-change binaries. Nothing reads `heaps` below that
        loop, so it cannot change an output.
    - **MEASURED PARENT COST (2026-09-18): the unrestricted `--buckets custom
      --metric ssq` triple stage extends 1,000,000 parent pairs in 3.0 hours**
      (18 threads), and the work is LINEAR in the parent count — so 2M is ~6 h
      and 10M ~30 h, per stage. The pair stage is minutes whatever `--top` says:
      it scores all 84129906 pairs regardless, and `--top` only changes what is
      kept.
  - **`--extend` WITHOUT `--parents-complete` BUILDS A PARENT TABLE, AND AT A
    BIG PARENT COUNT THAT IS RUINOUS** (diagnosed 2026-09-18). `pset_build` is
    a SERIAL open-addressed hash at four slots per parent — 12 bytes x 4n of
    `calloc` plus n random first-touches. MEASURED on the 138953994 disjoint
    triples: **12.9 GB and roughly fifty new pages a second**, i.e. days.
    - **IT USED TO BE INVISIBLE, WHICH IS WHAT MADE IT COST AN AFTERNOON.** No
      output, no parallel section, and the parent file already CLOSED, so `lsof`
      showed no I/O and `ps` showed one core — the run looked wedged rather than
      busy. **A stack sample (`sample <pid>`) was the only thing that located
      it**; reach for that before theorising about a silent C process. It now
      prints its size, reports progress, and REFUSES above a third of RAM,
      naming the way out.
    - **THE WAY OUT IS THE LETTER LADDER, not more memory.** The table only
      deduplicates candidates reachable through several parents, and
      `--parents-complete` replaces it with a rule needing none. That flag is
      sound only when every sub-opener of a candidate is in the parent file:
      dropping a word loses at most 5 letters, so a target needing L needs
      parents at `L-5` or fewer. **`--min-letters 19` over DISJOINT (15-letter)
      triples fails this — 19-5 = 14 < 15 — so the refusal is CORRECT, not a
      bug.** `--disjoint` (20) lines up exactly: 20-5 = 15 >= 15.
    - **A MISSING `parents_complete=` IN A SIDECAR IS AN OLD FILE, NOT A "NO".**
      `pairsplit` has written it on every run since the field existed, so
      absence means the run predates it — and `parents_complete_flag` reads
      absence as false, which silently sends a run down the table path. It now
      SAYS so instead. `triple_singletons_disjoint_exhaustive.csv.meta` was
      BACKFILLED with `min_letters=15` and `parents_complete=1`, which its own
      `_exhaustive` name witnesses (this wrapper only assigns that suffix when
      the same test fired for ITS parents).
  - **EVERY DISJOINT QUAD IS ALREADY ON DISK, COMPLETE** —
    `quad_singletons_disjoint_exhaustive.csv`, `scored=written=25456119`,
    `complete=1`. So a question about 20-distinct-letter quads needs NO
    regeneration; it is a guarantee sweep away. Check for a complete artifact
    before proposing to rebuild one.
  - **WORDS AND PAIRS ARE EXHAUSTIVE; TRIPLES AND QUADS ARE GREEDY SCREENS**
    (`solver/run-singles.sh` says so). So `clint soare` IS the top pair, but a
    triple/quad head is "best of those screened" — never call such a run "the best
    triple/quad".
- **Run it with `bash solver/run-multiwordle.sh -k K -t T [-n N]` (from `math/`)**,
  attached, same tee'd-log rules as the sweeps. Other knobs: `--seed`, and to name an
  opening explicitly, `--opener W` (repeatable) / `--openers "A B"` / `--openers-from
  FILE`.
  `tools/multiwordle_sim.py` REFUSES to start without `--out` AND without an opening.
  **Each (k, opening, t, seed) is a different sample and gets its own file** —
  `data/shared/multiwordle/k<K>_<opening words joined by ->_t<T>_s<SEED>.csv`, one row
  per game (answers + full guess sequence) with the summary as trailing `#` lines; log
  under `data/local/multiwordle/`. Re-running the same four reproduces the file exactly.
- **It is a Monte Carlo estimate** — the summary always prints a standard error, and
  two runs differing by less than a couple of SEs have measured nothing. Rows flush
  per game, so a Ctrl-C keeps the games already played (but writes no summary).
- **OPENER SWEEP: `bash solver/run-multiwordle-sweep.sh -k K -t T` (from `math/`)** —
  the same fixed number of trials for EVERY word of a list (`--words guess|mystery|
  <path>`, `--limit N` for an alphabetical prefix, `--prefix "W…"` to fix the opening
  words before the swept one). Resumable per word. Data in
  `data/shared/multiwordle/sweep_k<K>_t<T>_s<SEED>_<list>[_after-…][_limN].csv`.
  Measured cost: ~15 min for all 12972 words at k=4/t=1000, ~2.5 h at t=10000.
  - **COMMON RANDOM NUMBERS**: every opener faces the IDENTICAL sequence of answer
    draws (draw stream re-seeded per word, kept SEPARATE from the strategy's picks),
    so DIFFERENCES between words are much less noisy than their individual SEs. The
    flip side: **a sweep cell will not match a `run-multiwordle.sh` run at the same
    seed** — `multiwordle_sim.py` draws both from one stream, so they are different
    samples of the same quantity.
  - **THE WINNER'S CURSE IS REAL AT 12972 WORDS — the head of a sweep is a SHORTLIST,
    NOT A WINNER.** The best-looking mean belongs to whichever word drew the kindest
    sample, and at small `-t` the noise spread across 12972 words dwarfs one word's SE.
    Sound use is two-stage: screen wide at small `-t`, then re-run the top few at large
    `-t` or a fresh `--seed`. A word leading both is a finding; a word leading only the
    screen is a coin flip. Never report a screen head as "the best opener".
  - **STAGE 2 IS ONE FLAG: `--shortlist-from <stage-1 sweep>.csv`** (`--se N`, default
    10 standard errors of the best word's mean; or `--shortlist-top N`). It cuts the
    list with `tools/multiwordle_shortlist.py`, writes it to
    `data/shared/multiwordle/shortlist_<stage-1 stem>_se<N>.txt` best-first, and sweeps
    only those. **PASS A FRESH `--seed`** — the draw stream is seeded per word, so
    stage 2 at stage 1's seed replays stage 1's games as its first `-t`, re-using the
    very sample that chose the shortlist; the wrapper WARNS (not fatal) when the seeds
    match. **Keep the cut generous**: discarding the true best word on one unlucky
    sample is unrecoverable, while an over-wide cut only costs time.
- **`python3 tools/multiwordle_report.py` is the standing status report** — the
  (k, n) grid at one sample size, plus `--all` for one row per file, `--trials T` to
  pick the sample size, and **`--rank SWEEP.csv` to print EVERY word of an opener
  sweep in order** (rank, mean, stderr, gap to the leader in guesses and in leader-SEs,
  spread). The `ses` column is a crowding yardstick, NOT a test: the leader's mean is
  biased optimistic and common random numbers make the error on a DIFFERENCE smaller
  than either word's SE. **The grid shows BARE MEANS** (user's preference,
  2026-09-02); `--stderr` puts the standard errors back, `--all` always carries them,
  and each CSV records its own — so check a difference against them, not against the
  digits on screen. It READS the summary lines each run wrote, recomputing
  nothing, so it cannot disagree with its source. `n` is the opening's word count,
  read off the filename. **Compare down a column only**: a different opening is a
  different strategy, and same-size openings can come from rankings of very different
  quality.
### The opener RACE (`run-multiwordle-race.sh`) — the cascade as one process
**Its estimator and its cut now live in `tools/race_stats.py`, shared with the
wordlesim race** (see that section); the loop below stays its own, because only
this one has a per-opening setup table to amortise.
The staged cascade above (sweep, cut at N SE, re-sweep survivors at the next rung
with a fresh seed, repeat) run as a SINGLE resumable process:
**`bash solver/run-multiwordle-race.sh --strategy srank -k 16`** (from `math/`),
`--pairs` for the top 10000 of the pair ranking. Every opening starts on 100 games,
anything more than `--sigma` (default **5**) behind the leader leaves the moment
that becomes true, and the survivors keep playing on a doubling schedule.
- **PAIRED FROM THE FIRST GAME, which is why it can cut this early.** Every opening
  plays the identical games AND the identical coin flips — one float per decision,
  never `integers(n)`, so two openings whose live sets differ in size cannot fall out
  of step (the wordlesim lesson, ported). The cut uses the error on the DIFFERENCE;
  each row also carries the opening's own unpaired error, so the gain is visible.
  **So a race cell will not match a `run-multiwordle.sh` run at the same seed** — the
  coupling is a different sampler, deliberately.
- **A race ELIMINATES AGAINST A MOVING LEADER**, so a lucky first hundred games can
  push a better opening out. The generous cut is a mitigation, not a proof. **The head
  of a race is the best of the openings ENTERED, judged on the games played** — the
  same "screen, not a winner" rule the sweeps carry, and `--pairs` inherits the pair
  ranking's own caveat (a screen, for a different question, top 10000 only).
- **TWO PHASES, and the switch is exact**: an int16 per-game history while the field
  is wide, then pairwise `sum(d)`/`sum(d^2)` computed FROM it once the field is under
  `--pair-at`, after which memory no longer depends on the game count. Verified equal
  both ways, with the switch confirmed to actually fire.
- **GAMES ARE THE OUTER LOOP, so a halt always leaves the field LEVEL** (user's
  call, 2026-09-09). It used to run openings-outer inside a block, which left some
  openings on 100 games and the rest on 0 — resumable, but nothing you could rank
  or cut, which is most of what halting is for. Verified to change nothing it
  measures: games are seeded per game INDEX, so loop order cannot move a score, and
  the standings and eliminations are byte-identical to the openings-outer version
  for both rules and across the pairwise switch.
  - **The chunk size is MEASURED, not chosen.** Interleaving costs one pass of
    per-opening setup per game chunk (`minavg`'s 25 MB turn-2 table), so a
    calibration — once per block, after a warmup call so it does not time the JIT —
    sizes the chunk to hold setup under `--memo-overhead` (default 10%). `srank`
    has no setup and chunks as finely as it likes; `minavg` at k=2 has to take a
    whole block at a time and at k=16 takes about twenty chunks. **The cost of
    interleaving is inversely related to how much you need it**, which is why one
    fixed chunk size would have been wrong.
  - Checkpoints are bounded to one per `--checkpoint` seconds (default 30) rather
    than one per chunk, since the history grows with the game count; the state is
    consistent at every chunk boundary, so a skipped write costs seconds of games
    and never correctness.
- **RESUMABLE MID-BLOCK.** It checkpoints atomically as it goes; Ctrl-C and re-run the
  same command. Verified byte-identical to an uninterrupted run both after a clean
  stop and after a SIGINT part-way through a block, and invariant to `--chunk`.
- **The field is every legal guess, and ANSWER openings are tracked separately** —
  the best surviving one is named in every status line and the last one's elimination
  is called out, since the 2315 answers are a subset worth following in their own right.
- **WHY `minavg` COSTS ~2000x WHAT `srank` DOES**: it SEARCHES and `srank` does not.
  Every turn `minavg` evaluates all 12972 guesses against every unsolved board's live
  candidates and takes a lexicographic argmin; `srank` computes k colour compositions
  (~26 ops each) and draws twice. It is not overhead to tune away, it is what "near
  optimal" costs — the same shape as `strturns`.
- **THE SINGLETON FAST PATH IS EXACT and is most of `minavg`'s speed at large k.**
  `a_j(g)` is 0 only when board j holds ONE candidate and g is that word, so the
  moment any board is a singleton the smallest attainable first component is 0 and
  the ONLY guesses attaining it are the singleton boards' own words — the search
  collapses from 12972 to at most k, with no change to the answer. MEASURED share of
  searched turns that qualify: 36% at k=2, 55% at k=4, 69% at k=8, **88% at k=16**,
  i.e. most common exactly where the search is dearest. **Its tie-break is the trap
  the gate caught**: two singleton boards genuinely TIE (playing either scores 0 on
  its own board and 1 on the other), so the candidates must be sorted into POOL order
  or they tie-break by board and silently disagree with the full scan.
- **MEASURED first-block cost over all 12972 openings** (18 threads, 2026-09-09,
  with the singleton path): `srank` is seconds at every k; `minavg` is ~0.05 h at
  k=1, 0.07 h at k=2, 0.14 h at k=4, 0.23 h at k=8 and **0.49 h at k=16** (it was
  1.9 h at k=16 before that path). Its turn-2 search is separately memoised per
  opener (a 243x12972 table, 0.01 s to build), that being the one turn where every
  board's candidate set is still large.
- **`--dry-run` resolves everything and stops before any game**, leaving no partial
  CSV to be mistaken for a result that died. Use it for every wrapper change.
- Data: standings + eliminations CSVs in `data/shared/multiwordle/race_*`,
  checkpoint and log under `data/local/multiwordle/`.

### `run-multiwordle-exact.sh` — the one cell where sampling is unnecessary
**`minavg` at k=1 only.** The answer is one word drawn uniformly from the 2315 and
the rule is deterministic, so those 2315 games ARE the population: the mean is the
TRUE expected guesses. No standard error, no cut, no winner's curse, and the best
row is THE best opener among the 12972 rather than a screen.
- **It REFUSES a randomised strategy and refuses k>1** rather than returning
  something weaker under an exact-sounding name — `greedy`/`srank` have a
  distribution over their own coin flips, and k>1 has a population of `C(2315, k)`.
- **It stays opener-major on purpose, and that is NOT the race's bug.** A row is
  meaningful only once all 2315 answers are played, so interleaving would leave no
  complete rows until the very end — the opposite of what halting wants. What it
  needed instead was a visit ORDER.
- **The visit order is DERIVED AND NAMED: ascending expected answers remaining
  after the opener**, the quantity `minavg` minimises at the root (one 30M-lookup
  pass, 0.53 s; it ranks `roate` 60.4 best and `immix` 967.4 worst, both known
  results for that quantity). Alphabetical order left a halt holding an arbitrary
  slice — `trace` scores 3.4436 and sits near the end of the guess list. `--order
  file` restores the old behaviour, and the CSV stamps which it used: an explicit
  disagreement on resume is refused, a file predating the stamp is continued with a
  note, since its rows are exact either way.
- **It is also the gate's only check reaching OUTSIDE the multiwordle code**: at k=1
  `minavg` is a one-ply heuristic over ordinary Wordle, so whenever its worst game
  is within 6 its strategy lies inside the set `optturns` minimised over and its
  total must be at least the committed optimum. Measured: salet 7979 vs 7920, trace
  7972 vs 7926, laten 8119 vs 8038. The within-6 precondition is checked per opener.
- **`python3 tools/checkmultiwordle.py` is the GATE**: it replays the same seeds
  through an independent implementation that keeps candidates as LISTS OF WORDS and
  recomputes every feedback from the strings with `wordle.pattern` — no matrix, no
  bitmaps — and demands byte-identical guess sequences at k=1/2/3/5, across openings
  of one, two, three and four words. It also tallies how many turns actually hit a
  BOARD TIE and FAILS if none did anywhere, so a passing run cannot silently mean the
  tie-break was never exercised. Run it alongside
  `solver/validate.sh` and `tools/checkpatterns.py`.
  - **It covers all three rules by the same discipline — the oracle shares no
    machinery with what it checks.** `srank`'s composition is re-derived by
    `tree_states.state_from_strings`, which never looks at a tile; `minavg`'s
    average-remaining is recomputed by bucketing candidate WORDS with
    `wordle.pattern`, on the full 12972 pool at real states. It also diffs the numba
    kernels against the reference guess for guess, pins the float ranking table as
    having the same order AND tie classes as the exact Fractions, and checks the race
    (elimination arithmetic, coupling, resume, phase switch).
  - **COVERAGE IS ASSERTED, not hoped for.** It FAILS if `srank`'s random board
    tie-break never fired, if `minavg`'s lexicographic tie-break never had to look past
    the smallest value, if a board reached a composition the ranking lacks, if a
    resumed race did not actually resume, or if the pairwise switch did not actually
    fire. The `minavg`-refuses-an-uncovered-pool case is CONSTRUCTED, since the shipped
    pool could never produce it.
  - **It found the `minavg` non-termination bug on its first run** — the reason that
    precondition is written down above rather than discovered by a hung sweep.

## FoxiMax (a miss ADDS a word) — a SIMULATION of one greedy heuristic
[foximax.com](https://foximax.com/): hangman-style LETTER guessing where a letter that
appears in NONE of the words on the grid adds ANOTHER word to solve. Like multiwordle
this MEASURES a named heuristic by Monte Carlo — nothing searches or optimises — so its
numbers carry a standard error and are not comparable with any `optturns`-family optimum.
`math/foximax.py` states the game and the strategy exactly and is the source of truth.
- **The rules, as modelled** (the site's about page is vague; these are the user's calls,
  2026-09-02): one word starts on the grid; a turn spends a LETTER, never twice; the
  letter HITS if it is in at least one word IN PLAY and its positions are then revealed
  in every word at once; it MISSES if in none, and a miss ADDS one word. **A newcomer
  arrives with EVERY letter guessed so far already revealed in it — hits and earlier
  misses alike**, so a "miss" is only ever a claim about the words in play AT THAT
  MOMENT, and a letter missed on turn 3 may sit inside the word turn 3 brought in. The
  game ends when every word on the grid is fully revealed; the **SCORE is the WORD COUNT
  = 1 + misses**.
- **THE REAL GAME'S EIGHT-WORD CAP IS NOT MODELLED** (deliberate, user's call). Play
  always runs to completion, so no game is a loss and the mean is an UNCONSTRAINED
  expected word count — the same footing as multiwordle and the adversarial hill-climb,
  NOT the "optimum subject to a guarantee" every optturns/hardturns/ansall total reports.
  A run's losing fraction on the real site would be the fraction scoring above 8; nothing
  computes or reports that.
- **NO CAP IS NEEDED FOR TERMINATION** — every turn spends a distinct letter, so 26 turns
  reveal everything. `play_game` ASSERTS that bound rather than imposing one.
- **WE USE OUR OWN LIST — the 2315 mystery words**, as every other sweep in this video
  does. FoxiMax's list is unknown to us and its dailies are not random draws, so a number
  here describes THIS game on THIS list, never foximax.com.
- **The strategy: greedy, one step, no search.** Guess the unguessed letter maximising
  `P(hit) = 1 - prod over boards (1 - fraction of that board's candidates containing it)`
  — each board uniform over its own remaining candidates, boards treated as INDEPENDENT
  (an approximation: the words are drawn without replacement), ties broken alphabetically.
  **It is DETERMINISTIC** — the rng is consumed only by the word draws, so a game's score
  is a function of its word sequence alone.
- **A board's state is the POSITION SET of every guessed letter** (empty = absent), and
  because of rule 4 every board carries the full history, newcomers included. So one
  `(n_words, 26)` int bitmap array (`position_masks`) is the whole feedback model, and a
  reveal is one vectorised compare — there is no pattern matrix and `patterns.npy` is not
  needed here.
- **Run it with `bash solver/run-foximax.sh -t T [--seed S] [--words mystery|guess|PATH]`**
  (from `math/`), attached, same tee'd-log rules as the sweeps. `tools/foximax_sim.py`
  REFUSES to start without `--out`. **Each (word list, t, seed) is a different sample and
  gets its own file** — `data/shared/foximax/t<T>_s<SEED>[_<list>].csv`, one row per game
  (letters played, hit/miss string, the words) with the summary as trailing `#` lines; log
  under `data/local/foximax/`. Rows flush per game, so a Ctrl-C keeps the games played.
- **`python3 tools/checkfoximax.py` is the GATE**: it replays the same seeds through an
  independent implementation that keeps candidates as LISTS OF WORDS, recomputes reveals
  from the STRINGS, and computes the probabilities in EXACT RATIONALS (`Fraction`) so a
  float slip in the fast path shows rather than being shared — demanding identical letter
  sequences, hit flags and grids. It also tallies misses and newcomers carrying an earlier
  guess and FAILS if either never happened, so a pass cannot silently mean rule 4 went
  untested. Run it alongside `solver/validate.sh` and `tools/checkpatterns.py`.

## `wordlesim` — single-board strategy SIMULATION (the strategy sandbox)
Ordinary one-board Wordle, one named STRATEGY, measured by Monte Carlo. Like
multiwordle and foximax this MEASURES a heuristic — nothing searches — so its
numbers carry a standard error and are NOT comparable with any `optturns`-family
optimum. `math/wordlesim.py` states the game and the strategy protocol and IS the
source of truth. Run it with **`bash solver/run-wordle-sim.sh --strategy NAME -t T
[--seed S]`** (from `math/`), attached, same tee'd-log rules as the sweeps.
- **TWO NUMBERS, and only one of them involves six.** The MEAN is expected guesses
  **OUTRIGHT** — play is NEVER truncated, a game that misses at six keeps going
  until the word is found — so it sits with multiwordle / foximax / the adversarial
  hill-climb and NOT with the "optimum subject to a 6-guess guarantee" every
  optturns/hardturns/ansall total reports. Never table the two together. Six enters
  ONLY as the reporting threshold the **WIN RATE** is read off (the fraction of
  those untruncated scores at or under it); `--win-within` moves it and lands in its
  own file, since it is a different reported quantity.
- **NO CAP IS NEEDED FOR TERMINATION** — a tail guess is always a live candidate,
  so an all-green ends the game and any other reply eliminates the word just played.
  `_MAX_TURNS` is a runaway ASSERTION derived from that, not a modelling cap.
- **A STRATEGY IS A RULE PLUS A FOLLOW-UP, and BOTH are inputs.** The rule is
  `rule(turn, alive, played, replies, rng) -> guess index or None`, asked EVERY
  turn; **`None` means "I have no rule for this position"** and the FOLLOW-UP
  fills it in. So a new strategy writes only its own part, and may hand back and
  take over again. Register it in `wordlesim.STRATEGIES` (name -> `Strategy(factory,
  pinned follow-up or None)`); `--strategy list` prints the registry.
- **THREE FOLLOW-UPS, and which one is part of the strategy** — different strategies,
  different numbers, so `--fallback` is REQUIRED for any rule that does not pin one
  and it lands in the filename. **`answer`**: a word drawn UNIFORMLY AT RANDOM from
  the ANSWERS still consistent with every reply (2315). **`guess`**: the same draw
  from the LEGAL GUESSES still consistent with them (12972). **`custom`** (added
  2026-09-17, user's call): the same draw from **`words/custom.txt` (4282)** — every
  answer word plus every other legal word at wordfreq zipf >= 2.5, the same committed
  list the adversarial hill-climb uses. "Consistent" is `ultraturns`' legality notion
  (a word that could still BE the answer), so a word played and missed is never
  played again. A game ends only when the answer is actually PLAYED.
  - **`custom` IS A THIRD QUANTITY, NOT AN INTERPOLATION of the other two**, and its
    numbers never share a table with theirs. It models a player who knows ordinary
    English but not the curated answer list. SMOKE-TESTED at 2000 games of the bare
    baseline, which is where it must structurally sit: mean 4.10 / 98.1% win
    (`answer`), **4.30 / 97.2% (`custom`)**, 4.87 / 90.6% (`guess`).
  - **IT IS `RandomGuess` WITH A POOL MASK, not a second implementation** — the pool
    is a boolean mask over the 12972, `None` meaning all of them, so the draw, the
    live set and the history cache are the same machinery and the `guess` path is
    bit-identical (`checkwordlesim.py` still passes unchanged). **So it needs the
    SQUARE matrix too**, and every wrapper's precondition covers it.
  - **TWO PRECONDITIONS, BOTH ENFORCED BY `pool_mask`, NEITHER ASSUMED.** Every pool
    word must be a legal guess (or it could never be played), and **every ANSWER must
    be in the pool** — the termination argument is that the true answer survives every
    filter, so a pool missing one empties the live set mid-game, on exactly the games
    that hide that word. Both refusals are CONSTRUCTED in the gate and mutation-tested.
  - **`tail_pool_words()` is the ONE place a follow-up name resolves to a list**, and
    `check_tail()` the ONE place `--fallback` is validated. Before this, five tools
    each spelled `("answer", "guess")` out for themselves, so a third follow-up would
    have been valid in some and unknown in others — the § centralize rule.
  - **The gate ASSERTS the mask does something**: identically-seeded games under
    `custom` and under `guess` must DIVERGE, or a mask selecting all 12972 would pass
    every other check (it was mutation-tested exactly that way, and caught).
  - `random-custom` is the third baseline — the same empty rule under this follow-up,
    pinning it like the other two.
- **THE HIDDEN ANSWER IS DRAWN FROM THE 2315 WHICHEVER FOLLOW-UP IS IN USE — the
  pool is the STRATEGY's, never the GAME's.** That is what makes two runs differing
  only in their follow-up directly comparable with each other, unlike a
  cross-game comparison.
- **`random`, `random-guess` and `random-custom` are the SAME EMPTY RULE under the
  three follow-ups**,
  and each PINS its own (the name is what records it), so they take no `--fallback`
  and a conflicting one is refused rather than run under a name that hides it. On
  turn one every word in the pool is live, so the opening word is itself a uniform
  draw: **no opener is an input and no word is hardcoded anywhere.** `guess`
  deliberately plays words that can never be the answer (10657 of the 12972 are not
  mystery words) — what a player without the curated answer list can do, not a defect.
- **The `guess` and `custom` follow-ups keep their OWN live set over the guess list**
  (`play_game`'s
  `alive` is over the answers and cannot express it), **cached on the (guess, reply)
  HISTORY it was built from** — an extension is folded in incrementally, anything
  else is rebuilt. That is what makes it safe AS a follow-up: it can be handed a
  game already several turns old, or a fresh game whose opening happens to repeat
  the last one, and carries no stale state into either. **It needs the SQUARE
  12972x12972 matrix** (`python3 build_patterns.py --full`, ~18s/168 MB, gitignored
  under `local/` so it is missing on a fresh clone); the wrapper checks and refuses
  with that command.
- **The wrapper RESOLVES the strategy before it creates a log or a CSV** (`--resolve`
  on the simulator), so a run that will be refused leaves nothing behind — and the
  refusal still comes from the registry, the one place that owns it, rather than
  from a second copy of the rule in the shell.
- **THE STRATEGY AND ITS FOLLOW-UP ARE INPUTS AND ARE NEVER DEFAULTED** (the greens
  scar) — the simulator and the wrapper both refuse without `--strategy`, and it
  names the output file. Each (strategy, follow-up, t, seed) is a different sample
  with its own file, `data/shared/wordlesim/<strategy>[-<fallback>]_t<T>_s<SEED>.csv`
  — the follow-up appears in the stem only when the FLAG supplied it, so a strategy
  that pins its own keeps the plain name, one row per game (answer +
  full guess sequence + the win flag) with the summary as trailing `#` lines; log
  under `data/local/wordlesim/`. Rows flush per game, so a Ctrl-C keeps the games
  played. Re-running the same three reproduces the file exactly.
### Opener sweep (`run-wordle-sweep.sh`) — a two-stage SCREEN, not a winner
The `wordlesim` analogue of the multiwordle opener sweep, reusing that sweep's
doctrine and its cut. **`bash solver/run-wordle-sweep.sh --fallback answer|guess
-t T [--seed S]`** (from `math/`), attached, tee'd log, RESUMABLE per word (one
CSV row per word, flushed).
- **The swept thing is the `opener` RULE** — play this word on turn 1, decline
  after — so the sweep and a single `--strategy opener --strategy-arg WORD` run
  build the SAME rule (`wordlesim.fixed_opener`), one source of truth. There is no
  default opener anywhere: which word to open with is what the sweep asks.
- **`--fallback` IS REQUIRED HERE TOO, and the two sweeps are two different
  screens** — the opener is feeding a different player, so "which opener is best"
  has a different answer under each. It is in the filename, and **the wrapper
  REFUSES a `--shortlist-from` whose source was swept under the OTHER follow-up**,
  which would screen one player and test another.
- **COMMON RANDOM NUMBERS, and they are the point.** The answer-draw stream is
  re-seeded per word and kept SEPARATE from the follow-up's pick stream
  (`PICK_OFFSET = 1 << 20`), so every opener faces the identical games and the
  DIFFERENCE between two words is far less noisy than their individual SEs. Flip
  side: **a sweep cell will not match a `run-wordle-sim.sh` run at the same seed**
  — `wordle_sim.py` draws both from one stream, so they are different samples.
- **THE HEAD OF A SWEEP IS A SHORTLIST, NOT A WINNER.** At 12972 words the best
  mean belongs to whichever word drew the kindest sample. Stage it: screen wide and
  cheap, cut generously, re-run the survivors larger at a **FRESH `--seed`** (the
  wrapper WARNS on a repeat — the same seed replays the games that chose the
  shortlist), repeat. `--shortlist-from SWEEP.csv` does a stage in one command.
- **"REGULAR", OR AN UNQUALIFIED REQUEST, MEANS THE MEAN-BASED RANKING** (user,
  2026-09-08). A win-rate run is always named as one; anything else is `--rank
  mean`, the default. So "the next blind quint pass" is the mean cascade's next
  pass, never the win-rate cascade's.
- **WIN RATE IS A PARALLEL RANKING, not a variant (user's call, 2026-09-08):
  `--rank win_rate` on the sweep and on `run-wordle-paired.sh`.** Everything the
  mean ranking drives, the win rate drives in the same shape — the printed leader,
  the shortlist cut, the paired comparison — and a cascade INHERITS its ranking
  from its source, so it stays one all the way down. **It lands in the stem as
  `_win`**, because a win-rate cascade and a mean cascade off the same root at the
  same pass are two different experiments that would otherwise collide.
- **A LATER PASS INHERITS `--pair-adaptive` AND `--rank` FROM ITS SOURCE — the
  STRATEGY is a property of the CASCADE, not of one command.** This is a scar:
  `--rank` was inherited and `--pair-adaptive` was not, so the win-rate quad and
  quint cascades ran ADAPTIVE at pass 1 and BLIND at every pass after it, on a
  shortlist the adaptive pass had chosen. Nothing was mislabeled — the stems
  correctly lacked `_adapt2` — but the cascade was two different strategies
  spliced together, and the agent had told the user both flags were inherited.
  **Check a cascade's `# settings` line across its passes before trusting it.**
- **THE ORDERING CHOOSER IS OFF UNDER `--rank win_rate` (user's call,
  2026-09-08).** `order_openings.py` minimises EXPECTED GUESSES, which is the
  wrong criterion for a win-rate cascade, so applying it there would quietly build
  the whole thing on mean-best orderings. A win-rate run takes the ranking file's
  own ordering instead — arbitrary, and SAID to be arbitrary, which is the honest
  option when the alternative optimises a different question. `--best-order` still
  forces it on and warns what it optimised.
- **A PROPORTION'S STANDARD ERROR IS EXACTLY ZERO AT THE CEILING, so the cut uses
  PLUS-FOUR (Agresti-Coull).** `sqrt(p(1-p)/t)` is 0 when a word wins every game,
  and at t=100 many do — a 5-SE cut in those units becomes "must also be exactly
  100%", which MEASURED kept 5 openings of 12972. Adding two wins and two losses
  (`p~ = (k+2)/(t+4)`) gives an error that is never zero: a perfect word at t=100
  reads 1.000 +/- 0.0136 instead of +/- 0.0000. **The reported RATE stays raw and
  so does the ranking** — `p~` is monotone in the win count, so only the ERROR is
  replaced, which is the only place the zero does damage. Gated on hand-made rows:
  the raw cut keeps 1 of 4 at the ceiling, plus-four keeps 3.
- **THE PAIRED COMPARISON HAS NO SUCH PROBLEM**: under `--rank win_rate` the
  per-game score is the 0/1 indicator, so the difference is a per-game win/lose
  difference whose error comes from how often the two openings DISAGREE, not from
  how close the rate is to 1. MEASURED on two blind-triple finalists: 7.3x tighter
  than their unpaired errors.
- **TWO NUMBERS MEANS TWO POSSIBLE SHORTLISTS.** Each row carries mean AND win
  rate with their own standard errors, and they need not agree.
  `--shortlist-value mean` (default, lower better) or `win_rate` (higher better)
  says which the cut ranked on, and it lands in the shortlist's name. **Never cut
  on one and report the other.**
- **`tools/sweep_shortlist.py` IS THE CUT, SHARED WITH MULTIWORDLE.** The logic
  moved there when this became the second caller; `tools/multiwordle_shortlist.py`
  is now a thin front end over it and its CLI is unchanged (verified: the `se10`,
  `top` and `own-se` cuts of the committed multiwordle sweeps are byte-identical
  before and after, and `checkmultiwordle.py` still passes). Columns are found by
  NAME in the header, so any sweep CSV here works. **`--own-se` is a DIFFERENT
  question, not a looser one** — measuring each word in its own noise can drop a
  word a fixed cut keeps.
- Data under `data/shared/wordlesim/sweep_<fallback>_t<T>_s<SEED>_<list>.csv`,
  shortlists beside them as `shortlist_<source stem>_<cut>.txt`, logs under
  `data/local/wordlesim/`.
- **MEASURED (2026-09-08, this machine): ~490 words/s at `-t 100` under the
  `answer` follow-up and ~262/s under `guess`** — so a full 12972-word stage 1 is
  well under two minutes either way.
- **`--openings-in <list>` RESTRICTS THE FIELD TO OPENINGS WHOSE EVERY WORD IS IN
  THAT LIST** (added 2026-09-17, user's call) — a stem in `data/shared/words` or a
  path, on `run-wordle-sweep.sh`, `run-wordle-race.sh` and `tools/opening_list.py`.
  It exists to pair an opening pool with a follow-up drawing from the SAME list, so
  the strategy is one player who knows one list rather than two.
  - **IT CANNOT MANUFACTURE OPENINGS THE RANKING DOES NOT HOLD, and for quads it
    runs out.** A singletons ranking is a CAPPED top-N of an enormous screen —
    the quad file is the best **100000 of 1758571509** scored quads (its `.meta`
    says `written=100000 complete=0`) — so filtering it afterwards keeps only the
    qualifying rows that happened to make that cap. MEASURED: 3230 all-custom
    quads exist in it, so **no `--top` can ever yield more**, and a "top 10000
    all-custom quads" does not exist to be read. **The fix is to screen over the
    list in the first place** — see `--words` on `run-singles.sh` — which spends
    the whole cap on qualifying openings. Read-time filtering stays right for a
    ranking you do not want to regenerate.
  - **A REJECTED ROW DOES NOT SPEND THE `--top` BUDGET.** `--top N` keeps meaning
    "N openings examined" with and without the filter; the screen keeps its width
    and reads DEEPER into the ranking to fill it. The scan reports how deep it
    went and whether the ranking was EXHAUSTED — a field smaller than `--top` then
    means there were no more qualifying rows, not that the file was short.
  - **MEASURED against `custom.txt`**: **3.23%** of the 100000-row quad ranking
    qualifies (so `--top 10000` exhausts it at **3230** openings) and **0.51%** of
    the quint one (10000 found by reading 1.96M of its 23.5M rows, 1.2 s).
  - **IT NARROWS THE CLAIM exactly as `--top` does** — the head is the best of the
    QUALIFYING openings screened, and an opening using any word outside the list
    was never examined at all.
  - **It lands in the list name as `_in-<list>`, hence in every stem and lineage
    below it.** A restricted race and an unrestricted one must not share a file,
    and therefore a CHECKPOINT, or each resumes into the other.
  - **The informational line goes to STDERR**, because `--print-stem` parses the
    race's stdout — it shipped on stdout for one run and put the whole sentence,
    spaces and a percent sign included, INSIDE the output filename.
  - The filter lives in the shared `opening_list.read_openings`, so it reaches the
    sweep, the race and the multiwordle race at once. Gated and mutation-tested
    (spending the budget on a rejected row, and ignoring the restriction, were
    each caught); an unrestricted read is asserted unchanged, so it is opt-in.
- **AN ENTRY MAY BE A MULTI-WORD OPENING, and the same cascade ranks them.**
  `--openings-from RANKING.csv --top N` takes the top N openings off an existing
  ranking (`tools/opening_list.py`, any `word*` columns, so pair/triple/quad files
  all work) and sweeps those; a list line holding several words IS the opening,
  the CSV's `word` column holds it space-joined, and the shortlist writes it back
  verbatim, so later passes are identical. A sweep REFUSES a list mixing sizes —
  ranking a 1-word opening against a 2-word one compares two different strategies.
- **BLIND MEANS BLIND, and the gate CONSTRUCTS the case rather than waiting for
  it**: later opening words are played even when one candidate is left (that is
  what a multi-word opening bets on), while a game the FIRST word wins ends there,
  so no opening is charged after the answer is found. `checkwordlesim.py` picks a
  word and an answer it isolates to a singleton, then requires the second word to
  go down anyway and the game to cost 3 — a strategy that quietly stopped would
  score 2. A random tally never fired, which is why it is constructed.
- **`--pair-adaptive N` IS THE EXACT SOLVER'S RULE, PORTED — not a new one.**
  `optturns --pair-list --pair-adaptive N` already implements it and
  **`math/data/shared/PAIRS.md`** states it and holds the exact results (best pair
  `parse`+`clint`, total 8269 at N=2 over 100k screened; `crane`+`spilt` 8299
  exhaustive over answer pairs). N=0 is pure blind, N=1 names the lone survivor,
  N=2 settles a two-way split. **N is part of the objective** — three different
  games, not comparable — so it is in the filename, and PAIRS.md explains why it
  stops mattering at 3 (three named in order cost 6; so does a perfect three-way
  split). **At the threshold the simulator's "name one at random" and the solver's
  "guess them in order" are the SAME expected cost** (a 2-set totals 3 either way),
  so this is the same rule, not an approximation of it — only the deeper
  continuation differs (random-compatible here, optimal there), and the solver's
  totals are capped at depth 6 while these are unconstrained, so **never table them
  together**.
- **THE BEST ORDERING IS COMPUTED EXACTLY, BEFORE ANY GAMES** —
  `tools/order_openings.py`, the default for an adaptive run from a ranking
  (`--best-order`; `--all-orders` sweeps every ordering instead and is how the
  claim gets checked). Half the work on pairs, a sixth on triples, **nothing given
  up**, and the reasoning is worth keeping: orderings of a set can differ ONLY
  where the switch fires or where an opening word IS the answer, because the set
  after all the words is an INTERSECTION and so is order-independent — and every
  one of those cases has a closed form at N <= 2 (a switch at level j over m live
  words costs `j + (m+1)/2`; an answer that is the i-th word costs i). Answers
  that reach the follow-up with 3+ live are exactly the ones no ordering switches
  on, so they CANCEL. **N > 2 is refused** — with three live the continuation
  stops being a closed form and the argument would silently stop holding.
  **N = 0 is allowed and is not a no-op**: a blind opening still wins earlier when
  a word that is an answer goes first (PAIRS.md measures that gap as exactly 1).
- **IT IS VECTORISED, AND THE SCALAR VERSION SURVIVES AS THE ORACLE.** The live
  set after the first j words is a GROUP COUNT over a key built one word at a
  time, so it is one `unique`/`bincount` pass over the pool per level, not a loop
  over the 2315 answers — **47x**, and `best_order_reference` states the same rule
  answer by answer for `checkwordlesim.py` to diff against. (The key is compressed
  with `np.unique` rather than encoded base-243: at three words that encoding
  spans 14.3M values and allocating a counter that size per ordering costs more
  than sorting the pool.) **Bit us first: the scalar version ran ~0.017s per pair,
  which is 3 minutes for 10000 pairs and much worse on the guess pool — and the
  wrapper passed no `--report`, so a first pass sat silent with no output at all.**
  It now prints a header immediately and a progress line every 500 openings.
  MEASURED after: ~700 openings/s on the guess pool, so a 10000-pair first pass
  orders in seconds.
- **THE CHOOSER IS GATED IN BOTH HALVES, and the second is load-bearing**: every
  closed-form cost must be what the simulator averages to on that answer, AND
  every answer it calls order-independent must cost the same under both orderings
  — which it does EXACTLY, game for game (same state, same seed, same play), not
  merely in expectation. **Measured while building it: the spread between
  orderings runs to 25 total guesses over the 2315** (mean 6.5 across the top 200
  pairs), and only 12 of those 200 tied — so picking an ordering arbitrarily is
  not a rounding error.
- **A VALIDATION THAT LOOKS LIKE A FAILURE, recorded so it is not re-chased**: a
  first check compared predicted order-differences against whole-strategy
  simulation means at t=40000 and disagreed by 7-14 total guesses, sign included.
  That was NOISE — the SE of a mean at t=40000 is ~0.0045/answer, i.e. ~10 total
  guesses, the same size as the effect. The sharp test is PER ANSWER (tiny
  variance), which is what the gate does. It did also surface one real bug: the
  "is this answer one of the opening words" test compared an ANSWER index against
  a GUESS index, two different index spaces.
- **ORDER MATTERS UNDER IT, and `--both-orders` is REQUIRED for that reason.** A
  blind opening's partition cannot depend on play order, so `pairsplit.c`
  enumerates each pair ONCE (verified: 1,000,000 rows, zero reversed duplicates);
  this rule keys on what the FIRST word alone leaves, so `a b` and `b a` are
  different strategies. The wrapper **REFUSES** `--pair-adaptive` on a ranking
  without `--both-orders` rather than examine one ordering silently — the same
  trap `optturns`' pair driver avoids by expanding every listed pair to two
  candidates. MEASURED here at t=100: 45 of 50 pairs scored differently reversed.
  PAIRS.md found the same shape exactly — the winning PAIR never moved with N, the
  winning ORDER did.
- **THE COUNT COMES FROM THE FOLLOW-UP, and that is the one deliberate departure
  from the exact solver**, which only ever counts answers. Under `answer` they
  agree; under `guess` it counts live LEGAL WORDS, so the rule fires less often —
  a player drawing from the 12972 cannot know only two ANSWERS remain, and giving
  them that knowledge for the stopping rule while denying it for the guess would
  be two different players inside one strategy. The gate exhibits a position
  holding 1 answer but 3 legal words, where the two follow-ups genuinely differ.
- **TRIPLES: the switch applies at BOTH levels, exactly as the solver does it**
  (`optturns` drops g2-and-g3 after g1, then g3 after g2), and `AdaptiveOpening`
  gets this for free by testing before every word after the first. The gate
  constructs the second-level case — an answer that survives word 1 but not
  word 2, so the THIRD word must be abandoned — since random play reaches it
  rarely.
- **ORDER MATTERS FAR MORE FOR TRIPLES: MEASURED spreads of 313 total guesses
  between the best and worst ordering** (answer pool) and a mean of 158 over 40
  triples on the guess pool, against 6.5 for pairs — two levels of switching, six
  orderings, and **0 of 40 triples tied**. So the chooser is not an optimisation
  here, it is most of the answer. Diffed against the scalar oracle on 60 triples
  (6 orderings each): 0 disagreements. MEASURED cost: ~15 sets/s on the answer
  pool, so a 5000-triple first pass orders in about 6 minutes.
- **A PAIR RUN IS A SCREEN OF A RANKING BUILT FOR A DIFFERENT QUESTION.** 84,129,906
  pairs cannot be simulated, so it examines the head of
  `data/shared/singletons/pair_singletons.csv` — which ranks pairs by how many
  answers a blind opening isolates to a SINGLETON, exhaustively evaluated (its head
  is exact) but **not this objective**, and itself only the top 1,000,000 rows.
  A pair below `--top` is never examined at all. **Say "the best of the N
  screened", never "the best pair"** — the same caveat multiwordle's `--top-n`
  pair screen carries.
- **MEASURED (2026-09-08): pair sweeps are FASTER than single-word ones** — ~1448
  openings/s (`answer`) and ~627/s (`guess`) at `-t 100`, against 490 and 262 for
  single words, because a two-word opening leaves far fewer candidates and the
  follow-up does less work. So the whole committed 1M-pair file screens in ~12 min
  (`answer`) / ~27 min (`guess`).
- **THE TRIAL LADDER IS 100, 200, 300, 500, 1000, 2000, 3000, 5000, … (user's
  call, 2026-09-08).** Give `-t` on the first pass; **omit it on a
  `--shortlist-from` pass** and the wrapper takes the next rung above the source
  sweep's own `-t`, and the next SEED above its seed — both echoed, both in the
  filename. Deriving the seed is not a convenience: reusing the source's seed
  replays the very games that chose the shortlist. `-t`/`--seed` still override.
- **`--dry-run` STOPS AFTER RESOLUTION** (which list, trials, seed, output file)
  and before anything runs. It exists because checking the wrapper's plumbing
  must not cost a sweep — **a partial CSV from a "quick check" is
  indistinguishable from a real result that died.** Use it for every wrapper
  change; a bare invocation to "see if the flags parse" starts a real run.
- **NEVER EDIT A `run-*.sh` WHILE ONE IS EXECUTING IT.** Bash reads a script
  incrementally, so rewriting it in place shifts the byte offsets under the live
  process and it resumes mid-token — `syntax error near unexpected token` from a
  file that parses fine afterwards. Bit us 2026-09-08 mid-sweep; the run's own
  output survived (the tool had already written its CSV) but the wrapper died.
  `pgrep -f wordle_sweep.py` before touching one.
- **PROGRESS PRINTING TIGHTENS ONE RUNG PER PASS (user's call, 2026-09-08)** —
  100, 50, 30, 20, 10, 5, 3, 2, then every opening from pass 9 on. The wrapper derives the pass from the SOURCE SWEEP'S OWN NAME (each stage's
  word list is a shortlist of the stage before, so the nesting counts the passes),
  and `--progress` overrides it. It gates a print and nothing else, so it changes
  neither the games nor the filename — a run is comparable with one made before the
  default existed. (A `case`, not a bash array: macOS ships bash 3.2.)
- **THE STEM IS `sweep_<follow-up>_<root>_p<PASS>_t<T>_s<SEED>[_adapt<N>]`, and the
  LINEAGE LIVES IN THE FILE, not the name.** Each CSV's header carries
  `# lineage root=… pass=… source=…`, naming its immediate parent, whose own
  header names ITS parent — the chain is walkable one file at a time, in constant
  name length. **This is a scar**: the original scheme nested the whole ancestry
  into the name, which grew ~40 characters per pass and **died at macOS's 255-byte
  filename limit on pass 6** — after the shortlist had been cut and the run had
  started, so the failure came from `open()` with everything already done. The
  wrapper now REFUSES a stem over 200 characters rather than discover it at the
  first write, and recovers `root`/`pass` from an old nested stem (everything
  after `openings_`, trailing `_se<N>`/`_adapt<N>` stripped; passes counted by
  `shortlist_` occurrences) so cascades already in flight continue unbroken.
- **READ A RUN'S PARAMETERS FROM ITS HEADER, NOT ITS NAME.** Every sweep CSV's
  first line states its own trials, follow-up and seed, and that stays true across
  naming schemes — which have now changed twice, breaking a name-parser BOTH
  times (the nesting fix broke `-t`/`--seed` derivation, since the bounded stem
  puts `_t..._s...` at the END). Stem parsing survives only as a fallback for
  files written before the header existed. Same lesson one level down: the pass
  number is derived ONCE from the lineage header — it used to be counted a second
  time from `shortlist_` occurrences in the name, so a pass-9 run announced
  "pass 2" and printed on the wrong interval while correctly writing `p9`.
- **A STEM NESTS ITS ANCESTORS, so parse it ANCHORED at the front.**
  `sweep_answer_t10000_s2_shortlist_answer_t1000_s1_shortlist_..._t100_s0_...`
  holds three `_t` and three `_s`, oldest LAST — so a greedy `.*_t` reads the
  most distant pass. Bit us the moment the ladder started deriving values: a
  depth-4 chain derived `-t 200` from a `t=10000` source and reused seed 0 while
  announcing it had advanced the seed. The current sweep's own figures are the
  ones immediately after `sweep_<follow-up>_`. Caught by a `--dry-run` across four
  pass depths — which is exactly what that flag is for.
- **THE CUT IS 5 STANDARD ERRORS, not multiwordle's 10 (user's call, 2026-09-08),
  and that is MEASURED rather than preferred**: at `t=100` a word's SE is ~0.10, so
  10 SE spans a full guess and kept **12367 of 12972** words (`answer`) / 12911
  (`guess`) — too wide to screen anything. The default lives in
  `run-wordle-sweep.sh`; multiwordle's wrapper keeps its own 10 and the shared
  tool is untouched, so neither pipeline's cut can move under the other. The cut
  is in every filename, so stages cut differently cannot be confused.
- **THE WINNER'S CURSE IS NOT THEORETICAL HERE — MEASURED on pass 1 to 2 of the
  `answer` sweep (2026-09-08).** Stage 1's leader `parle` (3.5000 at t=100) came
  back at **3.9450 at t=1000, rank 730 of 12367** — a 0.445 regression, about 13 of
  its own stage-2 standard errors. **Only 2 of stage 1's top 20 were still in stage
  2's top 20**, and the new leader `trace` had been **rank 700** in the screen. So
  the generous net is load-bearing, not caution: any cut tight enough to look
  decisive at t=100 would have thrown the leader away. Quote this when explaining
  why a screen head is never reported as a winner.
- **A WIN-RATE CUT IS DEGENERATE AT SMALL `-t` — do not use `--shortlist-value
  win_rate` at t=100.** A word scoring 100/100 has a binomial SE of exactly 0, so
  "within N SE of the best" collapses to "also exactly 100%": measured, it kept
  3555 words (`answer`) and **5** (`guess`), an exact-tie filter rather than a net.
  Fixing it needs an interval that stays finite at p=1 (Wilson, say); until then
  the mean is the only sound column to cut on.

### `paired_compare.py` — settling finalists by DIFFERENCES, not by two means
At the end of a cascade the gaps between finalists are far smaller than their own
standard errors, and doubling the trials just reshuffles them. **`python3
tools/paired_compare.py --from FINALISTS.txt --fallback answer|guess
[--pair-adaptive N] -t T --seed S --out FILE`** compares them by paired
differences instead.
- **THE ESTIMATOR:** every opening plays the SAME game, `d_i = score_A - score_B`,
  reported as `mean(d) +/- sd(d)/sqrt(t)`. No new modelling — the same games, read
  as differences. **It sharpens COMPARISONS WITHIN the set only**; the absolute
  means keep their own errors, and it says nothing about openings outside the set.
- **MEASURED ON THE FIRST REAL RUN (2026-09-08), and this is why it exists**: 22
  adaptive-pair finalists that the sweep had left inside 1.5 SE resolved into a
  two-way TIE (`claes print` / `plant cries`, 0.4 sigma apart) with everything
  else separated at 1.4 to 8.6 sigma. The pairing was **14.9x tighter** than the
  unpaired errors on the closest pair — anagram openings play nearly identical
  games, so almost all of the variance cancels. It also overturned the sweep's own
  leader: `clans tripe`, which led pass 17, sits 3.4 sigma behind.
- **TWO COUPLINGS, and the second was the user's call (2026-09-08) and the bigger
  half.** MEASURED on `dance horst blimp` vs `chant dorse blimp`, t=20000:
  unpaired error 0.00413; sharing the ANSWER 0.00310 (1.3x); sharing the answer
  AND the follow-up's COIN FLIPS **0.00175 (2.4x)** — i.e. ~5.8x fewer games for
  the same precision. Unbiased either way: a uniform draw from an opening's own
  live set is still uniform over that set, so only the correlation changes.
- **THE COUPLED DRAW USES `random()` AND AN INDEX, NOT `integers(n)`** — `integers`
  consumes a variable number of bits (rejection sampling), so two openings whose
  live sets differ in SIZE fall out of step after the first differing draw and the
  coupling silently decays. One float per draw holds them turn for turn. It is a
  different consumption pattern from the sweep's, so **a paired mean will not match
  a sweep cell to the last digit** — same quantity, different sample.
- **RUN IT ON A SWEEP FILE DIRECTLY: `bash solver/run-wordle-paired.sh --from
  <sweep>.csv`.** The finalists, the follow-up, the `--pair-adaptive` threshold,
  the trial count and the seed are all READ FROM THE SOURCE — comparing finalists
  under a different strategy from the one that selected them would be a different
  experiment wearing the same filename. **The seed is the one exception: it
  advances by one**, since the finalists were chosen by the source's own games.
  Every one of those overrides on the command line.
- **THE SWEEP'S OUTPUT PATH IS GATED END TO END, and that is a scar**: every
  other check called `sweep_word` directly, so nothing exercised the header
  WRITING, and a format string with six placeholders and five arguments shipped —
  crashing every first pass AFTER the file was created, whose existence then
  suppresses the header on the re-run. The gate now runs the real `main()` into a
  temp file and reads it back with the parser that consumes it.
- **A `# settings follow_up=… pair_adaptive=… win_within=… trials=… seed=…` line
  is now written into every sweep CSV**, machine-readable beside the prose, so a
  later tool cannot be broken by rewording a paragraph. Older files fall back to
  the first line plus, for `adapt` alone, the prose — parsing prose is the
  fallback, never the plan, which is why the settings line exists.
- **THE OUTPUT IS SWEEP-SHAPED**: `word,trials,<value>,<value>_stderr` first,
  then `diff_vs_leader,paired_stderr,sigma`, so `sweep_shortlist.py` and every
  other reader of a sweep CSV reads it too. **The value column is named after the
  RANKING** (`mean`/`stderr` or `win_rate`/`win_rate_stderr`) — it used to be
  `mean` whatever was ranked, so a win-rate paired file carried a win rate in a
  column called `mean` and every reader asking for `win_rate` failed on it. Files
  written before the fix are still readable: `read_sweep` falls back to `mean`
  when the header's `# settings rank=` says that is what it holds. The name is derived by the tool itself
  (`--print-stem`), so the wrapper does not re-implement it in shell.
- **ROUNDS CHAIN, AND THE CUT IS ON THE PAIRED SIGMA.** A paired CSV is itself a
  valid `--from`: **`--sigma N` (default 5) keeps every opening within N PAIRED
  sigma of the leader** and the trials advance one rung of the same 1-2-3-5
  ladder, seed +1. That is the right cut for this file — its own `stderr` column
  is the conservative unpaired error the pairing exists to replace, so a
  `sweep_shortlist.py` cut on it would be answering the wrong question. MEASURED
  on the first real run: 22 openings, 5-sigma keeps 10, 3-sigma keeps 5.
- **THE PAIRED FILE WRITES THE SAME `# settings` AND `# lineage` LINES A SWEEP
  DOES** (plus `round=`), which is what makes a round chainable; files written
  before those lines existed are recovered from their own prose.
- **No per-game storage**: pairwise sums and sums of squares are accumulated, so
  `-t` can be as large as wanted for any number of finalists. It compares
  FINALISTS, not fields — every opening plays every game, so `--max-openings`
  refuses more than 50 unless raised, and `--top N` takes the source's best N.
- Gated: the coupled index reaches every live word across the unit interval,
  coupled games are legal (every guess consistent, ending on the answer),
  `mean(A-B)` equals `mean(A)-mean(B)` exactly, and pairing must actually reduce
  the spread.

### `run-second-exact.sh` — the EXACT best second word, and a PROOF of it
The one-ply table picks a second word by "fewest answers remaining", which is a
PROXY. This computes what the choice really costs and finds the true argmin:
**`bash solver/run-second-exact.sh [--opener W]`** (from `math/`), attached,
tee'd log, `--dry-run`. With no `--opener` it walks every opener and the result
is the proven optimum over all 12972 x 12972 (opener, second word) pairs.
- **THE RANDOM TAIL IS SUMMED EXACTLY, not simulated.** Its cost depends only on
  the live candidate SET, and a uniform random guess sends the answer into a part
  that never contains that guess — so the recursion terminates:
  `T(S) = |S| + (1/|S|) * sum over g of sum over parts P != {g} of T(P)`,
  memoised on the set. **VERIFIED against a brute-force playout** and, at full
  scale, against the committed race: `spilt`+`crane` is exactly **3.671133**
  where the Monte Carlo measured 3.670342 +/- 0.000649 — 1.2 sigma.
- **WHY EXACT RATHER THAN SIMULATED, measured**: separating 12972 second words
  means resolving ~0.005 guesses at a per-game sd near 0.9, so ~290000 games EACH
  — 3.8 billion for ONE opener, hours, and still an error bar. The recursion does
  it in **0.6 s**.
- **THE BOUND IS WHAT MAKES IT A PROOF.** `T(S) >= 2|S| - 1` by induction (a
  guess splits `S` minus itself into at most `|S|-1` parts), so summing over a
  second word's buckets needs only their SIZES — no recursion. MEASURED on
  `spilt`: **11008 of 12972 second words discarded outright**, a 16x saving, and
  `--no-prune` confirms the pruned and unpruned answers are identical.
- **BOUND FIRST, WALK ASCENDING** — and skipping that was a real mistake. In list
  order the first openers are `aahed`, `aalii`, … , each scanning thousands of
  second words before any incumbent exists to cut them: **`aahed` alone took 80 s
  against `spilt`'s 0.6**. Bounded first and walked ascending, a good incumbent
  exists before the bad openers are reached. **The visit order is a computation.**
- **MEASURED: bounding all 12972 openers takes ~55 s**; a full run is tens of
  minutes, and the `evaluated / cut` line is the real cost to watch.
- **IT IS TIED TO THE `answer` FOLLOW-UP** — the tail draws from consistent
  ANSWERS, so a state is a subset of the 2315. The `guess` follow-up is a
  different and much larger recursion.
- **TWO SCARS IN THE C, both found by the gate and ASan.** The recursion's
  scratch must be indexed BY DEPTH: it partitions a set while walking the parts
  of its caller's partition, so one shared counter array is clobbered by the very
  call reading it — a heap overflow, not a subtly wrong answer. And `Row` is
  `calloc`'d, so a CUT opener's `second` read back as index 0, a perfectly good
  word, and printed as a real choice.
- **The memo is a REPLACING cache keyed on a 128-bit fingerprint**, not a table
  that must hold everything: a bad opener has an enormous number of distinct
  subsets, growing to fit them is gigabytes per thread, and clearing when full
  thrashes (measured: seconds became minutes). A false hit needs a collision in
  both hashes AND the same set size.
- **`--by-grays N` GIVES EACH GREY COUNT ITS OWN WORD** — secondword's
  `e5.e4....eN` partition, evaluated exactly. **THE GROUPS ARE INDEPENDENT**:
  they partition the firing replies, so the total is the decline branch plus a
  SUM over groups, and each group's best word is found on its own — k separate
  argmins, not a joint search over k words, and since every answer still lands in
  exactly one group the scanning work barely moves.
  - **The per-group cut is weak on its own** (measured: `spilt`'s `e5` group
    scanned all 12971 words), because a group's words are all close together. The
    INCUMBENT cuts across groups instead and is still sound: whatever this group
    costs, the others cost at least their own bounds, so `decline + this word's
    bound + the others' floor` bounds the whole strategy.
  - **MEASURED: ~18 CPU-seconds per opener**, so a full run is around three hours
    on 18 threads — and that is the worst case, from a probe whose incumbent was
    weak. Watch the `evaluated / cut` line.
- **THE g3 RESULT (2026-09-10): `clint` then `parse`, 3.666937 exact**, over all
  12972 openers with 11324 evaluated and 1648 cut, in 653 s. **`spilt` is only
  4th** (3.671133) — it won the RACE because that race used the one-ply table's
  second words, and under exactly-optimal ones the ranking moves. That is the
  reason to prove rather than screen. NB `parse`+`clint` is also the best adaptive
  PAIR in `data/shared/PAIRS.md`, reached from a completely different direction.
- **IT TAKES EVERY PARTITION `secondword` DOES, because the two share ONE unit:
  `solver/groups.h`/`groups.c`.** The firing-condition grammar, the canonical
  label and the per-opener masks are compiled into BOTH binaries, so `--group`,
  `--by-grays N`, `--split-vowels` and `--split-matched-vowels` mean the same
  thing to each, and a table written by one is a table the other reads. The vowel
  atoms arrived here as a CONSEQUENCE of that extraction, not as a second
  implementation — which is the only reason `secondexact` can answer the
  vowel-partition question exactly instead of racing it.
  - **VERIFIED byte-identical across the extraction** on `g3`, `e3.e4.e5` and the
    greyed-vowel partition; the one deliberate change is the matched-vowel table
    dropping `e5_mv0` in favour of `e5` (a reply with 5 greys matched nothing, so
    the two name the same set), which took its rows from 900 to 360 with 297
    common non-empty rows and 0 disagreements.
  - **A VOWEL ATOM MAKES THE MASKS OPENER-DEPENDENT**, so they are rebuilt per
    opener, per thread — `groups_opener_dependent()` decides, and without one the
    single shared mask is used exactly as before.
  - **The WRAPPER asks the BINARY what the condition is called** (`--print-label`,
    which resolves the groups and stops without loading anything). groups.c sorts
    the groups, drops repeats and collapses a vacuous split, so a stem derived in
    shell would be that rule written a second time in a second language — the
    same reasoning behind `paired_compare.py --print-stem`. It also means an
    impossible combination is refused before a log or a CSV exists.
- **THE MATCHED-VOWEL RESULT (2026-09-16): `slant` scores 3.643368**, against
  3.650558 for the grey count alone and 3.666937 for one shared word — measured
  on one opener in 5.7 s, which is the whole point of the extraction.
- **`--topk K` MAKES IT A SCREEN, and ONE K GOVERNS BOTH ENDS** -- the K best
  OPENERS, and within each the K best second words per group. Every total is an
  **UPPER BOUND** and the winner is the best of the openers EXAMINED, never the
  proven optimum. K is part of the objective: it is in the filename and in the
  `# settings` stamp, and a resume refuses a file written under a different K or
  a different opener count.
  - **THE ROOT IS A BRANCHING POINT LIKE ANY OTHER.** This is the repo-wide
    convention (`strturns`, `greens`, `mmturns`, `wturns`, `ultraturns`, nerdle
    all say it) and a separate opener-count flag was proposed and REJECTED by the
    user for `greens` on 2026-09-03. **It shipped wrong here on 2026-09-16** --
    beaming only the second words while still sweeping all 12972 openers, so a
    `--topk 1` run still paid the full 112 s bound of every opener and then
    walked the lot. Caught by the user within minutes. The ranking convention was
    carried across and the SCOPE convention was not; the gate now ASSERTS that a
    small K examines fewer openers, so it cannot be dropped again quietly.
  - **The root rank is ascending EXPECTED ANSWERS REMAINING** (sum of squared bin
    sizes over the opener's own partition of the 2315, ties on the lowest guess
    index) -- one pass over the answers per opener, so the K best are known
    before anything is bounded, which is what makes a small-K run start in
    seconds instead of two minutes. **VERIFIED against a known result**: it ranks
    `roate` 60.4 best and `immix` 967.4 worst, the same figures
    `run-multiwordle-exact.sh` records for that quantity.
  - **A NAMED opener (`--opener` / `--openers`) is EXEMPT from the root beam** --
    there the root is chosen and K beams only the branching below it, which is
    how `wturns` splits the same two cases.
  - **WHY IT IS WORTH HAVING, measured on the completed by-grays run**: the
    within-opener bound barely prunes on the big groups (median words scanned per
    opener: e3 2803, e4 10809, **e5 12971 -- all of them**), so that run made
    **286 million** exact second-word evaluations. At K=10 it would make at most
    322800, an **886x** cut in the dominant cost. Reordering the exact walk
    cannot recover this: the within-group cut fires on the bound's VALUE, so when
    the bounds are clustered below the threshold no order prunes anything.
  - **THE RANKING IS `secondword`'s RULE, not a second copy of it** -- ascending
    sum of squared JOINT bucket sizes over the group's qualifying answers, every
    bucket counted including the all-green one, ties on the lowest guess index.
    It is computed in the SAME pass that already builds those buckets for the
    bound, so it costs one add per bucket. The gate diffs `--topk 1` against
    `secondword`'s own argmin and requires agreement in every cell, ties included.
  - **K=1 IS NOT ENOUGH, and that is measured**: over the 10760 openers of the
    completed by-grays run the one-ply argmin is the exact best second word only
    **22.9%** of the time (e3 27.7%, e4 22.9%, e5 18.0%). That is the same fact
    that made `spilt` win the RACE and `clint` win the exact solve. Choose K from
    data, never by eye.
  - **The within-group incumbent cut is deliberately OFF under `--topk`.** That
    cut leans on the other groups' costs, and once a group's value is itself only
    an upper bound the reasoning stops being sound -- so the beam stays the ONE
    approximation and the claim stays exactly "the best of the K examined". The
    OPENER-level cut is untouched and still sound, since the incumbent is always
    the value of a strategy that exists.
  - **`--no-prune` still means "every opener"** and composes with `--topk`, which
    is how the beam gets compared against the exact answer.
- **THE THIRD LEVEL (`--third-key group --third-max-matched N`)**: after the
  opener and the committed second word, a case whose two replies together have
  proved at most N letters plays a THIRD committed word, chosen in advance.
  Only on lines where the second word actually fired; above N, and on declined
  lines, the random tail takes over as before.
  - **THE KEY IS MATCHED LETTERS = `tree_states`' greens + yellows** (user's
    definition, 2026-09-16): distinct letters known present, counted AGAIN per
    proved copy. It is a function of the two REPLIES alone, so it is CONSTANT
    within a joint bucket -- which is what makes it a legal key, and the gate
    ASSERTS that constancy rather than assuming it.
    - **POSITION 0 IS THE MOST SIGNIFICANT TRIT** and the first implementation
      got this wrong, disagreeing with `tree_states` on 1161 of 4000 triples.
      `--dump-matched` exists for exactly that diff. See `secondword.py`'s
      `tile_at`, which documents the same trap.
  - **`group` KEEPS THE PROBLEM SEPARABLE; `shared` DOES NOT.** A word per
    (group, matched count) leaves each group's joint buckets disjoint from every
    other group's, so each group still picks its own second word and its own
    third words and the sum decomposes exactly. Sharing one word per matched
    count across the groups couples them: the second words must then be re-chosen
    inside a search over word TRIPLES, roughly `6k^4` per opener against
    `18k^2`. **`shared` is NOT BUILT YET and the flag says so.**
  - **IT REQUIRES `--topk`** -- choosing a third word for every candidate second
    word is a nested search and only the beam makes it affordable.
  - **`--third-decline` IS WHAT MAKES IT WORTH ANYTHING, and the difference is
    large.** A case may play NO committed word when the random tail is cheaper.
    FORCED, a third word is consistently WORSE than the tail it replaces;
    declining, it is consistently better. MEASURED on the real lists:

        k      two-level   forced third   third + decline
        5      3.708983    3.751380       3.704926
        20     3.686815    3.720679       3.683734
        50     3.663450    3.699032       3.659041
        100    3.652788    3.690977       3.647341

    At k=100 only **288 of 982** cases keep a word -- 71% decline -- and all 100
    openers are strictly better than two-level, none worse. The forced version
    is the same shape as firing a second word on two greys: where you still know
    almost nothing, a predetermined word cannot beat a random compatible answer.
  - **DECLINING GIVES A FREE ORACLE and the gate asserts it PER OPENER**: the
    three-level family then CONTAINS the two-level one (decline everywhere and
    you have it back), so no opener may come out worse. **Known coverage gap**:
    on the mini problem every committed word is declined, so a SURVIVING third
    word is never exercised there -- that case wants constructing.
  - Third words get their own CSV rows, `fires` = `<group>|m<matched count>`
    with `third` in the status column.
- **`--max-level N` PUTS A COMMITTED WORD AT EVERY LEVEL, each able to DECLINE**
  (user's call, 2026-09-17), and supersedes `--third-key`, which is its N=3 case.
  A CASE is a set of buckets sharing one word; it plays that word or declines to
  the random tail, whichever is cheaper, and the resulting buckets are regrouped
  by matched count into cases one level down. Level 2's cases are the
  partition's groups; below that the key is the matched count, nested under the
  path. Rows are named `<group>|m<a>|m<b>...`.
  - **DECLINING AT EVERY LEVEL MAKES THE FAMILY CONTAIN EVERY SHALLOWER ONE** --
    decline everywhere at level 2 and the plain opener is back -- which is where
    the gate's three oracles come from: `--max-level 2` can never be worse than
    the plain two-level beam, `--max-level 3` never worse than the fixed third
    level with declining, and the result must be MONOTONE in N.
  - **THE THREE ORACLES EARNED THEIR KEEP IMMEDIATELY.** `L->cand` was ONE array
    shared by every level: a case ranked into it, sorted, then walked it calling
    the recursion, which re-ranked the SAME array, so the parent resumed reading
    its child's candidate list. The symptom was `--max-level 4` coming out WORSE
    than 3 and every second word being `aahed` (guess index 0). **The fix is one
    candidate array PER LEVEL** -- the same per-depth scratch rule the memo
    arrays already carry, and ASan cannot see it because nothing is out of
    bounds. Note `--max-level 2` equals the two-level beam on the REAL lists but
    is strictly better on the mini problem, where declining always wins.
  - **COST IS THE BEAM WIDTH PER LEVEL**, `k^(N-1)` per group, so deep runs want
    a far smaller K than shallow ones. It requires `--topk` for that reason.
  - **An opener that declines everywhere still has a value**, and its rows now
    carry the total: it is the plain opener, not a blank.
- **IT RESUMES, and the CSV is the checkpoint.** Each opener's rows are appended
  the moment it finishes, so re-running the same command skips what is on file
  and -- the part that saves real time -- SEEDS THE INCUMBENT with the best total
  already proved, so the bound cuts from the first opener instead of after the
  first dozen. A CUT opener is deliberately not recorded: re-cutting it is free
  and still sound, because it was cut against an incumbent no better than the one
  a resume starts with. A file whose stamp names a different condition or a
  different K is REFUSED, not continued.
  - **Rows are therefore in COMPLETION order, not opener order.** Every reader
    here parses by column name, so nothing cares -- but a diff against a
    pre-resume file will not line up.
- Data under `math/data/shared/secondexact/`, log under `data/local/secondexact/`.
  **The LABEL is the filename**, so `exact_e3_mv0.e3_mv1.e3_mv2.e4_mv0.e4_mv1.e5`
  is one partition's file and cannot be confused with another's.
- **`python3 tools/checksecondexact.py` is the GATE**: the recursion against a
  brute-force enumeration in exact RATIONALS over all 24 mini openers, the pruned
  walk against `--no-prune`, the bound's soundness on random sets, the
  decline/fired split adding up, and the real-lists value against the race.
  - **Checks 6 and 7 are the PARTITION checks, and 7 is the only one that
    exercises the per-opener masks.** The enumeration is told which words the C
    committed to and must reproduce its total; the reference derives the
    matched-vowel key FROM THE STRINGS (y a vowel, counted by position) and takes
    the group NAMES from `--print-label` rather than spelling them itself.
    **Coverage is asserted**: it FAILS unless the finer partition actually beat
    the coarser one somewhere and unless some opener actually played two
    different words within one grey count. MUTATION-TESTED — counting greyed
    vowels instead of matched ones, dropping `y` from the vowels, and swapping
    the two counts inside `groups.c` were each caught.

### `run-second-loss.sh` — where the EV loss goes, by the opener's grey count
The gap between a second-word strategy and OPTIMAL play, decomposed. Every answer
is played `-n` times under the strategy and compared with what that answer costs
under the committed optimal TREE for the SAME opener; answers are grouped by how
many greys the opener's reply shows, and each group's share of the whole gap is
reported. **`bash solver/run-second-loss.sh --opener W [--second-from TABLE]`**
(from `math/`); omitting the table measures the plain opener, which is how you
price what the second word buys.
- **"OPTIMAL" IS THE SAME OPENER, NOT THE BEST ONE**, and that is what makes it a
  decomposition: each bucket's gap is about how the strategy plays THAT bucket
  with the opener held fixed. The opener's own cost is a separate number
  (`spilt` 3.48121 against `salet`'s 3.42117) and belongs to no bucket.
- **IT IS THE CAPPED OPTIMUM** — minimum guesses subject to solving every answer
  within six, which is what `optturns` computed and what the trees are — while
  the strategy is UNCAPPED. A capped optimum is >= the unconstrained one, so
  **every gap reported is a LOWER BOUND on the loss against true optimal play**.
- **THE ESTIMATOR IS STRATIFIED: every answer is played the same number of
  times**, so the answer weights are EXACT (1/2315 each) and the reported
  standard error is the strategy's coin flips ALONE. The spread between answers
  is the thing being decomposed, not noise in it — which is why this is per
  answer rather than a uniform draw, whose bucket shares would carry sampling
  noise of their own.
- **`--by-case` REPORTS THE STRATEGY'S OWN CASES, one row per group**, instead of
  by grey count. Whatever partition the table was built on -- grey counts, vowel
  splits, `nz` which-tiles -- its groups ARE the cases the strategy
  distinguishes, so the report keys on them directly rather than on a count that
  may be far coarser than the rule. Replies that DECLINE belong to no group and
  keep their grey count (`decline g2`), since that is all that separates them.
  - **It needs a `--second-from` table**, which is where the cases come from, and
    it is refused alongside `--split-matched-vowels`: two different report keys.
  - **THE TOTALS ARE INVARIANT TO THE BUCKETING and that is a free check** -- A,
    B, C and the word/followup split are properties of the strategy, not of how
    the rows are cut. MEASURED on `slane`'s 16-group table: A 3.43110 and
    word-choice loss 0.06825 both ways, to five decimals.
  - Its CSV carries a `case` column in place of `grays`, and the stem ends
    `_case`.
- **THE GATE IS BUILT IN and always runs**: the tree's per-answer costs must sum
  to the total the committed CSV records for that opener, it must cover every
  answer exactly once and open with that word, the grey counts are recomputed
  FROM THE STRINGS, and the bucket contributions must sum to the overall gap.
  Mutation-tested (a wrong share denominator and a single altered tree cost were
  each caught). It exits nonzero rather than reporting.
- **MEASURED: 46,300 games in 0.36 s**, so `-n 1000` (2.3M games) is under 20 s.
- Data under `math/data/shared/secondloss/`, log under `data/local/secondloss/`.

### The opener RACE (`run-wordle-race.sh`) — the cascade as ONE process
The `wordlesim` analogue of the multiwordle race, and the way to find a good
opener now. **`bash solver/run-wordle-race.sh --fallback answer|guess
[--second-from TABLE.csv]`** (from `math/`), attached, tee'd log, resumable —
Ctrl-C and re-run the same command. Every opener starts on 100 games, anything
more than `--sigma` (default **5**) PAIRED sigma behind the leader leaves the
moment that becomes true, and the survivors double.
- **IT REPLACES THE STAGED CASCADE**, which is still there and still works
  (`run-wordle-sweep.sh --shortlist-from …` pass by pass, then
  `run-wordle-paired.sh`) — same statistics, one process instead of a dozen
  commands with the ladder and the seed advanced by hand.
- **PAIRED FROM THE FIRST GAME**, which is why it can cut this early: every
  opener plays the identical games AND the identical coin flips — one float per
  decision, never `integers(n)`, the wordlesim lesson — so the cut uses the error
  on the DIFFERENCE. Both errors are in every row. **So a race cell will NOT
  match a sweep cell or a `run-wordle-sim.sh` run at the same seed**: the sweep
  couples the ANSWERS only and draws its picks with `integers`. Same quantity,
  different sampler, deliberately.
- **IT IS A SCREEN AND IT ELIMINATES AGAINST A MOVING LEADER**, so a lucky first
  hundred games can push a better opener out. The head of a race is **the best of
  the openers ENTERED, judged on the games actually played** — never "the best
  opener". The generous cut is a mitigation, not a proof.
- **IT RANKS ON THE MEAN *OR* THE WIN RATE — `--rank`, the sweep's own flag**
  (added 2026-09-17, user's call; it had been deliberately left out rather than
  half-built). Two different questions of the same games, which need not agree,
  so they are two different races: the ranking is in the stem (`_win`), in the
  `# settings` line and in the NAME of the value column, and whichever is not
  ranked rides along beside it, reported and never cut on.
  - **THE DRIVER STILL MINIMISES — each game scores 1 for a LOSS and 0 for a win**,
    so the race ranks a LOSS rate and the standings report its complement. That is
    not presentation: `race_stats` is shared with the multiwordle race, and
    inverting at the source is what keeps it meaning exactly what it meant there.
    Everything the console and the elimination log SHOW goes through an opt-in
    `display` hook that defaults to the identity, so the multiwordle race is
    byte-identical (`checkmultiwordle.py` passes unchanged).
  - **THE PLUS-FOUR PROBLEM DOES NOT ARISE HERE, unlike in the sweep.** The cut is
    on the PAIRED difference of two indicators, which lives in `{-1, 0, 1}` and
    whose spread is set by how often two openers DISAGREE — not by how close
    either rate is to 1, which is exactly what `sqrt(p(1-p)/n)` loses at the
    ceiling. `race_stats.paired_error`'s docstring says so; it used to justify
    this by "the difference of two guess COUNTS", which stopped covering the case
    the moment a score could be an indicator.
  - **Under win-rate ranking the checkpoint carries an EXTRA accumulator** (the
    guess total, so the mean stays reportable — the mirror of `wins` under mean
    ranking). It is added ONLY in that mode, so a mean race's checkpoint format,
    and any halted mean race resuming into it, are untouched.
  - **MEAN GUESSES IS THE SECONDARY KEY under win-rate ranking** (added
    2026-09-17, user's call): fewest guesses among those winning equally often.
    Without it the "leader" is whichever tied opener the ranking file listed
    first — and at 100 games a quad field is **9637 of 10000 tied at exactly
    1.0000**, so that is nearly the whole field. The status line prints it beside
    the win rate (`leader covet gland shrub wimpy 1.0000 [mean 4.2050]`) and the
    standings order breaks the same way, so the file and the log agree.
    - **IT IS NOT PURELY COSMETIC, and that is worth knowing before quoting a
      cut.** The leader is the reference the paired difference is measured
      against, so a different leader among ties leaves every `md` unchanged (the
      means are equal, by definition of a tie) but MOVES the paired errors — the
      variance of a difference depends on which entry you difference against. So
      a few borderline openers can be cut that otherwise would not, and the
      reverse. The cut is equally sound either way; it is simply better justified
      against a leader that is best on a stated key than against an arbitrary one.
    - **OPT-IN in the shared driver** (`tiebreak=(live, n_games) -> array`,
      taking the game count so it can return a printable MEAN rather than a
      running total). The mean-ranked race passes none and is untouched, which
      the gate asserts by requiring `[mean ` never to appear in its output.
  - **A FREE ORACLE, asserted at every write**: the reported win rate comes from
    the driver's mean of the indicator, and `wins` from a tally of the raw guess
    counts against the same threshold — two independent routes to one number, and
    they must agree. It is what caught both mutations when the flag was built.
- **`--pair-adaptive N` WORKS IN THE RACE TOO** (added 2026-09-17, same session).
  It had been hardcoded to 0, which is a COMPARABILITY bug for multi-word fields:
  every quad/quint cascade here ran `--pair-adaptive 2`, so racing the same
  openings would have measured the BLIND strategy against a field the ADAPTIVE
  one had chosen, and the two numbers would look like one experiment. It builds
  the rule through `wordlesim.make_opening_rule`, so there is no third definition
  of it; it lands in the stem as `_adapt<N>` and in the settings line; and it is
  REFUSED beside `--second-from`, two rules for the same turn, exactly as the
  sweep refuses it. Gated by replaying the race's rule against wordlesim's game
  for game at N=0 and N=2, with coverage asserting N=2 actually changed games.
  - Gated in `checkwordlesim.py`: a win-rate race's value column is NAMED
    `win_rate`, the mean race's columns have not moved, an UNCUT race's every
    win rate and mean guesses equal the same games recomputed from `play_chunk`,
    a resume still changes nothing, and **coverage FAILS unless the two rankings
    actually ordered the field differently**.
- **`--fallback` is REQUIRED and `--second-from` is the other half of the
  strategy** — with a table every opener plays its own predetermined second word
  at the threshold, without one the opener is blind and the follow-up takes over.
  Both are in the filename, and a table with no row for an opener in the field is
  refused UP FRONT, so the `mystery` table cannot be raced over the 12972.
- **`tools/race_stats.py` IS SHARED WITH THE MULTIWORDLE RACE** — the paired
  difference, both standard errors, the block schedule, the pairwise switch and
  the cut. Those are the one thing two races must not define twice. **The LOOP is
  deliberately NOT shared**: multiwordle's has to amortise `minavg`'s per-opening
  turn-2 table and this one has no setup at all, so one loop serving both would be
  the § shared-helper failure rather than reuse. (Extracted 2026-09-10 and
  verified bit-identical to the pre-extraction functions over 200 random
  histories, with `checkmultiwordle.py` passing in full; the checkpoint format is
  untouched, so a race halted before it resumes into it unchanged.)
- **THE CHUNK SIZE IS A CHECKPOINT INTERVAL, NOT A PARAMETER OF THE ANSWER** —
  games are seeded by INDEX, so any chunking plays the same games in the same
  order. It is sized from the measured cost of the last chunk, since a field of
  12972 and a field of 3 want very different numbers, and the gate asserts a
  `--chunk 97` race equals a `--chunk 5` one.
- **MEASURED 2026-09-10: the first block — all 12972 openers x 100 games under
  the `answer` follow-up — takes 11 s and eliminates 2342 openers outright**,
  leaving 10630. **THE TAIL IS THE EXPENSIVE PART, not the field**: once two or
  three are left they play millions of games until one is 5 sigma clear (a
  300-opener test ran to 3.28M). `--max-games N` bounds that, and stopping early
  is fine — the standings are a real ranking of whatever has been played.
- **THE STANDINGS ARE SWEEP-SHAPED** (`word,trials,mean,stderr,…` plus the same
  `# settings` and `# lineage` lines), so `sweep_shortlist.py` and
  `paired_compare.py` read a race exactly as they read a sweep — a finished race
  can hand its survivors straight to a paired round.
- Data: standings + eliminations in `data/shared/wordlesim/race_*`, checkpoint
  and log under `data/local/wordlesim/`.
- **Gated in `checkwordlesim.py`**: the games are a function of (seed, game
  index) alone, regrowing the coin-flip array extends the same stream, the cursor
  reproduces its row, a chunk equals the same games played one at a time, and a
  resume, the pairwise switch and the chunk size all change nothing. Mutation-
  tested by seeding the games per chunk instead of per index.

### `guarantee` — does an opening reach 100%?  EXACT, not simulated
`math/guarantee.py` states the question and IS the source of truth;
`tools/guarantee_sweep.py` is the driver. Run it with
**`bash solver/run-guarantee.sh [--pool P] [--adapt N] --openings-from RANK.csv
--top N`** (from `math/`), attached, tee'd log, `--dry-run`, resumable per opening.
- **A 100% WIN RATE AND A GUARANTEE ARE THE SAME STATEMENT, which is the whole
  point.** Every reachable draw of the random follow-up has POSITIVE probability
  (it draws uniformly from a finite live set), so "probability 1" and "no
  reachable draw sequence loses" coincide. `wordlesim` ESTIMATES the first; this
  DECIDES the second — no seed, no standard error, and a re-run reproduces the
  file byte for byte.
- **IT IS NOT OPTIMAL PLAY, and the `max` is not a solver choosing well.** The
  follow-up is the SAME random rule the race measures; the maximum is over what
  it could unluckily DRAW. So it is not an `optturns`-family number either —
  those are optima over a solver that chooses — and **never table a worst case
  beside a wordlesim win rate or mean**, which AVERAGE over these same draws.
- **The recursion:** `L(S,a) = 1` if `S == {a}`, else `1 + max over g in S, g != a
  of L(S|g,a, a)`. It terminates because a word's reply against itself is
  all-green, so playing one always eliminates it. An opening's worst case is the
  largest `t + L(S,a)` over answers, `t` being how many opening words were
  actually PLAYED — so **`--adapt` changes the budget per ANSWER, not per opening**.
  Skipping `g == answer` is an OPTIMISATION, not the rule (mutation-verified inert).
- **THE POOL IS PART OF THE QUESTION and is never defaulted in the tool** (the
  wrapper carries a default a human reads). Under `custom` the follow-up can
  spend a guess on a word that could never be the answer — which is what a worst
  case is made of, and the whole difference from `mystery`. Pool, `--adapt` and
  the cap are all in the filename.
- **MEASURED 2026-09-17, and it explains the race exactly**: the race leader
  `clown derby fight vamps` has a **worst case of 7** and **3 of 2315 answers that
  CAN lose**, so it does NOT reach 100%. The witness is checkable by hand — the
  opening leaves `odder order rodeo` live with two guesses left, and drawing
  `rodeo` (1 in 3) separates nothing, leaving a coin flip. That predicts a loss
  rate near 7e-5; the race measured **0.999922**, one loss in 12800. The exact
  and sampled answers agree.
- **COST: 0.06 s per opening**, all 2315 answers — so 3230 openings is ~3 minutes
  and the full 100000-row quad ranking ~1.7 h, single-threaded.
- **`python3 tools/checkguarantee.py` is the GATE**: a reference that keeps live
  sets as LISTS OF WORDS, recomputes every reply FROM THE STRINGS and ENUMERATES
  the draws rather than recursing on a sub-matrix, diffed over openings x two
  `--adapt` settings x three caps; every witness line replayed from the strings
  (each draw live, ending on its answer); and a COVERAGE tally that FAILS unless
  guaranteed AND non-guaranteed cells both occurred and the adaptive rule
  actually shortened an opening. Mutation-tested (an off-by-one in the
  recursion, an inverted part filter, and `<` for `<=` in the adaptive threshold
  were each caught).
- Data under `math/data/shared/guarantee/`, log under `math/data/local/guarantee/`.

### `answerpairs` — pairs of ANSWERS ranked by how FEW words split them
`tools/answer_pairs.py` states the question and IS the source of truth. Run it
with **`bash solver/run-answer-pairs.sh [--pairs L] [--splitters L] [--top N]`**
(from `math/`), attached, tee'd log, `--dry-run`. Exact and deterministic — no
sampling, no seed — so a re-run reproduces the file byte for byte.
- **THE QUANTITY** (user's, 2026-09-18): for every unordered pair `(a, b)` of
  words from the PAIR list, count the SPLITTER-pool words `g` with
  `pattern(g, a) != pattern(g, b)`, and rank **ASCENDING** — fewest splitters
  first, so the head is the pairs the follow-up can least often separate.
- **IT IS THE INVERSE OF EVERY OTHER RANKING HERE.** The rest of the repo scores
  a GUESS by what it does to the answer set; this scores a PAIR OF ANSWERS by
  how much of the pool can resolve it. A row is a property of two answers, not
  of an opener — never table it beside a singleton count, an ssq, a max bucket
  or an `optturns` total.
- **WHY IT BEARS ON THE GUARANTEE.** An answer is UNSOLVED exactly when some
  live pool word fails to fully split it, so a pair with few splitters is the
  raw material a fatal bucket is made of. This says which pairs those are
  BEFORE an opening is chosen, which no opener-side screen can do.
- **THE FLOOR IS 2 WHENEVER BOTH WORDS ARE IN THE POOL, and it is forced, not
  conventional**: a word replies all-green to itself and never to a different
  word, so each of the two splits the pair. `custom.txt` contains every answer,
  so under the default pools nothing can score below 2 — and a pair AT 2 is
  separated by nothing except naming one of them outright.
- **TWO LISTS, TWO ROLES, NEITHER DEFAULTED IN THE TOOL** (the greens scar; the
  wrapper carries defaults a human reads). `--pairs` must be a subset of the
  2315 (they are matrix COLUMNS); `--splitters` must be legal guesses (ROWS).
  Both are in the filename. `custom` is the wrapper default because it is the
  pool the random-compatible follow-up draws from; `guess` asks the same
  question of a player who knows all 12972.
- **NO NEW MATRIX** — splitters are a subset of the 12972 rows and pair words a
  subset of the 2315 columns, so it is a sub-block of the DEFAULT
  `patterns.npy`. It does not want `--full`.
- **The count is ONE COMPARISON DOWN A COLUMN**, not a bucketing: two columns
  differ in exactly the rows whose word separates them. Done one column at a
  time because the `(n, n, m)` broadcast would be 23 GB at the real sizes.
- **THE GATE IS BUILT IN and always runs**, in two halves that catch different
  things: sampled pairs are recomputed FROM THE STRINGS with `wordle.pattern`
  (and checked symmetric), and the floor of 2 is checked over EVERY pair.
  MUTATION-TESTED — reversing the column index map PASSES the floor check (it
  permutes the same multiset of counts) and is caught by the string check, which
  is why both exist.
- Data under `math/data/shared/answerpairs/` with a `.meta` sidecar recording
  `scored`/`written`/`complete`, log under `data/local/answerpairs/`.

### `hillclimb` — random starts, improved by SWAPPING WORDS
`math/hillclimb.py` states the rule and IS the source of truth;
`tools/hill_climb.py` is the driver. Run it with
**`bash solver/run-hill-climb.sh -t N [--candidates L]`** (from `math/`),
attached, tee'd log, `--dry-run`.
- **TWO OBJECTIVES, AND THEY ARE DIFFERENT QUANTITIES over the same openings —
  never put their numbers in one table** (`--objective`, user's call,
  2026-09-19). **`guarantee`** minimises the answers a random tail can be made
  to LOSE and wants zero; **`singles`** maximises the answers a reply names
  OUTRIGHT, which is what `data/shared/singletons/` ranks by. A guaranteed
  opening need not be singleton-rich, or the reverse.
  - **THE CLIMB IS OBJECTIVE-AGNOSTIC**: it takes `last_level(prefix)` as an
    injected callable returning two arrays over the candidates, both MINIMISED
    lexicographically. `guarantee` passes `(unsolved, ssq)`; `singles` passes
    **`(-singles, ssq)`**, negated because the climb only knows how to go down,
    and only the printout and the CSV turn it back the right way up. Nothing in
    the climb knows which is running, which is what keeps one climb and not two.
  - **THE OBJECTIVE IS REQUIRED BY THE TOOL AND DEFAULTED ONLY IN THE WRAPPER**
    (`guarantee`, a default a human reads — the greens scar). It LEADS the
    filename (`climb_…` keeps the historical name, `singles_…` is the new one,
    so no committed file is renamed), it is in the `# settings` stamp, **the
    value column is NAMED after it**, and a run REFUSES a file written under
    the other one.
  - **`--cap` APPLIES ONLY TO `guarantee`.** A singleton is a property of the
    partition with no tail to budget, so the "cap leaves no guesses" refusal is
    gated on the objective — otherwise a SIX-word opening in a six-guess game,
    a perfectly ordinary singles question, would be refused.
  - **`last_level_singles` REPRODUCES THE COMMITTED RANKINGS EXACTLY**, which is
    the oracle that matters: `laten` 41, `clint soare` 642 / ssq 10115,
    `blind chapt morse` 1725 / 3343, `bandy chimp fogle wurst` 2210 / 2437 —
    and each also matches a recount FROM THE STRINGS. Buckets are over the
    POOL and the count over the ANSWERS, so `--pool mystery` is the classic
    metric and `--pool custom` asks what `--buckets custom` asks.
  - **IT IS MUCH CHEAPER THAN `guarantee`** — no budget, no look-ahead, no
    recursion — so it runs at any opening size where the other does not.
  - **`singles_of` PRICES ONE OPENING; `last_level_singles` PRICES THE WHOLE
    POOL. Using the second for the first is a defect, not a slow path**: the
    pair and triple sections score thousands of moves per scan, and the
    whole-pool pass costs **21000x** what the single bucketing does (5.0 s
    against 0.24 ms, measured). Same numbers, verified against both the pass
    and the committed values.
  - **A SECTION WIDER THAN THE OPENING IS DROPPED, not run empty** —
    `anagram3` on a 2-word opening has no position triple to pick, and a
    totals line claiming it ran would be a lie. The banner filters the same way.
  - **The per-trial gate is PER OBJECTIVE**, since each needs an oracle sharing
    no machinery with the fast path: `guarantee` against
    `guarantee_sweep.check_opening`, `singles` against a recount from the
    STRINGS that buckets every answer by its tuple of replies with no matrix,
    no joint key and no candidate grouping (~14000 `pattern` calls, so free).
- **THE SEARCH** (user's, 2026-09-18): draw `k` random words; repeatedly take
  the single-word swap that lowers UNSOLVED the most; stop when none does; do
  that `-t` times from fresh random draws. Every accepted swap PRINTS, because
  it is the only thing that happens — the scan between two swaps is seconds of
  silence.
- **IT IS A LOCAL OPTIMUM, NOT AN OPTIMUM.** A climb stops where no SINGLE swap
  helps; two words might have to change together and this never tries that. So
  a result is "the best of `-t` random starts, each climbed until one-word moves
  run out" — never "the best opening". **The restarts are the only thing
  exploring**; the climb itself is greedy and deterministic given its start.
- **IT NEEDED NO NEW SCORER, and that is the reason it is affordable.** A blind
  opening is a SET, so "swap the word at position i" IS "hold the other k-1
  fixed and choose the last word" — which `paircover.last_level_scores` already
  answers for EVERY candidate in one pass. A neighbourhood scan is therefore `k`
  calls to it rather than `k * ncand` separate evaluations. MEASURED: a 4-way
  scan over custom's 4282 is 5-8 s, and a whole trial 60-90 s.
- **STEEPEST, not first-improvement**: all k positions are scanned before
  moving, so a printed step means "the best move available" rather than "the
  first one found".
- **FOUR SECTIONS, IN ORDER, each run to exhaustion, AND THEN ROUND AGAIN
  FROM THE FIRST until a WHOLE PASS moves nothing** (user's, 2026-09-18):
  single-word swaps; then PAIR swaps for a pair with the SAME letters; then
  pair swaps for a pair within ONE LETTER of the same letters; then TRIPLE
  swaps for three words with the same letters. Each later
  section can only move where the earlier one is stuck, which is the point —
  **the survivors of a one-word climb are near-anagram families** (`odder /
  order / rodeo`, `brags / grabs / grass / grays`) and separating those needs
  two words to change TOGETHER, which no one-word neighbourhood can do.
  - **MEASURED and it earns its keep**: a trial that stalled at **15** unsolved
    after 3 single-word swaps went to **10** and then **8** on two `anagram+1`
    moves. The exact-anagram section found nothing on that trial (`swap 3,
    anagram 0, anagram+1 2`) — within `custom` an exact pair anagram is rare.
  - **THE LOOP IS WHY THE SECTIONS ARE NOT ENOUGH ON THEIR OWN, and it is a
    scar.** A pair move REOPENS single-word swaps, so running each section once
    leaves improvements on the table BY CONSTRUCTION — measured on a real
    trial, a one-pass climb stopped at `payed tombs flung wreck` / 11 unsolved
    with `payed -> vapid` (10) sitting one swap away. It also made the per-trial
    gate below assert something false, and **the fix was the loop, not the
    check**. A section that moves invalidates every earlier section's "nothing
    helps", so the only sound stopping rule is a full barren pass.
  - The `steps` column now leads with `rounds N` and its per-section counts are
    SUMMED over rounds; every printed move is tagged `r<N>` and its section.
  - **`anagram3` IS CHEAPER THAN `anagram+1`, which the names do not suggest**
    (measured on custom's 4282, per scan): **372-2160 triple-exact moves
    against 1680-5775 pair-within-one**, so **1.6-9.4 s against 7.3-25 s** at
    4.3 ms a score. ENUMERATION is free either way (0.02-0.04 s) — what a
    section costs is what it SCORES, which is the number to price a new one by.
  - **Triple-exact CONTAINS pair-exact** (leave one of the three unchanged and
    the other two are an exact pair anagram), so `anagram` is redundant once
    `anagram3` exists. It stays because at 9-44 moves it is free and it fires
    first, which keeps the cheap move cheap.
  - **ONE GENERATOR AND ONE DESCENT FOR EVERY NON-SWAP SECTION**: `set_moves`
    (any size, any width) and `climb_moves`. `pair_moves`/`climb_pairs` are the
    size-2 front ends, kept because that is the shape the gate reads. A new
    section is a row in `SECTIONS` — `(label, size, within)` — not an edit to
    the loop.
  - **THE TARGET MUST STAY int16, AND GETTING THIS WRONG IS SILENT.**
    `anagram_index` keys on `C[i].tobytes()`, so a target promoted to int64 —
    which `C[rows].sum(axis=0)` does BY DEFAULT — hashes to a signature nothing
    matches and the section finds **NOTHING** while still passing every check
    that only looks at the moves it did emit. `set_moves` adds the rows one at
    a time for that reason. MUTATION-TESTED: the promotion takes `anagram3`
    from 398 moves to 0 and is caught by the completeness oracle below.
  - **`climb_all` OWNS the loop** (in `hillclimb.py`, the source of truth) and
    takes the pair widths as a tuple, so a new section is an extra width rather
    than an edit to the loop. It also cross-checks each round for free: the
    swap section re-derives the opening's score with `last_level_scores` and
    REFUSES to continue if it disagrees with what the pair sections reported
    through `greedybuild.score` — two implementations, one integer.
  - **COST: ~350 s a trial against ~70 s for swaps alone**, so the pair
    sections are most of the time. The `steps` column records the breakdown per
    section rather than one number, which is what says whether a section is
    earning it.
  - **The letters are a MULTISET** (`grass` is two s's), and the subset test is
    vectorised over all candidates at once — a Python loop per target is what
    makes the within-one neighbourhood (up to 260 targets per position pair)
    unaffordable.
- **THE BUDGET IS `cap - words`, WHICH IS WHAT MAKES `--words 3` A DIFFERENT
  QUESTION RATHER THAN A FLAG** (2026-09-18). Four blind words in a six-guess
  game leave TWO guesses, and every fast predicate here was written for exactly
  that: "every live word isolates the answer" IS one look-ahead. Three words
  leave THREE, so solved means `worst_case(S, a) <= 3`, which no rearrangement
  of the one-pass form expresses.
  - **THE GATE CAUGHT THIS RATHER THAN THE TOOL REPORTING A WRONG NUMBER.** Run
    at `--words 3` before the fix, the climb scored 551 unsolved where
    `guarantee_sweep` said 214 losing, and the per-trial cross-check refused the
    trial. Two implementations of one number, and that is the whole reason the
    cheap one is checked against the slow one every trial.
  - The budget threads through `greedybuild.solved_in_bucket`,
    `paircover.unsolved_in_bucket`/`prefix_buckets`/`last_level_scores` and the
    climb. **At budget 2 the fast paths still run**, so every committed quad
    result is reproducible bit for bit — VERIFIED on `craps until often fjord`
    385, `chubs delft grown vampy` 0, `caved forms plunk wight` 3 and
    `ledge pawns rocky thumb` 1.
  - **`guarantee.solved_within` IS THE DECISION FORM, AND ASKING FOR THE VALUE
    INSTEAD WAS THE MISTAKE.** `worst_case` returns the exact number, so it
    recurses until every branch bottoms out; nothing here ever wanted more than
    "does it exceed the budget". MEASURED: the exact walk did **not finish in
    eight minutes** on one whole-pool pass at budget 3, against 141 s for the
    capped one. Gated as `solved_within(S, a, b) == (worst_case(S, a) <= b)`
    over 4210 checks on reachable buckets, both outcomes asserted.
  - **`|S| <= budget` IS AN EARLY EXIT AT EVERY LEVEL, not just the top** — the
    same bound `prefix_buckets` prunes on, since every wrong draw eliminates at
    least the word drawn. Worth ~15% here; the size bound at the TOP is worth
    far more.
  - **MEASURED COST, AND IT IS THE SWAP SECTION THAT HURTS**: a whole-opening
    score is 0.01 s at budget 2 and 0.02-0.08 s at budget 3, so the pair and
    triple sections barely move — but ONE whole-pool pass is **0.8 s against
    73 s**. A 3-word opening fixes only two words, so the live buckets go from
    max 16 to **max 136** (207 buckets holding 2860 pool words, median 8), and
    the candidate-grouping collapse that makes the quad pass cheap stops
    collapsing. A swap scan is `k` passes, so ~3.6 minutes, and a trial is tens
    of minutes against ~6 for a quad.
  - **PROFILE FIRST: the cost was the PREDICATE, not the grouping.** Counting
    rather than guessing gave 20904 distinct candidate partitions and 23406
    predicate calls at budget 2, against **187568 and 358459** at budget 3 —
    9x and 15x more — while the grouping and splitting itself is only 2.1 s of
    the pass. So it is both more calls AND, at 390 us against 34 us, slower
    ones.
  - **`_unsolved3` VECTORISES THE TWO-PLY PREDICATE, and it is worth 2x, not the
    10x first guessed.** Same shape as the budget-2 form one ply deeper: with
    `A[g, h] = h is still live after drawing g`, the company left for `(g, h)`
    is `(A @ A.T)[g, h]`, so the whole question is one einsum over every answer
    at once. 141 s to 73 s. **It stops there because the remaining cost is
    per-call numpy OVERHEAD across 358459 calls of mean size 9.9**, not
    arithmetic — beating that needs batching across parts, which is a real
    rewrite of `last_level_scores`. Gated against `solved_within` on 597 real
    parts with both outcomes asserted; `SMALL_BUCKET3 = 32` caps the O(s^4)
    form and the tail falls back to the recursion.
- **`--workers N` RUNS WHOLE TRIALS IN PARALLEL, and changes NOTHING but the
  order lines appear in.** Trials are seeded by INDEX (`seed + trial`), so the
  result is independent of the worker count — which is what makes the parallel
  path checkable rather than merely faster. Step lines still print live,
  through a queue, each tagged with its trial.
  - **SPAWN, NOT FORK** (macOS default): each worker builds its own state in an
    initializer and holds its own 168 MB matrix. Budget for that before raising
    the count.
- **`python3 tools/checkhillclimb.py` is the GATE**, and it runs on a SMALL
  candidate list so a whole trial is seconds — what it checks does not depend on
  the candidate count, and a gate nobody can afford to run is not a gate. It
  verifies every move's letter relationship FROM THE STRINGS (exact at
  `within=0`, one substitution at `within=1`, pairs AND triples), with
  **coverage asserted per section**, and that `--workers 1` and `--workers 3`
  agree trial for trial on the opening AND the score.
  - **THE COMPLETENESS ORACLE IS THE OTHER HALF, and it is the one that catches
    a MISSING move.** The letter check can only fault a move that was emitted;
    this diffs `set_moves` against a BRUTE FORCE over every tuple of candidates,
    keeping those whose letters are within the bar — `collections.Counter` over
    the word STRINGS, no letter matrix, no `near_targets`, no `splits_into`.
    Exact agreement is required, and **coverage is asserted** because two empty
    sets agree trivially. Sizes are priced separately (`C(n, 3)` per
    position-triple), so the triple oracle runs on 100 candidates and the pair
    ones on 300.
  - **It iterates `SECTIONS`**, so a section added there is covered by existing
    rather than by anybody remembering to extend a list in the gate.
- **THE GATE RUNS ON EVERY TRIAL and both halves are free**: the climb must END
  at a local optimum of the SINGLE-WORD neighbourhood (the stopping scan is
  re-checked), and the reported unsolved must equal
  `guarantee_sweep.check_opening`'s losing count for the same opening — a
  different implementation reached a different way, at 0.06 s. **The first half
  is a real assertion ONLY BECAUSE the sections loop** — without the loop the
  last section run is a pair section, so a one-word swap can legitimately be
  available at the end and the check fires on a correct climb.
  - **IT CAUGHT A REAL DEFECT ON ITS FIRST RUN, and the defect was a LOOSE
    CONTRACT.** `neighbourhood` returned the best swap whether or not it
    improved, so "not None" did not mean "can still improve". The climb compared
    for itself and was correct; the GATE asked the function the question its
    docstring claimed to answer and got the wrong answer, failing on a climb
    that had stopped correctly. `current` is now a PARAMETER and the function
    returns None when nothing beats it. **One caller compensating for a loose
    contract is how the next caller gets it wrong.**
- Data under `math/data/shared/hillclimb/`, log under `data/local/hillclimb/`.
  Each (pool, candidates, words, cap, seed) is a different experiment with its
  own file, and **the SEED IS IN THE FILENAME — advance it for a new batch**,
  or the same trial INDEXES are replayed and appended a second time.
- **THE CSV STAMPS ITS SECTIONS (`sections=swap;2x0;2x1;3x0`) AND A MISMATCHED
  APPEND IS REFUSED** (added 2026-09-18 with `anagram3`). A row's `unsolved` is
  exact and search-independent — `guarantee_sweep` agrees with it — but a FILE
  is a record of what a search FINDS, so two searches in one file make it a
  record of neither. The stamp is `(size, within)` per section, which IS the
  definition, so it cannot drift from the labels.
  - **A MISSING `sections=` IS AN OLD FILE, NOT A MATCH**, and is refused with
    that said explicitly — the same lesson as `parents_complete=`. The two
    committed seed-0 files (`climb_custom_w4_s0.csv`, 171 trials, and
    `climb_custom-from-guess_w4_s0.csv`, 82) predate the field and are
    therefore refused rather than silently extended. **They hold the
    all-words `calmy pownd verbs fight` at 1 unsolved**, which is worth keeping.

### `paircover` — cover the hard pairs, harvest the failures, repeat
`math/paircover.py` states the rule and IS the source of truth;
`tools/pair_cover.py` is the driver. Run it with
**`bash solver/run-pair-cover.sh -k K --rounds N`** (from `math/`), attached,
tee'd log, `--dry-run`. Exact and deterministic — no sampling, no seed.
- **THE POOL AND THE CANDIDATES ARE TWO DIFFERENT LISTS** (user's call,
  2026-09-18). `--pool` is what the opening PARTITIONS and what the random fifth
  guess DRAWS FROM, so it is what `unsolved` is measured over and it must
  contain every answer. `--candidates` is only which words the four may be BUILT
  FROM: it need not contain the answers, need not be the pool, and widening it
  cannot change what the objective MEANS. It defaults to the pool, which is how
  this ran before the split, and both are in the filename
  (`cover_<pool>-from-<candidates>_...`).
  - **`--candidates guess` is the interesting one**, because the same asymmetry
    showed up in the quad screens: the all-words L19 quads reached **1** losing
    answer where the custom-restricted ones bottomed out at **5** over a million
    openings.
  - **TWO MATRICES, AND THEY ARE NOT INTERCHANGEABLE.** `cand_matrix` is
    candidate-by-pool and says how an opening SPLITS the pool; `pool_matrix` is
    pool-by-pool and says what the follow-up sees once it is INSIDE a bucket.
    The `harvest` recursion lives entirely in the second, because every word of
    a live set is a pool word — a candidate outside the pool can split a bucket
    but can never be in one.
  - **VERIFIED INERT when the lists match**: with `--candidates custom` against
    the same pool, round 1 reproduces `chomp fudge blink warts` / 27 unsolved
    byte for byte. And the gate re-runs the three-way losing-answer agreement
    with a WIDE candidate list, asserting that it actually used words outside
    the pool — an index-space slip between the two lists is exactly what that
    catches, and the equal-lists case cannot reach it.
- **THE LOOP** (user's, 2026-09-18), one round: score every candidate by the
  WEIGHTED pairs it splits; build an opening of `--words` words, recursing into
  the K best at each step; rank the finished openings by UNSOLVED ANSWERS;
  harvest the pairs that opening actually failed on; add them with a count;
  print, flush, go again. **The count IS the weight** (user's call), so a pair
  that has failed five rounds counts five times in the next ranking.
- **IT IS CONSTRAINT GENERATION, not a ranking.** The pair set is the hard
  constraints found so far and each round adds the ones the last opening
  violated, so the search is steered by its own failures rather than by a fixed
  screen. That is the thing no opener-side ranking can do.
- **THE SEED IS SCAFFOLDING FOR ROUND 1 ONLY** (user's call, 2026-09-18 — the
  first build got this wrong and kept it). The first harvest REPLACES the seeded
  pairs rather than joining them: the seed is the hardest-pairs PROXY and it
  over-demands, while a harvested pair is by construction a set that ran out of
  budget with company. Carrying the seed on keeps spending coverage on
  constraints that may not exist. A RESUMED run is already past that point and
  never re-seeds. Gated end to end through the real `main()` and
  MUTATION-TESTED (merging instead of replacing leaves 754 rows where 158 were
  harvested, and is caught).
  - **KNOW WHAT THIS DOES TO THE EARLY ROUNDS.** The set restarts TINY — 34
    pairs after a 1000-pair seed, measured — so coverage separates almost
    nothing, the ssq tie-break does most of the work, and the objective wanders
    before the set is big enough to bite: MEASURED at k=3, `29, 41, 25, 106`
    over four rounds against `29, 25, 18` when the seed was (wrongly) retained.
    It also costs TIME in exactly those rounds, since a huge tied group is what
    ssq then has to price — 26 s against 1 s. Judge the loop on where it gets
    to, not on round 2.
- **TWO OBJECTIVES AND ONLY THE SECOND IS THE ANSWER.** Coverage picks the
  WORDS; `unsolved` ranks the finished openings. Never quote a coverage score as
  a result.
- **COVERAGE IS SUFFICIENT BUT NOT NECESSARY, which is the proxy's one real
  imprecision.** A bucket of exactly TWO is SAFE — the follow-up draws one, and
  a wrong draw leaves exactly one word for the last guess — so the damage starts
  at THREE and the seeded "hardest pairs" over-demand. The HARVESTED pairs carry
  no such slack: they are exactly the sets that ran out of budget with company.
- **A HARVESTED PAIR IS (ANSWER, POOL WORD)**, not (answer, answer): the words
  standing beside a losing answer come from the whole pool, and one that could
  never BE the answer is still a way to lose. The seed is answer-by-answer,
  which sits inside that space, so the two compose with no conversion.
- **THE PRECISE FAILURE, not the whole bucket.** The pairs recorded are `(a, x)`
  for the `x` still standing when the budget runs out, unioned over every
  witnessing draw — not every other member of the bucket, most of which the
  opening DID separate. Recording the bucket whole fills the set with non-
  failures and steers the next round at nothing; that is MUTATION-TESTED and the
  gate names the offending pairs.
- **`--search branch|beam`**, the same two searches `greedybuild` carries and
  the same distinction. **BRANCH** (the default) recurses into the K best at
  every state: `k ** words` complete openings. **BEAM** carries K states
  forward and pools their children: `k * k` openings, so a MUCH wider K for the
  money — at k=20 that is 400 against 160000.
  - **STATES ARE RANKED BY WEIGHT COVERED SO FAR**, which is the one quantity
    comparable ACROSS beam states: each carries its own set of still-unsplit
    pairs, so their per-candidate coverage scores are on different scales, but
    "weight removed since the start" is not. Ties on ssq.
  - **THE SELECTION IS NESTED, NOT TOP-K OVERALL** — slot `i` from the children
    of slots `0..i` — which is what keeps it monotone in K. Plain top-K is not,
    and `greedybuild` MEASURED a k=2 worse than its k=1 before the same fix.
    Gated: the beam EQUALS branch at k=1 (both the single greedy path, a free
    oracle across two traversals) and is monotone, MEASURED `236, 54, 45` over
    k=1,3,9.
  - **THE TWO HAVE DIFFERENT LEAF COUNTS and the cost line must say which**:
    quoting branch's `k ** words` for a beam over-states it by orders of
    magnitude. MEASURED at k=20 with a real weight set: 13 s a round.
- **A SEARCH NARRATES ONLY ONCE IT IS SLOW (`--progress`, default 15 s).** One
  flag has to serve two very different shapes — a generator does thousands of
  FAST rounds and a wide beam does a few SLOW ones — so nothing extra is printed
  until a search has already run that long, and then at most one line per
  interval. A quick round stays quiet; a long one explains itself. The BEAM
  reports per level (pooled, kept, share of the weight covered) and then its
  progress through the final scoring; BRANCH reports nodes, complete openings
  and the best unsolved so far.
  - **`st["tick"]` IS OPTIONAL, not required** — the gate constructs a minimal
    `st` and is a legitimate caller, so the search defaults it to a no-op rather
    than raising. It shipped required once and the gate died with `KeyError`.
- **`--once` IS ONE SEARCH, AND IT IS A DIFFERENT JOB FROM THE LOOP** (user's
  call, 2026-09-18). The ROUNDS are constraint GENERATION — harvest, fold in,
  search again — and they only do anything because the harvest moves the
  weights; the search itself is deterministic, so with a fixed set round 2
  repeats round 1 but for the handful of pairs just added. `--once` is
  EXPLOITATION: run a wide search on a weight set someone else generated,
  report, and change nothing. It writes NO pair file, so the set handed in stays
  exactly the input, and the stem ends `_once`.
  - It still PRINTS what the opening failed on, with the weight each pair came
    in carrying — that is the other half of the result, and it is what says
    whether the search is hitting known constraints or new ones.
  - **The natural division of labour**: generate with a cheap `k` over thousands
    of rounds, then exploit with `--search beam --once` at a large `k`.
- **`--pairs-from FILE` STARTS FROM ANOTHER RUN'S WEIGHTS, AND KEEPS THEM**
  (user's call, 2026-09-18). Any `word1,word2,count` file does — it is the
  format this loop writes, so runs compose. **These are NOT dropped after round
  1**: the seed-drop rule exists because the hardest-pairs seed is a PROXY that
  over-demands, and a harvested set with earned counts is not. Precedence is
  resume, then `--pairs-from`, then the seed.
  - **THE WEIGHT SOURCE IS A BOUNDED TAG IN THE STEM, NOT A NESTED NAME**
    (`_w<8 hex of the path>`). Folding the source's own stem in grows the name
    ~40 characters per generation, which is the scar that killed a wordlesim
    cascade at macOS's 255-byte limit — and a weight set is exactly the thing
    that gets chained. The full path is in the header and in the rounds CSV's
    `source=` field, which is where lineage belongs.
- **BRANCH IS THE DEFAULT** (user's call), matching `greedy_build.py` and every other
  `--topk` here. **It must be the K BEST, not the K TIED AT THE TOP** — selecting
  only among candidates sharing the maximum meant a single decisive coverage
  word left nothing to branch on and every K returned the identical opening.
  Caught by the gate's monotonicity check on its first run. Ties break on ssq,
  priced only for the group STRADDLING the cut, so a decisive choice is free and
  a flat one still gets a real second key instead of the lowest index.
- **`--final-top` GIVES THE LAST WORD A WIDER SHORTLIST THAN THE OTHER LEVELS,
  AND THE DEFAULT IS 0 — NO SPECIAL CASE AT ALL** (user's call, 2026-09-18). `0`
  gives the last word the same K as every other level; `N` takes the N best by
  coverage; **`all` is EXHAUSTIVE**, every candidate ranked by the real
  objective. Monotone across all four, each a superset of the one above, and
  gated as such: MEASURED at k=2, unsolved `115, 54, 41, 18` over k, 20, 200,
  exhaustive.
  - **WHY 0 RATHER THAN A SHORTLIST, in the user's words: a wider shortlist at
    the last level "is just increasing k for one level", not a different
    design.** It shipped as 100 described as a "middle ground" between coverage
    and the objective, which it was not — coverage still chose the word.
  - **THE EXHAUSTIVE LEVEL IS OPT-IN, and that is also the USER'S CALL after
    running both: it is not worth its slowdown.** It finds strictly better
    openings — that is what monotone means — but not enough better per second at
    the K they work at. Do not quietly make either non-zero value the default.
  - **"GO BACK TO WHAT WE HAD BEFORE" WAS AMBIGUOUS AND WAS READ WRONG ONCE** —
    as the 100-shortlist rather than as the no-special-case default that
    predated the whole flag. When a revert has two readings, ASK which.
- **`last_level_scores` PRICES THE WHOLE POOL IN ONE PASS — MEASURED 0.9-2.2 s
  against 48 s one at a time (22-52x), exact on unsolved AND ssq.** It is what
  `--final-top all` runs on, and it is worth reading before anyone prices a
  last-level idea again, because two things in it are the reason the exhaustive
  form is affordable at all:
  - **THE PREFIX IS FIXED, SO THE BUCKETS ARE.** A final word only REFINES the
    partition the first N-1 words made, so only buckets of size >= 3 holding an
    answer are in play — MEASURED 386 of 2296, holding 47% of the pool.
    **A bucket of TWO is ALWAYS solved, and that wants proving rather than
    assuming**: the follow-up draws one of the pair, drawing the answer wins,
    and drawing the other replies non-green, eliminating it and leaving exactly
    one word to name. So `worst_case = 2`, inside a budget of 2, whatever the
    last word does.
  - **CANDIDATES GROUP BY THE PARTITION THEY INDUCE, NOT BY THEIR REPLIES.** The
    pattern codes are labels; what matters is which members a word puts
    together. A bucket of three has only **five** possible outcomes (Bell(3))
    however many candidates exist, so thousands collapse onto a handful each
    priced once. Keying on raw replies leaves most of the saving on the table —
    measured 11x that way against 39x this way. The key packs one bit per member
    PAIR, exact to size 11, with a raw-row fallback above.
  - **GATED AGAINST `greedybuild.score`** on 120 candidates a run, which prices a
    whole opening from scratch and shares none of the bucket reuse.
- **A SCAR ABOUT PRICING, worth more than the flag it came from.** The shortlist
  first shipped described as a "middle ground" between coverage and the real
  objective. It was not one — it was `k = 100` at the last level, with coverage
  still choosing the word — and the "too expensive to do it properly" that
  justified it was **pricing the implementation, not the design**: the quoted
  45 s was `greedybuild.score` rebuilding the whole 4282-word partition once per
  candidate. Both caught by the user. **Price the idea against a fit
  implementation before calling it unaffordable** — and then let the user decide,
  which here went the other way anyway, on real numbers rather than on mine.
- **ALMOST NOTHING COLLAPSES IN THE MEMO HERE, unlike `greedybuild`.** There the
  order of placements does not matter, so paths converge; here the candidates
  offered at each level DEPEND on the level above, so different paths reach
  different sets. MEASURED: 81 paths gave 81 distinct openings at k=3. Price a
  run as `k^(words-1) x final_top` leaves, not less.
- **THE HEADER'S COST LINE IS A ROUGH GUIDE AND SAYS SO — it is NOT a bound in
  either direction.** It times one last level at startup, but on a RANDOM
  prefix, and the search's own prefixes shatter the pool far better, which makes
  their last levels cheaper. MEASURED, three consecutive k=2 rounds against a
  104 s projection: **35 s, 8 s, 42 s**. An earlier version called it a floor;
  round 2 disproved that.
- **MEASURED 2026-09-18**: at k=3, 4 words, 1000 seeded pairs, a round is **~1 s**
  (120 nodes, 81 complete openings) and three rounds ran 29 → 25 → **18**
  unsolved. Leaves are `k^4` before the word-set memo collapses orderings, so
  k=10 is ~10000 leaves and k=20 ~160000 — pick K from that.
- **EVERY ROUND IS FLUSHED and the pair file is written atomically**, so a
  Ctrl-C keeps the set and every round played; re-running the same command
  CONTINUES from the file rather than re-seeding.
- **A LIVE CROSS-CHECK RUNS EVERY ROUND**: the harvest's losing-answer count must
  equal the objective's `unsolved`, two routes to one number, and the round dies
  rather than reporting if they differ.
- **`python3 tools/checkpaircover.py` is the GATE**: the split matrix against
  `wordle.pattern` from the STRINGS; the losing answers THREE ways (the harvest,
  `greedybuild`'s objective, `guarantee_sweep.check_opening`) agreeing on the
  count AND the words; every harvested pair replayed from the strings (same
  bucket, and some live draw failing to separate them); and branch monotonicity
  with coverage ASSERTED — it fails if a wider K never changed the answer.
- Data under `math/data/shared/paircover/` (`<stem>_pairs.csv`,
  `<stem>_rounds.csv`), log under `data/local/paircover/`.

### `greedybuild` — build an opening LETTER BY LETTER, against the real objective
`math/greedybuild.py` states the rule and IS the source of truth;
`tools/greedy_build.py` is the driver. Run it with
**`bash solver/run-greedy-build.sh -k K [--nwords N]`** (from `math/`), attached,
tee'd log, `--dry-run`. Exact and deterministic — no sampling, no seed.
- **THE CONSTRUCTION** (user's, 2026-09-18): start with N blank words (5N empty
  slots); at each step consider every (letter, slot) placement, keep the LEGAL
  ones, score them, take the best; repeat until full. **LEGAL** = the word
  receiving the letter can still be COMPLETED to a pool word, so a half-built
  word is always a prefix-pattern of something real.
- **IT REACHES OPENINGS THE SCREEN CANNOT.** `run-singles.sh` builds a quad by
  extending pairs that scored well, so an opening whose two-word PREFIXES look
  mediocre but whose four words combine well is unreachable by it. This never
  commits to a whole word.
- **THE OBJECTIVE IS THE GUARANTEE CONDITION, NOT A PROXY.** An ANSWER is
  UNSOLVED when some live pool word fails to fully split it — exactly
  `guarantee.worst_case(S,a) > 2`, i.e. the follow-up can draw a word at guess 5
  and still be choosing at guess 6. **VERIFIED END TO END**: `craps until often
  fjord` scores 385 unsolved here and `guarantee_sweep` independently reports
  385 losing.
  - **Two lists, two roles**: buckets are over the POOL the follow-up draws from
    (custom's 4282); the count is over the ANSWERS (2315).
  - **`--adapt` is irrelevant to this count** — abandoning the opening only ever
    fires when the live set is already ≤ 2, where the answer was solved anyway.
    MEASURED: adapt 0 and adapt 2 both give 385 for that opening.
- **TIES BREAK ON SUM OF SQUARES (user's call), AND THAT IS NOT A DETAIL.** For
  the first several placements almost nothing is split, so `unsolved` is pinned
  at every answer and the TIE-BREAK is choosing the whole construction.
- **A HALF-BUILT WORD IS SPELLED WITH `_`, which is the REAL feedback function
  on a real string** — `wordle.pattern` gives `_` grey everywhere (never green,
  in no answer, and it does not consume a spare copy), so placed letters get
  ordinary treatment and blanks are a constant column. No second feedback rule.
- **TWO SEARCHES, AND `--search` IS REQUIRED** (user's call, 2026-09-18 — keep
  both). They are different questions, not two speeds of one, and the name is in
  every filename.
  - **`branch` — RECURSE INTO THE K BEST at every step**, which is what `--topk`
    means everywhere else here (`strturns`, `greens`, `wturns`, `mmturns`,
    `ultraturns`, `secondexact` all say it). K=1 is the leftmost path of the K=2
    tree, so **a wider K contains a narrower one BY CONSTRUCTION and can never
    return worse**. Cost is exponential in the placements, tamed only by
    MEMOISATION on the state — and that works, because the ORDER of placements
    does not matter, so huge numbers of paths converge. MEASURED on a 2-word
    opening (10 placements): k=1 is 10 nodes / 1s / 2032 unsolved, k=2 is 812
    nodes / 472 states / 6s / 1765, k=3 is 10160 nodes / 4579 states / 55s /
    1596. `--max-nodes` bounds it; a stopped run is the best of what was searched.
  - **`beam` — carry K states forward.** Cost LINEAR in K, which is the whole
    reason to want it. **The selection is NESTED, not top-K overall**: slot `i`
    is filled from the children of slots `0..i`, which makes `beam_K`'s first
    K-1 slots identical to `beam_{K-1}` by induction. Plain top-K selection is
    **NOT monotone in K** — slot 1's best child can rank third once slot 2's
    children join the pool, evicting the K=1 trajectory — and that is not
    theoretical: **MEASURED at `-n 8`, k=2 came back WORSE than k=1**.
  - **THE FREE ORACLE: at K=1 both searches are the plain greedy and must return
    the same opening.** They do (385 unsolved, ssq 11112, by two quite different
    traversals), and the gate asserts it along with branch's monotonicity —
    failing if K never changed the answer, so a pass cannot mean it went untested.
- **`--ssq-first N` RANKS ON SUM OF SQUARES ALONE for the first N placements**
  (user's call, 2026-09-18), then switches to unsolved. The objective is PINNED
  early — almost nothing is split, so nearly every answer is unsolved and the
  number carries no signal — and the run skips the unsolved walk entirely while
  it is not being ranked on, scoring only the chosen winner for the log. `N=0`
  is the old behaviour exactly, and N is in the filename.
- **MEASURED at k=1: 6 seconds**, and it lands on `craps until often fjord` with
  **385 unsolved** — far WORSE than the ranked screens (5-17). The greedy is
  myopic exactly where the objective is flat: it commits to `j` on step 1, which
  forces `fjord`, and the result carries only 15 distinct letters. **That is the
  finding, not a bug** — and the reason `-k` exists.
- **THERE IS NO BOUND-BASED PRUNING, AND THAT IS A FACT ABOUT THE OBJECTIVE, not
  an omission.** Placing a letter REFINES the partition, so buckets only split:
  both `unsolved` and `ssq` are **monotone non-increasing** as the opening fills
  in. A partial state's score therefore bounds its completions from **ABOVE**,
  and an upper bound cannot cut a MINIMISATION — the cheap number points the
  wrong way. What the branch search has instead is **MEMOISATION on the state**,
  which is worth more here than a bound would be: placement ORDER does not
  affect the result, so the orderings of one assignment collapse to one search
  (measured: k=3 on 2 words visits 10160 nodes against 4579 distinct states).
  `--max-nodes` is a STOP, not a prune. Do not add a "bound" built on the
  partial score; it would cut correct openings.
- **BOTH SEARCHES NARRATE, AND THE BEAM'S TRACE IS ITS PROGRESS** (restored
  2026-09-18 — the `--search` rewrite had dropped it, so a beam run printed
  NOTHING between its banner and its answer). The beam prints one line per
  placement, `N/20` with a percentage, the leader's spelling, `unsolved` and
  `ssq` — and writes the same as a CSV row, so the file is the whole
  construction. **The line names the leader of what is CARRIED FORWARD** (the
  best of the chosen beam), not the top-scoring candidate: nested selection can
  leave that candidate out of the beam, and naming a discarded state would be a
  lie. At K=1 the two coincide.
  - The BRANCH search prints each new best plus **the fraction of its search
    TREE resolved**. Spans are 1.0 at the root split evenly among the children
    recursed into, and every resolved subtree — leaf, dead end or memo hit —
    adds its own, so the fraction is exact and lands on 100.0%. **It measures
    the TREE, not the time**: a memo hit resolves a subtree instantly and counts
    in full, so the percentage jumps (measured: 0.2% to 12.7% between two
    consecutive improvements). Do not read it as an ETA.
  - **EACH SEARCH WRITES ITS OWN COLUMNS**, because they have different records
    to keep: the beam's is a TRAJECTORY (one row per placement), the branch's a
    sequence of INCUMBENTS (one row per improvement, found anywhere in the
    tree). One header over both would put two meanings under one column name;
    `# settings search=` and the filename each say which a file is.
- **`python3 tools/checkgreedybuild.py` is the GATE**: the blank filler against
  `wordle.pattern` scalar-vs-vectorised, `solved_in_bucket` against
  `worst_case <= 2` on random buckets (asserting both branches occurred), the
  whole objective against `guarantee_sweep`'s losing count on complete openings,
  the legality refusal, the k=1 cross-search oracle and branch's monotonicity —
  **plus the progress report itself**, since a percentage nothing checks is
  decoration: a COMPLETED branch search must report 100.0% of its tree, and the
  beam must print one step line per placement ending at 100%. MUTATION-TESTED
  (dropping the memo hit's span credit makes the branch finish at 0.0%, caught).
  Run it alongside `tools/checkguarantee.py`.
- Data under `math/data/shared/greedybuild/`, log under `data/local/greedybuild/`.
  **The committed `greedy_custom_w4_k*.csv` files predate `--search`** — they are
  beam runs in the old single-header format; new runs are `greedy_beam_*` /
  `greedy_branch_*`, so nothing collides.

### `gray-second` — a PREDETERMINED second word, played only on enough greys
A `wordlesim` strategy, and a table that feeds it (the user's, 2026-09-10): play
an opener; if its reply shows **at least N grey tiles**, play a word committed to
IN ADVANCE for that opener; otherwise, and from the third guess on, the follow-up
plays a random compatible word. `math/secondword.py` states the objective and IS
the source of truth; `solver/secondword.c` computes the table.
- **THE OBJECTIVE, EXACTLY.** For an opener `g1`, take the answers whose reply to
  it shows `>= min_grays` greys, group them by that reply, and for each candidate
  `g2` score `sum over JOINT (reply to g1, reply to g2) buckets of n^2`; the
  reported `expected` is that over the number of qualifying answers. It is
  **`pairsplit`'s ssq restricted to the qualifying rows**, so exact and integral,
  and **ANSWER-WEIGHTED** (user's call): a reply 300 answers produce counts 300
  times against one that 2 produce. **The count is over the 2315 ANSWERS**, not
  the 12972 — so the table optimises for a player who knows the curated list even
  when the run's follow-up is `guess`, which is a deliberate mismatch, not a slip.
- **IT IS ONE PLY, so never quote `expected` as a cost.** It says what is left
  after two guesses, never what the game goes on to take; only the simulation the
  table feeds says that. And the sim's own mean is expected guesses **outright**
  — never table it beside an `optturns`-family total.
- **THE FIRING CONDITION IS A PARTITION INTO GROUPS, EACH WITH ITS OWN SECOND
  WORD** (user's call, 2026-09-10, the third step of the same idea). The reply's
  bucket SELECTS the word: `--group e5 --group e4 --group e3` gives a separate
  predetermined word for five, four and three greys, and `--by-grays 3` is the
  sugar that writes that out. A group spec is terms joined by `+`: `g<N>` (greys
  >= N), `e<N>` (greys == N exactly), `<G>g<Y>y` (that composition).
  - **GROUPS MUST BE DISJOINT** — a reply in two would have two predetermined
    words and no rule for choosing — and a reply in NO group declines to the
    follow-up. A condition covering EVERY reply is refused: that is a blind
    two-word opening, which the `opening` strategy already is.
  - **THE RULE IS ONE ARRAY**, `by_code[reply] -> guess index or -1`, built from
    the table's own groups. The single-word rules are that array with one word
    repeated, so every earlier variant is the one-group case, unchanged.
  - **A REDUNDANT TERM IS REFUSED, NOT DROPPED** (`g3+0g0y` covers exactly what
    `g3` covers), terms within a group are sorted, and the groups are sorted by
    their CANONICAL spec — so one rule cannot have two names, and therefore
    cannot have two tables a reader must tell apart by hand.
  - **A GROUP MAY KEY ON THE GREYED VOWELS, and that bucket depends on the
    OPENER as well as the reply** (user's call, 2026-09-10). `v<N>` is "exactly N
    of the greys sit on a vowel", counted by POSITION, and it is joined to other
    atoms with `_` (AND) inside a term, terms being unioned with `+`: `e3_v1` is
    "exactly three greys and exactly one greyed vowel". `--by-grays 3
    --split-vowels` is the sugar for the full cross product, 15 groups.
    - **Y IS ALWAYS A VOWEL** (`aeiouy`) — not a flag and not a default, this
      video's convention, stamped into every table as `vowels=`. NB
      `tools/vowels.py` still defaults to `aeiou` with `aeiouy` as an argument;
      it predates this and was left alone.
    - **THE MASKS ARE THEREFORE PER OPENER**, and so is the disjointness check:
      the same all-grey reply is a different bucket for a one-vowel opener than
      for a four-vowel one. A condition with no `v` atom is opener-independent
      and is checked once, up front, by both implementations.
    - Combinations an opener cannot produce (`v2` against a one-vowel word) are
      empty rows that never fire — a result, not a gap.
    - **The label is long and deliberately not abbreviated**:
      `e3_v0.e3_v1.…e5_v5` is 118 characters, which the filenames carry. A
      shorthand would have to canonicalise back to the same partition or one rule
      would have two names.
  - **MEASURED: 500 openers x 3 groups in 1.6 s**, so a full partition table is
    about the same minute as a single-group one — every answer falls in exactly
    one group, so the total work barely moves.
- **`--min-grays N` IS THE ONE-GROUP SUGAR for "at least N greys"**, and
  `--fire G,Y` adds a composition to it (user's call, 2026-09-10).
  A threshold on the grey count alone cannot say the thing that turned out to
  matter: two greys with three YELLOWS is nearly uninformative, while two greys
  with three GREENS has pinned three positions, and those do not belong on the
  same side of the line. `--fire G,Y` adds one composition, so the
  three-yellow rule is `--min-grays 3 --fire 0,3`.
  - **`nz<DIGITS>` KEYS ON *WHICH* TILES CAME BACK NON-GREY**, not on how many
    (user's call, 2026-09-16). `e3_nz02` is "exactly three greys, and the
    non-grey ones are positions 0 and 2". **GREEN AND YELLOW ARE THE SAME HERE**
    -- it asks which tiles matched, never how. It reads the REPLY alone, so
    unlike `v`/`mv` it is opener-INDEPENDENT and one mask serves every opener.
    - **`--split-nongray` is the sugar**: `--by-grays 3 --split-nongray` gives
      **16 groups** -- the all-grey reply, five one-match cases and ten
      two-match cases -- against 3 for the count alone.
    - **The digits are a SET and are canonicalised ascending**, so `nz20` and
      `nz02` are one group with one name. Both implementations do it; they
      disagreed at first, which is the "one rule, two names" trap the
      canonicalisation exists to close.
    - **A NEW ATOM MUST EXTEND `atom_key`'s table in groups.c.** It is
      `static const int order[5]` indexed BY KIND, so adding kind 5 read off
      the end and the term came out as `nz01_e3` instead of `e3_nz01`.
    - **MEASURED and it is the biggest single win so far**: against the same
      beam, keying on WHICH tiles beats keying on how many by ~0.055 --
      k=20 **3.654019** against 3.707971, k=50 **3.625487** against 3.680804.
      The k=50 figure already beats the best two-level number from any other
      partition (3.643368 at k=1000 on the matched-vowel split).
  - **THE LABEL IS A FUNCTION OF THE SET, NOT OF HOW IT WAS TYPED** — an
    `--fire` the threshold already covers is dropped and the rest are sorted, so
    two spellings of one rule cannot make two filenames (`g3+0g3y`). The label
    is in the table's stamp, in its filename and in every downstream stem, and
    the RULE rebuilds its mask from that label rather than being told a
    threshold. A non-canonical label is REFUSED, not normalised.
  - **The C and `secondword.py` build the set and the label INDEPENDENTLY**, and
    `checksecondword.py` diffs both over a range of specs — that is the one
    mistake a stamp cannot catch, since the stamp is written by whichever side is
    wrong.
  - **THE C SIDE OF IT IS `solver/groups.h`/`groups.c`, and `secondexact`
    COMPILES THE SAME FILE** — one grammar, one canonical label, one set of
    per-opener masks for both solvers, so extending the condition extends both at
    once and neither can drift. `groups_add_by_grays()` owns the `--by-grays`
    cross product (including the `e5_mv0` collapse), so the wrappers generate no
    specs of their own. See § `run-second-exact.sh`.
  - **A table written before this carries only `min_grays`, which means exactly
    `g<N>`**, so `second_guess_g3.csv` and the rest keep working and keep meaning
    what they meant.
  - **MEASURED: adding `0,3` to the `g3` rule grows the qualifying set of EVERY
    real opener and changes the chosen second word for NONE of them** (24 openers
    checked). The added bucket is a small part of ~2200, so this variant differs
    from plain `g3` almost entirely in WHEN it fires, not in WHAT it plays. The
    gate's winner-moves case is therefore CONSTRUCTED (`g5+0g2y` on the mini
    problem), since the natural one cannot demonstrate it.
- **`--min-grays` IS THE OBJECTIVE, not a knob**, and so are the two pools. Each
  combination is a different strategy: all three are in the filename AND in the
  table's own `# settings` stamp, and every reader refuses a table whose stamp
  disagrees with what it asked for (a filename cannot check itself — the greens
  scar). **TWO VARIANTS** (user's call, 2026-09-10), and their numbers must never
  share a table, the second being a strictly smaller strategy space:
  `--variant guess` (openers and second words both the 12972) and
  `--variant mystery` (both the 2315), swept with `--words guess` / `--words
  mystery` respectively.
- **Build it with `bash solver/run-second-word.sh [--variant V] [--min-grays N]`**
  (from `math/`), attached, tee'd log, `--dry-run`. Exact and deterministic — no
  sampling, no seed — so a re-run reproduces the file byte for byte. **MEASURED
  2026-09-10: 500 openers in 2.2 s on 18 threads, so the full 12972 is ~1 minute**
  and the `mystery` variant a few seconds. `--limit N` prices it and writes a
  PREFIX under its own name, with the stamp's opener pool RENAMED so nothing can
  read a priced run as the table.
- **AN EMPTY `second` IS A RESULT.** An opener no answer can give that many greys
  has nothing to choose between; the rule then never fires and the strategy is
  the plain opener.
- **THE FOLLOW-UP IS ALWAYS `answer` FOR THIS STRATEGY (user's call, 2026-09-10):
  the random compatible words come from the ANSWER list.** That is a THIRD axis,
  separate from the two pools above, and it is not defaulted by the code —
  `--fallback` stays required everywhere, because a wordlesim strategy is a rule
  plus a follow-up and the filename has to say which. It simply always gets
  `answer` here, which is also what makes the two variants directly comparable:
  they then differ only in where the two COMMITTED words came from.
- **THE TWO VARIANTS ARE `--words` PLUS THE TABLE, NEVER `--fallback`** — the
  answers-only run is `--words mystery` with `second_mystery_g3.csv`, the
  all-guesses run is `--words guess` with `second_guess_g3.csv`. **BOTH pools are
  in the race's stem** (`race_answer_mystery_sig5_s0_g3-mystery`): the opener list
  from `--words`, the second-word pool from the table's own stamp. The second half
  was missing at first, and racing the 2315 openers against the 12972-word table —
  a third experiment again — would have shared a filename, and therefore a
  CHECKPOINT, with the answers-only run.
- **The second word is played BLIND and is usually NOT a live candidate** — it
  was chosen to split, not to win. The opener is excluded as its own second word.
- **Run one opener with `--strategy gray-second --strategy-arg WORD
  --strategy-arg TABLE.csv`**; sweep with **`bash solver/run-wordle-sweep.sh
  --fallback answer|guess --second-from TABLE.csv -t 100`**, which is the ordinary
  cascade with this rule swapped in for the blind opening. It is **REFUSED
  alongside `--pair-adaptive`** (two rules for the same turn), refuses a
  multi-word entry, and **checks up front that the table has a row for every
  opener being swept** — which is what stops one variant's table being swept over
  the other's word list. The threshold lands in the stem as `_g<N>`, in the
  `# settings` line as `second_table=`/`min_grays=`, and **is INHERITED by every
  later pass and by `run-wordle-paired.sh`** — the § cascade scar, which is why a
  pass given a DIFFERENT table than its source is refused outright.
- **A STAGE-1 SWEEP'S LINEAGE ROOT IS NOW ITS WORD LIST** (fixed 2026-09-10). It
  was empty, so `--words guess` and `--words mystery` produced the SAME stem —
  `sweep_answer__p1_t100_s0.csv` — and the second would have resumed from the
  first, silently mixing two word lists into one file. Nothing committed carries
  the empty form: every single-word sweep on disk predates the lineage scheme.
- **`tools/wordle_sim.py --resolve` was BROKEN and is fixed** (same day): its
  early return dropped `adapt` after that flag was added, so it raised a
  ValueError — and the wrapper resolves every strategy through it before doing
  anything, so `run-wordle-sim.sh` was refusing **every** run.
- **`python3 tools/checksecondword.py` is the GATE** (~10 s), and it is
  MUTATION-TESTED (an off-by-one in the threshold and a dropped tie-break were
  each caught): the whole mini `--data` problem at every threshold against a
  reference that recomputes replies FROM THE STRINGS by the multiset rule and
  groups by the TILE TUPLE, so it never touches the encoding, the matrix or the
  run-histogram trick; the restricted pools, with the assertion that restricting
  actually CHANGED a row; real openers against the numpy reference over all 12972
  second words, and against the string reference over a 400-word pool; a
  CONSTRUCTED empty case (every answer carries an `e`, so five greys is
  impossible); and the refusals, including the reader's. **A REVERSED pool file is
  what pins the tie-break** — in index order "first found" and "lowest guess
  index" are the same word, so nothing else can tell a real tie-break from an
  accident of arrival. **Coverage is asserted**: it FAILS unless a tie, an empty
  row, a threshold that moved the winner and a pool restriction that moved it all
  occurred. `checkwordlesim.py` covers the RULE — both branches of the threshold
  constructed at exactly N and N-1 greys, an empty row reproducing the plain
  opener, and the sweep's `make_rule` hook actually running this rule rather than
  falling back to the blind opening.

- **`python3 tools/checkwordlesim.py` is the GATE**: it replays the same seeds
  through an independent implementation that keeps candidates as LISTS OF WORDS and
  recomputes every reply from the STRINGS by the **multiset rule** (a different
  algorithm from `wordle.pattern`'s consuming left-to-right scan, so a
  repeated-letter mistake cannot be shared), demanding identical guess sequences;
  it also checks, from the strings, that every follow-up guess really was compatible
  with every earlier reply, exercises the rule-then-`None` path with a synthetic
  opener **under BOTH follow-ups** (which is the only place the `guess` follow-up's
  catch-up from a history it did not watch gets tested), checks no follow-up
  replays the missed opener, pins the registry's refusals, and tallies coverage — FAILING if no game ran past six or none came in
  under it. **BOTH strategies are diffed against that one reference, differing
  only in the POOL it draws from**, which is also what pins `random-guess`'s
  per-game state reset (a leaked bitmap diverges from game two on); it FAILS if
  `random-guess` never played a non-mystery word, and it re-checks that every
  hidden answer came from the 2315. `--guess-games` sizes that half (the
  reference filters 12972 strings per turn, so it is the slow one). **It also
  diffs the SWEEP** — reproducing its two-stream loop from the strings and
  requiring the answers each word faced to be IDENTICAL across words, the property
  the whole sweep rests on (a shared stream would still report unbiased means
  while destroying the comparison between words) — and checks the shortlist cut on
  hand-made rows in both directions. Run it alongside `solver/validate.sh` and
  `tools/checkpatterns.py`.

## Wordle in One (`run-wordle-in-one.sh`) — singleton ROWS, and their RATE
A "Wordle in One" is a feedback ROW that names its answer outright: a guess and a
pattern that exactly ONE of the 2315 mystery answers produces, so seeing it forces
the answer. `math/tools/wordle_in_one.py` enumerates every such (guess, answer,
pattern) and breaks them down by tile composition. Run it with **`bash
solver/run-wordle-in-one.sh --guesses answers|all`** (from `math/`), attached,
tee'd log — never a bare `tools/wordle_in_one.py`, which REFUSES without the flag.
- **Exact and deterministic** — a pure function of the committed word lists and
  the pattern matrix. No sampling, no seed, no cap, so a re-run reproduces its
  files byte for byte and there is no standard error to quote.
- **THE GUESS SET IS PART OF THE QUESTION AND IS NEVER DEFAULTED IN THE SCRIPT**
  (the greens scar — the WRAPPER carries a default a human reads, `answers`, and
  forwards it explicitly). `answers` plays only the 2315 mystery words (the
  user's original call: "every singleton produced by every answer word, not all
  guesses"); `all` plays any of the 12972 legal words. **Two different quantities
  over the same answer set — never put their numbers in one table**, and each
  writes its own files.
- **THE RATE IS PAIR-WEIGHTED (user's call, 2026-09-08), and the other reading is
  a different number.** A cell's denominator is every (guess, answer) PAIR whose
  row has that composition, so `pct` answers "I played a word and saw this many
  greens and yellows — how often is the answer already forced?", the answer
  uniform over the 2315. It is NOT the fraction of DISTINCT (guess, pattern) ROWS
  of that shape that are singletons, which weights a 2-answer bucket like a
  300-answer one. Say which one a number is.
- **THE TWO RANDOM-GUESS COLUMNS ARE THE SAME QUESTION ONE STEP WEAKER.** `pct`
  asks how often the row FORCES the answer; `pct_rand_answers` / `pct_rand_guesses`
  ask how often a random pick from what the row leaves ALIVE would be right — the
  consistent ANSWER words (at most 2315) and the consistent LEGAL GUESS words (at
  most 12972). A row leaving `n` alive contributes `1/n`, the cell is the MEAN over
  its pairs, so both are `>= pct` and the legal-word column is always the smaller
  (its pool is a superset containing every consistent answer). **A pick from the
  WHOLE list ignoring the row is a flat 1/2315 or 1/12972 and is NOT what these
  report.** Identity worth knowing: `1/n` summed over a bucket's `n` pairs is
  exactly 1, so `pct_rand_answers` is also the count of DISTINCT non-empty
  (guess, pattern) rows of that composition over its pairs.
- **`avg_answers` / `avg_guesses` ARE THOSE SAME TWO POOLS COUNTED RATHER THAN
  INVERTED** (added 2026-09-09): the mean NUMBER of words the row leaves alive,
  over the same pairs, so a bucket of `n` answers enters the mean `n` times and
  the cell is `sum(n^2)/sum(n)`. **They are NOT `100/pct_rand_*`** — the mean of
  `n` and the mean of `1/n` are different aggregations of one distribution (the
  first is dominated by the wide buckets, the second by the narrow ones), so a
  composition can rank differently under the two. **The weighting is
  ANSWER-weighted** (user's call), matching every other column; the
  node-weighted reading (every distinct row once, `pairs/rows`) stays
  recoverable, since `pct_rand_answers` IS `rows/pairs`. Sort on `avg_answers`
  to rank compositions by how much the row narrowed things down; the tool also
  prints the table a second time in that order.
- **THE LEGAL-WORD COLUMN NEEDS THE SQUARE 12972x12972 MATRIX** (`python3
  build_patterns.py --full`, ~18s/168 MB), gitignored under `data/local/` and so
  MISSING ON A FRESH CLONE — the wrapper and the tool both refuse with that
  command. Its use is GATED: each row of the square matrix, restricted to the
  answer columns, must EQUAL the 12972x2315 matrix's row, which pins the column
  order and makes the legal-word bucket a provable superset of the answer bucket.
- **The all-green row's 100% is ARITHMETIC, not a measurement** — a guess equal to
  the answer is a singleton that tells you nothing you did not know by typing it,
  and its denominator is exactly the 2315 self-pairs. `games_nowin`/`pct_nowin`
  exclude it; every other cell has `games == games_nowin`.
- **A 0.00% cell is a RESULT** (the all-gray row, say), so cells with pairs but no
  singletons are printed. A cell missing entirely had NO pairs: 4 greens + 1
  yellow is impossible, which is the 238-of-243 rule.
- **THE GATE IS BUILT IN**: per-guess singleton totals must match the committed
  `guess_singletons_answers.csv` (answers) / `guess_singletons.csv` (all), and the
  no-win total must match their column sum. It fails loudly rather than reporting.
- Data under `math/data/shared/singletons/`: `wordle_in_one_games[_allguesses]
  .csv[.gz]` (one row per game) and `wordle_in_one_breakdown[_allguesses].csv`
  (`greens,yellows,grays,games,games_nowin,pairs,pct,pct_nowin,pct_rand_answers,
  pct_rand_guesses,avg_answers,avg_guesses`). The all-guesses
  games file is gzipped (264778 rows). Log under `data/local/singletons/`.

## `run-maxbucket.sh` — openers ranked by their LARGEST bucket (the minimax criterion)
A guess PARTITIONS the answers (same part iff same feedback); this ranks openers
by the size of the BIGGEST part — the worst case, how many answers survive the
unluckiest reply — ascending. `bash solver/run-maxbucket.sh` (from `math/`),
attached, tee'd log. Exact and deterministic: a pure function of the committed
word lists and the pattern matrix, no sampling, no seed, no cap, so a re-run
reproduces its file byte for byte.
- **IT IS A DIFFERENT QUANTITY FROM EVERY OTHER RANKING HERE — never table it
  beside one.** Not the EXPECTED answers remaining (a weighted mean over the same
  partition; the mean of `n` and the max of `n` are different aggregations and
  rank differently — the same distinction `wordle_in_one.py`'s `avg_answers` vs
  `pct_rand_*` carries). Not the singleton count of `run-singles.sh`, which looks
  only at the parts of size ONE while this looks only at the largest. And
  emphatically not an `optturns`-family total, which is a number of GUESSES
  subject to a 6-guess guarantee.
- **THE ANSWER SET IS PART OF THE QUESTION and is NOT defaulted in the tool** (the
  greens scar): `--answer-set mystery` counts buckets over the 2315 curated
  answers, `--answer-set all` makes every one of the 12972 legal words an answer
  (which needs the square matrix, `build_patterns.py --full`). Two different
  quantities, two files. The WRAPPER carries the default a human reads (`mystery`)
  and forwards it explicitly; `tools/maxbucket.py` refuses without it.
- **`--rank` IS A SEPARATE AXIS and changes no count** — `all` lists every legal
  guess, `answers` lists only the 2315, exactly as `singletons.py --answers` does.
  A word scores what it always scored; ranks move only because the field is
  smaller. Do not confuse it with `--answer-set`, which changes the numbers.
- **THE ALL-GREEN BUCKET CANNOT BE THE LARGEST**, so there is no `_nowin` column of
  the kind `singletons.py` needs: it holds the answers equal to the guess, hence
  size 1 for the 2315 guesses that are answers and 0 for the rest, against maxima
  in the hundreds.
- **TIES ARE REAL** (the quantity is an integer over a large field) and the
  ranking is on `max_bucket` ALONE — the alphabetical tie-break exists only to
  make the file deterministic and carries no meaning. `max_pattern` (the
  lowest-coded pattern attaining the maximum), `max_ties` and `buckets` are
  DESCRIPTIVE columns, not secondary keys.
- **IT REUSES `absurdle.bucket_counts`, and that is the source of the gate.**
  Absurdle's host answers with the pattern of the LARGEST bucket, so `max_bucket`
  IS the number of candidates an opener leaves against that host — the identity
  that makes `data/shared/absurdle/one_shortest_solution.txt` an independent
  oracle for the MINIMUM of this ranking. (Nothing here inherits Absurdle's
  unverified-rules caveat: the partition is plain Wordle feedback either way.)
- **`python3 tools/maxbucket.py` HAS THE GATE BUILT IN and it always runs**:
  sampled guesses are re-bucketed FROM THE STRINGS with `wordle.pattern`, sharing
  no machinery with the matrix path (pinning the matrix, its column order and the
  argmax bookkeeping), and in the default answer set the minimum is cross-checked
  against that committed Absurdle witness — read from the file, never typed in. It
  exits nonzero rather than reporting.
- Data under `math/data/shared/maxbucket/maxbucket_<answer-set>_<rank>.csv`
  (`word,max_bucket,max_pattern,max_ties,buckets,rank`); log under
  `math/data/local/maxbucket/`.

## Tree states (`run-tree-states.sh`) — the same two questions, at every level
The in-game companion to Wordle in One: it walks the emitted OPTIMAL TREES and
asks, at each LEVEL k (the state after k guesses and their feedback) and each
cumulative (greens, yellows) count, how often the strategy has already narrowed
the answer to ONE word and how often a random pick from what is still alive would
be right. **`bash solver/run-tree-states.sh --top N`** (from `math/`), attached,
tee'd log; `WORDLE_SOLVER` picks the sweep, `--top N` names the file.
- **Exact and deterministic** — a pure function of the committed trees and word
  lists. Nothing searches or samples. **MEASURED ~0.1 s per opener**, so the top
  1000 is a couple of minutes.
- **THE STATE DEFINITION IS THE USER'S CALL (2026-09-08), and the repeated-letter
  reading is "UNPLACED COPIES".** `greens` = POSITIONS pinned green by any guess
  so far (a position stays pinned; a later guess playing another letter there does
  not unpin it). `yellows` = COPIES of a letter known present but not yet pinned,
  SUMMED over letters — two loose B's count 2, and a letter with one copy green
  and another loose contributes 1. `grays` = 5 − greens − yellows. Chosen over
  "distinct unplaced letters" and over the literal "appeared yellow and never
  green" because it is the one making **greens + yellows the ANSWER SLOTS
  ACCOUNTED FOR**, hence grays exactly the slots still blank — an invariant
  asserted at every node. A different reading is a different table.
- **WEIGHTING IS BY ANSWERS, not by nodes (user's call)** — a node holding `n`
  candidates contributes `n` cases, so `pct_single` is the share of ANSWERS
  sitting in an already-narrowed node. `nodes` is reported beside `cases`, so the
  node-weighted reading stays recoverable (and `pct_rand_answers` IS `nodes/cases`,
  the same 1/n identity as in Wordle in One).
- **`avg_answers` / `avg_guesses` are the same two pools COUNTED rather than
  inverted** (added 2026-09-09, mirroring Wordle in One): the mean number of
  words still consistent, same answer weighting, so a node of `n` candidates
  contributes `n*n` and `n*m` and the cell is `sum(n^2)/sum(n)`. **NOT
  `100/pct_rand_*`.** The per-level summary carries both means.
- **THE `avg_answers` RANKING IS PRINTED TWICE, AND THE TWO ARE DIFFERENT
  QUESTIONS** (user's call, 2026-09-09). **WITHIN each level** is the default
  reading: how narrowed a board is depends heavily on how many rows have been
  played, so pooling ranks the game's CLOCK as much as the tiles, and two
  compositions are comparable when the same number of guesses produced them.
  **POOLED ACROSS the levels** asks what a composition is worth with the turn
  forgotten rather than held fixed.
  - **The pooled view's denominator is NOT ANSWERS.** An answer sits in a node at
    every level it survives, so pooling counts it once per surviving turn — those
    cells are candidate-weighted BOARD STATES, and **a pooled cell is not a share
    of the 2315**. Within a level each answer appears at most once, which is
    exactly what makes that view the answer-weighted one.
  - **The CSV stays per (level, composition)** — the raw cells both views are
    built from, so either is rebuildable from it.
- **A WON GAME IS NOT A CASE.** A tree line records no pattern for its final guess
  (it would be all green), so a game ending at turn k has no level-k state and
  leaves every deeper level. Level counts therefore FALL with depth.
- **`--top N` POOLS N DIFFERENT STRATEGIES**, best first by `total` in the sweep's
  CSV, ties on the word. Each contributes its own 2315 answers, so every opener
  carries EQUAL weight however good it is — a property of the aggregate, not of
  any tree. A single opener's numbers need `--top 1` on that opener's rank.
- **THE TREES ARE THE CONSTRAINED OPTIMA** (minimum total guesses subject to
  resolving every answer within 6), so these are states of THAT strategy, never of
  an unconstrained expected-guess minimiser. Same rule as everywhere: do not table
  them beside an outright-expectation number.
- **TWO GATES, BOTH ALWAYS ON AND BOTH DIFFERENTIAL** — mutation-tested when the
  tool shipped (a distinct-letters yellow rule, an off-by-one candidate count and
  a forgotten pinned position were each caught): (1) sampled lines have their
  cumulative state re-derived FROM THE STRINGS by a route that never looks at a
  tile — greens as positions where some guess matched the answer, known counts as
  `max over rows of min(count in guess, count in answer)` — and every recorded
  pattern re-derived with `wordle.pattern`; (2) on the first few openers a node's
  candidate count `n` and legal-word count `m` are recomputed by FILTERING THE
  WORD LISTS, which pins the tree's partition as the consistent set and checks the
  incremental matrix filtering inside the walk.
- **It reads the SQUARE 12972x12972 matrix** for the legal-word column
  (`python3 build_patterns.py --full`), gitignored under `local/` — wrapper and
  tool both refuse with that command on a fresh clone.
- Data: `math/data/shared/treestates/states_<solver>_top<N>.csv`
  (`level,greens,yellows,grays,nodes,cases,singles,pct_single,pct_rand_answers,
  pct_rand_guesses,avg_answers,avg_guesses`); log under
  `math/data/local/treestates/`.

## Nerdle (8-symbol equations) — the GUESS enumeration, pass one
A different game living beside the wordle variants. `math/nerdle.py` states the rules
and IS the source of truth; read it before quoting any count. Run it with
**`bash solver/run-nerdle-enumerate.sh [--width W] [--method dfs|split]`** (from `math/`).
- **THE GUESS RULES ARE ALL CONFIRMED AGAINST THE LIVE GAME (2026-09-03)** — the seven
  discriminating probes and their verdicts are listed in `nerdle.py`'s docstring
  (`-1+3=0+2`, `1*-2=-2`, `1---2=-1`, `0-0=-0`, `1/2=2/4` accepted; `1+1=2=2`, `12/0=12/0`
  rejected). **This mattered: 50605 guesses, 13.5%, turn on the unary-minus rule alone**,
  which until then rested on one recalled observation with three distinct behaviours
  folded into it. `-0` is therefore the game's behaviour, not an artefact. **THE GUESS
  COUNT HAS NO EXTERNAL CHECK** — Nerdle publishes no guess figure — so it rests entirely
  on those probes, unlike the answer count.
- **The rules — and they are much LOOSER than the answer rules.** 15 symbols
  (`0123456789+-*/=`), exactly one `=`, both sides full expressions with standard
  precedence. **The RIGHT SIDE IS AN EXPRESSION, not a number** (`1+9=0+10` is legal),
  **leading zeros are allowed** and **neither side needs an operator at all** (`0012=012`,
  which the live game accepted), a **unary `-` may precede any number ANYWHERE and may be
  REPEATED** (`1--2=3`, a double negative), and the two sides are compared as **EXACT
  RATIONALS** whose shared value need be neither whole (`1/2=2/4`) nor non-negative
  (`10-20=-10`). The only arithmetic prohibition is division by zero.
- **THE EXPRESSION RIGHT SIDE IS WHAT MAKES THIS EXPENSIVE, and it invalidated the
  original design.** The first plan walked to the `=` and counted the digits remaining;
  with an expression RHS the walk cannot stop there, so `--method dfs` — the specified
  single-pass descent — bottoms out roughly 188M structurally valid strings.
  **`--method split`** enumerates each SIDE once with its exact value and joins the sides
  of each `=` position on it: ~7.6M side evaluations, the SAME set, orders of magnitude
  cheaper. Both are exact, so the method is deliberately NOT part of the filename.
- **THE ANSWER RULES are settled (2026-09-03) and are `nerdle.py`'s A1-A4**, applied by
  `is_answer()` and by **`bash solver/run-nerdle-answers.sh [--width W]`**, which filters
  the pass-one guess list (answers are a strict SUBSET of guesses). An answer is a valid
  guess whose **right side is a bare NUMBER**, in which **no digit run begins with `0`
  EXCEPT that the ANSWER may be `0` itself** (so `1+2=03` and `1*0+7=7` are out but
  `12-3*4=0` is in; `10` is fine), which writes **no unary minus**, and whose **left side
  contains at least one operator**.
- **THE INTERMEDIATE VALUES ARE DELIBERATELY UNCONSTRAINED, and that is a DECISION.** The
  user settled that an answer's left side MAY pass through a negative value (`1-2+3=2`,
  running total -1) and MAY pass through a fraction (`1/2*4=2`). Both stricter readings
  were live until then and both give a **smaller** set, so a count computed under either
  is a DIFFERENT quantity — never quote one as the answer count. A2/A3 make every operand
  at least 1, so the only route to a negative is a subtraction in the running
  left-to-right total and the only route to a fraction is a division inside a term; there
  is nowhere else to look, which is why both questions had unambiguous answers.
- **BOTH OF NERDLE'S PUBLISHED COUNTS ARE REPRODUCED, and that is how A2's zero-answer
  exception was established.** Its FAQ gives "over 100,000 valid solutions" of which it
  "chose 17,723". At width 8: the settled rules give **exactly 17723**; without the
  exception 17356; with A2 dropped entirely **112566** (their "over 100,000"); also
  allowing bare `0` OPERANDS 25489, which overshoots and is ruled out. So their
  valid-solution set is ours with leading zeros allowed, and their cull drops leading
  zeros and `0` operands while KEEPING `0` as an answer. **The 17723 was a prediction,
  not a fit** — the switch was named as the likeliest single explanation of the 367 gap
  before the run. It is still an inference from two counts rather than a rule anyone has
  read, so **a past answer of `0` would settle it outright**.
- **`bash solver/run-nerdle-answers.sh --variants`** counts the answers under each
  disputed clause (`answer_rules()` carries them as switches). **Only the first row is the
  answer count**; every other row is a different quantity. Do not add switches until a
  number matches — a mismatch is evidence about the rules.
- **Width 8, rules as of 2026-09-03: 374246 valid GUESSES** (41.5s, `--method dfs`) and
  **17723 ANSWERS**, in `data/shared/nerdle/`.
- **Pass one counts equations AS WRITTEN** — `1+9=0+10` and `9+1=0+10` are two guesses,
  not one.
- **PASS TWO collapses the ANSWERS into commutative classes: `bash solver/run-nerdle-classes.sh`.**
  **ONLY `+` AND `*` COMMUTE** (user's call, 2026-09-03): the operator sequence is
  preserved and operands permute within their `+` slots and within their `*` slots, so a
  subtracted term and a divisor stay put. `12+34=46`≡`34+12=46`, `1*2+8=10`≡`8+1*2=10`,
  `9-8+7=8`≡`7-8+9=8` (the two `+` terms swap, `-8` holds its slot); but NOT
  `9-8+7=8`≡`9+7-8=8`, NOT `12/3/2=2`≡`12/2/3=2`.
  - **DO NOT re-adopt the FAQ's literal test.** It says a guess "must still have all the
    same numbers, the same operators and the same answer" — a **NECESSARY** condition,
    and reading it as SUFFICIENT was an error that put `1*2+8=10` and `1*8+2=10` in one
    class though their products are `1*2` and `1*8`. The FAQ never addresses `-` or `/`
    and gives no example beyond `+` and `*`; a web search (2026-09-03) found nothing
    better. NB commutative answers are a **SETTING, on by default**, so the win condition
    is setting-dependent.
  - **The formalisation is a CHOICE**: this preserves the operator sequence and permutes
    operands within it. The alternative — swap a `+`/`*` node's operands and re-flatten —
    also moves operators, additionally merging `8/2*3=12` with `3*8/2=12`. Both are "only
    `+` and `*` commute"; ours is the simpler to state and is what every count was
    computed under.
  - **The class count and the answer count are DIFFERENT QUANTITIES** — what the hidden
    equation may be as written, versus how many distinct puzzles that is — so never quote
    one as the other.
- **`python3 tools/checknerdle.py` is the GATE.** Its reference shares no code with
  `nerdle.py`: a regex screens a side, then every digit run is rewritten as `Fraction(n)`
  and the string handed to **PYTHON'S OWN PARSER** via `eval`, so precedence, repeated
  unary minus and exactness come from CPython (and the rewrite is what sidesteps Python
  rejecting `0012` as a literal). It diffs that against the rules EXHAUSTIVELY at widths
  3-5 (6 under `--wide`), diffs `evaluate` over every side to length 4 including the
  malformed ones, diffs the two walkers to width 6 (7 under `--wide`), and ends with a
  COVERAGE tally that FAILS if any awkward feature — unary minus, double negative, leading
  zero, division, expression on the right, operator-free side, negative value,
  non-integer value — never fired. Run it alongside `solver/validate.sh`. **`--width`
  exists FOR that gate** (so small widths can be brute-forced); the game is 8.
- Data under `math/data/shared/nerdle/guesses_w<W>.txt.gz` plus a `.meta` recording the
  rule set, the count and the per-`=`-position breakdown; log under
  `math/data/local/nerdle/`. The count is exact and integral — no sampling, no seed — so
  one width means one file and a re-run reproduces it.
- **Known edge case, RECORDED rather than decided: the unary-minus rule admits `-0`, so
  `0-0=-0` is counted.** Not checked against the live game.

## Nerdle solver — a top-K beam ranked by sum of squares
`math/nerdle_topk.py` states the objective and the strategy and IS the source of truth.
Run it with **`bash solver/run-nerdle-solve.sh [-k K] [--width W] [--rank-only]`**
(from `math/`).
- **THE OBJECTIVE IS EXPECTED GUESSES OUTRIGHT — NO DEPTH CAP.** Same footing as
  multiwordle and the adversarial hill-climb, and NOT the footing of any
  `optturns`/`hardturns`/`ansall` total, which are optima **subject to a guarantee**.
  Never put the two in one table. `MAXD` (32) is a recursion guard: every answer is a
  legal guess, so a candidate guess always outranks a non-splitting one and every child
  is strictly smaller.
- **IT IS A BEAM, NOT AN OPTIMUM. `-k K` restricts the ROOT too**, so the opener is the
  best of the K examined, not the best of 374246 — the same caveat `strturns` carries.
  Each K is a different strategy and gets its own file.
- **Ranking: ascending SUM OF SQUARED BIN SIZES, ties on the LOWEST GUESS INDEX** — the
  rule copied from `strturns.c`'s `GuessKey`/`cmp_guesskey`, including the warning never
  to pack the key beside the index.
- **A GUESS WINS AGAINST ITS WHOLE COMMUTATIVE CLASS**, so one guess can finish several
  candidates at once and the winning bin is the CLASS, not the all-green pattern (which
  is a subset of it). Nothing in the Wordle solvers works this way. The gate tests it
  sharply: a one-class answer list of size n must cost n, where exact-match scoring gives
  n+1.
- **GUESS ORDER IS PART OF THE STRATEGY — the list is sorted into canonical SYMBOL order
  on construction** (`canonical_order`). Ties break on the lowest index, and the two
  enumerators emit different orders, so a list taken in file order made width 6 give 526
  one way and 528 the other. Do not remove the sort; it is what makes the result a
  function of the guess SET.
- **NO PATTERN MATRIX — 374246 x 17723 is 13.3 GB**, so feedback is computed inside the
  numba kernel. **MEASURED: the root ranking is ~105s single-threaded**, and a level costs
  the guess count times the candidates alive at that level, so every level costs about
  what the root does rather than decaying. `--rank-only` does the root and stops.
  **`-k K` multiplies the work per level by K**, so it compounds with depth.
- **A FIXED OPENING: `--opener W` (repeatable), `--openers "A B"`, `--openers-from FILE`.**
  Point `--openers-from` at a pairs CSV to run its best pair — it takes the FIRST DATA ROW
  and keeps every field that is a legal guess, so it reads a pairs file as two words and a
  rank file as one, with no per-file column list. The opening is played **BLIND in order**,
  as a multiwordle opening is, and the beam takes over below it. **THE OPENING IS AN INPUT,
  NEVER A RESULT** — echoed, recorded in the `.meta` with its source, and in the filename
  (operators transliterate `+ - * / =` to `p m t d e`, since `/` cannot appear in a path).
  - **A BLIND OPENING CAN COST MORE THAN A FREE RUN, and measuring that is the point.** The
    second word is played even when the first already narrowed the answer to one class,
    whereas a free beam adapts after the first reply. **MEASURED at width 6: the best
    screened pair gives 3.0728 against the free run's 2.5534** — the pair splits better and
    still loses. Do not assume a better pair score means a better strategy.
  - A fixed opening never consults the root ranking, so the wrapper does not build one for
    it.
  - **The gate's tie: fixing the opening to the beam's OWN choice must reproduce the free
    run exactly.** That runs the whole blind-accounting path against the original one.
- **THE ROOT RANKING IS COMPUTED ONCE AND STORED: `bash solver/run-nerdle-rank.sh`**,
  writing `data/shared/nerdle/root_rank_w<W>.csv.gz` (every guess, best first, with its
  score). **RUN IT FIRST** — the solver and the pair screen both start from it and read it
  from disk. They used to each recompute it, and a single solve paid the ~110s twice.
  `nerdle_topk.attach_ranking()` is the ONE place that decides load-or-compute, so the
  consumers cannot drift.
  - **The file carries a FINGERPRINT over the width and BOTH word lists, and a mismatch is
    REFUSED, never used.** Re-enumerating the answers retires it automatically. Silently
    reusing one would leave every score confidently wrong rather than missing — the same
    hazard as a foreign `tt.bin`.
  - **THE SCORING IS CHUNKED (`block`, default 2000 guesses) AND THAT IS NOT A PERF
    KNOB.** A njit call never returns to the interpreter, so Python cannot run its SIGINT
    handler while one runs: scoring all 374246 in one call made **Ctrl-C do nothing for
    ~110s**. Returning between blocks is what makes the slow step interruptible and what
    lets it report progress. Do not merge it back into one call. An interrupt leaves NO
    partial file — the save happens only after the ranking completes.
  - **It is a RANKING, NOT A RESULT.** A good first-guess score says nothing about what
    happens after the reply; quote the solver's number, not this one.
- **ONE scoring rule, in `_score`**, called by both the per-node top-k ranking and the
  whole-root scoring — the discipline `strturns` keeps with its single `GuessKey`
  comparator. The root uses score-then-stable-argsort rather than top-k insertion, which
  is O(NG) instead of quadratic when k is the whole list and gives the identical order.
- **THE ROOT IS DRIVEN FROM PYTHON so the run reports progress** — the kernel does each
  subtree, the loop sees them finish. It reproduces the recursion's root exactly (same
  ranking, bucket order and running-cost cut) and the gate diffs the two rather than
  trusting it. Progress is a REAL completion fraction (answers resolved out of the answer
  count, spanning the whole beam at `k > 1`), not a heartbeat.
- **`solve()` is CACHED, and that was a bug fix**: the total and the opener come out of one
  walk, and asking for them separately ran the whole search TWICE.
- **TWO-EQUATION OPENERS: `bash solver/run-nerdle-pairs.sh [--top-n N]`.** Both guesses
  played BLIND; an answer's joint bin is the PAIR of feedbacks, ranked by ascending sum of
  squared joint bins, and an answer either guess WINS joins no bin. **IT IS A SCREEN, NOT
  A SEARCH** — only pairs drawn from the best N SINGLE guesses are examined, so the best
  pair overall can be missed outright (two poor splitters can cover each other's blind
  spots). Say "the best pair among the top N", never "the best pair"; `--top-n` widens it
  quadratically and never makes it exhaustive. **The score is split quality, NOT expected
  guesses** — it does not know an answer won by the FIRST guess is cheaper than one won by
  the second.
  - **THE SCREEN RETURNS ONLY WHAT IT WILL WRITE, and that limit is load-bearing.**
    Turning every pair into a Python tuple **killed a FINISHED 25-hour sweep** at
    `--top-n 30000`: 449985000 pairs need ~70 GB of tuples on a 25.8 GB machine, and
    nothing was written until after that step. `pair_scores(keep=N)` is now the contract;
    `keep=None` REFUSES above `MAX_MATERIALISE` rather than trying and dying. Scores are
    int32 (max is NA², 3.1e8) and the kept top-N is maintained AS THE SWEEP RUNS.
  - **PARTIAL RESULTS ARE CHECKPOINTED every few minutes, atomically**, so a kill never
    loses a long sweep. `finished=` in the meta says whether the sweep completed;
    `complete=` still says whether every scored pair was written.
  - **THE INCUMBENT LOG IS WHAT SAVED THAT RUN.** The tee'd `NEW BEST` lines in
    `data/local/nerdle/` were the only surviving record — recovered to
    `pairs_w8_n30000_incumbents.csv`. Best pair `47-11=36 2*029=58` at 37788, **found at
    5.8% of the sweep, with nothing improving across the remaining 24.5 hours**.
  - **ONLY THE BEST `--write-top` PAIRS ARE RECORDED (100000 default), GZIPPED.** Every
    pair is scored, but `--top-n 10000` is 49995000 of them and writing them all produced
    a **1.67 GB file in the committed tree**. The `.meta` carries `scored`/`written`/
    `complete` like the singletons files, so a capped file cannot be read as a full one.
  - **THE PAIR LOOP IS CHUNKED BY FIRST GUESS, for the same reason the root scoring is** —
    a njit call never returns to the interpreter, and at `--top-n 10000` that is 50M pairs
    and the better part of an hour with Ctrl-C dead and nothing printed. Do not merge it
    back into one call. **Every improvement on the running best prints as it is met**
    (ties do not, or a plateau floods the log); the running minimum must start from the
    INCUMBENT, not from the row, or a row whose own minimum falls while staying above the
    global best reports improvements that are nothing of the kind. The gate pins the log
    strictly decreasing and ending on the winner. The feedback table is int16 (every code plus the -1 marker fits),
    which halves a 354 MB allocation at that N.
- **`python3 tools/nerdle_symbols.py [--set answers|guesses|classes]`** reports symbol
  frequencies three ways (occurrences, equations containing, per equation) plus a position
  table. The three sets are different denominators and none is hidden as a default —
  answers is what the game draws from, guesses is what you may type (21x larger and much
  stranger), classes is one member per commutative class.
- **`python3 tools/checknerdletopk.py` is the GATE** — the numba kernel against a plain
  numpy reference that recomputes feedback from the STRINGS with `wordle.pattern`
  (identical totals and identical openers at several widths and K), the top-ranked guess
  against an independent argmin, the class-win rule, and a check that no surviving bin
  ever carries the all-green code. It enumerates its small word lists IN MEMORY so it runs
  on a fresh clone. Run it alongside `tools/checknerdle.py`.

## Letroso (letroso.com) — NOT a Wordle variant, and every secondary source is wrong
`math/letroso.py` states the rules and IS the source of truth; read it before quoting
anything. Run it with **`bash solver/run-letroso-rank.sh --length-prior lengths`** then
**`bash solver/run-letroso-solve.sh --length-prior lengths`** (from `math/`).
- **THE RULES CAME FROM THE SHIPPED BUNDLE, NOT FROM ANY ARTICLE.** Letroso is a
  **Daydash** game (the Contexto/Conexo/Expresso studio), `lang="pt-br"` with en/es
  localisations; `letroso.org` and the SEO sites are unaffiliated and describe a
  DIFFERENT, WRONG game (they claim Wordle green/yellow plus "connection lines"). The
  real algorithm is `zT`/`BT` in `assets/index-*.js`. **There is no positional
  green/yellow at all.**
- **The feedback is a MAXIMUM-SCORING LCS ALIGNMENT** between guess and answer.
  `head`/`tail` = letters in the alignment (they occur in the answer in that relative
  order); a maximal run consecutive in BOTH guess and answer draws as one connected
  block, which is what marketing calls a connection line. `present` = in the answer by
  multiset count but out of order. `absent` = not there. Plus `start`/`end` flags when
  the alignment reaches the first/last letter of both. Among maximum-cardinality
  alignments it maximises `d = 3*sum(position within run) + start + end`, then takes the
  lexicographically largest pattern.
- **VERIFIED, not inferred: the port reproduces all TWELVE worked examples in the game's
  own instructions modal**, across all three shipped languages (en `example`, pt
  `exemplo`, es `ejemplo`). That is the only external evidence and `tools/checkletroso.py`
  pins it.
- **YOU DO NOT KNOW THE ANSWER'S LENGTH.** `Pa=10` caps what you can TYPE (hence answers
  are ≤10), there is no grid of known width, and **no minimum is stated anywhere in the
  source** — the 3 in our lists is an ASSUMPTION (user's call). Their own list has 532
  two-letter words. Unlimited guesses.
- **A GREEDY LEFT-TO-RIGHT FEEDBACK IS WRONG, and was tried.** An unmatched position
  resolves to `present` or `absent` depending on what the WHOLE alignment consumed, so
  the lexicographic comparison is not decidable position by position: `aab` against
  `babaa` is `(1,0,0,2,3)`, not the greedy's `(0,2,3,1,0)`. The differential test caught
  it; do not re-derive it.
- **THE ONE KNOWN AMBIGUITY, and it is MEASURED at zero.** The game's tie-break sort
  comparator returns "less than" for EQUAL patterns and is therefore inconsistent, so
  which of two equal-pattern alignments displays is up to V8. We resolve it by preferring
  the LATEST match (`end` over `start`), matching the reference's enumeration order.
  **On 5000 real word pairs the top pattern is NEVER tied**, so the tie-break never
  actually decides; it fires only on toy inputs like `aa`/`a`. Do not report it as a risk
  without that number.
- **THE GUESS LIST IS LETROSO'S OWN (changed 2026-09-07; it used to be hello's).** The
  one thing knowable client-side is what letroso will ACCEPT as a guess: its bundle ships
  `assets/all-en-<hash>.js`, one JSON array of **93357** lowercase words, lengths **2-10**
  (`Pa`=10 caps typing; 532 two-letter words). `build_letroso_lists.py` fetches that
  (discovering the deploy-specific hash from `index-*.js`, caching the raw bundle under
  `data/local/letroso/`) and writes per-length **guess** lists to
  `data/shared/words/letroso/len<L>/` — a NEW dir, NOT `hello/` (the Wordle length-sweeps
  still read hello's guesses and must not be disturbed). So a word we accept is a word
  letroso accepts, and one it rejects (e.g. **`clarionets`** — in hello's Scrabble
  dictionary but NOT in letroso's list) we reject too. `MINLEN` is now **2**.
  - **The earlier decision to guess from hello's lists is REVERSED.** It was the reason we
    diverged from the live game; the user's call is to match letroso's guess list wherever
    possible (2026-09-07). letroso's list is a permissive web-corpus set full of proper
    nouns/initialisms (`aachen`, `kph`, `rss`) — we take it anyway, because it IS the game.
- **THE ANSWER LIST IS STILL OURS, and NOT letroso's** — its real answer set is
  server-side and unknown. We model it from hello wordl's curated `mystery.txt` (Norvig
  frequency, hand-pruned), **INTERSECTED with letroso's guess list** so every answer is a
  legal guess (`ANS2G` indexes answers into guesses). The intersection drops ~3-14% of
  hello's answers per length (they are not letroso-legal, so unwinnable anyway). A number
  here still describes THIS game on THESE lists, never letroso.com — but the guess half
  now matches the live game exactly.
- **LENGTHS 2 AND 3 ARE OURS AND ARE A MODELLING DECISION** (`build_letroso_lists.py`).
  hello's answer curation starts at 4, so those two lengths have no hello answers; we build
  them with the same rule the len-3 list always used — keep the guess words with
  `wordfreq zipf >= ZIPF_BAR` (3.0), chosen to put the answers/guesses ratio in line with
  4-10 (58% at L=4, rising as words shorten). **The pool it now filters is LETROSO's**
  short-word list, not hello's (len 3 went 1015 -> 3619 words). `--bar` keeps a different,
  recorded rule open; each `mystery.txt.meta` records which rule built it.
- **`--length-prior` IS PART OF THE OBJECTIVE AND HAS NO DEFAULT.** `lengths` (uniform over
  the lengths present — now **9**, lengths 2-10, the user's choice) vs `words` (uniform over
  the pooled list) are different objectives. The prior derives its length set from the
  answers, so adding length 2 shifts every length's share automatically.
- **THE CACHED ROOT RANKING IS FINGERPRINTED OVER BOTH LISTS**, so this change makes
  `data/shared/letroso/root_rank_lengths.csv.gz` STALE — re-run `run-letroso-rank.sh`
  before trusting any solve. The old `hello/len3/` dir is now orphaned (only the old
  letroso path read it); harmless, left in place.
- **The ranking rule is `topk.py`'s, NOT nerdle's**: `sum over bins != win of n_b * W_b`,
  ties on lowest guess index — the expected number of candidate WORDS still alive. Sum of
  squared bin sizes is undefined here because the answers are not equally likely.
- **`-k K` restricts the ROOT too**, so the opener is the best of the K examined, not of
  139072. Each K is a different strategy and gets its own file.
- **COST, measured.** 4.23e9 feedback evaluations for a root scan, each an LCS DP rather
  than a symbol compare: **15.9 us/pair** in the numba kernel against 981 us in pure
  python, so ~19 core-hours, under an hour on 20 threads. The root ranking is CACHED
  behind a fingerprint over both lists and the prior; **a mismatch is REFUSED**, since a
  foreign ranking would be confidently wrong rather than missing. **It CHECKPOINTS to
  `data/local/letroso/` every few chunks and RESUMES** — at ~19 core-hours it has to
  survive a Ctrl-C or a reboot, so re-running the same command picks up where it stopped;
  a checkpoint whose fingerprint does not match is ignored, never resumed from. (An
  earlier version saved only on completion, which was fine for nerdle's 110s rank and a
  defect here.)
- **`python3 tools/checkletroso.py` is the GATE** — tutorial rows, `feedback` vs the
  enumerate-every-path reference over 37332 exhaustive pairs, the numba kernel vs that on
  4000 real pairs, root scoring vs an independent dict-bucketing implementation, both
  priors summing to 1, a coverage tally that FAILS if any awkward feature never fired, and
  an independent REPLAY of the solver's strategy answer-by-answer to check the cost
  accounting. Run it alongside `solver/validate.sh`.

## Lingo (`run-lingo-sweep.sh`) — Wordle with the FIRST LETTER GIVEN, per letter
Lingo (the game show) reveals the opening letter; we model ONE INDEPENDENT game
per starting letter. `math/solver/README.md` "Lingo" is the detail; the key facts:
- **NO NEW SOLVER CODE — it is the validated `optturns` on restricted lists.** For
  each letter L both the answer pool and the legal guesses are restricted to words
  starting with L, so position 0 is always green and **the feedback function is
  Wordle's, UNCHANGED**. The restriction is entirely `--guess-list` (follow-ups AND
  swept openers) + `--answer-list` (the total's answers) + `--patterns` (a matrix
  built for exactly those columns). `validate.sh` is untouched and still passes.
- **THE FEEDBACK RULE IS UNVERIFIED** against the real show — we assume Wordle's
  green/yellow/grey with Wordle's duplicate-letter handling (the user's modelling
  call, 2026-09-07). Same standing as the Absurdle / Sea-of-Greens rules; a real
  Lingo board would settle it. Say so when quoting any number.
- **THE ANSWER POOL IS THE CURATED mystery LIST** (user's call): length 5 = the
  2315 NYT answers filtered by letter, guesses from the 12972 — the lists
  `patterns.npy` is built from. Length 6 has no NYT set, so it falls back to the
  **hello wordl** len-6 lists like the length sweeps — a different, NOT comparable
  curation (see "Other word lengths"). A number describes THIS game on THESE lists.
- **THE CAP IS PART OF THE OBJECTIVE.** Lingo gives five guesses (the given first
  letter is not one), so `--depth 5` IS the game; `--depth` is REQUIRED and each
  depth gets its own results dir. `INFEASIBLE` is an expected result (normal
  Wordle's "follow SALET's tree" escape needs a word that starts with L, so it does
  not transfer) — report totals as optima SUBJECT TO the guarantee, never as
  minimum expected guesses. Never table a Lingo total beside an `optturns` one.
- **`-k K` is a beam (upper bound) and restricts the ROOT too** — same caveat every
  `--topk` sweep here carries.
- **Run it with `bash solver/run-lingo-sweep.sh --depth 5 [--length L] [--letter X]`
  (from `math/`)**, attached, tee'd-log rules as the other sweeps. It auto-builds
  the per-letter lists (`build_lingo_lists.py`) and per-letter matrix
  (`build_patterns.py --answer-list`, additive + off the shared matrix paths).
  Length 5 uses plain `optturns`; other lengths need `sh build.sh <L>` first.
  Data: committed CSVs in `data/shared/lingo/len<L>_d<D>/<letter>_totals.csv`;
  matrices/trees/tt/log under `data/local/lingo/`. `python3 tools/lingo_report.py
  --length L --depth D` prints the best opener per letter.
- **`python3 tools/checklingo.py` is the GATE.** The one new artifact is the
  per-letter matrix, so the load-bearing check diffs every column BIT-IDENTICAL
  against the shared length matrix (`checkpatterns.py` validates that against
  `wordle.pattern`), proving true feedback AND correct column order; it also pins
  the lists as exactly the filtered full lists and replays emitted trees
  length-generally. Run it alongside `solver/validate.sh` and `checkpatterns.py`.

## `eldrowmax` — the LONGEST CONSISTENT CHAIN (every play a possible answer)
The exact answer to "how long can a game be dragged out if every word you play must
still be a POSSIBLE ANSWER — consistent with every clue so far?". Run it with
**`bash solver/run-eldrowmax.sh [--greedy | --target N | --floor N | --exact]`**
(from `math/`), attached, tee'd log; `--dry-run` resolves and stops.
- **IT IS `math/eldrow.py`'s `longest_chain` OBJECTIVE, made exact and made to
  scale.** That module states the rule and REMAINS THE REFERENCE; its exact search
  is Python branch-and-bound (tiny lists only) and its full-list mode is a beam,
  which finds chains and never proves one longest.
- **eldrow COUNTS ONE LESS.** It counts guesses-until-a-singleton; `eldrowmax`
  counts the WORDS IN THE SEQUENCE, the final naming move included. `c == python +
  1` exactly, and the gate asserts that relation rather than comparing loosely.
- **THREE DIFFERENT GAMES, and their totals never share a table.** `optturns`
  minimises; `antistall` maximises under ANTIWORDLE's legality — greens in place,
  yellows reused, greys as count caps — which is a strictly LOOSER rule admitting
  words the answer could not be (11 of the 16 plays in its best known line are
  guess-only junk like `bunjy`); `eldrowmax` maximises where every play is a live
  candidate. Same words, three objectives.
  - **BOTH LANDED ON 16, AND THAT IS A COINCIDENCE, NOT AN AGREEMENT (2026-09-09).**
    `antistall`'s `bully` line is 16 words; the first `eldrowmax` ladder also reached
    16 (not yet final — bar 17 was untested). The two numbers are about DIFFERENT
    GAMES and must never be quoted as confirming each other. The proof is the `bully`
    line itself: **only 5 of its 16 words (`buddy buggy bulky bully bushy`) are in
    the 2315 answer list at all**, so 11 of its plays are illegal here whatever the
    clues. `eldrowmax`'s 16 is under the strictly tighter rule.
  - **Asked "didn't we already find a 16?", CHECK WHICH SOLVER.** That question came
    up and was answered about `eldrow` (which has never been run) while the 16 the
    user remembered was `antistall`'s, recorded in
    `data/shared/antiwordle/stall.longest.csv` — a correct memory made to look wrong
    by answering the narrow question instead of asking which result was meant.
- **THE POOL IS PART OF THE OBJECTIVE**, `--words`, defaulting to the 2315 mystery
  answers (the user's call, 2026-09-09: plays drawn from the possible answers, and
  the answer likewise from the 2315). Every pool word must be in the pattern
  matrix's lists. A different pool is a different quantity and gets its own CSV.
- **THERE IS NO ANSWER TO FIX, and that is what makes it cheap** — unlike
  `antistall`, which sweeps 2315 separate searches. Choosing which feedback branch
  to follow IS choosing which answer survives, so the maximum over answers and the
  maximum over branches are one maximum, taken in a single search from the full
  list. The answer is just the last word of the chain.
- **THE STATE IS THE CANDIDATE SET AND NOTHING ELSE**, and a move is `(word,
  feedback)`. So two moves reaching the same bucket are the same subgame — which is
  what pass 1 dedups on, a strictly coarser collapse than dedup by feedback.
- **ONE BOUND, `value(S) <= |S|`** (every move drops at least the word played).
  **ANTISTALL'S OTHER TWO BOUNDS DO NOT TRANSFER and are deliberately absent**: its
  resource bound counts count-pins and square-bans, its letters bound counts
  untouched letters plus non-green squares, and both are facts about how
  antiwordle's CONSTRAINT tightens, not about how a candidate set shrinks. Carrying
  either across would have silently cut correct lines.
- **A SEPARATE BINARY, not a mode of `antistall.c`** (the `greens` precedent): it
  shares the loader, the table and the arena and NONE of the search — with plays
  restricted to the live set, `DELTA[g]` cannot express a move.
- **The DEFAULT is the decision ladder** (greedy playout for an incumbent, then
  `can_reach(bar + 1)` until it fails), because a subtree dies the moment it cannot
  reach the target rather than when it has been measured. `--exact` computes the
  same number by outright maximisation and is kept as the ladder's oracle; the gate
  diffs them. **The memo key carries the budget**, so every entry stays exact.
- **NO DEPTH CAP AND NO BEAM** — the game has none and a restricted search would
  not be the maximum. `MAXD` is an array bound (a chain cannot outlast its pool).
- **MEASURED 2026-09-09 on the 2315 pool, 18 threads:** greedy 9 in seconds; the
  ladder climbs 10, 11, 12, 13, 14, 15 in ~46s total, and **bar 16 decides in 29s**
  (58437 root moves to try, of 151333 children). Whether 17 is reachable is OPEN.
- **THE WITNESS REBUILD MUST USE THE SEARCH'S OWN WITNESS — this was a real defect,
  not a slow path.** `root_can_reach` runs the root's children across every thread
  and STOPS on the first success, so moves earlier in the canonical order are never
  tested; a `walk_line` that re-derived the line by scanning that order then paid
  full price for exactly those. MEASURED: bar 16 decided in 29s and its witness had
  not been rebuilt **six minutes** later, which reads as a hang. Taking the move
  from the search's witness at the root and from the TT below it (both VERIFIED —
  the word must be live and the child must reach the remaining budget, with the
  scan still underneath for an evicted entry) makes the whole run 29.1s including
  the rebuild.
- **THE LENGTH IS DETERMINISTIC; THE WITNESS LINE IS NOT.** The root loop stops on
  the first success, so which successful moves get tested depends on timing and a
  re-run can report a DIFFERENT chain of the SAME length (at `--threads 1` it is the
  canonical first success and is reproducible). Say "a longest chain", never "the".
- **EVERY IMPROVEMENT IS FLUSHED AS IT LANDS, and the length is recorded BEFORE the
  witness.** `status` is `greedy` / `reached` (length proved, line not yet rebuilt) /
  `improved` (with the line) / `final` (the ladder failed at length + 1, so nothing
  longer exists). A killed run writes no `final` row, which is exactly how a reader
  tells it from a finished one — and the `reached` row exists because the rebuild
  can outlast the decision, so a Ctrl-C in between used to discard a proved result.
- **`python3 tools/checkeldrowmax.py` is the GATE**: the value against
  `eldrow.longest_chain` plus one; the emitted line REPLAYED FROM THE STRINGS with
  `wordle.pattern` (every play consistent with every earlier clue, exactly ONE
  survivor at the end — a line ending with two alive is self-refuting); the line's
  length against the value; the ladder against `--exact`; `--no-prune` against
  pruned; a deliberately tiny table (the fingerprint IS the memo key, and a
  correlated-halves collision is exactly what got past a value-only diff in
  `antistall`); and `--threads 1` against `--threads 4`.
  - **ITS POOLS ARE REACHABLE GAME STATES, NOT RANDOM SUBSETS, and that is
    load-bearing.** A random sample of the 2315 is dissimilar enough that the first
    guess shatters it into singletons, so every case came back 3 with the recursion
    barely entered. Pools are built the way the game builds one: play a word, keep a
    bucket, repeat.
  - **THE HARD CASE IS HUNTED FOR, NOT HOPED FOR.** Greedy is optimal on most
    pools, and a pool where it is exercises none of the search; on random seeds the
    tally came up empty as often as not. So the gate keeps drawing until greedy is
    STRICTLY short of the answer, and failing to find one is itself a finding.
- Data under `math/data/shared/eldrow/eldrowmax.<pool>.csv`, one row per run with
  every knob as a column; log under `math/data/local/eldrow/`.
- **The rest of the antiwordle family (`antistall`, `antiexpect`, `antiwordle.py`,
  `eldrow.py`) has NO section here** — the source headers and the wrapper comments
  are the documentation. Worth writing up when one of them is next touched.

## `schedule(dynamic)` IS STATIC-STEAL ON THE MACS -- what a progress log means
**MEASURED 2026-09-16, and it explains a log that reads like a bug.** libomp
implements `schedule(dynamic, N)` as **static-steal**: each thread starts on its
own contiguous 1/nthreads slice of the iteration space and only steals from the
others once its own slice is exhausted. Verified three ways: thread first-touches
in `secondexact`'s walk were `0, 721, 1442, ... 12252` (exactly `ceil(12972/18)`
apart), a 20-line standalone program reproduces it with no solver code, and the
clause IS parsed -- `static,1` gives round-robin and `guided` its own pattern.
**`schedule(monotonic:dynamic, 1)` restores a true shared queue** (all threads
then start near k=0); a manual atomic counter would too.
- **IT IS NOT A LOAD-BALANCE PROBLEM -- CHECK BEFORE ASSUMING IT IS.** The
  stealing works: after 4 hours `ps -M <pid>` showed all 18 threads `R` with
  per-thread CPU between **119:58 and 120:01** -- a 3-second spread in 7200.
  Process-level `%CPU` CANNOT distinguish "18 threads at 47%" from "9 threads at
  100%"; `ps -M` can, and is the tool to reach for.
- **WHAT IT DOES CHANGE is the ORDER openers are TESTED in**, which is why a
  bound-sorted walk's cuts arrive in lumps of one slice. In the mv run, threads
  16 and 17 owned k=11532-12251 and 12252-12971, both entirely above the
  incumbent, so each evaluated ONE opener (its first, before the incumbent had
  improved past its band) and then cut the other 719 in milliseconds: **1438 =
  2 x (720 - 1)**, arriving a full evaluation AFTER the incumbent that enabled
  them. The next band flips only when a thread grinds down to it.
- **It does NOT affect any RESULT.** Every iteration runs exactly once, and a cut
  is sound whatever the order, since the incumbent is always the value of a
  strategy that exists.
- **The comment in `secondexact.c` claiming "the first opener whose bound exceeds
  the incumbent proves the whole tail is worse" describes a SERIAL walk and is
  not what runs.** The end-of-run claim is still true; the "first cut ends it"
  mechanism is not. Not yet corrected in the source (2026-09-16).

## `--tt-save` IS BACKWARDS EVERYWHERE — no wrapper writes a table any more
**Fixed 2026-09-09 in all five wrappers that did it** (`run-length-sweep.sh`,
`run-ultra-sweep.sh`, `run-mm-sweep.sh`, `run-strturns-sweep.sh`,
`run-strsts-sweep.sh`), generalising the fix `run-greens.sh` already carried.
- **THE FLAG CANNOT DO WHAT IT LOOKS LIKE IT DOES.** `tt_save` sits at the END of a
  code path, so it fires ONLY on normal completion — exactly when the table is
  worthless, because a finished run's CSV marks its work done and a re-run resumes,
  finds nothing to do and exits WITHOUT READING IT. The case that would pay, an
  interrupted run, saves nothing: **there is no signal handler in `optturns.c` or
  `strturns.c`**, so Ctrl-C never reaches the line.
- **MEASURED, and it is why the machine stopped working:** 302 snapshots at 8 GB
  each = **728 GB, 79% of the disk**, filling it to 1.1 GB free so that no process
  could write at all. One was an 8 GB table beside a **4 KB** result from a run that
  took **2 SECONDS**. It multiplies because each settings combination gets its own
  directory and table, so a sweep over ~20 values of K leaves ~160 GB for ONE word
  length (`optlen10` 160 GB, `optlen11` 152 GB, `optlen9` 108 GB, `ultraturns` 92).
- **The long sweeps never had this** — `run-sweep.sh`, `run-ans-sweep.sh` and
  `run-hard-sweep.sh` do not pass `--tt-save`. They snapshot the LIVE table with
  `tools/ttdump.py`, which is the mechanism that actually survives a kill. **That is
  the route to use if a warm table is ever genuinely wanted.**
- **`--tt-load` stays in all of them.** It costs nothing and a deliberately-made
  table is still worth warming from; with nothing writing one, `WARM` is just empty.
- `math/data/local/pairs/tt.bin` and `tt_ans.bin` were KEPT — `run-ans-sweep.sh` is
  the one place a snapshot is load-bearing.

## OPEN: the fixes above should not have needed doing five times
**The user's call, 2026-09-09 — RAISED, NOT YET SCHEDULED. Do not start it without
asking.** The `--tt-save` bug had already been diagnosed and fixed once, in
`run-greens.sh`, complete with a written explanation of why the flag is backwards —
and it still cost 728 GB, because the fix lived in one wrapper and the other five
were never revisited. The wrappers are largely copies of each other (same `WARM`
block, same `guard_output`, same tee'd-log preamble, same bash-3.2 array guards), so
a correction to one is invisible to the rest.
- The same shape has bitten repeatedly and is worth listing when the refactor is
  scoped: the `date -Is` GNU-ism (fixed in `run-greens.sh`, still broken in
  `run-sweep.sh`, `run-hard-sweep.sh`, `run-ans-sweep.sh`), the missing `--out`
  (`run-wordle-in-one.sh` is still red in `checkconventions.sh`), and this one.
- `solver/checkconventions.sh` is the existing mechanism for exactly this and it
  works — it is what catches a missing wrapper or a missing `--out`. **A cheaper
  first step than a refactor is probably a new CHECK there** ("no wrapper passes
  `--tt-save`", "every wrapper uses the portable `date`"), since a check applies
  everywhere by construction and needs no shared code.

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
