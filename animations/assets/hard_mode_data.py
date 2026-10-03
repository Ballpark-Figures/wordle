"""Scene 19's numbers — hard mode, every one SOURCED, then cached.

The scene reads `hard_mode_cache.json`; a render imports no solver. Regenerate (from
this directory):

    ../../.venv/bin/python hard_mode_data.py

The two scripted games (19b-e against GREAT, 19s-t against WIGHT) are game_data.py's
"hard_rules" and "ight"; this module CHECKS them against the hard-mode rule and the
hard trees but does not own their codes.

Provenance:
  hard sweep   math/data/shared/hardturns/opener_totals.csv — the ESCALATING sweep:
               `depth` is each opener's minimum feasible depth from 6 up, `total` the
               optimal total guesses over the 2315 answers SUBJECT TO solving each
               within that depth (a CONSTRAINED optimum, wordle/CLAUDE.md)
  depth 5      math/data/shared/hardturns/opener_totals_d5.csv (hard, pinned at 5:
               a blank total = INFEASIBLE) and math/data/shared/optturns/
               opener_totals_d5_feas.csv (normal, every one of the 12972 feasible)
  histogram    hard bins/rows for histogram_data's words, in ITS word order, by the
               same rules (bin = floor(total / 2315 / 0.01), rows sorted by
               (total, word)) — so a word's slice can travel from its normal place
               to its hard one
  table        openers by minimum turns to guarantee a solve: normal all at 5;
               hard 5 if feasible at 5, else the escalating sweep's depth
  depth 10     the openers whose hard minimum is 10 (19r's words, asserted)
  examples     19g/h: EVERY WORD AN ANSWER (the user's call, 2026-10-03) -- the
               best-ranked hard opener (by (total, word)) among the top 1000 that
               is an answer word and whose tree has a line of answer words only where guess 2 keeps a YELLOW letter in its
               yellow square (that letter once in the opener) / plays a letter guess 1
               showed GREY (and nowhere green or yellow), keeping no yellow in its
               square, so each example shows one thing; the first such line in its
               tree file. Codes re-derived with wordle.pattern and checked against
               the tree's own strings
  families     math/data/shared/families/deep_families_d7.csv cut by FAMILIES.md's
               rule (depth >= 8, or depth 7 with >= 3 fixed letters and >= 10
               words), in the script's order (ties as the user wrote them)
  fast openers the openers feasible in hard mode at depth 5, ranked by their hard
               total (escalating sweep), the best 10 (19z's list, asserted)
  coverage     math/data/shared/tiers/coverage_top1000_hardturns.csv if it exists
               (letter_explorer.ipynb under WORDLE_SOLVER=hardturns); else None
"""
import csv
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "hard_mode_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
SHARED = os.path.join(MATH, "data", "shared")
HARD = os.path.join(SHARED, "hardturns", "opener_totals.csv")
HARD_D5 = os.path.join(SHARED, "hardturns", "opener_totals_d5.csv")
NORMAL_D5 = os.path.join(SHARED, "optturns", "opener_totals_d5_feas.csv")
TREES = os.path.join(SHARED, "hardturns", "trees")
FAMILIES = os.path.join(SHARED, "families", "deep_families_d7.csv")
COVERAGE = os.path.join(SHARED, "tiers", "coverage_top1000_hardturns.csv")

N_ANSWERS = 2315
TOP = 1000
TURNS = list(range(5, 11))            # the table's rows (19m-p)
REFUSED = "solve"                     # 19c's word, refused after AGAIN vs GREAT

# the script's lists, ASSERTED against the data (never used in place of it)
SCRIPT_DEPTH10 = ("aight aught bight bigot dight digit gigot gitch gothy hight jigot "
                  "kight ought pight").split()
SCRIPT_FAMILIES = [(10, ".ight", 9), (9, ".ound", 8), (8, ".atch", 7), (8, ".ower", 7),
                   (8, "sha.e", 7), (8, ".aste", 6), (8, "gra.e", 6), (8, ".aunt", 6),
                   (8, ".o.er", 25), (7, ".a.er", 29), (7, ".i.er", 24),
                   (7, "..ing", 23), (7, "sta..", 19), (7, ".la.e", 16)]
SCRIPT_FAST = "dealt alist slart palet plast spalt leapt loast place trans".split()


def _rows(path, skip=0):
    lines = [l for l in open(path).read().splitlines() if not l.startswith("#")]
    return list(csv.DictReader(lines[skip:]))


def _tiles(code):
    return [(code // 3 ** (4 - i)) % 3 for i in range(5)]


def _hard_legal(guess, history):
    """The NYT hard-mode rule: every green repeated in place, every yellow letter
    somewhere in the guess. Greys constrain nothing."""
    for g, code in history:
        t = _tiles(code)
        for i in range(5):
            if t[i] == 2 and guess[i] != g[i]:
                return False
        need = {}
        for i in range(5):
            if t[i] == 1:
                need[g[i]] = need.get(g[i], 0) + 1
        for ch, n in need.items():
            # greens of the same letter also count towards the guess's copies
            greens = sum(1 for i in range(5) if t[i] == 2 and g[i] == ch)
            if guess.count(ch) < n + greens:
                return False
    return True


def _line_codes(wordle, seq):
    """(words, codes) of a tree line `opener code w2 code ... answer`, codes
    recomputed with wordle.pattern and checked against the tree's b/y/g strings."""
    words, strs = seq[0::2], seq[1::2]
    answer = words[-1]
    codes = [int(wordle.pattern(w, answer)) for w in words]
    for w, s, c in zip(words, strs, codes):
        assert "".join("byg"[t] for t in _tiles(c)) == s, (w, s, c)
    return words, codes


def _examples(wordle, top, answers):
    keep_yellow = keep_grey = None
    for w in top:
        if w not in answers:
            continue
        for line in gzip.open(os.path.join(TREES, f"{w}.txt.gz"), "rt"):
            p = line.split()
            seq = p[2:]
            if len(seq) < 4 or any(x not in answers for x in seq[0::2]):
                continue
            g1, c1, g2 = seq[0], seq[1], seq[2]
            if keep_yellow is None and any(
                    c1[i] == "y" and g2[i] == g1[i] and g1.count(g1[i]) == 1
                    for i in range(5)):
                keep_yellow = seq
            absent = {g1[i] for i in range(5) if c1[i] == "b"} - \
                     {g1[i] for i in range(5) if c1[i] != "b"}
            # the grey example shows ONLY the grey: no yellow kept in its square
            if keep_grey is None and any(ch in absent for ch in g2) and not any(
                    c1[i] == "y" and g2[i] == g1[i] for i in range(5)):
                keep_grey = seq
        if keep_yellow and keep_grey:
            break
    out = {}
    for name, seq in (("keep_yellow", keep_yellow), ("keep_grey", keep_grey)):
        words, codes = _line_codes(wordle, seq)
        for j in range(1, len(words)):
            assert _hard_legal(words[j], list(zip(words[:j], codes[:j]))), (name, words)
        out[name] = {"words": words, "codes": codes}
    return out


def _build():
    sys.path.insert(0, MATH)
    import wordle
    sys.path.insert(0, HERE)
    import game_data
    import histogram_data

    # ── the hard sweep, escalating and pinned at 5 ──────────────────────────────
    hard = _rows(HARD, skip=1)        # line 1 is a pre-`depth` header (two headers)
    assert len(hard) == 12972 and all(r["total"] and r["depth"] for r in hard)
    H = {r["word"]: (int(r["total"]), int(r["depth"])) for r in hard}
    d5 = _rows(HARD_D5)
    assert len(d5) == 12972
    hard5 = {r["word"] for r in d5 if r["total"]}
    assert all(H[w][1] == 6 for w in hard5), "a depth-5 opener the sweep put deeper"
    n5 = _rows(NORMAL_D5)
    assert len(n5) == 12972 and all(r["total"] for r in n5), "normal mode: not all at 5"

    # ── 19m-p: the table ────────────────────────────────────────────────────────
    turns = {w: 5 if w in hard5 else d for w, (_, d) in H.items()}
    table = {"normal": {str(t): (12972 if t == 5 else 0) for t in TURNS},
             "hard": {str(t): sum(1 for v in turns.values() if v == t) for t in TURNS}}
    assert sum(table["hard"].values()) == 12972
    depth10 = sorted(w for w, v in turns.items() if v == 10)
    assert depth10 == SCRIPT_DEPTH10, depth10

    # ── 19i-l: the histogram, normal to hard ────────────────────────────────────
    hist = histogram_data.load()
    words = hist["words"]
    order = sorted(words, key=lambda w: (H[w][0], w))
    hbins = {w: int(math.floor(H[w][0] / N_ANSWERS / 0.01)) for w in words}
    seen, hrow = {}, {}
    for w in order:
        b = hbins[w]
        hrow[w] = seen.get(b, 0)
        seen[b] = hrow[w] + 1
    ranked = [w for w in order]
    assert ranked[0] == "salet" and H["salet"][0] == H["trace"][0], "SALET/TRACE tie"

    # ── 19b-e, 19s-t: the scripted games, checked ───────────────────────────────
    g = game_data.load("hard_rules")
    hist_g = [(x["word"], x["code"]) for x in g["guesses"]]
    assert not _hard_legal(REFUSED, hist_g[:1]), "SOLVE should be refused after AGAIN"
    for j in range(1, len(hist_g)):
        assert _hard_legal(hist_g[j][0], hist_g[:j]), hist_g[j]
    ight = game_data.load("ight")
    line = None
    for l in gzip.open(os.path.join(TREES, "aught.txt.gz"), "rt"):
        if l.split()[0] == "wight":
            line = l.split()[2:]
    assert [x["word"] for x in ight["guesses"]] == line[0::2], (ight, line)

    # ── 19u: the families ───────────────────────────────────────────────────────
    fam = _rows(FAMILIES)
    cut = [(int(r["depth"]), r["family"], int(r["size"])) for r in fam
           if int(r["depth"]) >= 8 or (int(r["depth"]) == 7 and int(r["fixed"]) >= 3
                                       and int(r["size"]) >= 10)]
    assert sorted(cut) == sorted(SCRIPT_FAMILIES), cut
    families = [{"depth": d, "family": f, "size": s} for d, f, s in SCRIPT_FAMILIES]

    # ── 19z: the fast openers ───────────────────────────────────────────────────
    fast = sorted(hard5, key=lambda w: (H[w][0], w))[:10]
    assert fast == SCRIPT_FAST, fast

    top = ranked[:TOP]
    answers = set(open(os.path.join(SHARED, "words", "mystery.txt")).read().split())
    out = {
        "hist": {"bins": [hbins[w] for w in words], "rows": [hrow[w] for w in words],
                 "totals": [H[w][0] for w in words]},
        "best": {w: H[w][0] / N_ANSWERS for w in ("salet", "trace")},
        "table": table,
        "depth10": depth10,
        "examples": _examples(wordle, top, answers),
        "families": families,
        "fast": fast,
        "coverage": None,
    }
    if os.path.exists(COVERAGE):
        stamp = None
        for l in open(COVERAGE):
            if l.startswith("# settings "):
                stamp = dict(kv.split("=", 1) for kv in l[11:].split())
        assert stamp and int(stamp["num_trees"]) == TOP and stamp["solver"] == "hardturns"
        out["coverage"] = {"paths": int(stamp["paths"]),
                           "counts": {r["letter"]: [int(r["first1"]), int(r["first2"])]
                                      for r in _rows(COVERAGE)}}
    # the VO's other figures, reported (not shown on screen)
    out["vo"] = {
        "hard_d5_share": len(hard5) / 12972,
        "hard_not6_share": sum(1 for v in turns.values() if v > 6) / 12972,
        "top100_fail": sum(1 for w in ranked[:100] if turns[w] > 6),
        "top2000_fail_share": sum(1 for w in ranked[:2000] if turns[w] > 6) / 2000,
        "salet_normal": hist["totals"][hist["words"].index("salet")] / N_ANSWERS,
    }
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    print("table  turns  normal  hard")
    for t in TURNS:
        print(f"       {t:5d}  {d['table']['normal'][str(t)]:6d}  {d['table']['hard'][str(t)]:5d}")
    print("depth 10:", " ".join(d["depth10"]))
    print(f"SALET / TRACE hard: {d['best']['salet']:.5f} / {d['best']['trace']:.5f}")
    for k, v in d["examples"].items():
        print(f"{k}: {' '.join(v['words'])}  codes {v['codes']}")
    print("fast:", " ".join(d["fast"]))
    print("hist bins", min(d["hist"]["bins"]), "..", max(d["hist"]["bins"]))
    print("coverage:", "present" if d["coverage"] else "MISSING (hard coverage not saved)")
    for k, v in d["vo"].items():
        print(f"  vo {k}: {v}")
    print(f"wrote {CACHE}")
