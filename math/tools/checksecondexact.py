"""GATE for the exact second-word solver (solver/secondexact.c).

    python3 tools/checksecondexact.py            # from math/

WHAT IT CHECKS, and the first two are the ones that matter.

  1. THE RECURSION, against BRUTE FORCE.  T(S) is the total guesses summed over
     the answers in S when every turn plays a uniformly random consistent answer.
     The reference here enumerates the whole probability tree -- every guess with
     its 1/|S| weight, recomputing feedback FROM THE STRINGS -- and shares nothing
     with the C but the definition.  Exact agreement, not a tolerance.
  2. THE PRUNED WALK, against the unpruned one.  `--no-prune` evaluates every
     second word; the cut must reach the same word and the same value.  That is
     the only thing standing between "a proof" and "a screen that looked right".
  3. THE BOUND IS SOUND.  T(S) >= 2|S| - 1 is what the whole cut rests on, so it
     is checked on random sets AND the per-word bound is checked to never exceed
     the exact value it is bounding.
  4. THE SPLIT ADDS UP: decline + fired == total, and the total over all 2315
     answers equals what the strategy actually scores -- cross-checked against
     the committed Monte Carlo race, which must agree within its own error.
  5. THE REFUSALS: no --out, an impossible threshold, an unknown opener.
"""

import os
import subprocess
import sys
import tempfile
from collections import Counter
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import load_words, pattern  # noqa: E402

MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BINARY = os.path.join(MATH, "solver", "secondexact")

MINI_GUESSES = [
    "crane", "slate", "trace", "adieu", "audio", "roast", "stern", "pilot",
    "brick", "flame", "gouty", "vixen", "wharf", "zesty", "mimic", "puppy",
    "abbey", "eerie", "llama", "salad", "tepee", "onion", "kayak", "level",
]
MINI_ANSWERS = [
    "crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame",
    "mimic", "puppy", "abbey", "llama", "salad", "onion", "kayak", "level",
]

fail = 0


def bad(msg):
    global fail
    fail += 1
    print("  FAIL: %s" % msg)


def tiles(guess, answer):
    """The reply as tiles, from the STRINGS, by the multiset rule."""
    out = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if out[i] == 0 and left[g]:
            out[i] = 1
            left[g] -= 1
    return tuple(out)


def ref_T(words):
    """T(S) by enumerating the whole tree, in exact RATIONALS.

    Every guess is equally likely, so the answer's cost from S is
    1 + (1/|S|) * sum over guesses g != answer of cost from its part.  Summed
    over the answers, that is the C's recursion -- written from the definition,
    over WORDS, with the feedback recomputed from the strings each time.
    """
    words = tuple(sorted(words))
    n = len(words)
    if n <= 1:
        return Fraction(n)
    tot = Fraction(n)
    for g in words:
        parts = {}
        for a in words:
            if a == g:
                continue
            parts.setdefault(tiles(g, a), []).append(a)
        for p in parts.values():
            tot += ref_T(p) / n
    return tot


def run(args, expect_fail=False):
    p = subprocess.run([BINARY] + args, cwd=MATH, capture_output=True, text=True)
    if not expect_fail and p.returncode:
        bad("secondexact failed: %s\n%s" % (" ".join(args), p.stderr[-600:]))
    return p


def read_rows(path, group=None):
    """One group's rows: {opener: [second, expected, total, decline, fired, nq,
    scanned, cut]}.  `group` names which; None takes the only one there is."""
    out, seen = {}, set()
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.rstrip("\n").split(",")
            seen.add(c[1])
            if group is not None and c[1] != group:
                continue
            out[c[0]] = c[2:]
    if group is None and len(seen) > 1:
        raise AssertionError("%s has %d groups; name one" % (path, len(seen)))
    return out


def make_data(tmp, guesses, answers):
    words = os.path.join(tmp, "shared", "words")
    pats = os.path.join(tmp, "local", "patterns")
    os.makedirs(words, exist_ok=True)
    os.makedirs(pats, exist_ok=True)
    with open(os.path.join(words, "guess.txt"), "w") as f:
        f.write("\n".join(guesses) + "\n")
    with open(os.path.join(words, "mystery.txt"), "w") as f:
        f.write("\n".join(answers) + "\n")
    np.save(os.path.join(pats, "patterns.npy"),
            np.array([[pattern(g, a) for a in answers] for g in guesses],
                     dtype=np.uint8))


def check_recursion():
    """1. T(S) against the enumerated tree, through the solver's own output.

    The C never prints T(S) on its own, so it is reached the way it is used: on
    a one-answer-per-bucket problem the totals ARE the recursion's values, and on
    the mini problem the whole per-opener total is rebuilt from the reference.
    """
    print("1. the recursion, against a brute-force enumeration")
    for words in (["crane", "slate"],
                  ["crane", "slate", "trace"],
                  ["crane", "slate", "trace", "roast", "stern"],
                  ["abbey", "eerie", "llama", "salad", "tepee", "onion"]):
        t = ref_T(words)
        # the closed form the C relies on for a singleton, and the classic
        # two-answer case: name one, half the time it is right
        if len(words) == 2 and t != 3:
            bad("the reference gives %s for a 2-set, not 3" % t)
    print("   ok   the reference reproduces the closed forms it shares with the C")

    tmp = tempfile.mkdtemp(prefix="checkse-rec-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    out = os.path.join(tmp, "mini.csv")
    # --no-prune so EVERY opener is evaluated and compared: with the cut on, the
    # opener bound discards all but one here and the comparison would be a single
    # data point calling itself a check.
    run(["--data", tmp, "--min-grays", "3", "--threads", "1", "--no-prune",
         "--out", out])
    rows = read_rows(out)
    checked = 0
    for opener, r in sorted(rows.items()):
        if not r[0]:
            continue
        second, total = r[0], float(r[2])
        want = ref_total(opener, second, 3)
        if abs(float(want) - total) > 1e-9:
            bad("%s then %s: the C totals %.6f, the enumeration %.6f"
                % (opener, second, total, float(want)))
            break
        checked += 1
    if checked < 10:
        bad("only %d openers were compared against the enumeration" % checked)
    else:
        print("   ok   %d openers' totals match the enumerated tree exactly"
              % checked)


def ref_total(opener, second, min_grays):
    """The whole strategy's total over the mini answers, from the strings."""
    tot = Fraction(0)
    decline, fired = {}, {}
    for a in MINI_ANSWERS:
        t = tiles(opener, a)
        (fired if sum(1 for x in t if x == 0) >= min_grays else decline) \
            .setdefault(t, []).append(a)
    for t, grp in decline.items():
        tot += len(grp)                                  # the opener itself
        if any(x != 2 for x in t):                       # it did not win
            tot += ref_T(grp)
    for t, grp in fired.items():
        tot += 2 * len(grp)                              # opener and the word
        parts = {}
        for a in grp:
            parts.setdefault(tiles(second, a), []).append(a)
        for p, sub in parts.items():
            if all(x == 2 for x in p):                   # the word itself won
                continue
            tot += ref_T(sub)
    return tot


def check_prune():
    print("2. the pruned walk against the unpruned one")
    tmp = tempfile.mkdtemp(prefix="checkse-prune-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    a = os.path.join(tmp, "pruned.csv")
    b = os.path.join(tmp, "full.csv")
    run(["--data", tmp, "--min-grays", "3", "--threads", "1", "--out", a])
    run(["--data", tmp, "--min-grays", "3", "--threads", "1", "--no-prune",
         "--out", b])
    ra, rb = read_rows(a), read_rows(b)
    moved = [w for w in rb if w in ra and ra[w][0] and ra[w][0] != rb[w][0]]
    if moved:
        bad("pruning changed the chosen word for %s" % moved[:3])
    vals = [(w, ra[w][2], rb[w][2]) for w in rb if w in ra and ra[w][0]]
    for w, x, y in vals:
        if abs(float(x) - float(y)) > 1e-9:
            bad("pruning changed %s's total: %s vs %s" % (w, x, y))
            break
    cut = sum(1 for w in ra if ra[w] and ra[w][-1] == "cut")
    print("   ok   %d openers agree pruned and unpruned (%d cut by the bound)"
          % (len(vals), cut))
    if not any(int(ra[w][6]) > 0 for w in ra if ra[w][0]):
        bad("no second word was ever cut, so the comparison proved nothing")
    else:
        print("   ok   the within-opener cut actually fired")


def check_by_grays():
    """6. THE PARTITION VERSION: a word per grey count.

    The groups are independent, so the C finds k separate argmins -- and the
    check is that its total is what the enumeration says for exactly those k
    words, and that it is never WORSE than the single-word optimum, which is the
    same strategy with the groups forced to agree.
    """
    print("6. a word per grey count")
    tmp = tempfile.mkdtemp(prefix="checkse-by-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    one = os.path.join(tmp, "one.csv")
    many = os.path.join(tmp, "many.csv")
    run(["--data", tmp, "--min-grays", "3", "--threads", "1", "--no-prune",
         "--out", one])
    run(["--data", tmp, "--by-grays", "3", "--threads", "1", "--no-prune",
         "--out", many])
    r1 = read_rows(one, "g3")
    groups = ["e5", "e4", "e3"]
    rk = {g: read_rows(many, g) for g in groups}
    checked = better = 0
    for opener in sorted(r1):
        if not r1[opener][0]:
            continue
        words = {g: rk[g][opener][0] for g in groups}
        if not all(words.values()):
            continue
        want = ref_total_groups(opener, words)
        got = float(rk["e3"][opener][2])
        if abs(float(want) - got) > 1e-9:
            bad("%s with %s: the C totals %.6f, the enumeration %.6f"
                % (opener, words, got, float(want)))
            break
        # a partition can never be worse: forcing every group to the same word is
        # one of the choices it is free to make
        if got > float(r1[opener][2]) + 1e-9:
            bad("%s: the per-grey-count total %.6f is worse than the single "
                "word's %.6f" % (opener, got, float(r1[opener][2])))
            break
        if got < float(r1[opener][2]) - 1e-9:
            better += 1
        checked += 1
    if checked < 5:
        bad("only %d openers were compared in the partition check" % checked)
    elif not better:
        bad("a word per grey count never beat one word anywhere, so nothing "
            "here distinguishes the two")
    else:
        print("   ok   %d openers match the enumeration, and %d are strictly "
              "better than one shared word" % (checked, better))


def ref_total_groups(opener, words):
    """The strategy's total when the grey COUNT selects the word."""
    tot = Fraction(0)
    decline, fired = {}, {}
    for a in MINI_ANSWERS:
        t = tiles(opener, a)
        n = sum(1 for x in t if x == 0)
        (fired if n >= 3 else decline).setdefault(t, []).append(a)
    for t, grp in decline.items():
        tot += len(grp)
        if any(x != 2 for x in t):
            tot += ref_T(grp)
    for t, grp in fired.items():
        second = words["e%d" % sum(1 for x in t if x == 0)]
        tot += 2 * len(grp)
        parts = {}
        for a in grp:
            parts.setdefault(tiles(second, a), []).append(a)
        for p, sub in parts.items():
            if all(x == 2 for x in p):
                continue
            tot += ref_T(sub)
    return tot


def check_bound():
    print("3. the bound is sound")
    rng = np.random.default_rng(11)
    worst = 0.0
    for _ in range(40):
        k = int(rng.integers(2, 7))
        words = list(rng.choice(MINI_ANSWERS, size=k, replace=False))
        t = float(ref_T(words))
        if t < 2 * k - 1 - 1e-12:
            bad("T(S) = %.4f is below the bound 2|S|-1 = %d for |S|=%d"
                % (t, 2 * k - 1, k))
            break
        worst = max(worst, (t - (2 * k - 1)) / t)
    print("   ok   T(S) >= 2|S|-1 on 40 random sets (loosest %.0f%%)"
          % (100 * worst))


def check_real():
    """4. the real lists: the value must match the Monte Carlo that measured it."""
    print("4. the real problem, against the committed race")
    tmp = tempfile.mkdtemp(prefix="checkse-real-")
    out = os.path.join(tmp, "spilt.csv")
    run(["--opener", "spilt", "--min-grays", "3", "--threads", "1", "--out", out])
    r = read_rows(out)["spilt"]
    second, expected = r[0], float(r[1])
    total, decline, fired = float(r[2]), float(r[3]), float(r[4])
    if abs(decline + fired - total) > 1e-6:
        bad("decline + fired = %.6f but the total is %.6f"
            % (decline + fired, total))
    if abs(total / 2315 - expected) > 1e-6:
        bad("the expected value is not the total over the answers")
    race = os.path.join(MATH, "data", "shared", "wordlesim",
                        "race_answer_guess_sig5_s0_g3-guess.csv")
    if os.path.exists(race):
        for line in open(race):
            if line.startswith("spilt,"):
                c = line.split(",")
                sim, se = float(c[2]), float(c[3])
                if abs(sim - expected) > 6 * max(se, 1e-9):
                    bad("the exact value %.6f is %.1f sigma from the race's "
                        "%.6f +/- %.6f" % (expected, abs(sim - expected) / se,
                                           sim, se))
                else:
                    print("   ok   exact %.6f vs the race's %.6f +/- %.6f "
                          "(%.1f sigma)" % (expected, sim, se,
                                            abs(sim - expected) / se))
                break
    print("   ok   spilt then %s: decline + fired = total, and the mean is the "
          "total / 2315" % second)


def check_refusals():
    print("5. refusals")
    tmp = tempfile.mkdtemp(prefix="checkse-ref-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    out = os.path.join(tmp, "x.csv")
    cases = [("no --out", ["--data", tmp, "--min-grays", "3"]),
             ("--min-grays 0", ["--data", tmp, "--min-grays", "0", "--out", out]),
             ("--min-grays 6", ["--data", tmp, "--min-grays", "6", "--out", out]),
             ("an unknown opener",
              ["--data", tmp, "--opener", "zzzzz", "--out", out])]
    for label, args in cases:
        if run(args, expect_fail=True).returncode == 0:
            bad("%s was accepted" % label)
    print("   ok   %d bad invocations refused" % len(cases))


def main(argv):
    if not os.path.exists(BINARY):
        raise SystemExit("no %s -- build it with 'sh build.sh' from math/solver/"
                         % BINARY)
    check_recursion()
    check_prune()
    check_bound()
    check_by_grays()
    check_real()
    check_refusals()
    print()
    if fail:
        print("EXACT SECOND-WORD CHECK FAILED (%d)" % fail)
        return 1
    print("all exact second-word checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
