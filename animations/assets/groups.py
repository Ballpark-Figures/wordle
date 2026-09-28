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
from assets.board import get_scored_row, STROKE
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
DOT_BLOCK_GAP = 0.12       # least clear space between two dot groups
NEAR_SIGMA = 1.0           # spread of the candidates clustered round a target
DOT_REGION_TOP = 4.2       # the guess has left by then: dots take the whole frame,
                           # as far from the top as REGION_BOT is from the bottom
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

    With `targets` (a point per oval), each oval instead takes the valid spot
    NEAREST its target, from candidates half spread over the region and half
    clustered round the target (NEAR_SIGMA) — 06c/d's continuity, so a group lands
    near where its members already are. Without them the sampling is untouched.

    Seeded, so a render is repeatable; change the seed string for a different
    scatter. Returns (shrink factor, interior centres, [(edge index, centre)])."""
    rng = random.Random(seed)
    phase = rng.random()
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][0] * sizes[i][1])
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
            if targets is None:
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
        members, nc = b["g"]["members"], b["nc"]
        nr = math.ceil(len(members) / nc)
        for k, word in enumerate(members):
            i, j = divmod(k, nc)
            n_in_row = min(nc, len(members) - i * nc)
            wx = cx + (j - (n_in_row - 1) / 2) * (ww + cg) * f
            wy = cy + ((nr - 1) / 2 - i) * dy * f
            slots[word] = np.array([wx, wy, 0.0])
    return slots, GROUP_SCALE * f, headers, groups


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


def dot_layout(data, guess, seed=None, blocked=(), prev=None):
    """06b: EVERY group of `guess` (lists_data's `full`), each answer a dot in a
    square-ish grid, the group's scored row atop it, sqrt(size) dot pitches wide —
    so the row's width and height both go as the square root of its dots. Groups
    scattered as in `layout`, no edge groups: all of them are on the frame, and
    over the WHOLE frame (DOT_REGION_TOP) but for the `blocked` boxes — the guess
    has left the top centre (06: for the corner, kept clear via `blocked`).

    `prev` ({word: where its dot is now}) makes the layout CONTINUE the one on
    screen (06c/d): each group lands as near as it can to its members' centroid,
    and its dots fill the grid in the order they sit now — top to bottom into rows,
    left to right within one — so neighbours arrive as neighbours.

    Returns (groups, dots {word: centre}, row centres, row widths, dot radius) —
    groups in lists_data's order, the two lists in the same order."""
    groups = data["full"][guess]
    p, asp = DOT_PITCH, row_aspect()

    def block(g):
        n = g["size"]
        nc = math.ceil(math.sqrt(n))
        nr = math.ceil(n / nc)
        rw = p * math.sqrt(n)
        return dict(nc=nc, nr=nr, rw=rw, rh=rw * asp,
                    w=max(nc * p, rw) + DOT_PAD, h=nr * p + rw * asp + DOT_HEAD_GAP + DOT_PAD)

    bs = [block(g) for g in groups]
    targets = None
    if prev is not None:
        targets = [np.mean([prev[w] for w in g["members"]], axis=0) for g in groups]
    f, centres, _ = _scatter([(b["w"], b["h"]) for b in bs], [],
                             seed or f"06:{guess}:dots", block_gap=DOT_BLOCK_GAP,
                             region_top=DOT_REGION_TOP, blocked=blocked, targets=targets)
    dots, rows, widths = {}, [], []
    for g, b, (bx, by) in zip(groups, bs, centres):
        top = by + b["h"] * f / 2 - DOT_PAD * f / 2
        rows.append(np.array([bx, top - b["rh"] * f / 2, 0.0]))
        widths.append(b["rw"] * f)
        gy = top - (b["rh"] + DOT_HEAD_GAP) * f          # top of the dot grid
        nc, n = b["nc"], g["size"]
        members = g["members"]
        if prev is not None:                 # rows by height, each row left to right
            by_y = sorted(members, key=lambda w: -prev[w][1])
            members = [w for i in range(0, n, nc)
                       for w in sorted(by_y[i:i + nc], key=lambda w: prev[w][0])]
        for k, word in enumerate(members):
            i, j = divmod(k, nc)
            n_in_row = min(nc, n - i * nc)
            dots[word] = np.array([bx + (j - (n_in_row - 1) / 2) * p * f,
                                   gy - (i + 0.5) * p * f, 0.0])
    return groups, dots, rows, widths, DOT_FRAC * p * f
