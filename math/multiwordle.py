"""Multiwordle: k boards at once, one guess played on every unsolved board.

THE GAME.  k hidden answers are drawn without replacement from the 2315 mystery
words, one per BOARD.  A turn is a single guess, and that guess is played on
EVERY unsolved board simultaneously -- so one guess returns k separate feedback
patterns and narrows every board at once.  A board is solved when the word
guessed IS its answer (an all-green reply); narrowing it to one candidate does
not solve it, the naming guess still costs a turn.  A game's score is the TOTAL
number of guesses until every board is solved, the opener included.

THE STRATEGY IMPLEMENTED HERE, stated exactly, because it is the whole question:

  1. Play a FIXED OPENING SEQUENCE of one or more words, in order, BLIND -- each
     is played whatever the boards look like, the caller supplies them, and the
     sequence stops early only if every board is already solved.
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

BLIND MEANS BLIND.  With a multi-word opening, the second and later words are
played even when a board is already down to one candidate -- that is what makes
them an OPENING rather than part of the greedy, and it is the same assumption
the singleton ranking for pairs and triples is computed under (two answers share
a bucket iff they reply identically to EVERY word of the opening, so the count
does not depend on the order the words are played in).  Order is therefore
irrelevant to the partition the greedy inherits; it can still matter to an
incidental solve, which is why the sequence is played in the order given.

THE OPENING IS AN INPUT, NOT A RESULT.  It is passed in and never defaulted
here.  The ones the video is currently exploring are the heads of the SINGLETON
rankings (`tools/singletons.py` and `solver/run-singles.sh`,
data/shared/singletons/) -- but those are SINGLE-BOARD quantities: they count how
many feedback patterns are produced by exactly one of the 2315 answers.  They
optimise nothing about the k-board total, they are not unique (laten and rotan
tie at 41), and beyond pairs they are not even exhaustive -- the triple and quad
rankings are greedy screens, so their heads are "best of those screened".  So the
opening is a parameter of the experiment, deliberately, and every result file
records which one produced it.

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


def play_game(pat, ans2g, answer_idx, openers_g, rng):
    """Play one k-board game under the strategy above.

    pat        (n_guess, n_answer) pattern matrix
    ans2g      answer index -> guess index (from answer_to_guess)
    answer_idx (k,) ANSWER indices of the hidden words, one per board
    openers_g  GUESS indices of the fixed opening sequence, in play order
    rng        numpy Generator; consumed once per guess past the opening

    Returns the list of GUESS indices played, in order.  Its length is the
    game's score.
    """
    k = len(answer_idx)
    na = pat.shape[1]
    alive = np.ones((k, na), dtype=bool)
    solved = np.zeros(k, dtype=bool)
    played = []
    pending = [int(g) for g in openers_g]
    if not pending:
        raise ValueError("the opening sequence is empty")
    # runaway assertion, not a cap; see the module docstring
    max_turns = len(pending) + k * na

    g = pending.pop(0)
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
        if pending:
            g = pending.pop(0)      # the opening is blind: play it out
            continue

        counts = alive.sum(axis=1)
        counts[solved] = na + 1          # solved boards are out of the running
        j = int(counts.argmin())         # argmin breaks ties on the lowest index
        idx = np.flatnonzero(alive[j])
        g = int(ans2g[idx[int(rng.integers(len(idx)))]])


def draw_answers(na, k, rng):
    """The k hidden answers of one game: answer indices, without replacement."""
    return rng.choice(na, size=k, replace=False)
