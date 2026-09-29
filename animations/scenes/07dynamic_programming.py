"""Scene 07 — dynamic programming: an opener's groups, then the subgroups a second
guess makes of one of them. Navy background.

Talking head THE sits between 06 and here, so the frame starts empty and the board
fades in. The script's 07 is not finished yet (it stops at 07e), so no beat clears
the frame at the end.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_board   — the empty board fades in                           (07a, VO 1)
  b type_first   — FIRST typed into row 0                             (07b, VO 1)
  c first_groups — the board slides to the left edge while FIRST's groups
                   come in from beyond the frame, in the style of the end
                   of scene 06: every group, sorted by size, dots under a
                   scored FIRST row sqrt(size) dot pitches wide        (07c, VO 1)
  d all_gray     — the board's FIRST flips all gray; every other group
                   leaves by its nearest edge; the all-gray FIRST row moves
                   to the top middle of the column right of the board,
                   growing, while its dots travel to their words' spots;
                   then the dots turn into the words                   (07d, VO 2)
  e after_split  — AFTER typed into row 1; the words regroup into AFTER's
                   subgroups; then a scored AFTER row atop each        (07e, VO 2)

REUSE MAP — every element and the one source it comes from:
  board, typing, reveal   assets/board.py `get_board`, `type_word`, `reveal` (02)
  keystroke sfx           assets/keys.py `key_cues` (02, 97)
  sorted dot groups (c)   assets/groups.py `ranked_layout` + `scored_row`, dots
                          white, row stroke scaled — exactly 06b-f's end state
  entrance (c)            assets/groups.py `enter_from_beyond` — 06b's radial slide-in
  exit (d)                assets/groups.py `edge_out` — 06's switches
  dots into words (d)     06b's words-into-dots motion reversed (dots shrink
                          out, words GrowFromCenter)
  word groups (d, e)      assets/groups.py `ranked_word_layout` — 04's word
                          pitches and header proportion, packed as 06 packs dots
  regroup (e)             04i: words move to their new slots in one play, then
                          the scored rows FadeIn
  answer words            assets/pigpen.py `PigpenWord(revealed=True)`
  colours                 BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups, subgroups       assets/lists_data.py -> lists_cache.json `full["first"]`,
                          `sub["first:0:after"]`, from math/wordle.py `pattern`
No on-screen text beyond the words: column 2 names none. The spoken numbers (1,
2, 2.5 guesses) are not shown.

LAYOUT CHOICES, flagged:
  - FIRST and AFTER are read as the literal words the script capitalises.
  - The board is centred for a/b (it is alone) and slides to the left edge in c,
    taking the corner word's place from 06; the groups keep CORNER_MARGIN clear of it.
  - "The middle of the big right column" is read as the TOP middle of the region
    right of the board, the words gridded below the row. The row grows to PARENT_W.
  - The FIRST row stays at the top in e, above AFTER's subgroups.
  - In d the row move and the dots' travel are one play, then the dots turn into
    words — the words are far bigger than the dots, so turning them in place
    first would overlap.
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
                           REGION_HALF_W, DOT_REGION_TOP, enter_from_beyond, edge_out)
from assets import lists_data

DATA = lists_data.load()
FIRST, AFTER = "first", "after"    # the script's own words
ALL_GRAY = 0                       # pattern code of the all-gray reply
SUB = DATA["sub"][f"{FIRST}:{ALL_GRAY}:{AFTER}"]

DOT_COLOR = WHITE                  # 06's dots
CORNER_BUFF = 0.3                  # the board's gap to the left edge (06's corner gap)
CORNER_MARGIN = 0.35               # clear space kept between the board and the groups
PARENT_W = 2.4                     # the all-gray FIRST row's width atop the column
PARENT_GAP = 0.25                  # between that row and the words below it


class Scene07(WordleBoardScene):
    """BEAT MAP
    show_board — the empty board fades in
    type_first — FIRST typed
    first_groups — board to the left; FIRST's groups in, 06's sorted dot style
    all_gray — FIRST flips all gray; only the all-gray group stays, as words
    after_split — AFTER typed; the words split into AFTER's subgroups
    """

    def setup_scene(self):
        pass

    # a : the empty board fades in
    @subscene
    def show_board(self):
        self.board = get_board()
        self.play(FadeIn(self.board), run_time=0.8)

    # b : FIRST typed into row 0
    @subscene
    def type_first(self):
        self.board.type_word(self, 0, FIRST, 0.65, per_letter=key_cues(self))

    def _setup_first_groups(self):
        X = config.frame_x_radius
        w = self.board.width
        self.board_home = np.array([-X + CORNER_BUFF + w / 2, 0.0, 0.0])
        self.col_left = -X + CORNER_BUFF + w + CORNER_MARGIN
        groups, spots, rows, widths, r = ranked_layout(DATA, FIRST, left=self.col_left)
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.dots = {wd: Dot(point=c, radius=r, color=DOT_COLOR) for wd, c in spots.items()}
        self.rows = {g["code"]: scored_row(FIRST, g["code"], wd, c,
                                           stroke=STROKE * min(1.0, wd / HEADER_W))
                     for g, c, wd in zip(groups, rows, widths)}
        self.members = {g["code"]: g["members"] for g in groups}
        # every group starts beyond the frame, out along the ray through its spot
        self.incoming = []
        for g in groups:
            grp = VGroup(self.rows[g["code"]], *[self.dots[m] for m in g["members"]])
            self.incoming.append((grp, enter_from_beyond(grp)))

    # c : the board slides to the left edge as FIRST's groups come in, sorted by
    #     size — the end of scene 06's style
    @subscene
    def first_groups(self):
        self._setup_first_groups()
        self.play(self.board.animate.move_to(self.board_home),
                  *[grp.animate.move_to(c) for grp, c in self.incoming],
                  run_time=2.0)
        # unwrap the slide-in groups, so every row and dot is top-level
        for grp, _ in self.incoming:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.incoming = None

    def _setup_all_gray(self):
        self.row = self.rows.pop(ALL_GRAY)
        keep = set(self.members[ALL_GRAY])
        self.leaving = [*self.rows.values(),
                        *[d for wd, d in self.dots.items() if wd not in keep]]
        self.dots = {wd: self.dots[wd] for wd in self.members[ALL_GRAY]}
        x_mid = (self.col_left + REGION_HALF_W) / 2
        self.parent = scored_row(FIRST, ALL_GRAY, PARENT_W, ORIGIN)
        self.parent.move_to([x_mid, DOT_REGION_TOP - self.parent.height / 2, 0.0])
        gray = {"size": len(self.dots), "members": list(self.dots)}
        self.words_top = self.parent.get_bottom()[1] - PARENT_GAP
        slots, self.w_scale, _, _ = ranked_word_layout([gray], self.col_left,
                                                       top=self.words_top, header=False)
        self.words = {wd: PigpenWord(wd, revealed=True).scale(self.w_scale).move_to(c)
                      for wd, c in slots.items()}
        self.rows = self.members = None

    # d : FIRST flips all gray on the board; every other group leaves; the all-gray
    #     FIRST row moves to the top middle of the column as its dots travel to their
    #     words' spots; then the dots turn into the words
    @subscene
    def all_gray(self):
        self._setup_all_gray()
        self.board.reveal(self, 0, ALL_GRAY, 1.6)
        self.play(*[m.animate.move_to(edge_out(m)) for m in self.leaving], run_time=1.2)
        self.remove(*self.leaving)
        self.leaving = None
        self.play(Transform(self.row, self.parent),
                  *[d.animate.move_to(self.words[wd].get_center())
                    for wd, d in self.dots.items()],
                  run_time=1.5)
        self.remove(self.row)
        self.add(self.parent)
        self.row = None
        self.play(*[d.animate.scale(0.1).set_opacity(0) for d in self.dots.values()],
                  *[GrowFromCenter(m) for m in self.words.values()],
                  run_time=1.0)
        self.remove(*self.dots.values())
        self.dots = None

    def _setup_after_split(self):
        slots, s, heads, widths = ranked_word_layout(SUB, self.col_left, top=self.words_top)
        assert set(slots) == set(self.words)
        self.slots, self.f_words = slots, s / self.w_scale
        self.w_scale = s
        self.heads = [scored_row(AFTER, g["code"], wd, c)
                      for g, c, wd in zip(SUB, heads, widths)]

    # e : AFTER typed into row 1; the words regroup into AFTER's subgroups; then a
    #     scored AFTER row atop each (04i's order)
    @subscene
    def after_split(self):
        self._setup_after_split()
        self.board.type_word(self, 1, AFTER, 0.65, per_letter=key_cues(self))
        self.play(*[m.animate.scale(self.f_words).move_to(self.slots[wd])
                    for wd, m in self.words.items()],
                  run_time=2.0)
        self.play(*[FadeIn(h) for h in self.heads], run_time=0.8)
        self.slots = None
