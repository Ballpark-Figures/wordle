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

import contextlib
import io
import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from multiwordle import answer_to_guess, draw_answers, play_game  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402
import multiwordle as mw  # noqa: E402
import multiwordle_fast as mf  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import multiwordle_race as race  # noqa: E402
from multiwordle_sim import openers_from, summarise  # noqa: E402
from tree_states import state_from_strings  # noqa: E402
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

    check_ranking()
    check_srank(guesses, mystery, pat, ans2g, games)
    check_minavg(guesses, mystery, pat, ans2g)
    check_kernels(guesses, mystery, pat, ans2g)
    check_race(guesses, mystery)
    check_exact_vs_optimum(guesses, mystery, pat, ans2g)

    print()
    if FAILS:
        print("FAILED: " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


# --- srank and minavg: the same discipline, from the strings ---------------
#
# Everything below follows the rule the greedy differential above follows: the
# oracle must share no machinery with the thing it checks.  For `srank` that
# means the colour composition is re-derived by `tree_states.state_from_strings`,
# which never looks at a tile -- greens are positions where some guess matched the
# answer, and a letter's known count is the most any guess proved by
# min(copies in guess, copies in answer).  For `minavg` it means bucketing
# candidate WORDS with `wordle.pattern` in a dict.


def reference_srank(mystery, answer_words, opening, rng, ranking, ties):
    """`srank` from strings only: no matrix, no bitmaps, no tile decoding."""
    k = len(answer_words)
    cands = [list(mystery) for _ in range(k)]
    seen = [[] for _ in range(k)]                # guesses played on each board
    solved = [False] * k
    played = []
    pending = list(opening)
    g = pending.pop(0)
    while True:
        played.append(g)
        for j in range(k):
            if solved[j]:
                continue
            seen[j].append(g)
            fb = pattern(g, answer_words[j])
            if fb == ALL_GREEN:
                solved[j] = True
                continue
            cands[j] = [w for w in cands[j] if pattern(g, w) == fb]
        if all(solved):
            return played
        if pending:
            g = pending.pop(0)
            continue
        live = [j for j in range(k) if not solved[j]]
        vals = [ranking.get(state_from_strings(answer_words[j], seen[j]),
                            Fraction(-1)) for j in live]
        best = max(vals)
        tied = [j for j, v in zip(live, vals) if v == best]
        if len(tied) > 1:
            ties.append(len(played))
        j = tied[int(rng.integers(len(tied)))]    # always drawn, tie or not
        g = cands[j][int(rng.integers(len(cands[j])))]


def ref_avg_remaining(pool_words, cand_words):
    """`a(g)` for each pool word, by bucketing candidate WORDS from strings.

    The all-green bucket is skipped rather than squared, which is the same thing:
    `pattern(g, w)` is all-green only when w IS g, so that bucket never holds more
    than one word.  The denominator is still every candidate.
    """
    m = len(cand_words)
    out = []
    for g in pool_words:
        buckets = {}
        for w in cand_words:
            p = pattern(g, w)
            if p != ALL_GREEN:
                buckets[p] = buckets.get(p, 0) + 1
        out.append(sum(n * n for n in buckets.values()) / m)
    return out


def ref_lex_choice(vals_by_board):
    """The lexicographically smallest sorted column, ties on the lowest index."""
    best = None
    besti = -1
    for i in range(len(vals_by_board[0])):
        col = sorted(v[i] for v in vals_by_board)
        if best is None or col < best:
            best, besti = col, i
    return besti


def reference_minavg(mystery, answer_words, opening, pool_words, lex_ties):
    """`minavg` from strings only, over whatever pool it is handed."""
    k = len(answer_words)
    cands = [list(mystery) for _ in range(k)]
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
            g = pending.pop(0)
            continue
        vals = [ref_avg_remaining(pool_words, cands[j])
                for j in range(k) if not solved[j]]
        lo = min(min(v) for v in vals)
        firsts = sum(1 for i in range(len(pool_words))
                     if min(v[i] for v in vals) == lo)
        if firsts > 1:
            lex_ties.append(firsts)          # the smallest value did not decide
        g = pool_words[ref_lex_choice(vals)]


def check_ranking():
    ranking = mw.load_singleton_ranking()
    hand_s = hand_c = 0
    rows = 0
    with open(mw.RANKING_CSV) as f:
        head = None
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = [c.strip() for c in line.split(",")]
            if head is None:
                head = {c: i for i, c in enumerate(cols)}
                continue
            rows += 1
            if (int(cols[head["greens"]]), int(cols[head["yellows"]])) == (0, 0):
                hand_s += int(cols[head["singles"]])
                hand_c += int(cols[head["cases"]])
    check("the ranking pools LEVELS by summing singles and cases",
          ranking[(0, 0)] == Fraction(hand_s, hand_c),
          "all-gray: %d/%d over %d rows" % (hand_s, hand_c, rows))
    check("the ranking is an exact Fraction, so a tie is a real tie",
          all(isinstance(v, Fraction) for v in ranking.values())
          and ranking[(4, 1)] == ranking[(5, 0)] == 1,
          "(4,1) and (5,0) both exactly 1")

    # the float table the kernel uses must not merge or split any pair
    tab = mf.ranking_table(ranking)
    keys = sorted(ranking)
    bad = []
    for i, x in enumerate(keys):
        for y in keys[i + 1:]:
            e = (ranking[x] > ranking[y]) - (ranking[x] < ranking[y])
            fx, fy = float(tab[x]), float(tab[y])
            if (int(fx > fy) - int(fx < fy)) != e:
                bad.append((x, y))
    check("the kernel's float ranking has the same order AND ties as the exact one",
          not bad, "%d compositions, %d pairs compared"
          % (len(keys), len(keys) * (len(keys) - 1) // 2))


def check_srank(guesses, mystery, pat, ans2g, games):
    ranking = mw.load_singleton_ranking()
    ties = []
    unranked = 0
    for k in (2, 4, 8):
        for opening in (["laten"], ["clint", "soare"]):
            og = [guesses.index(w) for w in opening]
            seed = 20260909 + k + 10 * len(opening)
            rule = mw.make_rule(mw.SRANK, guesses=guesses, ranking=ranking)
            rng = np.random.default_rng(seed)
            fast = []
            for _ in range(games):
                a = draw_answers(len(mystery), k, rng)
                fast.append([guesses[g] for g in
                             play_game(pat, ans2g, a, og, rng, rule)])
            unranked += rule.unranked
            rng = np.random.default_rng(seed)
            ref = []
            for _ in range(games):
                a = draw_answers(len(mystery), k, rng)
                ref.append(reference_srank(mystery, [mystery[i] for i in a],
                                           opening, rng, ranking, ties))
            check("srank k=%d, %d-word opening: %d games identical to the "
                  "string replay" % (k, len(opening), games), fast == ref)
    check("srank's random board tie-break was exercised",
          len(ties) > 0, "%d tied turns" % len(ties))
    check("no board ever reached a composition the ranking does not carry",
          unranked == 0, "%d unranked states" % unranked)

    # At k=1 srank IS greedy AS A STRATEGY: the only board is trivially both the
    # fewest-candidate board and the best-ranked one, and no tie can arise.  They
    # are NOT the same sample path under one coin-flip stream, though, because
    # srank spends two draws per turn (tie-break then pick) and greedy one -- so
    # the comparison feeds greedy exactly srank's PICK draws, the odd-indexed
    # ones.  Getting that wrong is what this check caught the first time it ran.
    og = np.array([guesses.index("laten")], dtype=np.int64)
    rankval = mf.ranking_table(ranking)
    letters = mf.guess_letter_table(guesses)
    same = odd_used = True
    for gi in range(30):
        a = np.asarray(draw_answers(len(mystery), 1,
                                    np.random.default_rng([77, gi])),
                       dtype=np.int64)
        fl = np.random.default_rng([77, gi, 1]).random(512)
        buf = np.empty(mf.turn_bound(1, 1), dtype=np.int64)
        n1 = mf.play_pick(pat, ans2g, a, og, mf.PICK_SRANK, rankval, letters,
                          fl, buf)
        srank_seq = list(buf[:n1])
        n2 = mf.play_pick(pat, ans2g, a, og, mf.PICK_GREEDY, rankval, letters,
                          np.ascontiguousarray(fl[1::2]), buf)
        if srank_seq != list(buf[:n2]):
            same = False
    check("at k=1 srank is greedy, once its extra tie-break draw is accounted "
          "for (30 games)", same and odd_used)


def check_minavg(guesses, mystery, pat, ans2g):
    # A POOL THAT DOES NOT COVER THE ANSWERS IS REFUSED, not run: the rule is
    # deterministic, so a board no pool word splits would make it replay one
    # guess forever.  This is a constructed case -- the pool we ship is all 12972
    # guesses, which contain every answer, so it could never arise on its own.
    refused = False
    try:
        mw.make_rule(mw.MINAVG, pool=np.arange(0, len(guesses), 37),
                     answers_g=ans2g)
    except ValueError:
        refused = True
    check("minavg refuses a pool that omits answer words (it could not "
          "terminate)", refused)

    # whole games against the string replay, on the ANSWERS as the pool: covers
    # the answers so it terminates, is a legitimate pool, and is 5.6x cheaper for
    # the O(pool x candidates) string reference than the full guess list.
    pool_idx = np.sort(np.asarray(ans2g, dtype=np.int64))
    pool_words = [guesses[i] for i in pool_idx]
    lex_ties = []
    for k in (1, 2):
        og = [guesses.index("laten")]
        rule = mw.make_rule(mw.MINAVG, pool=pool_idx, answers_g=ans2g)
        fast, ref = [], []
        for gi in range(2):
            a = draw_answers(len(mystery), k, np.random.default_rng([31, gi]))
            fast.append([guesses[g] for g in
                         play_game(pat, ans2g, a, og, None, rule)])
            ref.append(reference_minavg(mystery, [mystery[i] for i in a],
                                        ["laten"], pool_words, lex_ties))
        check("minavg k=%d: 2 games identical to the string replay" % k,
              fast == ref, "" if fast == ref else "%s vs %s" % (fast[0], ref[0]))
    check("minavg's lexicographic tie-break was exercised (the smallest value "
          "alone did not decide)", len(lex_ties) > 0,
          "%d such turns, up to %d words tied on the minimum"
          % (len(lex_ties), max(lex_ties) if lex_ties else 0))

    # average_remaining itself, on the FULL 12972 pool, recomputed from strings
    full = np.arange(len(guesses))
    row = pat[guesses.index("laten")]
    for p in (int(row[11]), int(row[404])):
        idx = np.flatnonzero(row == p)
        got = mw.average_remaining(pat, full, idx)
        want = ref_avg_remaining(guesses, [mystery[i] for i in idx])
        check("average_remaining matches a from-strings bucket count "
              "(pattern %d, %d candidates, all %d guesses)"
              % (p, len(idx), len(guesses)),
              np.allclose(got, want, rtol=0, atol=1e-12))

    # a singleton board's own word scores 0 and nothing else scores less: that is
    # what stops minavg stalling on a board it has already pinned down
    one = np.array([7])
    vals = mw.average_remaining(pat, full, one)
    w = int(ans2g[7])
    check("a singleton board scores 0 for its own word and 1 for every other",
          vals[w] == 0.0 and set(np.delete(vals, w)) == {1.0},
          "answer %s" % mystery[7])


def check_kernels(guesses, mystery, pat, ans2g):
    ranking = mw.load_singleton_ranking()
    rankval = mf.ranking_table(ranking)
    letters = mf.guess_letter_table(guesses)
    bad = 0
    n = 0
    for mode, name in ((mf.PICK_GREEDY, mw.GREEDY), (mf.PICK_SRANK, mw.SRANK)):
        for k in (1, 2, 4, 8, 16):
            og = np.array([guesses.index("laten")], dtype=np.int64)
            for gi in range(4):
                a = draw_answers(len(mystery), k, np.random.default_rng([5, gi]))
                a64 = np.asarray(a, dtype=np.int64)
                fl = np.random.default_rng([5, gi, race.PICK_OFFSET]).random(512)
                played = np.empty(mf.turn_bound(k, 1), dtype=np.int64)
                nn = mf.play_pick(pat, ans2g, a64, og, mode, rankval, letters,
                                  fl, played)
                rule = None if name == mw.GREEDY else \
                    mw.make_rule(mw.SRANK, guesses=guesses, ranking=ranking)
                ref = play_game(pat, ans2g, a, og,
                                mw.CoupledRng(np.random.default_rng(
                                    [5, gi, race.PICK_OFFSET])), rule)
                n += 1
                if list(played[:nn]) != ref:
                    bad += 1
    check("the numba kernels match the reference guess for guess (%d games, "
          "greedy and srank, k=1..16)" % n, bad == 0, "%d mismatches" % bad)

    # the turn-2 memo is memoisation and nothing else
    pool = np.arange(len(guesses), dtype=np.int64)
    og = np.array([guesses.index("laten")], dtype=np.int64)
    t2 = mf.turn2_table(pat, int(og[0]), pool)
    row = pat[og[0]]
    p = int(row[3])
    idx = np.flatnonzero(row == p)
    check("the turn-2 table equals average_remaining on the opener's bucket",
          np.array_equal(t2[p], mw.average_remaining(pat, pool, idx)))
    agree = True
    fired = searched = 0
    for k in (1, 2, 4, 8):
        for gi in range(2 if k >= 8 else 3):
            a = draw_answers(len(mystery), k, np.random.default_rng([13, gi]))
            searched_g, fired_g = _singleton_turns(pat, a, og)
            searched += searched_g
            fired += fired_g
            a64 = np.asarray(a, dtype=np.int64)
            played = np.empty(mf.turn_bound(k, 1), dtype=np.int64)
            vals = np.empty((k, len(pool)))
            cur, best = np.empty(k), np.empty(k)
            n1 = mf.play_minavg(pat, ans2g, a64, og, pool, t2, True, played, vals,
                                cur, best)
            with_memo = list(played[:n1])
            n2 = mf.play_minavg(pat, ans2g, a64, og, pool, t2, False, played, vals,
                                cur, best)
            without = list(played[:n2])
            ref = play_game(pat, ans2g, a, og, None,
                            mw.make_rule(mw.MINAVG, pool=pool,
                                         answers_g=ans2g))
            if not (with_memo == without == ref):
                agree = False
    check("minavg agrees three ways: memoised kernel, bare kernel, reference",
          agree)
    # The kernel takes an EXACT shortcut whenever a board is down to one word (the
    # winner can then only be a singleton board's own word).  The reference has no
    # such path, so the agreement above IS the differential -- but only if the
    # shortcut actually fired, so that is counted rather than hoped for.  It also
    # caught a real bug: collected in board order the candidates tie-broke by
    # BOARD, where the full scan tie-breaks by lowest guess index.
    check("the minavg singleton fast path fired in that differential",
          fired > 0, "%d of %d searched turns (%.0f%%)"
          % (fired, searched, 100.0 * fired / max(searched, 1)))


def check_race(guesses, mystery):
    # the elimination arithmetic, on rows made by hand
    n = 100
    # opening 1 is +0.5 in EVERY game: sum(d)=50 and sum(d^2)=n*mean^2=25, so the
    # variance is exactly 0.  Opening 2 is +0.5 on average with real spread.
    # Opening 3 is ahead of the leader.
    sum_d = np.array([0.0, 50.0, 50.0, -10.0])
    sumsq_d = np.array([0.0, 25.0, 500.0, 20.0])
    md, se = race.paired_error(sum_d, sumsq_d, n)
    # opening 1 is +0.5 with no spread at all -> infinitely many sigma behind;
    # opening 2 is +0.5 with real spread; opening 3 is ahead of the leader
    check("a paired difference with zero variance has zero standard error",
          md[1] == 0.5 and se[1] < 1e-12 and md[0] == 0.0 and se[0] == 0.0,
          "an opening worse in every game leaves on the mean alone")
    check("the 5-sigma cut drops the noiseless laggard and keeps the noisy one",
          bool((md - 5 * se > 0)[1]) and not bool((md - 5 * se > 0)[2])
          and not bool((md - 5 * se > 0)[3]),
          "se: %.4f vs %.4f" % (se[1], se[2]))

    # every opening must face the SAME games and the SAME coin flips
    a1, f1 = race.make_games(len(mystery), 3, 7, 0, 5, 64)
    a2, f2 = race.make_games(len(mystery), 3, 7, 0, 5, 64)
    check("the race's games are a function of (seed, game index) alone",
          np.array_equal(a1, a2) and np.array_equal(f1, f2))
    a3, f3 = race.make_games(len(mystery), 3, 7, 0, 9, 128)
    check("regrowing the coin-flip array extends the same stream",
          np.array_equal(f1, f3[:5, :64]) and np.array_equal(a1, a3[:5]))

    # pairing must actually be tighter than not pairing, or it buys nothing
    # row 1 tracks row 0 without shadowing it (the difference varies), so the
    # paired error is smaller than the unpaired one WITHOUT being trivially zero;
    # row 2 is uncorrelated, which is what pairing cannot help with.
    hist = np.array([[5, 6, 7, 6, 5, 8, 6, 7],
                     [6, 7, 9, 7, 6, 10, 7, 8],
                     [9, 4, 8, 5, 9, 6, 4, 9]], dtype=np.int16)
    tot, sq, sd, ssd = race.history_paired(hist, 8, 0)
    md, se = race.paired_error(sd, ssd, 8)
    mean, ose = race.own_error(tot, sq, 8)
    check("pairing is tighter than the unpaired error for a correlated opening, "
          "without being degenerately zero",
          0 < se[1] < ose[1] and abs(md[1] - (mean[1] - mean[0])) < 1e-12,
          "paired se %.4f vs own se %.4f; uncorrelated row %.4f vs %.4f"
          % (se[1], ose[1], se[2], ose[2]))
    check("the pairwise sums equal the history they replace",
          abs(sd[2] - (hist[2].astype(float) - hist[0]).sum()) < 1e-9
          and abs(ssd[2] - ((hist[2].astype(float) - hist[0]) ** 2).sum()) < 1e-9)

    # a race resumed, and a race switched to pairwise sums, must both be exact
    loc = os.path.join("data", "local", "multiwordle")
    os.makedirs(loc, exist_ok=True)
    field = os.path.join(loc, "_checkfield.txt")
    with open(field, "w") as f:
        f.write("\n".join(guesses[i] for i in range(0, len(guesses), 500)) + "\n")


    def paths(tag):
        out = os.path.join(loc, "_checkrace_%s.csv" % tag)
        return (out, out[:-4] + "_eliminations.csv",
                os.path.join(loc, "_checkrace_%s.npz" % tag))

    def wipe(tag):
        for q in paths(tag):
            if os.path.exists(q):
                os.remove(q)

    def run(tag, max_games, pair_at):
        """One race, with its console output captured so the gate can assert on
        what it says as well as what it writes."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            race.main(["--strategy", "srank", "-k", "3", "--openings", field,
                       "--max-games", str(max_games), "--pair-at", str(pair_at),
                       "--chunk", "5", "--report", "1e9", "--seed", "3",
                       "--out", paths(tag)[0]])
        return buf.getvalue()

    def body(tag):
        return [ln for ln in open(paths(tag)[0]) if not ln.startswith("# race_")]

    for tag in ("whole", "split", "switch", "pairsplit"):
        wipe(tag)
    said = {}
    said["whole"] = run("whole", 800, 0)
    run("split", 400, 0)                       # stop early ...
    said["split"] = run("split", 800, 0)       # ... then resume into the same file
    said["switch"] = run("switch", 800, 9999)
    # AND A RESUME FROM THE PAIRWISE PHASE, which is a different checkpoint
    # payload entirely -- sums rather than a history -- and is the state a long
    # race spends nearly all of its life in.  The resume above never reaches it,
    # because it runs with the switch disabled.
    run("pairsplit", 400, 9999)
    said["pairsplit"] = run("pairsplit", 800, 9999)

    check("a race resumed from its checkpoint equals an uninterrupted one",
          body("split") == body("whole"),
          "resumed at %s" % ("yes" if "resuming" in said["split"] else "NO -- "
                             "it started over, so this proves nothing"))
    check("the resumed run really did resume rather than start again",
          "resuming" in said["split"])
    check("switching to pairwise sums changes no result",
          body("switch") == body("whole"))
    # ... and the switch must actually have happened, or the check above is
    # comparing two identical code paths and says nothing
    check("the pairwise switch fired in the switch run and not in the other",
          "switched to pairwise" in said["switch"]
          and "switched to pairwise" not in said["whole"])
    check("a race resumed from the PAIRWISE phase equals an uninterrupted one",
          body("pairsplit") == body("switch"),
          "resumed at %s" % ("yes" if "resuming" in said["pairsplit"] else
                             "NO -- it started over, so this proves nothing"))
    # The SECOND leg must not re-announce the switch: it loaded a checkpoint that
    # was already past it.  So the signature of a genuine pairwise resume is
    # "resuming" without "switched", plus a checkpoint that really holds sums.
    check("that resume really was from the pairwise phase",
          "resuming" in said["pairsplit"]
          and "switched to pairwise" not in said["pairsplit"]
          and bool(np.load(paths("pairsplit")[2],
                           allow_pickle=False)["paired"]))
    elim = open(paths("whole")[1]).read().strip().split("\n")
    check("the race eliminated openings and logged every one of them",
          len(elim) > 2 and elim[1].startswith("opening,"),
          "%d rows in the eliminations log" % (len(elim) - 2))

    for tag in ("whole", "split", "switch", "pairsplit"):
        wipe(tag)
    os.remove(field)


def _singleton_turns(pat, answer_idx, openers_g):
    """(searched turns, turns with a singleton board) for one minavg game.

    A COVERAGE tally, not an oracle: it replays the candidate counts to say how
    often the kernel's exact fast path applies, so a passing differential cannot
    silently mean it never ran.
    """
    k = len(answer_idx)
    na = pat.shape[1]
    alive = np.ones((k, na), dtype=bool)
    solved = np.zeros(k, dtype=bool)
    pool = np.arange(pat.shape[0])
    rule = mw.make_rule(mw.MINAVG, pool=pool,
                        answers_g=np.arange(na))     # identity: counts only
    searched = fired = 0
    pending = [int(g) for g in openers_g]
    g = pending.pop(0)
    played = []
    while True:
        played.append(g)
        row = pat[g]
        for j in range(k):
            if solved[j]:
                continue
            fb = int(row[answer_idx[j]])
            if fb == ALL_GREEN:
                solved[j] = True
                continue
            alive[j] &= row == fb
        if solved.all():
            return searched, fired
        if pending:
            g = pending.pop(0)
            continue
        searched += 1
        if min(int(alive[j].sum()) for j in range(k) if not solved[j]) == 1:
            fired += 1
        g = rule.choose(pat, None, alive, solved, None, played, None)


def check_exact_vs_optimum(guesses, mystery, pat, ans2g):
    """minavg at k=1 must never beat the exact optimum -- an outside cross-check.

    At k=1 `minavg` is a one-ply heuristic over ordinary Wordle, and this file can
    evaluate it EXACTLY (2315 answers, deterministic rule, no sampling).  So its
    total is directly comparable with `data/shared/optturns/opener_totals.csv`,
    which is the minimum total guesses subject to resolving every answer within 6
    and is itself validated against Bertsimas and Paskov.

    The comparison is only legitimate when minavg actually resolves every answer
    within 6, since otherwise its strategy is outside the set optturns minimised
    over -- so that is checked per opener rather than assumed, and an opener whose
    worst game is longer is skipped with a note.  Nothing else in this gate reaches
    outside the multiwordle code at all, which is what makes it worth having.
    """
    opt = {}
    path = os.path.join("data", "shared", "optturns", "opener_totals.csv")
    if not os.path.exists(path):
        check("optturns totals are available for the k=1 cross-check", True,
              "SKIPPED: no %s" % path)
        return
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("word,"):
                continue
            c = line.split(",")
            if len(c) > 1 and c[1].strip():
                opt[c[0].strip()] = int(c[1])

    pool = np.arange(len(guesses), dtype=np.int64)
    every = np.arange(len(mystery), dtype=np.int64).reshape(len(mystery), 1)
    scores = np.empty(len(mystery), dtype=np.int64)
    rows = []
    for w in ("salet", "trace", "laten"):
        if w not in opt:
            continue
        og = np.array([guesses.index(w)], dtype=np.int64)
        t2 = mf.turn2_table(pat, int(og[0]), pool)
        mf.run_minavg_games(pat, ans2g, every, og, pool, t2, True, scores)
        rows.append((w, int(scores.sum()), int(scores.max()), opt[w]))
    ok = all(tot >= o for _, tot, mx, o in rows if mx <= 6)
    used = [r for r in rows if r[2] <= 6]
    check("minavg's exact k=1 total never beats the optturns optimum",
          ok and used,
          "; ".join("%s %d vs optimum %d" % (w, t, o) for w, t, mx, o in used))
    check("every minavg k=1 game finished, and within the 6 optturns assumes",
          all(1 <= mx <= 6 for _, _, mx, _ in rows),
          "worst game per opener: "
          + ", ".join("%s %d" % (w, mx) for w, _, mx, _ in rows))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
