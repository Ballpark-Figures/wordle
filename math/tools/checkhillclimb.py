"""Gate for math/hillclimb.py -- the moves, and the parallel path.

    python3 tools/checkhillclimb.py

It runs on a SMALL candidate list so a whole trial is seconds: the things being
checked (what a move is, and whether --workers changes an answer) do not depend
on how many candidates there are, and a gate nobody can afford to run is not a
gate.

FOUR CHECKS:

  1  every MOVE really has the letter relationship it claims, recomputed from
     the STRINGS -- exact anagram at within=0, one substitution at within=1,
     for pairs AND triples -- with COVERAGE asserted per section, so a pass
     cannot mean no move of a given kind was ever generated;
  2  every move that SHOULD exist does: the generator is diffed against a
     BRUTE FORCE over every tuple of candidates, keeping those whose letters
     are within the bar.  Check 1 can only catch a move that is wrong; this is
     the one that catches a move that is MISSING -- and a section that silently
     finds nothing is exactly the failure an int16 target promoted to int64
     would cause, since the signature would then match nothing;
  3  a climb ENDS at a local optimum of the neighbourhood it claims;
  4  --workers changes NOTHING but the order lines appear in.  Trials are
     seeded by index, so the serial and parallel runs must agree trial for
     trial, on the opening AND the score.

The brute force shares NOTHING with what it checks: `collections.Counter` over
the word STRINGS, no letter matrix, no `near_targets`, no `splits_into`.
"""

import itertools
import os
import subprocess
import sys
import tempfile
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hillclimb import (SECTIONS, anagram_index, letter_counts,         # noqa: E402
                       set_moves)
from opening_list import resolve_word_set                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NCAND = 300
TRI_NCAND = 100   # C(n, 3) per position-triple, so the triple oracle gets less
TRIALS = 3


def bag(w):
    """Letter multiset of a word, from the STRING, as a sorted tuple."""
    return tuple(sorted(w))


def moved_letters(old_words, new_words):
    """How many letters would have to CHANGE to turn one multiset into the other.

    From the strings, with `Counter` -- no letter matrix, so a bug in
    `letter_counts` cannot hide here.
    """
    ca, cb = Counter("".join(old_words)), Counter("".join(new_words))
    if sum(ca.values()) != sum(cb.values()):
        return None                      # different LENGTH: not a letter trade
    return sum((ca - cb).values())


def brute_moves(cands, words, size, within):
    """Every legal move, by checking EVERY tuple of candidates directly.

    The oracle for completeness.  It enumerates rather than indexing anything,
    so it is far too slow for real use and exactly right for a gate.
    """
    cur = set(words)
    out = set()
    for pos in itertools.combinations(range(len(words)), size):
        old = tuple(words[i] for i in pos)
        keep = cur - set(old)
        for repl in itertools.combinations(range(len(cands)), size):
            if set(repl) == set(old) or any(w in keep for w in repl):
                continue
            m = moved_letters([cands[w] for w in old], [cands[w] for w in repl])
            if m is not None and m <= within:
                out.add((pos, repl))
    return out


def main(argv):
    failures = []
    pool = sorted(resolve_word_set("custom"))
    cands = pool[:NCAND]
    C = letter_counts(cands)
    by = anagram_index(C)

    # --- 1: what a move IS, recomputed from the strings --------------------
    # Every shipped section, so a new one is covered by being in SECTIONS
    # rather than by anybody remembering to extend this list.
    rng = np.random.default_rng(0)
    seen = {}
    for label, size, within in SECTIONS:
        seen[label] = 0
        for _ in range(60):
            words = [int(x) for x in rng.choice(len(cands), size=4, replace=False)]
            for pos, repl in set_moves(C, by, words, size, within):
                seen[label] += 1
                old = [cands[words[i]] for i in pos]
                new = [cands[w] for w in repl]
                moved = moved_letters(old, new)
                if moved is None:
                    failures.append("%s move changes the letter COUNT: %s -> %s"
                                    % (label, " ".join(old), " ".join(new)))
                    break
                if moved > within:
                    failures.append("%s emitted %s -> %s, %d letters apart but "
                                    "the section allows %d"
                                    % (label, " ".join(old), " ".join(new),
                                       moved, within))
                    break
                if set(repl) == set(words[i] for i in pos):
                    failures.append("%s put the same words back" % label)
                    break
                if len(set(repl)) != len(repl):
                    failures.append("%s repeated a word within one move" % label)
                    break
                dup = [w for w in repl
                       if w in words and w not in [words[i] for i in pos]]
                if dup:
                    failures.append("%s duplicated a word already in the "
                                    "opening" % label)
                    break
    for label, _, _ in SECTIONS:
        if not seen[label]:
            failures.append("no %s move was generated at all, so check 1 "
                            "proved nothing for it" % label)
    print("moves checked from the strings: "
          + ", ".join("%s %d" % (l, seen[l]) for l, _, _ in SECTIONS))

    # --- 2: every move that SHOULD exist does ------------------------------
    # Sizes are priced separately: the triple brute force is C(n, 3) per
    # position-triple, so it gets a shorter list and fewer openings.  Coverage
    # is asserted, since two empty sets agree trivially.
    plans = [(label, size, within, NCAND if size == 2 else TRI_NCAND,
              3 if size == 2 else 2)
             for label, size, within in SECTIONS]
    for label, size, within, ncand, nopen in plans:
        sub = pool[:ncand]
        Cs, bys = letter_counts(sub), anagram_index(letter_counts(sub))
        found = 0
        for _ in range(nopen):
            words = [int(x) for x in rng.choice(len(sub), size=4, replace=False)]
            got = {(pos, tuple(repl))
                   for pos, repl in set_moves(Cs, bys, words, size, within)}
            want = brute_moves(sub, words, size, within)
            found += len(want)
            if got != want:
                miss = sorted(want - got)[:3]
                extra = sorted(got - want)[:3]
                failures.append(
                    "%s on %s: generator and brute force disagree "
                    "(%d missing e.g. %s, %d extra e.g. %s)"
                    % (label, " ".join(sub[w] for w in words),
                       len(want - got), miss, len(got - want), extra))
                break
        if not found:
            failures.append("the brute force found no %s move at all, so the "
                            "completeness check proved nothing for it" % label)
        print("%-10s completeness: %d moves over %d openings of %d candidates"
              % (label, found, nopen, ncand))

    # --- 4: --workers changes only the ORDER -------------------------------
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
