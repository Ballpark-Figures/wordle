"""SCRATCH — exercises BpkScene.sfx end to end. Not a content scene; delete when done.

Shaped to hit every branch of the sound-effect path, including the ones that must
stay SILENT:

  a silent    — no sfx at all: proves an untouched subscene still renders with NO
                audio stream, and feeds the stitch's mixed silent/sounded branch
  b one_cue   — a single cue at the top of the body (the ordinary case)
  c two_cues  — two cues, one offset with `at=`, one attenuated with `gain=`
  d after     — no sfx, immediately AFTER a sounded subscene: proves _reset_audio
                discards the previous clip's audio rather than carrying it forward
  e in_hold   — a cue deliberately inside the TRAILING hold: proves the warning fires
  f still     — a @still with a cue: proves the no-op + warning, and no crash

The library is pointed at a scratch dir via BPK_SFX_DIR (see music-library/sfx),
so this needs no committed sound files:

    BPK_SFX_DIR=<dir with click.wav> render 98 all --no-sound
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *


class Scene98(WordleScene):
    def setup_scene(self):
        pass

    # a : no sfx — the silent control
    @subscene
    def silent(self):
        self._setup_dot()
        self.play(FadeIn(self.dot), run_time=0.6)

    # b : one cue at the top of the body
    @subscene
    def one_cue(self):
        self.sfx("click")
        self.play(self.dot.animate.shift(RIGHT * 2), run_time=0.8)

    # c : two cues — an offset one and an attenuated one
    @subscene
    def two_cues(self):
        self.sfx("click", at=0.4)
        self.sfx("click", gain=-6)
        self.play(self.dot.animate.shift(LEFT * 4), run_time=1.2)

    # d : no sfx, straight after a sounded subscene
    @subscene
    def after(self):
        self.play(self.dot.animate.set_color(ACCENT_GOLD), run_time=0.6)

    # e : a cue inside the trailing hold — should WARN
    @subscene
    def in_hold(self):
        self.play(self.dot.animate.shift(UP), run_time=0.5)
        self.wait(0.9)
        self.sfx("click")

    # f : a @still with a cue — should no-op and WARN
    @still
    def still_cue(self):
        self.sfx("click")
        self.add(crisp_text("still", font_size=72))

    def _setup_dot(self):
        self.dot = Dot(radius=0.4, color=ACCENT_FILL)
