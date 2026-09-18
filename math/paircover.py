"""Build an opening by COVERING the pairs the follow-up cannot separate.

THE CONSTRUCTION (the user's, 2026-09-18).  Carry a set of PAIRS of words that
are hard to tell apart, each with a WEIGHT.  Choose an opening word by the
weighted number of those pairs it SPLITS; delete the pairs it split; choose the
next word by how many of the REMAINING pairs it splits; repeat to `--words`.
Score the finished opening by the REAL objective -- how many answers are left
UNSOLVED -- then harvest the pairs it actually failed on, fold them back into the
set, and go round again.

IT IS CONSTRAINT GENERATION, not a ranking.  The pair set is the hard
constraints discovered so far; each round adds the ones the last opening
violated, and the weight is how many rounds a pair has survived unsplit.  So the
search is steered by its own failures rather than by a fixed screen, which is
what no opener-side ranking can do.

TWO OBJECTIVES, AND ONLY THE SECOND IS THE ANSWER.  Coverage picks the WORDS;
`unsolved` ranks the finished openings.  Never quote a coverage score as a
result -- see the proxy note below for exactly how much it is not one.

  COVERAGE IS SUFFICIENT BUT NOT NECESSARY, which is the proxy's one real
  imprecision.  A bucket holding exactly TWO words is SAFE: the follow-up draws
  one, and if it is wrong the reply leaves exactly one word for the last guess.
  The damage starts at THREE, where a drawn word can fail to separate the other
  two.  So splitting a pair always helps and is sometimes unnecessary, and the
  seeded "hardest pairs" over-demand.  The pairs HARVESTED from real failures
  carry no such slack -- they are exactly the sets that ran out of budget with
  company -- which is why the loop converges on the right constraints even
  though it starts from a heuristic.

A HARVESTED PAIR IS (ANSWER, POOL WORD), not (answer, answer).  The words still
standing beside a losing answer come from the whole follow-up pool, and one that
could never BE the answer is still a way to lose: the follow-up can spend its
last guess on it.  The seed is answer-by-answer, which sits inside that space,
so the two compose without a conversion.

THE PRECISE FAILURE, and why it is not the whole bucket.  An answer `a` is
unsolved when some live word `g` in its bucket leaves two or more words alive
after it is played.  The pairs recorded are `(a, x)` for the `x` STILL STANDING
at the moment the budget runs out -- unioned over every `g` that witnesses a
failure -- and NOT every other member of the bucket, most of which the opening
did separate.  Recording the bucket whole would fill the set with pairs that are
not failures and steer the next round at them.
"""

import numpy as np

from guarantee import worst_case

_RADIX = 243


def pool_matrix(full, cols):
    """Reply of every pool word against every pool word, (npool, npool)."""
    return np.ascontiguousarray(full[np.ix_(cols, cols)])


def split_matrix(M, ia, ib):
    """`S[c, p]` -- does pool word c separate pair p?

    Two words are separated by c exactly when c replies differently to them, so
    this is one comparison of two COLUMNS of the pool matrix.  No bucketing and
    no enumeration of patterns.
    """
    return M[:, ia] != M[:, ib]


def joint_key(M, chosen):
    """Fold the chosen words' replies into one key per pool word."""
    key = np.zeros(M.shape[1], dtype=np.int64)
    for c in chosen:
        key = key * _RADIX + M[c]
    return key


def ssq_of(key):
    """Sum of squared bucket sizes for a joint key -- the repo's tie-break."""
    _, inv = np.unique(key, return_inverse=True)
    sizes = np.bincount(inv)
    return int((sizes.astype(np.int64) ** 2).sum())


def failing_sets(sub, idx, pos, budget, out):
    """Every set that still holds the answer AND company when the budget ends.

    `sub` is the live set's own reply sub-matrix, `idx` the pool indices of its
    rows, `pos` the answer's position in it, `budget` the guesses left.  A line
    LOSES when it needs more than `budget`, so this walks exactly the losing
    lines and records the set standing at the end of each -- which is the set
    the follow-up must then gamble inside.

    Mirrors `guarantee.worst_case`'s recursion (`L(S,a) = 1 + max over g of
    L(S|g,a)`), consulting it to decide which branches actually lose, so the two
    cannot disagree about what a failure is.
    """
    n = len(idx)
    if n == 1:
        if budget < 1:
            out.append(idx)
        return
    if budget <= 1:
        # Two or more words and at most one guess: naming one is a gamble, and
        # every word here is one the answer could be confused with.
        out.append(idx)
        return
    for g in range(n):
        if g == pos:
            continue                      # drawing the answer ends it; see worst_case
        keep = np.flatnonzero(sub[g] == sub[g][pos])
        s2 = sub[np.ix_(keep, keep)]
        p = int(np.searchsorted(keep, pos))
        if worst_case(s2, p) > budget - 1:
            failing_sets(s2, idx[keep], p, budget - 1, out)


def harvest(M, chosen, ans_pool_idx, budget):
    """The pairs an opening actually fails on: {(i, j) sorted} -> times seen.

    Buckets the POOL by the opening's joint reply, then walks each bucket that
    holds an answer.  Returns the losing answers as well, so a caller can check
    them against an independently computed unsolved count rather than trusting
    this walk.
    """
    key = joint_key(M, chosen)
    order = np.argsort(key, kind="stable")
    skey = key[order]
    pairs, losers = {}, []
    for akey in np.unique(key[ans_pool_idx]):
        lo = int(np.searchsorted(skey, akey, "left"))
        hi = int(np.searchsorted(skey, akey, "right"))
        members = order[lo:hi]
        sub = M[np.ix_(members, members)]
        where = {int(m): p for p, m in enumerate(members)}
        for a in ans_pool_idx[key[ans_pool_idx] == akey]:
            pos = where[int(a)]
            out = []
            failing_sets(sub, members, pos, budget, out)
            if not out:
                continue
            losers.append(int(a))
            for term in out:
                for x in term:
                    if int(x) == int(a):
                        continue
                    kp = (int(a), int(x)) if a < x else (int(x), int(a))
                    pairs[kp] = pairs.get(kp, 0) + 1
    return pairs, losers


def cover_scores(S, weights, alive, banned):
    """Weighted pairs each candidate would split, over the pairs still alive."""
    if not alive.any():
        return np.zeros(S.shape[0], dtype=np.int64)
    sc = S[:, alive].astype(np.int64) @ weights[alive]
    sc[banned] = -1
    return sc
