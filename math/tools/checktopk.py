"""Gate for `topk.py` -- the top-K guesser the adversarial search plays against.

Five independent checks, none of which trusts the numba kernel:

  1. PATTERN SLICE   -- the game's matrix equals `wordle.pattern` recomputed from
                        the word STRINGS (catches a bad row/column slice).
  2. DIFFERENTIAL    -- the numba kernel equals the pure-numpy reference on random
                        weight vectors, for k = 1, 2, 3. Same rules, two
                        implementations; they must agree to the last bit, since
                        the cost is a sum of integers times the weights.
  3. ACCOUNTING      -- total_cost equals sum(w_i * per_word_guesses_i), i.e. the
                        recursion's cost and the independent replay agree.
  4. TRACE           -- every candidate's played line ends all-green, its length
                        equals its per-word guess count, and every pattern in it
                        recomputes from the strings via `wordle.pattern`.
  5. ZERO WEIGHTS    -- a zero-weight word is invisible: dropping it from the list
                        entirely gives the identical objective. (It must not be
                        counted in n_p either, which is what makes the count-based
                        ranking rule correct.)

Exits nonzero on any failure, so it works as a gate. Run it after ANY change to
topk.py, alongside solver/validate.sh and tools/checkpatterns.py.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import topk as T
from wordle import ALL_GREEN, pattern

RNG = np.random.default_rng(20260902)
FAILS = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILS
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        FAILS += 1


def small_game(n_ans=120, n_extra_guesses=400, k=1, use_numba=True):
    """A game small enough for the numpy reference to solve in seconds."""
    words = T.read_words(T.CUSTOM)
    guesses = T.read_words(os.path.join(os.path.dirname(T.CUSTOM), "guess.txt"))
    ans = sorted(RNG.choice(words, size=n_ans, replace=False).tolist())
    pool = [g for g in guesses if g not in set(ans)]
    extra = RNG.choice(pool, size=n_extra_guesses, replace=False).tolist()
    return T.TopKGame(answers=ans, guesses=sorted(set(ans) | set(extra)),
                      k=k, use_numba=use_numba)


def main() -> int:
    print("1. pattern slice vs wordle.pattern")
    g = small_game()
    bad = []
    for _ in range(4000):
        i = int(RNG.integers(g.NG))
        j = int(RNG.integers(g.N))
        if int(g.P[i, j]) != pattern(g.guess_words[i], g.words[j]):
            bad.append((g.guess_words[i], g.words[j]))
    check("4000 random cells match", not bad, f"{len(bad)} mismatched")

    print("2. numba kernel vs numpy reference")
    if not T._HAVE_NUMBA:
        check("numba available", False, "cannot differential-test the kernel")
    else:
        for k in (1, 2, 3):
            fast = small_game(n_ans=60, n_extra_guesses=200, k=k, use_numba=True)
            slow = T.TopKGame(answers=fast.words, guesses=fast.guess_words,
                              k=k, use_numba=False)
            worst = 0.0
            for t in range(3):
                w = np.ones(fast.N) if t == 0 else RNG.choice(
                    [0.0, 0.125, 0.5, 1.0, 4.0, 64.0], size=fast.N)
                if w.sum() == 0:
                    continue
                a, b = fast.total_cost(w), slow.total_cost(w)
                worst = max(worst, abs(a - b))
            check(f"k={k}, 3 weight vectors", worst == 0.0, f"max |diff| = {worst:g}")

    print("3. cost accounting vs replay")
    for k in (1, 2):
        game = small_game(n_ans=90, n_extra_guesses=300, k=k)
        w = RNG.choice([0.0, 0.25, 1.0, 8.0], size=game.N)
        if w.sum() == 0:
            w[:] = 1.0
        d = abs(game.total_cost(w) - float((w * game.per_word_guesses(w)).sum()))
        check(f"k={k}", d == 0.0, f"|diff| = {d:g}")

    print("4. traces")
    game = small_game(n_ans=90, n_extra_guesses=300, k=1)
    w = RNG.choice([0.0, 1.0, 4.0], size=game.N)
    if w.sum() == 0:
        w[:] = 1.0
    counts = game.per_word_guesses(w)
    bad_end = bad_len = bad_pat = 0
    for i, word in enumerate(game.words):
        if w[i] <= 0:
            continue
        line = game.trace(word, w)
        if line[-1][1] != ALL_GREEN or line[-1][0] != word:
            bad_end += 1
        if len(line) != counts[i]:
            bad_len += 1
        if any(pat != pattern(gw, word) for gw, pat in line):
            bad_pat += 1
    live = int((w > 0).sum())
    check(f"{live} lines end all-green on the answer", bad_end == 0, f"{bad_end} bad")
    check("line length equals per-word guess count", bad_len == 0, f"{bad_len} bad")
    check("every pattern recomputes from the strings", bad_pat == 0, f"{bad_pat} bad")

    print("5. zero-weight words are invisible")
    game = small_game(n_ans=80, n_extra_guesses=250, k=1)
    w = np.ones(game.N)
    drop = RNG.choice(game.N, size=25, replace=False)
    w[drop] = 0.0
    kept = [word for i, word in enumerate(game.words) if w[i] > 0]
    trimmed = T.TopKGame(answers=kept, guesses=game.guess_words, k=1)
    d = abs(game.expected_guesses(w) - trimmed.expected_guesses(np.ones(len(kept))))
    check("25 zeroed words == removed from the list", d == 0.0, f"|diff| = {d:g}")

    print(f"\n{'ALL CHECKS PASSED' if FAILS == 0 else str(FAILS) + ' CHECK(S) FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
