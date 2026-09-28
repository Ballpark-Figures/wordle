"""Pigpen cipher — words drawn as pigpen glyphs, and the flip that decodes them.

    w = PigpenWord("aback")                  # five glyphs, letters hidden underneath
    w = PigpenWord("piggy", revealed=True)   # the same word, already decoded
    scene.play(decode(w, run_time=0.8))      # each glyph flips over to its letter

Handles: `.word`, `.glyphs[i]`, `.letters[i]`, `.revealed`.

THE KEY IS THE STANDARD ONE (Wikipedia's "Pigpen cipher"):

    A B C      J. K. L.       S          W.
    D E F      M. N. O.     T   U      X.  Y.
    G H I      P. Q. R.       V          Z.

A-I sit in a plain noughts-and-crosses grid, J-R in a dotted one, S-V in a plain X
(S top, T left, U right, V bottom), W-Z in a dotted X. A letter is drawn as the
walls of its cell, so E (the middle cell) is a whole square and A (top-left) is the
two walls it shares with its neighbours, a `_|`. An X letter is the V its two
arms make around it: S opens upward, T to the left, U to the right, V downward.
The dot sits in the middle of the cell (the centroid of an X letter's wedge).

A GRID GLYPH IS ONE POLYLINE, not one Line per wall — the walls a cell draws are
always contiguous (an edge cell lacks one side, a corner cell two ADJACENT sides),
so the path can start just after the missing wall and walk round. Separate Lines
would leave a notch at every corner.

THE FLIP IS board.TileFlip's squash, applied to a glyph instead of a tile: the
glyph's height goes as |cos(pi*alpha)|, and at the midpoint it is swapped for the
letter, which grows back. So decoding a word reads like scoring a row.
"""
import numpy as np

from config import *

GLYPH = 0.30          # side of one glyph cell at list size
PITCH_FRAC = 1.28     # centre-to-centre glyph spacing, as a multiple of the cell
STROKE_W = 3.5        # glyph line width at list size
DOT_FRAC = 0.10       # dot radius as a fraction of the cell
LETTER_FRAC = 0.95    # decoded letter height as a fraction of the cell
INK = WHITE           # glyphs and letters, on the navy board background


def _grid_cell(ch):
    """(row, col, dotted) of a noughts-and-crosses letter, or None."""
    k = ord(ch) - ord("a")
    if 0 <= k < 18:
        return (k % 9) // 3, k % 3, k >= 9
    return None


def _x_cell(ch):
    """(quadrant, dotted) of an X letter: 0 top, 1 left, 2 right, 3 bottom."""
    k = ord(ch) - ord("s")
    if 0 <= k < 8:
        return k % 4, k >= 4
    raise ValueError(f"not a letter: {ch!r}")


def glyph(ch, size=GLYPH, stroke=STROKE_W, color=INK):
    """One pigpen glyph, centred on the origin, `size` on a side."""
    h = size / 2
    g = VGroup()
    cell = _grid_cell(ch)
    if cell is not None:
        r, c, dotted = cell
        # corners clockwise from top-left; wall i runs corner i -> corner i+1
        corners = [(-h, h), (h, h), (h, -h), (-h, -h)]
        walls = [r > 0, c < 2, r < 2, c > 0]           # top, right, bottom, left
        if all(walls):
            pts = corners + [corners[0]]
        else:
            # the first drawn wall after a missing one — NOT just past the first
            # missing wall, which for C (top AND right missing) lands on another
            # missing wall and draws nothing
            start = next(i for i in range(4) if walls[i] and not walls[i - 1])
            pts, i = [corners[start]], start
            while walls[i]:
                i = (i + 1) % 4
                pts.append(corners[i])
        centre = (0.0, 0.0)
    else:
        q, dotted = _x_cell(ch)
        pts = {0: [(-h, h), (0, -h), (h, h)],          # S: a V opening up
               1: [(-h, h), (h, 0), (-h, -h)],         # T: > opening left
               2: [(h, h), (-h, 0), (h, -h)],          # U: < opening right
               3: [(-h, -h), (0, h), (h, -h)]}[q]      # V: ^ opening down
        centre = tuple(np.mean(pts, axis=0))           # centroid of the wedge
    line = VMobject(stroke_color=color, stroke_width=stroke, fill_opacity=0)
    line.set_points_as_corners([[x, y, 0] for x, y in pts])
    line.joint_type = LineJointType.MITER               # square corners, no notch
    g.add(line)
    g.lines = line
    g.dot = None
    if dotted:
        dot = Dot([centre[0], centre[1], 0], radius=size * DOT_FRAC, color=color)
        g.add(dot)
        g.dot = dot
    return g


def _vis(mob, on):
    """Show or hide a glyph (stroke + dot) or a letter (fill)."""
    v = 1.0 if on else 0.0
    if hasattr(mob, "lines"):
        mob.lines.set_stroke(opacity=v)
        if mob.dot is not None:
            mob.dot.set_fill(opacity=v)
    else:
        mob.set_opacity(v)


class PigpenWord(VGroup):
    """A word as a row of pigpen glyphs, with its letters built underneath (hidden).

    Both live in the group, so moving or scaling the word carries the letters with
    it and `decode` can swap them in place. Scale with `scale_stroke=True` so the
    glyph lines thin with the word."""

    def __init__(self, word, size=GLYPH, revealed=False, **kwargs):
        super().__init__(**kwargs)
        self.word = word
        self.revealed = revealed
        pitch = size * PITCH_FRAC
        n = len(word)
        self.glyphs, self.letters = [], []
        for i, ch in enumerate(word):
            x = (i - (n - 1) / 2) * pitch
            g = glyph(ch, size).shift(RIGHT * x)
            l = crisp_text(ch.upper(), color=INK, weight=BOLD)
            l.scale_to_fit_height(size * LETTER_FRAC).move_to([x, 0, 0])
            _vis(g, not revealed)
            _vis(l, revealed)
            self.glyphs.append(g)
            self.letters.append(l)
            self.add(g, l)


class GlyphFlip(Animation):
    """One glyph turning over to show its letter — board.TileFlip's squash.

    Visibility is driven by ALPHA rather than set in begin(), for the reason
    board.TilePop gives: a LaggedStart calls begin() on every member up front."""

    def __init__(self, glyph_mob, letter, **kwargs):
        self.g, self.l = glyph_mob, letter
        self.h_g, self.h_l = glyph_mob.height, letter.height
        self.c_g, self.c_l = glyph_mob.get_center(), letter.get_center()
        super().__init__(VGroup(glyph_mob, letter), **kwargs)

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        s = max(abs(np.cos(np.pi * a)), 1e-3)
        first = a < 0.5
        _vis(self.g, first)
        _vis(self.l, not first)
        self.g.stretch_to_fit_height(self.h_g * s).move_to(self.c_g)
        self.l.stretch_to_fit_height(self.h_l * s).move_to(self.c_l)


def decode(word, run_time, lag_ratio=0.25):
    """The whole word decoding, glyph by glyph, left to right — one animation.
    Marks the word revealed."""
    word.revealed = True
    return LaggedStart(*[GlyphFlip(g, l) for g, l in zip(word.glyphs, word.letters)],
                       lag_ratio=lag_ratio, run_time=run_time)
