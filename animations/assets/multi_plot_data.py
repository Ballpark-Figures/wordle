"""Scene 16s-v's chart — average MISSES against the number of Wordles. SOURCED, then
cached.

    ../../.venv/bin/python multi_plot_data.py     # (from this directory)

AVERAGE MISSES = MEAN TOTAL GUESSES - k. Every board takes exactly one correct guess
(the answers are distinct, so no guess solves two), so whatever a game spends past k
is a miss. That subtraction is the only arithmetic here; every mean is the number the
run itself wrote in its summary block, read by math/tools/multiwordle_report.py's own
patterns.

PROVISIONAL, AND SAY SO (user's call, 2026-10-01: "build it with the best you have,
we'll come back with better data"). The script wants the BEST 1-, 2- and 3-word
opener at each number of Wordles; those races are queued, not run. Until then:

  1/2/3-word lines — math/multiwordle.py's `greedy` rule (the scene's own strategy:
      fewest candidates, a random candidate) with ONE fixed opening across every k,
      the head of each size's singleton ranking: LATEN, CLINT SOARE, CANST HORDE
      BLIMP, 1,000,000 games per cell, k = 1..32.
  Improved Strategy — `minavg`, only where it has been raced: the leading single
      word at k = 2, 4, 8, 16 (CANST, CLAPT, COMPT, TAMED). k = 8's race stopped
      at 51,200 games. A DIFFERENT OPENER at each point, and nothing in between.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.join(HERE, "..", "..", "math")
DIR = os.path.join(MATH, "data", "shared", "multiwordle")
CACHE = os.path.join(HERE, "multi_plot_cache.json")

KS = list(range(1, 33))
OPENERS = {1: "laten", 2: "clint-soare", 3: "canst-horde-blimp"}
TRIALS = 1000000
MINAVG_KS = [2, 4, 8, 16]


def _summary(k, stem):
    """(mean, stderr) from the run's own summary: the CSV's tail if it is here, else
    the committed .summary digest of it (the CSVs are gitignored -- too big)."""
    sys.path.insert(0, os.path.join(MATH, "tools"))
    from multiwordle_report import MEAN
    base = os.path.join(DIR, f"k{k}_{stem}_t{TRIALS}_s0.csv")
    for path in (base, base + ".summary"):
        if os.path.exists(path):
            with open(path, "rb") as f:
                f.seek(max(0, os.path.getsize(path) - 4000))
                m = MEAN.search(f.read().decode("utf-8", "replace"))
            if m:
                return float(m.group(1)), float(m.group(2))
    raise FileNotFoundError(f"no summary for k={k} {stem}")


def _race_head(k):
    """(opening, games, mean, stderr) of the live leader of the minavg race at k."""
    path = os.path.join(DIR, f"race_minavg_k{k}_guess_sig5_s0.csv")
    rows = [l for l in open(path) if not l.startswith("#")]
    head = rows[0].strip().split(",")
    lead = dict(zip(head, rows[1].strip().split(",")))
    assert lead["status"] == "live", path
    return lead["opening"], int(lead["games"]), float(lead["mean"]), float(lead["stderr"])


def _build():
    out = {"ks": KS, "lines": {}, "improved": []}
    for n, stem in OPENERS.items():
        pts = []
        for k in KS:
            mean, se = _summary(k, stem)
            pts.append({"k": k, "misses": round(mean - k, 4), "stderr": se})
        out["lines"][str(n)] = {"opening": stem.replace("-", " "), "points": pts}
    for k in MINAVG_KS:
        op, games, mean, se = _race_head(k)
        out["improved"].append({"k": k, "opening": op, "games": games,
                                "misses": round(mean - k, 4), "stderr": se})
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    for n, ln in data["lines"].items():
        print(f"{n}-word {ln['opening'].upper()}: " +
              " ".join(f"{p['k']}:{p['misses']:.3f}" for p in ln["points"]))
    print("improved (minavg race heads): " +
          " ".join(f"{p['k']}:{p['opening']}:{p['misses']:.3f}" for p in data["improved"]))
    print(f"wrote {CACHE}")
