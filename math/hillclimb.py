"""Improve an opening by SWAPPING ONE WORD AT A TIME, from a random start.

THE SEARCH (the user's, 2026-09-18).  Draw `k` random words.  Score them.  Then
ask, for every position and every candidate word, whether putting that word in
that position lowers the number of UNSOLVED answers; take the best such swap and
repeat until none does.  That is a local optimum.  Restart from a fresh random
draw and do it again, `--trials` times.

WHY IT IS AFFORDABLE, AND WHY IT NEEDED NO NEW SCORER.  A blind opening is a
SET, so "swap the word in position i" is the same question as "hold the other
k-1 fixed and choose the last word" -- which `paircover.last_level_scores`
already answers for EVERY candidate in one pass, by grouping candidates on the
partition they induce rather than on their replies.  One neighbourhood scan is
therefore k calls to it, not `k * ncand` separate evaluations.

  MEASURED: a full 4-position scan over the 4282-word custom pool is a few
  seconds, against roughly 12 hours if each candidate were scored on its own.

IT IS A LOCAL OPTIMUM, NOT AN OPTIMUM, and the distinction is the whole claim.
A climb stops where no SINGLE swap helps; two words might have to change
together to get past it, and this never tries that.  So a result is "the best of
`--trials` random starts, each climbed to where one-word moves run out" -- never
"the best opening".  The restarts are the only thing exploring; the climb itself
is greedy and deterministic given its start.

THE OBJECTIVE IS THE GUARANTEE CONDITION, the same number `greedybuild`,
`paircover` and `guarantee_sweep` all compute: how many of the 2315 answers can
be made to lose, with the follow-up drawing from the pool.  Ties break on ssq,
the repo's standing second key.

TWO LISTS, AS EVERYWHERE HERE.  The POOL is what the opening partitions and what
the random fifth guess draws from, so it is what `unsolved` counts over and it
must hold every answer.  The CANDIDATES are only what the k words may be drawn
from, and need not contain the answers.
"""

import numpy as np

from paircover import last_level_scores   # the one slot-scorer; see the note above


def neighbourhood(full, cols, M, words, ans, current, banned_extra=()):
    """The best IMPROVING single-word swap, or None if this is a local optimum.

    Returns `(unsolved, ssq, position, candidate)` for the best swap over EVERY
    position and EVERY candidate that beats `current`, or None when none does.

    `current` IS A PARAMETER RATHER THAN A DERIVED VALUE, and that is the fix
    for a real defect: this used to return the best swap whether or not it
    improved, so "not None" did not mean "can still improve".  The climb
    compared for itself and was correct, but the GATE asked this function
    whether a local optimum had been reached and got the wrong answer -- it
    failed on the first real run, on a climb that had stopped correctly.  One
    caller compensating for a loose contract is how the next caller gets it
    wrong.

    Scanning all k positions before moving is STEEPEST ascent: first-improvement
    would be k times cheaper per step but takes more steps and lands elsewhere,
    and steepest is what makes a printed step mean "the best move available".
    """
    best = None
    for i in range(len(words)):
        prefix = [int(w) for j, w in enumerate(words) if j != i]
        uns, ssq = last_level_scores(full, cols, M, prefix, ans)
        uns = uns.astype(np.int64)
        big = np.iinfo(np.int32).max
        # A word already in the opening cannot be swapped IN -- that would make
        # a k-1 word opening wearing a k-word name.
        for w in prefix:
            uns[w] = big
        for w in banned_extra:
            uns[int(w)] = big
        c = int(np.lexsort((ssq, uns))[0])
        if uns[c] >= big:
            continue
        cand = (int(uns[c]), int(ssq[c]), i, c)
        if cand[:2] >= tuple(current):
            continue                       # this position offers no improvement
        if best is None or cand[:2] < best[:2]:
            best = cand
    return best


def climb(full, cols, M, words, ans, on_step=None):
    """Swap the best single word until nothing helps.  Returns the local optimum.

    `on_step(step, pos, old, new, uns, ssq)` fires on every accepted swap, which
    is the only thing that happens here worth watching: the scan between them is
    silent and takes seconds.
    """
    words = [int(w) for w in words]
    prefix = words[:-1]
    uns, ssq = last_level_scores(full, cols, M, prefix, ans)
    cur = (int(uns[words[-1]]), int(ssq[words[-1]]))
    step = 0
    while True:
        mv = neighbourhood(full, cols, M, words, ans, cur)
        if mv is None:
            return cur[0], cur[1], words, step
        step += 1
        old = words[mv[2]]
        words[mv[2]] = mv[3]
        cur = mv[:2]
        if on_step:
            on_step(step, mv[2], old, mv[3], cur[0], cur[1])
