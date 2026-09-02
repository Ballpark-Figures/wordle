"""Gate for `antiwordle.py` — the model checked against independent references.

Antiwordle's whole model is the claim that a grey tile CAPS A LETTER'S COUNT
rather than banning the letter, and everything downstream (the search terminates,
repeats are impossible, no history belongs in the state) is a consequence.  None
of that is checkable by inspection, so it is checked here, six ways:

  1. VECTORIZED vs SCALAR legality.  `GuessSpace.legal_mask` (bitset intersections)
     against `legal()` (letter by letter), over every word in the list, for
     constraints drawn from real random play.

  2. ACCUMULATED vs REPLAYED legality.  `legal()` reads one accumulated `Cons`;
     the reference re-derives permission from the RAW TRANSCRIPT, checking every
     tile of every past guess directly and never building a lattice at all.  Two
     genuinely different routes to the same predicate, which is what makes this a
     differential test rather than a restatement.

  3. THE ANSWER IS ALWAYS LEGAL, over random walks — the invariant that keeps play
     from dead-ending and makes the endgame well posed.

  4. EVERY LEGAL NON-ANSWER GUESS STRICTLY TIGHTENS.  This is the DAG argument the
     search rests on, and its corollary is checked alongside: a word just played
     is never legal again, so antiwordle's no-repeat rule is redundant and no
     guess history belongs in the state.  A single counterexample here would mean
     the max-search can cycle and is unbounded.

  5. CANDIDATES ARE LEGAL (S subset of L).  Any word still consistent with the
     feedback is playable — the antiwordle analogue of the hard-mode property
     optturns' shortcuts depend on.

  6. `longest_stall` vs BRUTE FORCE.  The memoised, child-deduplicated longest
     path against a flat un-memoised recursion using only scalar `legal()`, on
     small random word lists where the naive search still terminates.

Plus a sanity check that the pattern matrix column the search is driven by agrees
with `wordle.pattern` recomputed from the strings.

WHAT THIS CANNOT DO is verify the RULES.  It proves the implementation matches an
independent reading of the same rules; whether that reading is antiwordle.com's
needs a game played on the site and diffed against `replay()`.

    python3 tools/checkantiwordle.py [--seed N] [--quick]
"""
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import (ALL_GREEN, TRITS, Cons, GuessSpace, StallSearch,
                        cons_none, legal, step)
from build_patterns import load_patterns
from wordle import WORD_LEN, load_words, pattern

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)
    return ok


# ------------------------------------------------------- independent reference

class Transcript:
    """Legality re-derived from the raw tile history, accumulating nothing.

    Deliberately a different shape from `Cons`: it keeps the (guess, pattern)
    pairs and re-reads every tile of every past guess on each question. Slow, and
    that is the point — it shares no code path with the thing it checks.
    """

    def __init__(self):
        self.history = []

    def play(self, guess, code):
        self.history.append((guess, TRITS[code]))

    def permits(self, word):
        for guess, trits in self.history:
            for i, t in enumerate(trits):
                c = guess[i]
                # how many copies of c that guess PROVED the answer holds
                shown = sum(1 for j, ch in enumerate(guess)
                            if ch == c and trits[j] != 0)
                if t == 2:                      # red: pinned to this square
                    if word[i] != c:
                        return False
                elif t == 1:                    # yellow: must move, must persist
                    if word[i] == c:
                        return False
                    if word.count(c) < shown:
                        return False
                else:                           # grey: this copy does not exist
                    if word.count(c) > shown:
                        return False
        return True


def tighter(a, b):
    """(a is at least as tight as b, a is strictly tighter than b)."""
    strict = False
    for x, y in zip(a.green, b.green):
        if y >= 0 and x != y:
            return False, False
        if x >= 0 and y < 0:
            strict = True
    for c in range(26):
        if a.minc[c] < b.minc[c] or a.maxc[c] > b.maxc[c]:
            return False, False
        if a.yban[c] & b.yban[c] != b.yban[c]:
            return False, False
        if (a.minc[c] > b.minc[c] or a.maxc[c] < b.maxc[c]
                or a.yban[c] != b.yban[c]):
            strict = True
    return True, strict


def random_walk(space, pat_col, answer, rng, max_steps=12):
    """Play random legal non-answer words until only the answer is left.

    Yields (constraint before, chosen word index, constraint after) so a caller
    can test any per-move property. This is the state distribution that actually
    matters — states reachable by real play, not synthetic constraints.
    """
    cons = cons_none(space.word_len)
    for _ in range(max_steps):
        idx = [int(g) for g in space.legal_list(cons) if g != answer]
        if not idx:
            return
        g = rng.choice(idx)
        after = step(cons, space.letter_tuples[g], TRITS[pat_col[g]])
        yield cons, g, after
        cons = after


# ------------------------------------------------------------------- the tests

def test_pattern_column(space, PAT, answers, ai):
    """The matrix column driving the search matches pattern() from the strings."""
    a = answers[ai]
    bad = [space.words[g] for g in range(0, space.n, 97)
           if int(PAT[g, ai]) != pattern(space.words[g], a)]
    check("pattern column agrees with wordle.pattern", not bad, f"answer={a}")


def test_mask_vs_scalar(space, PAT, answers, rng, walks):
    """Vectorized legal_mask == scalar legal(), word for word."""
    worst, states = None, 0
    for ai in rng.sample(range(len(answers)), walks):
        answer = space.index[answers[ai]]
        col = np.asarray(PAT[:, ai])
        for cons, _, _ in random_walk(space, col, answer, rng):
            states += 1
            mask = space.legal_mask(cons)
            for g in range(space.n):
                if bool(mask[g]) != legal(cons, space.words[g]):
                    worst = (space.words[g], cons)
                    break
            if worst:
                break
        if worst:
            break
    check("legal_mask == legal() over the full list", worst is None,
          f"{states} states x {space.n} words" if worst is None else str(worst[0]))


def test_accumulated_vs_transcript(space, PAT, answers, rng, walks):
    """Accumulated Cons == permission re-derived from the raw tile history."""
    bad, states = None, 0
    for ai in rng.sample(range(len(answers)), walks):
        answer = space.index[answers[ai]]
        col = np.asarray(PAT[:, ai])
        ref = Transcript()
        for cons, g, after in random_walk(space, col, answer, rng):
            ref.play(space.words[g], int(col[g]))
            states += 1
            for probe in rng.sample(range(space.n), 400):
                if legal(after, space.words[probe]) != ref.permits(space.words[probe]):
                    bad = (space.words[probe], space.words[g], answers[ai])
                    break
            if bad:
                break
        if bad:
            break
    check("accumulated Cons == raw-transcript permission", bad is None,
          f"{states} states x 400 probes" if bad is None else str(bad))


def test_answer_always_legal(space, PAT, answers, rng, walks):
    """The answer is legal in every reachable state, so play never dead-ends."""
    bad, states = None, 0
    for ai in rng.sample(range(len(answers)), walks):
        answer = space.index[answers[ai]]
        col = np.asarray(PAT[:, ai])
        for _, _, after in random_walk(space, col, answer, rng):
            states += 1
            if not legal(after, answers[ai]):
                bad = answers[ai]
                break
        if bad:
            break
    check("the answer stays legal in every reachable state", bad is None,
          f"{states} states" if bad is None else str(bad))


def test_strictly_tightens(space, PAT, answers, rng, walks):
    """Every legal non-answer guess strictly tightens -- the DAG argument.

    And its corollary: the word just played is no longer legal, so a repeat is
    impossible without any history in the state.
    """
    loose, repeat, moves = None, None, 0
    for ai in rng.sample(range(len(answers)), walks):
        answer = space.index[answers[ai]]
        col = np.asarray(PAT[:, ai])
        for before, g, after in random_walk(space, col, answer, rng):
            moves += 1
            ok, strict = tighter(after, before)
            if not (ok and strict):
                loose = (space.words[g], answers[ai])
                break
            if legal(after, space.words[g]):
                repeat = (space.words[g], answers[ai])
                break
        if loose or repeat:
            break
    check("every legal non-answer guess STRICTLY tightens", loose is None,
          f"{moves} moves" if loose is None else str(loose))
    check("a played word is never legal again (no-repeat is redundant)",
          repeat is None, f"{moves} moves" if repeat is None else str(repeat))


def test_candidates_are_legal(space, PAT, answers, rng, walks):
    """Every word still consistent with the feedback is playable (S subset of L)."""
    bad, states = None, 0
    aidx = np.array([space.index[w] for w in answers])
    for ai in rng.sample(range(len(answers)), walks):
        answer = space.index[answers[ai]]
        col = np.asarray(PAT[:, ai])
        alive = np.ones(len(answers), dtype=bool)
        for cons, g, after in random_walk(space, col, answer, rng):
            alive &= np.asarray(PAT[g, :]) == col[g]
            states += 1
            for j in np.flatnonzero(alive):
                if not legal(after, answers[j]):
                    bad = (answers[j], answers[ai])
                    break
            if bad:
                break
        if bad:
            break
    check("candidates are always legal (S subset of L)", bad is None,
          f"{states} states" if bad is None else str(bad))


def brute_stall(words, cons, answer, pat_of, word_len):
    """Un-memoised, un-deduplicated longest stall, on scalar legal() only."""
    best = 1
    for w in words:
        if w == answer or not legal(cons, w):
            continue
        letters = tuple(ord(ch) - 97 for ch in w)
        child = step(cons, letters, TRITS[pat_of[w]])
        v = 1 + brute_stall(words, child, answer, pat_of, word_len)
        if v > best:
            best = v
    return best


def test_stall_vs_brute(answers, rng, trials, size):
    """The real search against the flat recursion, on small random lists."""
    bad = None
    for _ in range(trials):
        answer = rng.choice(answers)
        pool = rng.sample([w for w in answers if w != answer], size - 1) + [answer]
        rng.shuffle(pool)
        space = GuessSpace(pool)
        ai = space.index[answer]
        col = np.array([pattern(w, answer) for w in pool])
        got = StallSearch(space, col, ai).value(cons_none())
        want = brute_stall(pool, cons_none(), answer,
                           {w: int(col[space.index[w]]) for w in pool}, WORD_LEN)
        if got != want:
            bad = (answer, got, want)
            break
    check("longest_stall == brute force on small lists", bad is None,
          f"{trials} lists of {size}" if bad is None else str(bad))


def test_bounds_admissible(answers, rng, trials, size):
    """Neither upper bound ever falls BELOW the true value.

    Checked separately rather than only through the pruned search, because an
    inadmissible bound does not always change an answer — it changes it only when
    it happens to cut the winning branch, so a search that agrees on a few cases
    is weak evidence. Here each bound is compared against the exact value directly,
    at every state an optimal line passes through.
    """
    bad = None
    for _ in range(trials):
        answer = rng.choice(answers)
        pool_words = rng.sample([w for w in answers if w != answer], size - 1)
        space = GuessSpace(pool_words + [answer])
        ai = space.index[answer]
        col = np.array([pattern(w, answer) for w in pool_words + [answer]])
        search = StallSearch(space, col, ai)
        cons = cons_none()
        while True:
            val = search.value(cons)
            words = int(space.legal_mask(cons).sum())
            res = search.resource_pool(cons) + 1
            if val > words or val > res:
                bad = (answer, val, words, res)
                break
            _, g = search.memo[cons]
            if g is None:
                break
            cons = step(cons, space.letter_tuples[g], TRITS[int(col[g])])
        if bad:
            break
    check("both bounds are admissible (never below the true value)", bad is None,
          f"{trials} lists of {size}" if bad is None
          else f"answer={bad[0]} value={bad[1]} word-bound={bad[2]} resource={bad[3]}")


def state_after(space, PAT, answers, answer, prefix=("sulky", "tempo")):
    """The constraint after playing a fixed opening prefix against `answer`.

    An arbitrary prefix, and it has to be one: an EMPTY board is out of reach for
    the exhaustive reference, which is the whole reason the bounds exist, so every
    differential test here runs from mid-game.
    """
    col = np.asarray(PAT[:, answers.index(answer)])
    cons = cons_none()
    for w in prefix:
        wi = space.index[w]
        cons = step(cons, space.letter_tuples[wi], TRITS[int(col[wi])])
    return cons, col


def roomiest(space, PAT, answers, rng, cases):
    """The `cases` sampled answers left with the most room after the prefix.

    Most answers are throttled to almost nothing, and a two-node search proves
    nothing about pruning or memo keying — the first cut of this gate happily
    "passed" on 135-node states while the pruning it was testing did 4% of what it
    should have. Ranking by surviving legal words puts the work where it counts.
    """
    sample = rng.sample(answers, 20 * cases)
    ranked = sorted(sample, key=lambda w: -int(
        space.legal_mask(state_after(space, PAT, answers, w)[0]).sum()))
    return ranked[:cases]


def test_pruned_equals_exhaustive(space, PAT, answers, rng, cases):
    """The pruned search == the exhaustive one it replaced, on the real lists.

    The bounds' own oracle: pruning is sound iff switching it off cannot change an
    answer.
    """
    bad, seen = None, []
    for answer in roomiest(space, PAT, answers, rng, cases):
        cons, col = state_after(space, PAT, answers, answer)
        gi = space.index[answer]
        fast = StallSearch(space, col, gi)
        slow = StallSearch(space, col, gi, prune=False)
        vf, vs = fast.value(cons), slow.value(cons)
        seen.append(f"{answer}={vf} ({slow.nodes}->{fast.nodes} nodes)")
        if vf != vs:
            bad = (answer, vf, vs)
            break
    check("pruned search == exhaustive search", bad is None,
          "; ".join(seen) if bad is None else str(bad))


def test_set_memo_matches(space, PAT, answers, rng, cases):
    """Keying the memo on the LEGAL SET changes no value — the theorem, tested.

    The claim is that the value depends only on which words are still playable,
    not on the constraint that made them so: a guess's effect D(g) is fixed by
    (g, its feedback) and does not consult the constraint, so a word already legal
    stays legal exactly when it satisfies D(g). If that is wrong, two states
    sharing a legal set have different values and set-keying returns one of them
    for the other — silently, and only sometimes, which is why it is checked
    against the constraint-keyed search rather than trusted from the argument.
    """
    bad, seen = None, []
    for answer in roomiest(space, PAT, answers, rng, cases):
        cons, col = state_after(space, PAT, answers, answer)
        gi = space.index[answer]
        bysets = StallSearch(space, col, gi, set_memo=True)
        bycons = StallSearch(space, col, gi, set_memo=False)
        vset, vcons = bysets.value(cons), bycons.value(cons)
        seen.append(f"{answer}={vset} ({bycons.nodes}->{bysets.nodes} nodes, "
                    f"{bysets.set_hits} set hits)")
        if vset != vcons:
            bad = (answer, vset, vcons)
            break
    check("legal-set memo == constraint memo", bad is None,
          "; ".join(seen) if bad is None else str(bad))


def main():
    argv = sys.argv[1:]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 12345
    quick = "--quick" in argv
    rng = random.Random(seed)

    guesses = load_words("guess")
    answers = load_words("mystery")
    PAT = load_patterns()
    print(f"antiwordle gate: {len(guesses)} guesses, {len(answers)} answers, "
          f"pattern matrix {PAT.shape}, seed {seed}"
          + ("  [quick]" if quick else ""))
    space = GuessSpace(guesses)
    walks = 2 if quick else 6

    print("\npattern matrix")
    test_pattern_column(space, PAT, answers, rng.randrange(len(answers)))

    print("\nlegality, two ways")
    test_mask_vs_scalar(space, PAT, answers, rng, 1 if quick else 2)
    test_accumulated_vs_transcript(space, PAT, answers, rng, walks)

    print("\ninvariants the search rests on")
    test_answer_always_legal(space, PAT, answers, rng, walks * 4)
    test_strictly_tightens(space, PAT, answers, rng, walks * 4)
    test_candidates_are_legal(space, PAT, answers, rng, walks)

    print("\nthe search itself")
    test_stall_vs_brute(answers, rng, 3 if quick else 8, 14 if quick else 18)
    test_bounds_admissible(answers, rng, 4 if quick else 12, 20 if quick else 40)
    test_pruned_equals_exhaustive(space, PAT, answers, rng, 2 if quick else 5)
    test_set_memo_matches(space, PAT, answers, rng, 2 if quick else 5)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s): " + ", ".join(FAILS))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
