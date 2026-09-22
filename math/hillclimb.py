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

SECTIONS, AND THE LOOP (the user's, 2026-09-18).  Single-word swaps run to
exhaustion; then PAIR swaps for two words with the same letters; then pair swaps
for two words within ONE LETTER of the same letters; then TRIPLE swaps for three
words with the same letters.  Each widens the neighbourhood, so each can only
move where the one before it is stuck.  Then it STARTS OVER AT THE FIRST SECTION
and keeps cycling until a WHOLE PASS through every section moves nothing.

  THE TRIPLE SECTION IS CHEAPER THAN THE PAIR-WITHIN-ONE ONE, which is not the
  order of the names.  MEASURED on custom (4282 candidates), per scan: 372-2160
  triple-exact moves against 1680-5775 pair-within-one, so 1.6-9.4 s against
  7.3-25 s at 4.3 ms a score.  Enumeration is 0.02-0.04 s either way -- a
  section costs what it SCORES.  Note triple-exact CONTAINS pair-exact (leave
  one of the three unchanged), so that section is redundant once this exists;
  it stays because at 9-44 moves it is free and it fires first.

  THE LOOP IS NOT TIDINESS, IT IS THE POINT: a pair move REOPENS single-word
  swaps.  Measured on a real trial, a climb that ran the three sections once
  stopped at `payed tombs flung wreck` with 11 unsolved -- and a single swap,
  `payed` to `vapid`, took it to 10.  Running each section once leaves that on
  the table by construction.

IT IS A LOCAL OPTIMUM, NOT AN OPTIMUM, and the distinction is the whole claim.
The loop stops where no move of ANY of the three kinds helps; three words might
have to change together to get past it, and nothing here tries that.  So a
result is "the best of `--trials` random starts, each climbed to where these
neighbourhoods run out" -- never "the best opening".  The restarts are the only
thing exploring; every climb is greedy and deterministic given its start.

THE OBJECTIVE IS THE GUARANTEE CONDITION, the same number `greedybuild`,
`paircover` and `guarantee_sweep` all compute: how many of the 2315 answers can
be made to lose, with the follow-up drawing from the pool.  Ties break on ssq,
the repo's standing second key.

TWO LISTS, AS EVERYWHERE HERE.  The POOL is what the opening partitions and what
the random tail draws from, so it is what `unsolved` counts over and it must
hold every answer.  The CANDIDATES are only what the k words may be drawn from,
and need not contain the answers.

THE BUDGET IS `cap - words`, NOT 2, and that is the whole difference between a
quad and a triple.  Four blind words in a six-guess game leave TWO, which is the
case every fast path here was written for; three blind words leave THREE, and
"solved" then means `worst_case(S, a) <= 3` rather than the one-look-ahead form.
It is threaded from the caller rather than assumed, and `guarantee.worst_case`
states the rule for any budget -- the one-pass predicates stay as the budget-2
specialisation, so every quad result is reproducible bit for bit.
"""

import itertools

import numpy as np

from openexact import (SCALE, evaluate, joint_key,   # the exact objective
                       last_level_mean)
from paircover import (last_level_scores,   # the two slot-scorers; see above
                       last_level_singles, singles_of)


def neighbourhood(last_level, words, current, banned_extra=()):
    """The best IMPROVING single-word swap, or None if this is a local optimum.

    Returns `(primary, secondary, position, candidate)` for the best swap over
    EVERY position and EVERY candidate that beats `current`, or None when none
    does.

    **`last_level(prefix)` IS THE OBJECTIVE, injected rather than hardcoded**:
    it returns two arrays over the candidates, both MINIMISED lexicographically.
    The guarantee objective passes `(unsolved, ssq)`; the singleton one passes
    `(-singles, ssq)`, since more singles is better and the climb only knows how
    to go down.  Nothing else here knows which is running, which is what keeps
    one climb rather than two.

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
        pri, sec = last_level(prefix)
        pri = pri.astype(np.int64)
        big = np.iinfo(np.int32).max
        # A word already in the opening cannot be swapped IN -- that would make
        # a k-1 word opening wearing a k-word name.
        for w in prefix:
            pri[w] = big
        for w in banned_extra:
            pri[int(w)] = big
        c = int(np.lexsort((sec, pri))[0])
        if pri[c] >= big:
            continue
        cand = (int(pri[c]), int(sec[c]), i, c)
        if cand[:2] >= tuple(current):
            continue                       # this position offers no improvement
        if best is None or cand[:2] < best[:2]:
            best = cand
    return best


def climb(last_level, words, on_step=None, current=None):
    """Swap the best single word until nothing helps.  Returns the local optimum.

    `on_step(step, pos, old, new, uns, ssq)` fires on every accepted swap, which
    is the only thing that happens here worth watching: the scan between them is
    silent and takes seconds.
    """
    words = [int(w) for w in words]
    pri, sec = last_level(words[:-1])
    cur = (int(pri[words[-1]]), int(sec[words[-1]]))
    if current is not None and tuple(current) != cur:
        # A FREE DIFFERENTIAL, fired once per round by `climb_all` below: the
        # pair sections price an opening with `greedybuild.score`, this one with
        # `last_level_scores`.  Two implementations, one integer -- a
        # disagreement is a real defect and must stop the run, not be averaged.
        raise SystemExit("hillclimb: the last-level pass scores this opening %s "
                         "but the section before it reported %s"
                         % (cur, tuple(current)))
    step = 0
    while True:
        mv = neighbourhood(last_level, words, cur)
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


def splits_into(C, by_sig, target, size):
    """Every unordered SIZE-tuple of DISTINCT candidates totalling `target`.

    `size == 2` is `splits_of` and delegates to it, so there is one subset scan
    and one order, not two.  Above that it recurses: fix the smallest member,
    split the residual into `size - 1`.  **Requiring `rest[0] > x` is what makes
    each unordered tuple come out ONCE** -- without it a triple appears three
    times, once per member taking the outer slot -- and it also forces the three
    to be distinct, so a "triple" can never be one word used twice.

    MEASURED at size 3 on custom's 4282: ~139 subset-candidates per 15-letter
    target and ~174 triples, 0.01 s per position-triple.  The ENUMERATION is
    free; what a section costs is SCORING what comes out of it.
    """
    if size == 1:
        return [(int(y),) for y in by_sig.get(target.tobytes(), ())]
    if size == 2:
        return splits_of(C, by_sig, target)
    out = []
    for x in np.flatnonzero((C <= target).all(axis=1)):
        x = int(x)
        for rest in splits_into(C, by_sig, target - C[x], size - 1):
            if rest[0] > x:
                out.append((x,) + rest)
    return out


def set_moves(C, by_sig, words, size, within):
    """Every `(positions, replacements)`: swap `size` words for `size` others.

    The one generator every non-swap section uses, so the pair and triple
    sections cannot drift apart in what they exclude -- a word already in the
    opening (that would shorten it), and the identity, which is not a move.

    **THE TARGET MUST STAY int16.**  `anagram_index` keys on `C[i].tobytes()`,
    so a target promoted to int64 -- which `C[rows].sum(axis=0)` does by
    default -- hashes to a signature nothing matches and the section silently
    finds NOTHING.  Adding the rows one at a time keeps the dtype.
    """
    cur = set(int(w) for w in words)
    out = []
    for pos in itertools.combinations(range(len(words)), size):
        old = tuple(int(words[i]) for i in pos)
        keep = cur - set(old)
        target = C[old[0]].copy()
        for w in old[1:]:
            target = target + C[w]        # NOT .sum(axis=0): see the note above
        for t in near_targets(target, within):
            for repl in splits_into(C, by_sig, t, size):
                if set(repl) == set(old):
                    continue
                if any(w in keep for w in repl):
                    continue
                out.append((pos, repl))
    return out


def pair_moves(C, by_sig, words, within):
    """Every (i, j, x, y): replace positions i and j with candidates x and y.

    The size-2 case of `set_moves`, flattened -- kept because it is the shape
    the gate reads moves in.
    """
    return [(pos[0], pos[1], repl[0], repl[1])
            for pos, repl in set_moves(C, by_sig, words, 2, within)]


def climb_moves(score_fn, words, C, by_sig, size, within, current, on_step=None):
    """Take the best improving SIZE-word move until none helps.  Steepest.

    ONE loop for every multi-word section: a pair section and a triple section
    differ only in `size`, so they share the descent rather than each carrying a
    copy of it.  `score_fn(words) -> (unsolved, ssq)` is passed in rather than
    rebuilt here, so this never grows a second copy of the objective either.

    `on_step(step, old_words, new_words, unsolved, ssq)` gets TUPLES of `size`
    indices, so a printer handles any section by joining them.
    """
    words = [int(w) for w in words]
    cur = tuple(current)
    step = 0
    while True:
        best = None
        for pos, repl in set_moves(C, by_sig, words, size, within):
            trial = list(words)
            for p, w in zip(pos, repl):
                trial[p] = w
            val = score_fn(trial)
            if val < cur and (best is None or val < best[0]):
                best = (val, pos, repl)
        if best is None:
            return cur[0], cur[1], words, step
        step += 1
        val, pos, repl = best
        old = tuple(words[p] for p in pos)
        for p, w in zip(pos, repl):
            words[p] = w
        cur = val
        if on_step:
            on_step(step, old, tuple(repl), cur[0], cur[1])


def climb_pairs(score_fn, words, C, by_sig, within, current, on_step=None):
    """The size-2 case of `climb_moves`."""
    return climb_moves(score_fn, words, C, by_sig, 2, within, current, on_step)


# ---------------------------------------------------------------------------
# THE TWO OBJECTIVES.  Each returns the pair of callables the climb needs:
# `last_level(prefix)` over every candidate, and `score_one(words)` for a whole
# opening -- both giving keys that are MINIMISED lexicographically.
#
# They are DIFFERENT QUANTITIES over the same openings and their numbers never
# share a table.  `guarantee` counts answers the random tail can be made to LOSE
# and wants it at zero; `singles` counts answers a reply names OUTRIGHT and
# wants it as large as possible.  A guaranteed opening need not have many
# singletons, and a singleton-rich one need not be guaranteed.
# ---------------------------------------------------------------------------

def guarantee_objective(full, cols, M, ans, codes, budget):
    """Fewest answers the follow-up can be made to lose, ties on ssq."""
    from greedybuild import score                     # local: avoids a cycle
    def last_level(prefix):
        uns, ssq = last_level_scores(full, cols, M, prefix, ans, budget)
        return uns, ssq
    def score_one(words):
        return score(tuple(words), (full, codes, cols, ans, [M[c] for c in words]),
                     budget=budget)
    return last_level, score_one


def singles_objective(M, ans):
    """MOST answers alone in their bucket, ties on ssq.

    **NEGATED, because the climb minimises.**  Everything downstream reports
    `-primary`, so a step that lowers the key raises the singleton count.  It
    needs no `full`, no codes and no budget -- a singleton is a fact about the
    partition, with no look-ahead -- which is why this objective is cheap at
    every opening size where the other is not.
    """
    def last_level(prefix):
        sg, ssq = last_level_singles(M, prefix, ans)
        return -sg.astype(np.int64), ssq
    def score_one(words):
        sg, ssq = singles_of(M, list(words), ans)
        return -sg, ssq
    return last_level, score_one


def mean_objective(Mpool, M, ans, k, cand_to_pool, cap=6):
    """Fewest EXPECTED GUESSES, exactly, ties on ssq.  `math/openexact.py`.

    THE THIRD OBJECTIVE, and the first whose primary is not a count.  It is the
    quantity `run-wordle-race.sh --fallback answer` estimates by Monte Carlo --
    a blind k-word opening then a uniform draw from the still-consistent
    answers -- computed rather than sampled, so a climb is reproducible and has
    no winner's curse.

    **FIXED POINT, NOT FLOAT, and that is forced by `neighbourhood`.**  It casts
    the primary with `astype(np.int64)` and bans a word by writing INT32's max
    into it, so a float key would be truncated and a key above that sentinel
    would make a banned word look best.  `SCALE` is 10**4: the total runs to
    about 8800 guesses over the 2315 answers, so the key peaks near 8.8e7 --
    two orders inside the sentinel -- and the granularity is 1e-4 of a guess in
    the TOTAL, i.e. 4e-8 in the mean.  Do not raise SCALE without moving that
    sentinel first.

    `score_one` goes through `evaluate`, the whole-opening path VERIFIED against
    the committed race cells, rather than through the pass it is checked
    against.  That makes `climb`'s `current` assertion a real differential
    between two implementations of one number, exactly as it is for guarantee.
    """
    memo, ev_memo = {}, {}

    def last_level(prefix):
        return last_level_mean(Mpool, M, prefix, ans, k, cand_to_pool, memo)

    def score_one(words):
        words = list(words)
        r = evaluate(Mpool, M[words], [int(cand_to_pool[w]) for w in words],
                     ans, cap=cap, memo=ev_memo)
        key = joint_key(M[words])
        _, inv = np.unique(key, return_inverse=True)
        sizes = np.bincount(inv)
        return (int(round(r["total"] * SCALE)),
                int((sizes.astype(np.int64) ** 2).sum()))

    return last_level, score_one


# THE SECTIONS AFTER THE SWAP, in order: `(label, size, within)`.  Adding one is
# adding a row here -- the generator and the descent are already size-general --
# and the ORDER is widest last, so each can only move where the one before it is
# stuck.  `anagram3` is the user's, 2026-09-18.
SECTIONS = (("anagram", 2, 0), ("anagram+1", 2, 1), ("anagram3", 3, 0))


def climb_all(last_level, score_fn, C, by_sig, words,
              sections=SECTIONS, on_swap=None, on_move=None):
    """Every section in turn, ROUND AND ROUND until a whole pass moves nothing.

    Returns `(unsolved, ssq, words, rounds, totals)`, where `totals` is a list
    of `(label, steps)` in section order SUMMED OVER ROUNDS -- which is the
    number worth reporting, since it says which neighbourhood earned its time.

    `sections` is `(label, size, within)` per section, so one is added by
    extending `SECTIONS` rather than by editing this loop.

    THE STOPPING RULE IS A FULL BARREN PASS, not a barren section.  A section
    that moves invalidates every earlier section's "nothing helps" -- widening
    the neighbourhood is exactly what lets the narrow ones find something again
    -- so the only sound place to stop is after all of them fail in a row.
    """
    words = [int(w) for w in words]
    # A section that would move more words than the opening HAS is dropped
    # rather than run empty: `anagram3` on a 2-word opening has no position
    # triple to pick, and a totals line claiming it ran would be a lie.
    sections = [t for t in sections if t[1] <= len(words)]
    order = ["swap"] + [lab for lab, _, _ in sections]
    totals = dict.fromkeys(order, 0)
    uns = ssq = None
    rounds = 0
    while True:
        rounds += 1
        moved = 0
        cb = None if on_swap is None else (
            lambda *a, _r=rounds: on_swap(_r, *a))
        uns, ssq, words, n = climb(last_level, words, cb,
                                   current=None if uns is None else (uns, ssq))
        totals["swap"] += n
        moved += n
        for label, size, within in sections:
            mb = None if on_move is None else (
                lambda *a, _r=rounds, _l=label: on_move(_r, _l, *a))
            uns, ssq, words, n = climb_moves(score_fn, words, C, by_sig, size,
                                             within, (uns, ssq), mb)
            totals[label] += n
            moved += n
        if not moved:
            return uns, ssq, words, rounds, [(l, totals[l]) for l in order]
