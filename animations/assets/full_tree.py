"""An opener's WHOLE optimal tree, laid out radially — scene 07's zoom-out (07zc),
shared with scene 99's thumbnail.

Moved out of scene 07 (its `_full_row` / `_glyph` / `_full_layout` / `_full_start` /
`_full_tree`, and the module helpers `_vdc` / `_spread`) when scene 99 needed the
same tree, unchanged in behaviour. Node widths go as sqrt(group size), big groups
sit near the middle, the root is centred. Trees come from assets/tree_data.py
(`load()["full"][word]`).
"""
import math

from config import *
from assets.board import LETTER_FRAC, get_typed_row, get_scored_row, TILE, GAP
from assets.groups import row_aspect

FULL_SCALE_W = 6.0                 # the size rule -- a node of n answers is
                                   #   FULL_SCALE_W * sqrt(n / N) wide, N all of them
FULL_ROOT_W = 3.0                  # the root's own width, OFF the rule (user's call)
FULL_R = 4.25                      # (vertical) distance of a one-answer node from the
                                   #   centre; a node of n answers sits at
                                   #   FULL_R * log(N / n) / log(N) -- the bigger the group,
                                   #   the nearer the middle (user's call), not level rings
FULL_X_STRETCH = 1.75              # the ellipses' width / height (the frame's shape)
FULL_START = math.pi / 2           # where the first branch sits (straight up)
FULL_LINE_W, FULL_LINE_OPACITY = 0.4, 0.2    # the branch lines
FULL_CLEAR = 0.15                  # least gap between the root and any node
FULL_LETTER_W = 0.35               # rows at least this wide are full board rows
FULL_GLYPH_W = 0.08                # narrower rows get copied letters down to this
                                   #   width (user's call: letters that cannot be read
                                   #   still read as letters); below it, bare tiles

_GLYPHS = {}                       # one board letter per character, built once


def _vdc(k):
    """The k-th term of the base-2 van der Corput sequence: 0, 1/2, 1/4, 3/4, 1/8 ..."""
    f, d = 0.0, 0.5
    while k:
        f += d * (k & 1)
        k >>= 1
        d /= 2
    return f


def spread(kids, around):
    """The order the tree lays a node's children out in (user's call: not
    pattern-code order, which put every big group on one side). `around` (the
    root's children, a full circle): largest first, then each next-largest into the
    middle of the biggest gap left -- van der Corput positions -- so the big groups
    are dealt evenly round the root. Otherwise (a slice of a parent's angle):
    largest in the MIDDLE, sizes falling off to both sides, so a node's big
    children sit on its own line out from the centre."""
    by_size = sorted(kids, key=lambda k: (-len(k["answers"]), k["code"]))
    if around:
        slot = {id(k): _vdc(i) for i, k in enumerate(by_size)}
        return sorted(by_size, key=lambda k: slot[id(k)])
    left, right = [], []
    for i, k in enumerate(by_size):
        (right if i % 2 else left).append(k)
    return left[::-1] + right


def _glyph(ch):
    """The board's letter for `ch`, 1 unit tall, built once per letter."""
    if ch not in _GLYPHS:
        g = crisp_text(ch.upper(), color=TILE_TEXT, weight=BOLD)
        _GLYPHS[ch] = g.scale(1 / g.height)
    return _GLYPHS[ch]


def full_row(word, code, width, centre):
    """A row `width` wide at `centre`: `word` scored as `code`, or typed (black)
    when `code` is None. Real letters only when wide enough to read; below
    FULL_LETTER_W just the tiles, flat (thousands of rows)."""
    if width >= FULL_LETTER_W:
        row = get_typed_row(word) if code is None else get_scored_row(word, code)
        return row.scale(width / row.width).move_to(centre)
    trits = [None] * 5 if code is None else [(code // 3 ** (4 - i)) % 3 for i in range(5)]
    tile = width / (5 + 4 * GAP / TILE)
    sq = [Square(side_length=tile, stroke_width=0, fill_opacity=1.0,
                 fill_color=TILE_EMPTY_FILL if t is None else TILE_STATE[t])
          for t in trits]
    row = VGroup(*sq).arrange(RIGHT, buff=tile * GAP / TILE).move_to(centre)
    if width < FULL_GLYPH_W:
        return row
    # letters too: unreadable this small, but a box with a letter still reads
    # differently from an empty one (user's call). One glyph per letter, built
    # once and copied -- thousands of rows
    return VGroup(row, *[_glyph(ch).copy().scale(tile * LETTER_FRAC).move_to(t)
                         for ch, t in zip(word, sq)])


def full_layout(tree, start):
    """Where every branch of `tree` goes, relative to its root: {path: (centre,
    width, open, angle)}, a path being the tuple of pattern codes from the root;
    the first branch at angle `start`."""
    def count(n):
        return sum(len(k["answers"]) if not k["node"] else count(k["node"])
                   for k in n["kids"])
    total = count(tree)
    k_w = FULL_SCALE_W / math.sqrt(total)
    root_h = FULL_ROOT_W * row_aspect()
    pitch = lambda w: w * row_aspect() * (1 + GAP / TILE)
    out = {}

    def place(node, a0, a1, depth, path):
        a = a0
        for kid in spread(node["kids"], depth == 1):
            key = path + (kid["code"],)
            n = len(kid["answers"])
            span = (a1 - a0) * n / sum(len(k["answers"]) for k in node["kids"])
            mid = a + span / 2
            r = FULL_R * math.log(total / n) / math.log(total)
            w = k_w * math.sqrt(n)
            h = (2 if kid["node"] is not None else 1) * pitch(w)
            off = lambda r: np.array([r * FULL_X_STRETCH * math.cos(mid), r * math.sin(mid), 0.0])
            # a node that would overlap the root is pushed out along its angle
            # until it clears it by FULL_CLEAR (nothing else moves)
            while (abs(off(r)[0]) < (FULL_ROOT_W + w) / 2 + FULL_CLEAR
                   and abs(off(r)[1]) < (root_h + h) / 2 + FULL_CLEAR):
                r *= 1.03
            out[key] = (off(r), w, kid["node"] is not None, mid)
            if kid["node"] is not None:
                place(kid["node"], a, a + span, depth + 1, key)
            a += span
    place(tree, start, start + 2 * math.pi, 1, ())
    return out


def full_start(tree, key, angle):
    """The start angle that puts branch `key` of `tree` at `angle` -- turning the
    whole tree (spans do not depend on where it starts)."""
    mid = full_layout(tree, FULL_START)[key][3]
    return FULL_START + angle - mid


def full_tree(tree, origin=ORIGIN, start=FULL_START):
    """Every node and line of `tree`, placed radially round `origin`. Returns
    (root row, {path: [colouring row, next-guess row (open branches only)]},
    {path: line in from its parent}, {path: node centre})."""
    layout = full_layout(tree, start)
    root = full_row(tree["guess"], None, FULL_ROOT_W, origin)
    nodes, lines, cents = {}, {}, {}

    def walk(node, path):
        for kid in node["kids"]:
            key = path + (kid["code"],)
            off, w, open_, _ = layout[key]
            c = origin + off
            cents[key] = c
            if not open_:                                  # a win: the green row
                nodes[key] = [full_row(node["guess"], kid["code"], w, c)]
            else:                                          # colouring + next guess
                p = w * row_aspect() * (1 + GAP / TILE)
                nodes[key] = [full_row(node["guess"], kid["code"], w, c + UP * p / 2),
                              full_row(kid["node"]["guess"], None, w, c + DOWN * p / 2)]
            parent = origin if not path else cents[path]
            lines[key] = Line(parent, c, color=WHITE, stroke_width=FULL_LINE_W,
                              stroke_opacity=FULL_LINE_OPACITY).set_z_index(-1)
            if open_:
                walk(kid["node"], key)
    walk(tree, ())
    return root, nodes, lines, cents
