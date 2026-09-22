#!/usr/bin/env python3
"""THE GATE for `secondexact --ladder`: one committed word per level, each fired
by its own threshold on the matched letters.

    python3 tools/checkladder.py           # ~40s
    python3 tools/checkladder.py --real    # + the real-list oracles (~1 min)

WHAT IT CHECKS, and why each one catches something the others cannot:

 1. THE VALUE, against `math/ladder.py`.  The reference works over WORDS,
    recomputes every reply from the STRINGS by the multiset rule, and sums the
    random tail in exact RATIONALS.  It shares no array, no pattern matrix and no
    encoding with the C.  Run with the thresholds PINNED, so both are pricing the
    same strategy rather than two searches agreeing by luck.

 2. THE SEARCH, against a brute force that enumerates every (word, threshold) at
    every level with no bound, no beam and no ordering.  Check 1 prices what the
    C chose; only this says the choice was RIGHT, and it is what would catch a
    bound cutting a genuine optimum.

 3. THE LEVEL-2 ORACLE, the load-bearing one: a 2-level ladder with threshold T
    pinned must equal `--group g<6-T>` EXACTLY, because after ONE guess the board
    is five tiles and matched is 5 minus the greys.  Two code paths, one number,
    and the group path is the one `checksecondexact.py` already validates.

 4. MONOTONICITY in the depth.  A deeper ladder can always set its extra
    threshold to 0 and never fire, so it can never come out worse.  COVERAGE IS
    ASSERTED: it fails if depth never actually changed the answer.

 5. THE BLIND CASE.  Every threshold pinned to 6 fires always, so the ladder is a
    blind N-word opening -- a structurally different strategy, and the one case
    where no bucket ever leaves early.

 6. THE MATCHED-LETTER KEY, three ways: the C's own count, `ladder.py` from the
    strings, and `tree_states.state_from_strings`, which never looks at a tile.
    Coverage is asserted on the two cases a distinct-letter word never produces.

 7. RESUME.  A half-written CSV must continue to the same answer AND report the
    same ladder, since the words live only in the file once an opener is done.

 8. THE REFUSALS, each of which exists because the alternative is a wrong number
    under a right-looking name.

THE MINI PROBLEM IS BUILT SO COMMITTED WORDS ACTUALLY WIN, and that is not a
detail: on an answer set where any guess separates everything, the random tail is
already optimal, every ladder declines, and checks 2, 4 and 5 prove nothing.
`checksecondexact.py`'s 16-word problem is exactly like that.  Here the answers
are `aaaab`..`aaaat` -- they differ in ONE position, so an answer played as a
guess eliminates only itself and the tail costs 1+2+...+n -- while the guess list
also holds words probing four of the distinguishing letters at once.  That is the
real lists' asymmetry in miniature: the tail draws from CANDIDATES, which split
each other badly, and a committed word is chosen to split them well.

Run it alongside `solver/validate.sh`, `tools/checkpatterns.py` and
`tools/checksecondexact.py`.
"""

import os
import subprocess
import sys
import tempfile
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.dirname(HERE)
sys.path.insert(0, MATH)
sys.path.insert(0, HERE)

from wordle import pattern                                    # noqa: E402
import ladder as LAD                                          # noqa: E402

BINARY = os.path.join(MATH, "solver", "secondexact")

fail = 0


def bad(msg):
    global fail
    fail += 1
    print("  FAIL: %s" % msg)


# THE CONFUSABLE FAMILY.  Every answer is `aaaa` plus one distinguishing letter,
# so playing one as a guess splits the rest into a SINGLE bucket -- the random
# tail costs 1+2+...+n.  The splitters probe four distinguishing letters at once
# in positions 0..3, never in position 4, so a splitter can never win outright
# and is always a pure probe.
_TAIL = "bcdefghijklmnopqrst"
MINI_ANSWERS = ["aaaa" + c for c in _TAIL]                     # 19
MINI_SPLITTERS = [
    "bcdea", "fghia", "jklma", "nopqa", "rstba",
    "cdefa", "ghija", "klmna", "opqra", "stbca",
    "bfjna", "cgkoa", "dhlpa", "eimqa", "aabbc",
]
MINI_GUESSES = MINI_ANSWERS + MINI_SPLITTERS                   # 34

# A SMALLER COPY for the brute force, which is a product over levels -- but not
# so small that the tail already wins at level 3, or the nested search would go
# untested.  The coverage assertion below is what holds this honest.
SMALL_ANSWERS = ["aaaa" + c for c in "bcdefghijklmn"]          # 13
SMALL_SPLITTERS = ["bcdea", "fghia", "jklma", "cdefa", "ghija", "klmna"]
SMALL_GUESSES = SMALL_ANSWERS + SMALL_SPLITTERS                # 19


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


def run(args, expect_fail=False):
    p = subprocess.run([BINARY] + args, cwd=MATH, capture_output=True, text=True)
    if not expect_fail and p.returncode:
        bad("secondexact failed: %s\n%s" % (" ".join(args), p.stderr[-800:]))
    return p


def read_ladders(path):
    """{opener: (total, [(word|None, threshold), ...])} from a ladder CSV."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.rstrip("\n").split(",")
            ow, fires = c[0], c[1]
            if fires == "ladder":
                if len(c) < 5 or not c[4]:
                    continue                       # a row the bound CUT
                out.setdefault(ow, [None, []])[0] = float(c[4])
            elif fires.startswith("L") and "|t" in fires:
                d = int(fires[1:fires.index("|")])
                t = int(fires[fires.index("|t") + 2:])
                w = c[2] if c[2] != "-" else None
                ent = out.setdefault(ow, [None, []])
                while len(ent[1]) < d - 1:
                    ent[1].append((None, 0))
                ent[1][d - 2] = (w, t)
    return {k: (v[0], v[1]) for k, v in out.items() if v[0] is not None}


def total_of(path):
    return min((t for t, _ in read_ladders(path).items().__iter__()), default=None)


def best_total(path):
    got = read_ladders(path)
    return min((t for t, _ in got.values()), default=None)


# --------------------------------------------------------------------------- 1
def check_value():
    """The C's total against ladder.py, on PINNED thresholds so both price one
    strategy.  The reference shares no machinery with the C: words not indices,
    replies from the strings, rationals not doubles."""
    print("1. the value, against math/ladder.py from the strings")
    tmp = tempfile.mkdtemp(prefix="checklad-val-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    checked, fired = 0, 0
    for pins in ("2", "2,2", "2,2,2", "3,2,2,2"):
        n = len(pins.split(",")) + 1
        out = os.path.join(tmp, "v%d.csv" % n)
        run(["--data", tmp, "--ladder", str(n), "--topk", "4", "--threads", "1",
             "--no-prune", "--limit", "8", "--pin-thresholds", pins,
             "--out", out])
        got = read_ladders(out)
        if not got:
            bad("no ladder rows for --pin-thresholds %s" % pins)
            continue
        for ow, (total, rungs) in sorted(got.items()):
            want = LAD.ladder_total(ow, [(w, t) for w, t in rungs], MINI_ANSWERS)
            if abs(float(want) - total) > 1e-6:
                bad("%s pins=%s: C says %.6f, the reference says %.6f for %s"
                    % (ow, pins, total, float(want),
                       " ".join("%s<%d" % (w or "-", t) for w, t in rungs)))
                return
            checked += 1
            fired += sum(1 for w, _ in rungs if w is not None)
    if not fired:
        bad("every pinned ladder declined at once, so nothing was priced")
        return
    print("   ok   %d ladders priced identically by the C and the reference "
          "(%d committed words in them)" % (checked, fired))


# --------------------------------------------------------------------------- 2
def brute_ladder(opener, answers, guesses, levels):
    """THE DEFINITION, ENUMERATED: every (word, threshold) at every level, no
    bound, no beam, no ordering, exact rationals.  Returns (total, rungs).

    A bucket carries the history that produced it, so the matched count is
    recomputed from the strings at every level rather than carried as a number
    the search could corrupt.
    """
    def tail(buckets):
        return sum(LAD.tail_total(tuple(sorted(m))) for m, _, _ in buckets)

    def search(buckets, left):
        if not buckets:
            return Fraction(0), [(None, 0)] * left
        if left == 0:
            return tail(buckets), []
        best, arg = tail(buckets), [(None, 0)] * left      # threshold 0: decline
        mat = [LAD.matched_letters(g, r) for _, g, r in buckets]
        for t in sorted({c + 1 for c in mat}):
            fire = [b for b, c in zip(buckets, mat) if c < t]
            rest = [b for b, c in zip(buckets, mat) if c >= t]
            if not fire:
                continue
            base = tail(rest)
            for w in guesses:
                cost = base
                kids = []
                for members, gs, rs in fire:
                    cost += len(members)               # this guess, per answer
                    parts = {}
                    for a in members:
                        parts.setdefault(LAD.tiles(w, a), []).append(a)
                    for p, mem in parts.items():
                        if all(x == 2 for x in p):
                            continue                   # w was the answer
                        kids.append((mem, gs + [w], rs + [p]))
                sub, rung = search(kids, left - 1)
                if cost + sub < best:
                    best, arg = cost + sub, [(w, t)] + rung
        return best, arg

    root = {}
    for a in answers:
        root.setdefault(LAD.tiles(opener, a), []).append(a)
    tot = Fraction(len(answers))                           # the opener, per answer
    buckets = [(mem, [opener], [p]) for p, mem in root.items()
               if not all(x == 2 for x in p)]
    sub, arg = search(buckets, levels - 1)
    return tot + sub, arg


def check_search():
    """The C's ARGMIN against the brute force.  A beam wider than the word list
    takes the beam out of the picture, so any disagreement is the SEARCH."""
    print("2. the search, against a brute-force enumeration")
    for levels, guesses, answers, want_words, tag in (
            (2, MINI_GUESSES, MINI_ANSWERS, 1, "the full mini problem"),
            (3, SMALL_GUESSES, SMALL_ANSWERS, 2,
             "a smaller one, two committed levels")):
        tmp = tempfile.mkdtemp(prefix="checklad-srch-")
        make_data(tmp, guesses, answers)
        ow = guesses[-2]                     # a splitter, so the ladder matters
        out = os.path.join(tmp, "s.csv")
        run(["--data", tmp, "--ladder", str(levels), "--topk",
             str(len(guesses) + 5), "--threads", "1", "--opener", ow,
             "--out", out])
        got = read_ladders(out)
        if ow not in got:
            bad("no row for %s at depth %d" % (ow, levels))
            return
        total, rungs = got[ow]
        best, arg = brute_ladder(ow, answers, guesses, levels)
        if abs(float(best) - total) > 1e-6:
            bad("%s depth %d: brute force %.6f (%s), the C %.6f (%s)"
                % (ow, levels, float(best),
                   " ".join("%s<%s" % (w or "-", t) for w, t in arg), total,
                   " ".join("%s<%s" % (w or "-", t) for w, t in rungs)))
            return
        # COVERAGE.  A brute-force optimum that declines is still an agreement,
        # but it exercises no committed word and none of the nesting -- so the
        # depth-3 case is required to commit at BOTH levels.
        got_words = sum(1 for w, _ in arg if w is not None)
        if got_words < want_words:
            bad("the brute-force optimum at depth %d commits %d words, needed "
                "%d -- the search was not exercised" % (levels, got_words,
                                                        want_words))
            return
        print("   ok   %s: %.6f, the brute-force optimum (%s)"
              % (tag, total, " ".join("%s<%s" % (w or "-", t) for w, t in arg)))


# --------------------------------------------------------------------------- 3
def check_group_oracle(real=False):
    """A 2-LEVEL LADDER IS A GROUP CONDITION.  After one guess the board is five
    tiles, so matched = 5 - greys and `matched < T` is exactly `greys >= 6 - T`.
    So `--ladder 2 --pin-thresholds T` and `--min-grays 6-T` are the same
    strategy reached by two searches sharing no layout and no accounting."""
    print("3. level 2 IS the group g<6-T>")
    tmp = tempfile.mkdtemp(prefix="checklad-grp-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    agreed = 0
    for t in (2, 3, 4):
        g = LAD.grays_of_threshold(t)
        a = os.path.join(tmp, "lad%d.csv" % t)
        b = os.path.join(tmp, "grp%d.csv" % t)
        run(["--data", tmp, "--ladder", "2", "--topk", "40", "--threads", "1",
             "--no-prune", "--pin-thresholds", str(t), "--out", a])
        run(["--data", tmp, "--min-grays", str(g), "--topk", "40",
             "--threads", "1", "--no-prune", "--out", b])
        lad = read_ladders(a)
        grp = {}
        with open(b) as f:
            for line in f:
                if line.startswith("#") or line.startswith("opener,"):
                    continue
                c = line.rstrip("\n").split(",")
                if len(c) > 4 and c[4]:
                    grp[c[0]] = (float(c[4]), c[2])
        common = set(lad) & set(grp)
        if not common:
            bad("no openers in common at T=%d / g%d" % (t, g))
            return
        for ow in sorted(common):
            lt, rungs = lad[ow]
            gt, gw = grp[ow]
            if abs(lt - gt) > 1e-9:
                bad("%s: ladder T=%d gives %.6f, --min-grays %d gives %.6f"
                    % (ow, t, lt, g, gt))
                return
            lw = rungs[0][0] if rungs else None
            if lw is not None and gw and lw != gw:
                bad("%s: ladder picks %s, --min-grays %d picks %s at the same "
                    "total, so the tie-break disagrees" % (ow, lw, g, gw))
                return
            agreed += 1
    print("   ok   %d (opener, threshold) cells agree exactly across the two "
          "code paths" % agreed)

    if not real:
        return
    # THE SAME ORACLE ON THE REAL LISTS, where a bucket is hundreds of answers
    # deep and the tail recursion is doing real work.
    tmp2 = tempfile.mkdtemp(prefix="checklad-grpreal-")
    t = 3
    g = LAD.grays_of_threshold(t)
    a = os.path.join(tmp2, "lad.csv")
    b = os.path.join(tmp2, "grp.csv")
    run(["--ladder", "2", "--topk", "8", "--pin-thresholds", str(t),
         "--opener", "soare", "--out", a])
    run(["--min-grays", str(g), "--topk", "8", "--opener", "soare", "--out", b])
    lad = read_ladders(a)
    gt = None
    with open(b) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.rstrip("\n").split(",")
            if len(c) > 4 and c[4]:
                gt = float(c[4])
    if "soare" not in lad or gt is None:
        bad("the real-list oracle produced no rows")
        return
    if abs(lad["soare"][0] - gt) > 1e-9:
        bad("real lists, soare: ladder T=%d gives %.6f, --min-grays %d gives "
            "%.6f" % (t, lad["soare"][0], g, gt))
        return
    print("   ok   real lists, soare: both paths give %.6f" % lad["soare"][0])


# --------------------------------------------------------------------------- 4
def check_monotone(real=False):
    """DEEPER CAN NEVER BE WORSE: an extra level can always take threshold 0 and
    never fire, so --ladder N+1 contains --ladder N at the same beam.  Coverage
    is ASSERTED -- if depth never changed the answer the check proved nothing."""
    print("4. monotone in the depth")
    tmp = tempfile.mkdtemp(prefix="checklad-mono-")
    if real:
        base = ["--topk", "4", "--opener", "soare"]
    else:
        make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
        base = ["--data", tmp, "--topk", "6", "--threads", "1",
                "--opener", MINI_SPLITTERS[0]]
    prev, seen = None, []
    for n in (2, 3, 4, 5):
        out = os.path.join(tmp, "m%d.csv" % n)
        run(base + ["--ladder", str(n), "--out", out])
        v = best_total(out)
        if v is None:
            bad("--ladder %d produced no rows" % n)
            return
        seen.append(v)
        if prev is not None and v > prev + 1e-9:
            bad("--ladder %d gives %.6f, WORSE than --ladder %d at %.6f -- the "
                "extra level can always take threshold 0" % (n, v, n - 1, prev))
            return
        prev = v
    if len({"%.9f" % v for v in seen}) < 2:
        bad("every depth gave the same total, so depth was not exercised: %s"
            % seen)
    else:
        print("   ok   monotone: %s" % " >= ".join("%.6f" % v for v in seen))


# --------------------------------------------------------------------------- 5
def check_blind():
    """EVERY THRESHOLD AT 6 FIRES ALWAYS, so the ladder is a blind N-word
    opening -- a structurally different strategy that the reference reaches by
    the same route, and the case where no bucket ever leaves early."""
    print("5. all thresholds at 6 is a blind opening")
    tmp = tempfile.mkdtemp(prefix="checklad-blind-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    out = os.path.join(tmp, "b.csv")
    run(["--data", tmp, "--ladder", "3", "--topk", "4", "--threads", "1",
         "--no-prune", "--limit", "8", "--pin-thresholds", "6,6", "--out", out])
    got = read_ladders(out)
    if not got:
        bad("no rows under --pin-thresholds 6,6")
        return
    for ow, (total, rungs) in sorted(got.items()):
        if any(t != 6 for _, t in rungs):
            bad("%s: a pinned threshold of 6 came back as %s" % (ow, rungs))
            return
        if any(w is None for w, _ in rungs):
            bad("%s: a pinned threshold of 6 fires on every bucket, so no level "
                "may decline -- got %s" % (ow, rungs))
            return
        want = LAD.ladder_total(ow, [(w, t) for w, t in rungs], MINI_ANSWERS)
        if abs(float(want) - total) > 1e-6:
            bad("%s blind: C %.6f, reference %.6f" % (ow, total, float(want)))
            return
    print("   ok   %d blind ladders agree with the reference" % len(got))


# --------------------------------------------------------------------------- 6
def check_matched():
    """THE KEY, three ways.  `--dump-matched` is the C's own two-guess count;
    ladder.py recomputes it from the replies; tree_states does it again by a
    route that never looks at a tile, deriving greens as positions where some
    guess matched the answer.  The cases that matter are the ones a
    distinct-letter word never produces: a repeated letter, and a position
    turned green then guessed over with another letter."""
    print("6. the matched-letter key, three implementations")
    import tree_states
    tmp = tempfile.mkdtemp(prefix="checklad-mat-")
    dump = os.path.join(tmp, "m.csv")
    run(["--dump-matched", dump])
    if not os.path.exists(dump):
        bad("--dump-matched wrote nothing")
        return
    rep = dup = green = 0
    with open(dump) as f:
        next(f)
        for line in f:
            g1, g2, ans, m = line.rstrip("\n").split(",")
            m = int(m)
            p1, p2 = LAD.tiles(g1, ans), LAD.tiles(g2, ans)
            mine = LAD.matched_letters([g1, g2], [p1, p2])
            if mine != m:
                bad("%s/%s vs %s: C says %d, ladder.py says %d"
                    % (g1, g2, ans, m, mine))
                return
            g, y = tree_states.state_from_strings(ans, [g1, g2])
            if g + y != m:
                bad("%s/%s vs %s: C says %d, tree_states says %d+%d"
                    % (g1, g2, ans, m, g, y))
                return
            rep += 1
            if len(set(g1)) < 5 or len(set(g2)) < 5:
                dup += 1
            if any(a == b and c != b for a, b, c in zip(g1, ans, g2)):
                green += 1
    if not dup or not green:
        bad("the sample never exercised a repeated letter (%d) or a re-guessed "
            "green position (%d)" % (dup, green))
    else:
        print("   ok   %d triples agree (%d with a repeated letter, %d with a "
              "green position guessed over)" % (rep, dup, green))


# --------------------------------------------------------------------------- 7
def check_resume():
    """A HALF-WRITTEN CSV MUST CONTINUE TO THE SAME ANSWER *AND* THE SAME
    LADDER.  The words live only in the file once an opener is done, so a resume
    that could not read its level rows back would report a total with no
    strategy attached -- the shape of the `0 openers attain it` scar."""
    print("7. resume")
    tmp = tempfile.mkdtemp(prefix="checklad-res-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    full = os.path.join(tmp, "full.csv")
    part = os.path.join(tmp, "part.csv")
    base = ["--data", tmp, "--ladder", "3", "--topk", "4", "--threads", "1",
            "--no-prune"]
    run(base + ["--out", full])
    run(base + ["--limit", "5", "--out", part])
    p = run(base + ["--out", part])
    if "resuming" not in p.stderr:
        bad("the second run did not resume from the partial file")
        return
    a, b = read_ladders(full), read_ladders(part)
    if set(a) != set(b):
        bad("resumed run covers %d openers, fresh run %d" % (len(b), len(a)))
        return
    for ow in sorted(a):
        if abs(a[ow][0] - b[ow][0]) > 1e-9 or a[ow][1] != b[ow][1]:
            bad("%s: fresh %s, resumed %s" % (ow, a[ow], b[ow]))
            return
    best = min(a, key=lambda w: a[w][0])
    if best not in p.stderr:
        bad("the resumed run never named its own leader (%s)" % best)
        return
    print("   ok   %d openers identical after a resume, words included" % len(a))


# --------------------------------------------------------------------------- 8
def check_refusals():
    """Each refusal exists because the alternative is a wrong number under a
    right-looking name."""
    print("8. the refusals")
    tmp = tempfile.mkdtemp(prefix="checklad-ref-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    out = os.path.join(tmp, "r.csv")
    d = ["--data", tmp]
    cases = [
        ("--ladder without --topk", d + ["--ladder", "3", "--out", out]),
        ("--ladder 1", d + ["--ladder", "1", "--topk", "3", "--out", out]),
        ("--ladder 99", d + ["--ladder", "99", "--topk", "3", "--out", out]),
        ("--ladder with --max-level",
         d + ["--ladder", "3", "--max-level", "3", "--topk", "3", "--out", out]),
        ("--ladder with --third-key",
         d + ["--ladder", "3", "--third-key", "group", "--third-max-matched",
              "2", "--topk", "3", "--out", out]),
        ("--ladder with --min-grays",
         d + ["--ladder", "3", "--min-grays", "3", "--topk", "3", "--out", out]),
        ("--ladder with --by-grays",
         d + ["--ladder", "3", "--by-grays", "3", "--topk", "3", "--out", out]),
        ("--ladder with --group",
         d + ["--ladder", "3", "--group", "e5", "--topk", "3", "--out", out]),
        ("--pin-thresholds without --ladder",
         d + ["--min-grays", "3", "--pin-thresholds", "3", "--out", out]),
        ("--pin-thresholds too short",
         d + ["--ladder", "4", "--topk", "3", "--pin-thresholds", "3",
              "--out", out]),
        ("--pin-thresholds too long",
         d + ["--ladder", "2", "--topk", "3", "--pin-thresholds", "3,3,3",
              "--out", out]),
        ("--pin-thresholds out of range",
         d + ["--ladder", "2", "--topk", "3", "--pin-thresholds", "9",
              "--out", out]),
        ("no --out", d + ["--ladder", "2", "--topk", "3"]),
    ]
    for name, args in cases:
        if os.path.exists(out):
            os.remove(out)
        p = run(args, expect_fail=True)
        if p.returncode == 0:
            bad("%s was ACCEPTED" % name)
            return
    print("   ok   all %d refused" % len(cases))


def main(argv):
    real = "--real" in argv
    if not os.path.exists(BINARY):
        print("no %s -- build it with 'sh build.sh' from math/solver/" % BINARY)
        return 1
    print("checkladder: the committed-word ladder\n")
    check_value()
    check_search()
    check_group_oracle(real)
    check_monotone(real)
    check_blind()
    check_matched()
    check_resume()
    check_refusals()
    print("\n%s" % ("FAILED (%d)" % fail if fail else "all checks passed"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
