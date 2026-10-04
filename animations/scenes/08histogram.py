"""Scene 08 — the histogram of every opener's average guesses, and what sits where on
it. Navy background (07 is navy, and 07 runs straight into 08).

The same 12972 openers in the same 0.01 bins as scene 01, drawn as a PLAIN LIGHT-BLUE
BAR CHART (user's call, 2026-09-29): every bar is secretly a stack of one slice per
word, with no gaps, so a single word — SALET at the bottom of the left bar — can be
highlighted by dimming the rest, and a set of words (always the bottom of each bar,
since each bar is sorted) as a lit LEVEL that rises and falls continuously.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_histogram — the bars grow up from the axis, the title fades in      (08a, VO 1)
  b salet          — zoom in on the left; then at once everything but SALET's
                     slice dims and SALET (large) grows out of its line       (08b, VO 1)
  c salet_label    — "3.42 guesses" under SALET                              (08c, VO 1)
  d tarse          — all at once: a little faded bar grows down below the axis
                     under SALET's, and TARSE pops out of a line from it      (08d, VO 2)
  e tarse_gloss    — "n. A" and a blurred word under TARSE                    (08e, VO 2)
  f slate          — as SALET in b, all at once: SLATE's slice lights up and
                     SLATE (as large as SALET) grows out of its line          (08f, VO 3)
  g label_axis     — SLATE (and its slice's highlight) and all of TARSE fade;
                     then tick labels and "Average Guesses" fade in           (08g, VO 4)
  h within_01      — the lit level rises to the words within 0.01 of SALET;
                     "3.42 guesses" fades                                     (08h, VO 5)
  i within_1       — zoom out to cover 0.1 guesses, the level rising to the
                     1480 within 0.1; SALET's callout moves and shrinks       (08i, VO 5)
  j within_2       — zoom all the way out, the level rising to the 6908
                     within 0.2; SALET still called out                       (08j, VO 5)
  k top_1000       — the level falls to the top 1000; SALET fades             (08k, VO 6)
  l unhighlight    — the level rises to the top of every bar                  (08l, VO 6)
  m qajaq          — QAJAQ with its line                                      (08m, VO 7)
  n popular        — QAJAQ fades; TRACE straight up over its bar, then ROATE,
                     ARISE, RAISE stepping diagonally down from it            (08n, VO 8)
  o nyt            — all four fade quickly; CRANE straight up, then STARE,
                     TRAIN, IRATE stepping diagonally down                    (08o, VO 8)
  p adieu          — the others fade quickly; ADIEU with its line            (08p, VO 9)
  q audio          — AUDIO with its line                                      (08q, VO 9)
  r stats_all      — vertical lines at the average and the median of all
                     openers, labelled                                        (08r, VO 10)
  s stats_answers  — the lines and their labels MOVE to the answer words'
                     figures; "Answer" fades in above each label, riding
                     along with it                                           (08s, VO 11)

REUSE MAP — every element and the one source it comes from:
  the bars          assets/word_stacks.py WordStacks in BAR MODE + StacksCamera — 01's
                    stacks, one slice per word
  camera, emphasis, assets/stacks_view.py StacksView — 01's machinery (_move_view,
  callouts, sounds  dim-the-rest at 0.2, callouts growing out of a white line, a ping
                    per callout and a whoosh per camera move), extracted from 01
  lit level         WordStacks `level` + _move_view(level=...): a full-strength bar
                    over each dimmed one, its height moving continuously (rate_func
                    smooth), as bar_graph.grow_bars grows bars — not 01's per-word steps
  callout words     assets/board.py get_typed_row — a typed, unscored row, as 06/07's
                    revealed words look
  TARSE's pop       the callouts' growth: its line draws while the word grows from
                    the line's end (GrowFromPoint about the anchor is the same motion)
  "3.42 guesses"    01's label: crisp_text, white, 40, FadeIn with a small rise
  the definition    assets/gloss.py gloss (the italic "n." every definition has), at
                    the label's size
  blurred word      one soft glow, no solid core: faint rounded rectangles building up
                    toward the middle, centred on the A's height (_blur_box);
                    white and navy mixed (user's call)
  axis labels       crisp_text at FONT_SIZE_SM, as get_histogram's ticks and axis label
  title             get_histogram's: FONT_SIZE_LG, TITLE_BUFF (0.5) above the plot
  every number      assets/histogram_data.py -> histogram_cache.json: the committed
                    optturns sweep; the stats are opener_distribution.ipynb's figures
  colours           BOARD_NAVY via WordleBoardScene; bars BG_COLOR (the channel's
                    light blue); average ACCENT_GOLD, median WHITE

On-screen text beyond the words (all the user's calls): the title "Average Guesses by
Opening Word" (08a), "3.42 guesses" (08c), the definition (08e), the axis labels
(08g), and the line labels (08r/s). The VO's other numbers are not shown.

LAYOUT CHOICES, flagged:
  - Each VIEW has its own squash (01's technique): the 0.1 view would otherwise
    crop the tall bars, and the zoomed-in view would make SALET's slice a hairline.
    The y axis carries no numbers, so its scale is free. The zoomed-in view puts
    the axis higher (BASE_LEFT) so TARSE has room below it.
  - The TITLE sits get_histogram's 0.5 above the top of the plot, where the top of
    the plot is the room the stat lines and their two-line labels need (08r/s), so
    the title never moves. It stays at that height in every view.
  - Ticks THIN WITH ZOOM (user's call): every 0.01 up close, every 0.1 all the way
    out, each level fading by its on-screen spacing.
  - TARSE's bar is one slice tall and as wide as SALET's, at TARSE_OPACITY, as are
    TARSE and its line; its line leaves the bar's bottom-left corner so it clears
    the 3.42 tick that arrives in 08g. The definition is not faded.
  - 08l ends fully lit, and the dimming is then switched off with no visible change.
  - Callout words appear together when a beat names several; every callout pings,
    as in 01, so four at once ring as one louder ping. TARSE pings too.
  - "Show X with line" lights nothing: only the callout appears (dim is off from 08l).
    From 08m every line runs to the CENTRE of the word's slice (user's call), except
    ADIEU's and AUDIO's, which end at their EXACT value on the axis scale, so they
    read correctly against the average and median lines (user's call). In 08n/o the
    leftmost word stands straight up over its bar and the rest step diagonally down
    and right from it, over the bars (user's call).
  - A whole hundredth sits mid-gap between two bars (bin b is [b, b+1) hundredths),
    so the ticks and the vertical lines share one value-to-x scale.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import numpy as np
from manim import MovingCameraScene

from config import *
from assets import histogram_data
from assets.board import STROKE, get_typed_row
from assets.gloss import gloss
from assets.word_stacks import WordStacks, StacksCamera, PITCH, STEP, WORD_W
from assets.stacks_view import (StacksView, pinned, ASPECT, FRAME_W, LINE_STROKE,
                                CALLOUT_GROW, PING_SFX, PING_GAIN)

DATA = histogram_data.load()
IDX = {w: i for i, w in enumerate(DATA["words"])}
BIN_LO, BIN_HI = min(DATA["bins"]), max(DATA["bins"])
TALLEST = max(DATA["rows"]) + 1
FRAME_H = FRAME_W / ASPECT

BAR_COLOR = BG_COLOR          # "default light blue" — the channel's light blue
BASE_FRAC = 0.14              # the baseline sits this far up the frame (i-s)
BASE_LEFT = 0.45              # ... and this far up while zoomed in (b-h), for TARSE
TOP_FRAC = 0.70               # the tallest bar in a view reaches this far up
STAT_TOP = 0.74               # r, s: the vertical lines rise to this far up
TITLE = "Average Guesses by Opening Word"
TITLE_BUFF = 0.5              # get_histogram's gap under its title (16-wide units)
AXIS_LO, AXIS_HI = 3.40, 4.12 # the axis line and its ticks run over these values
AXIS_STROKE = 3.0             # as it would be in a 16-wide frame
TICK_LEN = 0.12               # tick mark, in 16-wide-frame units
TICK_GAP = 0.08               # tick mark to its label
XLABEL_GAP = 0.15             # tick labels to the axis label
TICK_ON, TICK_OFF = 0.08, 0.07  # a tick level shows fully when its labels are this
                              # far apart (fraction of frame width), and not at all
                              # below TICK_OFF
LEFT_ROOM = 6.5               # b-h: frame room left of SALET's bar, for the notes
LEFT_SQUASH = 0.35            # b-h: a slice's height in the zoomed-in view
BIG_W = 0.25                  # SALET and TARSE, as a fraction of the frame width —
                              # wide enough that "3.42 guesses" fits under SALET
MID_W = 0.16                  # SALET once the view zooms out (i, j)
LABEL_FS = 40                 # "3.42 guesses" and the definition — 01's label size
LABEL_BUFF = 0.2              # their gap under SALET / TARSE
TARSE_OPACITY = 0.6           # "slightly faded"
TARSE_AT = (0.36, 0.22)       # TARSE's right edge, as frame fractions (zoomed in)
BLUR_WHITE = 0.25             # the blurred word: the navy background with this much
BLUR_INK = interpolate_color(BOARD_NAVY, WHITE, BLUR_WHITE)   # white mixed in (user's call)
BLUR_OUT, BLUR_IN = 1.3, 0.3  # the glow: its outermost and innermost layers, as a
                              # fraction of the A's height
BLUR_LAYERS = 16              # this many faint layers between them,
BLUR_OP = 0.14                # each this opaque (they build up toward the middle)
BLUR_RADIUS = 0.45            # corner radius, as a fraction of each layer's height
DIAG_Y = 0.62                 # n, o: the first word's bottom, as a frame fraction
DIAG_STEP = (0.13, 0.09)      # n, o: each next word this far right and down
STAT_STROKE = 4.0             # as it would be in a 16-wide frame
STAT_LABEL_BUFF = 0.12        # a line label's gap to its line (16-wide units)
STAT_LINE_BUFF = 0.08         # "Answer" above its label (16-wide units)


def x_of(v):
    """x of average-guess value v — WordStacks.x_of_value for origin (0, 0) at BIN_LO."""
    return (v * 100 - 0.5 - BIN_LO) * PITCH


HIST_L = -WORD_W / 2


def _value(word):
    """`word`'s exact average guesses (its total over the answers)."""
    return DATA["totals"][IDX[word]] / histogram_data.N_ANSWERS


def _view(left, right, tall_rows):
    """A view from `left` to `right` whose tallest bar (`tall_rows` words) reaches
    TOP_FRAC, the baseline at BASE_FRAC."""
    w = right - left
    h = w / ASPECT
    return (left, -BASE_FRAC * h, w, (TOP_FRAC - BASE_FRAC) * h / (tall_rows * STEP))


def _rows_upto(b):
    return max(r for r, bb in zip(DATA["rows"], DATA["bins"]) if bb <= b) + 1


# b-h: SALET's bar and the next, with room on the left for the notes
VIEW_LEFT = (HIST_L - LEFT_ROOM, -BASE_LEFT * FRAME_H, FRAME_W, LEFT_SQUASH)
# i: every bar holding a word within 0.1, a 5% margin each side
_B_TENTH = max(DATA["bins"][IDX[w]] for w in DATA["within"]["0.1"])
_T_SPAN = (_B_TENTH - BIN_LO) * PITCH + WORD_W
VIEW_TENTH = _view(HIST_L - 0.05 * _T_SPAN / 0.9, HIST_L + _T_SPAN + 0.05 * _T_SPAN / 0.9,
                   _rows_upto(_B_TENTH))
# a, j-s: the whole axis, a 4% margin each side (2% clipped the end tick labels)
_F_SPAN = x_of(AXIS_HI) - x_of(AXIS_LO)
VIEW_FULL = _view(x_of(AXIS_LO) - 0.04 * _F_SPAN / 0.92,
                  x_of(AXIS_HI) + 0.04 * _F_SPAN / 0.92, TALLEST)

def _diagonal(words):
    """n, o: the first word straight up above its own bar, DIAG_Y up the frame; each
    next one DIAG_STEP right and down of the last (over the bars is fine)."""
    left, _, w, _ = VIEW_FULL
    fx = ((DATA["bins"][IDX[words[0]]] - BIN_LO) * PITCH - left) / w
    return {wd: pinned(fx + i * DIAG_STEP[0], DIAG_Y - i * DIAG_STEP[1], "bottom",
                       "center")
            for i, wd in enumerate(words)}


# CALLOUTS pinned in the frame (see assets/stacks_view.py `pinned`). SALET and SLATE
# are placed for VIEW_LEFT, with SALET gliding to SALET_TENTH / SALET_FULL as i and j
# zoom out; the rest are placed for VIEW_FULL, their lines to the slice's centre.
CALLOUTS = {
    "salet": pinned(0.36, 0.60, "right", w=BIG_W),
    "slate": pinned(0.36, 0.77, "right", w=BIG_W),
    "qajaq": pinned(0.88, 0.30, "bottom", "center"),
    **_diagonal(["trace", "roate", "arise", "raise"]),        # n
    **_diagonal(["crane", "stare", "train", "irate"]),        # o
    "adieu": pinned(0.46, 0.66, "left", "center", x=x_of(_value("adieu"))),
    "audio": pinned(0.50, 0.42, "left", "center", x=x_of(_value("audio"))),
}
SALET_TENTH = pinned(0.16, 0.50, "bottom", w=MID_W)
SALET_FULL = pinned(0.12, 0.60, "bottom", w=MID_W)


def _tick_level(t):
    """A tick at t hundredths belongs to the 0.1, 0.05 or 0.01 level."""
    return 10 if t % 10 == 0 else 5 if t % 5 == 0 else 1


def _blur_box(w, h):
    """The blurred word as ONE SOFT GLOW, no solid core: BLUR_LAYERS faint rounded
    rectangles, from BLUR_OUT x the A's height `h` (and the hidden word's width `w`)
    down to BLUR_IN x, all centred, so they build up smoothly toward the middle and
    fade to nothing at the rim. The visible glow is about the A's height."""
    out = VGroup()
    for i in range(BLUR_LAYERS):
        t = i / (BLUR_LAYERS - 1)                     # 0 outermost .. 1 innermost
        k = BLUR_OUT + (BLUR_IN - BLUR_OUT) * t
        bh = h * k
        bw = w - h * (1 - k)                          # the same inset on every side
        out.add(RoundedRectangle(width=bw, height=bh, corner_radius=BLUR_RADIUS * bh,
                                 stroke_width=0, fill_color=BLUR_INK,
                                 fill_opacity=BLUR_OP))
    return out


def _counts(words):
    """How many of `words` each bar holds — the lit level that shows exactly them,
    since each bar is sorted and every set here is a bottom run of it."""
    bins = np.array([DATA["bins"][IDX[w]] for w in words])
    ubins = np.unique(DATA["bins"])
    return np.array([np.sum(bins == b) for b in ubins], dtype=float)


class Scene08(StacksView, MovingCameraScene, WordleBoardScene):
    """BEAT MAP
    show_histogram — the bars grow up, the title fades in
    salet — zoom in on the left, SALET's slice lit, SALET with its line
    salet_label — "3.42 guesses" under SALET
    tarse — TARSE's bar below the axis; TARSE pops out of its line
    tarse_gloss — its definition, the last word blurred
    slate — SLATE lit, then SLATE with its line
    label_axis — tick labels and the axis label; SLATE and TARSE fade
    within_01 — the level rises to the 8 within 0.01; "3.42 guesses" fades
    within_1 — zoom out to 0.1 guesses, the level rises to 1480, SALET follows
    within_2 — zoom all the way out, the level rises to 6908, SALET follows
    top_1000 — the level falls to the top 1000; SALET fades
    unhighlight — the level rises to the top of every bar
    qajaq — QAJAQ with its line
    popular — QAJAQ fades; TRACE, ROATE, ARISE, RAISE
    nyt — those fade; STARE, CRANE, TRAIN, IRATE
    adieu — those fade; ADIEU
    audio — AUDIO
    stats_all — average and median lines, all openers
    stats_answers — the lines move to the answer words' figures
    """

    def __init__(self, **kwargs):
        super().__init__(camera_class=StacksCamera, **kwargs)

    def setup_scene(self):
        self.view = VIEW_FULL
        self._set_frame(*VIEW_FULL[:3])
        self.callouts = []
        self.axis = self.ticks = self.xlabel = self.heading = None
        self.tick_alpha = ValueTracker(0.0)     # the axis labels fade in with this (g)

    # ── hooks for StacksView ──────────────────────────────────────────────────
    def _callout_row(self, word):
        return get_typed_row(word)

    def _callout_spec(self, word):
        return CALLOUTS.get(word)       # a module constant, so the digest sees edits

    def _callout_stroke(self, row, w):
        """A tile border in proportion to the row, as at its native width."""
        for t in row.tiles[0]:
            t.set_stroke(width=STROKE * row.width / WORD_W)

    def _place_overlay(self):
        """Everything sized in SCREEN terms: the axis, its labels, the title."""
        f = self.camera.frame
        left, bottom, w = f.get_left()[0], f.get_bottom()[1], f.width
        k = w / FRAME_W
        h = w / ASPECT
        if self.axis is not None:
            self.axis.set_stroke(width=AXIS_STROKE * k)
        if self.heading is not None:
            # get_histogram: TITLE_BUFF above the plot, whose top here is the room
            # the stat lines' two-line labels need
            self.heading.scale_to_fit_height(self.heading_h * k)
            top = bottom + STAT_TOP * h + (self.stat_room + TITLE_BUFF) * k
            self.heading.move_to([left + w / 2, top + self.heading.height / 2, 0])
        if self.ticks is not None:
            lab_h = 0.0
            for t, mark, lab, base_h in self.ticks:
                x = x_of(t / 100)
                spacing = _tick_level(t) * PITCH / w
                op = float(np.clip((spacing - TICK_OFF) / (TICK_ON - TICK_OFF), 0, 1))
                mark.put_start_and_end_on([x, 0, 0], [x, -TICK_LEN * k, 0])
                mark.set_stroke(width=AXIS_STROKE * k, opacity=op)
                lab.scale_to_fit_height(base_h * k)
                lab.move_to([x, -(TICK_LEN + TICK_GAP) * k - lab.height / 2, 0])
                op *= self.tick_alpha.get_value()
                mark.set_stroke(opacity=op)
                lab.set_opacity(op)
                lab_h = lab.height
            self.xlabel.scale_to_fit_height(self.xlabel_h * k)
            cx = float(np.clip(left + w / 2, x_of(AXIS_LO) + self.xlabel.width / 2,
                               x_of(AXIS_HI) - self.xlabel.width / 2))
            self.xlabel.move_to([cx, -(TICK_LEN + TICK_GAP + XLABEL_GAP) * k - lab_h
                                 - self.xlabel.height / 2, 0])
            self.xlabel.set_opacity(self.tick_alpha.get_value())

    def _at(self, fx, fy):
        """The point at (fx, fy) of the current view's frame."""
        left, bottom, w, _ = self.view
        return np.array([left + fx * w, bottom + fy * w / ASPECT, 0.0])

    def _callout_of(self, word):
        return next(c for c in self.callouts if c["word"] == word)

    # a : the bars grow up from the axis, the whole histogram in view; the title
    def _setup_show_histogram(self):
        self.stacks = WordStacks(DATA, origin=ORIGIN, origin_bin=BIN_LO,
                                 bar_color=BAR_COLOR)
        # every word is in from the start (01 lands them one by one; 08 does not)
        self.stacks.set_order(np.arange(len(DATA["words"])))
        self.stacks.set_state(n=len(DATA["words"]), squash=VIEW_FULL[3] * 1e-3)
        self.stacks.refresh(self.camera.frame)
        self.axis = Line([x_of(AXIS_LO), 0, 0], [x_of(AXIS_HI), 0, 0], color=WHITE)
        self.heading = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG)
        self.heading_h = self.heading.height
        # the room above the stat lines' tops that "Answer" will take (08s)
        probe = crisp_text("Answer", font_size=FONT_SIZE_SM)
        self.stat_room = probe.height + STAT_LINE_BUFF
        self._place_overlay()

    @subscene
    def show_histogram(self):
        self._setup_show_histogram()
        self.add(self.stacks)
        t = ValueTracker(1e-3)
        s_full = VIEW_FULL[3]

        def grow(m):
            m.set_state(squash=s_full * t.get_value())
            m.refresh(self.camera.frame)

        self.stacks.add_updater(grow)
        self.play(t.animate.set_value(1.0), FadeIn(self.axis), FadeIn(self.heading),
                  run_time=1.5)
        self.stacks.remove_updater(grow)
        self.remove(t)

    # b : zoom in on the left; SALET's slice lit; SALET grows out of its line
    @subscene
    def salet(self):
        self._move_view(VIEW_LEFT, run_time=2.5, whoosh=True)
        self._move_view(VIEW_LEFT, run_time=0.8, dim=1.0, weights={"salet": 1},
                        appear=["salet"])

    # c : "3.42 guesses" under SALET
    def _setup_salet_label(self):
        self.label = crisp_text(f"{DATA['labels'][IDX['salet']]} guesses", color=WHITE,
                                font_size=LABEL_FS)
        self.label.next_to(self._callout_of("salet")["row"], DOWN, buff=LABEL_BUFF)

    @subscene
    def salet_label(self):
        self._setup_salet_label()
        self.play(FadeIn(self.label, shift=UP * 0.2), run_time=1.0)

    # d : a little faded bar below the axis, under SALET's; TARSE pops out of a line
    #     from it, the way the callouts do
    def _setup_tarse(self):
        h = LEFT_SQUASH * STEP                             # one slice
        self.stub = Rectangle(width=WORD_W, height=h, stroke_width=0,
                              fill_color=BAR_COLOR, fill_opacity=TARSE_OPACITY)
        self.stub.move_to([0, -h / 2, 0])
        self.tarse = get_typed_row("tarse")
        self.tarse.scale_to_fit_width(BIG_W * FRAME_W)
        self._callout_stroke(self.tarse, FRAME_W)
        self.tarse.move_to(self._at(*TARSE_AT), aligned_edge=RIGHT)
        self.tarse.set_opacity(TARSE_OPACITY)
        self.t_anchor = self.stub.get_corner(DL)
        self.t_line = Line(self.t_anchor, self.tarse.get_right(), color=WHITE,
                           stroke_width=LINE_STROKE, stroke_opacity=TARSE_OPACITY)

    @subscene
    def tarse(self):
        self._setup_tarse()
        h = self.stub.height
        self.stub.stretch_to_fit_height(1e-3, about_edge=UP)     # grows DOWN, as a bar
        self.sfx(PING_SFX, gain=PING_GAIN)
        self.play(self.stub.animate.stretch_to_fit_height(h, about_edge=UP),
                  Create(self.t_line), GrowFromPoint(self.tarse, self.t_anchor),
                  run_time=0.5)

    # e : "n. A" and a blurred word under TARSE, formatted as "3.42 guesses"
    def _setup_tarse_gloss(self):
        line = gloss(["n. A penis"], LABEL_FS)[0]      # the shared definition style
        hidden = VGroup(*line.submobjects[-5:])          # "penis", never shown
        cap = line.submobjects[2]                        # "A": baseline to cap height
        self.blur = _blur_box(hidden.width, cap.height)
        self.blur.move_to([hidden.get_center()[0], cap.get_center()[1], 0])
        line.remove(*hidden.submobjects)
        self.gloss = VGroup(line, self.blur)
        self.gloss.next_to(self.tarse, DOWN, buff=LABEL_BUFF)

    @subscene
    def tarse_gloss(self):
        self._setup_tarse_gloss()
        self.play(FadeIn(self.gloss, shift=UP * 0.2), run_time=1.0)

    # f : SLATE's slice lights up; SLATE grows out of its line — SALET's two steps
    @subscene
    def slate(self):
        self._move_view(VIEW_LEFT, run_time=0.8, weights={"slate": 1},
                        appear=["slate"])

    def _setup_label_axis(self):
        self.ticks = []
        for t in range(round(AXIS_LO * 100), round(AXIS_HI * 100) + 1):
            lab = crisp_text(f"{t / 100:.2f}", color=WHITE, font_size=FONT_SIZE_SM)
            self.ticks.append((t, Line(ORIGIN, DOWN, color=WHITE), lab, lab.height))
        self.xlabel = crisp_text("Average Guesses", color=WHITE, font_size=FONT_SIZE_SM)
        self.xlabel_h = self.xlabel.height
        self._place_overlay()
        self.add(*[m for _, mark, lab, _ in self.ticks for m in (mark, lab)], self.xlabel)
        self.fading = [self.stub, self.t_line, self.tarse, self.gloss]

    # g : the axis labels fade in; SLATE (its slice too) and all of TARSE fade out
    @subscene
    def label_axis(self):
        self._setup_label_axis()
        self._move_view(VIEW_LEFT, run_time=0.8, weights={"slate": 0},
                        callout_alpha={"slate": 0.0},
                        extra=[FadeOut(m) for m in self.fading])
        self._drop_callouts(["slate"])
        self.remove(*self.fading)
        self.fading = self.stub = self.t_line = self.tarse = self.gloss = self.blur = None
        self._move_view(VIEW_LEFT, run_time=1.0,
                        extra=[self.tick_alpha.animate.set_value(1.0)])

    # h : the level rises to the words within 0.01 of SALET; "3.42 guesses" fades
    @subscene
    def within_01(self):
        self._move_view(VIEW_LEFT, run_time=1.0,
                        level=_counts(DATA["within"]["0.01"]),
                        extra=[FadeOut(self.label)])
        self.remove(self.label)
        self.label = None

    # i : zoom out to cover 0.1 guesses, the level rising to the 1480 within 0.1;
    #     SALET follows, smaller
    @subscene
    def within_1(self):
        self._move_view(VIEW_TENTH, run_time=3.0, whoosh=True,
                        level=_counts(DATA["within"]["0.1"]),
                        retarget={"salet": SALET_TENTH})

    # j : zoom all the way out, the level rising to the 6908 within 0.2; SALET follows
    @subscene
    def within_2(self):
        self._move_view(VIEW_FULL, run_time=3.0, whoosh=True,
                        level=_counts(DATA["within"]["0.2"]),
                        retarget={"salet": SALET_FULL})

    # k : the level falls to the top 1000; SALET fades
    @subscene
    def top_1000(self):
        self._move_view(VIEW_FULL, run_time=1.5, level=_counts(DATA["top"]),
                        callout_alpha={"salet": 0.0})
        self._drop_callouts(["salet"])

    # l : the level rises to the top of every bar; then the dimming is switched off,
    #     which changes nothing on screen
    @subscene
    def unhighlight(self):
        self._move_view(VIEW_FULL, run_time=1.5, level=_counts(DATA["words"]))
        self.stacks.set_state(dim=0.0, level=None,
                              weights={w: 0 for w in self.stacks.emphasised()})
        self.stacks.refresh(self.camera.frame)

    # m : QAJAQ with its line
    @subscene
    def qajaq(self):
        self._move_view(VIEW_FULL, run_time=0.8, appear=["qajaq"])

    # n : QAJAQ fades; TRACE, ROATE, ARISE, RAISE with their lines
    @subscene
    def popular(self):
        self._move_view(VIEW_FULL, run_time=0.8, callout_alpha={"qajaq": 0.0},
                        fade_time=CALLOUT_GROW,
                        appear=["trace", "roate", "arise", "raise"])
        self._drop_callouts(["qajaq"])

    # o : all four fade as STARE, CRANE, TRAIN, IRATE come in
    @subscene
    def nyt(self):
        gone = ["trace", "roate", "arise", "raise"]
        self._move_view(VIEW_FULL, run_time=0.8, callout_alpha={w: 0.0 for w in gone},
                        fade_time=CALLOUT_GROW,
                        appear=["crane", "stare", "train", "irate"])
        self._drop_callouts(gone)

    # p : those fade as ADIEU comes in
    @subscene
    def adieu(self):
        gone = ["stare", "crane", "train", "irate"]
        self._move_view(VIEW_FULL, run_time=0.8, callout_alpha={w: 0.0 for w in gone},
                        fade_time=CALLOUT_GROW, appear=["adieu"])
        self._drop_callouts(gone)

    # q : AUDIO with its line
    @subscene
    def audio(self):
        self._move_view(VIEW_FULL, run_time=0.8, appear=["audio"])

    # ── r, s: vertical lines at the average and the median ────────────────────
    def _stat_lines(self, key):
        """[(line, label, side, color)] — the median (white, label to its LEFT) and the
        average (gold, label to its RIGHT), rising from the axis to STAT_TOP, each
        label top-aligned with its line's top."""
        s = DATA["stats"][key]
        k = VIEW_FULL[2] / FRAME_W
        top = self._at(0, STAT_TOP)[1]
        out = []
        for v, color, text, side in [(s["median"], WHITE, "Median", LEFT),
                                     (s["mean"], ACCENT_GOLD, "Average", RIGHT)]:
            line = Line([x_of(v), 0, 0], [x_of(v), top, 0], color=color,
                        stroke_width=STAT_STROKE * k)
            lab = crisp_text(text, color=color, font_size=FONT_SIZE_SM).scale(k)
            lab.next_to(line.get_end(), side, buff=STAT_LABEL_BUFF * k)
            lab.align_to(line.get_end(), UP)
            out.append((line, lab, side, color))
        return out

    # r : average and median of all openers
    def _setup_stats_all(self):
        self.stats = self._stat_lines("all")

    @subscene
    def stats_all(self):
        self._setup_stats_all()
        self.play(*[Create(l) for l, _, _, _ in self.stats], run_time=1.0)
        self.play(*[FadeIn(t) for _, t, _, _ in self.stats], run_time=0.6)

    # s : the lines and their labels move to the answer words' figures; "Answer"
    #     fades in above each label, aligned on the side toward its line
    def _setup_stats_answers(self):
        k = VIEW_FULL[2] / FRAME_W
        self.moves, self.answers = [], []
        for (line, lab, side, color), (nl, nlab, _, _) in zip(self.stats,
                                                               self._stat_lines("answers")):
            self.moves += [Transform(line, nl), lab.animate.move_to(nlab)]
            ans = crisp_text("Answer", color=color,
                             font_size=FONT_SIZE_SM).scale(k)
            ans.next_to(nlab, UP, buff=STAT_LINE_BUFF * k)
            ans.align_to(nlab, -side)                 # the edge nearest the line
            # it fades in riding on its word: from above the word's old place
            self.answers.append((ans, nlab.get_center() - lab.get_center()))

    @subscene
    def stats_answers(self):
        self._setup_stats_answers()
        self.play(*self.moves, *[FadeIn(a, shift=d) for a, d in self.answers],
                  run_time=1.2)
        self.moves = None
