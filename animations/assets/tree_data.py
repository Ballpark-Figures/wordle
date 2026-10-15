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

Also "full": {"<opener>": its whole optimal tree as nested branches} for 07zc, and "avg": {"<FIRST's code>" or "<results dir>:<forced guess>": average guesses for
the whole game, the mean of the tree's own per-answer counts} for 07's "Average
Guesses:" text, and "subtree": {"<results dir>:<forced guess>": nested branches (see _trie)} for
07zb, read from math/data/shared/subtree/ (solver/run-subgroup-tree.sh).

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
# 07zb: one group's optimal trees with a forced next guess, from
# math/solver/run-subgroup-tree.sh -- (results dir, the forced guesses in order)
FULL_TREES = ["first", "salet"]   # 07zc-zd: openers' WHOLE optimal trees: the scene's
                                  #   own FIRST, then SALET (the optimal opener)
AVG_GROUPS = [242, 177, 26, 7, 225, 8]   # 07: FIRST's groups whose average guesses show
SUBTREES = [("first_30_cap6", ["after", "again", "other", "plane"]),   # BYBYB, 48 answers
            ("first_8_cap6", ["after", "again", "other", "bagel"])]    # BBBGG, 14 (in use)
SUBTREE_DIR = os.path.join(HERE, "..", "..", "math", "data", "shared", "subtree")


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
    # 07: AVERAGE GUESSES for a whole game, per group -- the mean of the tree's own
    # per-answer guess counts (field 2 of a tree line, FIRST included)
    out.setdefault("avg", {})
    for g in AVG_GROUPS:
        counts = [int(t[1]) for t in lines
                  if (g == 242 and len(t) == 3 and t[2] == OPENER)
                  or (len(t) > 3 and t[2] == OPENER and code(t[3]) == g)]
        assert counts, g
        out["avg"][str(g)] = sum(counts) / len(counts)
    out["full"] = {}
    for opener in FULL_TREES:
        with gzip.open(os.path.join(TREES, f"{opener}.txt.gz"), "rt") as f:
            t = _trie([l.split() for l in f if l.strip()])
        assert t["guess"] == opener
        out["full"][opener] = t
        with gzip.open(os.path.join(TREES, f"{opener}.txt.gz"), "rt") as f:
            counts = [int(l.split()[1]) for l in f if l.strip()]
        out.setdefault("avg", {})[f"full:{opener}"] = sum(counts) / len(counts)
    out["subtree"] = {}
    for name, guesses in SUBTREES:
        for g in guesses:
            with gzip.open(os.path.join(SUBTREE_DIR, name, "trees", f"{g}.txt.gz"), "rt") as f:
                sub = [l.split() for l in f if l.strip()]
            t = _trie(sub)
            assert t["guess"] == g
            out["subtree"][f"{name}:{g}"] = t
            # a subgroup tree counts guesses from the forced one on; the guesses of
            # the path before it (<opener>_<code>_...) are added back for the game
            before = (len(name.split("_cap")[0].split("_")) + 1) // 2
            out["avg"][f"{name}:{g}"] = sum(int(l[1]) for l in sub) / len(sub) + before
    return out


def _trie(lines):
    """A tree file as nested branches: {"guess": g, "kids": [{"code": c, "answers":
    [...], "node": child or None}]}, kids by code. The all-green kid (code 242) is
    the guess's own win and has no node; every other kid has one, since its answers
    are only finished once named."""
    root = {"guess": None, "kids": {}}
    for t in lines:
        answer, plays = t[0], t[2:]
        steps = list(zip(plays[0::2], [code(p) for p in plays[1::2]] + [242]))
        node = root
        for g, c in steps:
            assert node["guess"] in (None, g), "one move per position"
            node["guess"] = g
            kid = node["kids"].setdefault(c, {"code": c, "answers": [], "node": None})
            kid["answers"].append(answer)
            if c == 242:
                assert g == answer
                break
            if kid["node"] is None:
                kid["node"] = {"guess": None, "kids": {}}
            node = kid["node"]

    def freeze(n):
        return {"guess": n["guess"],
                "kids": [dict(k, node=freeze(k["node"]) if k["node"] else None)
                         for _, k in sorted(n["kids"].items())]}
    return freeze(root)


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
