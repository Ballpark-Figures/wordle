"""Scene 16 — multi-Wordle: one board splits into Octordle's eight, the browser
windows of the 2^n variants, then a played Octordle game. Navy background.

Follows talking head THJ, so the single board is up from frame 0 (THJ covers the
cut in). After it comes VO section 6 (no subscene) and then THK, so it ends on the
finished second game, its candidates under every board.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a one_board     — the ordinary 6-row board                               (16a, VO 1)
  b split_two     — splits into 2 side by side, 7 rows each               (16b, VO 1)
  c split_four    — splits into 4 in a row, 9 rows each                   (16c, VO 1)
  d split_eight   — splits into 8 in a row, 13 rows each                  (16d, VO 1)
  e browser_in    — boards shift up off frame, Octordle's window up in    (16e, VO 1)
  f variants      — Octordle to the top-right cell, the other five in     (16f, VO 2)
  g back_down     — windows shift down off frame, the 8 boards back       (16g, VO 3)
  h playthrough   — SOLVE EIGHT WORDS, then FIRST .. OCTET; FORTH's *     (16h, VO 3)
  i replay_trial  — the game flips back to black, boards up, then TRIAL;
                    each board's candidates appear beneath it             (16i, VO 4)
  j replay_guess  — GUESS, candidates updated                             (16j, VO 4)
  k replay_combo  — COMBO                                                 (16k, VO 4)
  l replay_third  — THIRD, the first answer, out of order                 (16l, VO 4)
  m replay_rest   — SIXTH SEVEN FIFTH OCTET FIRST HALVE FORTH, faster,
                    then the win wave                                     (16m, VO 4)
  n blank_all     — every row back to black, candidates out               (16n, VO 5)
  o solve_again   — SOLVE typed and scored (NOT IN THE SCRIPT YET)        (--,  VO 5)
  p flip_eight    — row 2 back to coloured EIGHT in one flip              (16o, VO 5)
  q flip_words    — row 3 back to WORDS in one flip                       (16p, VO 5)
  r after_solve   — rows 2-3 back to black, SOLVE's candidates back       (16q, VO 5)
  s greedy        — fewest-candidates board emphasised, a random one of
                    its candidates guessed, candidates updated, to the end (16r, VO 5)

  t chart_in      — the game shifts up off frame, the empty chart up into
                    it: "Average Misses in Multi-Wordle"                  (16s, VO 6)
  u plot_three    — the 3-word opener's line                              (16t, VO 6)
  v plot_one_two  — the 2-word and 1-word openers' lines                  (16u, VO 6)
  w plot_improved — the improved strategy                                 (16v, VO 6)

THE CHART'S DATA IS THE USER'S PLAN (2026-10-01): the best single / pair / triple
opener at each power of two, raced, then each winner run at every k up to the next
power -- see assets/multi_plot_data.py, which also leaves out any k not yet run (the
line is drawn straight across) and uses a race's own estimate at its power of two
until the fill-in exists. Re-run it as results land. Average misses
= mean total guesses - k. Styled after yahtzee's 08line_graph (bpkfigures
line_graph, lines drawn with Create + an end label), but drawn straight onto the
navy in WHITE ink, as 08histogram and 13 do -- no cream card (13's call: it looked
foreign in this all-dark video).

FROM o ON, THE SUBSCENE LETTERS ARE ONE AHEAD OF THE SCRIPT'S (o is the user's new
SOLVE beat, 2026-10-01, not yet in the Doc).

16i-m IS A DIFFERENT GAME FROM 16h (user's call, 2026-10-01; the script still says
SOLVE EIGHT WORDS in order): TRIAL GUESS COMBO, then the answers in a "weird order"
-- the most scrambled of the 2648 orders that keep every board down to one candidate
at its turn (plain number order does not). game_data "octordle_weird". Because the
rest of section 5 is written about SOLVE EIGHT WORDS, n blanks the whole game and o
plays SOLVE afresh.

A SOLVED BOARD SHOWS NOTHING BENEATH IT (user's call): its last word fades on the
update after the guess that solves it.

CANDIDATES UNDER A BOARD (16i-r): the answers still consistent with every reply that
board has had, as WHITE DOTS while there are too many to list and as WORDS below
that: ONE COLUMN of words, each as wide as fits under its board, and the cutoff is
however many of those fit (user's call -- the script's "20 or fewer" was for a
two-column list). ONE dot size for the whole scene (fitted to the largest set,
342), so a count reads as an area. Updating after a guess: the eliminated fade out, the rest
regrid, and a set crossing 20 turns into words that grow out of their dots (07's
move). Numbers from assets/multi_data.py -> multi_cache.json.

16r's GAME IS math/multiwordle.py's `greedy` RULE, PLAYED BY ITS OWN CODE: the board
with the fewest candidates (ties: lowest board index), a candidate of it drawn at
random. One draw, seed 0 (multi_data.GREEDY_SEED). The emphasis is a translucent
navy MASK over every other board's column -- lowering opacity instead would expose
the hidden glyphs inside each PigpenWord.

THE GAME HAS NO PAUSES OF ITS OWN (user's call): a solved board does not jump; one
wave runs through all eight winning rows at the end instead. The FOURTH footnote fades in with FIFTH's typing and out
with SIXTH's, staying up while the game goes on.

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
  typing / scoring          board.type_anim / reveal_anim, every unsolved board
                            in ONE play (one guess, all boards)
  the closing wave          board.bounce_tiles (bounce's per-tile jumps, added
                            for this), all 40 winning tiles in ONE LaggedStart
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
  flip back to black        board.TileFlip(..., swap_to=None) -- the blank face
  flip back to a word       board.TileFlip(..., swap_to=letter), lag 0 ("one flip")
  candidate dots            WHITE `Dot`s as scenes 06/07 (DOT_COLOR), in
                            assets/groups.py `dot_grid` (added for this)
  candidate words           assets/pigpen.py `PigpenWord(revealed=True)`, placed
                            by groups.py `ranked_word_layout` (a word grid that
                            fills a region), as 07
  dots -> words             07's `_setup_focus`: each word starts at its dot's
                            size and spot, invisible, and grows to its slot
  emphasis                  dim the rest (house rule), as masks (see above)
  second game               assets/multi_data.py load("greedy")

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
from assets.board import TileFlip
from assets import multi_data
from assets.groups import dot_grid, ranked_word_layout
from assets.pigpen import PigpenWord
from bpkfigures.browser import browser_window
from bpkfigures.line_graph import get_line_graph, line_point, spread_label_ys
from assets import multi_plot_data

MEDIA = Path(__file__).resolve().parent.parent / "assets" / "web_media"
GAME = game_data.load("octordle")
GUESSES = GAME["guesses"]
BOARDS = GAME["boards"]                     # in answer order: FIRST .. OCTET
WEIRD = game_data.load("octordle_weird")["boards"]   # 16i-m's game, same answers

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

# ── candidates under the boards (16i-r) ───────────────────────────────────────
REPLAY = multi_data.load("replay")
GREEDY = multi_data.load("greedy")
RAISE = 0.9                  # boards move up this far in 16i, to make room below
CAND_TOP_GAP = 0.15          # board bottom to the candidates' top
CAND_BOTTOM = -4.3
# WORDS ARE ONE COLUMN, AS WIDE AS FITS UNDER A BOARD, and the dots-to-words cutoff
# is however many of those fit below it (user's call, 2026-10-01 -- replacing the
# script's "20 or fewer"); `_sizes` derives it.
DOT_COLOR = WHITE            # 06's dots
# ── the chart (16s-v) ─────────────────────────────────────────────────────────
PLOT = multi_plot_data.load()
PLOT_C = [-1.2, -0.35, 0]     # the plot BOX's centre; room on the right for labels
PLOT_W, PLOT_H = 10.4, 5.4
Y_MAX = 4.0
X_TICKS = list(range(4, 33, 4))   # linear, every 4 (user's call)
LINE_SW = 4.0
LABEL_GAP = 0.06              # least space between two right-edge line labels
LINE_LABEL = {1: "1-word opener", 2: "2-word opener", 3: "3-word opener"}
IMPROVED_LABEL = "Improved Strategy"
LINE_COLOR = {1: LIGHT_BLUE, 2: LIGHT_GREEN, 3: LIGHT_RED}
IMPROVED_COLOR = LIGHT_YELLOW

ALL_GREEN = 242              # wordle.pattern's code for a win
DIM = 0.75                   # the emphasis mask's opacity over a dimmed column
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
        self.cands = None            # per board: {word: Dot or PigpenWord}
        self.masks = None

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
        at guess j while it has a row j. NO jump when a board is solved (user's
        call): the whole game's winning rows jump together at the end (`_wave`).
        `extra` animations (the footnote in and out) join the typing play."""
        live = [k for k, b in enumerate(BOARDS) if len(b["guesses"]) > j]
        word = GUESSES[j]
        types = []
        for n, k in enumerate(live):
            anim, total = self.boards[k].type_anim(
                self, j, word, type_rt, per_letter=key_cues(self) if n == 0 else None)
            types.append(anim)
        self.play(*types, *extra, run_time=total)
        self.play(*[self.boards[k].reveal_anim(j, BOARDS[k]["guesses"][j]["code"])
                    for k in live], run_time=score_rt)

    def _wave(self, run_time, boards=BOARDS, height=0.15):
        """One wave through every board's winning row, left to right: all 40 tiles
        in ONE LaggedStart, so it runs on across the gaps between boards. `boards`
        is the game's game_data boards, which say each board's winning row."""
        ups = []
        for k, b in enumerate(self.boards):
            ups += b.bounce_tiles(len(boards[k]["guesses"]) - 1, height)
        self.play(LaggedStart(*ups, lag_ratio=0.08), run_time=run_time)

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
        self._guess(8, 0.65, 0.9, extra=[FadeOut(self.star), FadeOut(self.foot)])  # SIXTH
        self._guess(9, 0.65, 0.9)              # SEVEN
        self._guess(10, 0.65, 0.9)             # OCTET
        self._wave(2.0)
        self.star = self.foot = None

    # ── candidates under the boards (16i-r) ───────────────────────────────────
    def _region(self, k):
        b = self.boards[k]
        return (b.get_left()[0], b.get_right()[0], b.get_bottom()[1] - CAND_TOP_GAP)

    def _word_slots(self, members, k):
        left, right, top = self._region(k)
        return ranked_word_layout([{"size": len(members), "members": members}],
                                  left, right, top, CAND_BOTTOM, heads=0, ncols=[1])

    def _sizes(self):
        """The ONE dot pitch (fitted to the largest set either game shows) and the
        dots-to-words cutoff: the most words that fit in one column at the size a
        lone word gets (as wide as fits under the board)."""
        if getattr(self, "_pitch", None) is not None:
            return self._pitch, self._word_max
        left, right, top = self._region(0)
        w, h = right - left, top - CAND_BOTTOM
        biggest = max(len(b["members"]) for g in (REPLAY, GREEDY)
                      for st in g["steps"] for b in st["boards"])
        lo, hi = 0.001, 1.0                       # largest pitch that fits `biggest`
        for _ in range(50):
            p = (lo + hi) / 2
            lo, hi = (p, hi) if int(w / p) * int(h / p) >= biggest else (lo, p)
        full = self._word_slots(["w0"], 0)[1]
        n = 1
        while self._word_slots([f"w{i}" for i in range(n + 1)], 0)[1] >= full * 0.999:
            n += 1
        self._pitch, self._word_max = lo, n
        return lo, n

    def _cand_anims(self, members_by_board):
        """ONE play's worth of animations taking every board's candidates to the
        sets given, plus what to do when it ends. Dots while a set is over WORD_MAX,
        words from there down; eliminated ones fade, survivors regrid, a set
        crossing to words grows its words out of their dots (07)."""
        pitch, word_max = self._sizes()
        anims, gone, new = [], [], []
        for k, members in enumerate(members_by_board):
            cur = self.cands[k]
            left, right, top = self._region(k)
            nxt = {}
            if not members:
                pass                           # solved: everything below it leaves
            elif len(members) > word_max:
                spots, r = dot_grid(members, pitch, left, right, top)
                for wd in members:
                    if wd in cur:
                        anims.append(cur[wd].animate.move_to(spots[wd]))
                        nxt[wd] = cur[wd]
                    else:
                        d = Dot(point=spots[wd], radius=r, color=DOT_COLOR)
                        anims.append(FadeIn(d))
                        new.append(d)
                        nxt[wd] = d
            else:
                slots, sc, _, _ = self._word_slots(members, k)
                for wd in members:
                    old = cur.get(wd)
                    if isinstance(old, PigpenWord):
                        anims.append(old.animate.move_to(slots[wd]))
                        nxt[wd] = old
                        continue
                    m = PigpenWord(wd, revealed=True).scale(sc).move_to(slots[wd])
                    if old is None:
                        anims.append(FadeIn(m))
                    else:                        # grows out of its dot (07)
                        m.generate_target()
                        m.scale(old.width / m.width).move_to(old).set_opacity(0)
                        anims += [MoveToTarget(m),
                                  old.animate.move_to(slots[wd]).set_opacity(0)]
                        gone.append(old)
                    new.append(m)
                    nxt[wd] = m
            for wd, m in cur.items():
                if wd not in nxt:
                    anims.append(FadeOut(m))
                    gone.append(m)
            self.cands[k] = nxt
        return anims, new, gone

    def _update_cands(self, members_by_board, run_time, extra=()):
        anims, new, gone = self._cand_anims(members_by_board)
        self.add(*new)
        self.play(*anims, *extra, run_time=run_time)
        self.remove(*gone)

    def _play(self, game, j, type_rt, score_rt, update_rt, extra=()):
        """Guess j of `game` (multi_data's): typed into every board it reaches,
        scored, then every board's candidates updated."""
        step = game["steps"][j]
        live = [k for k, b in enumerate(step["boards"]) if b["code"] is not None]
        types = []
        for n, k in enumerate(live):
            anim, total = self.boards[k].type_anim(
                self, j, step["word"], type_rt,
                per_letter=key_cues(self) if n == 0 else None)
            types.append(anim)
        self.play(*types, run_time=total)
        self.play(*[self.boards[k].reveal_anim(j, step["boards"][k]["code"])
                    for k in live], run_time=score_rt)
        # a SOLVED board shows nothing beneath it (user's call): its word goes on
        # the update of the guess that solves it
        self._update_cands([[] if b["code"] in (None, ALL_GREEN) else b["members"]
                            for b in step["boards"]], update_rt, extra)

    def _blank_flips(self, rows, shift=None):
        """Every tile of `rows` (per board) flipped to the blank face -- letters gone
        -- as one cascade per row; `shift` moves the WHOLE board meanwhile. Returns
        (animations, letters to remove after)."""
        anims, dead = [], []
        for k, b in enumerate(self.boards):
            for r in range(b.n_rows):
                flipping = r in rows[k]
                flips = []
                for c in range(b.n_cols):
                    tile, letter = b.tiles[r][c], b.letters[r][c]
                    if flipping:
                        to = None if shift is None else tile.get_center() + shift
                        flips.append(TileFlip(tile, letter, TILE_EMPTY_FILL,
                                              stroke=TILE_EMPTY_BORDER, swap_to=None,
                                              to_center=to))
                        if letter is not None:
                            dead.append((b, r, c, letter))
                    elif shift is not None:
                        anims.append(tile.animate.shift(shift))
                if flips:
                    anims.append(LaggedStart(*flips, lag_ratio=0.25))
        return anims, dead

    def _drop_letters(self, dead):
        for b, r, c, letter in dead:
            b.remove(letter)
            self.remove(letter)
            b.letters[r][c] = None

    def _filled_rows(self):
        return [[r for r in range(b.n_rows) if b.letters[r][0] is not None]
                for b in self.boards]

    def _flip_word_anims(self, j):
        """Row j of every board flips to 16h's coloured guess j (SOLVE, EIGHT, WORDS
        -- the game n-q are written about), all tiles at once ("in one flip"). A
        tile already showing a letter swaps it at the midpoint. Returns (flips,
        old letters to remove after)."""
        flips, dead = [], []
        for k, b in enumerate(self.boards):
            code = BOARDS[k]["guesses"][j]["code"]
            trits = [(code // 3 ** (4 - i)) % 3 for i in range(5)]
            for c, ch in enumerate(GUESSES[j]):
                tile, old = b.tiles[j][c], b.letters[j][c]
                letter = b._letter(ch, tile).set_opacity(0)
                if old is not None:
                    dead.append((b, j, c, old))
                b.letters[j][c] = letter
                b.add(letter)
                self.add(letter)
                flips.append(TileFlip(tile, old, TILE_STATE[trits[c]], swap_to=letter))
        return flips, dead

    def _flip_word_in(self, j, run_time):
        flips, dead = self._flip_word_anims(j)
        self.play(*flips, run_time=run_time)
        for b, r, c, old in dead:
            b.remove(old)
            self.remove(old)

    # i : the game flips back to black, then the boards move up; TRIAL, and each
    #     board's candidates appear beneath it
    @subscene
    def replay_trial(self):
        anims, dead = self._blank_flips(self._filled_rows())
        self.play(*anims, run_time=1.2)
        self._drop_letters(dead)
        self.play(*[b.animate.shift(UP * RAISE) for b in self.boards], run_time=0.8)
        self.cands = [{} for _ in self.boards]
        self._play(REPLAY, 0, 0.65, 0.9, 1.0)       # TRIAL

    # j : GUESS
    @subscene
    def replay_guess(self):
        self._play(REPLAY, 1, 0.65, 0.9, 1.0)

    # k : COMBO
    @subscene
    def replay_combo(self):
        self._play(REPLAY, 2, 0.65, 0.9, 1.0)

    # l : THIRD -- the first answer, out of order
    @subscene
    def replay_third(self):
        self._play(REPLAY, 3, 0.65, 0.9, 1.0)

    # m : the rest of the game, faster, then the win wave
    @subscene
    def replay_rest(self):
        self._play(REPLAY, 4, 0.45, 0.6, 0.4)       # SIXTH
        self._play(REPLAY, 5, 0.45, 0.6, 0.4)       # SEVEN
        self._play(REPLAY, 6, 0.45, 0.6, 0.4)       # FIFTH
        self._play(REPLAY, 7, 0.45, 0.6, 0.4)       # OCTET
        self._play(REPLAY, 8, 0.45, 0.6, 0.4)       # FIRST
        self._play(REPLAY, 9, 0.45, 0.6, 0.4)       # HALVE
        self._play(REPLAY, 10, 0.45, 0.6, 0.4)      # FORTH
        self._wave(2.0, WEIRD)

    # n : every row back to black; the candidates go
    @subscene
    def blank_all(self):
        anims, dead = self._blank_flips(self._filled_rows())
        cands = [m for c in self.cands for m in c.values()]
        self.play(*anims, *[FadeOut(m) for m in cands], run_time=1.2)
        self.remove(*cands)
        self._drop_letters(dead)
        self.cands = [{} for _ in self.boards]

    # o : SOLVE typed and scored on every board -- the opener the rest of section 5
    #     is about (p-s are written for SOLVE EIGHT WORDS)
    @subscene
    def solve_again(self):
        types = []
        for k, b in enumerate(self.boards):
            anim, total = b.type_anim(self, 0, GUESSES[0], 0.65,
                                      per_letter=key_cues(self) if k == 0 else None)
            types.append(anim)
        self.play(*types, run_time=total)
        self.play(*[b.reveal_anim(0, BOARDS[k]["guesses"][0]["code"])
                    for k, b in enumerate(self.boards)], run_time=0.9)

    # p : row 2 back to the coloured EIGHT, in one flip
    @subscene
    def flip_eight(self):
        self._flip_word_in(1, 0.6)

    # q : row 3 back to WORDS, in one flip
    @subscene
    def flip_words(self):
        self._flip_word_in(2, 0.6)

    # r : rows 2 and 3 back to black, and SOLVE's candidates back
    @subscene
    def after_solve(self):
        anims, dead = self._blank_flips([[1, 2] for _ in self.boards])
        self.play(*anims, run_time=1.0)
        self._drop_letters(dead)
        assert GREEDY["steps"][0]["word"] == GUESSES[0] == "solve"
        self._update_cands([b["members"] for b in GREEDY["steps"][0]["boards"]], 1.0)

    def _setup_masks(self):
        self.masks = []
        gap = self.boards[1].get_left()[0] - self.boards[0].get_right()[0]
        for b in self.boards:
            m = Rectangle(width=b.width + gap, height=FH, stroke_width=0,
                          fill_color=BOARD_NAVY, fill_opacity=0.0)
            m.move_to([b.get_center()[0], 0, 0]).set_z_index(50)
            self.masks.append(m)
        self.add(*self.masks)

    def _emphasize(self, k, run_time):
        """Board k (and its candidates) at full strength, every other column dimmed."""
        self.play(*[m.animate.set_fill(opacity=0.0 if i == k else DIM)
                    for i, m in enumerate(self.masks)], run_time=run_time)

    def _greedy(self, j, lift=False):
        """16r's guess j: its board emphasised, then the guess played everywhere.
        `lift` fades the masks off with this guess's candidate update.

        THE LIFT IS BUILT HERE, AFTER `_emphasize`, NEVER BY THE CALLER: `.animate`
        keeps its target on the mobject itself (`.target`), so a lift built before
        `_emphasize` had its target overwritten by the emphasis's own -- it then
        animated nothing, and the masks vanished in one frame when removed."""
        self._emphasize(GREEDY["steps"][j]["target"], 0.5)
        extra = [m.animate.set_fill(opacity=0.0) for m in self.masks] if lift else []
        self._play(GREEDY, j, 0.65, 0.9, 0.8, extra)

    # s : the board with the fewest candidates emphasised, a random one of its
    #     candidates guessed, every board's candidates updated -- to the end
    @subscene
    def greedy(self):
        self._setup_masks()
        self._greedy(1)              # SEVER  (for board 7)
        self._greedy(2)              # SEVEN  (board 7)
        self._greedy(3)              # VALVE  (board 2)
        self._greedy(4)              # HALVE  (board 2)
        self._greedy(5)              # OCTET  (board 8)
        self._greedy(6)              # WORTH  (board 4)
        self._greedy(7)              # THIRD  (board 3)
        self._greedy(8)              # FIRST  (board 1)
        self._greedy(9)              # FORTH  (board 4)
        self._greedy(10)             # FIFTH  (board 5)
        # the masks lift WITH the last update, not as a quick fade of their own
        # after it -- seven columns brightening at once read as a flash
        self._greedy(11, lift=True)  # SIXTH  (board 6)
        self.remove(*self.masks)
        self.masks = None

    # ── the chart (16s-v of the script) ───────────────────────────────────────
    def _setup_chart(self):
        """The whole chart, built at home and then moved one frame down, so the
        frame's shift up brings it in. Lines are built but not on screen yet. A k
        with no value yet (multi_plot_data's "missing") is skipped, so the line is
        drawn straight across it."""
        ks = PLOT["ks"]
        keys = (1, 2, 3, "imp")
        label = {**LINE_LABEL, "imp": IMPROVED_LABEL}
        color = {**LINE_COLOR, "imp": IMPROVED_COLOR}
        cache_key = {1: "1", 2: "2", 3: "3", "imp": "improved"}
        series = [{"label": label[n], "color": color[n],
                   "values": [pt["misses"] for pt in PLOT["lines"][cache_key[n]]["points"]]}
                  for n in keys]
        plot = get_line_graph(series, ks, center=PLOT_C, width=PLOT_W, height=PLOT_H,
                              y_min=0.0, y_max=Y_MAX, x_tick_values=X_TICKS,
                              title="Average Misses in Multi-Wordle",
                              x_axis_label="Number of Wordles",
                              y_axis_label="Average Misses",
                              line_stroke=LINE_SW, ink_color=WHITE)
        geom = plot.plot_geom
        self.chart_frame = VGroup(plot.title_text, plot.x_axis, plot.y_axis,
                                  plot.x_ticks, plot.y_ticks,
                                  plot.x_axis_label_text, plot.y_axis_label_text)
        self.chart_lines = {n: plot.lines[i] for i, n in enumerate(keys)}
        self.chart_labels = {}
        for i, n in enumerate(keys):
            k, v = [(k, v) for k, v in zip(ks, series[i]["values"]) if v is not None][-1]
            # at the right edge if the line runs (nearly) the whole axis; a line
            # that stops well short (results still landing) is labelled UNDER its
            # last point, or the label sits across the lines that carry on past it
            side, buff = (RIGHT, 0.15) if k >= ks[-1] - 2 else (DOWN, 0.18)
            self.chart_labels[n] = crisp_text(label[n], font_size=FONT_SIZE_SM * 0.8,
                                              color=color[n]).next_to(
                line_point(geom, k, v), side, buff=buff)
            self.chart_labels[n].at_right = side is RIGHT
            self.chart_labels[n].natural_y = self.chart_labels[n].get_y()
        self.chart_shown = []           # the lines drawn so far, in order
        self.chart_frame.shift(DOWN * FH)

    def _label_ys(self, keys):
        """Where the right-edge labels of `keys` sit: level with their own lines,
        pushed apart only as far as the labels ON SCREEN need (user's call: a label
        moves up when a later one arrives beside it, rather than starting moved)."""
        right = [n for n in keys if self.chart_labels[n].at_right]
        ys = spread_label_ys([(self.chart_labels[n].natural_y, self.chart_labels[n].height)
                              for n in right], LABEL_GAP)
        return dict(zip(right, ys))

    # t : the game moves up off the frame, the empty chart comes up into it
    @subscene
    def chart_in(self):
        self._setup_chart()
        self.add(self.chart_frame)
        self.play(*[b.animate.shift(UP * FH) for b in self.boards],
                  self.chart_frame.animate.shift(UP * FH), run_time=1.2)
        self.remove(*self.boards)
        self.boards = None

    def _draw(self, keys, run_time):
        """Lines drawn left to right with their end labels fading in, as yahtzee's
        08line_graph (Create + FadeIn of the label). Labels already on screen that
        the new ones crowd slide aside in the same play."""
        ys = self._label_ys(self.chart_shown + list(keys))
        for n in keys:
            if n in ys:
                self.chart_labels[n].set_y(ys[n])
        moves = [self.chart_labels[n].animate.set_y(ys[n]) for n in self.chart_shown
                 if n in ys and abs(self.chart_labels[n].get_y() - ys[n]) > 1e-4]
        self.play(*[Create(self.chart_lines[n]) for n in keys],
                  *[FadeIn(self.chart_labels[n]) for n in keys], *moves,
                  run_time=run_time)
        self.chart_shown += list(keys)

    # u : the 3-word opener
    @subscene
    def plot_three(self):
        self._draw([3], 2.0)

    # v : the 2-word opener, then the 1-word opener -- one at a time
    @subscene
    def plot_one_two(self):
        self._draw([2], 2.0)
        self._draw([1], 2.0)

    # w : the improved strategy
    @subscene
    def plot_improved(self):
        self._draw(["imp"], 2.0)
