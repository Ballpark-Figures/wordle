"""GATE for the multiwordle simulator: the fast path vs an independent replay.

    python3 tools/checkmultiwordle.py            # from math/
    python3 tools/checkmultiwordle.py --games 12 # more differential games

Exits nonzero on any failure, so it works as a gate.  Run it alongside
solver/validate.sh and tools/checkpatterns.py after touching math/multiwordle.py
or tools/multiwordle_sim.py.

WHAT THE ORACLE IS.  `play_game` is numpy over the precomputed pattern matrix:
candidate sets are boolean bitmaps over the 2315 answers, and feedback is a
lookup in PAT.  The reference here shares NONE of that -- it keeps candidates as
LISTS OF WORDS and recomputes every feedback from the strings with
`wordle.pattern`, the primitive the matrix itself was built from.  The two are
driven from the same seed and must produce byte-identical guess sequences, which
tests the strategy (board choice, tie-break, candidate pick, incidental solves,
when a board counts as solved) and the answer-index-to-guess-index map at once.

WHY THE SEEDS LINE UP.  Both consume the generator in the same order -- the k
answers, then one draw per non-opener guess -- and both index into their
candidates in ANSWER-LIST ORDER, since the mystery list is sorted on disk and
filtering preserves order.  So a divergence in either the game logic or the
order of random draws shows up as a differing sequence, not as noise.

THE TIE-BREAK IS COUNTED, not assumed exercised: the run reports how many turns
had two or more unsolved boards tied for fewest candidates, and warns if that
never happened (in which case the differential says nothing about tie-breaking).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from multiwordle import answer_to_guess, draw_answers, play_game  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiwordle_sim import summarise  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def reference_game(mystery, answer_words, opener, rng, ties):
    """Same strategy, from strings only: no pattern matrix, no bitmaps.

    Appends one entry to `ties` per turn where two or more unsolved boards tied
    for the fewest candidates.  Returns the guess WORDS played, in order.
    """
    k = len(answer_words)
    cands = [list(mystery) for _ in range(k)]     # answer-list order, preserved
    solved = [False] * k
    played = []
    g = opener
    while True:
        played.append(g)
        for j in range(k):
            if solved[j]:
                continue
            fb = pattern(g, answer_words[j])
            if fb == ALL_GREEN:
                solved[j] = True
                continue
            cands[j] = [w for w in cands[j] if pattern(g, w) == fb]
        if all(solved):
            return played
        live = [(len(cands[j]), j) for j in range(k) if not solved[j]]
        best = min(live)[0]
        if sum(1 for n, _ in live if n == best) > 1:
            ties.append(len(played))
        j = min(live)[1]                          # ties break on the board index
        g = cands[j][int(rng.integers(len(cands[j])))]


def main(argv):
    games = 8
    if "--games" in argv:
        games = int(argv[argv.index("--games") + 1])

    guesses = load_words("guess")
    mystery = load_words("mystery")
    pat = np.array(load_patterns())
    ans2g = answer_to_guess(mystery, guesses)

    check("ans2g maps every answer to its own guess word",
          all(mystery[i] == guesses[ans2g[i]] for i in range(len(mystery))))

    opener = "laten"
    opener_g = guesses.index(opener)

    # --- the differential: same seed, two independent implementations --------
    ks = [1, 2, 3, 5]
    for k in ks:
        fast, ref = [], []
        ties = []
        rng = np.random.default_rng(20260902 + k)
        for _ in range(games):
            answer_idx = draw_answers(len(mystery), k, rng)
            fast.append([guesses[g] for g in
                         play_game(pat, ans2g, answer_idx, opener_g, rng)])
        rng = np.random.default_rng(20260902 + k)
        for _ in range(games):
            answer_idx = draw_answers(len(mystery), k, rng)
            ref.append(reference_game(mystery, [mystery[a] for a in answer_idx],
                                      opener, rng, ties))
        same = fast == ref
        check("k=%d: %d games identical to the string replay" % (k, games), same,
              "" if same else "first divergence at game %d"
              % next(i for i in range(games) if fast[i] != ref[i]))
        if k > 1:
            check("k=%d: board tie-break was exercised" % k, bool(ties),
                  "%d tied turns" % len(ties) if ties
                  else "NO tied turns -- the differential says nothing about it")

    # --- invariants on a wider sample of games ------------------------------
    k = 4
    rng = np.random.default_rng(1)
    named = atleast = 0
    for _ in range(40):
        answer_idx = draw_answers(len(mystery), k, rng)
        played = play_game(pat, ans2g, answer_idx, opener_g, rng)
        words = [guesses[g] for g in played]
        if all(mystery[a] in words for a in answer_idx):
            named += 1
        if len(played) >= 1 + k:
            atleast += 1
    check("every board's answer is actually PLAYED, not merely narrowed to",
          named == 40, "%d/40 games" % named)
    # Sound only because no word is ever played twice (a guess is eliminated
    # from every board it did not solve) and this opener is not an answer word,
    # so the sequence holds the opener plus k distinct answers at minimum.
    check("no game finishes in fewer than 1 + k guesses (opener not an answer)",
          opener not in mystery and atleast == 40, "%d/40 games" % atleast)

    # --- determinism --------------------------------------------------------
    a = np.random.default_rng(99)
    b = np.random.default_rng(99)
    ia, ib = draw_answers(len(mystery), 3, a), draw_answers(len(mystery), 3, b)
    check("same seed reproduces the same game",
          list(ia) == list(ib)
          and play_game(pat, ans2g, ia, opener_g, a)
          == play_game(pat, ans2g, ib, opener_g, b))

    # --- the summary totals what it summarises ------------------------------
    scores = [7, 9, 8, 12, 9, 10]
    st = summarise(scores, 3)
    check("summary mean totals the scores it was given",
          abs(st["mean_guesses"] * len(scores) - sum(scores)) < 1e-9
          and abs(st["mean_per_board"] * 3 - st["mean_guesses"]) < 1e-9
          and st["trials"] == len(scores)
          and st["min"] == 7 and st["max"] == 12)

    print()
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
