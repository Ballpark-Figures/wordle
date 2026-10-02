"""Scene 17's numbers — what the optimal strategy plays, and how many answers are
left, by the colour combination on the board. Cached.

The scene reads `color_combos_cache.json`; a render imports no solver. Regenerate
(from this directory):

    ../../.venv/bin/python color_combos_data.py

THE STRATEGIES: the committed OPTIMAL TREES (optturns — fewest total guesses
subject to solving every answer within 6; see wordle/CLAUDE.md) of the TOP 1000
openers by committed `total`, ties on the word — math/notebooks/strategy_explorer.ipynb's
`select_openers(1000)`, restricted the same way to openers with a tree on disk
(math/data/shared/optturns/trees/). Trees are POOLED, each opener weighted equally.

THE DEFINITIONS (all the user's calls, 2026-10-02):
  position    one node of a tree: a history of (guess, reply) pairs, the answers
              still standing there (`n`), and the tree's next guess. "Ply k" = k
              guesses already played, so ply 1's next guess is the SECOND guess.
  board       the CUMULATIVE (greens, yellows, grays) after the history —
              math/tools/tree_states.py's definition, imported, not restated. At
              ply 1 it is just the opener's tile counts.
  compatible  the next guess is one of the answers still standing at the position
              (fits every clue AND is a mystery word — the notebook's
              'possible answer').
  all new     the next guess has 5 distinct letters, none played before.
  weighting   by ANSWERS: a position holding n answers counts n times.

WHAT IS CACHED:
  pie         ply 1 (the second guess): shares of answers whose position plays a
              compatible word / all new letters / something else. A guess that is
              BOTH counts as all new letters (the script, 17f).
  avg[combo]  ply 1, answer-weighted mean answers remaining: sum(n^2) / sum(n)
              over the positions showing that combo (the notebook's
              DIST_WEIGHT='answers', tree_states' avg_answers).
  bars[ply][combo]  plies 1, 2, 3 (second, third, fourth guess): answer shares of
              compatible only / both / all new only / something else. "Both" can
              only happen with nothing green or yellow (a compatible word must
              replay every proved letter) — asserted.
  ROWS        the 19 combos the table shows: every (g, y, b) except 4G1Y and 5G.
              At plies 2-3 the cumulative board CAN show those two; such positions
              are left out (the user's call) and their answer mass is recorded in
              `dropped`.
"""
import csv
import gzip
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "color_combos_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
TREES = os.path.join(MATH, "data", "shared", "optturns", "trees")
TOP_K = 1000
PLIES = (1, 2, 3)
LETTERS = 5
KINDS = ("compatible", "both", "new", "else")
ROWS = [(g, y, LETTERS - g - y) for b in range(LETTERS + 1)
        for g in range(LETTERS - b, -1, -1) for y in [LETTERS - b - g]
        if (g, y) not in ((4, 1), (5, 0))]   # fewest grays, then most greens


def _openers(paths):
    totals = paths.load_totals()
    have = {f[:-len(".txt.gz")] for f in os.listdir(TREES) if f.endswith(".txt.gz")}
    picked, skipped = [], []
    for w in sorted(totals, key=lambda w: (totals[w], w)):
        if len(picked) == TOP_K:
            break
        (picked if w in have else skipped).append(w)
    if skipped:
        print(f"no committed tree for: {' '.join(skipped)} -- skipped")
    return picked


def _nodes(opener):
    """{(ply, history): [next guess, answers]} for plies in PLIES."""
    nodes = {}
    with gzip.open(os.path.join(TREES, f"{opener}.txt.gz"), "rt") as f:
        for line in f:
            t = line.split()
            answer, guesses, pats = t[0], t[2::2], t[3::2]
            assert guesses[0] == opener and guesses[-1] == answer
            for k in PLIES:
                if len(guesses) <= k:
                    break
                key = (k, tuple(zip(guesses[:k], pats[:k])))
                node = nodes.setdefault(key, [guesses[k], []])
                assert node[0] == guesses[k], f"{opener}: {key} has two moves"
                node[1].append(answer)
    return nodes


def compute():
    sys.path.insert(0, os.path.join(MATH, "tools"))
    sys.path.insert(0, MATH)
    import paths
    import tree_states
    from wordle import pattern

    openers = _openers(paths)
    ans = {k: defaultdict(lambda: dict.fromkeys(KINDS, 0)) for k in PLIES}
    sq, lin = defaultdict(int), defaultdict(int)
    dropped = {k: 0 for k in PLIES}
    for opener in openers:
        for (k, hist), (guess, answers) in _nodes(opener).items():
            n = len(answers)
            state = tree_states.EMPTY
            for g, p in hist:
                assert pattern(g, answers[0]) == tree_states.code_of(p)
                state = tree_states.apply_row(state, g, p)
            gr, ye = tree_states.greens_yellows(state)
            combo = (gr, ye, LETTERS - gr - ye)
            if combo not in ROWS:
                dropped[k] += n
                continue
            compatible = guess in answers
            played = set("".join(g for g, _ in hist))
            new = len(set(guess)) == LETTERS and not (set(guess) & played)
            kind = ("both" if compatible and new else "compatible" if compatible
                    else "new" if new else "else")
            if kind == "both":
                assert combo == (0, 0, LETTERS), (opener, hist, guess)
            ans[k][combo][kind] += n
            if k == 1:
                sq[combo] += n * n
                lin[combo] += n

    tot1 = {c: sum(v.values()) for c, v in ans[1].items()}
    whole = sum(tot1.values())
    pie = {"compatible": sum(v["compatible"] for v in ans[1].values()) / whole,
           "new": sum(v["new"] + v["both"] for v in ans[1].values()) / whole,
           "else": sum(v["else"] for v in ans[1].values()) / whole}
    bars = {}
    for k in PLIES:
        bars[str(k)] = {}
        for c in ROWS:
            v = ans[k].get(c)
            t = sum(v.values()) if v else 0
            bars[str(k)]["".join(map(str, c))] = (
                {kk: v[kk] / t for kk in KINDS} if t else None)
    return {
        "openers": len(openers),
        "rows": ["".join(map(str, c)) for c in ROWS],
        "pie": pie,
        "all_gray_share": tot1.get((0, 0, 5), 0) / whole,
        "avg": {"".join(map(str, c)): sq[c] / lin[c] for c in ROWS if lin[c]},
        "bars": bars,
        "dropped": {str(k): v for k, v in dropped.items()},
        "answers_per_ply": {str(k): sum(sum(v.values()) for v in ans[k].values()) + dropped[k]
                            for k in PLIES},
    }


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = compute()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
    print(f"openers: {data['openers']}")
    print("pie (ply 1, answer-weighted):",
          {k: f"{v:.2%}" for k, v in data["pie"].items()})
    print(f"all-gray share at ply 1: {data['all_gray_share']:.2%}  (VO: about 13%)")
    print("avg answers remaining (ply 1):")
    for r in data["rows"]:
        print(f"  {r}: {data['avg'].get(r)}")
    for k, rows in data["bars"].items():
        print(f"ply {k} (guess {int(k) + 1}); dropped answer mass {data['dropped'][k]} "
              f"of {data['answers_per_ply'][k]}")
        for r, v in rows.items():
            print(f"  {r}: " + ("--" if v is None else
                                "  ".join(f"{kk} {v[kk]:.1%}" for kk in KINDS)))
