"""Branches of an opener's OPTIMAL TREE, for scene 07x-z — cached.

Scene 07 expands two of FIRST's 6-word groups into their trees: the next guess the
optimal strategy plays in that group, the colours it gets from each answer, and the
answer each branch then finishes on. Those are solver OUTPUT, so they come from the
committed tree `math/data/shared/optturns/trees/first.txt.gz` (optturns: fewest
total guesses subject to solving every answer within 6); this module reads it and
writes `tree_cache.json`, and the SCENE reads the cache.

Regenerate (from this directory):

    ../../.venv/bin/python tree_data.py

The tree is ONE optimal tree: where two next guesses tie, it records one of them.

Tree line format: `<answer> <guesses> <guess1> <pattern1> <guess2> <pattern2> ... <answer>`,
patterns as b/y/g per position, the winning guess carrying none. Codes here are
math/wordle.py pattern integers, POSITION 0 MOST SIGNIFICANT.

Cache: {"<opener>": {"<opener's code>": {"guess": next guess, "branches":
[{"code": next guess's code, "answer": the answer}, ...]}}}, branches ordered the
next guess's own win first (if it is an answer in the group), then by code.
"""
import gzip
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "tree_cache.json")
TREES = os.path.join(HERE, "..", "..", "math", "data", "shared", "optturns", "trees")

OPENER = "first"
GROUPS = [7, 225]     # FIRST's --- G Y (TEASE's group) and G G Y - - (FIERY's), the
                      # user's picks for 07x-z
TRIT = {"b": 0, "y": 1, "g": 2}


def code(pat):
    return sum(TRIT[c] * 3 ** (len(pat) - 1 - i) for i, c in enumerate(pat))


def _build():
    out = {OPENER: {}}
    with gzip.open(os.path.join(TREES, f"{OPENER}.txt.gz"), "rt") as f:
        lines = [l.split() for l in f if l.strip()]
    for g in GROUPS:
        guess, branches = None, []
        for t in lines:
            answer, plays = t[0], t[2:]
            if len(plays) < 3 or plays[0] != OPENER or code(plays[1]) != g:
                continue
            g2 = plays[2]
            assert guess in (None, g2), "one next guess per group"
            guess = g2
            if answer == g2:                              # won on the next guess
                branches.append({"code": 242, "answer": answer})
            else:
                assert len(plays) == 5 and plays[4] == answer, (
                    f"{answer}: scene 07 draws trees three guesses deep")
                branches.append({"code": code(plays[3]), "answer": answer})
        assert len({b["code"] for b in branches}) == len(branches), "one answer per branch"
        branches.sort(key=lambda b: (b["code"] != 242, b["code"]))
        out[OPENER][str(g)] = {"guess": guess, "branches": branches}
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    for g, node in data[OPENER].items():
        print(g, node["guess"], [(b["code"], b["answer"]) for b in node["branches"]])
    print(f"wrote {CACHE}")
