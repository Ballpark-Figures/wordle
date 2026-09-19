"""Does an opening GUARANTEE a win?  Exactly, with no sampling at all.

THE QUESTION, AND WHY IT IS NOT A SIMULATION.  A `wordlesim` strategy is an
opening played blind -- optionally ABANDONED once the follow-up is down to
`adapt` words -- and then a follow-up drawing uniformly from the words still
CONSISTENT with every reply.  `wordlesim` measures how OFTEN that wins within
six.  This asks the stronger question: **is there any answer, and any sequence
of draws the follow-up could make, that takes more than six guesses?**

  A 100% WIN RATE AND A GUARANTEE ARE THE SAME STATEMENT HERE, which is what
  makes the exact form worth having.  Every reachable draw sequence has POSITIVE
  probability -- the follow-up draws uniformly from a finite live set -- so
  "probability 1" and "no reachable sequence loses" coincide.  The simulation
  estimates the first; this decides the second, with no seed and no standard
  error, and a re-run reproduces it exactly.

THIS IS NOT OPTIMAL PLAY, and the `max` below is not a solver choosing well.
The follow-up is the SAME random rule the race measures; the maximum is over
what it could unluckily happen to draw.  Nothing here searches for a good guess,
and no number from here is an optimum.

  SO IT IS NOT AN `optturns`-FAMILY NUMBER EITHER.  Those are optima subject to
  a 6-guess guarantee, over a solver that CHOOSES its guesses.  A guaranteed
  opening here is a statement about a HEURISTIC.  And never table a worst case
  beside a win rate or a mean from wordlesim: those AVERAGE over the very draws
  this maximises over.

THE WORST CASE, STATED EXACTLY.  For a live set S and a true answer a in S:

    L(S, a) = 1                                          if S == {a}
            = 1 + max over g in S, g != a of L(S|g,a, a)  otherwise

where `S|g,a` is the part of S whose reply to g equals a's -- the words still
live after that guess.  While |S| > 1 the follow-up has a wrong word available,
and playing one strictly shrinks S (a word's reply against itself is all-green,
so it eliminates itself), which is why the recursion terminates.  An opening's
worst case is the largest `t + L(S, a)` over every answer, where `t` is how many
opening words were actually PLAYED before the follow-up took over.

WHICH WORDS THE FOLLOW-UP MAY PLAY IS PART OF THE QUESTION.  Under the `custom`
follow-up it draws from custom.txt's 4282, so it can spend a guess on a word
that could never be the answer -- which is what a worst case is made of, and the
whole difference from the `answer` pool's 2315.  The hidden answer still comes
from the 2315 whichever pool is in play.

THE ADAPTIVE RULE COUNTS.  `adapt` N abandons the rest of the opening once the
follow-up's live count is N or fewer, which SHORTENS the opening and leaves more
guesses for the tail -- so the budget is per ANSWER, not per opening.  The count
is the FOLLOW-UP's, over its own pool, exactly as `wordlesim.AdaptiveOpening`
defines it.
"""

import numpy as np

# Base-243 joint reply codes: 5 tiles, so one word's reply fits in 243 values and
# k of them in 243**k.  At k = 5 that is 14.3 billion, past float64's exact range
# but inside int64, which is what these are.
_RADIX = 243


def joint_keys(rows):
    """Fold a (k, n) stack of reply codes into one int64 key per column."""
    key = np.zeros(rows.shape[1], dtype=np.int64)
    for r in rows:
        key = key * _RADIX + r
    return key


def stop_levels(pool_rows, ans_rows, adapt):
    """How many opening words each ANSWER actually sees played.

    Mirrors `wordlesim.AdaptiveOpening`: before each word after the first, the
    rule asks the follow-up how many words it would be choosing between, and at
    `adapt` or fewer it declines.  Returns (level, live_count) per answer, where
    `level` is how many words were played -- always at least 1, at most k.
    """
    k, na = ans_rows.shape
    level = np.full(na, k, dtype=np.int32)
    counts = np.zeros(na, dtype=np.int64)
    settled = np.zeros(na, dtype=bool)
    pkey = np.zeros(pool_rows.shape[1], dtype=np.int64)
    akey = np.zeros(na, dtype=np.int64)
    for t in range(k):
        pkey = pkey * _RADIX + pool_rows[t]
        akey = akey * _RADIX + ans_rows[t]
        uniq, inv = np.unique(pkey, return_inverse=True)
        sizes = np.bincount(inv, minlength=len(uniq))
        # every answer is in the pool, so its key is present and this is exact
        live = sizes[np.searchsorted(uniq, akey)]
        counts = np.where(settled, counts, live)
        if adapt and t + 1 < k:
            fire = (~settled) & (live <= adapt)
            level[fire] = t + 1
            settled |= fire
    return level, counts


def solved_within(sub_rows, answer_pos, budget):
    """Is `worst_case(sub_rows, answer_pos) <= budget`?  The DECISION problem.

    THE SAME RULE, ASKED AS A YES/NO, and that is the whole point: `worst_case`
    computes the exact value, so it recurses until every branch bottoms out at a
    singleton however deep that is.  Here the recursion stops at `budget`, and
    one losing draw settles the answer immediately.

    **WHY IT EXISTS: a value is unaffordable where a verdict is cheap.**  With a
    4-word opening the live sets are tiny (max 16 measured) and the difference
    does not show.  With THREE words they are not -- measured on `ledge pawns`,
    207 live buckets holding 2860 pool words with a maximum of 136 -- and the
    exact walk on a 136-word set did not finish in EIGHT MINUTES for a single
    whole-pool pass, while the capped one answers in milliseconds.  Nothing here
    ever needed the value; `unsolved` only ever asked whether it exceeded the
    budget.

    `budget <= 1` with more than one word left is the early exit that does the
    work: one guess cannot both separate and name.

    Gated against `worst_case` directly -- `solved_within(S, a, b)` must equal
    `worst_case(S, a) <= b` for every b -- so the fast form cannot drift from
    the definition.
    """
    n = sub_rows.shape[0]
    if n <= budget:
        # `worst_case(S, a) <= |S|`: every wrong draw eliminates at least the
        # word drawn, so a set no bigger than the budget is always finished
        # inside it.  The SAME bound `prefix_buckets` prunes on, applied at
        # every level rather than only the top -- which is most of the speed,
        # because the parts below the first draw are nearly all small.
        return True
    if budget <= 1:
        return False
    for g in range(n):
        if g == answer_pos:
            continue                       # drawing the answer ends it; see below
        keep = np.flatnonzero(sub_rows[g] == sub_rows[g][answer_pos])
        if len(keep) == n:
            raise AssertionError("a guess failed to eliminate itself")
        pos = int(np.searchsorted(keep, answer_pos))
        if not solved_within(sub_rows[np.ix_(keep, keep)], pos, budget - 1):
            return False                   # one bad draw is enough to lose
    return True


def worst_case(sub_rows, answer_pos):
    """L(S, a) for one small live set, given its own reply sub-matrix.

    `sub_rows[i][j]` is the reply of live word i against live word j, and
    `answer_pos` indexes the answer within the set.  Counting the naming guess,
    so a singleton costs 1.
    """
    n = sub_rows.shape[0]
    if n == 1:
        return 1
    worst = 0
    for g in range(n):
        if g == answer_pos:
            # Skipping this is an OPTIMISATION, not the rule: drawing the answer
            # ends the game in one more guess, and any wrong word costs at least
            # that, so including it could never raise the maximum.  Verified by
            # mutation -- removing the skip changes no answer.
            continue
        keep = np.flatnonzero(sub_rows[g] == sub_rows[g][answer_pos])
        if len(keep) == n:
            # g separated nothing, so the set is unchanged and the game is
            # unbounded -- impossible, since g's own reply eliminates g
            raise AssertionError("a guess failed to eliminate itself")
        pos = int(np.searchsorted(keep, answer_pos))
        worst = max(worst, worst_case(sub_rows[np.ix_(keep, keep)], pos))
    return 1 + worst
