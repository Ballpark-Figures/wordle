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
  vowel_triples — 10e's "top 3-word starters that contain all 6 vowels": the FIRST
                 N_TRIPLES (3, the user's call) rows, in file order, of math/data/shared/singletons/triple_singletons.csv
                 whose three words between them use every one of A E I O U Y (Y a
                 vowel, the video's convention). That file ranks blind triples by
                 singleton count (the user's choice of ranking) and is the top
                 100000 of a GREEDY screen, so this is the best such triple among
                 those screened. The build asserts the file is in descending
                 `singles` order and that each triple has each vowel exactly once,
                 so its six vowel tiles are exactly the six on the board.
  lengths      — 10i's table rows, "3 to max that we have": every L with a
                 math/data/shared/optlen<L>/ result directory (the hello-wordl length
                 sweeps), plus 5, which is the NYT problem above rather than hello's.
                 Asserted contiguous from 3.
  table        — each length's best opener and total, read from the file TABLE_SOURCES
                 names (the user's choices, 2026-09-29), plus that length's hello answer
                 count; the build asserts total / answers reproduces the file's own
                 `expected`. EVERY ROW IS AN OPTIMUM SUBJECT TO A DEPTH CAP, and the
                 caps differ (the `depth` field), and the rows are NOT all the same
                 kind of result:
                   3   best of the --topk beams (k100-300 agree), depth 12 — an UPPER
                       BOUND, from a restricted search
                   4   TALE, the winner of an exact search that examined only 4 of
                       4030 openers (at depth 6); its TOTAL from its own tree --
                       for now the --topk 200 beam's (cap 10, deepest line 7), an
                       UPPER BOUND, until the exact uncapped tree replaces it
                   5   SALET on the NYT lists (the rest of this module), depth 6
                   6   best of the first 819 of 15787 openers, depth 5 — PROVISIONAL
                       (LENGTHS.md); the 7-11 rule would pick DISTAL at depth 4
                   7-11 COMPLETE and exact: fewest worst-case guesses first, then
                       lowest total (LENGTHS.md)
  grey_paths   — 10t / 10v's corner boards: the longest line of the row's own tree
                 (GREY_TREES) on which every reply is all grey, ending on its answer.
                 The build asserts the tree opens with the row's opener and sums to
                 its total, so the path is from the strategy the row reports.
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
TRIPLES = os.path.join(MATH, "data", "shared", "singletons", "triple_singletons.csv")
VOWELS = "aeiouy"
N_TRIPLES = 3


# length -> (result file under math/data/shared, how its best row is chosen). "depth"
# = fewest worst-case guesses first, then lowest total (the escalating runs' own
# lexicographic rule); "total" = lowest total (a pinned-depth file, one cap).
TABLE_SOURCES = {
    3: ("optlen3/k300/opener_totals_d12_ssq.csv", "total"),
    # 4: TALE (the exact search's winner over the 4 openers it examined), its total
    #    from its OWN tree, so the row is the corner path's strategy. For now that
    #    is the --topk 200 beam's tree (cap 10, deepest line 7, so the cap did not
    #    bind; a beam, so an UPPER BOUND -- k300 gives the same 9825). The user's
    #    call, "until we make the fix": the exact uncapped tree
    #    (run-length-tree.sh --depth max -> optlen4/trees_d19/) replaces it here.
    4: ("optlen4/k200/trees_d10/tale.txt.gz", "tree"),
    6: ("optlen6/opener_totals_d5_ssq.csv", "total"),
    7: ("optlen7/opener_totals_escalating_lb.csv", "depth"),
    8: ("optlen8/opener_totals_escalating_lb.csv", "depth"),
    9: ("optlen9/opener_totals_escalating_lb.csv", "depth"),
    10: ("optlen10/opener_totals_escalating_lb.csv", "depth"),
    11: ("optlen11/opener_totals_escalating_lb.csv", "depth"),
}


def _table(opener_total):
    shared = os.path.join(MATH, "data", "shared")
    out = {5: {"opener": OPENER, "total": opener_total, "answers": N_ANSWERS,
               "depth": 6, "source": "optturns/opener_totals.csv"}}
    for L, (rel, rule) in TABLE_SOURCES.items():
        answers = sum(1 for w in open(os.path.join(shared, "words", "hello", f"len{L}",
                                                    "mystery.txt")) if w.strip())
        if rule == "tree":
            path = os.path.join(shared, rel)
            opener = os.path.basename(rel).split(".")[0]
            cap = int(rel.split("trees_d")[1].split("/")[0])
            if not os.path.exists(path):
                print(f"STUB: no tree at {rel} -- length {L}'s average is BLANK. "
                      f"Run solver/run-length-tree.sh --length {L} --depth max "
                      f"--opener {opener}, then re-run this module.")
                out[L] = {"opener": opener, "total": None, "answers": answers,
                          "depth": cap, "source": rel}
                continue
            with gzip.open(path, "rt") as f:
                costs = [int(line.split()[1]) for line in f]
            assert len(costs) == answers, (rel, len(costs), answers)
            out[L] = {"opener": opener, "total": sum(costs), "answers": answers,
                      "depth": cap, "deepest": max(costs), "source": rel}
            continue
        rows = [r for r in csv.DictReader(open(os.path.join(shared, rel))) if r["total"]]
        key = (lambda r: (int(r["depth"]), int(r["total"]), r["word"])) if rule == "depth" \
            else (lambda r: (int(r["total"]), r["word"]))
        r = min(rows, key=key)
        assert len(r["word"]) == L, (L, r["word"])
        assert f"{int(r['total']) / answers:.5f}" == r["expected"], (L, r, answers)
        out[L] = {"opener": r["word"], "total": int(r["total"]), "answers": answers,
                  "depth": int(r["depth"]), "source": rel}
    return {str(L): out[L] for L in sorted(out)}


# length -> that row's tree (under math/data/shared), for 10t / 10v's all-grey path.
# Each must be the tree OF THE TABLE'S ROW: same opener, and its lines' costs must
# sum to the row's total (asserted). Length 4's comes from solver/run-length-tree.sh
# (for now the k200 beam's tree; see TABLE_SOURCES). A missing tree is a STUB
# (None), and so is its row's average.
GREY_TREES = {
    3: "optlen3/k300/trees_d12/ras.txt.gz",
    4: "optlen4/k200/trees_d10/tale.txt.gz",
}


def _grey_paths(table):
    """Each tree's ALL-GREY PATH: its longest line on which every reply is all grey,
    ending on that line's answer. Every tile re-checked against wordle.pattern."""
    sys.path.insert(0, MATH)
    import wordle
    shared = os.path.join(MATH, "data", "shared")
    out = {}
    for L, rel in GREY_TREES.items():
        path = os.path.join(shared, rel)
        row = table[str(L)]
        if not os.path.exists(path):
            print(f"STUB: no tree at {rel} -- length {L}'s all-grey path is empty. "
                  f"Run solver/run-length-tree.sh, then re-run this module.")
            out[str(L)] = None
            continue
        best, total = None, 0
        with gzip.open(path, "rt") as f:
            for raw in f:
                parts = raw.split()
                answer, n, moves = parts[0], int(parts[1]), parts[2:]
                assert moves[0] == row["opener"], (rel, raw)
                assert len(moves) == 2 * n - 1 and moves[-1] == answer, raw
                total += n
                if all(p == "b" * L for p in moves[1::2]) and \
                        (best is None or len(moves) > len(best)):
                    best = moves
        assert total == row["total"], (rel, total, row["total"])
        guesses = []
        answer = best[-1]
        for g, p in zip(best[0::2], best[1::2] + ["g" * L]):
            tiles = [TILE[c] for c in p]
            code = sum(t * 3 ** (L - 1 - i) for i, t in enumerate(tiles))
            assert code == wordle.pattern(g, answer), (rel, g, answer)
            guesses.append({"word": g, "code": code, "tiles": tiles})
        out[str(L)] = {"answer": answer, "guesses": guesses, "source": rel}
    return out


def _lengths():
    shared = os.path.join(MATH, "data", "shared")
    have = {int(d[len("optlen"):]) for d in os.listdir(shared)
            if d.startswith("optlen") and d[len("optlen"):].isdigit()}
    have.add(5)
    out = list(range(3, max(have) + 1))
    assert set(out) == have, f"lengths with results are not contiguous from 3: {have}"
    return out


def _vowel_triples():
    rows = list(csv.DictReader(open(TRIPLES)))
    singles = [int(r["singles"]) for r in rows]
    assert all(a >= b for a, b in zip(singles, singles[1:])), "not in ranked order"
    out = []
    for rank, r in enumerate(rows, 1):
        words = [r["word1"], r["word2"], r["word3"]]
        if set(VOWELS) <= set("".join(words)):
            joined = "".join(words)
            assert sorted(c for c in joined if c in VOWELS) == sorted(VOWELS), words
            out.append({"words": words, "rank": rank, "of": len(rows),
                        "singles": int(r["singles"])})
            if len(out) == N_TRIPLES:
                return out
    raise AssertionError(f"fewer than {N_TRIPLES} triples use all six vowels")


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
            "games": games, "vowel_triples": _vowel_triples(),
            "lengths": _lengths(), "table": (table := _table(total)),
            "grey_paths": _grey_paths(table)}


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
    for t in data["vowel_triples"]:
        print(f"vowel triple: {' '.join(t['words']).upper()}  (rank {t['rank']} of "
              f"{t['of']}, {t['singles']} singles)")
    assert sorted(map(int, data["table"])) == data["lengths"]
    for L, t in data["table"].items():
        avg = "----" if t["total"] is None else f"{t['total'] / t['answers']:.2f}"
        print(f"  {L:>2}  {t['opener'].upper():<12} {avg}  "
              f"depth {t['depth']:<2}  {t['source']}")
    for L, gp in data["grey_paths"].items():
        if gp:
            print(f"  all-grey path, length {L}: "
                  + " ".join(g["word"].upper() for g in gp["guesses"]))
    print(f"\nwrote {CACHE}")
