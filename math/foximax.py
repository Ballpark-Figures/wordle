"""FoxiMax: hangman-style letter guessing where every MISS adds another word.

THE GAME (foximax.com), stated exactly, because the details drive everything:

  1. One hidden word is in play at the start.  A turn guesses a LETTER, never a
     word, and no letter may be guessed twice.
  2. The guess is a HIT if the letter appears in AT LEAST ONE of the words
     currently in play.  A hit reveals every position that letter occupies in
     EVERY word in play -- so each word also learns the letter is absent from it
     when it is.
  3. The guess is a MISS if the letter appears in NONE of the words in play.  A
     miss adds ONE new word to the grid, drawn from the same list.
  4. When a new word arrives, EVERY letter guessed so far is immediately shown
     in it wherever it occurs -- hits and previous misses alike.  A "miss" was
     therefore only ever a statement about the words in play AT THAT MOMENT: a
     letter missed on turn 3 may well sit inside the word turn 3 brought in.
  5. The game ends when every word in play is fully revealed.  The SCORE is the
     NUMBER OF WORDS on the grid, which is 1 + the number of misses -- fewer is
     better.

  THE REAL GAME CAPS THE GRID AT EIGHT WORDS AND THAT IS NOT MODELLED HERE
  (the user's call, 2026-09-02).  Play always runs to completion, so every game
  yields a word count and no game is ever a loss.  A run's losing fraction on
  the real site is recoverable after the fact -- it is the fraction of games
  scoring more than 8 -- but nothing here computes or reports it.

  THE WORD LIST IS OURS, NOT FOXIMAX'S.  Hidden words are drawn from
  data/shared/words/mystery.txt (the 2315 NYT answers), the list every other
  sweep in this video uses; the real site's list is unknown to us and its daily
  puzzles are not random draws.  So a number from here describes THIS game on
  THIS list, and is not a prediction about foximax.com.

TERMINATION NEEDS NO CAP.  Every turn spends a distinct letter, so after at
most 26 turns every letter of every word has been guessed and the grid is fully
revealed.  ``play_game`` asserts that bound rather than imposing one.

THE STRATEGY IMPLEMENTED HERE -- greedy, one step, no search:

  Guess the unguessed letter with the highest probability of being a HIT, i.e.
  of appearing in AT LEAST ONE of the words in play.  Each board is modelled as
  uniform over its own remaining candidates and the boards are treated as
  independent, so for letter c

      P(hit) = 1 - prod_over_boards ( 1 - fraction of that board's
                                          candidates containing c )

  Ties break on the lowest letter (alphabetical).  It is a heuristic: it
  maximises the chance of avoiding a new word THIS turn and looks no further --
  nothing here searches, and no claim is made that it minimises anything.

  A BOARD'S CANDIDATES are the words consistent with everything seen about it:
  for each guessed letter, the exact SET OF POSITIONS that letter occupies in
  that word (the empty set meaning "absent from this word").  Because rule 4
  reveals the whole history in a newly added word, every board carries the full
  positional record of every letter guessed so far -- newcomers included.

  THE INDEPENDENCE IS AN APPROXIMATION, deliberately.  The hidden words are
  drawn WITHOUT replacement, so a word already identified on one board cannot be
  another board's answer, and the boards are very slightly dependent.  The
  strategy ignores that; it is a heuristic being measured, not an optimum being
  computed.

THE STRATEGY IS DETERMINISTIC.  Given the sequence of words the game deals, the
letters played are fixed -- the rng is consumed only by the draws.  So a game's
score is a function of its word sequence alone.
"""

import numpy as np

ALPHABET = 26


def position_masks(words):
    """(n_words, 26) int32 bitmaps: bit p of [w][c] set iff word w has c at p.

    This is the whole feedback model of the game in one array.  A guessed letter
    c splits the pool by ``masks[:, c]``, and two words are indistinguishable to
    a board iff their masks agree on every letter guessed so far -- so filtering
    is one vectorised comparison per turn, with no per-position work.
    """
    masks = np.zeros((len(words), ALPHABET), dtype=np.int32)
    for i, word in enumerate(words):
        for pos, ch in enumerate(word):
            masks[i, ord(ch) - ord("a")] |= 1 << pos
    return masks


def draw_word(rng, n, taken):
    """A hidden word index drawn uniformly from the pool, excluding `taken`.

    Rejection rather than a shuffle so the generator is consumed one draw per
    word in a fixed order, which is what lets an independent replay follow the
    same seed exactly (tools/checkfoximax.py relies on it).
    """
    w = int(rng.integers(n))
    while w in taken:
        w = int(rng.integers(n))
    return w


def hit_probabilities(contains, alive, guessed):
    """P(letter is a hit) for all 26 letters; already-guessed letters give -1.

    contains  (n_words, 26) bool, ``position_masks(...) != 0``
    alive     list of (n_words,) bool candidate bitmaps, one per board
    guessed   (26,) bool, letters already spent
    """
    miss = np.ones(ALPHABET, dtype=np.float64)
    for board in alive:
        miss *= 1.0 - contains[board].mean(axis=0)
    p = 1.0 - miss
    p[guessed] = -1.0
    return p


def play_game(masks, rng, first=None):
    """Play one game under the greedy strategy above.

    masks  (n_words, 26) from position_masks over the hidden-word pool
    rng    numpy Generator; consumed once per DRAW (rejections included)
    first  optional index of the opening word, for a reproducible single game;
           drawn like any other when omitted

    Returns (letters, hits, words): the letter indices played in order, a bool
    per letter saying whether it hit, and the word indices in play at the end in
    the order they arrived.  ``len(words)`` is the score, and equals
    ``1 + misses``.
    """
    n = len(masks)
    contains = masks != 0
    guessed = np.zeros(ALPHABET, dtype=bool)
    words, alive = [], []
    letters, hits = [], []

    def add_word(w):
        # Rule 4: every letter guessed so far is revealed in the newcomer, so it
        # arrives already carrying the full history rather than a clean slate.
        board = np.ones(n, dtype=bool)
        for c in np.flatnonzero(guessed):
            board &= masks[:, c] == masks[w, c]
        assert board[w], "the true word must survive its own reveals"
        words.append(w)
        alive.append(board)

    add_word(draw_word(rng, n, set()) if first is None else int(first))

    def all_revealed():
        return all(guessed[contains[w]].all() for w in words)

    while not all_revealed():
        p = hit_probabilities(contains, alive, guessed)
        c = int(p.argmax())              # argmax breaks ties on the lowest letter
        assert p[c] > 0.0, "an unrevealed grid must leave some letter reachable"
        hit = any(masks[w, c] for w in words)
        guessed[c] = True
        letters.append(c)
        hits.append(hit)
        # every board learns exactly where c sits in its own word, absent or not
        for j, w in enumerate(words):
            alive[j] &= masks[:, c] == masks[w, c]
            assert alive[j][w]
        if not hit:
            add_word(draw_word(rng, n, set(words)))
        # 26 distinct letters reveal everything; more means the loop is stuck
        assert len(letters) <= ALPHABET, "game ran past 26 letters"

    return letters, hits, words


def to_letters(idx):
    """Letter indices back to a string, for output and logging."""
    return "".join(chr(ord("a") + int(c)) for c in idx)
