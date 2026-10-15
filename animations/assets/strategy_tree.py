"""Pieces of scene 18's SLANT / PRICE strategy tree, for drawing another strategy
tree in the same style (the bonus video's TRINE tree).

COPIED VERBATIM from animations/scenes/18slant_price.py (`_row_width`, `_stroke`,
`_empty_row`, `_split_tile`, `_rca_card`, `_typed_board`'s body), not moved: scene 18
is shipped and is left alone. Keep the two in step by hand if either changes.

  pattern boxes  grey = TILE_ABSENT; a coloured tile is two triangles, TILE_CORRECT
                 top-left and TILE_PRESENT bottom-right (green or yellow); black = an
                 untouched tile (anything)
  words          a one-row board, typed (get_typed_row's look), at the rows' size
  RCA card       the number line's Random Compatible Answers card
"""
from config import *
from bpkfigures.card import card_behind
from bpkfigures.number_line import stack_lines
from assets.board import GAP, STROKE, TILE, WordleBoard
from assets.strategy_line import CARD_PAD, CARD_RADIUS, MARKER_FS

ROW_TILE = 0.62                   # scene 18's rows' tile side


def row_width(n=5, tile=ROW_TILE):
    return n * tile + (n - 1) * tile * GAP / TILE


def stroke(row):
    """12's rule: a scaled row's tile border thinned in proportion to its tiles."""
    return STROKE * min(1.0, row.tiles[0][0].height / TILE)


def empty_row(width):
    """A one-row board of untouched tiles, `width` wide."""
    row = WordleBoard(rows=1, cols=5)
    row.scale(width / row.width)
    for t in row.tiles[0]:
        t.set_stroke(width=stroke(row))
    return row


def split_tile(tile):
    """`tile` as two triangles: green top-left, yellow bottom-right (18i)."""
    ul, ur = tile.get_corner(UL), tile.get_corner(UR)
    dl, dr = tile.get_corner(DL), tile.get_corner(DR)
    green = Polygon(ul, ur, dl, stroke_width=0).set_fill(TILE_CORRECT, opacity=1.0)
    yellow = Polygon(ur, dr, dl, stroke_width=0).set_fill(TILE_PRESENT, opacity=1.0)
    return VGroup(green, yellow)


def pattern_row(kinds, width):
    """Five boxes, `width` wide: `kinds` a 5-string of "c" (coloured: green or
    yellow, 18's split tile), "g" (grey) or "." (black: anything). 18's two rows are
    "ccc.." (18i) and "ggg.." (18k)."""
    row = empty_row(width)
    extras = VGroup()
    for t, k in zip(row.tiles[0], kinds):
        if k == "g":
            t.set_fill(TILE_ABSENT, opacity=1.0).set_stroke(TILE_ABSENT)
        elif k == "c":
            extras.add(split_tile(t))
            t.set_fill(opacity=0).set_stroke(width=0)
    if len(extras):                  # an EMPTY group would sit at the origin and
        row.add(extras)              #   stretch the row's bounds (18l, 2026-10-03)
    return row


def word_row(word, width):
    """`word` typed on a one-row board `width` wide (18h's SLANT / 18l's PRICE)."""
    row = WordleBoard(rows=1, cols=5)
    row.scale(width / row.width)
    for i, ch in enumerate(word):
        tile = row.tiles[0][i]
        tile.set_stroke(TILE_FILLED_BORDER, stroke(row))
        letter = row._letter(ch, tile)
        row.letters[0][i] = letter
        row.add(letter)
    return row


def rca_card(top_center, font_size=MARKER_FS):
    """'Random Compatible Answers' on the number line's RCA card: three lines on a
    baseline pitch (bpkfigures `stack_lines`), on StrategyLine's card; no bold
    initials (user's call). Its top at `top_center`."""
    lines = stack_lines(["Random", "Compatible", "Answers"],
                        font_size=font_size, color=WHITE).set_z_index(1)
    card = card_behind(lines, pad=CARD_PAD, fill=TILE_EMPTY_FILL,
                       stroke_color=TILE_FILLED_BORDER, stroke_width=STROKE,
                       corner_radius=CARD_RADIUS)
    out = VGroup(card, lines)
    out.move_to(top_center, aligned_edge=UP)
    return out
