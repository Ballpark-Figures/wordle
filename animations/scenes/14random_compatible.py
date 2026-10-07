"""Scene 14 — one word of our choice, then random compatible answers; and how much
each guess matters. Navy background.

Talking head THI precedes it, so a starts on an empty frame. Scene 15 follows
directly, and i ends with everything faded out (user's call, 2026-10-01).

BEAT MAP — one subscene per Script.md beat, letters matching:

  a chose_game  — the scene OPENS on a blank board, its top row where CHOSE goes; the
                  rest of the board fades as CHOSE is typed (user 2026-10-07); then
                  scene 13's game again, from CHOSE (the "word of our choice"; the
                  script's CHOICE has six letters), against WOVEN: CHOSE typed and
                  flipped BBYBY, its 66 compatible answers in, and each next word
                  selected straight away (no random hops, per the script): VIDEO
                  (YBBGY, 5 left), NOVEL (YGGGB, 1 left), WOVEN (GGGGG, the win
                  bounce)                                               (14a, VO 1)
  b chose_line  — the camera pans down to scene 13's number line (the game leaves
                  upward), now 3.42 at the left and Random Compatible's 4.08 at the
                  right (user's call); the CHOSE marker pops out at 3.99 (98.53%)
                                                                        (14b, VO 1)
  c slate       — CHOSE flips to SLATE as its marker slides left to 3.82, its win
                  rate counting up to 98.87%                            (14c, VO 1)
  d table       — the camera pans down again (the line leaves upward) to the title
                  "Random Compatible on Turn ___ / Optimal Elsewhere" and a table:
                  turns 1-5 down the left, "Average Guesses" over the right
                                                                        (14d, VO 2)
  e turn5       — 3.4212 in row 5                                       (14e, VO 3)
  f turn4       — 3.4225 in row 4                                       (14f, VO 4)
  g turn1       — 3.61 in row 1                                         (14g, VO 5)
  h turn3       — 3.49 in row 3                                         (14h, VO 6)
  i turn2       — 3.67 in row 2; then everything fades out              (14i, VO 6)

REUSE MAP — every element, the one source it comes from, and how it enters:
  the game (a)          assets/strategy_line.py `StrategyLine` — scene 13's game,
                        moved there unchanged: typed rows `_type`, flips `_flip`,
                        the grid `_words_in`/`_regrid`, the highlight `_hops` (a
                        single hop, the next guess), the win `_win`
  CHOSE in (a)          typed as it appears (13's `_type`); the scene opens on it
  number line (b)       StrategyLine `_build_line` (13's title, subtitle and line),
                        bpkfigures ZoomLine; the 3.42 and 4.08 markers are
                        StrategyLine `optimal_marker`/`compatible_marker`, 13's
  line in (b)           already in place one frame below the game; the camera pans
                        down to it (`_pan_down`, 13k's pan; silent)
  CHOSE marker (b)      13's marker card (`_marker`), CHOSE as a tile row like 13b's
                        SALET (`word_line`); pops out of its dot with the pop sound
                        (`_pop_in`, 13's)
  CHOSE -> SLATE (c)    StrategyLine `replace_marker` (moved there from this beat for
                        scene 15): assets/flip.py `Flip(..., travel=True)` by
                        `row_parts`, the row sliding with its marker (bpkfigures
                        ZoomLine `move_marker`, added for this beat); the win rate
                        counting by bpkfigures style.py `CrispCounter` (`count_anim`,
                        so the count can ride the moving card), coloured by
                        StrategyLine `win_color`
  title (d)             crisp_text, WHITE, FONT_SIZE_LG — 13's title
  table (d)             scene 10's table: bold header at 28, cells at 30, rows 0.72
                        apart (10word_lengths.py:178-186, 409-416)
  stripes (d)           bpkfigures.table.row_stripes (the dark-background zebra,
                        user's call 2026-10-05), in place with the table
  table in (d)          already in place one frame below the line; the camera pans
                        down to it (13k's pan, as b)
  cells (e-i)           10's `_fill_avg`: FadeIn rising 0.3 (10word_lengths.py:437)
  the end (i)           FadeOut of everything
  colours               BOARD_NAVY via WordleBoardScene, as 13

EVERY NUMBER is sourced (assets/random_compatible_data.py -> its cache; provenance
there), except the two line markers carried over from scene 13 (its docstring):
  CHOSE   3.99 (3.987382), 98.53% (0.985295)   openexact, exact
  SLATE   3.82 (3.821367), 98.87% (0.988670)   openexact, exact (user's call: the
                                               exact rate, not the race's 98.86%)
  turn 1..5   3.61 3.67 3.49 3.4225 3.4212     kthrandom (k=1 the answer-word
                                               openers' optimal totals, averaged)
The markers' averages are shown only by where they sit (13's convention).

LAYOUT CHOICES, flagged:
  - The game is 13's, set one frame above the line, so a -> b and b -> d are pans
    and nothing fades (13's convention).
  - Every compatible answer shown, all 66 after CHOSE.
  - The CHOSE/SLATE card hangs above the line (4.08's is below, 3.42's is far left).
  - Its text is "Then RCA" under the tiles (user's call, 2026-10-01; it was "then
    Random" / "Compatible"); the 4.08 card bolds its own R, C and A to match.
  - The table's left column has no header (the script labels only the right one).
    Its title's blank is a short line of underscores (user's call).
  - Decimal places as the script writes them: 4 for turns 4 and 5, 2 for 1-3
    (`_fmt`).
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from assets import random_game_data, random_compatible_data
from assets.board import WordleBoard, GAP, TILE
from assets.pigpen import PigpenWord
from assets.keys import key_cues
from bpkfigures.table import row_stripes
from assets.strategy_line import (StrategyLine, GAME_DY, TITLE_BUFF,
                                  OPTIMAL, COMPATIBLE, word_line, rate_text)

DATA = random_compatible_data.load()
CHOSE, SLATE = DATA["openers"]["chose"], DATA["openers"]["slate"]
TURNS = {int(k): v for k, v in DATA["turns"].items()}

TABLE_TITLE = ["Random Compatible on Turn ___", "Optimal Elsewhere"]
TITLE_GAP = 0.15                # between the title's two lines
TABLE_TOP = 1.3                 # the header row's centre, in the table's frame
ROW_DY = 0.72                   # scene 10's
AVG_X = 0.0                     # the Average Guesses column's centre: the screen's
                                # (user's call); the averages, aligned on their
                                # decimal points, are centred on it as a block
TURN_X = AVG_X - 3.8            # the turn column's centre, as far left as before
HEADER_SIZE = 28                # scene 10's
CELL_SIZE = 30                  # scene 10's
SMALL_SIZE = 20                 # rows 4-5's third and fourth decimals (user's call)
SMALL_GAP = 0.02                # between the two-place part and the small digits
TABLE_DY = -GAME_DY             # the table sits one frame below the line
DP = {1: 2, 2: 2, 3: 2, 4: 4, 5: 4}   # the script's decimal places per row
STRIPE_PAD = 0.5                # the stripes' overhang past the turns and the averages


def _fmt(k):
    """Turn k's average as the table shows it."""
    return f"{TURNS[k]:.{DP[k]}f}"


def _cell(k, dot_x):
    """Turn k's average: the first two decimals at the cell size and any further
    ones smaller, sharing a baseline, the decimal point at dot_x."""
    s = _fmt(k)
    big = crisp_text(s[:4], font_size=CELL_SIZE, color=WHITE)
    big.move_to([0, _row_y(k), 0])
    big.shift(RIGHT * (dot_x - big[1].get_center()[0]))      # big[1] is the "."
    cell = VGroup(big)
    if len(s) > 4:
        small = crisp_text(s[4:], font_size=SMALL_SIZE, color=WHITE)
        small.next_to(big, RIGHT, buff=SMALL_GAP).align_to(big, DOWN)  # digits: bottom = baseline
        cell.add(small)
    return cell


def _row_y(k):
    return TABLE_DY + TABLE_TOP - k * ROW_DY


class Scene14(StrategyLine, MovingCameraScene, WordleBoardScene):
    """chose_game — CHOSE, VIDEO, NOVEL, WOVEN, each next word selected at once
    chose_line — pan down to the line; the CHOSE marker at 3.99
    slate — CHOSE flips to SLATE, sliding to 3.82; 98.53% counts to 98.87%
    table — pan down to the title and the turn table
    turn5 — 3.4212
    turn4 — 3.4225
    turn1 — 3.61
    turn3 — 3.49
    turn2 — 3.67
    fade_out — everything out
    """

    def setup_scene(self):
        self.game = random_game_data.load("14")
        self.camera.frame.move_to([0, GAME_DY, 0])     # the game's frame
        # on screen from frame 0 (user 2026-10-07): a full blank board whose top row
        # IS the game's first row, where CHOSE is typed; the five below it fade out
        # as CHOSE types (a). Built as the first row + a 5-row block, so the game's
        # later rows still stack under CHOSE exactly as StrategyLine stacks them.
        self.word_w = PigpenWord("salet", revealed=True).width
        self.rows = []
        self.first_row = self._new_row()
        self.rest_rows = WordleBoard(rows=5, cols=5)
        self.rest_rows.scale(self.first_row.width / self.rest_rows.width)
        self.rest_rows.next_to(self.first_row, DOWN,
                               buff=self.first_row.tiles[0][0].height * GAP / TILE)
        self.add(self.first_row, self.rest_rows)

    # a : the DICEY game again from CHOSE, each next word selected straight away
    @subscene
    def chose_game(self):
        self._setup_game()
        self.rows = [self.first_row]          # the blank board's top row
        # CHOSE types into it while the rest of the board fades over the typing
        typing, total = self.first_row.type_anim(self, 0, self.game["words"][0], 0.65,
                                                 per_letter=key_cues(self))
        self.play(typing, FadeOut(self.rest_rows), run_time=total)
        self.remove(self.rest_rows)
        self.first_row = self.rest_rows = None
        self._flip(0, 1.6)
        self._words_in(0.8)
        self._hops(0, 0.3)
        self._turn(1, 0.65, 1.6, 1.0, 0.3)
        self._turn(2, 0.65, 1.6, 1.0, 0.3)
        self._win(3, 0.65, 1.6, 1.0)

    # b : pan down to the number line (3.42 .. 4.08); CHOSE's marker at 3.99
    def _setup_chose_line(self):
        self._build_line(OPTIMAL[0], COMPATIBLE[0])
        self.optimal_marker(grow=1.0)
        self.compatible_marker(grow=1.0)
        self.chose_mk = self.opener_marker(round(CHOSE["mean"], 2), ["chose"],
                                           CHOSE["win_rate"])
        self.add(self.line, self.title, self.subtitle)

    @subscene
    def chose_line(self):
        self._setup_chose_line()
        self._pan_down(1.5)
        self.remove(*self.rows)            # off-frame now; keeps the snapshot light
        self.rows = []
        self._pop_in(self.chose_mk, 0.4)

    # c : CHOSE flips to SLATE as the marker slides to 3.82; the rate counts up
    @subscene
    def slate(self):
        self.replace_marker(self.chose_mk, ["slate"], round(SLATE["mean"], 2),
                            SLATE["win_rate"], 1.2)

    # d : pan down to the title and the table
    def _setup_table(self):
        lines = [crisp_text(t, color=WHITE, font_size=FONT_SIZE_LG) for t in TABLE_TITLE]
        self.table_title = VGroup(*lines).arrange(DOWN, buff=TITLE_GAP)
        self.table_title.to_edge(UP, buff=TITLE_BUFF).shift(UP * TABLE_DY)
        self.table_head = crisp_text("Average Guesses", font_size=HEADER_SIZE,
                                     color=WHITE, weight=BOLD).move_to([AVG_X, _row_y(0), 0])
        self.table_turns = VGroup(*[crisp_text(str(k), font_size=CELL_SIZE, color=WHITE)
                                    .move_to([TURN_X, _row_y(k), 0]) for k in range(1, 6)])
        # the decimal point's x that centres the aligned averages on AVG_X
        block = VGroup(*[_cell(k, 0.0) for k in range(1, 6)])
        self.dot_x = AVG_X - block.get_center()[0]
        # zebra stripes, from the turn column to the averages' (or the head's) right
        right = max(block.get_right()[0] + self.dot_x, self.table_head.get_right()[0])
        self.table_stripes = row_stripes([_row_y(k) for k in range(1, 6)],
                                         self.table_turns.get_left()[0] - STRIPE_PAD,
                                         right + STRIPE_PAD, ROW_DY)
        self.add(self.table_stripes, self.table_title, self.table_head, self.table_turns)

    @subscene
    def table(self):
        self._setup_table()
        self._pan_down(1.5)
        self.remove(self.line, self.title, self.subtitle)   # off-frame now
        self.line = self.title = self.subtitle = self.chose_mk = None
        self.cells = VGroup()

    # e-i : the averages, one row at a time
    def _fill(self, k, run_time):
        """Turn k's average rises into its cell (10's `_fill_avg`)."""
        cell = _cell(k, self.dot_x)
        self.cells.add(cell)
        self.play(FadeIn(cell, shift=UP * 0.3), run_time=run_time)

    # e : 3.4212 in row 5
    @subscene
    def turn5(self):
        self._fill(5, 0.5)

    # f : 3.4225 in row 4
    @subscene
    def turn4(self):
        self._fill(4, 0.5)

    # g : 3.61 in row 1
    @subscene
    def turn1(self):
        self._fill(1, 0.5)

    # h : 3.49 in row 3
    @subscene
    def turn3(self):
        self._fill(3, 0.5)

    # i : 3.67 in row 2
    @subscene
    def turn2(self):
        self._fill(2, 0.5)

    # j : everything fades out (its own beat, user's call; not yet in the Doc)
    @subscene
    def fade_out(self):
        self.play(FadeOut(*self.mobjects), run_time=0.8)
