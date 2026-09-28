"""Scene 04 — Wordle reframed as a puzzle: two word lists, and the groups a guess
makes. Navy background.

The empty board is up from frame 0 (setup_scene) — the scene follows talking head
THC, which covers the cut in. Scene 05 follows directly, so the last beat ends by
clearing the frame.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a empty_board  — the empty board, held (nothing moves)             (04a, VO 1)
  b answers      — board out; "2,315 Answers" + the answer column in
                   pigpen, rows rising one at a time, then "…"        (04b, VO 2)
  c guesses      — "12,972 Guesses" + the guess column, same         (04c, VO 2)
  d group_aahed  — the top guess to top centre, the rest fade; the
                   answers shrink into AAHED's groups, members not on
                   screen rising from below the column; ovals drawn,
                   scattered over the frame (not in rows)            (04d, VO 3)
  e group_more   — AAHED off left, PIGGY in from right, ovals out,
                   regroup, ovals back; the same again with CODES    (04e, VO 3)
  f back         — undo the grouping: answers back to their column, the
                   guess list back on the right                      (04f, VO 4)
  g reveal_right — the guess glyphs flip over to letters             (04g, VO 5)
  h reveal_left  — the answer glyphs flip over to letters            (04h, VO 5)
  i piggy        — PIGGY on top, the answers into PIGGY's groups, a
                   scored PIGGY row atop each oval; then clear       (04i, VO 6)

REUSE MAP — every element and the one source it comes from:
  board                  assets/board.py `get_board`, as scenes 02/03
  pigpen words + decode  assets/pigpen.py `PigpenWord` (board tiles + glyphs), `decode` — the
                         decode is board.TileFlip's squash, tile and glyph together
  list reveal            hangman's word_tables_scene `_reveal`: title FadeIn 0.4,
                         then rows FadeIn(shift=UP*0.3) in a LaggedStart, lag 0.12
  scored PIGGY rows      assets/board.py `get_scored_row`
  labels                 crisp_text, white, FadeIn (scene 01's convention)
  colours                BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  counts, lists, groups  assets/lists_data.py -> lists_cache.json: line counts of
                         the word lists, groups from math/wordle.py `pattern`
On-screen text is only what column 2 names: the two titles, the words, the "…".
"""
from pathlib import Path
import math
import random
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import get_board, get_scored_row
from assets.pigpen import PigpenWord, decode, WORD_W
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

# ── the groups ────────────────────────────────────────────────────────────────
GUESS_Y = 3.7              # the guess, top centre
GUESS_SCALE = 1.2
GROUP_SCALE = 0.45         # word size inside a group, before any fit-to-frame
CELL_GAP = 0.2             # between words in a group (group size)
CELL_DY = 0.26             # word row pitch in a group (group size)
ELLIPSE_K = 1.3            # ellipse / word-grid bounding box
ELLIPSE_PAD = 0.4
ELLIPSE_STROKE = 3
BLOCK_GAP = 0.3            # least clear space between two ovals
SCATTER_TRIES = 300       # candidate spots per oval
REGION_HALF_W = 7.7        # ovals stay inside x in [-7.7, 7.7]
REGION_TOP, REGION_BOT = 2.95, -4.2
HEADER_W = 1.3             # a scored PIGGY row's width atop its oval
HEADER_H = 0.35            # room reserved above an oval for that row
OFF_X = 10.0               # a guess entering/leaving sideways starts/ends here


def _home(r, x):
    return np.array([x, ROW0_Y - r * ROW_DY, 0.0])


def _offspot(w):
    """Below the frame under the answer column, in alphabetical order — where the
    word would be if the column ran on."""
    y = -config.frame_y_radius - 0.6 - (RANK[w] - N_ROWS) * OFF_DY
    return np.array([LEFT_X, y, 0.0])


def _scatter(sizes, seed):
    """Centres for blocks of size (w, h), SCATTERED over the group region rather
    than packed in rows. Best-candidate sampling: biggest block first, each takes
    whichever of SCATTER_TRIES random spots leaves the widest gap to the blocks
    already placed, and no spot closer than BLOCK_GAP counts. If a block finds no
    spot, everything shrinks 5% and the placement starts over.

    Seeded, so a render is repeatable; change the seed string for a different
    scatter. Returns (shrink factor, centres in block order)."""
    rng = random.Random(seed)
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][0] * sizes[i][1])
    f = 1.0
    while True:
        placed = {}
        for i in order:
            w, h = sizes[i][0] * f, sizes[i][1] * f
            xr, ylo, yhi = REGION_HALF_W - w / 2, REGION_BOT + h / 2, REGION_TOP - h / 2
            if xr < 0 or ylo > yhi:
                break
            best, best_gap = None, -1.0
            for _ in range(SCATTER_TRIES):
                x, y = rng.uniform(-xr, xr), rng.uniform(ylo, yhi)
                gap = min((max(abs(x - px) - (w + pw) / 2, abs(y - py) - (h + ph) / 2)
                           for (px, py), pw, ph in placed.values()), default=1e9)
                if gap >= BLOCK_GAP and gap > best_gap:
                    best, best_gap = (x, y), gap
            if best is None:
                break
            placed[i] = (best, w, h)
        if len(placed) == len(sizes):
            return f, [placed[i][0] for i in range(len(sizes))]
        f *= 0.95


def _layout(guess, header=False, chain=False):
    """Word centres, ovals and header positions for `guess`'s shown groups: the
    ovals scattered over the frame (`_scatter`), the words in a tidy grid inside
    each. `chain` takes 04e's carry-over groups (lists_data) instead of the
    size-target ones. Returns (slots {word: centre}, scale, ovals, header centres)."""
    groups = DATA["chain" if chain else "groups"][guess]
    ww, cg, dy = WORD_W * GROUP_SCALE, CELL_GAP, CELL_DY
    blocks = []
    for g in groups:
        n = len(g["members"])
        nc = math.ceil(math.sqrt(n))
        nr = math.ceil(n / nc)
        gw, gh = nc * ww + (nc - 1) * cg, nr * dy
        ew, eh = gw * ELLIPSE_K + ELLIPSE_PAD, gh * ELLIPSE_K + ELLIPSE_PAD
        hh = HEADER_H if header else 0.0
        blocks.append(dict(g=g, nc=nc, ew=ew, eh=eh, hh=hh))
    f, centres = _scatter([(b["ew"], b["eh"] + b["hh"]) for b in blocks],
                          f"04:{guess}:{header}")
    slots, ovals, headers = {}, [], []
    for b, (bx, by) in zip(blocks, centres):
        cx, cy = bx, by - b["hh"] * f / 2          # the oval sits under its header
        ovals.append(Ellipse(width=b["ew"] * f, height=b["eh"] * f, color=WHITE,
                             stroke_width=ELLIPSE_STROKE).move_to([cx, cy, 0]))
        headers.append(np.array([cx, cy + b["eh"] * f / 2, 0.0]))
        members, nc = b["g"]["members"], b["nc"]
        nr = math.ceil(len(members) / nc)
        for k, word in enumerate(members):
            i, j = divmod(k, nc)
            n_in_row = min(nc, len(members) - i * nc)
            wx = cx + (j - (n_in_row - 1) / 2) * (ww + cg) * f
            wy = cy + ((nr - 1) / 2 - i) * dy * f
            slots[word] = np.array([wx, wy, 0.0])
    return slots, GROUP_SCALE * f, ovals, headers


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
    piggy — PIGGY's groups, scored, then clear
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

    def _regroup(self, slots, scale, run_time, revealed=False):
        """Every word in `slots` to its slot at `scale`; every other answer on screen
        back down to its below-frame spot, and off. One play."""
        anims = []
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

    def _swap_guess(self, old, new, run_time):
        """The guess on top leaves left while `new` comes in from the right."""
        new.move_to([OFF_X, GUESS_Y, 0])
        self.play(old.animate.move_to([-OFF_X, GUESS_Y, 0]),
                  new.animate.move_to([0, GUESS_Y, 0]), run_time=run_time)
        self.remove(old)

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
        self.slots, self.gscale, self.ovals, _ = _layout(TOP_GUESS)

    # d : top guess to top centre, the rest fade; answers into AAHED's groups; ovals
    @subscene
    def group_aahed(self):
        self._setup_group_aahed()
        self.play(self.guess.animate.scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
                  .move_to([0, GUESS_Y, 0]),
                  *[FadeOut(m) for m in self.gss[1:]],
                  FadeOut(self.gss_title), FadeOut(self.gss_dots),
                  FadeOut(self.ans_title), FadeOut(self.ans_dots), run_time=1.0)
        self._regroup(self.slots, self.gscale, 2.0)
        self.play(*[Create(o) for o in self.ovals], run_time=0.8)

    def _setup_group_more(self):
        self.guess2 = PigpenWord(SECOND).scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
        self.guess3 = PigpenWord(THIRD).scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE)
        self.lay2 = _layout(SECOND, chain=True)
        self.lay3 = _layout(THIRD, chain=True)

    # e : AAHED out left, PIGGY in right, regroup; then the same with CODES
    @subscene
    def group_more(self):
        self._setup_group_more()
        self._swap_guess(self.guess, self.guess2, 1.0)
        self.play(*[FadeOut(o) for o in self.ovals], run_time=0.5)
        slots, scale, self.ovals, _ = self.lay2
        self._regroup(slots, scale, 2.0)
        self.play(*[Create(o) for o in self.ovals], run_time=0.8)

        self._swap_guess(self.guess2, self.guess3, 1.0)
        self.play(*[FadeOut(o) for o in self.ovals], run_time=0.5)
        slots, scale, self.ovals, _ = self.lay3
        self._regroup(slots, scale, 2.0)
        self.play(*[Create(o) for o in self.ovals], run_time=0.8)
        self.guess = self.guess3
        self.guess2 = self.guess3 = self.lay2 = self.lay3 = None

    def _setup_back(self):
        # AAHED left the frame in e; it fades back in at its own column slot
        self.gss[0].scale(1 / GUESS_SCALE).set_glyph_stroke(1.0).move_to(_home(0, RIGHT_X))

    # f : undo the grouping — the answers back into their column, the guess list
    #     back on the right (CODES, still on top, fades as it returns)
    @subscene
    def back(self):
        self._setup_back()
        self.play(*[FadeOut(o) for o in self.ovals], run_time=0.5)
        self.ovals = None
        self._regroup(self._column(), 1.0, 2.0)
        self.play(FadeOut(self.guess),
                  *[FadeIn(m) for m in self.gss],
                  FadeIn(self.gss_title), FadeIn(self.gss_dots),
                  FadeIn(self.ans_title), FadeIn(self.ans_dots), run_time=1.0)
        self.guess = None

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
        self.guess = PigpenWord(SECOND, revealed=True) \
            .scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE).move_to([OFF_X, GUESS_Y, 0])
        self.slots, self.gscale, self.ovals, heads = _layout(SECOND, header=True)
        self.heads = []
        for g, c in zip(DATA["groups"][SECOND], heads):
            row = get_scored_row(SECOND, g["code"])
            self.heads.append(row.scale_to_fit_width(HEADER_W).move_to(c))

    # i : PIGGY on top; the answers into PIGGY's groups, each with its coloured
    #     PIGGY; then the frame clears for scene 05
    @subscene
    def piggy(self):
        self._setup_piggy()
        self.play(*[FadeOut(m) for m in self.gss],
                  FadeOut(self.gss_title), FadeOut(self.gss_dots),
                  FadeOut(self.ans_title), FadeOut(self.ans_dots),
                  self.guess.animate.move_to([0, GUESS_Y, 0]), run_time=1.0)
        self._regroup(self.slots, self.gscale, 2.0, revealed=True)
        self.play(*[Create(o) for o in self.ovals],
                  *[FadeIn(h) for h in self.heads], run_time=0.8)
        self.wait(2.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.8)
