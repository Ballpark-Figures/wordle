"""Per-starting-letter guess/answer lists for the Lingo cell.

Lingo (the game show) is Wordle with the FIRST LETTER GIVEN: you are shown the
opening letter and then guess whole words that begin with it. We model one
independent game per starting letter, so both the answer pool and the legal
guesses are restricted to words starting with that letter. Because every word
shares the first letter, position 0 is always green -- the feedback function is
unchanged, the letter restriction is entirely in the WORD LISTS.

    python3 build_lingo_lists.py --length 5     # NYT lists (2315 / 12972)
    python3 build_lingo_lists.py --length 6     # hello wordl 6-letter lists

WHICH LISTS. Length 5 uses the curated NYT Wordle lists (mystery = the 2315
common answers, guess = the 12972 legal guesses) -- the same lists every 5-letter
sweep in this repo reads, and the ones the committed `patterns.npy` is built
from. There is no NYT 6-letter set, so length 6 falls back to the hello wordl
6-letter lists (`load_words(..., 6)`), exactly as the length sweeps do. The two
curations are NOT comparable (see the "Other word lengths" note in CLAUDE.md);
a Lingo len-6 number describes THIS game on hello's list, never the TV show.

Writes, per letter that has at least one answer:

    data/shared/words/lingo/len<L>/<letter>/guess.txt
    data/shared/words/lingo/len<L>/<letter>/mystery.txt

plus a `meta.json` in `len<L>/` recording the source and the per-letter counts.
The lists are tiny and deterministic, so they are committed (data/shared) -- the
laptop can run a sweep without regenerating them. The per-letter pattern
MATRICES are large and regenerable, so those live under data/local (built by
run-lingo-sweep.sh via build_patterns.py --answer-list).
"""

import json
import os
import string
import sys

from wordle import load_words

_SHARED = os.path.join(os.path.dirname(__file__), "data", "shared", "words", "lingo")


def _source_length(length):
    """(load_words length arg, human source name) for a Lingo length.

    Length 5 is the NYT curation (load_words length=None); every other length is
    hello wordl. Keep this the ONE place that decides, so the matrix builder and
    the checker cannot disagree with the list builder about which words a letter
    holds.
    """
    if length == 5:
        return None, "wordle"
    return length, "hello"


def lingo_lists(length):
    """(guesses, answers, source_name) for a Lingo length, before letter split."""
    la, source = _source_length(length)
    return load_words("guess", la), load_words("mystery", la), source


def build(length):
    guesses, answers, source = lingo_lists(length)
    outdir = os.path.join(_SHARED, "len%d" % length)
    os.makedirs(outdir, exist_ok=True)

    counts = {}
    for letter in string.ascii_lowercase:
        aw = [w for w in answers if w[0] == letter]
        if not aw:
            continue                    # no possible answer -> no game for this letter
        gw = [w for w in guesses if w[0] == letter]
        ldir = os.path.join(outdir, letter)
        os.makedirs(ldir, exist_ok=True)
        with open(os.path.join(ldir, "guess.txt"), "w") as f:
            f.write("\n".join(gw) + "\n")
        with open(os.path.join(ldir, "mystery.txt"), "w") as f:
            f.write("\n".join(aw) + "\n")
        counts[letter] = {"answers": len(aw), "guesses": len(gw)}

    with open(os.path.join(outdir, "meta.json"), "w") as f:
        json.dump({
            "length": length,
            "word_source": source,
            "letters": counts,
            "total_answers": sum(c["answers"] for c in counts.values()),
            "total_guesses": sum(c["guesses"] for c in counts.values()),
        }, f, indent=2)

    print("length %d (%s): %d letters with answers" % (length, source, len(counts)))
    for letter in sorted(counts):
        c = counts[letter]
        print("  %s  answers=%-4d guesses=%d" % (letter, c["answers"], c["guesses"]))


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--length" in argv:
        i = argv.index("--length")
        lengths = [int(a) for a in argv[i + 1:] if not a.startswith("-")]
        if not lengths:
            raise SystemExit("--length needs at least one word length")
    else:
        lengths = [5]
    for L in lengths:
        build(L)
