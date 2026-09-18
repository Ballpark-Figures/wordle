"""SCRATCH — a played game of Wordle — TRACE, LOINS, DUMPY, SNOWY against SNOWY. Dark mode.

BEAT MAP — one subscene per half-move, so the edit can hold a stretched still on a
completed row before the reveal (the user's call: type and score separate).

  a type_trace   — TRACE typed into row 0
  b score_trace  — row 0 flips: all absent
  c type_loins   — LOINS typed into row 1
  d score_loins  — row 1 flips: O, N, S present
  e type_dumpy   — DUMPY typed into row 2
  f score_dumpy  — row 2 flips: Y correct
  g type_snowy   — SNOWY typed into row 3
  h score_snowy  — row 3 flips all correct, then the winning bounce

REUSE MAP — every element and the one source it comes from:
  board + tiles + letters  assets/board.py `get_board` (new; the reuse audit found
                           nothing tile-shaped in bpkfigures or the other videos —
                           hangman's letter_grid is the 26-letter alphabet view)
  typing pop               board.type_word         (not a hand-rolled scale)
  scored flip              board.reveal / TileFlip (not a hand-rolled squash)
  winning bounce           board.bounce
  colours                  config.py WORDLE_BG / TILE_* — the authentic NYT dark
                           palette, named there, never a hex in this file
  tile letters             crisp_text, inside the asset
  feedback codes           assets/game_data.py -> game_cache.json, computed by
                           math/wordle.py `pattern` — never worked out by hand
  keystroke / typing sfx   music-library/sfx via self.sfx (see TYPING_SOUND)

TYPING_SOUND picks between the two approaches, to be compared:
  "keys"      one keystroke per letter, rotating through key1..key5 so consecutive
              letters are not the identical sample
  "sequence"  one continuous typing clip under the whole word
  None        silent
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board
from assets import game_data

TYPING_SOUND = "sequence"
KEY_SOUNDS = ["key1", "key2", "key3", "key4", "key5"]

# UNDER "sequence" THE BED'S LENGTH IS TIED TO THE TYPING run_time. The clip is one
# fixed-length sound played once per word, so if the 0.65 below changes, re-slice it
# to match or it runs on past the last letter:
#   python -m bpkfigures.sfx_import "<source>" --name typing \
#       --start 10.0 --duration <the new run_time> --fade 8 --force
# "keys" has no such coupling — a cue fires per letter, whatever the pace.

GAME = game_data.load()
WORDS = [g["word"] for g in GAME["guesses"]]
CODES = [g["code"] for g in GAME["guesses"]]


class Scene97(WordleDarkScene):
    def setup_scene(self):
        pass

    # ── the two typing-sound approaches, so a beat just says _type(row) ───────
    def _type(self, row, run_time):
        word = WORDS[row]
        per_letter = None
        if TYPING_SOUND == "keys":
            def per_letter(i, ch, at):
                # `at` places the cue at the letter's own moment — the word is ONE
                # play now, so the call order alone would stack them all at its start.
                self.sfx(KEY_SOUNDS[i % len(KEY_SOUNDS)], at=at)
        elif TYPING_SOUND == "sequence":
            self.sfx("typing")
        self.board.type_word(self, row, word, run_time, per_letter=per_letter)

    def _setup_board(self):
        self.board = get_board()
        self.add(self.board)

    # a : TRACE typed into row 0
    @subscene
    def type_trace(self):
        self._setup_board()
        self._type(0, 0.65)

    # b : row 0 flips — nothing in the word
    @subscene
    def score_trace(self):
        self.board.reveal(self, 0, CODES[0], 1.6)

    # c : LOINS typed into row 1
    @subscene
    def type_loins(self):
        self._type(1, 0.65)

    # d : row 1 flips — O, N, S present
    @subscene
    def score_loins(self):
        self.board.reveal(self, 1, CODES[1], 1.6)

    # e : DUMPY typed into row 2
    @subscene
    def type_dumpy(self):
        self._type(2, 0.65)

    # f : row 2 flips — Y correct
    @subscene
    def score_dumpy(self):
        self.board.reveal(self, 2, CODES[2], 1.6)

    # g : SNOWY typed into row 3
    @subscene
    def type_snowy(self):
        self._type(3, 0.65)

    # h : row 3 flips all correct, then the winning row jumps
    @subscene
    def score_snowy(self):
        self.board.reveal(self, 3, CODES[3], 1.6)
        self.board.bounce(self, 3, 1.0)
