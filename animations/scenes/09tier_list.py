"""SCENE 09 — the Hangman video, the poll, and the tier list carried over to Wordle.

BEAT MAP (one subscene per Script.md beat)
  a hangman_video — the dark-mode YouTube watch page for "I Tried to Solve Hangman"
                    fades in (VO 1: "My last video was about Hangman…")
  b poll          — a swipe: the watch page slides off to the LEFT as the dark-mode
                    community poll page slides in from the RIGHT (VO 2: "…I posted
                    this poll 3 days before the Hangman video came out.")
  c hangman_tiers — the poll page fades out; the Hangman tier list fades in with the
                    title "Hangman Tier List" at the top (VO 3)
  d wordle_tiers  — hangman list + title slide LEFT; a copy MORPHS into the Wordle
                    tier list on the right ("Wordle Tier List" fading in as it moves),
                    arrow drawn AFTER — the hangman scene-17 comparison style (VO 4)

REUSE MAP
  watch page      bpkfigures.youtube_card.youtube_watch (as hangman 93youtube_test c)
  poll            bpkfigures.youtube_card.youtube_poll
  tier lists      bpkfigures.tier_list (promoted from hangman's asset): filled_list,
                  morph_into; the LIST_SCALE / LEFT_X / RIGHT_X / LIST_Y / title height,
                  title style (30pt bold BLACK) and the arrow are hangman 17c's
  background      WordleScene (BG_COLOR, the tier-list world's light blue); the two
                  YouTube pages cover it with their own full-frame page

NUMBERS / ORDERINGS — all SOURCED
  video title / channel / views / age / duration: assets/youtube_data (analytics DB,
      committed youtube_cache.json); thumbnail + avatar: assets/youtube_media/fetch.py
  poll: assets/poll_data (hand-transcribed from a screenshot; the API has no posts)
  Hangman tiers: assets/tier_data.HANGMAN_LETTERS (hand-copy of hangman's TIER_LETTERS)
  Wordle tiers:  assets/tier_data.WORDLE_LETTERS (read from math/tiers.py)

d's ROW MAP: hangman TOP → wordle TOP▲, and each hangman HIGH/MID/LOW half onto the
wordle half of the same name; wordle TOP▼ (no hangman counterpart) fades in.

Render:  render 09a --fast (…09d)  /  render 09 sub  for the whole scene
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.youtube_card import youtube_watch, youtube_poll
from bpkfigures import tier_list as tl
from assets.youtube_data import get as yt_get
from assets.poll_data import get as poll_get
from assets import tier_data as td

HANGMAN_VIDEO = yt_get("hangman")
POLL = poll_get("wordle")

# ── tier lists (hangman 17c's layout) ─────────────────────────────────────────
LIST_SCALE = 0.62
LEFT_X, RIGHT_X = -3.45, 3.45
LIST_Y = -0.15
TITLE_BASELINE = 2.78            # hangman 17's TITLE_Y 2.9, as a baseline
TITLE_COLOR = BLACK               # tier-list world uses BLACK labels on the light bg
HANGMAN_TO_WORDLE_ROWS = [0, 2, 3, 4, 5, 6, 7]   # see "d's ROW MAP" above


class Scene09(WordleScene):
    """The Hangman video, the poll, and the tier list. See the module docstring."""

    def setup_scene(self):
        self.video_page = self.poll_page = None
        self.hang = self.hang_title = None
        self.wordle = self.wordle_title = None
        self.arrow = None

    def _title(self, text, x):
        # on a shared BASELINE, so "Hangman" (descender) and "Wordle" share one line
        return crisp_text(text, font_size=30, color=TITLE_COLOR, weight=BOLD,
                          baseline_at=(x, TITLE_BASELINE))

    # a : dark-mode watch page for the Hangman video fades in
    def _setup_hangman_video(self):
        self.video_page = youtube_watch(**HANGMAN_VIDEO, dark=True)

    @subscene
    def hangman_video(self):
        self._setup_hangman_video()
        self.play(FadeIn(self.video_page), run_time=0.8)

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
        self.remove(self.video_page)
        self.video_page = None

    # c : the poll page leaves; the Hangman tier list + its title fade in
    def _setup_hangman_tiers(self):
        self.hang = tl.filled_list(td.HANGMAN_LETTERS, names=td.HANGMAN_NAMES,
                                   scale=LIST_SCALE).move_to([0, LIST_Y, 0])
        self.hang_title = self._title("Hangman Tier List", 0)

    @subscene
    def hangman_tiers(self):
        self._setup_hangman_tiers()
        self.play(FadeOut(self.poll_page), run_time=0.6)
        self.poll_page = None
        self.play(FadeIn(self.hang, self.hang_title), run_time=0.8)

    # d : hangman list slides left; a copy morphs into the Wordle list; arrow after
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
                      HANGMAN_TO_WORDLE_ROWS, 2.0, extra=[FadeIn(self.wordle_title)])
        self.play(GrowArrow(self.arrow), run_time=0.5)
