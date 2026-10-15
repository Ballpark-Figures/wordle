"""Wrongle -- the rule and the two value functions stated exactly, plus a slow reference.

THE GAME.  Wrongle (an App Store game, "Wordle where more is more") reverses
Wordle: the player wants the game to go ON.  Every guess must FOLLOW THE FEEDBACK
received so far -- it has to be a word the answer could still be -- and the
"Wrongler Trophy" goes to a game reaching 6+ guesses.  That is the real game's
framing; the two objectives below are OURS (the user's, 2026-10-14), and so are
the word lists.

LEGALITY ("compatible", the user's call): a guess is legal iff it is one of the
12972 legal guess words AND it is CONSISTENT with every clue so far --
`pattern(g_i, w) == p_i` for every earlier (guess, reply).  That is ultraturns'
legality, NOT eldrowmax's: the guess pool is the 12972, so a word that is not in
the 2315 answer list may still be played as long as it fits the clues.  The
answer itself is drawn uniformly from the 2315, and since it fits every clue by
definition it is always among the legal words.

THE STATE IS THE SET OF LEGAL WORDS, L, and nothing else.  The legal set after a
history is the intersection of one filter per clue, so the legal set after one
more clue is just L filtered by it: everything a continuation depends on -- the
words it may play, the answers still possible (L restricted to the answer list),
the feedback each produces -- is a function of L.  The reference below does NOT
lean on that: it recomputes the legal set FROM THE STRINGS, from the whole guess
list, at every step, and memoises only on the result.

TERMINATION.  `pattern(g, g)` is all green, so a played word is in its own
all-green bucket and in no other: every surviving child EXCLUDES it.  The legal
set strictly shrinks, so every game ends -- the answer is always legal, and a
legal set of one word is the answer, which must then be played.

TWO OBJECTIVES, AND THEY ARE DIFFERENT QUANTITIES.  Never table them together,
and never beside an optturns-family total (those MINIMISE).

  LOSE (`--objective lose --depth D`) -- the one first asked for:

      MAXIMISE the number of the 2315 answers NOT FOUND within D guesses.

      lose(L, d) = |A_L|                                   if d == 0
                 = 0                                       if |L| <= d
                 = max over g in L of
                     sum over p != all-green of lose(L_p, d - 1)

      where A_L is L restricted to the answers and L_p the words of L giving
      feedback p to g.  An answer that IS g is won on that guess and contributes
      nothing.  `|L| <= d` is exact, not a heuristic: each guess removes at least
      the word played and the answer is never removed, so with at most d words
      legal the answer is reached within d guesses whatever is played.

      D IS PART OF THE OBJECTIVE.  6 is "lose the Wordle", 5 is "reach the
      trophy" (not found in 5 means a 6th guess); each depth gets its own file.

  EXPECT (`--objective expect`) -- UNCAPPED: maximise the EXPECTED number of
  guesses, reported as the integer TOTAL over the 2315 answers:

      total(L) = |A_L| + max over g in L of sum over p != all-green of total(L_p)

      Every answer still possible pays for this guess; those that were g stop.
      No cap, no depth flag -- play always ends (see TERMINATION).

  Children holding no answer are never reached and contribute 0 under both.

THE BEAM (`topk`).  Restrict every node -- THE ROOT INCLUDED -- to the K legal
guesses with the LARGEST expected number of answers remaining, i.e. the largest
sum over feedback bins of (answers in that bin)^2, every bin counted (the
all-green one included), ties on the LOWEST guess-list index.  It is the repo's
ranking rule turned upside down, as asked: maximise words remaining rather than
minimise them.  Every value it returns is ACHIEVABLE, so it is a LOWER bound on
the true maximum and the opener is the best of the K examined, never "the best
opener".  K = 0 is the exact search.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wordle import ALL_GREEN, pattern  # noqa: E402


def legal_words(guesses, history):
    """Every guess word consistent with every (guess, reply) in `history`,
    recomputed from the strings -- no incremental filtering."""
    return tuple(w for w in guesses
                 if all(pattern(g, w) == p for g, p in history))


def ranked(legal, answers):
    """Legal words, beam order: most answers remaining first, ties on the lowest
    guess-list index (`legal` is in guess-list order)."""
    poss = [w for w in legal if w in answers]
    def ssq(g):
        bins = {}
        for a in poss:
            p = pattern(g, a)
            bins[p] = bins.get(p, 0) + 1
        return sum(n * n for n in bins.values())
    keyed = [(-ssq(g), i, g) for i, g in enumerate(legal)]
    keyed.sort()
    return [g for _, _, g in keyed]


class Game:
    """One (guess list, answer list) problem.  `guesses` is the GUESS-LIST ORDER,
    which is what ties break on."""

    def __init__(self, guesses, answers):
        self.guesses = list(guesses)
        self.answers = frozenset(answers)
        missing = [a for a in answers if a not in set(self.guesses)]
        if missing:
            raise ValueError("answers not in the guess list: %s" % missing[:5])
        self._memo = {}

    def _moves(self, legal, topk):
        if topk:
            return ranked(legal, self.answers)[:topk]
        return list(legal)

    def lose(self, history, depth, topk=0):
        """Answers lost from this position with `depth` guesses left."""
        legal = legal_words(self.guesses, history)
        return self._lose(legal, history, depth, topk)

    def _lose(self, legal, history, depth, topk):
        key = ("lose", legal, depth, topk)
        if key in self._memo:
            return self._memo[key]
        poss = [w for w in legal if w in self.answers]
        if not poss:
            v = 0
        elif depth == 0:
            v = len(poss)
        elif len(legal) <= depth:
            v = 0
        else:
            v = max(self.lose_after(history, g, depth, topk, legal)
                    for g in self._moves(legal, topk))
        self._memo[key] = v
        return v

    def lose_after(self, history, g, depth, topk=0, legal=None):
        """Answers lost if `g` is played now with `depth` guesses left."""
        if legal is None:
            legal = legal_words(self.guesses, history)
        replies = sorted({pattern(g, a) for a in legal if a in self.answers})
        tot = 0
        for p in replies:
            if p == ALL_GREEN:
                continue
            h = history + ((g, p),)
            tot += self._lose(legal_words(self.guesses, h), h, depth - 1, topk)
        return tot

    def total(self, history, topk=0):
        """Total guesses over the answers still possible, uncapped."""
        legal = legal_words(self.guesses, history)
        return self._total(legal, history, topk)

    def _total(self, legal, history, topk):
        key = ("total", legal, topk)
        if key in self._memo:
            return self._memo[key]
        poss = [w for w in legal if w in self.answers]
        if not poss:
            v = 0
        else:
            v = len(poss) + max(self.total_after(history, g, topk, legal)
                                for g in self._moves(legal, topk))
        self._memo[key] = v
        return v

    def total_after(self, history, g, topk=0, legal=None):
        """Guesses AFTER `g`, summed over the answers g does not win."""
        if legal is None:
            legal = legal_words(self.guesses, history)
        replies = sorted({pattern(g, a) for a in legal if a in self.answers})
        tot = 0
        for p in replies:
            if p == ALL_GREEN:
                continue
            h = history + ((g, p),)
            tot += self._total(legal_words(self.guesses, h), h, topk)
        return tot

    def opener_value(self, objective, g, depth=None, topk=0):
        """The value of opening with g -- what the C reports per opener."""
        if objective == "lose":
            return self.lose_after((), g, depth, topk)
        return len(self.answers) + self.total_after((), g, topk)

    def openers(self, topk=0):
        """The openers the run examines: every guess, or the beam's K best."""
        return self._moves(tuple(self.guesses), topk)
