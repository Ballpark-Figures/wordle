"""Scene 06 — the candidates for best opener, read off the colour groups. Navy
background.

Talking head THD sits between 05 and here, so CODES's groups are up from frame 0
(setup_scene): 04e's CODES groups (the carry-over set), but DECODED and with a
scored CODES row atop each, as 04i does for PIGGY — so the frame is NOT 04e's
exactly (the header room re-seeds the scatter). No pigpen anywhere in this scene.
The script says PIGGY; CODES, arranged as in 04e, is the user's call (2026-09-28).

BEAT MAP — one subscene per Script.md beat, letters matching:

  a codes_groups — CODES's groups, decoded, scored rows on top, held    (06a, VO 1)
  b dots         — every answer word shrinks into a dot; then all 98 groups
                   come onto the frame, each scored CODES row resized to
                   sqrt(size) dot pitches wide. The dots and rows on screen
                   move to their new spots; everything else (every hidden
                   member, every group that was off screen) slides in from
                   beyond the edge; CODES moves to the top-left corner  (06b, VO 1)
  c trace        — the corner CODES and every CODES row turn over to TRACE
                   (a shared pattern keeps its colours, so only the letters
                   change); then every dot moves to its TRACE group, the rows
                   TRACE never makes slide off, the rows only TRACE makes
                   slide in                                              (06c, VO 1)

REUSE MAP — every element and the one source it comes from:
  group layout (a)      assets/groups.py `layout(chain=True, header=True)`
  answer words, guess   assets/pigpen.py `PigpenWord(revealed=True)`, sized as 04i
  scored CODES rows     assets/groups.py `scored_headers` (a), `scored_row` (b, c)
  the flip to TRACE     assets/pigpen.py `reletter` — GlyphFlip, letter to letter
  dot layout (b)        assets/groups.py `dot_layout`: 04's scatter, every group
  guess on top          GUESS_Y / GUESS_SCALE from assets/groups.py, as 04e
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`, from
                        math/wordle.py `pattern`
No on-screen text: 06a's numbers (60, 168, 114 …) are spoken, not shown.

LAYOUT CHOICES, flagged:
  - Dots are WHITE (the letters' colour); the script names no colour.
  - A dot row's tile stroke shrinks in proportion to its width against 04i's
    header width HEADER_W (capped at the board's STROKE), or tiny rows are all stroke.
  - With CODES moved to the top-left corner, the dot groups spread over the WHOLE
    frame (groups.py DOT_REGION_TOP) but for that corner (user's call).
  - The corner label keeps its 06a size.
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
from assets.pigpen import PigpenWord, reletter
from assets.groups import (layout, scored_headers, scored_row, dot_layout, GUESS_Y,
                           GUESS_SCALE, HEADER_W, REGION_BOT, DOT_REGION_TOP)
from assets import lists_data

DATA = lists_data.load()
GUESS = DATA["guesses"][2]                         # codes — 04e's last guess
TRACE = "trace"            # 06c's word — the script's own choice

DOT_COLOR = WHITE
ENTER_FROM = np.array([0.0, (DOT_REGION_TOP + REGION_BOT) / 2, 0.0])
ENTER_DIST = 10.0          # how far beyond its spot an entering group starts
CORNER_BUFF = 0.3          # the corner label's gap to the frame's edges


class Scene06(WordleBoardScene):
    """BEAT MAP
    codes_groups — CODES's groups, decoded and scored, held
    dots — words to dots; all 98 groups on the frame, rows sized by sqrt(size)
    trace — CODES flips to TRACE; the dots regroup into TRACE's 150 groups
    """

    def setup_scene(self):
        self.guess = PigpenWord(GUESS, revealed=True).scale(GUESS_SCALE) \
            .move_to([0, GUESS_Y, 0])
        slots, gscale, heads, groups = layout(DATA, GUESS, header=True, chain=True)
        self.words = {w: PigpenWord(w, revealed=True).scale(gscale).move_to(c)
                      for w, c in slots.items()}
        self.heads = dict(zip((g["code"] for g in groups),
                              scored_headers(GUESS, groups, heads, gscale)))
        self.add(self.guess, *self.words.values(), *self.heads.values())
        # where the guess goes in 06b, and the box the dot groups keep clear of
        w, h = self.guess.width, self.guess.height
        self.corner = np.array([-config.frame_x_radius + CORNER_BUFF + w / 2,
                                config.frame_y_radius - CORNER_BUFF - h / 2, 0.0])
        self.corner_box = ((self.corner[0], self.corner[1]), w, h)

    # a : CODES's groups, held — its VO plays over the framework's holds
    @subscene
    def codes_groups(self):
        pass

    def _setup_dots(self):
        groups, spots, rows, widths, r = dot_layout(DATA, GUESS, blocked=[self.corner_box])
        self.dot_r = r
        # every answer is a dot, in exactly one group
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.dots = {w: Dot(point=c, radius=r, color=DOT_COLOR)
                     for w, c in spots.items()}
        # each shown word's dot starts where the word is
        self.word_dots = {w: Dot(point=m.get_center(), radius=r, color=DOT_COLOR)
                          for w, m in self.words.items()}
        self.rows = {g["code"]: scored_row(GUESS, g["code"], wd, c,
                                           stroke=STROKE * min(1.0, wd / HEADER_W))
                     for g, c, wd in zip(groups, rows, widths)}
        # everything not yet on screen starts beyond the edge and slides in: a group
        # on screen brings its hidden members, a group off screen its row and dots
        self.incoming = []
        for g in groups:
            shown = g["code"] in self.heads
            grp = VGroup(*([] if shown else [self.rows[g["code"]]]),
                         *[self.dots[w] for w in g["members"] if w not in self.words])
            if not len(grp):
                continue
            d = grp.get_center() - ENTER_FROM
            d = d / (np.linalg.norm(d) or 1.0)
            self.incoming.append((grp, grp.get_center()))
            grp.shift(d * ENTER_DIST)

    # b : every word shrinks into a dot; then all 98 groups onto the frame, each
    #     CODES row sqrt(size) dot pitches wide; CODES to the top-left corner
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
                  self.guess.animate.move_to(self.corner),
                  run_time=2.0)
        # swap the moved stand-ins for the real dots and rows, so each group is
        # one set of mobjects from here on
        self.remove(*self.word_dots.values(), *self.heads.values())
        # unwrap the slide-in groups, so every row and dot is top-level: removing a
        # row inside one would leave it on screen (06c's flip hit exactly that)
        for grp, _ in self.incoming:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.add(*[self.dots[w] for w in self.word_dots], *[self.rows[c] for c in self.heads])
        self.word_dots = self.heads = self.incoming = None

    def _setup_trace(self):
        groups, spots, pos, widths, r = dot_layout(DATA, TRACE, blocked=[self.corner_box])
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.t_spots, self.t_scale = spots, r / self.dot_r
        self.t_rows = {g["code"]: scored_row(TRACE, g["code"], wd, c,
                                             stroke=STROKE * min(1.0, wd / HEADER_W))
                       for g, c, wd in zip(groups, pos, widths)}
        # the corner word, and each row TRACE shares with CODES, as TRACE in place:
        # its letters are the flip's new faces
        self.t_word = PigpenWord(TRACE, revealed=True).scale(GUESS_SCALE) \
            .move_to(self.guess)
        self.stay = {c: scored_row(TRACE, c, row.width, row.get_center(),
                                   stroke=row.tiles[0][0].get_stroke_width())
                     for c, row in self.rows.items() if c in self.t_rows}
        self.leave = {c: row for c, row in self.rows.items() if c not in self.t_rows}
        # the rows only TRACE makes start beyond the edge
        self.enter = [(self.t_rows[c], self.t_rows[c].get_center())
                      for c in self.t_rows if c not in self.rows]
        for row, home in self.enter:
            row.move_to(self._outward(row))

    def _outward(self, mob):
        d = mob.get_center() - ENTER_FROM
        return mob.get_center() + d / (np.linalg.norm(d) or 1.0) * ENTER_DIST

    # c : CODES turns over to TRACE, in the corner and on every row; then the dots
    #     regroup into TRACE's groups, rows leaving and arriving
    @subscene
    def trace(self):
        self._setup_trace()
        faces = [*self.t_word.letters, *[l for r in self.stay.values() for l in r.letters[0]]]
        for f in faces:
            f.set_fill(opacity=0)
        self.add(*faces)
        flips = [reletter(self.guess.tiles, self.guess.letters, self.t_word.letters, 1.0),
                 *[reletter(self.rows[c].tiles[0], self.rows[c].letters[0],
                            row.letters[0], 1.0) for c, row in self.stay.items()]]
        self.play(*flips, run_time=1.0)
        # swap the flipped words for the TRACE ones they now look like — and drop
        # the flips' own tile+letters groups, which play() added to the scene and
        # which would otherwise keep the old tiles on screen
        self.remove(*[f.mobject for lag in flips for f in lag.animations])
        self.remove(self.guess, *[self.rows[c] for c in self.stay], *faces)
        self.add(self.t_word, *self.stay.values())
        self.guess = self.t_word

        self.play(*[d.animate.move_to(self.t_spots[w]).scale(self.t_scale)
                    for w, d in self.dots.items()],
                  *[Transform(row, self.t_rows[c]) for c, row in self.stay.items()],
                  *[row.animate.move_to(self._outward(row)) for row in self.leave.values()],
                  *[row.animate.move_to(home) for row, home in self.enter],
                  run_time=2.0)
        self.remove(*self.stay.values(), *self.leave.values())
        self.add(*[self.t_rows[c] for c in self.stay])
        self.rows = self.t_rows
        self.t_word = self.stay = self.leave = self.enter = self.t_rows = None
