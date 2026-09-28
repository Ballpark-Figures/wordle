"""Scene 06 — the candidates for best opener, read off the colour groups. Navy
background.

Talking head THD sits between 05 and here, so PIGGY's groups are up from frame 0
(setup_scene) — 04i's end frame exactly, built by the same layout code.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a piggy_groups — PIGGY's groups as 04i left them, held                (06a, VO 1)
  b dots         — every answer word shrinks into a dot; then all 54 groups
                   come onto the frame, each scored PIGGY row resized to
                   sqrt(size) dot pitches wide — the shown groups rearrange,
                   their hidden members fade in, the groups that were off
                   screen slide in from beyond the edge                 (06b, VO 1)

REUSE MAP — every element and the one source it comes from:
  group layout (a)      assets/groups.py `layout` — 04i's own call, same seed
  scored PIGGY rows     assets/groups.py `scored_headers` (a), `scored_row` (b)
  answer words          assets/pigpen.py `PigpenWord`, revealed, sized as 04's `_to`
  dot layout (b)        assets/groups.py `dot_layout`: 04's scatter, every group
  guess on top          GUESS_Y / GUESS_SCALE from assets/groups.py, as 04i
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`, from
                        math/wordle.py `pattern`
No on-screen text: 06a's numbers (60, 168, 114 …) are spoken, not shown.

LAYOUT CHOICES, flagged:
  - Dots are WHITE (the pigpen ink); the script names no colour.
  - A dot row's tile stroke shrinks in proportion to its width against 04i's
    header width (capped at the board's STROKE), or the tiny rows are all stroke.
  - Groups that were off screen enter from beyond the frame's edge, along the line
    from the group region's centre out through where they land.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import STROKE
from assets.pigpen import PigpenWord
from assets.groups import (layout, scored_headers, scored_row, dot_layout,
                           GUESS_Y, GUESS_SCALE, REGION_TOP, REGION_BOT)
from assets import lists_data

DATA = lists_data.load()
GUESS = DATA["guesses"][1]                         # piggy — 04i's guess

DOT_COLOR = WHITE
ENTER_FROM = np.array([0.0, (REGION_TOP + REGION_BOT) / 2, 0.0])
ENTER_DIST = 10.0          # how far beyond its spot an off-screen group starts


class Scene06(WordleBoardScene):
    """BEAT MAP
    piggy_groups — PIGGY's groups, held (04i's end frame)
    dots — words to dots; all 54 groups on the frame, rows sized by sqrt(size)
    """

    def setup_scene(self):
        self.guess = PigpenWord(GUESS, revealed=True).scale(GUESS_SCALE) \
            .move_to([0, GUESS_Y, 0])
        self.slots, gscale, heads, groups = layout(DATA, GUESS, header=True)
        self.words = {w: PigpenWord(w, revealed=True).scale(gscale)
                      .set_glyph_stroke(gscale).move_to(c)
                      for w, c in self.slots.items()}
        self.heads = dict(zip((g["code"] for g in groups),
                              scored_headers(GUESS, groups, heads, gscale)))
        self.add(self.guess, *self.words.values(), *self.heads.values())

    # a : PIGGY's groups, held — its VO plays over the framework's holds
    @subscene
    def piggy_groups(self):
        pass

    def _setup_dots(self):
        groups, spots, rows, widths, r = dot_layout(DATA, GUESS)
        ref = next(iter(self.heads.values())).width      # 04i's header width
        self.dots = {w: Dot(point=c, radius=r, color=DOT_COLOR)
                     for w, c in spots.items()}
        # each shown word's dot starts where the word is
        self.word_dots = {w: Dot(point=m.get_center(), radius=r, color=DOT_COLOR)
                          for w, m in self.words.items()}
        self.rows = {g["code"]: scored_row(GUESS, g["code"], wd, c,
                                           stroke=STROKE * min(1.0, wd / ref))
                     for g, c, wd in zip(groups, rows, widths)}
        # the groups on screen: their rows and dots rearrange, hidden members fade in
        self.fresh = VGroup(*[self.dots[w] for g in groups if g["code"] in self.heads
                              for w in g["members"] if w not in self.words])
        # the groups off screen: row + dots start beyond the edge and slide in
        self.incoming = []
        for g in groups:
            if g["code"] in self.heads:
                continue
            grp = VGroup(self.rows[g["code"]], *[self.dots[w] for w in g["members"]])
            d = grp.get_center() - ENTER_FROM
            d = d / (np.linalg.norm(d) or 1.0)
            self.incoming.append((grp, grp.get_center()))
            grp.shift(d * ENTER_DIST)

    # b : every word shrinks into a dot; then all 54 groups onto the frame, each
    #     PIGGY row sqrt(size) dot pitches wide
    @subscene
    def dots(self):
        self._setup_dots()
        self.play(*[m.animate.scale(0.1).set_opacity(0) for m in self.words.values()],
                  *[GrowFromCenter(d) for d in self.word_dots.values()],
                  run_time=1.0)
        self.remove(*self.words.values())
        self.words = None

        self.play(*[d.animate.move_to(self.dots[w].get_center())
                    for w, d in self.word_dots.items()],
                  *[Transform(h, self.rows[c]) for c, h in self.heads.items()],
                  *[grp.animate.move_to(c) for grp, c in self.incoming],
                  FadeIn(self.fresh), run_time=2.0)
        # swap the moved stand-ins for the real dots and rows, so each group is
        # one set of mobjects from here on
        self.remove(*self.word_dots.values(), *self.heads.values())
        self.add(*[self.dots[w] for w in self.word_dots], *[self.rows[c] for c in self.heads])
        self.word_dots = self.heads = self.fresh = self.incoming = None
