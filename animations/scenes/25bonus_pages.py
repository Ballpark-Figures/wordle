"""Scene 25 — the bonus video's topics on the NYT's own pages, over talking head THM
("the best way to get the Sea of Greens achievement, and an analysis of the new
Wordle in One minigame"). Not in Script.md's column 2: the user's ask (2026-10-09).
Navy background (WordleBoardScene), as scene 24.

Opens on an empty Wordle board in a browser window, on from frame 0 (user's call,
2026-10-09), swipes to the Sea of Greens badge, to Wordle in One, back to the empty
board, and CEART is typed into it. Ends with the window on screen.

BEAT MAP
  a sea_of_greens — the empty board slides left inside the window, the badge in
                    from the right; address and tab title cross-fade
  b wordle_in_one — the same to Wordle in One
  c wordle        — the same to the empty Wordle board
  d ceart         — C, E, A, R, T appear one at a time (the page's own states)

REUSE MAP
  browser window    bpkfigures/browser.py `browser_window`, sized as scene 24's
  page-to-page move scene 20's `swipe` (scene 09's swipe, inside the window),
                    `BrowserWindow.swipe_to`
  typing            browser.py `fade_to` between real page states, as 24's clicks
  pages             assets/web_media: sea_of_greens.png and wordle_in_one_puzzle.png
                    are the user's own (logged-in) Safari screenshots, cropped to the
                    page; ceart_0..5 are the assets/web_shots.py `ceart` recipe
  addresses/titles  the pages' own: the badge page's URL as the screenshot shows
                    it, each tab title read from the live page

Wordle in One is subscriber-only, so it cannot be captured logged out (that gets
a paywall); its image is the user's screenshot, under a NEW filename -- manim's
animation cache cannot tell two images apart by their pixels (youtube_card.py).
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.browser import browser_window

MEDIA = Path(__file__).resolve().parent.parent / "assets" / "web_media"
WIN_W = 13.2                                     # as scene 24's window
# (screenshot, address, the page's own tab title)
BADGE = ("sea_of_greens", "nytimes.com/games/wordle/2026-07-10",
         "Friday, July 10, 2026 Wordle puzzle — The New York Times")
IN_ONE = ("wordle_in_one_puzzle", "nytimes.com/games/bonus/wordle-in-one/standard/2026-10-07-8",
          "Wednesday, October 7, 2026 Wordle in 1 — Bonus Puzzles — The New York Times")
WORDLE = ("ceart_0", "nytimes.com/games/wordle/index.html",
          "Wordle — The New York Times")         # as scene 24's


def _shot(name):
    return str(MEDIA / f"{name}.png")


class Scene25(WordleBoardScene):           # navy, as scene 24
    def setup_scene(self):
        name, url, title = WORDLE
        self.win = browser_window(url, title, image=_shot(name), width=WIN_W,
                                  aspect=9 / 16)               # on from frame 0
        self.add(self.win)

    def _swipe(self, page, run_time):
        name, url, title = page
        self.play(self.win.swipe_to(_shot(name), url, title), run_time=run_time)

    # a : the empty board swipes to the Sea of Greens badge
    @subscene
    def sea_of_greens(self):
        self._swipe(BADGE, 1.0)

    # b : the badge swipes to Wordle in One
    @subscene
    def wordle_in_one(self):
        self._swipe(IN_ONE, 1.0)

    # c : Wordle in One swipes back to the empty Wordle board
    @subscene
    def wordle(self):
        self._swipe(WORDLE, 1.0)

    # d : CEART typed, one letter at a time -- each a real state of the page
    @subscene
    def ceart(self):
        for k in range(1, 6):                    # lockstep: five identical keystrokes
            self.play(self.win.fade_to(_shot(f"ceart_{k}")), run_time=0.12)
