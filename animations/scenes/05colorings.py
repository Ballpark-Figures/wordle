"""Scene 05 — the colorings: 3**5 = 243 of them, five impossible, TRACE reaching 150.
Navy background.

Scene 04 ends on an empty frame, so this opens from nothing. Talking head THD
follows, so the last beat ends with the marked grid still on screen.

BEAT MAP — script beat 05a is split into six subscenes (the C's appearance, the
first split, one per later x3) and 05i into two (the return, then the five
vanishing) — the user's calls, for editing — so subscene letters run AHEAD of the
script's from b on:

  a gray_c     — one gray C                                           (05a, VO 1)
  b split      — three copies become green, yellow, gray              (05a, VO 1)
  c grow_9     — x3: CO, 9 colorings                                  (05a, VO 1)
  d grow_27    — x3: COL, 27                                          (05a, VO 1)
  e grow_81    — x3: COLO, 81                                         (05a, VO 1)
  f grow_243   — x3: COLOR, all 243                                   (05a, VO 1)
  g focus      — everything else fades; GGYGG grows to board size, centred (05b, VO 2)
  h emph_c     — C emphasised (the other tiles dim)                     (05c, VO 2)
  i emph_r     — R emphasised                                           (05d, VO 2)
  j emph_os    — both Os emphasised                                     (05e, VO 2)
  k emph_l     — L emphasised                                           (05f, VO 2)
  l unemph     — the emphasis undone                                    (05g, VO 2)
  m impossible — GGGGY, GGGYG above and GYGGG, YGGGG below fade in       (05h, VO 3)
  n back       — the five shrink back to their slots in the 243, every
                 letter fading; the other 238 fade back in without letters (05i, VO 4)
  o vanish     — the five impossible colorings fade out, leaving five
                 empty slots (05i split in two — the user's call)       (05i, VO 4)
  p trace      — TRACE's letters on the colorings it can produce; the rest's
                 colours partly fade (the five empty slots stay empty)  (05j, VO 4)

REUSE MAP — every element and the one source it comes from:
  the build-up        yahtzee scenes/03dice.py `_grow` + `_cluster_centers`, ported
                      with 3-way splits: each parent spawns copies of itself plus one
                      new tile, which starts hidden on the parent's last tile. Box
                      15.6 x 8.6, CELL_GAP 0.04, grow lag_ratio 0.002 and run_time 0.8
                      carried over verbatim. Tile size per level is Yahtzee's rule
                      (the largest that fits the leaf cell).
  tiles + letters     assets/board.py's tile: TILE_STATE fill with a matching stroke
                      of width STROKE, a bold white letter LETTER_FRAC of the tile
                      high, tiles GAP/TILE apart — so the big rows ARE board rows
  emphasis            dim the rest to 0.2 (the house move; scene 01's convention)
  colours             BOARD_NAVY via WordleBoardScene; tiles config.py TILE_STATE
  which colorings     assets/colorings_data.py -> colorings_cache.json: the codes no
                      guess ever produces (asserted = the five 4G+1Y) and the codes
                      TRACE produces (asserted = maxbucket's 150), from math/wordle.py

TWO LAYOUT CHOICES, flagged:
  - Colours in each split run GREEN, YELLOW, GRAY (the user's call) — so a coloring's
    slot in the 243 is 242 minus its pattern code. `_slot` is the one place that says so.
  - The splits alternate columns / rows / columns / rows / rows, so the 243 land as
    9 columns x 27 rows of five-tile rows.
No on-screen text but the tiles' letters: 243 / 238 / 150 are spoken, not shown.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import TILE, GAP
from assets import colorings_data
from assets.colorings import (code as _code, trits as _trits, slot as _slot,
                              letters_on as _letters_on, coloring as _coloring,
                              tile_size as _tile_size, level)

DATA = colorings_data.load()
IMPOSSIBLE = set(DATA["impossible"])
TRACE = set(DATA["trace"])
WORD = "COLOR"
TRACE_WORD = DATA["word"].upper()

FOCUS = _code("GGYGG")                                  # 05b
STACK = [_code(s) for s in ("GGGGY", "GGGYG", "GGYGG", "GYGGG", "YGGGG")]  # 05h, top down
assert set(STACK) == IMPOSSIBLE, "the script's five are not the cache's impossible set"

DIM = 0.2                  # the house dim-the-rest opacity
ROW_PITCH = TILE + GAP     # 05h's stack: board rows, board spacing


def _level(k):
    """All 3**k colorings of COLOR's first k letters (assets/colorings.py)."""
    return level(k, WORD)


class Scene05(WordleBoardScene):
    """BEAT MAP
    gray_c — one gray C
    split — three copies to G/Y/gray
    grow_9 — x3 to 9
    grow_27 — x3 to 27
    grow_81 — x3 to 81
    grow_243 — x3 to 243
    focus — the rest fades, GGYGG to board size at centre
    emph_c — C emphasised
    emph_r — R emphasised
    emph_os — both Os emphasised
    emph_l — L emphasised
    unemph — emphasis undone
    impossible — the other four 4G+1Y colorings fade in around it
    back — the five back to their slots, letters out; the 238 back in
    vanish — the five fade out
    trace — TRACE's letters on its 150; the rest dimmed
    """

    # ── a ─────────────────────────────────────────────────────────────────────
    def _setup_build(self):
        self.level = _level(1)
        self.seed_c = _coloring([0], WORD[0], _tile_size(1)).move_to(ORIGIN)

    def _split(self, run_time):
        """The one gray C becomes three: green, yellow, gray."""
        copies = [self.seed_c.copy() for _ in range(3)]
        self.add(*copies)
        self.remove(self.seed_c)
        self.play(*[ReplacementTransform(c, t)
                    for c, t in zip(copies, self.level)], run_time=run_time)
        self.seed_c = None

    def _grow(self, k, run_time, lag_ratio=0.002):
        """Level k -> k+1: each parent's 3 children are children[3p : 3p+3]; a child's
        seed is copies of the parent's k tiles plus the new tile, which starts hidden
        on the parent's last tile and fades in as the seed becomes the child.
        Builds level k+1 itself (its owner) and leaves it in `self.level`."""
        parents, children = self.level, _level(k + 1)
        seeds, anims = [], []
        for p, parent in enumerate(parents):
            for j in range(3):
                child = children[3 * p + j]
                anchor = parent.tiles[k - 1]
                new_t = child.tiles[k].copy().set_opacity(0).move_to(anchor)
                new_l = child.letters[k].copy().set_opacity(0).move_to(anchor)
                seed = VGroup(VGroup(*[t.copy() for t in parent.tiles], new_t),
                              VGroup(*[l.copy() for l in parent.letters], new_l))
                seeds.append(seed)
                anims.append(Transform(seed, child))
        self.add(*seeds)
        self.remove(*parents)
        self.play(LaggedStart(*anims, lag_ratio=lag_ratio), run_time=run_time)
        self.remove(*seeds)
        self.add(*children)
        self.level = children

    # a : one gray C
    @subscene
    def gray_c(self):
        self._setup_build()
        self.play(FadeIn(self.seed_c), run_time=0.6)

    # b : three copies become green, yellow, gray
    @subscene
    def split(self):
        self._split(0.8)

    # c : x3 — CO, 9 colorings
    @subscene
    def grow_9(self):
        self._grow(1, 0.8)

    # d : x3 — COL, 27
    @subscene
    def grow_27(self):
        self._grow(2, 0.8)

    # e : x3 — COLO, 81
    @subscene
    def grow_81(self):
        self._grow(3, 0.8)

    # f : x3 — COLOR, all 243
    @subscene
    def grow_243(self):
        self._grow(4, 0.8)
        self.grid, self.level = self.level, None

    # g : everything else fades; GGYGG grows to board size at the centre
    @subscene
    def focus(self):
        self.focus_row = self.grid[_slot(FOCUS)]
        others = VGroup(*[r for r in self.grid if r is not self.focus_row])
        self.focus_row.set_z_index(1)
        f = TILE / self.focus_row.tiles[0].width
        self.play(FadeOut(others),
                  self.focus_row.animate.scale(f).move_to(ORIGIN), run_time=1.2)
        self.grid = None

    def _emph(self, on, run_time):
        """Tiles in `on` at full opacity, the rest dimmed to DIM."""
        r = self.focus_row
        anims = []
        for i in range(5):
            o = 1.0 if i in on else DIM
            anims += [r.tiles[i].animate.set_opacity(o),
                      r.letters[i].animate.set_opacity(o)]
        self.play(*anims, run_time=run_time)

    # h : C — it has to start with a C
    @subscene
    def emph_c(self):
        self._emph({0}, 0.5)

    # i : R — and end with an R
    @subscene
    def emph_r(self):
        self._emph({4}, 0.5)

    # j : the Os in the 2nd and 4th positions
    @subscene
    def emph_os(self):
        self._emph({1, 3}, 0.5)

    # k : L — somewhere, but not third
    @subscene
    def emph_l(self):
        self._emph({2}, 0.5)

    # l : emphasis undone
    @subscene
    def unemph(self):
        self._emph(set(range(5)), 0.5)

    # ── h ─────────────────────────────────────────────────────────────────────
    def _setup_impossible(self):
        mid = STACK.index(FOCUS)
        self.stack = {}
        for i, code in enumerate(STACK):
            if code == FOCUS:
                self.stack[code] = self.focus_row
                continue
            row = _coloring(_trits(code), WORD, TILE)
            row.move_to(UP * (mid - i) * ROW_PITCH)
            self.stack[code] = row

    # m : GGGGY, GGGYG above and GYGGG, YGGGG below
    @subscene
    def impossible(self):
        self._setup_impossible()
        self.play(*[FadeIn(r) for c, r in self.stack.items() if c != FOCUS],
                  run_time=0.8)
        self.focus_row = None

    # ── i ─────────────────────────────────────────────────────────────────────
    def _setup_back(self):
        self.grid = _level(5)
        for row in self.grid:
            row.letters.set_opacity(0)

    # n : the five shrink back into the 243, letters fading; the other 238 fade
    #     back in without letters
    @subscene
    def back(self):
        self._setup_back()
        home = {_slot(c) for c in self.stack}
        self.play(*[ReplacementTransform(r, self.grid[_slot(c)])
                    for c, r in self.stack.items()],
                  FadeIn(VGroup(*[r for i, r in enumerate(self.grid) if i not in home])),
                  run_time=1.5)
        self.stack = None

    # o : the five impossible colorings fade out, leaving five empty slots (05i)
    @subscene
    def vanish(self):
        self.play(*[FadeOut(self.grid[_slot(c)]) for c in IMPOSSIBLE], run_time=0.8)

    # ── j ─────────────────────────────────────────────────────────────────────
    def _setup_trace(self):
        self.trace_letters = VGroup(*[_letters_on(self.grid[_slot(c)].tiles, TRACE_WORD)
                                      for c in sorted(TRACE)])

    # p : TRACE's letters on the colorings it can have; the others' colours fade
    @subscene
    def trace(self):
        self._setup_trace()
        # the five impossible slots faded out in o and stay empty — dimming them
        # here would bring them back at DIM
        keep = {_slot(c) for c in TRACE} | {_slot(c) for c in IMPOSSIBLE}
        self.play(FadeIn(self.trace_letters),
                  *[r.tiles.animate.set_opacity(DIM)
                    for i, r in enumerate(self.grid) if i not in keep],
                  run_time=1.0)
