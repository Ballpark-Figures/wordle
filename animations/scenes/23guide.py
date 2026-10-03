"""Scene 23 — the 80,000 Hours sign-up page, for the sponsor read (the script's
unlabelled row 34, VO: "signing up for their mailing list ... this entire book of
career advice ... 80000hours.org/ballpark"). Light blue background.

Opens on the top of the page in the browser window, up from frame 0, and scrolls
down it one window height at a time, a subscene per scroll so the edit sets the
pause between them. The address bar reads 80000hours.org/ballpark, the read's link. Ends with
the window on screen.

BEAT MAP
  a scroll_one   — the page scrolls down one window height
  b scroll_two   — and another
  c scroll_three — and another

REUSE MAP
  browser window    assets/sponsor_pages.py `window`, as scenes 21-22
  scrolling         bpkfigures/browser.py `BrowserWindow.scroll_by` (added for this)
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from assets import sponsor_pages

SCROLL = 1.0           # each scroll, in window heights


class Scene23(WordleScene):
    def setup_scene(self):
        self.win = sponsor_pages.window("80k_guide")       # on from frame 0
        self.add(self.win)

    # a : the page scrolls down one window height
    @subscene
    def scroll_one(self):
        self.play(self.win.scroll_by(SCROLL), run_time=1.5)

    # b : another
    @subscene
    def scroll_two(self):
        self.play(self.win.scroll_by(SCROLL), run_time=1.5)

    # c : another
    @subscene
    def scroll_three(self):
        self.play(self.win.scroll_by(SCROLL), run_time=1.5)
