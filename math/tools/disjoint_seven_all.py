#!/usr/bin/env python3
"""Count / enumerate ALL sets of N pairwise letter-disjoint Wordle guess words.

This is the fully general version of tools/disjoint_seven.py. It does NOT
assume one word per vowel class, so a solution may contain several vowel-free
words (crwth, cwtch, ...), a word carrying two vowels, and so on -- any N words
work as long as they are PAIRWISE letter-disjoint (no two share a letter).
Repeated letters within a word are fine; a repeat only shrinks that word's
distinct-letter set, which frees letters for the others.

A "solution" is a set of N words that are pairwise letter-disjoint. Two words
with the SAME letter set can never appear together (they share every letter),
but each is a distinct solution when swapped in for the other -- so the total
word-set count expands over words that share a letter set.

Vowels are a, e, i, o, u, y (six). Because each vowel can belong to at most one
word of a disjoint set, at most 6 of the words can carry any vowel -- so an
N-word set needs at least N-6 VOWEL-FREE words (>=2 for N=8, >=3 for N=9, ...).
--min-novowel encodes that: it restricts the count to sets with at least that
many vowel-free words, and prunes the search using the (very few) vowel-free
words available.

Usage (from math/):
    python3 tools/disjoint_seven_all.py                        # all 7-sets
    python3 tools/disjoint_seven_all.py --n 8 --min-novowel 2  # all 8-sets
    python3 tools/disjoint_seven_all.py --require-answer        # sets with an answer
    python3 tools/disjoint_seven_all.py --n 6 --limit 50        # 6-sets, 50 examples
    python3 tools/disjoint_seven_all.py --limit 0              # print every example
"""

import argparse
from pathlib import Path

ALPHABET = 26
VOWEL_BITS = sum(1 << (ord(c) - 97) for c in "aeiouy")


def popcount(x):
    return bin(x).count("1")


def mask_of(word):
    m = 0
    for c in word:
        m |= 1 << (ord(c) - 97)
    return m


def load(path):
    with open(path) as f:
        return [w.strip() for w in f if w.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", default=None,
                    help="word list (default: math/data/shared/words/guess.txt)")
    ap.add_argument("--answers", default=None,
                    help="answer list (default: math/data/shared/words/mystery.txt)")
    ap.add_argument("--n", type=int, default=7, help="set size (default 7)")
    ap.add_argument("--min-novowel", type=int, default=0,
                    help="require at least this many vowel-free words (default 0)")
    ap.add_argument("--require-answer", action="store_true",
                    help="only count/print sets with >=1 mystery answer word")
    ap.add_argument("--limit", type=int, default=20,
                    help="max example solutions to print; 0 = print every one")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent.parent / "data/shared/words"
    words = load(args.words or (base / "guess.txt"))
    answers = set(load(args.answers or (base / "mystery.txt")))

    # unique letter-set mask -> list of words with exactly that letter set
    groups = {}
    for w in words:
        groups.setdefault(mask_of(w), []).append(w)

    # candidate tuples, sorted by distinct-letter count (weight) ascending so
    # the budget lower-bound prunes hard and scarce low-weight words branch first.
    # tuple = (weight, mask, cnt, non_answer_cnt, is_vowel_free, words)
    cands = []
    for m, ws in groups.items():
        cnt = len(ws)
        non = sum(1 for w in ws if w not in answers)     # words that are NOT answers
        cands.append((popcount(m), m, cnt, non, (m & VOWEL_BITS) == 0, ws))
    cands.sort(key=lambda t: (t[0], t[1]))
    weights = [t[0] for t in cands]
    nv_indices = [i for i, t in enumerate(cands) if t[4]]   # vowel-free candidates

    N = args.n
    min_nv = args.min_novowel

    print(f"loaded {len(words)} words -> {len(cands)} distinct letter-sets")
    print(f"{len(answers)} answer words loaded"
          + ("; requiring >=1 answer per set" if args.require_answer else ""))
    vf_words = sorted(w for _, _, _, _, isvf, ws in cands if isvf for w in ws)
    print(f"vowel-free words ({len(vf_words)}): {' '.join(vf_words)}")
    if N - 6 > min_nv:
        print(f"NOTE: an {N}-word set needs >= {N - 6} vowel-free words; "
              f"consider --min-novowel {N - 6}")
    print(f"searching for all {N}-word pairwise-disjoint sets"
          + (f" with >= {min_nv} vowel-free" if min_nv else "") + "\n")

    limit = args.limit
    printed = 0
    total_cliques = 0     # distinct letter-set combinations
    total_sets = 0        # expanded word-sets
    total_ans_sets = 0    # expanded word-sets with >=1 answer word

    def show(chosen):
        acc = 0
        parts = []
        for i in chosen:
            _, m, _, _, _, ws = cands[i]
            acc |= m
            ans_here = [w for w in ws if w in answers]
            rep = ans_here[0] if ans_here else ws[0]
            tag = f"*{rep}" if rep in answers else rep
            if len(ws) > 1:
                tag += f"(+{len(ws) - 1})"
            parts.append(tag)
        print(f"  [{popcount(acc):2d} letters]  " + "  ".join(parts))

    def avail_nv(start, used):
        # vowel-free candidates still selectable from `start` onward
        return sum(1 for i in nv_indices if i >= start and not (cands[i][1] & used))

    def rec(start, depth, used, prod_all, prod_non, nv, chosen):
        nonlocal total_cliques, total_sets, total_ans_sets, printed
        if depth == N:
            if nv < min_nv:
                return
            total_cliques += 1
            total_sets += prod_all
            ans_here = prod_all - prod_non
            total_ans_sets += ans_here
            if (limit == 0 or printed < limit) and (not args.require_answer or ans_here > 0):
                show(chosen)
                printed += 1
            return

        need = N - depth
        if start + need > len(cands):
            return
        budget = ALPHABET - popcount(used)
        # lower bound on the letters the remaining `need` words must add: the
        # `need` smallest available weights (ignores disjointness -> sound).
        if sum(weights[start:start + need]) > budget:
            return
        # can we still reach the vowel-free minimum?
        if min_nv and nv + avail_nv(start, used) < min_nv:
            return

        for i in range(start, len(cands)):
            w, m, cnt, non, isvf, _ = cands[i]
            if len(cands) - i < need:
                break
            if w > budget:            # sorted ascending -> nothing later fits either
                break
            if m & used:
                continue
            chosen.append(i)
            rec(i + 1, depth + 1, used | m, prod_all * cnt, prod_non * non,
                nv + (1 if isvf else 0), chosen)
            chosen.pop()

    rec(0, 0, 0, 1, 1, 0, [])

    if printed:
        print("\neach printed word represents its letter-set; 'word(+N)' means N more"
              "\nwords share those exact letters (each gives a distinct solution).")
        if args.require_answer:
            print("'*' marks a mystery answer word.")

    print()
    label = f"{N}-word solutions"
    if min_nv:
        label += f" (>= {min_nv} vowel-free)"
    print(f"distinct letter-set combinations : {total_cliques}")
    print(f"total {label:30}: {total_sets}")
    if args.require_answer:
        print(f"...of which contain an answer     : {total_ans_sets}")
    else:
        print(f"...that contain an answer word    : {total_ans_sets}")


if __name__ == "__main__":
    main()
