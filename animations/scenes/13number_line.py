"""Scene 13 — random strategies on a number line of average guesses. Navy background.

Scene 12 ends with the frame cleared, so everything here fades in. Talking head THI
follows, so m ends with the whole line on screen.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_line     — the number line, 3 at the left and 6 at the right, running on
                    past both edges; the title and "(Win Rate)" fade in    (13a, VO 1)
  b optimal       — the Optimal SALET marker at 3.42                       (13b, VO 1)
  c random        — the line zooms out to 3..2500; the Random marker at 2315 (13c, VO 2)
  d no_repeats    — the Random (no repeats) marker at 1158                 (13d, VO 3)
  e until_single  — the line zooms in, the leftmost dot (3.42) at the left and the
                    new 6.90 dot at the right (1158 and 2315 slide off);
                    the Random Until One Answer marker at 6.90             (13e, VO 4)
  f pan_up        — the camera pans up, off the number line, to where the game
                    is set, one frame above it (user's call; the script says
                    "Fade everything out")                                 (13f, VO 5)
  g dicey         — DICEY typed at the top middle, its tiles appearing as typed,
                    and flips BBBYB; its 332 compatible answers fade in as a grid
                    below; a highlight hops 10 times, landing on GUESS     (13g, VO 5)
  h guess         — GUESS typed on a new row under DICEY and flips BYYBB; the
                    ruled-out words shrink away and the 21 left regrid; hops to
                    VALUE                                                  (13h, VO 5)
  i value         — the same: VALUE, BBYYG, 5 left, hops to FLUTE          (13i, VO 5)
  j flute         — the same: FLUTE, GGGBG, 2 left, hops to FLUKE          (13j, VO 5)
  k fluke         — FLUKE typed and flips GGGGG; both words left (FLUKE, FLUME)
                    vanish as FLUKE's row does the win bounce              (13k, VO 5)
  l back_to_line  — the camera pans back down to the number line; the game
                    slides up out of frame                                 (13l, VO 5)
  m compatible    — the Random Compatible Answers marker at 4.08, below
                    the line                                               (13m, VO 5)

REUSE MAP — every element, the one source it comes from, and how it enters:
  number line, ticks,   bpkfigures/number_line.py `ZoomLine` (new, for number lines
  zooms, markers        and timelines): `zoom` for c/e, `add_marker` + `marker_in`
  title                 crisp_text, WHITE, FONT_SIZE_LG — 08's title
  subtitle              crisp_text, WHITE, FONT_SIZE_MD, under the title
  title/subtitle in     plain FadeIn, played with their content — 08histogram.py:369
                        (the heading fades in with the axis), 10word_lengths.py:277
  line in               FadeIn, with the title (as 08's axis)
  markers in            ZoomLine.marker_in(pop=True): the card grows out of its dot
                        while the stem draws — 08's callouts, which grow from their
                        anchor as the line draws (stacks_view.py CALLOUT_GROW, 0.3s);
                        with the "pop" sound effect (user's call: the second pop of
                        ES_Cartoon, Pop, Various) as it starts
  zooms                 ZoomLine.zoom, eased with smootherstep (the asset's default) so
                        the ends come to rest; in c and e the new marker starts popping
                        out while the zoom is still settling (user's call), which the
                        asset allows because a pop drives the marker's `grow`
  zoom sound            none (user's call: 01's whoosh was tried and dropped)
  SALET                 assets/board.py `get_typed_row` (the black typed row, as 12's
                        SALET), its border thinned by 12's rule for a small row
  marker text           crisp_text via the asset, WHITE, on a card in the Wordle
                        TILE's own style (user's call, option 1: the cream house card
                        looked foreign in an all-dark video): card_behind with fill
                        TILE_EMPTY_FILL, border TILE_FILLED_BORDER at the board's
                        STROKE, via add_marker(box=...)
  colours               BOARD_NAVY via WordleBoardScene, as 08 and 12
  win-rate colours      style.py LIGHT_RED -> LIGHT_GREEN, by `win_color` — hangman's
                        win/lose colours on a dark ground (02rules.py:76)
  typed rows (g-j)      a one-row WordleBoard per word, tiles appearing as typed —
                        07n's type_fresh (07dynamic_programming.py:790), each row under
                        the last at the board's row spacing (07's `_typed_row`); the
                        first at 04i's GUESS_Y, TOP_SCALE wide (bigger than 04i's
                        GUESS_SCALE, user's call);
                        typing `type_word` + assets/keys.py `key_cues`; flips `reveal`
                        at 02's 1.6s. No board (user's call)
  compatible words      assets/pigpen.py `PigpenWord(revealed=True)` — 04's answer
                        words — laid out by assets/groups.py `ranked_word_layout`
                        (07d-g's: the grid shape that gives the LARGEST words in the
                        region, last row centred), NOT grid_cells' square grid (user's
                        call: words should fill the space); capped at list size; tile
                        strokes thinned by 12's rule for small rows
  words in (g)          plain FadeIn of the whole grid, below the typed rows (04i's
                        guess-on-top, groups-below arrangement)
  words ruled out       12's `_shrink_out` (06b's exit); survivors move and grow to
                        their new cells in the same play
  hops                  bpkfigures/highlight.py `highlight`: pulse=True for the 9
                        random hops (the module's "a highlight that walks"), then
                        persist=True on the next guess, faded as it is typed
  game words, lists     assets/random_game_data.py -> random_game_cache.json:
                        colourings and compatible answers from math/wordle.py
                        `pattern`, the 9 random hops per turn seeded
  pans (f, l)           the camera (MovingCameraScene, as 08) shifts one frame height;
                        the game is built GAME_DY above the line, so nothing fades
  the win (k)           07p's fresh_win (07dynamic_programming.py:806): the leftover
                        words go (here 12's shrink-out) AS the row does
                        `bounce_anim` at 07's `_jump` height
Nothing leaves at the end: THI follows.

EVERY NUMBER is the script's, and each matches the committed data it came from:
  3.42              optturns: salet 7920 / 2315 = 3.42117
  2315, 0.26%       uniform over the 2315 with repeats: mean 2315, 1-(2314/2315)^6
  1158              uniform without repeats: (2315 + 1) / 2
  6.90, 59.30%      data/shared/wordlesim/random-blind_t1000000_s0.csv (6.8996, 59.2955%)
  4.08, 98.20%      data/shared/wordlesim/random_t1000000_s0.csv (4.0840, 98.1953%)
The averages are shown only by where each marker sits (user's call).

On-screen text is column 2's (the title and the marker labels, without "Win") plus
the user's "(Win Rate)" subtitle, which is what the bare percentages mean. Tick
numbers are part of the number line.

LAYOUT CHOICES, flagged:
  - The line runs straight off both frame edges, no arrow tips (user's call). It opens on
    3..6 across x -6..6 (user's call: left at 3, the same 3-wide range as the earlier
    1..4 opening).
  - The zoom out keeps 3 where it was (3..2500), so the anchor does not jump; at that
    scale 0 is back in view, just left of 3.
  - The zoom in puts the leftmost marker at x=-6 and the new 6.90 marker at x=6
    (user's calls), both derived from the markers.
  - Labels are whole numbers only (min_label_step=1); ticks go down to tenths.
  - 4.08's label hangs BELOW the line: above, it would overlap 3.42's. Its stem
    runs from the dot through the tick labels; a tick label it crosses is dropped.
  - Markers: a white dot and stem, running into the card (user's call: boxed text).
  - 13g-k (user's calls, 2026-09-30): ONE BEAT PER WORD, each ending by selecting
    the next word (the word the script names in that beat), and each flipping its
    REAL colouring — the script's h-j colourings are the SELECTED word's. The typed
    words stack at the top middle, like a board without its empty rows; the
    compatible answers grid below. Each turn ends with 10 quick highlights, 9
    random and the last on the next guess.
  - The grid's region runs from one row's room below the typed rows to the frame's
    bottom, so the next word is always typed into clear space; each regrid (after a
    flip) moves down into the region for the new count of rows.
  - Every compatible answer is shown, all 332 after DICEY (so they are small), in
    the answer list's alphabetical order.
  - Both pans take 1.5s with manim's default easing, and play no sound.
  - Each win rate is coloured red -> green, very nonlinearly (user's call): the
    colour position is t = 1 - (1 - rate)^P with P set so t = 0.5 at WIN_MID (98%),
    i.e. a power law in the LOSS rate. The colour runs round the hue wheel from
    LIGHT_RED to LIGHT_GREEN (through yellow), since a straight RGB blend of the two
    goes muddy brown in the middle, where 98.20% sits. Resulting t: 0.26% 0.00,
    59.30% 0.15, 98.20% 0.51, 100% 1.00.
"""
from pathlib import Path
import colorsys
import math
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from bpkfigures.number_line import ZoomLine
from bpkfigures.highlight import highlight
from assets.board import STROKE, GAP, TILE, WordleBoard, get_typed_row
from assets.groups import HEADER_W, GUESS_Y, ranked_word_layout
from assets.pigpen import PigpenWord, WORD_W     # the list-size word ranked_word_layout sizes by
from assets.keys import key_cues
from assets import random_game_data

GAME = random_game_data.load()

TITLE = "Average Guesses by Strategy"
SUBTITLE = "(Win Rate)"
SUBTITLE_BUFF = 0.15
SALET_W = 2.2             # the SALET row's width in the Optimal label
LINE_Y = -0.4
TITLE_BUFF = 0.6
MARKER_FS = 30
CARD_PAD = 0.22           # the marker cards' margin round their text
CARD_RADIUS = 0.25        # the cards' corner rounding
WIN_LOW, WIN_HIGH = LIGHT_RED, LIGHT_GREEN
WIN_MID = 0.98            # the win rate that sits halfway from red to green
TOP_SCALE = 1.7           # g-j: the typed rows' size, as a PigpenWord scale
GRID_X = (-7.6, 7.6)      # g-j: the compatible-answer grid's region, below the rows
GRID_BOTTOM = -4.3
ROWS_GRID_GAP = 0.3       # between the room for the next typed row and the grid
GRID_MAX_SCALE = 1.0      # a gridded word is never bigger than 04's list size
GAME_DY = config.frame_height   # the game sits one frame above the number line
BOUNCE_H = 0.35           # board.bounce's height for a full-size tile (07's)


def _shrink_out(mob):
    """06b's exit for a thing going away where it stands (as 12's)."""
    return mob.animate.scale(0.1).set_opacity(0)


def _word_stroke(width):
    """12's thinned tile border for a word row `width` wide."""
    return STROKE * min(1.0, width / HEADER_W)


def win_color(rate):
    """A win rate (0..1) on the red -> green scale: halfway at WIN_MID, via a
    power law in the loss rate, interpolated round the hue wheel."""
    p = math.log(0.5) / math.log(1 - WIN_MID)
    t = 1 - (1 - rate) ** p
    (h0, s0, v0), (h1, s1, v1) = (colorsys.rgb_to_hsv(*ManimColor(c).to_rgb())
                                  for c in (WIN_LOW, WIN_HIGH))
    hsv = [a + (b - a) * t for a, b in ((h0, h1), (s0, s1), (v0, v1))]
    return ManimColor.from_rgb(colorsys.hsv_to_rgb(*hsv))


class Scene13(MovingCameraScene, WordleBoardScene):
    """show_line — the line, 3..6, and the title
    optimal — 3.42
    random — zoom out to 3..2500; 2315
    no_repeats — 1158
    until_single — zoom in to 3.42..6.90; 6.90
    pan_up — the camera up to the game
    dicey — DICEY typed at the top and flipped; 332 words in; hops to GUESS
    guess — GUESS's turn; hops to VALUE
    value — VALUE's turn; hops to FLUTE
    flute — FLUTE's turn; hops to FLUKE
    fluke — FLUKE's turn; both words go as the row bounces
    back_to_line — the camera back down
    compatible — 4.08, below the line
    """

    def setup_scene(self):
        pass

    # ── the game (g-j) ────────────────────────────────────────────────────────
    def _grid(self, words, k):
        """{word: (centre, PigpenWord scale)} for turn k's compatible `words`:
        07's `ranked_word_layout` (the shape giving the largest words) in the region
        below the room for turn k+1's row, capped at list size and kept top-aligned."""
        top = GAME_DY + GUESS_Y - self.row_h / 2 - (k + 1) * self.pitch - ROWS_GRID_GAP
        slots, sc, _, _ = ranked_word_layout([{"size": len(words), "members": words}],
                                             GRID_X[0], GRID_X[1], top,
                                             GAME_DY + GRID_BOTTOM,
                                             heads=0)
        width = WORD_W * sc                         # the layout's word width
        f = min(1.0, self.word_w * GRID_MAX_SCALE / width)
        pts = np.array([slots[w] for w in words])
        cx, ty = pts[:, 0].mean(), pts[:, 1].max()
        return {w: (np.array([cx + (slots[w][0] - cx) * f,
                              ty + (slots[w][1] - ty) * f, 0.0]),
                    width * f / self.word_w)
                for w in words}

    def _new_row(self):
        """An empty one-row board for the next typed word: the first at 04i's
        GUESS_Y, TOP_SCALE wide; each later one under the last at the board's
        row spacing (07's `_typed_row`)."""
        row = WordleBoard(rows=1, cols=5)
        row.scale(self.word_w * TOP_SCALE / row.width)
        if not self.rows:
            row.move_to([0, GAME_DY + GUESS_Y, 0])
        else:
            above = self.rows[-1]
            row.next_to(above, DOWN, buff=above.tiles[0][0].height * GAP / TILE)
        return row

    def _setup_game(self):
        self.word_w = PigpenWord("salet", revealed=True).width
        self.rows = []
        self.pitch = self.word_w * TOP_SCALE / (5 * TILE + 4 * GAP) * (TILE + GAP)
        self.row_h = self.pitch * TILE / (TILE + GAP)
        self.words, self.wscale = {}, {}
        for w, (c, sc) in self._grid(GAME["alive"][0], 0).items():
            m = PigpenWord(w, revealed=True).scale(sc).move_to(c)
            for t in m.tiles:
                t.set_stroke(width=_word_stroke(m.width))
            self.words[w], self.wscale[w] = m, sc
        self.mark = None

    def _type(self, k, run_time):
        """Turn k's word typed on a new row, its tiles appearing as typed (the
        previous hop's highlight fades first)."""
        if self.mark is not None:
            self.play(FadeOut(self.mark), run_time=0.2)
            self.mark = None
        row = self._new_row()
        self.rows.append(row)
        row.type_word(self, 0, GAME["words"][k], run_time,
                      per_letter=key_cues(self), appear=True)

    def _flip(self, k, run_time):
        self.rows[k].reveal(self, 0, GAME["codes"][k], run_time)

    def _regrid(self, k, run_time):
        """The words turn k rules out shrink away; the rest move to their cells."""
        keep = GAME["alive"][k]
        anims = []
        for w, (c, sc) in self._grid(keep, k).items():
            m = self.words[w]
            f = sc / self.wscale[w]
            anims.append(m.animate.scale(f).move_to(c))
            self.wscale[w] = sc
        gone = [w for w in self.words if w not in keep]
        anims += [_shrink_out(self.words[w]) for w in gone]
        self.play(*anims, run_time=run_time)
        for w in gone:
            self.remove(self.words.pop(w))
            del self.wscale[w]
        for m in self.words.values():
            for t in m.tiles:
                t.set_stroke(width=_word_stroke(m.width))

    def _hops(self, k, hop_rt):
        """10 quick highlights over turn k's compatible words: 9 random, then the
        next guess, which keeps its highlight until it is typed."""
        seq = GAME["hops"][k]
        for w in seq[:-1]:
            highlight(self, [self.words[w]], pulse=True, fade=hop_rt / 2, hold=hop_rt)
        self.mark = highlight(self, [self.words[seq[-1]]], persist=True, fade=hop_rt)[0]

    def _turn(self, k, type_rt, flip_rt, regrid_rt, hop_rt):
        """A later turn: type, flip, regrid, and (unless it won) hop on."""
        self._type(k, type_rt)
        self._flip(k, flip_rt)
        self._regrid(k, regrid_rt)
        if k + 1 < len(GAME["words"]):
            self._hops(k, hop_rt)

    def _zoom_pop(self, lo, hi, m, zoom_rt, pop_rt, lead):
        """Zoom to lo..hi, with m popping out of its dot (and the pop sound)
        starting `lead` seconds before the zoom ends."""
        start = zoom_rt - lead
        self.sfx("pop", at=start)
        self.play(self.line.zoom(lo, hi, run_time=zoom_rt),
                  Succession(Wait(start), self.line.marker_in(m, run_time=pop_rt)))

    def _pop_in(self, m, run_time):
        """The marker's card pops out of its dot, with the pop sound."""
        self.sfx("pop")
        self.play(self.line.marker_in(m), run_time=run_time)

    def _marker(self, value, lines, side=UP):
        """The last line is the win rate, "NN.NN%"; it takes its colour."""
        rate = lines[-1]
        lines = lines[:-1] + [(rate, win_color(float(rate.rstrip("%")) / 100))]
        return self.line.add_marker(value, lines, side=side, font_size=MARKER_FS,
                                    grow=0.0,
                                    text_color=WHITE,
                                    box={"pad": CARD_PAD, "fill": TILE_EMPTY_FILL,
                                         "stroke_color": TILE_FILLED_BORDER,
                                         "stroke_width": STROKE,
                                         "corner_radius": CARD_RADIUS})

    # a : the number line, 3 to 6, extending both ways; the title
    def _setup_show_line(self):
        self.line = ZoomLine(3, 6, y=LINE_Y, min_label_step=1, tips=False,
                             ends_buff=-0.1)
        self.title = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG)
        self.title.to_edge(UP, buff=TITLE_BUFF)
        self.subtitle = crisp_text(SUBTITLE, color=WHITE, font_size=FONT_SIZE_MD)
        self.subtitle.next_to(self.title, DOWN, buff=SUBTITLE_BUFF)

    @subscene
    def show_line(self):
        self._setup_show_line()
        self.play(FadeIn(self.line), FadeIn(self.title), FadeIn(self.subtitle),
                  run_time=1.2)

    # b : Optimal SALET at 3.42
    @subscene
    def optimal(self):
        salet = get_typed_row("salet")
        salet.scale(SALET_W / salet.width)
        for t in salet.tiles[0]:
            t.set_stroke(width=STROKE * min(1.0, SALET_W / HEADER_W))
        m = self._marker(3.42, ["Optimal", salet, "100%"])
        self._pop_in(m, 0.4)

    # c : zoom out to 3..2500; Random at 2315
    @subscene
    def random(self):
        m = self._marker(2315, ["Random", "0.26%"])
        self._zoom_pop(3, 2500, m, 2.0, 0.4, 0.5)

    # d : Random (no repeats) at 1158
    @subscene
    def no_repeats(self):
        m = self._marker(1158, ["Random", "(no repeats)", "0.26%"])
        self._pop_in(m, 0.4)

    # e : zoom in, the leftmost dot at the left, the new 6.90 dot at the right; 1158 and 2315
    #     slide off; Random Until One Answer at 6.90 (script: "Single"; user's call)
    @subscene
    def until_single(self):
        left = min(m.value for m in self.line.markers)
        m = self._marker(6.90, ["Random Until", "One Answer", "59.30%"])
        self._zoom_pop(left, m.value, m, 2.0, 0.4, 0.5)

    # f : the camera pans up to the game, set one frame above the line
    @subscene
    def pan_up(self):
        self.play(self.camera.frame.animate.shift(UP * GAME_DY), run_time=1.5)

    # g : DICEY typed at the top, flips BBBYB; the 332 compatible answers; hops to GUESS
    @subscene
    def dicey(self):
        self._setup_game()
        self._type(0, 0.65)
        self._flip(0, 1.6)
        self.play(FadeIn(VGroup(*self.words.values())), run_time=0.8)
        self._hops(0, 0.12)

    # h : GUESS's turn (BYYBB), 21 left; hops to VALUE
    @subscene
    def guess(self):
        self._turn(1, 0.65, 1.6, 1.0, 0.12)

    # i : VALUE's turn (BBYYG), 5 left; hops to FLUTE
    @subscene
    def value(self):
        self._turn(2, 0.65, 1.6, 1.0, 0.12)

    # j : FLUTE's turn (GGGBG), 2 left; hops to FLUKE
    @subscene
    def flute(self):
        self._turn(3, 0.65, 1.6, 1.0, 0.12)

    # k : FLUKE's turn (GGGGG); both words left vanish as the row does the win bounce
    @subscene
    def fluke(self):
        self._type(4, 0.65)
        self._flip(4, 1.6)
        row = self.rows[4]
        jump = BOUNCE_H * row.tiles[0][0].height / TILE
        self.play(*[_shrink_out(m) for m in self.words.values()],
                  row.bounce_anim(0, height=jump), run_time=1.0)
        self.remove(*self.words.values())
        self.words, self.wscale = {}, {}

    # l : the camera pans back down to the number line; the game leaves upward
    @subscene
    def back_to_line(self):
        self.play(self.camera.frame.animate.shift(DOWN * GAME_DY), run_time=1.5)
        self.remove(*self.rows)            # off-frame now; keeps the snapshot light
        self.rows = []

    # m : Random Compatible Answers at 4.08, below the line
    @subscene
    def compatible(self):
        m = self._marker(4.08, ["Random", "Compatible", "Answers", "98.20%"],
                         side=DOWN)
        self._pop_in(m, 0.4)
