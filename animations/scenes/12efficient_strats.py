"""Scene 12 — a whole strategy is too many decisions; simplification and randomness.
Navy background.

Talking head THH sits before this scene, so SALET (black background, i.e. a typed
row) is up from frame 0 (setup_scene). Scene 13 follows directly, so j ends with
the frame cleared.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a salet        — SALET, black background, in the middle; held          (12a, VO 1)
  b dots         — 06b's dot view with SALET as the starter: SALET to the top-left
                   corner, all 148 groups (scored row + dots) slide in from beyond
                   the edge, sorted by size                                (12b, VO 1)
  c remove_dots  — the dots shrink away, the coloured SALET rows stay     (12c, VO 1)
  d second_words — every optimal second word typed at once, each under its
                   coloured SALET, as wide as that row                   (12d, VO 1)
  e to_lucky     — SALET flips to LUCKY, 06c's switch: each slot's row flips to
                   LUCKY's colouring and its word to LUCKY's second word while both
                   travel to LUCKY's layout; the slots past LUCKY's 77 leave by the
                   nearest edge                                          (12e, VO 2)
  f to_guess     — the same switch, LUCKY to GUESS                        (12f, VO 2)
  g back_to_salet — the same switch, GUESS back to SALET; the slots past GUESS's
                   71 arrive from beyond the nearest edge                (12g, VO 2)
  h by_grays     — the typed words fade; the rows gather into six clusters by
                   their number of greys, an oval round each, that grey count's
                   word at the bottom of its oval                        (12h, VO 3)
  i undo         — back: the ovals and their words fade, the rows return, the
                   typed words fade back in                              (12i, VO 3)
  j random_answers — under every SALET row its word cycles through random answers
                   from that row's group; then everything fades           (12j, VO 4)

REUSE MAP — every element and the one source it comes from:
  SALET / corner word   assets/pigpen.py `PigpenWord(revealed=True)` at GUESS_SCALE —
                        06's corner word, which IS a black-background typed row
  sorted dot layout     assets/groups.py `ranked_layout` (b; e-g for the rows), as 06
  scored rows           assets/groups.py `scored_row`, stroke thinned as 06
  entrances, exits      assets/groups.py `enter_from_beyond` (b), `edge_out` (e-g),
                        06b's shrink-and-fade for dots/words going away
  every flip            assets/flip.py `Flip` / `flip` (corner word, rows, words)
  typing                assets/board.py `WordleBoard.type_anim`, several words in
                        ONE play with the key sound on the first only — 07's final
                        answers; the tiles' border thinned by the new `stroke` arg
  typed words           assets/board.py `get_typed_row`, under a row at the board's
                        row spacing — 07's `_typed_row`
  oval packing          assets/groups.py `_pack` (the packer ranked_layout uses)
  colours               BOARD_NAVY via WordleBoardScene; tiles config.py TILE_*
  groups                assets/lists_data.py -> lists_cache.json `full`
  second words etc.     assets/strategy_data.py -> strategy_cache.json (optimal
                        trees; secondexact --every-reply for h; 12j's draws)
No on-screen text but words and rows; the spoken numbers (148, thousands) are not
shown.

LAYOUT CHOICES, flagged:
  - Rows keep 06b's dot-view sizes throughout (user's call, 2026-09-30), so a typed
    word is as wide as its row and the small groups' words are specks.
  - A group with no second word (LUCKY's and GUESS's own all-green win) gets none:
    a word arriving there shrinks away, a word leaving it grows in.
  - The six clusters (h) are packed in reading order by grey count, 0 first; rows
    in a cluster keep rank order; the whole arrangement takes the largest scale
    that fits (so rows may grow). Ovals are WHITE (the script names no colour).
  - The grey-count words are typed rows at OVAL_WORD_W wide, inside the bottom of
    each oval.
  - j cycles CYCLE_STEPS times; a group smaller than that repeats its draws, a
    one-answer group never changes.
"""
from pathlib import Path
import math
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets.board import STROKE, GAP, TILE, WordleBoard, get_typed_row
from assets.pigpen import PigpenWord
from assets.flip import Flip, flip, row_parts
from assets.groups import (scored_row, ranked_layout, GUESS_SCALE, HEADER_W,
                           enter_from_beyond, edge_out, _pack, REGION_HALF_W,
                           DOT_REGION_TOP, REGION_BOT)
from assets.keys import key_cues
from assets import lists_data, strategy_data

DATA = lists_data.load()
SD = strategy_data.load()
SALET, LUCKY, GUESS = "salet", "lucky", "guess"     # the script's own choices

DOT_COLOR = WHITE
CORNER_BUFF = 0.3          # the corner word's gap to the frame's edges (06)
CORNER_MARGIN = 0.35       # clear space kept right of the corner word (06)

CLUSTER_GAP = 0.06         # between rows in a grey-count cluster (h)
CLUSTER_ASPECT = 2.0       # a cluster's width / height, before its word
OVAL_WORD_W = 1.1          # the grey-count word's width (h)
OVAL_WORD_GAP = 0.12       # between a cluster's rows and its word
OVAL_PAD = 0.25            # added to each oval axis beyond sqrt(2) x its content
OVAL_STROKE = 3
OVAL_COLOR = WHITE
CYCLE_STEPS = 6            # j: how many draws each word cycles through


def _grays(g):
    return sum(1 for t in g["tiles"] if t == 0)


def _stroke(width):
    """06's thinned tile border for a row `width` wide."""
    return STROKE * min(1.0, width / HEADER_W)


def _under(row):
    """Where a word typed under `row` goes: centre, at the board's row spacing."""
    h = row.height
    return row.get_center() + DOWN * (h + h * GAP / TILE)


def _typed(word, row):
    """`word` as a typed row, `row`'s width, under it."""
    w = get_typed_row(word)
    w.scale(row.width / w.width).move_to(_under(row))
    for t in w.tiles[0]:
        t.set_stroke(width=_stroke(row.width))
    return w


def _shrink_out(mob):
    """06b's exit for a thing going away where it stands."""
    return mob.animate.scale(0.1).set_opacity(0)


class Scene12(WordleBoardScene):
    """BEAT MAP
    salet — SALET in the middle, held
    dots — SALET to the corner; its 148 groups slide in, sorted by size
    remove_dots — the dots go; the coloured rows stay
    second_words — every optimal second word typed at once under its row
    to_lucky — SALET flips to LUCKY; rows and words flip and travel
    to_guess — LUCKY flips to GUESS
    back_to_salet — GUESS flips back to SALET
    by_grays — rows gather into six ovals by grey count, each with its word
    undo — back to the rows with their typed words
    random_answers — each word cycles through random answers of its group; all fades
    """

    def setup_scene(self):
        self.guess = PigpenWord(SALET, revealed=True).scale(GUESS_SCALE).move_to(ORIGIN)
        self.add(self.guess)
        w, h = self.guess.width, self.guess.height
        self.corner = np.array([-config.frame_x_radius + CORNER_BUFF + w / 2,
                                config.frame_y_radius - CORNER_BUFF - h / 2, 0.0])
        self.col_left = self.corner[0] + w / 2 + CORNER_MARGIN

    # a : SALET in the middle, held — its VO plays over the framework's holds
    @subscene
    def salet(self):
        pass

    def _rows(self, word):
        """`word`'s groups in rank order, each as (group, scored row at its dot-view
        spot), plus the dot positions and radius."""
        groups, spots, pos, widths, r = ranked_layout(DATA, word, left=self.col_left)
        rows = [scored_row(word, g["code"], wd, c, stroke=_stroke(wd))
                for g, c, wd in zip(groups, pos, widths)]
        return groups, rows, spots, r

    def _setup_dots(self):
        groups, rows, spots, r = self._rows(SALET)
        assert len(spots) == DATA["n_answers"]
        self.groups, self.rows = groups, rows
        self.dots = [Dot(point=spots[w], radius=r, color=DOT_COLOR)
                     for g in groups for w in g["members"]]
        by_word = dict(zip((w for g in groups for w in g["members"]), self.dots))
        # each group (its row and its dots) comes in from beyond the edge, as 06b
        self.incoming = []
        for g, row in zip(groups, rows):
            grp = VGroup(row, *[by_word[w] for w in g["members"]])
            self.incoming.append((grp, enter_from_beyond(grp)))

    # b : SALET to the corner; all 148 groups slide in from beyond, sorted by size
    @subscene
    def dots(self):
        self._setup_dots()
        self.play(self.guess.animate.move_to(self.corner),
                  *[grp.animate.move_to(c) for grp, c in self.incoming],
                  run_time=2.0)
        for grp, _ in self.incoming:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.incoming = None

    # c : the dots shrink away; the coloured rows stay
    @subscene
    def remove_dots(self):
        self.play(*[_shrink_out(d) for d in self.dots], run_time=1.0)
        self.remove(*self.dots)
        self.dots = None

    def _setup_second_words(self):
        """An empty one-row board under each row, to type that group's word into."""
        sec = SD["second"][SALET]
        self.blanks = []
        for g, row in zip(self.groups, self.rows):
            b = WordleBoard(rows=1, cols=5)
            b.scale(row.width / b.width).move_to(_under(row))
            self.blanks.append((b, sec[str(g["code"])]))

    # d : every optimal second word typed at once, each under its coloured SALET
    @subscene
    def second_words(self):
        self._setup_second_words()
        anims, total = [], 0.0
        for i, (b, word) in enumerate(self.blanks):
            a, total = b.type_anim(self, 0, word, 0.65,
                                   per_letter=key_cues(self) if i == 0 else None,
                                   appear=True, stroke=_stroke(b.width))
            anims.append(a)
        self.play(*anims, run_time=total)
        self.words = [b for b, _ in self.blanks]
        self.blanks = None

    # ── switching openers: 06's switch, with each row's typed word along (e-g) ─
    def _setup_switch(self, word):
        """Slot k is the k-th largest group. Each slot both openers have: the row
        flips to the new colouring and its word to the new second word, both
        travelling to the new layout. Slots past the shorter list leave by, or
        arrive from beyond, their nearest edge."""
        groups, rows, _, _ = self._rows(word)
        sec = SD["second"][word]
        words = [_typed(sec[str(g["code"])], row) if str(g["code"]) in sec else None
                 for g, row in zip(groups, rows)]
        t_word = PigpenWord(word, revealed=True).scale(GUESS_SCALE).move_to(self.guess)
        n = min(len(self.rows), len(rows))
        self.flips = [Flip(self.guess, t_word,
                           parts=(row_parts(self.guess), row_parts(t_word)))]
        self.extra, self.gone, self.arrive = [], [], []
        for k in range(n):
            self.flips.append(Flip(self.rows[k], rows[k],
                                   parts=(row_parts(self.rows[k]), row_parts(rows[k])),
                                   travel=True))
            old, new = self.words[k], words[k]
            if old is not None and new is not None:
                self.flips.append(Flip(old, new, parts=(row_parts(old), row_parts(new)),
                                       travel=True))
            elif old is not None:                       # the new slot is a win: no word
                self.extra.append(_shrink_out(old))
                self.gone.append(old)
            elif new is not None:                       # the old slot was a win
                self.arrive.append(new)
                self.extra.append(FadeIn(new))
        # the slots only the old opener has leave by their nearest edge
        for k in range(n, len(self.rows)):
            grp = VGroup(self.rows[k], *([self.words[k]] if self.words[k] else []))
            self.extra.append(grp.animate.move_to(edge_out(grp)))
            self.gone.append(grp)
        # the slots only the new opener has arrive from beyond theirs
        self.entering = []
        for k in range(n, len(rows)):
            grp = VGroup(rows[k], *([words[k]] if words[k] else []))
            home = grp.get_center()
            grp.move_to(edge_out(grp))
            self.extra.append(grp.animate.move_to(home))
            self.entering.append(grp)
        self.t = (t_word, groups, rows, words)

    def _switch(self, run_time):
        flip(self, self.flips, run_time, extra=self.extra)
        self.remove(*self.gone)
        for grp in self.entering:
            self.remove(grp)
            self.add(*grp.submobjects)
        self.guess, self.groups, self.rows, self.words = self.t
        self.flips = self.extra = self.gone = self.arrive = self.entering = self.t = None

    # e : SALET flips to LUCKY, with all of its optimal second guesses
    @subscene
    def to_lucky(self):
        self._setup_switch(LUCKY)
        self._switch(2.0)

    # f : LUCKY flips to GUESS
    @subscene
    def to_guess(self):
        self._setup_switch(GUESS)
        self._switch(2.0)

    # g : GUESS flips back to SALET
    @subscene
    def back_to_salet(self):
        self._setup_switch(SALET)
        self._switch(2.0)

    # ── grouping by grey count (h-i) ─────────────────────────────────────────
    def _setup_by_grays(self):
        """Six clusters, one per grey count: each cluster's rows shelf-packed at
        their current sizes (rank order), its word under them, an oval round both;
        the six ovals packed in reading order, 0 greys first, at one scale."""
        by = {n: [k for k, g in enumerate(self.groups) if _grays(g) == n] for n in range(6)}
        blocks = []
        for n in range(6):
            ks = by[n]
            ws = [self.rows[k].width for k in ks]
            hs = [self.rows[k].height for k in ks]
            area = sum(w * (h + CLUSTER_GAP) for w, h in zip(ws, hs))
            width = max(max(ws), math.sqrt(area * CLUSTER_ASPECT))
            # shelves at the current sizes, rank order, each shelf centred:
            # (k, x, y) from the cluster's top-left
            shelves, cur, x = [], [], 0.0
            for k, w in zip(ks, ws):
                if cur and x + w > width:
                    shelves.append(cur)
                    cur, x = [], 0.0
                cur.append(k)
                x += w + CLUSTER_GAP
            shelves.append(cur)
            span = lambda sh: sum(self.rows[k].width for k in sh) + CLUSTER_GAP * (len(sh) - 1)
            cw = max(span(sh) for sh in shelves)
            place, y = [], 0.0
            for sh in shelves:
                sh_h = max(self.rows[k].height for k in sh)
                x = (cw - span(sh)) / 2
                for k in sh:
                    w = self.rows[k].width
                    place.append((k, x + w / 2, y - sh_h / 2))
                    x += w + CLUSTER_GAP
                y -= sh_h + CLUSTER_GAP
            ch = -y - CLUSTER_GAP
            label = get_typed_row(SD["by_grays"][str(n)])
            label.scale(OVAL_WORD_W / label.width)
            content_w = max(cw, label.width)
            content_h = ch + OVAL_WORD_GAP + label.height
            ow = content_w * math.sqrt(2) + OVAL_PAD
            oh = content_h * math.sqrt(2) + OVAL_PAD
            blocks.append(dict(n=n, place=place, cw=cw, ch=ch, label=label,
                               content_w=content_w, content_h=content_h, w=ow, h=oh))
        f, centres = _pack(blocks, self.col_left, REGION_HALF_W, DOT_REGION_TOP,
                           REGION_BOT, center_last=True)
        self.home = [(row, row.get_center(), row.width) for row in self.rows]
        self.targets, self.ovals, self.labels = [], [], []
        for b, (bx, by_) in zip(blocks, centres):
            top = by_ + b["content_h"] * f / 2
            left = bx - b["cw"] * f / 2
            for k, px, py in b["place"]:
                self.targets.append((self.rows[k], np.array([left + px * f, top + py * f, 0.0]),
                                     self.rows[k].width * f))
            # the word sits at the bottom of the content, which the oval centres on
            lab = b["label"].scale(f)
            lab.move_to([bx, by_ - b["content_h"] * f / 2 + lab.height / 2, 0])
            for t in lab.tiles[0]:
                t.set_stroke(width=_stroke(lab.width))
            self.labels.append(lab)
            self.ovals.append(Ellipse(width=b["w"] * f, height=b["h"] * f,
                                      stroke_color=OVAL_COLOR, stroke_width=OVAL_STROKE)
                              .move_to([bx, by_, 0]))

    # h : the typed words fade; the rows gather into six ovals by grey count, each
    #     with that grey count's word at its bottom
    @subscene
    def by_grays(self):
        self._setup_by_grays()
        self.play(*[FadeOut(w) for w in self.words if w is not None],
                  *[row.animate.move_to(c).scale(wd / row.width) for row, c, wd in self.targets],
                  run_time=1.5)
        self.play(*[FadeIn(o) for o in self.ovals],
                  *[FadeIn(l) for l in self.labels],
                  run_time=1.0)
        self.targets = None

    # i : undo — the ovals and their words fade, the rows go back, the typed words
    #     fade back in
    @subscene
    def undo(self):
        self.play(*[FadeOut(o) for o in self.ovals],
                  *[FadeOut(l) for l in self.labels],
                  *[row.animate.move_to(c).scale(wd / row.width) for row, c, wd in self.home],
                  run_time=1.5)
        self.play(*[FadeIn(w) for w in self.words if w is not None], run_time=1.0)
        self.ovals = self.labels = self.home = None

    def _cycle_step(self, t):
        """Draw t: each word flips to its group's t-th random answer (a group with
        fewer repeats its draws); a word already showing that answer stays."""
        flips, new_words = [], []
        for g, row, old in zip(self.groups, self.rows, self.words):
            draws = SD["cycle"][str(g["code"])]
            word = draws[t % len(draws)]
            if old.word == word:
                new_words.append(old)
                continue
            new = _typed(word, row)
            new.word = word
            flips.append(Flip(old, new, parts=(row_parts(old), row_parts(new))))
            new_words.append(new)
        return flips, new_words

    # j : under every SALET row, its word cycles through random compatible answers
    #     from that row's group; then everything fades (scene 13 follows directly)
    @subscene
    def random_answers(self):
        for w, (g) in zip(self.words, self.groups):
            w.word = SD["second"][SALET][str(g["code"])]
        for t in range(CYCLE_STEPS):
            flips, self.words = self._cycle_step(t)
            flip(self, flips, 0.5)
        self.play(*[FadeOut(m) for m in [self.guess, *self.rows, *self.words]],
                  run_time=1.0)
