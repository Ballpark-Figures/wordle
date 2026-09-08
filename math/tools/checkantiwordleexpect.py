"""Gate for `antiwordle_expect` — the expectimax accounting, four ways.

Weight accounting is the easiest thing here to get subtly wrong, and a wrong weight
still prints a perfectly plausible expected-turns number. Nothing downstream would
catch it, so it is checked directly, on small self-contained word sets where the
unrestricted search is affordable.

  1. REPLAY.  The search's value must equal the MEASURED average of the strategy it
     produced, played against every answer. This is the load-bearing check: it
     recomputes the same quantity by a completely different route, walking real
     games rather than summing weighted branches.

  2. MONOTONE IN K.  Top-K restricts the search to the K best-scoring legal words,
     and the top-5 contains the top-3, so a larger K searches a SUPERSET and its
     value can only rise. A drop means the restriction is not nested -- for example
     ranking that varies with K, or a memo shared across different K.

  3. K = |L| IS THE OPTIMUM.  With K at least the number of legal words nothing is
     restricted, so the value must equal an independent brute-force expectimax that
     knows nothing about ranking or top-K.

  4. BOTH RANKINGS ARE VALID STRATEGIES.  "static" and "alive" choose different
     guesses and generally different values -- neither is required to be better --
     but each must still satisfy check 1, or the ranking is corrupting the search
     rather than just steering it.

    python3 tools/checkantiwordleexpect.py [--seed N] [--quick]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import GuessSpace
from antiwordle_expect import best_strategy, expected_turns, play_out
from antiwordle_sim import delta_mask
from wordle import ALL_GREEN, load_words, pattern

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def world(rng, n):
    """A small self-contained world: the same word set as guesses and answers."""
    words = sorted(rng.choice(load_words("mystery"), size=n, replace=False).tolist())
    space = GuessSpace(words)
    pat = np.array([[pattern(g, a) for a in words] for g in words], dtype=np.int16)
    return space, pat, words


def brute_expectimax(space, pat, legal, alive, memo):
    """Unrestricted expectimax, written independently of the module under test.

    No ranking, no top-K, no shared helpers beyond the mask -- it exists to give
    check 3 something that cannot inherit the same mistake.
    """
    key = (legal.tobytes(), alive.tobytes())
    if key in memo:
        return memo[key]
    alive_idx = np.flatnonzero(alive)
    n = len(alive_idx)
    best = -1.0
    for g in np.flatnonzero(legal):
        g = int(g)
        acc = 1.0
        for code in set(int(c) for c in pat[g, alive_idx]):
            if code == ALL_GREEN:
                continue
            sub = alive_idx[pat[g, alive_idx] == code]
            ca = np.zeros_like(alive)
            ca[sub] = True
            acc += (len(sub) / n) * brute_expectimax(
                space, pat, legal & delta_mask(space, g, code), ca, memo)
        if acc > best:
            best = acc
    memo[key] = best
    return best


def test_replay(rng, trials, n, ks, mode):
    bad = None
    for _ in range(trials):
        space, pat, words = world(rng, n)
        score = rng.random(len(words))
        for k in ks:
            val, _, memo = best_strategy(space, pat, score, k, mode,
                                         answers_n=len(words))
            measured = sum(len(play_out(space, pat, score, k, ai, mode, memo))
                           for ai in range(len(words))) / len(words)
            if abs(measured - val) > 1e-9:
                bad = f"k={k} {mode}: search {val:.6f} vs replay {measured:.6f}"
                break
        if bad:
            break
    check(f"search value == measured replay ({mode})", bad is None,
          f"{trials} worlds of {n}, k in {ks}" if bad is None else bad)


def test_monotone(rng, trials, n, ks):
    bad = None
    for _ in range(trials):
        space, pat, words = world(rng, n)
        score = rng.random(len(words))
        vals = [best_strategy(space, pat, score, k, "static",
                              answers_n=len(words))[0] for k in ks]
        for i in range(len(vals) - 1):
            if vals[i] > vals[i + 1] + 1e-12:
                bad = f"k={ks[i]} gives {vals[i]:.4f} > k={ks[i+1]} gives {vals[i+1]:.4f}"
                break
        if bad:
            break
    check("value is non-decreasing in K", bad is None,
          f"{trials} worlds, k in {ks}" if bad is None else bad)


def test_unrestricted_is_optimal(rng, trials, n):
    bad = None
    for _ in range(trials):
        space, pat, words = world(rng, n)
        score = rng.random(len(words))
        val, _, _ = best_strategy(space, pat, score, len(words), "static",
                                  answers_n=len(words))
        ref = brute_expectimax(space, pat, np.ones(len(words), bool),
                               np.ones(len(words), bool), {})
        if abs(val - ref) > 1e-9:
            bad = f"top-K unrestricted {val:.6f} vs brute force {ref:.6f}"
            break
    check("K = |L| equals an independent brute-force expectimax", bad is None,
          f"{trials} worlds of {n}" if bad is None else bad)


def main():
    argv = sys.argv[1:]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 20260904
    quick = "--quick" in argv
    rng = np.random.default_rng(seed)
    print(f"antiwordle_expect gate: seed {seed}" + ("  [quick]" if quick else "") + "\n")

    test_replay(rng, 2 if quick else 5, 16 if quick else 22, (1, 3, 5), "static")
    test_replay(rng, 1 if quick else 3, 12 if quick else 16, (2, 4), "alive")
    test_monotone(rng, 2 if quick else 5, 16 if quick else 22, (1, 2, 3, 5, 8))
    test_unrestricted_is_optimal(rng, 2 if quick else 4, 12 if quick else 15)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
