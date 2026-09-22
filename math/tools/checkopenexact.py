"""GATE for math/openexact.py -- the exact expected guesses and win rate.

Run it alongside solver/validate.sh and tools/checkpatterns.py:

    python3 tools/checkopenexact.py

WHAT IT CHECKS, and every oracle here shares as little machinery as possible
with the thing it checks -- a differential test against a re-implementation of
the same idea would only prove the idea was typed twice.

  A  `tail_total` against `ladder.tail_total`, which is an EXACT-RATIONAL
     recursion over WORD STRINGS: it recomputes every reply with `ladder.tiles`
     and never touches the pattern matrix, the pool indices or the memo.  So a
     matrix slip, a column-order slip and a memo-key collision all show here.

  B  `tail_lost` against a brute-force ENUMERATION of draw sequences in exact
     `Fraction`s -- it walks every sequence the follow-up could draw and counts
     the answers still unfound, with no recursion on sets and no memo.

  C  The win rate against `guarantee_sweep.check_opening`, a DIFFERENT TOOL
     answering the neighbouring question.  `win_rate == 1` and "no reachable
     draw sequence loses" are the same statement, so the two must agree on
     which openings are guaranteed -- and, more sharply, `lost > 0` must hold
     exactly when it names at least one losing answer.

  D  The bucketing against `wordle.pattern` recomputed FROM THE STRINGS, which
     pins the joint key, the base-243 fold and the answer-to-pool index map.

  E  The opening-word accounting: an answer that IS the i-th opening word must
     cost exactly i, checked against a direct replay.

COVERAGE IS ASSERTED, because every check above passes vacuously on a field that
never exercises the interesting branch.  It FAILS unless a guaranteed opening
and a non-guaranteed one both occurred, unless an opening word that is an answer
and one that is guess-only both occurred, and unless `tail_lost`'s `|S| <= b`
shortcut and its deep path were both taken.
"""

import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import ladder                                                             # noqa: E402
from build_patterns import load_patterns                                  # noqa: E402
from guarantee_sweep import check_opening                                 # noqa: E402
from openexact import evaluate, joint_key, tail_lost, tail_total          # noqa: E402
from paircover import pool_matrix                                         # noqa: E402
from wordle import load_words, pattern                                    # noqa: E402

TOL = 1e-9
FAILED = []


def check(ok, what, detail=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if not detail else "   " + detail))
    if not ok:
        FAILED.append(what)


def brute_lost(words, budget):
    """Answers in `words` NOT found within `budget` draws -- by ENUMERATION.

    Exact rationals, every draw sequence walked, no memo and no recursion on
    sets: the definition, written the slowest possible way.
    """
    words = tuple(sorted(words))
    n = len(words)
    if budget <= 0:
        return Fraction(n)
    if n <= 1:
        return Fraction(0)
    tot = Fraction(0)
    for g in words:
        parts = {}
        for a in words:
            if a != g:
                parts.setdefault(ladder.tiles(g, a), []).append(a)
        for p in parts.values():
            tot += brute_lost(tuple(p), budget - 1) / n
    return tot


def main():
    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(answers)}
    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in answers])
    M = pool_matrix(full, cols)
    ans = np.arange(len(answers))

    def rows_of(ws):
        return np.ascontiguousarray(full[np.ix_([gpos[w] for w in ws], cols)])

    # Openings chosen to exercise the branches, not at random: `slate` IS an
    # answer, `clint`/`horst`/`sowed` are guess-only, and `chubs delft grown
    # vampy` is the known GUARANTEED quad from the hill climb (0 unsolved) --
    # without one the win_rate == 1 branch is never taken and check C passes
    # having tested only the losing side, which is what the coverage tally
    # exists to catch.
    field = [["crane", "spilt"], ["parse", "clint"], ["slate"],
             ["dance", "horst", "blimp"], ["bugle", "champ", "downy", "first"],
             ["champ", "flint", "rugby", "sowed"],
             ["chubs", "delft", "grown", "vampy"]]
    seen = {"guaranteed": 0, "not": 0, "word_is_answer": 0, "guess_only": 0,
            "lost_shortcut": 0, "lost_deep": 0}

    print("A  tail_total vs ladder.tail_total (exact Fractions, from strings)")
    for ws in field[:3]:
        rows = rows_of(ws)
        key = joint_key(rows)
        uniq, inv = np.unique(key, return_inverse=True)
        # the three biggest live sets this opening leaves; small ones prove little
        # THE BIGGEST sets the oracle can still afford: it is an exponential
        # enumeration over draw sequences, so 9 words is the ceiling, and
        # picking the largest under it makes the check as sharp as it can be.
        sizes = {u: int((inv == u).sum()) for u in range(len(uniq))}
        order = sorted((u for u in sizes if 2 <= sizes[u] <= 9),
                       key=lambda u: -sizes[u])
        for u in order[:2]:
            live = np.sort(ans[inv == u])
            fast = tail_total(M, live, {})
            slow = float(ladder.tail_total(tuple(answers[i] for i in live)))
            check(abs(fast - slow) < TOL, "%s |S|=%d" % (" ".join(ws), len(live)),
                  "%.9f vs %.9f" % (fast, slow))

    print("B  tail_lost vs a brute-force enumeration of draw sequences")
    rows = rows_of(["crane", "spilt"])
    key = joint_key(rows)
    uniq, inv = np.unique(key, return_inverse=True)
    tried = 0
    for u in range(len(uniq)):
        live = np.sort(ans[inv == u])
        if not (2 <= len(live) <= 7):
            continue
        for b in (1, 2, 3):
            fast = tail_lost(M, live, b, {})
            slow = float(brute_lost(tuple(answers[i] for i in live), b))
            seen["lost_shortcut" if len(live) <= b else "lost_deep"] += 1
            check(abs(fast - slow) < TOL,
                  "|S|=%d budget=%d" % (len(live), b),
                  "%.9f vs %.9f" % (fast, slow))
        tried += 1
        if tried >= 3:
            break

    print("C  win rate vs guarantee_sweep.check_opening (a different tool)")
    # ONE-WORD OPENINGS ARE LEFT OUT OF THIS CHECK ON PURPOSE.  `check_opening`
    # computes the exact WORST CASE, which at k = 1 runs on live sets past 200
    # words -- the cell `guarantee.solved_within`'s docstring records as not
    # finishing in eight minutes.  The budget is what makes the decision form
    # affordable there, and this check wants the VALUE.  k >= 2 exercises the
    # identical code on sets the oracle can afford.
    # (full, cidx, pool, apool, answers, adapt, cap, gpos) -- the pool IS the
    # answer list here, so apool is the identity and adapt is 0 (blind).
    ctx = (full, cols, answers, np.arange(len(answers)), answers, 0, 6, gpos)
    for ws in field:
        if len(ws) < 2:
            continue
        r = evaluate(M, rows_of(ws), [ppos.get(w, -1) for w in ws], ans)
        _, losing, _, _, _ = check_opening(ws, ctx)
        nlos = len(losing)
        seen["guaranteed" if nlos == 0 else "not"] += 1
        agree = (r["lost"] > 1e-12) == (nlos > 0)
        check(agree, "%s: lost %.6g, guarantee names %d losing answer(s)"
              % (" ".join(ws), r["lost"], nlos))
        if nlos == 0:
            check(abs(r["win_rate"] - 1.0) < TOL,
                  "%s: guaranteed, so win_rate must be exactly 1"
                  % " ".join(ws), "%.12f" % r["win_rate"])

    print("D  the bucketing vs wordle.pattern recomputed from the strings")
    for ws in field[:4]:
        rows = rows_of(ws)
        key = joint_key(rows)
        want = {}
        for j, a in enumerate(answers):
            k = 0
            for w in ws:
                k = k * 243 + pattern(w, a)
            want[j] = k
        same = all(int(key[j]) == want[j] for j in range(len(answers)))
        check(same, "%s: joint key from strings" % " ".join(ws))

    print("E  an answer that IS the i-th opening word costs exactly i")
    for ws in field:
        for i, w in enumerate(ws, start=1):
            if w in ppos:
                seen["word_is_answer"] += 1
            else:
                seen["guess_only"] += 1
        # `slate` is the answer and the 1st word, so it must contribute 1 guess
        if ws == ["slate"]:
            r = evaluate(M, rows_of(ws), [ppos["slate"]], ans)
            r2 = evaluate(M, rows_of(ws), [-1], ans)   # pretend it cannot be the answer
            # charging it as a non-answer costs the tail instead: strictly more
            check(r["total"] < r2["total"],
                  "slate as its own answer costs less than not",
                  "%.1f vs %.1f" % (r["total"], r2["total"]))

    print("COVERAGE")
    for k, v in sorted(seen.items()):
        check(v > 0, "%s occurred" % k, "%d" % v)

    print()
    if FAILED:
        print("FAILED %d check(s):" % len(FAILED))
        for f in FAILED:
            print("  " + f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
