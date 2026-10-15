"""Scene 15's numbers and words — SOURCED from the pipeline's committed results, then
cached.

Regenerate (from this directory):

    ../../.venv/bin/python always_win_data.py

Writes `always_win_cache.json`; the scene reads only that.

  openers   k fixed words, then random compatible answers (computed exactly):
            mean guesses and win rate (<= 6) from
            math/data/shared/openexact/exact_named_answer_cap6.csv — the same file
            and strategy scene 14's SLATE marker reads (blind openings)
  fixed     5 and 6 fixed words played blind; an answer is UNSOLVED when another
            answer gives the same feedback to every word, so the next guess cannot
            be sure of it. Each count is RECOMPUTED here from the strings with
            math/wordle.py `pattern` and checked against its committed source:
              blunk cimex grypt vozhd waqfs   72 unsolved   singletons/
                  quint_singletons_disjoint_q25456119.csv (singles 2243)
              chott dumbo fawny verge spill   16 unsolved   hillclimb/
                  singles_mystery-from-guess_w5_s0.csv (singles 2299)
              catty frond rumba spill verge whack   0       singletons/
                  perfect_split_answers.csv (2315 of 2315)
            `groups` are the unsolved answers grouped by their shared feedback;
            `codes` is each group's feedback to the opening's words, in order.
  climb     the guarantee hill climb's trial 68 (pool custom, candidates custom,
            seed 1), the run that found LEDGE PAWNS ROCKY THUMB, read from its log
            math/data/local/hillclimb/climb_custom_w4_s1.log (GITIGNORED, so only
            the machine that ran it can regenerate this) and checked against the
            committed row in math/data/shared/hillclimb/climb_custom_w4_s1.csv.
            The climb's slot order ends `pawns rocky ledge thumb`; the board shows
            the slots in order 2, 0, 1, 3, which ends on LEDGE PAWNS ROCKY THUMB (a
            blind opening's score does not depend on order). `moves` are in board
            rows: [(row, new word), ...] per accepted move, in order.
            `start_unsolved` (1049) is QUERY NINNY BALER MASSE's count, which the
            log does not record: every count here comes from
            math/tools/guarantee_sweep.py `check_opening` (pool custom, cap 6),
            asserted equal to the log's after every move.
            NB its 1 unsolved answer is SALVE (asserted), in the bucket FALSE,
            SALLE, SALVE (SALLE is a custom.txt word, not an answer). check_opening's
            worst line is FALSE fifth (which does not split SALLE from SALVE), SALLE
            sixth, SALVE seventh: a loss needs SALLE played. The user accepts that,
            2026-10-01: nobody guesses SALLE over SALVE.
            The scene's counter shows every count minus 1 for that reason.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.join(HERE, "..", "..", "math")
SHARED = os.path.join(MATH, "data", "shared")
CACHE = os.path.join(HERE, "always_win_cache.json")

OPENERS = ["slate", "parse clint", "crane spilt", "dance horst blimp", "bland copse right",
           "champ flint rugby sowed", "bugle champ downy first"]
FIXED = {   # opening -> (committed file, how to read its isolated count)
    "blunk cimex grypt vozhd waqfs": "quint",
    "chott dumbo fawny verge spill": "climb",
    "catty frond rumba spill verge whack": "perfect",
}
SAME = ["puree", "purer", "rupee", "upper"]      # 15m's example: one shared feedback
CLIMB_LOG = os.path.join(MATH, "data", "local", "hillclimb", "climb_custom_w4_s1.log")
CLIMB_CSV = os.path.join(SHARED, "hillclimb", "climb_custom_w4_s1.csv")
TRIAL = 68
BOARD_ORDER = [2, 0, 1, 3]       # board row r shows climb slot BOARD_ORDER[r]
FINAL = ["ledge", "pawns", "rocky", "thumb"]


def _rows(path):
    return list(csv.DictReader(l for l in open(path) if not l.startswith("#")))


def _committed_singles(opening):
    ws = opening.split()
    kind = FIXED[opening]
    if kind == "quint":
        path = os.path.join(SHARED, "singletons", "quint_singletons_disjoint_q25456119.csv")
        for r in _rows(path):
            if sorted(r[f"word{i}"] for i in range(1, 6)) == sorted(ws):
                return int(r["singles"])
    elif kind == "climb":
        path = os.path.join(SHARED, "hillclimb", "singles_mystery-from-guess_w5_s0.csv")
        for r in _rows(path):
            if sorted(r["opening"].split()) == sorted(ws):
                return int(r["singles"])
    else:
        path = os.path.join(SHARED, "singletons", "perfect_split_answers.csv")
        for r in _rows(path):
            if sorted(r[f"word{i}"] for i in range(1, 7)) == sorted(ws):
                return int(r["singletons"])
    raise KeyError(opening)


def _fixed(opening, answers, wordle):
    ws = opening.split()
    buckets = {}
    for a in answers:
        buckets.setdefault(tuple(wordle.pattern(g, a) for g in ws), []).append(a)
    groups = sorted(([k, v] for k, v in buckets.items() if len(v) > 1),
                    key=lambda kv: (-len(kv[1]), kv[1]))
    unsolved = sum(len(v) for _, v in groups)
    assert len(answers) - unsolved == _committed_singles(opening), opening
    return {"words": ws, "unsolved": unsolved,
            "groups": [{"codes": list(k), "members": v} for k, v in groups]}


def _climb():
    lines = [l for l in open(CLIMB_LOG) if re.match(rf"\s*trial {TRIAL}\s", l)]
    start = re.match(rf"trial {TRIAL}\s+start (.*)", lines[0].strip()).group(1).split()
    slots, moves = list(start), []
    for l in lines[1:]:
        m = re.search(r"r\d+\s+(\S+)\s+(.*?)\s+->\s+(.*?)\s+unsolved\s+(\d+)", l)
        if not m:
            continue
        old, new = m.group(2).split(), m.group(3).split()
        pos = [slots.index(w) for w in old]
        assert pos == sorted(pos), l           # the climb fills old slots in order
        for p, w in zip(pos, new):
            slots[p] = w
        moves.append({"section": m.group(1), "unsolved": int(m.group(4)),
                      "rows": [[BOARD_ORDER.index(p), w] for p, w in zip(pos, new)],
                      "opening": list(slots)})
    row = next(r for r in _rows(CLIMB_CSV) if int(r["trial"]) == TRIAL)
    assert slots == row["opening"].split(), (slots, row["opening"])
    assert moves[-1]["unsolved"] == int(row["unsolved"]) == 1
    board = [slots[s] for s in BOARD_ORDER]
    assert board == FINAL, board
    # The log gives the unsolved count AFTER each move, not for the start. Every
    # count comes from guarantee_sweep.check_opening -- the check the climb ran
    # against itself every trial -- and must reproduce the log's own numbers.
    losing = _losing([start] + [m["opening"] for m in moves])
    assert losing[-1] == ["salve"], losing[-1]     # the one the counter leaves out
    unsolved = [len(l) for l in losing]
    for m, u in zip(moves, unsolved[1:]):
        assert u == m["unsolved"], (m["opening"], u, m["unsolved"])
    for m in moves:
        del m["opening"]
    return {"start": [start[s] for s in BOARD_ORDER], "start_unsolved": unsolved[0],
            "moves": moves, "final": board}


def _losing(openings):
    """The losing answers of each opening, pool custom.txt, cap 6 -- the climb's objective.
    (`adapt` 2, the committed guarantee runs' setting; it cannot change the count,
    since abandoning fires only on live sets of 2 or fewer: greedybuild's note.)"""
    import numpy as np
    sys.path.insert(0, os.path.join(MATH, "tools"))
    from build_patterns import load_patterns
    from guarantee_sweep import check_opening
    from opening_list import resolve_word_set
    from wordle import load_words
    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    pool = sorted(resolve_word_set("custom"))
    full = np.array(load_patterns(full=True))
    cidx = np.array([gpos[w] for w in pool])
    ppos = {w: i for i, w in enumerate(pool)}
    ctx = (full, cidx, pool, np.array([ppos[w] for w in answers]), answers, 2, 6, gpos)
    return [sorted(check_opening(list(o), ctx)[1]) for o in openings]


def _build():
    sys.path.insert(0, MATH)
    import wordle
    answers = [w.strip() for w in open(os.path.join(SHARED, "words", "mystery.txt"))
               if w.strip()]
    assert len(answers) == 2315
    rows = {r["word"]: r for r in _rows(os.path.join(SHARED, "openexact",
                                                     "exact_named_answer_cap6.csv"))}
    openers = {w: {"mean": float(rows[w]["mean"]), "win_rate": float(rows[w]["win_rate"])}
               for w in OPENERS}
    fixed = {o: _fixed(o, answers, wordle) for o in FIXED}
    blunk = fixed["blunk cimex grypt vozhd waqfs"]
    same = next(g for g in blunk["groups"] if SAME[0] in g["members"])
    assert sorted(same["members"]) == SAME, same
    return {"openers": openers, "fixed": fixed, "same": same, "climb": _climb()}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
    for w, o in d["openers"].items():
        print(f"  {w.upper():28s} mean {o['mean']:.6f}  win {o['win_rate']:.6f}")
    for o, f in d["fixed"].items():
        print(f"  {o.upper():38s} unsolved {f['unsolved']:3d} in {len(f['groups'])} groups")
    print(f"  shared feedback: {d['same']['members']} codes {d['same']['codes']}")
    c = d["climb"]
    print(f"  climb: {' '.join(c['start'])} -> {' '.join(c['final'])}, {len(c['moves'])} moves")
    print(f"wrote {CACHE}")
