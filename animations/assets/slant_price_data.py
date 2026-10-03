"""Scene 18's numbers — the top-1000 letter coverage table and the SLANT then PRICE
strategy. Cached.

The scene reads `slant_price_cache.json`; a render imports no solver. Regenerate
(from this directory):

    ../../.venv/bin/python slant_price_data.py

Provenance:
  coverage[letter] = [first1, first2]  -- number of PATHS (every tree x every answer,
                    the top 1000 openers' optimal trees) whose first 1 / first 2
                    guesses contain the letter, from math/data/shared/tiers/
                    coverage_top1000.csv (written by letter_explorer.ipynb via
                    math/letter_coverage.py). `paths` is the denominator (2,315,000).
                    The trees are the depth-6 CONSTRAINED optima (wordle/CLAUDE.md).
  strategy        -- SLANT; if its reply shows at least 3 greys, PRICE; then a
                    uniformly random consistent answer.
    mean          -- expected guesses OUTRIGHT, from math/data/shared/secondexact/
                    exact_g3.csv (secondexact, exact) -- and RE-CHECKED against
                    math/data/shared/ladder/win_named_cap6.csv (the same strategy as
                    the ladder `slant price<3`, priced by openexact.evaluate_ladder in
                    numpy, sharing no code with the C), which must agree to 1e-5.
    win_rate      -- the fraction of those same untruncated games won in <= 6, from
                    win_named_cap6.csv (exact, no sampling).
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "slant_price_cache.json")
SHARED = os.path.join(HERE, "..", "..", "math", "data", "shared")
COVERAGE = os.path.join(SHARED, "tiers", "coverage_top1000.csv")
EXACT_G3 = os.path.join(SHARED, "secondexact", "exact_g3.csv")
LADDER_WIN = os.path.join(SHARED, "ladder", "win_named_cap6.csv")

OPENER, SECOND = "slant", "price"     # the script's words
LADDER = "slant price<3"              # matched < 3 after one guess == at least 3 greys
NUM_TREES = 1000                      # the script's "Top 1000 Openers"


def _rows(path):
    with open(path) as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def _coverage():
    stamp = None
    with open(COVERAGE) as f:
        for line in f:
            if line.startswith("# settings "):
                stamp = dict(kv.split("=", 1) for kv in line[11:].split())
    assert stamp is not None, "coverage file has no settings stamp"
    assert int(stamp["num_trees"]) == NUM_TREES and stamp["solver"] == "optturns", stamp
    counts = {r["letter"]: [int(r["first1"]), int(r["first2"])] for r in _rows(COVERAGE)}
    assert len(counts) == 26
    return int(stamp["paths"]), counts


def _strategy():
    g3 = [r for r in _rows(EXACT_G3) if r["opener"] == OPENER]
    assert len(g3) == 1 and g3[0]["second"] == SECOND, g3
    mean = float(g3[0]["expected"])
    lad = [r for r in _rows(LADDER_WIN) if r["ladder"] == LADDER]
    assert len(lad) == 1, lad
    assert abs(float(lad[0]["mean"]) - mean) < 1e-5, (lad[0]["mean"], mean)
    assert int(lad[0]["cap"]) == 6
    return {"opener": OPENER, "second": SECOND, "min_grays": 3,
            "mean": mean, "win_rate": float(lad[0]["win_rate"])}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    paths, counts = _coverage()
    data = {"paths": paths, "coverage": counts, "strategy": _strategy()}
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    for c in "eartslionc":
        a, b = counts[c]
        print(f"{c.upper()}  first1 {100 * a / paths:6.2f}%   first2 {100 * b / paths:6.2f}%")
    s = data["strategy"]
    print(f"{s['opener']} / {s['second']}: mean {s['mean']:.6f}, win rate {s['win_rate']:.6f}")
    print(f"wrote {CACHE}")
