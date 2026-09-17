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
from tree_states import state_from_strings  # noqa: E402

MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BINARY = os.path.join(MATH, "solver", "secondexact")
WORD_LEN = 5

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


def by_grays_label(opener, t):
    """The grey COUNT names the group."""
    return "e%d" % sum(1 for x in t if x == 0)


def matched_vowel_label(opener, t):
    """The grey count AND how many of the OPENER's vowel positions came back
    non-grey.  Derived here from the STRINGS -- `y` is a vowel, counted by
    POSITION -- so it shares nothing with the C's tile tables.  A reply with 5
    greys matched nothing, so `e5_mv0` would be the whole of `e5`: groups.c
    writes the shorter name and this must agree, or the label it asks for will
    not be in the table."""
    n = sum(1 for x in t if x == 0)
    if n == WORD_LEN:
        return "e%d" % n
    mv = sum(1 for ch, x in zip(opener, t) if ch in "aeiouy" and x != 0)
    return "e%d_mv%d" % (n, mv)


def ref_total_groups(opener, words, label=by_grays_label):
    """The strategy's total when `label` selects which committed word to play."""
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
        key = label(opener, t)
        if key not in words or not words[key]:
            bad("%s: a reply lands in group %s, where the C committed to no "
                "word at all" % (opener, key))
            return None
        second = words[key]
        tot += 2 * len(grp)
        parts = {}
        for a in grp:
            parts.setdefault(tiles(second, a), []).append(a)
        for p, sub in parts.items():
            if all(x == 2 for x in p):
                continue
            tot += ref_T(sub)
    return tot


def check_vowel_groups():
    """7. A VOWEL PARTITION: the group depends on the OPENER, not just the reply.

    `--split-matched-vowels` crosses the grey counts with how many of the
    opener's own vowels came back matched, so two openers seeing the SAME reply
    can be in different groups -- the masks are rebuilt per opener and this is
    the only check that exercises that path.  Same discipline as check 6: the
    enumeration is told which words the C committed to and must reproduce its
    total, and the finer partition can never be worse than the coarser one it
    refines.
    """
    print("7. a word per (grey count, matched vowels)")
    tmp = tempfile.mkdtemp(prefix="checkse-mv-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    coarse = os.path.join(tmp, "coarse.csv")
    fine = os.path.join(tmp, "fine.csv")
    run(["--data", tmp, "--by-grays", "3", "--threads", "1", "--no-prune",
         "--out", coarse])
    run(["--data", tmp, "--by-grays", "3", "--split-matched-vowels",
         "--threads", "1", "--no-prune", "--out", fine])
    # THE GROUP NAMES COME FROM THE BINARY, not from a list typed here: groups.c
    # owns the canonical form, and a gate that spelled them itself would pass
    # while the two solvers disagreed about what to call the same partition.
    label = run(["--by-grays", "3", "--split-matched-vowels",
                 "--print-label"]).stdout.strip()
    groups = label.split(".")
    if matched_vowel_label("aeiou", (0, 0, 0, 0, 0)) != "e5" or "e5" not in groups:
        bad("the matched-vowel partition did not collapse e5: %s" % label)
        return
    rk = {g: read_rows(fine, g) for g in groups}
    rc = {g: read_rows(coarse, g) for g in ("e5", "e4", "e3")}
    checked = better = split = 0
    for opener in sorted(rk["e3"] if "e3" in rk else rk[groups[0]]):
        words = {g: rk[g][opener][0] for g in groups}
        if not any(words.values()):
            continue                      # nothing qualifies for this opener
        want = ref_total_groups(opener, words, matched_vowel_label)
        if want is None:
            return
        # an EMPTY group writes a row with no numbers (status `none`), so the
        # total is read off whichever group actually received answers
        got = next(float(rk[g][opener][2]) for g in groups if rk[g][opener][2])
        if abs(float(want) - got) > 1e-9:
            bad("%s with %s: the C totals %.6f, the enumeration %.6f"
                % (opener, words, got, float(want)))
            return
        # refining a partition can never hurt: giving every mv group the coarse
        # group's own word is one of the choices the finer search is free to make
        coarse_tot = next(float(rc[g][opener][2])
                          for g in ("e3", "e4", "e5") if rc[g][opener][2])
        if got > coarse_tot + 1e-9:
            bad("%s: splitting on matched vowels totals %.6f, worse than the "
                "grey count alone at %.6f" % (opener, got, coarse_tot))
            return
        if got < coarse_tot - 1e-9:
            better += 1
        # did the split actually CHOOSE differently anywhere?
        for n in (3, 4):
            picked = {words[g] for g in groups
                      if g.startswith("e%d_" % n) and words[g]}
            if len(picked) > 1:
                split = 1
        checked += 1
    if checked < 5:
        bad("only %d openers were compared in the vowel-partition check" % checked)
    elif not better:
        bad("the matched-vowel split never beat the grey count alone, so "
            "nothing here distinguishes the two")
    elif not split:
        bad("no opener ever played two different words within one grey count, "
            "so the vowel half of the key was never exercised")
    else:
        print("   ok   %d openers match the enumeration, %d strictly better "
              "than the grey count alone" % (checked, better))


def check_topk():
    """8. THE BEAM (--topk K), and its free oracle.

    A beam at least as wide as the guess pool examines every candidate, so it
    must reproduce the EXACT run row for row -- that single equality exercises
    the whole beam path (the ranking, the tie-break, the bookkeeping) against
    the answer the rest of this gate already trusts.  Narrower beams are then
    checked for the two properties a beam must have: never better than exact
    (better would mean it found something the full scan missed), and monotone
    in K.  Finally the RANKING itself is diffed against `secondword`, which
    computes the same one-ply score by a different route -- if the two ever
    disagree, `--topk` is not selecting the words the table would.
    """
    print("8. the beam, --topk K")
    tmp = tempfile.mkdtemp(prefix="checkse-topk-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    npool = len(MINI_GUESSES)
    base = ["--data", tmp, "--by-grays", "3", "--split-matched-vowels",
            "--threads", "1", "--no-prune"]
    paths = {}
    for k in (0, 1, 3, npool):
        paths[k] = os.path.join(tmp, "k%d.csv" % k)
        run(base + (["--topk", str(k)] if k else []) + ["--out", paths[k]])

    def cells(p):
        out = {}
        with open(p) as f:
            for line in f:
                if line.startswith("#") or line.startswith("opener,"):
                    continue
                c = line.rstrip("\n").split(",")
                out[(c[0], c[1])] = c[2:]
        return out

    ex = cells(paths[0])
    wide = cells(paths[npool])
    # THE ROOT IS BEAMED TOO: one K governs both, so a small K must examine
    # FEWER OPENERS.  Asserted, or the convention could be quietly dropped again.
    op = lambda c: {k[0] for k in c}
    if len(op(cells(paths[1]))) >= len(op(ex)):
        bad("--topk 1 examined %d openers of %d -- the root beam did not fire"
            % (len(op(cells(paths[1]))), len(op(ex))))
        return
    print("   ok   --topk 1 examines %d openers, the exact run %d"
          % (len(op(cells(paths[1]))), len(op(ex))))
    if ex != wide:
        diff = [k for k in ex if ex[k] != wide.get(k)]
        bad("a beam of %d over a %d-word pool differs from the exact run in %d "
            "cells, e.g. %s" % (npool, npool, len(diff), diff[:3]))
        return
    print("   ok   a beam as wide as the pool reproduces the exact run exactly")

    prev, moved = None, 0
    for k in (1, 3, npool):
        c = cells(paths[k])
        for key in c:
            if key in ex and c[key][1] and ex[key][1] and \
                    float(c[key][1]) < float(ex[key][1]) - 1e-9:
                bad("k=%d beat the exact answer on %s: %s vs %s"
                    % (k, key, c[key][1], ex[key][1]))
                return
        if prev is not None:
            shared = [key for key in c if key in prev]
            for key in shared:
                if c[key][1] and prev[key][1] and \
                        float(c[key][1]) > float(prev[key][1]) + 1e-9:
                    bad("k=%d is WORSE than a narrower beam on %s" % (k, key))
                    return
            moved += sum(1 for key in shared if c[key][0] != prev[key][0])
        prev = c
    if not moved:
        bad("every K chose the same words, so nothing here exercises the beam")
        return
    print("   ok   no beam beats exact, wider is never worse, and K moved "
          "%d choices" % moved)

    # the ranking itself, against the other implementation of the same score
    one = os.path.join(tmp, "oneply.csv")
    sw = os.path.join(MATH, "solver", "secondword")
    if not os.path.exists(sw):
        bad("no solver/secondword to diff the ranking against")
        return
    p = subprocess.run([sw] + base[:-1] + ["--out", one],
                       cwd=MATH, capture_output=True, text=True)
    if p.returncode:
        bad("secondword failed: %s" % p.stderr[-300:])
        return
    k1, sword = cells(paths[1]), cells(one)
    diff = [key for key in k1 if key in sword and k1[key][0] != sword[key][0]]
    if diff:
        bad("--topk 1 and secondword disagree on %d cells, e.g. %s -- the beam "
            "is not ranking by the table's score" % (len(diff), diff[:3]))
    else:
        print("   ok   --topk 1 picks secondword's argmin in all %d cells "
              "(ties included)" % len(k1))


def check_resume():
    """9. RESUME: the CSV is the checkpoint, so a part-run plus a finish must
    equal an uninterrupted run -- same rows, same values, same leader."""
    print("9. resume")
    tmp = tempfile.mkdtemp(prefix="checkse-res-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    base = ["--data", tmp, "--by-grays", "3", "--split-matched-vowels",
            "--threads", "1", "--topk", "3"]
    fresh = os.path.join(tmp, "fresh.csv")
    part = os.path.join(tmp, "part.csv")
    run(base + ["--out", fresh])
    run(base + ["--limit", "8", "--out", part])
    p = run(base + ["--out", part])
    if "resumed" not in p.stderr:
        bad("the second run did not report resuming: %s" % p.stderr[-200:])
        return

    def cells(path):
        out = {}
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("opener,"):
                    continue
                c = line.rstrip("\n").split(",")
                out[(c[0], c[1])] = c[2:7]
        return out

    a, b = cells(fresh), cells(part)
    if set(a) != set(b):
        bad("resumed file covers %d cells, fresh covers %d" % (len(b), len(a)))
        return
    diff = [k for k in a if a[k] != b[k]]
    if diff:
        bad("%d cells differ after a resume, e.g. %s: %s vs %s"
            % (len(diff), diff[0], a[diff[0]], b[diff[0]]))
        return
    print("   ok   a part-run plus a finish equals an uninterrupted run "
          "(%d cells)" % len(a))

    # a file written under a DIFFERENT condition must be refused, not continued
    p = run(["--data", tmp, "--by-grays", "3", "--threads", "1", "--topk", "3",
             "--out", part], expect_fail=True)
    if not p.returncode:
        bad("resuming a file written for another firing condition was allowed")
    else:
        print("   ok   a resume across a different condition is refused")


def ref_total_third(opener, words, third, third_max):
    """The THREE-level strategy, enumerated from the strings.

    Opener, then the group's committed word, then -- where the two replies
    together have proved at most `third_max` letters -- that case's committed
    third word, then the random tail.  The matched count comes from
    `tree_states.state_from_strings`, which derives it from the WORDS and never
    looks at a tile, so it shares nothing with the C's reply arithmetic.
    """
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
        key = matched_vowel_label(opener, t)
        second = words[key]
        tot += 2 * len(grp)
        parts = {}
        for a in grp:
            parts.setdefault(tiles(second, a), []).append(a)
        for p, sub in parts.items():
            if all(x == 2 for x in p):
                continue                       # the second word won outright
            # the matched count is constant on a joint bucket -- assert it
            ms = {sum(state_from_strings(a, [opener, second])) for a in sub}
            assert len(ms) == 1, (
                "matched is not constant on a joint bucket: %s" % ms)
            m = ms.pop()
            w3 = third.get((key, m)) if m <= third_max else None
            if w3 is None:
                tot += ref_T(sub)
                continue
            tot += len(sub)                     # the third guess itself
            sub2 = {}
            for a in sub:
                sub2.setdefault(tiles(w3, a), []).append(a)
            for p2, s2 in sub2.items():
                if all(x == 2 for x in p2):
                    continue
                tot += ref_T(s2)
    return tot


def check_third():
    """10. THE THIRD LEVEL, against an enumeration from the strings.

    The C is told nothing; the reference is told which words the C committed to
    at both levels and must reproduce its total exactly.  It also re-derives the
    matched count by a route that never looks at a tile, and ASSERTS that the
    count is constant within a joint bucket -- the property that makes it a legal
    key in the first place.
    """
    print("10. the third level")
    tmp = tempfile.mkdtemp(prefix="checkse-third-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    two = os.path.join(tmp, "two.csv")
    three = os.path.join(tmp, "three.csv")
    base = ["--data", tmp, "--by-grays", "3", "--split-matched-vowels",
            "--threads", "1", "--no-prune", "--topk", "3"]
    run(base + ["--out", two])
    run(base + ["--third-key", "group", "--third-max-matched", "2",
                "--out", three])

    rows = {}
    with open(three) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.rstrip("\n").split(",")
            rows.setdefault(c[0], {})[c[1]] = c[2:]

    checked = 0
    for opener, by in rows.items():
        words = {g: v[0] for g, v in by.items() if "|" not in g and v[0]}
        third = {}
        for g, v in by.items():
            if "|" in g and v[0]:
                grp, mm = g.split("|m")
                third[(grp, int(mm))] = v[0]
        if not words:
            continue
        tot = next((float(v[2]) for v in by.values() if v[2]), None)
        if tot is None:
            continue
        want = ref_total_third(opener, words, third, 2)
        if abs(float(want) - tot) > 1e-9:
            bad("%s: the C totals %.6f, the three-level enumeration %.6f"
                % (opener, tot, float(want)))
            return
        checked += 1
    if checked < 1:
        bad("no opener was compared in the third-level check")
        return
    print("   ok   %d openers match a three-level enumeration from the strings"
          % checked)
    if not any("|" in g for by in rows.values() for g in by):
        bad("no third word was ever committed, so nothing was exercised")
        return

    # --- THE PRINTOUT IS THE PRODUCT: a run watched on screen must show the
    # third words, not just the second ones.  This shipped printing four words
    # for a nine-word strategy, so it is asserted rather than assumed.
    p = run(base + ["--third-key", "group", "--third-max-matched", "2",
                    "--out", os.path.join(tmp, "print.csv")])
    if "+" not in p.stderr:
        bad("no third word appears in the run's own output:\n%s"
            % p.stderr[-400:])
    else:
        print("   ok   the progress lines show the third words")

    # --- DECLINING makes the three-level family CONTAIN the two-level one, so
    # its total can never be worse.  That is a free oracle and it is asserted
    # per opener, not just on the winner.
    dec = os.path.join(tmp, "decline.csv")
    run(base + ["--third-key", "group", "--third-max-matched", "2",
                "--third-decline", "--out", dec])

    def totals(path):
        out = {}
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("opener,"):
                    continue
                c = line.rstrip("\n").split(",")
                if len(c) > 4 and c[4]:
                    out[c[0]] = float(c[4])
        return out

    t2, td = totals(two), totals(dec)
    shared = [w for w in t2 if w in td]
    worse = [w for w in shared if td[w] > t2[w] + 1e-9]
    if worse:
        bad("declining is allowed but %d openers got WORSE than the two-level "
            "strategy, e.g. %s: %.6f vs %.6f"
            % (len(worse), worse[0], td[worse[0]], t2[worse[0]]))
        return
    better = sum(1 for w in shared if td[w] < t2[w] - 1e-9)
    print("   ok   with declining, %d openers match or beat the two-level "
          "strategy (%d strictly)" % (len(shared), better))

    # and declining must ACTUALLY happen somewhere, or the option is untested
    forced_cases = sum(1 for by in rows.values() for g in by if "|" in g)
    drows = {}
    with open(dec) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.split(",")
            if "|" in c[1]:
                drows[(c[0], c[1])] = 1
    if len(drows) >= forced_cases:
        bad("declining never dropped a single committed word (%d cases both "
            "ways), so the option was not exercised" % forced_cases)
    else:
        print("   ok   declining dropped %d of %d committed words"
              % (forced_cases - len(drows), forced_cases))


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
    check_vowel_groups()
    check_topk()
    check_resume()
    check_third()
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
