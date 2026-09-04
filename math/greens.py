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

TWO OBJECTIVES LIVE HERE, and they are DIFFERENT QUANTITIES.  Never quote one
as the other, and never put them in one table.

  PLAIN (the default, and the one asked for -- user, 2026-09-04):

      MAXIMISE the number of answers WON WITHIN `depth` GUESSES WITH NO YELLOW.

      One event per answer, not a constraint plus an objective: an answer counts
      iff the play both stays yellow-free AND finishes inside the cap.  An answer
      that draws a yellow is simply LOST and the strategy owes it nothing
      afterwards -- it may abandon that game entirely.  So yellow branches are
      never searched, which is also why this is much the cheaper of the two.

  MUST-WIN (`must_win=True`, `--must-win`):

      The same maximisation SUBJECT TO the strategy still resolving EVERY answer
      within `depth`, yellow ones included.  Lexicographic: the guarantee first,
      the badge second.  A strictly smaller strategy space, so its value is
      always <= the plain one.

IN PLAIN WORDS.  Plain asks "how often can I win in 6 with all greens?".
Must-win asks "if I refuse to ever lose a game, how often can I win in 6 with
all greens?".  The second is a real question but it is not the badge question --
the badge does not care about games that were never going to be badged anyway.

THE CAP IS PART OF THE OBJECTIVE and here it is not a tuning knob: `depth` is 6
because a Wordle game is 6 guesses, and clause 1 is exactly "do not lose".  A
depth-7 run would answer a question about a game nobody plays.  It stays a flag
so the gate can check small cases, and every depth still gets its own file.

THE VALUE FUNCTIONS.

  PLAIN.  Non-negative, always defined, and it never looks at a yellow bucket:

      w(S, d) = 0                                if d == 0
              = 1                                if d == 1 (play a candidate)
              = max over g of  [1 if g in S]
                             + sum over yellow-free non-green P of w(P, d-1)

  MUST-WIN.  Both clauses ride in ONE integer per state, which is what makes it
  memoisable:

      v(S, d) = -1                    if no strategy resolves all of S within d
              = max badges over all such strategies, otherwise
      v(S, d) = max over g of  [1 if g in S]
                             + sum over yellow-free non-green P of v(P, d-1)
                subject to v(P, d-1) >= 0 for EVERY bucket P, YELLOW ONES TOO

  A yellow bucket contributes 0 badges either way.  The difference is entirely
  whether it must still be WINNABLE: under must-win it needs `feasible(P, d-1)`,
  the decision version; under plain it is not examined at all.

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


def beam_order(cands, guesses):
    """Guesses that SPLIT `cands`, ordered the way --topk selects them.

    Ascending sum of squared bin sizes -- the evenest split first -- with ties on
    the lowest guess index. It is the one ranking rule this repo uses, and the
    ONLY thing the beam selects on: deliberately not also the solver's counting
    bound, since a selection that depended on a bound this reference does not
    have could not be checked against the solver at all.
    """
    scored = []
    for i, g in enumerate(guesses):
        parts = partition(g, cands)
        if len(parts) == 1:
            continue                       # reveals nothing
        ss = sum(len(v) * len(v) for v in parts.values())
        scored.append((ss, i, g))
    scored.sort()
    return [g for _, _, g in scored]


def solve(cands, guesses, depth, memo=None, fmemo=None, topk=0, must_win=False):
    """(value, best guess) for a state whose badge is still ALIVE.

    value is INFEASIBLE (-1) when no strategy wins every candidate within
    `depth`; otherwise it is the maximum number of candidates that can be won
    yellow-free while still winning them all.

    Under the PLAIN objective (the default) the value is never negative: a
    yellow bucket is worth nothing and is never examined, so nothing can fail.
    Under `must_win` it is INFEASIBLE (-1) when no strategy wins every candidate
    within `depth`.

    `topk` beams it, exactly as `solver/greens.c` does: recurse into only the
    first `topk` of `beam_order`, EXCEPT that the scan continues past the beam
    while nothing feasible has been found -- so under must_win the guarantee
    stays exact and only the badge count is approximated. A beamed value is
    achievable by a real strategy, hence a LOWER bound on the unbeamed one.
    """
    if memo is None:
        memo = {}
    if fmemo is None:
        fmemo = {}
    n = len(cands)
    if n == 0:
        return 0, None
    if depth <= 0:
        return (INFEASIBLE, None) if must_win else (0, None)
    if n == 1:
        return 1, cands[0]
    if depth == 1:
        # One guess left, more than one candidate. No guarantee is possible, so
        # must_win fails; plain just plays a candidate and badges it if right.
        return (INFEASIBLE, None) if must_win else (1, cands[0])
    key = (cands, depth, must_win)
    if key in memo:
        return memo[key]
    memo[key] = (INFEASIBLE if must_win else 0, None)   # self-dependence guard
    word_len = len(cands[0])
    ag = all_green(word_len)

    best, bestg = INFEASIBLE, None
    order = beam_order(cands, guesses) if topk else guesses
    for i, g in enumerate(order):
        if topk and i >= topk and best >= 0:
            break                          # past the beam, and something works
        parts = partition(g, cands)
        if len(parts) == 1:
            continue
        val, ok = 0, True
        for code, sub in parts.items():
            if code == ag:
                val += 1                   # sub is exactly (g,): won, no yellow
            elif has_yellow(code, word_len):
                # The badge is gone for these answers. Under the plain objective
                # that is the end of it; under must_win they must still be
                # winnable, and that is the only thing ever asked of them.
                if must_win and not feasible(sub, guesses, depth - 1, fmemo):
                    ok = False
                    break
            else:
                v, _ = solve(sub, guesses, depth - 1, memo, fmemo, topk, must_win)
                if v < 0:
                    ok = False
                    break
                val += v
        if ok and val > best:
            best, bestg = val, g
        if best == len(cands):
            break                          # every candidate badged
    memo[key] = (best, bestg)
    return best, bestg


def opener_order(answers, guesses):
    """The openers --topk examines, best first: the root is a branching point
    like any other, so it is the same rule over the whole answer set."""
    return beam_order(tuple(sorted(answers)), guesses)


def solve_opener(opener, answers, guesses, depth, topk=0, must_win=False):
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
            if must_win and not feasible(sub, guesses, depth - 1, fmemo):
                return INFEASIBLE
        else:
            v, _ = solve(sub, guesses, depth - 1, memo, fmemo, topk, must_win)
            if v < 0:
                return INFEASIBLE
            val += v
    return val
