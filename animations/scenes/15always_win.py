"""Scene 15 — multi-word openers, and a strategy that always wins. Navy background.

Scene 14 ends with everything faded out, so a starts on an empty frame. Talking head
THJ follows, so the scene ends with LEDGE PAWNS ROCKY THUMB on screen.

GEOMETRY: the boards live in the frame at the origin; scene 14's number line sits ONE
FRAME ABOVE them (StrategyLine `_build_line(..., dy=GAME_DY)`), so the script's "bring
back the timeline" / "move up to reveal a board" / "go back down to the timeline" are
camera pans (13's convention) and nothing fades.

BEAT MAP — one subscene per Script.md beat, with departures (user's calls): 15a is
SPLIT into a and b (2026-10-07), 15n and 15o are MERGED (2026-10-01), and three beats
not in the Doc are ADDED (g, h, z: 2026-10-07). So RENDERED letters do not match the
Doc's; the Doc's own beat is in brackets, and an added beat says (added):

  a second_words — SALET in the top-left corner and its 148 groups as coloured rows
                   (scene 12's view, no dots: user's call) fade in (15a, VO 1)
  b type_seconds — every optimal second word typed under its row at once
                                                                   (15a, VO 1)
  c clone        — CLONE typed over every second word and under the corner SALET,
                   all at once (user's calls)                      (15b, VO 2)
  d to_board     — the corner SALET (the uncoloured one: user's call) and the
                   CLONE under it travel into rows 1 and 2 of a board in the
                   middle as its other rows fade in around them; everything else
                   shrinks away                                    (15c, VO 3)
  e third        — THIRD typed into row 3                          (15d, VO 3)
  f timeline     — the camera pans up to scene 14's number line as it ended: 3.42 to
                   4.08, the Optimal, Random Compatible Answers and SLATE markers
                                                                   (15e, VO 4)
  g emph_slate   — SLATE's box emphasised: every other marker dims (user's call)
                                                                   (added)
  h de_emph_slate — everything comes back                          (added)
  i two_words    — the PARSE CLINT marker pops out at 3.69, below the line; then
                   CLINT and its definition fade in right of the card (user's call)
                                                                   (15f, VO 5)
  j crane_spilt  — its words flip to CRANE SPILT as it slides to 3.70, the win rate
                   counting, CLINT's definition fading out         (15g, VO 5)
  k three_words  — the line zooms out to fit 4.16, the DANCE HORST BLIMP marker
                   popping out there, above the line; then HORST and its
                   definition fade in left of the card (user's call) (15h, VO 6)
  l bland_copse  — flips to BLAND COPSE RIGHT, sliding to 4.17, HORST's definition
                   fading out                                      (15i, VO 6)
  m four_words   — the line zooms out to fit 5.02, the CHAMP FLINT RUGBY SOWED
                   marker popping out there, above the line        (15j, VO 7)
  n bugle_champ  — flips to BUGLE CHAMP DOWNY FIRST (same 5.02)    (15k, VO 7)
  o reveal_board — the camera pans down to an empty board          (15l, VO 8)
  p five_words   — BLUNK CIMEX GRYPT VOZHD WAQFS typed             (15m, VO 9)
  q puree        — (15n+15o MERGED: user's call) the five rows flip to the colouring
                   PUREE, PURER, RUPEE and UPPER all give as the board moves to the
                   left half                                  (15n+15o, VO 9)
  r puree_words  — PUREE PURER RUPEE UPPER typed at once, a column on the right half
                   (user's call)                                   (15p, VO 9)
  s chott        — the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the four words
                   fade out                                        (15q, VO 10)
  t unsolved     — its 16 unsolved answers typed at once on the right, grouped by
                   the feedback they share                            (15r, VO 10)
  u board_back   — the words slide off to the right; the board back to centre
                                                                   (15s, VO 11)
  v six_words    — the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK (15t, VO 11)
    (VO 12 has no subscene)
  w back_to_line — the camera pans up to the number line           (15u, VO 13)
  x two_up       — every marker but the 2-word one dims            (15v, VO 13)
  y four_up      — the 2-word marker dims, the 3- and 4-word ones return (user's
                   call: the VO now says "a 3- or 4-word opener") (15w, VO 13)
  z de_emph      — every dimmed marker comes back to full (user's call)
                                                                   (added)
  za empty_board — the camera pans down to an empty board          (15x, VO 14)
  zb climb_start — trial 68's starting words typed: QUERY NINNY BALER MASSE
                                                                   (15y, VO 14)
  zc climb       — each of its nine accepted moves flips the rows it changes, ending
                   on LEDGE PAWNS ROCKY THUMB; the counter counts down beside it, the
                   last count growing and turning green as it reaches 0
                                                                   (15z, VO 14)
  zd finale      — the two empty rows drop off the bottom; the four words grow,
                   centred                                         (15za, VO 15)

REUSE MAP — every element, the one source it comes from, and how it enters:
  SALET (a)             assets/pigpen.py `PigpenWord(revealed=True)` at GUESS_SCALE in
                        the corner — scene 12's corner word (assets/second_view.py
                        `corner_spot`, moved out of scene 12 for this scene)
  coloured rows (a)     assets/second_view.py `group_rows` — 12's rows at 06b's
                        dot-view sizes, sorted by size
  a's entrance          plain FadeIn of the word and rows together (13a's: the frame
                        was cleared, 13number_line.py:182)
  second words (b)      12d's typing: `WordleBoard.type_anim` under each row, all in
                        ONE play, key sound on the first only (12efficient_strats.py
                        second_words); words from strategy_data (the optimal trees)
  every word flip       assets/flip.py `Flip` by `row_parts` (12e's word flips)
  boards (d, o-zd)      assets/board.py at the origin, unscaled — 02's and 04's board;
                        from l on, six one-row boards stacked at the board's spacing,
                        so each row can be typed, flipped and moved on its own
  rows leaving (d)      06b's shrink-out (strategy_line `shrink_out`)
  typing                `WordleBoard.type_word` + assets/keys.py `key_cues` (02's);
                        x types four rows in one play, key sound on the first (12d's)
  number line (f-n,w-z) assets/strategy_line.py `StrategyLine` — scene 14's line,
                        title, subtitle and markers, built one frame up
  pans                  StrategyLine `_pan_up` / `_pan_down` (13's pan, silent)
  new markers (i,k,m)   StrategyLine `opener_marker` (13's cards: the words, "Then
                        RCA", the win rate; several words as a `word_stack`, board-
                        tight, SLATE's size: user's calls) popping out with the pop
                        sound (`_pop_in`; with a zoom, `_zoom_pop` as 13c/e)
  zooms (k, m)          13e's rule, the leftmost marker at the left end and the new one
                        at the right, but at +-ZOOM_EDGE (6.5, not 13e's 6) so the
                        full-size cards clear each other — only when a new marker
                        would not fit (user's call)
  marker swaps (j,l,n)  StrategyLine `replace_marker` — 14c's flip-while-sliding with
                        the win rate counting (moved there from scene 14 for this)
  CLINT / HORST notes   the card's own `word_line` + assets/gloss.py `gloss` under it
  (i-l)                 (06d's word-then-definition); FadeIn after the pop, FadeOut
                        during the next beat's flip (the flip replaces the word)
  emphasis (g,h,x-z)    dim the rest to 0.2 (house rule: save_state / Restore)
  o's words             one-row boards typed in ONE play, key sound on the first only
                        (12d's), at the board's size and spacing
  q's words             one-row boards typed in ONE play (12d's), at the size
                        PigpenWord(revealed=True) takes in
                        `ranked_word_layout` (07's groups, filling the region), its
                        rows of groups then re-spread by `_close_columns`
  words in / out        plain FadeIn / FadeOut; s slides them off to the right
  finale (zd)           the rows move and scale as one (no source: the script's own)
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
SALVE, in the bucket FALSE / SALLE / SALVE (SALLE is not an answer); losing it
needs SALLE guessed (worst line FALSE, SALLE, SALVE). The user accepts that
(2026-10-01): nobody guesses SALLE over SALVE. Do not re-flag it. The w-y counter
shows every count minus 1 (UNCOUNTED) for that reason, so it ends at 0.

LAYOUT CHOICES, flagged:
  - b: every CLONE typed at the normal pace (0.65s) in one play; an old letter
    vanishes the moment its replacement lands.
  - c: the travelling rows sit above everything they cross (z-index 1: user's
    call); their borders thicken to the board's STROKE.
  - Every opener card reads "Then RCA" (user's call); the 4.08 card keeps "Random
    Compatible Answers" with its initials bold.
  - Marker sides: 2-word below, 3- and 4-word above (the 4-word card is tall, and
    at the right end nothing is above the line), so no two cards overlap.
  - o: the four words at the board's size, a column centred on the right half,
    mirroring the board.
  - q: the sixteen words grouped (their shared feedback is not drawn), largest group
    first, right of the board; the space between the two columns of groups equals
    the space between their rows (user's call: the layout's last row was squeezed
    and read as one group of four).
  - x: the board's slot order is the climb's slots 2, 0, 1, 3 (user's call: an order
    that ends on LEDGE PAWNS ROCKY THUMB; a blind opening's score ignores order).
  - z: the four rows grow to FINAL_SCALE, centred on the frame.
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
from bpkfigures.style import CrispCounter
from assets.second_view import corner_spot, row_stroke, under, group_rows
from assets.strategy_line import (StrategyLine, GAME_DY, shrink_out,
                                  word_stroke, whole, word_line, MARKER_FS,
                                  OPTIMAL, COMPATIBLE)
from assets.gloss import gloss

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
UNSOLVED_LEFT = -1.1       # q: the grouped words' region starts here
ZOOM_EDGE = 6.5            # h, j: where a zoom puts its end markers (13e: 6)
LINE_DROP = -0.2           # the line sits this much lower than 13/14's and every
MARKER_STEM_15 = 0.3       #   stem is shorter (13: 0.45), so the full-size 3- and
                           #   4-word cards clear the subtitle and the frame edge
COUNT_LABEL = ["Unsolved", "Words"]   # w-y (user's wording)
COUNT_LABEL_FS = 60        # w-y: the label's size (user: bigger than LG's 48)
COUNT_FS = 60               # w-y: the counter's size (user: smaller than 72)
COUNT_LINE_GAP = 0.15      # w-y: between the label's two lines
COUNT_GAP = 0.45           # w-y: between the label and the counter (user: wider)
UNCOUNTED = 1              # w-y: SALVE's one loss is not counted (user's call: it
                           #   needs SALLE guessed), so the counter shows count - 1
COUNT_DONE = LIGHT_GREEN   # w-y: the counter at 0 -- the win-rate scale's green
COUNT_GROW = 1.4           # y: how much the counter grows as it reaches 0
FINAL_SCALE = 1.5          # z: the four rows' growth
# f, h: a word of the opener defined beside its card (user's calls): the word, its
# definition (user's words, broken by hand so no line is much wider than the word),
# and which side of the card it sits on
CLINT = ("clint", ["n. A hard or", "flinty rock"], RIGHT)
HORST = ("horst", ["n. A raised", "block of", "Earth's crust"], LEFT)
NOTE_BUFF = 0.35           # f, h: between the card and the word
NOTE_GLOSS_BUFF = 0.15     # f, h: between the word and its definition (06's GLOSS_BUFF)


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
    """15q (Doc 15r): the layout's group blocks keep their rows, but each row of blocks is
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


def _finish(m, p):
    """The counter `p` (0..1) of the way to done: grown towards COUNT_GROW and
    coloured towards COUNT_DONE, about its own centre."""
    m.scale(1 + (COUNT_GROW - 1) * p)
    m.set_color(interpolate_color(WHITE, COUNT_DONE, p))


def _at_once(t):
    """A rate function that is done the instant it starts: an old letter gone as
    its typed-over replacement lands. 0 at t = 0, since a LaggedStart holds a
    member not yet due at alpha 0 -- the same rule board.TilePop shows by."""
    return 1.0 if t > 0 else 0.0


def _at(new, old):
    """`new` (a one-row word) sized and placed over `old`."""
    return new.scale(old.width / new.width).move_to(old)


class Scene15(StrategyLine, MovingCameraScene, WordleBoardScene):
    """second_words — SALET and its coloured rows fade in
    type_seconds — every optimal second word typed under its row
    clone — every second word flips to CLONE
    to_board — SALET and a CLONE into a board's first two rows; the rest goes
    third — THIRD typed into row 3
    timeline — pan up to scene 14's line
    emph_slate — SLATE's box emphasised
    de_emph_slate — back to normal
    two_words — PARSE CLINT at 3.69; CLINT's definition beside it
    crane_spilt — flips to CRANE SPILT at 3.70
    three_words — zoom; DANCE HORST BLIMP at 4.16; HORST's definition beside it
    bland_copse — flips to BLAND COPSE RIGHT at 4.17
    four_words — zoom; CHAMP FLINT RUGBY SOWED at 5.02
    bugle_champ — flips to BUGLE CHAMP DOWNY FIRST
    reveal_board — pan down to an empty board
    five_words — BLUNK CIMEX GRYPT VOZHD WAQFS typed
    puree — the rows flip to PUREE's colouring as the board moves left
    puree_words — PUREE PURER RUPEE UPPER on the right
    chott — the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the words go
    unsolved — its 16 unsolved answers, grouped, on the right
    board_back — the words off right; the board back to centre
    six_words — the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK
    back_to_line — pan up to the line
    two_up — dim all but the 2-word marker
    four_up — the 4-word marker instead
    de_emph — every dimmed marker back to full
    empty_board — pan down to an empty board
    climb_start — QUERY NINNY BALER MASSE typed
    climb — the nine moves, to LEDGE PAWNS ROCKY THUMB
    finale — the empty rows drop away; the four grow, centred
    """

    def setup_scene(self):
        self.marker_stem = MARKER_STEM_15

    # a : SALET in the corner and its coloured rows fade in
    def _setup_second_words(self):
        corner, left = corner_spot(SALET)
        self.guess = PigpenWord(SALET, revealed=True).scale(GUESS_SCALE).move_to(corner)
        self.groups, self.rows, _, _ = group_rows(DATA, SALET, left)

    @subscene
    def second_words(self):
        self._setup_second_words()
        self.play(FadeIn(self.guess), *[FadeIn(r) for r in self.rows], run_time=1.0)

    # b : every optimal second word typed under its row at once (split from a,
    #     user 2026-10-07)
    def _setup_type_seconds(self):
        sec = SD["second"][SALET]
        self.blanks = []
        for g, row in zip(self.groups, self.rows):
            b = WordleBoard(rows=1, cols=5)
            b.scale(row.width / b.width).move_to(under(row))
            self.blanks.append((b, sec[str(g["code"])]))

    @subscene
    def type_seconds(self):
        self._setup_type_seconds()
        anims, total = [], 0.0
        for i, (b, word) in enumerate(self.blanks):
            a, total = b.type_anim(self, 0, word, 0.65,
                                   per_letter=key_cues(self) if i == 0 else None,
                                   appear=True, stroke=row_stroke(b.width))
            anims.append(a)
        self.play(*anims, run_time=total)
        self.words = [b for b, _ in self.blanks]
        self.blanks = None

    # c : CLONE typed over every second word and under the corner SALET
    def _setup_clone(self):
        self.corner_clone = WordleBoard(rows=1, cols=5)
        self.corner_clone.scale(self.guess.width / self.corner_clone.width)
        self.corner_clone.move_to(under(self.guess))

    @subscene
    def clone(self):
        """CLONE typed OVER every second word (user's call) and under the corner
        SALET, all in one play at the normal pace, key sound on the first only
        (12d's): each old letter goes the moment its new one lands."""
        self._setup_clone()
        cc = self.corner_clone
        anims, total, gone = [], 0.0, []
        a, total = cc.type_anim(self, 0, CLONE, 2.5, per_letter=key_cues(self),
                                appear=True, stroke=row_stroke(cc.width))
        anims.append(a)
        n = len(CLONE)
        for b in self.words:
            olds = list(b.letters[0])
            a, _ = b.type_anim(self, 0, CLONE, 2.5, stroke=row_stroke(b.width))
            anims += [a, LaggedStart(*[FadeOut(l, rate_func=_at_once) for l in olds],
                                     lag_ratio=1 / n)]
            gone.append((b, olds))
        self.play(*anims, run_time=total)
        for b, olds in gone:
            b.remove(*olds)
            self.remove(*olds)

    # d : the corner SALET and its CLONE travel into a board's first two rows as
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
        # the board's other rows travel WITH SALET and CLONE as they fade in (user's
        # call): they start where they would hang under the corner pair -- the same
        # map that takes board row 0 onto SALET -- invisible, and end in place
        self.rest = VGroup(*self.board.rows[2:])
        self.rest.save_state()
        row0 = self.board.rows[0]
        c0 = row0.get_center()
        self.rest.scale(self.guess.width / row0.width, about_point=c0)
        self.rest.shift(self.guess.get_center() - c0).set_opacity(0)

    @subscene
    def to_board(self):
        self._setup_to_board()
        self.add(self.rest)
        self.play(*[MoveToTarget(m) for m in self.movers],
                  *[shrink_out(m) for m in self.leaving],
                  Restore(self.rest),
                  run_time=1.5)
        self.remove(*self.leaving, self.rest)
        self.add(*self.board.rows[2:])
        self.rest = None
        self.salet_row, self.clone_row = self.movers
        self.rows = self.words = self.groups = self.leaving = self.movers = None
        self.corner_clone = None

    # e : THIRD typed into row 3
    @subscene
    def third(self):
        self.board.type_word(self, 2, THIRD, 0.65, per_letter=key_cues(self))

    # f : the camera pans up to scene 14's number line as it ended
    def _setup_timeline(self):
        self._build_line(OPTIMAL[0], COMPATIBLE[0], dy=GAME_DY, line_dy=LINE_DROP)
        self.optimal_marker(grow=1.0)
        self.compatible_marker(grow=1.0)
        self.slate = self.opener_marker(round(SLATE["mean"], 2), ["slate"],
                                        SLATE["win_rate"], grow=1.0)
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

    def _swap(self, mk, key, run_time, follow=False, extra=()):
        """`mk` flips to `key`'s opener; `follow` zooms so it lands at the right
        end (15i: it slides past the edge, so the view pans with it)."""
        o = AW["openers"][key]
        value = round(o["mean"], 2)
        zoom = self._window(value) if follow else None
        self.replace_marker(mk, key.split(), value, o["win_rate"], run_time, zoom=zoom,
                            extra=extra)

    def _window(self, right):
        """13e's zoom window: the leftmost marker at x = -ZOOM_EDGE and the value
        `right` at +ZOOM_EDGE (13e used 6; full-size cards need the extra room)."""
        lo, hi = min(m.value for m in self.line.markers), right
        s = 2 * ZOOM_EDGE / (hi - lo)                  # screen units per guess
        half = (self.line.x_range[1] - self.line.x_range[0]) / 2 / s
        c = (lo + hi) / 2
        return c - half, c + half

    def _zoom_to(self, mk, zoom_rt, pop_rt, lead):
        self._zoom_pop(*self._window(mk.value), mk, zoom_rt, pop_rt, lead)

    def _note(self, note):
        """A word of an opener, as the card's own word row, with its definition
        under it (06d's word-then-definition). Placed by `_place_note`."""
        word, lines, side = note
        row = word_line(word)
        defn = gloss(lines, MARKER_FS)
        defn.next_to(row, DOWN, buff=NOTE_GLOSS_BUFF, aligned_edge=LEFT)
        out = VGroup(row, defn)
        out.side = side
        return out

    def _place_note(self, note, mk):
        """Beside the marker's card, where it has landed."""
        note.next_to(mk.label, note.side, buff=NOTE_BUFF)

    # g : emph SLATE's box: every other marker dims (user 2026-10-07)
    @subscene
    def emph_slate(self):
        self.slate_rest = [m for m in self.line.markers if m is not self.slate]
        for m in self.slate_rest:
            m.save_state()
        self.play(*[m.animate.set_opacity(0.2) for m in self.slate_rest], run_time=0.6)

    # h : de-emph: everything comes back
    @subscene
    def de_emph_slate(self):
        self.play(*[Restore(m) for m in self.slate_rest], run_time=0.6)
        self.slate_rest = None

    # i : PARSE CLINT at 3.69, below the line; once it has popped out, CLINT and
    #     its definition fade in to the right of the card
    def _setup_two_words(self):
        self.two = self._opener(TWO, DOWN)
        self.clint = self._note(CLINT)

    @subscene
    def two_words(self):
        self._setup_two_words()
        self._pop_in(self.two, 0.4)
        self._place_note(self.clint, self.two)          # the card's landed place
        self.play(FadeIn(self.clint), run_time=0.5)

    # j : PARSE CLINT flips to CRANE SPILT, sliding to 3.70, CLINT's definition
    #     fading out as it goes
    @subscene
    def crane_spilt(self):
        self._swap(self.two, TWO_B, 1.2, extra=[FadeOut(self.clint)])
        self.clint = None

    # k : zoom out to fit DANCE HORST BLIMP at 4.16, above the line; once it has
    #     popped out, HORST and its definition fade in to the left of the card
    def _setup_three_words(self):
        self.three = self._opener(THREE, UP)
        self.horst = self._note(HORST)

    @subscene
    def three_words(self):
        self._setup_three_words()
        self._zoom_to(self.three, 1.0, 0.4, 0.3)
        self._place_note(self.horst, self.three)        # after the zoom moved it
        self.play(FadeIn(self.horst), run_time=0.5)

    # l : flips to BLAND COPSE RIGHT, sliding to 4.17, HORST's definition fading
    #     out as it goes
    @subscene
    def bland_copse(self):
        self._swap(self.three, THREE_B, 1.2, follow=True, extra=[FadeOut(self.horst)])
        self.horst = None

    # m : zoom out to fit CHAMP FLINT RUGBY SOWED at 5.02, above the line (right of
    #     the title, so the tall card has room)
    @subscene
    def four_words(self):
        self.four = self._opener(FOUR, UP)
        self._zoom_to(self.four, 1.0, 0.4, 0.3)

    # n : flips to BUGLE CHAMP DOWNY FIRST (still 5.02)
    @subscene
    def bugle_champ(self):
        self._swap(self.four, FOUR_B, 1.2)

    # o : the camera pans down to an empty board
    def _setup_reveal_board(self):
        self.rows = _stack()
        self.add(*self.rows)

    @subscene
    def reveal_board(self):
        self._setup_reveal_board()
        self._pan_down(1.5)

    # p : BLUNK CIMEX GRYPT VOZHD WAQFS typed
    @subscene
    def five_words(self):
        for r, w in enumerate(BLUNK.split()):
            self.rows[r].type_word(self, 0, w, 0.5, per_letter=key_cues(self))

    def _flip_rows(self, news, run_time, extra=(), shift=None):
        """Rows r flip to news[r] (a dict), each in place -- or, with `shift`,
        while travelling by it; the new rows replace them."""
        fl = []
        for r, new in news.items():
            old = self.rows[r]
            _at(new, old)
            if shift is not None:
                new.shift(shift)
            olds = row_parts(old) if old.letters[0][0] is not None else list(old.tiles[0])
            fl.append(Flip(old, new, parts=(olds, row_parts(new)),
                           travel=shift is not None))
        flip(self, fl, run_time, extra=extra)
        for r, new in news.items():
            self.rows[r] = new

    # q : (15n+15o, merged: user's call) the five rows flip to the colouring PUREE,
    #     PURER, RUPEE and UPPER share as the board moves to the left half
    @subscene
    def puree(self):
        codes = AW["same"]["codes"]
        shift = LEFT * BOARD_SIDE_X
        self._flip_rows({r: get_scored_row(w, c)
                         for r, (w, c) in enumerate(zip(BLUNK.split(), codes))}, 1.6,
                        extra=[self.rows[5].animate.shift(shift)], shift=shift)

    # r : PUREE PURER RUPEE UPPER on the right half
    def _setup_puree_words(self):
        """An empty one-row board per word, in a column at the board's own size and
        spacing, mirroring the board on the right half."""
        self.same = [WordleBoard(rows=1, cols=5) for _ in AW["same"]["members"]]
        VGroup(*self.same).arrange(DOWN, buff=GAP).move_to(RIGHT * self._right_mid())

    def _right_mid(self):
        """x halfway between the (left-moved) board and the frame's right edge."""
        return (VGroup(*self.rows).get_right()[0] + config.frame_x_radius) / 2

    @subscene
    def puree_words(self):
        self._setup_puree_words()
        anims, total = [], 0.0
        for i, (b, w) in enumerate(zip(self.same, AW["same"]["members"])):
            a, total = b.type_anim(self, 0, w, 0.65, appear=True,
                                   per_letter=key_cues(self) if i == 0 else None)
            anims.append(a)
        self.play(*anims, run_time=total)

    # s : the rows flip to CHOTT DUMBO FAWNY VERGE SPILL; the four words fade out
    @subscene
    def chott(self):
        self._flip_rows({r: get_typed_row(w) for r, w in enumerate(CHOTT.split())}, 1.6,
                        extra=[FadeOut(m) for m in self.same])
        self.remove(*self.same)
        self.same = None

    # t : CHOTT...'s 16 unsolved answers on the right, grouped by shared feedback
    def _setup_unsolved(self):
        groups = [{"size": len(g["members"]), "members": g["members"]}
                  for g in AW["fixed"][CHOTT]["groups"]]
        slots, sc, _, _ = ranked_word_layout(groups, UNSOLVED_LEFT, REGION_HALF_W,
                                             DOT_REGION_TOP, REGION_BOT, heads=0)
        slots = _close_columns(groups, slots, sc, UNSOLVED_LEFT, REGION_HALF_W)
        width = PigpenWord("salet", revealed=True).scale(sc).width
        self.unsolved_words = []
        for w, c in slots.items():
            b = WordleBoard(rows=1, cols=5)
            b.scale(width / b.width).move_to(c)
            self.unsolved_words.append((b, w))

    @subscene
    def unsolved(self):
        self._setup_unsolved()
        anims, total = [], 0.0
        for i, (b, w) in enumerate(self.unsolved_words):
            a, total = b.type_anim(self, 0, w, 0.65, appear=True,
                                   per_letter=key_cues(self) if i == 0 else None,
                                   stroke=word_stroke(b.width))
            anims.append(a)
        self.play(*anims, run_time=total)
        self.unsolved_words = [b for b, _ in self.unsolved_words]

    # u : the words slide off to the right; the board back to centre
    @subscene
    def board_back(self):
        self.play(VGroup(*self.unsolved_words).animate.shift(RIGHT * config.frame_width),
                  VGroup(*self.rows).animate.shift(RIGHT * BOARD_SIDE_X),
                  run_time=1.2)
        self.remove(*self.unsolved_words)
        self.unsolved_words = None

    # v : the rows flip to CATTY FROND RUMBA SPILL VERGE WHACK (the sixth row too)
    @subscene
    def six_words(self):
        self._flip_rows({r: get_typed_row(w) for r, w in enumerate(SIX.split())}, 1.6)

    # w : the camera pans up to the number line; the board is swapped for an
    #     empty one while it is off-frame (for x)
    @subscene
    def back_to_line(self):
        self._pan_up(1.5)
        self._clear_below()
        self.rows = _stack()
        VGroup(*self.rows).shift(LEFT * BOARD_SIDE_X)      # w-y: the board on the left
        self.add(*self.rows)

    # x : every marker but the 2-word one dims
    @subscene
    def two_up(self):
        for m in self.line.markers:
            m.save_state()
        self.play(*[m.animate.set_opacity(0.2) for m in self.line.markers
                    if m is not self.two], run_time=0.6)

    # y : the 2-word marker dims and the 3- and 4-word ones come back (user's call:
    #     the VO now says "a 3- or 4-word opener")
    @subscene
    def four_up(self):
        self.play(self.two.animate.set_opacity(0.2), Restore(self.three),
                  Restore(self.four), run_time=0.6)

    # z : de-emph: every dimmed marker comes back (user 2026-10-07)
    @subscene
    def de_emph(self):
        self.play(*[Restore(m) for m in self.line.markers
                    if m is not self.three and m is not self.four], run_time=0.6)

    # za : the camera pans down to the empty board
    @subscene
    def empty_board(self):
        self._pan_down(1.5)

    # zb : trial 68's starting words, typed at once; the unsolved counter beside
    #     the board fades in with them
    def _setup_climb_start(self):
        cx = self._right_mid()
        self.count_label = VGroup(*[crisp_text(t, color=WHITE, font_size=COUNT_LABEL_FS)
                                    for t in COUNT_LABEL]).arrange(DOWN, buff=COUNT_LINE_GAP)
        start = AW["climb"]["start_unsolved"] - UNCOUNTED
        self.counter = CrispCounter("", ValueTracker(start), left=0.0, y=0.0,
                                    font_size=COUNT_FS, color=WHITE,
                                    fmt=whole)
        block = VGroup(self.count_label, self.counter.mob).arrange(DOWN, buff=COUNT_GAP)
        block.move_to([cx, 0, 0])
        self.counter.left = self.counter.mob.get_left()[0]
        self.counter.y = self.counter.mob.get_center()[1]
        self.count_x = cx

    @subscene
    def climb_start(self):
        self._setup_climb_start()
        anims, total = [], 0.0
        for r, w in enumerate(AW["climb"]["start"]):
            a, total = self.rows[r].type_anim(self, 0, w, 0.65,
                                              per_letter=key_cues(self) if r == 0 else None)
            anims.append(a)
        self.play(*anims, FadeIn(self.count_label), FadeIn(self.counter.mob),
                  run_time=total)

    # zc : each accepted move flips the rows it changes while the counter counts
    #     down to its unsolved words, ending on LEDGE PAWNS ROCKY THUMB at 0, green
    @subscene
    def climb(self):
        c, cx = self.counter, self.count_x
        moves = AW["climb"]["moves"]
        for k, mv in enumerate(moves):
            v0, v1 = c.tracker.get_value(), mv["unsolved"] - UNCOUNTED
            count = c.count_anim(v1, flash="none")
            c.mob.add_updater(lambda m: m.set_x(cx))      # centred, after the rebuild
            if k == len(moves) - 1:
                # the last count grows and turns green as it reaches 0, in the
                # same play (user's call), following the count's own progress
                tr = c.tracker
                c.mob.add_updater(lambda m: _finish(m, (v0 - tr.get_value()) / (v0 - v1)))
            self._flip_rows({r: get_typed_row(w) for r, w in mv["rows"]}, 1.0,
                            extra=[count])
            c.end_count()
            if k < len(moves) - 1:
                self.wait(1.1)                 # each number holds before the next move

    # zd : the counter fades and the two empty rows drop off the bottom; the four
    #      words grow, centred
    @subscene
    def finale(self):
        self.play(VGroup(*self.rows[4:]).animate.shift(DOWN * config.frame_height),
                  FadeOut(self.count_label), FadeOut(self.counter.mob),
                  VGroup(*self.rows[:4]).animate.scale(FINAL_SCALE).move_to(ORIGIN),
                  run_time=1.5)
        self.remove(*self.rows[4:], self.count_label, self.counter.mob)
        self.rows = self.rows[:4]
        self.count_label = self.counter = None
