"""Scene 19 — hard mode: the rule, what it leaves out, the histogram shifting, the
openers that cannot finish in six, the families that trap them, the fast openers, and
hard mode's letter table. Navy background.

Talking head THM precedes it, so a opens on the blank board already on screen.

GEOMETRY: screens one frame apart, each move a camera pan with a whoosh (13's / 18's
convention), so nothing fades between screens. a-h on the ordinary frame; i-m in the
histogram's world (it is 27x wider than the frame, 08's), with the boards one frame
ABOVE it and the turns table one frame BELOW it; at the end of m everything on screen
is re-projected back to the ordinary frame (09e's seam, run in reverse), so n-z are
ordinary again: the turns table at the origin, the families one frame below, the fast
openers one frame right of those, hard mode's letter table one frame below that.

BEAT MAP — one subscene per Script.md beat, letters matching:
  a blank         — the empty board, held                                (19a, VO 1)
  b again         — AGAIN typed and scored against GREAT                 (19b, VO 1)
  c solve         — SOLVE typed; the row shakes, refused; SOLVE deleted  (19c, VO 1)
  d again_twice   — AGAIN typed and scored twice more                    (19d, VO 2)
  e great         — GREAT typed and scored; the winning bounce           (19e, VO 2)
  f split         — every tile flips back to empty as the board moves left; an
                    empty copy moves out of it to the right              (19f, VO 3)
  g keep_yellow   — left: SCALE SCANT, typed and scored                  (19g, VO 3)
  h keep_grey     — right: INLET NIGHT, typed and scored                 (19h, VO 3)
  i histogram     — pan down to 08's histogram (normal mode), its axis running on
                    to 4.22 to leave room on the right                   (19i, VO 4)
  j shift         — every word's slice slides to its hard-mode place     (19j, VO 5)
  k salet         — SALET called out                                     (19k, VO 5)
  l trace         — TRACE called out                                     (19l, VO 5)
  m turns_table   — pan down to "Words by Turns to Solve": Normal / Hard, rows 5-10,
                    12,972 in Normal's row 5                             (19m, VO 6)
  n hard_5        — Hard's row 5                                         (19n, VO 6)
  o hard_6        — Hard's row 6                                         (19o, VO 6)
  p hard_7_10     — Hard's rows 7-10                                     (19p, VO 6)
  q depth10       — everything fades as Hard's row-10 number turns into 14
                    dots; then they become the 14 words, left half    (19q, VO 7)
  r ight_game     — right half: EIGHT ... WIGHT flip in, scored against WIGHT (19r)
  s aught         — AUGHT moves to the top of the game and is scored     (19s, VO 7)
  t families      — pan down to the families table (Max Guesses / Family / # Words)
                                                                         (19t, VO 8)
  u trace_up      — TRACE on the right                                   (19u, VO 8)
  v emph_er       — everything dims but E and R, in the words with BOTH  (19v, VO 8)
  w emph_atc      — instead, A T C in .ATCH and in TRACE                 (19w, VO 8)
  x unemph        — everything back                                      (19x, VO 8)
  y fast          — pan right to "Top Fast Openers"                      (19y, VO 9)
  z letters       — pan down to hard mode's letter table and tier list   (19z, VO 10)

REUSE MAP — every element, its one source, and how it enters / leaves:
  board, typing, scoring, bounce   assets/board.py get_board / type_word (+ keys.py
                    key_cues) / reveal / bounce, as 02
  refusal (c)       board.shake — NEW in board.py (RowShake), the real game's jiggle
  delete (c)        board.delete_word — NEW in board.py: discrete keypresses, right
                    to left, each with the delete key's sound (keys.backspace_cues)
  flip out (f)      board.TileFlip(swap_to=None, to_center=...) — 10's flip that
                    travels; the copy is a plain get_board sliding out
  histogram (i-l)   assets/histogram_view.py (08's bars / chrome) at full_view(3.40,
                    4.22) — the axis range is the one new parameter; StacksView
                    _move_view for both pans (08's whoosh); callouts as 08's
                    (get_typed_row, pinned, ping)
  the shift (j)     WordStacks bar mode; each word's x and row interpolated from its
                    normal place to its hard place (no new asset code — flagged as a
                    promote candidate)
  the seams (i, m)  histogram_view.to_view / from_view (09e's map, now offsettable and
                    invertible)
  tables (m-p, t, y, z)  14d's / 18's: title crisp_text WHITE FONT_SIZE_LG at
                    TITLE_BUFF, bold heads 28, cells 30, cells rising in (14's _fill)
  14 words (q)      get_typed_row in groups.grid_cells (4+4+4+2), growing out of the
                    number as it fades
  game (r)          a 10-row board, row 0 held empty; rows 1-9 flip in with TileFlip
                    (appear=True, 16's flip-in), already scored
  AUGHT (s)         its row travels up into row 0, then board.reveal
  family templates  board tiles: fixed letters on TILE_CORRECT, dots as untouched
                    tiles (TILE_EMPTY_FILL / TILE_EMPTY_BORDER)
  emphasis (v-x)    dim the rest to word_stacks.DIM (0.2), the house move
  tier list (z)    bpkfigures.tier_list filled_list, boxed, at 18's corner size

EVERY NUMBER is sourced (assets/hard_mode_data.py -> hard_mode_cache.json; the two
games' codes from assets/game_data.py, computed by math/wordle.py pattern):
  histogram      the hard sweep's totals (escalating, each CONSTRAINED at its minimum
                 feasible depth), binned by 08's rule
  table          normal: optturns opener_totals_d5_feas.csv (all 12972 at 5); hard:
                 hardturns opener_totals_d5.csv + the escalating sweep's depth
  14 words       the openers whose hard minimum is 10 (asserted = the script's)
  examples (g,h) the best-ranked hard opener with such a line, its first one
  families       deep_families_d7.csv cut by FAMILIES.md's rule (asserted = script)
  fast openers   feasible at 5, ranked by hard total (asserted = the script's)
  letter table   coverage_top1000_hardturns.csv (letter_explorer.ipynb, HARD_MODE)

FLAGGED — choices and gaps for the user:
  - m: the script says "2315 in row 5"; the table counts OPENERS (its row 10 is the
    14 words of 19r, 11 of them not answers), so Normal's row 5 is 12,972. Built so.
    Normal's rows 6-10 are left blank ("already populated with ... in row 5").
  - VO 6 "about 1 in every seven openers can't even guarantee a win in 6": the data
    says 2022 of 12972 = 15.6%, about 1 in 6.4.
  - c: after the shake SOLVE is backspaced, right to left, as the real game's delete
    key (the user's call: in c, not d).
  - e: GREAT bounces as 02's winning row does; g/h's last rows do not.
  - w: "ATC in WATCH" built as the A T C of the .ATCH row (the table shows templates).
  - u: TRACE "put up" as a typed row rising in, not typed letter by letter.
  - y: the ten openers in one ranked column, not a grid.
  - z: hard mode's tiers are the user's cuts on the hardturns greedy order (math/
    tiers.py HARD_TIERS); the table's rows are its top two tiers' letters, as 18's.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import numpy as np
from manim import MovingCameraScene

from config import *
from bpkfigures import tier_list as tl
from assets import hard_mode_data, histogram_data, game_data
from assets import tier_data as td
from assets import histogram_view as hv
from assets.board import STROKE, GAP, TILE, TileFlip, WordleBoard, get_board, get_typed_row
from assets.groups import grid_cells
from assets.strategy_line import win_color
from assets.keys import key_cues, backspace_cues
from assets.word_stacks import StacksCamera, PITCH, DIM
from assets.stacks_view import (StacksView, pinned, ASPECT, WHOOSH_SFX, WHOOSH_GAIN,
                                WHOOSH_PEAK)

DATA = hard_mode_data.load()
HIST = histogram_data.load()
RULES = game_data.load("hard_rules")
IGHT = game_data.load("ight")
EX = DATA["examples"]
REFUSED = "solve"                    # 19c

FRAME_H = config.frame_height        # one screen down
FRAME_W16 = config.frame_width       # one screen across
TITLE_BUFF = 0.6                     # 13's / 14's / 18's screen titles
HEADER_SIZE = 28                     # 14d's / 18's table heads
CELL_SIZE = 30                       # ... and cells
RISE = 0.3                           # 14's _fill: a cell rises this far as it fades in

# ── a-h: the boards ──────────────────────────────────────────────────────────
BOARD_X = 4.0                        # f: the two boards' centres, either side

# ── i-l: the histogram (08's, its axis run on to make room for hard mode) ────
BIN_LO = min(HIST["bins"])
AXIS_LO, AXIS_HI = 3.40, 4.22        # hard mode reaches bin 4.21
VIEW = hv.full_view(AXIS_LO, AXIS_HI, hv.TALLEST)
VH = VIEW[2] / ASPECT                # the view's height
UPPER = (VIEW[0], VIEW[1] + VH, VIEW[2], VIEW[3])       # the boards' screen
LOWER = (VIEW[0], VIEW[1] - VH, VIEW[2], VIEW[3])       # the turns table's
assert max(DATA["hist"]["rows"]) + 1 <= hv.TALLEST, "hard mode's tallest bar won't fit"
_SALET_FX = ((DATA["hist"]["bins"][HIST["words"].index("salet")] - BIN_LO) * PITCH
             - VIEW[0]) / VIEW[2]
CALLOUT_W19 = 0.11
CALLOUTS = {                         # both left of their (shared) bar, SALET above
    "salet": pinned(_SALET_FX - 0.02, 0.44, "right", "center", w=CALLOUT_W19),
    "trace": pinned(_SALET_FX - 0.02, 0.29, "right", "center", w=CALLOUT_W19),
}

# ── m-p: the turns table (ordinary frame, built at the origin) ───────────────
TURNS = [str(t) for t in range(5, 11)]
T_HEAD_Y = 2.3
T_ROW_DY = 0.72                      # 14's
T_COL_X = (-3.2, 0.0, 3.2)           # turns, Normal, Hard

# ── q-s: the 14 words and the IGHT game ──────────────────────────────────────
WORDS_C = (-4.0, 0.0)                # the 14 words' grid centre
WORD_W19 = 1.5
WORD_PITCH = (1.75, 0.62)
TEN_DOT_PITCH = 0.22                 # r: the dots the 14 becomes, in the grid's arrangement
TEN_DOT_R = 0.06
DOT_COLOR = WHITE                    # the answer dots are white, as in 06 / 07 / 12 / 16
GAME_H = 8.1                         # the 10-row board's height
GAME_C = (4.0, 0.0)

# ── t-x: the families (one frame below) ──────────────────────────────────────
F_DY = -FRAME_H
F_HEAD_Y = 3.75
F_ROW_Y0 = 3.15
F_ROW_DY = 0.5
F_COL_X = (-4.4, -1.2, 1.6)          # Max Guesses, Family, # Words
F_TEMPLATE_W = 2.0
TRACE_C = (None, 0.0)                # x: centred right of the numbers (19v)
TRACE_W = 2.6

# ── y: the fast openers (one frame right of the families) ────────────────────
Z_DX = FRAME_W16
FAST_W = 2.6
FAST_Y0 = 2.55
FAST_DY = 0.66

# ── z: hard mode's letter table (one frame below the fast openers) ──────────
# 18's layout constants, COPIED (18 keeps them scene-local; promote candidate)
ZA_DY = -2 * FRAME_H
LIST_SCALE = 0.62
CORNER_SCALE = 0.40
CORNER_UR = (7.6, 4.1)
TABLE_CX = -1.6
HEAD_Y = 2.2
ROW_DY = 0.62
LETTER_X = TABLE_CX - 2.6
COL_X = (TABLE_CX, TABLE_CX + 2.6)
TABLE_BOX = 0.46
SUB_BUFF = 0.15
TABLE_MID = 0.5                      # 18's: the share coloured halfway (yellow)


def _stroke(row):
    """12's rule: a scaled row's tile border thinned in proportion to its tiles."""
    return STROKE * min(1.0, row.tiles[0][0].height / TILE)


def _typed(word, width, center):
    row = get_typed_row(word)
    row.scale(width / row.width).move_to([*center, 0] if len(center) == 2 else center)
    for t in row.tiles[0]:
        t.set_stroke(width=_stroke(row))
    return row


def _cell(text, x, y, bold=False):
    return crisp_text(text, font_size=HEADER_SIZE if bold else CELL_SIZE, color=WHITE,
                      weight=BOLD if bold else NORMAL).move_to([x, y, 0])


def _title(text, center):
    t = crisp_text(text, font_size=FONT_SIZE_LG, color=WHITE)
    t.move_to([center[0], center[1] + FRAME_H / 2 - TITLE_BUFF - t.height / 2, 0])
    return t


def _template(fam, width, center):
    """A family's template as a row of tiles: fixed letters on green, dots untouched.
    Returns (row, [(letter or None, piece)])."""
    row = WordleBoard(rows=1, cols=5)
    row.scale(width / row.width).move_to(center)
    pieces = []
    for i, ch in enumerate(fam):
        t = row.tiles[0][i]
        t.set_stroke(width=_stroke(row))
        if ch == ".":
            pieces.append((None, VGroup(t)))
            continue
        t.set_fill(TILE_CORRECT, opacity=1.0).set_stroke(TILE_CORRECT)
        letter = row._letter(ch, t)
        row.letters[0][i] = letter
        row.add(letter)
        pieces.append((ch, VGroup(t, letter)))
    return row, pieces


class Scene19(StacksView, MovingCameraScene, WordleBoardScene):
    """blank — the empty board
    again — AGAIN typed and scored
    solve — SOLVE typed and refused
    again_twice — SOLVE deleted; AGAIN twice more
    great — GREAT typed and scored
    split — board flips empty, moves left; a copy moves right
    keep_yellow — SCALE SCANT
    keep_grey — INLET NIGHT
    histogram — pan down to the normal-mode histogram
    shift — the slices slide to hard mode
    salet — SALET called out
    trace — TRACE called out
    turns_table — pan down to Words by Turns to Solve
    hard_5 — Hard row 5
    hard_6 — Hard row 6
    hard_7_10 — Hard rows 7-10
    depth10 — all but Hard's 10-row number fade; it becomes the 14 words
    ight_game — the IGHT game flips in
    aught — AUGHT to the top, scored
    families — pan down to the families table
    trace_up — TRACE on the right
    emph_er — E and R emphasised
    emph_atc — A T C in .ATCH and TRACE emphasised
    unemph — emphasis off
    fast — pan right to Top Fast Openers
    letters — pan down to hard mode's letter table
    """

    def __init__(self, **kwargs):
        super().__init__(camera_class=StacksCamera, **kwargs)

    def setup_scene(self):
        self.board = get_board()
        self.add(self.board)
        self.callouts = []

    # ── helpers ───────────────────────────────────────────────────────────────
    def _type(self, board, row, word, run_time):
        board.type_word(self, row, word, run_time, per_letter=key_cues(self))

    def _pan(self, direction, run_time):
        """The camera moves one screen, whooshing (13's / 18's pan)."""
        self.sfx(WHOOSH_SFX, at=max(0.0, run_time / 2 - WHOOSH_PEAK), gain=WHOOSH_GAIN)
        self.play(self.camera.frame.animate.shift(direction), run_time=run_time)

    def _clear_except(self, keep):
        """Drop everything off screen but `keep` (and the camera frame)."""
        frame = self.camera.frame
        self.remove(*[m for m in self.mobjects if m is not frame and m not in keep])

    def _fill(self, cells, run_time):
        """The cells rise into place one after another — the video's table stagger
        (04 / 10 / 17: LaggedStart, lag 0.12, rising 0.3)."""
        self.play(LaggedStart(*[FadeIn(c, shift=UP * RISE) for c in cells],
                              lag_ratio=0.12), run_time=run_time)

    # a : the empty board, held (on screen from setup_scene)
    @subscene
    def blank(self):
        pass

    # b : AGAIN typed and scored against GREAT
    @subscene
    def again(self):
        g = RULES["guesses"][0]
        self._type(self.board, 0, g["word"], 0.65)
        self.board.reveal(self, 0, g["code"], 1.6)

    # c : SOLVE typed into the next row; refused, the row shakes; then backspaced
    @subscene
    def solve(self):
        self._type(self.board, 1, REFUSED, 0.65)
        self.board.shake(self, 1, 0.6)
        self.board.delete_word(self, 1, 0.6, per_press=backspace_cues(self))

    # d : AGAIN typed and scored, twice
    @subscene
    def again_twice(self):
        for row in (1, 2):
            g = RULES["guesses"][row]
            self._type(self.board, row, g["word"], 0.65)
            self.board.reveal(self, row, g["code"], 1.6)

    # e : GREAT typed and scored; the winning row jumps
    @subscene
    def great(self):
        g = RULES["guesses"][3]
        self._type(self.board, 3, g["word"], 0.65)
        self.board.reveal(self, 3, g["code"], 1.6)
        self.board.bounce(self, 3, 1.0)

    # f : every tile flips back to empty as the board moves left; an empty copy
    #     moves out from under it to the right
    def _setup_split(self):
        self.right = get_board().move_to(self.board)
        self.right.set_z_index(-1)

    @subscene
    def split(self):
        self._setup_split()
        self.add(self.right)
        d = LEFT * BOARD_X
        anims = []
        for r in range(self.board.n_rows):
            for c in range(self.board.n_cols):
                t, l = self.board.tiles[r][c], self.board.letters[r][c]
                if l is None:
                    anims.append(t.animate.shift(d))
                else:
                    anims.append(TileFlip(t, l, TILE_EMPTY_FILL, stroke=TILE_EMPTY_BORDER,
                                          swap_to=None, to_center=t.get_center() + d))
        self.play(*anims, self.right.animate.shift(RIGHT * BOARD_X), run_time=1.2)
        for r in range(self.board.n_rows):
            for c in range(self.board.n_cols):
                l = self.board.letters[r][c]
                if l is not None:
                    self.board.remove(l)
                    self.remove(l)
                    self.board.letters[r][c] = None
        self.right.set_z_index(0)
        self.left = self.board
        self.board = None

    # g, h : an example line typed and scored on one board
    def _play_line(self, board, line, lag_ratio=0.45, n_rows=None):
        """`lag_ratio` 0 flips a row's tiles all at once (19g and 19h, the user's call).
        `n_rows` plays only the line's first rows (19g and 19h stop at the second
        guess, the user's call)."""
        rows = list(zip(line["words"], line["codes"]))[:n_rows]
        for row, (w, code) in enumerate(rows):
            self._type(board, row, w, 0.65)
            board.reveal(self, row, code, 1.6 if lag_ratio else 0.6,
                         lag_ratio=lag_ratio)

    @subscene
    def keep_yellow(self):
        self._play_line(self.left, EX["keep_yellow"], lag_ratio=0, n_rows=2)

    @subscene
    def keep_grey(self):
        self._play_line(self.right, EX["keep_grey"], lag_ratio=0, n_rows=2)

    # ── i-l : the histogram ───────────────────────────────────────────────────
    def _callout_row(self, word):
        return get_typed_row(word)

    def _callout_spec(self, word):
        return CALLOUTS.get(word)       # a module constant, so the digest sees edits

    def _callout_stroke(self, row, w):
        for t in row.tiles[0]:
            t.set_stroke(width=STROKE * row.width / hv.WORD_W)

    # i : the boards are re-projected into the histogram's world one frame above it
    #     (nothing visibly changes), then the camera pans down to it
    def _setup_histogram(self):
        for m in [m for m in self.mobjects if m is not self.camera.frame]:
            hv.to_view(m, VIEW, shift=UP * VH)
        self.view = UPPER
        self._set_frame(*UPPER[:3])
        self.stacks = hv.full_stacks(squash=VIEW[3])
        self.stacks.refresh(self.camera.frame)
        self.chrome = hv.HistogramChrome(VIEW, AXIS_LO, AXIS_HI)
        self.add(self.stacks, self.chrome)
        # BEHIND everything: manim redraws only the mobjects from the first one with
        # an updater onward and freezes the rest into a still — the stacks carry the
        # move's updater, so the boards, ahead of them, rode the camera (fixed 19i)
        self.bring_to_back(self.stacks)

    @subscene
    def histogram(self):
        self._setup_histogram()
        self._move_view(VIEW, run_time=1.5, whoosh=True)
        self._clear_except([self.stacks, self.chrome])
        self.left = self.right = None

    # j : the histogram becomes hard mode's — each bar changes height IN PLACE
    #     (yahtzee 13's morph_panning: bars pair by bin), new bars growing from the
    #     axis on the right. The stacks swap for plain bars of identical look while
    #     they move, and back afterwards with every word at its hard-mode place.
    def _bars(self, bins):
        """One plain bar per bin over the whole range, `bins`' words tall —
        histogram_view.layer_bars, which draws exactly what the stacks draw."""
        counts = np.bincount(np.array(bins) - BIN_LO, minlength=self.n_bins)
        bars = hv.layer_bars(counts, hv.BAR_COLOR, squash=VIEW[3],
                             bins=np.arange(BIN_LO, BIN_LO + self.n_bins))
        # every bar OPAQUE: layer_bars hides an empty one, which made a bar that
        # empties FADE as it shrank. An empty bar is 1e-3 tall, so it cannot show.
        return bars.set_fill(opacity=1.0)

    def _setup_shift(self):
        self.n_bins = max(max(HIST["bins"]), max(DATA["hist"]["bins"])) - BIN_LO + 1
        self.bars_n = self._bars(HIST["bins"])
        self.bars_h = self._bars(DATA["hist"]["bins"])

    @subscene
    def shift(self):
        self._setup_shift()
        self.remove(self.stacks)
        self.add(self.bars_n)
        self.bring_to_back(self.bars_n)
        self.play(Transform(self.bars_n, self.bars_h), run_time=3.0)
        s = self.stacks
        s.x = s.x0 + (np.array(DATA["hist"]["bins"]) - s.bin0) * PITCH
        s.row = np.array(DATA["hist"]["rows"], dtype=float)
        s.refresh(self.camera.frame)
        self.remove(self.bars_n)
        self.add(s)
        self.bring_to_back(s)
        self.bars_n = self.bars_h = None

    # k, l : SALET, then TRACE, called out (08's callouts)
    @subscene
    def salet(self):
        self._move_view(VIEW, run_time=0.8, appear=["salet"])

    @subscene
    def trace(self):
        self._move_view(VIEW, run_time=0.8, appear=["trace"])

    # ── m-r : the turns table ─────────────────────────────────────────────────
    def _setup_turns_table(self):
        self.t_title = _title("Words by Turns to Solve", (0, 0))
        self.t_heads = VGroup(*[_cell(h, x, T_HEAD_Y, bold=True)
                                for h, x in zip(("Normal", "Hard"), T_COL_X[1:])])
        ys = {k: T_HEAD_Y - (i + 1) * T_ROW_DY for i, k in enumerate(TURNS)}
        self.t_labels = VGroup(*[_cell(k, T_COL_X[0], ys[k]) for k in TURNS])
        self.normal_cells = {k: _cell(f"{DATA['table']['normal'][k]:,}", T_COL_X[1], ys[k])
                             for k in TURNS}
        self.hard_cells = {k: _cell(f"{DATA['table']['hard'][k]:,}", T_COL_X[2], ys[k])
                           for k in TURNS}
        self.t_static = [self.t_title, self.t_heads, self.t_labels,
                         *self.normal_cells.values()]
        for m in self.t_static:
            hv.to_view(m, VIEW, shift=DOWN * VH)
        self.add(*self.t_static)

    @subscene
    def turns_table(self):
        self._setup_turns_table()
        # the callouts STOP being placed: a pinned callout is held at a fraction of
        # the FRAME, so it rode the camera down (fixed 19m). Let go, they are plain
        # mobjects at their place in the world and leave with the histogram.
        self.callouts = []
        self._move_view(LOWER, run_time=1.5, whoosh=True)
        # the seam back: everything on screen to the ordinary frame, invisibly
        self._clear_except(self.t_static)
        for m in self.t_static:
            hv.from_view(m, VIEW, shift=DOWN * VH)
        self._set_frame(-FRAME_W16 / 2, -FRAME_H / 2, FRAME_W16)
        self.stacks = self.chrome = self.view = None
        self.callouts = []

    @subscene
    def hard_5(self):
        self._fill([self.hard_cells["5"]], 0.5)

    @subscene
    def hard_6(self):
        self._fill([self.hard_cells["6"]], 0.5)

    @subscene
    def hard_7_10(self):
        self._fill([self.hard_cells[k] for k in TURNS[2:]], 1.0)

    # q : everything fades but Hard's row-10 number; it turns into the 14 words,
    #     gridded on the left half (19q and 19r merged in the Doc, 2026-10-03)
    def _setup_depth10(self):
        cells = grid_cells(len(DATA["depth10"]))
        self.ten_words = {w: _typed(w, WORD_W19, (WORDS_C[0] + cx * WORD_PITCH[0],
                                                  WORDS_C[1] + cy * WORD_PITCH[1]))
                          for w, (cx, cy) in zip(DATA["depth10"], cells)}

    @subscene
    def depth10(self):
        self._setup_depth10()
        # 1: everything else fades out WHILE the 14 becomes 14 dots where it stands,
        #    in the words' own arrangement
        gone = [*self.t_static, *[c for k, c in self.hard_cells.items() if k != "10"]]
        self.ten = self.hard_cells["10"]
        p = self.ten.get_center()
        cells = grid_cells(len(self.ten_words))
        dots = [Dot(point=p + np.array([cx * TEN_DOT_PITCH, cy * TEN_DOT_PITCH, 0]),
                    radius=TEN_DOT_R, color=DOT_COLOR) for cx, cy in cells]
        copies = [self.ten.copy() for _ in dots]
        self.remove(self.ten)
        self.play(*[FadeOut(m) for m in gone],
                  *[ReplacementTransform(c, d) for c, d in zip(copies, dots)],
                  run_time=0.8)
        self.remove(*gone)
        self.t_title = self.t_heads = self.t_labels = None
        self.t_static = self.normal_cells = self.hard_cells = None
        # 2: each dot travels to its word's place and becomes the word on the way —
        #    06b's word-to-dot cross-shrink, reversed
        words = list(self.ten_words.values())
        for w, d in zip(words, dots):
            w.save_state()
            w.scale(0.1).move_to(d).set_opacity(0)
        self.add(*words)
        self.play(*[Restore(w) for w in words],
                  *[d.animate.move_to(w.saved_state).scale(0.1).set_opacity(0)
                    for w, d in zip(words, dots)], run_time=1.2)
        self.remove(*dots)
        self.ten = None

    # r : the IGHT game flips in on the right, scored against WIGHT, its top row
    #     left empty for AUGHT
    def _setup_ight_game(self):
        n = len(IGHT["guesses"])
        g = WordleBoard(rows=n, cols=5)
        g.scale(GAME_H / g.height).move_to([*GAME_C, 0])
        for row in g.tiles:
            for t in row:
                t.set_stroke(width=_stroke(g))
        for t in g.tiles[0]:
            t.set_fill(opacity=0.0).set_stroke(opacity=0.0)
        self.flips = []
        for r in range(1, n):
            guess = IGHT["guesses"][r]
            row = []
            for c, (ch, k) in enumerate(zip(guess["word"], guess["tiles"])):
                t = g.tiles[r][c]
                t.set_fill(TILE_STATE[k], opacity=1.0).set_stroke(TILE_STATE[k])
                letter = g._letter(ch, t)
                g.letters[r][c] = letter
                g.add(letter)
                row.append(TileFlip(t, letter, TILE_STATE[k], appear=True))
            self.flips.append(LaggedStart(*row, lag_ratio=0.2))
        self.game = g

    @subscene
    def ight_game(self):
        self._setup_ight_game()
        self.add(self.game)
        self.play(LaggedStart(*self.flips, lag_ratio=0.15), run_time=3.0)
        self.flips = None

    # s : AUGHT travels up from the word grid into the game's top row; scored
    @subscene
    def aught(self):
        src = self.ten_words["aught"]
        top = self.game.rows[0]
        self.play(src.animate.scale_to_fit_width(top.width).move_to(top), run_time=1.0)
        for c, ch in enumerate(IGHT["guesses"][0]["word"]):
            t = self.game.tiles[0][c]
            t.set_fill(TILE_EMPTY_FILL, opacity=1.0).set_stroke(TILE_FILLED_BORDER,
                                                                opacity=1.0)
            letter = self.game._letter(ch, t)
            self.game.letters[0][c] = letter
            self.game.add(letter)
            self.add(letter)
        self.remove(src)
        del self.ten_words["aught"]
        self.game.reveal(self, 0, IGHT["guesses"][0]["code"], 1.6)

    # ── t-x : the families ────────────────────────────────────────────────────
    def _setup_families(self):
        y = F_DY
        heads = VGroup(*[_cell(h, x, y + F_HEAD_Y, bold=True)
                         for h, x in zip(("Max Guesses", "Family", "# Words"), F_COL_X)])
        self.f_text = [heads]
        self.f_pieces = []          # (row's family, letter or None, piece)
        self.f_rows = VGroup(heads)
        for i, f in enumerate(DATA["families"]):
            ry = y + F_ROW_Y0 - i * F_ROW_DY
            d = _cell(str(f["depth"]), F_COL_X[0], ry)
            n = _cell(str(f["size"]), F_COL_X[2], ry)
            row, pieces = _template(f["family"], F_TEMPLATE_W, [F_COL_X[1], ry, 0])
            self.f_text += [d, n]
            self.f_pieces += [(f["family"], ch, p) for ch, p in pieces]
            self.f_rows.add(d, row, n)
        self.f_rows.set_x(0)               # centred across the frame (the user's call)
        self.add(self.f_rows)

    @subscene
    def families(self):
        self._setup_families()
        self._pan(DOWN * FRAME_H, 1.5)
        self._clear_except([self.f_rows])
        self.ten_words = self.game = None

    @subscene
    def trace_up(self):
        # centred between the # Words numbers' right edge and the frame's
        right = max(m.get_right()[0] for m in self.f_text[2::2])
        x = (right + self.camera.frame.get_right()[0]) / 2
        self.trace_row = _typed("trace", TRACE_W, (x, F_DY + TRACE_C[1]))
        self.t_pieces = [(ch, VGroup(self.trace_row.tiles[0][i],
                                     self.trace_row.letters[0][i]))
                         for i, ch in enumerate("trace")]
        self.play(FadeIn(self.trace_row, shift=UP * RISE), run_time=0.6)

    def _emph(self, keep, run_time):
        """Every piece to full or dimmed; `keep(family, letter)` says which stay
        full (family is "trace" for TRACE's tiles); None restores everything."""
        anims = []
        pieces = self.f_pieces + [("trace", ch, p) for ch, p in self.t_pieces]
        for fam, ch, p in pieces:
            on = keep is None or (ch is not None and keep(fam, ch))
            anims.append(p.animate.set_opacity(1.0 if on else DIM))
        anims += [m.animate.set_opacity(1.0 if keep is None else DIM) for m in self.f_text]
        self.play(*anims, run_time=run_time)

    @subscene
    def emph_er(self):
        self._emph(lambda fam, ch: ch in "er" and "e" in fam and "r" in fam, 0.8)

    @subscene
    def emph_atc(self):
        self._emph(lambda fam, ch: fam in (".atch", "trace") and ch in "atc", 0.8)

    @subscene
    def unemph(self):
        self._emph(None, 0.8)

    # y : pan right to the fast openers
    def _setup_fast(self):
        c = (Z_DX, F_DY)
        self.z_title = _title("Top Fast Openers", c)
        self.z_words = VGroup(*[_typed(w, FAST_W, (c[0], c[1] + FAST_Y0 - i * FAST_DY))
                                for i, w in enumerate(DATA["fast"])])
        self.add(self.z_title, self.z_words)

    @subscene
    def fast(self):
        self._setup_fast()
        self._pan(RIGHT * FRAME_W16, 1.5)
        self._clear_except([self.z_title, self.z_words])
        self.f_rows = self.trace_row = self.f_pieces = self.t_pieces = None
        self.f_text = None

    # z : pan down to hard mode's letter table (18's), the hard tier list on the
    #      right — both only once their data exist (see the docstring)
    def _setup_letters(self):
        c = np.array([Z_DX, ZA_DY, 0.0])
        title = crisp_text("Appearances in First ___ Guesses", font_size=FONT_SIZE_LG,
                           color=WHITE)
        title.move_to(c + UP * (FRAME_H / 2 - TITLE_BUFF - title.height / 2))
        title.set_x(c[0] + TABLE_CX)
        sub = crisp_text("(Top 1000 Openers, Hard Mode)", font_size=FONT_SIZE_MD, color=WHITE)
        sub.next_to(title, DOWN, buff=SUB_BUFF)
        heads = VGroup(*[_cell(h, c[0] + x, c[1] + HEAD_Y, bold=True)
                         for h, x in zip(("1", "2"), COL_X)])
        self.za = VGroup(title, sub, heads)
        tiers, cov = td.WORDLE_HARD_LETTERS, DATA["coverage"]
        if tiers is not None and cov is not None:
            box_stroke = STROKE * tl.BOX_FILL_FRAC * tl.LETTER_PITCH * LIST_SCALE / TILE
            box = {"fill": TILE_EMPTY_FILL, "stroke_color": TILE_FILLED_BORDER,
                   "stroke_width": box_stroke}
            lst = tl.filled_list(tiers, names=td.WORDLE_NAMES, scale=CORNER_SCALE,
                                 panel_fill=td.PANEL_ON_NAVY, box=box)
            lst.move_to(c + np.array([*CORNER_UR, 0]), aligned_edge=UR)
            self.za.add(lst)
            for k, ch in enumerate("".join(tiers[:4])):
                y = c[1] + HEAD_Y - (k + 1) * ROW_DY
                b = tl.letter_box(ch.lower(), TABLE_BOX, box).move_to(
                    [c[0] + LETTER_X, y, 0])
                b.box.set_stroke(width=box_stroke)
                self.za.add(b)
                for col in (0, 1):
                    pct = 100 * cov["counts"][ch.lower()][col] / cov["paths"]
                    share = cov["counts"][ch.lower()][col] / cov["paths"]
                    self.za.add(_cell(f"{pct:.2f}%", c[0] + COL_X[col], y)
                                .set_color(win_color(share, mid=TABLE_MID)))
        self.add(self.za)

    @subscene
    def letters(self):
        self._setup_letters()
        self._pan(DOWN * FRAME_H, 1.5)
        self._clear_except([self.za])
        self.z_title = self.z_words = None
