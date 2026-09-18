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


# ---------------------------------------------------------------------------
# PAIR MOVES: swap TWO words at once for two whose letters are the same, or
# nearly.  (The user's, 2026-09-18.)
#
# WHY A PAIR MOVE IS WORTH HAVING AT ALL.  A one-word climb stops where no
# SINGLE swap helps, and the failures that survive are near-anagram families --
# `odder/order/rodeo`, `brags/grabs/grass/grays`.  Separating those often needs
# two words to change TOGETHER, which is exactly the move a one-word
# neighbourhood cannot make.  Restricting the pair's replacement to the same
# LETTERS keeps the neighbourhood small enough to enumerate while changing
# precisely what a single swap cannot: where those letters sit.
#
# THE LETTERS ARE A MULTISET, not a set -- `grass` is two s's and it matters --
# so everything below counts them.
# ---------------------------------------------------------------------------

def letter_counts(words):
    """(n, 26) counts, one row per word."""
    C = np.zeros((len(words), 26), dtype=np.int16)
    for i, w in enumerate(words):
        for ch in w:
            C[i, ord(ch) - 97] += 1
    return C


def anagram_index(C):
    """signature -> the candidates having exactly those letters."""
    by = {}
    for i in range(C.shape[0]):
        by.setdefault(C[i].tobytes(), []).append(i)
    return by


def splits_of(C, by_sig, target):
    """Every unordered candidate pair whose letters total exactly `target`.

    The subset test is VECTORISED over all candidates at once -- `target` is a
    (26,) vector and `C <= target` is one pass -- because the alternative, a
    Python loop per target, is what makes the within-one-letter neighbourhood
    (up to 260 targets per position pair) unaffordable.
    """
    out = []
    ok = np.flatnonzero((C <= target).all(axis=1))
    for x in ok:
        comp = (target - C[x]).tobytes()
        for y in by_sig.get(comp, ()):
            if int(y) > int(x):
                out.append((int(x), int(y)))
    return out


def near_targets(target, within):
    """`target`, and every multiset one substitution away from it.

    `within=0` is the exact anagram neighbourhood; `within=1` also allows one
    letter to be traded for another, which is the second, wider section.
    """
    seen = {target.tobytes(): target}
    if within >= 1:
        for c in np.flatnonzero(target > 0):
            for d in range(26):
                if d == c:
                    continue
                t = target.copy()
                t[c] -= 1
                t[d] += 1
                seen.setdefault(t.tobytes(), t)
    return list(seen.values())


def pair_moves(C, by_sig, words, within):
    """Every (i, j, x, y): replace positions i and j with candidates x and y.

    Excludes anything that would repeat a word already in the opening, and the
    identity -- putting the same two words back is not a move.
    """
    k = len(words)
    cur = set(int(w) for w in words)
    out = []
    for i in range(k):
        for j in range(i + 1, k):
            keep = cur - {int(words[i]), int(words[j])}
            target = C[words[i]] + C[words[j]]
            for t in near_targets(target, within):
                for x, y in splits_of(C, by_sig, t):
                    if {x, y} == {int(words[i]), int(words[j])}:
                        continue
                    if x in keep or y in keep:
                        continue
                    out.append((i, j, x, y))
    return out


def climb_pairs(score_fn, words, C, by_sig, within, current, on_step=None):
    """Swap the best PAIR until nothing helps.  Steepest, as the one-word climb.

    `score_fn(words) -> (unsolved, ssq)` is passed in rather than rebuilt here,
    so this never grows a second copy of the objective.
    """
    words = [int(w) for w in words]
    cur = tuple(current)
    step = 0
    while True:
        best = None
        for i, j, x, y in pair_moves(C, by_sig, words, within):
            trial = list(words)
            trial[i], trial[j] = x, y
            val = score_fn(trial)
            if val < cur and (best is None or val < best[0]):
                best = (val, i, j, x, y)
        if best is None:
            return cur[0], cur[1], words, step
        step += 1
        val, i, j, x, y = best
        old = (words[i], words[j])
        words[i], words[j] = x, y
        cur = val
        if on_step:
            on_step(step, old, (x, y), cur[0], cur[1])
