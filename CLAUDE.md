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

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
