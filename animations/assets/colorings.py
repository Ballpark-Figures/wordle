"""The 3**5 = 243 colorings as rows of board tiles — scene 05's builders, shared.

Moved out of scenes/05colorings.py when scene 17 needed the same grid (the user's
call, 2026-10-01); 05 imports everything from here and renders as before.

  - Colours in each split run GREEN, YELLOW, GRAY, so a coloring's slot in the 243 is
    242 minus its pattern code. `slot` is the one place that says so.
  - The splits alternate columns / rows / columns / rows / rows, so the 243 land as
    9 columns x 27 rows of five-tile rows (yahtzee 03dice's `_cluster_centers`, with
    3-way splits; box 15.6 x 8.6, CELL_GAP 0.04 carried over verbatim).
"""
from itertools import product

from config import *
from assets.board import GAP, STROKE, LETTER_FRAC, TILE

ORDER = (2, 1, 0)          # tile colour per split, in slot order: green, yellow, gray
NAMES = {"G": 2, "Y": 1, "-": 0}

BUILD_W, BUILD_H = 15.6, 8.6
CELL_GAP = 0.04            # gap between sibling cells, as a fraction of the box
SPLITS = [(1, 3), (3, 1), (1, 3), (3, 1), (3, 1)]     # (rows, cols) per letter
TILE_BUFF = GAP / TILE     # tile gap as a fraction of tile size — the board's ratio
GRID_BUFF = 0.2            # the 243 grid's tile gap (the user's call, 2026-10-02: a bit
                           # wider than the board's, so small rows read as five tiles)


def code(tiles):
    """'GGYGG' -> wordle.pattern integer, position 0 the most significant trit."""
    c = 0
    for ch in tiles:
        c = 3 * c + NAMES[ch]
    return c


def trits(c, n=5):
    return [(c // 3 ** (n - 1 - i)) % 3 for i in range(n)]


def slot(c):
    """A coloring's index in the 243 — the split order is ORDER, not the trit order."""
    s = 0
    for t in trits(c):
        s = 3 * s + ORDER.index(t)
    return s


def glyph(ch, size):
    """One crisp_text per letter, built once and copied.

    The cache lives ON THIS FUNCTION, not as a module global, on purpose: the
    snapshot digest records the printed value of every module global a subscene
    touches, and a cache prints `{}` when a render starts but full by the time a
    snapshot is saved — so the key saved never matched the key looked up, and
    every render replayed from the top. A function is digested by its source.
    """
    cache = glyph.__dict__.setdefault("cache", {})
    if ch not in cache:
        cache[ch] = crisp_text(ch, color=TILE_TEXT, weight=BOLD)
    return cache[ch].copy().scale_to_fit_height(size * LETTER_FRAC)


def letters_on(tiles, word):
    return VGroup(*[glyph(ch, t.height).move_to(t) for ch, t in zip(word, tiles)])


def tile(t, size):
    """One board tile in state `t` (0 gray, 1 yellow, 2 green)."""
    return Square(side_length=size, stroke_width=STROKE, stroke_color=TILE_STATE[t],
                  fill_color=TILE_STATE[t], fill_opacity=1.0)


def coloring(ts, word, size, buff=TILE_BUFF):
    """A scored row: `.tiles` in their colours, `.letters` on top (board look). `buff`
    is the tile gap as a fraction of the tile: the board's by default, GRID_BUFF in
    the 243 grid."""
    tiles = VGroup(*[tile(t, size) for t in ts])
    tiles.arrange(RIGHT, buff=size * buff)
    letters = letters_on(tiles, word)
    row = VGroup(tiles, letters)
    row.tiles, row.letters = tiles, letters
    return row


def centers(splits, cx, cy, w, h):
    """Cell centres for nested splits, lex order (splits[0] = first letter)."""
    if not splits:
        return [(cx, cy)]
    (r, c), rest = splits[0], splits[1:]
    gx, gy = w * CELL_GAP, h * CELL_GAP
    cw, ch = (w - (c - 1) * gx) / c, (h - (r - 1) * gy) / r
    out = []
    for v in range(r * c):
        rr, cc = divmod(v, c)
        out.extend(centers(rest, cx + (cc - (c - 1) / 2) * (cw + gx),
                           cy + ((r - 1) / 2 - rr) * (ch + gy), cw, ch))
    return out


def tile_size(k):
    """Largest tile so a k-tile row fits the leaf cell (yahtzee's `_die_size`)."""
    w, h = BUILD_W, BUILD_H
    for r, c in SPLITS[:k]:
        w = (w - (c - 1) * w * CELL_GAP) / c
        h = (h - (r - 1) * h * CELL_GAP) / r
    return max(min(w * 0.98 / (k + GRID_BUFF * (k - 1)), h * 0.94), 0.01)


def level(k, word):
    """All 3**k colorings of `word`'s first k letters, in slot order, placed."""
    size = tile_size(k)
    cs = centers(SPLITS[:k], 0.0, 0.0, BUILD_W, BUILD_H)
    rows = []
    for i, digits in enumerate(product(range(3), repeat=k)):
        row = coloring([ORDER[d] for d in digits], word[:k], size, buff=GRID_BUFF)
        row.move_to([*cs[i], 0.0])
        rows.append(row)
    return rows
