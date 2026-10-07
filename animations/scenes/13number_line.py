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
  f dicey         — the camera pans up, off the number line, to where the game
                    is set, one frame above it (user's call; the script says
                    "Fade everything out"), and DICEY starts typing at the top
                    middle the moment its row is fully in view (user's call:
                    13f and 13g MERGED, so from here each letter is ONE BEHIND
                    the Doc's); DICEY flips BBBYB; its 332 compatible answers
                    fade in as a grid below; a highlight hops 10 times, landing
                    on GUESS                                          (13f+13g, VO 5)
  g guess         — GUESS typed on a new row under DICEY and flips BYYBB; the
                    ruled-out words shrink away and the 21 left regrid; hops to
                    VALUE                                                  (13h, VO 5)
  h value         — the same: VALUE, BBYYG, 5 left, hops to FLUTE          (13i, VO 5)
  i flute         — the same: FLUTE, GGGBG, 2 left, hops to FLUKE          (13j, VO 5)
  j fluke         — FLUKE typed and flips GGGGG; both words left (FLUKE, FLUME)
                    vanish as FLUKE's row does the win bounce              (13k, VO 5)
  k back_to_line  — the camera pans back down to the number line; the game
                    slides up out of frame                                 (13l, VO 5)
  l compatible    — the Random Compatible Answers marker at 4.08, below
                    the line                                               (13m, VO 5)

REUSE MAP — every element, the one source it comes from, and how it enters.
Since 2026-10-01 the line, its markers and the game are assets/strategy_line.py
`StrategyLine`, shared with scene 14 and unchanged in behaviour:
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
  pans (f, k)           the camera (MovingCameraScene, as 08) shifts one frame height;
                        the game is built GAME_DY above the line, so nothing fades
  pan sound             none: screen-to-screen pans are silent (user 2026-10-07;
                        01's camera-move whoosh was used here until then)
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
  - Both pans take 1.5s with manim's default easing. DICEY's
    typing starts when the pan brings its row TYPE_MARGIN inside the frame's top,
    found from the pan's own rate function, so retiming the pan keeps it right.
  - Each win rate is coloured red -> green, very nonlinearly (user's call): the
    colour position is t = 1 - (1 - rate)^P with P set so t = 0.5 at WIN_MID (98%),
    i.e. a power law in the LOSS rate. The colour runs round the hue wheel from
    LIGHT_RED to LIGHT_GREEN (through yellow), since a straight RGB blend of the two
    goes muddy brown in the middle, where 98.20% sits. Resulting t: 0.26% 0.00,
    59.30% 0.15, 98.20% 0.51, 100% 1.00.
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from manim import MovingCameraScene
from assets import random_game_data
from assets.strategy_line import StrategyLine


class Scene13(StrategyLine, MovingCameraScene, WordleBoardScene):
    """show_line — the line, 3..6, and the title
    optimal — 3.42
    random — zoom out to 3..2500; 2315
    no_repeats — 1158
    until_single — zoom in to 3.42..6.90; 6.90
    dicey — the camera up to the game, DICEY typing as it arrives; 332 words in;
        hops to GUESS
    guess — GUESS's turn; hops to VALUE
    value — VALUE's turn; hops to FLUTE
    flute — FLUTE's turn; hops to FLUKE
    fluke — FLUKE's turn; both words go as the row bounces
    back_to_line — the camera back down
    compatible — 4.08, below the line
    """

    def setup_scene(self):
        self.game = random_game_data.load("13")

    # a : the number line, 3 to 6, extending both ways; the title
    def _setup_show_line(self):
        self._build_line(3, 6)

    @subscene
    def show_line(self):
        self._setup_show_line()
        self.play(FadeIn(self.line), FadeIn(self.title), FadeIn(self.subtitle),
                  run_time=1.2)

    # b : Optimal SALET at 3.42
    @subscene
    def optimal(self):
        self._pop_in(self.optimal_marker(), 0.4)

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

    # f : (13f+13g, merged) the camera pans up to the game and DICEY types as its
    #     row arrives; flips BBBYB; the 332 compatible answers; hops to GUESS
    @subscene
    def dicey(self):
        self._setup_game()
        self._pan_and_type(1.5, 0.65)
        self._flip(0, 1.6)
        self._words_in(0.8)
        self._hops(0, 0.12)

    # g : GUESS's turn (BYYBB), 21 left; hops to VALUE
    @subscene
    def guess(self):
        self._turn(1, 0.65, 1.6, 1.0, 0.12)

    # h : VALUE's turn (BBYYG), 5 left; hops to FLUTE
    @subscene
    def value(self):
        self._turn(2, 0.65, 1.6, 1.0, 0.12)

    # i : FLUTE's turn (GGGBG), 2 left; hops to FLUKE
    @subscene
    def flute(self):
        self._turn(3, 0.65, 1.6, 1.0, 0.12)

    # j : FLUKE's turn (GGGGG); both words left vanish as the row does the win bounce
    @subscene
    def fluke(self):
        self._win(4, 0.65, 1.6, 1.0)

    # k : the camera pans back down to the number line; the game leaves upward
    @subscene
    def back_to_line(self):
        self._pan_down(1.5)
        self.remove(*self.rows)            # off-frame now; keeps the snapshot light
        self.rows = []

    # l : Random Compatible Answers at 4.08, below the line
    @subscene
    def compatible(self):
        self._pop_in(self.compatible_marker(), 0.4)
