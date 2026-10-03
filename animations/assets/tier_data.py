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

# HARD MODE's list (scene 19za): the user's cuts, recorded as math/tiers.py HARD_TIERS
# (the order is order_r1_top1000_hardturns.csv's; the CUTS are editorial). None until
# they are recorded — the scene then leaves the list out rather than invent one.
WORDLE_HARD_LETTERS = list(getattr(_mod, "HARD_TIERS", ())) or None

# ── the Wordle list WITH DOUBLES (09k) ────────────────────────────────────────
# The singles and doubles ranked together: the greedy order in
# math/data/shared/tiers/order_r2_top1000.csv (max_repeat=2 — the file carries the
# ORDER; the tier CUTS are editorial). The user's cuts (2026-09-29): LOW splits in
# three — LOW▲ everything up to V, LOW■ (a square) everything up to SS, LOW▼
# everything up to Q — and every token after Q is not shown. The six tiers above
# LOW are math/tiers.py's, unchanged. A token is a letter or a double ("ee").
_ORDER_R2 = Path(__file__).resolve().parents[2] / "math" / "data" / "shared" / "tiers" \
    / "order_r2_top1000.csv"
LOW_CUTS = ["v", "ss", "q"]          # the LAST token of LOW▲, LOW■, LOW▼


def _double_rows():
    lines = [l for l in _ORDER_R2.read_text().splitlines() if l and not l.startswith("#")]
    order = [l.split(",")[1] for l in lines[1:]]
    upper = [list(t.lower()) for t in WORDLE_LETTERS[:6]]
    first_low = len([c for t in upper for c in t])
    assert sorted(order[:first_low]) == sorted(c for t in upper for c in t), \
        "order_r2's top tokens are not math/tiers.py's upper six tiers"
    rows, i = [], first_low
    for cut in LOW_CUTS:
        j = order.index(cut) + 1
        rows.append(order[i:j])
        i = j
    singles = lambda r: {t for t in r if len(t) == 1}
    assert singles(rows[0]) | singles(rows[1]) == set(WORDLE_LETTERS[6].lower()), rows
    assert singles(rows[2]) == set(WORDLE_LETTERS[7].lower()), rows
    return [[c.upper() for c in t] for t in WORDLE_LETTERS[:6]] + \
        [[t.upper() for t in r] for r in rows]


WORDLE_DOUBLE_LETTERS = _double_rows()
WORDLE_DOUBLE_NAMES = WORDLE_NAMES[:6] + [("LOW", "up"), ("LOW", "square"),
                                          ("LOW", "down")]

# ── the lists' panels on the navy background (09e on, and scene 18) ───────────
# Moved here from scene 09 when scene 18 needed the same colour.
from manim import WHITE, interpolate_color                     # noqa: E402
from bpkfigures.style import BOARD_NAVY                         # noqa: E402
PANEL_ON_NAVY = interpolate_color(BOARD_NAVY, WHITE, 0.22)     # lighter panels
