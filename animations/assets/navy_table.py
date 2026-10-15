"""THE MAIN VIDEO'S TABLE LOOK, as one function — for stills that need a table
(the bonus video's above all), so a new table matches the video's without being
re-derived.

    tab = navy_table(["Word Length", "Average Guesses"], [["5", "3.42"], ...],
                     title="Average Guesses by Word Length")
    self.add(tab)

Scenes 10, 14 and 19 each lay their table out by hand around their own content
(tiles, aligned decimals, the strategy line). Their SHARED convention is collected
here, every value from those scenes; the scenes themselves are shipped and left
alone:

  no card, no rule under the header, on the navy
  title    WHITE, FONT_SIZE_LG, TITLE_BUFF (0.6) from the top     13/14/18/19
  headers  WHITE BOLD, HEADER_SIZE 28                            10 (14, 19 cite it)
  cells    WHITE, CELL_SIZE 30, centred on their column          10
           (on a shared BASELINE, not box-centred: the scenes
           box-centre, which lifts "Opener" and "7,920" off the
           row; the shared rule for text on one line wins)
  decimals a column holding decimals lines up on the point,
           the block centred on its column                       14 (`_cell`)
  rows     ROW_DY 0.72 apart, the first HEAD_GAP 0.85 under
           the header                                            10 (3.4 head, 2.55 row 1)
  stripes  bpkfigures.table.row_stripes (white at 0.07) on every
           other body row, the first bare, overhanging STRIPE_PAD 0.5   14, 19

The scenes placed each column by hand, so the one thing NOT from a scene is
COL_GAP, the space between neighbouring columns' widest entries: an automatic
layout needs some value. The block of header + rows is centred in the space between
the title and an optional one-line `note` at the bottom (a footnote, e.g. what a *
means), and only the BLOCK shrinks to fit, so the title and note keep their places. Cells are shown as given, so formatting
is the caller's and the numbers are SOURCED.

Role handles: `.title` / `.note` (None without one), `.header`, `.rows`, `.cells[r][c]`,
`.stripes`.
"""
import re

from manim import *

from bpkfigures.style import FONT_SIZE_LG, crisp_text, place_on_baseline
from bpkfigures.table import row_stripes

TITLE_BUFF = 0.6        # 13's / 14's / 18's / 19's screen titles
HEADER_SIZE = 28        # scene 10's
CELL_SIZE = 30          # scene 10's
ROW_DY = 0.72           # scene 10's row pitch
HEAD_GAP = 0.85         # scene 10: header centre 3.4, first row 2.55
STRIPE_PAD = 0.5        # 14's / 19's overhang past the outer columns
COL_GAP = 1.0           # NOT from a scene (they placed columns by hand)
TITLE_GAP = 0.15        # 14's, between a two-line title's lines
BLOCK_GAP = 0.6         # title bottom to the header, at least
NOTE_SIZE = 24          # a footnote under the table (no main-video precedent)
NOTE_GAP = 0.4          # the table's bottom to the note's top, at least

_DECIMAL = re.compile(r"^[+\-−]?[\d,]*\.\d+%?$")


def _text(s, size, **kw):
    return crisp_text(s or " ", font_size=size, color=WHITE, **kw)


def _sit(mob, s, x, y, size):
    """Put `mob` on its row by its TEXT BASELINE, with the row's visual middle (half
    the cap height above the baseline) at y, so words with descenders and numbers
    with commas share one line (the shared baseline rule)."""
    cap = crisp_text("H", font_size=size).height
    return place_on_baseline(mob, (x, y - cap / 2), string=s or " ")


def navy_table(headers, rows, *, title=None, note=None, fit_buff=0.4, region=None,
               top=None):
    """`region=(x0, x1)` confines the table, its title and note to that strip of the
    frame (centred in it, fitted to its width), so two tables can sit side by side;
    the whole frame without one. `top` caps the table's top edge (below a title the
    caller placed, e.g. one title over two halves). A cell may be a Mobject (a tile row) instead of
    text: it is centred on its column and its row's y, and never decimal-aligned."""
    mobs = {(i, c): v for i, r in enumerate(rows) for c, v in enumerate(r)
            if isinstance(v, Mobject)}
    headers = [str(h) for h in headers]
    rows = [["" if (i, c) in mobs else str(v) for c, v in enumerate(r)]
            for i, r in enumerate(rows)]
    ncol = len(headers)
    for i, r in enumerate(rows):
        if len(r) != ncol:
            raise ValueError(f"row {i} has {len(r)} cells, want {ncol}: {r}")

    head = [_text(h, HEADER_SIZE, weight=BOLD) for h in headers]
    cells = [[mobs.get((i, c)) or _text(v, CELL_SIZE) for c, v in enumerate(r)]
             for i, r in enumerate(rows)]
    is_mob = [any((i, c) in mobs for i in range(len(rows))) for c in range(ncol)]
    decimal = [not is_mob[c] and bool(rows)
               and all(_DECIMAL.match(r[c]) for r in rows if r[c].strip())
               and any(r[c].strip() for r in rows) for c in range(ncol)]

    def point_x(mob, s):
        """x of the decimal point inside a cell (its glyph index in the string)."""
        return mob[s.index(".")].get_center()[0]

    # each column's width: the header, or the cells as they will sit (a decimal
    # column's cells aligned on the point, so its width is left-of-point plus right)
    widths = []
    for c in range(ncol):
        if decimal[c]:
            filled = [r for r in range(len(rows)) if rows[r][c].strip()]
            lefts = [point_x(cells[r][c], rows[r][c]) - cells[r][c].get_left()[0]
                     for r in filled]
            rights = [cells[r][c].get_right()[0] - point_x(cells[r][c], rows[r][c])
                      for r in filled]
            body_w = max(lefts) + max(rights)
        else:
            body_w = max((row[c].width for row in cells), default=0)
        widths.append(max(head[c].width, body_w))
    xs, x = [], -(sum(widths) + COL_GAP * (ncol - 1)) / 2
    for w in widths:
        xs.append(x + w / 2)
        x += w + COL_GAP

    # rows laid out from y = 0 at the header; the block is moved into place after
    row_ys = [-HEAD_GAP - i * ROW_DY for i in range(len(rows))]
    for c in range(ncol):
        _sit(head[c], headers[c], xs[c], 0, HEADER_SIZE)
        if decimal[c]:
            filled = [r for r in range(len(rows)) if rows[r][c].strip()]
            lefts = [point_x(cells[r][c], rows[r][c]) - cells[r][c].get_left()[0]
                     for r in filled]
            rights = [cells[r][c].get_right()[0] - point_x(cells[r][c], rows[r][c])
                      for r in filled]
            dot = xs[c] - (max(lefts) + max(rights)) / 2 + max(lefts)
            for r in range(len(rows)):
                _sit(cells[r][c], rows[r][c], 0 if r in filled else xs[c], row_ys[r], CELL_SIZE)
                if r in filled:               # a blank cell has no point to align
                    cells[r][c].shift(RIGHT * (dot - point_x(cells[r][c], rows[r][c])))
        else:
            for r in range(len(rows)):
                if (r, c) in mobs:
                    cells[r][c].move_to([xs[c], row_ys[r], 0])
                else:
                    _sit(cells[r][c], rows[r][c], xs[c], row_ys[r], CELL_SIZE)

    header = VGroup(*head)
    body = [VGroup(*row) for row in cells]
    everything = VGroup(header, *body)
    stripes = row_stripes(row_ys, everything.get_left()[0] - STRIPE_PAD,
                          everything.get_right()[0] + STRIPE_PAD, ROW_DY)
    block = VGroup(stripes, header, *body)

    out = VGroup()
    title_mob = note_mob = None
    top = config.frame_y_radius - fit_buff if top is None else top
    bottom = -config.frame_y_radius + fit_buff
    if title is not None:
        lines = [title] if isinstance(title, str) else list(title)
        title_mob = VGroup(*[crisp_text(t, font_size=FONT_SIZE_LG, color=WHITE)
                             for t in lines]).arrange(DOWN, buff=TITLE_GAP)
        title_mob.to_edge(UP, buff=TITLE_BUFF)
        top = title_mob.get_bottom()[1] - BLOCK_GAP
    if note is not None:
        note_mob = crisp_text(note, font_size=NOTE_SIZE, color=WHITE)
        note_mob.to_edge(DOWN, buff=TITLE_BUFF)
        bottom = note_mob.get_top()[1] + NOTE_GAP
    # the TABLE alone shrinks to fit between the title and the note (never grows),
    # so the title keeps its place at the top and the note at the bottom
    x0, x1 = region if region is not None else (-config.frame_x_radius, config.frame_x_radius)
    cx = (x0 + x1) / 2
    max_w = (x1 - x0) - 2 * fit_buff
    for m in (title_mob, note_mob):
        if m is not None:
            if m.width > max_w:                  # a title / note wider than its strip
                m.scale(max_w / m.width, about_edge=UP if m is title_mob else DOWN)
            m.set_x(cx)
    f = min(1.0, max_w / block.width, (top - bottom) / block.height)
    block.scale(f)
    block.move_to([cx, (top + bottom) / 2, 0])
    out.add(block)
    for m in (title_mob, note_mob):
        if m is not None:
            out.add(m)

    out.title, out.note, out.header, out.rows, out.cells, out.stripes = (
        title_mob, note_mob, header, body, cells, stripes)
    return out
