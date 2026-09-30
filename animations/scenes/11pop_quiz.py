"""SCENE 11 — the pop quiz: ICILY from its vowels, BEFIT from its consonants.

Follows talking head THG, so it opens EMPTY; talking head THH follows, so it may end
with content up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a blank_words   — two blank 5-tile words pop in, tile by tile: one bottom left,
                    one top right                                          (VO 1)
  b green_blanks  — tiles 1, 3, 5 of each word flip to blank green         (VO 1)
  c ring          — a red ring with 15 in the middle, top-left corner      (VO 2)
  d countdown     — the green tiles flip to I_I_Y and B_F_T, then the ring
                    counts 15 to 0 over 15 s while its arc runs down to
                    nothing; the timer sfx rings as it hits 0              (VO 3)
  e reveal_left   — the left word's blanks flip to C, L                    (VO 4)
  f reveal_right  — the right word's blanks flip to E, I                   (VO 4)
  g vowel_colors  — every tile flips to black, letters vowel red /
                    consonant blue                                          (VO 4)
  h-j (Hebrew / Arabic) NOT BUILT YET — waiting on the word choice and what
                    counts as a vowel there.

REUSE MAP — every element and the one source it comes from:
  words          assets/board.py WordleBoard(rows=1), scaled — the video's tiles
  blank pop-in   board.TilePop with letter=None, appear=True (the None case added
                 for this scene; every other caller unchanged)
  every flip     board.TileFlip (swap_to shows a letter on the new face), as 10's
  green          config.py TILE_CORRECT
  black tiles    config.py TILE_EMPTY_FILL + TILE_FILLED_BORDER, as scene 10's
                 vowel board
  letter colours bpkfigures.tier_list.tile_color — vowel red / consonant blue,
                 Y a vowel (the video's rule; scene 10's table)
  ring           a manim Arc in style.py ACCENT_RED; numbers crisp_text
  timer sfx      music-library `timer`, cut so its ring starts 15.044 s in
                 (catalog.md); cued at=-0.044 before the 15 s play

NUMBERS: the VO's "only one possible Wordle answer matches" — checked against the
2315 answers (math/data/shared/words/mystery.txt): i.i.y matches only ICILY, b.f.t
only BEFIT. Nothing numeric is on screen but the countdown.

No other on-screen text: column 2 asks for the words, the ring and its number.
"""
from pathlib import Path
import math
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import WordleBoard, TileFlip, TilePop
from bpkfigures.tier_list import tile_color

LEFT_WORD, RIGHT_WORD = "icily", "befit"
SHOWN = [0, 2, 4]                     # the three letters given (1st, 3rd, 5th)
HIDDEN = [1, 3]

WORD_SCALE = 1.2
LEFT_CENTER = np.array([-3.6, -1.9, 0])
RIGHT_CENTER = np.array([3.6, 1.9, 0])

SECONDS = 15
RING_CENTER = np.array([-6.5, 3.3, 0])
RING_RADIUS = 0.75
RING_STROKE = 12
NUM_SIZE = 44
TIMER_RING_AT = 15.044                # where the timer sfx's bell starts (catalog.md)


def _arc(frac):
    """The ring with `frac` of it left, running clockwise from 12 o'clock."""
    arc = Arc(radius=RING_RADIUS, start_angle=PI / 2, angle=-TAU * max(frac, 1e-4),
              stroke_color=ACCENT_RED, stroke_width=RING_STROKE)
    arc.move_arc_center_to(RING_CENTER)
    if frac <= 0:
        arc.set_stroke(opacity=0)
    return arc


class Countdown(Animation):
    """The ring runs down to nothing while its number counts SECONDS to 0.

    A custom Animation rather than a ValueTracker + updater, so nothing holds a
    lambda and the snapshot cache still pickles the scene (board.TileFlip's reason).
    The number shows the seconds LEFT, rounded up: 15 at the start, 0 only at the end.
    """

    def __init__(self, ring, number, numbers, **kwargs):
        self.ring, self.number, self.numbers = ring, number, numbers
        super().__init__(VGroup(ring, number), **kwargs)

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        self.ring.become(_arc(1 - a))
        self.number.become(self.numbers[math.ceil(round(SECONDS * (1 - a), 6))])


class Scene11(WordleBoardScene):
    """BEAT MAP
    blank_words — two blank words pop in
    green_blanks — tiles 1, 3, 5 flip to blank green
    ring — the 15 s ring appears
    countdown — I_I_Y and B_F_T revealed, then the 15 s countdown
    reveal_left — C, L
    reveal_right — E, I
    vowel_colors — black tiles, vowels red, consonants blue
    """

    def setup_scene(self):
        pass

    def _word(self, center):
        w = WordleBoard(rows=1, cols=5)
        w.scale(WORD_SCALE).move_to(center)
        return w

    def _letter(self, w, i, ch, color=None):
        """A letter for tile i of word w, hidden until its flip shows it."""
        tile = self.words[w].tiles[0][i]
        letter = self.words[w]._letter(ch, tile) if color is None else \
            self.words[w]._letter(ch, tile, color=color)
        letter.set_opacity(0)
        self.add(letter)
        return letter

    def _flip(self, w, i, fill, stroke=None, new=None):
        """Tile i of word w flips to `fill`, showing `new` (a letter, or blank)."""
        old = self.faces[w][i]
        self.faces[w][i] = new
        return TileFlip(self.words[w].tiles[0][i], old, fill, stroke=stroke,
                        swap_to=new)

    def _reveal(self, w, cols):
        """Tiles `cols` of word w flip green, showing their letters."""
        word = self.letters_of[w]
        return LaggedStart(*[self._flip(w, i, TILE_CORRECT,
                                        new=self._letter(w, i, word[i]))
                             for i in cols], lag_ratio=0.45)

    # a : two blank words pop in, left one first
    def _setup_blank_words(self):
        self.words = [self._word(LEFT_CENTER), self._word(RIGHT_CENTER)]
        self.letters_of = [LEFT_WORD, RIGHT_WORD]
        self.faces = [[None] * 5, [None] * 5]      # the letter each tile shows
        for w in self.words:
            for t in w.tiles[0]:
                t.set_fill(opacity=0).set_stroke(opacity=0)
            self.add(w)

    @subscene
    def blank_words(self):
        self._setup_blank_words()
        for w in self.words:
            self.play(LaggedStart(*[TilePop(t, None, appear=True) for t in w.tiles[0]],
                                  lag_ratio=0.2), run_time=0.65)

    # b : tiles 1, 3, 5 of both words flip to blank green
    @subscene
    def green_blanks(self):
        self.play(*[LaggedStart(*[self._flip(w, i, TILE_CORRECT) for i in SHOWN],
                                lag_ratio=0.45) for w in range(2)], run_time=1.2)

    # c : the red ring with 15 in the middle, top-left corner
    def _setup_ring(self):
        self.numbers = [crisp_text(str(n), font_size=NUM_SIZE, weight=BOLD)
                        .move_to(RING_CENTER) for n in range(SECONDS + 1)]
        self.ring = _arc(1.0)
        self.number = self.numbers[SECONDS].copy()

    @subscene
    def ring(self):
        self._setup_ring()
        self.play(Create(self.ring), FadeIn(self.number), run_time=0.8)

    # d : I_I_Y and B_F_T flip in, then 15 seconds run down
    @subscene
    def countdown(self):
        self.play(*[self._reveal(w, SHOWN) for w in range(2)], run_time=1.2)
        # the bell lands on 0: the countdown is linear, so its end is SECONDS in
        self.sfx("timer", at=SECONDS - TIMER_RING_AT)
        self.play(Countdown(self.ring, self.number, self.numbers),
                  run_time=SECONDS, rate_func=linear)
        # NOT a stray trailing hold: the bell rings ~1.8 s past 0, and a cue in the
        # framework's trailing hold is dropped from the stitch and silent under the
        # still in the edit — so the ring needs this much of the clip after 0.
        self.wait(2.0)

    # e : the left word's blanks flip to C, L
    @subscene
    def reveal_left(self):
        self.play(self._reveal(0, HIDDEN), run_time=0.8)

    # f : the right word's blanks flip to E, I
    @subscene
    def reveal_right(self):
        self.play(self._reveal(1, HIDDEN), run_time=0.8)

    # g : every tile to black, vowels red, consonants blue
    @subscene
    def vowel_colors(self):
        flips = []
        for w in range(2):
            word = self.letters_of[w]
            flips.append(LaggedStart(*[
                self._flip(w, i, TILE_EMPTY_FILL, stroke=TILE_FILLED_BORDER,
                           new=self._letter(w, i, word[i], tile_color(word[i])))
                for i in range(5)], lag_ratio=0.45))
        self.play(*flips, run_time=1.6)
