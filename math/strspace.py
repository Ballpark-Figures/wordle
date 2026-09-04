"""Candidate sets over EVERY length-L string, held as CONSTRAINTS, not lists.

The word-list cells of the strategy grid can carry their candidate set as an
explicit array of answer indices, because there are only 2315 or 12972 of them.
The cells whose ANSWER set is every 5-letter string cannot: 26**5 = 11,881,376,
so a per-node list is both too big to store and too big to hash.

The way out is that such a set is never arbitrary. Whatever sequence of guesses
and feedback produced it, the surviving strings are exactly those satisfying:

  * a per-POSITION set of allowed letters   (greens pin, yellows and greys ban)
  * a per-LETTER minimum count `lo`         (greens and yellows demand)
  * a per-LETTER maximum count `hi`         (a grey caps the letter at what the
                                             non-grey copies in that guess showed)

That is ~72 bytes whatever the candidate count, it is hashable as-is, and a
guess splits it into at most 3**L children by refining it once per pattern. The
size of the set is then a COUNTING problem -- a DP over positions carrying the
counts of the constrained letters -- never an enumeration.

`alpha` is the alphabet size and `length` the word length, both parameters, so
the whole thing can be checked EXHAUSTIVELY on a small alphabet where every
state and every string can be enumerated by brute force. See
`tools/checkstrspace.py`; that is the gate, not a spot check.

NOTHING HERE CHOOSES A STRATEGY OR SCORES ONE. It is the state representation
only: refine, count, partition. What to do with it is a separate question.
"""

from itertools import product

WORD_LEN = 5
ALPHABET = 26


class State:
    """A candidate set over `alpha`**`length` strings, as constraints.

    `allow[i]` is a bitmask of letters legal at position i; `lo[c]`/`hi[c]` bound
    how many copies of letter c the answer holds. Immutable and hashable, so it
    doubles as a transposition-table key with no separate encoding step.
    """

    __slots__ = ("allow", "lo", "hi", "length", "alpha", "_key")

    def __init__(self, allow, lo, hi, length, alpha):
        self.allow = tuple(allow)
        self.lo = tuple(lo)
        self.hi = tuple(hi)
        self.length = length
        self.alpha = alpha
        self._key = (self.allow, self.lo, self.hi, length, alpha)

    def __eq__(self, other):
        return isinstance(other, State) and self._key == other._key

    def __hash__(self):
        return hash(self._key)

    def __repr__(self):
        pos = ["".join(chr(ord("a") + c) for c in range(self.alpha)
                       if self.allow[i] >> c & 1) for i in range(self.length)]
        bounds = " ".join("%s%d-%d" % (chr(ord("a") + c), self.lo[c], self.hi[c])
                          for c in range(self.alpha)
                          if self.lo[c] or self.hi[c] < self.length)
        return "State(%s | %s)" % (" ".join(pos), bounds or "-")


def initial(length=WORD_LEN, alpha=ALPHABET):
    """The unconstrained set: every one of `alpha`**`length` strings."""
    full = (1 << alpha) - 1
    return State([full] * length, [0] * alpha, [length] * alpha, length, alpha)


def refine(st, guess, code):
    """The subset of `st` consistent with `guess` scoring feedback `code`.

    `guess` is a sequence of letter codes; `code` is the base-3 encoding used
    everywhere else in the repo (position 0 most significant, 2 = green,
    1 = yellow, 0 = grey). Returns a State, or None when the constraints are
    outright contradictory.

    NOTE an EMPTY-but-consistent result is a State, not None: the five
    unreachable patterns (L-1 greens plus a yellow) refine to a state whose
    count is 0 rather than to a contradiction, and `count` is what says so.
    """
    length, alpha = st.length, st.alpha
    tiles = []
    c = code
    for _ in range(length):
        tiles.append(c % 3)
        c //= 3
    tiles.reverse()

    allow = list(st.allow)
    lo = list(st.lo)
    hi = list(st.hi)

    nongrey = [0] * alpha
    grey = [False] * alpha
    for i, t in enumerate(tiles):
        if t:
            nongrey[guess[i]] += 1
        else:
            grey[guess[i]] = True

    # YELLOWS ARE A PREFIX OF A LETTER'S NON-GREEN COPIES, and a pattern that
    # breaks that is UNREACHABLE, not merely empty. `wordle.pattern` marks greens
    # first, then walks the remaining positions LEFT TO RIGHT handing out the
    # answer's spare copies until they run out -- so for one letter, the non-green
    # copies read yellow, yellow, ..., grey, grey. A grey followed by a yellow of
    # the SAME letter can never be produced. The count bounds below cannot see
    # this (both orders give identical lo/hi), so without this test `abb` reports
    # 8 non-empty patterns where only 7 exist, and every count downstream of the
    # phantom one is wrong. Caught by tools/checkstrspace.py; a distinct-letter
    # guess like `salet` never exercises it.
    seen_grey = [False] * alpha
    for i, t in enumerate(tiles):
        if t == 2:
            continue
        g = guess[i]
        if t == 0:
            seen_grey[g] = True
        elif seen_grey[g]:
            return None

    for i, t in enumerate(tiles):
        g = guess[i]
        if t == 2:
            allow[i] &= 1 << g          # green pins this position
        else:
            allow[i] &= ~(1 << g)       # yellow and grey both ban it HERE
        if allow[i] == 0:
            return None

    for g in range(alpha):
        if nongrey[g] > lo[g]:
            lo[g] = nongrey[g]
        if grey[g] and nongrey[g] < hi[g]:
            hi[g] = nongrey[g]          # a grey copy caps the letter exactly
        if lo[g] > hi[g]:
            return None

    if sum(lo) > length:
        return None
    return _canon(allow, lo, hi, length, alpha)


def _canon(allow, lo, hi, length, alpha):
    """Put a state in canonical form, or return None if it is contradictory.

    Two propagations, both implied by the constraints they come from -- so the
    SET is unchanged and only the representation moves:

      * `hi[c] == 0` means c appears nowhere, so clear it from EVERY position
        mask. Refinement only clears the position it was guessed at, which
        leaves the same set described two different ways -- bad for a
        transposition table keyed on the state -- and leaves a dead letter in
        the counting DP's constrained list, where it costs work for nothing.
      * a position with a single allowed letter FORCES that letter, so it lifts
        that letter's floor.

    Then two cheap contradiction tests: a letter cannot be required more often
    than it has positions available, and the floors cannot exceed the length.
    """
    allow = list(allow)
    lo = list(lo)
    hi = list(hi)
    for c in range(alpha):
        if hi[c] == 0:
            bit = ~(1 << c)
            for i in range(length):
                allow[i] &= bit
    forced = [0] * alpha
    for i in range(length):
        if allow[i] == 0:
            return None
        if allow[i] & (allow[i] - 1) == 0:          # exactly one letter legal
            forced[allow[i].bit_length() - 1] += 1
    avail = [0] * alpha
    for i in range(length):
        m = allow[i]
        while m:
            b = m & -m
            avail[b.bit_length() - 1] += 1
            m ^= b
    for c in range(alpha):
        if forced[c] > lo[c]:
            lo[c] = forced[c]
        if lo[c] > hi[c] or lo[c] > avail[c]:
            return None
    if sum(lo) > length:
        return None
    return State(allow, lo, hi, length, alpha)


def count(st):
    """How many strings satisfy `st`. Exact, and never enumerates.

    A DP across positions whose key is the count vector of the CONSTRAINED
    letters only -- the ones with a nonzero floor or a ceiling below `length`.
    Unconstrained letters legal at a position collapse into a single multiplier,
    which is what keeps the key small: after k guesses at most 5k letters have
    been mentioned, so the vector stays short however big the alphabet is.
    `hi` prunes during the walk; `lo` is applied to the surviving keys at the end.
    """
    length, alpha = st.length, st.alpha
    con = [c for c in range(alpha) if st.lo[c] or st.hi[c] < length]
    if not con:
        total = 1
        for m in st.allow:
            total *= bin(m).count("1")
        return total

    conset = {c: k for k, c in enumerate(con)}
    dp = {(0,) * len(con): 1}
    for i in range(length):
        mask = st.allow[i]
        here = [c for c in con if mask >> c & 1]
        free = bin(mask).count("1") - len(here)
        nxt = {}
        for key, ways in dp.items():
            if free:
                nxt[key] = nxt.get(key, 0) + ways * free
            for c in here:
                k = conset[c]
                if key[k] < st.hi[c]:
                    nk = key[:k] + (key[k] + 1,) + key[k + 1:]
                    nxt[nk] = nxt.get(nk, 0) + ways
        dp = nxt
        if not dp:
            return 0

    total = 0
    for key, ways in dp.items():
        if all(key[k] >= st.lo[c] for c, k in conset.items()):
            total += ways
    return total


def partition(st, guess):
    """Split `st` by the feedback `guess` would draw: {code: (State, count)}.

    Only non-empty parts are returned, so the result is the guess's real
    branching profile -- the thing a solver bounds and orders on. The counts sum
    to `count(st)`, which is the cheapest available check that this is a genuine
    partition; `tools/checkstrspace.py` asserts it.
    """
    out = {}
    for code in range(3 ** st.length):
        sub = refine(st, guess, code)
        if sub is None:
            continue
        n = count(sub)
        if n:
            out[code] = (sub, n)
    return out


def enumerate_strings(st):
    """Every string satisfying `st`, as tuples of letter codes -- BRUTE FORCE.

    Exponential by construction and only for verification on a small alphabet.
    Never call it on the real 26**5 space from solver code.
    """
    out = []
    for s in product(range(st.alpha), repeat=st.length):
        if any(not (st.allow[i] >> s[i] & 1) for i in range(st.length)):
            continue
        ok = True
        for c in range(st.alpha):
            k = s.count(c)
            if k < st.lo[c] or k > st.hi[c]:
                ok = False
                break
        if ok:
            out.append(s)
    return out
