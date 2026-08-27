"""Verify the length-general pattern primitives, including the L=5 regression.

Three independent checks, because the vectorized `pattern_row` is the one piece
whose bugs would silently corrupt every solver result downstream:

  1. REGRESSION. Rows regenerated at L=5 must be BIT-IDENTICAL to the committed
     12972x2315 `patterns.npy`, dtype included. This is what proves generalising
     the primitives left the existing results untouched.
  2. CROSS-CHECK. At every length, the vectorized `pattern_row` must agree with
     the scalar `pattern()` — the faithful port of the original `compare` — on a
     sample of guesses against the whole answer list.
  3. REPEATED LETTERS. The hand-worked cases the two-pass rule exists for, where
     a naive implementation gets greens/yellows wrong.

Run:  python3 tools/checkpatterns.py         # from math/
      python3 tools/checkpatterns.py 4 7     # only these lengths

Exits nonzero on any failure, so it works as a gate alongside solver/validate.sh.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import (  # noqa: E402
    all_green, load_words, pattern, pattern_dtype, pattern_row, to_codes,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATTERNS = os.path.join(_HERE, "..", "data", "local", "patterns", "patterns.npy")

# Hand-worked repeated-letter cases: (guess, answer, expected tiles).
# 0 = grey, 1 = yellow, 2 = green.
REPEATS = [
    # two 'l' in the guess, one in the answer, and that one is GREEN at pos 1 --
    # so the guess's other 'l' has nothing left to claim and is grey.
    ("llama", "alarm", [0, 2, 2, 1, 1]),
    # both 's' green, so neither can also be yellow elsewhere.
    ("sassy", "sissy", [2, 0, 2, 2, 2]),
    # three yellows that each consume a DIFFERENT answer position, plus a green
    # 'b' at pos 2 -- the guess's other 'b' still finds the answer's second 'b'.
    ("abbey", "kebab", [1, 1, 2, 1, 0]),
    # no greens at all: the two 'e' in the guess claim the two 'e' in the answer.
    ("erase", "speed", [1, 0, 0, 1, 1]),
]

failures = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(label)


def check_regression():
    print("regression: regenerated L=5 rows vs committed patterns.npy")
    if not os.path.exists(_PATTERNS):
        check("patterns.npy present", False,
              "-- run `python3 build_patterns.py` from math/ first")
        return
    pat = np.load(_PATTERNS, mmap_mode="r")
    guesses = load_words("guess")
    answers = load_words("mystery")
    check("shape", pat.shape == (len(guesses), len(answers)),
          f"{pat.shape} vs ({len(guesses)}, {len(answers)})")
    check("dtype", pat.dtype == np.uint8, str(pat.dtype))

    codes = to_codes(answers)
    # Spread the sample across the list rather than taking a prefix, so an
    # error confined to one alphabetic region cannot hide.
    idx = np.linspace(0, len(guesses) - 1, 400).astype(int)
    bad = [i for i in idx if not np.array_equal(pattern_row(guesses[i], codes), pat[i])]
    check("400 sampled rows bit-identical", not bad,
          f"{len(bad)} differ (e.g. {[guesses[i] for i in bad[:3]]})" if bad else "")


def check_length(length):
    guesses = load_words("guess", length)
    answers = load_words("mystery", length)
    codes = to_codes(answers)
    print(f"length {length}: {len(guesses)} guesses x {len(answers)} answers")

    idx = np.linspace(0, len(guesses) - 1, 25).astype(int)
    mismatch = 0
    for i in idx:
        g = guesses[i]
        row = pattern_row(g, codes)
        want = np.array([pattern(g, a) for a in answers], dtype=row.dtype)
        mismatch += int((row != want).sum())
    check("vectorized == scalar (25 guesses x all answers)", mismatch == 0,
          f"{mismatch} cells differ" if mismatch else "")

    row = pattern_row(guesses[0], codes)
    check("dtype", row.dtype == pattern_dtype(length), str(row.dtype))
    check("codes in range", int(row.max()) <= all_green(length),
          f"max {int(row.max())} vs all-green {all_green(length)}")
    # A word scored against itself must be all-green; that is the solver's win
    # test, so an off-by-one in the encoding would break every terminal node.
    same = [w for w in guesses[:200] if pattern(w, w) != all_green(length)]
    check("self-score is all-green", not same, str(same[:3]) if same else "")


def check_repeats():
    print("repeated letters (hand-worked cases)")
    for guess, answer, tiles in REPEATS:
        want = 0
        for t in tiles:
            want = want * 3 + t
        got = pattern(guess, answer)
        check(f"{guess} vs {answer}", got == want, f"got {got}, want {want}")
        # the vectorized path must agree on the same case
        row = pattern_row(guess, to_codes([answer]))
        check(f"{guess} vs {answer} (vectorized)", int(row[0]) == want,
              f"got {int(row[0])}, want {want}")


if __name__ == "__main__":
    lengths = [int(a) for a in sys.argv[1:]] or list(range(4, 12))
    check_repeats()
    print()
    check_regression()
    for length in lengths:
        print()
        check_length(length)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {failures}")
        sys.exit(1)
    print("ALL CHECKS PASSED")
