"""Scene 24 — turning on Hard Mode in the real NYT Wordle, for talking head THM
("depending on how you play Wordle, ignoring information might not be allowed").
Not in Script.md's column 2: the user's ask. Navy background, as scene 16's
browser windows.

The page is NYT Wordle in DARK mode, captured live (assets/web_shots.py recipe
`wordle`, ad slot hidden -- user's call). A cursor clicks the gear, the Settings
panel opens, the cursor clicks the Hard Mode switch and it turns on. Every cursor
target is the element's box RECORDED by the capture (`wordle_boxes.json`), not
eyeballed. Ends with the window and cursor on screen.

BEAT MAP
  a settings — the cursor fades in, glides to the gear, clicks; Settings opens
  b hard     — it glides to the Hard Mode switch and clicks; the switch turns on

REUSE MAP
  browser window    bpkfigures/browser.py `browser_window`, as scenes 16 and 21-23
  page states       browser.py `fade_to` (added for this): game -> settings -> hard
  cursor, click     bpkfigures/cursor.py `Cursor` (`glide_to`, `click`)
  click sound       sfx `click` (music-library), on the press
  targets           browser.py `page_point` on web_media/wordle_boxes.json
"""
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.browser import browser_window
from bpkfigures.cursor import Cursor

MEDIA = Path(__file__).resolve().parent.parent / "assets" / "web_media"
BOXES = json.loads((MEDIA / "wordle_boxes.json").read_text())
URL = "nytimes.com/games/wordle/index.html"
TITLE = "Wordle — The New York Times"      # the page's own <title>
WIN_W = 13.2                                     # as the sponsor windows
CURSOR_START = (1250, 700)                       # screenshot pixels, below-left of the gear


def _shot(state):
    return str(MEDIA / f"wordle_{state}.png")


def _centre(box):
    x0, y0, x1, y1 = box
    return (x0 + x1) / 2, (y0 + y1) / 2


class Scene24(WordleBoardScene):
    def setup_scene(self):
        self.win = browser_window(URL, TITLE, image=_shot("game"), width=WIN_W,
                                  aspect=9 / 16)               # on from frame 0
        self.add(self.win)
        self.cursor = None

    def _target(self, name):
        return self.win.page_point(*_centre(BOXES[name]))

    # a : the cursor clicks the gear and Settings opens
    @subscene
    def settings(self):
        self.cursor = Cursor().point_to(self.win.page_point(*CURSOR_START))
        self.play(FadeIn(self.cursor), run_time=0.3)
        self.play(self.cursor.glide_to(self._target("gear")), run_time=0.8)
        self.sfx("click")
        self.play(self.cursor.click(), run_time=0.35)
        self.play(self.win.fade_to(_shot("settings")), run_time=0.15)

    # b : the cursor clicks the Hard Mode switch and it turns on
    @subscene
    def hard(self):
        self.play(self.cursor.glide_to(self._target("hard_mode")), run_time=0.8)
        self.sfx("click")
        self.play(self.cursor.click(), run_time=0.35)
        self.play(self.win.fade_to(_shot("hard")), run_time=0.2)
