"""Scene 15 — multi-word openers, and a strategy that always wins. Navy background.

Scene 14 ends with everything faded out, so a starts on an empty frame. Talking head
THJ follows, so the scene may end with LEDGE PAWNS ROCKY THUMB on screen.

BEAT MAP — one subscene per Script.md beat, letters matching. BUILT SO FAR: a-d.

  a second_words — SALET in the top-left corner and its 148 groups as coloured rows
                   (scene 12's view, no dots: user's call) fade in; every optimal
                   second word is typed under its row at once      (15a, VO 1)
  b clone        — every second word flips to CLONE                (15b, VO 2)
  c to_board     — the corner SALET (the uncoloured one: user's call) and the
                   largest group's CLONE travel into rows 1 and 2 of a board in the
                   middle as its other rows fade in around them; everything else
                   shrinks away                                    (15c, VO 3)
  d third        — THIRD typed into row 3                          (15d, VO 3)
  e-za           — not built yet

REUSE MAP — every element, the one source it comes from, and how it enters:
  SALET (a)             assets/pigpen.py `PigpenWord(revealed=True)` at GUESS_SCALE in
                        the corner — scene 12's corner word (assets/second_view.py
                        `corner_spot`, moved out of scene 12 for this scene)
  coloured rows (a)     assets/second_view.py `group_rows` — 12's rows at 06b's
                        dot-view sizes, sorted by size
  a's entrance          plain FadeIn of the word and rows together (13a's: the frame
                        was cleared, 13number_line.py:182)
  second words (a)      12d's typing: `WordleBoard.type_anim` under each row, all in
                        ONE play, key sound on the first only (12efficient_strats.py
                        second_words); words from strategy_data (the optimal trees)
  CLONE (b)             assets/flip.py `Flip` by `row_parts`, every word at once (12e's
                        word flips); typed rows by second_view `typed_under`
  board (c)             assets/board.py `get_board()` at the origin, unscaled — 02's and
                        04's board; rows 3-6 fade in as SALET and CLONE travel
  rows leaving (c)      06b's shrink-out (strategy_line `shrink_out`)
  THIRD (d)             `WordleBoard.type_word` + assets/keys.py `key_cues` (02's typing)
  colours               BOARD_NAVY via WordleBoardScene

EVERY NUMBER is sourced (assets/always_win_data.py -> its cache; provenance there).
The words of a-d are the script's (SALET, CLONE, THIRD) and the optimal trees'.

LAYOUT CHOICES, flagged:
  - c: CLONE comes from the largest group's slot (the first row), the one nearest
    the corner; every CLONE is the same word.
  - c: the travelling rows' tile borders thicken to the board's STROKE as they grow.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from assets import lists_data, strategy_data, always_win_data
from assets.board import STROKE, WordleBoard, get_board
from assets.pigpen import PigpenWord
from assets.flip import Flip, flip, row_parts
from assets.groups import GUESS_SCALE
from assets.keys import key_cues
from assets.second_view import corner_spot, row_stroke, under, typed_under, group_rows
from assets.strategy_line import StrategyLine, shrink_out

DATA = lists_data.load()
SD = strategy_data.load()
AW = always_win_data.load()
SALET, CLONE, THIRD = "salet", "clone", "third"      # the script's words


def _tiles(row):
    """A word row's tiles: a PigpenWord's, or a one-row board's."""
    return row.tiles if isinstance(row, PigpenWord) else row.tiles[0]


class Scene15(StrategyLine, MovingCameraScene, WordleBoardScene):
    """second_words — SALET and its coloured rows; every optimal second word typed
    clone — every second word flips to CLONE
    to_board — SALET and a CLONE into a board's first two rows; the rest goes
    third — THIRD typed into row 3
    """

    def setup_scene(self):
        pass

    # a : SALET in the corner and its coloured rows fade in; every optimal second
    #     word is typed under its row at once
    def _setup_second_words(self):
        corner, left = corner_spot(SALET)
        self.guess = PigpenWord(SALET, revealed=True).scale(GUESS_SCALE).move_to(corner)
        self.groups, self.rows, _, _ = group_rows(DATA, SALET, left)
        sec = SD["second"][SALET]
        self.blanks = []
        for g, row in zip(self.groups, self.rows):
            b = WordleBoard(rows=1, cols=5)
            b.scale(row.width / b.width).move_to(under(row))
            self.blanks.append((b, sec[str(g["code"])]))

    @subscene
    def second_words(self):
        self._setup_second_words()
        self.play(FadeIn(self.guess), *[FadeIn(r) for r in self.rows], run_time=1.0)
        anims, total = [], 0.0
        for i, (b, word) in enumerate(self.blanks):
            a, total = b.type_anim(self, 0, word, 0.65,
                                   per_letter=key_cues(self) if i == 0 else None,
                                   appear=True, stroke=row_stroke(b.width))
            anims.append(a)
        self.play(*anims, run_time=total)
        self.words = [b for b, _ in self.blanks]
        self.blanks = None

    # b : every second word flips to CLONE
    def _setup_clone(self):
        self.clones = [typed_under(CLONE, row) for row in self.rows]

    @subscene
    def clone(self):
        self._setup_clone()
        flip(self, [Flip(old, new, parts=(row_parts(old), row_parts(new)))
                    for old, new in zip(self.words, self.clones)], 1.2)
        self.words, self.clones = self.clones, None

    # c : SALET and the first CLONE travel into a board's first two rows as its
    #     other rows fade in; everything else shrinks away
    def _setup_to_board(self):
        self.board = get_board()
        self.movers = []
        for mob, r in ((self.guess, 0), (self.words[0], 1)):
            target = self.board.rows[r]
            mob.generate_target()
            mob.target.scale(target.width / mob.width).move_to(target)
            for t in _tiles(mob.target):
                t.set_stroke(width=STROKE)
            self.movers.append(mob)
        self.leaving = self.rows + self.words[1:]

    @subscene
    def to_board(self):
        self._setup_to_board()
        self.play(*[MoveToTarget(m) for m in self.movers],
                  *[shrink_out(m) for m in self.leaving],
                  *[FadeIn(r) for r in self.board.rows[2:]],
                  run_time=1.5)
        self.remove(*self.leaving)
        self.salet_row, self.clone_row = self.movers
        self.rows = self.words = self.groups = self.leaving = self.movers = None

    # d : THIRD typed into row 3
    @subscene
    def third(self):
        self.board.type_word(self, 2, THIRD, 0.65, per_letter=key_cues(self))
