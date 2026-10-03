"""Scene 23 — the 80,000 Hours sign-up page, for the sponsor read (the script's
unlabelled row 34, VO: "signing up for their mailing list ... this entire book of
career advice ... 80000hours.org/ballpark"). Light blue background.

A STILL: the page in the browser window, nothing moving, so `render 23a` writes a
PNG for the edit to hold as long as the VO needs.

BEAT MAP
  a guide — the get-the-guide page in the browser window

REUSE MAP
  browser window    assets/sponsor_pages.py `window`, as scenes 21-22
  still frame       @still, as hangman 93youtube_test.py
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets import sponsor_pages


class Scene23(WordleScene):
    def setup_scene(self):
        pass

    # a : the sign-up page
    @still
    def guide(self):
        self.add(sponsor_pages.window("80k_guide"))
