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
"""
import csv
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import *

DATA = Path(__file__).resolve().parents[2] / "math" / "data" / "shared"


class Bonus(WordleScene):
    def setup_scene(self):
        pass

    # a : plumbing test — top 5 openers by total guesses
    @still
    def smoke_table(self):
        with open(DATA / "optturns" / "opener_totals.csv") as f:
            rows = sorted((r for r in csv.DictReader(f) if r["total"]),
                          key=lambda r: (int(r["total"]), r["word"]))[:5]
        self.add(get_table(
            ["Opener", "Total guesses", "Average"],
            [[r["word"].upper(), f"{int(r['total']):,}", r["expected"]] for r in rows],
            title="Best openers"))
