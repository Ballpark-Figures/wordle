from bpkfigures.scene import *

# ── The Wordle palette ────────────────────────────────────────────────────────
# Wordle's dark-mode colours, with the three SCORED tiles brightened toward the
# channel palette (user's call, 2026-09-28, option B of scenes/95palette_test):
# yellow is the channel's ACCENT_GOLD toned down 10%, green a lifted green,
# grey a notch lighter. Still unmistakably Wordle's grey/yellow/green, which is the
# recognition that matters. The NYT originals are kept alongside for reference.
# The board asset reads these and never hardcodes.
WORDLE_BG = "#121213"          # page background
TILE_EMPTY_BORDER = "#3a3a3c"  # an untouched tile's border
# An untouched (or typed, unscored) tile is FILLED with Wordle's own near-black, so
# the board reads as the real game's even on the navy background (user's call,
# 2026-09-28, for every board). Scoring replaces it with the TILE_STATE colour.
TILE_EMPTY_FILL = WORDLE_BG
TILE_FILLED_BORDER = "#565758" # a typed but unsubmitted tile — brighter border
TILE_ABSENT = "#4a4a4d"        # scored: letter not in the word   (NYT #3a3a3c)
TILE_PRESENT = "#D19337"       # scored: right letter, wrong place (NYT #b59f3b)
                               #   ACCENT_GOLD (#E8A33D) at 90% brightness
TILE_CORRECT = "#4CB050"       # scored: right letter, right place (NYT #538d4e)
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
