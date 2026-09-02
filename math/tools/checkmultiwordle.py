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
tests the strategy (blind opening, board choice, tie-break, candidate pick,
incidental solves, when a board counts as solved) and the answer-index-to-guess-
index map at once.  Multi-word openings are covered too, since a blind opening
that stops early -- or one word too many -- changes the sequence immediately.

WHY THE SEEDS LINE UP.  Both consume the generator in the same order -- the k
answers, then one draw per non-opener guess -- and both index into their
candidates in ANSWER-LIST ORDER, since the mystery list is sorted on disk and
filtering preserves order.  So a divergence in either the game logic or the
order of random draws shows up as a differing sequence, not as noise.

THE TIE-BREAK IS COUNTED, not assumed exercised: the run tallies how many turns
had two or more unsolved boards tied for fewest candidates, per k, and FAILS if
that never happened anywhere (in which case the differential would say nothing
about tie-breaking).  The tally is over the whole run rather than per k, since
whether a particular k and seed happens to produce a tie is luck.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from multiwordle import answer_to_guess, draw_answers, play_game  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiwordle_sim import openers_from, summarise  # noqa: E402
from multiwordle_shortlist import shortlist  # noqa: E402
from multiwordle_sweep import PICK_OFFSET, load_done, sweep_word  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def reference_game(mystery, answer_words, opening, rng, ties):
    """Same strategy, from strings only: no pattern matrix, no bitmaps.

    Appends one entry to `ties` per turn where two or more unsolved boards tied
    for the fewest candidates.  Returns the guess WORDS played, in order.
    """
    k = len(answer_words)
    cands = [list(mystery) for _ in range(k)]     # answer-list order, preserved
    solved = [False] * k
    played = []
    pending = list(opening)
    g = pending.pop(0)
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
        if pending:
            g = pending.pop(0)          # blind: the opening is played out
            continue
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

    top_pair = openers_from("data/shared/singletons/pair_singletons.csv")
    check("--openers-from reads a pair off the singletons ranking",
          len(top_pair) == 2 and all(w in guesses for w in top_pair),
          " ".join(top_pair))

    # openings of one, two, three and four words -- the single word and the
    # exact top pair, then heads of the (screened) triple and quad rankings
    openings = [
        ["laten"],
        ["clint", "soare"],
        ["canst", "horde", "blimp"],
        ["bandy", "chimp", "fogle", "wurst"],
    ]
    opening = openings[0]

    # --- the differential: same seed, two independent implementations --------
    ties_by_k = {}
    for k in [1, 2, 3, 5]:
        for opening in openings:
            openers_g = [guesses.index(w) for w in opening]
            fast, ref = [], []
            ties = []
            seed = 20260902 + k + 100 * len(opening)
            rng = np.random.default_rng(seed)
            for _ in range(games):
                answer_idx = draw_answers(len(mystery), k, rng)
                fast.append([guesses[g] for g in
                             play_game(pat, ans2g, answer_idx, openers_g, rng)])
            rng = np.random.default_rng(seed)
            for _ in range(games):
                answer_idx = draw_answers(len(mystery), k, rng)
                ref.append(reference_game(mystery,
                                          [mystery[a] for a in answer_idx],
                                          opening, rng, ties))
            same = fast == ref
            check("k=%d, %d-word opening: %d games identical to the string replay"
                  % (k, len(opening), games), same,
                  "" if same else "first divergence at game %d"
                  % next(i for i in range(games) if fast[i] != ref[i]))
            ties_by_k[k] = ties_by_k.get(k, 0) + len(ties)

    check("the board tie-break was exercised somewhere in the differential",
          sum(ties_by_k.values()) > 0,
          "tied turns by k: " + ", ".join("k=%d:%d" % kv
                                          for kv in sorted(ties_by_k.items())))

    # every word of a blind opening is played, even one that cannot help
    opening = ["clint", "soare"]
    openers_g = [guesses.index(w) for w in opening]
    rng = np.random.default_rng(5)
    blind = 0
    for _ in range(20):
        answer_idx = draw_answers(len(mystery), 2, rng)
        played = [guesses[g] for g in
                  play_game(pat, ans2g, answer_idx, openers_g, rng)]
        if played[:2] == opening:
            blind += 1
    check("every word of a blind opening is played, in order", blind == 20,
          "%d/20 games" % blind)

    opening = ["laten"]
    opener_g = guesses.index("laten")

    # --- invariants on a wider sample of games ------------------------------
    k = 4
    rng = np.random.default_rng(1)
    named = atleast = 0
    for _ in range(40):
        answer_idx = draw_answers(len(mystery), k, rng)
        played = play_game(pat, ans2g, answer_idx, [opener_g], rng)
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
          "laten" not in mystery and atleast == 40, "%d/40 games" % atleast)

    # --- determinism --------------------------------------------------------
    a = np.random.default_rng(99)
    b = np.random.default_rng(99)
    ia, ib = draw_answers(len(mystery), 3, a), draw_answers(len(mystery), 3, b)
    check("same seed reproduces the same game",
          list(ia) == list(ib)
          and play_game(pat, ans2g, ia, [opener_g], a)
          == play_game(pat, ans2g, ib, [opener_g], b))

    # --- the sweep: common random numbers, and an independent replay --------
    k, t, seed = 3, 12, 4242
    na = len(mystery)
    two = [["laten"], ["clint"]]
    seen = []
    for opening in two:
        rng = np.random.default_rng(seed)
        seen.append([list(draw_answers(na, k, rng)) for _ in range(t)])
    check("every swept opener faces the identical answer draws",
          seen[0] == seen[1] and len(seen[0]) == t)

    pick_stream = [list(draw_answers(na, k, np.random.default_rng(seed + PICK_OFFSET)))]
    check("the pick stream is not the draw stream under another name",
          pick_stream[0] != seen[0][0])

    # replay sweep_word's t games in an independent loop and compare the summary
    opening = ["clint"]
    openers_g = [guesses.index(w) for w in opening]
    st = sweep_word(pat, ans2g, na, k, t, seed, openers_g)
    draw_rng = np.random.default_rng(seed)
    pick_rng = np.random.default_rng(seed + PICK_OFFSET)
    scores = [len(play_game(pat, ans2g, draw_answers(na, k, draw_rng),
                            openers_g, pick_rng)) for _ in range(t)]
    ref = summarise(scores, k)
    check("sweep_word matches an independent replay of the same streams",
          st == ref, "%.4f vs %.4f" % (st["mean_guesses"], ref["mean_guesses"]))
    check("a sweep row totals its own trials", st["trials"] == t)

    # --- the summary totals what it summarises ------------------------------
    scores = [7, 9, 8, 12, 9, 10]
    st = summarise(scores, 3)
    check("summary mean totals the scores it was given",
          abs(st["mean_guesses"] * len(scores) - sum(scores)) < 1e-9
          and abs(st["mean_per_board"] * 3 - st["mean_guesses"]) < 1e-9
          and st["trials"] == len(scores)
          and st["min"] == 7 and st["max"] == 12)

    # --- the shortlist cut keeps exactly what it claims to -------------------
    rows = [("aaa", 4.00, 0.10), ("bbb", 4.05, 0.20), ("ccc", 4.30, 0.10),
            ("ddd", 3.90, 0.10), ("eee", 4.40, 0.50)]
    # best is ddd 3.90 se 0.10; 2 SE of the BEST's se keeps mean <= 4.10
    keep, _ = shortlist(rows, se=2)
    check("shortlist --se cuts on the best word's standard error",
          [w for w, _, _ in keep] == ["ddd", "aaa", "bbb"])
    # with each word's own se, eee (0.50) survives at 4.40 <= 3.90 + 2*0.50
    keep, _ = shortlist(rows, se=2, own_se=True)
    check("shortlist --own-se is the more permissive cut",
          set(w for w, _, _ in keep) == {"ddd", "aaa", "bbb", "eee"})
    keep, _ = shortlist(rows, top=2)
    check("shortlist --top keeps the N best, best first",
          [w for w, _, _ in keep] == ["ddd", "aaa"])

    # --- the sweep's resume reads back what it wrote ------------------------
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "data", "local", "multiwordle", "_checkresume.csv")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w") as f:
        f.write("# a comment\nword,trials,mean\nlaten,10,3.9\nclint,10,3.8\n")
    check("the sweep resumes from the words already in its CSV",
          load_done(tmp) == {"laten", "clint"})
    os.remove(tmp)

    print()
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
