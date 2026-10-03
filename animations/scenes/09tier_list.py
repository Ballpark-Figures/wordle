"""SCENE 09 — the Hangman video, the poll, and the tier list carried over to Wordle.

BEAT MAP (one subscene per Script.md beat)
  a hangman_video — the scene OPENS on the dark-mode YouTube watch page for "I Tried
                    to Solve Hangman" (on screen from frame 0; VO 1: "My last video
                    was about Hangman…")
  b poll          — a swipe: the watch page slides off to the LEFT as the dark-mode
                    community poll page slides in from the RIGHT (VO 2: "…I posted
                    this poll 3 days before the Hangman video came out.")
  c hangman_clip  — a swipe BACK: the poll page slides off to the RIGHT as the watch
                    page slides in from the LEFT, then 10 s of the Hangman video
                    from 13:30 plays in its player (VO 3)
  d hangman_tiers — the watch page fades out; the Hangman tier list fades in with the
                    title "Hangman Tier List" at the top (VO 3)
  e wordle_tiers  — hangman list + title slide LEFT; a copy MORPHS into the Wordle
                    tier list on the right ("Wordle Tier List" fading in as it moves),
                    arrow drawn AFTER — the hangman scene-17 comparison style (VO 4)
  f histogram     — the camera jumps (invisibly) to 08's histogram view; the navy
                    background fades in, the Hangman list, the titles and the arrow
                    fade out, the Wordle list shrinks into the top-RIGHT corner, its
                    panels turning lighter; then 08's histogram grows back up with
                    its axis and title                                       (VO 5)
  g low_tiers     — the corner list dims every tier but LOW▲ and LOW▼      (VO 6)
  h low_1         — the 1+ low-tier layer grows up over the bars, with a legend
                    row (Yahtzee 07's overlay style; no row for the whole chart) (VO 6)
  i low_2         — the 2+ layer grows up over it; its legend row appears    (VO 6)
  j low_3         — the 3+ layer, POPPED: it grows up exaggerated and straight
                    back down to its true height, so its shape can be seen    (VO 6)
  k list_center   — the histogram, its layers and legend fall/fade away; the list
                    returns to the centre at full brightness                 (VO 7)
  l doubles       — the list morphs into the list WITH DOUBLES: LOW splits into
                    LOW▲ / LOW■ / LOW▼ and the doubles ride in with their rows (VO 7)
  m histogram_2   — the list slides off to the right AS the histogram grows back (VO 8)
  n dup_1 / o dup_2 / p dup_3 — the duplicate-letter layers, as h-j (p popped) (VO 8)
  q restore       — the duplicate layers fall back to the axis, legend out   (VO 8)
  r vowel_3 / s vowel_4 — the distinct-vowel layers, as h-i (s popped)       (VO 9)
  t to_black      — everything fades out as the navy page turns Wordle's black
                    (WORDLE_BG), the background scene 10 opens on (the user's
                    call, 2026-09-29; not a script beat)

REUSE MAP
  watch page      bpkfigures.youtube_card.youtube_watch (as hangman 93youtube_test c)
  clip            bpkfigures.youtube_card.play_clip, from footage/hangman.mp4 (the
                  YouTube upload, pulled with yt-dlp; gitignored, so a fresh machine
                  needs it re-pulled)
  poll            bpkfigures.youtube_card.youtube_poll
  tier lists      bpkfigures.tier_list (promoted from hangman's asset): filled_list,
                  morph_into; the LIST_SCALE / LEFT_X / RIGHT_X / LIST_Y / title height,
                  title style (30pt bold BLACK) and the arrow are hangman 17c's
  background      WordleScene (BG_COLOR, the tier-list world's light blue); the two
                  YouTube pages cover it with their own full-frame page; from e a
                  BOARD_NAVY page (08's background) covers it
  histogram       assets/histogram_view.py — 08's full view, bars, axis, ticks, x
                  label and title, copied from 08 (see that module's note)
  layers          histogram_view.layer_bars (one bar per histogram bar, same scale);
                  grown by bar_graph.grow_bars and dropped by bar_graph.shrink_bars
                  (yahtzee 07's _grow_up / _fall_down); legend = yahtzee's
                  make_hist_legend look (0.22 swatch + FONT_SIZE_SM label), in white
  emphasis        tier_list.emphasize (dim the rest)
  doubles         tier_list tokens: a small copy then a full-size copy

NUMBERS / ORDERINGS — all SOURCED
  video title / channel / views / age / duration: assets/youtube_data (analytics DB,
      committed youtube_cache.json); thumbnail + avatar: assets/youtube_media/fetch.py
  poll: assets/poll_data (hand-transcribed from a screenshot; the API has no posts)
  Hangman tiers: assets/tier_data.HANGMAN_LETTERS (hand-copy of hangman's TIER_LETTERS)
  Wordle tiers:  assets/tier_data.WORDLE_LETTERS (read from math/tiers.py)
  with doubles:  assets/tier_data.WORDLE_DOUBLE_LETTERS (order_r2_top1000.csv, cut at
                 the user's V / SS / Q; everything after Q not shown, the user's call)
  histogram:     assets/histogram_data (the committed optturns sweep)
  layers:        assets/subhist_data -> subhist_cache.json: opener_distribution.ipynb's
                 conditions, asserted to reproduce its printed sizes
                 (low 4750/692/36, dup 4650/465/9, vowel 1156/20)

ON-SCREEN TEXT beyond column 2 (the user's call, Yahtzee-style legends): the legend
rows "All opening words" and one per layer.

LAYOUT CHOICES, flagged: the Wordle title fades with the Hangman list in e (column 2
names only the list going to the corner); the lighter panel colour on the navy is
BOARD_NAVY with 22% white; layer colours ORANGE / RED / PURPLE, in nesting order
(yahtzee 07 used ORANGE then RED); a double's small copy sits on the full copy's
baseline; LOW■ grows out of the old LOW▼ with LOW▼.

THE SEAM (e): 08's histogram lives in a view 27x the 16-wide frame. Everything before
e is laid out in the ordinary frame, so at e's first instant the camera moves to the
histogram view AND every mobject on screen is re-projected by the same map
(histogram_view.to_view): nothing visibly changes, and every later beat is built in
design coordinates through the same map (histogram_view.design).

d's ROW MAP: every Wordle tier travels in from the Hangman list — the reverse of the
hangman video's tier MERGE: Hangman's TOP SPLITS into Wordle's TOP▲ and TOP▼, and
each HIGH/MID/LOW half becomes the Wordle half of the same name.

Render:  render 09a --fast (…09e)  /  render 09 sub  for the whole scene
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

import numpy as np
from manim import MovingCameraScene

from config import *
from bpkfigures.youtube_card import youtube_watch, youtube_poll, play_clip
from bpkfigures import tier_list as tl
from bpkfigures.bar_graph import grow_bars, shrink_bars
from assets.youtube_data import get as yt_get
from assets.poll_data import get as poll_get
from assets import tier_data as td
from assets import subhist_data
from assets.word_stacks import StacksCamera
from assets.histogram_view import (HistogramChrome, full_stacks, layer_bars, to_view,
                                   design, K, CENTER, WIDTH, HEIGHT, SQUASH, BAR_COLOR,
                                   TALLEST)

HANGMAN_VIDEO = yt_get("hangman")
HANGMAN_FILE = str(Path(__file__).resolve().parents[2] / "footage" / "hangman.mp4")
POLL = poll_get("wordle")
LAYERS = subhist_data.load()["layers"]

# ── tier lists (hangman 17c's layout) ─────────────────────────────────────────
LIST_SCALE = 0.62
LEFT_X, RIGHT_X = -3.45, 3.45
LIST_Y = -0.15
TITLE_BASELINE = 2.78            # hangman 17's TITLE_Y 2.9, as a baseline
TITLE_COLOR = BLACK               # tier-list world uses BLACK labels on the light bg
WORDLE_ROWS_FROM = [0, 0, 1, 2, 3, 4, 5, 6]      # see "d's ROW MAP" above
DOUBLES_ROWS_FROM = [0, 1, 2, 3, 4, 5, 6, 7, 7]  # k: LOW■ and LOW▼ both from LOW▼
LOW_TIERS = {6, 7}                               # LOW▲, LOW▼ — the user's "low tier"

# ── the histogram beats (design coordinates, 16 x 9) ──────────────────────────
CORNER_SCALE = 0.40               # the tier list in the corner
CORNER_UR = (7.7, 2.3)            # its top-RIGHT corner (bars short there)
LEGEND_GAP = 0.35                 # the legend's right edge to the corner list's left
PANEL_ON_NAVY = td.PANEL_ON_NAVY  # e on: lighter panels (moved to tier_data, shared)
LAYER_COLORS = [ACCENT_ORANGE, ACCENT_RED, ACCENT_PURPLE]    # outermost first
POP_FRAC = 0.35                   # a popped layer's tallest bar, over the histogram's
LEGEND_LABELS = {
    "low": ["1+ low tier letter", "2+ low tier letters", "3+ low tier letters"],
    "dup": ["1+ duplicate letter", "2+ duplicate letters", "3+ duplicate letters"],
    "vowel": ["3+ distinct vowels", "4+ distinct vowels"],
}


class Scene09(MovingCameraScene, WordleScene):
    """The Hangman video, the poll, the tier list, and the histogram's sub-histograms.
    See the module docstring."""

    def __init__(self, **kwargs):
        super().__init__(camera_class=StacksCamera, **kwargs)

    def setup_scene(self):
        self.video_page = youtube_watch(**HANGMAN_VIDEO, dark=True)   # on from frame 0
        self.add(self.video_page)
        self.poll_page = None
        self.hang = self.hang_title = None
        self.wordle = self.wordle_title = None
        self.arrow = None
        self.navy = self.stacks = self.chrome = self.legend = None
        self.layers = []

    def _title(self, text, x):
        # on a shared BASELINE, so "Hangman" (descender) and "Wordle" share one line
        return crisp_text(text, font_size=30, color=TITLE_COLOR, weight=BOLD,
                          baseline_at=(x, TITLE_BASELINE))

    # a : hold on the watch page (built in setup_scene — on screen from frame 0)
    @subscene
    def hangman_video(self):
        pass

    # b : swipe — the watch page slides off LEFT as the poll page slides in from RIGHT
    def _setup_poll(self):
        # page backing a touch WIDER than the frame so it overlaps the watch page
        # mid-swipe (abutting edges leave an anti-aliased seam of background)
        self.poll_page = youtube_poll(**POLL, width=12.0, dark=True, page=True,
                                      frame_w=config.frame_width + 0.1)
        self.poll_page.shift(RIGHT * config.frame_width)       # start just off-frame

    @subscene
    def poll(self):
        self._setup_poll()
        self.add(self.poll_page)
        self.play(self.video_page.animate.shift(LEFT * config.frame_width),
                  self.poll_page.animate.shift(LEFT * config.frame_width), run_time=1.0)
        self.remove(self.video_page)              # kept off-frame: c swipes it back

    # c : swipe back — the poll page slides off RIGHT as the watch page slides in from
    #     LEFT; then the Hangman video plays from 13:30 for 10 s in its player
    @subscene
    def hangman_clip(self):
        self.add(self.video_page)
        self.play(self.video_page.animate.shift(RIGHT * config.frame_width),
                  self.poll_page.animate.shift(RIGHT * config.frame_width), run_time=1.0)
        self.remove(self.poll_page)
        self.poll_page = None
        self.play(play_clip(self.video_page, HANGMAN_FILE, "13:30"), run_time=10.0)

    # d : the watch page leaves; the Hangman tier list + its title fade in
    def _setup_hangman_tiers(self):
        self.hang = tl.filled_list(td.HANGMAN_LETTERS, names=td.HANGMAN_NAMES,
                                   scale=LIST_SCALE).move_to([0, LIST_Y, 0])
        self.hang_title = self._title("Hangman Tier List", 0)

    @subscene
    def hangman_tiers(self):
        self._setup_hangman_tiers()
        self.play(FadeOut(self.video_page), run_time=0.6)
        self.video_page = None
        self.play(FadeIn(self.hang, self.hang_title), run_time=0.8)

    # e : hangman list slides left; a copy morphs into the Wordle list; arrow after
    def _setup_wordle_tiers(self):
        self.wordle = tl.filled_list(td.WORDLE_LETTERS, names=td.WORDLE_NAMES,
                                     scale=LIST_SCALE).move_to([RIGHT_X, LIST_Y, 0])
        self.wordle_title = self._title("Wordle Tier List", RIGHT_X)
        self.arrow = Arrow([-1.05, LIST_Y, 0], [1.05, LIST_Y, 0], buff=0.0,
                           color=TITLE_COLOR, stroke_width=6)

    @subscene
    def wordle_tiers(self):
        self._setup_wordle_tiers()
        self.play(self.hang.animate.set_x(LEFT_X), self.hang_title.animate.set_x(LEFT_X),
                  run_time=0.8)
        tl.morph_into(self, self.hang, self.wordle, td.HANGMAN_LETTERS, td.WORDLE_LETTERS,
                      None, 2.0, extra=[FadeIn(self.wordle_title)],
                      split_from=WORDLE_ROWS_FROM)
        self.play(GrowArrow(self.arrow), run_time=0.5)

    # ── histogram helpers ─────────────────────────────────────────────────────
    def _list_at(self, letters, names, scale, *, ur=None, center=(0, LIST_Y),
                 panel_width=tl._DEFAULT_PANEL_W):
        """A filled tier list on the navy (lighter panels), laid out in DESIGN
        coordinates, then projected into the histogram view (to_view)."""
        lst = tl.filled_list(letters, names=names, scale=scale, panel_width=panel_width,
                             panel_fill=PANEL_ON_NAVY)
        if ur is not None:
            lst.move_to([*ur, 0], aligned_edge=UR)
        else:
            lst.move_to([*center, 0])
        return to_view(lst)

    def _grow_histogram(self, run_time, extra=()):
        """08a's entrance: the bars grow up from the axis as the chrome fades in;
        `extra` plays alongside."""
        self.stacks = full_stacks(squash=SQUASH * 1e-3)
        self.stacks.refresh(self.camera.frame)
        self.chrome = HistogramChrome()
        self.add(self.stacks)
        t = ValueTracker(1e-3)

        def grow(m):
            m.set_state(squash=SQUASH * t.get_value())
            m.refresh(self.camera.frame)

        self.stacks.add_updater(grow)
        self.play(t.animate.set_value(1.0), FadeIn(self.chrome), *extra,
                  run_time=run_time)
        self.stacks.remove_updater(grow)
        self.remove(t)

    def _drop_histogram(self, run_time):
        """The reverse: the bars (and any layers) fall to the axis as the chrome and
        legend fade; then all of it is removed."""
        t = ValueTracker(1.0)

        def fall(m):
            m.set_state(squash=SQUASH * t.get_value())
            m.refresh(self.camera.frame)

        self.stacks.add_updater(fall)
        fades = [FadeOut(m) for m in (self.chrome, self.legend) if m is not None]
        bars = [b for layer in self.layers for b in layer]
        shrink_bars(self, bars, run_time, extra=[t.animate.set_value(1e-3), *fades])
        self.stacks.remove_updater(fall)
        # the bars too: animating each bar added it to the scene on its own
        self.remove(t, self.stacks, *self.layers, *bars)
        self.stacks = self.chrome = self.legend = None
        self.layers = []

    @staticmethod
    def _legend_swatch_row(color, text):
        sw = Square(side_length=0.22, fill_color=color, fill_opacity=1.0, stroke_width=0)
        txt = crisp_text(text, font_size=FONT_SIZE_SM, color=WHITE)
        txt.next_to(sw, RIGHT, buff=0.15)
        return VGroup(sw, txt)

    def _legend_row(self, color, text, i):
        """Legend row `i` — yahtzee's make_hist_legend look, in white. There is no row
        for the whole histogram (the user's call). Every legend sits in ONE place: on
        the right, just LEFT of the corner tier list and top-aligned with it (the
        user's call) — also in m-r, when the list is gone. Its left edge is fixed by
        the WIDEST row of any legend, so rows line up and nothing reaches the list."""
        row = self._legend_swatch_row(color, text)
        widest = max(self._legend_swatch_row(WHITE, t).width
                     for labels in LEGEND_LABELS.values() for t in labels)
        corner = tl.filled_list(td.WORDLE_LETTERS, names=td.WORDLE_NAMES,
                                scale=CORNER_SCALE).move_to([*CORNER_UR, 0],
                                                            aligned_edge=UR)
        left = corner.get_left()[0] - LEGEND_GAP - widest
        pitch = row.height + 0.18
        row.move_to([left, CORNER_UR[1] - i * pitch, 0], aligned_edge=UL)
        return to_view(row)

    def _layer(self, family, i, run_time, pop=False):
        """Layer `i` of `family` grows up over the bars (over any layer before it) and
        its legend row fades in. `pop`, for a layer too thin to see: every bar grows
        to a height that makes the tallest POP_FRAC of the histogram's (the same
        factor for all, so the shape reads), then straight back down to its true
        height, no pause at the top; `run_time` covers both halves."""
        counts = np.array(LAYERS[family][i]["counts"], dtype=float)
        row = self._legend_row(LAYER_COLORS[i], LEGEND_LABELS[family][i], i)
        if self.legend is None:
            self.legend = VGroup()
        self.legend.add(row)
        if not pop:
            layer = layer_bars(counts, LAYER_COLORS[i])
            self.add(layer)
            self.layers.append(layer)
            grow_bars(self, layer, run_time, extra=[FadeIn(row)])
            return
        r = run_time / 2.0
        k = POP_FRAC * TALLEST / counts.max()
        layer = layer_bars(counts * k, LAYER_COLORS[i])
        self.add(layer)
        self.layers.append(layer)
        grow_bars(self, layer, 1.0 * r, extra=[FadeIn(row)])
        self.play(*[b.animate.stretch(1 / k, dim=1, about_edge=DOWN) for b in layer],
                  run_time=1.0 * r)

    def _drop_layers(self, run_time):
        """Every layer falls back to the axis; the legend fades; the bars stay."""
        bars = [b for layer in self.layers for b in layer]
        shrink_bars(self, bars, run_time, extra=[FadeOut(self.legend)])
        self.remove(*self.layers, *bars, self.legend)   # bars: see _drop_histogram
        self.layers, self.legend = [], None

    # f : the invisible camera jump, then navy in, Hangman list out, Wordle list to
    #     the corner; then the histogram grows back
    def _to_histogram_view(self):
        for m in list(self.mobjects):
            to_view(m)
        f = self.camera.frame
        f.stretch_to_fit_width(WIDTH).stretch_to_fit_height(HEIGHT).move_to(CENTER)

    def _setup_histogram(self):
        self.navy = Rectangle(width=WIDTH * 1.02, height=HEIGHT * 1.02, stroke_width=0,
                              fill_color=BOARD_NAVY, fill_opacity=1.0).move_to(CENTER)
        self.corner = self._list_at(td.WORDLE_LETTERS, td.WORDLE_NAMES, CORNER_SCALE,
                                    ur=CORNER_UR)

    @subscene
    def histogram(self):
        self._to_histogram_view()
        self._setup_histogram()
        self.add(self.navy)
        self.bring_to_back(self.navy)
        self.play(FadeIn(self.navy),
                  FadeOut(self.hang, self.hang_title, self.wordle_title, self.arrow),
                  Transform(self.wordle, self.corner), run_time=1.2)
        self.remove(self.hang, self.hang_title, self.wordle_title, self.arrow)
        self.hang = self.hang_title = self.wordle_title = self.arrow = self.corner = None
        self._grow_histogram(1.5)
        self.bring_to_front(self.wordle)

    # g : dim every tier but the two LOW ones
    @subscene
    def low_tiers(self):
        self.play(*tl.emphasize(self.wordle, LOW_TIERS), run_time=0.8)

    # h : the 1+ low-tier layer
    @subscene
    def low_1(self):
        self._layer("low", 0, 1.0)

    # i : the 2+ low-tier layer
    @subscene
    def low_2(self):
        self._layer("low", 1, 1.0)

    # j : the 3+ low-tier layer
    @subscene
    def low_3(self):
        self._layer("low", 2, 2.0, pop=True)

    # k : the histogram goes; the list returns to the centre, undimmed
    def _setup_list_center(self):
        self.center_list = self._list_at(td.WORDLE_LETTERS, td.WORDLE_NAMES, LIST_SCALE)

    @subscene
    def list_center(self):
        self._setup_list_center()
        self._drop_histogram(1.0)
        self.play(Transform(self.wordle, self.center_list), run_time=1.2)
        self.center_list = None

    # l : the list morphs into the list WITH DOUBLES (LOW splits in three)
    def _setup_doubles(self):
        self.doubles = self._list_at(
            td.WORDLE_DOUBLE_LETTERS, td.WORDLE_DOUBLE_NAMES, LIST_SCALE,
            panel_width=tl.panel_width_for(td.WORDLE_DOUBLE_LETTERS))

    @subscene
    def doubles(self):
        self._setup_doubles()
        self.remove(self.wordle)                 # its copies carry the morph
        tl.morph_into(self, self.wordle, self.doubles, td.WORDLE_LETTERS,
                      td.WORDLE_DOUBLE_LETTERS, None, 2.0, split_from=DOUBLES_ROWS_FROM)
        self.wordle, self.doubles = self.doubles, None

    # m : the list slides off to the right; the histogram grows back
    @subscene
    def histogram_2(self):
        self._grow_histogram(1.5, extra=[self.wordle.animate.shift(RIGHT * WIDTH)])
        self.remove(self.wordle)
        self.wordle = None

    # n : the 1+ duplicate layer
    @subscene
    def dup_1(self):
        self._layer("dup", 0, 1.0)

    # o : the 2+ duplicate layer
    @subscene
    def dup_2(self):
        self._layer("dup", 1, 1.0)

    # p : the 3+ duplicate layer
    @subscene
    def dup_3(self):
        self._layer("dup", 2, 2.0, pop=True)

    # q : the duplicate layers fall back to the axis; the legend fades
    @subscene
    def restore(self):
        self._drop_layers(1.0)

    # r : the 3+ distinct-vowel layer
    @subscene
    def vowel_3(self):
        self._layer("vowel", 0, 1.0)

    # s : the 4+ distinct-vowel layer
    @subscene
    def vowel_4(self):
        self._layer("vowel", 1, 2.0, pop=True)

    # t : everything fades as the navy page turns Wordle's black — scene 10 opens on it
    @subscene
    def to_black(self):
        rest = [m for m in self.mobjects if m is not self.navy]
        self.play(FadeOut(*rest), self.navy.animate.set_fill(WORDLE_BG),
                  run_time=1.2)

