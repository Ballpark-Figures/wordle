"""Antiwordle under RANDOM play — the game model for the opener simulation.

THE EXPERIMENT.  Fix an opening word.  Draw a hidden answer uniformly from the 2315
mystery words.  Play the opener, then keep playing words chosen UNIFORMLY AT RANDOM
from whatever is still legal, until the answer is played.  The score is the number
of guesses, INCLUDING the one that lands on the answer.  Average that over many
random games and you have a per-opener figure; the sweep in
`tools/antiwordle_sim_run.py` does that for every legal opener.

THE PLAYER KNOWS NOTHING.  It does not know the answer, and it does not consult the
answer list — every legal word is equally likely, so it can and does END THE GAME BY
LUCK by stumbling onto the answer.  That is deliberate (chosen 2026-09-04): it is the
plain reading of "random play", and it is a floor, not a strategy.  Two consequences
worth stating before anyone reads a number:

  - These averages are far SHORTER than skilled play.  A real player deliberately
    guesses words that cannot be the answer, which is the whole skill of antiwordle;
    this one does not.  Nor is it comparable to `antistall`, which is clairvoyant and
    reports the LONGEST game an answer admits.  Random play sits below real play,
    which sits below the clairvoyant maximum.
  - It ranks openers by how well they survive random continuation, which is a proxy
    for "keeps the legal set big", not a proof about optimal play.  A better opener
    under this measure is a HYPOTHESIS about the real game, to be checked, never a
    result about it.

WHY THE GAME ALWAYS ENDS.  Every legal non-answer guess strictly tightens the
constraint (proved in `antiwordle.py`), so the legal set shrinks every turn; and the
answer is always legal, so there is always something to play.  No guess cap is needed
and none is imposed.

THE LEGAL SET IS UPDATED INCREMENTALLY, which is what makes the sweep affordable.
Playing g with feedback p turns the legal set L into L & D(g, p), where D depends
only on (g, p) and never on the constraint accumulated so far — the same fact the C
solver is built on.  So this file never carries a `Cons` at all; it intersects masks.
`tools/checkantiwordlesim.py` checks that against `antiwordle.legal_mask` composed
with `step`, which is the audited path.

WORD LISTS ARE OURS: openers and every later guess come from the 12972 `guess.txt`,
answers from the 2315 `mystery.txt`.  antiwordle.com's dictionary is not ours, so a
number here is a fact about OUR lists.

    from antiwordle_sim import delta_mask, play_random_game, simulate_opener
"""

import numpy as np

from antiwordle import TRITS
from wordle import ALL_GREEN, WORD_LEN


def delta_mask(space, gi, code, out=None):
    """Words permitted by ONE guess's feedback, as a boolean mask.

    `D(g, p)` from the module docstring: greens pin their square, revealed counts
    are a floor, a grey tile caps that letter's count exactly, and a yellow bans its
    own square. Depends only on (guess, feedback) — never on what came before — so
    intersecting these is the whole state update.
    """
    letters = space.letter_tuples[gi]
    trits = TRITS[code]
    m = np.ones(space.n, dtype=bool) if out is None else out
    if out is not None:
        m.fill(True)

    req = [0] * 26
    grey = [False] * 26
    for i in range(space.word_len):
        c, t = letters[i], trits[i]
        if t == 2:
            m &= space.pos[i, c]
            req[c] += 1
        elif t == 1:
            m &= ~space.pos[i, c]
            req[c] += 1
        else:
            grey[c] = True
    for c in range(26):
        if req[c]:
            m &= space.cnt[c, req[c]]
        if grey[c]:
            m &= ~space.cnt[c, req[c] + 1]
    return m


def play_random_game(space, pat, answer_ai, opener_gi, rng, opener_cache=None):
    """One random game. Returns (guesses, ended_on_opener).

    `pat` is the full 12972 x 2315 pattern matrix; `answer_ai` indexes its columns.
    `opener_cache` maps a feedback code to the opener's already-computed mask, which
    is worth caching because every trial for this opener starts by applying it.
    """
    code = int(pat[opener_gi, answer_ai])
    if code == ALL_GREEN:                 # the opener WAS the answer
        return 1, True

    if opener_cache is None:
        legal = delta_mask(space, opener_gi, code).copy()
    else:
        cached = opener_cache.get(code)
        if cached is None:
            cached = delta_mask(space, opener_gi, code)
            opener_cache[code] = cached
        legal = cached.copy()

    guesses = 1
    while True:
        idx = np.flatnonzero(legal)
        # The answer is always legal, so this is never empty.
        g = int(idx[rng.integers(len(idx))])
        guesses += 1
        code = int(pat[g, answer_ai])
        if code == ALL_GREEN:
            return guesses, False
        legal &= delta_mask(space, g, code)


def simulate_opener(space, pat, opener_gi, trials, rng, n_answers):
    """`trials` random games for one opener: (mean, stderr, min, max, lucky).

    `lucky` counts games the opener itself ended, which is worth reporting
    separately: an opener that is a common answer wins by accident more often, and
    that drags its mean down for a reason that has nothing to do with stalling.
    """
    lengths = np.empty(trials, dtype=np.int32)
    cache = {}
    lucky = 0
    for t in range(trials):
        ai = int(rng.integers(n_answers))
        n, on_opener = play_random_game(space, pat, ai, opener_gi, rng, cache)
        lengths[t] = n
        lucky += on_opener
    mean = float(lengths.mean())
    # Standard error of the mean -- this is a Monte Carlo estimate, and two openers
    # closer together than a couple of SEs have not been shown to differ.
    se = float(lengths.std(ddof=1) / np.sqrt(trials)) if trials > 1 else float("nan")
    return mean, se, int(lengths.min()), int(lengths.max()), lucky


__all__ = ["ALL_GREEN", "WORD_LEN", "delta_mask", "play_random_game",
           "simulate_opener"]
