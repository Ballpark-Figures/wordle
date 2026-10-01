"""Scene 17 — colour combinations: the 243 colorings collapse to 21 (G, Y, gray) counts.
Navy background.

Talking head THK precedes it, so it opens from an empty frame; THL follows.

BEAT MAP:
  a show_243   — the 243 colorings from scene 05, colours only, fade in      (17a, VO 1)
  b two_kinds  — the 5 rows of 4 greens + a gray go left, the 30 of 2G 2Y 1 gray
                 go right (above the rest), everything else fades out        (17b, VO 2)
  c combos     — GGGG- and GGYY- move into their places in the triangle of 21
                 combinations while the other 33 fade; then the other 19 fade in (17c, VO 2)
  (17d is NOT BUILT — its direction is not final, the user's call 2026-10-01.)

REUSE MAP — every element and the one source it comes from:
  the 243 grid        assets/colorings.py `level` — scene 05's 9 x 27 build, moved out
                      to be shared; built with no letters, as 05n leaves it
  17a entrance        FadeIn of the grid rows, as 05n brings the 238 back
                      (05colorings.py `back`)
  tiles               assets/colorings.py `tile` — board tile, TILE_STATE fill + stroke
  17b motion          kept rows scaled and moved (05g's `animate.scale().move_to()`),
                      the rest FadeOut, kept rows at z_index 1 (script)
  17c combinations    tiles greens, yellows, grays; tile gap the board's ratio
                      (TILE_BUFF), BLOCK_GAP between colour blocks (script: "slight gaps")
  colours             BOARD_NAVY via WordleBoardScene; tiles config.py TILE_STATE

LAYOUT CHOICES, flagged:
  - 17b: the 5 in one column on the left, the 30 in three columns of ten on the right,
    in their 243-grid order, all at COMBO_TILE.
  - 17c: a triangle (the user's call): one line per green count, 5 at the top, most
    yellows on the left; combinations centred in fixed-pitch cells.
No on-screen text: 243 / 5 / 30 / 21 / 19 are spoken, not shown.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.colorings import level, code, trits, slot, TILE_BUFF, tile

# ── 17b: the two kinds ─────────────────────────────────────────────────────────
KIND_A = (4, 0, 1)         # (greens, yellows, grays): 4 greens and a gray — 5 rows
KIND_B = (2, 2, 1)         # 2 greens, 2 yellows, a gray — 30 rows
PART_TILE = 0.34           # tile side for the 35 kept rows
PART_ROW_GAP = 0.5         # gap between rows, in tiles
PART_COL_GAP = 1.5         # gap between columns, in tiles
LEFT_X, RIGHT_X = -4.0, 4.0
RIGHT_COLS = 3

# ── 17c: the triangle of 21 ────────────────────────────────────────────────────
COMBO_TILE = 0.32
BLOCK_GAP = 0.45           # gap between colour blocks, in tiles (tile gap is TILE_BUFF)
COMBO_PITCH = 8.0          # cell width, in tiles (the widest combination is 6.8)
LINE_PITCH = 1.1           # vertical distance between green-count lines


def _counts(c):
    t = trits(c)
    return (t.count(2), t.count(1), t.count(0))


def _part_cells(n, cols, cx, size):
    """Centres for n five-tile rows in `cols` columns, filled row by row, centred."""
    w = size * (5 + 4 * TILE_BUFF)
    px, py = w + PART_COL_GAP * size, size * (1 + PART_ROW_GAP)
    nr = -(-n // cols)
    return [np.array([cx + (k % cols - (cols - 1) / 2) * px,
                      ((nr - 1) / 2 - k // cols) * py, 0.0]) for k in range(n)]


def _combo(g, y, b, size):
    """g greens, y yellows, b grays; board tile gaps inside a block, BLOCK_GAP between.
    Same shape as a coloring row (tiles, empty letters) so a row transforms into it."""
    tiles, x, prev = VGroup(), 0.0, None
    for t in [2] * g + [1] * y + [0] * b:
        if prev is not None:
            x += size * (1 + (TILE_BUFF if t == prev else BLOCK_GAP))
        tiles.add(tile(t, size).move_to([x, 0, 0]))
        prev = t
    tiles.move_to(ORIGIN)
    row = VGroup(tiles, VGroup())
    row.tiles, row.letters = tiles, row[1]
    return row


def _triangle():
    """{(g, y, b): combination} — one line per green count, 5 greens on top, most
    yellows on the left; each line centred."""
    out = {}
    for g in range(5, -1, -1):
        ys = range(5 - g, -1, -1)
        for i, y in enumerate(ys):
            x = (i - (len(ys) - 1) / 2) * COMBO_PITCH * COMBO_TILE
            yy = (g - 2.5) * LINE_PITCH
            out[(g, y, 5 - g - y)] = _combo(g, y, 5 - g - y, COMBO_TILE).move_to([x, yy, 0])
    return out


class Scene17(WordleBoardScene):
    """BEAT MAP
    show_243 — the 243 colorings fade in, colours only
    two_kinds — 4G+gray to the left, 2G2Y+gray to the right, the rest fade
    combos — two move into the triangle of 21, the rest fade; the other 19 fade in
    """

    def setup_scene(self):
        pass

    # a : the 243 colorings from before
    def _setup_show_243(self):
        self.grid = level(5, "")

    @subscene
    def show_243(self):
        self._setup_show_243()
        self.play(FadeIn(VGroup(*self.grid)), run_time=1.0)

    # b : the 5 with 4 greens and a gray to the left, the 30 with 2G 2Y 1 gray to the
    #     right, everything else fading out
    def _setup_two_kinds(self):
        by_code = {c: self.grid[slot(c)] for c in range(243)}
        self.kind_a = {c: r for c, r in by_code.items() if _counts(c) == KIND_A}
        self.kind_b = {c: r for c, r in by_code.items() if _counts(c) == KIND_B}
        assert (len(self.kind_a), len(self.kind_b)) == (5, 30)
        kept = {**self.kind_a, **self.kind_b}
        self.rest = VGroup(*[r for c, r in by_code.items() if c not in kept])
        order = lambda d: sorted(d, key=slot)               # the 243 grid's order
        self.targets = list(zip([self.kind_a[c] for c in order(self.kind_a)],
                                _part_cells(5, 1, LEFT_X, PART_TILE))) + \
            list(zip([self.kind_b[c] for c in order(self.kind_b)],
                     _part_cells(30, RIGHT_COLS, RIGHT_X, PART_TILE)))
        for r, _ in self.targets:
            r.set_z_index(1)

    @subscene
    def two_kinds(self):
        self._setup_two_kinds()
        self.play(FadeOut(self.rest),
                  *[r.animate.scale(PART_TILE / r.tiles[0].width).move_to(p)
                    for r, p in self.targets],
                  run_time=1.5)
        self.grid = self.rest = self.targets = None

    # c : GGGG- and GGYY- into the triangle of 21, the other 33 fading; then the
    #     other 19 fade in
    def _setup_combos(self):
        self.combos = _triangle()
        movers = {code("GGGG-"): KIND_A, code("GGYY-"): KIND_B}
        kept = {**self.kind_a, **self.kind_b}
        self.moves = [(kept[c], self.combos[k]) for c, k in movers.items()]
        self.fading = VGroup(*[r for c, r in kept.items() if c not in movers])

    @subscene
    def combos(self):
        self._setup_combos()
        self.play(*[ReplacementTransform(r, t) for r, t in self.moves],
                  FadeOut(self.fading), run_time=1.5)
        self.play(FadeIn(VGroup(*[c for k, c in self.combos.items()
                                  if k not in (KIND_A, KIND_B)])), run_time=1.0)
        self.kind_a = self.kind_b = self.fading = self.moves = None

    # d : NOT BUILT — 17d's direction is not final (the user, 2026-10-01)
