"""THE LADDER: one committed word per level, each fired by its own THRESHOLD on
how many letters you have matched.

THE STRATEGY (the user's, 2026-09-22), and this module IS the source of truth
for it; `solver/secondexact.c --ladder N` is the fast implementation.

    guess 1     w1                                       always
    guess d     matched < T_d ?  w_d  :  a uniformly random consistent ANSWER,
                                         and the LADDER IS OVER
    guess N+1   a uniformly random consistent ANSWER

So the whole strategy is N words and N-1 thresholds -- nine numbers at N = 5 --
and the only thing it asks a player to read off the board is a count of letters.

WHAT `matched` IS.  The CUMULATIVE number of letters proved present over every
reply so far: tree_states' greens + yellows, counted AGAIN for each proved copy,
with a position some reply turned green counted as a green forever after.  It is
a function of the WORDS AND REPLIES alone, never of the answer, so it is constant
within a bucket -- which is what makes it a legal thing to branch on, and what
lets the value be summed exactly rather than simulated.  `tree_states.
state_from_strings` is the independent implementation the gate diffs against.

DECLINING ENDS THE LADDER.  Once a level is over its threshold, every remaining
guess is random; word d is played only when levels 2..d-1 all fired.  The other
reading -- test every level against the board whatever was played before -- is a
different and strictly richer strategy, and is NOT what this computes.

THE VALUE IS EXACT.  The random tail's cost depends only on the live candidate
SET, and playing a uniform random g from S sends the answer into a part of S that
never contains g, so the recursion terminates:

    T(S) = |S| + (1/|S|) * sum over g in S of sum over parts P != {g} of T(P)

There is no seed and no standard error.  `secondexact.c` states the same
recursion and the bound the search prunes with.

WHAT THE NUMBER IS.  Expected guesses OUTRIGHT -- play is never truncated -- so
it belongs with `wordlesim` / `multiwordle` / `foximax` and NEVER in a table with
an optturns-family total, every one of which is an optimum SUBJECT TO a 6-guess
guarantee.  Guess 6 being random is not a cap; it is where a 5-word ladder runs
out of committed words.

IT IS TIED TO THE `answer` FOLLOW-UP: the tail draws from consistent ANSWERS, so
a state is a subset of the 2315.

THE LEVEL-2 THRESHOLD IS A GROUP CONDITION, AND THAT IS THE ORACLE.  After ONE
guess the board shows 5 tiles and nothing else, so matched = 5 - greys exactly.
Hence `matched < T` at level 2 IS `greys >= 6 - T`, which is groups.c's `g<6-T>`
-- so a 2-level ladder with a pinned threshold must reproduce `secondexact
--group g<6-T>` to the last digit, by two code paths that share no search.
Deeper the equivalence stops: matched accumulates across replies and the greys of
one reply no longer determine it.

This module is a REFERENCE, written for clarity and for the gate to diff against.
It works over WORDS and recomputes every reply from the strings; it is far too
slow for the real lists beyond a handful of openers.
"""

from collections import Counter
from fractions import Fraction
from functools import lru_cache

__all__ = ["tiles", "matched_letters", "tail_total", "ladder_total",
           "threshold_of_grays", "grays_of_threshold"]


def tiles(guess, answer):
    """The reply as a tuple of 0/1/2 tiles, from the STRINGS, by the multiset
    rule -- greens first, then the answer's spare copies handed out left to
    right.  A second implementation of `wordle.pattern`, deliberately: a
    repeated-letter mistake in one cannot be shared by the other."""
    out = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if out[i] == 0 and left[g]:
            out[i] = 1
            left[g] -= 1
    return tuple(out)


def matched_letters(guesses, replies):
    """Cumulative greens + yellows after the given (guess, reply) pairs.

    Per LETTER, the most copies any single reply proved -- its non-grey tiles of
    that letter.  Per POSITION, green is permanent: a position some reply turned
    green counts as a green even if a later guess put a different letter there.
    Greens are counted first and each letter's remaining proved copies are the
    yellows, so greens + yellows is exactly the number of answer slots accounted
    for and 5 - that is the blanks.
    """
    pinned = {}                       # position -> the letter pinned there
    known = {}                        # letter -> most copies any reply proved
    for g, p in zip(guesses, replies):
        seen = Counter()
        for i, (ch, t) in enumerate(zip(g, p)):
            if t:
                seen[ch] += 1
            if t == 2:
                pinned[i] = ch
        for ch, n in seen.items():
            if n > known.get(ch, 0):
                known[ch] = n
    greens = len(pinned)
    pin = Counter(pinned.values())
    yellows = sum(max(0, n - pin[ch]) for ch, n in known.items())
    return greens + yellows


def grays_of_threshold(t, word_len=5):
    """The group condition a LEVEL-2 threshold is: `matched < t` means
    `greys >= word_len + 1 - t`.  Only valid at level 2, where exactly one reply
    has been seen."""
    return word_len + 1 - t


def threshold_of_grays(n, word_len=5):
    """The inverse: `greys >= n` is `matched < word_len + 1 - n`."""
    return word_len + 1 - n


@lru_cache(maxsize=None)
def tail_total(words):
    """T(S): total guesses summed over the answers in S, playing a uniformly
    random consistent ANSWER every turn.  Exact rationals, so nothing here is a
    float comparison."""
    words = tuple(sorted(words))
    n = len(words)
    if n <= 1:
        return Fraction(n)
    tot = Fraction(n)
    for g in words:
        parts = {}
        for a in words:
            if a != g:
                parts.setdefault(tiles(g, a), []).append(a)
        for p in parts.values():
            tot += tail_total(tuple(p)) / n
    return tot


def ladder_total(opener, rungs, answers):
    """The EXACT total guesses over `answers` under one ladder.

    `rungs` is [(w2, T2), (w3, T3), ...] in order; a rung whose word is None ends
    the ladder there.  Returns a Fraction, so `ladder_total(...) / len(answers)`
    is the expected guesses with no rounding anywhere.

    Written as the strategy reads: play the word, split what it leaves by the
    reply, and at each level compare the cumulative matched count against that
    level's threshold.
    """
    answers = tuple(answers)

    def walk(live, guesses, replies, rungs):
        """`live` is the set still consistent; `guesses`/`replies` the history.
        The cost returned covers every guess from here on, summed over `live`."""
        if not live:
            return Fraction(0)
        if not rungs or rungs[0][0] is None:
            return tail_total(tuple(sorted(live)))
        w, thr = rungs[0]
        # THE THRESHOLD IS TESTED ON THE BOARD AS IT STANDS, before this guess.
        # It is constant across `live` -- it depends only on the replies -- so
        # the whole set fires or the whole set leaves.
        if matched_letters(guesses, replies) >= thr:
            return tail_total(tuple(sorted(live)))
        tot = Fraction(len(live))                  # this guess, once per answer
        parts = {}
        for a in live:
            parts.setdefault(tiles(w, a), []).append(a)
        for p, members in parts.items():
            if all(t == 2 for t in p):
                continue                           # w was the answer: nothing more
            tot += walk(members, guesses + [w], replies + [p], rungs[1:])
        return tot

    tot = Fraction(0)
    parts = {}
    for a in answers:
        parts.setdefault(tiles(opener, a), []).append(a)
    for p, members in parts.items():
        tot += len(members)                        # the opener, once per answer
        if all(t == 2 for t in p):
            continue
        tot += walk(members, [opener], [p], list(rungs))
    return tot
