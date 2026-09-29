"""Scene 10's numbers — SALET's guess distribution and two of its games, SOURCED.

Everything here is read from SALET's committed OPTIMAL TREE; nothing is solved or
re-derived. This module writes `word_lengths_cache.json`; the SCENE reads that cache,
so a render imports nothing from the pipeline and the numbers sync through git.

Regenerate (from this directory):

    ../../.venv/bin/python word_lengths_data.py

Provenance for everything it writes:
  distribution — for n = 1..6, how many of the 2315 answers SALET's tree solves in
                 exactly n guesses: a count of the tree's per-line guess column
                 (math/data/shared/optturns/trees/salet.txt.gz). The tree is the
                 CONSTRAINED optimum — minimum total guesses subject to solving every
                 answer within 6 — so this is that strategy's distribution. The build
                 asserts the counts sum to 2315 and the guesses to 7920, SALET's
                 `total` in math/data/shared/optturns/opener_totals.csv.
  games        — the tree's own line for each answer in GAMES (Script.md 10b THIRD,
                 10c WHEEL), in game_data.py's format so the same board code draws
                 them. Tiles are the tree's recorded patterns, and the build asserts
                 each one equals math/wordle.py `pattern(guess, answer)` recomputed.
"""
import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "word_lengths_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
SHARED = os.path.join(MATH, "data", "shared", "optturns")
TREE = os.path.join(SHARED, "trees", "salet.txt.gz")
TOTALS = os.path.join(SHARED, "opener_totals.csv")

OPENER = "salet"
N_ANSWERS = 2315
# answers whose SALET line the script shows: 10b THIRD, 10c WHEEL
GAMES = ["third", "wheel"]
TILE = {"b": 0, "y": 1, "g": 2}


def _build():
    sys.path.insert(0, MATH)
    import wordle

    lines = {}
    with gzip.open(TREE, "rt") as f:
        for raw in f:
            parts = raw.split()
            answer, n, moves = parts[0], int(parts[1]), parts[2:]
            # guess pattern guess pattern ... answer: n guesses, n-1 patterns
            assert len(moves) == 2 * n - 1 and moves[0] == OPENER, raw
            assert moves[-1] == answer, raw
            assert answer not in lines, f"{answer} appears twice"
            lines[answer] = moves

    counts = {n: 0 for n in range(1, 7)}
    for moves in lines.values():
        counts[(len(moves) + 1) // 2] += 1
    total = sum(n * c for n, c in counts.items())
    row = next(r for r in csv.DictReader(open(TOTALS)) if r["word"] == OPENER)
    assert sum(counts.values()) == N_ANSWERS, sum(counts.values())
    assert total == int(row["total"]), (total, row["total"])

    games = {}
    for answer in GAMES:
        moves = lines[answer]
        guesses = moves[0::2]
        pats = moves[1::2] + ["g" * 5]            # the winning guess is all green
        game = {"answer": answer, "in_mystery": True, "guesses": []}
        for g, p in zip(guesses, pats):
            tiles = [TILE[c] for c in p]
            code = sum(t * 3 ** (4 - i) for i, t in enumerate(tiles))
            assert code == wordle.pattern(g, answer), (answer, g, p)
            game["guesses"].append({"word": g, "code": code, "tiles": tiles})
        games[answer] = game

    return {"opener": OPENER, "total": total, "answers": N_ANSWERS,
            "distribution": {str(n): c for n, c in counts.items()},
            "games": games}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"{data['opener'].upper()}: {data['total']} guesses over "
          f"{data['answers']} answers = {data['total'] / data['answers']:.5f}")
    for n, c in data["distribution"].items():
        print(f"  {n}: {c:5d}  {100 * c / data['answers']:5.1f}%")
    for answer, game in data["games"].items():
        print(f"{answer.upper()}: " + "  ".join(
            f"{g['word'].upper()} {''.join('bYG'[t] for t in g['tiles'])}"
            for g in game["guesses"]))
    print(f"\nwrote {CACHE}")
