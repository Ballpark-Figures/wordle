"""01 Intro — START on a board, then every legal opener, stacked into a histogram.

Each of the 12972 words is a scored Wordle row against the mystery word INTRO,
stacked in its 0.01 bin of average guesses (fewest at the bottom).

BEAT MAP
  a type_start     — empty board (up from frame 0), START typed into row 0
  b to_navy        — rows 1-5 fade, the board drops so START is centred, bg to navy
  c score_start    — START flips against INTRO; "3.58 guesses" written below it
  d pan_great      — pan to GREAT; "3.50 guesses"
  e pan_slows      — pan to SLOWS; "3.70 guesses"
  f fill           — pan back to START (labels fade), then every word drops into
                     its stack; the camera follows the growth, rows squash flat and
                     the letters fade as the stacks get tall
  g zoom_left      — zoom into the leftmost stacks (the starters' bins centred),
                     rows back to full height; letters stay off
  h starters       — IRATE TRAIN ARISE CRANE RAISE SLATE STARE emphasised ONE AT A
                     TIME, each word's letters coming back with it
  i noise          — no change (the VO's noise plays over this; sound comes later)
  j left_ten       — zoom out to the left 10 bins, squashing again; the starters
                     drop back, everything stays dimmed
  k those_words    — zoom out until THOSE and WORDS are in frame, WORDS' column the
                     last on the right; THOSE and WORDS light up and their callouts —
                     a full-size copy just above each word on a short white line —
                     grow in while the camera zooms. ADIEU and AUDIO are lit and
                     called out here too, OFF SCREEN, so l can simply reveal them
  l hello          — zoom out to HELLO, its callout growing in on the way; the zoom
                     uncovers ADIEU and AUDIO, already there
  m zoom_out       — (added by the user, not yet in the Doc) out the rest of the
                     way to the whole histogram; callouts and emphasis fade

LETTERS: they fade out during the fill once the stacks outgrow legibility, and from
then on ONLY an emphasised word carries them (the user's rule).

REUSE MAP
  board, typing, flip        assets/board.py get_board / type_word / reveal
  typing sound               assets/keys.py key_cues (the only sound in the scene;
                             words appearing stay silent — the user's call)
  the histogram              assets/word_stacks.py WordStacks + StacksCamera
                             (bulk drawing — see its docstring for why)
  every average, bin, tile   assets/intro_data.py -> intro_cache.json: the
                             committed optturns sweep + math/wordle.py pattern()
  label numbers              the cache's `labels` (rounded to 2 dp)
  navy background            style.py BOARD_NAVY
  labels                     crisp_text, white, entering with FadeIn (never Write)
  callout words              assets/board.py get_scored_row — the board's own row
  emphasis                   the house dim-the-rest (0.2 opacity), in WordStacks
  colours                    config.py WORDLE_BG / TILE_*

CAMERA. Every move from d on goes through `_move_view`, which interpolates a VIEW —
frame left edge, frame bottom, frame width (geometric), squash (geometric) — and
rebuilds the stacks each frame from it. Frames are anchored bottom-left, so a zoom
keeps the histogram's corner steady rather than swinging round a centre. During the
fill the view is instead a FUNCTION OF HOW MANY WORDS ARE DOWN (`_fill_view`), so the
camera tracks the tallest stack exactly rather than chasing a guessed schedule.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import numpy as np
from manim import MovingCameraScene

from config import *
from assets.board import get_board, get_scored_row
from assets.keys import key_cues
from assets import intro_data
from assets.word_stacks import (WordStacks, StacksCamera, PITCH, STEP, SIDE,
                                WORD_W)

DATA = intro_data.load()
WORDS = DATA["words"]
IDX = {w: i for i, w in enumerate(WORDS)}
ANSWER_CODE = {w: DATA["codes"][IDX[w]] for w in DATA["pinned"]}
START_BIN = DATA["bins"][IDX["start"]]
BIN_LO, BIN_HI = min(DATA["bins"]), max(DATA["bins"])
N_FILL = len(DATA["order"])

ASPECT = 16 / 9
FRAME_W = 16.0
LABEL_FS = 40                 # "3.58 guesses"
LABEL_BUFF = 0.35             # gap under the word
SIDE_MARGIN = 1.0             # beside the leftmost stack in the zoomed views
FILL_BASE = 0.4               # fill: frame centre rises 0.4 per unit of extra height
FILL_TOP = 0.85               # fill: tallest stack reaches this fraction of the frame
FULL_MARGIN = 10.0            # full view: space either side of the histogram
SQUASH_FROM = 20              # fill: rows stay square until a stack is this tall
LETTERS_FADE = (25, 60)       # fill: letters fade out between these stack heights
STARTERS = ["irate", "train", "arise", "crane", "raise", "slate", "stare"]
CALLED_OUT = ["those", "words", "hello", "adieu", "audio"]

# CALLOUTS sit a little ABOVE their word in the histogram, joined to it by a short
# white line (the user's call — they may overlap the stacks). Sizes are in SCREEN
# terms (fractions of the frame), so a callout stays legible while the camera zooms.
CALLOUT_W = 0.12              # a callout word's width, as a fraction of frame width
CALLOUT_LIFT = 0.05           # line length, as a fraction of frame height
LINE_STROKE = 3.0             # line width as it would be in a 16-wide frame
CALLOUT_DX = {"words": -0.07, "adieu": 0.07}
                              # sideways lean, as a fraction of frame width: WORDS'
                              # callout leans left so it fits in k, whose right edge
                              # is WORDS' column; ADIEU's leans right so it stays out
                              # of k's frame until l reveals it
WORDS_AT = 0.72               # k, l: WORDS sits this far up the frame, leaving
                              # room above it for its callout


def x_of_bin(b):
    return (b - START_BIN) * PITCH


HIST_L = x_of_bin(BIN_LO) - WORD_W / 2
HIST_R = x_of_bin(BIN_HI) + WORD_W / 2


def row_top(rows, s):
    """y of the top edge of a stack `rows` words high, at squash s."""
    return STEP * s * (rows - 1) + SIDE * s / 2


# ── the fill's camera: a function of the tallest stack ────────────────────────
def _fill_frame(h_rows, s):
    """(left, bottom, width) for a fill frame whose tallest stack is h_rows high."""
    h = max(9.0, (row_top(h_rows, s) + FILL_BASE * 9) / FILL_TOP)
    w = h * ASPECT
    cy = FILL_BASE * (h - 9)
    span = HIST_R - HIST_L + 2 * FULL_MARGIN
    mid = (HIST_L + HIST_R) / 2
    if w >= span:
        cx = mid
    else:
        cx = min(max(0.0, HIST_L - FULL_MARGIN + w / 2), HIST_R + FULL_MARGIN - w / 2)
    return cx - w / 2, cy - h / 2, w


def _full_squash():
    """The squash at which the finished histogram exactly fills the full-view width.

    Solved so the fill's own framing rule, at the tallest stack, gives a frame just
    wide enough for every stack plus FULL_MARGIN each side — so the fill ENDS on the
    full view by construction rather than by a hand-matched constant."""
    tall = max(DATA["rows"]) + 1
    h = (HIST_R - HIST_L + 2 * FULL_MARGIN) / ASPECT
    return (h * FILL_TOP - FILL_BASE * 9) / row_top(tall, 1.0)


S_FULL = _full_squash()


def _squash_for(h_rows):
    """Square rows until SQUASH_FROM, then geometric down to S_FULL at the peak."""
    tall = max(DATA["rows"]) + 1
    if h_rows <= SQUASH_FROM:
        return 1.0
    u = np.log(h_rows / SQUASH_FROM) / np.log(tall / SQUASH_FROM)
    return float(np.exp(np.log(S_FULL) * u))


def _letters_for(h_rows):
    a, b = LETTERS_FADE
    return float(np.clip((b - h_rows) / (b - a), 0, 1))


# ── named views, as (left, bottom, width, squash) ─────────────────────────────
def view_on(word):
    """A plain 16-wide frame centred on a pinned word at row 0."""
    x = x_of_bin(DATA["bins"][IDX[word]])
    return (x - FRAME_W / 2, -4.5, FRAME_W, 1.0)


def view_fit(right, top_rows, s, bottom=-1.5):
    """Left edge beside the first stack; wide enough to reach `right`, and tall
    enough for `top_rows` rows at squash s — whichever needs the bigger frame."""
    left = HIST_L - SIDE_MARGIN
    w = right - left
    h = max(w / ASPECT, row_top(top_rows, s) + 1.0 - bottom)
    return (left, bottom, h * ASPECT, s)


def _bin_right(b):
    return x_of_bin(b) + WORD_W / 2 + SIDE_MARGIN


def _rows_of(words):
    return max(DATA["rows"][IDX[w]] for w in words) + 1


def view_centred(bins, top_rows, s, bottom=-1.5):
    """Centred horizontally on a run of bins, tall enough for `top_rows` rows."""
    cx = (x_of_bin(min(bins)) + x_of_bin(max(bins))) / 2
    span = x_of_bin(max(bins)) - x_of_bin(min(bins)) + WORD_W + 2 * SIDE_MARGIN
    w = max(span, (row_top(top_rows, s) + 1.0 - bottom) * ASPECT)
    return (cx - w / 2, bottom, w, s)


# g: the starters' bins centred, every starter in frame, rows at full height
VIEW_STARTERS = view_centred([DATA["bins"][IDX[w]] for w in STARTERS],
                             _rows_of(STARTERS), 1.0)
# j: the left 10 bins, squashing again
VIEW_TEN = view_fit(_bin_right(BIN_LO + 9), 0, 0.5)
# k: THOSE and WORDS in frame, WORDS' column the last on the right (the right edge
# halfway into the gap after it, so ADIEU's stack is out), with room above WORDS
# for its callout
_K_RIGHT = x_of_bin(DATA["bins"][IDX["words"]]) + WORD_W / 2 + (PITCH - WORD_W) / 2
_K_W = _K_RIGHT - (HIST_L - SIDE_MARGIN)
_K_S = (WORDS_AT * _K_W / ASPECT - 1.5) / (STEP * DATA["rows"][IDX["words"]])
VIEW_THOSE_WORDS = (HIST_L - SIDE_MARGIN, -1.5, _K_W, _K_S)
# l: out to HELLO; ADIEU and AUDIO are between. Squashed only enough to keep WORDS
# at WORDS_AT of the (bigger) frame — NOT k's squash, which only k's narrow frame
# needs. Carrying k's squash here left l flatter than the full view, so m's zoom
# OUT made the stacks grow UP on screen as the rows unsquashed.
# (wide enough that HELLO's callout, centred on it and CALLOUT_W of the frame
# wide, fits: w = x + w * CALLOUT_W / 2 + margin - left, solved for w)
_L_W = (x_of_bin(DATA["bins"][IDX["hello"]]) + SIDE_MARGIN - (HIST_L - SIDE_MARGIN)) \
    / (1 - CALLOUT_W / 2)
_L_S = (WORDS_AT * _L_W / ASPECT - 1.5) / (STEP * DATA["rows"][IDX["words"]])
VIEW_HELLO = (HIST_L - SIDE_MARGIN, -1.5, _L_W, _L_S)
# m: the whole histogram — the view the fill ends on
_TALL = max(DATA["rows"]) + 1
VIEW_FULL = (*_fill_frame(_TALL, _squash_for(_TALL)), _squash_for(_TALL))


class Scene01(MovingCameraScene, WordleDarkScene):
    def __init__(self, **kwargs):
        super().__init__(camera_class=StacksCamera, **kwargs)

    def setup_scene(self):
        # the empty board is on screen from frame 0 (the script opens on it)
        self.board = get_board()
        self.add(self.board)
        self.callouts = None

    # ── helpers ───────────────────────────────────────────────────────────────
    def _bg_to(self, color):
        """An animation tweening the camera background (the setter rebuilds it)."""
        cam, c0 = self.camera, ManimColor(self.camera.background_color)
        return UpdateFromAlphaFunc(
            Mobject(), lambda m, a: setattr(cam, "background_color",
                                            interpolate_color(c0, color, a)))

    def _label(self, word):
        t = crisp_text(f"{DATA['labels'][IDX[word]]} guesses", color=WHITE,
                       font_size=LABEL_FS)
        x = x_of_bin(DATA["bins"][IDX[word]])
        t.next_to(np.array([x, -SIDE / 2, 0]), DOWN, buff=LABEL_BUFF)
        return t

    def _set_frame(self, left, bottom, w):
        f = self.camera.frame
        f.stretch_to_fit_width(w).stretch_to_fit_height(w / ASPECT)
        f.move_to([left + w / 2, bottom + w / ASPECT / 2, 0])

    def _apply_view(self, v):
        left, bottom, w, s = v
        self._set_frame(left, bottom, w)
        self.stacks.set_state(squash=s)

    def _move_view(self, to, run_time, letters=None, dim=None, weights=None,
                   callouts=None, present=(), callout_alpha=None, extra=(),
                   rate_func=smooth):
        """Animate the view (and optionally letter opacity / emphasis) to `to`.

        `callouts` is {word: (u0, u1)}: that word's callout is created and GROWS IN
        over that stretch of the move (its line first, then the word), so a callout
        can arrive while the camera is still zooming. `present` callouts are
        created already fully grown (for words off screen, waiting to be revealed).
        `callout_alpha` fades every
        callout on screen to that opacity.

        Left and bottom interpolate linearly, width and squash geometrically, and
        the stacks are rebuilt every frame from the interpolated view. The updater
        is REMOVED before returning, so nothing unpicklable reaches the snapshot."""
        fr = self.view
        l0, d0 = self.stacks.letter_opacity, self.stacks.dim
        l1 = l0 if letters is None else letters
        d1 = d0 if dim is None else dim
        w1 = weights or {}
        w0 = self.stacks.weights_of(w1)
        grow = callouts or {}
        for word in grow:
            self._callout(word)
        for word in present:
            self._callout(word)["g"] = 1.0
        a0 = {c["word"]: c["a"] for c in self.callouts or []}
        t = ValueTracker(0)

        def lerp(a, b, u):
            return a + (b - a) * u

        def glerp(a, b, u):
            return float(np.exp(lerp(np.log(a), np.log(b), u)))

        def upd(m):
            u = t.get_value()
            v = (lerp(fr[0], to[0], u), lerp(fr[1], to[1], u),
                 glerp(fr[2], to[2], u), glerp(fr[3], to[3], u))
            self._apply_view(v)
            m.set_state(letters=lerp(l0, l1, u), dim=lerp(d0, d1, u),
                        weights={w: lerp(w0[w], w1[w], u) for w in w1})
            m.refresh(self.camera.frame)
            for c in self.callouts or []:
                if c["word"] in grow:
                    u0, u1 = grow[c["word"]]
                    c["g"] = float(np.clip((u - u0) / (u1 - u0), 0, 1))
                if callout_alpha is not None:
                    c["a"] = lerp(a0[c["word"]], callout_alpha, u)
            self._place_callouts()

        self.stacks.add_updater(upd)
        self.play(t.animate.set_value(1), *extra, run_time=run_time,
                  rate_func=rate_func)
        self.stacks.remove_updater(upd)
        self.remove(t)
        self.view = to

    # ── callouts: a full-size copy of a word, just above it, on a short line ───
    def _callout(self, word):
        """Build a callout for `word`, not yet grown in, and register it."""
        row = get_scored_row(word, DATA["codes"][IDX[word]])
        line = Line(ORIGIN, UP, color=WHITE)
        c = {"word": word, "row": row, "line": line, "g": 0.0, "a": 1.0}
        self.callouts.append(c)
        self.add(line, row)
        return c

    def _place_callouts(self):
        """Put every callout above its word at the current zoom and squash.

        `g` grows it in: the line draws up from the word over the first half, the
        word fades in over the second. `a` scales the whole callout's opacity."""
        f = self.camera.frame
        w, h = f.width, f.height
        for c in self.callouts or []:
            row, line = c["row"], c["line"]
            row.scale_to_fit_width(CALLOUT_W * w)
            top = self.stacks.word_center(c["word"]) + \
                UP * SIDE * self.stacks.squash / 2
            foot = top + UP * CALLOUT_LIFT * h \
                + RIGHT * CALLOUT_DX.get(c["word"], 0) * w     # the callout's bottom-centre
            row.move_to(foot + UP * row.height / 2)
            g_line = min(1.0, 2 * c["g"])
            g_row = max(0.0, 2 * c["g"] - 1)
            line.put_start_and_end_on(top, top + (foot - top) * max(g_line, 1e-3))
            line.set_stroke(WHITE, width=LINE_STROKE * w / FRAME_W,
                            opacity=c["a"] * (1.0 if g_line > 0 else 0.0))
            row.set_opacity(c["a"] * g_row)

    # a : empty board up from frame 0; START typed into row 0
    @subscene
    def type_start(self):
        self.board.type_word(self, 0, "start", run_time=3.0, per_letter=key_cues(self))

    # b : bottom five rows fade, board drops so START is centred, bg to navy
    def _setup_to_navy(self):
        b = self.board
        self.start_row = VGroup(*b.tiles[0], *b.letters[0])
        self.empty_rows = VGroup(*b.rows[1:])
        self.drop = b.tiles[0][2].get_center()[1]      # START's centre -> y = 0

    @subscene
    def to_navy(self):
        self._setup_to_navy()
        self.play(self.empty_rows.animate.shift(DOWN * self.drop).set_opacity(0),
                  self.start_row.animate.shift(DOWN * self.drop),
                  self._bg_to(BOARD_NAVY), run_time=1.5)
        self.remove(self.empty_rows)
        self.empty_rows = None

    # c : START flips against INTRO; its average written below it
    def _setup_score_start(self):
        self.labels = {"start": self._label("start")}

    @subscene
    def score_start(self):
        self._setup_score_start()
        self.board.reveal(self, 0, ANSWER_CODE["start"], run_time=1.6)
        self.play(FadeIn(self.labels["start"], shift=UP * 0.2), run_time=1.0)

    # d : pan to GREAT
    def _setup_pan_great(self):
        # the bulk histogram takes over from the board row here: it draws START
        # (and GREAT and SLOWS, off screen) at exactly the board row's size, so
        # swapping one for the other is invisible
        self.stacks = WordStacks(DATA, origin=ORIGIN, origin_bin=START_BIN)
        self.view = view_on("start")
        self._apply_view(self.view)
        self.stacks.refresh(self.camera.frame)
        self.labels["great"] = self._label("great")
        self.labels["slows"] = self._label("slows")

    @subscene
    def pan_great(self):
        self._setup_pan_great()
        # HARD clear, not remove(board): the flip and the drop each added their own
        # groups of board tiles at top level, and those would linger over START
        # (undimmed, unsquashed) for the rest of the scene
        for m in list(self.mobjects):
            self.remove(m)
        self.board = self.start_row = None
        self.add(self.stacks, self.labels["start"])
        self._move_view(view_on("great"), run_time=2.0)
        self.play(FadeIn(self.labels["great"], shift=UP * 0.2), run_time=1.0)

    # e : pan to SLOWS
    @subscene
    def pan_slows(self):
        self._move_view(view_on("slows"), run_time=3.0)
        self.play(FadeIn(self.labels["slows"], shift=UP * 0.2), run_time=1.0)

    # f : back to START (labels fade), then every word drops into its stack
    def _setup_fill(self):
        # the tallest stack after k words of the fill, for every k — so the camera,
        # the squash and the letter fade are all a function of the fill itself
        bins = np.array(DATA["bins"])
        count = {b: 0 for b in set(DATA["bins"])}
        for w in DATA["pinned"]:
            count[DATA["bins"][IDX[w]]] += 1
        tall = np.empty(N_FILL + 1, dtype=int)
        tall[0] = max(count.values())
        for k, i in enumerate(DATA["order"]):
            count[bins[i]] += 1
            tall[k + 1] = max(tall[k], count[bins[i]])
        self.fill_tall = tall

    @subscene
    def fill(self):
        self._setup_fill()
        self._move_view(view_on("start"), run_time=2.5,
                        extra=[FadeOut(VGroup(*self.labels.values()))])
        self.labels = None

        t = ValueTracker(0)
        tall = self.fill_tall

        def upd(m):
            n = int(round(t.get_value() * N_FILL))
            h = int(tall[n])
            s = _squash_for(h)
            left, bottom, w = _fill_frame(h, s)
            self._set_frame(left, bottom, w)
            m.set_state(n=n, squash=s, letters=_letters_for(h))
            m.refresh(self.camera.frame)

        # slow at first (the first words land one by one), then accelerating
        k = 9.0
        grow = lambda u: (np.exp(k * u) - 1) / (np.exp(k) - 1)
        self.stacks.add_updater(upd)
        self.play(t.animate.set_value(1), run_time=20.0, rate_func=grow)
        self.stacks.remove_updater(upd)
        self.remove(t)
        h = int(tall[-1])
        s = _squash_for(h)
        self.view = (*_fill_frame(h, s), s)

    # g : zoom into the leftmost stacks, rows back to full height, letters back
    @subscene
    def zoom_left(self):
        self._move_view(VIEW_STARTERS, run_time=3.0)

    # h : Wordlebot's regulars
    @subscene
    def starters(self):
        # the rest dims as the first comes up, then one word at a time
        self._move_view(VIEW_STARTERS, run_time=0.8, dim=1.0, weights={"irate": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"train": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"arise": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"crane": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"raise": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"slate": 1})
        self.wait(0.4)
        self._move_view(VIEW_STARTERS, run_time=0.5, weights={"stare": 1})

    # i : the noise — no change
    @subscene
    def noise(self):
        pass

    # j : out to the left 10 bins, squashing again; the rest stays dimmed
    @subscene
    def left_ten(self):
        self._move_view(VIEW_TEN, run_time=2.5, weights={w: 0 for w in STARTERS})

    # k : out until THOSE and WORDS are in frame; their callouts grow in as it zooms.
    # ADIEU and AUDIO are lit and called out now, off screen, for l to uncover.
    @subscene
    def those_words(self):
        self.callouts = []
        self._move_view(VIEW_THOSE_WORDS, run_time=3.0,
                        weights={"those": 1, "words": 1, "adieu": 1, "audio": 1},
                        callouts={"those": (0.35, 0.75), "words": (0.6, 1.0)},
                        present=["adieu", "audio"])

    # l : out to HELLO, its callout growing in on the way; ADIEU and AUDIO uncovered
    @subscene
    def hello(self):
        self._move_view(VIEW_HELLO, run_time=2.5, weights={"hello": 1},
                        callouts={"hello": (0.5, 1.0)})

    # m : out the rest of the way; callouts and emphasis fade
    @subscene
    def zoom_out(self):
        self._move_view(VIEW_FULL, run_time=3.0, dim=0.0, callout_alpha=0.0,
                        weights={w: 0 for w in CALLED_OUT})
        self.remove(*[m for c in self.callouts for m in (c["row"], c["line"])])
        self.callouts = None
