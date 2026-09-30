"""The colour groups a guess splits the answers into, laid out on the frame.

    slots, scale, heads, groups = layout(DATA, "piggy", header=True)   # words
    rows = scored_headers("piggy", groups, heads, scale)              # PIGGY rows
    dots = dot_layout(DATA, "piggy")                                  # every answer

Scene 04 introduced the groups (04d-04i); scene 06 opens on 04i's end frame and
turns it into dots. Both scenes place groups through this module, so the two
frames are the same frame. (Extracted from scenes/04new_rules.py unchanged — the
scatter seed still says "04:", which is what keeps 04's renders and 06a identical.)

GROUPS ARE SCATTERED, NOT PACKED IN ROWS (`_scatter`): best-candidate sampling over
the region below the guess, biggest first, everything shrinking 5% and starting
over if a group finds no spot. Each group's footprint is the room an oval round it
took; no oval is drawn (user's call), but the clusters keep that spacing.

A dot row's tile stroke shrinks with it (the scene sets it from the row's width);
04's headers keep the board's STROKE, as they always had.

`dot_layout` is 06b's version: EVERY group of the guess, every answer a dot in a
square-ish grid, and the group's scored row as wide as sqrt(size) dot pitches — so
a row's dimensions go as the square root of its dots (script 06b). Seeded, so a
render is repeatable; change the seed string for a different scatter.
"""
import math
import random

import numpy as np

from config import *
from assets.board import get_scored_row, STROKE, TILE, GAP
from assets.pigpen import WORD_W

# ── the guess, top centre ─────────────────────────────────────────────────────
GUESS_Y = 3.7
GUESS_SCALE = 1.2

# ── words in a group (04) ─────────────────────────────────────────────────────
GROUP_SCALE = 0.45         # word size inside a group, before any fit-to-frame
CELL_GAP = 0.2             # between words in a group (group size)
CELL_DY = 0.26             # word row pitch in a group (group size)
ELLIPSE_K = 1.3            # a group's footprint / its word grid — the room an oval
ELLIPSE_PAD = 0.4          #   round it took; no oval is drawn (user's call), but the
                           #   clusters keep that spacing
BLOCK_GAP = 0.3            # least clear space between two groups' footprints
SCATTER_TRIES = 300        # candidate spots per oval
REGION_HALF_W = 7.7        # ovals stay inside x in [-7.7, 7.7]
REGION_TOP, REGION_BOT = 2.95, -4.2
HEADER_W = 1.9             # a scored row's width atop its oval
HEADER_H = 0.45            # room reserved above an oval for that row
EDGE_SLOTS = 12            # evenly spaced points round the border for edge ovals
EDGE_TOP_CLEAR = 4.5       # no edge oval on the top edge within this of centre
EDGE_OUT = 0.25            # edge oval centre beyond the edge, as a fraction of
                           # its half-size (0 = centred on the edge)

# ── dots (06b) ────────────────────────────────────────────────────────────────
DOT_PITCH = 0.16           # dot spacing, before any fit-to-frame
DOT_FRAC = 0.32            # dot radius / pitch
DOT_PAD = 0.2              # footprint padding round a dot cluster
DOT_HEAD_GAP = 0.08        # between a scored row and its dots (x pitch-scale)
RANK_GAP = 0.05            # between blocks in the sorted layout (DOT_PAD adds more)
DOT_BLOCK_GAP = 0.12       # least clear space between two dot groups
NEAR_SIGMA = 1.0           # spread of the candidates clustered round a target
DOT_REGION_TOP = 4.2       # the guess has left by then: dots take the whole frame,
                           # as far from the top as REGION_BOT is from the bottom
WORD_PAD = 0.3             # footprint padding round a packed word block (07)
WORD_HEAD_GAP = 0.08       # between a packed block's scored rows and its words (07)
HEAD_ROW_GAP = GAP / TILE  # between two stacked scored rows, per row height — the
                           # board's own row spacing (07)

# ── groups entering and leaving (06b-f, 07) ───────────────────────────────────
ENTER_FROM = np.array([0.0, (DOT_REGION_TOP + REGION_BOT) / 2, 0.0])
ENTER_DIST = 10.0          # how far beyond its spot an entering group starts
EDGE_CLEAR = 0.3           # how far past its nearest edge a leaving thing goes
ROW_ASPECT = None          # a scored row's height / width, measured on first use


def _gap(a, b):
    """Clear space between two boxes ((x, y), w, h); negative if they overlap."""
    (ax, ay), aw, ah = a
    (bx, by), bw, bh = b
    return max(abs(ax - bx) - (aw + bw) / 2, abs(ay - by) - (ah + bh) / 2)


def _border_point(s):
    """The point at arc length `s` round the frame's edge, clockwise from the
    top-left corner, and the outward normal there."""
    X, Y = config.frame_x_radius, config.frame_y_radius
    s %= 4 * (X + Y)
    for (x0, y0), (dx, dy), n, length in [((-X, Y), (1, 0), (0, 1), 2 * X),
                                          ((X, Y), (0, -1), (1, 0), 2 * Y),
                                          ((X, -Y), (-1, 0), (0, -1), 2 * X),
                                          ((-X, -Y), (0, 1), (-1, 0), 2 * Y)]:
        if s <= length:
            return np.array([x0 + dx * s, y0 + dy * s]), np.array(n, float)
        s -= length


def _place_edges(sizes, f, rng_phase):
    """Hang edge ovals on the frame's border: EDGE_SLOTS evenly spaced points round
    it (the top middle kept clear for the guess), each oval's centre pushed EDGE_OUT
    of its half-size beyond the edge. A slot whose oval would hit one already hung
    is skipped. Returns [(index into sizes, box)]."""
    X, Y = config.frame_x_radius, config.frame_y_radius
    perim = 4 * (X + Y)
    hung, k = [], 0
    for j in range(EDGE_SLOTS):
        if k >= len(sizes):
            break
        p, n = _border_point((rng_phase + j / EDGE_SLOTS) * perim)
        if n[1] > 0 and abs(p[0]) < EDGE_TOP_CLEAR:
            continue
        w, h = sizes[k][0] * f, sizes[k][1] * f
        c = p + n * np.array([w, h]) / 2 * EDGE_OUT
        box = ((c[0], c[1]), w, h)
        if all(_gap(box, b) >= BLOCK_GAP for _, b in hung):
            hung.append((k, box))
            k += 1
    return hung


def _scatter(sizes, edge_sizes, seed, block_gap=BLOCK_GAP, region_top=REGION_TOP,
             blocked=(), targets=None):
    """Centres for the interior ovals (sizes (w, h)), SCATTERED over the group
    region rather than packed in rows, around edge ovals hung first on the border.
    Best-candidate sampling: biggest oval first, each takes whichever of
    SCATTER_TRIES random spots leaves the widest gap to everything placed, and no
    spot closer than `block_gap` counts. If an oval finds no spot, everything
    shrinks 5% and the placement starts over. `blocked` boxes ((x, y), w, h) are
    kept clear, like boxes already placed (06's corner label).

    With `targets` (a point, or None, per oval), an oval WITH a target takes the
    valid spot NEAREST it, from candidates half spread over the region and half
    clustered round it (NEAR_SIGMA), and those ovals are placed first — 06c/d's
    pattern anchoring. An oval without one is scattered as usual; with no targets
    at all, nothing here changes.

    Seeded, so a render is repeatable; change the seed string for a different
    scatter. Returns (shrink factor, interior centres, [(edge index, centre)])."""
    rng = random.Random(seed)
    phase = rng.random()
    anchored = (lambda i: targets is not None and targets[i] is not None)
    order = sorted(range(len(sizes)),
                   key=lambda i: (not anchored(i), -sizes[i][0] * sizes[i][1]))
    f = 1.0
    while True:
        hung = _place_edges(edge_sizes, f, phase)
        boxes = [b for _, b in hung] + list(blocked)
        placed = {}
        for i in order:
            w, h = sizes[i][0] * f, sizes[i][1] * f
            xr, ylo, yhi = REGION_HALF_W - w / 2, REGION_BOT + h / 2, region_top - h / 2
            if xr < 0 or ylo > yhi:
                break
            best, best_gap = None, -1.0
            if not anchored(i):
                for _ in range(SCATTER_TRIES):
                    box = ((rng.uniform(-xr, xr), rng.uniform(ylo, yhi)), w, h)
                    gap = min((_gap(box, b) for b in boxes), default=1e9)
                    if gap >= block_gap and gap > best_gap:
                        best, best_gap = box, gap
            else:
                tx, ty = targets[i][0], targets[i][1]
                best_d = None
                for k in range(SCATTER_TRIES):
                    if k % 2:
                        x, y = rng.gauss(tx, NEAR_SIGMA), rng.gauss(ty, NEAR_SIGMA)
                        x, y = min(max(x, -xr), xr), min(max(y, ylo), yhi)
                    else:
                        x, y = rng.uniform(-xr, xr), rng.uniform(ylo, yhi)
                    box = ((x, y), w, h)
                    if min((_gap(box, b) for b in boxes), default=1e9) < block_gap:
                        continue
                    d = (x - tx) ** 2 + (y - ty) ** 2
                    if best_d is None or d < best_d:
                        best, best_d = box, d
            if best is None:
                break
            placed[i] = best
            boxes.append(best)
        if len(placed) == len(sizes):
            return (f, [placed[i][0] for i in range(len(sizes))],
                    [(k, b[0]) for k, b in hung])
        f *= 0.95


def layout(data, guess, header=False, chain=False):
    """Word centres, ovals and header positions for `guess`'s shown groups: the
    interior ovals scattered over the frame and the edge ovals hung off its border
    (`_scatter`), the words in a tidy grid inside each. `chain` takes 04e's
    carry-over groups (lists_data) instead of the size-target ones.
    Returns (slots {word: centre}, scale, header centres, groups) — the last two
    in one order, edge groups after interior ones. (An 'oval' throughout is a
    group's footprint; none is drawn.)"""
    key = "chain" if chain else "groups"
    inner, edge = data[key][guess], data[key + "_edge"][guess]
    ww, cg, dy = WORD_W * GROUP_SCALE, CELL_GAP, CELL_DY
    hh = HEADER_H if header else 0.0

    def block(g):
        n = len(g["members"])
        nc = math.ceil(math.sqrt(n))
        nr = math.ceil(n / nc)
        gw, gh = nc * ww + (nc - 1) * cg, nr * dy
        return dict(g=g, nc=nc, ew=gw * ELLIPSE_K + ELLIPSE_PAD,
                    eh=gh * ELLIPSE_K + ELLIPSE_PAD)

    ib, eb = [block(g) for g in inner], [block(g) for g in edge]
    f, centres, hung = _scatter([(b["ew"], b["eh"] + hh) for b in ib],
                                [(b["ew"], b["eh"] + hh) for b in eb],
                                f"04:{guess}:{header}:{chain}")
    placed = list(zip(ib, centres)) + [(eb[k], c) for k, c in hung]
    slots, headers, groups = {}, [], []
    for b, (bx, by) in placed:
        cx, cy = bx, by - hh * f / 2               # the group sits under its header
        headers.append(np.array([cx, cy + b["eh"] * f / 2, 0.0]))
        groups.append(b["g"])
        members = b["g"]["members"]
        for word, (ox, oy) in zip(members, grid_cells(len(members))):
            slots[word] = np.array([cx + ox * (ww + cg) * f, cy + oy * dy * f, 0.0])
    return slots, GROUP_SCALE * f, headers, groups


def grid_cells(n):
    """THE way a group of words is gridded in this video (04's): ceil(sqrt(n))
    columns, filled row by row, a short last row centred. Returns each word's
    (column, row) offset from the grid's centre, in pitches, rows counting UP
    (the first row is on top) -- multiply by the caller's pitches and add its
    centre. Every word grid goes through here, so there is one rule to follow."""
    nc = max(1, math.ceil(math.sqrt(n)))
    nr = math.ceil(n / nc)
    cells = []
    for k in range(n):
        i, j = divmod(k, nc)
        in_row = min(nc, n - i * nc)
        cells.append((j - (in_row - 1) / 2, (nr - 1) / 2 - i))
    return cells


def scored_row(guess, code, width, centre, stroke=STROKE):
    """`guess` scored as `code`, `width` wide at `centre`, tile stroke `stroke`
    (04's headers keep the board's; at dot size a fixed STROKE swamps the tiles)."""
    row = get_scored_row(guess, code)
    row.scale(width / row.width).move_to(centre)
    for t in row.tiles[0]:
        t.set_stroke(width=stroke)
    return row


def scored_headers(guess, groups, heads, scale):
    """04i's coloured `guess` row atop each group, HEADER_W wide at group size."""
    return [scored_row(guess, g["code"], HEADER_W * scale / GROUP_SCALE, c)
            for g, c in zip(groups, heads)]


def row_aspect():
    """A scored row's height / width (the board's tile and gap proportions)."""
    global ROW_ASPECT
    if ROW_ASPECT is None:
        r = get_scored_row("aaaaa", 0)
        ROW_ASPECT = r.height / r.width
    return ROW_ASPECT


def _dot_block(g):
    """A dot group's block at scale 1: its dots in a square-ish grid (nc columns,
    nr rows) under its scored row, sqrt(size) pitches wide; w and h include
    DOT_PAD."""
    p, asp, n = DOT_PITCH, row_aspect(), g["size"]
    nc = math.ceil(math.sqrt(n))
    nr = math.ceil(n / nc)
    rw = p * math.sqrt(n)
    return dict(nc=nc, nr=nr, rw=rw, rh=rw * asp,
                w=max(nc * p, rw) + DOT_PAD, h=nr * p + rw * asp + DOT_HEAD_GAP + DOT_PAD)


def _fill(groups, bs, centres, f):
    """Every block's dots and row, the blocks centred at `centres`, all at scale
    `f`. Dots fill each grid row by row, left to right, in member order. Returns
    (dots {word: centre}, row centres, row widths, dot radius)."""
    p = DOT_PITCH
    dots, rows, widths = {}, [], []
    for g, b, (bx, by) in zip(groups, bs, centres):
        top = by + b["h"] * f / 2 - DOT_PAD * f / 2
        rows.append(np.array([bx, top - b["rh"] * f / 2, 0.0]))
        widths.append(b["rw"] * f)
        gy = top - (b["rh"] + DOT_HEAD_GAP) * f          # top of the dot grid
        nc, n = b["nc"], g["size"]
        for k, word in enumerate(g["members"]):
            i, j = divmod(k, nc)
            n_in_row = min(nc, n - i * nc)
            dots[word] = np.array([bx + (j - (n_in_row - 1) / 2) * p * f,
                                   gy - (i + 0.5) * p * f, 0.0])
    return dots, rows, widths, DOT_FRAC * p * f


def dot_layout(data, guess, seed=None, blocked=(), anchors=None):
    """06b: EVERY group of `guess` (lists_data's `full`), each answer a dot in a
    square-ish grid, the group's scored row atop it, sqrt(size) dot pitches wide —
    so the row's width and height both go as the square root of its dots. Groups
    scattered as in `layout`, no edge groups: all of them are on the frame, and
    over the WHOLE frame (DOT_REGION_TOP) but for the `blocked` boxes — the guess
    has left the top centre (06: for the corner, kept clear via `blocked`).

    `anchors` ({pattern code: where that pattern's row is now}) CONTINUES the
    layout on screen (06c/d): a group whose pattern is already on screen keeps its
    row where it is, as near as it fits; the rest scatter round them. (Which dot
    goes to which slot is the scene's business — 06 matches them by distance.)
    (Placing groups at their members' CENTROID was tried and dropped, user's call:
    a new group draws from all over, so every centroid sat mid-frame and the big
    groups just bunched up in the centre.)

    Returns (groups, dots {word: centre}, row centres, row widths, dot radius) —
    groups in lists_data's order, the two lists in the same order."""
    groups = data["full"][guess]
    bs = [_dot_block(g) for g in groups]
    targets = None
    if anchors is not None:           # a row's spot, as its box's centre (unshrunk)
        targets = [None if g["code"] not in anchors else
                   anchors[g["code"]] - np.array([0.0, (b["h"] - DOT_PAD - b["rh"]) / 2, 0.0])
                   for g, b in zip(groups, bs)]
    f, centres, _ = _scatter([(b["w"], b["h"]) for b in bs], [],
                             seed or f"06:{guess}:dots", block_gap=DOT_BLOCK_GAP,
                             region_top=DOT_REGION_TOP, blocked=blocked, targets=targets)
    return (groups, *_fill(groups, bs, centres, f))


def _pack(bs, left, right, top, bottom, center_last=False):
    """Shelf-pack blocks (dicts with w, h at scale 1) in reading order inside x in
    [left, right], y in [bottom, top]: left to right along a row, then the next row
    down; blocks in a row top-aligned and spread to fill the row's width, the last
    row excepted (centred instead with `center_last`). One scale for everything, the
    largest that fits. Returns (scale, block centres)."""
    gap = RANK_GAP

    def shelves(f):
        out, cur, x = [], [], 0.0
        for k, b in enumerate(bs):
            w = b["w"] * f
            if cur and x + gap + w > right - left:
                out.append(cur)
                cur, x = [], 0.0
            x += (gap if cur else 0.0) + w
            cur.append(k)
        out.append(cur)
        return out

    def height(f):
        # a block wider than the region fits nowhere: the shelves would still
        # take it (alone on a row) and it would spill off the sides
        if max(b["w"] for b in bs) * f > right - left:
            return math.inf
        return sum(max(bs[k]["h"] * f for k in sh) for sh in shelves(f)) + \
            gap * (len(shelves(f)) - 1)

    lo, hi = 0.01, 3.0                         # the largest scale that fits
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if height(mid) <= top - bottom else (lo, mid)
    f = lo
    centres = [None] * len(bs)
    y = top
    rows_of = shelves(f)
    for i, sh in enumerate(rows_of):
        ws = [bs[k]["w"] * f for k in sh]
        spare = (right - left) - sum(ws) - gap * (len(sh) - 1)
        last = i == len(rows_of) - 1
        g_eff = gap + (spare / (len(sh) - 1) if len(sh) > 1 and not last else 0)
        x = left + (spare / 2 if last and center_last else 0.0)
        for k, w in zip(sh, ws):
            centres[k] = (x + w / 2, y - bs[k]["h"] * f / 2)
            x += w + g_eff
        y -= max(bs[k]["h"] * f for k in sh) + gap
    return f, centres


def ranked_layout(data, guess, left, right=REGION_HALF_W, top=DOT_REGION_TOP,
                  bottom=REGION_BOT):
    """06, the SORTED version: every group of `guess` as a dot block (as
    `dot_layout`), packed in reading order BY SIZE — largest first, left to right
    along a row, then the next row down — inside x in [left, right], y in [bottom,
    top]. Blocks in a row are top-aligned (so their scored rows line up) and spread
    to fill the row's width, the last row excepted; one scale for everything, the
    largest that fits. Ties in size keep lists_data's order (by pattern code).

    Returns what `dot_layout` does, groups in rank order; the dots dict is in that
    order too (group by group, each grid row by row), which is the SEQUENCE the
    scene moves dots along."""
    groups = sorted(data["full"][guess], key=lambda g: (-g["size"], g["code"]))
    bs = [_dot_block(g) for g in groups]
    f, centres = _pack(bs, left, right, top, bottom)
    return (groups, *_fill(groups, bs, centres, f))


# ── words packed by size (07) ─────────────────────────────────────────────────
WORD_ASPECTS = np.geomspace(0.2, 5.0, 33)   # grid shapes tried: columns ~ sqrt(n * a)


def _word_block(n, heads, aspect, nc=None):
    """A block of `n` words at scale 1 (GROUP_SCALE words, 04's CELL_GAP/CELL_DY
    pitches) under a stack of `heads` scored rows, each AS WIDE AS THE WORD GRID --
    sized by its group, as c's rows span their dots (user's call). The grid has about
    sqrt(n * aspect * dy / (ww + cg)) columns — aspect 1 makes its AREA square-ish.
    `nc` fixes the column count instead."""
    ww, cg, dy = WORD_W * GROUP_SCALE, CELL_GAP, CELL_DY
    if nc is None:
        nc = min(n, max(1, math.ceil(math.sqrt(n * aspect * dy / (ww + cg)))))
    nr = math.ceil(n / nc)
    gw = nc * ww + (nc - 1) * cg
    rh = gw * row_aspect()
    hh = heads * rh + (heads - 1) * rh * HEAD_ROW_GAP + WORD_HEAD_GAP if heads else 0.0
    return dict(nc=nc, nr=nr, hh=hh, rh=rh, gw=gw, w=gw + WORD_PAD,
                h=nr * dy + hh + WORD_PAD)


def ranked_word_layout(groups, left, right=REGION_HALF_W, top=DOT_REGION_TOP,
                       bottom=REGION_BOT, heads=1, ncols=None):
    """07: `groups` (in the order given — pass them largest first) as WORD blocks,
    packed as `ranked_layout` packs dot blocks, the last row centred; each block
    under a stack of `heads` scored rows as wide as its word grid. The grid shape is the one of WORD_ASPECTS (the same for every
    block) that gives the LARGEST words. One block alone sits centred at the top.
    `ncols` (one per group) FIXES the column counts instead -- for a group that is
    already on screen and should keep its arrangement while it resizes (07f).

    Returns (slots {word: centre}, word scale, [[header centre, top first] per
    block], [header width per block])."""
    best = None
    for a in (WORD_ASPECTS if ncols is None else [1.0]):
        bs = [_word_block(g["size"], heads, a, None if ncols is None else ncols[i])
              for i, g in enumerate(groups)]
        f, centres = _pack(bs, left, right, top, bottom, center_last=True)
        if best is None or f > best[0]:
            best = (f, centres, bs)
    f, centres, bs = best
    ww, cg, dy = WORD_W * GROUP_SCALE, CELL_GAP, CELL_DY
    slots, hds = {}, []
    for g, b, (bx, by) in zip(groups, bs, centres):
        top_y = by + (b["h"] - WORD_PAD) * f / 2
        hds.append([np.array([bx, top_y - (k * b["rh"] * (1 + HEAD_ROW_GAP) + b["rh"] / 2) * f,
                              0.0]) for k in range(heads)])
        gy = top_y - b["hh"] * f                     # top of the word grid
        nc, n = b["nc"], g["size"]
        for k, word in enumerate(g["members"]):
            i, j = divmod(k, nc)
            n_in_row = min(nc, n - i * nc)
            slots[word] = np.array([bx + (j - (n_in_row - 1) / 2) * (ww + cg) * f,
                                    gy - (i + 0.5) * dy * f, 0.0])
    return slots, GROUP_SCALE * f, hds, [b["gw"] * f for b in bs]


def enter_from_beyond(mob, origin=ENTER_FROM, dist=ENTER_DIST):
    """Move `mob` `dist` further out along the ray from `origin` through it — where
    a group entering the frame starts (06b's radial slide-in). Returns the spot it
    left, for `mob.animate.move_to(home)`."""
    home = mob.get_center()
    d = home - origin
    mob.shift(d / (np.linalg.norm(d) or 1.0) * dist)
    return home


def edge_out(mob, clear=EDGE_CLEAR):
    """Just beyond the frame edge NEAREST `mob`, straight out — how a group leaves
    (06's switches), so none crosses the frame."""
    c = mob.get_center()
    X, Y = config.frame_x_radius, config.frame_y_radius
    gaps = [(X - c[0], RIGHT, mob.width), (X + c[0], LEFT, mob.width),
            (Y - c[1], UP, mob.height), (Y + c[1], DOWN, mob.height)]
    d, v, size = min(gaps, key=lambda g: g[0])
    return c + v * (d + size / 2 + clear)
