"""Sea of Greens -- the badge objective stated exactly, plus a slow reference.

THE BADGE.  NYT Wordle awards the "Sea of Greens" badge for COMPLETING a puzzle
with no YELLOW tile anywhere in the game.  Greys are fine and so is any number
of guesses; one yellow, in any row, at any point, kills it.  A shared example:

    Wordle 1,720 2/6   greens/greys only, no yellow -> badge
    row 1: green grey green grey grey
    row 2: green green green green green

PROVENANCE, and say this whenever a number from here is quoted.  That rule was
read from player reports and discussion via web search, NOT from the NYT and NOT
from a verified badge screen of our own.  It has exactly the standing of the
Absurdle tie-break rules in `absurdle.py`: the likeliest reading of the public
evidence, unverified against the source.  Two clauses in particular are
INFERRED rather than observed: that a FAILED game (X/6) with no yellows does not
earn it, and that a lucky 1/6 does.  Check both against a real badge before any
number ships.

THE OBJECTIVE IS LEXICOGRAPHIC, and it is the user's call (2026-09-03):

    1. HARD CONSTRAINT -- the strategy must resolve EVERY one of the 2315
       answers within `depth` guesses.  Losing a game to chase the badge is not
       allowed, so this is not "maximise P(badge)": it is the maximum SUBJECT TO
       a 6-guess guarantee, and the two are different quantities.
    2. Subject to that, MAXIMISE the number of answers whose play is yellow-free.

    Once a yellow appears the badge is gone for that answer and the strategy is
    only required to WIN from there -- "once we get a yellow, we stop checking".

THE CAP IS PART OF THE OBJECTIVE and here it is not a tuning knob: `depth` is 6
because a Wordle game is 6 guesses, and clause 1 is exactly "do not lose".  A
depth-7 run would answer a question about a game nobody plays.  It stays a flag
so the gate can check small cases, and every depth still gets its own file.

THE VALUE FUNCTION.  Both clauses ride in ONE integer per state, which is what
makes the search memoisable:

    v(S, d) = -1                       if no strategy resolves all of S within d
            = max badges over all such strategies, otherwise

    v(S, d) = max over legal g of
                  [1 if g in S]                       the all-green bucket wins
                + sum over yellow-free non-green buckets P of v(P, d-1)
              subject to  v(P, d-1) >= 0  for EVERY bucket P, yellow ones too

A bucket whose pattern contains a yellow contributes 0 badges but STILL has to
be winnable -- that is clause 1 -- and nothing about it is scored beyond that,
which is clause 2's "stop checking".  So a yellow bucket only needs
`feasible(P, d-1)`, the decision version, which is much cheaper than v.

WHAT IS IN HERE.  A deliberately slow, string-based reference: every pattern is
recomputed with `wordle.pattern` and candidate sets are tuples of words.  It is
the ORACLE for `solver/greens.c` (see `tools/checkgreens.py`), which is why it
shares no data structure with it -- no pattern matrix, no indices, no bitsets.
Do not optimise it; its whole value is being a second opinion.
"""
import sys
from collections import defaultdict

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from wordle import WORD_LEN, all_green, pattern  # noqa: E402

INFEASIBLE = -1


def has_yellow(code, word_len=WORD_LEN):
    """True iff the base-3 feedback code carries a yellow (a digit equal to 1).

    The badge turns on this one predicate.  Note it is a property of the CODE,
    so it needs no knowledge of the guess or the answer.
    """
    for _ in range(word_len):
        if code % 3 == 1:
            return True
        code //= 3
    return False


def yellow_free_codes(word_len=WORD_LEN):
    """Every code with no yellow digit: 2**L of the 3**L (32 of 243 at L=5).

    All of them are attainable, unlike the full space -- the unreachable codes
    are the "L-1 greens plus a yellow" ones, and those all carry a yellow.
    """
    return frozenset(c for c in range(3 ** word_len) if not has_yellow(c, word_len))


def partition(guess, cands):
    """code -> tuple of candidates giving that code against `guess`."""
    out = defaultdict(list)
    for a in cands:
        out[pattern(guess, a)].append(a)
    return {c: tuple(v) for c, v in out.items()}


def feasible(cands, guesses, depth, memo=None):
    """Can some strategy resolve every word of `cands` within `depth` guesses?

    The badge plays no part here -- this is clause 1 alone, and it is what a
    yellow bucket is held to.  Early-exits on the first witness guess, since any
    witness settles the question.
    """
    if memo is None:
        memo = {}
    n = len(cands)
    if n <= 1:
        return n == 0 or depth >= 1
    if depth <= 1:
        return False
    key = (cands, depth)
    if key in memo:
        return memo[key]
    memo[key] = False                      # guard: a state cannot depend on itself
    ag = all_green(len(cands[0]))
    ok = False
    for g in guesses:
        parts = partition(g, cands)
        if len(parts) == 1:
            continue                       # reveals nothing; strictly weaker
        if all(feasible(sub, guesses, depth - 1, memo)
               for code, sub in parts.items() if code != ag):
            ok = True
            break
    memo[key] = ok
    return ok


def solve(cands, guesses, depth, memo=None, fmemo=None):
    """(value, best guess) for a state whose badge is still ALIVE.

    value is INFEASIBLE (-1) when no strategy wins every candidate within
    `depth`; otherwise it is the maximum number of candidates that can be won
    yellow-free while still winning them all.
    """
    if memo is None:
        memo = {}
    if fmemo is None:
        fmemo = {}
    n = len(cands)
    if n == 0:
        return 0, None
    if n == 1:
        return (1, cands[0]) if depth >= 1 else (INFEASIBLE, None)
    if depth <= 1:
        return INFEASIBLE, None
    key = (cands, depth)
    if key in memo:
        return memo[key]
    memo[key] = (INFEASIBLE, None)         # guard against self-dependence
    word_len = len(cands[0])
    ag = all_green(word_len)

    best, bestg = INFEASIBLE, None
    for g in guesses:
        parts = partition(g, cands)
        if len(parts) == 1:
            continue
        val, ok = 0, True
        for code, sub in parts.items():
            if code == ag:
                val += 1                   # sub is exactly (g,): won, no yellow
            elif has_yellow(code, word_len):
                if not feasible(sub, guesses, depth - 1, fmemo):
                    ok = False
                    break                  # clause 1: must still be winnable
            else:
                v, _ = solve(sub, guesses, depth - 1, memo, fmemo)
                if v < 0:
                    ok = False
                    break
                val += v
        if ok and val > best:
            best, bestg = val, g
    memo[key] = (best, bestg)
    return best, bestg


def solve_opener(opener, answers, guesses, depth):
    """Value of committing to `opener` as the first guess.

    The root is a branching point like any other, so this is just the guess loop
    of `solve` with the guess pinned -- kept separate because that is the number
    the solver reports per opener.
    """
    cands = tuple(sorted(answers))
    word_len = len(cands[0])
    ag = all_green(word_len)
    memo, fmemo = {}, {}
    parts = partition(opener, cands)
    if len(parts) == 1:
        return INFEASIBLE
    val = 0
    for code, sub in parts.items():
        if code == ag:
            val += 1
        elif has_yellow(code, word_len):
            if not feasible(sub, guesses, depth - 1, fmemo):
                return INFEASIBLE
        else:
            v, _ = solve(sub, guesses, depth - 1, memo, fmemo)
            if v < 0:
                return INFEASIBLE
            val += v
    return val
