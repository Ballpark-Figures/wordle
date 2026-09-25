"""TEST — a career in calendars, for the 80,000 Hours ad read. Not a content scene.

40 years -> 2000 working weeks -> 80,000 hours, in yahtzee 03dice's "grow" style:
every parent is split into copies of itself, and each copy flies out and becomes
one of its children, so the same full-frame box just keeps subdividing.

BEAT MAP
  a years  — 40 year calendars fade in, a 5x8 grid (rows x cols)
  b weeks  — each year splits into 50 weekly calendars (5 rows x 10 cols in its
             cell); a week is a header strip + 5 day rows
  c hours  — each day row splits into 8 hour dots (a week -> 5 x 8 = 40 dots)

LEDGER — both splits are yahtzee 03dice `_grow`, same lag (0.002) and run (0.8):
  one LaggedStart item per CHILD, in lex order (parent-major).
  b: EVERY week (1-50) starts as a full, visible copy of its year stacked on
     it; each copy slides to its slot turning into its week on the way (page ->
     5 day rows, header -> header, month boxes shrink onto the week and fade).
  c: per week, each day row copied 8 times Transforms into that row's 8 dots;
     the week header fades alongside. One item per week, same lag/run as b.

REUSE MAP
  grow motion      -> yahtzee 03dice `_grow` (lag 0.002, run 0.8, lex order)
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
# hours-in-a-week (a week's hours are 5 day rows of 8).
_YEAR_SPLIT = (5, 8, 0.22)
_WEEK_SPLIT = (5, 10, 0.015)
_HOUR_SPLIT = (5, 8, 0.0)

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
    """A week's 40 hours: 5 day rows of 8 dots, filling the week's cell."""
    cent, cw, ch = _split(cx, cy, w, h, _HOUR_SPLIT)
    rad = min(cw, ch) * _DOT_FRAC / 2
    return VGroup(*[Dot([x, y, 0], radius=rad, color=CARD_FILL) for x, y in cent])


def _layout():
    """(year cells, week cells per year) — all centres + sizes, lex order."""
    ycent, yw, yh = _split(0.0, 0.0, _BOX_W, _BOX_H, _YEAR_SPLIT)
    weeks = [_split(x, y, yw, yh, _WEEK_SPLIT) for x, y in ycent]
    return (ycent, yw, yh), weeks


class Scene96(WordleScene):
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
        self.play(LaggedStart(*[FadeIn(y, scale=0.9) for y in self.years],
                              lag_ratio=0.04), run_time=2.0)

    # b : each year splits into 50 weekly calendars
    @subscene
    def weeks(self):
        # yahtzee 03dice `_grow`: EVERY child starts as a full, visible copy of
        # its parent stacked on it, and all of them slide out at once. Here each
        # of a year's 50 weeks starts as a copy of the year and turns into its
        # week on the way. One LaggedStart item per child, lex order, same lag
        # and run as `_grow`.
        self._setup_weeks()
        # remove the parents BEFORE adding their copies' pieces: adding a
        # submobject of an on-screen group makes manim split that group and keep
        # its OTHER pieces on screen until the end, where they snap away.
        self.remove(*self.years)
        items = [self._year_copy_into_week(year, week)
                 for year, wk in zip(self.years, self.weeks) for week in wk]
        self.play(LaggedStart(*items, lag_ratio=0.002), run_time=0.8)
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
        # times and the copies shrink into that row's 8 dots; the week header
        # fades alongside. One LaggedStart item per week, with b's stagger.
        self._setup_hours()
        self.remove(*[w for wk in self.weeks for w in wk])   # before adding pieces
        items = []
        for wk, hr in zip(self.weeks, self.hours):
            for week, dots in zip(wk, hr):
                seed = VGroup(*[row.copy() for row in week.rows for _ in range(8)])
                self.add(seed, week.header)
                items.append(AnimationGroup(Transform(seed, dots),
                                            FadeOut(week.header)))
        self.play(LaggedStart(*items, lag_ratio=0.002), run_time=0.8)
        self._only(*[d for hr in self.hours for d in hr])
        self.weeks = None                       # consumed
