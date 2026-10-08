"""Scene 21 — 80,000 Hours' research pages and podcast, for the sponsor read (the
script's unlabelled row 34, VO: "how many lives does a typical doctor save" or "how
does your impact vary over the different problems you could work on?" ... "Their
guests include Elie Hassenfeld ... Emily Oster ... and Nate Silver"). Light blue
background.

SCENE 22 IS MERGED INTO THIS ONE (user's call, 2026-10-08), and 22 is not
renumbered away: the slot is simply empty, so 23 and 24 keep their numbers.

Opens on the 80,000 Hours homepage in a browser window, up from frame 0 (user's
call, 2026-10-08), and swipes page to page: the doctor article, the world-problems
page, the podcast homepage, then the three episodes. Ends with the window on screen.

BEAT MAP
  a doctor   — the homepage slides left inside the window, the doctor article in
               from the right; address and tab title cross-fade (user's added beat)
  b problems — the same to the world-problems page
  c podcast  — to the podcast homepage (user's added beat)
  d elie     — to Elie Hassenfeld's episode (was 22's opening page)
  e oster    — to Emily Oster's (was 22a)
  f silver   — to Nate Silver's (was 22b)

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
        self.win = sponsor_pages.window("80k_home")        # on from frame 0
        self.add(self.win)

    # a : the homepage swipes to the doctor article
    @subscene
    def doctor(self):
        self.play(sponsor_pages.swipe(self.win, "80k_doctor"), run_time=1.0)

    # b : the doctor article swipes to the world-problems page
    @subscene
    def problems(self):
        self.play(sponsor_pages.swipe(self.win, "80k_problems"), run_time=1.0)

    # c : the world-problems page swipes to the podcast homepage
    @subscene
    def podcast(self):
        self.play(sponsor_pages.swipe(self.win, "80k_podcast"), run_time=1.0)

    # d : the podcast homepage -> Elie Hassenfeld
    @subscene
    def elie(self):
        self.play(sponsor_pages.swipe(self.win, "80k_elie"), run_time=1.0)

    # e : Elie Hassenfeld -> Emily Oster
    @subscene
    def oster(self):
        self.play(sponsor_pages.swipe(self.win, "80k_oster"), run_time=1.0)

    # f : Emily Oster -> Nate Silver
    @subscene
    def silver(self):
        self.play(sponsor_pages.swipe(self.win, "80k_silver"), run_time=1.0)
