"""Scene 07 — dynamic programming: an opener's groups, then the subgroups each
later guess makes of one of them. Navy background.

Talking head THE sits between 06 and here and covers the cut, so the empty board is
up from frame 0 (setup_scene). The script's 07 is not finished yet (it stops at 07g), so no beat clears
the frame at the end.

THE BOARD starts centred at full size. Once FIRST is typed (c) it shrinks into the
top-left corner so its first row is exactly scene 06's corner word — same place,
same size — while every other row fades out; the groups then use 06's region right
of it. A later guess's tiles appear from nowhere as its letters are typed.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_board   — the empty board, centred, held (a still beat)       (07a, VO 1)
  b type_first   — FIRST typed into row 0                             (07b, VO 1)
  c first_groups — the board shrinks into the corner, its FIRST row where
                   06's corner word was, the other rows fading out; FIRST's
                   groups come in from beyond the frame, in the style of
                   the end of scene 06: every group, sorted by size, dots
                   under a scored FIRST row                            (07c, VO 1)
  d first_narrow — the board's FIRST flips to ----Y (yellow T); then ONE
                   play: every other group leaves by its nearest edge, the
                   yellow-T FIRST row moves to the top middle of the column, and its
                   dots travel there, turning into the words          (07d, VO 2)
  e after_split  — AFTER typed into row 1, its tiles appearing as typed;
                   the words regroup into AFTER's subgroups, the FIRST row
                   flying to the top of each with a scored AFTER row
                   fading in under it as it goes                       (07e, VO 2)
  f after_narrow — the board's AFTER flips to Y-Y-- (A, T yellow); then ONE
                   play: every other subgroup leaves by its nearest edge,
                   that one's FIRST/AFTER pair moves to the top middle and its
                   words regrow to fill the column                    (07f, VO 2)
  g third_split  — THIRD typed into row 2; the same split as e, each
                   subgroup under FIRST, AFTER and a scored THIRD      (07g, VO 2)
  h rewind       — quickly back to c's end state, d-g reversed in one play (07h, VO 3)
  i branches     — lines from the left FIRST's R to every coloured FIRST's R,
                   all drawn at once; then every group but the all-green
                   one goes up off the top at once, the lines stretching
                   with them, still anchored to FIRST             (07i, VO 4)
  j all_green    — the left FIRST to the top centre, the all-green FIRST to
                   the bottom centre, its dot growing into the word    (07j, VO 4)
  k green_centre — the top FIRST off the top; the green FIRST (its word
                   with it) to the centre, its line running out the top (07k, VO 4)
  l green_win    — the bottom word fades as the green FIRST does the winning
                   row's bounce (02's win), in place of a glow (user's call) (07l, VO 4)
  m case_swap    — the green case off to the left, FRESH's case in from the
                   right: FIRST scored G-YG-, its line out the top, FRESH
                   under it (FRESH is the user's pick)                 (07m, VO 5)
  n type_fresh   — FRESH typed below that FIRST, tiles appearing as typed (07n, VO 5)
  o score_fresh  — FRESH scored, all green                            (07o, VO 5)
  p fresh_win    — the bottom word fades as FRESH does the win bounce (07p, VO 5)
  q pair_swap    — FRESH's case off left, the two-word case in from the right:
                   FIRST scored --GGG, its line, BURST and WORST under it
                   (the user's pick; BURST is guessed first)           (07q, VO 6)
  r type_burst   — BURST typed below FIRST                            (07r, VO 6)
  s branch_score — ONE play for the script's s, t and u (user's call): the
                   case rises to the top as two copies branch off, left
                   and right, a line from BURST's R to each; each BURST
                   flips to its scoring on the way (all green left, --GGG
                   right); BURST and WORST glide under their cases (07s-u, VO 6)
  t left_win     — the left case's winning bounce as BURST fades       (07v, VO 6)
  u right_branch — the right case branches down again, the black WORST
                   coming down with it; WORST typed, scored all green,
                   winning bounce as the black WORST fades             (07w, VO 6)

  NB from s on the LETTERS run behind the script's: three script beats (s, t, u)
  are one subscene, so the script's v is subscene t and its w is u.

REUSE MAP — every element and the one source it comes from:
  board, typing, reveal   assets/board.py `get_board`, `type_word` (its
                          `appear=True` for rows not on screen), `reveal` (02)
  keystroke sfx           assets/keys.py `key_cues` (02, 97)
  corner position         06's corner word: GUESS_SCALE, CORNER_BUFF from the edges
  sorted dot groups (c)   assets/groups.py `ranked_layout` + `scored_row`, dots
                          white, row stroke scaled — exactly 06b-f's end state
  entrance (c)            assets/groups.py `enter_from_beyond` — 06b's radial slide-in
  exits (d, f)            assets/groups.py `edge_out` — 06's switches
  word groups (d-g)       assets/groups.py `ranked_word_layout` — 04's word
                          pitches and header proportion, packed as 06 packs dots
  regroup (e, g)          04i's word move; the new scored rows fade in DURING
                          it, travelling with the stack (user's call)
  answer words            assets/pigpen.py `PigpenWord(revealed=True)`
  colours                 BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups, subgroups       assets/lists_data.py -> lists_cache.json `full["first"]`,
                          `sub["first:0:after"]`, `sub["first:0:after:0:third"]`,
                          from math/wordle.py `pattern`
No on-screen text beyond the words: column 2 names none. The spoken numbers (1,
2, 2.5 guesses) are not shown.

LAYOUT CHOICES, flagged:
  - FIRST, AFTER and THIRD are read as the literal words the script capitalises.
  - The groups kept are the user's call, not the script's all gray: FIRST's yellow
    T, then AFTER's largest subgroup (see KEEP).
  - "The middle of the big right column" is the TOP middle of the region right of
    the board, the words gridded below the rows.
  - Every group of words sits under the stack of guesses that made it (user's
    call): the rows above a subgroup are FIRST, AFTER … each scored as that group
    scored them. A split sends a copy of the stack to every subgroup.
  - The grid's shape is whichever makes the words largest (user's call).
  - 07f's "turn dots to words" has no dots to act on — 07e left words — so the
    words simply regrow into the bigger grid.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board, WordleBoard, STROKE, TILE, GAP
from assets.pigpen import PigpenWord
from assets.keys import key_cues
from assets.flip import Flip, flip, row_parts
from assets.groups import (ranked_layout, ranked_word_layout, scored_row, HEADER_W,
                           GUESS_SCALE, GUESS_Y, HEAD_ROW_GAP, row_aspect, enter_from_beyond,
                           edge_out)
from assets import lists_data

DATA = lists_data.load()
FIRST, AFTER, THIRD = "first", "after", "third"   # the script's own words
# the group each guess narrows to (pattern codes, position 0 most significant) —
# the user's calls, 2026-09-29, in place of the script's all gray: FIRST's yellow T
# (----Y), then AFTER's largest subgroup there, A and T yellow (Y-Y--), since AFTER
# can never come back all gray once T is known
KEEP = {FIRST: 1, AFTER: 90}
SPLITS = {AFTER: DATA["sub"][f"{FIRST}:{KEEP[FIRST]}:{AFTER}"],
          THIRD: DATA["sub"][f"{FIRST}:{KEEP[FIRST]}:{AFTER}:{KEEP[AFTER]}:{THIRD}"]}

DOT_COLOR = WHITE                  # 06's dots
CORNER_BUFF = 0.3                  # 06's corner word's gap to the frame's edges
CORNER_MARGIN = 0.35               # 06's clear space right of the corner word
ALL_GREEN = 242                    # pattern code of the all-green reply (FIRST is an answer)
LINE_W = 1.5                       # branch lines (hangman 18's tree edges: white, behind)
OFF_CLEAR = 0.3                    # how far past the top edge things leaving go
K_FLY = 3.0                        # k: how many frame heights FIRST shoots up
SINGLE = "fresh"                   # m-p: the one-word group shown (user's pick of
SINGLE_CODE = 177                  #   FIRST's 25) and FIRST's score against it, G-YG-
CASE_WORD_Y = -2.0                 # m: that case's word, below the row typed in n
BOUNCE_H = 0.35                    # board.bounce's default height, for a full-size tile
SWAP_DIST = 16.0                   # m, q: how far the cases travel (a frame width)
PAIR = ("burst", "worst")          # q-w: the two-word group (user's pick of FIRST's 18)
PAIR_CODE = 26                     #   FIRST's score against both, --GGG; BURST is
CROSS = DATA["cross"]["burst:worst"]   # guessed first; its score against WORST
TREE_Y = 2.6                       # s: the pair case's FIRST row once it rises
CHILD_DY = 2.2                     # s, w: a branch's drop, FIRST row to FIRST row
CHILD_DX = 3.5                     # s: the two branches' distance from the centre
PAIR_WORD_DX = 1.3                 # q: the two words, side by side at CASE_WORD_Y
WORD_GAP = 0.25                    # u, w: a word's gap under the case it moves to
GREEN_Y = -2.3                     # j: the all-green FIRST row, bottom centre
WORD_Y = -3.4                      # j: its one word, under it
WIN_SCALE = 0.8                    # that word's size (1 = scene 04's list size)


def _r(row):
    """The centre of `row`'s R tile — the middle tile — where every branch line ends.
    Takes a scored row (board.get_scored_row) or the left FIRST (its five tiles first)."""
    tiles = row.tiles[0] if hasattr(row, "tiles") else row
    return tiles[2].get_center()


def _line(a, b):
    """A branch line from `a` to `b`: white, thin, behind the tiles (hangman 18's edges)."""
    return Line(a, b, color=WHITE, stroke_width=LINE_W).set_z_index(-1)


def _jump(row):
    """The win bounce's height for `row`: the board's default, scaled with the tiles,
    so a small row does not jump over the row above it."""
    return BOUNCE_H * row.tiles[0][0].height / TILE


def _corner():
    """06's corner word: its centre and width (GUESS_SCALE, CORNER_BUFF in)."""
    w = PigpenWord(FIRST, revealed=True).scale(GUESS_SCALE)
    return np.array([-config.frame_x_radius + CORNER_BUFF + w.width / 2,
                     config.frame_y_radius - CORNER_BUFF - w.height / 2, 0.0]), w.width


class Scene07(WordleBoardScene):
    """BEAT MAP
    show_board — the empty board, centred, held
    type_first — FIRST typed
    first_groups — board to the corner, other rows out; FIRST's groups in
    first_narrow — FIRST flips to yellow T; only that group stays, as words
    after_split — AFTER typed; the words split into AFTER's subgroups
    after_narrow — AFTER flips to A, T yellow; only that subgroup stays
    third_split — THIRD typed; the words split into THIRD's subgroups
    rewind — back to FIRST and its groups
    branches — every line at once, then every group but the all-green up
    all_green — FIRST top centre, the all-green FIRST and its word bottom centre
    green_centre — top FIRST off; green FIRST and word to the centre
    green_win — the word fades; the green FIRST bounces
    case_swap — green case out left, FRESH's case in from the right
    type_fresh — FRESH typed under FIRST
    score_fresh — FRESH scored all green
    fresh_win — the word fades; FRESH bounces
    pair_swap — FRESH's case out left, the BURST/WORST case in from the right
    type_burst — BURST typed under FIRST
    branch_score — rise, branch, score both BURSTs, words under, all at once
    left_win — the left case bounces
    right_branch — the right case branches down: WORST typed, scored, bounces
    """

    def setup_scene(self):
        self.board = get_board()
        self.add(self.board)

    # a : the empty board, centred, held — its VO plays over the framework's holds
    @subscene
    def show_board(self):
        pass

    # b : FIRST typed into row 0
    @subscene
    def type_first(self):
        self.board.type_word(self, 0, FIRST, 0.65, per_letter=key_cues(self))

    def _setup_first_groups(self):
        # the board's move: scale about its centre by k, then shift by v, so its
        # first row lands on 06's corner word
        corner, w = _corner()
        b = self.board
        self.k = w / b.rows[0].width
        self.pivot = b.get_center()
        self.v = corner - (self.pivot + self.k * (b.rows[0].get_center() - self.pivot))
        # ONE target for the whole board, its other rows transparent: animating the
        # rows through wrapper groups, then removing the wrappers, took FIRST's
        # letters off the screen with them
        b.generate_target()
        b.target.scale(self.k, about_point=self.pivot).shift(self.v)
        for row in b.target.rows[1:]:
            row.set_opacity(0)
        self.col_left = corner[0] + w / 2 + CORNER_MARGIN
        self.dots, self.units = self._first_groups()
        # every group starts beyond the frame, out along the ray through its spot
        self.incoming = []
        for row, members in self.units.values():
            grp = VGroup(row, *[self.dots[m] for m in members])
            self.incoming.append((grp, enter_from_beyond(grp)))

    def _first_groups(self):
        """c's end state, built: every answer a dot, every group of FIRST a unit
        (scored row, members) keyed by code, laid out as 06 ends. Also h's target."""
        groups, spots, rows, widths, r = ranked_layout(DATA, FIRST, left=self.col_left)
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        dots = {wd: Dot(point=c, radius=r, color=DOT_COLOR) for wd, c in spots.items()}
        units = {g["code"]: (scored_row(FIRST, g["code"], wd, c,
                                        stroke=STROKE * min(1.0, wd / HEADER_W)),
                             g["members"])
                 for g, c, wd in zip(groups, rows, widths)}
        return dots, units

    # c : the board shrinks into the corner, the other rows fading out, as FIRST's
    #     groups come in, sorted by size — the end of scene 06's style
    @subscene
    def first_groups(self):
        self._setup_first_groups()
        self.play(MoveToTarget(self.board),
                  *[grp.animate.move_to(c) for grp, c in self.incoming], run_time=2.0)
        # unwrap the slide-in groups, so every row and dot is top-level
        for grp, _ in self.incoming:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.incoming = None

    # ── narrowing to one group (d, f) ─────────────────────────────────────────
    def _setup_focus(self, guesses, stack, members, leaving, dots=None):
        """The KEEP group alone at the top of the column: `stack` (its rows, on
        screen) turns into new rows for `guesses`, as scored, at the new size; its
        `members` go to a single block; `leaving` (mobjects) goes off the nearest
        edge. With `dots`, the words are new, and grow out of the dots on the way."""
        group = {"size": len(members), "members": members}
        slots, s, hds, hw = ranked_word_layout([group], self.col_left, heads=len(guesses))
        self.f_stack = [scored_row(g, KEEP[g], hw, c) for g, c in zip(guesses, hds[0])]
        self.f_old, self.f_leaving, self.f_dots = stack, leaving, dots
        if dots is None:
            self.f_moves = [m.animate.scale(s / self.w_scale).move_to(slots[wd])
                            for wd, m in self.words.items()]
        else:
            self.words = {}
            for wd, c in slots.items():
                m = PigpenWord(wd, revealed=True).scale(s).move_to(c)
                m.generate_target()                   # the word as it will end
                d = dots[wd]
                m.scale(d.width / m.width).move_to(d).set_opacity(0)
                self.words[wd] = m
            self.f_moves = [*[MoveToTarget(m) for m in self.words.values()],
                            *[d.animate.move_to(slots[wd]).set_opacity(0)
                              for wd, d in dots.items()]]
        self.w_scale = s

    def _focus(self, run_time):
        """ONE play: the rest leaves, the stack moves and grows, the words go (or grow
        out of their dots) to the single block."""
        if self.f_dots is not None:
            self.add(*self.words.values())
        self.play(*[m.animate.move_to(edge_out(m)) for m in self.f_leaving],
                  *[Transform(o, n) for o, n in zip(self.f_old, self.f_stack)],
                  *self.f_moves,
                  run_time=run_time)
        self.remove(*self.f_leaving, *self.f_old, *(self.f_dots or {}).values())
        self.add(*self.f_stack)
        self.stack = self.f_stack
        self.f_stack = self.f_old = self.f_leaving = self.f_dots = self.f_moves = None

    def _setup_first_narrow(self):
        row, members = self.units.pop(KEEP[FIRST])
        leaving = [VGroup(r, *[self.dots[m] for m in ms]) for r, ms in self.units.values()]
        self.stack_words = [FIRST]              # the guesses over the words, top first
        self._setup_focus(self.stack_words, [row], members, leaving,
                          dots={m: self.dots[m] for m in members})
        self.units = self.dots = None

    # d : FIRST flips to yellow T on the board; then in ONE play every other group
    #     leaves, the yellow-T FIRST row moves to the top middle of the column, and
    #     its dots travel there turning into the words
    @subscene
    def first_narrow(self):
        self._setup_first_narrow()
        self.board.reveal(self, 0, KEEP[FIRST], 1.6)
        self._focus(2.0)

    # ── splitting by the next guess (e, g) ────────────────────────────────────
    def _setup_split(self, guess):
        """The words regrouped by `guess`: every subgroup under a copy of the stack
        (the stack itself goes to the first) and a new scored `guess` row, which
        starts invisible one row under the stack, at its size, and travels with it."""
        sub = SPLITS[guess]
        assert sum(g["size"] for g in sub) == len(self.words)
        n = len(self.stack) + 1
        slots, s, hds, hw = ranked_word_layout(sub, self.col_left, heads=n)
        assert set(slots) == set(self.words)
        self.s_slots, self.s_f = slots, s / self.w_scale
        self.w_scale = s
        self.s_stacks = [[scored_row(self.stack_words[k], KEEP[self.stack_words[k]], hw, c)
                          for k, c in enumerate(h[:-1])] for h in hds]
        self.s_new = [scored_row(guess, g["code"], hw, h[-1]) for g, h in zip(sub, hds)]
        ow = self.stack[-1].width                         # the stack's row width now
        start = self.stack[-1].get_center() + \
            DOWN * ow * row_aspect() * (1 + HEAD_ROW_GAP)
        for r in self.s_new:
            r.generate_target()
            r.scale(ow / r.width).move_to(start).set_opacity(0)
        self.blocks = [(g, st, nw) for g, st, nw in zip(sub, self.s_stacks, self.s_new)]

    def _split(self, run_time):
        """ONE play: words to their subgroups, the stack to the first and copies to
        the rest, and each new row fading in as it travels with its stack."""
        first, rest = self.s_stacks[0], self.s_stacks[1:]
        self.add(*self.s_new)
        self.play(*[m.animate.scale(self.s_f).move_to(self.s_slots[wd])
                    for wd, m in self.words.items()],
                  *[Transform(o, n) for o, n in zip(self.stack, first)],
                  *[TransformFromCopy(o, n) for st in rest for o, n in zip(self.stack, st)],
                  *[MoveToTarget(r) for r in self.s_new],
                  run_time=run_time)
        self.remove(*self.stack)
        self.add(*first)
        self.stack = self.s_stacks = self.s_new = self.s_slots = None

    # e : AFTER typed into row 1, its tiles appearing as typed; the words regroup
    #     into AFTER's subgroups, FIRST over each, a scored AFTER fading in under it
    @subscene
    def after_split(self):
        self._setup_split(AFTER)
        self.board.type_word(self, 1, AFTER, 0.65, per_letter=key_cues(self), appear=True)
        self._split(2.0)

    def _setup_after_narrow(self):
        (g, stack, row), rest = self.blocks[0], self.blocks[1:]
        assert g["code"] == KEEP[AFTER]
        leaving = [VGroup(*st, nw, *[self.words.pop(m) for m in gg["members"]])
                   for gg, st, nw in rest]
        self.stack_words = [FIRST, AFTER]
        self._setup_focus(self.stack_words, [*stack, row], g["members"], leaving)
        self.blocks = None

    # f : AFTER flips to A, T yellow on the board; then in ONE play every other
    #     subgroup leaves, that one's FIRST/AFTER pair moves to the top middle, and its words
    #     regrow to fill the column
    @subscene
    def after_narrow(self):
        self._setup_after_narrow()
        self.board.reveal(self, 1, KEEP[AFTER], 1.6)
        self._focus(2.0)

    # g : THIRD typed into row 2, its tiles appearing as typed; the words regroup
    #     into THIRD's subgroups, FIRST and AFTER over each, a scored THIRD fading in
    @subscene
    def third_split(self):
        self._setup_split(THIRD)
        self.board.type_word(self, 2, THIRD, 0.65, per_letter=key_cues(self), appear=True)
        self._split(2.0)

    # ── back to FIRST's groups, and FIRST's own branch (h-l) ──────────────────
    def _setup_rewind(self):
        """h's target is c's end state, rebuilt. What is on screen goes back into
        it: the kept block's first FIRST row turns into the yellow-T row, every other
        stacked row folds into that row and fades; the words shrink into their dots;
        everything that left comes back from beyond its nearest edge; the board's
        later rows fade, and FIRST flips back to typed."""
        self.dots, self.units = self._first_groups()
        target = self.units[KEEP[FIRST]][0]
        heads = [r for _, st, nw in self.blocks for r in (*st, nw)]
        first_row = heads.pop(0)
        self.r_anims = [Transform(first_row, target)]
        self.r_gone = [first_row, *heads, *self.words.values()]
        self.r_swap = (first_row, target)
        k = target.width
        self.r_anims += [h.animate.scale(k / h.width).move_to(target).set_opacity(0)
                         for h in heads]
        # the words on screen shrink into their own dots, which grow out of them
        for wd, m in self.words.items():
            d = self.dots[wd]
            d.generate_target()
            d.move_to(m).set_opacity(0)
            self.r_anims += [m.animate.scale(d.width / m.width).move_to(d.target)
                             .set_opacity(0), MoveToTarget(d)]
        # everything else comes back from beyond its nearest edge, as it left: the
        # other groups whole (d), the rest of the kept group by AFTER subgroup (f)
        back = [VGroup(row, *[self.dots[m] for m in ms])
                for c, (row, ms) in self.units.items() if c != KEEP[FIRST]]
        back += [VGroup(*[self.dots[m] for m in g["members"]])
                 for g in SPLITS[AFTER] if g["code"] != KEEP[AFTER]]
        for grp in back:
            home = grp.get_center()
            grp.move_to(edge_out(grp))
            self.r_anims.append(grp.animate.move_to(home))
        self.r_back = back
        # the board: AFTER and THIRD fade, FIRST turns back over
        b = self.board
        later = [m for r in (1, 2) for m in (*b.tiles[r], *b.letters[r])]
        self.r_anims += [m.animate.set_opacity(0) for m in later] + [b.unscore(0)]
        self.r_later = later
        self.blocks = self.words = None

    # h : quickly back to FIRST and its groups — the reverse of d-g in one play
    @subscene
    def rewind(self):
        self._setup_rewind()
        self.play(*self.r_anims, run_time=1.5)
        first_row, target = self.r_swap
        self.remove(*self.r_gone, *self.r_later, *self.r_back)
        self.add(target, *self.dots.values(), *[row for row, _ in self.units.values()])
        # FIRST on the left is one row from here on; the rest of the board is done
        b = self.board
        self.left = VGroup(*b.tiles[0], *b.letters[0])
        self.remove(b)
        self.add(self.left)
        self.r_anims = self.r_gone = self.r_swap = self.r_back = self.r_later = None
        self.board = None

    def _setup_branches(self):
        """A line from the left FIRST to every coloured FIRST, all drawn at once;
        then every group but the all-green one goes off the top at once (user's
        call). Every line runs R TO R — the centre of the left FIRST's R tile to the
        centre of the row's (user's call), behind the tiles — and STAYS ANCHORED: a
        leaving group's line stretches up off the frame with it, and every line
        follows FIRST from then on."""
        Y = config.frame_y_radius
        start = _r(self.left)
        self.lines = {c: _line(start, _r(row)) for c, (row, _) in self.units.items()}
        self.up = []
        for c, (row, ms) in self.units.items():
            if c == ALL_GREEN:
                continue
            grp = VGroup(row, *[self.dots[m] for m in ms])
            self.up.append((grp, UP * (Y + OFF_CLEAR - grp.get_bottom()[1]), self.lines[c]))
        self.units = {ALL_GREEN: self.units[ALL_GREEN]}
        # the lines to groups that have left: off the frame, still anchored to FIRST
        self.gone = [l for c, l in self.lines.items() if c != ALL_GREEN]
        self.lines = {ALL_GREEN: self.lines[ALL_GREEN]}

    # i : every line drawn at once; then everything but the all-green group goes up
    #     off the top at once, the lines staying anchored to FIRST
    @subscene
    def branches(self):
        self._setup_branches()
        self.play(*[Create(l) for l in self.gone], Create(self.lines[ALL_GREEN]),
                  run_time=1.0)
        self.play(*[grp.animate.shift(v) for grp, v, _ in self.up],
                  *[l.animate.put_start_and_end_on(l.get_start(), l.get_end() + v)
                    for _, v, l in self.up],
                  run_time=1.2)
        self.remove(*[grp for grp, _, _ in self.up])
        self.up = None

    def _setup_all_green(self):
        self.g_row, members = self.units.pop(ALL_GREEN)
        (win,) = members
        self.left.generate_target()
        self.left.target.move_to([0, GUESS_Y, 0])
        self.g_row.generate_target()
        self.g_row.target.scale(self.left.width / self.g_row.width).move_to([0, GREEN_Y, 0])
        for t in self.g_row.target.tiles[0]:
            t.set_stroke(width=STROKE)
        # the all-green group's one dot becomes its word, growing out of the dot
        self.g_dot = self.dots[win]
        self.g_word = PigpenWord(win, revealed=True).scale(WIN_SCALE) \
            .move_to([0, WORD_Y, 0])
        self.g_word.generate_target()
        self.g_word.scale(self.g_dot.width / self.g_word.width).move_to(self.g_dot) \
            .set_opacity(0)
        self.g_line = self.lines.pop(ALL_GREEN)
        # every line keeps R to R: the lines to the groups that left keep their far
        # ends and follow FIRST's R; the green one follows both R's
        self.g_start = _r(self.left.target)
        self.g_line_new = _line(self.g_start, _r(self.g_row.target))
        self.units = self.dots = self.lines = None

    # j : the left FIRST to the top centre, the all-green FIRST to the bottom centre,
    #     its dot turning into the word (the other groups left during i)
    @subscene
    def all_green(self):
        self._setup_all_green()
        self.add(self.g_word)
        self.play(MoveToTarget(self.left), MoveToTarget(self.g_row),
                  MoveToTarget(self.g_word),
                  self.g_dot.animate.move_to(self.g_word.target).set_opacity(0),
                  Transform(self.g_line, self.g_line_new),
                  *[l.animate.put_start_and_end_on(self.g_start, l.get_end())
                    for l in self.gone],
                  run_time=2.0)
        self.remove(self.g_dot)
        self.g_dot = self.g_line_new = self.g_start = None

    def _setup_green_centre(self):
        Y = config.frame_y_radius
        # FIRST shoots off the top, far past it (user's call): K_FLY frame heights up,
        # accelerating, its lines going with it
        self.k_up = UP * (K_FLY * 2 * Y)
        # the green FIRST to the centre, its word under it moving with it
        self.k_shift = ORIGIN - self.g_row.get_center()
        # the connecting line's two ends each ride their own R, at their own pace
        self.k_ends = (_r(self.left), _r(self.g_row))

    def _connect(self, alpha):
        """k's connecting line at `alpha`: its top end on the top FIRST's R (rush_into,
        as that FIRST moves), its bottom end on the green R (smooth)."""
        top, bot = self.k_ends
        self.g_line.put_start_and_end_on(top + self.k_up * rush_into(alpha),
                                         bot + self.k_shift * smooth(alpha))

    # k : the original FIRST off the top; the green FIRST to the centre with its word
    #     under it, the line from it running out of the top after the old FIRST
    @subscene
    def green_centre(self):
        self._setup_green_centre()
        self.play(self.left.animate(rate_func=rush_into).shift(self.k_up),
                  *[l.animate(rate_func=rush_into).shift(self.k_up) for l in self.gone],
                  self.g_row.animate.shift(self.k_shift),
                  self.g_word.animate.shift(self.k_shift),
                  UpdateFromAlphaFunc(self.g_line, lambda m, a: self._connect(a),
                                      rate_func=linear),
                  run_time=1.5)
        self.remove(self.left, *self.gone)
        self.left = self.gone = self.k_ends = self.k_up = self.k_shift = None

    # l : the FIRST at the bottom vanishes AS the green FIRST gets the winning row's
    #     bounce (02's and 97's emphasis for a win, in place of the script's glow —
    #     user's call to swap)
    @subscene
    def green_win(self):
        self.play(FadeOut(self.g_word),
                  self.g_row.bounce_anim(0, height=_jump(self.g_row)), run_time=1.0)
        self.remove(self.g_word)
        self.g_word = None

    # ── a one-word group: guess the word and finish in two (m-p) ──────────────
    def _setup_case_swap(self):
        """FRESH's case, built at the centre as the green case stands now: FIRST
        scored as FRESH scores it, its line out of the top, FRESH under it. It comes
        in from the right as the green case leaves left."""
        X, Y = config.frame_x_radius, config.frame_y_radius
        self.case = scored_row(FIRST, SINGLE_CODE, self.g_row.width, ORIGIN)
        self.case_line = _line([0, Y + OFF_CLEAR, 0], _r(self.case))
        self.case_word = PigpenWord(SINGLE, revealed=True).scale(WIN_SCALE) \
            .move_to([0, CASE_WORD_Y, 0])
        self.m_away = LEFT * SWAP_DIST
        self.m_in = VGroup(self.case, self.case_line, self.case_word).shift(RIGHT * SWAP_DIST)

    # m : the green FIRST off to the left with its line, as FRESH's case comes in
    #     from the right
    @subscene
    def case_swap(self):
        self._setup_case_swap()
        self.play(VGroup(self.g_row, self.g_line).animate.shift(self.m_away),
                  self.m_in.animate.shift(self.m_away), run_time=1.5)
        self.remove(self.g_row, self.g_line, self.m_in)
        self.add(self.case, self.case_line, self.case_word)
        self.g_row = self.g_line = self.m_in = self.m_away = None

    def _setup_type_fresh(self):
        """An empty row the case's size, under it at the board's row spacing."""
        self.guess2 = WordleBoard(rows=1, cols=5)
        self.guess2.scale(self.case.width / self.guess2.width)
        self.guess2.next_to(self.case, DOWN, buff=self.case.tiles[0][0].height * GAP / TILE)

    # n : FRESH typed below FIRST, its tiles appearing as typed
    @subscene
    def type_fresh(self):
        self._setup_type_fresh()
        self.guess2.type_word(self, 0, SINGLE, 0.65, per_letter=key_cues(self), appear=True)

    # o : FRESH scored — all green
    @subscene
    def score_fresh(self):
        self.guess2.reveal(self, 0, ALL_GREEN, 1.6)

    # p : the word at the bottom vanishes AS FRESH does the winning row's bounce (as l)
    @subscene
    def fresh_win(self):
        self.play(FadeOut(self.case_word),
                  self.guess2.bounce_anim(0, height=_jump(self.guess2)), run_time=1.0)
        self.remove(self.case_word)
        self.case_word = None

    # ── a two-word group: guess one, and branch on the answer (q-w) ────────────
    def _typed_row(self, above):
        """An empty row `above`'s size, under it at the board's row spacing."""
        row = WordleBoard(rows=1, cols=5)
        row.scale(above.width / row.width)
        row.next_to(above, DOWN, buff=above.tiles[0][0].height * GAP / TILE)
        return row

    def _setup_pair_swap(self):
        X, Y = config.frame_x_radius, config.frame_y_radius
        self.pcase = scored_row(FIRST, PAIR_CODE, self.case.width, ORIGIN)
        self.pline = _line([0, Y + OFF_CLEAR, 0], _r(self.pcase))
        self.pwords = [PigpenWord(w, revealed=True).scale(WIN_SCALE)
                       .move_to([sx * PAIR_WORD_DX, CASE_WORD_Y, 0])
                       for w, sx in zip(PAIR, (-1, 1))]
        self.q_out = VGroup(self.case, self.guess2, self.case_line)
        self.q_in = VGroup(self.pcase, self.pline, *self.pwords).shift(RIGHT * SWAP_DIST)

    # q : FRESH's case off to the left, the BURST/WORST case in from the right
    @subscene
    def pair_swap(self):
        self._setup_pair_swap()
        self.play(self.q_out.animate.shift(LEFT * SWAP_DIST),
                  self.q_in.animate.shift(LEFT * SWAP_DIST), run_time=1.5)
        self.remove(self.q_out, self.q_in)
        self.add(self.pcase, self.pline, *self.pwords)
        self.case = self.guess2 = self.case_line = self.q_out = self.q_in = None

    # r : BURST typed below FIRST, tiles appearing as typed
    @subscene
    def type_burst(self):
        self.prow = self._typed_row(self.pcase)
        self.prow.type_word(self, 0, PAIR[0], 0.65, per_letter=key_cues(self), appear=True)

    def _branch(self, parent, rows, targets, rise=ORIGIN):
        """Copies of the case `rows` (top first), each sliding from where the case is
        to its target FIRST-row centre, each with a line from `parent`'s R to the
        copy's FIRST R that stays anchored as it goes. `rise` is how far the case
        itself moves meanwhile (its copies' targets are absolute). Returns (copies,
        lines, the play's animations)."""
        copies, lines, anims = [], [], []
        src = _r(parent)
        for t in targets:
            c = VGroup(*[r.copy() for r in rows])
            v = np.array(t) - rows[0].get_center()
            line = _line(src, _r(rows[0]))
            copies.append(c)
            lines.append(line)
            anims.append(c.animate.shift(v))
            r0 = _r(rows[0])
            anims.append(UpdateFromAlphaFunc(
                line, lambda m, a, r0=r0, v=v: m.put_start_and_end_on(
                    src + rise * smooth(a), r0 + v * smooth(a)),
                rate_func=linear))
        return copies, lines, anims

    def _under(self, word, rows):
        """Where `word` sits under the case `rows`."""
        return rows[-1].get_bottom() + DOWN * (WORD_GAP + word.height / 2)

    def _setup_branch_score(self):
        """ONE play (user's call, merging the script's s, t and u): the case rises to
        TREE_Y, its line from the top shortening with it; two copies branch off, left
        and right, a line from BURST's R to each; each copy's BURST flips to its
        scoring AS it travels — all green on the left (the answer is BURST), --GGG
        on the right (the answer is WORST); and BURST and WORST glide under their
        cases."""
        y = TREE_Y - CHILD_DY
        rise = UP * (TREE_Y - self.pcase.get_center()[1])
        pitch = self.prow.get_center() - self.pcase.get_center()
        targets = [np.array([-CHILD_DX, y, 0]), np.array([CHILD_DX, y, 0])]
        firsts, self.kid_lines, self.s_anims = self._branch(
            self.prow, [self.pcase], targets, rise)
        top, r0 = self.pline.get_start(), _r(self.pcase)
        self.s_anims += [VGroup(self.pcase, self.prow).animate.shift(rise),
                         UpdateFromAlphaFunc(self.pline, lambda m, a: m.put_start_and_end_on(
                             top, r0 + rise * smooth(a)), rate_func=linear)]
        # each copy's BURST: a copy of the typed row flipping into its scored row
        # while travelling to its place (flip.Flip's travel, as 06's switches)
        self.s_olds, self.s_flips, scored = [], [], []
        for t, code in zip(targets, (ALL_GREEN, CROSS)):
            old = self.prow.copy()
            new = scored_row(PAIR[0], code, self.prow.width, t + pitch)
            self.s_olds.append(old)
            self.s_flips.append(Flip(old, new, parts=(row_parts(old), row_parts(new)),
                                     travel=True))
            scored.append(new)
        self.s_anims += [w.animate.move_to(self._under(w, [new]))
                         for w, new in zip(self.pwords, scored)]
        self.kids = [VGroup(f[0], new) for f, new in zip(firsts, scored)]
        self.s_firsts = [f[0] for f in firsts]

    # s : one play — the case rises as two copies branch off left and right, each
    #     BURST flipping to its scoring on the way, BURST and WORST gliding under
    #     their cases (the script's s, t and u together)
    @subscene
    def branch_score(self):
        self._setup_branch_score()
        self.add(*self.kid_lines, *self.s_firsts, *self.s_olds)
        flip(self, self.s_flips, 1.8, extra=self.s_anims)
        self.remove(VGroup(self.pcase, self.prow))
        self.add(self.pcase, self.prow, *self.prow.letters[0], *self.s_firsts)
        self.s_anims = self.s_olds = self.s_flips = self.s_firsts = None

    # t (script v) : the left case (all green) does the winning bounce as BURST under it fades
    @subscene
    def left_win(self):
        row = self.kids[0][1]
        self.play(FadeOut(self.pwords[0]), row.bounce_anim(0, height=_jump(row)),
                  run_time=1.0)
        self.remove(self.pwords[0])

    def _setup_right_branch(self):
        kid = self.kids[1]
        t = kid[0].get_center() + DOWN * CHILD_DY
        (self.gkid,), (self.gline,), self.w_anims = self._branch(kid[1], list(kid), [t])
        # the row WORST will be typed into, where it will be once the branch lands,
        # and WORST travelling down to sit under it as the branch comes down
        self.grow = self._typed_row(kid[1].copy().shift(t - kid[0].get_center()))
        w = self.pwords[1]
        self.w_anims.append(w.animate.move_to(self._under(w, [self.grow])))

    # u (script w) : the right case branches down once more, WORST (black) coming down with it;
    #     WORST typed under the copy, scored all green, and the winning bounce as
    #     the black WORST fades
    @subscene
    def right_branch(self):
        self._setup_right_branch()
        self.add(self.gline, self.gkid)
        self.play(*self.w_anims, run_time=1.2)
        self.w_anims = None
        self.grow.type_word(self, 0, PAIR[1], 0.65, per_letter=key_cues(self), appear=True)
        self.grow.reveal(self, 0, ALL_GREEN, 1.6)
        self.play(FadeOut(self.pwords[1]), self.grow.bounce_anim(0, height=_jump(self.grow)),
                  run_time=1.0)
        self.remove(self.pwords[1])
