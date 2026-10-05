"""ONE example of the hard-mode all-grey loss: seven legal guesses sharing no
letter, at least one of them an answer.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-disjoint-words.sh            # from math/

WHY IT LOSES.  Hard mode constrains a guess only by the greens and yellows
already shown; an all-grey reply shows neither.  So with seven words that share
no letter, one of them the answer, the other six can be played in any order:
every reply is all grey, every next guess stays hard-mode legal, and the sixth
grey row ends the game LOST.

THE CONSTRUCTION (the user's method).  Vowels are A E I O U Y -- Y counts, as it
does throughout this video.  Pick:
  * one word with NO vowel at all (from the 12972 legal guesses);
  * for each of the six vowels, one word whose only vowel is that one;
all seven pairwise letter-disjoint, at least one of them one of the 2315
answers.  Depth-first over those seven slots, the vowelless word first, then the
vowels in order of fewest candidates; within a slot, words in alphabetical
order.  It STOPS at the first set found.  The search is complete, so "none
found" would be a real negative, not a gave-up.

THE CHECK IS BUILT IN and always runs on the set it reports: every word is a
legal guess, the vowel conditions hold from the strings, at least one word is an
answer, and every pair scores all grey both ways under wordle.pattern.  It exits
nonzero rather than reporting a set that fails.
"""
import itertools
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csvout import fresh_file  # noqa: E402
from wordle import load_words, pattern  # noqa: E402

VOWELS = "aeiouy"


def vowels_in(word):
    return set(word) & set(VOWELS)


def first_example(guesses, answers):
    """The first seven-word set in the visit order described above, or None."""
    vowelless = sorted(w for w in guesses if not vowels_in(w))
    by_vowel = {v: sorted(w for w in guesses if vowels_in(w) == {v}) for v in VOWELS}
    order = sorted(VOWELS, key=lambda v: len(by_vowel[v]))
    slots = [vowelless] + [by_vowel[v] for v in order]

    def rec(depth, used, chosen):
        if depth == len(slots):
            return list(chosen) if any(w in answers for w in chosen) else None
        for w in slots[depth]:
            if used & set(w):
                continue
            chosen.append(w)
            got = rec(depth + 1, used | set(w), chosen)
            chosen.pop()
            if got:
                return got
        return None

    sizes = {"none": len(vowelless), **{v: len(by_vowel[v]) for v in VOWELS}}
    return rec(0, set(), []), sizes


def check(found, guesses, answers):
    legal = set(guesses)
    for w in found:
        if w not in legal:
            raise SystemExit(f"CHECK FAIL: {w} is not a legal guess")
    vowel_sets = sorted((tuple(sorted(vowels_in(w))) for w in found))
    if vowel_sets != sorted([()] + [(v,) for v in VOWELS]):
        raise SystemExit(f"CHECK FAIL: vowel split is {vowel_sets}")
    if not any(w in answers for w in found):
        raise SystemExit("CHECK FAIL: no answer in the set")
    for a, b in itertools.permutations(found, 2):
        if pattern(a, b) != 0:
            raise SystemExit(f"CHECK FAIL: {a} against {b} is not all grey")


def main(argv):
    out = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            out = argv[i + 1]; i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])
    if out is None:
        raise SystemExit("--out is required; use solver/run-disjoint-words.sh")

    guesses = load_words("guess")
    answers = set(load_words("mystery"))
    t0 = time.time()
    found, sizes = first_example(guesses, answers)
    secs = time.time() - t0
    print("candidates per slot: " + ", ".join(f"{k} {n}" for k, n in sizes.items()))
    if not found:
        print(f"NO SET EXISTS under this construction ({secs:.1f}s, search complete)")
        return
    check(found, guesses, answers)
    if not fresh_file(out):
        raise SystemExit(f"{out} already has content; refusing to overwrite")
    with open(out, "w") as f:
        f.write("# Seven legal guesses, pairwise letter-disjoint: one with no vowel,\n")
        f.write("# one per vowel A E I O U Y; at least one is an answer. The FIRST set\n")
        f.write("# found (see tools/disjoint_words.py for the order), not the only one.\n")
        f.write("word,vowel,answer\n")
        for w in found:
            v = "".join(sorted(vowels_in(w))) or "-"
            f.write(f"{w},{v},{int(w in answers)}\n")
    print("check: legal, vowel split, an answer present, every pair all grey -- OK")
    print("set: " + "  ".join(w.upper() if w in answers else w for w in found)
          + f"   ({secs:.2f}s; answers in CAPITALS)")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
