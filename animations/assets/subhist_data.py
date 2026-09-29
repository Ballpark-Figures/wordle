"""Scene 09's sub-histograms — the openers meeting a condition, SOURCED, then cached.

The conditions are math/notebooks/opener_distribution.ipynb's, verbatim, and the build
asserts it reproduces the layer sizes that notebook printed (its cells 13, 14, 15):

  low tier   — tiles from the bottom TWO tiers of math/tiers.py (LOW▲ + LOW▼ =
               FKWV + XZJQ; the user's call, 2026-09-29), counted by TILE, so a
               repeat counts twice: 1+ / 2+ / 3+          (4750 / 692 / 36)
  duplicates — duplicate TILES, 5 - distinct letters: 1+ / 2+ / 3+   (4650 / 465 / 9)
  vowels     — DISTINCT vowels, aeiouy (y always a vowel): 3+ / 4+   (1156 / 20)

Each layer is contained in the one before it, which is ASSERTED (the notebook's
_check_nested), so a nested bar can never stand taller than its parent.

For every layer the cache holds its words and its COUNT PER BAR, aligned to
histogram_cache.json's bars (one entry per distinct bin, ascending) — the heights the
scene draws. Nothing in the scene counts anything.

Regenerate (from this directory):

    ../../.venv/bin/python subhist_data.py
"""
import importlib.util
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "subhist_cache.json")
HIST = os.path.join(HERE, "histogram_cache.json")
TIERS = os.path.join(HERE, "..", "..", "math", "tiers.py")

VOWELS = set("aeiouy")          # the notebook's VOWELS: y always counts
# the sizes opener_distribution.ipynb printed — the build must reproduce them
NOTEBOOK = {"low": [4750, 692, 36], "dup": [4650, 465, 9], "vowel": [1156, 20]}


def _tiers():
    spec = importlib.util.spec_from_file_location("wordle_math_tiers", TIERS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build():
    hist = json.load(open(HIST))
    words, bins = hist["words"], hist["bins"]
    bar_bins = sorted(set(bins))
    low = _tiers().bottom(2)
    feats = {
        "low": lambda w: sum(c in low for c in w),
        "dup": lambda w: 5 - len(set(w)),
        "vowel": lambda w: len(set(w) & VOWELS),
    }
    thresholds = {"low": [1, 2, 3], "dup": [1, 2, 3], "vowel": [3, 4]}
    out = {"bar_bins": bar_bins, "low_letters": "".join(sorted(low)), "layers": {}}
    for fam, ts in thresholds.items():
        layers, prev = [], None
        for t in ts:
            sel = [w for w in words if feats[fam](w) >= t]
            if prev is not None:
                assert set(sel) <= prev, f"{fam} {t}+ is not inside the layer above"
            prev = set(sel)
            per = Counter(b for w, b in zip(words, bins) if w in prev)
            layers.append({"min": t, "n": len(sel), "words": sel,
                           "counts": [per.get(b, 0) for b in bar_bins]})
        assert [l["n"] for l in layers] == NOTEBOOK[fam], (fam, [l["n"] for l in layers])
        out["layers"][fam] = layers
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    print(f"low-tier letters: {d['low_letters']}")
    for fam, layers in d["layers"].items():
        print(f"  {fam}: " + ", ".join(f"{l['min']}+ n={l['n']} (tallest bar "
                                        f"{max(l['counts'])})" for l in layers))
    print(f"wrote {CACHE}")
