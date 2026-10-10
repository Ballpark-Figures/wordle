"""Scene 99 — YouTube thumbnails (static, NOT animated).

One `@thumbnail` per thumbnail, each a static composition from a clean frame.

    render 99a              # 4K PNG, the upload asset (media/images/99thumbnails/2160p/)
    render 99a --fast       # quick low-res check

BEAT MAP
  a histogram — light blue; scene 08's normal-mode histogram in navy with no gaps;
                ADIEU and AUDIO at the top with lines to their values, SALET as
                ????? with a line to its value; GREAT <-> WORST along the bottom.
                Every word is a tile row scored against VIDEO. White lines.
  b-e         — a with black / gold / yellow / orange lines, for comparison

REUSE MAP
  background    WordleScene (BG_COLOR, the channel's light blue)
  histogram     bpkfigures.histogram.get_histogram, bar_ratio=1.0 (no gaps), bars
                BOARD_NAVY; counts per 0.01 bin from assets/histogram_data.py ->
                histogram_cache.json (the committed optturns sweep, 08's bins)
  word rows     assets/board.py get_scored_row; codes from math/wordle.py pattern
                against VIDEO (SALET's code is its own, its letters shown as ?)
  marker lines  from the bottom of the middle letter to the TOP of the word's bar
                (user's call), rounded ends, LINE_STROKE 5; ADIEU/AUDIO at their
                exact value as in 08, SALET at its bar's centre
  tile borders  thin black (user's call)
  arrow         manim DoubleArrow, navy
"""
from pathlib import Path
from collections import Counter
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "math"))

import numpy as np

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
LINE_STROKE = 5                  # thicker than 08's LINE_STROKE (3), rounded ends
LINE_COLOR = WHITE               # a's line colour; b-e try others (user comparing)
TILE_BORDER = BLACK              # thin black border around every tile (user's call)
TILE_BORDER_W = 2.0


def _row(word, shown=None):
    """`word`'s row scored against ANSWER, with `shown` letters on the tiles."""
    row = get_scored_row(shown or word, pattern(word, ANSWER)).scale(ROW_SCALE)
    for t in row.tiles[0]:
        t.set_stroke(TILE_BORDER, width=TILE_BORDER_W)
    return row


class Thumbnails(WordleScene):

    def setup_scene(self):
        pass

    # a : the histogram, ADIEU / AUDIO / ?????, GREAT <-> WORST
    @thumbnail
    def histogram(self):
        self._histogram(LINE_COLOR)

    # b : a with black lines
    @thumbnail
    def histogram_black(self):
        self._histogram(BLACK)

    # c : a with gold lines
    @thumbnail
    def histogram_gold(self):
        self._histogram(ACCENT_GOLD)

    # d : a with yellow lines
    @thumbnail
    def histogram_yellow(self):
        self._histogram(LIGHT_YELLOW)

    # e : a with orange lines
    @thumbnail
    def histogram_orange(self):
        self._histogram(ACCENT_ORANGE)

    def _histogram(self, line_color):
        counts = Counter(DATA["bins"])
        lo, hi = min(counts), max(counts)
        plot = get_histogram(None, counts=counts, min_val=lo, max_val=hi,
                             width=HIST_W, height=HIST_H, center=HIST_CENTER,
                             bar_color=BOARD_NAVY, ink_color=BOARD_NAVY,
                             bar_ratio=1.0, x_tick_step=10 ** 6)
        # one merged outline over the bars' own corners, so there is no seam between
        # neighbouring bars at any resolution (separate rectangles antialias a seam)
        pts = []
        for bar in sorted(plot.bars, key=lambda b: b.get_left()[0]):
            pts += [[bar.get_left()[0], bar.get_top()[1], 0],
                    [bar.get_right()[0], bar.get_top()[1], 0]]
        base_y = plot.bars[0].get_bottom()[1]
        pts = [[pts[0][0], base_y, 0]] + pts + [[pts[-1][0], base_y, 0]]
        skyline = Polygon(*pts, fill_color=BOARD_NAVY, fill_opacity=1, stroke_width=0)
        plot.remove(plot.bars)
        plot.add(skyline)
        g = plot.hist_geom
        bar_w = g["width"] / g["n"]
        left = plot.x_axis.get_left()[0]

        def x_of(word):
            # exact value on the bin scale: bin b spans [b, b+1) hundredths
            v = DATA["totals"][DATA["words"].index(word)] / N_ANSWERS * 100
            return left + (v - lo) * bar_w

        def bar_top(word):
            # the top of the bar holding `word`, read off the drawn bar itself
            b = DATA["bins"][DATA["words"].index(word)]
            x = left + (b - lo + 0.5) * bar_w
            bar = next(r for r in plot.bars if r.get_left()[0] <= x <= r.get_right()[0])
            return bar.get_top()[1]

        def marked(word, row_x, exact, shown=None):
            # from the bottom of the middle letter to the top of the word's bar --
            # at its exact value (ADIEU, AUDIO, as 08) or the bar's centre (SALET)
            row = _row(word, shown).move_to([row_x, TOP_Y, 0])
            b = DATA["bins"][DATA["words"].index(word)]
            x = x_of(word) if exact else left + (b - lo + 0.5) * bar_w
            line = Line(row.get_bottom(), [x, bar_top(word), 0], color=line_color,
                        stroke_width=LINE_STROKE)
            line.set_cap_style(CapStyleType.ROUND)
            return VGroup(line, row)

        salet = marked("salet", -4.9, False, shown="?????")
        adieu = marked("adieu", 0.3, True)
        audio = marked("audio", 5.0, True)

        great = _row("great")
        worst = _row("worst")
        great.move_to([-8 + 0.35 + great.width / 2, ARROW_Y, 0])
        worst.move_to([8 - 0.35 - worst.width / 2, ARROW_Y, 0])
        arrow = DoubleArrow(great.get_right() + RIGHT * 0.2, worst.get_left() + LEFT * 0.2,
                            buff=0, color=BOARD_NAVY, stroke_width=8,
                            tip_length=0.35, max_tip_length_to_length_ratio=1)

        self.add(plot, salet, adieu, audio, great, worst, arrow)
