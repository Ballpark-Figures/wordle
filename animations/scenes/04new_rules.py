"""Scene 04 — Wordle reframed as a puzzle: two word lists, and the groups a guess
makes. Navy background.

The empty board is up from frame 0 (setup_scene) — the scene follows talking head
THC, which covers the cut in. Scene 05 follows directly, so an extra last beat (j)
clears the frame.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a empty_board  — the empty board, held (nothing moves)             (04a, VO 1)
  b answers      — board out; "2,315 Answers" + the answer column in
                   pigpen, rows rising one at a time, then "…"        (04b, VO 2)
  c guesses      — "12,972 Guesses" + the guess column, same         (04c, VO 2)
  d group_aahed  — the top guess to top centre, the rest fade; the
                   answers shrink into AAHED's groups, members not on
                   screen rising from below the column; the groups
                   scattered over the frame (not in rows), more hung
                   off its edges, as if every group is out there. NO
                   OVALS (user's call, overriding the script)        (04d, VO 3)
  e group_more   — AAHED off left, PIGGY in from right as the
                   answers regroup; the same with CODES              (04e, VO 3)
  f back         — undo the grouping: answers back to their column as
                   CODES leaves off the top; the guess list back     (04f, VO 4)
  g reveal_right — the guess glyphs flip over to letters             (04g, VO 5)
  h reveal_left  — the answer glyphs flip over to letters            (04h, VO 5)
  i piggy        — PIGGY rises from below the guess list to the top as
                   the answers regroup into its groups; a scored
                   PIGGY row atop each group                         (04i, VO 6)
  j clear_out    — everything out, for scene 05 (not a script beat)

REUSE MAP — every element and the one source it comes from:
  board                  assets/board.py `get_board`, as scenes 02/03
  pigpen words + decode  assets/pigpen.py `PigpenWord` (board tiles + glyphs), `decode` — the
                         decode is board.TileFlip's squash, tile and glyph together
  list reveal            hangman's word_tables_scene `_reveal`: title FadeIn 0.4,
                         then rows FadeIn(shift=UP*0.3) in a LaggedStart, lag 0.12
  group layout           assets/groups.py `layout` (extracted from this scene for 06)
  scored PIGGY rows      assets/groups.py `scored_headers` (board.py `get_scored_row`)
  labels                 crisp_text, white, FadeIn (scene 01's convention)
  colours                BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  counts, lists, groups  assets/lists_data.py -> lists_cache.json: line counts of
                         the word lists, groups from math/wordle.py `pattern`
On-screen text is only what column 2 names: the two titles, the words, the "…".
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board
from assets.pigpen import PigpenWord, decode
from assets.groups import layout, scored_headers, GUESS_Y, GUESS_SCALE
from assets import lists_data

DATA = lists_data.load()
ANSWERS = DATA["answers"]
RANK = {w: i for i, w in enumerate(ANSWERS)}
TOP_GUESS, SECOND, THIRD = DATA["guesses"]          # aahed (the list's first), piggy, codes

# ── the two columns ───────────────────────────────────────────────────────────
N_ROWS = 12                # words shown in each column above the "…"
LEFT_X, RIGHT_X = -4.0, 4.0
TITLE_Y = 3.75
ROW0_Y = 2.85              # first word's centre
ROW_DY = 0.5
TITLE_FS = 40
DOTS_FS = 40
OFF_DY = 0.003             # below-frame spacing per alphabetical rank (compressed)

# ── the groups (layout in assets/groups.py) ─────────────────────────────────
OFF_X = 10.0               # a guess entering/leaving sideways starts/ends here


def _home(r, x):
    return np.array([x, ROW0_Y - r * ROW_DY, 0.0])


def _offspot(w):
    """Below the frame under the answer column, in alphabetical order — where the
    word would be if the column ran on."""
    y = -config.frame_y_radius - 0.6 - (RANK[w] - N_ROWS) * OFF_DY
    return np.array([LEFT_X, y, 0.0])


def _layout(guess, header=False, chain=False):
    return layout(DATA, guess, header=header, chain=chain)


class Scene04(WordleBoardScene):
    """BEAT MAP
    empty_board — the empty board, held
    answers — the answer list, in pigpen
    guesses — the guess list, in pigpen
    group_aahed — the answers into AAHED's groups
    group_more — PIGGY's groups, then CODES's
    back — undo the grouping, back to the two lists
    reveal_right — decode the guesses
    reveal_left — decode the answers
    piggy — PIGGY's groups, scored
    clear_out — everything out
    """

    def setup_scene(self):
        self.board = get_board()
        self.add(self.board)

    # ── answer words: one mobject per word, created on demand ─────────────────
    def _ans(self, w, revealed=False):
        """The answer word `w`, parked at its below-frame spot if new. A word that
        is off screen and in the wrong state (pigpen vs letters) is rebuilt."""
        mob = self.ans.get(w)
        if mob is None or (w not in self.on and mob.revealed != revealed):
            mob = PigpenWord(w, revealed=revealed).move_to(_offspot(w))
            self.ans[w], self.scale[w] = mob, 1.0
        return mob

    def _to(self, w, centre, scale):
        mob = self.ans[w]
        f = scale / self.scale[w]
        self.scale[w] = scale
        return mob.animate.scale(f).set_glyph_stroke(scale).move_to(centre)

    def _regroup(self, slots, scale, run_time, revealed=False, extra=()):
        """Every word in `slots` to its slot at `scale`; every other answer on screen
        back down to its below-frame spot, and off. One play, which `extra`
        animations join (the guess moving, say)."""
        anims = list(extra)
        for w, c in slots.items():
            if w not in self.on:
                self.add(self._ans(w, revealed))
            anims.append(self._to(w, c, scale))
        leaving = [w for w in self.on if w not in slots]
        for w in leaving:
            anims.append(self._to(w, _offspot(w), 1.0))
        self.play(*anims, run_time=run_time)
        for w in leaving:
            self.remove(self.ans[w])
        self.on = set(slots)

    def _column(self):
        return {w: _home(r, LEFT_X) for r, w in enumerate(ANSWERS[:N_ROWS])}

    def _swap_guess(self, old, new):
        """The guess on top leaving left while `new` comes in from the right — the
        animations, to ride along with a regroup."""
        new.move_to([OFF_X, GUESS_Y, 0])
        return [old.animate.move_to([-OFF_X, GUESS_Y, 0]),
                new.animate.move_to([0, GUESS_Y, 0])]

    def _reveal_list(self, title, rows, rows_run_time):
        """hangman word_tables_scene `_reveal`: title in, then the rows rise one at a
        time."""
        self.play(FadeIn(title), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.3) for r in rows],
                              lag_ratio=0.12), run_time=rows_run_time)

    # a : the empty board, held — its VO plays over the framework's holds
    @subscene
    def empty_board(self):
        pass

    def _setup_answers(self):
        self.ans, self.scale, self.on = {}, {}, set()
        self.ans_title = crisp_text(f"{DATA['n_answers']:,} Answers", font_size=TITLE_FS,
                                    color=WHITE, weight=BOLD).move_to([LEFT_X, TITLE_Y, 0])
        for w, c in self._column().items():
            self._ans(w).move_to(c)
        self.on = set(self._column())
        self.ans_dots = crisp_text("…", font_size=DOTS_FS, color=WHITE) \
            .move_to(_home(N_ROWS, LEFT_X))

    # b : board out; the answer list, in pigpen, one row at a time
    @subscene
    def answers(self):
        self._setup_answers()
        self.play(FadeOut(self.board), run_time=0.6)
        self.board = None
        rows = [self.ans[w] for w in ANSWERS[:N_ROWS]] + [self.ans_dots]
        self._reveal_list(self.ans_title, rows, 2.4)

    def _setup_guesses(self):
        self.gss_title = crisp_text(f"{DATA['n_guesses']:,} Guesses", font_size=TITLE_FS,
                                    color=WHITE, weight=BOLD).move_to([RIGHT_X, TITLE_Y, 0])
        self.gss = [PigpenWord(w).move_to(_home(r, RIGHT_X))
                    for r, w in enumerate(DATA["guesses_head"][:N_ROWS])]
        self.gss_dots = crisp_text("…", font_size=DOTS_FS, color=WHITE) \
            .move_to(_home(N_ROWS, RIGHT_X))

    # c : the guess list, the same way
    @subscene
    def guesses(self):
        self._setup_guesses()
        self._reveal_list(self.gss_title, self.gss + [self.gss_dots], 2.4)

    def _setup_group_aahed(self):
        assert self.gss[0].word == TOP_GUESS
        self.guess = self.gss[0]
        self.slots, self.gscale, _, _ = _layout(TOP_GUESS)

    # d : top guess to top centre, the rest fade; answers into AAHED's groups,
    #     some hanging off the frame's edges
    @subscene
    def group_aahed(self):
        self._setup_group_aahed()
        self.play(self.guess.animate.scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
                  .move_to([0, GUESS_Y, 0]),
                  *[FadeOut(m) for m in self.gss[1:]],
                  FadeOut(self.gss_title), FadeOut(self.gss_dots),
                  FadeOut(self.ans_title), FadeOut(self.ans_dots), run_time=1.0)
        self._regroup(self.slots, self.gscale, 2.0)

    def _setup_group_more(self):
        self.guess2 = PigpenWord(SECOND).scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
        self.guess3 = PigpenWord(THIRD).scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
        self.lay2 = _layout(SECOND, chain=True)
        self.lay3 = _layout(THIRD, chain=True)

    # e : AAHED out left and PIGGY in right WHILE the answers regroup; then the
    #     same with CODES
    @subscene
    def group_more(self):
        self._setup_group_more()
        slots, scale, _, _ = self.lay2
        self._regroup(slots, scale, 2.0, extra=self._swap_guess(self.guess, self.guess2))
        self.remove(self.guess)
        self.wait(1.0)                              # PIGGY's groups hold a moment

        slots, scale, _, _ = self.lay3
        self._regroup(slots, scale, 2.0, extra=self._swap_guess(self.guess2, self.guess3))
        self.remove(self.guess2)
        self.guess = self.guess3
        self.guess2 = self.guess3 = self.lay2 = self.lay3 = None

    def _setup_back(self):
        # AAHED left the frame in e; it fades back in at its own column slot
        self.gss[0].scale(1 / GUESS_SCALE).set_glyph_stroke(1.0).move_to(_home(0, RIGHT_X))

    # f : undo the grouping — the answers back into their column while CODES leaves
    #     off the top; then the guess list back on the right
    @subscene
    def back(self):
        self._setup_back()
        self._regroup(self._column(), 1.0, 2.0,
                      extra=[self.guess.animate.move_to(
                          [0, config.frame_y_radius + 1.0, 0])])
        self.remove(self.guess)
        self.guess = None
        self.play(*[FadeIn(m) for m in self.gss],
                  FadeIn(self.gss_title), FadeIn(self.gss_dots),
                  FadeIn(self.ans_title), FadeIn(self.ans_dots), run_time=1.0)

    # g : the guesses decode, glyph by glyph
    @subscene
    def reveal_right(self):
        self.play(LaggedStart(*[decode(w, 0.8) for w in self.gss], lag_ratio=0.12),
                  run_time=2.5)

    # h : the answers decode, glyph by glyph
    @subscene
    def reveal_left(self):
        words = [self.ans[w] for w in ANSWERS[:N_ROWS]]
        self.play(LaggedStart(*[decode(w, 0.8) for w in words], lag_ratio=0.12),
                  run_time=2.5)

    def _setup_piggy(self):
        # PIGGY starts below the guess list, where it would sit if the list ran on
        self.guess = PigpenWord(SECOND, revealed=True) \
            .move_to([RIGHT_X, -config.frame_y_radius - 0.6, 0])
        self.slots, self.gscale, heads, groups = _layout(SECOND, header=True)
        self.heads = scored_headers(SECOND, groups, heads, self.gscale)

    # i : PIGGY rises from below the guess list to the top WHILE the answers regroup
    #     into its groups; then each group's coloured PIGGY
    @subscene
    def piggy(self):
        self._setup_piggy()
        self.add(self.guess)
        self._regroup(self.slots, self.gscale, 2.0, revealed=True, extra=[
            *[FadeOut(m) for m in self.gss],
            FadeOut(self.gss_title), FadeOut(self.gss_dots),
            FadeOut(self.ans_title), FadeOut(self.ans_dots),
            self.guess.animate.scale(GUESS_SCALE).move_to([0, GUESS_Y, 0])])
        self.play(*[FadeIn(h) for h in self.heads], run_time=0.8)

    # j : everything out, so scene 05 starts on an empty frame (not a script beat —
    #     split from i so the clear can be placed on its own in the edit)
    @subscene
    def clear_out(self):
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.8)
