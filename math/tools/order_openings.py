"""Pick the BEST ORDERING of each opening, exactly, before any games are played.

    python3 tools/order_openings.py --from SETS.txt --fallback answer \\
        --pair-adaptive 2 --out ORDERED.txt

Reads a list of openings (one per line, words space separated), and writes ONE
line per opening: the ordering with the lowest EXACT expected guesses under
`--pair-adaptive N`, ties broken alphabetically.  A pair sweep then costs half
what --both-orders costs, and a triple sweep a sixth, with no loss: the ordering
that wins here is the best one, not a screened guess at it.

WHY THIS IS EXACT RATHER THAN A HEURISTIC, which is the whole point:

  * Under a BLIND opening every ordering costs the same.  The words are played
    regardless, and the candidate set after all of them is an INTERSECTION of
    per-word filters, so it does not depend on the order.  The follow-up's
    continuation therefore does not either.
  * So two orderings can differ ONLY where the adaptive switch fires -- the rule
    keys on what the words played SO FAR have left -- or where an opening word IS
    the answer, and is reached at a different position.
  * Every one of those cases has a CLOSED-FORM cost at N <= 2.  A switch at
    level j over a live set of size m costs j + (m+1)/2: 1 guess for m=1, and 1.5
    for m=2, since naming one of two is right half the time.  An answer that is
    itself the i-th word of the opening costs i.
  * And the answers whose cost is NOT closed form -- the ones that reach the
    follow-up with three or more still live -- are exactly the answers where NO
    ordering switches, so their cost is identical across orderings and CANCELS.
    (If a switch fires in any ordering, the final set is a subset of a set of
    size <= N, so it too is 1 or 2 and its continuation is known.)

So the difference between orderings is a sum over a small, identifiable set of
answers with known costs.  No simulation, no sampling, no tie-breaking by luck.

N = 0 IS ALLOWED, and it is not a no-op: a BLIND opening still costs less when a
word that IS an answer is played earlier, which is the only way order can matter
without the switch.  PAIRS.md measures that as a gap of exactly 1 whenever one
word is an answer.  So the same tool orders a blind sweep too, replacing "take
whichever ordering the ranking happened to list".

N > 2 IS REFUSED, and this is the reason: with three live words the continuation
is no longer a closed form -- naming one of three at random costs 2 only if the
reply always separates the other two, which is a property of the words, not the
count.  The argument above would silently stop being exact.

THE FOLLOW-UP DECIDES WHICH POOL IS COUNTED, exactly as in the simulator: live
ANSWERS under `answer`, live LEGAL GUESSES under `guess`.  A set's best ordering
is therefore not the same question under the two, and each gets its own file.

WHAT THIS DOES NOT DO: it says nothing about which OPENING is best, only which
ORDERING of a given one.  The sweep still measures that, and the screen the
openings came from is still a screen.
"""

import os
import sys
import time
from itertools import permutations

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402
from wordlesim import answer_to_guess  # noqa: E402

# Naming one of m live words at random, when the answer is among them.  Exact for
# m = 1 and 2 only, which is why the tool refuses a larger threshold.
_NAME = {1: 1.0, 2: 1.5}


def live_sizes(rows, keys):
    """For each answer, how many pool words share its key so far.

    `rows` is (k, n_pool) -- the replies of the k opening words against every
    pool word -- and `keys` the same k replies against the ANSWER.  Returns a
    list: element j is the number of pool words matching the answer on words
    0..j.  Built cumulatively, so it is the live set after each guess.
    """
    mask = np.ones(rows.shape[1], dtype=bool)
    out = []
    for j in range(rows.shape[0]):
        mask &= rows[j] == keys[j]
        out.append(int(mask.sum()))
    return out


def order_cost(order_rows, order_keys, answer_pos, adapt, k):
    """Exact expected guesses for ONE answer under one ordering, or None.

    None means "the same under every ordering" -- the answer reached the
    follow-up with more than `adapt` words live and no opening word was it -- so
    the caller can leave it out of the comparison entirely.
    """
    sizes = live_sizes(order_rows, order_keys)
    for j in range(k):
        if answer_pos == j:
            return float(j + 1)              # this word IS the answer
        if adapt and j + 1 < k and sizes[j] <= adapt:
            return (j + 1) + _NAME[sizes[j]]  # abandon the rest, name one
    if adapt and sizes[-1] <= adapt:
        return k + _NAME[sizes[-1]]           # the follow-up names one
    return None                               # order-independent: cancels


def best_order_reference(words, gi, pat_rows, pool_rows, adapt, ans2g):
    """The best ordering of one opening, and the spread between orderings.

    THE SLOW, OBVIOUS IMPLEMENTATION, kept as the oracle for the fast one below.
    It walks the answers one at a time in Python, which is exactly why it cannot
    be the one a 10000-opening sweep calls -- but it is the readable statement of
    the rule, and `checkwordlesim.py` diffs the two.

    `pat_rows`  (k, n_answers)  each word's reply against every ANSWER
    `pool_rows` (k, n_pool)     each word's reply against every POOL word
    `ans2g`     answer index -> GUESS index, which is what makes the "this answer
                IS one of the opening words" test compare like with like.  The
                opening is a list of guess indices; an answer index is a different
                index space entirely, and comparing the two silently never matches
                (or matches the wrong word).
    """
    k = len(words)
    na = pat_rows.shape[1]
    best, best_total, totals = None, None, {}
    for perm in permutations(range(k)):
        rows_pool = pool_rows[list(perm)]
        rows_ans = pat_rows[list(perm)]
        total = 0.0
        for a in range(na):
            pos = next((j for j in range(k) if int(ans2g[a]) == gi[perm[j]]), None)
            c = order_cost(rows_pool, rows_ans[:, a], pos, adapt, k)
            if c is not None:
                total += c
        name = " ".join(words[i] for i in perm)
        totals[name] = total
        # ties break alphabetically, so the choice is reproducible
        if best_total is None or total < best_total - 1e-12 or (
                abs(total - best_total) <= 1e-12 and name < best):
            best, best_total = name, total
    spread = max(totals.values()) - min(totals.values())
    return best, spread, totals


def order_costs(rows_pool, rows_ans, order_gi, ans2g, adapt):
    """Per-answer exact cost under ONE ordering, vectorised over the answers.

    Returns (cost, known).  `known` is False exactly where the cost is the same
    under every ordering -- the answer reached the follow-up with more than
    `adapt` words live and no opening word was it -- so those entries cancel and
    are left out of the comparison.

    The live set after the first j words is "the pool words whose replies to all
    of them match the answer's", so it is a GROUP COUNT over a key built one word
    at a time -- one pass over the pool per level, not a loop over answers.  The
    key is compressed with np.unique rather than encoded as base-243 digits: at
    three words that encoding spans 14.3 million values, and allocating a counter
    that size per ordering is slower than sorting the pool.
    """
    k, na = rows_ans.shape
    cost = np.zeros(na, dtype=np.float64)
    known = np.zeros(na, dtype=bool)
    key_pool = np.zeros(rows_pool.shape[1], dtype=np.int64)
    key_ans = np.zeros(na, dtype=np.int64)
    sizes = None
    for j in range(k):
        key_pool = key_pool * 243 + rows_pool[j]
        key_ans = key_ans * 243 + rows_ans[j]
        uniq, inv = np.unique(key_pool, return_inverse=True)
        counts = np.bincount(inv, minlength=len(uniq))
        # every answer is in the pool, so its key is present and searchsorted is exact
        sizes = counts[np.searchsorted(uniq, key_ans)]
        is_word = (~known) & (ans2g == order_gi[j])
        cost[is_word] = j + 1                      # this word IS the answer
        known |= is_word
        if adapt and j + 1 < k:
            fire = (~known) & (sizes <= adapt)
            cost[fire] = (j + 1) + np.where(sizes[fire] == 1, 1.0, 1.5)
            known |= fire                          # abandon the rest, name one
    if adapt:
        fin = (~known) & (sizes <= adapt)
        cost[fin] = k + np.where(sizes[fin] == 1, 1.0, 1.5)
        known |= fin                               # the follow-up names one
    return cost, known


def best_order(words, gi, pat_rows, pool_rows, adapt, ans2g):
    """The best ordering of one opening, and the spread between orderings.

    The vectorised path, and what every sweep calls.  `best_order_reference`
    above states the same rule answer by answer and is diffed against this one by
    tools/checkwordlesim.py -- a fast path that nothing contradicts is how a
    silent wrong answer ships.
    """
    k = len(words)
    best, best_total, totals = None, None, {}
    for perm in permutations(range(k)):
        order_gi = [gi[i] for i in perm]
        cost, known = order_costs(pool_rows[list(perm)], pat_rows[list(perm)],
                                  np.asarray(order_gi), ans2g, adapt)
        total = float(cost[known].sum())
        name = " ".join(words[i] for i in perm)
        totals[name] = total
        if best_total is None or total < best_total - 1e-12 or (
                abs(total - best_total) <= 1e-12 and name < best):
            best, best_total = name, total
    return best, max(totals.values()) - min(totals.values()), totals


def main(argv):
    src = out = None
    fallback = None
    adapt = 2
    report = 500
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--fallback":
            fallback = argv[i + 1]; i += 2
        elif a == "--pair-adaptive":
            adapt = int(argv[i + 1]); i += 2
        elif a == "--report":
            report = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if src is None or out is None:
        raise SystemExit("--from SETS.txt and --out ORDERED.txt are required")
    if fallback not in ("answer", "guess"):
        raise SystemExit("--fallback answer|guess is required: which pool the "
                         "switch counts is part of the question")
    if adapt not in (0, 1, 2):
        raise SystemExit("--pair-adaptive must be 0, 1 or 2 here: above that the "
                         "continuation is no longer a closed form and this tool "
                         "would silently stop being exact")

    guesses = load_words("guess")
    answers = load_words("mystery")
    ans2g = answer_to_guess(answers, guesses)
    pat = np.array(load_patterns())
    if fallback == "answer":
        pool = pat                       # columns are the 2315 answers
    else:
        from build_patterns import load_patterns as lp
        pool = np.array(lp(full=True))   # columns are the 12972 guesses

    sets = []
    with open(src) as f:
        for line in f:
            w = line.split()
            if w:
                sets.append(w)
    sizes = {len(w) for w in sets}
    if len(sizes) != 1:
        raise SystemExit("the list mixes openings of %s words"
                         % " and ".join(map(str, sorted(sizes))))

    pos = {w: i for i, w in enumerate(guesses)}
    ans2g_arr = np.asarray(ans2g)
    lines, spreads, ties = [], [], 0
    print("ordering %d openings exactly (follow-up %s, pair-adaptive %d)"
          % (len(sets), fallback, adapt), flush=True)
    t0 = time.time()
    for n, words in enumerate(sets):
        gi = [pos[w] for w in words]
        best, spread, totals = best_order(
            words, gi, pat[gi], pool[gi], adapt, ans2g_arr)
        lines.append(best)
        spreads.append(spread)
        ties += spread == 0
        if report and (n + 1) % report == 0:
            el = time.time() - t0
            print("  %d/%d  %-20s spread %5.1f   %.0f/s  eta %.1f min"
                  % (n + 1, len(sets), best, spread, (n + 1) / el,
                     (len(sets) - n - 1) / ((n + 1) / el) / 60), flush=True)

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for line in lines:
            f.write(line + "\n")
    sp = np.asarray(spreads)
    print("%s: %d openings, one ordering each (of %d)"
          % (out, len(lines), len(list(permutations(range(len(sets[0])))))))
    print("  exact under --pair-adaptive %d, follow-up %s; ties alphabetical"
          % (adapt, fallback))
    print("  orderings that tied exactly: %d of %d" % (ties, len(sets)))
    print("  spread between orderings, in TOTAL guesses over the %d answers: "
          "max %.1f, mean %.2f" % (len(answers), sp.max(), sp.mean()))
    print("  head: %s" % " | ".join(lines[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
