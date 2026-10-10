"""Scene 99 — YouTube thumbnails (static, NOT animated).

One `@thumbnail` per thumbnail, each a static composition from a clean frame.

    render 99a              # 4K PNG, the upload asset (media/images/99thumbnails/2160p/)
    render 99a --fast       # quick low-res check

BEAT MAP
  a histogram — light blue; scene 08's normal-mode histogram in navy with no gaps;
                ADIEU and AUDIO at the top with lines to their values, SALET as
                ????? with a line to its value; GREAT <-> WORST along the bottom.
                Every word is a tile row scored against VIDEO.

REUSE MAP
  background    WordleScene (BG_COLOR, the channel's light blue)
  histogram     bpkfigures.histogram.get_histogram, bar_ratio=1.0 (no gaps), bars
                BOARD_NAVY; counts per 0.01 bin from assets/histogram_data.py ->
                histogram_cache.json (the committed optturns sweep, 08's bins)
  word rows     assets/board.py get_scored_row; codes from math/wordle.py pattern
                against VIDEO (SALET's code is its own, its letters shown as ?)
  marker lines  08's callouts: a line from the word to the word's EXACT value
                (total / 2315), here stopping at the top of its bar, in navy
  arrow         manim DoubleArrow, navy
"""
from pathlib import Path
from collections import Counter
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "math"))

from config import *
from bpkfigures.histogram import get_histogram
from assets import histogram_data
from assets.board import get_scored_row
from wordle import pattern

DATA = histogram_data.load()
N_ANSWERS = 2315
ANSWER = "video"                 # every word on the thumbnail is scored against this

HIST_W, HIST_H = 14.4, 4.4       # the histogram's plot area
HIST_CENTER = DOWN * 0.55
ROW_SCALE = 0.62                 # tile rows, relative to a board row (4.9 wide)
TOP_Y = 3.55                     # word rows at the top of the frame
ARROW_Y = -3.75                  # GREAT <-> WORST
LINE_STROKE = 5


def _row(word, shown=None):
    """`word`'s row scored against ANSWER, with `shown` letters on the tiles."""
    return get_scored_row(shown or word, pattern(word, ANSWER)).scale(ROW_SCALE)


class Thumbnails(WordleScene):

    def setup_scene(self):
        pass

    # a : the histogram, ADIEU / AUDIO / ?????, GREAT <-> WORST
    @thumbnail
    def histogram(self):
        counts = Counter(DATA["bins"])
        lo, hi = min(counts), max(counts)
        plot = get_histogram(None, counts=counts, min_val=lo, max_val=hi,
                             width=HIST_W, height=HIST_H, center=HIST_CENTER,
                             bar_color=BOARD_NAVY, ink_color=BOARD_NAVY,
                             bar_ratio=1.0, x_tick_step=10 ** 6)
        plot.bars.set_stroke(BOARD_NAVY, width=1)   # hides antialias seams between bars
        g = plot.hist_geom
        bar_w = g["width"] / g["n"]
        left = plot.x_axis.get_left()[0]
        base = plot.x_axis.get_center()[1]

        def x_of(word):
            # exact value on the bin scale: bin b spans [b, b+1) hundredths
            v = DATA["totals"][DATA["words"].index(word)] / N_ANSWERS * 100
            return left + (v - lo) * bar_w

        def bar_top(word):
            b = DATA["bins"][DATA["words"].index(word)]
            return base + counts[b] / g["max_mag"] * g["height"]

        def marked(word, row_x, shown=None):
            row = _row(word, shown).move_to([row_x, TOP_Y, 0])
            x = x_of(word)
            line = Line(row.get_bottom() + DOWN * 0.12, [x, bar_top(word) + 0.08, 0],
                        color=BOARD_NAVY, stroke_width=LINE_STROKE)
            return VGroup(row, line)

        salet = marked("salet", -4.9, shown="?????")
        adieu = marked("adieu", 0.3)
        audio = marked("audio", 5.0)

        great = _row("great")
        worst = _row("worst")
        great.move_to([-8 + 0.35 + great.width / 2, ARROW_Y, 0])
        worst.move_to([8 - 0.35 - worst.width / 2, ARROW_Y, 0])
        arrow = DoubleArrow(great.get_right() + RIGHT * 0.2, worst.get_left() + LEFT * 0.2,
                            buff=0, color=BOARD_NAVY, stroke_width=8,
                            tip_length=0.35, max_tip_length_to_length_ratio=1)

        self.add(plot, salet, adieu, audio, great, worst, arrow)
