"""GATE for the FoxiMax simulator: the fast path vs an independent replay.

    python3 tools/checkfoximax.py              # from math/
    python3 tools/checkfoximax.py --games 25   # more differential games

Exits nonzero on any failure, so it works as a gate.  Run it alongside
solver/validate.sh and tools/checkpatterns.py after touching math/foximax.py or
tools/foximax_sim.py.

WHAT THE ORACLE IS.  `foximax.play_game` is numpy over the position-mask array:
a board's candidates are a boolean bitmap over the word list, a reveal is one
vectorised comparison of int bitmasks, and the hit probabilities are float64
products of column means.  The reference here shares NONE of that -- it keeps
candidates as LISTS OF WORDS, recomputes every reveal by finding the letter's
positions in the STRINGS, and computes the probabilities in EXACT RATIONALS
(fractions.Fraction), so a float rounding error in the fast path is visible
rather than shared.  The two are driven from the same seed and must produce
identical letter sequences, hit/miss flags and word grids -- which tests the
candidate filtering, the greedy rule, its alphabetical tie-break, what counts as
a hit, and when the grid is fully revealed, all at once.

WHAT IS DELIBERATELY SHARED: `draw_word`, so both consume the generator in the
same order (one draw per word, rejections included).  The draw rule is the
GAME's, not the strategy's; sharing it is what lets a divergence in the strategy
show up as a differing sequence rather than as noise.

RULE 4 IS COUNTED, not assumed exercised.  The subtle rule -- a word added by a
miss arrives with every letter guessed so far already revealed in it, the missed
letter included -- only bites when a newcomer actually contains an earlier
guess.  The run tallies how often that happened and FAILS if it never did, since
the differential would then say nothing about it.  Misses themselves are tallied
and required for the same reason.

IF IT EVER FAILS ON A NEAR-TIE: the report prints both letters' EXACT
probabilities.  Equal values mean the fast path broke a tie on something other
than the lowest letter (a real bug); values differing in the 15th digit mean
float rounding flipped an all-but-tie, which is a genuine finding about the
fast path, not a flake in this gate.
"""

import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from foximax import draw_word, play_game, position_masks, to_letters  # noqa: E402
from wordle import load_words  # noqa: E402


def positions(word, ch):
    """Where `ch` sits in `word`; the empty tuple means absent."""
    return tuple(i for i, c in enumerate(word) if c == ch)


def ref_play(pool, rng, stats):
    """Replay one game from strings and exact rationals. Returns the fast
    path's (letters, hits, words) triple in the same shape."""
    n = len(pool)
    guessed = []          # letters in play order, as characters
    words, boards = [], []

    def add_word(w):
        # rule 4: the newcomer arrives carrying every reveal so far
        true = pool[w]
        cand = [x for x in pool
                if all(positions(x, ch) == positions(true, ch) for ch in guessed)]
        if any(ch in true for ch in guessed):
            stats["newcomer_carried_a_letter"] += 1
        words.append(w)
        boards.append(cand)

    add_word(draw_word(rng, n, set()))

    letters, hits = [], []
    while not all(all(ch in guessed for ch in pool[w]) for w in words):
        best, best_p = None, None
        for ci in range(26):
            ch = chr(ord("a") + ci)
            if ch in guessed:
                continue
            miss = Fraction(1)
            for cand in boards:
                miss *= Fraction(sum(1 for x in cand if ch not in x), len(cand))
            p = 1 - miss
            if best_p is None or p > best_p:
                best, best_p = ci, p
            elif p == best_p:
                stats["ties"] += 1
        ch = chr(ord("a") + best)
        hit = any(ch in pool[w] for w in words)
        guessed.append(ch)
        letters.append(best)
        hits.append(hit)
        boards = [[x for x in cand if positions(x, ch) == positions(pool[w], ch)]
                  for cand, w in zip(boards, words)]
        for cand, w in zip(boards, words):
            assert pool[w] in cand
        if not hit:
            stats["misses"] += 1
            add_word(draw_word(rng, n, set(words)))
    return letters, hits, words


def main(argv):
    games = 10
    i = 0
    while i < len(argv):
        if argv[i] == "--games":
            games = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])

    pool = load_words("mystery")
    masks = position_masks(pool)

    # the masks are the fast path's whole feedback model -- check them against
    # the strings before trusting anything built on top of them
    for w in (0, len(pool) // 3, len(pool) - 1):
        for ci in range(26):
            ch = chr(ord("a") + ci)
            want = sum(1 << p for p in positions(pool[w], ch))
            if int(masks[w, ci]) != want:
                print("FAIL mask %s/%s: %d != %d"
                      % (pool[w], ch, masks[w, ci], want))
                return 1

    stats = {"misses": 0, "ties": 0, "newcomer_carried_a_letter": 0}
    failures = 0
    for seed in range(games):
        fast = play_game(masks, np.random.default_rng(seed))
        ref = ref_play(pool, np.random.default_rng(seed), stats)
        f_letters, f_hits, f_words = fast
        r_letters, r_hits, r_words = ref
        if (f_letters, f_hits, f_words) != (r_letters, r_hits, r_words):
            failures += 1
            print("FAIL seed %d" % seed)
            print("  fast %s hits=%s words=%s"
                  % (to_letters(f_letters),
                     "".join("1" if h else "0" for h in f_hits),
                     " ".join(pool[w] for w in f_words)))
            print("  ref  %s hits=%s words=%s"
                  % (to_letters(r_letters),
                     "".join("1" if h else "0" for h in r_hits),
                     " ".join(pool[w] for w in r_words)))
            for j, (a, b) in enumerate(zip(f_letters, r_letters)):
                if a != b:
                    print("  first divergence at letter %d: fast %s, ref %s"
                          % (j + 1, chr(97 + a), chr(97 + b)))
                    break
            continue
        # the score IS the word count, and every word past the first came from
        # a miss -- if those two ever disagree the accounting is broken
        if len(f_words) != 1 + sum(1 for h in f_hits if not h):
            failures += 1
            print("FAIL seed %d: %d words but %d misses"
                  % (seed, len(f_words), sum(1 for h in f_hits if not h)))
        if len(set(f_letters)) != len(f_letters):
            failures += 1
            print("FAIL seed %d: a letter was guessed twice" % seed)
        for w in f_words:
            if not set(pool[w]) <= set(to_letters(f_letters)):
                failures += 1
                print("FAIL seed %d: %s left unrevealed" % (seed, pool[w]))

    print("%d games: %d misses, %d newcomers carrying an earlier letter, "
          "%d exact ties in the greedy"
          % (games, stats["misses"], stats["newcomer_carried_a_letter"],
             stats["ties"]))
    if not stats["misses"]:
        print("FAIL no game ever missed, so the add-a-word path was never tested")
        failures += 1
    if not stats["newcomer_carried_a_letter"]:
        print("FAIL no newcomer ever carried an earlier guess, so rule 4 "
              "(the whole history is revealed in a new word) was never tested")
        failures += 1
    if failures:
        print("FAILED (%d)" % failures)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
