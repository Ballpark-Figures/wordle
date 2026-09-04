"""Gate: `eldrow` reproduces the ORIGINAL Eldrow.py search, exactly.

Three checks, all against verbatim copies of the old code pasted in below:
  1. longest_chain(bound="size")    vs allSplit         — exact length AND line.
  2. longest_chain(bound="letters") vs betterAllSplit   — exact length AND line.
  3. beam_stall                     vs sizePassLevelSearch (prints stripped, made to
                                       RETURN its deepest depth) across several
                                       (size, target) settings — same depth reached.
Plus one property anchor: with the width cap and reachability filter made
non-binding, the beam agrees with the exact longest_chain — the exhaustive limit.

    python3 tools/checkeldrow.py        # random-seeded, exits nonzero on any mismatch

Small lists keep the exponential exact search cheap while still exercising the
duplicate-letter feedback the whole thing turns on.
"""
import copy
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import eldrow as new
from wordle import load_words


# --- ORIGINAL code, verbatim from Puzzles/Eldrow.py (the oracle) --------------
def _compare(a, b):
    result = [0 for i in range(len(a))]
    aused = [False for i in range(len(a))]
    bused = [False for i in range(len(b))]
    for i in range(len(a)):
        if a[i] == b[i]:
            result[i] = 2
            aused[i] = True
            bused[i] = True
    for i in range(len(a)):
        if aused[i] == False:
            for j in range(len(b)):
                if bused[j] == False and a[i] == b[j]:
                    result[i] = 1
                    aused[i] = True
                    bused[j] = True
                    break
    return tuple(result)


def _split(l, w):
    d = {}
    for i in range(len(l)):
        c = _compare(w, l[i])
        if c in d:
            d[c].append(l[i])
        else:
            d[c] = [l[i]]
    return d


def _letterscore(l):
    vals = [set([]) for i in range(5)]
    for w in l:
        for i in range(5):
            vals[i].add(w[i])
    return [len(vals[i]) for i in range(5)]


def _sortedLetterScore(l):
    vals = [set([]) for i in range(5)]
    for w in l:
        for i in range(5):
            vals[i].add(w[i])
    scores = [len(vals[i]) for i in range(5)]
    return tuple(sorted(scores, reverse=True))


def _allSplit(prev, l, level, bestsofar):
    if len(l) == 1:
        newL = copy.deepcopy(prev)
        return (newL, level - 1)
    elif len(prev) + len(l) <= bestsofar:
        return ([], 0)
    else:
        m = 0
        best = []
        for i in range(len(l)):
            d = _split(l, l[i])
            for j in d.values():
                newPrev = copy.deepcopy(prev)
                newPrev.append(l[i])
                val = _allSplit(newPrev, j, level + 1, bestsofar)
                if val[1] > m:
                    m = val[1]
                    best = val[0]
                    if val[1] > bestsofar:
                        bestsofar = val[1]
        return (best, m)


def _betterAllSplit(prev, l, level, bestsofar):
    if len(l) == 1:
        newL = copy.deepcopy(prev)
        return (newL, level - 1)
    elif len(prev) + max(_letterscore(l)) <= bestsofar:
        return ([], 0)
    else:
        m = 0
        best = []
        for i in range(len(l)):
            d = _split(l, l[i])
            for j in d.values():
                newPrev = copy.deepcopy(prev)
                newPrev.append(l[i])
                val = _allSplit(newPrev, j, level + 1, bestsofar)
                if val[1] > m:
                    m = val[1]
                    best = val[0]
                    if val[1] > bestsofar:
                        bestsofar = val[1]
        return (best, m)


def _sizePassLevelSearch(size, n, l):
    """Original sizePassLevelSearch with prints stripped, returning (depth, line)."""
    levels = [[] for i in range(n + 1)]
    levels[0] = [([], l, _sortedLetterScore(l))]
    bestsofar = 0
    best_line = []
    while (max([len(i) for i in levels]) > 0 and len(levels[-1]) == 0):
        for nextLevel in range(len(levels) - 1):
            count = 0
            while count < size and len(levels[nextLevel]) > 0:
                if nextLevel > bestsofar:
                    bestsofar = nextLevel
                    best_line = levels[nextLevel][0][0]
                count += len(levels[nextLevel][0][1])
                for w in levels[nextLevel][0][1]:
                    d = _split(levels[nextLevel][0][1], w)
                    for val in d.values():
                        s = _sortedLetterScore(val)
                        if s[0] + nextLevel + 1 >= n and w not in levels[nextLevel][0][0]:
                            newList = copy.deepcopy(levels[nextLevel][0][0])
                            newList.append(w)
                            levels[nextLevel + 1].append((newList, val, s))
                levels[nextLevel].pop(0)
                levels[nextLevel + 1] = sorted(
                    levels[nextLevel + 1],
                    key=lambda x: x[2][0] * 100000000 + x[2][1] * 1000000
                    + x[2][2] * 10000 + x[2][3] * 100 + x[2][4],
                    reverse=True)[:1000000]
    if len(levels[-1]) > 0:
        bestsofar = n
        best_line = levels[-1][0][0]
    return bestsofar, best_line


def _bestLevel(l):
    for i in range(len(l) - 1):
        if len(l[i]) > 0 and (len(l[i + 1]) == 0 or l[i + 1][0][2][0] < l[i][0][2][0] - 5):
            return i


def _sumBestLevel(l):
    for i in range(len(l) - 1):
        if len(l[i]) > 0 and (len(l[i + 1]) == 0 or sum(l[i + 1][0][2]) < sum(l[i][0][2]) - 35):
            return i


def _newBestLevel(l, counts):
    for i in range(len(l) - 1):
        if len(l[i]) > 0 and (len(l[i + 1]) == 0 or counts[i + 1] >= 100
                              or l[i + 1][0][2][0] < l[i][0][2][0] - 5):
            counts[i] += 1
            for j in range(i + 1, len(l)):
                counts[j] = 0
                return i


def _single_level_search(n, l, selector):
    """levelSearch / sumLevelSearch / newLevelSearch, prints stripped, returning
    (depth, line) with the same max-tracker as heuristic_search."""
    levels = [[] for i in range(n + 1)]
    levels[0] = [([], l, _sortedLetterScore(l))]
    counts = [0 for i in range(len(l))]
    bestsofar, best_line = 0, []
    while (max([len(i) for i in levels]) > 0 and len(levels[-1]) == 0):
        if selector == "sum":
            nextLevel = _sumBestLevel(levels)
        elif selector == "new":
            nextLevel = _newBestLevel(levels, counts)
        else:
            nextLevel = _bestLevel(levels)
        if nextLevel is None:
            break
        if nextLevel > bestsofar:
            bestsofar, best_line = nextLevel, levels[nextLevel][0][0]
        for w in levels[nextLevel][0][1]:
            d = _split(levels[nextLevel][0][1], w)
            for val in d.values():
                s = _sortedLetterScore(val)
                if s[0] + nextLevel + 1 >= n and w not in levels[nextLevel][0][0]:
                    newList = copy.deepcopy(levels[nextLevel][0][0])
                    newList.append(w)
                    levels[nextLevel + 1].append((newList, val, s))
        if selector == "sum":
            levels[nextLevel + 1] = sorted(levels[nextLevel + 1],
                                           key=lambda x: sum(x[2]), reverse=True)
        else:
            levels[nextLevel + 1] = sorted(levels[nextLevel + 1],
                                           key=lambda x: x[2], reverse=True)
        levels[nextLevel].pop(0)
    if len(levels[-1]) > 0:
        bestsofar, best_line = n, levels[-1][0][0]
    return bestsofar, best_line


def _randSizePassLevelSearch(r, size, n, l):
    """randSizePassLevelSearch, prints stripped, returning (depth, line). Consumes
    the GLOBAL random stream exactly as the original, so seeding matches the port."""
    levels = [[] for i in range(n + 1)]
    levels[0] = [([], l, _sortedLetterScore(l))]
    bestsofar, best_line = 0, []
    while (max([len(i) for i in levels]) > 0 and len(levels[-1]) == 0):
        for nextLevel in range(len(levels) - 1):
            count = 0
            while count < size and len(levels[nextLevel]) > 0:
                if len(levels[nextLevel]) >= r:
                    ind = math.floor(random.random() * r)
                else:
                    ind = math.floor(random.random() * len(levels[nextLevel]))
                if nextLevel > bestsofar:
                    bestsofar, best_line = nextLevel, levels[nextLevel][ind][0]
                count += len(levels[nextLevel][ind][1])
                for w in levels[nextLevel][ind][1]:
                    d = _split(levels[nextLevel][ind][1], w)
                    for val in d.values():
                        s = _sortedLetterScore(val)
                        if s[0] + nextLevel + 1 >= n and w not in levels[nextLevel][ind][0]:
                            newList = copy.deepcopy(levels[nextLevel][ind][0])
                            newList.append(w)
                            levels[nextLevel + 1].append((newList, val, s))
                levels[nextLevel + 1] = sorted(
                    levels[nextLevel + 1],
                    key=lambda x: x[2][0] * 100000000 + x[2][1] * 1000000
                    + x[2][2] * 10000 + x[2][3] * 100 + x[2][4],
                    reverse=True)
                levels[nextLevel].pop(ind)
    if len(levels[-1]) > 0:
        bestsofar, best_line = n, levels[-1][0][0]
    return bestsofar, best_line


def main():
    words = load_words("mystery")
    rng = random.Random(20260904)

    exact_bad = beam_bad = anchor_bad = single_bad = rand_bad = 0
    n_exact, n_beam = 40, 24

    # 1 & 2: exact search, both bounds, length AND line
    for _ in range(n_exact):
        cand = rng.sample(words, rng.randint(2, 7))
        for bound, oracle in (("size", _allSplit), ("letters", _betterAllSplit)):
            o_line, o_len = oracle([], list(cand), 1, 0)
            n_len, n_line = new.longest_chain(list(cand), bound=bound)
            if o_len != n_len or o_line != n_line:
                exact_bad += 1
                print("EXACT MISMATCH", bound, cand,
                      "old", (o_len, o_line), "new", (n_len, n_line))

    # 3: beam vs the value-returning original, several settings
    for _ in range(n_beam):
        cand = rng.sample(words, rng.randint(3, 8))
        for size in (1, 3, 1000):
            for target in (2, 3, 4):
                o_depth, _ = _sizePassLevelSearch(size, target, list(cand))
                n_depth, _ = new.beam_stall(list(cand), target, size=size)
                if o_depth != n_depth:
                    beam_bad += 1
                    print("BEAM MISMATCH", cand, "size", size, "target", target,
                          "old", o_depth, "new", n_depth)

    # anchor: an uncapped, unfiltered beam reaches the exact longest chain
    for _ in range(n_beam):
        cand = rng.sample(words, rng.randint(2, 6))
        exact, _ = new.longest_chain(list(cand))
        if exact >= 1:
            # target = exact is reachable; a huge beam explores exhaustively
            depth, _ = new.beam_stall(list(cand), exact, size=10 ** 9,
                                      beam_cap=10 ** 9)
            if depth != exact:
                anchor_bad += 1
                print("ANCHOR MISMATCH", cand, "exact", exact, "beam", depth)

    # 4: single-level searches (levelSearch / sumLevelSearch / newLevelSearch)
    for _ in range(n_beam):
        for selector in ("best", "sum", "new"):
            for target in (2, 3):
                cand = rng.sample(words, rng.randint(target + 1, 8))
                o_depth, o_line = _single_level_search(target, list(cand), selector)
                n_depth, n_line = new.heuristic_search(list(cand), target,
                                                       selector=selector)
                if (o_depth, o_line) != (n_depth, n_line):
                    single_bad += 1
                    print("SINGLE MISMATCH", selector, cand, "target", target,
                          "old", (o_depth, o_line), "new", (n_depth, n_line))

    # 5: randomized beam (randSizePassLevelSearch) -- seed the GLOBAL stream so the
    # port and the verbatim original draw the same indices.
    for trial in range(n_beam):
        for r in (2, 4):
            for size in (1, 1000):
                for target in (2, 3):
                    cand = rng.sample(words, rng.randint(3, 8))
                    seed = 900 + trial
                    random.seed(seed)
                    o_depth, o_line = _randSizePassLevelSearch(r, size, target,
                                                               list(cand))
                    random.seed(seed)
                    n_depth, n_line = new.beam_stall(list(cand), target, size=size,
                                                     beam_cap=None, rand_top=r,
                                                     rng=random)
                    if (o_depth, o_line) != (n_depth, n_line):
                        rand_bad += 1
                        print("RAND MISMATCH", cand, "r", r, "size", size,
                              "target", target, "old", (o_depth, o_line),
                              "new", (n_depth, n_line))

    ok = (exact_bad == 0 and beam_bad == 0 and anchor_bad == 0
          and single_bad == 0 and rand_bad == 0)
    print("PASS" if ok else "FAIL",
          "-- %d exact / %d beam / %d anchor / %d single / %d rand mismatches"
          % (exact_bad, beam_bad, anchor_bad, single_bad, rand_bad))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
