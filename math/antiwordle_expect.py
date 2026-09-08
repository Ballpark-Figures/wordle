"""Antiwordle: maximise EXPECTED turns — the reference implementation.

A DIFFERENT OBJECTIVE from everything else in this repo's antiwordle family, and
the one the game actually poses:

  antistall.c        fixes an ANSWER and finds its LONGEST game, choosing the line
                     clairvoyantly. A per-answer maximum, and an upper bound on real
                     play.
  antiwordle_sim.py  plays UNIFORMLY AT RANDOM. A floor, not a strategy.
  THIS FILE          a STRATEGY played without knowing the answer, scored as the
                     EXPECTED number of turns averaged over all still-possible
                     answers. Between the two, and the thing a player actually wants.

THE STATE IS TWO SETS, and conflating them is the mistake to avoid:

  L   the words that may legally be PLAYED here
  A   the answers still POSSIBLE here

They are genuinely different. With `goose` the only possible answer, `goofs`,
`gooks` and `goops` are still legal plays — and playing them is how a game gets
long. A is always a subset of L, never the reverse.

THE RECURSION:

    value(L, A) = max over g in L of
                  1 + SUM over p != all-green  (|A_p| / |A|) * value(L & D(g,p), A_p)

Every answer pays 1 for the guess; those for which g WAS the answer stop there, and
the rest continue, weighted by how many produce each feedback. D(g,p) is the mask
from `antiwordle_sim`, so L narrows exactly as the rules say.

NO SPECIAL CASE IS NEEDED WHEN |A| = 1. Playing a non-answer word then leaves A
unchanged and L smaller, so the recursion degenerates to `1 + value(...)` and the
max over guesses IS the longest stall — the same quantity antistall computes. The
endgame falls out rather than being bolted on.

TOP-K IS PART OF THE OBJECTIVE. At each node only the K best-scoring LEGAL words are
examined — the K best of what remains HERE, never a global top-K filtered by what
happens to still be legal, which would run dry a few guesses in. Restricting the
search can only miss a better strategy, never invent one, so what comes back is a
REAL ACHIEVABLE STRATEGY and its expected turns is a LOWER BOUND on the optimum.
Report it as "best found examining K guesses per node", never as the maximum.

TWO RANKINGS, because which one to trust is an open question:
  "static"  a per-word score supplied by the caller — e.g. the mean game length
            each word achieves as an OPENER under random play
            (tools/antiwordle_sim_run.py). Cheap, but measured at an empty board
            and applied at every depth, which is an extrapolation.
  "alive"   how many legal words the guess LEAVES, computed at this node. What
            antistall's greedy already uses. Costs a mask per candidate.

WORD LISTS ARE OURS: plays from the 12972, answers from the 2315.

This module is the ORACLE for the C port, not the production path — it is written
for clarity and checked by `tools/checkantiwordleexpect.py`. Expect it to be usable
only on small word lists.

    from antiwordle_expect import best_strategy, expected_turns
"""

import numpy as np

from antiwordle_sim import delta_mask
from wordle import ALL_GREEN


def _key(legal, alive):
    """Memo key: both sets, packed. The value depends on the PAIR, not either alone."""
    return (np.packbits(legal).tobytes(), np.packbits(alive).tobytes())


def _rank_legal(space, pat, legal_idx, alive_idx, score, k, mode):
    """The K best legal words HERE, by the chosen ranking.

    Ranked among what is legal at THIS node -- not a global top-K intersected with
    it, which would leave nothing to choose from once play has narrowed.
    """
    if len(legal_idx) <= k:
        return legal_idx
    if mode == "alive":
        # How many legal words each candidate leaves, summed over the feedbacks the
        # surviving answers can actually produce. Expensive but node-accurate.
        keep = np.empty(len(legal_idx), dtype=np.int64)
        for i, g in enumerate(legal_idx):
            total = 0
            for code in np.unique(pat[g, alive_idx]):
                if int(code) == ALL_GREEN:
                    continue
                total += int((delta_mask(space, int(g), int(code))[legal_idx]).sum())
            keep[i] = total
        order = np.argsort(-keep, kind="stable")
    else:
        order = np.argsort(-score[legal_idx], kind="stable")
    return legal_idx[order[:k]]


def expected_turns(space, pat, legal, alive, score, k, mode="static",
                   memo=None, stats=None):
    """Max expected turns from (legal, alive), examining K guesses per node.

    `legal` and `alive` are boolean masks over the guess list and the answer list.
    Returns (expected_turns, best_guess_index).
    """
    if memo is None:
        memo = {}
    key = _key(legal, alive)
    hit = memo.get(key)
    if hit is not None:
        return hit
    if stats is not None:
        stats["nodes"] = stats.get("nodes", 0) + 1

    legal_idx = np.flatnonzero(legal)
    alive_idx = np.flatnonzero(alive)
    n_alive = len(alive_idx)

    best_val, best_g = -1.0, -1
    for g in _rank_legal(space, pat, legal_idx, alive_idx, score, k, mode):
        g = int(g)
        codes = pat[g, alive_idx]
        total = 1.0                          # every answer pays for this guess
        for code in np.unique(codes):
            code = int(code)
            if code == ALL_GREEN:
                continue                     # those answers are finished here
            sub = alive_idx[codes == code]
            child_alive = np.zeros_like(alive)
            child_alive[sub] = True
            child_legal = legal & delta_mask(space, g, code)
            v, _ = expected_turns(space, pat, child_legal, child_alive, score, k,
                                  mode, memo, stats)
            total += (len(sub) / n_alive) * v
        if total > best_val:
            best_val, best_g = total, g

    memo[key] = (best_val, best_g)
    return best_val, best_g


def best_strategy(space, pat, score, k, mode="static", answers_n=None, memo=None):
    """Solve from the opening position: (expected_turns, opening_guess, memo)."""
    legal = np.ones(space.n, dtype=bool)
    alive = np.ones(pat.shape[1] if answers_n is None else answers_n, dtype=bool)
    memo = {} if memo is None else memo
    val, g = expected_turns(space, pat, legal, alive, score, k, mode, memo)
    return val, g, memo


def play_out(space, pat, score, k, answer_ai, mode="static", memo=None):
    """Play the strategy against ONE answer, returning the line actually played.

    An INDEPENDENT check on the recursion's accounting: replaying the strategy
    against every answer and averaging must reproduce `expected_turns` exactly. The
    weights are the easiest thing to get subtly wrong, and a wrong one still prints
    a plausible number.
    """
    legal = np.ones(space.n, dtype=bool)
    alive = np.ones(pat.shape[1], dtype=bool)
    memo = {} if memo is None else memo
    line = []
    while True:
        _, g = expected_turns(space, pat, legal, alive, score, k, mode, memo)
        line.append(space.words[g])
        code = int(pat[g, answer_ai])
        if code == ALL_GREEN:
            return line
        keep = pat[g, :] == code
        alive = alive & keep
        legal = legal & delta_mask(space, g, code)


__all__ = ["best_strategy", "expected_turns", "play_out"]
