"""Scene 20 — a career in calendars, for the 80,000 Hours sponsor read (the script's
unlabelled row 34, VO: "40 years ... 50 weeks a year ... 40 hours a week"). Light
blue background. Promoted from test scene 96; scenes 21-22 are the read's browser
pages.

40 years -> 2000 working weeks -> 80,000 hours, in yahtzee 03dice's "grow" style:
every parent is split into copies of itself, and each copy flies out and becomes
one of its children, so the same full-frame box just keeps subdividing.

BEAT MAP
  a years  — 40 year calendars fade in, a 5x8 grid (rows x cols)
  b weeks  — each year splits into 50 weekly calendars (5 rows x 10 cols in its
             cell); a week is a header strip + 5 day rows
  c hours  — each day row splits into 8 hour dots; a week's 40 dots sit 8 rows x
             5 cols, one COLUMN per day

LEDGER — both splits are yahtzee 03dice `_grow` (run 0.8); the ORDER differs:
  ORDER: a 45-degree sweep from the top-left in all three subscenes, by SCREEN
  position (x - y), so the front is 45 degrees whatever the grid's aspect
  (`_diagonal`; by year in a, by week in b and c).
  b: EVERY week (1-50) starts as a full, visible copy of its year stacked on
     it; each copy slides to its slot turning into its week on the way (page ->
     5 day rows, header -> header, month boxes shrink onto the week and fade).
  c: per week, each day row copied 8 times Transforms into that day's column
     of 8 dots (day d -> column d);
     the week header fades alongside. One item per week, same lag/run as b.

REUSE MAP
  grow motion      -> yahtzee 03dice `_grow` (run 0.8), diagonal order
  nested layout    -> yahtzee 03dice `_cluster_centers` (full-frame box that
                      subdivides; here with absolute gaps, since each level's
                      split shape differs)
  colours          -> style.py CARD_FILL (paper), ACCENT_FILL (header / ink)
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *


# ── layout ─────────────────────────────────────────────────────────────────────
_BOX_W, _BOX_H = 15.6, 8.6
# (rows, cols, gap) per level, outermost first: years, weeks-in-a-year,
# hours-in-a-week (8 rows x 5 cols: one column of 8 hours per day).
_YEAR_SPLIT = (5, 8, 0.22)
_WEEK_SPLIT = (5, 10, 0.015)
_HOUR_SPLIT = (8, 5, 0.0)

_HEADER_FRAC = 0.2      # header strip height as a fraction of its calendar
_WEEK_ROW_GAP = 0.006   # gap between a week's day rows
_DOT_FRAC = 0.8         # hour-dot diameter as a fraction of its cell's short side


def _split(cx, cy, w, h, shape):
    """Cell centres + cell size for a (rows, cols, gap) split of a box, reading
    order (left to right, then top to bottom)."""
    r, c, g = shape
    cw, ch = (w - (c - 1) * g) / c, (h - (r - 1) * g) / r
    centers = []
    for i in range(r * c):
        rr, cc = divmod(i, c)
        centers.append((cx + (cc - (c - 1) / 2) * (cw + g),
                        cy + ((r - 1) / 2 - rr) * (ch + g)))
    return centers, cw, ch


def _year(cx, cy, w, h):
    """A wall-calendar icon: paper body, blue header, 3x4 faint month boxes."""
    r = min(w, h) * 0.08
    body = RoundedRectangle(width=w, height=h, corner_radius=r,
                            fill_color=CARD_FILL, fill_opacity=1.0, stroke_width=0)
    hh = h * _HEADER_FRAC
    # rounded TOP corners only, matching the page. NB manim's radius list is offset
    # by one vertex (entry i rounds vertex i+1; vertices run UR, UL, DL, DR), so
    # [r, 0, 0, r] rounds UL and UR. Checked against the points, not assumed.
    header = RoundedRectangle(width=w, height=hh, corner_radius=[r, 0, 0, r],
                              fill_color=ACCENT_FILL, fill_opacity=1.0,
                              stroke_width=0)
    body.move_to([cx, cy, 0])
    header.move_to([cx, cy + (h - hh) / 2, 0])
    mcent, mw, mh = _split(cx, cy - hh / 2, w * 0.86, (h - hh) * 0.84,
                           (3, 4, min(w, h) * 0.05))
    months = VGroup(*[Rectangle(width=mw, height=mh, fill_color=ACCENT_FILL,
                                fill_opacity=0.18, stroke_width=0).move_to([x, y, 0])
                      for x, y in mcent])
    g = VGroup(body, header, months)
    g.body, g.header, g.months = body, header, months
    return g


def _week(cx, cy, w, h):
    """A weekly-planner icon: a blue header strip over 5 paper day rows."""
    hh = h * _HEADER_FRAC
    header = Rectangle(width=w, height=hh, fill_color=ACCENT_FILL, fill_opacity=1.0,
                       stroke_width=0).move_to([cx, cy + (h - hh) / 2, 0])
    rh = (h - hh - 5 * _WEEK_ROW_GAP) / 5
    top = cy + h / 2 - hh - _WEEK_ROW_GAP
    rows = VGroup(*[Rectangle(width=w, height=rh, fill_color=CARD_FILL,
                              fill_opacity=1.0, stroke_width=0)
                    .move_to([cx, top - rh / 2 - d * (rh + _WEEK_ROW_GAP), 0])
                    for d in range(5)])
    g = VGroup(header, rows)
    g.header, g.rows = header, rows
    return g


def _hours(cx, cy, w, h):
    """A week's 40 hours: 8 rows x 5 cols of dots (a column per day), filling
    the week's cell, in reading order."""
    cent, cw, ch = _split(cx, cy, w, h, _HOUR_SPLIT)
    rad = min(cw, ch) * _DOT_FRAC / 2
    return VGroup(*[Dot([x, y, 0], radius=rad, color=CARD_FILL) for x, y in cent])


def _layout():
    """(year cells, week cells per year) — all centres + sizes, lex order."""
    ycent, yw, yh = _split(0.0, 0.0, _BOX_W, _BOX_H, _YEAR_SPLIT)
    weeks = [_split(x, y, yw, yh, _WEEK_SPLIT) for x, y in ycent]
    return (ycent, yw, yh), weeks


def _pitch(shape, cw, ch):
    """The smaller centre-to-centre spacing of a (rows, cols, gap) grid of
    cw x ch cells — the diagonal's step size."""
    return min(cw, ch) + shape[2]


def _diagonal(anims_xy, step, item_frac):
    """A 45-degree sweep from the top-left, by SCREEN position: animations are
    keyed on x - y (a true 45-degree line whatever the grid's aspect ratio),
    binned to `step`, and every bin starts together. Distance along the
    diagonal maps linearly to start time (an empty bin is a Wait), so the
    front moves at a steady speed. `item_frac` is each bin's share of the
    run_time, so every item's own move keeps the same length."""
    keyed = [(anim, round((x - y) / step)) for anim, x, y in anims_xy]
    lo = min(k for _, k in keyed)
    bins = [[] for _ in range(max(k for _, k in keyed) - lo + 1)]
    for anim, k in keyed:
        bins[k - lo].append(anim)
    n = len(bins)
    lag = (1 / item_frac - 1) / (n - 1) if n > 1 else 0.0
    return LaggedStart(*[AnimationGroup(*b) if b else Wait() for b in bins],
                       lag_ratio=lag)


class Scene20(WordleScene):
    def setup_scene(self):
        pass

    def _setup_years(self):
        (ycent, yw, yh), _ = _layout()
        self.years = [_year(x, y, yw, yh) for x, y in ycent]

    def _setup_weeks(self):
        _, weeks = _layout()
        self.weeks = [[_week(x, y, ww, wh) for x, y in cent]
                      for cent, ww, wh in weeks]

    def _setup_hours(self):
        _, weeks = _layout()
        self.hours = [[_hours(x, y, ww, wh) for x, y in cent]
                      for cent, ww, wh in weeks]

    # a : 40 year calendars
    @subscene
    def years(self):
        self._setup_years()
        # 45-degree sweep; item_frac 0.39 keeps each year's fade as long as under
        # the old 40-item stagger (1 / (1 + 39 x 0.04))
        (_, yw, yh), _ = _layout()
        self.play(_diagonal([(FadeIn(y, scale=0.9), *y.get_center()[:2])
                             for y in self.years],
                            step=_pitch(_YEAR_SPLIT, yw, yh), item_frac=0.39),
                  run_time=2.0)

    # b : each year splits into 50 weekly calendars
    @subscene
    def weeks(self):
        # yahtzee 03dice `_grow`: EVERY child starts as a full, visible copy of
        # its parent stacked on it, and all of them slide out at once. Here each
        # of a year's 50 weeks starts as a copy of the year and turns into its
        # week on the way.
        self._setup_weeks()
        # remove the parents BEFORE adding their copies' pieces: adding a
        # submobject of an on-screen group makes manim split that group and keep
        # its OTHER pieces on screen until the end, where they snap away.
        self.remove(*self.years)
        items = [(self._year_copy_into_week(year, week), *week.get_center()[:2])
                 for year, wk in zip(self.years, self.weeks) for week in wk]
        # 45-degree sweep; item_frac 0.2 keeps each week's move as long as under
        # `_grow`'s 0.002 over 2000 items (1 / (1 + 1999 x 0.002))
        self.play(_diagonal(items, step=self._week_pitch(), item_frac=0.2),
                  run_time=0.8)
        self._only(*[w for wk in self.weeks for w in wk])
        self.years = None                       # consumed

    def _year_copy_into_week(self, year, week):
        """One visible copy of `year`, turning into `week` as it travels: page ->
        the 5 day rows, header -> header, month boxes shrink onto the week and
        fade. Added page, months, header in that order, so each copy's header
        sits on top of its OWN page (never over every page)."""
        rows = VGroup(*[year.body.copy() for _ in range(5)])
        months = year.months.copy()
        header = year.header.copy()
        self.add(rows, months, header)
        ghost = months.copy().stretch_to_fit_width(week.width) \
            .stretch_to_fit_height(week.height).move_to(week).set_opacity(0.0)
        return AnimationGroup(Transform(rows, week.rows),
                              Transform(months, ghost),
                              Transform(header, week.header))

    def _week_pitch(self):
        _, weeks = _layout()
        _, ww, wh = weeks[0]
        return _pitch(_WEEK_SPLIT, ww, wh)

    def _only(self, *mobs):
        """Hard-clear, then keep just `mobs` — drops the spent seeds and the
        faded-out pieces so nothing lingers invisibly into the next subscene."""
        for m in list(self.mobjects):
            self.remove(m)
        self.add(*mobs)

    # c : each day row splits into 8 hour dots
    @subscene
    def hours(self):
        # the ORIGINAL c mechanism (user liked it): each day row is copied 8
        # times and the copies shrink into that DAY'S COLUMN of 8 dots; the week header
        # fades alongside.
        self._setup_hours()
        self.remove(*[w for wk in self.weeks for w in wk])   # before adding pieces
        items = []
        for wk, hr in zip(self.weeks, self.hours):
            for week, dots in zip(wk, hr):
                seed = VGroup(*[row.copy() for row in week.rows for _ in range(8)])
                self.add(seed, week.header)
                # seed runs day by day; order the dots to match: column d top->bottom
                by_day = VGroup(*[dots[r * 5 + d] for d in range(5) for r in range(8)])
                items.append((AnimationGroup(Transform(seed, by_day),
                                             FadeOut(week.header)),
                              *week.get_center()[:2]))
        # same diagonal sweep as b, by week
        self.play(_diagonal(items, step=self._week_pitch(), item_frac=0.2),
                  run_time=0.8)
        self._only(*[d for hr in self.hours for d in hr])
        self.weeks = None                       # consumed
