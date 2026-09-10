"""GATE for the predetermined-second-word table (solver/secondword.c).

    python3 tools/checksecondword.py            # from math/
    python3 tools/checksecondword.py --wide     # more real openers, slower

math/secondword.py states the objective; this checks that the C computes it.

THE ORACLE SHARES NOTHING WITH WHAT IT CHECKS.  The reference recomputes every
reply FROM THE STRINGS by the MULTISET rule -- greens first, then each remaining
letter matched against the answer's unused copies -- and groups answers by the
TILE TUPLE itself, so it never touches the base-3 encoding, the pattern matrix's
column order, the run-reordering or the L1 counters the C runs on.  It counts
greys by looking at tiles, not by decoding a number.

WHAT IS CHECKED

  1. THE MINI PROBLEM, EXHAUSTIVELY.  A complete miniature `--data` directory, so
     the binary reads a small problem by its NORMAL path and the code under test
     is the code that runs for real.  Every row -- the chosen word, the integer
     score, the qualifying count, the bucket count and the TIE COUNT -- is
     compared at every threshold from 1 to 5.
  2. THE RESTRICTED POOLS.  The same, with both pools cut to the answer list
     (the `mystery` variant), plus the assertion that the restriction actually
     CHANGED a row: a pool check that never bit has checked nothing.
  3. THE REAL LISTS.  Real openers over the real 2315, against the numpy
     reference in secondword.py -- a second implementation of the aggregation at
     full scale -- and, over a cut-down second-word pool so it is affordable,
     against the same from-the-strings reference used on the mini problem.
  4. THE EMPTY CASE, CONSTRUCTED.  An opener that no answer can give the
     threshold's worth of greys has nothing to choose between, and its row must
     be EMPTY rather than arbitrary.  Random word lists produce it rarely, so it
     is built deliberately: every answer carries an `e` and so does the opener,
     which caps the greys at four.
  5. THE REFUSALS, and the TABLE READER.  No --out, no --min-grays, an
     impossible threshold, a pool word that is not a legal guess; and on the
     reader, a stampless file, a threshold that disagrees with the stamp, a pool
     that disagrees with it, and a --limit run being refused as the real table.

COVERAGE IS ASSERTED.  The run FAILS unless a tie, an empty row, a threshold
that changed the winner and a pool restriction that changed the winner all
actually occurred -- twenty passing comparisons that never exercised those would
say nothing about them.
"""

import os
import subprocess
import sys
import tempfile
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from secondword import Table, best_second, gray_counts, read_table  # noqa: E402
from wordle import load_words, pattern  # noqa: E402

MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BINARY = os.path.join(MATH, "solver", "secondword")

MINI_GUESSES = [
    "crane", "slate", "trace", "adieu", "audio", "roast", "stern", "pilot",
    "brick", "flame", "gouty", "vixen", "wharf", "zesty", "mimic", "puppy",
    "abbey", "eerie", "llama", "salad", "tepee", "onion", "kayak", "level",
]
MINI_ANSWERS = [
    "crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame",
    "mimic", "puppy", "abbey", "llama", "salad", "onion", "kayak", "level",
]

# Every answer contains an `e`, so an opener that also contains one can never be
# answered with five greys -- check 4's constructed empty case.
EMPTY_ANSWERS = ["crane", "slate", "eerie", "level", "tepee", "abbey"]
EMPTY_GUESSES = EMPTY_ANSWERS + ["pilot", "mimic", "gouty"]

fail = 0
notes = Counter()


def bad(msg):
    global fail
    fail += 1
    print("  FAIL: %s" % msg)


# --------------------------------------------------------------- the reference

def tiles_from_strings(guess, answer):
    """Wordle's reply as a tuple of 0 (grey) / 1 (yellow) / 2 (green).

    The MULTISET rule, written out: greens are taken first and their letters
    consumed, then each remaining guess letter is yellow while the answer still
    has an unused copy of it.  A different algorithm from wordle.pattern's
    consuming left-to-right scan, so a repeated-letter mistake cannot be shared
    between the two.
    """
    tiles = [0] * len(guess)
    left = Counter()
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            tiles[i] = 2
        else:
            left[a] += 1
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g]:
            tiles[i] = 1
            left[g] -= 1
    return tuple(tiles)


def ref_best_second(guesses, answers, opener, min_grays, seconds):
    """(second, score, nq, nbuckets, ties) by grouping WORDS, not codes.

    `opener` and `seconds` are words; the returned second is a word or None.  The
    tie-break is the lowest index in `guesses`, which is what the C means by the
    lowest guess index.
    """
    q = [a for a in answers
         if sum(1 for t in tiles_from_strings(opener, a) if t == 0) >= min_grays]
    first = {a: tiles_from_strings(opener, a) for a in q}
    nbuckets = len(set(first.values()))
    if not q:
        return None, 0, 0, 0, 0
    order = {w: i for i, w in enumerate(guesses)}
    best, best_score, ties = None, None, 0
    for g2 in seconds:
        if g2 == opener:
            continue
        groups = Counter((first[a], tiles_from_strings(g2, a)) for a in q)
        score = sum(n * n for n in groups.values())
        if best_score is None or score < best_score:
            best, best_score, ties = g2, score, 1
        elif score == best_score:
            ties += 1
            if order[g2] < order[best]:
                best = g2
    return best, best_score, len(q), nbuckets, ties


# ------------------------------------------------------------------ the driver

def make_data(tmp, guesses, answers):
    """A complete miniature `--data` directory."""
    words = os.path.join(tmp, "shared", "words")
    pats = os.path.join(tmp, "local", "patterns")
    os.makedirs(words, exist_ok=True)
    os.makedirs(pats, exist_ok=True)
    with open(os.path.join(words, "guess.txt"), "w") as f:
        f.write("\n".join(guesses) + "\n")
    with open(os.path.join(words, "mystery.txt"), "w") as f:
        f.write("\n".join(answers) + "\n")
    mat = np.array([[pattern(g, a) for a in answers] for g in guesses],
                   dtype=np.uint8)
    np.save(os.path.join(pats, "patterns.npy"), mat)
    return words


def run(args, expect_fail=False):
    """Run the binary, returning (returncode, stderr)."""
    p = subprocess.run([BINARY] + args, cwd=MATH, capture_output=True, text=True)
    if not expect_fail and p.returncode:
        bad("secondword failed: %s\n%s" % (" ".join(args), p.stderr[-800:]))
    return p.returncode, p.stderr


def read_rows(path):
    """The table's data rows as {opener: (second, score, nq, nbuckets, ties)}."""
    out = {}
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            p = line.rstrip("\n").split(",")
            out[p[0]] = (p[1] or None,
                         int(p[3]) if p[3] else 0,
                         int(p[4]), int(p[5]), int(p[6]))
    return out


def compare(rows, guesses, answers, seconds, min_grays, label):
    """Diff every row against the from-the-strings reference."""
    for opener, got in sorted(rows.items()):
        want = ref_best_second(guesses, answers, opener, min_grays, seconds)
        if got != want:
            bad("%s min_grays=%d opener %s: C gave %s, reference %s"
                % (label, min_grays, opener, got, want))
            return
        if got[0] is None:
            notes["empty"] += 1
        if got[4] > 1:
            notes["tie"] += 1


# ------------------------------------------------------------------- 1. + 2. + 4.

def check_mini():
    print("1-2. the mini problem, every threshold, against the strings")
    tmp = tempfile.mkdtemp(prefix="checksw-mini-")
    words = make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    winners = {}
    for mg in range(1, 6):
        out = os.path.join(tmp, "full_g%d.csv" % mg)
        run(["--data", tmp, "--min-grays", str(mg), "--out", out, "--threads", "2"])
        rows = read_rows(out)
        if len(rows) != len(MINI_GUESSES):
            bad("expected %d rows, got %d" % (len(MINI_GUESSES), len(rows)))
            return
        compare(rows, MINI_GUESSES, MINI_ANSWERS, MINI_GUESSES, mg, "mini")
        winners[mg] = {w: r[0] for w, r in rows.items()}
    if not fail:
        print("   ok   %d openers x 5 thresholds match the reference exactly"
              % len(MINI_GUESSES))

    # THE TIE-BREAK, WHERE IT CAN ACTUALLY SHOW.  Walked in index order, "the
    # first word attaining the minimum" and "the lowest guess index" are the same
    # word, so neither the default run nor a pool file in list order can tell a
    # real tie-break from an accident of arrival.  This pool is REVERSED, so they
    # differ wherever there is a tie -- and the reference orders by the guess
    # list, never by the pool.
    rev = os.path.join(tmp, "reversed.txt")
    with open(rev, "w") as f:
        f.write("\n".join(reversed(MINI_GUESSES)) + "\n")
    out = os.path.join(tmp, "reversed.csv")
    run(["--data", tmp, "--min-grays", "2", "--threads", "2", "--out", out,
         "--seconds", rev, "--seconds-name", "reversed"])
    rows = read_rows(out)
    before = notes["tie"]
    compare(rows, MINI_GUESSES, MINI_ANSWERS, list(reversed(MINI_GUESSES)), 2,
            "reversed pool")
    if notes["tie"] > before:
        notes["tie-break"] += 1
        print("   ok   ties break on the lowest guess index, not on arrival")
    else:
        bad("no tie arose against the reversed pool -- the tie-break was not "
            "exercised where pool order and index order differ")

    # THE THRESHOLD MUST MATTER.  It is the objective; if every threshold picked
    # the same words, none of these comparisons would say anything about it.
    if any(winners[a] != winners[b] for a in winners for b in winners):
        notes["threshold-moved"] += 1
        print("   ok   the threshold changes the winner")
    else:
        bad("no threshold changed any winner -- min_grays was never exercised")

    # 2. the restricted pools: the `mystery` variant, at mini scale
    mg = 3
    out = os.path.join(tmp, "restricted.csv")
    run(["--data", tmp, "--min-grays", str(mg), "--threads", "2", "--out", out,
         "--openers", os.path.join(words, "mystery.txt"),
         "--seconds", os.path.join(words, "mystery.txt"),
         "--openers-name", "mystery", "--seconds-name", "mystery"])
    rows = read_rows(out)
    if sorted(rows) != sorted(MINI_ANSWERS):
        bad("restricted run should have one row per answer word, got %d"
            % len(rows))
    compare(rows, MINI_GUESSES, MINI_ANSWERS, MINI_ANSWERS, mg, "restricted")
    changed = sum(1 for w in rows if rows[w][0] != winners[mg][w])
    if changed:
        notes["pool-moved"] += 1
        print("   ok   restricting the second words changed %d of %d rows"
              % (changed, len(rows)))
    else:
        bad("restricting the pool changed nothing -- the restriction never bit")
    # and the stamp must say so, or a later reader cannot tell the two apart
    t = read_table(out, min_grays=mg, openers="mystery", seconds="mystery")
    if t.answers != len(MINI_ANSWERS):
        bad("stamp records %d answers, not %d" % (t.answers, len(MINI_ANSWERS)))

    # 4. the constructed empty case
    print("4. an opener nothing can qualify against")
    tmp2 = tempfile.mkdtemp(prefix="checksw-empty-")
    make_data(tmp2, EMPTY_GUESSES, EMPTY_ANSWERS)
    out = os.path.join(tmp2, "empty.csv")
    run(["--data", tmp2, "--min-grays", "5", "--out", out, "--threads", "2"])
    rows = read_rows(out)
    compare(rows, EMPTY_GUESSES, EMPTY_ANSWERS, EMPTY_GUESSES, 5, "empty")
    blanks = [w for w, r in rows.items() if r[0] is None]
    with_e = [w for w in EMPTY_GUESSES if "e" in w]
    if sorted(blanks) < sorted(with_e) or not set(with_e) <= set(blanks):
        bad("every opener containing an 'e' must have an EMPTY row here "
            "(every answer has one, so five greys is impossible); blank: %s"
            % sorted(blanks))
    else:
        print("   ok   %d openers have no qualifying answer and an empty row"
              % len(blanks))
    tbl = read_table(out, min_grays=5)
    if tbl.rows[with_e[0]] is not None:
        bad("the reader should give None for an empty second word")


# ---------------------------------------------------------------------- 3. real

def check_real(wide):
    print("3. the real lists")
    guesses = load_words("guess")
    answers = load_words("mystery")
    from build_patterns import load_patterns
    pat = np.array(load_patterns())
    grays = gray_counts()

    # 3a. real openers over the full second-word pool, against the numpy
    # reference -- the aggregation written a second way, at full scale.
    n = 24 if wide else 8
    tmp = tempfile.mkdtemp(prefix="checksw-real-")
    out = os.path.join(tmp, "real.csv")
    run(["--min-grays", "3", "--limit", str(n), "--threads", "0", "--out", out])
    rows = read_rows(out)
    idx = {w: i for i, w in enumerate(guesses)}
    for opener, got in sorted(rows.items()):
        g2, score, nq, nb, ties = best_second(pat, idx[opener], 3, grays=grays)
        want = (guesses[g2] if g2 is not None else None, score, nq, nb, ties)
        if got != want:
            bad("real opener %s: C gave %s, numpy reference %s" % (opener, got, want))
            break
        if nq == len(answers):
            bad("opener %s qualified every answer -- the filter never bit" % opener)
        else:
            notes["filtered"] += 1
    print("   ok   %d real openers match the numpy reference over all %d "
          "second words" % (len(rows), len(guesses)))

    # 3b. the same at real scale against the FROM-THE-STRINGS reference, over a
    # cut-down second-word pool so the Python cost is affordable.  This is the
    # one check that pins the real pattern matrix and its column order.
    pool = guesses[:400]
    poolfile = os.path.join(tmp, "pool.txt")
    with open(poolfile, "w") as f:
        f.write("\n".join(pool) + "\n")
    openers = ["salet", "crane", "abbey"] + (["fuzzy", "immix"] if wide else [])
    openfile = os.path.join(tmp, "openers.txt")
    with open(openfile, "w") as f:
        f.write("\n".join(openers) + "\n")
    out2 = os.path.join(tmp, "real_pool.csv")
    run(["--min-grays", "3", "--threads", "0", "--out", out2,
         "--openers", openfile, "--seconds", poolfile,
         "--openers-name", "check", "--seconds-name", "check"])
    rows = read_rows(out2)
    for opener in openers:
        got = rows[opener]
        want = ref_best_second(guesses, answers, opener, 3, pool)
        if got != want:
            bad("real opener %s over a 400-word pool: C gave %s, strings %s"
                % (opener, got, want))
            break
    print("   ok   %d real openers match the from-the-strings reference over "
          "the 2315 answers" % len(openers))


# ------------------------------------------------------------------ 5. refusals

def check_refusals():
    print("5. refusals, and the table reader")
    tmp = tempfile.mkdtemp(prefix="checksw-ref-")
    make_data(tmp, MINI_GUESSES, MINI_ANSWERS)
    out = os.path.join(tmp, "x.csv")
    cases = [
        ("no --out", ["--data", tmp, "--min-grays", "3"]),
        ("no --min-grays", ["--data", tmp, "--out", out]),
        ("--min-grays 6", ["--data", tmp, "--min-grays", "6", "--out", out]),
        ("a pool word that is not a legal guess",
         ["--data", tmp, "--min-grays", "3", "--out", out,
          "--seconds", os.path.join(tmp, "shared", "words", "nope.txt")]),
    ]
    with open(os.path.join(tmp, "shared", "words", "nope.txt"), "w") as f:
        f.write("crane\nzzzzz\n")
    for label, args in cases:
        rc, _ = run(args, expect_fail=True)
        if rc == 0:
            bad("%s was accepted" % label)
    print("   ok   %d bad invocations refused" % len(cases))

    # the reader
    good = os.path.join(tmp, "good.csv")
    run(["--data", tmp, "--min-grays", "3", "--out", good, "--threads", "2"])
    reader_cases = []
    stampless = os.path.join(tmp, "stampless.csv")
    with open(good) as f, open(stampless, "w") as o:
        for line in f:
            if not line.startswith("# settings"):
                o.write(line)
    reader_cases.append(("a stampless table", lambda: read_table(stampless)))
    reader_cases.append(("the wrong threshold",
                         lambda: read_table(good, min_grays=4)))
    reader_cases.append(("the wrong pool",
                         lambda: read_table(good, seconds="mystery")))
    reader_cases.append(("a missing file",
                         lambda: read_table(os.path.join(tmp, "nofile.csv"))))
    limited = os.path.join(tmp, "limited.csv")
    run(["--data", tmp, "--min-grays", "3", "--limit", "4", "--out", limited,
         "--threads", "2"])
    reader_cases.append(("a --limit PREFIX read as the table",
                         lambda: read_table(limited, openers="guess")))
    for label, fn in reader_cases:
        try:
            fn()
        except SystemExit:
            continue
        bad("the reader accepted %s" % label)
    print("   ok   %d bad tables refused by the reader" % len(reader_cases))


def main(argv):
    wide = "--wide" in argv
    if not os.path.exists(BINARY):
        raise SystemExit("no %s -- build it with 'sh build.sh' from math/solver/"
                         % BINARY)
    check_mini()
    check_real(wide)
    check_refusals()

    print("\ncoverage")
    need = {
        "empty": "an opener with no qualifying answer",
        "tie": "a tied second word",
        "threshold-moved": "a threshold that changed the winner",
        "pool-moved": "a pool restriction that changed the winner",
        "filtered": "an opener whose threshold excluded some answers",
        "tie-break": "a tie broken against the pool's own order",
    }
    for key, what in need.items():
        if notes[key]:
            print("   ok   %-46s %d" % (what, notes[key]))
        else:
            bad("%s never occurred -- the checks above did not exercise it" % what)

    print()
    if fail:
        print("SECOND-WORD CHECK FAILED (%d)" % fail)
        return 1
    print("all second-word checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
