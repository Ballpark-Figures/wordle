"""Pigpen cipher — words as Wordle tiles carrying pigpen glyphs, and the flip that
decodes them.

    w = PigpenWord("aback")                  # five tiles, a glyph on each
    w = PigpenWord("piggy", revealed=True)   # the same word, already decoded
    scene.play(decode(w, run_time=0.8))      # each tile flips over to its letter

Handles: `.word`, `.tiles[i]`, `.glyphs[i]`, `.letters[i]`, `.revealed`.

THE TILES ARE THE BOARD'S — a one-row `board.WordleBoard`, shrunk, with its tiles
given the typed-tile border — and the decoded letters are `board`'s own
`_letter`, so a decoded word looks exactly like a typed row.

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
so the path can start at the first drawn wall and walk round. Separate Lines
would leave a notch at every corner.

THE FLIP IS board.TileFlip's squash: tile and glyph go flat as |cos(pi*alpha)|, and
at the midpoint the glyph is swapped for the letter, which grows back with the
tile. The tile keeps its colour — this decodes, it does not score.

NEVER SCALE A WORD WITH `scale_stroke=True`. manim 0.20 turns a stroke of width 0
into the default width times the factor, so the letters (crisp_text, stroke 0)
came out with a thick outline — MEASURED 0 -> 4.8 on a 1.2x scale. Scale plainly and
call `set_glyph_stroke(scale)`, which sets the one stroke that should thin.
"""
import numpy as np

from config import *
from assets.board import WordleBoard, TILE, GAP, STROKE

TILE_LIST = 0.42      # tile side at list size (scale 1)
GLYPH_FRAC = 0.55     # glyph cell as a fraction of the tile
STROKE_W = 3.0        # glyph line width at scale 1
DOT_FRAC = 0.10       # dot radius as a fraction of the glyph cell
INK = WHITE           # the glyphs
WORD_W = 5 * TILE_LIST + 4 * GAP * TILE_LIST / TILE     # a word's width at scale 1



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


def glyph(ch, size=TILE_LIST * GLYPH_FRAC, stroke=STROKE_W, color=INK):
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
    """Show or hide a glyph (stroke + dot) or a letter (fill only — a letter's
    stroke is width 0 and must stay out of this)."""
    v = 1.0 if on else 0.0
    if hasattr(mob, "lines"):
        mob.lines.set_stroke(opacity=v)
        if mob.dot is not None:
            mob.dot.set_fill(opacity=v)
    else:
        mob.set_fill(opacity=v)


class PigpenWord(VGroup):
    """A word as a row of Wordle tiles, a pigpen glyph on each, with its letters
    built underneath (hidden). Everything lives in the group, so moving or scaling
    the word carries the letters with it and `decode` can swap them in place."""

    def __init__(self, word, revealed=False, **kwargs):
        super().__init__(**kwargs)
        self.word = word
        self.revealed = revealed
        row = WordleBoard(rows=1, cols=len(word)).scale(TILE_LIST / TILE)
        self.tiles = row.tiles[0]
        self.glyphs, self.letters = [], []
        for ch, tile in zip(word, self.tiles):
            tile.set_stroke(TILE_FILLED_BORDER, STROKE)     # a typed tile
            g = glyph(ch, TILE_LIST * GLYPH_FRAC).move_to(tile)
            l = row._letter(ch, tile)
            _vis(g, not revealed)
            _vis(l, revealed)
            self.glyphs.append(g)
            self.letters.append(l)
        self.add(*self.tiles, *self.glyphs, *self.letters)

    def set_glyph_stroke(self, scale):
        """The glyph line width for a word drawn at `scale` (1 = list size). Chain
        it after a plain `.scale`, `.animate` included."""
        for g in self.glyphs:
            g.lines.set_stroke(width=STROKE_W * scale)
        return self


class GlyphFlip(Animation):
    """One tile turning over to show its letter — board.TileFlip's squash.

    Visibility is driven by ALPHA rather than set in begin(), for the reason
    board.TilePop gives: a LaggedStart calls begin() on every member up front."""

    def __init__(self, tile, glyph_mob, letter, **kwargs):
        self.parts = [tile, glyph_mob, letter]
        self.g, self.l = glyph_mob, letter
        self.h = [m.height for m in self.parts]
        self.c = tile.get_center()
        super().__init__(VGroup(*self.parts), **kwargs)

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        s = max(abs(np.cos(np.pi * a)), 1e-3)
        _vis(self.g, a < 0.5)
        _vis(self.l, a >= 0.5)
        for m, h in zip(self.parts, self.h):
            m.stretch_to_fit_height(h * s).move_to(self.c)


def decode(word, run_time, lag_ratio=0.25):
    """The whole word decoding, tile by tile, left to right — one animation.
    Marks the word revealed."""
    word.revealed = True
    return LaggedStart(*[GlyphFlip(t, g, l)
                         for t, g, l in zip(word.tiles, word.glyphs, word.letters)],
                       lag_ratio=lag_ratio, run_time=run_time)


def reletter(tiles, old, new, run_time, lag_ratio=0.25):
    """Tiles turning over from one set of letters to another (06c: CODES to TRACE)
    — GlyphFlip with a letter on both faces. `new` must already be in the scene,
    placed on its tile; the flip hides it until the midpoint."""
    return LaggedStart(*[GlyphFlip(t, o, n) for t, o, n in zip(tiles, old, new)],
                       lag_ratio=lag_ratio, run_time=run_time)
