"""Scene 13 — random strategies on a number line of average guesses. Navy background.

Scene 12 ends with the frame cleared, so everything here fades in. Talking head THI
follows, so f ends with the whole line on screen.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_line     — the number line, 3 at the left and 6 at the right, running on
                    past both edges; the title and "(Win Rate)" fade in    (13a, VO 1)
  b optimal       — the Optimal SALET marker at 3.42                       (13b, VO 1)
  c random        — the line zooms out to 3..2500; the Random marker at 2315 (13c, VO 2)
  d no_repeats    — the Random (no repeats) marker at 1158                 (13d, VO 3)
  e until_single  — the line zooms in, the leftmost dot (3.42) at the left and 8
                    at the right (1158 and 2315 slide off);
                    the Random Until Single Answer marker at 6.90          (13e, VO 4)
  f compatible    — the Random Compatible Answers marker at 4.08, below
                    the line                                               (13f, VO 5)

REUSE MAP — every element, the one source it comes from, and how it enters:
  number line, ticks,   bpkfigures/number_line.py `ZoomLine` (new, for number lines
  zooms, markers        and timelines): `zoom` for c/e, `add_marker` + `marker_in`
  title                 crisp_text, WHITE, FONT_SIZE_LG — 08's title
  subtitle              crisp_text, WHITE, FONT_SIZE_MD, under the title
  title/subtitle in     plain FadeIn, played with their content — 08histogram.py:369
                        (the heading fades in with the axis), 10word_lengths.py:277
  line in               FadeIn, with the title (as 08's axis)
  markers in            ZoomLine.marker_in (new with the asset; no earlier scene has
                        a marker)
  SALET                 assets/board.py `get_typed_row` (the black typed row, as 12's
                        SALET), its border thinned by 12's rule for a small row
  marker text           crisp_text via the asset, BLACK, on the shared card
                        (bpkfigures/card.py `card_behind`, via add_marker(box=...)) —
                        no earlier scene in this video boxes a label, so the house
                        card is the precedent
  colours               BOARD_NAVY via WordleBoardScene, as 08 and 12
  win-rate colours      config.py SCORE_RED -> SCORE_GREEN (yahtzee's, made for text on
                        this cream card), by `win_color`
Nothing leaves: THI follows.

EVERY NUMBER is the script's, and each matches the committed data it came from:
  3.42              optturns: salet 7920 / 2315 = 3.42117
  2315, 0.26%       uniform over the 2315 with repeats: mean 2315, 1-(2314/2315)^6
  1158              uniform without repeats: (2315 + 1) / 2
  6.90, 59.30%      data/shared/wordlesim/random-blind_t1000000_s0.csv (6.8996, 59.2955%)
  4.08, 98.20%      data/shared/wordlesim/random_t1000000_s0.csv (4.0840, 98.1953%)
The averages are shown only by where each marker sits (user's call).

On-screen text is column 2's (the title and the marker labels, without "Win") plus
the user's "(Win Rate)" subtitle, which is what the bare percentages mean. Tick
numbers are part of the number line.

LAYOUT CHOICES, flagged:
  - The line runs off both frame edges with arrow tips (user's call). It opens on
    3..6 across x -6..6 (user's call: left at 3, the same 3-wide range as the earlier
    1..4 opening).
  - The zoom out keeps 3 where it was (3..2500), so the anchor does not jump; at that
    scale 0 is back in view, just left of 3.
  - The zoom in puts the leftmost marker at x=-6 (user's call), derived from the
    markers, with 8 still at x=6.
  - Labels are whole numbers only (min_label_step=1); ticks go down to tenths.
  - 4.08's label hangs BELOW the line: above, it would overlap 3.42's. Its stem
    runs from the dot through the tick labels; a tick label it crosses is dropped.
  - Markers: a white dot and stem, running into the card (user's call: boxed text).
  - Each win rate is coloured red -> green, very nonlinearly (user's call): the
    colour position is t = 1 - (1 - rate)^P with P set so t = 0.5 at WIN_MID (98%),
    i.e. a power law in the LOSS rate. The colour runs round the hue wheel from
    SCORE_RED to SCORE_GREEN (through amber), since a straight RGB blend of the two
    goes muddy brown in the middle, where 98.20% sits. Resulting t: 0.26% 0.00,
    59.30% 0.15, 98.20% 0.51, 100% 1.00.
"""
from pathlib import Path
import colorsys
import math
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.number_line import ZoomLine
from assets.board import STROKE, get_typed_row
from assets.groups import HEADER_W

TITLE = "Average Guesses by Strategy"
SUBTITLE = "(Win Rate)"
SUBTITLE_BUFF = 0.15
SALET_W = 2.2             # the SALET row's width in the Optimal label
LINE_Y = -0.4
TITLE_BUFF = 0.6
MARKER_FS = 30
CARD_PAD = 0.18           # the marker cards' margin round their text
WIN_MID = 0.98            # the win rate that sits halfway from red to green


def win_color(rate):
    """A win rate (0..1) on the red -> green scale: halfway at WIN_MID, via a
    power law in the loss rate, interpolated round the hue wheel."""
    p = math.log(0.5) / math.log(1 - WIN_MID)
    t = 1 - (1 - rate) ** p
    (h0, s0, v0), (h1, s1, v1) = (colorsys.rgb_to_hsv(*ManimColor(c).to_rgb())
                                  for c in (SCORE_RED, SCORE_GREEN))
    hsv = [a + (b - a) * t for a, b in ((h0, h1), (s0, s1), (v0, v1))]
    return ManimColor.from_rgb(colorsys.hsv_to_rgb(*hsv))


class Scene13(WordleBoardScene):
    """show_line — the line, 3..6, and the title
    optimal — 3.42
    random — zoom out to 3..2500; 2315
    no_repeats — 1158
    until_single — zoom in to 3.42..8; 6.90
    compatible — 4.08, below the line
    """

    def setup_scene(self):
        pass

    def _marker(self, value, lines, side=UP):
        """The last line is the win rate, "NN.NN%"; it takes its colour."""
        rate = lines[-1]
        lines = lines[:-1] + [(rate, win_color(float(rate.rstrip("%")) / 100))]
        return self.line.add_marker(value, lines, side=side, font_size=MARKER_FS,
                                    text_color=BLACK, box={"pad": CARD_PAD})

    # a : the number line, 3 to 6, extending both ways; the title
    def _setup_show_line(self):
        self.line = ZoomLine(3, 6, y=LINE_Y, min_label_step=1)
        self.title = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG)
        self.title.to_edge(UP, buff=TITLE_BUFF)
        self.subtitle = crisp_text(SUBTITLE, color=WHITE, font_size=FONT_SIZE_MD)
        self.subtitle.next_to(self.title, DOWN, buff=SUBTITLE_BUFF)

    @subscene
    def show_line(self):
        self._setup_show_line()
        self.play(FadeIn(self.line), FadeIn(self.title), FadeIn(self.subtitle),
                  run_time=1.2)

    # b : Optimal SALET at 3.42
    @subscene
    def optimal(self):
        salet = get_typed_row("salet")
        salet.scale(SALET_W / salet.width)
        for t in salet.tiles[0]:
            t.set_stroke(width=STROKE * min(1.0, SALET_W / HEADER_W))
        m = self._marker(3.42, ["Optimal", salet, "100%"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # c : zoom out to 3..2500; Random at 2315
    @subscene
    def random(self):
        self.play(self.line.zoom(3, 2500), run_time=3.0)
        m = self._marker(2315, ["Random", "0.26%"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # d : Random (no repeats) at 1158
    @subscene
    def no_repeats(self):
        m = self._marker(1158, ["Random", "(no repeats)", "0.26%"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # e : zoom in, the leftmost dot at the left, 8 at the right; 1158 and 2315
    #     slide off; Random Until Single Answer at 6.90
    @subscene
    def until_single(self):
        left = min(m.value for m in self.line.markers)
        self.play(self.line.zoom(left, 8), run_time=3.0)
        m = self._marker(6.90, ["Random Until", "Single Answer", "59.30%"])
        self.play(self.line.marker_in(m), run_time=1.0)

    # f : Random Compatible Answers at 4.08, below the line
    @subscene
    def compatible(self):
        m = self._marker(4.08, ["Random", "Compatible Answers", "98.20%"],
                         side=DOWN)
        self.play(self.line.marker_in(m), run_time=1.0)
