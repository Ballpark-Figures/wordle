from bpkfigures.scene import *

# ── Wordle's own dark-mode palette ────────────────────────────────────────────
# The REAL NYT dark-mode colours, named here because they are not in style.py and a
# scene may never inline a hex. They are deliberately authentic rather than brand:
# the green in particular is load-bearing recognition — viewers know these tiles at a
# glance, and a brand-accent board would not read as Wordle. A later scene wanting
# brand accents swaps these constants; the board asset reads them and never hardcodes.
WORDLE_BG = "#121213"          # page background
TILE_EMPTY_BORDER = "#3a3a3c"  # an untouched tile's border
# An untouched (or typed, unscored) tile is FILLED with Wordle's own near-black, so
# the board reads as the real game's even on the navy background (user's call,
# 2026-09-28, for every board). Scoring replaces it with the TILE_STATE colour.
TILE_EMPTY_FILL = WORDLE_BG
TILE_FILLED_BORDER = "#565758" # a typed but unsubmitted tile — brighter border
TILE_ABSENT = "#3a3a3c"        # scored: letter not in the word
TILE_PRESENT = "#b59f3b"       # scored: right letter, wrong place
TILE_CORRECT = "#538d4e"       # scored: right letter, right place
TILE_TEXT = "#ffffff"

# Feedback code -> scored fill, indexed by the trit values wordle.pattern emits
# (0 absent, 1 present, 2 correct). Keeping this next to the colours means the
# board asset never maps a code to a colour itself.
TILE_STATE = {0: TILE_ABSENT, 1: TILE_PRESENT, 2: TILE_CORRECT}


class WordleScene(BpkScene):
    def construct(self):
        self.camera.background_color = BG_COLOR
        super().construct()


class WordleBoardScene(BpkScene):
    """THE DEFAULT FOR BOARD/GAMEPLAY SCENES — the board on BOARD_NAVY (user's call,
    2026-09-28), the same navy scene 01 settles on after its opening."""

    def construct(self):
        self.camera.background_color = BOARD_NAVY
        super().construct()


class WordleDarkScene(BpkScene):
    """A scene on Wordle's own near-black. NOT the board default any more — kept for
    scene 01, whose script opens on the authentic dark page and fades to navy."""

    def construct(self):
        self.camera.background_color = WORDLE_BG
        super().construct()
