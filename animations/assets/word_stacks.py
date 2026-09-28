"""Every legal opener as a scored word, stacked into a histogram — drawn in BULK.

    class Scene01(MovingCameraScene, ...):
        def __init__(self, **kw):
            super().__init__(camera_class=StacksCamera, **kw)   # REQUIRED

    stacks = WordStacks(intro_data.load(), origin=ORIGIN, origin_bin=358)
    stacks.set_state(n=0, squash=1.0, letters=1.0)       # what to draw
    stacks.refresh(scene.camera.frame)                   # rebuild for this frame

WHY BULK. 12972 words x 5 tiles x (tile + letter) is ~130k mobjects, and manim's
cost is per mobject. Pre-rendered images are no better — the cairo camera solves a
homography and PIL-transforms every ImageMobject separately. So the histogram is a
handful of mobjects: ONE per tile colour (x dimmed/undimmed) holding every rectangle
of that colour, plus one for the letters of the rest and one for the focus words.

WHY A CAMERA SUBCLASS. Even batched, manim builds a cairo path by walking every
bezier in Python: MEASURED 2.4 s per 1080p frame for the full histogram (1.04M
points). `StacksCamera` hands a batch mobject the cairo context and lets it draw
itself — `ctx.rectangle` per tile, and a pre-built glyph path stamped per letter —
and leaves every other mobject to manim. Fill and stroke are still manim's, from the
batch mobject's own colour, so opacity and fades work as normal.

A batch mobject's `points` are only its BOUNDING BOX (manim skips a mobject with no
points, and uses them for get_center/width); the real geometry is in `self.data`.

WHAT IS CULLED. Only words overlapping the camera frame are drawn, and letters only
while their tile is big enough on screen to show one. Culled = off screen or
sub-legible, so culling never visibly changes a frame.

GEOMETRY. Words sit exactly as on the board (`board.TILE`, `board.GAP`), one stack
per 0.01 bin, `PITCH` apart. `origin` is where the word at (origin_bin, row 0) is
centred — the scene puts START's board row there, so the hand-off is seamless.
`squash` scales the VERTICAL only (row spacing, tile and letter height) about the
row-0 line, so the histogram can be flattened to fit the frame as it grows.

SCORED-TILE SIZE. A scored board tile is a `TILE` square with a `board.STROKE`
border in its own fill colour; cairo line width is 0.01 unit per stroke unit and
scales with the camera, so the visible square is TILE + STROKE*0.01. `SIDE` is that,
so a word drawn here is the same size as the board row it replaces.
"""
import cairo
import numpy as np
from manim import MovingCamera

from config import *
from assets.board import TILE, GAP, STROKE, LETTER_FRAC, COLS

STEP = TILE + GAP                   # centre-to-centre, tiles and rows alike
WORD_W = COLS * TILE + (COLS - 1) * GAP
STACK_GAP = 0.6                     # clear space between neighbouring stacks
PITCH = WORD_W + STACK_GAP
SIDE = TILE + STROKE * 0.01
DIM = 0.2                           # the house "dim the rest" opacity
LETTER_MIN_PX = 4.0                 # below this tile size a letter is sub-legible
_EMPTY = np.zeros((0, 3))


def _trits(code):
    return [(code // 3 ** (COLS - 1 - i)) % 3 for i in range(COLS)]


# ── glyphs ────────────────────────────────────────────────────────────────────
_GLYPH_POINTS = None     # letter -> point array, built once per process
_GLYPH_PATHS = {}        # letter -> cairo.Path (not picklable, so never on a mobject)


def glyph_points():
    """Bezier points for A-Z, centred on the origin, sized exactly as board._letter."""
    global _GLYPH_POINTS
    if _GLYPH_POINTS is None:
        _GLYPH_POINTS = {}
        for ch in "abcdefghijklmnopqrstuvwxyz":
            t = crisp_text(ch.upper(), color=TILE_TEXT, weight=BOLD)
            t.scale_to_fit_height(TILE * LETTER_FRAC)
            t.move_to(ORIGIN)
            _GLYPH_POINTS[ch] = [m.points.copy()
                                 for m in t.family_members_with_points()]
    return _GLYPH_POINTS


def _glyph_path(ctx, ch):
    """The cairo path for one letter, built once — with the same subpath walk
    manim's own `set_cairo_context_path` does — and replayed per letter."""
    path = _GLYPH_PATHS.get(ch)
    if path is None:
        helper = VMobject()
        ctx.save()
        ctx.identity_matrix()
        ctx.new_path()
        for pts in glyph_points()[ch]:
            for sub in helper.gen_subpaths_from_points_2d(pts):
                ctx.new_sub_path()
                ctx.move_to(*sub[0][:2])
                for _p0, p1, p2, p3 in helper.gen_cubic_bezier_tuples_from_points(sub):
                    ctx.curve_to(*p1[:2], *p2[:2], *p3[:2])
                if helper.consider_points_equals_2d(sub[0], sub[-1]):
                    ctx.close_path()
        path = ctx.copy_path()
        ctx.new_path()
        ctx.restore()
        _GLYPH_PATHS[ch] = path
    return path


# ── batch mobjects ────────────────────────────────────────────────────────────
def _bbox_points(x0, y0, x1, y1):
    return np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]], float)


class RectBatch(VMobject):
    """Many axis-aligned rectangles, drawn by StacksCamera with `ctx.rectangle`.

    `data` is an (n, 4) array of (x_left, y_bottom, width, height)."""

    def set_rects(self, data):
        self.data = data
        if len(data) == 0:
            self.points = _EMPTY
        else:
            self.set_points_as_corners(_bbox_points(
                data[:, 0].min(), data[:, 1].min(),
                (data[:, 0] + data[:, 2]).max(), (data[:, 1] + data[:, 3]).max()))
        return self

    def cairo_draw(self, ctx):
        rect = ctx.rectangle
        for x, y, w, h in self.data.tolist():
            rect(x, y, w, h)


class GlyphBatch(VMobject):
    """Many letters, drawn by StacksCamera by stamping one path per letter.

    `data` is (cx, cy, letter index, y-scale) arrays."""

    def set_glyphs(self, cx, cy, ch, sy):
        self.data = (cx, cy, ch, sy)
        if len(cx) == 0:
            self.points = _EMPTY
        else:
            h = TILE * LETTER_FRAC / 2
            self.set_points_as_corners(_bbox_points(
                cx.min() - h, cy.min() - h, cx.max() + h, cy.max() + h))
        return self

    def cairo_draw(self, ctx):
        cx, cy, ch, sy = self.data
        for x, y, k in zip(cx.tolist(), cy.tolist(), ch.tolist()):
            path = _glyph_path(ctx, chr(97 + k))
            ctx.save()
            ctx.translate(x, y)
            ctx.scale(1.0, sy)
            ctx.append_path(path)
            ctx.restore()


class StacksCamera(MovingCamera):
    """A MovingCamera that lets a batch mobject draw its own cairo path."""

    def set_cairo_context_path(self, ctx, vmobject):
        draw = getattr(vmobject, "cairo_draw", None)
        if draw is None:
            return super().set_cairo_context_path(ctx, vmobject)
        ctx.new_path()
        draw(ctx)
        return self


# ── the histogram ─────────────────────────────────────────────────────────────
class WordStacks(VGroup):
    def __init__(self, data, origin, origin_bin, **kwargs):
        super().__init__(**kwargs)
        self.words = data["words"]
        bins = np.array(data["bins"])
        self.row = np.array(data["rows"], dtype=float)
        self.order = np.array(data["order"])
        self.pinned = np.array([self.words.index(w) for w in data["pinned"]])
        self.state = np.array([_trits(c) for c in data["codes"]])       # (N, 5)
        self.letters_of = np.array([[ord(ch) - 97 for ch in w] for w in self.words])
        self.x = origin[0] + (bins - origin_bin) * PITCH                  # word centre
        self.y0 = origin[1]
        self.index = {w: i for i, w in enumerate(self.words)}

        # what to draw — the scene sets these (see set_state), then calls refresh
        self.n = 0                  # words of `order` placed so far (pinned always are)
        self.squash = 1.0
        self.letter_opacity = 1.0
        self.focus = np.zeros(len(self.words), dtype=bool)   # emphasised words
        self.dim = 0.0              # 0 = nobody dimmed, 1 = non-focus fully at DIM

        mk = lambda c, o: RectBatch(fill_color=c, fill_opacity=o, stroke_width=0)
        self.tiles = [mk(TILE_STATE[s], 1.0) for s in range(3)]
        self.tiles_dim = [mk(TILE_STATE[s], 1.0) for s in range(3)]
        self.text = GlyphBatch(fill_color=TILE_TEXT, fill_opacity=1.0, stroke_width=0)
        self.text_focus = GlyphBatch(fill_color=TILE_TEXT, fill_opacity=1.0,
                                     stroke_width=0)
        for m in self.tiles + self.tiles_dim:
            m.set_rects(np.zeros((0, 4)))
        self.text.set_glyphs(*[np.zeros(0)] * 4)
        self.text_focus.set_glyphs(*[np.zeros(0)] * 4)
        self.add(*self.tiles, *self.tiles_dim, self.text, self.text_focus)

    # ── what to draw ──────────────────────────────────────────────────────────
    def set_state(self, n=None, squash=None, letters=None, dim=None, focus=None):
        if n is not None:
            self.n = int(round(n))
        if squash is not None:
            self.squash = float(squash)
        if letters is not None:
            self.letter_opacity = float(letters)
        if dim is not None:
            self.dim = float(dim)
        if focus is not None:
            self.focus[:] = False
            self.focus[[self.index[w] for w in focus]] = True
        return self

    def word_center(self, word, squash=None):
        """Where `word` sits at the current (or a given) squash."""
        i = self.index[word]
        s = self.squash if squash is None else squash
        return np.array([self.x[i], self.y0 + self.row[i] * STEP * s, 0.0])

    def height_of(self, word):
        """Rows in the stack holding `word` (its full height, pinned included)."""
        i = self.index[word]
        same = self.x == self.x[i]
        return int(self.row[same].max()) + 1

    def top(self, squash=None):
        """y of the top edge of the tallest stack."""
        s = self.squash if squash is None else squash
        return self.y0 + self.row.max() * STEP * s + SIDE * s / 2

    # ── rebuild ───────────────────────────────────────────────────────────────
    def refresh(self, frame):
        s = self.squash
        shown = np.zeros(len(self.words), dtype=bool)
        shown[self.pinned] = True
        shown[self.order[:self.n]] = True

        # cull to the frame (a word of slack each way)
        fx, fy = frame.get_center()[:2]
        hw, hh = frame.width / 2, frame.height / 2
        y = self.y0 + self.row * STEP * s
        vis = shown & (np.abs(self.x - fx) < hw + WORD_W) \
                    & (np.abs(y - fy) < hh + STEP * s)
        idx = np.nonzero(vis)[0]

        # tiles: one batch per (colour, dimmed?)
        offs = (np.arange(COLS) - (COLS - 1) / 2) * STEP
        tx = (self.x[idx, None] + offs).ravel()
        ty = np.repeat(y[idx], COLS)
        st = self.state[idx].ravel()
        fo = np.repeat(self.focus[idx], COLS)
        dimmed = (~fo) & (self.dim > 0)
        h = SIDE * s
        for k in range(3):
            for mob, sel in ((self.tiles[k], (st == k) & ~dimmed),
                             (self.tiles_dim[k], (st == k) & dimmed)):
                n = int(sel.sum())
                mob.set_rects(np.stack([tx[sel] - SIDE / 2, ty[sel] - h / 2,
                                        np.full(n, SIDE), np.full(n, h)], axis=1))
            # a dimmed tile fades from full to DIM as `dim` goes 0 -> 1
            self.tiles_dim[k].set_fill(opacity=1 - (1 - DIM) * self.dim)

        # letters, only where a tile is big enough on screen to carry one
        px = SIDE * min(1.0, s) * config.pixel_width / frame.width
        big = px >= LETTER_MIN_PX
        rest_op = self.letter_opacity * (1 - (1 - DIM) * self.dim)
        rest = idx[~self.focus[idx]] if big and rest_op > 0 else idx[:0]
        focus = idx[self.focus[idx]] if big else idx[:0]
        self._fill_glyphs(self.text, rest, y, s).set_fill(opacity=rest_op)
        self._fill_glyphs(self.text_focus, focus, y, s) \
            .set_fill(opacity=max(self.letter_opacity, self.dim))
        return self

    def _fill_glyphs(self, mob, idx, y, s):
        offs = (np.arange(COLS) - (COLS - 1) / 2) * STEP
        cx = (self.x[idx, None] + offs).ravel()
        cy = np.repeat(y[idx], COLS)
        ch = self.letters_of[idx].ravel()
        return mob.set_glyphs(cx, cy, ch, s)
