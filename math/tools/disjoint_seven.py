#!/usr/bin/env python3
"""Find 7 pairwise letter-disjoint Wordle guess words, one per vowel class.

Vowels are a, e, i, o, u, AND y (six of them). Every guess word is classified
by the set of vowels it contains:

  - 'none'          : the word has no vowels at all
  - a / e / i / o / u / y : the word contains exactly ONE distinct vowel
  - any word with two or more distinct vowels is unusable here and dropped.

We then look for a choice of one word from each of the seven classes
(none, a, e, i, o, u, y) whose letter SETS are pairwise disjoint -- i.e. no
two of the seven words share any letter. Words may contain repeated letters;
a repeat only shrinks a word's distinct-letter set, which HELPS (it frees up
letters for the other words).

Because the seven classes carry distinct vowels, the vowels can never collide
across the seven picks -- the real constraint is fitting all the CONSONANTS
into the 20 available (26 letters minus the 6 vowels).

Usage (from math/):
    python3 tools/disjoint_seven.py                 # print the first 20 sets
    python3 tools/disjoint_seven.py --limit 0       # find/print every set
    python3 tools/disjoint_seven.py --words <path>  # use a different word list
    python3 tools/disjoint_seven.py --require-answer # >=1 of the 7 is an answer

With --require-answer, only sets in which at least one of the seven words is a
mystery ANSWER word (math/data/shared/words/mystery.txt) are reported. In the
output an answer word is marked with a leading '*'.
"""

import argparse
from pathlib import Path

VOWELS = set("aeiouy")
ORDER = ["none", "a", "e", "i", "o", "u", "y"]


def mask_of(word):
    m = 0
    for c in word:
        m |= 1 << (ord(c) - 97)
    return m


def classify(word):
    """Return the word's vowel class, or None if it has 2+ distinct vowels."""
    vs = set(word) & VOWELS
    if len(vs) == 0:
        return "none"
    if len(vs) == 1:
        return next(iter(vs))
    return None


def load(path):
    with open(path) as f:
        return [w.strip() for w in f if w.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", default=None,
                    help="word list (default: math/data/shared/words/guess.txt)")
    ap.add_argument("--limit", type=int, default=20,
                    help="max solutions to print; 0 = find them all")
    ap.add_argument("--require-answer", action="store_true",
                    help="only report sets with >=1 mystery answer word")
    ap.add_argument("--answers", default=None,
                    help="answer list (default: math/data/shared/words/mystery.txt)")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent.parent / "data/shared/words"
    path = args.words or (base / "guess.txt")
    words = load(path)

    answers = set()
    if args.require_answer:
        answers = set(load(args.answers or (base / "mystery.txt")))

    # class -> { letter-set mask -> [words with that exact letter set] }
    classes = {k: {} for k in ORDER}
    dropped = 0
    for w in words:
        c = classify(w)
        if c is None:
            dropped += 1
            continue
        classes[c].setdefault(mask_of(w), []).append(w)

    # class -> set of masks having at least one answer word among them
    ans_masks = {k: {m for m, ws in classes[k].items() if any(w in answers for w in ws)}
                 for k in ORDER}

    print(f"loaded {len(words)} words from {path}")
    print(f"dropped {dropped} words with 2+ distinct vowels")
    if args.require_answer:
        print(f"requiring >=1 answer word from {len(answers)} answers")
    print()
    for k in ORDER:
        nword = sum(len(v) for v in classes[k].values())
        print(f"  class {k:>4}: {nword:5d} words, {len(classes[k]):5d} distinct letter-sets")
    print()

    empty = [k for k in ORDER if not classes[k]]
    if empty:
        for k in empty:
            print(f"class {k!r} has no usable words -> a full 7-word set is impossible")
        return

    # Search order: branch on the class with the fewest distinct letter-sets
    # first, so early picks prune hardest.
    order = sorted(ORDER, key=lambda k: len(classes[k]))
    mask_lists = {k: sorted(classes[k].keys()) for k in ORDER}

    solutions = []
    limit = args.limit
    chosen = {}

    def rec(i, used, has_ans):
        if i == len(order):
            if args.require_answer and not has_ans:
                return False
            solutions.append(dict(chosen))
            return limit != 0 and len(solutions) >= limit
        k = order[i]
        for m in mask_lists[k]:
            if m & used:
                continue
            chosen[k] = m
            if rec(i + 1, used | m, has_ans or m in ans_masks[k]):
                return True
        return False

    rec(0, 0, False)

    capped = " (capped at print limit)" if limit and len(solutions) >= limit else ""
    print(f"found {len(solutions)} solution(s) by distinct letter-set{capped}\n")

    for sol in solutions:
        # verify pairwise-disjoint
        acc = 0
        for k in ORDER:
            assert not (acc & sol[k]), "internal error: overlap in reported solution"
            acc |= sol[k]
        words_out = []
        for k in ORDER:
            reps = classes[k][sol[k]]
            # prefer showing an answer word for this class when one exists
            ans_here = [w for w in reps if w in answers]
            rep = ans_here[0] if ans_here else reps[0]
            tag = f"*{rep}" if rep in answers else rep
            if len(reps) > 1:
                tag += f"(+{len(reps) - 1})"
            words_out.append(tag)
        ndistinct = bin(acc).count("1")
        print(f"  [{ndistinct:2d} letters]  " + "  ".join(words_out))

    if solutions:
        print("\neach printed word represents its letter-set; 'word(+N)' means N more"
              "\nwords use those exact letters and are interchangeable.")
        if args.require_answer:
            print("'*' marks a mystery answer word.")


if __name__ == "__main__":
    main()
