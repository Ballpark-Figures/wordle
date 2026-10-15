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


class BranchPop(Animation):
    """A branch line extending from `a` to `b` while `target` (a row, a card) pops
    out along it: at progress g the line runs a -> a + (b - a) g, and the target is
    g of its size, centred g of the way from `a` to its own place. The number
    line's marker pop (bpkfigures ZoomLine `_place_marker` / MarkerPop), with the
    branch as the stem (scene 18). Build `line` and `target` at their FINAL places;
    pass VGroup-free: the scene adds both."""

    def __init__(self, line, target, a, b, **kwargs):
        self.line, self.target = line, target
        self.a, self.b = np.array(a, dtype=float), np.array(b, dtype=float)
        self.home = target.get_center().copy()
        self.full_w = target.width
        super().__init__(VGroup(line, target), **kwargs)

    def create_starting_mobject(self):
        return Mobject()

    def interpolate_mobject(self, alpha):
        g = max(self.rate_func(alpha), 1e-3)
        self.line.put_start_and_end_on(self.a, self.a + (self.b - self.a) * g + 1e-4 * UP)
        self.target.scale(g * self.full_w / self.target.width)
        self.target.move_to(self.a + (self.home - self.a) * g)

    def finish(self):
        super().finish()
        self.line.put_start_and_end_on(self.a, self.b)
        self.target.scale(self.full_w / self.target.width).move_to(self.home)
