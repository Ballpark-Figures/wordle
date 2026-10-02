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
  f pie        — move up to "Second Guess" alone; then the pie fans in      (17f, VO 3)
  g table      — move up to "Average Words Remaining" alone                 (17g, VO 4)
  h fill_320   — the 3G2Y row and its bold 1 rise in                         (17h, VO 4)
  i fill_230   — the 2G3Y row and its bold 1                                 (17i, VO 5)
  j bared      — BARED (scored) / BEARD / BREAD, stacked bottom middle, rise
                 together from below the frame                              (17j, VO 5)
  k bared_off  — the three slide back off the bottom, together, no fade     (17k, VO 5)
  l-q fill_0 .. fill_5 — rows + values, one gray-count group per beat,
                 staggered upward fade                                      (17l-q, VO 6)
  r breakdown  — title flips to Strategy Breakdown (Second Guess); values out,
                 legend in, the combinations slide left                     (17r, VO 7)
  s-x bars_0, bars_5, bars_1 .. bars_4 — the bars grow, a group per beat     (17s-x, VO 7-11)
  y third      — title flips to (Third Guess); bars morph to the third guess's (17y, VO 12)
  z fourth     — title flips to (Fourth Guess); bars morph to the fourth's    (17z, VO 12)

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
  17f pie             bpkfigures.pie_chart get_pie_chart, callout labels, fan_all
  17f/g "move up"     `_move_up`: the old screen slides up a frame as the new one rises
                      from below — 15's camera-pan look (strategy_line._pan_down),
                      done by moving content since nothing here lives off-frame
  titles              crisp_text, WHITE, FONT_SIZE_LG (08's / 13's), FadeIn with content
  title changes       assets/flip.py Flip / flip() (the script's "flip")
  table combinations  `_combo` (17c's) at ROW_TILE with NO extra block gap (the user's
                      call), left-aligned; each row arrives with its value
  table values        crisp_text FONT_SIZE_SM, centred in the column; 1 bold (17h)
  table rows in       LaggedStart FadeIn(shift=UP*0.3), lag 0.12 — 04new_rules.py:156
  17j words           assets/board.py get_scored_row (BARED) / get_typed_row, stacked at
                      the bottom middle; slide in from / out below the frame, no fade
  bars                bpkfigures.bar_graph get_stacked_bar (added for this scene),
                      segments compatible / something else / both / all new (all new
                      on the right: the user's call), legend in that order,
                      entrance grow_bars(edge=LEFT), ply changes Transform per bar
  bar / pie colours   style.py LIGHT_BLUE (compatible), LIGHT_RED (all new),
                      LIGHT_PURPLE (both, all-gray row only), MUTED_GREY (something else)
  numbers             assets/color_combos_data.py -> color_combos_cache.json (top 1000
                      openers' optimal trees; definitions in that module's docstring)
  colours             BOARD_NAVY via WordleBoardScene; tiles config.py TILE_STATE

LAYOUT CHOICES, flagged:
  - 17b: the 5 in one column on the left, the 30 in three columns of ten on the right,
    in their 243-grid order down each column, all at PART_TILE; equal gaps edge -> 5 -> 30 -> edge
    (the user's call).
  - 17c: a rectangular grid (the user's call): one column per green count, all greens
    in the last column, each column from the top, most yellows first; combinations
    centred in fixed-pitch cells.
  - 17g-q: the table centred (the user's call); 17r slides the combinations left to
    X_COMBO so the bars (from X_VAL) and the legend fit to their right.
  - 17j: BEARD and BREAD unscored (typed rows).
  - "Something Else" grey (no colour in the script).
On-screen text: the titles, the pie's wedge names + percentages, the table values and
the legend (all column 2's). 243 / 5 / 30 / 21 / 19 are spoken, not shown.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.colorings import level, code, trits, slot, TILE_BUFF, GRID_BUFF, tile
from assets.stacks_view import WHOOSH_GAIN
from assets.board import get_scored_row, get_typed_row
from assets.flip import Flip, flip
from assets import color_combos_data
from bpkfigures.pie_chart import get_pie_chart
from bpkfigures.bar_graph import get_stacked_bar, grow_bars

DATA = color_combos_data.load()

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

# ── 17f-z: the pie, the table, the bars ───────────────────────────────────────
TITLE_Y = 3.85             # every title's centre
PIE_TITLE = "Second Guess"
PIE_NAMES = ("Compatible Word", "All New Letters", "Something Else")
PIE_RADIUS = 2.3
PIE_CENTER = DOWN * 0.45
TABLE_TITLE = "Average Words Remaining"
BREAKDOWN = "Strategy Breakdown ({} Guess)"
# segment order and colours of a breakdown bar; "both" is compatible AND all new
# letters, which only the all-gray row can show — purple (script 17r)
KINDS = ("compatible", "both", "new", "else")
KIND_COLORS = {"compatible": LIGHT_BLUE, "both": LIGHT_PURPLE, "new": LIGHT_RED,
               "else": MUTED_GREY}
ROW_TILE = 0.25            # table combinations' tile side; also a bar's height
ROW_PITCH = 0.34
GROUP_GAP = 0.16           # extra gap between gray-count groups (script: "slight gaps")
TOP_ROW_Y = 3.1
VAL_GAP = 0.6              # combinations' right edge to the values column
X_COMBO = -6.6             # combinations' left edge once the bars are in (17r on)
X_VAL = -4.5               # the bars' left edge
BAR_LEN = 8.1
VALUE_SIZE = FONT_SIZE_SM
LEGEND_X = 4.3             # legend swatches' left edge
LEGEND_SWATCH = 0.3
LEGEND_PITCH = 0.55
WORD_TILE = 0.6            # 17j: BARED / BEARD / BREAD, stacked, bottom middle
WORD_PITCH = 0.78          # row pitch in the stack
WORD_MARGIN = 0.4          # stack's distance from the frame's bottom edge
ROW_RISE = 0.3             # table rows' staggered upward fade (04's / 10's)
ROW_LAG = 0.12
MOVE_UP_RT = 1.2           # a "move up" to the next screen
ROWS = [tuple(int(ch) for ch in k) for k in DATA["rows"]]
# segment order of a breakdown bar, left to right: all new letters on the RIGHT
# (the user's call); "both" (compatible AND all new) sits next to it
BAR_ORDER = ("compatible", "else", "both", "new")


def _key(combo):
    return "".join(map(str, combo))


def _row_y(i, combo):
    """Row i of the table; one GROUP_GAP more per gray count above it."""
    return TOP_ROW_Y - i * ROW_PITCH - combo[2] * GROUP_GAP


def _title(text):
    return crisp_text(text, color=WHITE, font_size=FONT_SIZE_LG).move_to([0, TITLE_Y, 0])


def _table_xs():
    """(combos' left edge, values column centre) with the table — combinations plus
    values — centred on the frame (the user's call)."""
    combo_w = _combo(5, 0, 0, ROW_TILE).width
    col_w = crisp_text("305.7", font_size=VALUE_SIZE).width
    left = -(combo_w + VAL_GAP + col_w) / 2
    return left, left + combo_w + VAL_GAP + col_w / 2


def _value(v, y, cx):
    """1 in bold, anything else to one decimal (script 17h), centred in its column
    (the user's call)."""
    one = abs(v - 1) < 1e-9
    s = "1" if one else f"{v:.1f}"
    assert one or s != "1.0", v
    return crisp_text(s, color=WHITE, font_size=VALUE_SIZE,
                      weight=BOLD if one else NORMAL).move_to([cx, y, 0])


def _bar(ply, combo, y):
    shares = DATA["bars"][str(ply)][_key(combo)]
    return get_stacked_bar([shares[k] for k in BAR_ORDER],
                           [KIND_COLORS[k] for k in BAR_ORDER],
                           length=BAR_LEN, height=ROW_TILE).shift([X_VAL, y, 0])


def _legend():
    entries = VGroup()
    for name, kind in (("Compatible Word", "compatible"), ("Something Else", "else"),
                       ("All New Letters", "new")):                 # the bars' order
        sw = Square(side_length=LEGEND_SWATCH, fill_color=KIND_COLORS[kind],
                    fill_opacity=1, stroke_width=0)
        lab = crisp_text(name, color=WHITE, font_size=VALUE_SIZE)
        entries.add(VGroup(sw, lab).arrange(RIGHT, buff=0.15))
    entries.arrange(DOWN, buff=LEGEND_PITCH - LEGEND_SWATCH, aligned_edge=LEFT)
    return entries.move_to([LEGEND_X + entries.width / 2, 0, 0])


def _counts(c):
    t = trits(c)
    return (t.count(2), t.count(1), t.count(0))


def _block_w(cols, size):
    """Width of `cols` columns of five-tile (grid-spaced) rows at tile side `size`."""
    w = size * (5 + 4 * GRID_BUFF)
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
    w = size * (5 + 4 * GRID_BUFF)
    px, py = w + PART_COL_GAP * size, size * (1 + PART_ROW_GAP)
    nr = -(-n // cols)
    return [np.array([cx + (k // nr - (cols - 1) / 2) * px,
                      ((nr - 1) / 2 - k % nr) * py, 0.0]) for k in range(n)]


def _combo(g, y, b, size, block_gap=BLOCK_GAP):
    """g greens, y yellows, b grays; board tile gaps inside a block, `block_gap` (in
    tiles) between. Same shape as a coloring row (tiles, empty letters) so a row
    transforms into it. The table passes TILE_BUFF: no extra gap (the user's call)."""
    tiles, x, prev = VGroup(), 0.0, None
    for t in [2] * g + [1] * y + [0] * b:
        if prev is not None:
            x += size * (1 + (TILE_BUFF if t == prev else block_gap))
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
    pie — the Second Guess pie
    table — Average Words Remaining, combos only
    fill_320, fill_230 — the two 1s
    bared, bared_off — BARED / BEARD / BREAD up and back down
    fill_0 .. fill_5 — the values by gray count
    breakdown — title flip, values out, legend in
    bars_0, bars_5, bars_1 .. bars_4 — the bars by gray count
    third, fourth — the third- and fourth-guess bars
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
        rt = 0.7
        self.sfx(VANISH_SFX, at=max(0.0, rt / 2 - VANISH_PEAK), gain=WHOOSH_GAIN)
        self.play(FadeOut(self.combos.pop(IMPOSSIBLE)), run_time=rt)

    # e : GGGGG, the all-greens combination (the game is over), fades out
    @subscene
    def drop_win(self):
        rt = 0.7
        self.sfx(VANISH_SFX, at=max(0.0, rt / 2 - VANISH_PEAK), gain=WHOOSH_GAIN)
        self.play(FadeOut(self.combos.pop(WIN)), run_time=rt)

    def _move_up(self, old, new, run_time):
        """The old screen slides up and out as the new one rises from below — the
        video's "move up" (a page's height). `new` is built where it will END."""
        h = config.frame_height
        new.shift(DOWN * h)
        self.play(old.animate.shift(UP * h), new.animate.shift(UP * h), run_time=run_time)
        self.remove(old)

    # f : move up to an empty screen with just the title; then the pie fans in
    def _setup_pie(self):
        p = DATA["pie"]
        self.pie = get_pie_chart([p["compatible"], p["new"], p["else"]],
                                 colors=[KIND_COLORS[k] for k in ("compatible", "new", "else")],
                                 labels=PIE_NAMES, radius=PIE_RADIUS, center=PIE_CENTER,
                                 label_mode="callout")
        self.title = _title(PIE_TITLE)

    @subscene
    def pie(self):
        self._setup_pie()
        self._move_up(VGroup(*self.combos.values()), self.title, MOVE_UP_RT)
        self.pie.fan_all(self, 1.5)
        self.combos = None

    # g : move up again, to the table's title alone; rows arrive with their values
    def _setup_table(self):
        self.new_title = _title(TABLE_TITLE)
        left, self.val_x = _table_xs()
        self.rows = {}
        for i, c in enumerate(ROWS):
            row = _combo(*c, ROW_TILE, block_gap=TILE_BUFF)
            row.shift([left - row.get_left()[0], _row_y(i, c) - row.get_y(), 0])
            self.rows[c] = row
        self.values = {}

    @subscene
    def table(self):
        self._setup_table()
        self._move_up(VGroup(self.pie, self.title), self.new_title, MOVE_UP_RT)
        self.title, self.new_title, self.pie = self.new_title, None, None

    def _fill(self, combos, run_time):
        """`combos`' rows — combination and value together — rise in, staggered
        (the table rows' convention, 04new_rules.py:156)."""
        for c in combos:
            self.values[c] = _value(DATA["avg"][_key(c)], self.rows[c].get_y(), self.val_x)
        self.play(LaggedStart(*[FadeIn(VGroup(self.rows[c], self.values[c]),
                                       shift=UP * ROW_RISE) for c in combos],
                              lag_ratio=ROW_LAG), run_time=run_time)

    def _group(self, grays):
        return [c for c in ROWS if c[2] == grays]

    # h : 3G2Y — 1, in bold
    @subscene
    def fill_320(self):
        self._fill([(3, 2, 0)], 0.6)

    # i : 2G3Y — 1, in bold
    @subscene
    def fill_230(self):
        self._fill([(2, 3, 0)], 0.6)

    # j : BARED (green, three yellows, green), BEARD and BREAD, stacked at the bottom
    #     middle, rise together from below the frame
    def _setup_bared(self):
        rows = [get_scored_row("bared", code("GYYYG")), get_typed_row("beard"),
                get_typed_row("bread")]
        for i, r in enumerate(rows):
            r.scale(WORD_TILE / r.tiles[0][0].width).move_to(DOWN * i * WORD_PITCH)
        self.words = VGroup(*rows)
        self.words.move_to([0, -config.frame_y_radius + WORD_MARGIN + self.words.height / 2, 0])
        # far enough to start / end wholly below the frame
        self.word_drop = self.words.get_top()[1] + config.frame_y_radius + 0.1

    @subscene
    def bared(self):
        self._setup_bared()
        self.words.shift(DOWN * self.word_drop)
        self.add(self.words)
        self.play(self.words.animate.shift(UP * self.word_drop), run_time=1.0)

    # k : the three words go back off the bottom, together (no fade: they leave the
    #     frame anyway)
    @subscene
    def bared_off(self):
        self.play(self.words.animate.shift(DOWN * self.word_drop), run_time=0.8)
        self.remove(self.words)
        self.words = None

    # l : the rest of the 0-gray rows
    @subscene
    def fill_0(self):
        self._fill([c for c in self._group(0) if c not in self.values], 0.8)

    # m : the 1-gray rows
    @subscene
    def fill_1(self):
        self._fill(self._group(1), 0.8)

    # n : the 2-gray rows
    @subscene
    def fill_2(self):
        self._fill(self._group(2), 0.8)

    # o : the 3-gray rows
    @subscene
    def fill_3(self):
        self._fill(self._group(3), 0.8)

    # p : the 4-gray rows
    @subscene
    def fill_4(self):
        self._fill(self._group(4), 0.6)

    # q : the all-gray row
    @subscene
    def fill_5(self):
        self._fill(self._group(5), 0.6)

    # r : title flips to Strategy Breakdown (Second Guess); values out, legend in; the
    #     combinations slide left to make room for the bars
    def _setup_breakdown(self):
        self.new_title = _title(BREAKDOWN.format("Second"))
        self.legend = _legend()
        self.bars = {c: _bar(1, c, self.rows[c].get_y()) for c in ROWS}

    @subscene
    def breakdown(self):
        self._setup_breakdown()
        combos = VGroup(*self.rows.values())
        flip(self, [Flip(self.title, self.new_title)], 0.8,
             extra=[FadeOut(VGroup(*self.values.values())), FadeIn(self.legend),
                    combos.animate.shift(RIGHT * (X_COMBO - combos.get_left()[0]))])
        self.title, self.new_title, self.values = self.new_title, None, None

    def _grow(self, grays, run_time):
        grow_bars(self, [self.bars[c] for c in self._group(grays)], run_time, edge=LEFT)

    # s : the 0-gray bars
    @subscene
    def bars_0(self):
        self._grow(0, 0.8)

    # t : the all-gray bar
    @subscene
    def bars_5(self):
        self._grow(5, 0.8)

    # u : the 1-gray bars
    @subscene
    def bars_1(self):
        self._grow(1, 0.8)

    # v : the 2-gray bars
    @subscene
    def bars_2(self):
        self._grow(2, 0.8)

    # w : the 3-gray bars
    @subscene
    def bars_3(self):
        self._grow(3, 0.8)

    # x : the 4-gray bars
    @subscene
    def bars_4(self):
        self._grow(4, 0.8)

    def _to_ply(self, ply, name, run_time):
        """Title flips to `name`'s breakdown; every bar morphs to that ply's shares."""
        new_title = _title(BREAKDOWN.format(name))
        new_bars = {c: _bar(ply, c, self.rows[c].get_y()) for c in ROWS}
        flip(self, [Flip(self.title, new_title)], run_time,
             extra=[Transform(self.bars[c], new_bars[c]) for c in ROWS])
        self.title = new_title

    # y : Strategy Breakdown (Third Guess); the bars become the third guess's
    @subscene
    def third(self):
        self._to_ply(2, "Third", 1.2)

    # z : ... (Fourth Guess); the bars become the fourth guess's
    @subscene
    def fourth(self):
        self._to_ply(3, "Fourth", 1.2)
