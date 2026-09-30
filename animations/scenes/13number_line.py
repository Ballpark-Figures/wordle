"""Scene 13 — random strategies on a number line of average guesses. Navy background.

Scene 12 ends with the frame cleared, so everything here fades in. Talking head THI
follows, so l ends with the whole line on screen.

BEAT MAP — one subscene per Script.md beat, letters matching:

  a show_line     — the number line, 3 at the left and 6 at the right, running on
                    past both edges; the title and "(Win Rate)" fade in    (13a, VO 1)
  b optimal       — the Optimal SALET marker at 3.42                       (13b, VO 1)
  c random        — the line zooms out to 3..2500; the Random marker at 2315 (13c, VO 2)
  d no_repeats    — the Random (no repeats) marker at 1158                 (13d, VO 3)
  e until_single  — the line zooms in, the leftmost dot (3.42) at the left and the
                    new 6.90 dot at the right (1158 and 2315 slide off);
                    the Random Until One Answer marker at 6.90             (13e, VO 4)
  f fade_out      — everything fades out                                   (13f, VO 5)
  g dicey         — an empty board fades in on the left; DICEY is typed and flips
                    BBBYB; its 332 compatible answers fade in as a grid on the
                    right; a highlight hops 10 times, landing on GUESS     (13g, VO 5)
  h guess_value   — GUESS typed, flips BYYBB (the script gives no colouring for
                    it; this is its real one); the ruled-out words shrink away and
                    the 21 left regrid; hops to VALUE. Then VALUE the same: BBYYG,
                    5 left, hops to FLUTE                                  (13h, VO 5)
  i flute         — FLUTE typed, GGGBG, 2 left, hops to FLUKE              (13i, VO 5)
  j fluke         — FLUKE typed, GGGGG; FLUKE alone is left                (13j, VO 5)
  k back_to_line  — the board and FLUKE fade out as the number line, its markers
                    and the title fade back in                             (13k, VO 5)
  l compatible    — the Random Compatible Answers marker at 4.08, below
                    the line                                               (13l, VO 5)

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
  the board (g-j)       assets/board.py `get_board`, scaled onto the left; typing
                        `type_word` + assets/keys.py `key_cues` (02, 07); flips
                        `reveal` at 02's 1.6s
  board in (g)          plain FadeIn — no earlier scene brings a board on mid-scene
                        (every one is up from frame 0), so this is flagged
  compatible words      assets/pigpen.py `PigpenWord(revealed=True)` — 04's answer
                        words — gridded by assets/groups.py `grid_cells` at 04's
                        CELL_GAP / CELL_DY pitches (relative to GROUP_SCALE), scaled
                        to fill the right-hand region; tile strokes thinned by 12's
                        rule for small rows
  words in (g)          plain FadeIn of the whole grid
  words ruled out       12's `_shrink_out` (06b's exit); survivors move and grow to
                        their new cells in the same play
  hops                  bpkfigures/highlight.py `highlight`: pulse=True for the 9
                        random hops (the module's "a highlight that walks"), then
                        persist=True on the next guess, faded as it is typed
  game words, lists     assets/random_game_data.py -> random_game_cache.json:
                        colourings and compatible answers from math/wordle.py
                        `pattern`, the 9 random hops per turn seeded
  the line back (k)     FadeOut the board with FadeIn of the line and title (the
                        same objects f faded, markers and all)
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
  - 13g-j (user's calls, 2026-09-30): each (colouring, word) pair in the script is
    that word's turn, so h plays two turns (GUESS, then VALUE); the board sits on
    the left and the compatible answers in a grid on the right; each turn ends with
    10 quick highlights, 9 random and the last on the next guess.
  - Every compatible answer is shown, all 332 after DICEY (so they are small), in
    the answer list's alphabetical order.
  - k crossfades the board out and the line in, in one play.
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
from bpkfigures.number_line import ZoomLine
from bpkfigures.highlight import highlight
from assets.board import STROKE, get_typed_row, get_board
from assets.groups import HEADER_W, GROUP_SCALE, CELL_GAP, CELL_DY, grid_cells
from assets.pigpen import PigpenWord
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
BOARD_H = 6.2             # g-j: the board's height, on the left
BOARD_X = -5.0            # ... and its centre
GRID_X = (-1.9, 7.6)      # g-j: the compatible-answer grid's region
GRID_Y = (-4.0, 4.0)
GRID_MAX_SCALE = 1.0      # a gridded word is never bigger than 04's list size


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


class Scene13(WordleBoardScene):
    """show_line — the line, 3..6, and the title
    optimal — 3.42
    random — zoom out to 3..2500; 2315
    no_repeats — 1158
    until_single — zoom in to 3.42..6.90; 6.90
    fade_out — everything out
    dicey — board in; DICEY typed and flipped; 332 words in; hops to GUESS
    guess_value — GUESS's turn, then VALUE's
    flute — FLUTE's turn
    fluke — FLUKE's turn
    back_to_line — board out, line back
    compatible — 4.08, below the line
    """

    def setup_scene(self):
        pass

    # ── the game (g-j) ────────────────────────────────────────────────────────
    def _grid(self, words):
        """{word: (centre, scale)} for `words` gridded by grid_cells in the region."""
        n = len(words)
        nc = max(1, math.ceil(math.sqrt(n)))
        nr = math.ceil(n / nc)
        ww = self.word_w                            # a word's width at scale 1
        cg, dy = CELL_GAP / GROUP_SCALE, CELL_DY / GROUP_SCALE
        rw, rh = GRID_X[1] - GRID_X[0], GRID_Y[1] - GRID_Y[0]
        s = min(rw / (nc * ww + (nc - 1) * cg), rh / (nr * dy), GRID_MAX_SCALE)
        cx, cy = sum(GRID_X) / 2, sum(GRID_Y) / 2
        return {w: (np.array([cx + ox * (ww + cg) * s, cy + oy * dy * s, 0.0]), s)
                for w, (ox, oy) in zip(words, grid_cells(n))}

    def _setup_game(self):
        self.board = get_board()
        self.board.scale(BOARD_H / self.board.height).move_to([BOARD_X, 0, 0])
        self.word_w = PigpenWord("salet", revealed=True).width
        self.words, self.wscale = {}, {}
        for w, (c, sc) in self._grid(GAME["alive"][0]).items():
            m = PigpenWord(w, revealed=True).scale(sc).move_to(c)
            for t in m.tiles:
                t.set_stroke(width=_word_stroke(m.width))
            self.words[w], self.wscale[w] = m, sc
        self.mark = None

    def _type(self, k, run_time):
        """Turn k's word typed into row k (the previous hop's highlight fades)."""
        if self.mark is not None:
            self.play(FadeOut(self.mark), run_time=0.2)
            self.mark = None
        self.board.type_word(self, k, GAME["words"][k], run_time,
                             per_letter=key_cues(self))

    def _flip(self, k, run_time):
        self.board.reveal(self, k, GAME["codes"][k], run_time)

    def _regrid(self, k, run_time):
        """The words turn k rules out shrink away; the rest move to their cells."""
        keep = GAME["alive"][k]
        anims = []
        for w, (c, sc) in self._grid(keep).items():
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

    # f : everything fades out
    @subscene
    def fade_out(self):
        self.play(FadeOut(self.line), FadeOut(self.title), FadeOut(self.subtitle),
                  run_time=1.0)

    # g : board in; DICEY typed, flips BBBYB; the 332 compatible answers; hops to GUESS
    @subscene
    def dicey(self):
        self._setup_game()
        self.play(FadeIn(self.board), run_time=0.6)
        self._type(0, 0.65)
        self._flip(0, 1.6)
        self.play(FadeIn(VGroup(*self.words.values())), run_time=0.8)
        self._hops(0, 0.12)

    # h : GUESS's turn (BYYBB), hops to VALUE; VALUE's turn (BBYYG), hops to FLUTE
    @subscene
    def guess_value(self):
        self._turn(1, 0.65, 1.6, 1.0, 0.12)
        self._turn(2, 0.65, 1.6, 1.0, 0.12)

    # i : FLUTE's turn (GGGBG), hops to FLUKE
    @subscene
    def flute(self):
        self._turn(3, 0.65, 1.6, 1.0, 0.12)

    # j : FLUKE's turn (GGGGG); FLUKE alone is left
    @subscene
    def fluke(self):
        self._turn(4, 0.65, 1.6, 1.0, 0.12)

    # k : back to the timeline — the board and FLUKE out, the line and title in
    @subscene
    def back_to_line(self):
        self.play(FadeOut(self.board), *[FadeOut(m) for m in self.words.values()],
                  FadeIn(self.line), FadeIn(self.title), FadeIn(self.subtitle),
                  run_time=1.2)
        self.board, self.words, self.wscale = None, {}, {}

    # l : Random Compatible Answers at 4.08, below the line
    @subscene
    def compatible(self):
        m = self._marker(4.08, ["Random", "Compatible", "Answers", "98.20%"],
                         side=DOWN)
        self._pop_in(m, 0.4)
