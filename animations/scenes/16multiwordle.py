"""Scene 16 — multi-Wordle: one board splits into Octordle's eight, the browser
windows of the 2^n variants, then a played Octordle game. Navy background.

Follows talking head THJ, so the single board is up from frame 0 (THJ covers the
cut in). After it comes VO section 4 (no subscene) and then THK, so it ends on the
finished game, with the FOURTH footnote faded out.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a one_board     — the ordinary 6-row board                               (16a, VO 1)
  b split_two     — splits into 2 side by side, 7 rows each               (16b, VO 1)
  c split_four    — splits into 4 in a 2x2 grid, 9 rows each              (16c, VO 1)
  d split_eight   — splits into 8 in a 2x4 grid, 13 rows each             (16d, VO 1)
  e browser_in    — boards shift up off frame, Octordle's window up in    (16e, VO 1)
  f variants      — Octordle to the top-right cell, the other five in     (16f, VO 2)
  g back_down     — windows shift down off frame, the 8 boards back       (16g, VO 3)
  h playthrough   — SOLVE EIGHT WORDS, then FIRST .. OCTET; FORTH's *     (16h, VO 3)

THE SPLITS ARE PIECE BY PIECE. Every old tile is transformed to its counterpart in
ONE of the two children; a copy of it goes to the other child; only the rows a
child has that its parent did not (the "adding a row" of the script) fade in, from
BEHIND the moving tiles, the trick `board.add_row` uses. The 13-row layout of d is
exactly the board the game of h is played on, so nothing changes at the seam.

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
_S2 = 1.0
_X2 = (BOARD_W * _S2 + 1.0) / 2
L2 = (7, _S2, [LEFT * _X2, RIGHT * _X2])
_S4, _G4 = 0.44, 0.3
_DX4 = (BOARD_W * _S4 + _G4) / 2
_DY4 = (_board_h(9) * _S4 + _G4) / 2
# left board -> top-left, bottom-left; right board -> top-right, bottom-right
L4 = (9, _S4, [np.array([-_DX4, _DY4, 0]), np.array([-_DX4, -_DY4, 0]),
               np.array([_DX4, _DY4, 0]), np.array([_DX4, -_DY4, 0])])
_S8, _G8 = 0.30, 0.25
_Y8 = 0.15                                    # block raised, room for the footnote
_PX8 = BOARD_W * _S8 + _G8
_DY8 = (_board_h(13) * _S8 + _G8) / 2
_XS8 = [(-1.5 + k) * _PX8 for k in range(4)]
# each 2x2 board splits sideways: TL -> cols 0,1 top; BL -> 0,1 bottom; TR -> 2,3
# top; BR -> 2,3 bottom. GRID8[i] is the centre of child i.
_TOP8, _BOT8 = _Y8 + _DY8, _Y8 - _DY8
L8 = (13, _S8, [np.array([_XS8[0], _TOP8, 0]), np.array([_XS8[1], _TOP8, 0]),
                np.array([_XS8[0], _BOT8, 0]), np.array([_XS8[1], _BOT8, 0]),
                np.array([_XS8[2], _TOP8, 0]), np.array([_XS8[3], _TOP8, 0]),
                np.array([_XS8[2], _BOT8, 0]), np.array([_XS8[3], _BOT8, 0])])
# which split child sits in which game slot: game board k (answer k, read like
# Octordle: top row left to right, then bottom row) -> child index
SLOT8 = [0, 1, 4, 5, 2, 3, 6, 7]

# ── browser windows ───────────────────────────────────────────────────────────
WIN_W = 13.6                                  # the full-frame Octordle window
CELL_W = 4.6                                  # one window of the 3x2 variants grid
CELL_GX, CELL_GY = 0.4, 0.5
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
    win_h = CELL_W * (9 / 16 + 0.046)          # viewport + chrome (browser.py fracs)
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
        """Every board splits in two, both children growing to `layout`'s rows."""
        anims, new, gone = [], [], []
        for i, b in enumerate(self.boards):
            twin = b.copy()
            kids = [self._board(layout, 2 * i), self._board(layout, 2 * i + 1)]
            for src, kid in zip((b, twin), kids):
                for r in range(b.n_rows):
                    for c in range(b.n_cols):
                        anims.append(Transform(src.tiles[r][c], kid.tiles[r][c]))
                for r in range(b.n_rows, kid.n_rows):
                    kid.rows[r].set_z_index(-1)
                    anims.append(FadeIn(kid.rows[r]))
            gone += [b, twin]
            new += kids
        self.add(*[b for b in gone if b not in self.boards])
        self.play(*anims, run_time=run_time)
        self.remove(*gone)
        for kid in new:
            for row in kid.rows:
                row.set_z_index(0)
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
        # game order: answer k's board is child SLOT8[k]
        self.boards = [self.boards[j] for j in SLOT8]

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
    def _guess(self, j, type_rt, score_rt, win_rt=0.8):
        """Guess j typed into every unsolved board, scored, and any board it solves
        jumps. A board is unsolved at guess j while it has a row j."""
        live = [k for k, b in enumerate(BOARDS) if len(b["guesses"]) > j]
        word = GUESSES[j]
        types = []
        for n, k in enumerate(live):
            anim, total = self.boards[k].type_anim(
                self, j, word, type_rt, per_letter=key_cues(self) if n == 0 else None)
            types.append(anim)
        self.play(*types, run_time=total)
        self.play(*[self.boards[k].reveal_anim(j, BOARDS[k]["guesses"][j]["code"])
                    for k in live], run_time=score_rt)
        won = [k for k in live if BOARDS[k]["answer"] == word]
        if won:
            self.play(*[self.boards[k].bounce_anim(j) for k in won], run_time=win_rt)

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
        self._guess(0, 0.65, 1.2)              # SOLVE
        self._guess(1, 0.65, 1.2)              # EIGHT
        self._guess(2, 0.65, 1.2)              # WORDS
        self._guess(3, 0.65, 1.2)              # FIRST
        self._guess(4, 0.65, 1.2)              # HALVE
        self._guess(5, 0.65, 1.2)              # THIRD
        self._guess(6, 0.65, 1.2)              # FORTH
        self._setup_footnote()
        self.play(FadeIn(self.star), FadeIn(self.foot), run_time=0.6)
        self.wait(1.5)
        self._guess(7, 0.65, 1.2)              # FIFTH
        self._guess(8, 0.65, 1.2)              # SIXTH
        self._guess(9, 0.65, 1.2)              # SEVEN
        self._guess(10, 0.65, 1.2)             # OCTET
        self.play(FadeOut(self.star), FadeOut(self.foot), run_time=0.6)
        self.star = self.foot = None
