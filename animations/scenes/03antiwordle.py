"""Scene 03 — the antiwordle chain: 16 guesses, every one a possible answer. Navy background.

The empty 6-row board is up from frame 0 (setup_scene), as in scene 02 — the scene
follows talking head THB, which covers the cut in. It ends on the three-column
layout, since THC follows.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a chain    — all 16 words typed and QUICK-scored (5 tiles flip at once) in one
               giant column; from the 7th guess on, the column shrinks to fit a
               new row before each word                              (03a, VO 1)
  b columns  — the column rearranges into 3 columns of 6 rows       (03b, VO 2)

REUSE MAP — every element and the one source it comes from:
  board + tiles + letters  assets/board.py `get_board`, as scenes 02/97
  typing pop               board.type_word
  quick score              board.reveal with lag_ratio=0 — the same TileFlip,
                           all five tiles together (no new motion)
  growing column           board.add_row (added for this scene)
  keystroke sfx            assets/keys.py `key_cues`
  colours                  BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  the 16 words + codes     assets/game_data.py load("antiwordle") -> game_cache.json:
                           the `final` row of math/data/shared/eldrow/eldrowmax.
                           mystery.csv, codes from math/wordle.py `pattern`
No other on-screen text: column 2 asks only for the words and their scoring.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board, TILE, GAP, COLS, ROWS
from assets import game_data
from assets.keys import key_cues

# dB: this scene types quieter than the video-wide TYPING_GAIN (-6) (user 2026-10-06)
TYPING_GAIN_03 = -12.0

GAME = game_data.load("antiwordle")
WORDS = [g["word"] for g in GAME["guesses"]]
CODES = [g["code"] for g in GAME["guesses"]]

# The column holds the height of the ordinary 6-row board as it grows: "shrink the
# text to fit the new row in", so every row from the 7th on costs a shrink.
COLUMN_H = ROWS * TILE + (ROWS - 1) * GAP

# ...but the column also GROWS toward the full frame as words are added, evenly per
# row: the ordinary board's height at 6 rows, COLUMN_H_MAX at the last word. So
# each new row still shrinks the tiles, just less than a fixed height would.
COLUMN_MARGIN = 0.4        # space kept above and below the finished column
COLUMN_H_MAX = config.frame_height - 2 * COLUMN_MARGIN


def column_height(n_rows):
    """The column's height once it holds `n_rows` rows (6 .. len(WORDS))."""
    t = (n_rows - ROWS) / (len(WORDS) - ROWS)
    return COLUMN_H + t * (COLUMN_H_MAX - COLUMN_H)

# 03b: three 6-row boards side by side. The third holds 4 words and 2 empty rows,
# so the frame shows three full games' worth of rows.
GRID_SCALE = 0.85          # tile size as a fraction of the ordinary board's
GRID_COL_GAP = 0.6         # space between the three boards


class Scene03(WordleBoardScene):
    """BEAT MAP
    chain — the 16-word chain, typed and quick-scored in one growing column
    columns — rearranged into 3 columns of 6 rows
    """

    def setup_scene(self):
        self.board = get_board()
        self.add(self.board)

    # a : the chain — type, quick-score; past the 6th guess, shrink to fit a row
    @subscene
    def chain(self):
        type_rt, score_rt, grow_rt = 0.35, 0.3, 0.25       # lockstep, all 16
        for i, word in enumerate(WORDS):
            if i >= ROWS:
                self.board.add_row(self, grow_rt, column_height(i + 1))
            elif i > 0:
                self.wait(grow_rt)       # the first six keep the grow's beat (none before guess 1)
            self.board.type_word(self, i, word, type_rt,
                                 per_letter=key_cues(self, gain=TYPING_GAIN_03))
            self.board.reveal(self, i, CODES[i], score_rt, lag_ratio=0)

    def _setup_columns(self):
        """Target pose of every row in the 3 x 6 grid, plus the 2 empty rows."""
        s = GRID_SCALE
        width = s * (COLS * TILE + (COLS - 1) * GAP)
        height = s * COLUMN_H
        self.grid_slots = []
        for k in range(3 * ROWS):
            c, r = divmod(k, ROWS)
            x = (c - 1) * (width + GRID_COL_GAP)
            y = height / 2 - s * (TILE / 2 + r * (TILE + GAP))
            self.grid_slots.append(np.array([x, y, 0.0]))
        n_empty = 3 * ROWS - len(WORDS)
        self.grid_empty = get_board(rows=n_empty).scale(s)
        for row, slot in zip(self.grid_empty.rows, self.grid_slots[len(WORDS):]):
            row.move_to(slot)

    # b : into 3 columns of 6 rows — three games' worth of guesses
    @subscene
    def columns(self):
        self._setup_columns()
        f = GRID_SCALE * TILE / self.board.tiles[0][0].width
        moves = []
        for i in range(len(WORDS)):
            row = VGroup(*self.board.tiles[i], *self.board.letters[i])
            moves.append(row.animate.scale(f).move_to(self.grid_slots[i]))
        self.play(*moves, run_time=1.5)
        self.play(FadeIn(self.grid_empty), run_time=0.6)
