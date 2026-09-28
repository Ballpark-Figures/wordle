"""Scene 01's opener histogram — every legal opener, SOURCED, then cached.

Every word's average comes from the finished depth-6 sweep, and every word's tile
colours from the pipeline's own feedback function. This module reads both and writes
`intro_cache.json`; the SCENE reads that cache, so a render imports no solver and the
numbers sync between machines through git.

Regenerate (from this directory):

    ../../.venv/bin/python intro_data.py

Provenance for every number it writes:
  total      — math/data/shared/optturns/opener_totals.csv `total`: the optimal total
               guesses over the 2315 answers, SUBJECT TO solving each within 6
  label      — total / 2315 ROUNDED to 2 dp for display (the user's call: GREAT
               shows 3.50, SLOWS 3.70)
  bin        — floor(total / 2315 / 0.01), the house histogram's rule, copied
               verbatim from math/tools/report.py. So GREAT (3.49978) stacks at 3.49
               while its label says 3.50; the scene fades the labels before the
               stacks exist, so the two never share the screen.
  tiles      — math/wordle.py `pattern(word, ANSWER)`, decoded with POSITION 0 AS
               THE MOST SIGNIFICANT TRIT (the convention board.py documents)

The FILL ORDER is a presentation choice, not a result (the user's rule, 01f):
  - at each step, add one word to the stack MISSING THE MOST WORDS (raw count, target
    minus current), ties broken at random with a fixed seed so re-runs reproduce;
  - each stack fills BOTTOM TO TOP, fewest average guesses at the bottom;
  - START, GREAT and SLOWS are already on screen, so they sit at the BOTTOM of their
    stacks and count as present from the start.
  - NUDGED words BREAK the sorted order on purpose (the user's call, 2026-09-28):
    IRATE and ARISE are moved down their stacks so every Wordlebot starter sits low
    and scene 01g/h can zoom in tighter. Their BIN — which stack, i.e. their average
    — is untouched; only their height within the stack is not their rank.
"""
import csv
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "intro_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
TOTALS = os.path.join(MATH, "data", "shared", "optturns", "opener_totals.csv")

ANSWER = "intro"                       # the mystery word every opener is scored against
PINNED = ["start", "great", "slows"]   # shown one by one before the fill (01a-01e)
N_ANSWERS = 2315
BIN = 0.01                             # report.py's bin width
SEED = 1                               # tie-breaking in the fill order only
# word -> row within its stack (0 = bottom). Placed just above the highest other
# starter in reach (RAISE, row 12, shares IRATE's stack), so none of them move.
NUDGE = {"irate": 13, "arise": 12}


def _build():
    sys.path.insert(0, MATH)
    import wordle

    rows = list(csv.DictReader(open(TOTALS)))
    assert len(rows) == 12972, f"expected every opener solved, got {len(rows)}"
    for r in rows:
        assert r["total"], f"{r['word']} has no total"

    # stack order within a bin: fewest guesses at the bottom, word as a tie-break;
    # the three pinned words go to the very bottom of their own stacks
    rows.sort(key=lambda r: (int(r["total"]), r["word"]))
    words = [r["word"] for r in rows]
    totals = [int(r["total"]) for r in rows]
    bins = [int(math.floor(t / N_ANSWERS / BIN)) for t in totals]
    labels = [f"{t / N_ANSWERS:.2f}" for t in totals]
    codes = [int(wordle.pattern(w, ANSWER)) for w in words]

    stacks = {}
    for i, b in enumerate(bins):
        stacks.setdefault(b, []).append(i)
    pinned_idx = [words.index(w) for w in PINNED]
    for b, members in stacks.items():
        pins = [i for i in members if i in pinned_idx]
        stacks[b] = pins + [i for i in members if i not in pins]
    for w, target in NUDGE.items():
        i = words.index(w)
        members = stacks[bins[i]]
        members.remove(i)
        members.insert(target, i)
    row = [0] * len(words)
    for members in stacks.values():
        for k, i in enumerate(members):
            row[i] = k

    # the fill: always the stack missing the most words, ties at random
    rng = random.Random(SEED)
    placed = {b: sum(1 for i in m if i in pinned_idx) for b, m in stacks.items()}
    order = []
    remaining = len(words) - len(pinned_idx)
    while remaining:
        gap = max(len(stacks[b]) - placed[b] for b in stacks)
        tied = sorted(b for b in stacks if len(stacks[b]) - placed[b] == gap)
        b = rng.choice(tied)
        order.append(stacks[b][placed[b]])
        placed[b] += 1
        remaining -= 1

    return {"answer": ANSWER, "pinned": PINNED, "words": words, "totals": totals,
            "labels": labels, "bins": bins, "rows": row, "codes": codes,
            "order": order}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    lo, hi = min(d["bins"]), max(d["bins"])
    tall = max(d["rows"]) + 1
    print(f"{len(d['words'])} words, bins {lo / 100:.2f}..{hi / 100:.2f} "
          f"({hi - lo + 1} stacks), tallest {tall}")
    for w in d["pinned"] + ["salet", "hello", "adieu", "audio", "those", "words"]:
        i = d["words"].index(w)
        print(f"  {w.upper()}  total {d['totals'][i]}  label {d['labels'][i]}  "
              f"bin {d['bins'][i] / 100:.2f}  row {d['rows'][i]}  code {d['codes'][i]}")
    print(f"\nwrote {CACHE}")
