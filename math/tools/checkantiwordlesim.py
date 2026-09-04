"""Gate for `antiwordle_sim` — the fast path against the audited model.

The simulation never builds a `Cons`. It intersects per-guess masks, relying on the
fact that a guess's effect depends only on (guess, feedback) and not on the
constraint accumulated so far. That is the same theorem the C solver rests on, and
it is exactly the kind of shortcut that can be subtly wrong while still producing
plausible-looking averages — a simulation reports a number whatever it does, so
nothing else here would catch it.

FOUR CHECKS:

  1. ONE STEP.  `delta_mask(g, p)` against `legal_mask(step(CONS_NONE, g, p))`, the
     audited path, over many (guess, feedback) pairs.

  2. A WHOLE GAME.  The incrementally intersected mask against `legal_mask` of the
     constraint accumulated the slow way, at every turn of real random games. This
     is the one that would catch an error that only shows up after composition.

  3. GAMES ARE VALID.  Every guess legal when played, the last guess is the answer
     and no earlier one is, and no word is ever played twice.

  4. REPRODUCIBLE.  The same (opener, trials, seed) gives the same mean twice, and a
     different seed generally does not — the sweep's results are only meaningful if
     its parameters pin them down.

    python3 tools/checkantiwordlesim.py [--seed N] [--quick]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import CONS_NONE, GuessSpace, TRITS, legal, step
from antiwordle_sim import ALL_GREEN, delta_mask, play_random_game, simulate_opener
from build_patterns import load_patterns
from wordle import load_words

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def test_one_step(space, pat, rng, n):
    """delta_mask(g, p) == legal_mask(step(CONS_NONE, g, p))."""
    bad = None
    for _ in range(n):
        gi = int(rng.integers(space.n))
        ai = int(rng.integers(pat.shape[1]))
        code = int(pat[gi, ai])
        fast = delta_mask(space, gi, code)
        slow = space.legal_mask(step(CONS_NONE, space.letter_tuples[gi], TRITS[code]))
        if not np.array_equal(fast, slow):
            bad = (space.words[gi], code, int((fast != slow).sum()))
            break
    check("delta_mask == legal_mask(step(...))", bad is None,
          f"{n} (guess, feedback) pairs" if bad is None
          else f"{bad[0]} code {bad[1]}: {bad[2]} words differ")


def test_whole_game(space, pat, answers, rng, games):
    """The intersected mask tracks the accumulated constraint, turn by turn."""
    bad = None
    turns = 0
    for _ in range(games):
        ai = int(rng.integers(len(answers)))
        gi = int(rng.integers(space.n))
        cons = CONS_NONE
        legal_fast = np.ones(space.n, dtype=bool)
        for _turn in range(40):
            code = int(pat[gi, ai])
            if code == ALL_GREEN:
                break
            legal_fast &= delta_mask(space, gi, code)
            cons = step(cons, space.letter_tuples[gi], TRITS[code])
            turns += 1
            if not np.array_equal(legal_fast, space.legal_mask(cons)):
                bad = (answers[ai], space.words[gi], _turn)
                break
            idx = np.flatnonzero(legal_fast)
            gi = int(idx[rng.integers(len(idx))])
        if bad:
            break
    check("incremental mask == accumulated constraint, every turn", bad is None,
          f"{games} games, {turns} turns" if bad is None else str(bad))


def test_games_valid(space, pat, answers, rng, games):
    """Guesses legal when played, ends on the answer, nothing played twice."""
    bad = None
    for _ in range(games):
        ai = int(rng.integers(len(answers)))
        opener = int(rng.integers(space.n))
        # replay the same game deterministically, recording the line
        sub = np.random.default_rng(int(rng.integers(1 << 30)))
        cons = CONS_NONE
        legal_mask = np.ones(space.n, dtype=bool)
        gi, line = opener, []
        for _turn in range(60):
            if not legal(cons, space.words[gi]):
                bad = f"{space.words[gi]} illegal when played (answer {answers[ai]})"
                break
            if space.words[gi] in line:
                bad = f"{space.words[gi]} played twice (answer {answers[ai]})"
                break
            line.append(space.words[gi])
            code = int(pat[gi, ai])
            if code == ALL_GREEN:
                break
            legal_mask &= delta_mask(space, gi, code)
            cons = step(cons, space.letter_tuples[gi], TRITS[code])
            idx = np.flatnonzero(legal_mask)
            gi = int(idx[sub.integers(len(idx))])
        else:
            bad = f"game did not finish in 60 guesses (answer {answers[ai]})"
        if bad:
            break
        if line[-1] != answers[ai]:
            bad = f"line ends on {line[-1]!r}, not the answer {answers[ai]!r}"
            break
        if any(w == answers[ai] for w in line[:-1]):
            bad = f"answer {answers[ai]!r} played before the end"
            break
    check("games are legal, terminate, and end on the answer", bad is None,
          f"{games} games" if bad is None else str(bad))


def test_reproducible(space, pat, answers, rng):
    """Same (opener, trials, seed) -> same mean; a different seed -> a new sample."""
    gi = int(rng.integers(space.n))
    a = simulate_opener(space, pat, gi, 60, np.random.default_rng(7), len(answers))
    b = simulate_opener(space, pat, gi, 60, np.random.default_rng(7), len(answers))
    c = simulate_opener(space, pat, gi, 60, np.random.default_rng(8), len(answers))
    check("same seed reproduces the mean exactly", a[0] == b[0],
          f"{space.words[gi]}: {a[0]:.4f}")
    check("a different seed draws a different sample", a[0] != c[0],
          f"seed 7 {a[0]:.4f} vs seed 8 {c[0]:.4f}")


def main():
    argv = sys.argv[1:]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 4242
    quick = "--quick" in argv
    rng = np.random.default_rng(seed)

    guesses = load_words("guess")
    answers = load_words("mystery")
    space = GuessSpace(guesses)
    pat = load_patterns()
    print(f"antiwordle_sim gate: {len(guesses)} guesses, {len(answers)} answers, "
          f"seed {seed}" + ("  [quick]" if quick else "") + "\n")

    test_one_step(space, pat, rng, 40 if quick else 200)
    test_whole_game(space, pat, answers, rng, 3 if quick else 12)
    test_games_valid(space, pat, answers, rng, 5 if quick else 25)
    test_reproducible(space, pat, answers, rng)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
