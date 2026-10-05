"""Scratch: a DARK-MODE striped table on BOARD_NAVY (style trial, not a script scene).

The shared ``bpkfigures.table.get_table`` with no card, white ink, and the zebra
stripes in white at low opacity, instead of grey on the cream card.

Beat map:
  a  stripes at 0.07 opacity
  b  stripes at 0.12 opacity

Data: rows read verbatim from math/data/shared/optturns/opener_totals.csv
(constrained optima: minimum total guesses subject to a 6-guess guarantee).
"""
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.table import get_table

CSV = Path(__file__).resolve().parents[2] / "math/data/shared/optturns/opener_totals.csv"
WORDS = ["salet", "reast", "crate", "trace", "slate", "crane", "slant"]
TEXT = WHITE


def _rows():
    with open(CSV) as f:
        by_word = {r["word"]: r for r in csv.DictReader(f)}
    return [[w.upper(), by_word[w]["total"], by_word[w]["expected"]] for w in WORDS]


def _table(stripe_opacity):
    return get_table(["opener", "total guesses", "expected"], _rows(),
                     title="Best openers", card=False, ink=TEXT,
                     stripe_color=WHITE, stripe_opacity=stripe_opacity)


class TableTest(WordleBoardScene):
    # a : stripes at 0.07 opacity
    @still
    def stripes_light(self):
        self.add(_table(0.07))

    # b : stripes at 0.12 opacity
    @still
    def stripes_strong(self):
        self.add(_table(0.12))
