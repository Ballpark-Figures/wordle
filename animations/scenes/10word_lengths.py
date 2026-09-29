"""SCENE 10 — SALET's guess distribution, two of its games, and word lengths.

Navy background (WordleBoardScene). Follows scene 09 directly, so it opens EMPTY and
brings the chart in. Talking head THG follows, so it ends with the WHEEL board up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a distribution — the Wordle-stats "guess distribution" chart for SALET's optimal
                   strategy grows in: rows 1-6, one bar each, count inside  (VO 1)
  b game_third   — a mini board just above bar 3 plays SALET, NORTH, THIRD  (VO 1)
  c game_wheel   — a mini board just below bar 3, right of bar 4, plays SALET,
                   BEVOR, CHIMP, WHEEL                                       (VO 1)
  d wheel_center — the chart and the THIRD board fade; the WHEEL board moves to
                   the middle at full tile size                              (VO 1)
  (VO 2 — the word-length discussion — has no subscene in the script yet.)

REUSE MAP — every element and the one source it comes from:
  chart          bpkfigures.bar_graph.get_bar_chart(orientation="horizontal",
                 min_length=…, value_inside=True) — the horizontal mode was added
                 for this scene; entrance bar_graph.grow_bars(edge=LEFT)
  bar colour     config.py TILE_ABSENT (Wordle's grey, as the real stats graph)
  text           crisp_text, white; title bold
  boards         assets/board.py get_board(rows=n), scaled down; typing
                 board.type_word + assets/keys.py key_cues, scoring board.reveal,
                 win board.bounce (height scaled with the tiles, as 07)

NUMBERS — all SOURCED, from assets/word_lengths_data.py -> word_lengths_cache.json:
  counts per row   SALET's committed optimal tree (constrained to 6 guesses),
                   asserted there to sum to 2315 answers and 7920 guesses
  THIRD / WHEEL    those answers' lines in the same tree, codes re-checked against
                   math/wordle.py pattern()

ON-SCREEN TEXT beyond column 2 (the user's call): the "GUESS DISTRIBUTION" title,
in the real Wordle stats screen's capitals.

LAYOUT (the user's): the chart follows Wordle's stats screen — title flush left with
the row numbers, row numbers and counts one size, bars close together. Both boards
start just right of bar 4's end: THIRD's directly above bar 3, WHEEL's directly
below it. Boards have only as many rows as the game used.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.bar_graph import get_bar_chart, grow_bars
from assets.board import get_board
from assets.keys import key_cues
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
BOARD_GAP_X = 0.3            # boards start this far right of bar 4's end
BOARD_GAP_Y = 0.15           # THIRD this far above bar 3, WHEEL this far below
BOUNCE_H = 0.35              # board.bounce's default, for a full-size tile


class Scene10(WordleBoardScene):
    """BEAT MAP
    distribution — SALET's guess-distribution chart grows in
    game_third — mini board beside row 3 plays SALET's game for THIRD
    game_wheel — mini board beside row 4 plays SALET's game for WHEEL
    wheel_center — chart and THIRD board leave; WHEEL board to the middle
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
        """A mini board just right of bar 4's end — its top just under bar 3 if
        `below` (WHEEL), else its bottom just over bar 3 (THIRD)."""
        game = GAMES[answer]
        board = get_board(rows=len(game["guesses"])).scale(BOARD_SCALE)
        bar3, bar4 = self.chart.bar_of["3"], self.chart.bar_of["4"]
        board.align_to(bar4.get_right() + RIGHT * BOARD_GAP_X, LEFT)
        if below:
            board.align_to(bar3.get_bottom() + DOWN * BOARD_GAP_Y, UP)
        else:
            board.align_to(bar3.get_top() + UP * BOARD_GAP_Y, DOWN)
        return board

    def _play_game(self, board, answer):
        """Type and score each guess in turn, then the winning row bounces."""
        guesses = GAMES[answer]["guesses"]
        for row, g in enumerate(guesses):
            board.type_word(self, row, g["word"], 0.65, per_letter=key_cues(self))
            board.reveal(self, row, g["code"], 1.2)
        board.bounce(self, len(guesses) - 1, 0.8, height=BOUNCE_H * BOARD_SCALE)

    # a : SALET's guess distribution grows in
    @subscene
    def distribution(self):
        self._setup_chart()
        c = self.chart
        self.play(FadeIn(c.title), FadeIn(c.labels), run_time=0.8)
        grow_bars(self, c.bars, 1.5, lag=0.08, edge=LEFT)
        self.play(FadeIn(c.values), run_time=0.6)

    # b : beside row 3, SALET's game for THIRD
    @subscene
    def game_third(self):
        self.board_third = self._setup_board("third", below=False)
        self.play(FadeIn(self.board_third), run_time=0.6)
        self._play_game(self.board_third, "third")

    # c : beside row 4, SALET's game for WHEEL
    @subscene
    def game_wheel(self):
        self.board_wheel = self._setup_board("wheel", below=True)
        self.play(FadeIn(self.board_wheel), run_time=0.6)
        self._play_game(self.board_wheel, "wheel")

    # d : the chart and THIRD's board leave; WHEEL's board to the middle
    @subscene
    def wheel_center(self):
        self.play(FadeOut(self.chart), FadeOut(self.board_third), run_time=0.8)
        self.play(self.board_wheel.animate.scale(1 / BOARD_SCALE).move_to(ORIGIN),
                  run_time=1.2)
        self.chart = self.board_third = None
