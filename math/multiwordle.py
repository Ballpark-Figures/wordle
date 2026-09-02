"""Multiwordle: k boards at once, one guess played on every unsolved board.

THE GAME.  k hidden answers are drawn without replacement from the 2315 mystery
words, one per BOARD.  A turn is a single guess, and that guess is played on
EVERY unsolved board simultaneously -- so one guess returns k separate feedback
patterns and narrows every board at once.  A board is solved when the word
guessed IS its answer (an all-green reply); narrowing it to one candidate does
not solve it, the naming guess still costs a turn.  A game's score is the TOTAL
number of guesses until every board is solved, the opener included.

THE STRATEGY IMPLEMENTED HERE, stated exactly, because it is the whole question:

  1. Play a FIXED opener on turn 1 (the caller supplies it; see the note below).
  2. Among the boards still unsolved, take the one with the FEWEST remaining
     candidates, breaking ties by BOARD INDEX (lowest wins).
  3. Guess a word drawn UNIFORMLY AT RANDOM from that board's remaining
     candidates, and apply it to every unsolved board.
  4. Repeat 2-3 until every board is solved.

It is a heuristic, not an optimum: nothing here searches, and no claim is made
that this minimises anything.  It is also RANDOMISED, so a fixed set of k
answers still gives a distribution rather than a number.

INCIDENTAL SOLVES COUNT.  The word played for board A can happen to be board B's
answer; B is then solved too, for free, on that same turn.

THE OPENER IS AN INPUT, NOT A RESULT.  It is passed in and never defaulted here.
The one the video is currently exploring is the top of the SINGLETON ranking
(`tools/singletons.py`, data/shared/singletons/guess_singletons.csv) -- but that
ranking is a SINGLE-BOARD quantity: it counts how many of a guess's feedback
patterns are produced by exactly one of the 2315 answers.  It optimises nothing
about the k-board total, and it is not even unique (laten and rotan tie at 41).
So the opener is a parameter of the experiment, deliberately, and every result
file records which one produced it.

THERE IS NO GUESS CAP, and none is needed.  The word played is always a
candidate of the targeted board, and whatever comes back it leaves that board
strictly smaller: an all-green reply solves the board, and any other reply
eliminates the guessed word (its own reply against itself is all-green).  So the
process terminates on its own, and the expected total is an UNCONSTRAINED
expected-guess count -- NOT the "optimum subject to a guarantee" that every
optturns/hardturns/ansall number in this repo reports.  Do not put the two in
one table.  `_MAX_TURNS` below is a runaway ASSERTION derived from that bound,
not a modelling cap: reaching it means the invariant broke.
"""

import numpy as np

from wordle import ALL_GREEN


def answer_to_guess(answers, guesses):
    """Index map: answer index -> that word's index in the GUESS list.

    A candidate is picked out of a board's answer-indexed bitmap, but it is then
    PLAYED, so it has to be re-expressed as a guess index before it indexes the
    pattern matrix.  Skipping this map reads the wrong row of PAT and produces a
    confidently wrong game.
    """
    pos = {w: i for i, w in enumerate(guesses)}
    return np.array([pos[w] for w in answers], dtype=np.int32)


def play_game(pat, ans2g, answer_idx, opener_g, rng):
    """Play one k-board game under the strategy above.

    pat        (n_guess, n_answer) pattern matrix
    ans2g      answer index -> guess index (from answer_to_guess)
    answer_idx (k,) ANSWER indices of the hidden words, one per board
    opener_g   GUESS index of the fixed opener
    rng        numpy Generator; consumed once per non-opener guess

    Returns the list of GUESS indices played, in order.  Its length is the
    game's score.
    """
    k = len(answer_idx)
    na = pat.shape[1]
    alive = np.ones((k, na), dtype=bool)
    solved = np.zeros(k, dtype=bool)
    played = []
    max_turns = 1 + k * na          # runaway assertion, not a cap; see module doc

    g = int(opener_g)
    while True:
        played.append(g)
        if len(played) > max_turns:
            raise AssertionError("game exceeded %d turns -- the candidate set "
                                 "stopped shrinking" % max_turns)
        row = pat[g]
        for j in range(k):
            if solved[j]:
                continue
            fb = int(row[answer_idx[j]])
            if fb == ALL_GREEN:
                solved[j] = True
                continue
            alive[j] &= row == fb
            # the true answer is consistent with every reply it produced
            assert alive[j][answer_idx[j]]

        if solved.all():
            return played

        counts = alive.sum(axis=1)
        counts[solved] = na + 1          # solved boards are out of the running
        j = int(counts.argmin())         # argmin breaks ties on the lowest index
        idx = np.flatnonzero(alive[j])
        g = int(ans2g[idx[int(rng.integers(len(idx)))]])


def draw_answers(na, k, rng):
    """The k hidden answers of one game: answer indices, without replacement."""
    return rng.choice(na, size=k, replace=False)
