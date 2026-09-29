"""SCENE 10 — SALET's guess distribution, two of its games, and word lengths.

Opens on Wordle's black (WordleDarkScene, WORDLE_BG), the colour scene 09 ends on;
d turns it back to navy. Follows scene 09 directly, so it opens EMPTY and brings the
chart in. Talking head THG follows, so it ends with the WHEEL board up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a distribution — the Wordle-stats "guess distribution" chart for SALET's optimal
                   strategy grows in: rows 1-6, one bar each, count inside  (VO 1)
  b game_third   — bar 3 turns green; a mini board of SALET, NORTH, THIRD,
                   already scored, fades in above bar 3                      (VO 1)
  c game_wheel   — bar 4 turns green; a mini board of SALET, BEVOR, CHIMP,
                   WHEEL fades in below bar 3                                (VO 1)
  d wheel_center — the chart and the THIRD board fade as the background turns
                   navy; the WHEEL board moves to the middle at full size    (VO 1)
  (VO 2 — the word-length discussion — has no subscene in the script yet.)

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

ON-SCREEN TEXT beyond column 2 (the user's call): the "GUESS DISTRIBUTION" title,
in the real Wordle stats screen's capitals.

LAYOUT (the user's): the chart follows Wordle's stats screen — title flush left with
the row numbers, row numbers and counts one size, bars close together. Both boards
start a little right of bar 4's end: THIRD's above bar 3, WHEEL's below it. Boards
have only as many rows as the game used. Bar 3 stays green through c (not asked to
turn back).
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.bar_graph import get_bar_chart, grow_bars
from assets.board import get_scored_row, GAP
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


class Scene10(WordleDarkScene):
    """BEAT MAP
    distribution — SALET's guess-distribution chart grows in
    game_third — bar 3 green; SALET's scored game for THIRD fades in above it
    game_wheel — bar 4 green; SALET's scored game for WHEEL fades in below bar 3
    wheel_center — chart and THIRD board leave, bg to navy; WHEEL board to the middle
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

    def _green(self, n):
        return self.chart.bar_of[n].animate.set_fill(TILE_CORRECT) \
                                           .set_stroke(TILE_CORRECT)

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
        self.play(self._green("3"), FadeIn(self.board_third), run_time=0.8)

    # c : bar 4 turns green; SALET's game for WHEEL fades in below bar 3
    @subscene
    def game_wheel(self):
        self.board_wheel = self._setup_board("wheel", below=True)
        self.play(self._green("4"), FadeIn(self.board_wheel), run_time=0.8)

    # d : the chart and THIRD's board leave as the background turns navy; WHEEL's
    #     board to the middle
    @subscene
    def wheel_center(self):
        self.play(FadeOut(self.chart), FadeOut(self.board_third),
                  bg_to(self, BOARD_NAVY), run_time=1.0)
        self.play(self.board_wheel.animate.scale(1 / BOARD_SCALE).move_to(ORIGIN),
                  run_time=1.2)
        self.chart = self.board_third = None
