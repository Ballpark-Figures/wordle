"""Scene 02 — the rules of Wordle, played on one board against ENDED. Navy background.

The empty board is up from frame 0 (setup_scene) — the scene follows talking head
THA, which covers the cut in — and it ends on the full board, since THB follows.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a type_begin     — BEGIN typed into row 0                        (02a, VO 1)
  b score_begin    — row 0 flips: E, N present                     (02b, VO 2)
  c type_edits     — EDITS typed into row 1                        (02c, VO 3)
  d score_e        — E alone flips: correct                        (02d, VO 3)
  e score_d        — D alone flips: present                        (02e, VO 3)
  f score_edits    — I, T, S flip: absent                          (02f, VO 3)
  g type_melee     — MELEE typed into row 2                        (02g, VO 4)
  h score_melee    — row 2 flips: E present, E correct, E absent   (02h, VO 4)
  i type_ended     — ENDED typed into row 3                        (02i, VO 5)
  j score_ended    — row 3 flips all correct, then the winning bounce (02j, VO 5)

REUSE MAP — every element and the one source it comes from:
  board + tiles + letters  assets/board.py `get_board`, as scene 97
  typing pop               board.type_word
  scored flip              board.reveal; d/e/f use its `cols=` to flip part of
                           the row, always passing the full row's code
  keystroke sfx            assets/keys.py `key_cues` (shared with scene 97)
  colours                  BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  feedback codes           assets/game_data.py load("rules") -> game_cache.json,
                           computed by math/wordle.py `pattern` — never by hand
No other on-screen text: column 2 asks only for the words and their scoring.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board
from assets import game_data
from assets.keys import key_cues

GAME = game_data.load("rules")
WORDS = [g["word"] for g in GAME["guesses"]]
CODES = [g["code"] for g in GAME["guesses"]]


class Scene02(WordleBoardScene):
    """BEAT MAP
    type_begin — BEGIN typed
    score_begin — BEGIN scored against ENDED
    type_edits — EDITS typed
    score_e — E scored alone
    score_d — D scored alone
    score_edits — rest of EDITS scored
    type_melee — MELEE typed
    score_melee — MELEE scored
    type_ended — ENDED typed
    score_ended — ENDED scored
    """

    def setup_scene(self):
        self.board = get_board()
        self.add(self.board)

    def _type(self, row, run_time):
        self.board.type_word(self, row, WORDS[row], run_time,
                             per_letter=key_cues(self))

    # a : BEGIN typed into row 0
    @subscene
    def type_begin(self):
        self._type(0, 0.65)

    # b : BEGIN scored against ENDED
    @subscene
    def score_begin(self):
        self.board.reveal(self, 0, CODES[0], 1.6)

    # c : EDITS typed into row 1
    @subscene
    def type_edits(self):
        self._type(1, 0.65)

    # d : E alone — green, right letter in the right place
    @subscene
    def score_e(self):
        self.board.reveal(self, 1, CODES[1], 0.6, cols=[0])

    # e : D alone — yellow, in the word but elsewhere
    @subscene
    def score_d(self):
        self.board.reveal(self, 1, CODES[1], 0.6, cols=[1])

    # f : the rest of EDITS — gray
    @subscene
    def score_edits(self):
        self.board.reveal(self, 1, CODES[1], 1.1, cols=[2, 3, 4])

    # g : MELEE typed into row 2
    @subscene
    def type_melee(self):
        self._type(2, 0.65)

    # h : MELEE scored — repeated E: one yellow, one green, one gray
    @subscene
    def score_melee(self):
        self.board.reveal(self, 2, CODES[2], 1.6)

    # i : ENDED typed into row 3
    @subscene
    def type_ended(self):
        self._type(3, 0.65)

    # j : ENDED scored — all green, then the winning row jumps
    @subscene
    def score_ended(self):
        self.board.reveal(self, 3, CODES[3], 1.6)
        self.board.bounce(self, 3, 1.0)
