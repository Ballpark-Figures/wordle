"""EXACT expected guesses and EXACT win probability for a BLIND multi-word
opening followed by a random-compatible tail.  No sampling, no seed.

THE STRATEGY, and it is the one `wordlesim` measures.  A fixed opening of k
words is played BLIND in order -- every word goes down whatever the board shows
-- except that a game whose answer IS an opening word ends the moment that word
is played.  From guess k+1 a follow-up draws UNIFORMLY from the pool words still
CONSISTENT with every reply so far, until the answer is played.  `run-wordle-
race.sh --fallback answer` estimates the two numbers below by Monte Carlo; this
computes them, so a re-run reproduces the file byte for byte.

TWO QUANTITIES, AND THEY TREAT THE CAP DIFFERENTLY.  That is not an
inconsistency, it is what the two words mean in this repo:

  * `mean` is expected guesses OUTRIGHT.  Play is never truncated -- a game
    that misses at six keeps going -- so no cap enters it at all, and it sits
    with `wordlesim`/`multiwordle`/`foximax` and NEVER beside an optturns-family
    total, every one of which is an optimum subject to a 6-guess guarantee.
  * `win_rate` is the fraction of those untruncated scores at `cap` or fewer.
    The cap is a REPORTING THRESHOLD on the same play, not a rule the strategy
    obeys, exactly as `--win-within` is for the simulation.

THE TWO RECURSIONS.  Write S for a live set of pool words and let a uniform draw
from S be the follow-up's move.  A word's reply against itself is all-green and
against anything else is not, so a draw always eliminates at least the word
drawn and both recursions terminate.

    T(S)    = |S| + (1/|S|) * sum over g in S of sum over parts P of S\\{g} of T(P)

      total guesses summed over the answers in S.  UNCAPPED, so it recurses
      until every branch bottoms out at a singleton.  This is `ladder.tail_total`
      -- which is the exact-rational ORACLE for it -- and the same recursion
      `solver/secondexact.c` sums in double precision.

    L(S, b) = |S|                                             if b == 0
            = 0                                               if |S| <= b
            = (1/|S|) * sum over g of sum over parts P of L(P, b-1)

      the expected number of answers in S NOT found within b further guesses.
      The drawn word contributes 0 -- it is found on that guess.

WHY `win_rate` IS THE CHEAPER OF THE TWO, which is the opposite of what the
extra index suggests.  L carries a BUDGET in its memo key where T does not, so
its state space is nominally bigger -- but the budget also TRUNCATES it: after a
k-word opening the tail has `cap - k` guesses, so L is at most that many levels
deep and `|S| <= b` closes whole subtrees outright.  T has no such floor and
must walk every branch down to a singleton.  So at k = 4 or 5 both are trivial,
while at k = 1 the buckets run past 200 words and T is the expensive one.  The
same asymmetry `guarantee.solved_within` documents against `worst_case`.

`|S| <= b` IS A BOUND, NOT A GUESS: every wrong draw eliminates at least the
word drawn, so a set no bigger than the budget is always finished inside it.

THE POOL IS PART OF THE QUESTION and is not defaulted here.  Under `answer` the
follow-up draws from the 2315 mystery words, under `guess` from the 12972 legal
ones and under `custom` from custom.txt -- three different players, three
different numbers.  The hidden answer is drawn from the 2315 whichever pool is
in play, which is what makes the three comparable with each other.

AN OPENING WORD IS ALWAYS ALONE IN ITS BUCKET, which is why the "the answer was
an opening word" case needs no special handling in the recursions: w replies
all-green to itself and non-all-green to every other answer, so its joint key is
shared with nothing.  Its game costs the POSITION of that word in the opening.
"""

import numpy as np

_RADIX = 243


def joint_key(rows):
    """Fold the opening's replies into one int64 key per pool word.

    `rows` is (k, npool): the reply of each opening word against every pool
    word.  THE OPENING WORDS ARE GUESSES, NOT POOL WORDS, and need not be in the
    pool at all -- `clint`, `horst` and `sowed` are guess-only words that lead
    real openings here -- so they index the candidate side of the rectangle,
    never the pool side.  A live set is still a set of POOL words: a guess-only
    word can SPLIT a bucket but can never BE in one (`paircover.cand_matrix`
    makes the same split for the same reason).

    Base-243 per word, as `guarantee.joint_keys` does it: 5 tiles fit in 243
    values, and k of them in 243**k -- 14.3 billion at k = 5, past float64's
    exact range but comfortably inside int64, which is what these are.
    """
    key = np.zeros(rows.shape[1], dtype=np.int64)
    for r in rows:
        key = key * _RADIX + r
    return key


def _parts(sub, gi, idx):
    """The parts a draw of `idx[gi]` splits the rest of `idx` into.

    Yields index arrays into the POOL, each still sorted, so a part is a valid
    memo key in its own right without re-sorting.
    """
    n = len(idx)
    row = sub[gi]
    keep = np.arange(n) != gi
    vals, members = row[keep], idx[keep]
    order = np.argsort(vals, kind="stable")
    vals, members = vals[order], members[order]
    cuts = np.flatnonzero(np.diff(vals)) + 1
    for part in np.split(members, cuts):
        yield np.sort(part)


def tail_total(M, idx, memo):
    """T(S): total guesses over the answers in S, for a live set `idx`.

    `M` is the pool-vs-pool reply matrix and `idx` a SORTED array of pool
    indices, so `idx.tobytes()` is a canonical key for the set and two paths
    reaching the same live set share one entry.  Double precision, matching
    `secondexact.c`; `ladder.tail_total` is the exact-rational oracle the gate
    diffs this against.
    """
    n = len(idx)
    if n <= 1:
        return float(n)
    key = idx.tobytes()
    hit = memo.get(key)
    if hit is not None:
        return hit
    sub = M[np.ix_(idx, idx)]
    tot = float(n)
    for gi in range(n):
        for part in _parts(sub, gi, idx):
            tot += tail_total(M, part, memo) / n
    memo[key] = tot
    return tot


def tail_lost(M, idx, budget, memo):
    """L(S, b): expected answers in `idx` NOT found within `budget` guesses.

    The budget rides in the memo key, because a live set reached with two
    guesses left is a different question from the same set with three.
    """
    n = len(idx)
    if budget <= 0:
        return float(n)
    if n <= budget:
        return 0.0                      # every wrong draw eliminates one word
    key = (idx.tobytes(), budget)
    hit = memo.get(key)
    if hit is not None:
        return hit
    sub = M[np.ix_(idx, idx)]
    tot = 0.0
    for gi in range(n):
        for part in _parts(sub, gi, idx):
            tot += tail_lost(M, part, budget - 1, memo) / n
    memo[key] = tot
    return tot


def evaluate(M, rows, at_pool, ans_pool_idx, cap=6, memo=None, lost_memo=None):
    """Exact (mean guesses, win rate) for one blind opening.

    `M`            pool-vs-pool reply matrix -- what the tail sees inside a bucket.
    `rows`         (k, npool) replies of the opening's words, in PLAY ORDER.
    `at_pool`      per opening word, its pool index, or -1 for a guess-only word
                   that can never be the answer.
    `ans_pool_idx` each of the 2315 answers as a pool index.

    Returns a dict; `total` and `lost` are the raw sums the two numbers divide.
    A repeated word is charged at its FIRST position, matching a game that ends
    the moment the answer is played.
    """
    memo = {} if memo is None else memo
    lost_memo = {} if lost_memo is None else lost_memo
    k = len(rows)
    budget = cap - k

    key = joint_key(rows)
    uniq, inv = np.unique(key[ans_pool_idx], return_inverse=True)

    # An answer that IS an opening word ends its game at that word's position.
    first_at = {}
    for pos, c in enumerate(at_pool, start=1):
        if c >= 0:
            first_at.setdefault(int(c), pos)

    total, lost, n_ans = 0.0, 0.0, len(ans_pool_idx)
    for u in range(len(uniq)):
        members = ans_pool_idx[inv == u]
        if len(members) == 1 and int(members[0]) in first_at:
            total += first_at[int(members[0])]   # never a loss: pos <= k <= cap
            continue
        live = np.sort(members)
        total += k * len(live) + tail_total(M, live, memo)
        if budget < len(live):                   # else provably all found
            lost += tail_lost(M, live, budget, lost_memo)
    return {"mean": total / n_ans, "win_rate": 1.0 - lost / n_ans,
            "total": total, "lost": lost, "answers": n_ans,
            "buckets": len(uniq), "budget": budget}


# ---------------------------------------------------------------------------
# THE WHOLE LAST LEVEL AT ONCE -- what makes this usable as a HILL-CLIMB
# objective rather than only as a way to price one opening.
#
# `evaluate` answers about ONE opening.  A swap scan asks about every candidate
# in every position, so it needs the same question answered for the whole pool
# in one pass -- the shape `paircover.last_level_scores` already has for the
# guarantee objective, and for the same two reasons:
#
#   * THE PREFIX IS FIXED, SO ITS BUCKETS ARE.  A final word only REFINES the
#     partition the first k-1 words made, so each prefix bucket can be priced on
#     its own and the results summed.
#   * CANDIDATES GROUP BY THE PARTITION THEY INDUCE, not by their replies.  The
#     pattern codes are labels; what matters is which members a word puts
#     together, so a bucket of three has five possible outcomes however many
#     candidates exist.  `_rep_rows` is that collapse and it is shared.
#
# WHERE THIS DIFFERS FROM THE GUARANTEE PASS, and it is the one real difference:
# **a bucket of TWO is not constant here.**  There, one and two are solved
# whatever the last word does, so only their ssq was owed.  For the mean a
# two-bucket costs T = 3 left whole and 2 when split, so the last word is worth
# exactly one guess on it and the bucket has to be priced.  Buckets of ONE stay
# constant (T = 1).
# ---------------------------------------------------------------------------

SCALE = 10 ** 4
"""Fixed-point units for the climb's primary key -- see `mean_objective`."""


def last_level_mean(Mpool, M, prefix, ans_pool_idx, k, cand_to_pool, memo=None):
    """(total guesses x SCALE, ssq) for EVERY candidate as the k-th word.

    `Mpool` is pool-vs-pool (what a live set is made of, and what `tail_total`
    walks); `M` is candidate-vs-pool (how a candidate SPLITS, and a candidate
    need not be a pool word).  `cand_to_pool` maps each candidate to its pool
    index or -1 -- the one thing the guarantee pass does not need and this one
    does, because an opening word that IS an answer is found by playing it.

    The returned total is the WHOLE opening's, constant terms included, so it is
    directly comparable with `evaluate`'s -- which is what makes the climb's
    own `current` assertion a free differential between the two paths.
    """
    from paircover import _parts, _rep_rows          # local: avoids a cycle

    memo = {} if memo is None else memo
    nc = M.shape[0]
    rows = M[list(prefix)] if len(prefix) else M[:0]
    key = joint_key(rows)
    order = np.argsort(key, kind="stable")
    skey = key[order]
    cuts = np.flatnonzero(np.r_[True, skey[1:] != skey[:-1], True])

    # An opening word that is a pool word is ALONE in its prefix bucket (it
    # replies all-green to itself and to nothing else), and its game ended when
    # it was played -- so that bucket costs its POSITION and nothing the last
    # word does can touch it.
    at_pos = {}
    for pos, c in enumerate(prefix, start=1):
        p = int(cand_to_pool[c])
        if p >= 0:
            at_pos.setdefault(p, pos)

    const = 0.0
    var = np.zeros(nc, dtype=np.float64)
    ssq = np.zeros(nc, dtype=np.int64)
    eligible = np.zeros(Mpool.shape[0], dtype=bool)
    for lo, hi in zip(cuts[:-1], cuts[1:]):
        members = order[lo:hi]
        n = hi - lo
        if n == 1 and int(members[0]) in at_pos:
            const += at_pos[int(members[0])]
            ssq += 1
            continue
        eligible[members] = True
        const += k * n                     # every answer here plays all k words
        if n == 1:
            const += 1.0                   # T({x}) = 1, whatever the last word
            ssq += 1
            continue
        if n == 2:
            same = M[:, members[0]] == M[:, members[1]]
            var += np.where(same, 3.0, 2.0)
            ssq += np.where(same, 4, 2)
            continue
        reps, inv = _rep_rows(M[:, members])
        cv = np.empty(len(reps), dtype=np.float64)
        cs = np.empty(len(reps), dtype=np.int64)
        for r, rep in enumerate(reps):
            t = 0.0
            s2 = 0
            for loc in _parts(rep):
                s2 += len(loc) * len(loc)
                t += tail_total(Mpool, np.sort(members[loc]), memo)
            cv[r], cs[r] = t, s2
        var += cv[inv]
        ssq += cs[inv]

    # A CANDIDATE THAT IS ITSELF A LIVE ANSWER IS FOUND BY PLAYING IT, so it
    # costs k rather than k + T({c}) = k + 1.  It is alone in its sub-bucket for
    # the same reason a prefix word is, so the correction is exactly one guess.
    live = (cand_to_pool >= 0)
    live[live] &= eligible[cand_to_pool[live]]
    var -= live

    return np.rint((const + var) * SCALE).astype(np.int64), ssq


# ---------------------------------------------------------------------------
# THE LADDER -- the same two quantities for a CONDITIONAL opening.
#
# Everything above prices a BLIND opening: k words go down whatever the board
# shows, so their replies fold into one joint key and a bucket is reached one
# way.  A LADDER (`math/ladder.py`, `solver/secondexact.c --ladder N`) plays its
# d-th committed word only while `matched < T_d`, so which words a game sees
# depends on its replies and there is no single joint key -- it needs an
# explicit walk.  What does NOT change is anything below the handoff: the tail
# is the same uniform draw from the consistent ANSWERS, so `tail_total` and
# `tail_lost` are reused exactly as `evaluate` uses them, and `mean` and
# `win_rate` mean precisely what they mean above.  That is why this lives here
# rather than in a module of its own.
#
# `ladder.py` is the source of truth for the rule and the exact-rational oracle
# (`ladder_total`, `ladder_lost`); this is the fast path the gate diffs it
# against.  `matched_letters` is IMPORTED from it rather than restated -- the
# independent implementations of that key are the C's and `tree_states`', which
# `checkladder.check_matched` already diffs all three ways.
# ---------------------------------------------------------------------------


def _split_row(row, live):
    """(reply code, members) per distinct reply of one word over `live`.

    `live` is a sorted array of pool indices and each part comes back sorted, so
    a part is a valid `tail_total` / `tail_lost` memo key in its own right.
    """
    vals = row[live]
    order = np.argsort(vals, kind="stable")
    v, m = vals[order], live[order]
    cuts = np.flatnonzero(np.diff(v)) + 1
    for seg_v, seg_m in zip(np.split(v, cuts), np.split(m, cuts)):
        yield int(seg_v[0]), np.sort(seg_m)


def evaluate_ladder(M, crows, words, thresholds, ans_pool_idx, cap=6,
                    memo=None, lost_memo=None):
    """Exact (mean guesses, win rate) for one committed-word ladder.

    `M`            pool-vs-pool reply matrix -- what the tail sees in a bucket.
    `crows`        (len(words), npool) replies of each committed word against
                   every pool word, in PLAY ORDER.  THEY ARE GUESSES, NOT POOL
                   WORDS: `trine` leads the best ladder here and is not an
                   answer, so they index the candidate side of the rectangle.
    `words`        the committed words themselves, opener first, already
                   TRUNCATED at the first declined level -- a rung with no word
                   ends the ladder, so it is simply absent.
    `thresholds`   `T_2 .. T_N`, one shorter than `words`: word `d` is played
                   only while the cumulative matched count is below `T_d`.
    `ans_pool_idx` each answer as a pool index.

    Returns a dict shaped like `evaluate`'s.  `total` and `lost` are the raw
    sums the two numbers divide, so a caller can add runs up.
    """
    from ladder import matched_letters                  # local: the reference
    from wordle import ALL_GREEN, decode

    if len(thresholds) != len(words) - 1:
        raise ValueError("a ladder of %d words has %d thresholds, not %d"
                         % (len(words), len(words) - 1, len(thresholds)))
    memo = {} if memo is None else memo
    lost_memo = {} if lost_memo is None else lost_memo

    state = {"total": 0.0, "lost": 0.0, "leaves": 0, "won": 0, "deepest": 1}

    def handoff(live, played):
        """The ladder is over for `live`; the random tail runs from here."""
        state["leaves"] += 1
        state["total"] += tail_total(M, live, memo)
        budget = cap - played
        if budget < len(live):              # else provably all found in time
            state["lost"] += tail_lost(M, live, budget, lost_memo)

    def walk(live, played, hist_w, hist_t):
        if len(live) == 0:
            return
        state["deepest"] = max(state["deepest"], played)
        if played >= len(words):
            handoff(live, played)
            return
        # Constant across `live` -- it reads the REPLIES, never the answer --
        # so the whole set fires or the whole set leaves.
        if matched_letters(hist_w, hist_t) >= thresholds[played - 1]:
            handoff(live, played)
            return
        state["total"] += len(live)         # this committed word, once per answer
        w, row = words[played], crows[played]
        for code, part in _split_row(row, live):
            if code == ALL_GREEN:
                # w WAS the answer: the game ended on the guess just charged.
                # It is alone in its part, and never a loss while the ladder is
                # no longer than the cap -- asserted by the caller.
                state["won"] += len(part)
                continue
            walk(part, played + 1, hist_w + [w], hist_t + [decode(code)])

    n_ans = len(ans_pool_idx)
    state["total"] += n_ans                 # the opener, once per answer
    for code, part in _split_row(crows[0], np.sort(ans_pool_idx)):
        if code == ALL_GREEN:
            state["won"] += len(part)
            continue
        walk(part, 1, [words[0]], [decode(code)])

    return {"mean": state["total"] / n_ans,
            "win_rate": 1.0 - state["lost"] / n_ans,
            "total": state["total"], "lost": state["lost"], "answers": n_ans,
            "leaves": state["leaves"], "won_outright": state["won"],
            "deepest": state["deepest"], "cap": cap}
