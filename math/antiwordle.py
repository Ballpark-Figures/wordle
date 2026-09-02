"""Antiwordle — the rules as a CONSTRAINT, and the deterministic stalling endgame.

Antiwordle is Wordle with the objective reversed: the word is fixed up front, you
lose the moment you play it, and the score is how many guesses you survived. What
makes it a game rather than "guess junk forever" is that the feedback is BINDING —
every hint you uncover restricts what you are allowed to play next.

THE RULES, as three constraints on the next guess:

    red (= Wordle's green)  the letter is pinned to that square forever
    yellow                  the letter must be REUSED, but never again in the
                            square it was yellow on
    grey                    that COPY of the letter does not exist

THE GREY RULE IS A COUNT CAP, NOT A LETTER BAN, and the distinction is the whole
model.  Wordle marks greens first, then hands out the answer's spare copies of a
letter left to right; a grey tile on letter c therefore means the answer holds
EXACTLY as many c's as that guess showed red or yellow.  So grey sets an UPPER
bound `maxc[c]`.  The familiar "the letter is dead, the keyboard greys it out" is
just the case maxc[c] == 0, which is what a letter with no red or yellow tile
gets.  Reading grey as a flat letter ban instead breaks immediately on a guess
like `stats` against `stack`, where the second t is grey while the first is red.

SO THIS IS HARD MODE'S CONSTRAINT, DUALISED.  optturns' hard mode (see the `Cons`
struct in solver/optturns.c) carries `green[]` plus `minc[]`, a LOWER bound on
each letter's count.  Antiwordle carries the same greens, the same minc (yellow
still means "in the word", so it must be reused), and adds the dual `maxc[]` plus
a per-letter bitmask of squares yellows have burned:

    green[i]  letter pinned to square i, or -1
    minc[c]   at least this many copies          (yellows + reds)
    maxc[c]   at most this many copies           (greys)   -- the dual
    yban[c]   bitmask of squares c may not occupy (yellows) -- the new axis

All four are MONOTONE down a line of play, which is what makes the whole thing
well-founded:

  EVERY LEGAL NON-ANSWER GUESS STRICTLY TIGHTENS THE CONSTRAINT.  Take a legal
  guess g != answer.  Some square i has g[i] != answer[i], so its tile is yellow
  or grey.  If YELLOW on letter c: it adds the ban (c, i), which cannot have been
  there already or g would have been illegal to play.  If GREY on letter c: it
  sets maxc[c] to c's non-grey tile count k in g, but g itself holds at least
  k + 1 copies of c and g was legal, so maxc[c] was at least k + 1 before.
  Strict either way.

  THREE CONSEQUENCES.  (1) The state graph is a DAG, so the search terminates and
  the longest path is well defined.  (2) Replaying a word is ALWAYS illegal unless
  it is the answer, so antiwordle's "you cannot repeat a guess" rule is redundant
  — a UI courtesy, not something to model, and no guess HISTORY belongs in the
  state.  (3) The game is finite: the lattice is finite and every move descends.

THE ANSWER IS ALWAYS LEGAL — its counts sit inside [minc, maxc] by construction,
it has the reds in place, and a yellow on square i means the answer does not have
that letter there.  So play never dead-ends, and the game ends exactly when the
answer is the ONLY legal word left.

WHAT THIS MODULE DOES *NOT* COVER.  The uncertainty phase (several candidates
alive, so the guess partitions them and the objective averages over answers) is a
max-expectimax and is not here.  What IS here is the endgame after the candidate
set collapses to one word: all feedback becomes predictable, every guess has ONE
child, and "play as long as possible" is a LONGEST PATH in the DAG above.  See
`longest_stall`.

WORD LISTS ARE OURS, NOT ANTIWORDLE'S.  Guesses are the 12972 `guess.txt`,
answers the 2315 `mystery.txt` — the original Wordle lists the rest of this video
runs on.  antiwordle.com's dictionary is not ours and is not readable from here,
and the stalling words are exactly the junk (`anana`, `stots`) most likely to
differ, so a stall length computed here is a fact about OUR lists.  The rules
above are likewise transcribed from third-party writeups and have NOT been diffed
against the live game; `tools/checkantiwordle.py` verifies this module against a
brute-force reference, it cannot verify the RULE.

    from antiwordle import CONS_NONE, GuessSpace, step, longest_stall
"""

import numpy as np

from wordle import ALL_GREEN, N_PATTERNS, WORD_LEN, decode

try:                                        # 3.11+, and every venv here is 3.13+
    from typing import NamedTuple
except ImportError:                         # pragma: no cover
    from collections import namedtuple as NamedTuple


class Cons(NamedTuple):
    """The accumulated antiwordle constraint. Immutable, so it doubles as a key.

    Every field is a tuple of small ints, so the whole thing hashes as-is and can
    be used directly as the memo key of the stalling search — there is no
    separate Zobrist step the way optturns needs one for its candidate set.
    """
    green: tuple            # WORD_LEN entries: letter 0..25 pinned there, or -1
    minc: tuple             # 26 entries: at least this many copies
    maxc: tuple             # 26 entries: at most this many copies
    yban: tuple             # 26 entries: bitmask of squares this letter may not use


def cons_none(word_len=WORD_LEN):
    """"Nothing known yet": no pins, no floors, every ceiling at the word length."""
    return Cons(green=(-1,) * word_len,
                minc=(0,) * 26,
                maxc=(word_len,) * 26,
                yban=(0,) * 26)


CONS_NONE = cons_none()

# decode() per call would dominate the search; 243 codes is a trivial table.
TRITS = tuple(decode(code) for code in range(N_PATTERNS))


def step(cons, letters, trits):
    """Fold one guess's feedback into the constraint.

    `letters` is the guess as WORD_LEN letter codes (0..25), `trits` its feedback
    as WORD_LEN tile codes (0 grey / 1 yellow / 2 green) — both precomputed by
    `GuessSpace`, because this is the search's innermost operation.

    A guess mentions at most WORD_LEN distinct letters, so only that many of the
    26-wide fields can move; the rest are copied through untouched.
    """
    green = list(cons.green)
    minc = list(cons.minc)
    maxc = list(cons.maxc)
    yban = list(cons.yban)

    req = {}                                  # reds + yellows of each letter
    greys = set()                             # letters with at least one grey tile
    for i, (c, t) in enumerate(zip(letters, trits)):
        if t == 2:
            green[i] = c
            req[c] = req.get(c, 0) + 1
        elif t == 1:
            req[c] = req.get(c, 0) + 1
            yban[c] |= 1 << i
        else:
            greys.add(c)

    for c, k in req.items():                  # yellows/reds raise the floor
        if k > minc[c]:
            minc[c] = k
    for c in greys:                           # a grey tile PINS the count exactly
        k = req.get(c, 0)
        if k < maxc[c]:
            maxc[c] = k

    return Cons(tuple(green), tuple(minc), tuple(maxc), tuple(yban))


def legal(cons, word):
    """Scalar legality of one word under `cons` — the readable reference.

    The search uses `GuessSpace.legal_mask` instead, which is this predicate
    vectorized over a whole word list; `tools/checkantiwordle.py` diffs the two.
    """
    for i, c in enumerate(cons.green):
        if c >= 0 and ord(word[i]) - 97 != c:
            return False
    cnt = [0] * 26
    for i, ch in enumerate(word):
        c = ord(ch) - 97
        cnt[c] += 1
        if cons.yban[c] >> i & 1:
            return False
    for c in range(26):
        if cnt[c] < cons.minc[c] or cnt[c] > cons.maxc[c]:
            return False
    return True


class GuessSpace:
    """A word list plus the bitsets `legal_mask` intersects — built once.

    The same trick optturns uses (`BS_POS` / `BS_CNT` in solver/optturns.c), with
    numpy boolean arrays standing in for the 64-bit words: legality is an
    intersection of precomputed membership sets, so a constraint expands to its
    legal list without ever touching a word's letters again.
    """

    def __init__(self, words, word_len=WORD_LEN):
        self.words = list(words)
        self.word_len = word_len
        self.n = len(self.words)
        self.index = {w: i for i, w in enumerate(self.words)}

        self.letters = np.array([[ord(ch) - 97 for ch in w] for w in self.words],
                                dtype=np.int8)
        self.letter_tuples = [tuple(int(x) for x in row) for row in self.letters]

        # pos[i, c] — words with letter c in square i
        self.pos = np.zeros((word_len, 26, self.n), dtype=bool)
        for i in range(word_len):
            for c in range(26):
                self.pos[i, c] = self.letters[:, i] == c
        # cnt[c, k] — words with AT LEAST k copies of c (k = 0 is everything)
        self.cnt = np.zeros((26, word_len + 1, self.n), dtype=bool)
        counts = np.zeros((self.n, 26), dtype=np.int8)
        for c in range(26):
            counts[:, c] = (self.letters == c).sum(axis=1)
            for k in range(word_len + 1):
                self.cnt[c, k] = counts[:, c] >= k
        self.counts = counts

    def legal_mask(self, cons):
        """Boolean mask over the word list of everything `cons` permits."""
        m = np.ones(self.n, dtype=bool)
        for i, c in enumerate(cons.green):
            if c >= 0:
                m &= self.pos[i, c]
        for c in range(26):
            k = cons.minc[c]
            if k:
                m &= self.cnt[c, k]
            mx = cons.maxc[c]
            if mx < self.word_len:
                m &= ~self.cnt[c, mx + 1]
            yb = cons.yban[c]
            if yb:
                for i in range(self.word_len):
                    if yb >> i & 1:
                        m &= ~self.pos[i, c]
        return m

    def legal_list(self, cons):
        """The permitted words as ascending indices."""
        return np.flatnonzero(self.legal_mask(cons))

    def count_legal_delta(self, parent, child, idx):
        """How many of `idx` stay legal under `child`, given all satisfy `parent`.

        The child's legal set is a SUBSET of the parent's — legality only tightens
        — so counting it means re-testing the parent's survivors against the few
        fields the move actually moved, not testing 12972 words against 26 letters.
        A guess touches at most WORD_LEN distinct letters, so this is a handful of
        masked comparisons over a set that is usually tiny.

        That cheapness is the whole point: it makes the WORD BOUND affordable per
        child, and the word bound is the one that discriminates between a move
        that keeps the game alive and one that ends it.
        """
        m = np.ones(len(idx), dtype=bool)
        for i, c in enumerate(child.green):
            if c >= 0 and parent.green[i] < 0:
                m &= self.pos[i, c][idx]
        for c in range(26):
            k = child.minc[c]
            if k > parent.minc[c]:
                m &= self.cnt[c, k][idx]
            mx = child.maxc[c]
            if mx < parent.maxc[c]:
                m &= ~self.cnt[c, mx + 1][idx]
            new = child.yban[c] & ~parent.yban[c]
            if new:
                for i in range(self.word_len):
                    if new >> i & 1:
                        m &= ~self.pos[i, c][idx]
        return int(m.sum())


class StallSearch:
    """Longest legal chain of guesses before a KNOWN answer must be named.

    Once the candidate set is a single word the game stops being probabilistic:
    the feedback for every guess is already determined, so each guess has exactly
    ONE child and "survive as long as possible" is a longest path over the
    constraint DAG.  Memoised on the constraint itself, which is both correct (the
    value depends on nothing else — no candidate set, no history) and where much
    of the speed comes from: thousands of guesses collapse onto far fewer distinct
    children, anagrams first among them.

    `value(cons)` counts the guesses REMAINING, including the forced final play of
    the answer, so a state whose only legal word is the answer is worth 1.

    TWO UPPER BOUNDS PRUNE IT, both falling out of the monotonicity proof at the
    top of this module, and the search takes whichever is smaller.

      THE WORD BOUND, |L|.  Legality only ever tightens, so every word played from
      here on is legal NOW; and a played word is never legal again, so they are
      all distinct.  The game therefore cannot outlast the current legal set.
      Exactly tight in an endgame where the legal words do not interfere — `?ummy`
      against `mummy`, where you really do get to play all of them.

      THE RESOURCE BOUND, the one that does the work up top.  |L| says "you cannot
      outlast 12972 words", which prunes nothing at the start of a game.  But every
      legal non-answer guess must spend something FINITE: it has a tile that is
      yellow (adding a square to that letter's ban mask — necessarily a new one, or
      the guess was illegal) or grey (pinning that letter's count, which can happen
      only ONCE per letter, since a grey tile sets maxc to the true count exactly).
      So count the units still unspent — letters not yet count-pinned, plus squares
      not yet banned for the answer's own letters — and no line can be longer than
      that, plus the final naming move.  At an empty board that is about 50 rather
      than 12972.

      Both are ADMISSIBLE (never below the truth), so pruning a child whose bound
      cannot beat the incumbent leaves the value EXACT — no window is passed down
      and nothing memoised is a bound, which is what keeps the table reusable.

    The resource bound is maintained by DELTA rather than recomputed: a move spends
    one unit per distinct grey letter plus one per yellow tile, both read straight
    off the five tiles.  That per-move count is also the strict-tightening proof in
    executable form — it is at least 1 for every non-answer guess.

    THE MEMO IS KEYED TWICE, AND THE SECOND KEY IS THE LEGAL SET, NOT THE
    CONSTRAINT.  The constraint is the obvious key and it is a poor one: many
    different constraints permit exactly the same words, and keyed that way each is
    searched again from scratch.

      WHY THE LEGAL SET SUFFICES.  Playing g turns the constraint C into C and D(g),
      where D(g) — the greens, ban bits and count caps that guess's feedback
      imposes — depends only on (g, pattern(g, answer)) and NOT on C.  A word w
      already legal under C is legal under C and D(g) exactly when it satisfies
      D(g): every field is a conjunction (floors take a max, ceilings a min, ban
      masks a union, and two greens on one square must agree, both being the
      answer's letter there).  So the child's legal set is {w in L : w satisfies
      D(g)} — a function of L and g alone.  By induction the whole future, and
      therefore the VALUE, is a function of L alone.

      SO TWO LAYERS.  The constraint key is checked first because it is free; on a
      miss the legal set is packed to bytes and checked, and a hit there is written
      back to the constraint key so the same state stays cheap next time.  Set
      `set_memo=False` to key on the constraint only, which is what the gate diffs
      against — the theorem above is exactly the claim that this changes no value.
    """

    def __init__(self, space, pat_col, answer_index, prune=True, set_memo=True):
        self.space = space
        self.pat_col = pat_col              # pattern of every word vs this answer
        self.answer = answer_index          # its index in `space`
        # prune=False disables both bounds, leaving the exhaustive search they
        # replaced. Kept as the ORACLE: a bound is admissible iff turning it off
        # cannot change an answer, and tools/checkantiwordle.py diffs the two.
        self.prune = prune
        self.set_memo = set_memo
        self.memo = {}                      # constraint -> (value, move)
        self.by_set = {}                    # packed legal set -> (value, move)
        self.nodes = 0                      # states expanded (both memos missed)
        self.edges = 0                      # child constraints recursed into
        self.pruned = 0                     # children a bound ruled out unexplored
        self.set_hits = 0                   # states the legal-set key alone caught

        self.answer_letters = space.letter_tuples[answer_index]
        self.acount = [0] * 26
        for c in self.answer_letters:
            self.acount[c] += 1

    def resource_pool(self, cons):
        """Units of tightening still unspent — the resource bound, minus the +1.

        Full recomputation, used once per entry point; inside the search the count
        travels by delta.
        """
        pool = 0
        for c in range(26):
            if cons.maxc[c] > self.acount[c]:
                pool += 1                   # this letter's count is still unpinned
        for i, c in enumerate(self.answer_letters):
            for c2 in range(26):
                if (self.acount[c2] and c2 != c
                        and not (cons.yban[c2] >> i & 1)):
                    pool += 1               # square i still open to a yellow c2
        return pool

    def children(self, cons, pool, legal):
        """Distinct one-move successors, best-bound first.

        Deduplicating here rather than recursing per word is the difference
        between a hopeless search and a feasible one: every guess that leaves the
        same constraint leaves the same future, and at the top of the game a great
        many do.  Each child keeps one witness word, so a line can be recovered.

        Returns (bound, child, witness, child_pool) tuples sorted by DESCENDING
        bound, which lets `value` stop at the first child that cannot beat the
        incumbent — every one after it is worse.
        """
        out = {}
        letters, pat, trits = self.space.letter_tuples, self.pat_col, TRITS
        for g in legal:
            g = int(g)
            if g == self.answer:
                continue
            gl = trits[pat[g]]
            spent = 0                       # units this move costs -- always >= 1
            greys = set()
            for i, t in enumerate(gl):
                if t == 1:
                    spent += 1              # a yellow always bans a NEW square
                elif t == 0:
                    greys.add(letters[g][i])
            spent += len(greys)             # each grey letter pins a count, once
            child = step(cons, letters[g], gl)
            if child not in out:
                out[child] = (g, pool - spent)

        # Score each DISTINCT child by both bounds and keep the smaller. The word
        # bound is what separates a move that leaves the game alive from one that
        # strangles it; the resource bound is nearly flat this deep and would rank
        # them all the same. Descending, so `value` can stop at the first child
        # that cannot beat its incumbent.
        scored = []
        for child, (g, cpool) in out.items():
            words = self.space.count_legal_delta(cons, child, legal)
            scored.append((min(cpool + 1, words), child, g, cpool))
        scored.sort(key=lambda t: -t[0])
        return scored

    def value(self, cons, pool=None):
        hit = self.memo.get(cons)
        if hit is not None:
            return hit[0]

        mask = self.space.legal_mask(cons)
        key = None
        if self.set_memo:
            key = np.packbits(mask).tobytes()
            hit = self.by_set.get(key)
            if hit is not None:                # same words permitted, same future
                self.memo[cons] = hit
                self.set_hits += 1
                return hit[0]

        if pool is None:
            pool = self.resource_pool(cons)
        self.nodes += 1

        legal = np.flatnonzero(mask)
        ceiling = min(len(legal), pool + 1)   # nothing here can beat this
        if not self.prune:
            ceiling = len(legal) + 1          # unreachable: every branch explored

        best, best_move = 1, None             # name the answer now and be done
        if best < ceiling:
            for bound, child, g, cpool in self.children(cons, pool, legal):
                if self.prune and 1 + bound <= best:
                    self.pruned += 1          # sorted desc: the rest are no better
                    break
                self.edges += 1
                v = 1 + self.value(child, cpool)
                if v > best:
                    best, best_move = v, g
                    if best >= ceiling:
                        break                 # hit the ceiling; nothing can beat it
        self.memo[cons] = (best, best_move)
        if key is not None:
            self.by_set[key] = (best, best_move)
        return best

    def line(self, cons):
        """One optimal stalling line as words, ending with the answer."""
        out = []
        while True:
            self.value(cons)
            _, g = self.memo[cons]
            if g is None:
                out.append(self.space.words[self.answer])
                return out
            out.append(self.space.words[g])
            cons = step(cons, self.space.letter_tuples[g],
                        TRITS[self.pat_col[g]])


def longest_stall(space, pat_col, answer_index, cons=None):
    """Longest surviving play against a KNOWN answer: (guesses, line, search).

    `pat_col[g]` must be the pattern word `g` scores against this answer — a
    COLUMN of the pattern matrix, which is exactly how the caller should get it.
    Returns the guess count (including the final forced naming), one optimal line,
    and the search object, whose `.nodes` / `.edges` price the run.
    """
    if cons is None:
        cons = cons_none(space.word_len)
    search = StallSearch(space, pat_col, answer_index)
    total = search.value(cons)
    return total, search.line(cons), search


def replay_prefix(space, pat_col, words, cons=None):
    """Apply already-played words, REFUSING any that were not legal to play.

    An illegal prefix names a state no game can reach: if `sulky` turned a letter
    yellow, a follow-up without that letter was never a legal move, and searching
    onward from it answers a question about a position that cannot occur. The
    search would still be exact there, which is exactly why this has to raise
    rather than warn — a wrong number is obvious, a right number about the wrong
    position is not.

    Shared by `tools/antiwordle_stall.py` and the C port's gate so the two agree
    on which prefixes exist; `solver/antistall` enforces the same rule.
    """
    cons = cons_none(space.word_len) if cons is None else cons
    for w in words:
        if w not in space.index:
            raise ValueError("%s is not a legal guess" % w)
        if not legal(cons, w):
            raise ValueError("%s is not legal at that point in the line" % w)
        gi = space.index[w]
        cons = step(cons, space.letter_tuples[gi], TRITS[int(pat_col[gi])])
    return cons


def replay(space, cons, words, answers_of):
    """Walk a transcript, returning the constraint after each guess.

    `answers_of(word)` gives that guess's feedback code. Used by the check tool
    and by anything replaying a real antiwordle game against this model.
    """
    out = []
    for w in words:
        gi = space.index[w]
        cons = step(cons, space.letter_tuples[gi], TRITS[answers_of(w)])
        out.append(cons)
    return out


def show(code, word_len=WORD_LEN):
    """Render a pattern code as tiles, grey `.` / yellow `y` / red `R`."""
    return "".join(".yR"[t] for t in decode(code, word_len))


__all__ = ["ALL_GREEN", "CONS_NONE", "Cons", "GuessSpace", "StallSearch",
           "cons_none", "legal", "longest_stall", "replay", "show", "step"]
