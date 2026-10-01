"""The strategies number line and the Random Compatible Answers game — scenes 13, 14.

Moved out of scene 13 when scene 14 needed the same things (2026-10-01), unchanged
in behaviour. A scene mixes `StrategyLine` in ahead of its scene classes:

    class Scene14(StrategyLine, MovingCameraScene, WordleBoardScene):
        def setup_scene(self):
            self.game = random_game_data.load("14")

THE NUMBER LINE: bpkfigures.number_line `ZoomLine`, titled "Average Guesses by
Strategy" / "(Win Rate)", markers on cards in the Wordle tile's own style (TILE
fill and border at the board's stroke), the win rate coloured red -> green by
`win_color`. `optimal_marker` and `compatible_marker` are the two markers both
scenes show, at the script's 13b and 13m values (provenance in scene 13's
docstring).

THE GAME is set GAME_DY (one frame) above the line, so the camera pans between
them and nothing fades. Typed rows stack at the top middle, the board's row
spacing apart; the compatible answers grid below them by `ranked_word_layout`;
a guess flips, the ruled-out words shrink away and the rest regrid; highlights
hop to the next guess; the winning row bounces as the last words go. `self.game`
is a random_game_data cache.
"""
import colorsys
import math

from config import *
from bpkfigures.number_line import ZoomLine
from bpkfigures.highlight import highlight
from bpkfigures.style import CrispCounter
from assets.flip import Flip, flip, row_parts
from assets.board import STROKE, GAP, TILE, WordleBoard, get_typed_row
from assets.groups import HEADER_W, GUESS_Y, ranked_word_layout
from assets.pigpen import PigpenWord, WORD_W     # the list-size word ranked_word_layout sizes by
from assets.keys import key_cues
from assets.stacks_view import WHOOSH_SFX, WHOOSH_GAIN, WHOOSH_PEAK

TITLE = "Average Guesses by Strategy"
SUBTITLE = "(Win Rate)"
SUBTITLE_BUFF = 0.15
WORD_LINE_W = 2.2         # a word's tile row's width in a marker label (SALET's)
LINE_Y = -0.4
TITLE_BUFF = 0.6
MARKER_FS = 30
MARKER_STEM = 0.45        # ZoomLine's default; a scene may set self.marker_stem
CARD_PAD = 0.22           # the marker cards' margin round their text
CARD_RADIUS = 0.25        # the cards' corner rounding
WIN_LOW, WIN_HIGH = LIGHT_RED, LIGHT_GREEN
WIN_MID = 0.98            # the win rate that sits halfway from red to green
TOP_SCALE = 1.7           # the typed rows' size, as a PigpenWord scale
GRID_X = (-7.6, 7.6)      # the compatible-answer grid's region, below the rows
GRID_BOTTOM = -4.3
ROWS_GRID_GAP = 0.3       # between the room for the next typed row and the grid
GRID_MAX_SCALE = 1.0      # a gridded word is never bigger than 04's list size
GAME_DY = config.frame_height   # the game sits one frame above the number line
BOUNCE_H = 0.35           # board.bounce's height for a full-size tile (07's)
TYPE_MARGIN = 0.15        # a word types once its row is this far inside the frame

# the two markers both scenes show: the script's 13b and 13m values
OPTIMAL = (3.42, "100%")
COMPATIBLE = (4.08, "98.20%")


def shrink_out(mob):
    """06b's exit for a thing going away where it stands (as 12's)."""
    return mob.animate.scale(0.1).set_opacity(0)


def word_stroke(width):
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


def word_line(word, width=WORD_LINE_W):
    """A word as a black typed tile row for a marker label (13b's SALET), its
    border thinned by 12's rule for a small row. `width` for a narrower card."""
    row = get_typed_row(word)
    row.scale(width / row.width)
    for t in row.tiles[0]:
        t.set_stroke(width=STROKE * min(1.0, width / HEADER_W))
    return row


THEN_RCA = "Then RCA"     # an opener card's "then Random Compatible Answers" (user's call)


def word_stack(words, width=WORD_LINE_W):
    """Several words as `word_line` rows stacked at the board's row spacing (no
    extra gap: user's call), one mobject on a card. `.is_stack` marks it for
    replace_marker."""
    rows = [word_line(w, width) for w in words]
    stack = VGroup(*rows).arrange(DOWN, buff=rows[0].height * GAP / TILE)
    stack.is_stack = True
    return stack


def opener_lines(words, rate):
    """A k-word opener's card lines: the words, "Then RCA", the win rate."""
    words = list(words)
    head = word_line(words[0]) if len(words) == 1 else word_stack(words)
    return [head, THEN_RCA, rate_text(rate)]


def rate_text(rate):
    """A win rate as a marker shows it: 2 dp and a percent sign."""
    return f"{rate * 100:.2f}%"


def pct(v):
    """A counting win rate (in percent) as a marker shows it."""
    return f"{v:.2f}%"


def whole(v):
    """A counter's readout as a whole number. In an asset so a scene can keep a
    CrispCounter on self: a function defined in a scene file does not pickle."""
    return f"{round(v)}"


def _pct_color(v):
    """A counting win rate's (in percent) colour: `win_color` of what it shows."""
    return win_color(v / 100)


class StrategyLine:
    """The number line and the game, as methods of the scene they are mixed into."""

    # ── the number line ──────────────────────────────────────────────────────
    def _build_line(self, lo, hi, dy=0.0, line_dy=0.0):
        """The line over lo..hi, its title and subtitle above it (not added), all
        `dy` above the frame at the origin (scene 15 sets it one frame up); the line
        alone a further `line_dy` (scene 15 lowers it for its taller cards)."""
        self.line = ZoomLine(lo, hi, y=LINE_Y + dy + line_dy, min_label_step=1, tips=False,
                             ends_buff=-0.1)
        self.title = crisp_text(TITLE, color=WHITE, font_size=FONT_SIZE_LG)
        self.title.to_edge(UP, buff=TITLE_BUFF).shift(UP * dy)
        self.subtitle = crisp_text(SUBTITLE, color=WHITE, font_size=FONT_SIZE_MD)
        self.subtitle.next_to(self.title, DOWN, buff=SUBTITLE_BUFF)

    def _marker(self, value, lines, side=UP, grow=0.0):
        """The last line is the win rate, "NN.NN%"; it takes its colour."""
        rate = lines[-1]
        lines = lines[:-1] + [(rate, win_color(float(rate.rstrip("%")) / 100))]
        mk = self.line.add_marker(value, lines, side=side, font_size=MARKER_FS,
                                  grow=grow,
                                  stem=getattr(self, "marker_stem", MARKER_STEM),
                                  text_color=WHITE,
                                  box={"pad": CARD_PAD, "fill": TILE_EMPTY_FILL,
                                       "stroke_color": TILE_FILLED_BORDER,
                                       "stroke_width": STROKE,
                                       "corner_radius": CARD_RADIUS})
        mk.rate = float(rate.rstrip("%")) / 100        # what replace_marker counts from
        return mk

    def optimal_marker(self, grow=0.0):
        return self._marker(OPTIMAL[0], ["Optimal", word_line("salet"), OPTIMAL[1]],
                            grow=grow)

    def compatible_marker(self, grow=0.0):
        """Its initials bold, since later cards abbreviate it "RCA" (user's call)."""
        return self._marker(COMPATIBLE[0],
                            [(w, None, {"t2w": {w[0]: BOLD}})
                             for w in ("Random", "Compatible", "Answers")]
                            + [COMPATIBLE[1]],
                            side=DOWN, grow=grow)

    def opener_marker(self, value, words, rate, side=UP, grow=0.0):
        """An opener's card: its words (one row, or a board-tight stack), "Then
        RCA", and its win rate."""
        return self._marker(value, opener_lines(words, rate), side=side, grow=grow)

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

    # ── the camera ───────────────────────────────────────────────────────────
    def _whoosh(self, pan_rt):
        """01's camera-move whoosh, loudest at the pan's midpoint."""
        self.sfx(WHOOSH_SFX, at=max(0.0, pan_rt / 2 - WHOOSH_PEAK), gain=WHOOSH_GAIN)

    def _pan_down(self, run_time):
        """The camera pans down one frame (the content leaves upward), whooshing."""
        self._whoosh(run_time)
        self.play(self.camera.frame.animate.shift(DOWN * GAME_DY), run_time=run_time)

    def _pan_up(self, run_time):
        """The camera pans up one frame (the content leaves downward), whooshing."""
        self._whoosh(run_time)
        self.play(self.camera.frame.animate.shift(UP * GAME_DY), run_time=run_time)

    # ── a marker's words change as it slides (14c's, then 15's) ──────────────
    def replace_marker(self, mk, words, value, rate, run_time, zoom=None):
        """The marker's word rows flip to `words` while it slides to `value` and its
        win rate (the last line) counts to `rate`. The rows are its first line: a
        single `word_line`, or a `word_stack` whose rows flip one each. `zoom`
        (lo, hi) zooms the line to that window in the same play (15i: the card
        slides past the edge, so the view follows it)."""
        content = mk.label[1]
        stack = content[0] if getattr(content[0], "is_stack", False) else None
        olds = list(stack) if stack is not None else list(content[:len(words)])
        rate_mob = content[-1]
        old_rate = mk.rate
        line = self.line
        if zoom is None:
            x_end = line.x_of(value)
        else:                                           # where `value` lands after the zoom
            lo, hi = zoom
            x_end = line.x_range[0] + (value - lo) * (line.x_range[1] - line.x_range[0]) / (hi - lo)
        dx = x_end - line.x_of(mk.value)
        news = [word_line(w, o.width).move_to(o.get_center() + RIGHT * dx)
                for w, o in zip(words, olds)]
        # the readout takes the rate's place in the card, at its left edge
        counter = CrispCounter("", ValueTracker(old_rate * 100),
                               left=rate_mob.get_left()[0], y=rate_mob.get_center()[1],
                               font_size=MARKER_FS, color=win_color(rate), fmt=pct,
                               color_of=_pct_color)     # the colour of what it shows
        content.remove(rate_mob)
        content.add(counter.mob)
        # the flips carry the rows: off the card while they run. A stack leaves
        # WHOLE -- emptied in place it would still count in the card's bounds, at
        # the origin, and drag the card off its marker (15g, 2026-10-01)
        for o in ([stack] if stack is not None else olds):
            content.remove(o)
        v0, left0 = mk.value, counter.left
        counter.mob.add_updater(                        # ride the card (before the count's)
            lambda m: setattr(counter, "left",
                              left0 + line.x_of(mk.value) - line.x_of(v0)))
        count = counter.count_anim(rate * 100)
        flip(self, [Flip(o, n, parts=(row_parts(o), row_parts(n)), travel=True)
                    for o, n in zip(olds, news)],
             run_time, extra=[line.move_marker(mk, value), count]
             + ([line.zoom(*zoom)] if zoom is not None else []))
        counter.end_count()
        self.remove(*news)
        if stack is not None:
            new_stack = VGroup(*news)
            new_stack.is_stack = True
            content.submobjects.insert(0, new_stack)
        else:
            for i, n in enumerate(news):
                content.submobjects.insert(i, n)
        mk.rate = rate

    # ── the game ─────────────────────────────────────────────────────────────
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
        for w, (c, sc) in self._grid(self.game["alive"][0], 0).items():
            m = PigpenWord(w, revealed=True).scale(sc).move_to(c)
            for t in m.tiles:
                t.set_stroke(width=word_stroke(m.width))
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
        row.type_word(self, 0, self.game["words"][k], run_time,
                      per_letter=key_cues(self), appear=True)

    def _pan_and_type(self, pan_rt, type_rt):
        """The camera pans up one frame to the game, and the first word starts
        typing as soon as its row is TYPE_MARGIN inside the frame's top — the
        moment read off the pan's own rate function."""
        row = self._new_row()
        self.rows.append(row)
        frame = self.camera.frame
        need = row.get_top()[1] + TYPE_MARGIN - config.frame_height / 2 - frame.get_y()
        a = next(a for a in np.linspace(0, 1, 1001) if smooth(a) * GAME_DY >= need)
        t0 = a * pan_rt
        cues = key_cues(self)
        typing, total = row.type_anim(self, 0, self.game["words"][0], type_rt,
                                      appear=True,
                                      per_letter=lambda i, ch, at: cues(i, ch, t0 + at))
        frame.generate_target()
        frame.target.shift(UP * GAME_DY)
        self._whoosh(pan_rt)
        self.play(MoveToTarget(frame, run_time=pan_rt),
                  Succession(Wait(t0), AnimationGroup(typing, run_time=total)))

    def _flip(self, k, run_time):
        self.rows[k].reveal(self, 0, self.game["codes"][k], run_time)

    def _words_in(self, run_time):
        """The first turn's compatible answers fade in as a grid."""
        self.play(FadeIn(VGroup(*self.words.values())), run_time=run_time)

    def _regrid(self, k, run_time):
        """The words turn k rules out shrink away; the rest move to their cells."""
        keep = self.game["alive"][k]
        anims = []
        for w, (c, sc) in self._grid(keep, k).items():
            m = self.words[w]
            f = sc / self.wscale[w]
            anims.append(m.animate.scale(f).move_to(c))
            self.wscale[w] = sc
        gone = [w for w in self.words if w not in keep]
        anims += [shrink_out(self.words[w]) for w in gone]
        self.play(*anims, run_time=run_time)
        for w in gone:
            self.remove(self.words.pop(w))
            del self.wscale[w]
        for m in self.words.values():
            for t in m.tiles:
                t.set_stroke(width=word_stroke(m.width))

    def _hops(self, k, hop_rt):
        """Quick highlights over turn k's compatible words: the random ones, then
        the next guess, which keeps its highlight until it is typed."""
        seq = self.game["hops"][k]
        for w in seq[:-1]:
            highlight(self, [self.words[w]], pulse=True, fade=hop_rt / 2, hold=hop_rt)
        self.mark = highlight(self, [self.words[seq[-1]]], persist=True, fade=hop_rt)[0]

    def _turn(self, k, type_rt, flip_rt, regrid_rt, hop_rt):
        """A later turn: type, flip, regrid, and (unless it won) hop on."""
        self._type(k, type_rt)
        self._flip(k, flip_rt)
        self._regrid(k, regrid_rt)
        if k + 1 < len(self.game["words"]):
            self._hops(k, hop_rt)

    def _win(self, k, type_rt, flip_rt, run_time):
        """The last word typed and flipped all green; the words left vanish as the
        row does the win bounce (07p's fresh_win)."""
        self._type(k, type_rt)
        self._flip(k, flip_rt)
        row = self.rows[k]
        jump = BOUNCE_H * row.tiles[0][0].height / TILE
        self.play(*[shrink_out(m) for m in self.words.values()],
                  row.bounce_anim(0, height=jump), run_time=run_time)
        self.remove(*self.words.values())
        self.words, self.wscale = {}, {}
