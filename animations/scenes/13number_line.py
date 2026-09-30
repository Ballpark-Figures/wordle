"""Scene 13 — random strategies on a number line of average guesses. Navy background.

Scene 12 ends with the frame cleared, so everything here fades in. Talking head THI
follows, so f ends with the whole line on screen.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_line     — the number line, 0 to 4 across the middle, running on past both
                    ends; the title fades in                               (13a, VO 1)
  b optimal       — the Optimal (SALET) marker at 3.42                     (13b, VO 1)
  c random        — the line zooms out to 0..2500; the Random marker at 2315 (13c, VO 2)
  d no_repeats    — the Random (no repeats) marker at 1158                 (13d, VO 3)
  e until_single  — the line zooms in to 0..8 (1158 and 2315 slide off);
                    the Random Until Single Answer marker at 6.90          (13e, VO 4)
  f compatible    — the Random Compatible Answers marker at 4.08, below
                    the line                                               (13f, VO 5)

REUSE MAP — every element and the one source it comes from:
  number line, ticks,   bpkfigures/number_line.py `ZoomLine` (new, for number lines
  zooms, markers        and timelines): `zoom` for c/e, `add_marker` + `marker_in`
  title                 crisp_text, WHITE, FONT_SIZE_LG — 08's title
  text                  crisp_text / crisp_paragraph via the asset, WHITE
  colours               BOARD_NAVY via WordleBoardScene, as 08 and 12

EVERY NUMBER is the script's, and each matches the committed data it came from:
  3.42              optturns: salet 7920 / 2315 = 3.42117
  2315, 0.26%       uniform over the 2315 with repeats: mean 2315, 1-(2314/2315)^6
  1158              uniform without repeats: (2315 + 1) / 2
  6.90, 59.30%      data/shared/wordlesim/random-blind_t1000000_s0.csv (6.8996, 59.2955%)
  4.08, 98.20%      data/shared/wordlesim/random_t1000000_s0.csv (4.0840, 98.1953%)

On-screen text is only column 2's: the title and the marker labels. Tick numbers are
part of the number line.

LAYOUT CHOICES, flagged:
  - "0 to 4, extending in both directions": 0..4 spans x -6..6 and the line runs on
    to the frame edges with arrow tips, ticked and labelled all the way (so -0.5 and
    4.5 show). tick_min=0 on the ZoomLine would stop the ticks at 0.
  - Labels are whole numbers only (min_label_step=1); ticks go down to tenths.
  - Both zooms keep 0 at x=-6: out to 0..2500, in to 0..8.
  - 4.08's label hangs BELOW the line: above, it would overlap 3.42's.
  - Markers are white: a dot, a stem and the centred label.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.number_line import ZoomLine

TITLE = "Average Guesses by Strategy"
LINE_Y = -0.4
TITLE_BUFF = 0.6
MARKER_FS = 30


class Scene13(WordleBoardScene):
    """show_line — the line, 0..4, and the title
    optimal — 3.42
    random — zoom out to 0..2500; 2315
    no_repeats — 1158
    until_single — zoom in to 0..8; 6.90
    compatible — 4.08, below the line
    """

    def setup_scene(self):
        pass

    def _marker(self, value, lines, side=UP):
        return self.line.add_marker(value, lines, side=side, font_size=MARKER_FS)

    # a : the number line, 0 to 4, extending both ways; the title
    def _setup_show_line(self):
        self.line = ZoomLine(0, 4, y=LINE_Y, min_label_step=1)
        self.title = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG)
        self.title.to_edge(UP, buff=TITLE_BUFF)

    @subscene
    def show_line(self):
        self._setup_show_line()
        self.play(FadeIn(self.line), FadeIn(self.title, shift=DOWN * 0.2),
                  run_time=1.2)

    # b : Optimal (SALET) at 3.42
    @subscene
    def optimal(self):
        m = self._marker(3.42, ["Optimal", "(SALET)", "100% Win"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # c : zoom out to 0..2500; Random at 2315
    @subscene
    def random(self):
        self.play(self.line.zoom(0, 2500), run_time=3.0)
        m = self._marker(2315, ["Random", "0.26% Win"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # d : Random (no repeats) at 1158
    @subscene
    def no_repeats(self):
        m = self._marker(1158, ["Random", "(no repeats)", "0.26% Win"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # e : zoom in to 0..8, 1158 and 2315 slide off; Random Until Single Answer at 6.90
    @subscene
    def until_single(self):
        self.play(self.line.zoom(0, 8), run_time=3.0)
        m = self._marker(6.90, ["Random Until", "Single Answer", "59.30% Win"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # f : Random Compatible Answers at 4.08, below the line
    @subscene
    def compatible(self):
        m = self._marker(4.08, ["Random", "Compatible Answers", "98.20% Win"],
                         side=DOWN)
        self.play(self.line.marker_in(m), run_time=1.0)
