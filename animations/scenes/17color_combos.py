"""Scene 17 — colour combinations: the 243 colorings collapse to 21 (G, Y, gray) counts.
Navy background.

Talking head THK precedes it, so it opens with the 243 already on screen; THL follows.

BEAT MAP:
  a show_243   — the 243 colorings from scene 05, colours only, held       (17a, VO 1)
  b two_kinds  — the 5 rows of 4 greens + a gray go left, the 30 of 2G 2Y 1 gray
                 go right (above the rest), everything else fades out        (17b, VO 2)
  c combos     — GGGG- and GGYY- move into their places in the grid of 21
                 combinations while the other 33 fade; then the other 19 fade in (17c, VO 2)
  d drop_impossible — GGGGY fades out, whoosh                                (17d, VO 2)
  e drop_win   — GGGGG, all greens, fades out, whoosh                       (17e, VO 2)
  (17f is NOT BUILT — its direction is not final, the user's call 2026-10-01.)

REUSE MAP — every element and the one source it comes from:
  the 243 grid        assets/colorings.py `level` — scene 05's 9 x 27 build, moved out
                      to be shared; built with no letters, as 05n leaves it
  17a                 on screen from setup_scene, no entrance (06 after THD)
  tiles               assets/colorings.py `tile` — board tile, TILE_STATE fill + stroke
  17b motion          kept rows scaled and moved (05g's `animate.scale().move_to()`),
                      the rest FadeOut, kept rows at z_index 1 (script)
  17c combinations    tiles greens, yellows, grays; tile gap the board's ratio
                      (TILE_BUFF), BLOCK_GAP between colour blocks (script: "slight gaps")
  17d/e sound         11j's vanish: whoosh-mids at stacks_view WHOOSH_GAIN, peaking
                      mid-fade (11pop_quiz.py `poof`)
  colours             BOARD_NAVY via WordleBoardScene; tiles config.py TILE_STATE

LAYOUT CHOICES, flagged:
  - 17b: the 5 in one column on the left, the 30 in three columns of ten on the right,
    in their 243-grid order down each column, all at PART_TILE; equal gaps edge -> 5 -> 30 -> edge
    (the user's call).
  - 17c: a rectangular grid (the user's call): one column per green count, all greens
    in the last column, each column from the top, most yellows first; combinations
    centred in fixed-pitch cells.
No on-screen text: 243 / 5 / 30 / 21 / 19 are spoken, not shown.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.colorings import level, code, trits, slot, TILE_BUFF, tile
from assets.stacks_view import WHOOSH_GAIN

# ── 17b: the two kinds ─────────────────────────────────────────────────────────
KIND_A = (4, 0, 1)         # (greens, yellows, grays): 4 greens and a gray — 5 rows
KIND_B = (2, 2, 1)         # 2 greens, 2 yellows, a gray — 30 rows
PART_TILE = 0.34           # tile side for the 35 kept rows
PART_ROW_GAP = 0.5         # gap between rows, in tiles
PART_COL_GAP = 1.5         # gap between columns, in tiles
RIGHT_COLS = 3             # the 30 in three columns of ten; the 5 in one column

# ── 17c: the grid of 21 ────────────────────────────────────────────────────────
COMBO_TILE = 0.32
BLOCK_GAP = 0.45           # gap between colour blocks, in tiles (tile gap is TILE_BUFF)
COMBO_PITCH = 8.0          # column pitch, in tiles (the widest combination is 6.8)
LINE_PITCH = 1.1           # row pitch
IMPOSSIBLE = (4, 1, 0)     # 17d: 4 greens and a yellow can never happen
WIN = (5, 0, 0)            # 17e: all greens — the game is over
# 17d/e: 11j's vanish sound, copied — whoosh-mids at scene 01's whoosh level,
# timed so its loudest point lands mid-fade
VANISH_SFX = "whoosh-mids"
VANISH_PEAK = 0.20         # s into the file where it is loudest (11pop_quiz.py's MEASURED)


def _counts(c):
    t = trits(c)
    return (t.count(2), t.count(1), t.count(0))


def _block_w(cols, size):
    """Width of `cols` columns of five-tile rows at tile side `size`."""
    w = size * (5 + 4 * TILE_BUFF)
    return cols * w + (cols - 1) * PART_COL_GAP * size


def _part_xs(size):
    """Centres of the 5's column and the 30's block: frame edge -> 5 -> 30 -> frame
    edge, three equal gaps (the user's call)."""
    wa, wb = _block_w(1, size), _block_w(RIGHT_COLS, size)
    gap = (2 * config.frame_x_radius - wa - wb) / 3
    xa = -config.frame_x_radius + gap + wa / 2
    return xa, xa + wa / 2 + gap + wb / 2


def _part_cells(n, cols, cx, size):
    """Centres for n five-tile rows in `cols` columns, filled DOWN each column, top
    to bottom, then the next column to the right (the user's call)."""
    w = size * (5 + 4 * TILE_BUFF)
    px, py = w + PART_COL_GAP * size, size * (1 + PART_ROW_GAP)
    nr = -(-n // cols)
    return [np.array([cx + (k // nr - (cols - 1) / 2) * px,
                      ((nr - 1) / 2 - k % nr) * py, 0.0]) for k in range(n)]


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


def _grid21():
    """{(g, y, b): combination} — a rectangular grid, one COLUMN per green count, 0
    greens on the left to 5 on the right; each column from the top, most yellows
    first (the user's call). Cells on fixed pitches, combinations centred in them."""
    out = {}
    for g in range(6):
        for row, y in enumerate(range(5 - g, -1, -1)):
            x = (g - 2.5) * COMBO_PITCH * COMBO_TILE
            yy = (2.5 - row) * LINE_PITCH
            out[(g, y, 5 - g - y)] = _combo(g, y, 5 - g - y, COMBO_TILE).move_to([x, yy, 0])
    return out


class Scene17(WordleBoardScene):
    """BEAT MAP
    show_243 — the 243 colorings held, colours only
    two_kinds — 4G+gray to the left, 2G2Y+gray to the right, the rest fade
    combos — two move into the grid of 21, the rest fade; the other 19 fade in
    drop_impossible — GGGGY fades out
    drop_win — GGGGG fades out
    """

    def setup_scene(self):
        # on screen from frame 0: THK cuts straight to it (06's convention)
        self.grid = level(5, "")
        self.add(*self.grid)

    # a : the 243 colorings from before, held — its VO plays over the framework's holds
    @subscene
    def show_243(self):
        pass

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
        xa, xb = _part_xs(PART_TILE)
        self.targets = list(zip([self.kind_a[c] for c in order(self.kind_a)],
                                _part_cells(5, 1, xa, PART_TILE))) + \
            list(zip([self.kind_b[c] for c in order(self.kind_b)],
                     _part_cells(30, RIGHT_COLS, xb, PART_TILE)))
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
        self.combos = _grid21()
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

    # d : GGGGY, the impossible combination, fades out
    @subscene
    def drop_impossible(self):
        rt = 0.8
        self.sfx(VANISH_SFX, at=max(0.0, rt / 2 - VANISH_PEAK), gain=WHOOSH_GAIN)
        self.play(FadeOut(self.combos.pop(IMPOSSIBLE)), run_time=rt)

    # e : GGGGG, the all-greens combination (the game is over), fades out
    @subscene
    def drop_win(self):
        rt = 0.8
        self.sfx(VANISH_SFX, at=max(0.0, rt / 2 - VANISH_PEAK), gain=WHOOSH_GAIN)
        self.play(FadeOut(self.combos.pop(WIN)), run_time=rt)

    # f : NOT BUILT — 17f's direction is not final (the user, 2026-10-01)
