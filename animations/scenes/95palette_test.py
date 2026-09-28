"""SCRATCH — tile palette candidates, side by side, to choose the board colours.

START scored against INTRO (so one grey, one yellow, one green tile shows each
colour), three ways, on navy (left) and Wordle black (right). The hexes here are
CANDIDATES under comparison, which is why they are literals in a test scene; the
chosen set belongs in config.py's TILE_* constants, and this file then goes away.

    render 95a
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import TILE, GAP, STROKE, LETTER_FRAC

#            name                      grey       yellow     green
OPTIONS = [("Current (NYT)",          TILE_ABSENT, TILE_PRESENT, TILE_CORRECT),
           ("A: gold + accent green", "#4a4a4d", ACCENT_GOLD, ACCENT_GREEN),
           ("B: gold + lifted green", "#4a4a4d", ACCENT_GOLD, "#4CB050")]
CODE = [0, 1, 0, 2, 0]      # START against INTRO: S grey, T yellow, R green


def _row(word, colours):
    g = VGroup()
    for i, (ch, t) in enumerate(zip(word, CODE)):
        c = colours[t]
        sq = Square(side_length=TILE, fill_color=c, fill_opacity=1,
                    stroke_color=c, stroke_width=STROKE).shift(RIGHT * i * (TILE + GAP))
        letter = crisp_text(ch, color=TILE_TEXT, weight=BOLD)
        letter.scale_to_fit_height(TILE * LETTER_FRAC).move_to(sq)
        g.add(sq, letter)
    return g


class Scene95(WordleBoardScene):
    # a : the three candidates, on navy and on Wordle black
    @still
    def compare(self):
        fw = config.frame_x_radius
        self.add(Rectangle(width=fw, height=2 * config.frame_y_radius,
                           fill_color=WORDLE_BG, fill_opacity=1, stroke_width=0)
                 .move_to(RIGHT * fw / 2))
        for k, (name, grey, yellow, green) in enumerate(OPTIONS):
            y = 2.6 - 2.6 * k
            self.add(crisp_text(name, color=WHITE, font_size=30).move_to(UP * (y + 0.95)))
            for x in (-fw / 2, fw / 2):
                self.add(_row("START", {0: grey, 1: yellow, 2: green}).move_to([x, y, 0]))
        self.add(crisp_text("on navy", color=WHITE, font_size=22).move_to([-fw / 2, -4.1, 0]),
                 crisp_text("on Wordle black", color=WHITE, font_size=22)
                 .move_to([fw / 2, -4.1, 0]))
