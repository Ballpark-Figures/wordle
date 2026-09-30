"""SCENE 10 — SALET's guess distribution, two of its games, and word lengths.

Opens on Wordle's black (WordleDarkScene, WORDLE_BG), the colour scene 09 ends on;
d turns it back to navy. Follows scene 09 directly, so it opens EMPTY and brings the
chart in. Talking head THG follows, so it ends with the vowel board up.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a distribution — the Wordle-stats "guess distribution" chart for SALET's optimal
                   strategy grows in: rows 1-6, one bar each, count inside  (VO 1)
  b game_third   — bar 3 turns green; a mini board of SALET, NORTH, THIRD,
                   already scored, fades in above bar 3                      (VO 1)
  c game_wheel   — bar 3 back to grey, bar 4 green; a mini board of SALET,
                   BEVOR, CHIMP, WHEEL fades in below bar 3                  (VO 1)
  d wheel_center — ONE play: bar 4 greys as the chart and the THIRD board fade,
                   the background turns navy, and the WHEEL board grows to the
                   middle with its WHEEL row fading while every other tile
                   FLIPS to black, keeping only the A (SALET), E O (BEVOR) and
                   I (CHIMP), the T flipping to Y and the V to U (the user's) (VO 1)
  e triple_vowels — the tiles flip, one play each, through where the three best
                   all-six-vowel triples in the singletons ranking put the
                   vowels: CURSE PAINT GODLY, CURSE POINT BADLY, BIONT CARSE
                   DUPLY                                                     (VO 2)
  f adieu        — ADIEU in the first word, O in the middle of the second, Y at
                   the end of the third                                      (VO 3)
  g audio        — AUDIO in the first word, E in the middle of the second
                   (the script says U; the user's correction)                (VO 3)
  h crypt        — CRYPT in the third word                                   (VO 3)
  i table        — the boxes fade out; a table comes in: Word Length /
                   Average Guesses / Best Opener, one row per length, 3 to 11 (the
                   longest with results) — only the lengths filled          (VO 4)
  j salet_row    — SALET typed into length 5's row as tiles, then 3.42       (VO 4)
  k avg_6 / l opener_6 / m avg_7 / n opener_7 — one cell each               (VO 5)
  o both_8 / p both_9 / q both_10 / r both_11 — average, then opener        (VO 5)
  s avg_4 / t opener_4 — t then puts TALE's all-grey path (its tree's longest
                   all-grey line, to the answer) in the top-right corner    (VO 6)
  u avg_3 / v opener_3 — v swaps in RAS's all-grey path in its place       (VO 7)
  j and o-r fill a whole row the same way: average, then opener.
  An average fades in; an opener is TYPED in as tiles, as SALET is, its letters
  coloured vowel red / consonant blue (hangman's rule, Y a vowel — the user's).
  EVERY LETTER CHANGE IS A FLIP (the user's): a tile turns over and shows its new
  letter, or none — nothing slides or morphs. Only tiles that change flip, left to
  right, top to bottom. Every tile has the same border.

REUSE MAP — every element and the one source it comes from:
  chart          bpkfigures.bar_graph.get_bar_chart(orientation="horizontal",
                 min_length=…, value_inside=True) — the horizontal mode was added
                 for this scene; entrance bar_graph.grow_bars(edge=LEFT)
  bar colours    config.py TILE_ABSENT (Wordle's grey, as the real stats graph);
                 TILE_CORRECT for a highlighted row, as Wordle marks today's game
  text           crisp_text, white; title bold
  boards         assets/board.py get_scored_row, one per guess, stacked at the
                 board's own GAP and scaled down
  background     assets/background.py bg_to (promoted from scene 01's _bg_to)
  table letters  bpkfigures.tier_list.tile_color (hangman's vowel/consonant colours
                 for letters on a dark panel), via board.type_word's letter_color
  letter flips   assets/board.py TileFlip, with the swap_to / to_center / to_scale
                 options added for this scene (off by default)

NUMBERS — all SOURCED, from assets/word_lengths_data.py -> word_lengths_cache.json:
  counts per row   SALET's committed optimal tree (constrained to 6 guesses),
                   asserted there to sum to 2315 answers and 7920 guesses
  THIRD / WHEEL    those answers' lines in the same tree, codes re-checked against
                   math/wordle.py pattern()
  the table      word_lengths_data `table`: each length's opener and total from
                   the file the user chose (TABLE_SOURCES there); averages 2 dp.
                   NOT one kind of result — 3 is a beam's upper bound, 4 exact over
                   only 4 openers, 6 provisional, 7-11 complete; caps differ
  10e's triples   the first three rows of the singletons triple ranking
                   (math/data/shared/singletons/triple_singletons.csv, ranks 365,
                   380, 478 of the top 100000 of a greedy screen) using all six
                   vowels

ON-SCREEN TEXT beyond column 2 (the user's call): the "GUESS DISTRIBUTION" title,
in the real Wordle stats screen's capitals.

THE TABLE MIXES WORD LISTS, as the script asks: length 5 is SALET on the NYT lists
(the rest of this video's problem); every other length is hello wordl's lists
(math/data/shared/LENGTHS.md), a different curation. Its averages are also optima
under different depth caps, per length. The table rows are
word_lengths_data's `lengths` (every length with a result directory).

LAYOUT (the user's): the chart follows Wordle's stats screen — title flush left with
the row numbers, row numbers and counts one size, bars close together. Both boards
start a little right of bar 4's end: THIRD's above bar 3, WHEEL's below it. Boards
have only as many rows as the game used. A bar is green only during its own game's
beat (the user's): 3 in b, 4 in c.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.bar_graph import get_bar_chart, grow_bars
from assets.board import get_board, get_scored_row, GAP, TileFlip
from assets.keys import key_cues
from bpkfigures.tier_list import tile_color
from assets.background import bg_to
from assets import word_lengths_data

DATA = word_lengths_data.load()
DIST = [(n, DATA["distribution"][n]) for n in sorted(DATA["distribution"], key=int)]
GAMES = DATA["games"]

# ── the chart ─────────────────────────────────────────────────────────────────
# Wordle's stats screen: 20px bars 4px apart, row numbers and counts one size, the
# title a little larger and flush left with the row numbers.
CHART_CENTER = np.array([-0.7, 0.075, 0])
CHART_WIDTH = 9.0            # a full-length bar (1231)
ROW_PITCH = 0.55
CHART_HEIGHT = 6 * ROW_PITCH
BAR_RATIO = 0.83
MIN_BAR = 0.55               # the stub a 0 row keeps, wide enough for its "0"
NUM_SIZE = FONT_SIZE_SM      # row numbers AND counts
TITLE_SIZE = 28

# ── the mini boards ───────────────────────────────────────────────────────────
BOARD_SCALE = 0.7
BOARD_GAP_X = 0.8            # boards start this far right of bar 4's end
BOARD_GAP_Y = 0.4            # THIRD this far above bar 3, WHEEL this far below

# ── d-h: what each of the three rows' tiles shows, {(row, position): letter} ──
# Every change of letter is a FLIP (board.TileFlip's swap_to): the tile turns over
# and shows its new letter, or none, on the new face.
VOWELS = "aeiouy"                # Y a vowel, the video's convention
_ROWS = [g["word"] for g in DATA["games"]["wheel"]["guesses"][:3]]
assert _ROWS == ["salet", "bevor", "chimp"], _ROWS


def _vowels_in(word, row):
    return {(row, i): c for i, c in enumerate(word) if c in VOWELS}


def _word_at(word, row):
    return {(row, i): c for i, c in enumerate(word)}


# d: SALET / BEVOR / CHIMP down to their vowels — the A; the E, O; the I — with the
#    T and the V flipping to Y and U (the user's call), so the three rows hold all
#    six vowels, spread across the three guesses
BOARD_D = {(0, 1): "a", (0, 4): "y", (1, 1): "e", (1, 2): "u", (1, 3): "o",
           (2, 2): "i"}
assert [_ROWS[0][4], _ROWS[1][2]] == ["t", "v"]
assert all(_ROWS[r][i] == c for (r, i), c in BOARD_D.items() if c not in "yu")
# e: the best all-six-vowel triples in the singletons ranking (sourced), in rank
#    order — the vowels flip through each in turn
TRIPLES = [t["words"] for t in DATA["vowel_triples"]]
BOARDS_E = [{k: v for r, w in enumerate(t) for k, v in _vowels_in(w, r).items()}
            for t in TRIPLES]
# f: ADIEU in the first word, O mid second word, Y ending the third (Script.md 10f)
BOARD_F = {**_word_at("adieu", 0), (1, 2): "o", (2, 4): "y"}
# g: AUDIO, E mid second word (the user's correction of the script's "U")
BOARD_G = {**_word_at("audio", 0), (1, 2): "e", (2, 4): "y"}
# h: AUDIO / E / CRYPT
CRYPT = "crypt"
BOARD_H = {**_word_at("audio", 0), (1, 2): "e", **_word_at(CRYPT, 2)}
for _b in [BOARD_D] + BOARDS_E + [BOARD_F, BOARD_G, BOARD_H]:
    assert set(VOWELS) <= set(_b.values()), _b

# ── i-j: the word-length table ────────────────────────────────────────────────
LENGTHS = DATA["lengths"]                 # 3 .. the longest length with results
HEADERS = ["Word Length", "Average Guesses", "Best Opener"]
HEADER_Y = 3.4                            # header row's centre
ROW_Y0 = 2.55                             # first data row's centre
ROW_DY = 0.72
LEN_X = -5.7                              # Word Length column's centre
AVG_X = -1.8                              # Average Guesses column's centre
OPENER_X = 0.6                            # Best Opener column's LEFT edge (tiles
                                          # left-aligned, so every word starts there)
TABLE_TILE_SCALE = 0.6                    # opener tiles vs a full board tile
HEADER_SIZE = 28
CELL_SIZE = 30


TABLE = {int(L): t for L, t in DATA["table"].items()}
GREY_PATHS = {int(L): p for L, p in DATA["grey_paths"].items()}
# the corner the all-grey paths sit in: top-right, clear of the header and of the
# longer openers' rows (row 7's SALTINE ends at x 4.8)
CORNER_UR = (7.6, 4.2)
CORNER_W = 3.0
CORNER_H = 4.1
assert sorted(TABLE) == LENGTHS


def _row_y(L):
    return ROW_Y0 - LENGTHS.index(L) * ROW_DY


def _avg(total, answers):
    """An average guess count as shown in the table: 2 dp, the VO's "3.18"."""
    return f"{total / answers:.2f}"


class Scene10(WordleDarkScene):
    """BEAT MAP
    distribution — SALET's guess-distribution chart grows in
    game_third — bar 3 green; SALET's scored game for THIRD fades in above it
    game_wheel — bar 3 grey, bar 4 green; SALET's game for WHEEL fades in below bar 3
    wheel_center — chart and THIRD board leave, bg to navy, WHEEL board to the
                   middle minus its WHEEL row, tiles flipping to black vowels
    triple_vowels — flips through the top three all-six-vowel triples' vowels
    adieu — flips to ADIEU / O mid row 2 / Y end of row 3
    audio — flips to AUDIO / E mid row 2
    crypt — flips to CRYPT in row 3
    table — boxes out; the word-length table in, lengths only
    salet_row — SALET typed in as tiles, 3.42 beside it
    avg_6, opener_6, avg_7, opener_7 — one cell each
    both_8, both_9, both_10, both_11 — average then opener
    avg_4, opener_4, avg_3, opener_3 — one cell each
    """

    def setup_scene(self):
        pass

    # ── builders ─────────────────────────────────────────────────────────────
    def _setup_chart(self):
        white = lambda s, fs: crisp_text(str(s), font_size=fs, color=WHITE,
                                         weight=BOLD)
        title = crisp_text("GUESS DISTRIBUTION", font_size=TITLE_SIZE, color=WHITE,
                           weight=BOLD)
        self.chart = get_bar_chart(
            DIST, orientation="horizontal", center=CHART_CENTER,
            width=CHART_WIDTH, height=CHART_HEIGHT, bar_ratio=BAR_RATIO,
            bar_color=TILE_ABSENT, ink_color=WHITE, min_length=MIN_BAR,
            label_factory=lambda s: white(s, NUM_SIZE), label_buff=0.2,
            value_labels=True, value_inside=True, value_buff=0.15,
            value_factory=lambda v: white(v, NUM_SIZE),
            title_mobject=title, title_buff=0.35)
        title.align_to(self.chart.labels, LEFT)

    def _setup_board(self, answer, below):
        """SALET's finished game for `answer`, scored, as a mini board a little
        right of bar 4's end — under bar 3 if `below` (WHEEL), else over it."""
        rows = [get_scored_row(g["word"], g["code"])
                for g in GAMES[answer]["guesses"]]
        board = VGroup(*rows).arrange(DOWN, buff=GAP).scale(BOARD_SCALE)
        bar3, bar4 = self.chart.bar_of["3"], self.chart.bar_of["4"]
        board.align_to(bar4.get_right() + RIGHT * BOARD_GAP_X, LEFT)
        if below:
            board.align_to(bar3.get_bottom() + DOWN * BOARD_GAP_Y, UP)
        else:
            board.align_to(bar3.get_top() + UP * BOARD_GAP_Y, DOWN)
        return board

    def _bar_color(self, n, color):
        return self.chart.bar_of[n].animate.set_fill(color).set_stroke(color)

    # a : SALET's guess distribution grows in
    @subscene
    def distribution(self):
        self._setup_chart()
        c = self.chart
        self.play(FadeIn(c.title), FadeIn(c.labels), run_time=0.8)
        grow_bars(self, c.bars, 1.5, lag=0.08, edge=LEFT)
        self.play(FadeIn(c.values), run_time=0.6)

    # b : bar 3 turns green; SALET's game for THIRD fades in above it
    @subscene
    def game_third(self):
        self.board_third = self._setup_board("third", below=False)
        self.play(self._bar_color("3", TILE_CORRECT), FadeIn(self.board_third),
                  run_time=0.8)

    # c : bar 3 back to grey, bar 4 green; SALET's game for WHEEL fades in below bar 3
    @subscene
    def game_wheel(self):
        self.board_wheel = self._setup_board("wheel", below=True)
        self.play(self._bar_color("3", TILE_ABSENT), self._bar_color("4", TILE_CORRECT),
                  FadeIn(self.board_wheel), run_time=0.8)

    # d : ONE play — bar 4 greys as the chart and THIRD's board fade, the background
    #     turns navy, and WHEEL's board grows to the middle with its WHEEL row
    #     fading, while EVERY tile of the other three rows flips to Wordle's empty
    #     black, showing BOARD_D's letter (or none) on its new face
    def _setup_wheel_center(self):
        c = self.chart
        bar4 = c.bar_of["4"]
        # bar 4 is animated on its own (grey AND out), so the rest of the chart
        # fades without it — one mobject, one animation
        self.chart_rest = [b for b in c.bars if b is not bar4] + \
                          [c.labels, c.values, c.title]
        self.upper = VGroup(*self.board_wheel[:-1])      # SALET, BEVOR, CHIMP
        self.wheel_row = self.board_wheel[-1]
        # full tile size, with the three rows that stay centred in the frame
        self.k = 1 / BOARD_SCALE
        self.pivot = self.board_wheel.get_center()
        grown = self.upper.copy().scale(self.k, about_point=self.pivot)
        self.to_mid = ORIGIN - grown.get_center()
        grown.shift(self.to_mid)
        self.end_center = {(r, i): grown[r].tiles[0][i].get_center()
                           for r in range(3) for i in range(5)}
        # BOARD_D's letters, built on the tiles' END pose; each flip shows its own
        self.shown = {}                     # (row, position) -> the letter showing
        self.new_d = {}
        for (r, i), ch in BOARD_D.items():
            self.new_d[(r, i)] = self._new_letter(r, i, ch, grown[r].tiles[0][i])

    def _new_letter(self, r, i, ch, tile):
        """A letter for tile (r, i), built on `tile`'s pose, hidden until its flip."""
        letter = self.upper[r]._letter(ch, tile)
        letter.set_opacity(0)
        self.upper[r].add(letter)
        self.add(letter)
        return letter

    def _flip(self, r, i, new, **kwargs):
        """Tile (r, i) flips to the empty black face showing `new` (or nothing)."""
        tile = self.upper[r].tiles[0][i]
        old = self.shown.get((r, i))
        self.shown[(r, i)] = new
        return TileFlip(tile, old, TILE_EMPTY_FILL, stroke=TILE_FILLED_BORDER,
                        swap_to=new, **kwargs)

    def _move(self, m):
        """`m`'s animation to its place in the grown, centred board."""
        return m.animate.scale(self.k, about_point=self.pivot).shift(self.to_mid)

    @subscene
    def wheel_center(self):
        self._setup_wheel_center()
        bar4 = self.chart.bar_of["4"]
        self.shown = {(r, i): self.upper[r].letters[0][i]
                      for r in range(3) for i in range(5)}
        flips = [self._flip(r, i, self.new_d.get((r, i)),
                            to_center=self.end_center[(r, i)], to_scale=self.k)
                 for r in range(3) for i in range(5)]
        self.play(bar4.animate.set_fill(TILE_ABSENT, opacity=0)
                      .set_stroke(TILE_ABSENT, opacity=0),
                  FadeOut(*self.chart_rest), FadeOut(self.board_third),
                  bg_to(self, BOARD_NAVY),
                  self._move(self.wheel_row).set_opacity(0),
                  *flips, run_time=1.2)
        self.remove(self.chart, bar4, self.board_third, self.wheel_row)
        self.board_wheel.remove(self.wheel_row)
        self.chart = self.board_third = self.wheel_row = self.new_d = None
        self.board = BOARD_D

    # ── e-h: the three rows flip from one board to the next ───────────────────
    def _flip_to(self, board, run_time, lag=0.1):
        """ONE play: every tile whose letter differs between the current board and
        `board` flips to show its new one, left to right, top to bottom."""
        flips = []
        for r in range(3):
            for i in range(5):
                ch = board.get((r, i))
                if ch == self.board.get((r, i)):
                    continue
                new = None if ch is None else \
                    self._new_letter(r, i, ch, self.upper[r].tiles[0][i])
                flips.append(self._flip(r, i, new))
        self.board = board
        self.play(LaggedStart(*flips, lag_ratio=lag), run_time=run_time)

    # e : the vowels flip through the best three all-six-vowel triples' positions
    @subscene
    def triple_vowels(self):
        self._flip_to(BOARDS_E[0], 1.2)
        self._flip_to(BOARDS_E[1], 1.2)
        self._flip_to(BOARDS_E[2], 1.2)

    # f : ADIEU in the first word, O mid second word, Y ending the third
    @subscene
    def adieu(self):
        self._flip_to(BOARD_F, 1.2)

    # g : AUDIO in the first word, E mid second word (Y stays)
    @subscene
    def audio(self):
        self._flip_to(BOARD_G, 1.2)

    # h : CRYPT in the third word
    @subscene
    def crypt(self):
        self._flip_to(BOARD_H, 1.2)

    # i : the boxes fade out; the table comes in — headers, then a row per length
    def _setup_table(self):
        cell = lambda t, size, **kw: crisp_text(t, font_size=size, color=WHITE, **kw)
        heads = [cell(h, HEADER_SIZE, weight=BOLD) for h in HEADERS]
        heads[0].move_to([LEN_X, HEADER_Y, 0])
        heads[1].move_to([AVG_X, HEADER_Y, 0])
        heads[2].move_to([0, HEADER_Y, 0]).align_to(np.array([OPENER_X, 0, 0]), LEFT)
        self.table_head = VGroup(*heads)
        self.table_rows = VGroup(*[cell(str(L), CELL_SIZE).move_to([LEN_X, _row_y(L), 0])
                                   for L in LENGTHS])

    @subscene
    def table(self):
        self._setup_table()
        self.play(FadeOut(*self.mobjects), run_time=0.8)
        self.upper = self.board_wheel = self.shown = self.board = None
        self.play(FadeIn(self.table_head), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.3) for r in self.table_rows],
                              lag_ratio=0.12), run_time=1.2)

    # ── j-v: filling in the table, one cell at a time ──────────────────────
    def _fill_avg(self, L, run_time):
        """Length L's average guesses fades into its cell."""
        t = TABLE[L]
        cell = crisp_text(_avg(t["total"], t["answers"]), font_size=CELL_SIZE,
                          color=WHITE).move_to([AVG_X, _row_y(L), 0])
        self.play(FadeIn(cell), run_time=run_time)

    def _fill_opener(self, L, run_time):
        """Length L's best opener typed into its row as tiles (they appear as their
        letters land), with the keystroke sounds."""
        row = get_board(rows=1, cols=L).scale(TABLE_TILE_SCALE)
        row.move_to([0, _row_y(L), 0]).align_to(np.array([OPENER_X, 0, 0]), LEFT)
        row.type_word(self, 0, TABLE[L]["opener"], run_time,
                      per_letter=key_cues(self), appear=True,
                      letter_color=tile_color)

    def _fill_both(self, L, avg_run_time, opener_run_time):
        """A whole row, as every row filled in one beat is: average, then opener."""
        self._fill_avg(L, avg_run_time)
        self._fill_opener(L, opener_run_time)

    def _corner_path(self, L):
        """Length L's all-grey path as a scored board in the top-right corner, or
        None while it is still a stub in the data (see word_lengths_data)."""
        gp = GREY_PATHS[L]
        if gp is None:
            return None
        rows = [get_scored_row(g["word"], g["code"]) for g in gp["guesses"]]
        board = VGroup(*rows).arrange(DOWN, buff=GAP)
        board.scale(min(CORNER_W / board.width, CORNER_H / board.height, 1.0))
        board.align_to(np.array([CORNER_UR[0], CORNER_UR[1], 0]), UR)
        return board

    # j : SALET's row, the same way as every other whole row
    @subscene
    def salet_row(self):
        self._fill_both(5, 0.5, 0.65)

    # k : length 6's average
    @subscene
    def avg_6(self):
        self._fill_avg(6, 0.5)

    # l : length 6's opener
    @subscene
    def opener_6(self):
        self._fill_opener(6, 0.78)

    # m : length 7's average
    @subscene
    def avg_7(self):
        self._fill_avg(7, 0.5)

    # n : length 7's opener
    @subscene
    def opener_7(self):
        self._fill_opener(7, 0.91)

    # o : both for 8
    @subscene
    def both_8(self):
        self._fill_both(8, 0.5, 1.04)

    # p : both for 9
    @subscene
    def both_9(self):
        self._fill_both(9, 0.5, 1.17)

    # q : both for 10
    @subscene
    def both_10(self):
        self._fill_both(10, 0.5, 1.3)

    # r : both for 11
    @subscene
    def both_11(self):
        self._fill_both(11, 0.5, 1.43)

    # s : length 4's average
    @subscene
    def avg_4(self):
        self._fill_avg(4, 0.5)

    # t : length 4's opener, then its tree's all-grey path in the top-right corner
    @subscene
    def opener_4(self):
        self._fill_opener(4, 0.52)
        self.path4 = self._corner_path(4)
        if self.path4 is not None:          # a stub until the TALE tree exists
            self.play(FadeIn(self.path4), run_time=0.8)

    # u : length 3's average
    @subscene
    def avg_3(self):
        self._fill_avg(3, 0.5)

    # v : length 3's opener, then its tree's all-grey path replacing 4's in the corner
    @subscene
    def opener_3(self):
        self._fill_opener(3, 0.39)
        path3 = self._corner_path(3)
        out = [] if self.path4 is None else [FadeOut(self.path4)]
        self.play(*out, FadeIn(path3), run_time=0.8)
        self.path4 = None
