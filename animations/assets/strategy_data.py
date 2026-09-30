"""Scene 12's words — each opener's optimal second guesses, SALET's word per grey
count, and the random compatible answers 12j cycles through. Cached.

The scene reads `strategy_cache.json`; a render imports no solver. Regenerate
(from this directory):

    ../../.venv/bin/python strategy_data.py

Provenance:
  second[opener][code]  -- the OPTIMAL second guess after `opener` gives pattern
                           `code`, read off the committed optimal tree
                           math/data/shared/optturns/trees/<opener>.txt.gz (the
                           depth-6 constrained optimum -- see wordle/CLAUDE.md).
                           Every line's reply is re-checked against
                           math/wordle.py `pattern`, and every group is checked to
                           carry exactly ONE second word. The opener's own
                           all-green win has no second guess and no entry.
  by_grays[n]           -- SALET's committed second word for replies with n greys,
                           from math/data/shared/secondexact/
                           exact_e0.e1.e2.e3.e4.e5_salet.csv (secondexact
                           --every-reply: a word for EVERY grey count, then a
                           uniformly random consistent answer; exact, no beam).
  by_grays_expected     -- that strategy's expected guesses (not shown on screen).
  cycle[code]           -- 12j: for each SALET group, up to CYCLE answers drawn
                           from that group's members in a seeded random order --
                           the "random compatible answers" the strategy would draw
                           (the group IS the set of answers consistent with the
                           reply). A visual draw, not a statistic.

The openers are the script's own choices (12a, 12e, 12f).
"""
import csv
import gzip
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "strategy_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
TREES = os.path.join(MATH, "data", "shared", "optturns", "trees")
BY_GRAYS = os.path.join(MATH, "data", "shared", "secondexact",
                        "exact_e0.e1.e2.e3.e4.e5_salet.csv")

OPENERS = ["salet", "lucky", "guess"]
STRATEGY = "salet"
CYCLE = 6                  # 12j: answers cycled under each row (fewer if the group is smaller)
SEED = "12j"
TRIT = {"b": 0, "y": 1, "g": 2}


def _code(reply):
    """A tree's reply string (b/y/g) as a pattern code, position 0 most significant."""
    c = 0
    for ch in reply:
        c = c * 3 + TRIT[ch]
    return c


def _second(opener, wordle):
    out = {}
    with gzip.open(os.path.join(TREES, f"{opener}.txt.gz"), "rt") as f:
        for line in f:
            t = line.split()
            answer, played = t[0], t[2:]
            assert played[0] == opener
            if len(played) == 1:                       # the opener was the answer
                continue
            code = _code(played[1])
            assert wordle.pattern(opener, answer) == code, (opener, answer)
            second = played[2]
            assert out.setdefault(code, second) == second, \
                f"{opener}: group {code} has two second words"
    return out


def _by_grays():
    words, expected = {}, None
    with open(BY_GRAYS) as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for r in rows:
            assert r["opener"] == STRATEGY
            words[int(r["fires"][1:])] = r["second"]
            expected = float(r["expected"])
    assert sorted(words) == list(range(6)), words
    return words, expected


def _build():
    sys.path.insert(0, MATH)
    import wordle
    sys.path.insert(0, HERE)
    import lists_data
    full = lists_data.load()["full"]
    out = {"second": {}, "cycle": {}}
    for o in OPENERS:
        sec = _second(o, wordle)
        codes = {g["code"] for g in full[o]}
        win = 242 if o in lists_data.load()["answers"] else None
        # every group but the opener's own win has exactly one second word
        assert set(sec) == codes - {win}, o
        out["second"][o] = {str(c): w for c, w in sorted(sec.items())}
    out["by_grays"], out["by_grays_expected"] = _by_grays()
    rng = random.Random(SEED)
    for g in full[STRATEGY]:
        m = list(g["members"])
        rng.shuffle(m)
        out["cycle"][str(g["code"])] = m[:CYCLE]
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    for o in OPENERS:
        print(f"{o}: {len(data['second'][o])} second words")
    print("salet by grey count:", data["by_grays"], data["by_grays_expected"])
    print(f"wrote {CACHE}")
