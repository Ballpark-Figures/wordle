"""Scene 18 — back to the tier list; the letters the top openers reach for first; the
SLANT / PRICE strategy and its place on the number line. Navy background.

Talking head THL precedes it, so a opens with the tier list already on screen. THM
follows, so the scene ends with the number line on screen.

GEOMETRY: three screens stacked one frame apart, so the script's "move down" is a
camera pan (13's convention) and nothing fades: the tier list and the table at the
origin, "Near Optimal Strategy" one frame below, the number line two frames below.

BEAT MAP — one subscene per Script.md beat, letters matching:
  a tiers       — the tier list, letters in boxes, held                  (18a, VO 1)
  b table       — the list shrinks into the top right; the title "Appearances in
                  First ___ Guesses" / "(Top 1000 Openers)" and the column heads 1, 2
                  fade in on the left                                    (18b, VO 2)
  c top_tier    — copies of E A R T S travel into the left column; their column-1
                  percentages rise in                                    (18c, VO 2)
  d high_tier   — copies of L I O N C the same; then the rest of column 1 and all of
                  column 2                                               (18d, VO 3)
  e crate       — copies of C R A T E travel down into a word under the list (18e, VO 4)
  f lions       — copies of L I O N S into a word under it               (18f, VO 4)
  g near_optimal — pan down to "Near Optimal Strategy"                   (18g, VO 5)
  h slant       — SLANT typed at the top                                 (18h, VO 6)
  i left_branch — a white line extends down-left, five boxes popping out along it:
                  three split green / yellow, two black                  (18i, VO 6)
  j left_rca    — a line down from them, a "Random Compatible Answers" card popping
                  out along it (user's call)                             (18j, VO 6)
  k right_branch — the same down-right: three grey boxes, two black      (18k, VO 6)
  l price       — PRICE typed directly below                             (18l, VO 6)
  m right_rca   — a line down from PRICE, its card popping out (as j)    (18m, VO 6)
  n average     — "Average Guesses: 3.67" rises in at the bottom         (18n, VO 6)
  o timeline    — pan down to the number line, Optimal (3.42) at the left and Random
                  Compatible Answers (4.08) at the right, scene 15's markers in
                  between; the SLANT PRICE card ("Strategy", user's call) pops out
                  at 3.67                                                (18o, VO 7)

REUSE MAP — every element, the one source it comes from, and how it enters:
  tier list (a)       bpkfigures.tier_list `filled_list` at 09's LIST_SCALE, panels
                      tier_data.PANEL_ON_NAVY (09e's lighter panels on the navy);
                      letters IN BOXES (the user's call) via its new `box` option:
                      the board's typed tile (TILE_EMPTY_FILL, TILE_FILLED_BORDER),
                      letters keeping the vowel/consonant colours (user's call)
  a's entrance        none: on screen from setup_scene (17a after THK)
  shrink (b)          09e's move into the top-right corner (`animate.scale().move_to`)
  table title (b)     14d's: crisp_text WHITE, FONT_SIZE_LG, the blank a short line
                      of underscores; the parenthetical a second line at FONT_SIZE_MD
                      (StrategyLine's "(Win Rate)" subtitle)
  table (b-d)         14d's / 10's: bold heads at 28, cells at 30; FadeIn with the
                      title (13a's: title and content together)
  letter copies (c-f) copies of the list's own boxed tiles, Transformed into their
                      places (09d's per-letter moves, tier_list.morph_into)
  cells (c, d)        14's `_fill`: FadeIn rising 0.3; coloured red -> green by
                      StrategyLine `win_color` with its halfway point at 50% (user's
                      call: colour-coded; the midpoint is the VO's "half")
  words (e, f)        assets/board.py `get_typed_row`; each box -> tile, glyph -> letter
  pans (g, o)         StrategyLine `_pan_down` (13's pan + whoosh)
  screen title (g)    crisp_text WHITE FONT_SIZE_LG at TITLE_BUFF (13's / 14's)
  typing (h, l)       WordleBoard.type_word(appear=True) + assets/keys.py `key_cues`
                      (13's `_type`)
  branch lines (i-m)  assets/branch.py — 07's tree edges (white, 1.5, behind, middle
                      tile to middle tile), moved out of 07 for this scene; each
                      extends with its row / card popping out along it (`BranchPop`,
                      the number line's marker pop with the branch as the stem)
  pattern boxes (i,k) assets/board.py tiles: grey = TILE_ABSENT, black = an untouched
                      tile (TILE_EMPTY_FILL / TILE_EMPTY_BORDER); the split tiles are
                      two triangles, TILE_CORRECT top-left, TILE_PRESENT bottom-right
  RCA cards (j, m)    the number line's RCA card: bpkfigures `stack_lines` (baseline
                      pitch), StrategyLine's card style; initials NOT bold (user's call)
  average (n)         crisp_text WHITE FONT_SIZE_MD; FadeIn rising 0.3
  number line (o)     assets/strategy_line.py `StrategyLine`: `_build_line(3.42, 4.08)`
                      with scene 15's LINE_DROP and stem; Optimal / SLATE / CRANE SPILT
                      / Random Compatible markers as scene 15 left them (grow=1.0)
  new marker (o)      StrategyLine `_marker`: a board-tight word_stack, "Strategy"
                      (user's call, not "Then RCA"), the win rate; `_pop_in`
  colours             BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*

EVERY NUMBER is sourced (assets/slant_price_data.py -> slant_price_cache.json):
  table          coverage_top1000.csv, count / 2,315,000 paths, 2 dp
  SLANT PRICE    3.67 (3.669980, exact_g3.csv, re-checked by the ladder walk),
                 99.37% (0.993746, win_named_cap6.csv, exact)
  line markers   scene 13's 3.42 / 4.08; SLATE (random_compatible_data) and CRANE
                 SPILT (always_win_data), as scene 15 shows them
The VO's 3.67 is shown only where column 2 asks for it (n); markers show their
averages only by where they sit (13's convention).

LAYOUT CHOICES, flagged:
  - e/f: the copies land as ordinary typed tiles, letters turning white.
  - o: SLANT PRICE hangs ABOVE the line (CRANE SPILT is below at 3.70).
  - Percentages to 2 dp (the video's percent format, StrategyLine `rate_text`).
  - The Doc's 18o direction still says "SLANT CRANE"; built as SLANT PRICE (the VO).
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from bpkfigures import tier_list as tl
from assets import tier_data as td
from assets import slant_price_data, random_compatible_data, always_win_data
from assets.board import STROKE, GAP, TILE, WordleBoard, get_typed_row
from assets.branch import branch_line, mid_tile, BranchPop
from assets.keys import key_cues
from assets.strategy_line import (StrategyLine, GAME_DY, TITLE_BUFF, OPTIMAL,
                                  COMPATIBLE, CARD_PAD, CARD_RADIUS, MARKER_FS,
                                  win_color, word_stack, rate_text)
from bpkfigures.number_line import stack_lines
from bpkfigures.card import card_behind

DATA = slant_price_data.load()
STRAT = DATA["strategy"]
SLATE = random_compatible_data.load()["openers"]["slate"]        # scene 14's marker
CRANE_SPILT = always_win_data.load()["openers"]["crane spilt"]   # scene 15's
TOP_TIER, HIGH_TIER = "EARTS", "LIONC"       # tier_data's TOP (E + ARTS), HIGH (L + IONC)
FIRST_WORD, SECOND_WORD = "crate", "lions"   # the script's words (18e, 18f)
FIRST_PAIR = ["crane", "spilt"]              # scene 15's two-word marker (15g)

# ── the tier list ────────────────────────────────────────────────────────────
LIST_SCALE = 0.62                 # 09's
LIST_Y = -0.15                    # 09's
BOX_STROKE = STROKE * tl.BOX_FILL_FRAC * tl.LETTER_PITCH * LIST_SCALE / TILE   # 12's rule
BOX = {"fill": TILE_EMPTY_FILL, "stroke_color": TILE_FILLED_BORDER,
       "stroke_width": BOX_STROKE}
CORNER_SCALE = 0.40               # 09e's corner size
CORNER_UR = (7.6, 4.1)            # its top-right corner here (room under it for words)
WORD_W = 2.6                      # e, f: the two words' width
WORD_TOP_GAP = 0.45               # e: the list's bottom to CRATE's top

# ── the table (14d's / 10's sizes) ───────────────────────────────────────────
TITLE_TEXT = "Appearances in First ___ Guesses"
SUB_TEXT = "(Top 1000 Openers)"
SUB_BUFF = 0.15                   # StrategyLine's SUBTITLE_BUFF
HEADER_SIZE = 28
CELL_SIZE = 30
TABLE_CX = -1.6                   # the table's (and title's) centre: the left region's
HEAD_Y = 2.2                      # the head row
ROW_DY = 0.62                     # 14's 0.72, tightened so ten rows fit
LETTER_X = TABLE_CX - 2.6
COL_X = (TABLE_CX, TABLE_CX + 2.6)
TABLE_BOX = 0.46                  # a letter's box in the table

# ── Near Optimal Strategy (one frame down) ───────────────────────────────────
B_DY = -GAME_DY
ROW_TILE = 0.62                   # its rows' tile side
SLANT_Y = 2.3
BRANCH_X = 4.0                    # the two pattern rows' centres, either side
PATTERN_Y = 0.4
RCA_LINK = 0.35                   # j, m: the line showing between a row and its card
TABLE_MID = 0.5                   # c, d: the share coloured halfway (yellow) on the
                                  #   win-rate red -> green scale -- the VO's "half"
AVG_Y = -3.7

# ── the number line (two frames down; scene 15's line) ───────────────────────
C_DY = -2 * GAME_DY
LINE_DROP = -0.2                  # 15's
MARKER_STEM_15 = 0.3              # 15's


def _row_width(n=5, tile=ROW_TILE):
    return n * tile + (n - 1) * tile * GAP / TILE


def _stroke(row):
    """12's rule: a scaled row's tile border thinned in proportion to its tiles."""
    return STROKE * min(1.0, row.tiles[0][0].height / TILE)


def _empty_row(width):
    """A one-row board of untouched tiles, `width` wide."""
    row = WordleBoard(rows=1, cols=5)
    row.scale(width / row.width)
    for t in row.tiles[0]:
        t.set_stroke(width=_stroke(row))
    return row


def _split_tile(tile):
    """`tile` as two triangles: green top-left, yellow bottom-right (18i)."""
    ul, ur = tile.get_corner(UL), tile.get_corner(UR)
    dl, dr = tile.get_corner(DL), tile.get_corner(DR)
    green = Polygon(ul, ur, dl, stroke_width=0).set_fill(TILE_CORRECT, opacity=1.0)
    yellow = Polygon(ur, dr, dl, stroke_width=0).set_fill(TILE_PRESENT, opacity=1.0)
    return VGroup(green, yellow)


def _pattern_row(kind, center):
    """18i's (kind "gy") or 18k's ("gray") five boxes: three coloured, two black."""
    row = _empty_row(_row_width()).move_to(center)
    extras = VGroup()
    for i, t in enumerate(row.tiles[0][:3]):
        if kind == "gray":
            t.set_fill(TILE_ABSENT, opacity=1.0).set_stroke(TILE_ABSENT)
        else:
            extras.add(_split_tile(t))
            t.set_fill(opacity=0).set_stroke(width=0)
    if len(extras):                  # an EMPTY group would sit at the origin and
        row.add(extras)              #   stretch the row's bounds (18l, 2026-10-03)
    return row


def _rca_card(top_center):
    """'Random Compatible Answers' on the number line's RCA card: three lines on a
    baseline pitch (bpkfigures `stack_lines`, as every marker card -- NOT
    `arrange`, which spaces bounding boxes, so the p in "Compatible" pushed
    "Answers" down), on StrategyLine's card; no bold initials (user's call). Its top at
    `top_center`."""
    lines = stack_lines(["Random", "Compatible", "Answers"],
                        font_size=MARKER_FS, color=WHITE).set_z_index(1)
    card = card_behind(lines, pad=CARD_PAD, fill=TILE_EMPTY_FILL,
                       stroke_color=TILE_FILLED_BORDER, stroke_width=STROKE,
                       corner_radius=CARD_RADIUS)
    out = VGroup(card, lines)
    out.move_to(top_center, aligned_edge=UP)
    return out


def _pct(count):
    return f"{100 * count / DATA['paths']:.2f}%"


class Scene18(StrategyLine, MovingCameraScene, WordleBoardScene):
    """tiers — the tier list, boxed, held
    table — list to the top right; table title and heads in
    top_tier — E A R T S into the table; column 1 for them
    high_tier — L I O N C into the table; the rest of columns 1 and 2
    crate — C R A T E copied down into a word
    lions — L I O N S copied down into a word
    near_optimal — pan down to "Near Optimal Strategy"
    slant — SLANT typed
    left_branch — line down-left; green/yellow boxes
    left_rca — Random Compatible Answers under them
    right_branch — line down-right; grey boxes
    price — PRICE typed below them
    right_rca — Random Compatible Answers under it
    average — Average Guesses: 3.67
    timeline — pan down to the number line; SLANT PRICE pops out
    """

    def setup_scene(self):
        self.marker_stem = MARKER_STEM_15
        self.tier_list = tl.filled_list(td.WORDLE_LETTERS, names=td.WORDLE_NAMES,
                                    scale=LIST_SCALE, panel_fill=td.PANEL_ON_NAVY,
                                    box=BOX).move_to([0, LIST_Y, 0])
        self.add(self.tier_list)

    def _tile(self, ch):
        """The list's boxed tile for letter `ch`."""
        return tl.tile_map(self.tier_list, td.WORDLE_LETTERS)[ch.upper()]

    # a : the tier list, held (on screen from setup_scene)
    @subscene
    def tiers(self):
        pass

    # b : the list shrinks into the top right; the table's title and heads fade in
    def _setup_table(self):
        self.title_t = crisp_text(TITLE_TEXT, font_size=FONT_SIZE_LG, color=WHITE)
        self.title_t.to_edge(UP, buff=TITLE_BUFF).set_x(TABLE_CX)
        self.sub_t = crisp_text(SUB_TEXT, font_size=FONT_SIZE_MD, color=WHITE)
        self.sub_t.next_to(self.title_t, DOWN, buff=SUB_BUFF)
        self.heads = VGroup(*[crisp_text(h, font_size=HEADER_SIZE, color=WHITE,
                                         weight=BOLD).move_to([x, HEAD_Y, 0])
                              for h, x in zip(("1", "2"), COL_X)])
        self.corner = self.tier_list.copy().scale(CORNER_SCALE / LIST_SCALE)
        self.corner.move_to([*CORNER_UR, 0], aligned_edge=UR)

    @subscene
    def table(self):
        self._setup_table()
        self.play(Transform(self.tier_list, self.corner), run_time=1.2)
        self.corner = None
        self.play(FadeIn(self.title_t, self.sub_t, self.heads), run_time=0.8)

    # c, d : a tier's letters into the table, then their percentages
    def _row_y(self, k):
        return HEAD_Y - (k + 1) * ROW_DY

    def _letters_in(self, letters, first_row, run_time):
        """Copies of the list's boxed `letters` travel into the left column."""
        movers, anims = [], []
        for k, ch in enumerate(letters):
            src = self._tile(ch)
            m = src.copy()
            dst = tl.letter_box(ch.lower(), TABLE_BOX, BOX).move_to(
                [LETTER_X, self._row_y(first_row + k), 0])
            dst.box.set_stroke(width=BOX_STROKE)
            anims.append(Transform(m, dst))
            movers.append(m)
        self.add(*movers)
        self.play(*anims, run_time=run_time)
        return movers

    def _cells(self, letters, first_row, col):
        """Column `col`'s (0 or 1) percentages for `letters`."""
        out = []
        for k, ch in enumerate(letters):
            n = DATA["coverage"][ch.lower()][col]
            out.append(crisp_text(_pct(n), font_size=CELL_SIZE, color=WHITE)
                       .set_color(win_color(n / DATA["paths"], mid=TABLE_MID))
                       .move_to([COL_X[col], self._row_y(first_row + k), 0]))
        return out

    def _fill(self, cells, run_time):
        """14's `_fill`: the cells rise into place."""
        self.play(*[FadeIn(c, shift=UP * 0.3) for c in cells], run_time=run_time)
        return cells

    @subscene
    def top_tier(self):
        self.table_letters = self._letters_in(TOP_TIER, 0, 1.2)
        self.cells = self._fill(self._cells(TOP_TIER, 0, 0), 0.5)

    @subscene
    def high_tier(self):
        self.table_letters += self._letters_in(HIGH_TIER, 5, 1.2)
        self.cells += self._fill(self._cells(HIGH_TIER, 5, 0), 0.5)
        self.cells += self._fill(self._cells(TOP_TIER + HIGH_TIER, 0, 1), 0.5)

    # e, f : copies of a word's letters travel down into a typed row under the list
    def _word_in(self, word, top_y, run_time):
        row = get_typed_row(word)
        row.scale(WORD_W / row.width).move_to([self.tier_list.get_x(), top_y, 0],
                                              aligned_edge=UP)
        for t in row.tiles[0]:
            t.set_stroke(width=_stroke(row))
        movers, anims = [], []
        for i, ch in enumerate(word):
            m = self._tile(ch).copy()
            anims += [Transform(m.box, row.tiles[0][i]), Transform(m.glyph, row.letters[0][i])]
            movers.append(m)
        self.add(*movers)
        self.play(*anims, run_time=run_time)
        self.remove(*movers)
        self.add(row)
        return row

    @subscene
    def crate(self):
        top = self.tier_list.get_bottom()[1] - WORD_TOP_GAP
        self.crate_row = self._word_in(FIRST_WORD, top, 1.2)

    @subscene
    def lions(self):
        top = self.crate_row.get_bottom()[1] - self.crate_row.height * GAP / TILE
        self.lions_row = self._word_in(SECOND_WORD, top, 1.2)

    # g : pan down to "Near Optimal Strategy"
    def _setup_near_optimal(self):
        self.near_title = crisp_text("Near Optimal Strategy", font_size=FONT_SIZE_LG,
                                     color=WHITE)
        self.near_title.to_edge(UP, buff=TITLE_BUFF).shift(UP * B_DY)
        self.add(self.near_title)

    @subscene
    def near_optimal(self):
        self._setup_near_optimal()
        self._pan_down(1.5)
        self.remove(*[m for m in self.mobjects
                      if m is not self.camera.frame and m is not self.near_title])
        self.tier_list = self.crate_row = self.lions_row = None
        self.table_letters = self.cells = None
        self.title_t = self.sub_t = self.heads = None

    # h, l : a word typed on a one-row board
    def _typed_board(self, center):
        row = WordleBoard(rows=1, cols=5)
        row.scale(_row_width() / row.width).move_to(center)
        for t in row.tiles[0]:
            t.set_stroke(width=_stroke(row))
        return row

    @subscene
    def slant(self):
        self.slant_row = self._typed_board([0, B_DY + SLANT_Y, 0])
        self.slant_row.type_word(self, 0, STRAT["opener"], 0.65,
                                 per_letter=key_cues(self), appear=True)

    # i, k : a branch line extends and the five boxes pop out along it
    def _branch(self, kind, x, run_time):
        row = _pattern_row(kind, [x, B_DY + PATTERN_Y, 0])
        a, b = mid_tile(self.slant_row), mid_tile(row)
        line = branch_line(a, b)
        self.add(line, row)
        self.play(BranchPop(line, row, a, b), run_time=run_time)
        return line, row

    # j, m : a line down from a row, its Random Compatible Answers card popping out
    def _rca_branch(self, row, run_time):
        card = _rca_card(row.get_bottom() + DOWN * RCA_LINK)
        a, b = mid_tile(row), card.get_center()
        line = branch_line(a, b)
        self.add(line, card)
        self.play(BranchPop(line, card, a, b), run_time=run_time)
        return line, card

    @subscene
    def left_branch(self):
        self.left_line, self.left_row = self._branch("gy", -BRANCH_X, 0.6)

    @subscene
    def left_rca(self):
        self.left_link, self.left_words = self._rca_branch(self.left_row, 0.6)

    @subscene
    def right_branch(self):
        self.right_line, self.right_row = self._branch("gray", BRANCH_X, 0.6)

    @subscene
    def price(self):
        r = self.right_row
        h = r.tiles[0][0].height                      # the board's row spacing below it
        center = r.get_center() + DOWN * (h + h * GAP / TILE)
        self.price_row = self._typed_board(center)
        self.price_row.type_word(self, 0, STRAT["second"], 0.65,
                                 per_letter=key_cues(self), appear=True)

    @subscene
    def right_rca(self):
        self.right_link, self.right_words = self._rca_branch(self.price_row, 0.6)

    @subscene
    def average(self):
        self.avg = crisp_text(f"Average Guesses: {STRAT['mean']:.2f}",
                              font_size=FONT_SIZE_MD, color=WHITE)
        self.avg.move_to([0, B_DY + AVG_Y, 0])
        self.play(FadeIn(self.avg, shift=UP * 0.3), run_time=0.6)

    # o : pan down to the number line; SLANT PRICE pops out at 3.67
    def _setup_timeline(self):
        self._build_line(OPTIMAL[0], COMPATIBLE[0], dy=C_DY, line_dy=LINE_DROP)
        self.optimal_marker(grow=1.0)
        self.compatible_marker(grow=1.0)
        self.opener_marker(round(SLATE["mean"], 2), ["slate"], SLATE["win_rate"],
                           grow=1.0)
        self.opener_marker(round(CRANE_SPILT["mean"], 2), FIRST_PAIR,
                           CRANE_SPILT["win_rate"], side=DOWN, grow=1.0)
        self.add(self.line, self.title, self.subtitle)

    @subscene
    def timeline(self):
        self._setup_timeline()
        self._pan_down(1.5)
        frame = [self.camera.frame] if self.camera.frame in self.mobjects else []
        self.remove(*self.mobjects)
        self.add(*frame, self.line, self.title, self.subtitle)
        # built only now, as 15f's markers are: a marker at grow=0 still shows its
        # card's border (strokes do not shrink) as a dark speck on the line
        # "Strategy" in place of the opener cards' "Then RCA" (user's call)
        self.sp_marker = self._marker(round(STRAT["mean"], 2),
                                      [word_stack([STRAT["opener"], STRAT["second"]]),
                                       "Strategy", rate_text(STRAT["win_rate"])],
                                      side=UP, grow=0.0)
        self._pop_in(self.sp_marker, 0.4)

