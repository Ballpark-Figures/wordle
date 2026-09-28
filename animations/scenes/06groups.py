"""Scene 06 — the candidates for best opener, read off the colour groups. Navy
background.

Talking head THD sits between 05 and here, so CODES's groups are up from frame 0
(setup_scene) — 04e's end frame exactly (pigpen, no scored rows), built by the
same layout code. The script says PIGGY; CODES, arranged as in 04e, is the user's
call (2026-09-28).

BEAT MAP — one subscene per Script.md beat, letters matching:

  a codes_groups — CODES's groups as 04e left them, held               (06a, VO 1)
  b dots         — every answer word shrinks into a dot; then all 98 groups
                   come onto the frame, each with a scored CODES row
                   sqrt(size) dot pitches wide. The dots on screen move to
                   their new spots; everything else (every row, every hidden
                   member, every group that was off screen) slides in from
                   beyond the edge; CODES leaves off the top            (06b, VO 1)

REUSE MAP — every element and the one source it comes from:
  group layout (a)      assets/groups.py `layout(chain=True)` — 04e's own call, same seed
  answer words, guess   assets/pigpen.py `PigpenWord`, sized as 04's `_to` / 04e's guess
  scored CODES rows     assets/groups.py `scored_row` (board.py `get_scored_row`)
  dot layout (b)        assets/groups.py `dot_layout`: 04's scatter, every group
  guess on top          GUESS_Y / GUESS_SCALE from assets/groups.py, as 04e
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`, from
                        math/wordle.py `pattern`
No on-screen text: 06a's numbers (60, 168, 114 …) are spoken, not shown.

LAYOUT CHOICES, flagged:
  - Dots are WHITE (the pigpen ink); the script names no colour.
  - A dot row's tile stroke shrinks in proportion to its width against 04i's
    header width HEADER_W (capped at the board's STROKE), or tiny rows are all stroke.
  - What enters comes from beyond the frame's edge, a group's row and hidden
    members together, along the line from the group region's centre out through
    where they land.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import STROKE
from assets.pigpen import PigpenWord
from assets.groups import (layout, scored_row, dot_layout, GUESS_Y, GUESS_SCALE,
                           HEADER_W, REGION_TOP, REGION_BOT)
from assets import lists_data

DATA = lists_data.load()
GUESS = DATA["guesses"][2]                         # codes — 04e's last guess

DOT_COLOR = WHITE
ENTER_FROM = np.array([0.0, (REGION_TOP + REGION_BOT) / 2, 0.0])
ENTER_DIST = 10.0          # how far beyond its spot an entering group starts


class Scene06(WordleBoardScene):
    """BEAT MAP
    codes_groups — CODES's groups, held (04e's end frame)
    dots — words to dots; all 98 groups on the frame, rows sized by sqrt(size)
    """

    def setup_scene(self):
        self.guess = PigpenWord(GUESS).scale(GUESS_SCALE).set_glyph_stroke(GUESS_SCALE) \
            .move_to([0, GUESS_Y, 0])
        slots, gscale, _, _ = layout(DATA, GUESS, chain=True)
        self.words = {w: PigpenWord(w).scale(gscale).set_glyph_stroke(gscale).move_to(c)
                      for w, c in slots.items()}
        self.add(self.guess, *self.words.values())

    # a : CODES's groups, held — its VO plays over the framework's holds
    @subscene
    def codes_groups(self):
        pass

    def _setup_dots(self):
        groups, spots, rows, widths, r = dot_layout(DATA, GUESS)
        # every answer is a dot, in exactly one group
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.dots = {w: Dot(point=c, radius=r, color=DOT_COLOR)
                     for w, c in spots.items()}
        # each shown word's dot starts where the word is
        self.word_dots = {w: Dot(point=m.get_center(), radius=r, color=DOT_COLOR)
                          for w, m in self.words.items()}
        rows = {g["code"]: scored_row(GUESS, g["code"], wd, c,
                                      stroke=STROKE * min(1.0, wd / HEADER_W))
                for g, c, wd in zip(groups, rows, widths)}
        # everything not yet on screen starts beyond the edge and slides in: each
        # group's row, with its members not already on screen as words
        self.incoming = []
        for g in groups:
            grp = VGroup(rows[g["code"]],
                         *[self.dots[w] for w in g["members"] if w not in self.words])
            d = grp.get_center() - ENTER_FROM
            d = d / (np.linalg.norm(d) or 1.0)
            self.incoming.append((grp, grp.get_center()))
            grp.shift(d * ENTER_DIST)

    # b : every word shrinks into a dot; then all 98 groups onto the frame, each
    #     CODES row sqrt(size) dot pitches wide; CODES off the top
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
                  *[grp.animate.move_to(c) for grp, c in self.incoming],
                  self.guess.animate.move_to(
                      [0, config.frame_y_radius + self.guess.height, 0]),
                  run_time=2.0)
        # swap the moved stand-ins for the real dots, so each group is one set of
        # mobjects from here on
        self.remove(*self.word_dots.values(), self.guess)
        self.add(*[self.dots[w] for w in self.word_dots])
        self.word_dots = self.incoming = self.guess = None
