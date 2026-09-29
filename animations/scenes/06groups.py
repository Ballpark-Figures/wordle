"""Scene 06 — the candidates for best opener, read off the colour groups. Navy
background.

Talking head THD sits between 05 and here, so GROUP's groups are up from frame 0
(setup_scene), decoded, with a scored GROUP row atop each, chosen and laid out
as 04i does for PIGGY (size targets, whole groups hung off the edges)
exactly (the header room re-seeds the scatter). No pigpen anywhere in this scene.
The script says PIGGY; GROUP, for scene 06 only, is the user's call (2026-09-28;
it was CODES arranged as in 04e before that — GROUP has no 04 arrangement).

BEAT MAP — one subscene per Script.md beat, letters matching:

  a group_groups — GROUP's groups, decoded, scored rows on top, held    (06a, VO 1)
  b dots         — every answer word shrinks into a dot; then all 98 groups
                   come onto the frame, each scored GROUP row resized to
                   sqrt(size) dot pitches wide. The dots and rows on screen
                   move to their new spots; everything else (every hidden
                   member, every group that was off screen) slides in from
                   beyond the edge; GROUP moves to the top-left corner  (06b, VO 1)
  c trace        — the corner GROUP and every GROUP row turn over to TRACE
                   (a shared pattern keeps its colours, so only the letters
                   change); then every dot moves to its TRACE group, the rows
                   TRACE never makes slide off, the rows only TRACE makes
                   slide in                                              (06c, VO 1)
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
  scored GROUP rows     assets/groups.py `scored_headers` (a), `scored_row` (b, c)
  the flip to TRACE/ROATE  assets/pigpen.py `reletter` — GlyphFlip, letter to letter
  definitions, lists    crisp_text, white, FadeIn; words verbatim from column 2,
                        italics from the Doc; listed words are PigpenWord rows
  dot layout (b)        assets/groups.py `dot_layout`: 04's scatter, every group
  guess on top          GUESS_Y / GUESS_SCALE from assets/groups.py, as 04i
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`, from
                        math/wordle.py `pattern`
The only on-screen text beyond the words is 06d's definition, which column 2
names. The spoken numbers (60, 168, 114 …) are not shown.

LAYOUT CHOICES, flagged:
  - Dots are WHITE (the letters' colour); the script names no colour.
  - A dot row's tile stroke shrinks in proportion to its width against 04i's
    header width HEADER_W (capped at the board's STROKE), or tiny rows are all stroke.
  - With GROUP moved to the top-left corner, the dot groups spread over the WHOLE
    frame (groups.py DOT_REGION_TOP) but for that corner (user's call).
  - The corner label keeps its 06a size.
  - Definitions are broken into lines BY HAND (GLOSSES), left-aligned under their
    word: 28pt under the corner word, 20pt under a listed word. Italics are
    the Doc's ("n", and "rote" in ROATE's). ROATE's comes out "n. Obsolete" /
    "variant of rote".
  - The listed tied words (06e and 06f, bottom left) are decoded tile
    rows at 0.8 of scene 04's list size, in the script's order.
  - Notes belong to the corner word they annotate: when it flips, its notes fade
    out during the shuffle as the new word's fade in. (The script does not say
    whether the ARISE list stays into 06f; it goes with ARISE.)
  - A switch (c, d) is kept calm (user's call): a pattern both words make keeps
    its row where it was (pattern anchoring, groups.py `anchors`), and rows leave
    and arrive by their NEAREST edge. 06b's entrances still come radially.
  - From 06c on a dot is ONE ANSWER OF ITS GROUP, not a particular word (user's
    call): every group always has exactly as many dots as answers, but a switch
    matches the dots on screen to the new slots by least total squared distance
    (scipy linear_sum_assignment), so most move only locally. MEASURED for
    CODES to TRACE (when 06 opened on CODES): median dot move 1.31 (5.85 with
    each dot tied to its word),
    90% under 2.47; the matching takes ~4 s at setup.
  - The corner word and every note keep CORNER_MARGIN of clear space round them;
    no dot or row enters it.
  - What enters comes from beyond the frame's edge, a group's row and hidden
    members together, along the line from the group region's centre out through
    where they land.
"""
from pathlib import Path
import re
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import STROKE
from assets.pigpen import PigpenWord, reletter
from assets.groups import (layout, scored_headers, scored_row, dot_layout, GUESS_Y,
                           GUESS_SCALE, HEADER_W, REGION_BOT, DOT_REGION_TOP)
from assets import lists_data
from scipy.optimize import linear_sum_assignment

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
ENTER_FROM = np.array([0.0, (DOT_REGION_TOP + REGION_BOT) / 2, 0.0])
ENTER_DIST = 10.0          # how far beyond its spot an entering group starts
CORNER_BUFF = 0.3          # the corner label's gap to the frame's edges
CORNER_MARGIN = 0.35       # clear space kept round the corner word (and definition)
EDGE_CLEAR = 0.3           # how far past its nearest edge a switch's row goes


def _keepout(mob):
    """The box ((x, y), w, h) the dot groups keep clear of round `mob` — its bounds
    plus CORNER_MARGIN on every side."""
    c = mob.get_center()
    return ((c[0], c[1]), mob.width + 2 * CORNER_MARGIN, mob.height + 2 * CORNER_MARGIN)


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
        self.corner_box = _keepout(self.guess.copy().move_to(self.corner))

    # a : GROUP's groups, held — its VO plays over the framework's holds
    @subscene
    def group_groups(self):
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
    #     GROUP row sqrt(size) dot pitches wide; GROUP to the top-left corner
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

    # ── switching words: one guess's groups to another's (06c TRACE, 06d ROATE) ──
    def _setup_switch(self, word, blocked):
        """Build the switch to `word`: its dot layout (keeping `blocked` clear), its
        rows, the corner word and each shared row as `word` in place — their letters
        are the flip's new faces — and the rows leaving and arriving."""
        groups, spots, pos, widths, r = dot_layout(
            DATA, word, blocked=blocked,
            anchors={c: row.get_center() for c, row in self.rows.items()})
        assert len(spots) == sum(g["size"] for g in groups) == DATA["n_answers"]
        self.t_scale, self.dot_r = r / self.dot_r, r
        # a dot stands for ONE ANSWER IN ITS GROUP, not for a particular word, so
        # each group gets exactly as many dots as it has answers but any dot may
        # fill any slot: the dots on screen are matched to the new slots by least
        # total squared distance, so most move only locally and the surplus travels
        dots, words = list(self.dots.values()), list(spots)
        a = np.array([d.get_center()[:2] for d in dots])
        b = np.array([spots[w][:2] for w in words])
        i, j = linear_sum_assignment(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1))
        self.moves = [(dots[p], spots[words[q]]) for p, q in zip(i, j)]
        self.t_dots = {words[q]: dots[p] for p, q in zip(i, j)}
        self.t_rows = {g["code"]: scored_row(word, g["code"], wd, c,
                                             stroke=STROKE * min(1.0, wd / HEADER_W))
                       for g, c, wd in zip(groups, pos, widths)}
        self.t_word = PigpenWord(word, revealed=True).scale(GUESS_SCALE) \
            .move_to(self.guess)
        self.stay = {c: scored_row(word, c, row.width, row.get_center(),
                                   stroke=row.tiles[0][0].get_stroke_width())
                     for c, row in self.rows.items() if c in self.t_rows}
        self.leave = {c: row for c, row in self.rows.items() if c not in self.t_rows}
        # the rows only `word` makes start just beyond their nearest edge
        self.enter = [(self.t_rows[c], self.t_rows[c].get_center())
                      for c in self.t_rows if c not in self.rows]
        for row, home in self.enter:
            row.move_to(self._edge_out(row))

    def _outward(self, mob):
        d = mob.get_center() - ENTER_FROM
        return mob.get_center() + d / (np.linalg.norm(d) or 1.0) * ENTER_DIST

    def _edge_out(self, mob):
        """Just beyond the frame edge NEAREST `mob`, straight out — a switch's rows
        leave and arrive this way, so none crosses the frame."""
        c = mob.get_center()
        X, Y = config.frame_x_radius, config.frame_y_radius
        gaps = [(X - c[0], RIGHT, mob.width), (X + c[0], LEFT, mob.width),
                (Y - c[1], UP, mob.height), (Y + c[1], DOWN, mob.height)]
        d, v, size = min(gaps, key=lambda g: g[0])
        return c + v * (d + size / 2 + EDGE_CLEAR)

    def _flip(self, run_time):
        """The corner word and every shared row turn over to the new word."""
        faces = [*self.t_word.letters, *[l for r in self.stay.values() for l in r.letters[0]]]
        for f in faces:
            f.set_fill(opacity=0)
        self.add(*faces)
        flips = [reletter(self.guess.tiles, self.guess.letters, self.t_word.letters, run_time),
                 *[reletter(self.rows[c].tiles[0], self.rows[c].letters[0],
                            row.letters[0], run_time) for c, row in self.stay.items()]]
        self.play(*flips, run_time=run_time)
        # swap the flipped words for the new ones they now look like — and drop
        # the flips' own tile+letters groups, which play() added to the scene and
        # which would otherwise keep the old tiles on screen
        self.remove(*[f.mobject for lag in flips for f in lag.animations])
        self.remove(self.guess, *[self.rows[c] for c in self.stay], *faces)
        self.add(self.t_word, *self.stay.values())
        self.guess = self.t_word

    def _regroup(self, run_time, extra=()):
        """Every dot to its matched slot; shared rows resize and move, the rest
        leave off the edge or arrive from beyond it. `extra` animations join in."""
        self.play(*extra,
                  *[d.animate.move_to(c).scale(self.t_scale) for d, c in self.moves],
                  *[Transform(row, self.t_rows[c]) for c, row in self.stay.items()],
                  *[row.animate.move_to(self._edge_out(row)) for row in self.leave.values()],
                  *[row.animate.move_to(home) for row, home in self.enter],
                  run_time=run_time)
        self.remove(*self.stay.values(), *self.leave.values())
        self.add(*[self.t_rows[c] for c in self.stay])
        self.rows, self.dots = self.t_rows, self.t_dots
        self.t_word = self.stay = self.leave = self.enter = self.t_rows = None
        self.moves = self.t_dots = None

    # c : GROUP turns over to TRACE, in the corner and on every row; then the dots
    #     regroup into TRACE's groups, rows leaving and arriving
    @subscene
    def trace(self):
        self._setup_switch(TRACE, [self.corner_box])
        self._flip(1.0)
        self._regroup(2.0)

    # ── notes: a definition under a word, a list of words (06d-f) ─────────────
    def _setup_notes(self, word, notes, blocked):
        """The switch to `word`, with `notes` (placed mobjects) replacing the notes
        on screen; the new layout keeps `blocked` clear."""
        self.old_notes, self.notes = self.notes, notes
        self._setup_switch(word, blocked)

    def _switch_notes(self, flip_run_time, regroup_run_time):
        """Flip, then shuffle with the old notes fading out and the new fading in."""
        self._flip(flip_run_time)
        self._regroup(regroup_run_time,
                      extra=[*[FadeOut(n) for n in self.old_notes],
                             *[FadeIn(n) for n in self.notes]])
        self.old_notes = None

    def _setup_roate(self):
        gloss = _gloss(*GLOSSES[ROATE], GLOSS_FS) \
            .next_to(self.guess, DOWN, buff=GLOSS_BUFF, aligned_edge=LEFT)
        self._setup_notes(ROATE, [gloss], [_keepout(VGroup(self.guess, gloss))])

    # d : TRACE turns over to ROATE and the dots regroup, the same way; its
    #     definition fades in during the shuffle
    @subscene
    def roate(self):
        self._setup_roate()
        self._switch_notes(1.0, 2.0)

    def _setup_arise(self):
        ties = _entries(ARISE_TIES).to_corner(DL, buff=CORNER_BUFF)
        self._setup_notes(ARISE, [ties], [self.corner_box, _keepout(ties)])

    # e : ROATE turns over to ARISE and the dots regroup; ROATE's definition fades
    #     out and the other four tied words fade in at the bottom left
    @subscene
    def arise(self):
        self._setup_arise()
        self._switch_notes(1.0, 2.0)

    def _setup_aurei(self):
        gloss = _gloss(*GLOSSES[AUREI], GLOSS_FS) \
            .next_to(self.guess, DOWN, buff=GLOSS_BUFF, aligned_edge=LEFT)
        other = _entries(AUREI_TIES).to_corner(DL, buff=CORNER_BUFF)
        self._setup_notes(AUREI, [gloss, other],
                          [_keepout(VGroup(self.guess, gloss)), _keepout(other)])

    # f : ARISE turns over to AUREI and the dots regroup; the ARISE list fades out,
    #     AUREI's definition fades in, and URAEI with its own at the bottom left
    @subscene
    def aurei(self):
        self._setup_aurei()
        self._switch_notes(1.0, 2.0)
