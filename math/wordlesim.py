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

  * The FOLLOW-UP is one of the `TAILS` below, and it is a rule of the same
    shape that simply never declines.  Which one is part of the strategy: they
    are different strategies and get different result files.

        answer   a word drawn UNIFORMLY AT RANDOM from the ANSWERS still
                 consistent with every reply so far (the 2315 mystery words)
        guess    the same draw from the LEGAL GUESSES still consistent with them
                 (the 12972 typeable words)
        custom   the same draw from `words/custom.txt` (4282): every answer word
                 plus every other legal word at wordfreq zipf >= 2.5.  It models
                 a player who knows ordinary English but not the curated answer
                 list -- between the other two, and a THIRD quantity, not an
                 interpolation of them.

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
answer is in EVERY pool -- which `pool_mask` enforces rather than assumes -- and
reproduces every reply it produced, so it is never eliminated.  A rule that plays other words only delays that; it may not do so
forever, which `_MAX_TURNS` asserts.
"""

from collections import namedtuple

import numpy as np

from secondword import gray_counts, read_table, word_by_code
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


# --- the follow-ups --------------------------------------------------------
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

    def live_count(self, alive, played, replies):
        """How many words this follow-up would be choosing between right now.

        A rule that hands over early needs this, and it must be THIS pool's
        count: what a player can see depends on which list they are playing from.
        """
        return int(alive.sum())

    def __init__(self, ans2g):
        self.ans2g = ans2g

    def __call__(self, turn, alive, played, replies, rng):
        idx = np.flatnonzero(alive)
        if not len(idx):
            raise AssertionError("no answer is consistent with the replies so far")
        return int(self.ans2g[idx[int(rng.integers(len(idx)))]])


class RandomGuess:
    """Guess a word drawn uniformly from the live words of a GUESS-LIST POOL.

    The pool is a SUBSET of the 12972 legal words, given as a boolean mask over
    them; `None` means all 12972 (the `guess` follow-up).  Restricting it is the
    whole of the `custom` follow-up -- the draw, the live set and the caching are
    the same machinery, because they are the same question asked of fewer words.

    IT PLAYS WORDS THAT CANNOT BE THE ANSWER, whatever the pool.  10657 of the
    12972 are not in the mystery list, and 1967 of custom.txt's 4282 are not; so
    many draws are words the game would never choose as an answer.  That is the
    point of it -- it is what a player who does not know the curated answer list
    can do -- not a defect.

    THE POOL MUST CONTAIN EVERY ANSWER, and `pool_mask` refuses one that does
    not.  That is not fastidiousness: the termination argument is that the true
    answer reproduces every reply it produced and so is never filtered out, and a
    pool missing an answer breaks it -- the live set empties mid-game, on a
    hidden word the follow-up could never have named.

    IT KEEPS ITS OWN LIVE SET, over the guess list, because `play_game`'s `alive`
    bitmap is over the ANSWERS and cannot express this.  That set is a pure
    function of the (guess, reply) history, so the cache is keyed on the history
    itself: an extension of what it last saw is folded in incrementally, and
    anything else is rebuilt from scratch.  **That is what makes it safe as a
    FOLLOW-UP** -- it may be handed a game already several turns old, or a fresh
    game whose opening happens to match the last one, and it cannot carry stale
    state into either.
    """

    def __init__(self, full, pool=None):
        self.full = full          # 12972 x 12972: full[g][w] = reply of g against w
        self.pool = pool          # boolean mask over the 12972, or None for all
        self.hist = []            # the (guess, reply) prefix `live` was built from
        self.live = None

    pool_size = property(lambda self: int(self.full.shape[0] if self.pool is None
                                          else self.pool.sum()))

    def _seed(self):
        """A fresh live set: the pool itself, before any reply has narrowed it."""
        if self.pool is None:
            return np.ones(self.full.shape[0], dtype=bool)
        return self.pool.copy()

    def _refresh(self, played, replies):
        """Bring the live set up to date with the history, rebuilding if needed."""
        seen = list(zip(played, replies))
        if self.live is None or seen[:len(self.hist)] != self.hist:
            self.live = self._seed()
            self.hist = []
        for g, fb in seen[len(self.hist):]:
            self.live &= self.full[g] == fb
            self.hist.append((g, fb))
        return self.live

    def live_count(self, alive, played, replies):
        """How many words this follow-up would be choosing between right now.

        Counted over the POOL, NOT the answers: a player drawing from the legal
        guesses cannot see that only two ANSWERS remain -- knowing that would mean
        knowing the curated list they are defined as not having.
        """
        return int(self._refresh(played, replies).sum())

    def __call__(self, turn, alive, played, replies, rng):
        idx = np.flatnonzero(self._refresh(played, replies))
        if not len(idx):
            raise AssertionError("no legal word is consistent with the replies so far")
        return int(idx[int(rng.integers(len(idx)))])


class CoupledDraw:
    """A follow-up whose draws are ONE FLOAT each, so entries stay in lockstep.

    Wraps either ordinary follow-up: same live set, same uniform distribution over
    it, but the index comes from `rng.random()` rather than `rng.integers`.  That
    is not a style choice -- `integers` uses rejection sampling and consumes a
    VARIABLE number of bits, so two entries whose live sets differ in size fall
    out of step after the first differing draw and the coupling silently decays.
    One float per decision holds them turn for turn.

    IT IS WHAT MAKES A PAIRED COMPARISON PAIRED, and it is a DIFFERENT SAMPLER
    from the sweeps': a coupled run will not match a sweep cell at the same seed.
    Same quantity, different sample, deliberately.

    `rng` need only provide `.random()`, so a race can hand it a cursor over a
    pre-drawn row of floats instead of a Generator.
    """

    def __init__(self, tail):
        self.tail = tail

    def live_count(self, alive, played, replies):
        return self.tail.live_count(alive, played, replies)

    def __call__(self, turn, alive, played, replies, rng):
        if hasattr(self.tail, "_refresh"):
            live = self.tail._refresh(played, replies)
            idx = np.flatnonzero(live)
            pick = idx[min(int(rng.random() * len(idx)), len(idx) - 1)]
            return int(pick)
        idx = np.flatnonzero(alive)
        pick = idx[min(int(rng.random() * len(idx)), len(idx) - 1)]
        return int(self.tail.ans2g[pick])


def _tail_answer(guesses, answers, ans2g):
    return RandomAnswer(ans2g)


def load_full(guesses, who):
    """The SQUARE 12972x12972 pattern matrix, or a refusal naming its build.

    A separate artifact from the 12972x2315 one every other tool here reads, and
    gitignored like all of data/local/, so it is MISSING ON A FRESH CLONE --
    refuse with the build command rather than dying inside numpy.
    """
    from build_patterns import load_patterns
    try:
        full = np.array(load_patterns(full=True))
    except FileNotFoundError:
        raise SystemExit(
            "the %r follow-up needs the SQUARE guess x guess pattern matrix.\n"
            "Build it with 'python3 build_patterns.py --full' (about 18s, 168 MB)."
            % who)
    if full.shape != (len(guesses), len(guesses)):
        raise SystemExit("patterns_full.npy is %s, not %d x %d -- rebuild it"
                         % (full.shape, len(guesses), len(guesses)))
    return full


def pool_mask(guesses, answers, pool_words, who):
    """A boolean mask over the 12972 for `pool_words`, with both preconditions.

    TWO THINGS MUST HOLD, and neither is checked anywhere else, so both are
    checked here rather than discovered as a wrong number or a mid-game crash:

      * every pool word must be a LEGAL GUESS, or it cannot be played at all;
      * every ANSWER must be in the pool, or the follow-up's live set can empty
        mid-game -- the termination argument in the module docstring rests on
        the true answer surviving every filter, and a pool missing one breaks
        it on exactly the games that hide that word.
    """
    pos = {w: i for i, w in enumerate(guesses)}
    missing = [w for w in pool_words if w not in pos]
    if missing:
        raise SystemExit(
            "the %r follow-up's pool has %d word(s) that are not legal guesses, "
            "so they could never be played: %s"
            % (who, len(missing), ", ".join(missing[:5])))
    mask = np.zeros(len(guesses), dtype=bool)
    for w in pool_words:
        mask[pos[w]] = True
    absent = [w for w in answers if not mask[pos[w]]]
    if absent:
        raise SystemExit(
            "the %r follow-up's pool is missing %d ANSWER word(s) -- it could "
            "never name them, and its live set would empty mid-game on exactly "
            "those: %s" % (who, len(absent), ", ".join(absent[:5])))
    return mask


def _tail_guess(guesses, answers, ans2g):
    """The whole 12972-word guess list: the pool is unrestricted."""
    return RandomGuess(load_full(guesses, "guess"))


def _tail_custom(guesses, answers, ans2g):
    """words/custom.txt -- every answer, plus every legal word at zipf >= 2.5.

    THE LIST IS AN INPUT, NOT A RESULT: it is the committed artifact
    build_freq_wordlist.py writes, the same one the adversarial hill-climb uses,
    so a zipf means here what it means there.  NB it carries no spellcheck and
    no curated block/allow lists -- only the frequency bar and the answer floor.
    """
    return RandomGuess(
        load_full(guesses, "custom"),
        pool_mask(guesses, answers,
                  tail_pool_words("custom", guesses, answers), "custom"))


TAILS = {
    "answer": _tail_answer,
    "guess": _tail_guess,
    "custom": _tail_custom,
}

# A pool-restricted follow-up's word list, by its stem in data/shared/words/.
# Adding a follow-up that draws from a list means one entry here and one in
# TAILS; nothing else in the repo learns a filename.
TAIL_LISTS = {
    "custom": "custom",
}

# What each follow-up draws from, for the prose line a result file carries.  Kept
# beside TAILS so a new follow-up cannot be registered without describing itself
# -- `describe_tail` asserts the two agree.
TAIL_POOLS = {
    "answer": "2315 mystery",
    "guess": "12972 legal guess",
    "custom": "4282 custom",
}
assert set(TAIL_POOLS) == set(TAILS)


def tail_pool_words(name, guesses, answers):
    """The WORDS a follow-up draws from, as a list.

    THE ONE PLACE A FOLLOW-UP NAME RESOLVES TO A LIST.  The follow-up itself
    needs it as a mask and the ordering chooser needs it as pattern COLUMNS, and
    if each resolved the name for itself the two could quietly come to mean
    different lists -- the ordering optimised for one player and the games played
    by another.
    """
    check_tail(name)
    if name == "answer":
        return list(answers)
    if name == "guess":
        return list(guesses)
    from wordle import load_words
    return load_words(TAIL_LISTS[name])


def tail_names():
    """The registered follow-ups, sorted -- the ONE list every caller validates
    against, so adding one here reaches every tool instead of none of them."""
    return sorted(TAILS)


def check_tail(name, why=""):
    """Refuse an unknown or missing follow-up, naming the registered ones.

    Every entry point takes `--fallback` and every one of them used to spell the
    valid set out for itself, so a third follow-up would have been valid in some
    tools and unknown in others.  They all come through here now.
    """
    if name not in TAILS:
        raise SystemExit(
            "--fallback must be one of: %s\n"
            "  (which random word fills in wherever the strategy's own rule "
            "declines)%s" % (", ".join(tail_names()),
                             "\n  " + why if why else ""))
    return name


def describe_tail(name):
    """The pool a follow-up draws from, as a result file's prose names it."""
    return TAIL_POOLS[check_tail(name)]


def make_tail(name, guesses, answers, ans2g):
    """Build the named follow-up, or refuse with the list of known names."""
    return TAILS[check_tail(name)](guesses, answers, ans2g)


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


def _no_rule(guesses, answers, ans2g, args, name, tail=None, adapt=0):
    """No rule at all: the follow-up plays the whole game.

    On turn one every word in its pool is still live, so the opening word is
    itself a uniform draw -- nothing is hardcoded and no opener is an input.
    """
    if args:
        raise SystemExit("strategy %r takes no arguments, got: %s"
                         % (name, " ".join(args)))
    return None


class BlindRandomAnswer:
    """Guess a uniform random ANSWER every turn, IGNORING the replies -- until
    exactly one candidate is left, and then name it.

    The deliberately feedback-blind baseline (the user's, 2026-09-22), and the
    companion to `random`: that one draws from the answers still CONSISTENT with
    every reply, this one draws from all 2315 whatever the board says.  The ONE
    thing it ever reads off the board is when the candidate set reaches a single
    word, and then it plays that word.  So the two differ only in how the guess
    is CHOSEN, which is what makes them directly comparable.

    THE DRAW IS WITH REPLACEMENT (the user's call, 2026-09-22) -- a word already
    played can come up again, which is the literal reading of "random answers".
    A repeat returns the IDENTICAL reply, so it eliminates nothing, and this rule
    therefore BREAKS the invariant `_MAX_TURNS` is justified by up top ("a
    follow-up eliminates at least one word per turn").  Termination is still
    certain, by a different argument: every non-repeat strictly shrinks the
    candidate set, and a repeat has probability at most (turns so far) / 2315, so
    the run of repeats needed to reach 100000 turns has probability zero in any
    practical sense.  The bound cannot fire here; the REASON is this paragraph,
    not the one it is stated with.

    IT STILL LEARNS.  An inconsistent guess is scored against the true answer
    like any other, so its reply narrows the candidates just the same -- badly,
    since the word was not chosen to split anything, but not not-at-all.  This is
    "ignores the board when CHOOSING", never "receives no information".

    IT CAN ALSO WIN BY LUCK: a draw that happens to BE the answer ends the game
    inside `play_game` however many candidates were alive.  The singleton ending
    is the usual one, not the only one, so a mean built only from the singleton
    path would be wrong.

    The rule answers EVERY turn (`alive` always holds at least the true answer),
    so the follow-up it is registered with NEVER FIRES.  `answer` is the honest
    name for it regardless, because the answer list is the pool this draws from.
    """

    def __init__(self, ans2g):
        self.ans2g = ans2g

    def __call__(self, turn, alive, played, replies, rng):
        idx = np.flatnonzero(alive)
        if not len(idx):
            raise AssertionError("no answer is consistent with the replies so far")
        if len(idx) == 1:
            # The lone survivor is an ANSWER index and is about to be used as a
            # GUESS -- the two index spaces are different lists, so it goes
            # through ans2g.  (The same trap checktopk.py caught in topk.py.)
            return int(self.ans2g[idx[0]])
        return int(self.ans2g[int(rng.integers(len(self.ans2g)))])


def _make_blind_random(guesses, answers, ans2g, args, name, tail=None, adapt=0):
    """The BlindRandomAnswer rule -- takes no arguments and no opening."""
    if args:
        raise SystemExit("strategy %r takes no arguments, got: %s"
                         % (name, " ".join(args)))
    if adapt:
        raise SystemExit("--pair-adaptive needs an opening to abandon; strategy "
                         "%r plays a fresh random draw every turn" % name)
    return BlindRandomAnswer(ans2g)


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


class AdaptiveOpening:
    """Play the opening in order, but ABANDON it once the field is tiny.

    THIS IS `optturns --pair-adaptive N`, ported to the simulator -- same rule,
    same name, same meaning, measured under a different continuation.
    math/data/shared/PAIRS.md states it and carries the exact results:

        N = 0   pure blind: the later words are always played
        N = 1   one candidate left after g1: name it
        N = 2   two left: guess them (in order there, at random here -- same cost)

    Before each word after the first, the rule asks the FOLLOW-UP how many words
    it would be choosing between; at N or fewer it declines and the follow-up
    names one.

    THE ARITHMETIC IT BETS ON.  With two left, naming one costs 1.5 guesses on
    average -- half the time it is right -- while playing the blind word first
    costs 2, since that word identifies the answer without being it.  With one
    left it is 1 against 2.  So the early-out is a strict improvement per bucket,
    never a trade.  **At the threshold, "guess them in order" and "guess one at
    random" are the SAME expected cost** (a 2-set totals 3 either way), which is
    why this matches the exact solver's rule rather than approximating it.

    N STOPS BEING INTERESTING AT 3, and PAIRS.md says why: three candidates named
    in order cost 1+2+3 = 6, and a perfect three-way split also costs 6, so the
    objective goes indifferent and only variance separates them.  Nothing here
    forbids a larger N; it is simply a different game, and it is in the filename.

    N IS PART OF THE OBJECTIVE, not a tuning knob.  0, 1 and 2 are three
    different strategies whose numbers are not comparable with each other.

    THE COUNT COMES FROM THE FOLLOW-UP, and this is the ONE place the simulator
    must differ from the exact solver, which only ever counts answers.  Under the
    `answer` follow-up the two agree.  Under `guess` the count is over the live
    LEGAL WORDS, which is larger, so the early-out fires less often -- and it has
    to be that way: a player drawing from the 12972 cannot know that only two
    ANSWERS remain, and giving them that knowledge here while denying it when
    they guess would be two different players inside one strategy.

    ORDER MATTERS NOW, unlike a blind opening.  Whether the field is down to N
    after ONE word depends on WHICH word went first, so `a b` and `b a` are
    different strategies and both must be swept.  Blind openings are
    order-independent by construction -- solver/pairsplit.c enumerates only
    unordered pairs for exactly that reason -- and this rule is what breaks it.
    PAIRS.md measures the consequence: the winning PAIR never moved with N, but
    the winning ORDER did.
    """

    def __init__(self, opening_g, tail, adapt):
        self.opening_g = [int(g) for g in opening_g]
        self.tail = tail
        self.adapt = int(adapt)
        if not self.opening_g:
            raise ValueError("an opening needs at least one word")
        if self.adapt < 1:
            raise ValueError("an adaptive opening needs a threshold of at least 1")
        if tail is None:
            raise ValueError("the adaptive rule needs the follow-up it hands to")

    def __call__(self, turn, alive, played, replies, rng):
        if turn >= len(self.opening_g):
            return None
        if turn and self.tail.live_count(alive, played, replies) <= self.adapt:
            return None
        return self.opening_g[turn]


def make_opening_rule(opening_g, tail=None, adapt=0):
    """Build an opening rule from GUESS INDICES: the sweep's entry point.

    `adapt` is `--pair-adaptive N`: 0 plays the opening blind (the rule every
    earlier sweep here used), and N >= 1 abandons it once the follow-up is down
    to N or fewer words.  One place decides what that means, so the sweep and the
    registry cannot drift -- both end here.
    """
    if adapt:
        return AdaptiveOpening(opening_g, tail, adapt)
    return FixedOpening(opening_g)


class SecondWordByReply:
    """Open, and let the REPLY choose a word committed to up front.

    THE STRATEGY (the user's, 2026-09-10, in three steps).  Play the opener.  The
    reply's bucket then selects a word decided before the game -- one word per
    bucket, chosen by minimising the answers left over that bucket's own cases
    (math/secondword.py).  A reply in no bucket declines, and so does every turn
    from the third on: the follow-up plays a random compatible word.

    ONE ARRAY IS THE WHOLE RULE: `by_code[reply]` is the guess index to play, or
    -1 to decline.  It is built from the table's own groups, so the rule cannot
    disagree with the table it came from -- and the earlier single-word versions
    are just an array with one word repeated across the firing codes.

    THE SECOND WORD IS PLAYED BLIND, and usually is NOT a word the answer could
    still be.  That is the point of predetermining it: it was chosen to SPLIT
    what is left, not to win.  Nothing stops it being a live candidate when it
    happens to be one; nothing arranges for it either.

    THE COMPOSITION IS WHAT THE PLAYER SEES.  A repeated letter shown grey counts
    as a grey.  All-green ends the game before turn two, so a first-guess win can
    never trigger this.
    """

    def __init__(self, opener_g, by_code):
        self.opener_g = int(opener_g)
        self.by_code = np.asarray(by_code, dtype=np.int32)
        if (self.by_code == self.opener_g).any():
            raise ValueError("a second word repeats the opener, which can only "
                             "reproduce the reply already seen")
        # A RULE THAT NEVER FIRES IS LEGITIMATE, and it is not this rule being
        # misused: it is one opener whose table rows are all empty, because no
        # answer gives it a qualifying reply.  The strategy is then the plain
        # opener for that word, and a sweep over 12972 of them must not abort on
        # it.  Whether the CONDITION as a whole is sensible -- covering every
        # reply would be a blind two-word opening -- is a property of the table,
        # checked once by secondword.fire_groups, not per opener here.

    def __call__(self, turn, alive, played, replies, rng):
        if turn == 0:
            return self.opener_g
        if turn == 1:
            g = int(self.by_code[replies[0]])
            if g >= 0:
                return g
        return None


def make_second_rule(opener_g, by_code):
    """The reply-selected second-word rule, by GUESS INDEX: built in one place.

    The single-run registry entry and the opener SWEEP both end here, so the two
    cannot drift into being two slightly different strategies under one name --
    the same discipline `make_opening_rule` keeps for blind openings.
    """
    return SecondWordByReply(opener_g, by_code)


def second_rule_for(opening_g, table, guesses):
    """Build the rule for one opener out of a loaded second-word table.

    `opening_g` is the sweep's list of guess indices, which must hold exactly one
    word: this strategy is about what follows ONE opener, and a two-word blind
    opening is a different strategy that already has its own name.  An opener the
    table has no row for is REFUSED, which is what stops a `mystery` table being
    swept over the 12972 (or the reverse) without anyone noticing.
    """
    if len(opening_g) != 1:
        raise SystemExit(
            "this strategy takes ONE opener, not %d words: it chooses "
            "the second word from the FIRST word's reply, so a blind multi-word "
            "opening is a different strategy." % len(opening_g))
    word = guesses[int(opening_g[0])]
    if word not in table.rows:
        raise SystemExit(
            "%s has no row for the opener %r.\nIt was built over the %s opener "
            "pool -- sweeping a different pool with it would run the strategy on "
            "openers it never chose a second word for." % (table.path, word,
                                                           table.openers))
    return make_second_rule(int(opening_g[0]),
                            word_by_code(table, word, guesses))


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


def _make_opener(guesses, answers, ans2g, args, name, tail=None, adapt=0):
    """Rule: open with the word given as --strategy-arg, then decline.

    The word is REQUIRED -- there is no default opener here, and there could not
    honestly be one: which word to open with is the question a sweep exists to
    ask, so writing one down would be an answer hiding in configuration.
    """
    if len(args) != 1:
        raise SystemExit("strategy %r needs exactly one word: "
                         "--strategy-arg WORD (got %d arguments)" % (name, len(args)))
    return make_opening_rule(_resolve_opening(guesses, args, name),
                             tail=tail, adapt=adapt)


def _make_opening(guesses, answers, ans2g, args, name, tail=None, adapt=0):
    """Rule: play the given words in order, BLIND, then decline.

    Any number of words, one per --strategy-arg (or space-separated in one).  The
    words are REQUIRED for the same reason the single opener's is.
    """
    words = [w for a in args for w in a.split()]
    if not words:
        raise SystemExit("strategy %r needs at least one word: "
                         "--strategy-arg WORD (repeat it for more)" % name)
    return make_opening_rule(_resolve_opening(guesses, words, name),
                             tail=tail, adapt=adapt)


def _make_gray_second(guesses, answers, ans2g, args, name, tail=None, adapt=0):
    """Rule: the opener, then its table's word IF the reply shows enough greys.

    Both arguments are REQUIRED and neither could honestly be defaulted: which
    word to open with is the question a sweep exists to ask, and the TABLE is
    where the second word comes from -- a default table would bury the threshold
    and the two pools, which are the objective, inside the program.

        --strategy-arg WORD --strategy-arg TABLE.csv
    """
    if len(args) != 2:
        raise SystemExit(
            "strategy %r needs two arguments: --strategy-arg WORD "
            "--strategy-arg TABLE.csv (got %d)\n"
            "The table is built by: bash solver/run-second-word.sh --variant "
            "guess --min-grays 3" % (name, len(args)))
    word, path = args
    table = read_table(path)
    return second_rule_for(_resolve_opening(guesses, [word], name), table, guesses)


STRATEGIES = {
    # The baselines: the SAME empty rule under each follow-up.  Each PINS its
    # follow-up, because the name is what says which one it used -- so they take
    # no --fallback and a conflicting one is refused rather than run under a name
    # that hides it.  On turn one every word in the pool is live, so the opening
    # word is itself a uniform draw: no opener is an input to any of them.
    "random":        Strategy(_no_rule, "answer"),
    "random-guess":  Strategy(_no_rule, "guess"),
    "random-custom": Strategy(_no_rule, "custom"),
    # The FEEDBACK-BLIND baseline: a uniform draw from all 2315 answers every
    # turn, consistent or not, until exactly one candidate is left.  It pins
    # `answer` because that is the list it draws from -- but unlike the three
    # above it HAS a rule, and that rule answers every turn, so the follow-up
    # never actually plays.
    "random-blind":  Strategy(_make_blind_random, "answer"),
    # One fixed opener, then the follow-up.  It pins NOTHING: both follow-ups are
    # meaningful under it, they are different strategies, and --fallback says which.
    "opener":       Strategy(_make_opener, None),
    # The same, for an opening of ANY length played blind -- a pair, a triple.
    "opening":      Strategy(_make_opening, None),
    # One opener, then a PREDETERMINED second word SELECTED BY THE REPLY --
    # SecondWordByReply above, and math/secondword.py for the table.  Pins no
    # follow-up either: it is the same question again, asked of a different
    # player.  The NAME is the one it was born with, when the rule was a single
    # word above a grey threshold; the table it reads says what it does now.
    "gray-second":  Strategy(_make_gray_second, None),
}


def make_strategy(name, guesses, answers, ans2g, args=(), fallback=None,
                  tail=None, adapt=0):
    """Resolve a named strategy into (rule, follow-up NAME).

    The follow-up is never defaulted.  A strategy whose NAME pins one refuses a
    conflicting --fallback rather than running something its own filename would
    misdescribe; any other strategy requires the flag.

    `tail` is the BUILT follow-up OBJECT, and it is only needed by a rule that
    asks how many words the follow-up is choosing between (--pair-adaptive).  It
    is deliberately a separate argument from the NAME this returns: a caller
    resolves the name first (which is cheap), builds the follow-up, and calls
    again with it -- so a --resolve dry run never loads a 168 MB matrix.
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
                   next((n for n, e in STRATEGIES.items()
                         if e.fallback == fallback and e.factory is _no_rule),
                        "a strategy that does not pin one")))
        tail_name = entry.fallback
    else:
        if fallback is None:
            raise SystemExit(
                "strategy %r does not pin a follow-up, so --fallback is required "
                "(one of: %s).\nIt is part of the strategy, and it is in the "
                "result filename." % (name, ", ".join(sorted(TAILS))))
        tail_name = check_tail(fallback)
    if adapt:
        if entry.factory is _no_rule:
            raise SystemExit("--pair-adaptive needs an opening to abandon; "
                             "strategy %r has no rule" % name)
        if tail is None:
            raise SystemExit("--pair-adaptive needs the follow-up object: build "
                             "it with make_tail and pass tail=")
    rule = entry.factory(guesses, answers, ans2g, list(args), name, tail, adapt)
    return rule, tail_name
