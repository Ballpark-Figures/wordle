"""GATE for the single-board Wordle simulator: the fast path vs an independent replay.

    python3 tools/checkwordlesim.py                 # from math/
    python3 tools/checkwordlesim.py --games 400     # more differential games

Exits nonzero on any failure, so it works as a gate.  Run it alongside
solver/validate.sh and tools/checkpatterns.py after touching math/wordlesim.py or
tools/wordle_sim.py.

WHAT THE ORACLE IS.  `wordlesim.play_game` is numpy over the 12972x2315 pattern
matrix: candidates are a boolean bitmap over the answer list, and filtering is
one vectorised `alive &= row == fb`.  The reference here shares NONE of that --
it keeps candidates as a LIST OF WORDS and recomputes every reply from the
STRINGS by the MULTISET rule (greens, then a yellow for each guess letter still
available in the answer's leftover counts), which is a different algorithm from
`wordle.pattern`'s left-to-right consuming scan, so a repeated-letter mistake
cannot be shared between them.  Both are driven from the same seed and must
produce IDENTICAL guess sequences -- which tests the candidate filtering, the
answer-index-to-guess-index map, the uniform draw's consumption of the generator
and the win condition all at once.

THE DEFINING PROPERTY IS CHECKED SEPARATELY, not inferred from the diff: every
guess the tail plays must be CONSISTENT with every reply so far (a word the
answer could still be), recomputed from the strings.  A shared bug that made
both sides pick the same wrong word would still fail this.

BOTH REGISTERED STRATEGIES ARE DIFFED, against the same reference driven from a
different POOL -- the 2315 answers for `random`, the 12972 legal guesses for
`random-guess`.  That one parameter is the entire difference between them.
`random-guess` also keeps its OWN state (a bitmap over the guess list, reset on
turn 0), and replaying it across many games is what tests that the reset really
happens: a leaked bitmap shows up as a diverging sequence from the second game on.

THE RULE-THEN-FOLLOW-UP PATH IS EXERCISED TOO, under BOTH follow-ups.  Almost
every strategy the video will try is "something specific for a while, then a
random compatible word", which in code is a rule returning a guess and then None.
So the run also plays a synthetic rule that opens with a fixed word (the guess
list's first entry, taken BY INDEX so no word is written down here) and then
declines, and checks the opener really is played first, that it is played even
though it is not a candidate, that no follow-up ever replays it once missed, and
that the rest of the game matches the reference.  Handing that game to the guess
follow-up at TURN 1 is also the only place its catch-up is tested: it must build
its live set from a history it was not present for.

THE OPENER SWEEP IS DIFFED TOO, against the same reference: its two-stream loop
is reproduced here from the strings, and the answers each word faced are recorded
and required to be IDENTICAL across words.  That is the property the whole sweep
rests on -- a sweep sharing one stream would still report unbiased means, and
would quietly destroy the comparison between words that is the point of it.  The
shortlist cut is checked on hand-made rows whose survivors are known by hand, in
both directions (minimising a mean, maximising a win rate).

COVERAGE IS TALLIED, not assumed.  The run FAILS if no game ever ran past the
six-guess threshold, or if none came in at or under it, since the win-rate
accounting would then be untested in one direction -- and, for `random-guess`,
if it never played a word outside the mystery list, since it would then be
indistinguishable from `random`.

IT IS NOT INSTANT.  The reference filters its pool word by word in Python, so a
`random-guess` game costs a pass over 12972 strings per turn; --guess-games keeps
that to a few seconds by default.
"""

import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402
from wordlesim import (WIN_WITHIN, answer_to_guess, draw_answer,  # noqa: E402
                       make_strategy, make_tail, play_game)
from wordle_sim import summarise  # noqa: E402
from wordle_sweep import PICK_OFFSET, sweep_word  # noqa: E402
from sweep_shortlist import shortlist  # noqa: E402


def ref_pattern(guess, answer):
    """Feedback code, by the MULTISET rule -- an independent implementation.

    Greens first; then a yellow for each remaining guess letter that the answer
    still has a spare copy of, counted rather than scanned.  Encoded base 3 with
    position 0 as the most significant trit, matching wordle.pattern's code.
    """
    tiles = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g] > 0:
            tiles[i] = 1
            left[g] -= 1
    code = 0
    for t in tiles:
        code = code * 3 + t
    return code


def ref_play(pool, answer, rng, opener=None):
    """Replay one game from strings alone.  Returns the words played, in order.

    `pool` is the list the strategy draws from -- the 2315 answers for `random`,
    the 12972 legal guesses for `random-guess` -- in list order, which is the
    order the fast path's flatnonzero produces.  The hidden ANSWER is drawn from
    the mystery words either way; only this pool changes.
    """
    cands = list(pool)
    played = []
    while True:
        if opener is not None and not played:
            g = opener
        else:
            g = cands[int(rng.integers(len(cands)))]
        played.append(g)
        if g == answer:
            return played
        fb = ref_pattern(g, answer)
        cands = [w for w in cands if ref_pattern(g, w) == fb]
        if answer not in cands:
            # the answer reproduces every reply it produced, so it can only be
            # filtered out by a broken feedback rule
            raise AssertionError("reference eliminated the answer %s" % answer)


def consistent_prefix(played, answer):
    """Was every guess a word the answer could still have been at the time?

    Recomputed from the strings: guess i must reproduce every earlier reply.
    Returns the index of the first guess that was not, or None.
    """
    for i in range(1, len(played)):
        for j in range(i):
            if ref_pattern(played[j], played[i]) != ref_pattern(played[j], answer):
                return i
    return None


def main(argv):
    games = 200
    if "--games" in argv:
        games = int(argv[argv.index("--games") + 1])
    # the reference filters 12972 strings per turn here, so this one is smaller
    guess_games = 12
    if "--guess-games" in argv:
        guess_games = int(argv[argv.index("--guess-games") + 1])

    guesses = load_words("guess")
    answers = load_words("mystery")
    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    failures = []

    # --- the encodings the two sides must agree on, before any game runs ------
    checked = 0
    rng = np.random.default_rng(12345)
    for _ in range(4000):
        g = guesses[int(rng.integers(len(guesses)))]
        a = answers[int(rng.integers(len(answers)))]
        if ref_pattern(g, a) != pattern(g, a):
            failures.append("ref_pattern disagrees with wordle.pattern on %s/%s" % (g, a))
            break
        if ref_pattern(g, a) != int(pat[guesses.index(g)][answers.index(a)]):
            failures.append("the matrix disagrees with ref_pattern on %s/%s" % (g, a))
            break
        checked += 1
    print("pattern encodings agreed on %d random guess/answer pairs "
          "(strings, wordle.pattern, matrix)" % checked)

    # --- the ans2g map -------------------------------------------------------
    bad = [i for i in range(len(answers)) if guesses[ans2g[i]] != answers[i]]
    if bad:
        failures.append("ans2g maps %d answers to the wrong guess word" % len(bad))

    # --- differential: the bare tail -----------------------------------------
    rule, tail_name = make_strategy("random", guesses, answers, ans2g)
    tail = make_tail(tail_name, guesses, answers, ans2g)
    if tail_name != "answer":
        failures.append("strategy 'random' resolved to the %r follow-up" % tail_name)
    scores, over, under, longest = [], 0, 0, 0
    for seed in range(games):
        fast_rng = np.random.default_rng(seed)
        ref_rng = np.random.default_rng(seed)
        a_fast = draw_answer(len(answers), fast_rng)
        a_ref = int(ref_rng.integers(len(answers)))
        if a_fast != a_ref:
            failures.append("seed %d: the two sides drew different answers" % seed)
            break
        answer = answers[a_fast]
        played, replies = play_game(pat, ans2g, a_fast, None, tail, fast_rng)
        words = [guesses[g] for g in played]
        ref_words = ref_play(answers, answer, ref_rng)
        if words != ref_words:
            failures.append("seed %d (%s): fast %s vs reference %s"
                            % (seed, answer, " ".join(words), " ".join(ref_words)))
            break
        if words[-1] != answer or answer in words[:-1]:
            failures.append("seed %d (%s): the game did not end on the answer" % (seed, answer))
            break
        if replies[-1] != ALL_GREEN or ALL_GREEN in replies[:-1]:
            failures.append("seed %d (%s): the all-green reply is misplaced" % (seed, answer))
            break
        bad_at = consistent_prefix(words, answer)
        if bad_at is not None:
            failures.append("seed %d (%s): guess %d (%s) was not compatible with the "
                            "replies so far" % (seed, answer, bad_at + 1, words[bad_at]))
            break
        scores.append(len(words))
        over += len(words) > WIN_WITHIN
        under += len(words) <= WIN_WITHIN
        longest = max(longest, len(words))
    print("replayed %d games of the bare tail against the string reference: "
          "identical sequences, every guess compatible" % len(scores))

    # --- differential: the same draw, from the 12972-word GUESS list ----------
    # Only the pool differs.  The hidden answer is still drawn from the 2315.
    mystery = set(answers)
    grule, gtail_name = make_strategy("random-guess", guesses, answers, ans2g)
    gtail = make_tail(gtail_name, guesses, answers, ans2g)
    if gtail_name != "guess":
        failures.append("strategy 'random-guess' resolved to the %r follow-up" % gtail_name)
    gscores, gover, gunder, off_list, drawn_outside = [], 0, 0, 0, 0
    for seed in range(guess_games):
        fast_rng = np.random.default_rng(500000 + seed)
        ref_rng = np.random.default_rng(500000 + seed)
        a_fast = draw_answer(len(answers), fast_rng)
        a_ref = int(ref_rng.integers(len(answers)))
        if a_fast != a_ref:
            failures.append("random-guess seed %d: the two sides drew different answers" % seed)
            break
        answer = answers[a_fast]
        drawn_outside += answer not in mystery      # the game's own draw, checked
        played, replies = play_game(pat, ans2g, a_fast, grule, gtail, fast_rng)
        words = [guesses[g] for g in played]
        ref_words = ref_play(guesses, answer, ref_rng)
        if words != ref_words:
            failures.append("random-guess seed %d (%s): fast %s vs reference %s"
                            % (seed, answer, " ".join(words), " ".join(ref_words)))
            break
        if words[-1] != answer or answer in words[:-1]:
            failures.append("random-guess seed %d (%s): the game did not end on the "
                            "answer" % (seed, answer))
            break
        bad_at = consistent_prefix(words, answer)
        if bad_at is not None:
            failures.append("random-guess seed %d (%s): guess %d (%s) was not "
                            "compatible with the replies so far"
                            % (seed, answer, bad_at + 1, words[bad_at]))
            break
        gscores.append(len(words))
        gover += len(words) > WIN_WITHIN
        gunder += len(words) <= WIN_WITHIN
        off_list += sum(1 for w in words if w not in mystery)
    print("replayed %d games of random-guess against the same reference over the "
          "12972-word pool: identical sequences, %d guesses played that are NOT "
          "mystery words" % (len(gscores), off_list))
    if drawn_outside:
        failures.append("%d hidden answers came from outside the 2315 mystery words"
                        % drawn_outside)

    # --- differential: a prefix strategy that then defers to the tail ---------
    # The opener is taken BY INDEX, so no word is written down in this gate.
    opener_g = 0
    opener = guesses[opener_g]

    def prefix(turn, alive, played, replies, rng):
        return opener_g if turn == 0 else None

    # BOTH follow-ups are handed the same rule, so the composition is tested
    # against each -- and the guess follow-up is then FIRST CALLED AT TURN 1,
    # which is what exercises its catch-up from a history it did not watch.
    opened, non_candidate, handed = 0, 0, {}
    for tname, pool in (("answer", answers), ("guess", guesses)):
        ptail = make_tail(tname, guesses, answers, ans2g)
        n = 0
        for seed in range(min(games, 60 if tname == "answer" else guess_games)):
            fast_rng = np.random.default_rng(1000 + seed)
            ref_rng = np.random.default_rng(1000 + seed)
            a_fast = draw_answer(len(answers), fast_rng)
            int(ref_rng.integers(len(answers)))
            answer = answers[a_fast]
            played, _ = play_game(pat, ans2g, a_fast, prefix, ptail, fast_rng)
            words = [guesses[g] for g in played]
            ref_words = ref_play(pool, answer, ref_rng, opener=opener)
            if words != ref_words:
                failures.append("prefix/%s seed %d (%s): fast %s vs reference %s"
                                % (tname, seed, answer, " ".join(words),
                                   " ".join(ref_words)))
                break
            if words[0] != opener:
                failures.append("prefix/%s seed %d: the opener was not played first"
                                % (tname, seed))
                break
            if len(words) > 1 and words[1] == opener:
                failures.append("prefix/%s seed %d: the follow-up replayed the "
                                "missed opener" % (tname, seed))
                break
            n += 1
            opened += 1
            non_candidate += opener not in answers
        handed[tname] = n
    print("replayed opener-then-follow-up under both follow-ups (%s): the opener "
          "leads every game (%s a mystery word, so playing a NON-candidate is "
          "exercised) and no follow-up replayed it"
          % (", ".join("%s %d" % (k, v) for k, v in handed.items()),
             "not" if opener not in answers else "IS"))
    if not all(handed.values()):
        failures.append("a follow-up was never handed a game in progress")

    # --- the reported numbers ------------------------------------------------
    if scores:
        st = summarise(scores, WIN_WITHIN)
        arr = np.asarray(scores, dtype=np.float64)
        if abs(st["mean_guesses"] - sum(scores) / len(scores)) > 1e-12:
            failures.append("summarise reported the wrong mean")
        if st["wins"] != sum(1 for s in scores if s <= WIN_WITHIN):
            failures.append("summarise counted the wrong number of wins")
        if abs(st["win_rate"] - st["wins"] / len(scores)) > 1e-12:
            failures.append("the win rate is not wins/trials")
        if abs(st["stderr"] - arr.std(ddof=1) / np.sqrt(len(scores))) > 1e-12:
            failures.append("the standard error is not sd/sqrt(n)")
        print("summary arithmetic: mean %.4f, win rate %.2f%% over %d games, "
              "longest %d guesses" % (st["mean_guesses"], 100.0 * st["win_rate"],
                                      len(scores), longest))

    # --- the opener sweep: the two streams, and common random numbers --------
    # Reproduced here from the strings, including the stream discipline: the
    # ANSWERS come from one generator seeded per word and the follow-up's picks
    # from another, so every word must see the SAME games.  A sweep that shared
    # one stream would still look reasonable -- each word's mean would be
    # unbiased -- while quietly destroying the whole point of the sweep, which is
    # that DIFFERENCES between words are compared on identical games.
    sweep_t, sweep_seed = 8, 4
    probe = [guesses[0], guesses[len(guesses) // 2], guesses[-1]]
    seen_answers = {}
    for tname, pool in (("answer", answers), ("guess", guesses)):
        ptail = make_tail(tname, guesses, answers, ans2g)
        for w in probe:
            st = sweep_word(pat, ans2g, len(answers), sweep_t, sweep_seed,
                            guesses.index(w), ptail, WIN_WITHIN)
            draw_rng = np.random.default_rng(sweep_seed)
            pick_rng = np.random.default_rng(sweep_seed + PICK_OFFSET)
            ref_scores, drew = [], []
            for _ in range(sweep_t):
                a = int(draw_rng.integers(len(answers)))
                drew.append(answers[a])
                ref_scores.append(len(ref_play(pool, answers[a], pick_rng,
                                               opener=w)))
            ref = summarise(ref_scores, WIN_WITHIN)
            if abs(st["mean_guesses"] - ref["mean_guesses"]) > 1e-12 or \
                    abs(st["win_rate"] - ref["win_rate"]) > 1e-12:
                failures.append("sweep/%s %s: fast mean %.6f win %.6f vs reference "
                                "%.6f / %.6f" % (tname, w, st["mean_guesses"],
                                                 st["win_rate"], ref["mean_guesses"],
                                                 ref["win_rate"]))
            seen_answers.setdefault(tname, []).append(drew)
    for tname, seqs in seen_answers.items():
        if any(seq != seqs[0] for seq in seqs):
            failures.append("sweep/%s: the swept words did not face the same "
                            "answers -- common random numbers are broken" % tname)
    print("opener sweep: %d words x %d games under both follow-ups match the "
          "string reference, and every word faced the identical answers"
          % (len(probe), sweep_t))

    # --- the shortlist cut ---------------------------------------------------
    # value, stderr per word; the best is 1.00 with a standard error of 0.10, so
    # a 2-SE cut on the mean keeps everything up to 1.20 and nothing above.
    rows = [("best", 1.00, 0.10), ("in", 1.19, 0.50), ("edge", 1.20, 0.01),
            ("out", 1.21, 0.90), ("far", 2.00, 0.10)]
    keep, _ = shortlist(rows, se=2.0)
    if [w for w, _, _ in keep] != ["best", "in", "edge"]:
        failures.append("the mean cut kept %s" % [w for w, _, _ in keep])
    # maximising, the same numbers read as win rates: best is 2.00, keep >= 1.80
    keep, _ = shortlist([(w, v, e) for w, v, e in rows], se=2.0, maximise=True)
    if [w for w, _, _ in keep] != ["far"]:
        failures.append("the maximising cut kept %s" % [w for w, _, _ in keep])
    keep, _ = shortlist(rows, top=2)
    if [w for w, _, _ in keep] != ["best", "in"]:
        failures.append("--top did not take the best two")
    # --own-se measures each word in ITS OWN noise, so `edge` -- 0.20 above the
    # best on a standard error of 0.01 -- now falls OUT, while the noisier `out`
    # survives.  The two cuts are different questions, not one loosened.
    keep, _ = shortlist(rows, se=2.0, own_se=True)
    if [w for w, _, _ in keep] != ["best", "in", "out"]:
        failures.append("--own-se kept %s" % [w for w, _, _ in keep])
    print("shortlist: the 2-SE cut, its maximising form, --top and --own-se all "
          "keep exactly the right words")

    # --- the follow-up is an input, and the registry defends that -------------
    try:
        make_strategy("random", guesses, answers, ans2g, (), "guess")
        failures.append("a --fallback conflicting with the strategy name was accepted")
    except SystemExit:
        pass
    try:
        make_strategy("random", guesses, answers, ans2g, ("extra",))
        failures.append("a strategy taking no arguments accepted one")
    except SystemExit:
        pass
    try:
        make_tail("neither", guesses, answers, ans2g)
        failures.append("an unknown follow-up name was accepted")
    except SystemExit:
        pass
    try:
        make_strategy("opener", guesses, answers, ans2g, (), "answer")
        failures.append("the opener strategy accepted no word")
    except SystemExit:
        pass
    try:
        make_strategy("opener", guesses, answers, ans2g, ("zzzzz",), "answer")
        failures.append("the opener strategy accepted a word that is not a legal guess")
    except SystemExit:
        pass
    try:
        make_strategy("opener", guesses, answers, ans2g, (guesses[0],))
        failures.append("the opener strategy ran without a follow-up")
    except SystemExit:
        pass
    print("refusals: a conflicting --fallback, a stray argument, an unknown "
          "follow-up, and an opener with no word / an illegal word / no "
          "follow-up are all rejected")

    # --- coverage: a pass must not mean the branches never fired -------------
    if not scores:
        failures.append("no game completed, so nothing was compared")
    if not over:
        failures.append("no game ran past %d guesses -- the loss branch of the "
                        "win rate was never exercised (raise --games)" % WIN_WITHIN)
    if not under:
        failures.append("no game finished within %d guesses -- the win branch was "
                        "never exercised" % WIN_WITHIN)
    if not gscores:
        failures.append("no random-guess game completed, so nothing was compared")
    if not off_list:
        failures.append("random-guess never played a word outside the mystery list, "
                        "so it was indistinguishable from random (raise --guess-games)")
    if not non_candidate:
        failures.append("the synthetic opener was itself a mystery word, so playing "
                        "a NON-candidate was never exercised")
    print("coverage: %d games ran past %d guesses, %d came in within it; "
          "random-guess %d past / %d within"
          % (over, WIN_WITHIN, under, gover, gunder))

    if failures:
        print("\nFAIL")
        for f in failures:
            print("  " + f)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
