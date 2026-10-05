"""Sets of K legal guesses sharing NO letter, at least one of them an answer.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-disjoint-words.sh            # from math/, K = 7
    bash solver/run-disjoint-words.sh -k 6

WHY THIS IS THE HARD-MODE ALL-GREY LOSS.  Hard mode constrains a guess only by
the greens and yellows already shown; an all-grey reply shows neither, so after
nothing but grey rows EVERY legal word is still a legal hard-mode guess.  So if
seven words share no letter pairwise and one of them is an answer, the other six
can be played in any order against it: each reply is all grey (no shared letter
means no green and no yellow), each next guess is therefore hard-mode legal, and
the sixth grey row ends the game LOST.  K = 7 is that game; K is a flag so the
same search answers the neighbouring question.

THE QUESTION, exactly.  Over the 12972 legal guesses, every set of K words whose
letter sets are pairwise disjoint and which contains at least one of the 2315
answers.  Nothing about vowels is assumed: the search is over letter sets, and
whatever structure the sets have is a RESULT, read off the output.

HOW.  Words with the same LETTER SET are interchangeable here, so the search runs
over distinct letter-set bitmasks and expands each found combination back into
words afterwards.  Combinations are enumerated in increasing mask order (each
set once), the candidate list filtered by disjointness at every level, and a
branch cut when the letters left cannot hold the words still needed (each needs
at least the smallest letter count among the remaining candidates).  The cut
only discards branches that cannot finish, so the enumeration is complete.

OUTPUT: one row per combination of letter sets --
    set,slot,letters,words,answers
`words` lists every legal word with that letter set ('|'-joined), `answers` the
ones among them that are answers.  A combination qualifies when ANY slot holds an
answer.  The number of distinct WORD sets is the product of the slot sizes and is
printed with the summary.

THE GATE IS BUILT IN and always runs:
  * the search against a brute force over itertools.combinations of word STRINGS
    with Python set intersection, on several small samples, compared exactly;
  * every reported set replayed with wordle.pattern: each pair of its words must
    score all grey both ways.
It exits nonzero rather than reporting.
"""
import itertools
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csvout import fresh_file  # noqa: E402
from wordle import load_words, pattern  # noqa: E402


def mask_of(word):
    m = 0
    for c in word:
        m |= 1 << (ord(c) - 97)
    return m


def popcount(m):
    return bin(m).count("1")


def find_sets(words, k, progress=False):
    """Every K-combination of pairwise-disjoint letter sets.  Returns a list of
    tuples of masks (ascending) and the mask -> words map.  `progress` prints a
    line per 5% of the top-level masks, with the sets found so far."""
    by_mask = {}
    for w in words:
        by_mask.setdefault(mask_of(w), []).append(w)
    masks = np.array(sorted(by_mask), dtype=np.int64)
    pops = np.array([popcount(int(m)) for m in masks], dtype=np.int64)
    found = []

    def rec(cand, cpop, used, nused, chosen):
        need = k - len(chosen)
        if need == 0:
            found.append(tuple(chosen))
            return
        if len(cand) < need:
            return
        if nused + need * int(cpop.min()) > 26:
            return
        for i in range(len(cand) - need + 1):
            m = int(cand[i])
            rest = cand[i + 1:]
            keep = (rest & m) == 0
            chosen.append(m)
            rec(rest[keep], cpop[i + 1:][keep], used | m, nused + int(cpop[i]), chosen)
            chosen.pop()

    if not progress:
        rec(masks, pops, 0, 0, [])
        return found, by_mask
    # The top level unrolled, so a long run says how far it has got.
    n, t0, step = len(masks), time.time(), max(1, len(masks) // 20)
    print(f"{len(words)} words, {n} distinct letter sets; searching for {k}...",
          flush=True)
    for i in range(n):
        m = int(masks[i])
        rest = masks[i + 1:]
        keep = (rest & m) == 0
        rec(rest[keep], pops[i + 1:][keep], m, int(pops[i]), [m])
        if (i + 1) % step == 0 or i + 1 == n:
            print(f"  {i + 1}/{n} top-level letter sets  {len(found)} found  "
                  f"{time.time() - t0:.0f}s", flush=True)
    return found, by_mask


def brute(words, k):
    """The reference: combinations of word STRINGS, set intersection, no masks."""
    out = set()
    for combo in itertools.combinations(sorted(set(words)), k):
        sets = [set(w) for w in combo]
        if all(not (a & b) for a, b in itertools.combinations(sets, 2)):
            out.add(frozenset(combo))
    return out


def expand(found, by_mask):
    out = set()
    for combo in found:
        for words in itertools.product(*(by_mask[m] for m in combo)):
            out.add(frozenset(words))
    return out


def gate(guesses, answers_set, sets_found, by_mask):
    rng = random.Random(0)
    # 1. search vs brute force on small samples
    for n, k in ((60, 3), (80, 3), (120, 2), (50, 4)):
        sample = rng.sample(guesses, n)
        f, bm = find_sets(sample, k)
        got = expand(f, bm)
        ref = brute(sample, k)
        if got != ref:
            raise SystemExit(f"GATE FAIL: search vs brute force, n={n} k={k}: "
                             f"{len(got)} vs {len(ref)}")
    # coverage: the samples must actually have contained sets, or the diff is vacuous
    probe = rng.sample(guesses, 120)
    if not brute(probe, 2):
        raise SystemExit("GATE FAIL: coverage -- the brute-force sample held no sets")
    # 2. every reported set replays all grey, every pair, both ways
    for combo in sets_found:
        for words in itertools.product(*(by_mask[m] for m in combo)):
            for a, b in itertools.permutations(words, 2):
                if pattern(a, b) != 0:
                    raise SystemExit(f"GATE FAIL: {a} vs {b} is not all grey")
    print("gate: search == brute force on 4 samples; every reported set replays all grey")


def main(argv):
    k, out = None, None
    i = 0
    while i < len(argv):
        if argv[i] == "-k":
            k = int(argv[i + 1]); i += 2
        elif argv[i] == "--out":
            out = argv[i + 1]; i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])
    if k is None:
        raise SystemExit("-k is required (the set size IS the question)")
    if out is None:
        raise SystemExit("--out is required; use solver/run-disjoint-words.sh")

    guesses = load_words("guess")
    answers = set(load_words("mystery"))
    t0 = time.time()
    found, by_mask = find_sets(guesses, k, progress=True)
    qual = [c for c in found if any(w in answers for m in c for w in by_mask[m])]
    secs = time.time() - t0

    gate(guesses, answers, qual, by_mask)

    nword = sum(int(np.prod([len(by_mask[m]) for m in c])) for c in qual)
    if not fresh_file(out):
        raise SystemExit(f"{out} already has content; refusing to overwrite")
    with open(out, "w") as f:
        f.write(f"# {k} legal guesses, pairwise letter-disjoint, >= 1 of the 2315 answers\n")
        f.write(f"# letter-set combinations (all): {len(found)}  with an answer: {len(qual)}"
                f"  word sets with an answer: {nword}  seconds: {secs:.1f}\n")
        f.write("set,slot,letters,words,answers\n")
        f.flush()
        for s, c in enumerate(qual, 1):
            for j, m in enumerate(c, 1):
                ws = sorted(by_mask[m])
                letters = "".join(sorted(set(ws[0])))
                ans = [w for w in ws if w in answers]
                f.write(f"{s},{j},{letters},{'|'.join(ws)},{'|'.join(ans)}\n")
    print(f"K={k}: {len(found)} letter-set combinations, {len(qual)} with an answer, "
          f"{nword} word sets with an answer ({secs:.1f}s)")
    for s, c in enumerate(qual, 1):
        parts = []
        for m in c:
            ws = sorted(by_mask[m])
            parts.append("/".join(w.upper() if w in answers else w for w in ws))
        print(f"  {s:3d}. " + "  ".join(parts))
    print(f"wrote {out}   (answers in CAPITALS)")


if __name__ == "__main__":
    main(sys.argv[1:])
