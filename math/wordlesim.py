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

A STRATEGY IS A RULE PLUS A FOLLOW-UP, and both are INPUTS -- never defaulted,
and both named in the result file, because together they are the experiment.

  * The RULE is what the strategy does while it has something to say:

        rule(turn, alive, played, replies, rng) -> guess index, or None

    where `turn` is how many guesses have already been played, `alive` is the
    boolean bitmap of ANSWERS still consistent with every reply so far, `played`
    and `replies` are the history as GUESS indices and pattern codes, and the
    return is an index into the 12972-word GUESS list.  **Returning None means
    "I have no rule for this position" -- the FOLLOW-UP fills it in.**  A rule
    may return None on some turns and a guess on others; it is asked every turn,
    so it can hand back and take over again.

  * The FOLLOW-UP is one of the two `TAILS` below, and it is a rule of the same
    shape that simply never declines.  Which one is part of the strategy: they
    are different strategies and get different result files.

        answer   a word drawn UNIFORMLY AT RANDOM from the ANSWERS still
                 consistent with every reply so far (the 2315 mystery words)
        guess    the same draw from the LEGAL GUESSES still consistent with them
                 (the 12972 typeable words)

    "Consistent" means what it means in `ultraturns`: a word that could still BE
    the answer, i.e. one reproducing every reply seen so far.  So a word played
    and missed is never played again -- its own greys and yellows rule it out.

A rule of None (no rule at all) leaves the follow-up playing the whole game, and
that is exactly how the two baselines `random` and `random-guess` are defined:
the same empty rule under the two different follow-ups.  Every other strategy is
measured against them.

THE HIDDEN ANSWER ALWAYS COMES FROM THE 2315, whichever follow-up is in use.
The pool is the STRATEGY's, never the GAME's -- so two runs differing only in
their follow-up are directly comparable with each other.

They are heuristics, not optima: nothing here searches, and no claim is made
that any of this minimises anything.  They are also RANDOMISED, so even a fixed
answer gives a distribution rather than a number, which is why this is a Monte
Carlo estimate with a standard error rather than an exact computation.

WHY IT TERMINATES (and needs no cap): either follow-up plays a word that is
itself still consistent, so whatever comes back leaves its live set strictly
smaller -- an all-green reply ends the game, and any other reply eliminates the
word just played, since a word's reply against itself is all-green.  The true
answer is in both pools and reproduces every reply it produced, so it is never
eliminated.  A rule that plays other words only delays that; it may not do so
forever, which `_MAX_TURNS` asserts.
"""

from collections import namedtuple

import numpy as np

from wordle import ALL_GREEN

# How many guesses a game may take before we call the invariant broken.  Not a
# modelling cap: a follow-up eliminates at least one word per turn, so a game
# cannot legitimately run past the size of its pool, and reaching this means a
# rule stopped handing back.
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


# --- the two follow-ups ----------------------------------------------------
#
# Both have the RULE signature and simply never return None, so a follow-up is
# usable as a strategy in its own right and a rule can hand over to it on any
# turn -- including turn 0, which is what the two baselines do.


class RandomAnswer:
    """Guess a word drawn uniformly from the live ANSWERS (the 2315).

    Stateless: `play_game` maintains the answer-side bitmap every turn whatever
    the rule played, so this can be picked up at any point in a game.
    """

    pool_size = property(lambda self: len(self.ans2g))

    def __init__(self, ans2g):
        self.ans2g = ans2g

    def __call__(self, turn, alive, played, replies, rng):
        idx = np.flatnonzero(alive)
        if not len(idx):
            raise AssertionError("no answer is consistent with the replies so far")
        return int(self.ans2g[idx[int(rng.integers(len(idx)))]])


class RandomGuess:
    """Guess a word drawn uniformly from the live LEGAL GUESSES (the 12972).

    IT PLAYS WORDS THAT CANNOT BE THE ANSWER.  10657 of the 12972 are not in the
    mystery list, so most draws are words the game would never choose as an
    answer.  That is the point of it -- it is what a player who does not know the
    curated answer list can do -- not a defect.

    IT KEEPS ITS OWN LIVE SET, over the GUESS list, because `play_game`'s `alive`
    bitmap is over the ANSWERS and cannot express this.  That set is a pure
    function of the (guess, reply) history, so the cache is keyed on the history
    itself: an extension of what it last saw is folded in incrementally, and
    anything else is rebuilt from scratch.  **That is what makes it safe as a
    FOLLOW-UP** -- it may be handed a game already several turns old, or a fresh
    game whose opening happens to match the last one, and it cannot carry stale
    state into either.
    """

    def __init__(self, full):
        self.full = full          # 12972 x 12972: full[g][w] = reply of g against w
        self.hist = []            # the (guess, reply) prefix `live` was built from
        self.live = None

    def __call__(self, turn, alive, played, replies, rng):
        seen = list(zip(played, replies))
        if self.live is None or seen[:len(self.hist)] != self.hist:
            self.live = np.ones(self.full.shape[0], dtype=bool)
            self.hist = []
        for g, fb in seen[len(self.hist):]:
            self.live &= self.full[g] == fb
            self.hist.append((g, fb))
        idx = np.flatnonzero(self.live)
        if not len(idx):
            raise AssertionError("no legal word is consistent with the replies so far")
        return int(idx[int(rng.integers(len(idx)))])


def _tail_answer(guesses, answers, ans2g):
    return RandomAnswer(ans2g)


def _tail_guess(guesses, answers, ans2g):
    """Build the guess-list follow-up, loading the matrix it needs.

    The SQUARE 12972x12972 matrix (~168 MB) is a separate artifact from the
    12972x2315 one every other tool here reads, and it is gitignored like all of
    data/local/, so it will be missing on a fresh clone -- refuse with the build
    command rather than dying inside numpy.
    """
    from build_patterns import load_patterns
    try:
        full = np.array(load_patterns(full=True))
    except FileNotFoundError:
        raise SystemExit(
            "the 'guess' follow-up needs the SQUARE guess x guess pattern matrix.\n"
            "Build it with 'python3 build_patterns.py --full' (about 18s, 168 MB).")
    if full.shape != (len(guesses), len(guesses)):
        raise SystemExit("patterns_full.npy is %s, not %d x %d -- rebuild it"
                         % (full.shape, len(guesses), len(guesses)))
    return RandomGuess(full)


TAILS = {
    "answer": _tail_answer,
    "guess": _tail_guess,
}


def make_tail(name, guesses, answers, ans2g):
    """Build the named follow-up, or refuse with the list of known names."""
    if name not in TAILS:
        raise SystemExit("unknown follow-up %r; known: %s"
                         % (name, ", ".join(sorted(TAILS))))
    return TAILS[name](guesses, answers, ans2g)


# --- the game --------------------------------------------------------------

def play_game(pat, ans2g, answer_idx, rule, tail, rng):
    """Play one game under `rule`, with `tail` filling in wherever it declines.

    pat        (n_guess, n_answer) pattern matrix
    ans2g      answer index -> guess index (from answer_to_guess)
    answer_idx ANSWER index of the hidden word
    rule       callable per the module docstring, or None for no rule at all
    tail       the follow-up, a callable of the same shape that never declines
    rng        numpy Generator, consumed once per follow-up guess

    `played` is the list of GUESS indices in order -- its length is the score --
    and `replies` the pattern code each drew.
    """
    alive = np.ones(pat.shape[1], dtype=bool)
    played, replies = [], []
    while True:
        g = None
        if rule is not None:
            g = rule(turn=len(played), alive=alive, played=played,
                     replies=replies, rng=rng)
        if g is None:
            g = tail(turn=len(played), alive=alive, played=played,
                     replies=replies, rng=rng)
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
    """The hidden answer of one game: an answer index, uniform over the 2315."""
    return int(rng.integers(na))


# --- the strategy registry -------------------------------------------------
#
# One entry per named strategy: the factory that builds its RULE, plus the
# follow-up the NAME pins, if it pins one.  A factory takes the loaded lists plus
# the strategy's own --strategy-arg values, so a rule that needs a word list, an
# opener or a precomputed table can have one without the trial loop knowing
# anything about it.

Strategy = namedtuple("Strategy", "factory fallback")


def _no_rule(guesses, answers, ans2g, args, name):
    """No rule at all: the follow-up plays the whole game.

    On turn one every word in its pool is still live, so the opening word is
    itself a uniform draw -- nothing is hardcoded and no opener is an input.
    """
    if args:
        raise SystemExit("strategy %r takes no arguments, got: %s"
                         % (name, " ".join(args)))
    return None


class FixedOpening:
    """Play a fixed sequence of words in order, BLIND, then decline.

    The smallest rule there is, and the one an OPENER SWEEP varies: it says what
    to open with and nothing else, so the follow-up plays the rest of the game.
    Which follow-up is in use is therefore the whole difference between two runs.

    BLIND MEANS BLIND: the second and later words are played whatever the replies
    said -- even when the candidates are already down to one, which is exactly
    what makes a multi-word opening a bet rather than a strategy.  The one thing
    that stops the sequence is WINNING: an all-green reply ends the game inside
    `play_game`, so a game the first word wins never plays the second and scores
    1.  That is the game's rule, not the opening's, and the opening never gets a
    chance to "waste" a guess after the answer is found.
    """

    def __init__(self, opening_g):
        self.opening_g = [int(g) for g in opening_g]
        if not self.opening_g:
            raise ValueError("an opening needs at least one word")

    def __call__(self, turn, alive, played, replies, rng):
        return self.opening_g[turn] if turn < len(self.opening_g) else None


def fixed_opening(opening_g):
    """The FixedOpening rule for a list of GUESS indices -- what a sweep builds.

    Public so the sweep and the registry share one rule rather than two copies:
    the sweep resolves its candidates against its own index map and calls this,
    while `--strategy opening --strategy-arg W1 --strategy-arg W2` goes through
    the registry.
    """
    return FixedOpening(opening_g)


def fixed_opener(opener_g):
    """The one-word case, kept as its own name because it is its own experiment."""
    return FixedOpening([opener_g])


def _resolve_opening(guesses, words, name):
    """Guess indices for an opening, refusing an illegal or repeated word.

    A repeat is refused because the second copy cannot inform anything: the reply
    to a word is a function of that word, so playing it twice spends a guess to
    learn what is already known.  If that is ever the experiment, it needs a name
    that says so.
    """
    seen = {}
    out = []
    for w in words:
        try:
            out.append(guesses.index(w))
        except ValueError:
            raise SystemExit("%s word %r is not one of the 12972 legal guesses"
                             % (name, w))
        if w in seen:
            raise SystemExit("the opening repeats %r; a repeated word learns "
                             "nothing the first one did not" % w)
        seen[w] = True
    return out


def _make_opener(guesses, answers, ans2g, args, name):
    """Rule: open with the word given as --strategy-arg, then decline.

    The word is REQUIRED -- there is no default opener here, and there could not
    honestly be one: which word to open with is the question a sweep exists to
    ask, so writing one down would be an answer hiding in configuration.
    """
    if len(args) != 1:
        raise SystemExit("strategy %r needs exactly one word: "
                         "--strategy-arg WORD (got %d arguments)" % (name, len(args)))
    return fixed_opening(_resolve_opening(guesses, args, name))


def _make_opening(guesses, answers, ans2g, args, name):
    """Rule: play the given words in order, BLIND, then decline.

    Any number of words, one per --strategy-arg (or space-separated in one).  The
    words are REQUIRED for the same reason the single opener's is.
    """
    words = [w for a in args for w in a.split()]
    if not words:
        raise SystemExit("strategy %r needs at least one word: "
                         "--strategy-arg WORD (repeat it for more)" % name)
    return fixed_opening(_resolve_opening(guesses, words, name))


STRATEGIES = {
    # The two baselines: the same empty rule under the two follow-ups.  Each
    # PINS its follow-up, because the name is what says which one it used.
    "random":       Strategy(_no_rule, "answer"),
    "random-guess": Strategy(_no_rule, "guess"),
    # One fixed opener, then the follow-up.  It pins NOTHING: both follow-ups are
    # meaningful under it, they are different strategies, and --fallback says which.
    "opener":       Strategy(_make_opener, None),
    # The same, for an opening of ANY length played blind -- a pair, a triple.
    "opening":      Strategy(_make_opening, None),
}


def make_strategy(name, guesses, answers, ans2g, args=(), fallback=None):
    """Resolve a named strategy into (rule, follow-up name).

    The follow-up is never defaulted.  A strategy whose NAME pins one refuses a
    conflicting --fallback rather than running something its own filename would
    misdescribe; any other strategy requires the flag.
    """
    if name not in STRATEGIES:
        raise SystemExit("unknown strategy %r; known: %s"
                         % (name, ", ".join(sorted(STRATEGIES))))
    entry = STRATEGIES[name]
    if entry.fallback is not None:
        if fallback is not None and fallback != entry.fallback:
            raise SystemExit(
                "strategy %r always follows up with %r, so --fallback %s would be "
                "a different strategy under a name that hides it.\n"
                "The %s follow-up with no rule is the strategy %r."
                % (name, entry.fallback, fallback, fallback,
                   next(n for n, e in STRATEGIES.items()
                        if e.fallback == fallback and e.factory is _no_rule)))
        tail = entry.fallback
    else:
        if fallback is None:
            raise SystemExit(
                "strategy %r does not pin a follow-up, so --fallback is required "
                "(one of: %s).\nIt is part of the strategy, and it is in the "
                "result filename." % (name, ", ".join(sorted(TAILS))))
        if fallback not in TAILS:
            raise SystemExit("unknown follow-up %r; known: %s"
                             % (fallback, ", ".join(sorted(TAILS))))
        tail = fallback
    rule = entry.factory(guesses, answers, ans2g, list(args), name)
    return rule, tail
