"""Gate: `antiwordle_greedy` reproduces the ORIGINAL greedy code, exactly.

The port in `antiwordle_greedy.py` claims to speed up the old `antiwordleAverage`
without moving the number. This proves it: the OLD functions are pasted in below
VERBATIM (from Puzzles/Wordle.py), and we diff the two on random inputs —
`greedy_opener`'s chosen word, and the full `greedy_expected` value — asserting bit
equality (the value math is unchanged; the selection sums floats in the same order).

    python3 tools/checkantigreedy.py            # random-seeded sweep, exits nonzero on mismatch

Order matters nowhere here except reproducibility, so the RNG is seeded. Small lists
keep the recursion cheap while still exercising duplicate-letter buckets — exactly
where the old rule model's quirks live.
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import antiwordle_greedy as new
from wordle import load_words


# --- ORIGINAL code, verbatim from Puzzles/Wordle.py (the oracle) --------------
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


def _antiwordleCompare(a, b, c):
    for i in range(len(a)):
        if c[i] == 2 and a[i] != b[i]:
            return False
        elif c[i] == 1 and a[i] not in b:
            return False
        elif c[i] == 0 and a[i] in b:
            found = False
            for j in range(5):
                if b[j] == a[i] and c[j] != 2:
                    found = True
            if found == True:
                for j in range(i):
                    if a[j] == a[i]:
                        found = False
            if found == True:
                return False
    return True


def _antiwordleSplit(l, w):
    d = {}
    for i in range(len(l)):
        for m in range(3):
            for n in range(3):
                for o in range(3):
                    for p in range(3):
                        for q in range(3):
                            c = tuple([m, n, o, p, q])
                            comp = _antiwordleCompare(w, l[i], c)
                            if comp == True:
                                if c in d:
                                    d[c].append(l[i])
                                else:
                                    d[c] = [l[i]]
    return d


def _antiwordleAverage(l, mystery, guess, level=0):
    mysteryCount = 0
    for i in l:
        if i in mystery:
            mysteryCount += 1
    if len(l) == 1 and mysteryCount == 1:
        return 1
    elif mysteryCount == 0:
        return 0
    else:
        best = 0
        argBest = {}
        bestWord = ''
        for w in l:
            s = _antiwordleSplit(l, w)
            avg = 0
            for i in l:
                avg += len(s[_compare(w, i)]) / len(l)
            if avg > best:
                best = avg
                argBest = s
                bestWord = w
        ans = 0
        for i in argBest:
            mc = 0
            if bestWord in argBest[i]:
                argBest[i].remove(bestWord)
            for j in argBest[i]:
                if j in mystery and _compare(bestWord, j) == i:
                    mc += 1
            ans += mc * _antiwordleAverage(argBest[i], mystery, guess, level + 1)
        ans /= mysteryCount
        ans += 1
    return ans


def _old_opener(l):
    """The original's first-step choice, extracted for comparison with greedy_opener."""
    best, best_word = 0, ''
    for w in l:
        s = _antiwordleSplit(l, w)
        avg = 0
        for i in l:
            avg += len(s[_compare(w, i)]) / len(l)
        if avg > best:
            best, best_word = avg, w
    return best_word, best


def main():
    words = load_words("mystery")
    rng = random.Random(1234)

    n_trials, list_size, answer_frac = 60, 8, 0.7
    opener_bad = value_bad = 0
    for t in range(n_trials):
        cand = rng.sample(words, list_size)
        answers = set(rng.sample(cand, max(1, int(len(cand) * answer_frac))))

        w_old, keep_old = _old_opener(list(cand))
        w_new, keep_new = new.greedy_opener(list(cand), answers)
        if w_old != w_new or keep_old != keep_new:
            opener_bad += 1
            print("OPENER MISMATCH", cand, "old", (w_old, keep_old),
                  "new", (w_new, keep_new))

        v_old = _antiwordleAverage(list(cand), answers, None)
        v_new = new.greedy_expected(list(cand), answers)
        if v_old != v_new:
            value_bad += 1
            print("VALUE MISMATCH", cand, "old", v_old, "new", v_new)

    ok = opener_bad == 0 and value_bad == 0
    print("PASS" if ok else "FAIL",
          "-- %d trials, %d opener / %d value mismatches"
          % (n_trials, opener_bad, value_bad))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
