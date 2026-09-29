"""Scene 06 — the candidates for best opener, read off the colour groups. Navy
background.

Talking head THD sits between 05 and here, so GROUP's groups are up from frame 0
(setup_scene), decoded, with a scored GROUP row atop each, chosen and laid out as
04i does for PIGGY (size targets, whole groups hung off the edges). No pigpen
anywhere in this scene. The script says PIGGY; GROUP, for scene 06 only, is the
user's call (2026-09-28).

THIS IS THE SORTED VERSION (user's call, 2026-09-28). The scattered one — groups
anywhere on the frame, pattern-anchored, dots matched by distance — is commit
4ee7924a. Here the groups are packed in rows BY SIZE, largest first, right of an
empty column under the corner word; the column holds only the notes.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a group_groups — GROUP's groups, decoded, scored rows on top, held    (06a, VO 1)
  b dots         — every answer word shrinks into a dot; then all 98 groups
                   come onto the frame SORTED BY SIZE, each scored GROUP row
                   sqrt(size) dot pitches wide. The dots and rows on screen
                   move to their new spots; everything else (every hidden
                   member, every group that was off screen) slides in from
                   beyond the edge; GROUP moves to the top-left corner  (06b, VO 1)
  c trace        — all at once: the corner GROUP flips to TRACE; slot by slot
                   every row flips to TRACE's colouring of that rank WHILE it
                   travels to its new slot; the dots flow along the order into
                   TRACE's sizes; the slots TRACE has beyond GROUP's 98 arrive
                   from the nearest edge                                 (06c, VO 1)
  d roate        — the same switch to ROATE, with "n. Obsolete variant of
                   rote" fading in under the corner word during the shuffle (06d, VO 2)
  e arise        — the same switch to ARISE; ROATE's definition fades out and
                   the other four tied words (RAISE, AESIR, REAIS, SERAI, three
                   with definitions) fade in at the bottom left          (06e, VO 3)
  f aurei        — the same switch to AUREI; the ARISE list fades out, AUREI's
                   definition fades in under it and URAEI with its own at the
                   bottom left                                           (06f, VO 4)

REUSE MAP — every element and the one source it comes from:
  group layout (a)      assets/groups.py `layout(header=True)` — 04i's rule
  answer words, guess   assets/pigpen.py `PigpenWord(revealed=True)`, sized as 04i
  scored rows           assets/groups.py `scored_headers` (a), `scored_row` (b-f)
  sorted dot layout     assets/groups.py `ranked_layout` (b-f)
  every flip            assets/flip.py `flip` — anything into anything
  entrances, exits      assets/groups.py `enter_from_beyond` (b), `edge_out` (c-f)
  definitions, lists    crisp_text, white, FadeIn; words verbatim from column 2,
                        italics from the Doc; listed words are PigpenWord rows
  guess on top          GUESS_Y / GUESS_SCALE from assets/groups.py, as 04i
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`, from
                        math/wordle.py `pattern`
The only on-screen text beyond the words is the definitions, which column 2
names. The spoken numbers (60, 168, 114 …) are not shown.

LAYOUT CHOICES, flagged:
  - Dots are WHITE (the letters' colour); the script names no colour.
  - A dot row's tile stroke shrinks in proportion to its width against 04i's
    header width HEADER_W (capped at the board's STROKE), or tiny rows are all stroke.
  - The corner label keeps its 06a size.
  - Sorted rows are top-aligned, so a row's scored words line up, and spread to
    fill the width (the last row excepted); ties in size go by pattern code.
  - A switch FLIPS rather than shuffles (user's call): slot k is always the k-th
    largest group, so each slot both words have flips its row, colour and
    letters, while it slides and resizes to the new layout — one motion. Only the slots past the end of the shorter list
    travel, by their NEAREST edge. 06b's entrances still come radially.
  - A dot is ONE ANSWER OF ITS GROUP, not a particular word (user's call): the
    dots are one sequence in rank order, group by group, and dot j takes slot j
    of the new layout — so dots pass only between neighbouring groups in the
    order (a row's end to the next row's start included), as few as the changed
    sizes require.
  - Definitions are broken into lines BY HAND (GLOSSES), left-aligned under their
    word: 28pt under the corner word, 20pt under a listed word. Italics are
    the Doc's ("n", and "rote" in ROATE's).
  - The listed tied words (06e and 06f, bottom left) are decoded tile rows at 0.8
    of scene 04's list size, in the script's order.
  - Notes belong to the corner word they annotate: when it flips, its notes fade
    out during the shuffle as the new word's fade in. (The script does not say
    whether the ARISE list stays into 06f; it goes with ARISE.)
  - The groups keep CORNER_MARGIN clear of the corner word's column.
"""
from pathlib import Path
import re
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import STROKE
from assets.pigpen import PigpenWord
from assets.flip import Flip, flip, row_parts
from assets.groups import (layout, scored_headers, scored_row, ranked_layout, GUESS_Y,
                           GUESS_SCALE, HEADER_W, enter_from_beyond, edge_out)
from assets import lists_data

DATA = lists_data.load()
GUESS = "group"            # 06a's word — the user's choice, scene 06 only
TRACE = "trace"            # 06c's word — the script's own choice
ROATE = "roate"            # 06d-f's words — the script's own choices
ARISE = "arise"
AUREI = "aurei"
ARISE_TIES = ["raise", "aesir", "reais", "serai"]   # 06e's list, the script's order
AUREI_TIES = ["uraei"]                              # 06f, bottom left
# 06d's definition, verbatim from the script, on two lines so it is no wider than
# the definitions, verbatim from the script, broken into lines by hand so no line
# is wider than the word above it (only "n. Representation" is, being one word),
# with the words the Doc italicises
GLOSSES = {
    "roate": (["n. Obsolete", "variant of rote"], ["n", "rote"]),
    "aesir": (["n. A group of", "Norse Gods", "associated", "with war"], ["n"]),
    "reais": (["n. Plural of", "Real (Brazilian", "currency)"], ["n"]),
    "serai": (["n. A palace or", "inn (Turkey/", "Middle East)"], ["n"]),
    "aurei": (["n. Plural of", "Aureus (Roman", "gold coin)"], ["n"]),
    "uraei": (["n. Representation", "of the sacred", "asp (ancient", "Egypt)"], ["n"]),
}
GLOSS_LINE_BUFF = 0.1
GLOSS_FS = 28              # under the corner word
GLOSS_BUFF = 0.15          # between a word and its definition
LIST_SCALE = 0.8           # a listed word's size (1 = scene 04's list size)
LIST_FS = 20               # a listed word's definition
LIST_GAP = 0.25            # between two listed entries

DOT_COLOR = WHITE
CORNER_BUFF = 0.3          # the corner label's gap to the frame's edges
CORNER_MARGIN = 0.35       # clear space kept round the corner word (and definition)


def _gloss(lines, italic, font_size):
    """A definition, one crisp_text per line, left-aligned; whole words in
    `italic` set italic."""
    def slices(line):
        return {f"[{m.start()}:{m.end()}]": ITALIC for it in italic
                for m in re.finditer(rf"\b{re.escape(it)}\b", line)}
    return VGroup(*[crisp_text(l, font_size=font_size, color=WHITE, t2s=slices(l))
                    for l in lines]).arrange(DOWN, buff=GLOSS_LINE_BUFF, aligned_edge=LEFT)


def _entries(words):
    """A column of listed words, each a decoded tile row with its definition (if the
    script gives one) under it; left-aligned."""
    out = []
    for w in words:
        row = PigpenWord(w, revealed=True).scale(LIST_SCALE)
        if w in GLOSSES:
            g = _gloss(*GLOSSES[w], LIST_FS)
            out.append(VGroup(row, g.next_to(row, DOWN, buff=GLOSS_BUFF, aligned_edge=LEFT)))
        else:
            out.append(VGroup(row))
    return VGroup(*out).arrange(DOWN, buff=LIST_GAP, aligned_edge=LEFT)


class Scene06(WordleBoardScene):
    """BEAT MAP
    group_groups — GROUP's groups, decoded and scored, held
    dots — words to dots; all 98 groups on the frame, rows sized by sqrt(size)
    trace — GROUP flips to TRACE; the dots regroup into TRACE's 150 groups
    roate — TRACE flips to ROATE, the dots regroup; its definition fades in
    arise — ROATE flips to ARISE; the other four tied words at the bottom left
    aurei — ARISE flips to AUREI with its definition; URAEI at the bottom left
    """

    def setup_scene(self):
        self.notes = []            # definitions / lists beside the corner word (d-f)
        self.guess = PigpenWord(GUESS, revealed=True).scale(GUESS_SCALE) \
            .move_to([0, GUESS_Y, 0])
        slots, gscale, heads, groups = layout(DATA, GUESS, header=True)
        self.words = {w: PigpenWord(w, revealed=True).scale(gscale).move_to(c)
                      for w, c in slots.items()}
        self.heads = dict(zip((g["code"] for g in groups),
                              scored_headers(GUESS, groups, heads, gscale)))
        self.add(self.guess, *self.words.values(), *self.heads.values())
        # where the guess goes in 06b, and the box the dot groups keep clear of
        w, h = self.guess.width, self.guess.height
        self.corner = np.array([-config.frame_x_radius + CORNER_BUFF + w / 2,
                                config.frame_y_radius - CORNER_BUFF - h / 2, 0.0])
        # the column under the corner word is kept for the notes: the groups sit
        # right of it, CORNER_MARGIN clear of the word
        self.col_left = self.corner[0] + w / 2 + CORNER_MARGIN

    # a : GROUP's groups, held — its VO plays over the framework's holds
    @subscene
    def group_groups(self):
        pass

    def _setup_dots(self):
        groups, spots, rows, widths, r = ranked_layout(DATA, GUESS, left=self.col_left)
        self.dot_r = r
        # every answer is a dot, in exactly one group
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.dots = {w: Dot(point=c, radius=r, color=DOT_COLOR)
                     for w, c in spots.items()}
        # the dots in rank order, group by group — the SEQUENCE a switch moves them along
        self.seq = [self.dots[w] for w in spots]
        # each shown word's dot starts where the word is
        self.word_dots = {w: Dot(point=m.get_center(), radius=r, color=DOT_COLOR)
                          for w, m in self.words.items()}
        self.rows = {g["code"]: scored_row(GUESS, g["code"], wd, c,
                                           stroke=STROKE * min(1.0, wd / HEADER_W))
                     for g, c, wd in zip(groups, rows, widths)}
        self.slots = [self.rows[g["code"]] for g in groups]     # rows in rank order
        # everything not yet on screen starts beyond the edge and slides in: a group
        # on screen brings its hidden members, a group off screen its row and dots
        self.incoming = []
        for g in groups:
            shown = g["code"] in self.heads
            grp = VGroup(*([] if shown else [self.rows[g["code"]]]),
                         *[self.dots[w] for w in g["members"] if w not in self.words])
            if not len(grp):
                continue
            self.incoming.append((grp, enter_from_beyond(grp)))

    # b : every word shrinks into a dot; then all 98 groups onto the frame, sorted
    #     by size, each GROUP row sqrt(size) dot pitches wide; GROUP to the corner
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
        # row inside one would leave it on screen
        for grp, _ in self.incoming:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.add(*[self.dots[w] for w in self.word_dots], *[self.rows[c] for c in self.heads])
        self.word_dots = self.heads = self.incoming = self.rows = self.dots = None

    # ── switching words: one guess's groups to another's (06c-f) ─────────────
    def _setup_switch(self, word):
        """Build the switch to `word`. Slot k is the k-th largest group, so each
        slot both words have keeps its place in the order: its row FLIPS to the new
        colouring while travelling to its new spot. Slots past the end of the
        shorter list leave or arrive by their nearest edge."""
        groups, spots, pos, widths, r = ranked_layout(DATA, word, left=self.col_left)
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.t_scale, self.dot_r = r / self.dot_r, r
        # a dot is ONE ANSWER OF ITS GROUP, not a particular word: dot j of the
        # sequence takes slot j of the new one, so dots pass only between
        # neighbouring groups in the order (row ends included), as few as the
        # changed sizes require
        self.moves = list(zip(self.seq, spots.values()))
        self.t_rows = [scored_row(word, g["code"], wd, c,
                                  stroke=STROKE * min(1.0, wd / HEADER_W))
                       for g, c, wd in zip(groups, pos, widths)]
        self.t_word = PigpenWord(word, revealed=True).scale(GUESS_SCALE) \
            .move_to(self.guess)
        n = min(len(self.slots), len(self.t_rows))
        # slot k (both words have it): its row flips into the new colouring WHILE
        # it travels to the new slot; the corner word flips in place
        self.flips = [Flip(self.guess, self.t_word,
                           parts=(row_parts(self.guess), row_parts(self.t_word))),
                      *[Flip(old, new, parts=(row_parts(old), row_parts(new)), travel=True)
                        for old, new in zip(self.slots[:n], self.t_rows[:n])]]
        self.leave = self.slots[n:]
        # the slots only `word` has start just beyond their nearest edge
        self.enter = [(row, row.get_center()) for row in self.t_rows[n:]]
        for row, home in self.enter:
            row.move_to(edge_out(row))

    def _switch(self, run_time, extra=()):
        """All at once: the corner word and every shared slot flip (the slots while
        travelling to the new layout), every dot flows along the sequence to its
        new slot, the rest of the slots leave off the edge or arrive from beyond
        it. `extra` animations join in."""
        flip(self, self.flips, run_time, extra=[
            *extra,
            *[d.animate.move_to(c).scale(self.t_scale) for d, c in self.moves],
            *[row.animate.move_to(edge_out(row)) for row in self.leave],
            *[row.animate.move_to(home) for row, home in self.enter]])
        self.remove(*self.leave)
        self.guess, self.slots = self.t_word, self.t_rows
        self.t_word = self.flips = self.leave = self.enter = self.t_rows = self.moves = None

    # c : GROUP turns over to TRACE, in the corner and on every shared slot, while
    #     the dots flow into TRACE's sizes and the extra slots arrive at the end
    @subscene
    def trace(self):
        self._setup_switch(TRACE)
        self._switch(2.0)

    # ── notes: a definition under a word, a list of words (06d-f) ─────────────
    def _setup_notes(self, word, notes):
        """The switch to `word`, with `notes` (placed mobjects, in the column under
        the corner word) replacing the notes on screen."""
        self.old_notes, self.notes = self.notes, notes
        self._setup_switch(word)

    def _switch_notes(self, run_time):
        """The switch, with the old notes fading out and the new fading in."""
        self._switch(run_time, extra=[*[FadeOut(n) for n in self.old_notes],
                                      *[FadeIn(n) for n in self.notes]])
        self.old_notes = None

    def _setup_roate(self):
        gloss = _gloss(*GLOSSES[ROATE], GLOSS_FS) \
            .next_to(self.guess, DOWN, buff=GLOSS_BUFF, aligned_edge=LEFT)
        self._setup_notes(ROATE, [gloss])

    # d : TRACE turns over to ROATE and the dots regroup, the same way; its
    #     definition fades in during the shuffle
    @subscene
    def roate(self):
        self._setup_roate()
        self._switch_notes(2.0)

    def _setup_arise(self):
        ties = _entries(ARISE_TIES).to_corner(DL, buff=CORNER_BUFF)
        self._setup_notes(ARISE, [ties])

    # e : ROATE turns over to ARISE and the dots regroup; ROATE's definition fades
    #     out and the other four tied words fade in at the bottom left
    @subscene
    def arise(self):
        self._setup_arise()
        self._switch_notes(2.0)

    def _setup_aurei(self):
        gloss = _gloss(*GLOSSES[AUREI], GLOSS_FS) \
            .next_to(self.guess, DOWN, buff=GLOSS_BUFF, aligned_edge=LEFT)
        other = _entries(AUREI_TIES).to_corner(DL, buff=CORNER_BUFF)
        self._setup_notes(AUREI, [gloss, other])

    # f : ARISE turns over to AUREI and the dots regroup; the ARISE list fades out,
    #     AUREI's definition fades in, and URAEI with its own at the bottom left
    @subscene
    def aurei(self):
        self._setup_aurei()
        self._switch_notes(2.0)
