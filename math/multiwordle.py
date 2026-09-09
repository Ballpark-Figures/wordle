"""Multiwordle: k boards at once, one guess played on every unsolved board.

THE GAME.  k hidden answers are drawn without replacement from the 2315 mystery
words, one per BOARD.  A turn is a single guess, and that guess is played on
EVERY unsolved board simultaneously -- so one guess returns k separate feedback
patterns and narrows every board at once.  A board is solved when the word
guessed IS its answer (an all-green reply); narrowing it to one candidate does
not solve it, the naming guess still costs a turn.  A game's score is the TOTAL
number of guesses until every board is solved, the opener included.

THE OPENING IS ALWAYS BLIND, whatever the rule.  A fixed sequence of one or more
words is played in order, each played whatever the boards look like, stopping
early only if every board is already solved.  What differs between the three
rules below is what happens AFTER the opening.

THREE RULES, AND THEY ARE THREE DIFFERENT STRATEGIES.  Every one of them is a
heuristic: nothing here searches for an optimum, and no claim is made that any
of them minimises anything.  Their numbers are comparable WITH EACH OTHER (same
game, same lists, same unconstrained expected-guess quantity) and must never be
tabled beside an optturns/hardturns/ansall total, which is an optimum SUBJECT TO
a 6-guess guarantee.

  `greedy` -- the original, and the DEFAULT, unchanged.
     2. Among the boards still unsolved, take the one with the FEWEST remaining
        candidates, breaking ties by BOARD INDEX (lowest wins).
     3. Guess a word drawn UNIFORMLY AT RANDOM from that board's remaining
        candidates, and apply it to every unsolved board.

  `srank` -- the same shape, but the board is chosen by TILE COLOUR rather than
     by a candidate count, which is the point: a human can see how many greens
     and yellows a board is showing and cannot count its candidates.
     2. Rank the unsolved boards by the SINGLETON CHANCE of the cumulative
        colour composition they are showing -- `(greens, yellows, grays)` in the
        tree-states sense (see `board_composition`), scored by the all-levels
        pooled ranking of `data/shared/treestates/states_optturns_top1000.csv`
        (see `load_singleton_ranking`).  Take the best-ranked board; break ties
        UNIFORMLY AT RANDOM among the tied boards, not by index.
     3. Guess a word drawn UNIFORMLY AT RANDOM from that board's remaining
        candidates, exactly as `greedy` does.
     It IGNORES CANDIDATE COUNTS ENTIRELY: a board with 300 candidates and two
     greens outranks a board with two candidates and none.  That is the rule as
     specified, not an oversight.
     NOTE at k=1 this IS `greedy` -- one board is trivially both the fewest-
     candidate board and the best-ranked one, and no tie can arise -- so a k=1
     `srank` run re-measures the committed k=1 `greedy` sweep.  The gate uses
     that as a differential test.

  `minavg` -- no board is targeted at all; a WORD is chosen directly.
     2. For every guess `g` in the pool and every unsolved board `j`, compute
        the AVERAGE ANSWERS REMAINING `a_j(g)` (see `average_remaining`).  Sort
        those k values ASCENDING and choose the `g` whose sorted vector is
        LEXICOGRAPHICALLY SMALLEST: minimise the smallest average-remaining,
        break ties on the second smallest, then the third, and so on; break a
        remaining tie on the LOWEST GUESS INDEX.
     3. Play it on every unsolved board.  There is no random step, so `minavg`
        is DETERMINISTIC: a game is a function of the k answers alone, and all
        the Monte Carlo variance comes from the answer draw.
     The pool is the whole 12972-word GUESS list, unfiltered -- words already
     played and words no board could still be are left in deliberately (they can
     be optimal, and filtering repeats is not worth the cost; they score badly on
     their own and are not chosen unless everything ties).

INCIDENTAL SOLVES COUNT, under every rule.  The word played for board A can
happen to be board B's answer; B is then solved too, for free, on that turn.

BLIND MEANS BLIND.  With a multi-word opening, the second and later words are
played even when a board is already down to one candidate -- that is what makes
them an OPENING rather than part of the rule, and it is the same assumption the
singleton ranking for pairs and triples is computed under (two answers share a
bucket iff they reply identically to EVERY word of the opening, so the count does
not depend on the order the words are played in).  Order is therefore irrelevant
to the partition the rule inherits; it can still matter to an incidental solve,
which is why the sequence is played in the order given.

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

THERE IS NO GUESS CAP, and none is needed -- but the two rules terminate for
DIFFERENT REASONS and the argument does not transfer, so both are written out.

  `greedy` and `srank`: the word played is always a candidate of the targeted
  board, and whatever comes back it leaves that board strictly smaller -- an
  all-green reply solves it, and any other reply eliminates the guessed word (its
  own reply against itself is all-green).

  `minavg`: nothing guarantees the played word is anybody's candidate, so that
  argument is GONE.  What replaces it: let `m_j` be board j's candidate count and
  `b` a board attaining the smallest of them.  Playing any candidate `h` of board
  b gives `a_b(h) < m_b`, so the chosen `g*`, which minimises the smallest
  average-remaining, satisfies `min_j a_j(g*) <= min_j a_j(h) < m_b = min_j m_j`.
  The board `j*` attaining that minimum therefore has `a_{j*}(g*) < m_{j*}`,
  which happens only when `g*` splits board j* into at least two buckets
  (counting the all-green one) -- so board j* is either solved or left a PROPER
  subset of itself.  Every turn strictly reduces `sum_j m_j`, hence termination.
  Note this is where the all-green bucket scoring 0 earns its keep: it is what
  makes a singleton board's own word score 0, the unique minimum, so the rule
  finishes a board it has already pinned down instead of stalling on it.

`_MAX_TURNS` below is a runaway ASSERTION derived from those bounds, not a
modelling cap: reaching it means the invariant broke.
"""

import os
from fractions import Fraction

import numpy as np

from wordle import ALL_GREEN, N_PATTERNS, WORD_LEN, decode

GREEDY = "greedy"
SRANK = "srank"
MINAVG = "minavg"
STRATEGIES = (GREEDY, SRANK, MINAVG)

_HERE = os.path.dirname(os.path.abspath(__file__))
RANKING_CSV = os.path.join(_HERE, "data", "shared", "treestates",
                           "states_optturns_top1000.csv")


def answer_to_guess(answers, guesses):
    """Index map: answer index -> that word's index in the GUESS list.

    A candidate is picked out of a board's answer-indexed bitmap, but it is then
    PLAYED, so it has to be re-expressed as a guess index before it indexes the
    pattern matrix.  Skipping this map reads the wrong row of PAT and produces a
    confidently wrong game.
    """
    pos = {w: i for i, w in enumerate(guesses)}
    return np.array([pos[w] for w in answers], dtype=np.int32)


# --- the cumulative colour composition (the tree-states definition) --------
#
# Carried per board as (pinned, known): `pinned` is an L-list of letter indices
# with -1 where the position is not yet pinned, and `known` maps a letter to the
# most copies any single reply has proved.  This is `tools/tree_states.py`'s
# state, deliberately -- the ranking `srank` reads was tabulated under it, so a
# different reading of "yellows" would be indexing that table with a quantity it
# does not describe.

def new_composition_state(word_len=WORD_LEN):
    """A board before any guess: nothing pinned, nothing known."""
    return [-1] * word_len, {}


def apply_composition(state, guess_letters, code):
    """Fold one reply into a board's cumulative state.

    `guess_letters` is the guess as letter indices (0..25); `code` the encoded
    pattern.  A position once pinned STAYS pinned -- a later guess playing a
    different letter there does not unpin it -- and a letter's known count is the
    most any single reply proved, never a sum over replies.
    """
    pinned, known = state
    tiles = decode(code, len(guess_letters))
    row = {}
    for i, t in enumerate(tiles):
        c = guess_letters[i]
        if t == 2:
            # two different letters green in one position is impossible
            assert pinned[i] in (-1, c), "position %d pinned twice" % i
            pinned[i] = c
            row[c] = row.get(c, 0) + 1
        elif t == 1:
            row[c] = row.get(c, 0) + 1
    for c, n in row.items():
        if n > known.get(c, 0):
            known[c] = n
    return state


def board_composition(state):
    """(greens, yellows) for a board: the tree-states reading, exactly.

    greens  = POSITIONS pinned green by any guess so far.
    yellows = COPIES of a letter known present but not yet pinned, SUMMED over
              letters -- two loose B's count 2, and a letter with one copy green
              and another loose contributes 1.
    grays   = word length - greens - yellows, so greens + yellows is the number
              of answer slots accounted for.  That invariant is what picks this
              reading over "distinct unplaced letters".
    """
    pinned, known = state
    pc = {}
    greens = 0
    for c in pinned:
        if c >= 0:
            pc[c] = pc.get(c, 0) + 1
            greens += 1
    yellows = 0
    for c, n in known.items():
        extra = n - pc.get(c, 0)
        if extra > 0:
            yellows += extra
    return greens, yellows


# --- the all-levels singleton ranking -------------------------------------

def load_singleton_ranking(path=None):
    """(greens, yellows) -> Fraction(singles, cases), POOLED OVER LEVELS.

    Reads the committed tree-states table and sums `singles` and `cases` across
    every level for each colour composition, ranking on the pooled ratio.  That
    matches the file's own weighting: a case is an ANSWER, so a node holding n
    candidates counts n times, and pooling by summing keeps that weighting rather
    than averaging per-level rates that stand on very different sample sizes.

    The value is an exact Fraction, not a float, so two compositions are TIED
    only when they are genuinely equal -- `srank`'s random tie-break must not
    fire or fail to fire on a rounding artifact.

    NB the table has 21 compositions, not the 20 a single pattern can show:
    `(4 green, 1 yellow)` is unreachable as one reply but IS reachable
    cumulatively, when four positions have been pinned by various guesses and a
    fifth letter is known present without having been pinned.
    """
    path = path or RANKING_CSV
    singles = {}
    cases = {}
    with open(path) as f:
        header = None
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            row = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None:
                header = row
                col = {c: i for i, c in enumerate(header)}
                for need in ("greens", "yellows", "cases", "singles"):
                    if need not in col:
                        raise SystemExit("%s has no %s column" % (path, need))
                continue
            key = (int(row[col["greens"]]), int(row[col["yellows"]]))
            singles[key] = singles.get(key, 0) + int(row[col["singles"]])
            cases[key] = cases.get(key, 0) + int(row[col["cases"]])
    if not cases:
        raise SystemExit("%s has no data rows" % path)
    return {k: Fraction(singles[k], cases[k]) for k in cases}


# --- average answers remaining --------------------------------------------

def average_remaining(pat, pool, alive_idx):
    """`a_j(g)` for every g in `pool`, against one board's candidate set.

    The average number of that board's candidates still consistent after playing
    g, the answer taken UNIFORMLY over the board's own candidates:

        a(g) = sum over patterns p != all-green of |S_p|^2 / |S|

    THE ALL-GREEN BUCKET COUNTS AS ZERO, deliberately: a solved board has nothing
    remaining.  That is what `topk.py`'s ranking rule does too, and it is what
    makes a singleton board's own word score 0 rather than 1 -- see the
    termination argument in the module docstring.

    Reference implementation: correct and readable, not fast.  `multiwordle_fast`
    carries the kernel the sweeps use and is diffed against this one.
    """
    m = len(alive_idx)
    if m == 0:
        raise ValueError("a board with no candidates")
    sub = pat[np.ix_(pool, alive_idx)]
    npool = len(pool)
    off = sub.astype(np.int64) + N_PATTERNS * np.arange(npool, dtype=np.int64)[:, None]
    cnt = np.bincount(off.ravel(), minlength=N_PATTERNS * npool)
    cnt = cnt.reshape(npool, N_PATTERNS).astype(np.float64)
    cnt[:, ALL_GREEN] = 0.0
    return (cnt * cnt).sum(axis=1) / m


def lexicographic_argmin(vals):
    """Index of the column whose SORTED values are lexicographically smallest.

    `vals` is (n_boards, n_pool).  Sort each column ascending, then compare
    columns on the smallest entry, then the second smallest, and so on; ties
    break on the LOWEST column index, which is why the pool must be given in
    ascending guess order.

    Float comparison is EXACT here, which is worth knowing rather than assuming:
    every value is `N/m` with integer `N <= 2315^2` and `1 <= m <= 2315`, so two
    DISTINCT values differ by at least `1/m1/m2 >= 1/2315^2 ~ 1.9e-7` absolute
    against magnitudes of at most 2315 -- a relative gap of ~8e-11, four orders
    above the double epsilon.  Distinct rationals cannot collide, so an equality
    here is a real tie.
    """
    order = np.sort(vals, axis=0)
    keys = [np.arange(vals.shape[1])]          # least significant: lowest index
    for i in range(order.shape[0] - 1, -1, -1):
        keys.append(order[i])
    return int(np.lexsort(keys)[0])


# --- the rules -------------------------------------------------------------

class Greedy:
    """Fewest candidates, ties by board index, uniform random candidate."""

    name = GREEDY
    needs_composition = False

    def choose(self, pat, ans2g, alive, solved, states, played, rng):
        na = alive.shape[1]
        counts = alive.sum(axis=1)
        counts[solved] = na + 1          # solved boards are out of the running
        j = int(counts.argmin())         # argmin breaks ties on the lowest index
        idx = np.flatnonzero(alive[j])
        return int(ans2g[idx[int(rng.integers(len(idx)))]])


class SingletonRank:
    """Best colour composition by the pooled singleton ranking, ties at random.

    `ranking` is the dict `load_singleton_ranking` returns.  A composition the
    table does not carry ranks LAST and is counted in `.unranked`, so a run can
    report whether that ever happened rather than hiding it.
    """

    name = SRANK
    needs_composition = True

    def __init__(self, guess_letters, ranking):
        self.guess_letters = guess_letters
        self.ranking = ranking
        self.unranked = 0

    def value(self, comp):
        v = self.ranking.get(comp)
        if v is None:
            self.unranked += 1
            return Fraction(-1)          # below any real rate, so it ranks last
        return v

    def choose(self, pat, ans2g, alive, solved, states, played, rng):
        boards = [j for j in range(alive.shape[0]) if not solved[j]]
        vals = [self.value(board_composition(states[j])) for j in boards]
        best = max(vals)
        tied = [j for j, v in zip(boards, vals) if v == best]
        # ALWAYS draw, even with one tied board (where the draw can only return
        # 0).  Consumption then depends on the turn number alone and not on the
        # state, which is what keeps two coupled candidates in step: a rule that
        # skipped the draw when there was no tie would consume a different number
        # of randoms per game and the pairing would decay after the first turn
        # where they disagreed about whether a tie existed.
        j = tied[int(rng.integers(len(tied)))]
        idx = np.flatnonzero(alive[j])
        return int(ans2g[idx[int(rng.integers(len(idx)))]])


class MinAvg:
    """Lexicographically smallest sorted vector of average answers remaining.

    `pool` must be ascending guess indices (the tie-break is "lowest guess
    index", and `lexicographic_argmin` reads it off the column order).

    `turn2` is an optional (N_PATTERNS, len(pool)) table of `a(g)` for a board in
    each of the opener's reply buckets -- the SECOND guess of every game depends
    on the boards only through which bucket each fell in, so the whole table is a
    function of the opener alone and is worth computing once per opener rather
    than once per game.  It is pure memoisation: `multiwordle_fast.turn2_table`
    builds it with the same `average_remaining`, and the gate diffs a run using
    it against a run without.
    """

    name = MINAVG
    needs_composition = False

    def __init__(self, pool, turn2=None):
        self.pool = np.asarray(pool, dtype=np.int64)
        if np.any(np.diff(self.pool) <= 0):
            raise ValueError("the minavg pool must be ascending guess indices")
        self.turn2 = turn2

    def choose(self, pat, ans2g, alive, solved, states, played, rng):
        boards = [j for j in range(alive.shape[0]) if not solved[j]]
        vals = np.empty((len(boards), len(self.pool)), dtype=np.float64)
        for bi, j in enumerate(boards):
            idx = np.flatnonzero(alive[j])
            if self.turn2 is not None and len(played) == 1:
                # every board has seen exactly the opener, so its candidate set
                # IS the opener's bucket, named by the reply any survivor gives
                vals[bi] = self.turn2[int(pat[played[0], idx[0]])]
            else:
                vals[bi] = average_remaining(pat, self.pool, idx)
        return int(self.pool[lexicographic_argmin(vals)])


def make_rule(name, guesses=None, ranking=None, pool=None, turn2=None):
    """Build a rule by name.  Never defaulted by a caller: the name is the
    experiment, and a run whose file does not say which rule produced it is
    ambiguous forever."""
    if name == GREEDY:
        return Greedy()
    if name == SRANK:
        if guesses is None:
            raise ValueError("srank needs the guess list")
        letters = [[ord(c) - 97 for c in w] for w in guesses]
        return SingletonRank(letters, ranking or load_singleton_ranking())
    if name == MINAVG:
        if pool is None:
            raise ValueError("minavg needs a pool of guess indices")
        return MinAvg(pool, turn2)
    raise ValueError("unknown strategy %r (have %s)"
                     % (name, ", ".join(STRATEGIES)))


class CoupledRng:
    """`rng.integers`, but consuming exactly ONE float per decision.

    Wraps a numpy Generator and is passed to `play_game` in place of it, so the
    game code is untouched.  Why it exists: a paired comparison wants two
    candidates to face the same coin flips, and `Generator.integers` consumes a
    VARIABLE number of bits (rejection sampling), so two candidates whose live
    sets differ in size fall out of step after the first differing draw and the
    coupling silently decays.  One float per draw holds them turn for turn.

    It is therefore a DIFFERENT SAMPLER from the bare Generator: a coupled run
    and an uncoupled run at the same seed are two samples of the same quantity
    and will not match.  The default everywhere stays the bare Generator, so
    every committed result reproduces unchanged.
    """

    def __init__(self, gen):
        self.gen = gen

    def integers(self, n):
        return min(int(self.gen.random() * n), n - 1)


def play_game(pat, ans2g, answer_idx, openers_g, rng, rule=None):
    """Play one k-board game under one of the rules above.

    pat        (n_guess, n_answer) pattern matrix
    ans2g      answer index -> guess index (from answer_to_guess)
    answer_idx (k,) ANSWER indices of the hidden words, one per board
    openers_g  GUESS indices of the fixed opening sequence, in play order
    rng        numpy Generator (or CoupledRng); consumed by the rule only
    rule       a rule object, or None for `greedy` -- the default keeps every
               existing caller and every committed result bit-identical

    Returns the list of GUESS indices played, in order.  Its length is the
    game's score.
    """
    if rule is None:
        rule = Greedy()
    k = len(answer_idx)
    na = pat.shape[1]
    alive = np.ones((k, na), dtype=bool)
    solved = np.zeros(k, dtype=bool)
    played = []
    pending = [int(g) for g in openers_g]
    if not pending:
        raise ValueError("the opening sequence is empty")
    states = ([new_composition_state() for _ in range(k)]
              if rule.needs_composition else None)
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
            if states is not None:
                apply_composition(states[j], rule.guess_letters[g], fb)
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

        g = rule.choose(pat, ans2g, alive, solved, states, played, rng)


def draw_answers(na, k, rng):
    """The k hidden answers of one game: answer indices, without replacement."""
    return rng.choice(na, size=k, replace=False)
