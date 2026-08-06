"""Core Wordle primitives — the vectorized rebuild of the old Puzzles/Wordle.py.

The old code's two workhorses were ``compare(guess, answer)`` (per-tile feedback)
and ``split(candidates, guess)`` (partition candidates by feedback). Both were
scalar Python loops. Here they become one precomputed artifact plus numpy ops:

  * A feedback pattern is encoded as a base-3 integer in ``0..242`` (3**5 = 243
    patterns). Tile code per position: 0 = grey (absent), 1 = yellow (present,
    wrong spot), 2 = green (correct spot). Position 0 is the most-significant
    trit, so ``ALL_GREEN == 242``.
  * ``pattern(guess, answer)`` reproduces the old ``compare`` (correct repeated-
    letter handling) but returns the encoded int.
  * ``pattern_row(guess, answers)`` scores one guess against a whole answer array
    at once — this is the primitive the pattern matrix (build_patterns.py) and the
    filter step are built from.
  * A candidate set is a boolean "bitmap" over the answer list; filtering after an
    observed guess is a vectorized ``alive &= (row == observed)``.

Load order for downstream scripts::

    from wordle import load_words, pattern, pattern_row, ALL_GREEN

Design note: everything is keyed off the answer array's index space, so the same
primitives extend to (a) ranking every guess by entropy, (b) the memoized optimal
tree, and (c) hard mode (a legality mask over guesses) without a representation
change.
"""

import os

import numpy as np

WORD_LEN = 5
N_PATTERNS = 3 ** WORD_LEN          # 243
ALL_GREEN = N_PATTERNS - 1          # 242 == "22222" in base 3, MSB = position 0

_DATA = os.path.join(os.path.dirname(__file__), "data", "shared", "words")


# --- word lists -----------------------------------------------------------

def load_words(which):
    """Return the canonical word list. ``which`` in {"mystery", "guess"}.

    mystery = the 2315 possible answers; guess = the 12972 allowed guesses
    (a superset that contains every answer). Lists are pre-sorted + deduped on
    disk, so index order is stable and reproducible across machines.
    """
    path = os.path.join(_DATA, f"{which}.txt")
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def to_codes(words):
    """Pack a word list into an (n, 5) uint8 array of 0..25 letter codes."""
    arr = np.frombuffer("".join(words).encode("ascii"), dtype=np.uint8)
    return (arr - ord("a")).reshape(len(words), WORD_LEN)


# --- feedback (the old `compare`, encoded) --------------------------------

def pattern(guess, answer):
    """Encoded feedback of ``guess`` against ``answer`` (both 5-char strings).

    Faithful port of the old two-pass `compare`: greens first, then yellows
    consuming unused answer letters left-to-right, so repeated letters resolve
    exactly as real Wordle. Returns an int in ``0..242``.
    """
    tiles = [0] * WORD_LEN
    used = [False] * WORD_LEN
    for i in range(WORD_LEN):
        if guess[i] == answer[i]:
            tiles[i] = 2
            used[i] = True
    for i in range(WORD_LEN):
        if tiles[i] == 0:
            for j in range(WORD_LEN):
                if not used[j] and guess[i] == answer[j]:
                    tiles[i] = 1
                    used[j] = True
                    break
    code = 0
    for t in tiles:
        code = code * 3 + t
    return code


def pattern_row(guess, answer_codes):
    """Encoded feedback of one ``guess`` vs every answer at once.

    ``guess`` is a 5-char string; ``answer_codes`` is the (n, 5) uint8 array
    from ``to_codes``. Returns a (n,) uint8 array of encoded patterns. This is
    the vectorized core the pattern matrix and candidate filtering are built on.
    """
    g = np.frombuffer(guess.encode("ascii"), dtype=np.uint8) - ord("a")
    n = answer_codes.shape[0]
    tiles = np.zeros((n, WORD_LEN), dtype=np.uint8)
    ans_used = np.zeros((n, WORD_LEN), dtype=bool)

    greens = answer_codes == g                       # (n, 5)
    tiles[greens] = 2
    ans_used |= greens

    for i in range(WORD_LEN):
        need = tiles[:, i] == 0
        if not need.any():
            continue
        # first unused answer position holding letter g[i]
        match = (answer_codes == g[i]) & ~ans_used    # (n, 5)
        match[~need] = False
        has = match.any(axis=1)
        j = np.argmax(match, axis=1)                   # first True per row
        rows = np.nonzero(has)[0]
        tiles[rows, i] = 1
        ans_used[rows, j[rows]] = True

    # base-3 encode, position 0 as MSB
    weights = (3 ** np.arange(WORD_LEN - 1, -1, -1)).astype(np.uint16)
    return (tiles.astype(np.uint16) @ weights).astype(np.uint8)


# --- candidate bitmap ------------------------------------------------------

def all_alive(n):
    """A fresh candidate bitmap: every one of ``n`` answers still possible."""
    return np.ones(n, dtype=bool)


def filter_alive(alive, pattern_row_vals, observed):
    """Narrow ``alive`` to answers consistent with seeing ``observed`` for a guess.

    ``pattern_row_vals`` is that guess's row of the pattern matrix (uint8, len n).
    Returns a new boolean bitmap; the caller keeps the AND-chain of observations.
    """
    return alive & (pattern_row_vals == observed)


def decode(code):
    """Turn an encoded pattern back into a 5-tuple of tile codes (for display)."""
    trits = []
    for _ in range(WORD_LEN):
        trits.append(code % 3)
        code //= 3
    return tuple(reversed(trits))
