"""Scene 22 — 80,000 Hours' podcast episodes, for the sponsor read (the script's
unlabelled row 34, VO: "Their guests include Elie Hassenfeld ... Emily Oster ...
and Nate Silver"). Light blue background.

Opens on the Elie Hassenfeld episode in a browser window, up from frame 0, then
swipes to Emily Oster's and then Nate Silver's. Ends with the window on screen.

BEAT MAP
  a oster  — Elie Hassenfeld's page slides left, Emily Oster's in from the right
  b silver — Emily Oster's page slides left, Nate Silver's in from the right

REUSE MAP
  browser window    bpkfigures/browser.py `browser_window`, as scene 16
  pages             assets/sponsor_pages.py (screenshots from assets/web_shots.py)
  page-to-page move scene 21's `swipe` (scene 09's swipe, inside the window)
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets import sponsor_pages


class Scene22(WordleScene):
    def setup_scene(self):
        self.win = sponsor_pages.window("80k_elie")        # on from frame 0
        self.add(self.win)

    # a : Elie Hassenfeld -> Emily Oster
    @subscene
    def oster(self):
        self.play(sponsor_pages.swipe(self.win, "80k_oster"), run_time=1.0)

    # b : Emily Oster -> Nate Silver
    @subscene
    def silver(self):
        self.play(sponsor_pages.swipe(self.win, "80k_silver"), run_time=1.0)
