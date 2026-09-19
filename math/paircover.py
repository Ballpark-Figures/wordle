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

from guarantee import solved_within, worst_case

_RADIX = 243


def pool_matrix(full, cols):
    """Reply of every pool word against every pool word, (npool, npool)."""
    return np.ascontiguousarray(full[np.ix_(cols, cols)])


def cand_matrix(full, cand_cols, pool_cols):
    """Reply of every CANDIDATE against every POOL word, (ncand, npool).

    THE TWO LISTS HAVE DIFFERENT JOBS AND NEED NOT BE THE SAME (user's call,
    2026-09-18).  The POOL is what the opening partitions and what the random
    fifth guess draws from, so it is what "unsolved" is measured over; the
    CANDIDATES are merely the words the four may be built from, and widening
    them costs nothing in the objective's meaning.  This is the rectangle that
    lets them differ -- rows indexed by candidate, columns by pool word.

    Everything scored against a bucket still goes through the POOL-vs-POOL
    matrix, because a live set is a set of pool words: a candidate outside the
    pool can SPLIT a bucket but can never BE in one.
    """
    return np.ascontiguousarray(full[np.ix_(cand_cols, pool_cols)])


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


def harvest(C, Mpool, chosen, ans_pool_idx, budget):
    """The pairs an opening actually fails on: {(i, j) sorted} -> times seen.

    Buckets the POOL by the opening's joint reply, then walks each bucket that
    holds an answer.  Returns the losing answers as well, so a caller can check
    them against an independently computed unsolved count rather than trusting
    this walk.

    TWO MATRICES, and they are not interchangeable: `C` is candidate-by-pool and
    says how the opening SPLITS the pool, while `Mpool` is pool-by-pool and says
    what the follow-up sees once it is inside a bucket.  The recursion lives
    entirely in the second, since every word of a live set is a pool word.
    """
    key = joint_key(C, chosen)
    order = np.argsort(key, kind="stable")
    skey = key[order]
    pairs, losers = {}, []
    for akey in np.unique(key[ans_pool_idx]):
        lo = int(np.searchsorted(skey, akey, "left"))
        hi = int(np.searchsorted(skey, akey, "right"))
        members = order[lo:hi]
        sub = Mpool[np.ix_(members, members)]
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


# ---------------------------------------------------------------------------
# THE LAST LEVEL, with the prefix hoisted out of the candidate loop.
#
# `greedybuild.score` answers "how many answers does this WHOLE opening leave
# unsolved", from scratch, which is the right shape when the whole opening
# varies.  At the last word it is the wrong shape: the first k-1 words are FIXED,
# so they fix the partition of the pool, and a k-th word only REFINES it.  Doing
# it from scratch rebuilds a 4282-wide unique and argsort per candidate and then
# walks every bucket, almost all of which the k-th word cannot affect.
#
# TWO FACTS DO THE WORK, and both are about buckets the k-th word cannot save or
# spoil:
#
#   A bucket of ONE is solved, trivially.
#
#   A BUCKET OF TWO IS ALSO ALWAYS SOLVED, whatever the k-th word does, and that
#   is the one worth proving rather than assuming.  For `S = {a, x}` the
#   follow-up draws one of them; drawing `a` wins outright, and drawing `x`
#   replies something other than all-green, which eliminates `x` and leaves
#   exactly `{a}` to name.  So `worst_case(S, a) = 2`, inside a budget of 2.
#   Refining such a bucket can only split it into singletons, so it is safe
#   before the k-th word is chosen and safe after.
#
# So only the prefix buckets of size >= 3 that contain an ANSWER are in play, and
# within those only the sub-buckets of size >= 3 the k-th word leaves behind.
# MEASURED on a real 3-word prefix: 386 of 2296 buckets, holding 47% of the pool.
# ---------------------------------------------------------------------------

def prefix_buckets(M, prefix, ans_pool_idx, budget=2):
    """The only buckets a final word can change: bigger than `budget`, with an answer.

    **A BUCKET OF `budget` OR FEWER IS ALWAYS SOLVED**, which generalises the
    bucket-of-two proof above: every wrong draw eliminates at least the word
    drawn, so `worst_case(S, a) <= |S|`, and a set no bigger than the budget is
    finished inside it whatever the last word does.  At `budget == 2` that is
    the "size >= 3" threshold this has always used.

    Returns (members, is_answer) per bucket, with members as POOL indices and
    `is_answer` a boolean over them, computed ONCE for a fixed prefix.
    Everything it leaves out is an answer that is already solved and stays
    solved -- see the proof above -- so the unsolved count is exactly what these
    buckets go on to contribute.
    """
    key = joint_key(M, prefix)
    is_ans = np.zeros(M.shape[1], dtype=bool)
    is_ans[ans_pool_idx] = True
    order = np.argsort(key, kind="stable")
    skey = key[order]
    cuts = np.flatnonzero(np.r_[True, skey[1:] != skey[:-1], True])
    out = []
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        if hi - lo <= budget:
            continue
        members = order[lo:hi]
        flags = is_ans[members]
        if flags.any():
            out.append((members, flags))
    return out


# A bucket bigger than this falls back to the walking form.  The vectorised one
# below is O(s^3) in MEMORY, so it needs a ceiling -- but the ceiling is slack
# by a wide margin: MEASURED over 7799 real sub-buckets the median size is 3,
# the 99th percentile 14 and the maximum 25.
SMALL_BUCKET = 64


# The budget-3 vectorised form is O(s^4) in TIME and O(s^3) in memory, so it
# needs a tighter ceiling than the budget-2 one.  MEASURED on a real 2-word
# prefix the parts needing the predicate have mean size 9.9 and a maximum of
# 136, so almost everything lands well inside this and the tail falls back to
# the recursion.
SMALL_BUCKET3 = 32


def _unsolved3(sub, flags):
    """Budget-3 unsolved count for one part, as array ops rather than recursion.

    THE SAME SHAPE AS THE BUDGET-2 FORM, one ply deeper.  Write `P_g` for the
    words still live after drawing `g` (those replying to `g` as the answer `p`
    does, `p` itself dropped).  Then

        p is UNSOLVED  iff  some draw `g` leaves an `h` in `P_g` whose own
                            reply class inside `P_g` still holds someone else

    and "still holds someone else" is a COUNT OF SHARED MEMBERS, which is a
    matrix product: with `A[g, h] = h is in P_g`, the count for `(g, h)` is
    `(A @ A.T)[g, h]`.  So the whole two-ply question is one einsum over every
    answer at once, instead of a Python recursion per answer.

    Dropping `p` from every `P` is what lets the test be `>= 1` rather than
    `>= 2`: `p` is in every class by construction and is not company.

    `g == p` needs no special case -- drawing the answer wins, and the row for
    it is empty once `p` is dropped, since a word replies all-green only to
    itself.  Gated against `guarantee.solved_within`, which states the rule.
    """
    n = sub.shape[0]
    eq = sub[:, :, None] == sub[:, None, :]      # eq[g, h, p]: h is in P_g(p)
    idx = np.arange(n)
    eq[:, idx, idx] = False                      # drop p itself from every P
    shared = np.einsum("gjp,hjp->ghp", eq, eq)   # |P_g ∩ P_h| , p excluded
    bad = eq & (shared >= 1)
    return int(bad.any(axis=(0, 1))[flags].sum())


def unsolved_in_bucket(sub, flags, budget=2):
    """How many of this bucket's answers are UNSOLVED, in one pass.

    **THE ONE PASS IS THE budget == 2 CASE**: "some other live word leaves
    company behind" is exactly one look-ahead, and no rearrangement of it
    expresses two.  Any other budget goes to `guarantee.worst_case`, so the rule
    lives in one place and the fast path stays a specialisation rather than a
    second definition.  At 2 nothing changed, so every committed quad result is
    reproducible bit for bit.

    `greedybuild.solved_in_bucket` walks the live words and exits as soon as the
    candidate list empties, which is the right shape for a wide bucket.  At the
    last level the buckets are TINY -- median 3 -- so that loop is all numpy call
    overhead, and the whole question fits in one expression instead.

    An answer `p` is unsolved exactly when some other live word `g` can be drawn
    and leave company behind: some `j != p` replies to `g` as `p` does.  So build
    `eq[g, p, j]`, count the company each `(g, p)` leaves, and ask whether any
    `g != p` leaves any.  The `g == p` diagonal is dropped because drawing the
    answer ends the game -- the same exemption `worst_case` makes.
    """
    if budget == 3 and sub.shape[0] <= SMALL_BUCKET3:
        return _unsolved3(sub, flags)
    if budget != 2:
        return sum(1 for p in np.flatnonzero(flags)
                   if not solved_within(sub, int(p), budget))
    eq = sub[:, :, None] == sub[:, None, :]
    bad = (eq.sum(axis=2) - 1) > 0
    np.fill_diagonal(bad, False)
    return int(bad[:, flags].any(axis=0).sum())


def last_level_unsolved(full, cols, buckets, row, budget=2):
    """Unsolved answers for one final word, given the prefix's live buckets.

    `row` is that word's reply against every pool word.  Each live bucket is
    split by it and only the parts still holding three or more words can leave
    an answer unsolved.
    """
    uns = 0
    for members, flags in buckets:
        rep = row[members]
        o = np.argsort(rep, kind="stable")
        srep = rep[o]
        cuts = np.flatnonzero(np.r_[True, srep[1:] != srep[:-1], True])
        for lo, hi in zip(cuts[:-1], cuts[1:]):
            if hi - lo <= budget:
                continue                  # no bigger than the budget: solved
            loc = o[lo:hi]
            fl = flags[loc]
            if not fl.any():
                continue                  # no answer here, so nothing to lose
            sub_idx = cols[members[loc]]
            sub = full[np.ix_(sub_idx, sub_idx)]
            if hi - lo <= SMALL_BUCKET:
                uns += unsolved_in_bucket(sub, fl, budget)
            else:
                from greedybuild import solved_in_bucket
                apos = list(np.flatnonzero(fl))
                uns += len(apos) - len(solved_in_bucket(full, cols,
                                                        members[loc], apos,
                                                        budget))
    return uns


def _parts(rep):
    """Local index groups of equal reply, as a list of arrays."""
    o = np.argsort(rep, kind="stable")
    s = rep[o]
    cuts = np.flatnonzero(np.r_[True, s[1:] != s[:-1], True])
    return [o[lo:hi] for lo, hi in zip(cuts[:-1], cuts[1:])]


def _partition_key(blk):
    """Group candidates by the PARTITION they induce, not by their replies.

    THIS IS THE WHOLE SAVING, and grouping by reply values instead throws most
    of it away.  What a final word does to a bucket is decided entirely by which
    members it puts TOGETHER -- the actual pattern codes are labels.  A bucket of
    three therefore has only FIVE possible outcomes however many candidates
    there are (Bell(3)), and a bucket of four fifteen, so thousands of
    candidates collapse onto a handful of cases each priced once.

    The key packs one bit per member PAIR -- equal or not -- which determines the
    partition exactly.  That is s(s-1)/2 bits, so it is exact up to s = 11 and
    the caller falls back to the raw rows above that.
    """
    nc, s = blk.shape
    key = np.zeros(nc, dtype=np.int64)
    bit = 0
    for i in range(s):
        for j in range(i + 1, s):
            key |= (blk[:, i] == blk[:, j]).astype(np.int64) << bit
            bit += 1
    uniq, inv = np.unique(key, return_inverse=True)
    # One representative per class, found by sorting rather than by scanning the
    # candidates: a Python walk over the pool here would cost more than the
    # pricing it exists to avoid.
    order = np.argsort(inv, kind="stable")
    si = inv[order]
    first = order[np.flatnonzero(np.r_[True, si[1:] != si[:-1]])]
    return blk[first], inv


PAIRBIT_MAX = 11        # s(s-1)/2 bits must fit an int64 sign-free


def _rep_rows(blk):
    """(one representative row per distinct partition, inverse index)."""
    if blk.shape[1] <= PAIRBIT_MAX:
        return _partition_key(blk)
    blk = np.ascontiguousarray(blk)
    v = blk.view(np.dtype((np.void, blk.dtype.itemsize * blk.shape[1]))).ravel()
    uniq, inv = np.unique(v, return_inverse=True)
    return uniq.view(blk.dtype).reshape(len(uniq), blk.shape[1]), inv


def last_level_scores(full, cols, M, prefix, ans_pool_idx, budget=2):
    """(unsolved, ssq) for EVERY candidate as the final word, in one pass.

    THIS IS THE WHOLE LAST LEVEL AT ONCE, and it is what makes ranking the final
    word by the REAL objective affordable instead of shortlisting on a proxy
    first.  Evaluating candidates one at a time costs ~5 ms each -- 21 s for the
    pool -- and almost all of that is numpy call overhead from re-walking the
    same few hundred buckets per candidate.

    The saving is that a candidate only matters through the PARTITION it induces
    on a bucket, and a bucket of three has very few distinct partitions however
    many words there are.  So each bucket groups the candidates by the partition
    they induce (`_row_key`), prices each distinct one ONCE, and scatters the
    result back.  Buckets of one and two need no partitioning at all: their
    answers are solved whatever comes (see the proof above), and their ssq
    contribution is a single vectorised comparison.
    """
    nc = M.shape[0]
    key = joint_key(M, prefix)
    is_ans = np.zeros(M.shape[1], dtype=bool)
    is_ans[ans_pool_idx] = True
    order = np.argsort(key, kind="stable")
    skey = key[order]
    cuts = np.flatnonzero(np.r_[True, skey[1:] != skey[:-1], True])

    uns = np.zeros(nc, dtype=np.int32)
    ssq = np.zeros(nc, dtype=np.int64)
    singles = 0
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        members = order[lo:hi]
        n = hi - lo
        if n == 1:
            singles += 1
            continue
        if n == 2:
            # Sound at EVERY budget >= 2, not just 2: one and two are solved
            # under any of them, so only the ssq contribution is owed.
            same = M[:, members[0]] == M[:, members[1]]
            ssq += np.where(same, 4, 2)
            continue
        rows, inv = _rep_rows(M[:, members])
        flags = is_ans[members]
        sub = full[np.ix_(cols[members], cols[members])]
        cu = np.empty(len(rows), dtype=np.int32)
        cs = np.empty(len(rows), dtype=np.int64)
        for r, rep in enumerate(rows):
            u = s2 = 0
            for loc in _parts(rep):
                s2 += len(loc) * len(loc)
                if len(loc) <= budget:
                    continue           # no bigger than the budget: solved
                fl = flags[loc]
                if fl.any():
                    u += unsolved_in_bucket(sub[np.ix_(loc, loc)], fl, budget)
            cu[r], cs[r] = u, s2
        uns += cu[inv]
        ssq += cs[inv]
    return uns, ssq + singles
