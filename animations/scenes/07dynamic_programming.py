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
from assets.board import get_board, STROKE
from assets.pigpen import PigpenWord
from assets.keys import key_cues
from assets.groups import (ranked_layout, ranked_word_layout, scored_row, HEADER_W,
                           GUESS_SCALE, HEAD_ROW_GAP, row_aspect, enter_from_beyond,
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
        groups, spots, rows, widths, r = ranked_layout(DATA, FIRST, left=self.col_left)
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.dots = {wd: Dot(point=c, radius=r, color=DOT_COLOR) for wd, c in spots.items()}
        # each group — its scored row and its dots — as one unit, keyed by code
        self.units = {}
        for g, c, wd in zip(groups, rows, widths):
            row = scored_row(FIRST, g["code"], wd, c, stroke=STROKE * min(1.0, wd / HEADER_W))
            self.units[g["code"]] = (row, g["members"])
        # every group starts beyond the frame, out along the ray through its spot
        self.incoming = []
        for row, members in self.units.values():
            grp = VGroup(row, *[self.dots[m] for m in members])
            self.incoming.append((grp, enter_from_beyond(grp)))

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
