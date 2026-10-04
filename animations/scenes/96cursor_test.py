"""TEST — the shared mouse cursor (bpkfigures/cursor.py), for THM's click on the
hard-mode setting. Not a content scene: the button is a stand-in, and there is no
sound until the click effect is in the library.

BEAT MAP
  a glide — the cursor fades in and glides to the button
  b click — one click on it
  c both  — back out, then glide and click as ONE play (the Succession form)
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.cursor import Cursor

START = np.array([4.5, -2.5, 0])


class Scene96(WordleScene):
    def setup_scene(self):
        self.button = RoundedRectangle(width=3.2, height=0.9, corner_radius=0.2,
                                       fill_color=CARD_FILL, fill_opacity=1.0,
                                       stroke_width=0)
        label = crisp_text("Hard Mode", font_size=32, color=ACCENT_FILL)
        self.add(VGroup(self.button, label.move_to(self.button)))
        self.cursor = None

    # a : the cursor fades in and glides to the button
    @subscene
    def glide(self):
        self.cursor = Cursor().point_to(START)
        self.play(FadeIn(self.cursor), run_time=0.3)
        self.play(self.cursor.glide_to(self.button.get_center()), run_time=0.8)

    # b : one click
    @subscene
    def click(self):
        self.play(self.cursor.click(), run_time=0.35)

    # c : out and back in, glide + click as one play
    @subscene
    def both(self):
        self.play(self.cursor.glide_to(START), run_time=0.6)
        self.play(Succession(self.cursor.glide_to(self.button.get_center()),
                             self.cursor.click(), lag_ratio=1.0), run_time=1.15)
