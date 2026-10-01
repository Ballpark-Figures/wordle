"""Scene 15 — multi-word openers, and a strategy that always wins. Navy background.

Scene 14 ends with everything faded out, so a starts on an empty frame. Talking head
THJ follows, so the scene ends with LEDGE PAWNS ROCKY THUMB on screen.

GEOMETRY: the boards live in the frame at the origin; scene 14's number line sits ONE
FRAME ABOVE them (StrategyLine `_build_line(..., dy=GAME_DY)`), so the script's "bring
back the timeline" / "move up to reveal a board" / "go back down to the timeline" are
camera pans (13's convention) and nothing fades.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a second_words — SALET in the top-left corner and its 148 groups as coloured rows
                   (scene 12's view, no dots: user's call) fade in; every optimal
                   second word is typed under its row at once      (15a, VO 1)
  b clone        — every second word flips to CLONE, and CLONE is typed under the
                   corner SALET (user's call)                  (15b, VO 2)
  c to_board     — the corner SALET (the uncoloured one: user's call) and the
                   CLONE under it travel into rows 1 and 2 of a board in the
                   middle as its other rows fade in around them; everything else
                   shrinks away                                    (15c, VO 3)
  d third        — THIRD typed into row 3                          (15d, VO 3)
  e timeline     — the camera pans up to scene 14's number line as it ended: 3.42 to
                   4.08, the Optimal, Random Compatible Answers and SLATE markers
                                                                   (15e, VO 4)
  f two_words    — the PARSE CLINT marker pops out at 3.69, below the line
                                                                   (15f, VO 5)
  g crane_spilt  — its words flip to CRANE SPILT as it slides to 3.70, the win rate
                   counting                                        (15g, VO 5)
  h three_words  — the line zooms out to fit 4.16, the DANCE HORST BLIMP marker
                   popping out there, above the line               (15h, VO 6)
  i bland_copse  — flips to BLAND COPSE RIGHT, sliding to 4.17     (15i, VO 6)
  j four_words   — the line zooms out to fit 5.02, the CHAMP FLINT RUGBY SOWED
                   marker popping out there, above the line        (15j, VO 7)
  k bugle_champ  — flips to BUGLE CHAMP DOWNY FIRST (same 5.02)    (15k, VO 7)
  l reveal_board — the camera pans down to an empty board          (15l, VO 8)
  m five_words   — BLUNK CIMEX GRYPT VOZHD WAQFS typed             (15m, VO 9)
  n puree        — the five rows flip to the colouring PUREE, PURER, RUPEE and UPPER
                   all give                                        (15n, VO 9)
  o board_left   — the board moves to the left half                (15o, VO 9)
  p puree_words  — PUREE PURER RUPEE UPPER typed at once, a column on the right half
                   (user's call)                                   (15p, VO 9)
  q chott        — the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the four words
                   fade out                                        (15q, VO 10)
  r unsolved     — its 16 unsolved answers fade in on the right, grouped by the
                   feedback they share                             (15r, VO 10)
  s board_back   — the words slide off to the right; the board back to centre
                                                                   (15s, VO 11)
  t six_words    — the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK (15t, VO 11)
    (VO 12 has no subscene)
  u back_to_line — the camera pans up to the number line           (15u, VO 13)
  v two_up       — every marker but the 2-word one dims            (15v, VO 13)
  w four_up      — the 2-word marker dims, the 3- and 4-word ones return (user's
                   call: the VO now says "a 3- or 4-word opener") (15w, VO 13)
  x empty_board  — the camera pans down to an empty board          (15x, VO 14)
  y climb_start  — trial 68's starting words typed: QUERY NINNY BALER MASSE
                                                                   (15y, VO 14)
  z climb        — each of its nine accepted moves flips the rows it changes, ending
                   on LEDGE PAWNS ROCKY THUMB                      (15z, VO 14)
  za finale      — the two empty rows drop off the bottom; the four words grow,
                   centred                                         (15za, VO 15)

REUSE MAP — every element, the one source it comes from, and how it enters:
  SALET (a)             assets/pigpen.py `PigpenWord(revealed=True)` at GUESS_SCALE in
                        the corner — scene 12's corner word (assets/second_view.py
                        `corner_spot`, moved out of scene 12 for this scene)
  coloured rows (a)     assets/second_view.py `group_rows` — 12's rows at 06b's
                        dot-view sizes, sorted by size
  a's entrance          plain FadeIn of the word and rows together (13a's: the frame
                        was cleared, 13number_line.py:182)
  second words (a)      12d's typing: `WordleBoard.type_anim` under each row, all in
                        ONE play, key sound on the first only (12efficient_strats.py
                        second_words); words from strategy_data (the optimal trees)
  every word flip       assets/flip.py `Flip` by `row_parts` (12e's word flips)
  boards (c, l-za)      assets/board.py at the origin, unscaled — 02's and 04's board;
                        from l on, six one-row boards stacked at the board's spacing,
                        so each row can be typed, flipped and moved on its own
  rows leaving (c)      06b's shrink-out (strategy_line `shrink_out`)
  typing                `WordleBoard.type_word` + assets/keys.py `key_cues` (02's);
                        y types four rows in one play, key sound on the first (12d's)
  number line (e-k,u-w) assets/strategy_line.py `StrategyLine` — scene 14's line,
                        title, subtitle and markers, built one frame up
  pans                  StrategyLine `_pan_up` / `_pan_down` (13's pan + whoosh)
  new markers (f,h,j)   StrategyLine `opener_marker` (13's cards: the words, "Then
                        RCA", the win rate; several words as a `word_stack`, board-
                        tight, SLATE's size: user's calls) popping out with the pop
                        sound (`_pop_in`; with a zoom, `_zoom_pop` as 13c/e)
  zooms (h, j)          13e's rule, the leftmost marker at the left end and the new one
                        at the right, but at +-ZOOM_EDGE (6.5, not 13e's 6) so the
                        full-size cards clear each other — only when a new marker
                        would not fit (user's call)
  marker swaps (g,i,k)  StrategyLine `replace_marker` — 14c's flip-while-sliding with
                        the win rate counting (moved there from scene 14 for this)
  emphasis (v, w)       dim the rest to 0.2 (house rule: save_state / Restore)
  p's words             one-row boards typed in ONE play, key sound on the first only
                        (12d's), at the board's size and spacing
  r's words             PigpenWord(revealed=True) — 04's answer words, by
                        `ranked_word_layout` (07's groups, filling the region), its
                        rows of groups then re-spread by `_close_columns`
  words in / out        plain FadeIn / FadeOut; s slides them off to the right
  finale (za)           the rows move and scale as one (no source: the script's own)
  colours               BOARD_NAVY via WordleBoardScene; win rates by `win_color`

EVERY NUMBER is sourced (assets/always_win_data.py -> its cache; provenance there):
  SLATE                     3.82, 98.87% (scene 14's exact rate: user's call, not
                            the VO's 98.86%)
  PARSE CLINT / CRANE SPILT 3.69, 99.48% / 3.70, 99.51%     openexact, exact
  DANCE HORST BLIMP / BLAND COPSE RIGHT   4.16, 99.84% / 4.17, 99.91%
  CHAMP FLINT RUGBY SOWED / BUGLE CHAMP DOWNY FIRST   5.02, 99.92% / 5.02, 99.88%
  BLUNK CIMEX GRYPT VOZHD WAQFS 72 unsolved; PUREE PURER RUPEE UPPER share codes
  CHOTT DUMBO FAWNY VERGE SPILL 16 unsolved, in 8 groups
  CATTY FROND RUMBA SPILL VERGE WHACK separates all 2315
  trial 68: QUERY NINNY BALER MASSE, nine moves, LEDGE PAWNS ROCKY THUMB
The markers' averages are shown only by where they sit (13's convention). The VO's
72/16 are spoken, not shown.

NB LEDGE PAWNS ROCKY THUMB has ONE unsolved answer under the custom.txt follow-up:
SALLE, beside FALSE and SALVE. The user accepts that (2026-10-01): nobody guesses
SALLE over SALVE. Do not re-flag it.

LAYOUT CHOICES, flagged:
  - b: the corner CLONE's letter i lands as the words' tile i turns over (user's
    call: in sync), derived from the flips' lag.
  - c: the travelling rows sit above everything they cross (z-index 1: user's
    call); their borders thicken to the board's STROKE.
  - Every opener card reads "Then RCA" (user's call); the 4.08 card keeps "Random
    Compatible Answers" with its initials bold.
  - Marker sides: 2-word below, 3- and 4-word above (the 4-word card is tall, and
    at the right end nothing is above the line), so no two cards overlap.
  - p: the four words at the board's size, a column centred on the right half,
    mirroring the board.
  - r: the sixteen words grouped (their shared feedback is not drawn), largest group
    first, right of the board; the space between the two columns of groups equals
    the space between their rows (user's call: the layout's last row was squeezed
    and read as one group of four).
  - y: the board's slot order is the climb's slots 2, 0, 1, 3 (user's call: an order
    that ends on LEDGE PAWNS ROCKY THUMB; a blind opening's score ignores order).
  - za: the four rows grow to FINAL_SCALE, centred on the frame.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from assets import lists_data, strategy_data, always_win_data, random_compatible_data
from assets.board import (STROKE, GAP, WordleBoard, get_board, get_typed_row,
                          get_scored_row)
from assets.pigpen import PigpenWord
from assets.flip import Flip, flip, row_parts
from assets.groups import (GUESS_SCALE, ranked_word_layout, REGION_HALF_W,
                           DOT_REGION_TOP, REGION_BOT)
from assets.keys import key_cues
from assets.second_view import corner_spot, row_stroke, under, typed_under, group_rows
from assets.strategy_line import (StrategyLine, GAME_DY, shrink_out,
                                  word_stroke, OPTIMAL, COMPATIBLE)

DATA = lists_data.load()
SD = strategy_data.load()
AW = always_win_data.load()
SLATE = random_compatible_data.load()["openers"]["slate"]   # scene 14's marker
SALET, CLONE, THIRD = "salet", "clone", "third"      # the script's words
TWO, TWO_B = "parse clint", "crane spilt"            # the script's openers
THREE, THREE_B = "dance horst blimp", "bland copse right"
FOUR, FOUR_B = "champ flint rugby sowed", "bugle champ downy first"
BLUNK = "blunk cimex grypt vozhd waqfs"
CHOTT = "chott dumbo fawny verge spill"
SIX = "catty frond rumba spill verge whack"

BOARD_SIDE_X = 4.0         # o: how far left the board moves
UNSOLVED_LEFT = -1.1       # r: the grouped words' region starts here
FLIP_LAG = 0.25            # b: the word flips' lag_ratio (Flip's default), which
                           #   CLONE's typing is timed against
POP_RT = 0.3               # b: one CLONE letter's pop
ZOOM_EDGE = 6.5            # h, j: where a zoom puts its end markers (13e: 6)
LINE_DROP = -0.2           # the line sits this much lower than 13/14's and every
MARKER_STEM_15 = 0.3       #   stem is shorter (13: 0.45), so the full-size 3- and
                           #   4-word cards clear the subtitle and the frame edge
FINAL_SCALE = 1.5          # za: the four rows' growth


def _tiles(row):
    """A word row's tiles: a PigpenWord's, or a one-row board's."""
    return row.tiles if isinstance(row, PigpenWord) else row.tiles[0]


def _stack():
    """An empty board as six one-row boards at the board's spacing, at the origin
    (the same geometry as get_board), so each row is its own mobject."""
    rows = [WordleBoard(rows=1, cols=5) for _ in range(6)]
    VGroup(*rows).arrange(DOWN, buff=GAP).move_to(ORIGIN)
    return rows


def _close_columns(groups, slots, sc, left, right):
    """15r: the layout's group blocks keep their rows, but each row of blocks is
    re-spread so the space between blocks ACROSS equals the space between block
    rows DOWN (user's call), centred in [left, right]. `sc` is the layout's word
    scale. Returns new slots."""
    probe = PigpenWord(groups[0]["members"][0], revealed=True).scale(sc)
    wd, ht = probe.width, probe.height
    blocks = []
    for g in groups:
        pts = np.array([slots[w] for w in g["members"]])
        blocks.append({"members": g["members"], "pts": pts, "cx": pts[:, 0].mean(),
                       "top": pts[:, 1].max() + ht / 2,
                       "bot": pts[:, 1].min() - ht / 2,
                       "w": pts[:, 0].max() - pts[:, 0].min() + wd})
    tops = sorted({round(b["top"], 6) for b in blocks}, reverse=True)
    rows = [[b for b in blocks if round(b["top"], 6) == t] for t in tops]
    out = {w: p for b in blocks for w, p in zip(b["members"], b["pts"])}
    if len(rows) < 2:
        return out
    vgap = min(b["bot"] for b in rows[0]) - max(b["top"] for b in rows[1])
    mid = (left + right) / 2
    for r in rows:
        r.sort(key=lambda b: b["cx"])
        total = sum(b["w"] for b in r) + vgap * (len(r) - 1)
        x = mid - total / 2
        for b in r:
            cx = x + b["w"] / 2
            for w, p in zip(b["members"], b["pts"]):
                out[w] = np.array([cx + p[0] - b["cx"], p[1], 0.0])
            x += b["w"] + vgap
    return out


def _at(new, old):
    """`new` (a one-row word) sized and placed over `old`."""
    return new.scale(old.width / new.width).move_to(old)


class Scene15(StrategyLine, MovingCameraScene, WordleBoardScene):
    """second_words — SALET and its coloured rows; every optimal second word typed
    clone — every second word flips to CLONE
    to_board — SALET and a CLONE into a board's first two rows; the rest goes
    third — THIRD typed into row 3
    timeline — pan up to scene 14's line
    two_words — PARSE CLINT at 3.69
    crane_spilt — flips to CRANE SPILT at 3.70
    three_words — zoom; DANCE HORST BLIMP at 4.16
    bland_copse — flips to BLAND COPSE RIGHT at 4.17
    four_words — zoom; CHAMP FLINT RUGBY SOWED at 5.02
    bugle_champ — flips to BUGLE CHAMP DOWNY FIRST
    reveal_board — pan down to an empty board
    five_words — BLUNK CIMEX GRYPT VOZHD WAQFS typed
    puree — the rows flip to PUREE's colouring
    board_left — the board to the left half
    puree_words — PUREE PURER RUPEE UPPER on the right
    chott — the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the words go
    unsolved — its 16 unsolved answers, grouped, on the right
    board_back — the words off right; the board back to centre
    six_words — the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK
    back_to_line — pan up to the line
    two_up — dim all but the 2-word marker
    four_up — the 4-word marker instead
    empty_board — pan down to an empty board
    climb_start — QUERY NINNY BALER MASSE typed
    climb — the nine moves, to LEDGE PAWNS ROCKY THUMB
    finale — the empty rows drop away; the four grow, centred
    """

    def setup_scene(self):
        self.marker_stem = MARKER_STEM_15

    # a : SALET in the corner and its coloured rows fade in; every optimal second
    #     word is typed under its row at once
    def _setup_second_words(self):
        corner, left = corner_spot(SALET)
        self.guess = PigpenWord(SALET, revealed=True).scale(GUESS_SCALE).move_to(corner)
        self.groups, self.rows, _, _ = group_rows(DATA, SALET, left)
        sec = SD["second"][SALET]
        self.blanks = []
        for g, row in zip(self.groups, self.rows):
            b = WordleBoard(rows=1, cols=5)
            b.scale(row.width / b.width).move_to(under(row))
            self.blanks.append((b, sec[str(g["code"])]))

    @subscene
    def second_words(self):
        self._setup_second_words()
        self.play(FadeIn(self.guess), *[FadeIn(r) for r in self.rows], run_time=1.0)
        anims, total = [], 0.0
        for i, (b, word) in enumerate(self.blanks):
            a, total = b.type_anim(self, 0, word, 0.65,
                                   per_letter=key_cues(self) if i == 0 else None,
                                   appear=True, stroke=row_stroke(b.width))
            anims.append(a)
        self.play(*anims, run_time=total)
        self.words = [b for b, _ in self.blanks]
        self.blanks = None

    # b : every second word flips to CLONE, and CLONE is typed under the corner SALET
    def _setup_clone(self):
        self.clones = [typed_under(CLONE, row) for row in self.rows]
        self.corner_clone = WordleBoard(rows=1, cols=5)
        self.corner_clone.scale(self.guess.width / self.corner_clone.width)
        self.corner_clone.move_to(under(self.guess))

    @subscene
    def clone(self):
        self._setup_clone()
        cc, rt = self.corner_clone, 1.2
        # CLONE's letter i lands as every word's tile i turns over: a Flip of 5
        # parts at lag 0.25 gives each part d = 1 / (1 + 4 * 0.25) of the run, part
        # i starting at i * 0.25 * d and turning over half-way through it
        d = 1 / (1 + 4 * FLIP_LAG)
        t0, gap = d / 2 * rt, FLIP_LAG * d * rt
        cues = key_cues(self)
        typing, total = cc.type_anim(self, 0, CLONE, POP_RT, key_gap=gap, appear=True,
                                     per_letter=lambda i, ch, at: cues(i, ch, t0 + at),
                                     stroke=row_stroke(cc.width))
        flip(self, [Flip(old, new, parts=(row_parts(old), row_parts(new)),
                         lag_ratio=FLIP_LAG)
                    for old, new in zip(self.words, self.clones)], rt,
             extra=[Succession(Wait(t0), AnimationGroup(typing, run_time=total))])
        self.words, self.clones = self.clones, None

    # c : the corner SALET and its CLONE travel into a board's first two rows as
    #     its other rows fade in; everything else shrinks away
    def _setup_to_board(self):
        self.board = get_board()
        self.movers = []
        for mob, r in ((self.guess, 0), (self.corner_clone, 1)):
            target = self.board.rows[r]
            mob.generate_target()
            mob.target.scale(target.width / mob.width).move_to(target)
            for t in _tiles(mob.target):
                t.set_stroke(width=STROKE)
            mob.set_z_index(1)                 # over the rows it crosses (user's call)
            self.movers.append(mob)
        self.leaving = self.rows + self.words

    @subscene
    def to_board(self):
        self._setup_to_board()
        self.play(*[MoveToTarget(m) for m in self.movers],
                  *[shrink_out(m) for m in self.leaving],
                  *[FadeIn(r) for r in self.board.rows[2:]],
                  run_time=1.5)
        self.remove(*self.leaving)
        self.salet_row, self.clone_row = self.movers
        self.rows = self.words = self.groups = self.leaving = self.movers = None
        self.corner_clone = None

    # d : THIRD typed into row 3
    @subscene
    def third(self):
        self.board.type_word(self, 2, THIRD, 0.65, per_letter=key_cues(self))

    # e : the camera pans up to scene 14's number line as it ended
    def _setup_timeline(self):
        self._build_line(OPTIMAL[0], COMPATIBLE[0], dy=GAME_DY, line_dy=LINE_DROP)
        self.optimal_marker(grow=1.0)
        self.compatible_marker(grow=1.0)
        self.opener_marker(round(SLATE["mean"], 2), ["slate"], SLATE["win_rate"],
                           grow=1.0)
        self.add(self.line, self.title, self.subtitle)

    @subscene
    def timeline(self):
        self._setup_timeline()
        self._pan_up(1.5)
        self._clear_below()
        self.board = self.salet_row = self.clone_row = None   # off-frame now

    def _clear_below(self):
        """Everything but the number line off the scene — including the typing's
        wrapper groups, which keep a removed board's tiles on screen (flip.py's
        ghost note). Only while the board's frame is out of view. Everything goes
        and the line comes back, rather than keeping it by identity: after a zoom
        or a marker swap the line is held inside an animation's wrapper group, not
        on the scene itself, so an identity test cleared it too (15u, 2026-10-01)."""
        frame = [self.camera.frame] if self.camera.frame in self.mobjects else []
        self.remove(*self.mobjects)
        self.add(*frame, self.line, self.title, self.subtitle)

    def _opener(self, key, side):
        """A k-word opener's marker: its words, "Then RCA", its win rate."""
        o = AW["openers"][key]
        return self.opener_marker(round(o["mean"], 2), key.split(), o["win_rate"],
                                  side=side)

    def _swap(self, mk, key, run_time):
        o = AW["openers"][key]
        self.replace_marker(mk, key.split(), round(o["mean"], 2), o["win_rate"], run_time)

    def _zoom_to(self, mk):
        """13e's zoom, the leftmost marker at x = -ZOOM_EDGE and `mk` at +ZOOM_EDGE
        (13e used 6; full-size cards need the extra room to clear each other)."""
        lo, hi = min(m.value for m in self.line.markers), mk.value
        s = 2 * ZOOM_EDGE / (hi - lo)                  # screen units per guess
        half = (self.line.x_range[1] - self.line.x_range[0]) / 2 / s
        c = (lo + hi) / 2
        self._zoom_pop(c - half, c + half, mk, 2.0, 0.4, 0.5)

    # f : PARSE CLINT at 3.69, below the line
    @subscene
    def two_words(self):
        self.two = self._opener(TWO, DOWN)
        self._pop_in(self.two, 0.4)

    # g : PARSE CLINT flips to CRANE SPILT, sliding to 3.70
    @subscene
    def crane_spilt(self):
        self._swap(self.two, TWO_B, 1.2)

    # h : zoom out to fit DANCE HORST BLIMP at 4.16, above the line
    @subscene
    def three_words(self):
        self.three = self._opener(THREE, UP)
        self._zoom_to(self.three)

    # i : flips to BLAND COPSE RIGHT, sliding to 4.17
    @subscene
    def bland_copse(self):
        self._swap(self.three, THREE_B, 1.2)

    # j : zoom out to fit CHAMP FLINT RUGBY SOWED at 5.02, above the line (right of
    #     the title, so the tall card has room)
    @subscene
    def four_words(self):
        self.four = self._opener(FOUR, UP)
        self._zoom_to(self.four)

    # k : flips to BUGLE CHAMP DOWNY FIRST (still 5.02)
    @subscene
    def bugle_champ(self):
        self._swap(self.four, FOUR_B, 1.2)

    # l : the camera pans down to an empty board
    def _setup_reveal_board(self):
        self.rows = _stack()
        self.add(*self.rows)

    @subscene
    def reveal_board(self):
        self._setup_reveal_board()
        self._pan_down(1.5)

    # m : BLUNK CIMEX GRYPT VOZHD WAQFS typed
    @subscene
    def five_words(self):
        for r, w in enumerate(BLUNK.split()):
            self.rows[r].type_word(self, 0, w, 0.5, per_letter=key_cues(self))

    def _flip_rows(self, news, run_time, extra=()):
        """Rows r flip to news[r] (a dict), each in place; the new rows replace them."""
        fl = []
        for r, new in news.items():
            old = self.rows[r]
            _at(new, old)
            olds = row_parts(old) if old.letters[0][0] is not None else list(old.tiles[0])
            fl.append(Flip(old, new, parts=(olds, row_parts(new))))
        flip(self, fl, run_time, extra=extra)
        for r, new in news.items():
            self.rows[r] = new

    # n : the five rows flip to the colouring PUREE, PURER, RUPEE and UPPER share
    @subscene
    def puree(self):
        codes = AW["same"]["codes"]
        self._flip_rows({r: get_scored_row(w, c)
                         for r, (w, c) in enumerate(zip(BLUNK.split(), codes))}, 1.6)

    # o : the board moves to the left half
    @subscene
    def board_left(self):
        self.play(VGroup(*self.rows).animate.shift(LEFT * BOARD_SIDE_X), run_time=1.0)

    # p : PUREE PURER RUPEE UPPER on the right half
    def _setup_puree_words(self):
        """An empty one-row board per word, in a column at the board's own size and
        spacing, mirroring the board on the right half."""
        self.same = [WordleBoard(rows=1, cols=5) for _ in AW["same"]["members"]]
        VGroup(*self.same).arrange(DOWN, buff=GAP).move_to(RIGHT * BOARD_SIDE_X)

    @subscene
    def puree_words(self):
        self._setup_puree_words()
        anims, total = [], 0.0
        for i, (b, w) in enumerate(zip(self.same, AW["same"]["members"])):
            a, total = b.type_anim(self, 0, w, 0.65, appear=True,
                                   per_letter=key_cues(self) if i == 0 else None)
            anims.append(a)
        self.play(*anims, run_time=total)

    # q : the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the four words fade out
    @subscene
    def chott(self):
        self._flip_rows({r: get_typed_row(w) for r, w in enumerate(CHOTT.split())}, 1.6,
                        extra=[FadeOut(m) for m in self.same])
        self.remove(*self.same)
        self.same = None

    # r : CHOTT...'s 16 unsolved answers on the right, grouped by shared feedback
    def _setup_unsolved(self):
        groups = [{"size": len(g["members"]), "members": g["members"]}
                  for g in AW["fixed"][CHOTT]["groups"]]
        slots, sc, _, _ = ranked_word_layout(groups, UNSOLVED_LEFT, REGION_HALF_W,
                                             DOT_REGION_TOP, REGION_BOT, heads=0)
        slots = _close_columns(groups, slots, sc, UNSOLVED_LEFT, REGION_HALF_W)
        self.unsolved_words = []
        for w, c in slots.items():
            m = PigpenWord(w, revealed=True).scale(sc).move_to(c)
            for t in m.tiles:
                t.set_stroke(width=word_stroke(m.width))
            self.unsolved_words.append(m)

    @subscene
    def unsolved(self):
        self._setup_unsolved()
        self.play(*[FadeIn(m) for m in self.unsolved_words], run_time=0.8)

    # s : the words slide off to the right; the board back to centre
    @subscene
    def board_back(self):
        self.play(VGroup(*self.unsolved_words).animate.shift(RIGHT * config.frame_width),
                  VGroup(*self.rows).animate.shift(RIGHT * BOARD_SIDE_X),
                  run_time=1.2)
        self.remove(*self.unsolved_words)
        self.unsolved_words = None

    # t : the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK (the sixth row too)
    @subscene
    def six_words(self):
        self._flip_rows({r: get_typed_row(w) for r, w in enumerate(SIX.split())}, 1.6)

    # u : the camera pans up to the number line; the board is swapped for an
    #     empty one while it is off-frame (for x)
    @subscene
    def back_to_line(self):
        self._pan_up(1.5)
        self._clear_below()
        self.rows = _stack()
        self.add(*self.rows)

    # v : every marker but the 2-word one dims
    @subscene
    def two_up(self):
        for m in self.line.markers:
            m.save_state()
        self.play(*[m.animate.set_opacity(0.2) for m in self.line.markers
                    if m is not self.two], run_time=0.6)

    # w : the 2-word marker dims and the 3- and 4-word ones come back (user's call:
    #     the VO now says "a 3- or 4-word opener")
    @subscene
    def four_up(self):
        self.play(self.two.animate.set_opacity(0.2), Restore(self.three),
                  Restore(self.four), run_time=0.6)

    # x : the camera pans down to the empty board
    @subscene
    def empty_board(self):
        self._pan_down(1.5)

    # y : trial 68's starting words, typed at once
    @subscene
    def climb_start(self):
        anims, total = [], 0.0
        for r, w in enumerate(AW["climb"]["start"]):
            a, total = self.rows[r].type_anim(self, 0, w, 0.65,
                                              per_letter=key_cues(self) if r == 0 else None)
            anims.append(a)
        self.play(*anims, run_time=total)

    # z : each accepted move flips the rows it changes, ending on LEDGE PAWNS ROCKY THUMB
    @subscene
    def climb(self):
        for mv in AW["climb"]["moves"]:
            self._flip_rows({r: get_typed_row(w) for r, w in mv["rows"]}, 0.6)

    # za : the two empty rows drop off the bottom; the four words grow, centred
    @subscene
    def finale(self):
        self.play(VGroup(*self.rows[4:]).animate.shift(DOWN * config.frame_height),
                  VGroup(*self.rows[:4]).animate.scale(FINAL_SCALE).move_to(ORIGIN),
                  run_time=1.5)
        self.remove(*self.rows[4:])
        self.rows = self.rows[:4]
