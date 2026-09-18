"""SCRATCH — a played game of Wordle — TRACE, LOINS, DUMPY, SNOWY against SNOWY. Dark mode.

The empty board is up from frame 0 (setup_scene), so the scene opens on the grid and
the first beat types into a board that is already there.

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

TYPING_SOUND = "keys"
# ONE KEYSTROKE PER LETTER OF THE ALPHABET, the way a real keyboard behaves: the
# same letter always makes the same sound, so a letter recurring across guesses
# sounds like the same physical key being hit again. (In this game S, N, O and Y
# all come back in SNOWY, so four of its five keys are ones already heard.)
#
# The source yields 25 separable presses against 26 letters, so exactly one pair
# has to share — Q and Z, the two rarest, chosen so the doubling is the least
# likely to be audible. Q and Z never both appear in a word here anyway.
KEY_SOUNDS = [f"key{i:02d}" for i in range(1, 26)]
_Q = ord("q") - ord("a")

# Letters whose assigned key did not sit right, SWAPPED with another letter's. A
# swap rather than a reassignment, so every letter still owns exactly one sound —
# the rejected one just moves to a letter this game never types. Pick the partner
# from a letter that does not appear, or you only move the problem.
#   s <-> j : S's original key19 was disliked; J is unused here, so it absorbs it.
KEY_SWAPS = [("s", "j")]


def _build_key_map():
    m = {}
    for c in "abcdefghijklmnopqrstuvwxyz":
        m[c] = KEY_SOUNDS[_Q if c == "z" else ord(c) - ord("a")]
    for a, b in KEY_SWAPS:
        m[a], m[b] = m[b], m[a]
    return m


KEY_MAP = _build_key_map()


def key_for(ch):
    """The keystroke sound for a letter. Q and Z share; every other letter is its own."""
    return KEY_MAP[ch.lower()]
# Which keyboard the "sequence" bed is. Same slice length and level throughout, so
# swapping this string is an A/B of the KEYBOARD alone.
#   "typing-classic" | "typing-corsair" | "typing-logitech" | "typing-razer"
# typing-classic is the odd one: its source has DISCRETE keystrokes rather than
# continuous texture, so its cut was chosen to contain exactly five hits, matching
# the five letters. Change the typing run_time and that match is what breaks.
TYPING_BED = "typing-classic"

# UNDER "sequence" THE BED'S LENGTH IS TIED TO WHEN THE LAST LETTER LANDS — which is
# NOT the typing run_time. The pops deliberately overlap, so a 5-letter word is fully
# on screen at about 0.44 of the run_time (measured: 0.29s of a 0.65s type). Cut the
# bed to roughly that plus a short tail, or it keeps typing after the word looks done:
#   python -m bpkfigures.sfx_import "<source>" --name typing-<keyboard> \
#       --start 10.0 --duration 0.33 --fade 8 --force
# "keys" has no such coupling — a cue fires per letter, whatever the pace.

GAME = game_data.load()
WORDS = [g["word"] for g in GAME["guesses"]]
CODES = [g["code"] for g in GAME["guesses"]]


class Scene97(WordleDarkScene):
    def setup_scene(self):
        # The empty board is ON SCREEN FROM FRAME 0, which is what setup_scene is
        # for. It used to be added inside subscene a, so the framework's leading
        # hold showed an empty frame and then the board POPPED in at the very
        # instant the first letter was typed — both the wrong first impression and
        # the silent-add the continuity rule warns about. Built here it is simply
        # there, the way the real game's grid is when you open it.
        self.board = get_board()
        self.add(self.board)

    # ── the two typing-sound approaches, so a beat just says _type(row) ───────
    def _type(self, row, run_time):
        word = WORDS[row]
        per_letter = None
        if TYPING_SOUND == "keys":
            def per_letter(i, ch, at):
                # `at` places the cue at the letter's own moment — the word is ONE
                # play now, so the call order alone would stack them all at its start.
                self.sfx(key_for(ch), at=at)
        elif TYPING_SOUND == "sequence":
            self.sfx(TYPING_BED)
        self.board.type_word(self, row, word, run_time, per_letter=per_letter)

    # a : TRACE typed into row 0 (the board is already up, from setup_scene)
    @subscene
    def type_trace(self):
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
