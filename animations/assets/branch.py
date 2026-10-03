"""Branch lines between word rows — scene 07's tree edges, shared with scene 18.

Moved out of scene 07 (its `_line` / `_r`) when scene 18 needed the same line,
unchanged in behaviour: white, thin, behind the tiles (hangman 18's edges), from
and to the centre of a row's MIDDLE tile.
"""
from config import *

LINE_W = 1.5                       # branch lines (hangman 18's tree edges: white, behind)


def mid_tile(row):
    """The centre of `row`'s middle tile — where every branch line ends. Takes a
    board row (board.get_scored_row / get_typed_row) or a bare list of five tiles."""
    tiles = row.tiles[0] if hasattr(row, "tiles") else row
    return tiles[2].get_center()


def branch_line(a, b):
    """A branch line from `a` to `b`: white, thin, behind the tiles."""
    return Line(a, b, color=WHITE, stroke_width=LINE_W).set_z_index(-1)
