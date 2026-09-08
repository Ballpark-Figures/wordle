"""GATE for the single-board Wordle simulator: the fast path vs an independent replay.

    python3 tools/checkwordlesim.py                 # from math/
    python3 tools/checkwordlesim.py --games 400     # more differential games

Exits nonzero on any failure, so it works as a gate.  Run it alongside
solver/validate.sh and tools/checkpatterns.py after touching math/wordlesim.py or
tools/wordle_sim.py.

WHAT THE ORACLE IS.  `wordlesim.play_game` is numpy over the 12972x2315 pattern
matrix: candidates are a boolean bitmap over the answer list, and filtering is
one vectorised `alive &= row == fb`.  The reference here shares NONE of that --
it keeps candidates as a LIST OF WORDS and recomputes every reply from the
STRINGS by the MULTISET rule (greens, then a yellow for each guess letter still
available in the answer's leftover counts), which is a different algorithm from
`wordle.pattern`'s left-to-right consuming scan, so a repeated-letter mistake
cannot be shared between them.  Both are driven from the same seed and must
produce IDENTICAL guess sequences -- which tests the candidate filtering, the
answer-index-to-guess-index map, the uniform draw's consumption of the generator
and the win condition all at once.

THE DEFINING PROPERTY IS CHECKED SEPARATELY, not inferred from the diff: every
guess the tail plays must be CONSISTENT with every reply so far (a word the
answer could still be), recomputed from the strings.  A shared bug that made
both sides pick the same wrong word would still fail this.

THE PREFIX-THEN-TAIL PATH IS EXERCISED TOO.  Almost every strategy the video will
try is "something specific for a while, then guess a random compatible answer",
which in code is a callable returning a guess and then None.  So the run also
plays a synthetic strategy that opens with a fixed word (the guess list's first
entry, taken BY INDEX so no word is written down here) and then defers, and
checks the opener really is played first, that it is played even when it is not a
candidate, and that the rest of the game matches the reference.

COVERAGE IS TALLIED, not assumed.  The run FAILS if no game ever ran past the
six-guess threshold, or if none came in at or under it, since the win-rate
accounting would then be untested in one direction.
"""

import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402
from wordlesim import (WIN_WITHIN, answer_to_guess, draw_answer,  # noqa: E402
                       make_strategy, play_game)
from wordle_sim import summarise  # noqa: E402


def ref_pattern(guess, answer):
    """Feedback code, by the MULTISET rule -- an independent implementation.

    Greens first; then a yellow for each remaining guess letter that the answer
    still has a spare copy of, counted rather than scanned.  Encoded base 3 with
    position 0 as the most significant trit, matching wordle.pattern's code.
    """
    tiles = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g] > 0:
            tiles[i] = 1
            left[g] -= 1
    code = 0
    for t in tiles:
        code = code * 3 + t
    return code


def ref_play(answers, answer, rng, opener=None):
    """Replay one game from strings alone.  Returns the words played, in order."""
    cands = list(answers)          # answer-list order, as the bitmap's flatnonzero is
    played = []
    while True:
        if opener is not None and not played:
            g = opener
        else:
            g = cands[int(rng.integers(len(cands)))]
        played.append(g)
        if g == answer:
            return played
        fb = ref_pattern(g, answer)
        cands = [w for w in cands if ref_pattern(g, w) == fb]
        if not cands:
            raise AssertionError("reference eliminated every candidate")


def consistent_prefix(played, answer):
    """Was every guess a word the answer could still have been at the time?

    Recomputed from the strings: guess i must reproduce every earlier reply.
    Returns the index of the first guess that was not, or None.
    """
    for i in range(1, len(played)):
        for j in range(i):
            if ref_pattern(played[j], played[i]) != ref_pattern(played[j], answer):
                return i
    return None


def main(argv):
    games = 200
    if "--games" in argv:
        games = int(argv[argv.index("--games") + 1])

    guesses = load_words("guess")
    answers = load_words("mystery")
    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    failures = []

    # --- the encodings the two sides must agree on, before any game runs ------
    checked = 0
    rng = np.random.default_rng(12345)
    for _ in range(4000):
        g = guesses[int(rng.integers(len(guesses)))]
        a = answers[int(rng.integers(len(answers)))]
        if ref_pattern(g, a) != pattern(g, a):
            failures.append("ref_pattern disagrees with wordle.pattern on %s/%s" % (g, a))
            break
        if ref_pattern(g, a) != int(pat[guesses.index(g)][answers.index(a)]):
            failures.append("the matrix disagrees with ref_pattern on %s/%s" % (g, a))
            break
        checked += 1
    print("pattern encodings agreed on %d random guess/answer pairs "
          "(strings, wordle.pattern, matrix)" % checked)

    # --- the ans2g map -------------------------------------------------------
    bad = [i for i in range(len(answers)) if guesses[ans2g[i]] != answers[i]]
    if bad:
        failures.append("ans2g maps %d answers to the wrong guess word" % len(bad))

    # --- differential: the bare tail -----------------------------------------
    strategy = make_strategy("random", guesses, answers, ans2g)
    scores, over, under, longest = [], 0, 0, 0
    for seed in range(games):
        fast_rng = np.random.default_rng(seed)
        ref_rng = np.random.default_rng(seed)
        a_fast = draw_answer(len(answers), fast_rng)
        a_ref = int(ref_rng.integers(len(answers)))
        if a_fast != a_ref:
            failures.append("seed %d: the two sides drew different answers" % seed)
            break
        answer = answers[a_fast]
        played, replies = play_game(pat, ans2g, a_fast, strategy, fast_rng)
        words = [guesses[g] for g in played]
        ref_words = ref_play(answers, answer, ref_rng)
        if words != ref_words:
            failures.append("seed %d (%s): fast %s vs reference %s"
                            % (seed, answer, " ".join(words), " ".join(ref_words)))
            break
        if words[-1] != answer or answer in words[:-1]:
            failures.append("seed %d (%s): the game did not end on the answer" % (seed, answer))
            break
        if replies[-1] != ALL_GREEN or ALL_GREEN in replies[:-1]:
            failures.append("seed %d (%s): the all-green reply is misplaced" % (seed, answer))
            break
        bad_at = consistent_prefix(words, answer)
        if bad_at is not None:
            failures.append("seed %d (%s): guess %d (%s) was not compatible with the "
                            "replies so far" % (seed, answer, bad_at + 1, words[bad_at]))
            break
        scores.append(len(words))
        over += len(words) > WIN_WITHIN
        under += len(words) <= WIN_WITHIN
        longest = max(longest, len(words))
    print("replayed %d games of the bare tail against the string reference: "
          "identical sequences, every guess compatible" % len(scores))

    # --- differential: a prefix strategy that then defers to the tail ---------
    # The opener is taken BY INDEX, so no word is written down in this gate.
    opener_g = 0
    opener = guesses[opener_g]

    def prefix(turn, alive, played, replies, rng):
        return opener_g if turn == 0 else None

    opened, non_candidate = 0, 0
    for seed in range(min(games, 60)):
        fast_rng = np.random.default_rng(1000 + seed)
        ref_rng = np.random.default_rng(1000 + seed)
        a_fast = draw_answer(len(answers), fast_rng)
        int(ref_rng.integers(len(answers)))
        answer = answers[a_fast]
        played, _ = play_game(pat, ans2g, a_fast, prefix, fast_rng)
        words = [guesses[g] for g in played]
        ref_words = ref_play(answers, answer, ref_rng, opener=opener)
        if words != ref_words:
            failures.append("prefix seed %d (%s): fast %s vs reference %s"
                            % (seed, answer, " ".join(words), " ".join(ref_words)))
            break
        if words[0] != opener:
            failures.append("prefix seed %d: the opener was not played first" % seed)
            break
        opened += 1
        non_candidate += opener not in answers
    print("replayed %d games of opener-then-tail: the opener leads every game "
          "(%s a mystery word, so the non-candidate path is exercised)"
          % (opened, "not" if opener not in answers else "IS"))

    # --- the reported numbers ------------------------------------------------
    if scores:
        st = summarise(scores, WIN_WITHIN)
        arr = np.asarray(scores, dtype=np.float64)
        if abs(st["mean_guesses"] - sum(scores) / len(scores)) > 1e-12:
            failures.append("summarise reported the wrong mean")
        if st["wins"] != sum(1 for s in scores if s <= WIN_WITHIN):
            failures.append("summarise counted the wrong number of wins")
        if abs(st["win_rate"] - st["wins"] / len(scores)) > 1e-12:
            failures.append("the win rate is not wins/trials")
        if abs(st["stderr"] - arr.std(ddof=1) / np.sqrt(len(scores))) > 1e-12:
            failures.append("the standard error is not sd/sqrt(n)")
        print("summary arithmetic: mean %.4f, win rate %.2f%% over %d games, "
              "longest %d guesses" % (st["mean_guesses"], 100.0 * st["win_rate"],
                                      len(scores), longest))

    # --- coverage: a pass must not mean the branches never fired -------------
    if not scores:
        failures.append("no game completed, so nothing was compared")
    if not over:
        failures.append("no game ran past %d guesses -- the loss branch of the "
                        "win rate was never exercised (raise --games)" % WIN_WITHIN)
    if not under:
        failures.append("no game finished within %d guesses -- the win branch was "
                        "never exercised" % WIN_WITHIN)
    if not non_candidate:
        failures.append("the synthetic opener was itself a mystery word, so playing "
                        "a NON-candidate was never exercised")
    print("coverage: %d games ran past %d guesses, %d came in within it"
          % (over, WIN_WITHIN, under))

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
