"""Core Wordle primitives — the vectorized rebuild of the old Puzzles/Wordle.py.

The old code's two workhorses were ``compare(guess, answer)`` (per-tile feedback)
and ``split(candidates, guess)`` (partition candidates by feedback). Both were
scalar Python loops. Here they become one precomputed artifact plus numpy ops:

  * A feedback pattern is encoded as a base-3 integer in ``0..3**L - 1`` (243
    patterns at the standard L=5). Tile code per position: 0 = grey (absent),
    1 = yellow (present, wrong spot), 2 = green (correct spot). Position 0 is
    the most-significant trit, so ``ALL_GREEN == 3**L - 1`` (242 at L=5).
  * ``pattern(guess, answer)`` reproduces the old ``compare`` (correct repeated-
    letter handling) but returns the encoded int.
  * ``pattern_row(guess, answers)`` scores one guess against a whole answer array
    at once — this is the primitive the pattern matrix (build_patterns.py) and the
    filter step are built from.
  * A candidate set is a boolean "bitmap" over the answer list; filtering after an
    observed guess is a vectorized ``alive &= (row == observed)``.

Load order for downstream scripts::

    from wordle import load_words, pattern, pattern_row, ALL_GREEN

WORD LENGTH.  Wordle is 5 letters and that stays the default of every function
here, so existing callers are unchanged. Length is otherwise INFERRED from the
data (``len(guess)``, ``answer_codes.shape[1]``) rather than read from a global,
which is what lets the same primitives build a 7-letter pattern matrix. The one
thing that genuinely varies is the STORAGE dtype: ``3**L - 1`` outgrows uint8 at
L=6 and uint16 at L=11, so use ``pattern_dtype(L)`` rather than assuming uint8.

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


def n_patterns(word_len=WORD_LEN):
    """Size of the pattern ENCODING space at this length: 3**L.

    Not every code is reachable — 4 greens + 1 yellow is impossible, so L=5 has
    243 encodings but only 238 attainable patterns. The unreachable codes are
    simply array slots that never fill.
    """
    return 3 ** word_len


def all_green(word_len=WORD_LEN):
    """The winning pattern's code at this length: every position green."""
    return 3 ** word_len - 1


def pattern_dtype(word_len=WORD_LEN):
    """Smallest unsigned dtype holding every pattern code at this length.

    uint8 through L=5 (max 242), uint16 through L=10 (max 59048), uint32 above.
    Keeping L=5 on uint8 is what makes the existing 12972x2315 matrix and the C
    solver's ``uint8_t *PAT`` bit-identical to before.
    """
    top = 3 ** word_len - 1
    if top <= np.iinfo(np.uint8).max:
        return np.uint8
    if top <= np.iinfo(np.uint16).max:
        return np.uint16
    return np.uint32


# --- word lists -----------------------------------------------------------

def load_words(which, length=None):
    """Return a canonical word list. ``which`` in {"mystery", "guess"}.

    With no ``length``: the Wordle lists — mystery = the 2315 possible answers,
    guess = the 12972 allowed guesses (a superset containing every answer).

    With ``length=L``: the hello wordl lists for that length, from
    ``data/shared/words/hello/len<L>/``, built by ``build_wordlists.py``. NOTE
    these are a DIFFERENT curation, not an extension of the Wordle lists —
    ``load_words("mystery", 5)`` is hello's 3238 answers, not the NYT's 2315.

    Lists are pre-sorted + deduped on disk, so index order is stable and
    reproducible across machines.
    """
    if length is None:
        path = os.path.join(_DATA, f"{which}.txt")
    else:
        path = os.path.join(_DATA, "hello", f"len{length}", f"{which}.txt")
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def to_codes(words, word_len=None):
    """Pack a word list into an (n, L) uint8 array of 0..25 letter codes."""
    if word_len is None:
        word_len = len(words[0]) if words else WORD_LEN
    arr = np.frombuffer("".join(words).encode("ascii"), dtype=np.uint8)
    return (arr - ord("a")).reshape(len(words), word_len)


# --- feedback (the old `compare`, encoded) --------------------------------

def pattern(guess, answer):
    """Encoded feedback of ``guess`` against ``answer`` (equal-length strings).

    Faithful port of the old two-pass `compare`: greens first, then yellows
    consuming unused answer letters left-to-right, so repeated letters resolve
    exactly as real Wordle. Returns an int in ``0..3**L - 1``.
    """
    word_len = len(guess)
    tiles = [0] * word_len
    used = [False] * word_len
    for i in range(word_len):
        if guess[i] == answer[i]:
            tiles[i] = 2
            used[i] = True
    for i in range(word_len):
        if tiles[i] == 0:
            for j in range(word_len):
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

    ``guess`` is an L-char string; ``answer_codes`` is the (n, L) uint8 array
    from ``to_codes``, which is what fixes L. Returns an (n,) array in
    ``pattern_dtype(L)``. This is the vectorized core the pattern matrix and
    candidate filtering are built on.
    """
    word_len = answer_codes.shape[1]
    g = np.frombuffer(guess.encode("ascii"), dtype=np.uint8) - ord("a")
    n = answer_codes.shape[0]
    tiles = np.zeros((n, word_len), dtype=np.uint8)
    ans_used = np.zeros((n, word_len), dtype=bool)

    greens = answer_codes == g                       # (n, L)
    tiles[greens] = 2
    ans_used |= greens

    for i in range(word_len):
        need = tiles[:, i] == 0
        if not need.any():
            continue
        # first unused answer position holding letter g[i]
        match = (answer_codes == g[i]) & ~ans_used    # (n, L)
        match[~need] = False
        has = match.any(axis=1)
        j = np.argmax(match, axis=1)                   # first True per row
        rows = np.nonzero(has)[0]
        tiles[rows, i] = 1
        ans_used[rows, j[rows]] = True

    # base-3 encode, position 0 as MSB. Accumulate in uint32 so the sum cannot
    # wrap at L=11 (max code 177146), then narrow to the storage dtype — which
    # leaves L=5 exactly the uint8 it has always been.
    weights = (3 ** np.arange(word_len - 1, -1, -1)).astype(np.uint32)
    codes = tiles.astype(np.uint32) @ weights
    return codes.astype(pattern_dtype(word_len))


# --- candidate bitmap ------------------------------------------------------

def all_alive(n):
    """A fresh candidate bitmap: every one of ``n`` answers still possible."""
    return np.ones(n, dtype=bool)


def filter_alive(alive, pattern_row_vals, observed):
    """Narrow ``alive`` to answers consistent with seeing ``observed`` for a guess.

    ``pattern_row_vals`` is that guess's row of the pattern matrix (len n).
    Returns a new boolean bitmap; the caller keeps the AND-chain of observations.
    """
    return alive & (pattern_row_vals == observed)


def decode(code, word_len=WORD_LEN):
    """Turn an encoded pattern back into an L-tuple of tile codes (for display)."""
    trits = []
    for _ in range(word_len):
        trits.append(code % 3)
        code //= 3
    return tuple(reversed(trits))
