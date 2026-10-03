"""Scene 08's opener histogram in its FULL view — the bars, the axis, the ticks, the
axis label and the title — for a scene that brings it back (09).

COPIED from scenes/08histogram.py (2026-09-29): the constants and layout rules below
are 08's verbatim, so 09's histogram is the one 08 ends on. 08 still carries its own
copy (it was uncommitted work when 09 needed this); moving 08 onto this module is the
follow-up, and until then an edit to 08's layout must be made in both places.

Only the FULL view is here — 09 never zooms — so the tick fading 08 does per frame is
evaluated once, for VIEW_FULL.

    chrome = HistogramChrome()                # axis, ticks, x label, title
    stacks = full_stacks()                    # the bars, every word placed
    layer_bars(counts, color)                 # a sub-histogram layer over the bars
"""
import numpy as np

from config import *
from assets import histogram_data
from assets.word_stacks import WordStacks, PITCH, STEP, WORD_W
from assets.stacks_view import ASPECT, FRAME_W

DATA = histogram_data.load()
BIN_LO = min(DATA["bins"])
TALLEST = max(DATA["rows"]) + 1

BAR_COLOR = BG_COLOR          # "default light blue" — the channel's light blue
BASE_FRAC = 0.14              # the baseline sits this far up the frame
TOP_FRAC = 0.70               # the tallest bar in a view reaches this far up
STAT_TOP = 0.74               # 08r/s: the vertical lines rise to this far up
TITLE = "Average Guesses by Opening Word"
TITLE_BUFF = 0.5              # get_histogram's gap under its title (16-wide units)
AXIS_LO, AXIS_HI = 3.40, 4.12 # the axis line and its ticks run over these values
AXIS_STROKE = 3.0             # as it would be in a 16-wide frame
TICK_LEN = 0.12               # tick mark, in 16-wide-frame units
TICK_GAP = 0.08               # tick mark to its label
XLABEL_GAP = 0.15             # tick labels to the axis label
TICK_ON, TICK_OFF = 0.08, 0.07  # a tick level shows fully when its labels are this
                              # far apart (fraction of frame width), not at all below
STAT_LINE_BUFF = 0.08         # "Answer" above its label (16-wide units)


def x_of(v):
    """x of average-guess value v — WordStacks.x_of_value for origin (0, 0) at BIN_LO."""
    return (v * 100 - 0.5 - BIN_LO) * PITCH


def _view(left, right, tall_rows):
    w = right - left
    h = w / ASPECT
    return (left, -BASE_FRAC * h, w, (TOP_FRAC - BASE_FRAC) * h / (tall_rows * STEP))


def full_view(axis_lo=AXIS_LO, axis_hi=AXIS_HI, tallest=TALLEST):
    """08's FULL view for an axis running `axis_lo`..`axis_hi`: a 4% margin each side
    (2% clipped the end tick labels), the tallest bar (`tallest` words) at TOP_FRAC.
    The defaults are 08's own; scene 19 widens the axis to make room for hard mode."""
    span = x_of(axis_hi) - x_of(axis_lo)
    return _view(x_of(axis_lo) - 0.04 * span / 0.92,
                 x_of(axis_hi) + 0.04 * span / 0.92, tallest)


def view_center(view):
    """The world centre of `view`'s frame."""
    left, bottom, w, _ = view
    return np.array([left + w / 2, bottom + w / ASPECT / 2, 0.0])


def view_k(view):
    """One 16-wide design unit, in `view`'s world units."""
    return view[2] / FRAME_W


VIEW_FULL = full_view()
LEFT, BOTTOM, WIDTH, SQUASH = VIEW_FULL
HEIGHT = WIDTH / ASPECT
K = view_k(VIEW_FULL)         # one 16-wide design unit, in this view's world units
CENTER = view_center(VIEW_FULL)


def design(x, y, view=VIEW_FULL):
    """The world point at design coordinates (x, y) of the ordinary 16 x 9 frame."""
    return view_center(view) + view_k(view) * np.array([x, y, 0.0])


def _restroke(mob):
    """(member, stroke width) for every stroked member, read before a rescale."""
    return [(m, m.get_stroke_width()) for m in mob.get_family()
            if isinstance(m, VMobject) and len(m.points) and m.get_stroke_width() > 0]


def to_view(mob, view=VIEW_FULL, shift=ORIGIN):
    """Re-project `mob`, built in the ordinary 16 x 9 frame, into `view` (VIEW_FULL
    by default) so it looks exactly as it did: scaled by the view's K about the
    origin, moved to the view's centre (plus `shift`, world units: scene 19 puts a
    screen one frame above or below the histogram), strokes widened by K (they are
    in world units). Returns `mob`."""
    k = view_k(view)
    widths = _restroke(mob)
    if isinstance(mob, Arrow):
        mob.scale(k, scale_tips=True, about_point=ORIGIN)   # else its tip regrows
    else:
        mob.scale(k, about_point=ORIGIN)
    mob.shift(view_center(view) + np.asarray(shift, dtype=float))
    # each member's OWN stroke (family=False: a group's set_stroke would repeat the
    # multiplication down the whole tree), read before scaling touched anything
    for m, w in widths:
        m.set_stroke(width=w * k, family=False)
    return mob


def from_view(mob, view=VIEW_FULL, shift=ORIGIN):
    """`to_view`'s inverse: `mob`, placed in `view` (plus `shift`), back into the
    ordinary 16 x 9 frame, looking exactly as it did. Returns `mob`."""
    k = view_k(view)
    widths = _restroke(mob)
    mob.shift(-(view_center(view) + np.asarray(shift, dtype=float)))
    if isinstance(mob, Arrow):
        mob.scale(1 / k, scale_tips=True, about_point=ORIGIN)
    else:
        mob.scale(1 / k, about_point=ORIGIN)
    for m, w in widths:
        m.set_stroke(width=w / k, family=False)
    return mob


def _tick_level(t):
    return 10 if t % 10 == 0 else 5 if t % 5 == 0 else 1


def full_stacks(squash=SQUASH):
    """08's bars, every word placed, at `squash` (1e-3 x SQUASH to grow them up)."""
    s = WordStacks(DATA, origin=ORIGIN, origin_bin=BIN_LO, bar_color=BAR_COLOR)
    s.set_order(np.arange(len(DATA["words"])))
    s.set_state(n=len(DATA["words"]), squash=squash)
    return s


class HistogramChrome(VGroup):
    """The axis, the ticks visible at VIEW_FULL, the axis label and the title, placed
    by 08's `_place_overlay` rules for that view (08g onward: ticks labelled)."""

    def __init__(self, view=VIEW_FULL, axis_lo=AXIS_LO, axis_hi=AXIS_HI):
        """`view` and the axis range default to 08's; scene 19 passes its wider pair
        (full_view(axis_hi=...)) and gets the same chrome over the longer axis."""
        super().__init__()
        LEFT, BOTTOM, WIDTH, _ = view
        k, h = view_k(view), WIDTH / ASPECT
        self.axis = Line([x_of(axis_lo), 0, 0], [x_of(axis_hi), 0, 0], color=WHITE,
                         stroke_width=AXIS_STROKE * k)
        self.ticks = VGroup()
        lab_h = 0.0
        for t in range(round(axis_lo * 100), round(axis_hi * 100) + 1):
            spacing = _tick_level(t) * PITCH / WIDTH
            op = float(np.clip((spacing - TICK_OFF) / (TICK_ON - TICK_OFF), 0, 1))
            if op <= 0:
                continue
            x = x_of(t / 100)
            mark = Line([x, 0, 0], [x, -TICK_LEN * k, 0], color=WHITE,
                        stroke_width=AXIS_STROKE * k, stroke_opacity=op)
            lab = crisp_text(f"{t / 100:.2f}", color=WHITE, font_size=FONT_SIZE_SM)
            lab.scale(k).move_to([x, -(TICK_LEN + TICK_GAP) * k - lab.height / 2, 0])
            lab.set_opacity(op)
            lab_h = lab.height
            self.ticks.add(VGroup(mark, lab))
        self.xlabel = crisp_text("Average Guesses", color=WHITE, font_size=FONT_SIZE_SM)
        self.xlabel.scale(k)
        cx = float(np.clip(LEFT + WIDTH / 2, x_of(axis_lo) + self.xlabel.width / 2,
                           x_of(axis_hi) - self.xlabel.width / 2))
        self.xlabel.move_to([cx, -(TICK_LEN + TICK_GAP + XLABEL_GAP) * k - lab_h
                             - self.xlabel.height / 2, 0])
        self.heading = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG).scale(k)
        stat_room = crisp_text("Answer", font_size=FONT_SIZE_SM).height + STAT_LINE_BUFF
        top = BOTTOM + STAT_TOP * h + (stat_room + TITLE_BUFF) * k
        self.heading.move_to([LEFT + WIDTH / 2, top + self.heading.height / 2, 0])
        self.add(self.axis, self.ticks, self.xlabel, self.heading)


def layer_bars(counts, color):
    """A sub-histogram LAYER: one bar per histogram bar, `counts[i]` words tall (the
    words of bar i meeting the condition), drawn over the full bars on the same
    baseline and scale — so a layer can never stand taller than its bar."""
    bar_x = (np.unique(DATA["bins"]) - BIN_LO) * PITCH
    g = VGroup()
    for x, n in zip(bar_x, counts):
        h = max(n, 1e-3) * STEP * SQUASH
        r = Rectangle(width=WORD_W, height=h, stroke_width=0, fill_color=color,
                      fill_opacity=1.0 if n > 0 else 0.0)
        r.move_to([x, h / 2, 0])
        g.add(r)
    return g
