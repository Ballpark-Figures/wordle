"""BONUS video graphics — no script. Each graphic is one @still method, added on
request ("make a table of ..."), and renders as one PNG.

Render from bonus/scenes/ with --stills so it lands in DaVinci:

    render 01a --stills

That copies the PNG to <repo>/edit_clips_bonus/ and imports it into the `Bonus`
bin of the open DaVinci project; a re-render refreshes it in place, including any
copy already on the timeline. The main video's edit_clips/ and bins are untouched.

Every number shown is READ from the pipeline's committed files, never typed in.

BEAT MAP (one line per graphic, in order):
  smoke_table — plumbing test: top 5 openers from opener_totals.csv
  today_board — channel post: NEWER WORDY VIDEO HOURS AFTER scored against TODAY, TODAY unscored
  title_mockup — title-card mockup

EVERY bonus still is on BOARD_NAVY (user's call, 2026-10-10: the main video is
almost all navy), hence the WordleBoardScene base.

REUSE MAP — every kind of still copies the MAIN VIDEO's own version of it.
Before the FIRST still of a new kind, find that version in animations/scenes/ and
add a line here; every later still of the kind follows the line.
  table      -> animations/assets/navy_table.py `navy_table`: scenes 10/14/19's
                convention (no card, white title, bold white heads, faint white
                stripes on the navy), collected into one function. NOT
                bpkfigures.table.get_table, which is the cream-card table.
  browser    -> bpkfigures/browser.py `browser_window` at scene 24/25's width
                (WIN_W 13.2); page screenshots from animations/assets/web_shots.py
                recipes into assets/web_media/ (scene 25's REUSE MAP).
  title card -> yahtzee/animations/scenes/00transitions.py `_card` (Wordle has no
                title cards): crisp_text BOLD, built at TITLE_BASE_FS and scaled by
                TITLE_SCALE (so it never wraps), centred. WHITE, not yahtzee's
                black, because it sits on navy: the main video's titles on navy
                are white (08histogram.py's heading).
"""
import csv
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import *
from assets.navy_table import navy_table

MATH = Path(__file__).resolve().parents[2] / "math"
DATA = Path(__file__).resolve().parents[2] / "math" / "data" / "shared"

# title cards: yahtzee 00transitions' values, carried over verbatim
TITLE_BASE_FS = 20     # built at this (under the crisp_text wrap threshold)...
TITLE_SCALE = 3.0      # ...then scaled to its final size


class Bonus(WordleBoardScene):
    def setup_scene(self):
        pass

    # a : plumbing test — top 5 openers by total guesses
    @still
    def smoke_table(self):
        with open(DATA / "optturns" / "opener_totals.csv") as f:
            rows = sorted((r for r in csv.DictReader(f) if r["total"]),
                          key=lambda r: (int(r["total"]), r["word"]))[:5]
        self.add(navy_table(
            ["Opener", "Total Guesses", "Average"],
            [[r["word"].upper(), f"{int(r['total']):,}", r["expected"]] for r in rows],
            title="Best Openers"))

    # b : channel post — five guesses scored against TODAY, then TODAY typed, unscored
    @still
    def today_board(self):
        sys.path.insert(0, str(MATH))
        from wordle import pattern
        from assets.board import GAP, get_scored_row, get_typed_row

        self.camera.background_color = BOARD_NAVY
        answer = "today"
        guesses = ["newer", "wordy", "video", "hours", "after"]
        rows = [get_scored_row(g, pattern(g, answer)) for g in guesses]
        rows.append(get_typed_row(answer))
        board = VGroup(*rows).arrange(DOWN, buff=GAP).scale(1.2).move_to(ORIGIN)
        self.add(board)

    def _title_card(self, name):
        """A title card: yahtzee 00transitions' `_card`, in white on the navy."""
        return crisp_text(name, font_size=TITLE_BASE_FS, color=WHITE,
                          weight="BOLD").scale(TITLE_SCALE).move_to(ORIGIN)

    # c : title-card mockup
    @still
    def title_mockup(self):
        self.add(self._title_card("Antiwordle"))
