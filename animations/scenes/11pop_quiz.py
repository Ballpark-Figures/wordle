"""SCENE 11 — the pop quiz: ICILY from its vowels, BEFIT from its consonants.

Follows talking head THG, so it opens EMPTY; talking head THH follows, so it may end
with content up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a blank_words   — two blank 5-tile words pop in, tile by tile: one bottom left,
                    one top right                                          (VO 1)
  b green_blanks  — tiles 1, 3, 5 of each word flip to blank green         (VO 1)
  c ring          — a red ring with 15 in the middle, top-left corner      (VO 2)
  d countdown     — the green tiles flip to I_I_Y and B_F_T, all at once, then
                    the ring counts 15 to 0 over 15 s while its arc runs down
                    to nothing; the timer sfx rings as it hits 0, and the 0
                    pops and shrinks away during the bell                  (VO 3)
  e reveal_right  — the right word's blanks flip to E, I. BEFIT FIRST (the
                    user's call): the script has the left word at 11e       (VO 4)
  f reveal_left   — the left word's blanks flip to C, L                    (VO 4)
  g vowel_colors  — every tile flips to black in ONE flip, letters vowel
                    red / consonant blue                                    (VO 4)
  h scripts       — ONE flip turns the left word into Hebrew עִבְרִית and the
                    right into Arabic الْعَرَبِيَّة, vowel marks red, letters
                    blue                                                    (VO 5)
  i script_names  — (Hebrew) and (Arabic) fade up under them               (VO 5)
  j poof          — the vowel marks fade out, with the mids whoosh sfx (the
                    user's swap for the script's poof)                     (VO 5)

THE VOWELS in h-j are the OPTIONAL marks, the ones everyday text leaves out (the
user's definition): Hebrew's niqqud below the letters (hiriq, shva, hiriq — the yud
stays a consonant), Arabic's harakat (sukun, fatha, fatha, kasra, and the shadda
with its fatha). THE SHADDA IS NOT A VOWEL — it doubles a consonant — but every
Arabic font here draws shadda+fatha as ONE glyph, so it goes red and vanishes with
its fatha. Everything else, letter dots included, is a consonant and stays blue.
The marks are picked out by GLYPH INDEX (dumped once from the rendered text), and
`_script_word` asserts the glyph count so a font or spelling change fails loudly
rather than colouring the wrong shape.

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
  word -> script assets/flip.py Flip / flip(), the whole word at once
  script words   crisp_text in a system font with the script (Inter has neither):
                 Arial Hebrew, Geeza Pro; coloured VOWEL_TILE_COLOR /
                 CONS_TILE_COLOR, the same pair tile_color uses
  whoosh sfx     music-library `whoosh-mids`, at scene 01's WHOOSH_GAIN
                 (assets/stacks_view.py)

NUMBERS: the VO's "only one possible Wordle answer matches" — checked against the
2315 answers (math/data/shared/words/mystery.txt): i.i.y matches only ICILY, b.f.t
only BEFIT. Nothing numeric is on screen but the countdown.

No other on-screen text: column 2 asks for the words, the ring and its number, and
the (Hebrew) / (Arabic) labels.
"""
from pathlib import Path
import math
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import WordleBoard, TileFlip, TilePop
from assets.flip import Flip, flip
from assets.stacks_view import WHOOSH_GAIN
from bpkfigures.tier_list import tile_color, VOWEL_TILE_COLOR, CONS_TILE_COLOR

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

# h-j: (text, font, glyph count, which glyphs are vowel marks), glyphs indexed left
# to right as rendered — from a dump of the rendered text, see the docstring
HEBREW = ("עִבְרִית", "Arial Hebrew", 8, {2, 4, 6})
ARABIC = ("الْعَرَبِيَّة", "Geeza Pro", 12, {1, 3, 5, 7, 9})
SCRIPT_SIZE = 130

# j's sound: the second whoosh of Epidemic's 'Mids' (music-library catalog.md),
# at scene 01's whoosh level
J_WHOOSH_SFX = "whoosh-mids"
J_WHOOSH_PEAK = 0.20                     # s into the file where it is loudest (MEASURED)
LABEL_SIZE = FONT_SIZE_SM
LABEL_BUFF = 0.35


def _script_word(spec):
    """The word coloured vowel red / consonant blue; returns (word, its marks)."""
    text, font, n, marks = spec
    word = crisp_text(text, font=font, font_size=SCRIPT_SIZE)
    assert len(word.submobjects) == n, (text, font, len(word.submobjects))
    vowels = VGroup()
    for i, g in enumerate(word.submobjects):
        g.set_color(VOWEL_TILE_COLOR if i in marks else CONS_TILE_COLOR)
        if i in marks:
            vowels.add(g)
    return word, vowels


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
    reveal_right — E, I (BEFIT first)
    reveal_left — C, L
    vowel_colors — black tiles, vowels red, consonants blue
    scripts — the words flip into Hebrew and Arabic
    script_names — (Hebrew), (Arabic)
    poof — the vowel marks vanish
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

    def _reveal(self, w, cols, lag_ratio=0.45):
        """Tiles `cols` of word w flip green, showing their letters."""
        word = self.letters_of[w]
        return LaggedStart(*[self._flip(w, i, TILE_CORRECT,
                                        new=self._letter(w, i, word[i]))
                             for i in cols], lag_ratio=lag_ratio)

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

    # d : I_I_Y and B_F_T flip in (all six at once), 15 seconds run down, and the
    #     0 pops and shrinks to nothing while the bell rings
    @subscene
    def countdown(self):
        self.play(*[self._reveal(w, SHOWN, lag_ratio=0) for w in range(2)],
                  run_time=0.6)
        # the bell lands on 0: the countdown is linear, so its end is SECONDS in
        self.sfx("timer", at=SECONDS - TIMER_RING_AT)
        self.play(Countdown(self.ring, self.number, self.numbers),
                  run_time=SECONDS, rate_func=linear)
        # the 0 pops, then shrinks away — two plays, not a Succession of two
        # .animate targets (both would be built from the unpopped size)
        self.play(self.number.animate.scale(1.4), run_time=0.2)
        self.play(self.number.animate.scale(0.01), run_time=0.5)
        self.remove(self.ring, self.number)
        self.ring = self.number = self.numbers = None
        # NOT a stray trailing hold: the bell rings ~1.8 s past 0, and a cue in the
        # framework's trailing hold is dropped from the stitch and silent under the
        # still in the edit — so the ring needs this much of the clip after 0.
        self.wait(1.3)

    # e : the right word's blanks flip to E, I — BEFIT first (the user's call; the
    #     script has the left word here)
    @subscene
    def reveal_right(self):
        self.play(self._reveal(1, HIDDEN), run_time=0.8)

    # f : the left word's blanks flip to C, L
    @subscene
    def reveal_left(self):
        self.play(self._reveal(0, HIDDEN), run_time=0.8)

    # g : every tile to black, vowels red, consonants blue — all ten in one flip
    @subscene
    def vowel_colors(self):
        flips = [self._flip(w, i, TILE_EMPTY_FILL, stroke=TILE_FILLED_BORDER,
                            new=self._letter(w, i, self.letters_of[w][i],
                                             tile_color(self.letters_of[w][i])))
                 for w in range(2) for i in range(5)]
        self.play(*flips, run_time=0.6)

    # h : one flip turns both words into their scripts
    def _setup_scripts(self):
        self.scripts, self.marks = [], []
        for spec, center in ((HEBREW, LEFT_CENTER), (ARABIC, RIGHT_CENTER)):
            word, marks = _script_word(spec)
            word.move_to(center)
            self.scripts.append(word)
            self.marks.append(marks)

    @subscene
    def scripts(self):
        self._setup_scripts()
        olds = []
        for w in range(2):
            faces = [f for f in self.faces[w] if f is not None]
            self.remove(self.words[w], *faces)      # the flip carries them now
            olds.append(VGroup(*self.words[w].tiles[0], *faces))
        flip(self, [Flip(olds[w], self.scripts[w]) for w in range(2)], run_time=0.8)
        self.words = self.faces = None

    # i : (Hebrew) and (Arabic) fade up under the words
    def _setup_script_names(self):
        self.names = [crisp_text(t, font_size=LABEL_SIZE)
                      .next_to(self.scripts[w], DOWN, buff=LABEL_BUFF)
                      for w, t in enumerate(("(Hebrew)", "(Arabic)"))]

    @subscene
    def script_names(self):
        self._setup_script_names()
        self.play(*[FadeIn(n, shift=UP * 0.2) for n in self.names], run_time=0.8)

    # j : the vowel marks vanish, with a whoosh (the user's swap for the script's
    #     poof) — whoosh-mids, at scene 01's whoosh level, loudest mid-fade
    @subscene
    def poof(self):
        rt = 0.7
        self.sfx(J_WHOOSH_SFX, at=max(0.0, rt / 2 - J_WHOOSH_PEAK), gain=WHOOSH_GAIN)
        self.play(*[FadeOut(m) for m in self.marks], run_time=rt)
        for w in range(2):
            self.scripts[w].remove(*self.marks[w])
        self.marks = None
