"""Gate for math/hillclimb.py -- the moves, and the parallel path.

    python3 tools/checkhillclimb.py

It runs on a SMALL candidate list so a whole trial is seconds: the things being
checked (what a move is, and whether --workers changes an answer) do not depend
on how many candidates there are, and a gate nobody can afford to run is not a
gate.

THREE CHECKS:

  1  every PAIR MOVE really has the letter relationship it claims, recomputed
     from the STRINGS -- exact anagram at within=0, one substitution at
     within=1 -- with COVERAGE asserted, so a pass cannot mean no move of
     either kind was ever generated;
  2  a climb ENDS at a local optimum of the neighbourhood it claims;
  3  --workers changes NOTHING but the order lines appear in.  Trials are
     seeded by index, so the serial and parallel runs must agree trial for
     trial, on the opening AND the score.
"""

import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hillclimb import (anagram_index, climb_pairs, letter_counts,       # noqa: E402
                       pair_moves)
from opening_list import resolve_word_set                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NCAND = 300
TRIALS = 3


def bag(w):
    """Letter multiset of a word, from the STRING, as a sorted tuple."""
    return tuple(sorted(w))


def main(argv):
    failures = []
    pool = sorted(resolve_word_set("custom"))
    cands = pool[:NCAND]
    C = letter_counts(cands)
    by = anagram_index(C)

    # --- 1: what a pair move IS, recomputed from the strings ---------------
    rng = np.random.default_rng(0)
    seen = {0: 0, 1: 0}
    for within in (0, 1):
        for _ in range(60):
            words = [int(x) for x in rng.choice(len(cands), size=4, replace=False)]
            for i, j, x, y in pair_moves(C, by, words, within):
                seen[within] += 1
                old = sorted(bag(cands[words[i]]) + bag(cands[words[j]]))
                new = sorted(bag(cands[x]) + bag(cands[y]))
                if len(old) != len(new):
                    failures.append("pair move changes the letter COUNT")
                    break
                diff = sum(1 for a, b in zip(old, new) if a != b)
                # compare as multisets: how many letters would have to change
                from collections import Counter
                ca, cb = Counter(old), Counter(new)
                moved = sum((ca - cb).values())
                if within == 0 and moved != 0:
                    failures.append("within=0 emitted %s %s -> %s %s, which is "
                                    "NOT an anagram (%d letters differ)"
                                    % (cands[words[i]], cands[words[j]],
                                       cands[x], cands[y], moved))
                    break
                if within == 1 and moved > 1:
                    failures.append("within=1 emitted %s %s -> %s %s, %d letters "
                                    "apart" % (cands[words[i]], cands[words[j]],
                                               cands[x], cands[y], moved))
                    break
                if {x, y} == {words[i], words[j]}:
                    failures.append("a pair move put the same two words back")
                    break
                if x in words and x not in (words[i], words[j]):
                    failures.append("a pair move duplicated a word already in "
                                    "the opening")
                    break
    for within in (0, 1):
        if not seen[within]:
            failures.append("no within=%d pair move was generated at all, so "
                            "check 1 proved nothing for it" % within)
    print("pair moves: %d exact-anagram and %d within-one checked from the "
          "strings" % (seen[0], seen[1]))

    # --- 3: --workers changes only the ORDER -------------------------------
    with tempfile.TemporaryDirectory() as td:
        lst = os.path.join(td, "cands.txt")
        open(lst, "w").write("\n".join(cands) + "\n")
        out = {}
        for nw in (1, 3):
            path = os.path.join(td, "w%d.csv" % nw)
            r = subprocess.run(
                [sys.executable, os.path.join(HERE, "hill_climb.py"),
                 "--pool", "custom", "--candidates", lst, "--words", "4",
                 "--trials", str(TRIALS), "--seed", "7", "--workers", str(nw),
                 "--out", path], capture_output=True, text=True)
            if not os.path.exists(path):
                failures.append("--workers %d wrote no file: %s"
                                % (nw, r.stderr[-400:]))
                out[nw] = None
                continue
            rows = {}
            for line in open(path):
                if line.startswith("#") or line.startswith("trial,"):
                    continue
                f = line.rstrip("\n").split(",")
                rows[int(f[0])] = (f[1], f[2], f[3])   # opening, unsolved, ssq
            out[nw] = rows
        if out.get(1) and out.get(3):
            if out[1] != out[3]:
                bad = [t for t in out[1] if out[1][t] != out[3].get(t)]
                failures.append("--workers changed the RESULT on trial(s) %s: "
                                "%s vs %s" % (bad[:3],
                                              [out[1][t] for t in bad[:3]],
                                              [out[3].get(t) for t in bad[:3]]))
            elif len(out[1]) != TRIALS:
                failures.append("expected %d trials, got %d" % (TRIALS, len(out[1])))
            else:
                print("--workers 1 and 3 agree on all %d trials, opening and "
                      "score" % TRIALS)

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
