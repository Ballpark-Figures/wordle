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

THE ORDERING CHOOSER IS CHECKED IN BOTH HALVES, since it replaces work rather
than adding it: every closed-form cost it predicts must be what the simulator
averages to on that answer, and every answer it declares order-INDEPENDENT must
actually cost the same under both orderings -- which it does exactly, game for
game, not merely in expectation.  If the second half ever fails, the chooser is
picking orderings on an incomplete accounting and every sweep built on it is
measuring the wrong ordering.

`--pair-adaptive` GETS ITS OWN CONSTRUCTED CASES, since every branch of it is
rare in random play: a bucket of exactly 1 and of exactly 2 (the opening must be
abandoned and the follow-up must name the answer), a big bucket (it must still be
played), the same position judged by both follow-ups (the guess pool is larger, so
the rule can fire under one and not the other), and a pair whose two ORDERINGS
score differently -- which is the entire reason --both-orders exists.

MULTI-WORD OPENINGS ARE DIFFED THE SAME WAY, and their defining property --
BLIND play, the later words going down even when one candidate is left -- is
TALLIED and required to have happened, since a run where it never came up would
say nothing about it.

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

import contextlib
import io
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import ALL_GREEN, load_words, pattern  # noqa: E402
from secondword import (Table, fire_groups, fire_set,  # noqa: E402
                        gray_counts)
from wordlesim import (WIN_WITHIN, CoupledDraw, answer_to_guess,  # noqa: E402
                       draw_answer,
                       fixed_opening, make_opening_rule, make_strategy,
                       make_second_rule, second_rule_for,
                       make_tail, play_game)
from wordle_sim import summarise  # noqa: E402
from wordle_sweep import PICK_OFFSET, sweep_word  # noqa: E402
from sweep_shortlist import shortlist  # noqa: E402
from order_openings import (best_order, best_order_reference,  # noqa: E402
                             order_cost)
from paired_compare import read_sweep_settings  # noqa: E402


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


def refplay_game(pool, answer, rng, opening=()):
    """Replay one game from strings alone.  Returns the words played, in order.

    `pool` is the list the strategy draws from -- the 2315 answers for `random`,
    the 12972 legal guesses for `random-guess` -- in list order, which is the
    order the fast path's flatnonzero produces.  The hidden ANSWER is drawn from
    the mystery words either way; only this pool changes.
    """
    cands = list(pool)
    played = []
    singleton_blind = 0          # times a later opening word was played anyway
    while True:
        if len(played) < len(opening):
            # BLIND: the opening's words are played in order whatever the replies
            # said -- including when one candidate is left, which is the property
            # a multi-word opening lives or dies by.
            if played and len(cands) == 1:
                singleton_blind += 1
            g = opening[len(played)]
        else:
            g = cands[int(rng.integers(len(cands)))]
        played.append(g)
        if g == answer:
            return played, singleton_blind
        fb = ref_pattern(g, answer)
        cands = [w for w in cands if ref_pattern(g, w) == fb]
        if answer not in cands:
            # the answer reproduces every reply it produced, so it can only be
            # filtered out by a broken feedback rule
            raise AssertionError("reference eliminated the answer %s" % answer)


def ref_play_second(pool, answer, rng, opener, second, fires):
    """Replay a gray-second game from strings alone.  Returns the words played.

    `fires` is a predicate on the TILES this file derives itself, never on a
    pattern code and never on secondword's mask -- so a mistake in the encoding,
    in the composition, or in the condition's direction cannot be shared with the
    thing being checked.
    """
    cands = list(pool)
    played = []
    fired = None
    while True:
        if not played:
            g = opener
        elif len(played) == 1 and second is not None and fired is None:
            fired = fires(ref_tiles(opener, answer))
            g = second if fired else cands[int(rng.integers(len(cands)))]
        else:
            g = cands[int(rng.integers(len(cands)))]
        played.append(g)
        if g == answer:
            return played, fired
        fb = ref_pattern(g, answer)
        cands = [w for w in cands if ref_pattern(g, w) == fb]
        if answer not in cands:
            raise AssertionError("reference eliminated the answer %s" % answer)


def ref_tiles(guess, answer):
    """The reply as tiles, 0 grey / 1 yellow / 2 green -- ref_pattern, undecoded."""
    tiles = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g] > 0:
            tiles[i] = 1
            left[g] -= 1
    return tiles


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
        ref_words, _ = refplay_game(answers, answer, ref_rng)
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
        ref_words, _ = refplay_game(guesses, answer, ref_rng)
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
            ref_words, _ = refplay_game(pool, answer, ref_rng, opening=[opener])
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
                            [guesses.index(w)], ptail, WIN_WITHIN)
            draw_rng = np.random.default_rng(sweep_seed)
            pick_rng = np.random.default_rng(sweep_seed + PICK_OFFSET)
            ref_scores, drew = [], []
            for _ in range(sweep_t):
                a = int(draw_rng.integers(len(answers)))
                drew.append(answers[a])
                ref_scores.append(len(refplay_game(pool, answers[a], pick_rng,
                                               opening=[w])[0]))
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

    # --- multi-word openings: BLIND play, and the sweep over them ------------
    # A pair sweep ranks two-word openings, so the same loop is diffed with the
    # opening the sweep would build.  The property to prove is BLINDNESS: the
    # second word is played even when the first left ONE candidate, which is what
    # a multi-word opening is betting on.  It is TALLIED, not assumed -- a run
    # where it never happened would say nothing about it.
    pairs = [[guesses[0], guesses[1]],
             [guesses[len(guesses) // 3], guesses[-1]]]
    blind_hits, pair_rows = 0, 0
    for tname, pool in (("answer", answers), ("guess", guesses)):
        ptail = make_tail(tname, guesses, answers, ans2g)
        for opening in pairs:
            gs = [guesses.index(w) for w in opening]
            st = sweep_word(pat, ans2g, len(answers), sweep_t, sweep_seed, gs,
                            ptail, WIN_WITHIN)
            draw_rng = np.random.default_rng(sweep_seed)
            pick_rng = np.random.default_rng(sweep_seed + PICK_OFFSET)
            ref_scores = []
            for _ in range(sweep_t):
                a = int(draw_rng.integers(len(answers)))
                words, blind = refplay_game(pool, answers[a], pick_rng, opening=opening)
                ref_scores.append(len(words))
                blind_hits += blind
                if words[:len(opening)] != opening and answers[a] not in opening:
                    failures.append("pair/%s %s: the opening was not played in "
                                    "order (%s)" % (tname, " ".join(opening),
                                                    " ".join(words)))
            ref = summarise(ref_scores, WIN_WITHIN)
            if abs(st["mean_guesses"] - ref["mean_guesses"]) > 1e-12:
                failures.append("pair/%s %s: fast mean %.6f vs reference %.6f"
                                % (tname, " ".join(opening), st["mean_guesses"],
                                   ref["mean_guesses"]))
            pair_rows += 1
    # The blind case CONSTRUCTED rather than waited for: pick a first word and an
    # answer that word isolates to a SINGLETON, so the state after word 1 is known
    # to hold exactly one candidate.  A strategy that quietly stopped playing the
    # opening once it "knew" the answer would score 2 here; blind scores 3.
    ptail = make_tail("answer", guesses, answers, ans2g)
    w1 = guesses[0]
    row = pat[guesses.index(w1)]
    counts = np.bincount(row, minlength=int(row.max()) + 1)
    singles = [a for a in range(len(answers))
               if counts[row[a]] == 1 and answers[a] != w1]
    if not singles:
        failures.append("no answer is isolated by %s, so the blind case could not "
                        "be constructed" % w1)
    else:
        a = singles[0]
        w2 = guesses[1] if guesses[1] != answers[a] else guesses[2]
        played, _ = play_game(pat, ans2g, a,
                              fixed_opening([guesses.index(w1), guesses.index(w2)]),
                              ptail, np.random.default_rng(0))
        words = [guesses[g] for g in played]
        alive_after_1 = sum(1 for x in answers
                            if ref_pattern(w1, x) == ref_pattern(w1, answers[a]))
        if alive_after_1 != 1:
            failures.append("the constructed state holds %d candidates, not 1"
                            % alive_after_1)
        elif words[:2] != [w1, w2]:
            failures.append("the opening was not played blind over a single "
                            "surviving candidate: %s" % " ".join(words))
        elif len(words) != 3 or words[2] != answers[a]:
            failures.append("after a blind second word the follow-up should name "
                            "the one candidate, got %s" % " ".join(words))
        else:
            blind_hits += 1
        print("multi-word openings: %d sweeps of 2-word openings match the "
              "reference under both follow-ups; with %s isolating %s to one "
              "candidate, %s is still played and the game costs 3"
              % (pair_rows, w1, answers[a], w2))
    if not blind_hits:
        failures.append("no opening ever played on past a single surviving "
                        "candidate, so BLIND play is untested")

    # --- --pair-adaptive: the opening abandoned once the field is tiny -------
    # The rule ports optturns' --pair-adaptive (data/shared/PAIRS.md).  Three
    # things are checked, each CONSTRUCTED rather than waited for, because all
    # three are rare in random play:
    #   1. at N or fewer the later word is NOT played and the follow-up names one
    #   2. above N it IS played, so the rule has not simply become "stop early"
    #   3. the count comes from the FOLLOW-UP's pool, so the same position can be
    #      adaptive under `answer` and blind under `guess`
    w1 = guesses[0]
    row = pat[guesses.index(w1)]
    counts = np.bincount(row, minlength=int(row.max()) + 1)
    by_size = {}
    for a in range(len(answers)):
        by_size.setdefault(int(counts[row[a]]), []).append(a)
    atail = make_tail("answer", guesses, answers, ans2g)
    for size in (1, 2):
        if size not in by_size:
            failures.append("no g1 bucket of size %d, so the adaptive branch "
                            "could not be constructed" % size)
            continue
        a = by_size[size][0]
        w2 = next(g for g in guesses if g not in (w1, answers[a]))
        gs = [guesses.index(w1), guesses.index(w2)]
        played, _ = play_game(pat, ans2g, a,
                              make_opening_rule(gs, tail=atail, adapt=2),
                              atail, np.random.default_rng(3))
        words = [guesses[g] for g in played]
        if w2 in words:
            failures.append("pair-adaptive played the second word over a bucket "
                            "of %d: %s" % (size, " ".join(words)))
        elif words[-1] != answers[a]:
            failures.append("pair-adaptive did not end on the answer: %s"
                            % " ".join(words))
        elif len(words) > 1 + size:
            failures.append("pair-adaptive spent %d guesses on a bucket of %d"
                            % (len(words), size))
    # above the threshold the blind word must still go down
    big = max(by_size)
    if big <= 2:
        failures.append("no g1 bucket bigger than 2, so 'above the threshold' "
                        "was never tested")
    else:
        a = by_size[big][0]
        w2 = next(g for g in guesses if g not in (w1, answers[a]))
        gs = [guesses.index(w1), guesses.index(w2)]
        played, _ = play_game(pat, ans2g, a,
                              make_opening_rule(gs, tail=atail, adapt=2),
                              atail, np.random.default_rng(3))
        if [guesses[g] for g in played][:2] != [w1, w2]:
            failures.append("pair-adaptive skipped the second word over a bucket "
                            "of %d, well above the threshold" % big)
    # the same position, judged by the two follow-ups: the guess pool is larger,
    # so a bucket that is adaptive under `answer` can be blind under `guess`
    gtail = make_tail("guess", guesses, answers, ans2g)
    a = by_size[1][0] if 1 in by_size else by_size[min(by_size)][0]
    fb = int(pat[guesses.index(w1)][a])
    n_ans = int((pat[guesses.index(w1)] == fb).sum())
    n_gss = gtail.live_count(None, [guesses.index(w1)], [fb])
    if n_gss < n_ans:
        failures.append("the guess pool (%d) cannot be smaller than the answer "
                        "pool (%d) in the same position" % (n_gss, n_ans))
    print("pair-adaptive: at 1 and 2 the opening is abandoned and the follow-up "
          "names the answer; at %d it is still played; the same position holds %d "
          "answers but %d legal words, so the two follow-ups judge it differently"
          % (big, n_ans, n_gss))

    # ORDER MATTERS under the rule, and that is the reason --both-orders exists.
    # Constructed: a pair whose two orderings score differently on one answer.
    swapped = 0
    for a in list(by_size.get(1, []))[:40]:
        w2 = next(g for g in guesses if g not in (w1, answers[a]))
        fwd = play_game(pat, ans2g, a, make_opening_rule(
            [guesses.index(w1), guesses.index(w2)], tail=atail, adapt=2),
            atail, np.random.default_rng(5))[0]
        rev = play_game(pat, ans2g, a, make_opening_rule(
            [guesses.index(w2), guesses.index(w1)], tail=atail, adapt=2),
            atail, np.random.default_rng(5))[0]
        swapped += len(fwd) != len(rev)
    if not swapped:
        failures.append("no pair scored differently in its two orderings, so the "
                        "reason --both-orders exists is untested")
    else:
        print("order: %d of the constructed pairs score differently when reversed"
              % swapped)

    # --- the exact ordering chooser ------------------------------------------
    # tools/order_openings.py claims it can pick the best ORDERING of an opening
    # without playing a game, because orderings differ only where the switch
    # fires and those costs are closed form at N <= 2.  Both halves of that are
    # checked here, and the second is the load-bearing one.
    otail = make_tail("answer", guesses, answers, ans2g)
    probe_pairs = [[guesses[0], guesses[len(guesses) // 2]],
                   [guesses[3], guesses[-4]]]
    closed, mismatched, cancels, cancel_diff = 0, 0, 0, 0.0
    for words in probe_pairs:
        gi = [guesses.index(w) for w in words]
        orders = ([gi[0], gi[1]], [gi[1], gi[0]])
        for ai in range(0, len(answers), 97):
            preds = []
            for order in orders:
                rows = pat[order]
                ppos = next((j for j in range(2) if int(ans2g[ai]) == order[j]), None)
                preds.append(order_cost(rows, rows[:, ai], ppos, 2, 2))
            if preds[0] is None and preds[1] is None:
                # HALF TWO: an answer no ordering switches on must cost the same
                # under both.  This is what lets the chooser ignore them, and it
                # is stronger than "in expectation" -- with the same seed the
                # follow-up faces the same state and plays the same game.
                means = []
                for order in orders:
                    rule = make_opening_rule(order, tail=otail, adapt=2)
                    r = np.random.default_rng(ai + 11)
                    means.append(np.mean([len(play_game(pat, ans2g, ai, rule,
                                                        otail, r)[0])
                                          for _ in range(30)]))
                cancels += 1
                cancel_diff = max(cancel_diff, abs(means[0] - means[1]))
                continue
            # HALF ONE: a closed-form cost must be what the simulator averages to
            for order, pred in zip(orders, preds):
                if pred is None:
                    continue
                rule = make_opening_rule(order, tail=otail, adapt=2)
                r = np.random.default_rng(ai + 3)
                m = np.mean([len(play_game(pat, ans2g, ai, rule, otail, r)[0])
                             for _ in range(120)])
                closed += 1
                if abs(m - pred) > 0.2:
                    mismatched += 1
                    if mismatched <= 3:
                        failures.append("order_cost said %.2f for %s on %s, the "
                                        "simulator averaged %.3f"
                                        % (pred, " ".join(guesses[g] for g in order),
                                           answers[ai], m))
    if cancel_diff > 1e-9:
        failures.append("an answer no ordering switches on cost %.3f more under "
                        "one ordering; the chooser's cancellation is unsound"
                        % cancel_diff)
    if not closed or not cancels:
        failures.append("the ordering check saw no %s answers"
                        % ("closed-form" if not closed else "cancelling"))
    print("ordering chooser: %d closed-form costs match the simulator (%d off), "
          "and %d cancelling answers cost IDENTICALLY under both orderings "
          "(max difference %.g)" % (closed, mismatched, cancels, cancel_diff))

    # THE FAST PATH AGAINST THE SLOW ONE.  best_order() groups the pool with one
    # unique/bincount per level; best_order_reference() walks the answers in
    # Python.  They must agree exactly -- a 47x speedup that nothing contradicts
    # is how a silently wrong ordering ships, and every sweep is built on this.
    disagreed = 0
    for i in range(0, 40):
        words = [guesses[i * 37 % len(guesses)], guesses[(i * 91 + 5) % len(guesses)]]
        if words[0] == words[1]:
            continue
        gi = [guesses.index(w) for w in words]
        fast = best_order(words, gi, pat[gi], pat[gi], 2, np.asarray(ans2g))
        slow = best_order_reference(words, gi, pat[gi], pat[gi], 2, ans2g)
        if fast[0] != slow[0] or abs(fast[1] - slow[1]) > 1e-9 or any(
                abs(fast[2][k] - slow[2][k]) > 1e-9 for k in fast[2]):
            disagreed += 1
            if disagreed <= 3:
                failures.append("fast/slow ordering disagree on %s: %s vs %s"
                                % (" ".join(words), fast[2], slow[2]))
    print("ordering fast path: 40 pairs agree with the scalar reference "
          "(%d disagreements)" % disagreed)

    # TRIPLES: the second-level switch, and the chooser over 6 orderings.  Both
    # are new surface a pair sweep never touches -- the rule must abandon the
    # THIRD word when the first two have left 2 or fewer, and the chooser must
    # rank six orderings, not two.
    tri = [guesses[0], guesses[len(guesses) // 2], guesses[-1]]
    tgi = [guesses.index(w) for w in tri]
    fast = best_order(tri, tgi, pat[tgi], pat[tgi], 2, np.asarray(ans2g))
    slow = best_order_reference(tri, tgi, pat[tgi], pat[tgi], 2, ans2g)
    if fast[0] != slow[0] or abs(fast[1] - slow[1]) > 1e-9:
        failures.append("fast/slow ordering disagree on the triple %s: %s vs %s"
                        % (" ".join(tri), fast[2], slow[2]))
    if len(fast[2]) != 6:
        failures.append("a triple produced %d orderings, not 6" % len(fast[2]))
    # constructed: after two words 2 or fewer live, but more than 2 after one
    r1 = pat[tgi[0]]
    c1 = np.bincount(r1, minlength=int(r1.max()) + 1)
    second_level = None
    for ai in range(len(answers)):
        if c1[r1[ai]] <= 2:
            continue                       # the FIRST level would fire instead
        both = (r1 == r1[ai]) & (pat[tgi[1]] == pat[tgi[1]][ai])
        if int(both.sum()) <= 2:
            second_level = ai
            break
    if second_level is None:
        failures.append("no answer survives word 1 but not word 2, so the "
                        "second-level switch could not be constructed")
    else:
        played, _ = play_game(pat, ans2g, second_level,
                              make_opening_rule(tgi, tail=otail, adapt=2),
                              otail, np.random.default_rng(9))
        words = [guesses[g] for g in played]
        if tri[2] in words:
            failures.append("the third word was played over a 2-candidate field: %s"
                            % " ".join(words))
        elif words[:2] != tri[:2]:
            failures.append("the first two words were not played: %s" % " ".join(words))
        else:
            print("triples: 6 orderings ranked and matching the reference; with "
                  "%s the field survives %s and not %s, so the THIRD word is "
                  "abandoned (%s)" % (answers[second_level], tri[0], tri[1],
                                      " ".join(words)))

    # ties break alphabetically, so a rerun cannot pick a different ordering
    same = [guesses[0], guesses[1]]
    gi = [guesses.index(w) for w in same]
    b, spread, totals = best_order(same, gi, pat[gi], pat[gi], 2, ans2g)
    if abs(spread) < 1e-12 and b != min(totals):
        failures.append("a tied ordering did not break alphabetically")
    try:
        order_cost(pat[gi], pat[gi][:, 0], None, 3, 2)
        # order_cost itself does not police N; the tool does, and that is checked
        # by the CLI refusing --pair-adaptive 3
    except Exception:
        pass

    # --- the sweep's own OUTPUT PATH, end to end ------------------------------
    # Everything above calls sweep_word directly, so the header-writing path had
    # nothing exercising it -- and a format string with six placeholders and five
    # arguments shipped, crashing every first pass AFTER creating the file (whose
    # existence then suppresses the header on a re-run).  This runs the real main()
    # into a temp file and reads it back with the parser that consumes it.
    import tempfile
    import wordle_sweep as ws
    with tempfile.TemporaryDirectory() as td:
        lst = os.path.join(td, "openings.txt")
        with open(lst, "w") as f:
            f.write("%s %s\n%s %s\n" % (guesses[0], guesses[1],
                                          guesses[2], guesses[3]))
        csv = os.path.join(td, "sweep.csv")
        ws.main(["-t", "5", "--fallback", "answer", "--pair-adaptive", "2",
                 "--seed", "3", "--words", lst, "--out", csv,
                 "--root", "gatecheck", "--pass", "2", "--progress", "0"])
        meta = read_sweep_settings(csv)
        want = dict(fallback="answer", adapt=2, trials=5, seed=3, root="gatecheck")
        for k, v in want.items():
            if meta[k] != v:
                failures.append("the sweep header round-trip lost %s: %r not %r"
                                % (k, meta[k], v))
        if meta["pass"] != 2 or len(meta["openings"]) != 2:
            failures.append("the sweep header round-trip lost the pass or the rows")
    print("sweep output: a real run's header round-trips through the parser that "
          "reads it (follow-up, adapt, trials, seed, root, pass, rows)")

    # --- the paired comparison ------------------------------------------------
    # It replaces two independent means with one difference, so the two things
    # that must hold are: the coupled draw is still a UNIFORM draw from the live
    # set (or every mean it reports is biased), and the difference arithmetic is
    # the difference of the means (or the sharper error is measuring nothing).
    ctail = CoupledDraw(make_tail("answer", guesses, answers, ans2g))
    # the index mapping, checked against the whole unit interval on a small set
    for m in (1, 2, 3, 7, 100):
        seen = {min(int(u * m), m - 1) for u in np.linspace(0, 1, 10001)[:-1]}
        if seen != set(range(m)):
            failures.append("the coupled draw cannot reach every one of %d live "
                            "words: %s" % (m, sorted(seen)))
    # a coupled game is still a legal game
    crule = make_opening_rule([guesses.index(guesses[0])], tail=ctail, adapt=0)
    bad = 0
    for ai in range(0, len(answers), 331):
        played, _ = play_game(pat, ans2g, ai, crule, ctail,
                          np.random.default_rng([7, ai]))
        words = [guesses[g] for g in played]
        if words[-1] != answers[ai] or consistent_prefix(words, answers[ai]) is not None:
            bad += 1
    if bad:
        failures.append("%d coupled games played an inconsistent guess or did not "
                        "end on the answer" % bad)
    # mean(A - B) must equal mean(A) - mean(B), exactly -- the accumulators' identity
    ops = [[guesses[0]], [guesses[len(guesses) // 2]]]
    rules = [make_opening_rule([guesses.index(o[0])], tail=ctail, adapt=0) for o in ops]
    sa, sb, sd_ = [], [], []
    ar = np.random.default_rng(21)
    for i in range(150):
        ai = draw_answer(len(answers), ar)
        sc = []
        for r in rules:
            sc.append(len(play_game(pat, ans2g, ai, r, ctail,
                                np.random.default_rng([21, i]))[0]))
        sa.append(sc[0]); sb.append(sc[1]); sd_.append(sc[0] - sc[1])
    if abs(np.mean(sd_) - (np.mean(sa) - np.mean(sb))) > 1e-12:
        failures.append("the paired difference is not the difference of the means")
    if np.std(sd_, ddof=1) > np.std(sa, ddof=1) + np.std(sb, ddof=1):
        failures.append("pairing did not reduce the spread at all, so the coupling "
                        "is not doing what it claims")
    print("paired comparison: the coupled draw reaches every live word, %d coupled "
          "games are legal, and mean(A-B) == mean(A)-mean(B) with the paired "
          "spread %.3f against %.3f unpaired"
          % (len(range(0, len(answers), 331)), np.std(sd_, ddof=1),
             np.hypot(np.std(sa, ddof=1), np.std(sb, ddof=1))))

    # --- the race: one process, eliminating as the evidence lands ------------
    # The statistics are checkmultiwordle's business (both races import them from
    # race_stats.py, and that gate diffs them against hand-made histories).  What
    # is checked HERE is everything the wordlesim race adds: that its games are a
    # function of (seed, game index) alone, that the coin-flip cursor really is
    # the coupled draw, that a resume and the pairwise switch and the chunk size
    # change nothing, and that the scores are the scores of the strategy it says
    # it is racing.
    import wordle_race as wrace

    # THE GAMES ARE THE SEED AND THE INDEX, AND NOTHING ELSE -- which is what
    # makes a resume exact and the comparison paired.
    a1, f1 = wrace.make_games(len(answers), 5, 0, 6, 32)
    a2, f2 = wrace.make_games(len(answers), 5, 0, 6, 32)
    a3, f3 = wrace.make_games(len(answers), 5, 3, 6, 64)
    if not (np.array_equal(a1, a2) and np.array_equal(f1, f2)):
        failures.append("the race's games are not a function of (seed, index)")
    if not np.array_equal(a1[3:], a3):
        failures.append("game 3 differs depending on which chunk asked for it")
    if not np.array_equal(f1[3:], f3[:, :32]):
        failures.append("regrowing the coin-flip array did not extend the same "
                        "stream, so a regrown game is a different game")

    # THE CURSOR IS THE COUPLED DRAW.  A game played against a pre-drawn row must
    # be the game played against a Generator that produces those same floats --
    # otherwise the race and the paired comparison are two different samplers
    # wearing one name.
    class _RowRng:
        def __init__(self, row):
            self.row, self.i = row, 0

        def random(self):
            self.i += 1
            return self.row[self.i - 1]

    rrule = make_opening_rule([0], tail=ctail, adapt=0)
    same = 0
    for gi in range(12):
        ans_i, fl_i = wrace.make_games(len(answers), 9, gi, gi + 1, 64)
        w1 = play_game(pat, ans2g, int(ans_i[0]), rrule, ctail,
                       wrace.FloatCursor(fl_i[0]))[0]
        w2 = play_game(pat, ans2g, int(ans_i[0]), rrule, ctail,
                       _RowRng(list(fl_i[0])))[0]
        if w1 != w2:
            failures.append("the float cursor does not reproduce the row it "
                            "reads")
            break
        same += 1

    # AND THE SCORES ARE THE STRATEGY'S.  play_chunk is diffed against playing the
    # very same games one at a time, so a transposed matrix or a rule handed to
    # the wrong row would show.
    rules2 = [make_opening_rule([0], tail=ctail, adapt=0),
              make_opening_rule([len(guesses) // 2], tail=ctail, adapt=0)]
    cans, cfl = wrace.make_games(len(answers), 4, 0, 15, 64)
    sc = wrace.play_chunk(pat, ans2g, rules2, ctail, cans, cfl)
    for i, r in enumerate(rules2):
        for j in range(len(cans)):
            n = len(play_game(pat, ans2g, int(cans[j]), r, ctail,
                              wrace.FloatCursor(cfl[j]))[0])
            if sc[i, j] != n:
                failures.append("play_chunk disagrees with the same game played "
                                "alone (opener %d, game %d)" % (i, j))
                break
    print("the race's games are (seed, index) alone, the coin-flip cursor "
          "reproduces its row (%d games) and a chunk equals the games played "
          "one at a time" % same)

    # A RESUME, THE PAIRWISE SWITCH AND THE CHUNK SIZE MUST ALL CHANGE NOTHING.
    # Run the same small race four ways and diff the standings.
    rloc = os.path.join("data", "local", "wordlesim")
    os.makedirs(rloc, exist_ok=True)
    rfield = os.path.join(rloc, "_checkfield.txt")
    with open(rfield, "w") as f:
        f.write("\n".join(guesses[i] for i in range(0, len(guesses), 900)) + "\n")

    def rpaths(tag):
        o = os.path.join(rloc, "_checkrace_%s.csv" % tag)
        return (o, o[:-4] + "_eliminations.csv",
                os.path.join(rloc, "_checkrace_%s.npz" % tag))

    def rwipe(tag):
        for q in rpaths(tag):
            if os.path.exists(q):
                os.remove(q)

    def rrun(tag, max_games, pair_at, chunk):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            wrace.main(["--fallback", "answer", "--words", rfield,
                        "--max-games", str(max_games), "--pair-at", str(pair_at),
                        "--chunk", str(chunk), "--report", "1e9", "--seed", "3",
                        "--sigma", "2", "--out", rpaths(tag)[0]])
        return buf.getvalue()

    def rbody(tag):
        return [ln for ln in open(rpaths(tag)[0]) if not ln.startswith("# race_")]

    for tag in ("whole", "split", "switch", "chunky", "pairsplit"):
        rwipe(tag)
    rsaid = {}
    rsaid["whole"] = rrun("whole", 800, 0, 5)
    rrun("split", 400, 0, 5)                      # stop early ...
    rsaid["split"] = rrun("split", 800, 0, 5)     # ... then resume into it
    rsaid["switch"] = rrun("switch", 800, 9999, 5)
    rsaid["chunky"] = rrun("chunky", 800, 0, 97)
    # AND A RESUME FROM THE PAIRWISE PHASE, a different checkpoint payload
    # entirely -- sums rather than a history -- and the state a long race spends
    # nearly all of its life in.  The resume above never reaches it, because it
    # runs with the switch disabled.  This is the case that caught the extras
    # being rebound instead of filled in place.
    rrun("pairsplit", 400, 9999, 5)
    rsaid["pairsplit"] = rrun("pairsplit", 800, 9999, 5)

    if rbody("split") != rbody("whole"):
        failures.append("a race resumed from its checkpoint does not equal an "
                        "uninterrupted one")
    if "resuming" not in rsaid["split"]:
        failures.append("the resumed race started over, so that check proved "
                        "nothing")
    if rbody("switch") != rbody("whole"):
        failures.append("switching to pairwise sums changed a race's result")
    if not ("switched to pairwise" in rsaid["switch"]
            and "switched to pairwise" not in rsaid["whole"]):
        failures.append("the pairwise switch did not fire where it was meant to, "
                        "so that comparison was between two identical paths")
    if rbody("pairsplit") != rbody("switch"):
        failures.append("a race resumed from the PAIRWISE phase does not equal "
                        "an uninterrupted one")
    if not ("resuming" in rsaid["pairsplit"]
            and "switched to pairwise" not in rsaid["pairsplit"]
            and bool(np.load(rpaths("pairsplit")[2],
                             allow_pickle=False)["paired"])):
        failures.append("that resume was not from the pairwise phase, so it "
                        "proved nothing about the sums")
    if rbody("chunky") != rbody("whole"):
        failures.append("the chunk size changed a race's result -- it is a "
                        "checkpoint interval, not a parameter of the answer")
    relim = open(rpaths("whole")[1]).read().strip().split("\n")
    if not (len(relim) > 2 and relim[1].startswith("word,")):
        failures.append("the race eliminated nobody, or did not log them")
    print("the race: a resume in EITHER phase, the pairwise switch and the "
          "chunk size all change nothing (%d openers, %d eliminated and logged)"
          % (len(open(rfield).read().split()), len(relim) - 2))

    # THE STANDINGS ARE SWEEP-SHAPED, so the cut and the paired round can read a
    # race exactly as they read a sweep -- that is the whole reason for the
    # column names and the settings line.
    rmeta = read_sweep_settings(rpaths("whole")[0])
    if rmeta["fallback"] != "answer" or rmeta["rank"] != "mean":
        failures.append("a race's standings do not parse as a sweep's settings")
    rdata = [r.split(",") for r in rbody("whole")
             if not r.startswith("#") and not r.startswith("word,")]
    rrows, _ = shortlist([(c[0], float(c[2]), float(c[3])) for c in rdata
                          if c[2]], se=5.0)
    if not rrows:
        failures.append("the shortlist tool could not cut a race's standings")
    print("a race's standings parse as a sweep's (%d live rows the cut can read)"
          % len(rrows))

    for tag in ("whole", "split", "switch", "chunky", "pairsplit"):
        rwipe(tag)
    os.remove(rfield)

    # --- ranking by WIN RATE, the parallel ranking ---------------------------
    # A win rate is a PROPORTION, whose ordinary error is exactly zero at the
    # ceiling -- so a cut in those units becomes an equality test.  The cut uses
    # the plus-four (Agresti-Coull) estimate instead; these rows are hand-made so
    # the survivors are known without running anything.
    import sweep_shortlist as ss
    perfect = [("perfect", 1.0, 0.0), ("high", 0.99, 0.00995), ("mid", 0.95, 0.0218),
               ("low", 0.80, 0.04)]
    trials = {w: 100 for w, _, _ in perfect}
    adj = ss.plus_four(perfect, trials)
    if any(e <= 0 for _, _, e in adj):
        failures.append("plus-four left a zero standard error: %s" % adj)
    # the VALUE stays raw -- p~ is monotone in the win count, so the ranking is
    # the raw ranking and only the ERROR is adjusted, which is where zero bites
    if adj[0][1] != 1.0:
        failures.append("plus-four changed the reported rate to %.6f; it must "
                        "adjust the ERROR only" % adj[0][1])
    want = ((102.0 / 104.0) * (2.0 / 104.0) / 104.0) ** 0.5
    if abs(adj[0][2] - want) > 1e-12:
        failures.append("plus-four error is %.6f, not sqrt(p~(1-p~)/(t+4))=%.6f"
                        % (adj[0][2], want))
    keep, _ = ss.shortlist(adj, se=5.0, maximise=True)
    if len(keep) < 3:
        failures.append("the plus-four win-rate cut kept only %d of 4 rows, so it "
                        "is still behaving like an equality test" % len(keep))
    raw_keep, _ = ss.shortlist(perfect, se=5.0, maximise=True)
    if len(raw_keep) != 1:
        failures.append("the RAW proportion cut kept %d rows; it should keep only "
                        "the exact tie, which is why plus-four exists"
                        % len(raw_keep))
    print("win-rate cut: the raw proportion error keeps %d of 4 rows at the "
          "ceiling, plus-four keeps %d" % (len(raw_keep), len(keep)))

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

    # --- gray-second: a fixed second word, but only on enough greys ----------
    # THE OPENER AND THE SECOND WORD ARE TAKEN BY INDEX, so no word is written
    # down in this gate -- the table it builds is synthetic, in memory, and owes
    # nothing to any committed file.
    gs_opener_g, gs_second_g, GS_MIN = 0, 1, 3
    GS_MASK, GS_LABEL = fire_set(GS_MIN)
    gs_fires = lambda tiles: sum(1 for t in tiles if t == 0) >= GS_MIN
    def by_code(second_g, mask=GS_MASK):
        """The rule as the table hands it over: reply code -> guess index."""
        a = np.full(len(mask), -1, dtype=np.int32)
        if second_g is not None:
            a[mask] = second_g
        return a
    gs_opener, gs_second = guesses[gs_opener_g], guesses[gs_second_g]
    gs_fired = gs_declined = 0
    for tname, pool in (("answer", answers), ("guess", guesses)):
        gtail = make_tail(tname, guesses, answers, ans2g)
        rule = make_second_rule(gs_opener_g, by_code(gs_second_g))
        for seed in range(min(games, 80 if tname == "answer" else guess_games)):
            fast_rng = np.random.default_rng(7000 + seed)
            ref_rng = np.random.default_rng(7000 + seed)
            a_fast = draw_answer(len(answers), fast_rng)
            int(ref_rng.integers(len(answers)))
            answer = answers[a_fast]
            played, _ = play_game(pat, ans2g, a_fast, rule, gtail, fast_rng)
            words = [guesses[g] for g in played]
            ref_words, fired = ref_play_second(pool, answer, ref_rng, gs_opener,
                                               gs_second, gs_fires)
            if words != ref_words:
                failures.append("gray-second/%s seed %d (%s): fast %s vs "
                                "reference %s" % (tname, seed, answer,
                                                  " ".join(words),
                                                  " ".join(ref_words)))
                break
            if fired:
                gs_fired += 1
                if len(words) > 1 and words[1] != gs_second:
                    failures.append("gray-second/%s seed %d: the reply had %d+ "
                                    "greys but the second word was not played"
                                    % (tname, seed, GS_MIN))
                    break
            else:
                gs_declined += 1
                if len(words) > 1 and words[1] == gs_second:
                    failures.append("gray-second/%s seed %d: the second word was "
                                    "played on fewer than %d greys"
                                    % (tname, seed, GS_MIN))
                    break
    print("gray-second replayed under both follow-ups: %d games fired the second "
          "word, %d declined to the follow-up" % (gs_fired, gs_declined))

    # THE THRESHOLD, ON BOTH SIDES OF ITSELF, CONSTRUCTED.  Random play does fire
    # both branches, but not at the boundary, and off-by-one is exactly where this
    # rule can be wrong: an answer whose reply has EXACTLY the threshold's greys
    # must play the word, and one with exactly one fewer must not.
    grays = gray_counts()
    boundary = {}
    for a_idx, a in enumerate(answers):
        n = int(grays[pat[gs_opener_g][a_idx]])
        if n in (GS_MIN - 1, GS_MIN) and n not in boundary:
            boundary[n] = a_idx
        if len(boundary) == 2:
            break
    if len(boundary) != 2:
        failures.append("no answers sit either side of the %d-grey boundary, so "
                        "the threshold was not exercised at its edge" % GS_MIN)
    else:
        btail = make_tail("answer", guesses, answers, ans2g)
        rule = make_second_rule(gs_opener_g, by_code(gs_second_g))
        for n, a_idx in sorted(boundary.items()):
            # the tiles are recounted from the STRINGS, so the case really is the
            # one it claims to be
            tiles = ref_tiles(gs_opener, answers[a_idx])
            if sum(1 for t in tiles if t == 0) != n:
                failures.append("the %d-grey case is not one: %s vs %s"
                                % (n, gs_opener, answers[a_idx]))
                continue
            played, _ = play_game(pat, ans2g, a_idx, rule, btail,
                                  np.random.default_rng(3))
            second = guesses[played[1]] if len(played) > 1 else None
            if n >= GS_MIN and second != gs_second:
                failures.append("exactly %d greys did not fire the rule" % n)
            if n < GS_MIN and second == gs_second:
                failures.append("exactly %d greys fired the rule" % n)
        print("the threshold fires at exactly %d greys and not at %d "
              "(constructed, both checked from the strings)" % (GS_MIN, GS_MIN - 1))

    # AND A COMPOSITION, WHICH IS THE POINT OF THE SET: with (0 green, 3 yellow)
    # added, a 2-grey reply fires iff it has no greens.  Both sides of THAT are
    # constructed too, because random play meets them rarely and the whole rule
    # turns on telling them apart.
    cmask, clabel = fire_set(GS_MIN, [(0, 3)])
    crule = make_second_rule(gs_opener_g, by_code(gs_second_g, cmask))
    ctail2 = make_tail("answer", guesses, answers, ans2g)
    want = {(0, 3): True, (1, 2): False, (2, 1): False, (3, 0): False}
    seen = {}
    for a_idx in range(len(answers)):
        tiles = ref_tiles(gs_opener, answers[a_idx])
        comp = (sum(1 for t in tiles if t == 2), sum(1 for t in tiles if t == 1))
        if sum(1 for t in tiles if t == 0) != 2 or comp in seen:
            continue
        seen[comp] = a_idx
    for comp, should in want.items():
        if comp not in seen:
            continue
        played, _ = play_game(pat, ans2g, seen[comp], crule, ctail2,
                              np.random.default_rng(11))
        fired = len(played) > 1 and guesses[played[1]] == gs_second
        if fired != should:
            failures.append("%s: a %d-green %d-yellow 2-grey reply %s the rule"
                            % (clabel, comp[0], comp[1],
                               "fired" if fired else "did not fire"))
    if len(seen) < 2:
        failures.append("fewer than two 2-grey compositions occurred against "
                        "this opener, so the composition rule was not exercised")
    print("%s: of the 2-grey replies, only the all-yellow one fires (%d "
          "compositions constructed from the strings)" % (clabel, len(seen)))

    # AN EMPTY TABLE ROW MAKES IT THE PLAIN OPENER.  An opener no answer can give
    # that many greys has nothing to choose, and the rule must then never speak
    # after turn one rather than play something arbitrary.
    empty_rule = make_second_rule(gs_opener_g, by_code(None))
    etail = make_tail("answer", guesses, answers, ans2g)
    plain = make_opening_rule([gs_opener_g], tail=etail, adapt=0)
    for seed in range(20):
        w1, _ = play_game(pat, ans2g, draw_answer(len(answers),
                          np.random.default_rng(50 + seed)), empty_rule, etail,
                          np.random.default_rng(60 + seed))
        w2, _ = play_game(pat, ans2g, draw_answer(len(answers),
                          np.random.default_rng(50 + seed)), plain, etail,
                          np.random.default_rng(60 + seed))
        if w1 != w2:
            failures.append("an empty table row did not reproduce the plain opener")
            break
    print("an empty table row reproduces the plain opener exactly")

    # THE TABLE PATH, AND WHAT IT REFUSES.  second_rule_for is what the sweep and
    # the paired comparison both call, so it is checked rather than the class.
    tbl = Table(path="(synthetic)", min_grays=GS_MIN, fire=GS_LABEL,
                groups=[GS_LABEL], openers="guess", seconds="guess",
                answers=len(answers),
                rows={gs_opener: {GS_LABEL: gs_second},
                      guesses[2]: {GS_LABEL: None}})
    r = second_rule_for([gs_opener_g], tbl, guesses)
    if r(turn=0, alive=None, played=[], replies=[], rng=None) != gs_opener_g:
        failures.append("second_rule_for did not open with its own word")
    gs_refusals = 0
    for label, args in (("a two-word opening", ([gs_opener_g, gs_second_g], tbl)),
                        ("an opener with no row", ([5], tbl))):
        try:
            second_rule_for(args[0], args[1], guesses)
            failures.append("second_rule_for accepted %s" % label)
        except SystemExit:
            gs_refusals += 1
    try:
        make_second_rule(gs_opener_g, by_code(gs_opener_g))
        failures.append("the rule accepted a second word equal to the opener")
    except ValueError:
        gs_refusals += 1
    # A CONDITION COVERING EVERY REPLY is a blind two-word opening, and it is
    # refused where the CONDITION is built -- once, by the table -- rather than
    # per opener, because a rule that never fires is legitimate: it is one opener
    # whose rows are all empty, and a sweep must not abort on it.
    try:
        fire_groups(["g0"])
        failures.append("a condition covering every reply was accepted")
    except SystemExit:
        gs_refusals += 1
    print("gray-second refusals: %d (a two-word opening, an opener the table has "
          "no row for, a repeat of the opener, and a condition covering every "
          "reply)" % gs_refusals)

    # THE SWEEP RUNS THE SAME RULE.  sweep_word's make_rule hook is the only way
    # the strategy reaches a sweep, so it is diffed against the rule built here --
    # a hook that silently fell back to the blind opening would otherwise sweep
    # the wrong strategy under the right filename.
    st_hook = sweep_word(pat, ans2g, len(answers), 40, 11, [gs_opener_g], etail,
                         WIN_WITHIN, 0,
                         lambda og: second_rule_for(og, tbl, guesses))
    st_blind = sweep_word(pat, ans2g, len(answers), 40, 11, [gs_opener_g], etail,
                          WIN_WITHIN, 0)
    direct = []
    draw_rng = np.random.default_rng(11)
    pick_rng = np.random.default_rng(11 + PICK_OFFSET)
    direct_rule = make_second_rule(gs_opener_g, by_code(gs_second_g))
    for _ in range(40):
        a_idx = draw_answer(len(answers), draw_rng)
        pl, _ = play_game(pat, ans2g, a_idx, direct_rule, etail, pick_rng)
        direct.append(len(pl))
    if abs(st_hook["mean_guesses"] - sum(direct) / len(direct)) > 1e-12:
        failures.append("sweep_word's make_rule hook did not run the gray-second rule")
    if abs(st_hook["mean_guesses"] - st_blind["mean_guesses"]) < 1e-12:
        failures.append("the hooked sweep matched the BLIND one, so the hook "
                        "may not be doing anything")
    print("the sweep's make_rule hook runs this rule and not the blind opening "
          "(%.4f vs %.4f)" % (st_hook["mean_guesses"], st_blind["mean_guesses"]))

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
    if not gs_fired:
        failures.append("the gray-second rule never fired, so its second word "
                        "was never played")
    if not gs_declined:
        failures.append("the gray-second rule always fired, so the decline "
                        "branch was never exercised")
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
