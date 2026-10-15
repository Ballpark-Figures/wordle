"""An opener in the corner, its groups as coloured rows in 06b's sorted dot-view
layout, and a word typed under each row — scenes 12 and 15.

Moved out of scene 12 when scene 15 needed the same view (2026-10-01), unchanged in
behaviour.
"""
from config import *
from assets.board import STROKE, GAP, TILE, get_typed_row
from assets.pigpen import PigpenWord
from assets.groups import scored_row, ranked_layout, GUESS_SCALE, HEADER_W

CORNER_BUFF = 0.3          # the corner word's gap to the frame's edges (06)
CORNER_MARGIN = 0.35       # clear space kept right of the corner word (06)


def corner_spot(word):
    """(centre, the rows' left edge) for `word` in the top-left corner at GUESS_SCALE."""
    m = PigpenWord(word, revealed=True).scale(GUESS_SCALE)
    corner = np.array([-config.frame_x_radius + CORNER_BUFF + m.width / 2,
                       config.frame_y_radius - CORNER_BUFF - m.height / 2, 0.0])
    return corner, corner[0] + m.width / 2 + CORNER_MARGIN


def row_stroke(width):
    """06's thinned tile border for a row `width` wide."""
    return STROKE * min(1.0, width / HEADER_W)


def under(row):
    """Where a word typed under `row` goes: centre, at the board's row spacing."""
    h = row.height
    return row.get_center() + DOWN * (h + h * GAP / TILE)


def typed_under(word, row):
    """`word` as a typed row, `row`'s width, under it."""
    w = get_typed_row(word)
    w.scale(row.width / w.width).move_to(under(row))
    for t in w.tiles[0]:
        t.set_stroke(width=row_stroke(row.width))
    return w


def group_rows(data, word, left):
    """`word`'s groups in rank order, each as (group, scored row at its dot-view
    spot), plus the dot positions and radius."""
    groups, spots, pos, widths, r = ranked_layout(data, word, left=left)
    rows = [scored_row(word, g["code"], wd, c, stroke=row_stroke(wd))
            for g, c, wd in zip(groups, pos, widths)]
    return groups, rows, spots, r
