# wordle video — specifics

wordle-only conventions. The shared cross-video rules (`bpkfigures/CLAUDE.md`)
and private operational notes (`dotclaude/CLAUDE.md`) load via the two in-tree
symlink imports below — a within-project `@import` path pointing out via a symlink
(an additional-dir CLAUDE.md won't auto-load, and a cross-dir `@../` import won't
expand). Committed + portable. See `yahtzee/CLAUDE.md` "Config loading" for the
full cross-machine history.

@CLAUDE.shared.md
@CLAUDE.private.md

> **Import canary — check this first.** The two `@import`s above pull in the
> shared and private rules through committed symlinks. If you cannot see the
> tokens `SHARED-RULES-LOADED` and `PRIVATE-RULES-LOADED` in your context, those
> imports **silently failed** and you are missing every shared and private
> convention. Usual cause: the workspace was opened Windows-side over
> `\\wsl$\`, where the WSL symlinks are unreadable 23-byte stubs. Recover by
> reading `bpkfigures/CLAUDE.md` and `dotclaude/CLAUDE.md` directly, and tell the
> user to reopen the workspace from a WSL shell
> (`cd ~/projects/ballpark-figures && code <video>.code-workspace`) so the
> bottom-left of VS Code reads `WSL: Ubuntu-22.04`.

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
- `math/solver/` is the C solver computing the exact minimum expected turns for
  every one of the 12972 openers, plus each one's optimal tree. **Read
  `math/solver/README.md` first** — build, flags, output format, gotchas.
- The objective is an INTEGER (total guesses over all 2315 answers), so results
  are exact, not float-compared. Validate any solver change with
  `bash solver/validate.sh` from `math/`: SALET 7920, REAST 7923, TRACE/CRATE
  7926, SLATE 7928 (Bertsimas & Paskov Table 1, reproduced exactly).
- Long sweep resumes with `bash ~/bin/resume-jobs.sh` (skips finished openers
  via the CSV, warm-starts the transposition table from `tt.bin`). A Windows
  Scheduled Task runs the same script at boot so a forced Windows Update
  restart self-recovers.
- Outputs follow the shared/local split: **`math/data/shared/optturns/opener_totals.csv`**
  is the committed result that syncs between machines;
  `math/data/local/optturns/` holds the regenerable bulk (`trees/`, `tt.bin`,
  `sweep.log`, `archive/`).
- `math/tools/` holds the analysis scripts, all importing `paths.py` for
  locations. **`python3 math/tools/report.py`** is the standing status report
  (progress, best/worst, 0.01-bin histogram with percentiles, slowest solves);
  also `lookup.py` (rank named openers), `vowels.py`, `depths.py` (tree depth +
  tree-vs-CSV check), `ttdump.py`/`ttverify.py`/`ttscan.py` (table snapshots).

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
