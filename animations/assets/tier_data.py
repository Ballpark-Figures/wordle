"""The two tier lists scene 09 shows — SOURCED, never invented here.

HANGMAN: the Hangman video's main (equal-weighted) tier list, in its within-tier
display order. HAND-COPIED from hangman/animations/assets/tier_list.py's
TIER_LETTERS (itself the order letter_analysis.ipynb generated), with that video's
seven tier names. Copied rather than imported so a render never reaches into
another video's repo; if the hangman list ever changed, change it here too.

WORDLE: the user's hand ranking recorded in math/tiers.py (TIERS), read from there
so there is ONE copy. Within-tier order is as recorded, which matches the greedy
order in math/data/shared/tiers/order_r1_top1000.csv. Its eight tier names are the
user's call (2026-09-29): TOP/HIGH/MID/LOW, each in two halves.
"""
from pathlib import Path
import importlib.util

HANGMAN_LETTERS = ["EIA", "SR", "TNO", "LDC", "PUGMBH", "FYVWK", "XZJQ"]
HANGMAN_NAMES = [("TOP", None), ("HIGH", "up"), ("HIGH", "down"), ("MID", "up"),
                 ("MID", "down"), ("LOW", "up"), ("LOW", "down")]

_TIERS = Path(__file__).resolve().parents[2] / "math" / "tiers.py"
_spec = importlib.util.spec_from_file_location("wordle_math_tiers", _TIERS)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

WORDLE_LETTERS = list(_mod.TIERS)
WORDLE_NAMES = [(w, a) for w in ("TOP", "HIGH", "MID", "LOW") for a in ("up", "down")]
assert len(WORDLE_NAMES) == len(WORDLE_LETTERS), "tier names and tiers disagree"
