"""Single-board Wordle: simulate a named STRATEGY and measure what it costs.

THE GAME.  One hidden answer is drawn uniformly at random from the 2315 mystery
words.  A turn is a guess, which may be any of the 12972 legal words; the reply
is Wordle's own green/yellow/grey feedback (`wordle.pattern`).  The game ends
when the answer is actually PLAYED -- narrowing the candidates to one word does
not end it, the naming guess still costs a turn.  A game's score is the number
of guesses played.

THERE IS NO GUESS CAP HERE, and that is deliberate: play continues past six
until the word is found, so the mean is an UNCONSTRAINED expected-guess count --
NOT the "optimum subject to a 6-guess guarantee" that every optturns / hardturns
/ ansall number in this repo reports.  Do not put the two in one table.  Real
Wordle's six-guess rule enters only as a REPORTING threshold: the WIN RATE is
the fraction of games finished within `win_within` guesses (6 by default, the
game's own rule), computed from scores the cap never truncated.  `_MAX_TURNS`
below is a runaway ASSERTION derived from the termination argument, not a cap.

THE STRATEGY IS AN INPUT, NOT A RESULT.  It is passed in and never defaulted,
and it names the experiment: every result file records which one produced it.

HOW A STRATEGY IS WRITTEN, and why it is shaped this way.  Almost every strategy
worth trying here is "do something specific for a while, then guess a random
compatible answer".  So a strategy is a callable

    strategy(turn, alive, played, replies, rng) -> guess index, or None

where `turn` is how many guesses have already been played, `alive` is the
boolean bitmap of answers still consistent with every reply so far, `played` and
`replies` are the history as GUESS indices and pattern codes, and the return is
an index into the 12972-word GUESS list.  **Returning None means "the main part
of my strategy is over -- fall through to a random compatible answer"**, which
is the shared tail below.  A strategy that always returns None IS the pure
random-compatible strategy; that is exactly how `random` is defined.

THE RANDOM-COMPATIBLE TAIL, stated exactly: guess a word drawn UNIFORMLY AT
RANDOM from the answers still consistent with every reply so far.  It is a
heuristic, not an optimum -- nothing here searches, and no claim is made that it
minimises anything.  It is also RANDOMISED, so even a fixed answer gives a
distribution rather than a number, which is why this is a Monte Carlo estimate
with a standard error rather than an exact computation.

WHY IT TERMINATES (and needs no cap): the word played by the tail is always a
live candidate, so whatever comes back leaves the candidate set strictly
smaller -- an all-green reply ends the game, and any other reply eliminates the
word just played, since a word's reply against itself is all-green.  A strategy
that plays non-candidates for a while only delays that; it may not do so
forever, which `_MAX_TURNS` asserts.
"""

import numpy as np

from wordle import ALL_GREEN

# How many guesses a game may take before we call the invariant broken.  Not a
# modelling cap: the tail eliminates one candidate per turn at worst, so a game
# cannot legitimately exceed the number of answers by more than the opening
# phase, and reaching this means a strategy stopped shrinking the set.
_MAX_TURNS = 100000

# Real Wordle's rule.  Used ONLY to report a win rate; play is never truncated.
WIN_WITHIN = 6


def answer_to_guess(answers, guesses):
    """Index map: answer index -> that word's index in the GUESS list.

    A candidate is picked out of the answer-indexed bitmap but then PLAYED, so it
    has to be re-expressed as a guess index before it indexes the pattern matrix.
    Skipping this map reads the wrong row of PAT and produces a confidently wrong
    game.
    """
    pos = {w: i for i, w in enumerate(guesses)}
    return np.array([pos[w] for w in answers], dtype=np.int32)


def random_compatible(alive, ans2g, rng):
    """The shared tail: a guess index drawn uniformly from the live candidates."""
    idx = np.flatnonzero(alive)
    if not len(idx):
        raise AssertionError("no candidate is consistent with the replies so far")
    return int(ans2g[idx[int(rng.integers(len(idx)))]])


def play_game(pat, ans2g, answer_idx, strategy, rng):
    """Play one game under `strategy`, returning (played, replies).

    pat        (n_guess, n_answer) pattern matrix
    ans2g      answer index -> guess index (from answer_to_guess)
    answer_idx ANSWER index of the hidden word
    strategy   callable per the module docstring; None means use the tail
    rng        numpy Generator, consumed once per tail guess

    `played` is the list of GUESS indices in order -- its length is the score --
    and `replies` the pattern code each drew.
    """
    alive = np.ones(pat.shape[1], dtype=bool)
    played, replies = [], []
    while True:
        g = None
        if strategy is not None:
            g = strategy(turn=len(played), alive=alive, played=played,
                         replies=replies, rng=rng)
        if g is None:
            g = random_compatible(alive, ans2g, rng)
        g = int(g)
        row = pat[g]
        fb = int(row[answer_idx])
        played.append(g)
        replies.append(fb)
        if len(played) > _MAX_TURNS:
            raise AssertionError("game exceeded %d turns -- the candidate set "
                                 "stopped shrinking" % _MAX_TURNS)
        if fb == ALL_GREEN:
            return played, replies
        alive &= row == fb
        # the true answer is consistent with every reply it produced
        assert alive[answer_idx]


def draw_answer(na, rng):
    """The hidden answer of one game: an answer index, uniform over the list."""
    return int(rng.integers(na))


# --- the strategy registry -------------------------------------------------
#
# One entry per named strategy.  A factory takes the loaded lists plus the
# strategy's own arguments and returns the callable (or None for the bare tail),
# so a strategy that needs a word list, an opener or a precomputed table can
# have one without the trial loop knowing anything about it.


def _make_random(guesses, answers, ans2g, args):
    """Guess a random compatible answer, from the first guess to the last.

    The whole strategy is the shared tail, so it defers on every turn.  On turn
    one every answer is still alive, which means the opening word is itself a
    uniform draw from the 2315 -- nothing is hardcoded and no opener is an input.
    """
    if args:
        raise SystemExit("strategy 'random' takes no arguments, got: %s" % " ".join(args))
    return None


STRATEGIES = {
    "random": _make_random,
}


def make_strategy(name, guesses, answers, ans2g, args=()):
    """Build the named strategy, or refuse with the list of known names."""
    if name not in STRATEGIES:
        raise SystemExit("unknown strategy %r; known: %s"
                         % (name, ", ".join(sorted(STRATEGIES))))
    return STRATEGIES[name](guesses, answers, ans2g, list(args))
