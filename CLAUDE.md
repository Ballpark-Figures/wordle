# wordle video — specifics

wordle-only conventions. The shared cross-video rules (`bpkfigures/CLAUDE.md`)
and private operational notes (`dotclaude/CLAUDE.md`) load via the two in-tree
symlink imports below — a within-project `@import` path pointing out via a symlink
(an additional-dir CLAUDE.md won't auto-load, and a cross-dir `@../` import won't
expand). Committed + portable. See `yahtzee/CLAUDE.md` "Config loading" for the
full cross-machine history.

@CLAUDE.shared.md
@CLAUDE.private.md

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

## Gameplay layout
- (Describe this video's on-screen layout and the assets in `animations/assets/`.)

## Style
- Uses `bpkfigures` style + the local `config.py` for colors/fonts.
