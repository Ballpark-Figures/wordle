"""Scene 14's numbers — SOURCED from the pipeline's committed results, then cached.

Regenerate (from this directory):

    ../../.venv/bin/python random_compatible_data.py

Writes `random_compatible_cache.json`; the scene reads only that.

  openers   one word of our choice, then random compatible answers (the race's
            strategy, computed exactly): mean guesses and win rate (<= 6) from
            math/data/shared/openexact/exact_named_answer_cap6.csv
              chose  3.987382  0.985295
              slate  3.821367  0.988670
  turns     the optimal strategy (SALET's committed tree) on every guess except
            guess k, which is a random compatible answer; mean guesses.
              k = 2..5  math/data/shared/kthrandom/salet_d6_compatible.csv `mean`
              k = 1     the random guess IS the opener, a uniform draw from the 2315
                        answers, so the mean is the optimal totals of the 2315 answer
                        words as openers, averaged: math/data/shared/optturns/
                        opener_totals.csv `total`, summed over mystery.txt, over
                        2315 x 2315 (3.60730, the identity solver/README states for
                        --kth-random's k=1 under the `compatible` pool)
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(HERE, "..", "..", "math", "data", "shared")
CACHE = os.path.join(HERE, "random_compatible_cache.json")
OPENERS = ["chose", "slate"]


def _build():
    rows = {r["word"]: r for r in csv.DictReader(
        l for l in open(os.path.join(SHARED, "openexact", "exact_named_answer_cap6.csv"))
        if not l.startswith("#"))}
    openers = {w: {"mean": float(rows[w]["mean"]), "win_rate": float(rows[w]["win_rate"])}
               for w in OPENERS}

    turns = {}
    with open(os.path.join(SHARED, "kthrandom", "salet_d6_compatible.csv")) as f:
        for r in csv.DictReader(f):
            assert float(r["pct_infeasible"]) == 0.0, r
            turns[int(r["k"])] = float(r["mean"])
    answers = [w.strip() for w in open(os.path.join(SHARED, "words", "mystery.txt"))
               if w.strip()]
    assert len(answers) == 2315
    totals = {r["word"]: int(r["total"]) for r in
              csv.DictReader(open(os.path.join(SHARED, "optturns", "opener_totals.csv")))}
    turns[1] = sum(totals[w] for w in answers) / (len(answers) * len(answers))
    assert round(turns[1], 5) == 3.60730, turns[1]
    return {"openers": openers,
            "turns": {str(k): turns[k] for k in range(1, 6)}}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
    for w, o in d["openers"].items():
        print(f"  {w.upper()}  mean {o['mean']:.6f}  win {o['win_rate']:.6f}")
    for k, v in d["turns"].items():
        print(f"  random on guess {k}: {v:.6f}")
    print(f"wrote {CACHE}")
