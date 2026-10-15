"""Scene 08's opener histogram — every legal opener, SOURCED, then cached.

The same histogram as scene 01 (same sweep, same 0.01 bins), drawn as a plain bar
chart, plus the handful of figures scene 08 marks on it. This module reads the
committed sweep and writes `histogram_cache.json`; the SCENE reads that cache, so a
render imports nothing from the pipeline and the numbers sync through git.

Regenerate (from this directory):

    ../../.venv/bin/python histogram_data.py

Provenance for everything it writes:
  total     — math/data/shared/optturns/opener_totals.csv `total`: the optimal total
              guesses over the 2315 answers, SUBJECT TO solving each within 6
  bin       — floor(total / 2315 / 0.01), math/tools/report.py's rule, the same as
              intro_data.py, so 08's stacks are 01's stacks
  label     — total / 2315 rounded to 2 dp (01's rule): SALET's "3.42 guesses"
  within    — the words whose average is within d of the best, for the VO's d =
              0.01, 0.1, 0.2. Tested in INTEGERS, total - best <= d * 2315, so no
              float compare decides a boundary. Counts 8 / 1480 / 6908, which are
              the VO's "8", "almost 1500" and "the majority".
  top       — the 1000 best openers, by (total, word). The cut SPLITS A TIE at 8123,
              broken on the word exactly as math/tools/tree_states.py --top does
  stats     — mean and median of total / 2315, over every opener and over the
              openers that are answer words (math/data/shared/words/mystery.txt).
              These are the figures math/notebooks/opener_distribution.ipynb prints
              ("mean 3.6259 median 3.6138", "mean 3.6073 median 3.5922"), and the
              build asserts it reproduces them.

STACK ORDER is a presentation choice: each stack runs bottom to top, fewest average
guesses at the bottom, word as the tie-break. So SALET is the bottom of the left bar,
and every "within d" / top-1000 set fills each stack from the bottom up. Unlike
scene 01 nothing is pinned or nudged.
"""
import csv
import json
import math
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "histogram_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
TOTALS = os.path.join(MATH, "data", "shared", "optturns", "opener_totals.csv")
MYSTERY = os.path.join(MATH, "data", "shared", "words", "mystery.txt")

N_ANSWERS = 2315
BIN = 0.01
WITHIN = ["0.01", "0.1", "0.2"]        # the VO's margins, as written
TOP = 1000
# the notebook's printed figures, to 4 dp — the build must reproduce them
NOTEBOOK = {"all": (3.6259, 3.6138), "answers": (3.6073, 3.5922)}


def _build():
    rows = list(csv.DictReader(open(TOTALS)))
    assert len(rows) == 12972 and all(r["total"] for r in rows)
    rows.sort(key=lambda r: (int(r["total"]), r["word"]))
    words = [r["word"] for r in rows]
    totals = [int(r["total"]) for r in rows]
    bins = [int(math.floor(t / N_ANSWERS / BIN)) for t in totals]
    labels = [f"{t / N_ANSWERS:.2f}" for t in totals]
    row, seen = [], {}
    for b in bins:                       # already in (total, word) order
        row.append(seen.get(b, 0))
        seen[b] = row[-1] + 1

    best = totals[0]
    within = {d: [w for w, t in zip(words, totals)
                  if (t - best) * 100 <= round(float(d) * 100) * N_ANSWERS]
              for d in WITHIN}
    # the 1000th and 1001st TIE (total 8123), so "the top 1000" needs a tie rule:
    # math/tools/tree_states.py's own, sorted by (total, word) — the analysis the VO's
    # "top 1000 opening words" refers to — which is this list's order already
    assert words[TOP - 1] == "slued" and totals[TOP - 1] == totals[TOP] == 8123

    answers = set(open(MYSTERY).read().split())
    exp = [t / N_ANSWERS for t in totals]
    exp_a = [e for w, e in zip(words, exp) if w in answers]
    stats = {"all": (statistics.mean(exp), statistics.median(exp)),
             "answers": (statistics.mean(exp_a), statistics.median(exp_a))}
    for k, (m, md) in stats.items():
        assert (round(m, 4), round(md, 4)) == NOTEBOOK[k], (k, m, md)

    return {"words": words, "totals": totals, "bins": bins, "rows": row,
            "labels": labels, "within": within, "top": words[:TOP],
            "stats": {k: {"mean": m, "median": md} for k, (m, md) in stats.items()}}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    lo, hi = min(d["bins"]), max(d["bins"])
    print(f"{len(d['words'])} words, bins {lo / 100:.2f}..{hi / 100:.2f}, "
          f"tallest {max(d['rows']) + 1}")
    for k, v in d["within"].items():
        print(f"  within {k}: {len(v)}")
    print(f"  top {TOP}: last {d['top'][-1]}")
    for k, s in d["stats"].items():
        print(f"  {k}: mean {s['mean']:.4f} median {s['median']:.4f}")
    for w in ["salet", "slate", "qajaq", "adieu", "audio"]:
        i = d["words"].index(w)
        print(f"  {w.upper()} rank {i + 1} total {d['totals'][i]} label {d['labels'][i]} "
              f"bin {d['bins'][i]} row {d['rows'][i]}")
    print(f"wrote {CACHE}")
