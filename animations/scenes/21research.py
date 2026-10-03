"""Scene 21 — 80,000 Hours' research pages, for the sponsor read (the script's
unlabelled row 34, VO: "how many lives does a typical doctor save" or "how does
your impact vary over the different problems you could work on?"). Light blue
background.

Opens on the doctor article in a browser window, up from frame 0, and swipes to the
world-problems page. Ends with the window on screen.

BEAT MAP
  a problems — the page slides left inside the window, the world-problems page in
               from the right; address and tab title cross-fade

REUSE MAP
  browser window    bpkfigures/browser.py `browser_window`, as scene 16
  pages             assets/sponsor_pages.py (screenshots from assets/web_shots.py)
  page-to-page move scene 09's swipe (09tier_list.py:179: old off LEFT, new in from
                    the right, run 1.0) -- but INSIDE the window only, via
                    `BrowserWindow.swipe_to`
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets import sponsor_pages


class Scene21(WordleScene):
    def setup_scene(self):
        self.win = sponsor_pages.window("80k_doctor")      # on from frame 0
        self.add(self.win)

    # a : the doctor article swipes to the world-problems page
    @subscene
    def problems(self):
        self.play(sponsor_pages.swipe(self.win, "80k_problems"), run_time=1.0)
