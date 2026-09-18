"""Gate for math/guarantee.py: the exact worst case, against brute force.

    python3 tools/checkguarantee.py [--openings N]

THE REFERENCE SHARES NO MACHINERY WITH WHAT IT CHECKS.  It keeps live sets as
LISTS OF WORDS, recomputes every reply from the STRINGS with `wordle.pattern`,
and ENUMERATES the follow-up's draw sequences outright rather than recursing on a
reply sub-matrix.  So a transposed matrix, a wrong pool index or a mis-derived
key shows as a disagreement instead of being shared by both sides.

Run it alongside solver/validate.sh and tools/checkpatterns.py.
"""

import os
import sys
from itertools import permutations

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guarantee import stop_levels, worst_case                      # noqa: E402
from guarantee_sweep import check_opening, worst_line              # noqa: E402
from wordle import load_words, pattern                             # noqa: E402
from build_patterns import load_patterns                           # noqa: E402


def ref_worst(live, answer):
    """L(S, a) from STRINGS, by enumerating what the follow-up could draw.

    The follow-up may play any live word; the worst case is the longest game it
    can produce.  Written as the definition reads -- try every word, filter by
    the reply recomputed from the strings, recurse -- with no matrix and no key.
    """
    if len(live) == 1:
        assert live[0] == answer
        return 1
    worst = 0
    for g in live:
        if g == answer:
            continue
        fb = pattern(g, answer)
        part = [w for w in live if pattern(g, w) == fb]
        assert answer in part and len(part) < len(live)
        worst = max(worst, ref_worst(part, answer))
    return 1 + worst


def ref_opening(opening, pool, answers, adapt, cap):
    """The whole check for one opening, from strings alone."""
    worst, losing = 0, 0
    for a in answers:
        live = list(pool)
        played = 0
        for t, g in enumerate(opening):
            if t and len(live) <= adapt:
                break
            fb = pattern(g, a)
            live = [w for w in live if pattern(g, w) == fb]
            played += 1
            if g == a:
                break
        if played and opening[played - 1] == a:
            total = played
        else:
            total = played + ref_worst(live, a)
        losing += total > cap
        worst = max(worst, total)
    return worst, losing


def main(argv):
    nopen = 6
    if "--openings" in argv:
        nopen = int(argv[argv.index("--openings") + 1])
    failures = []

    guesses = load_words("guess")
    answers = load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    full = np.array(load_patterns(full=True))

    # --- a SMALL pool and a small answer set, so brute force is affordable ----
    # The answer set must be a SUBSET of the pool, which is the precondition the
    # whole termination argument rests on.
    pool = sorted(guesses[i] for i in range(0, len(guesses), 260))
    ans = [w for w in answers if w in set(pool)]
    if len(ans) < 20:
        ans = pool[:40]
    cidx = np.array([gpos[w] for w in pool])
    ppos = {w: i for i, w in enumerate(pool)}
    apool = np.array([ppos[w] for w in ans])
    print("reference problem: %d pool words, %d answers" % (len(pool), len(ans)))

    # --- differential over several openings, both adapt settings -------------
    rng = np.random.default_rng(7)
    openings = [[pool[int(i)] for i in rng.choice(len(pool), 3, replace=False)]
                for _ in range(nopen)]
    tally = {"guaranteed": 0, "not": 0, "adapt_fired": 0, "opening_was_answer": 0}
    for adapt in (0, 2):
        # CAPS THAT SPAN THE ANSWER.  At 3 nothing on this problem is
        # guaranteed and at 7 everything is, so a range that brackets it is what
        # makes the coverage tally meaningful rather than one-sided.
        for cap in (3, 5, 7):
            ctx = (full, cidx, pool, apool, ans, adapt, cap, gpos)
            for op in openings:
                fast = check_opening(op, ctx)
                ref = ref_opening(op, pool, ans, adapt, cap)
                if (fast[0], len(fast[1])) != ref:   # check_opening NAMES the losers
                    failures.append(
                        "adapt %d cap %d, opening %s: fast (worst %d, losing %d) "
                        "vs reference (worst %d, losing %d)"
                        % (adapt, cap, " ".join(op), fast[0], len(fast[1]),
                           ref[0], ref[1]))
                    continue
                tally["guaranteed" if fast[0] <= cap else "not"] += 1
                if any(w in ans for w in op):
                    tally["opening_was_answer"] += 1
    print("diffed %d (opening, adapt, cap) cells against the string reference"
          % (len(openings) * 6))

    # --- the adaptive rule must actually have FIRED somewhere ----------------
    for op in openings:
        pool_rows = np.stack([full[gpos[w]][cidx] for w in op])
        lv0, _ = stop_levels(pool_rows, pool_rows[:, apool], 0)
        lv2, _ = stop_levels(pool_rows, pool_rows[:, apool], 2)
        tally["adapt_fired"] += int((lv2 < lv0).sum())

    # --- the WITNESS must replay, from the strings, to the reported length ----
    ctx = (full, cidx, pool, apool, ans, 2, 4, gpos)
    checked = 0
    for op in openings:
        worst, losing, wans, wline = check_opening(op, ctx)
        if len(wline) != worst:
            failures.append("witness for %s is %d words but the worst case is %d"
                            % (" ".join(op), len(wline), worst))
            continue
        # replay it: every guess after the opening must have been LIVE, and the
        # last word must be the answer
        live = list(pool)
        for t, g in enumerate(wline):
            if g not in live and t >= len(op):
                failures.append("witness for %s plays %s, which was not live"
                                % (" ".join(op), g))
                break
            fb = pattern(g, wans)
            live = [w for w in live if pattern(g, w) == fb]
        else:
            if wline[-1] != wans:
                failures.append("witness for %s does not end on the answer %s"
                                % (" ".join(op), wans))
            checked += 1
    print("replayed %d witness lines from the strings: every draw was live and "
          "each ends on its answer" % checked)

    # --- a hand-made case with a KNOWN answer --------------------------------
    # Three words, pairwise indistinguishable to each other under one guess, is
    # the shape that costs 3: play a wrong one, learn nothing, coin-flip.
    small = ["abbey", "abbes", "abbot"]
    for a in small:
        got = ref_worst(small, a)
        if got < 2:
            failures.append("a 3-word live set cost %d, which is impossible" % got)
    # and a set whose every member separates the others costs exactly 2
    if ref_worst(["aahed", "zymic"], "aahed") != 2:
        failures.append("a 2-word live set does not cost 2")

    # --- COVERAGE: a pass must not mean the branches never fired -------------
    if not tally["guaranteed"]:
        failures.append("no cell was GUARANTEED, so that branch never fired "
                        "(raise --openings or the cap)")
    if not tally["not"]:
        failures.append("every cell was guaranteed, so the losing branch never "
                        "fired -- the check cannot tell the two apart")
    if not tally["adapt_fired"]:
        failures.append("--adapt never shortened an opening, so the adaptive "
                        "path was never compared")
    print("coverage: %d guaranteed cells, %d not, the adaptive rule fired on %d "
          "(opening, answer) pairs" % (tally["guaranteed"], tally["not"],
                                       tally["adapt_fired"]))

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
