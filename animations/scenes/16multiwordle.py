"""Scene 16 — multi-Wordle: one board splits into Octordle's eight, the browser
windows of the 2^n variants, then a played Octordle game. Navy background.

Follows talking head THJ, so the single board is up from frame 0 (THJ covers the
cut in). After it comes VO section 4 (no subscene) and then THK, so it ends on the
finished game, with the FOURTH footnote faded out.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a one_board     — the ordinary 6-row board                               (16a, VO 1)
  b split_two     — splits into 2 side by side, 7 rows each               (16b, VO 1)
  c split_four    — splits into 4 in a row, 9 rows each                   (16c, VO 1)
  d split_eight   — splits into 8 in a row, 13 rows each                  (16d, VO 1)
  e browser_in    — boards shift up off frame, Octordle's window up in    (16e, VO 1)
  f variants      — Octordle to the top-right cell, the other five in     (16f, VO 2)
  g back_down     — windows shift down off frame, the 8 boards back       (16g, VO 3)
  h playthrough   — SOLVE EIGHT WORDS, then FIRST .. OCTET; FORTH's *     (16h, VO 3)

THE GAME HAS NO PAUSES OF ITS OWN (user's call): a solved board jumps during the
next guess's typing, and the FOURTH footnote fades in with FIFTH's typing and out
with SEVEN's, staying up while the game goes on.

ALL BOARDS IN ONE ROW (user's call, 2026-10-01 -- the script's "grid" and "2x4"
were overridden): each board splits into two neighbours, pushing the row apart.

THE NEW ROWS ARE ATTACHED (user's call): each child moves as one board, starting as
an exact overlay of its parent with its extra rows already in place below the last
row but invisible, and those rows fade in as the board travels (`_split`). The
13-row layout of d is exactly the board the game of h is played on, so nothing
changes at that seam.

THE ROW COUNTS ARE THE REAL GAMES': 7 (Dordle), 9 (Quordle), 13 (Octordle).

REUSE MAP — every element and the one source it comes from:
  boards, tiles, letters    assets/board.py `get_board`, as scene 02
  typing / scoring / win    board.type_anim / reveal_anim / bounce_anim, every
                            unsolved board in ONE play (one guess, all boards)
  keystroke sfx             assets/keys.py `key_cues` (scene 02), first board only
  browser windows           bpkfigures/browser.py `browser_window` (new, modelled
                            on youtube_card.py)
  page screenshots          assets/web_media/*.png, made by assets/web_shots.py
  window in / out           whole-frame shift, as scene 09's video_page -> poll_page
                            (09tier_list.py:179)
  the five variants in      LaggedStart of FadeIn, as 04new_rules.py:156 and
                            10word_lengths.py:425 (there with a small rise; here
                            plain, they are windows not rows)
  FORTH footnote            raised-asterisk footnote of hangman
                            18choosing_strategy.py:412, in WHITE on navy (the
                            video's text colour, e.g. 14random_compatible.py:192)
  feedback codes            assets/game_data.py load("octordle") -> game_cache.json,
                            computed by math/wordle.py `pattern`
  colours                   BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*

ON-SCREEN TEXT, each licensed by column 2: the windows' tab titles and addresses
("browser window", 16e/f), and the asterisk + "*Yes, I know how to spell FOURTH"
(16h, quoted). Nothing else.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board, ROWS, TILE, GAP, STROKE
from assets import game_data
from assets.keys import key_cues
from bpkfigures.browser import browser_window

MEDIA = Path(__file__).resolve().parent.parent / "assets" / "web_media"
GAME = game_data.load("octordle")
GUESSES = GAME["guesses"]
BOARDS = GAME["boards"]                     # in answer order: FIRST .. OCTET

FH = config.frame_height                    # one whole frame, for the shifts

# ── board layouts ─────────────────────────────────────────────────────────────
# (rows per board, board scale, [centres]) — centres in the order children are
# made: board i splits into children 2i and 2i+1.
BOARD_W = 5 * TILE + 4 * GAP                 # 4.9 unscaled


def _board_h(rows):
    return rows * TILE + (rows - 1) * GAP


L1 = (ROWS, 1.0, [ORIGIN])
ROW_GAP = 0.8                 # space between neighbouring boards, in unscaled units
ROW_MAX_W, ROW_MAX_H = 15.2, 8.2


def _row_layout(n, rows):
    """n boards of `rows` rows side by side in ONE row, centred, as big as fits (never
    bigger than the ordinary board). Board i splits into children 2i and 2i+1, which
    sit next to each other -- so every split pushes boards apart sideways."""
    span = n * BOARD_W + (n - 1) * ROW_GAP
    s = min(1.0, ROW_MAX_W / span, ROW_MAX_H / _board_h(rows))
    xs = [(-span / 2 + BOARD_W / 2 + k * (BOARD_W + ROW_GAP)) * s for k in range(n)]
    return (rows, s, [np.array([x, 0, 0]) for x in xs])


L2 = _row_layout(2, 7)
L4 = _row_layout(4, 9)
L8 = _row_layout(8, 13)

# ── browser windows ───────────────────────────────────────────────────────────
# The screenshots are 1920x1490 (web_shots.py --size 1920x1490), not 16:9: taller
# windows fill the 3x2 grid's cells, which a 16:9 window cannot. A window is then
# WIN_TALL times its width (page 1490/1920 plus browser.py's tab strip + toolbar).
WIN_TALL = 1490 / 1920 + 0.046
WIN_W = 10.4                                  # the full-frame Octordle window
CELL_W = 5.0                                  # one window of the 3x2 variants grid
CELL_GX, CELL_GY = 0.25, 0.3
# (screenshot, tab title, address). Power-of-two order, read left to right, top
# row first -- which puts Octordle in the TOP-RIGHT cell the script names.
VARIANTS = [
    ("dordle", "Dordle", "zaratustra.itch.io/dordle"),
    ("quordle", "Quordle", "merriam-webster.com/games/quordle"),
    ("octordle", "Octordle", "britannica.com/games/octordle"),
    ("sedecordle", "Sedecordle", "sedecordle.com"),
    ("duotrigordle", "Duotrigordle", "duotrigordle.com"),
    ("sexaginta", "Sexaginta-quattuordle", "sexaginta-quattuordle.pages.dev"),
]
OCT = 2                                        # Octordle's index in VARIANTS

FOOT_W = 4.2                                   # footnote width
FORTH_BOARD = 3                                # board whose answer is FORTH


def _cell_center(i):
    win_h = CELL_W * WIN_TALL
    col, row = i % 3, i // 3
    return np.array([(col - 1) * (CELL_W + CELL_GX),
                     (0.5 - row) * (win_h + CELL_GY), 0])


def _window(i, width):
    name, title, url = VARIANTS[i]
    return browser_window(url, title, image=str(MEDIA / f"{name}.png"), width=width)


class Scene16(WordleBoardScene):
    """BEAT MAP
    one_board — the ordinary board
    split_two — 2 boards, 7 rows
    split_four — 4 boards, 9 rows
    split_eight — 8 boards, 13 rows
    browser_in — Octordle's browser window slides up in
    variants — the 2^n variants in a grid
    back_down — back to the 8 boards
    playthrough — the game
    """

    def setup_scene(self):
        self.boards = [self._board(L1, 0)]
        self.add(*self.boards)
        self.windows = None
        self.foot = None

    @staticmethod
    def _board(layout, i):
        rows, s, centres = layout
        return get_board(rows=rows).scale(s).move_to(centres[i])

    def _split(self, layout, run_time):
        """Every board splits in two, both children growing to `layout`'s rows.

        Each child moves as ONE board: it starts as an exact overlay of its parent,
        its extra rows already ATTACHED below the parent's last row but invisible,
        and travels to its own pose while those rows fade in -- so the new rows ride
        with the board rather than appearing where it ends up. The parent is swapped
        for the two overlays before the play (identical pose, so no pop).
        """
        anims, starts, new = [], [], []
        for i, b in enumerate(self.boards):
            for kid in (self._board(layout, 2 * i), self._board(layout, 2 * i + 1)):
                start = kid.copy()
                start.scale(b.tiles[0][0].width / kid.tiles[0][0].width)
                start.shift(b.tiles[0][0].get_center() - start.tiles[0][0].get_center())
                for r in range(b.n_rows, kid.n_rows):
                    start.rows[r].set_opacity(0)
                anims.append(Transform(start, kid))
                starts.append(start)
                new.append(kid)
        self.remove(*self.boards)
        self.add(*starts)
        self.play(*anims, run_time=run_time)
        self.remove(*starts)
        self.add(*new)
        self.boards = new

    # a : the ordinary board, on from frame 0 (THJ covers the cut in)
    @subscene
    def one_board(self):
        pass

    # b : two boards side by side, each a row longer (Dordle's 7)
    @subscene
    def split_two(self):
        self._split(L2, 1.4)

    # c : four boards in a 2x2 grid, two rows longer (Quordle's 9)
    @subscene
    def split_four(self):
        self._split(L4, 1.4)

    # d : eight boards in a 2x4 grid, four rows longer (Octordle's 13)
    @subscene
    def split_eight(self):
        self._split(L8, 1.4)

    def _setup_browser(self):
        win = _window(OCT, WIN_W)
        win.move_to(ORIGIN).shift(DOWN * FH)   # one frame below, slides up into place
        self.windows = [win]

    # e : the boards go up off frame and Octordle's window comes up into it
    @subscene
    def browser_in(self):
        self._setup_browser()
        self.add(self.windows[0])
        self.play(*[b.animate.shift(UP * FH) for b in self.boards],
                  self.windows[0].animate.shift(UP * FH), run_time=1.2)

    def _setup_variants(self):
        # the Octordle window shrinks into its cell; at the end it is swapped for a
        # window BUILT at that size, whose screenshot is resampled for it (a big
        # window scaled down shows manim's un-averaged pixels — browser.py)
        self.oct_small = _window(OCT, CELL_W).move_to(_cell_center(OCT))
        self.others = [_window(i, CELL_W).move_to(_cell_center(i))
                       for i in range(len(VARIANTS)) if i != OCT]

    # f : Octordle to the top-right cell, then the other five fade in
    @subscene
    def variants(self):
        self._setup_variants()
        big = self.windows[0]
        self.play(big.animate.scale(CELL_W / WIN_W).move_to(_cell_center(OCT)),
                  run_time=1.0)
        self.remove(big)
        self.add(self.oct_small)
        self.play(LaggedStart(*[FadeIn(w) for w in self.others], lag_ratio=0.3),
                  run_time=1.6)
        self.windows = self.others[:OCT] + [self.oct_small] + self.others[OCT:]
        self.oct_small = self.others = None

    # g : the windows go down off frame and the eight boards come back down
    @subscene
    def back_down(self):
        self.play(*[w.animate.shift(DOWN * FH) for w in self.windows],
                  *[b.animate.shift(DOWN * FH) for b in self.boards], run_time=1.2)
        self.remove(*self.windows)
        self.windows = None

    # ── the game ──────────────────────────────────────────────────────────────
    def _guess(self, j, type_rt, score_rt, extra=()):
        """Guess j typed into every unsolved board, then scored. A board is unsolved
        at guess j while it has a row j.

        NO PAUSE OF ITS OWN BETWEEN GUESSES: a board this guess solves jumps DURING
        the next guess's typing (held in `self.wins` until then), and `extra`
        animations (the footnote in and out) join the typing play too. Only the
        last guess's jump plays on its own (`_last_win`)."""
        live = [k for k, b in enumerate(BOARDS) if len(b["guesses"]) > j]
        word = GUESSES[j]
        types = []
        for n, k in enumerate(live):
            anim, total = self.boards[k].type_anim(
                self, j, word, type_rt, per_letter=key_cues(self) if n == 0 else None)
            types.append(anim)
        self.play(*types, *self.wins, *extra, run_time=total)
        self.play(*[self.boards[k].reveal_anim(j, BOARDS[k]["guesses"][j]["code"])
                    for k in live], run_time=score_rt)
        self.wins = [self.boards[k].bounce_anim(j) for k in live
                     if BOARDS[k]["answer"] == word]

    def _last_win(self, run_time):
        self.play(*self.wins, run_time=run_time)
        self.wins = []

    def _setup_footnote(self):
        b = self.boards[FORTH_BOARD]
        row = b.rows[GUESSES.index("forth")]
        self.star = crisp_text("*", font_size=36, color=WHITE)
        self.star.scale_to_fit_height(row.height * 0.45)
        self.star.next_to(row, RIGHT, buff=0.06).align_to(row, UP)
        body = crisp_text("Yes, I know how to spell FOURTH", font_size=24, color=WHITE)
        star = crisp_text("*", font_size=24, color=WHITE).next_to(body, LEFT, buff=0.04)
        star.set_y(body.get_top()[1])          # raised, as hangman 18's footnote
        foot = VGroup(star, body).scale_to_fit_width(FOOT_W)
        bottom = min(bb.get_bottom()[1] for bb in self.boards)
        foot.move_to([0, (bottom - config.frame_y_radius) / 2, 0])
        self.foot = foot

    # h : SOLVE EIGHT WORDS, then the eight answers in order
    @subscene
    def playthrough(self):
        self.wins = []
        self._guess(0, 0.65, 0.9)              # SOLVE
        self._guess(1, 0.65, 0.9)              # EIGHT
        self._guess(2, 0.65, 0.9)              # WORDS
        self._guess(3, 0.65, 0.9)              # FIRST
        self._guess(4, 0.65, 0.9)              # HALVE
        self._guess(5, 0.65, 0.9)              # THIRD
        self._guess(6, 0.65, 0.9)              # FORTH
        self._setup_footnote()
        # the footnote comes up WITH the next guess's typing -- no pause of its own --
        # and stays up while the game goes on
        self._guess(7, 0.65, 0.9, extra=[FadeIn(self.star), FadeIn(self.foot)])  # FIFTH
        self._guess(8, 0.65, 0.9)              # SIXTH
        self._guess(9, 0.65, 0.9, extra=[FadeOut(self.star), FadeOut(self.foot)])  # SEVEN
        self._guess(10, 0.65, 0.9)             # OCTET
        self._last_win(0.8)
        self.star = self.foot = None
