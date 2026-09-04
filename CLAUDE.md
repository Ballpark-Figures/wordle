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
- **THE OBJECTIVE IS LEXICOGRAPHIC (user's call, 2026-09-03), and it is NOT "maximise
  P(badge)".** Clause 1 is a HARD CONSTRAINT — the strategy must win every one of the
  2315 answers within 6. Clause 2 maximises the badge count among strategies that
  never lose. **Once a yellow appears the badge is gone for that answer and the play
  is only required to FINISH the game** — "we stop checking". So the number is a
  maximum SUBJECT TO a 6-guess guarantee; never quote it as an unconstrained one, and
  never put it in a table beside the multiwordle/foximax/adversarial figures, which
  are expected guesses OUTRIGHT.
  - **CLAUSE 1 MEASURABLY BINDS** — `checkgreens.py` computes the unconstrained value
    too, purely to prove it: on the small case `moobs` at d=3 scores 3 constrained
    against 4 unconstrained. The constraint is not decoration.
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
- Data under `math/data/{shared,local}/greens/`; trees in `shared/greens/trees/`.
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
- **The gates: `python3 math/tools/checktopk.py` and `math/tools/checkfreqsearch.py`.**
  The first diffs the numba kernel against a pure-numpy reference implementing the
  identical rules (k=1/2/3, exact agreement), checks the pattern slice against
  `wordle.pattern` recomputed from the strings, the cost accounting against an
  independent replay, every trace against the strings, and that zeroed words are
  identical to removed ones. The second checks the weight product from strings, a
  monotone log, and an exact CSV replay. Run both after any change to either file.

## Multiwordle (k boards at once) — a SIMULATION, not a solver
k hidden answers, one per board, every guess played on every unsolved board at once.
**Nothing here searches or optimises** — it MEASURES one named heuristic by Monte
Carlo, so its numbers carry a standard error and are not comparable with any
`optturns`-family optimum.
- **The strategy, exactly** (`math/multiwordle.py` states it and is the source of truth):
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
- **`python3 tools/checkmultiwordle.py` is the GATE**: it replays the same seeds
  through an independent implementation that keeps candidates as LISTS OF WORDS and
  recomputes every feedback from the strings with `wordle.pattern` — no matrix, no
  bitmaps — and demands byte-identical guess sequences at k=1/2/3/5, across openings
  of one, two, three and four words. It also tallies how many turns actually hit a
  BOARD TIE and FAILS if none did anywhere, so a passing run cannot silently mean the
  tie-break was never exercised. Run it alongside
  `solver/validate.sh` and `tools/checkpatterns.py`.

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

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
