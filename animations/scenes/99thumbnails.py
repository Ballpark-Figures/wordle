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
  marker lines  08's pinned callouts (assets/stacks_view.py pinned, 08's CALLOUTS):
                white, LINE_STROKE, into the word's own SLICE of its bar --
                ADIEU/AUDIO from the row's left side to the slice centre at the
                exact value, SALET from the row's bottom to its slice's top edge
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
from assets.stacks_view import LINE_STROKE
from wordle import pattern

DATA = histogram_data.load()
N_ANSWERS = 2315
ANSWER = "video"                 # every word on the thumbnail is scored against this

HIST_W, HIST_H = 14.4, 4.4       # the histogram's plot area
HIST_CENTER = DOWN * 0.55
ROW_SCALE = 0.62                 # tile rows, relative to a board row (4.9 wide)
TOP_Y = 3.55                     # word rows at the top of the frame
ARROW_Y = -3.75                  # GREAT <-> WORST
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

        def slice_box(word):
            # 08's slice: each bar is a stack of its words, best at the bottom, so
            # `word` is row DATA["rows"] of its bin's bar, one count tall
            i = DATA["words"].index(word)
            b, r = DATA["bins"][i], DATA["rows"][i]
            h = g["height"] / g["max_mag"]
            x0 = left + (b - lo) * bar_w
            return x0, base_y + r * h, x0 + bar_w, base_y + (r + 1) * h

        def marked(word, row_x, attach, anchor, exact, shown=None):
            # 08's pinned callout (assets/stacks_view.py `pinned`): the line runs
            # from the row's `attach` side to the slice's centre ("center") or the
            # side facing the row ("edge"), moved sideways to the exact value
            row = _row(word, shown).move_to([row_x, TOP_Y, 0])
            x0, y0, x1, y1 = slice_box(word)
            ax, ay = {"center": (0, 0), "edge": (0, 1)}[anchor]
            end = np.array([(x0 + x1) / 2, (y0 + y1) / 2 + ay * (y1 - y0) / 2, 0])
            if exact:
                end[0] = x_of(word)
            start = {"left": row.get_left(), "bottom": row.get_bottom()}[attach]
            line = Line(start, end, color=line_color, stroke_width=LINE_STROKE)
            return VGroup(line, row)

        # 08's specs: SALET_FULL is pinned(..., "bottom") to its slice's top edge;
        # ADIEU and AUDIO to their slice centres at the exact value, as 08, but every
        # line leaves the bottom of the middle letter (user's call)
        salet = marked("salet", -4.9, "bottom", "edge", False, shown="?????")
        adieu = marked("adieu", 0.3, "bottom", "center", True)
        audio = marked("audio", 5.0, "bottom", "center", True)

        great = _row("great")
        worst = _row("worst")
        great.move_to([-8 + 0.35 + great.width / 2, ARROW_Y, 0])
        worst.move_to([8 - 0.35 - worst.width / 2, ARROW_Y, 0])
        arrow = DoubleArrow(great.get_right() + RIGHT * 0.2, worst.get_left() + LEFT * 0.2,
                            buff=0, color=BOARD_NAVY, stroke_width=8,
                            tip_length=0.35, max_tip_length_to_length_ratio=1)

        self.add(plot, salet, adieu, audio, great, worst, arrow)
