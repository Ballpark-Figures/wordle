"""Gate for math/greedybuild.py -- the construction, against what it claims.

    python3 tools/checkgreedybuild.py

THE LOAD-BEARING CHECK IS THAT `unsolved` IS THE GUARANTEE CONDITION.  The whole
point of this search is that it optimises the real objective rather than a
proxy, so the objective is diffed against `guarantee_sweep.check_opening` -- a
separate implementation, reached by a different route (it walks answers and
recurses; this walks buckets and stops early).  If those two ever disagree the
construction is optimising something else.

Run it alongside tools/checkguarantee.py.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                            # noqa: E402
from greedybuild import BLANK, completions, score, solved_in_bucket, spell  # noqa: E402
from guarantee import worst_case                                    # noqa: E402
from guarantee_sweep import check_opening                           # noqa: E402
from wordle import load_words, pattern, pattern_row, to_codes       # noqa: E402


def main(argv):
    failures = []
    guesses = load_words("guess")
    answers = load_words("mystery")
    pool = sorted(load_words("custom"))
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(pool)}
    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    pool_codes = to_codes(pool)
    ans_pool_idx = np.array([ppos[w] for w in answers])

    # --- the blank filler IS the real feedback function ----------------------
    # A partial word is spelled with `_`, so this is not a new rule but the old
    # one applied to a string; the vectorised row must equal the scalar one.
    bad = 0
    for g in ("s_l__", "_____", "__z__", "a_a_a", "craps"):
        row = pattern_row(g, pool_codes)
        bad += sum(1 for i, w in enumerate(pool[:300]) if row[i] != pattern(g, w))
    if bad:
        failures.append("pattern_row disagrees with pattern on %d partial-word "
                        "cells" % bad)
    # and a blank can never be anything but grey
    for w in pool[:200]:
        p = pattern(BLANK * 5, w)
        if p != 0:
            failures.append("a fully blank word scored %d, not all-grey" % p)
            break
    print("the blank filler is the real feedback rule: vectorised equals scalar, "
          "and an all-blank word is all-grey")

    # --- solved_in_bucket IS worst_case <= 2 --------------------------------
    rng = np.random.default_rng(3)
    checked, both = 0, [0, 0]
    for _ in range(300):
        n = int(rng.integers(1, 7))
        members = np.sort(rng.choice(len(pool), n, replace=False))
        sub = full[np.ix_(cols[members], cols[members])]
        got = set(solved_in_bucket(full, cols, members, list(range(n))))
        want = {p for p in range(n) if worst_case(sub, p) <= 2}
        if got != want:
            failures.append("solved_in_bucket disagrees with worst_case <= 2 on "
                            "%s" % [pool[i] for i in members])
            break
        checked += 1
        both[0] += len(want) > 0
        both[1] += len(want) < n
    if not both[0] or not both[1]:
        failures.append("every sampled bucket came out all-solved or all-unsolved, "
                        "so the comparison never separated the two")
    print("solved_in_bucket equals worst_case <= 2 on %d random buckets "
          "(%d had a solved answer, %d had an unsolved one)"
          % (checked, both[0], both[1]))

    # --- the OBJECTIVE equals the guarantee sweep's losing count ------------
    # The end-to-end check: a COMPLETE opening scored here must have exactly the
    # answers the guarantee sweep calls losing.
    ctx_g = (full, cols, pool, ans_pool_idx, answers, 0, 6, gpos)
    openings = [["craps", "until", "often", "fjord"],
                ["salet", "courd", "nymph", "biggy"],
                ["clown", "derby", "fight", "vamps"]]
    agreed = 0
    for op in openings:
        if any(w not in ppos for w in op):
            continue
        rows = [pattern_row(w, pool_codes) for w in op]
        ctx = (full, pool_codes, cols, ans_pool_idx, rows)
        uns, ssq = score(tuple(tuple(w) for w in op), ctx)
        _, losers, _, _, _ = check_opening(op, ctx_g)
        if uns != len(losers):
            failures.append("%s: greedy says %d unsolved, the guarantee sweep "
                            "says %d can lose" % (" ".join(op), uns, len(losers)))
            continue
        agreed += 1
    if not agreed:
        failures.append("no complete opening was compared against the sweep")
    print("the objective IS the guarantee condition: %d complete openings agree "
          "with guarantee_sweep's losing count exactly" % agreed)

    # --- legality: a placed word must stay completable ----------------------
    w = [None] * 5
    w[0] = "q"
    if not completions(pool_codes, w).any():
        failures.append("q at position 0 has no completion, but the pool has "
                        "q-initial words")
    w2 = [None] * 5
    w2[0], w2[1] = "q", "q"
    if completions(pool_codes, w2).any():
        failures.append("qq at positions 0-1 was called completable")
    print("legality: a completable prefix is kept and an impossible one refused")

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
