"""SCENE 10 — SALET's guess distribution, two of its games, and word lengths.

Opens on Wordle's black (WordleDarkScene, WORDLE_BG), the colour scene 09 ends on;
d turns it back to navy. Follows scene 09 directly, so it opens EMPTY and brings the
chart in. Talking head THG follows, so it ends with the vowel board up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a distribution — the Wordle-stats "guess distribution" chart for SALET's optimal
                   strategy grows in: rows 1-6, one bar each, count inside  (VO 1)
  b game_third   — bar 3 turns green; a mini board of SALET, NORTH, THIRD,
                   already scored, fades in above bar 3                      (VO 1)
  c game_wheel   — bar 3 back to grey, bar 4 green; a mini board of SALET,
                   BEVOR, CHIMP, WHEEL fades in below bar 3                  (VO 1)
  d wheel_center — ONE play: bar 4 greys as the chart and the THIRD board fade,
                   the background turns navy, and the WHEEL board grows to the
                   middle with its WHEEL row fading, every tile going black,
                   every letter fading but the A (SALET), E V O (BEVOR), I
                   (CHIMP) and T, and T becoming Y, V becoming U (the user's) (VO 1)
  e triple_vowels — the six vowels move, one play each, through where the three
                   best all-six-vowel triples in the singletons ranking put
                   them: CURSE PAINT GODLY, CURSE POINT BADLY, BIONT CARSE
                   DUPLY                                                     (VO 2)
  f adieu        — A I E U into ADIEU's positions in the first word as its D
                   lands, O to the middle of the second, Y to the end of the
                   third                                                     (VO 3)
  g audio        — A U D I O into AUDIO's positions, E to the middle of the
                   second word (the script says U; the user's correction)    (VO 3)
  h crypt        — Y into the middle of the third word as C R P T land
                   around it, spelling CRYPT                                 (VO 3)
  Letters move in ONE play per arrangement; every tile has the same border.

REUSE MAP — every element and the one source it comes from:
  chart          bpkfigures.bar_graph.get_bar_chart(orientation="horizontal",
                 min_length=…, value_inside=True) — the horizontal mode was added
                 for this scene; entrance bar_graph.grow_bars(edge=LEFT)
  bar colours    config.py TILE_ABSENT (Wordle's grey, as the real stats graph);
                 TILE_CORRECT for a highlighted row, as Wordle marks today's game
  text           crisp_text, white; title bold
  boards         assets/board.py get_scored_row, one per guess, stacked at the
                 board's own GAP and scaled down
  background     assets/background.py bg_to (promoted from scene 01's _bg_to)

NUMBERS — all SOURCED, from assets/word_lengths_data.py -> word_lengths_cache.json:
  counts per row   SALET's committed optimal tree (constrained to 6 guesses),
                   asserted there to sum to 2315 answers and 7920 guesses
  THIRD / WHEEL    those answers' lines in the same tree, codes re-checked against
                   math/wordle.py pattern()
  10e's triples   the first three rows of the singletons triple ranking
                   (math/data/shared/singletons/triple_singletons.csv, ranks 365,
                   380, 478 of the top 100000 of a greedy screen) using all six
                   vowels

ON-SCREEN TEXT beyond column 2 (the user's call): the "GUESS DISTRIBUTION" title,
in the real Wordle stats screen's capitals.

LAYOUT (the user's): the chart follows Wordle's stats screen — title flush left with
the row numbers, row numbers and counts one size, bars close together. Both boards
start a little right of bar 4's end: THIRD's above bar 3, WHEEL's below it. Boards
have only as many rows as the game used. A bar is green only during its own game's
beat (the user's): 3 in b, 4 in c.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.bar_graph import get_bar_chart, grow_bars
from assets.board import get_scored_row, GAP, TilePop
from assets.background import bg_to
from assets import word_lengths_data

DATA = word_lengths_data.load()
DIST = [(n, DATA["distribution"][n]) for n in sorted(DATA["distribution"], key=int)]
GAMES = DATA["games"]

# ── the chart ─────────────────────────────────────────────────────────────────
# Wordle's stats screen: 20px bars 4px apart, row numbers and counts one size, the
# title a little larger and flush left with the row numbers.
CHART_CENTER = np.array([-0.7, 0.075, 0])
CHART_WIDTH = 9.0            # a full-length bar (1231)
ROW_PITCH = 0.55
CHART_HEIGHT = 6 * ROW_PITCH
BAR_RATIO = 0.83
MIN_BAR = 0.55               # the stub a 0 row keeps, wide enough for its "0"
NUM_SIZE = FONT_SIZE_SM      # row numbers AND counts
TITLE_SIZE = 28

# ── the mini boards ───────────────────────────────────────────────────────────
BOARD_SCALE = 0.7
BOARD_GAP_X = 0.8            # boards start this far right of bar 4's end
BOARD_GAP_Y = 0.4            # THIRD this far above bar 3, WHEEL this far below

# ── d: WHEEL's board, down to its vowels ──────────────────────────────────────
# (row, position) of each letter that stays, in SALET / BEVOR / CHIMP: the A; the
# E, V, O; the I — and the T. T and V then become Y and U (the user's call), so
# the three rows hold all six vowels, spread across the three guesses.
KEEP = {0: {1, 4}, 1: {1, 2, 3}, 2: {2}}
MORPH = {(0, 4): "y", (1, 2): "u"}
_ROWS = [g["word"] for g in DATA["games"]["wheel"]["guesses"][:3]]
assert _ROWS == ["salet", "bevor", "chimp"], _ROWS
assert [_ROWS[r][i] for (r, i) in MORPH] == ["t", "v"]

# ── e-h: where the six vowels go, (row, position) per vowel ───────────────────
VOWELS = "aeiouy"                # Y a vowel, the video's convention


def _vowels_in(word, row):
    return {c: (row, i) for i, c in enumerate(word) if c in VOWELS}


# e: the best all-six-vowel triples in the singletons ranking (sourced), in rank
#    order — the vowels rearrange through each in turn
TRIPLES = [t["words"] for t in DATA["vowel_triples"]]
LAYOUT_TRIPLES = []
for _t in TRIPLES:
    _l = {}
    for _r, _w in enumerate(_t):
        _l.update(_vowels_in(_w, _r))
    LAYOUT_TRIPLES.append(_l)
# f: ADIEU in the first word (its D lands as the vowels move), O mid second word,
#    Y ending the third (Script.md 10f)
LAYOUT_ADIEU = {**_vowels_in("adieu", 0), "d": (0, "adieu".index("d")),
                "o": (1, 2), "y": (2, 4)}
# g: AUDIO, its D moving over with it; E mid second word (the user's correction of
#    the script's "U")
LAYOUT_AUDIO = {**_vowels_in("audio", 0), "d": (0, "audio".index("d")),
                "e": (1, 2), "y": (2, 4)}
# h: Y mid third word, the rest spelling CRYPT
CRYPT = "crypt"
LAYOUT_CRYPT = {**LAYOUT_AUDIO, "y": (2, CRYPT.index("y"))}
for _l in LAYOUT_TRIPLES + [LAYOUT_ADIEU, LAYOUT_AUDIO, LAYOUT_CRYPT]:
    assert set(VOWELS) <= set(_l) <= set(VOWELS + "d"), _l
    assert len(set(_l.values())) == len(_l), _l


class Scene10(WordleDarkScene):
    """BEAT MAP
    distribution — SALET's guess-distribution chart grows in
    game_third — bar 3 green; SALET's scored game for THIRD fades in above it
    game_wheel — bar 3 grey, bar 4 green; SALET's game for WHEEL fades in below bar 3
    wheel_center — chart and THIRD board leave, bg to navy, WHEEL board to the
                   middle minus its WHEEL row; tiles black, vowels kept; T->Y, V->U
    triple_vowels — vowels through the top three all-six-vowel triples' positions
    adieu — vowels to ADIEU as D lands / O mid row 2 / Y end of row 3
    audio — vowels and D to AUDIO / E mid row 2
    crypt — Y mid row 3, C R P T land: CRYPT
    """

    def setup_scene(self):
        pass

    # ── builders ─────────────────────────────────────────────────────────────
    def _setup_chart(self):
        white = lambda s, fs: crisp_text(str(s), font_size=fs, color=WHITE,
                                         weight=BOLD)
        title = crisp_text("GUESS DISTRIBUTION", font_size=TITLE_SIZE, color=WHITE,
                           weight=BOLD)
        self.chart = get_bar_chart(
            DIST, orientation="horizontal", center=CHART_CENTER,
            width=CHART_WIDTH, height=CHART_HEIGHT, bar_ratio=BAR_RATIO,
            bar_color=TILE_ABSENT, ink_color=WHITE, min_length=MIN_BAR,
            label_factory=lambda s: white(s, NUM_SIZE), label_buff=0.2,
            value_labels=True, value_inside=True, value_buff=0.15,
            value_factory=lambda v: white(v, NUM_SIZE),
            title_mobject=title, title_buff=0.35)
        title.align_to(self.chart.labels, LEFT)

    def _setup_board(self, answer, below):
        """SALET's finished game for `answer`, scored, as a mini board a little
        right of bar 4's end — under bar 3 if `below` (WHEEL), else over it."""
        rows = [get_scored_row(g["word"], g["code"])
                for g in GAMES[answer]["guesses"]]
        board = VGroup(*rows).arrange(DOWN, buff=GAP).scale(BOARD_SCALE)
        bar3, bar4 = self.chart.bar_of["3"], self.chart.bar_of["4"]
        board.align_to(bar4.get_right() + RIGHT * BOARD_GAP_X, LEFT)
        if below:
            board.align_to(bar3.get_bottom() + DOWN * BOARD_GAP_Y, UP)
        else:
            board.align_to(bar3.get_top() + UP * BOARD_GAP_Y, DOWN)
        return board

    def _bar_color(self, n, color):
        return self.chart.bar_of[n].animate.set_fill(color).set_stroke(color)

    # a : SALET's guess distribution grows in
    @subscene
    def distribution(self):
        self._setup_chart()
        c = self.chart
        self.play(FadeIn(c.title), FadeIn(c.labels), run_time=0.8)
        grow_bars(self, c.bars, 1.5, lag=0.08, edge=LEFT)
        self.play(FadeIn(c.values), run_time=0.6)

    # b : bar 3 turns green; SALET's game for THIRD fades in above it
    @subscene
    def game_third(self):
        self.board_third = self._setup_board("third", below=False)
        self.play(self._bar_color("3", TILE_CORRECT), FadeIn(self.board_third),
                  run_time=0.8)

    # c : bar 3 back to grey, bar 4 green; SALET's game for WHEEL fades in below bar 3
    @subscene
    def game_wheel(self):
        self.board_wheel = self._setup_board("wheel", below=True)
        self.play(self._bar_color("3", TILE_ABSENT), self._bar_color("4", TILE_CORRECT),
                  FadeIn(self.board_wheel), run_time=0.8)

    # d : ONE play — bar 4 greys as the chart and THIRD's board fade, the background
    #     turns navy, and WHEEL's board grows to the middle with its WHEEL row
    #     fading, its tiles going black, every letter but the vowels (and T, V)
    #     fading, and T becoming Y and V becoming U, all at the same time
    def _setup_wheel_center(self):
        c = self.chart
        bar4 = c.bar_of["4"]
        # bar 4 is animated on its own (grey AND out), so the rest of the chart
        # fades without it — one mobject, one animation
        self.chart_rest = [b for b in c.bars if b is not bar4] + \
                          [c.labels, c.values, c.title]
        self.upper = VGroup(*self.board_wheel[:-1])      # SALET, BEVOR, CHIMP
        self.wheel_row = self.board_wheel[-1]
        # full tile size, with the three rows that stay centred in the frame
        self.k = 1 / BOARD_SCALE
        self.pivot = self.board_wheel.get_center()
        grown = self.upper.copy().scale(self.k, about_point=self.pivot)
        self.to_mid = ORIGIN - grown.get_center()
        # Y and U, built on the tiles' END pose so they morph in place as they move
        grown.shift(self.to_mid)
        self.morph_to = {(r, i): self.upper[r]._letter(ch, grown[r].tiles[0][i])
                         for (r, i), ch in MORPH.items()}

    def _move(self, m):
        """`m`'s animation to its place in the grown, centred board."""
        return m.animate.scale(self.k, about_point=self.pivot).shift(self.to_mid)

    def _board_anims(self):
        """Every tile and letter of the three rows that stay, ONE animation each:
        moved, tiles to Wordle's empty black, letters not in KEEP faded, T and V
        morphed. EVERY tile gets the same (typed) border, the one TilePop gives a
        tile a letter lands in, so the board stays uniform (the user's)."""
        anims = []
        for r, row in enumerate(self.upper):
            for i in range(5):
                keep = i in KEEP[r]
                anims.append(self._move(row.tiles[0][i]).set_fill(TILE_EMPTY_FILL)
                             .set_stroke(TILE_FILLED_BORDER))
                letter = row.letters[0][i]
                if (r, i) in self.morph_to:
                    anims.append(Transform(letter, self.morph_to[(r, i)]))
                elif keep:
                    anims.append(self._move(letter))
                else:
                    anims.append(self._move(letter).set_opacity(0))
        return anims

    @subscene
    def wheel_center(self):
        self._setup_wheel_center()
        bar4 = self.chart.bar_of["4"]
        self.play(bar4.animate.set_fill(TILE_ABSENT, opacity=0)
                      .set_stroke(TILE_ABSENT, opacity=0),
                  FadeOut(*self.chart_rest), FadeOut(self.board_third),
                  bg_to(self, BOARD_NAVY),
                  self._move(self.wheel_row).set_opacity(0),
                  *self._board_anims(),
                  run_time=1.2)
        self.remove(self.chart, bar4, self.board_third, self.wheel_row)
        self.board_wheel.remove(self.wheel_row)
        self.chart = self.board_third = self.wheel_row = None
        # the six vowel letters, by character, for e-h to move around
        self.placed = {MORPH.get((r, i), _ROWS[r][i]): self.upper[r].letters[0][i]
                       for r, keep in KEEP.items() for i in keep}
        assert sorted(self.placed) == sorted(VOWELS)
        # above EVERY row's tiles: a letter moving to a lower row would otherwise
        # pass under that row's tiles, which are drawn after its own
        for letter in self.placed.values():
            letter.set_z_index(1)

    # ── e-h: the six vowels moved between the three rows ──────────────────────
    def _tile(self, r, i):
        return self.upper[r].tiles[0][i]

    def _land(self, r, i, ch):
        """A new letter `ch` typed into tile (r, i): returns its TilePop, the same
        pop board.type_word gives a typed letter."""
        row, tile = self.upper[r], self._tile(r, i)
        letter = row._letter(ch, tile)
        letter.set_opacity(0).set_z_index(1)       # TilePop reveals it on its turn
        row.letters[0][i] = letter
        row.add(letter)
        self.add(letter)
        return letter, TilePop(tile, letter)

    def _arrange(self, layout, run_time, extra=()):
        """ONE play: every placed letter to its (row, position) in `layout`, with
        `extra` (letters landing) alongside."""
        anims = [self.placed[ch].animate.move_to(self._tile(r, i).get_center())
                 for ch, (r, i) in layout.items() if ch in self.placed]
        self.play(*anims, *extra, run_time=run_time)

    # e : the vowels through the positions of the best three all-six-vowel triples
    @subscene
    def triple_vowels(self):
        self._arrange(LAYOUT_TRIPLES[0], 1.2)
        self._arrange(LAYOUT_TRIPLES[1], 1.2)
        self._arrange(LAYOUT_TRIPLES[2], 1.2)

    # f : ADIEU in the first word as its D lands, O mid second word, Y ending the
    #     third
    @subscene
    def adieu(self):
        d, pop = self._land(*LAYOUT_ADIEU["d"], "d")
        self._arrange(LAYOUT_ADIEU, 1.2, extra=[pop])
        self.placed["d"] = d

    # g : AUDIO in the first word, D moving with it, E mid second word (Y stays)
    @subscene
    def audio(self):
        self._arrange(LAYOUT_AUDIO, 1.2)

    # h : Y into the middle of the third word as C R P T land around it: CRYPT
    @subscene
    def crypt(self):
        pops = [self._land(2, i, ch)[1] for i, ch in enumerate(CRYPT) if ch != "y"]
        self._arrange(LAYOUT_CRYPT, 1.0, extra=[LaggedStart(*pops, lag_ratio=0.25)])
