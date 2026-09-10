"""GATE for tools/topk_eval.py -- the driver, not the search.

    python3 tools/checktopkeval.py          # from math/

`tools/checktopk.py` already diffs topk.py's numba kernel against its numpy
reference, so the SEARCH has an oracle.  What that leaves unchecked is everything
this driver adds: reading a weight stem, the uniform-vs-stem choice, dropping
zero-weight words, and the CSV it writes.  Each of those is a place a wrong
number could arrive under a right-looking name.

IT RUNS ON A MINIATURE PROBLEM, built here and passed via TopKGame's `patterns=`,
so it needs neither the committed 12972x12972 matrix nor numba -- it works on a
fresh clone.

COVERAGE IS ASSERTED: it FAILS if the uniform and weighted answers never actually
differed, or if a zero weight never actually dropped a word.  A check that
compared two identical numbers would prove nothing.
"""
import os
import subprocess
import sys
import tempfile
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from topk import TopKGame                       # noqa: E402
from topk_eval import read_weight_stem          # noqa: E402
from wordle import pattern                      # noqa: E402

MATH = os.path.join(HERE, "..")
TOOL = os.path.join(HERE, "topk_eval.py")

GUESSES = [
    "crane", "slate", "trace", "adieu", "audio", "roast", "stern", "pilot",
    "brick", "flame", "gouty", "vixen", "wharf", "zesty", "mimic", "puppy",
]
ANSWERS = ["crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame"]
WEIGHTS = [Fraction(8), Fraction(4), Fraction(2), Fraction(1),
           Fraction(1, 2), Fraction(1, 4), Fraction(0), Fraction(1, 8)]

FAILURES = []
SKIPPED = []

# topk.py slices the square 12972x12972 matrix unless a caller passes its own
# `patterns=`, and the CLI deliberately does not expose that -- it is for the
# other-language lists.  So the one subprocess check needs the matrix, which is
# gitignored under data/local/ and absent on a fresh clone.  It is SKIPPED rather
# than failed there, and reported as skipped rather than quietly passing.
FULL_MATRIX = os.path.join(MATH, "data", "local", "patterns", "patterns_full.npy")


def skip(m):
    SKIPPED.append(m)
    print("SKIPPED: %s" % m)


def bad(m):
    FAILURES.append(m)
    print("FAIL: %s" % m)


def ok(m):
    print("ok: %s" % m)


def mini_patterns(answers):
    return np.array([[pattern(g, a) for a in answers] for g in GUESSES],
                    dtype=np.uint8)


def game(answers, k=1):
    return TopKGame(answers=answers, guesses=GUESSES, k=k,
                    use_numba=False, patterns=mini_patterns(answers))


def write_stem(stem, words, weights):
    with open(stem + ".txt", "w") as fw, open(stem + ".weights", "w") as fx:
        fx.write("# weights from a test\n# scale 8\n")
        for w, x in zip(words, weights):
            fw.write(w + "\n")
            fx.write("%s %s\n" % (w, Fraction(x)))


def run_tool(tmp, extra):
    return subprocess.run([sys.executable, TOOL] + extra, cwd=MATH,
                          capture_output=True, text=True)


def main():
    tmp = tempfile.mkdtemp(prefix="checktopkeval-")

    # ---- 1. the stem reader: order is VERIFIED, not assumed -----------------
    stem = os.path.join(tmp, "adv")
    write_stem(stem, ANSWERS, WEIGHTS)
    words, wts = read_weight_stem(stem)
    if words != ANSWERS or [Fraction(x) for x in map(Fraction, map(str, wts))] and \
            [float(x) for x in WEIGHTS] != wts:
        bad("read_weight_stem did not round-trip the words and weights")
    else:
        ok("read_weight_stem round-trips a stem written beside it")

    bent = os.path.join(tmp, "bent")
    write_stem(bent, ANSWERS, WEIGHTS)
    lines = open(bent + ".weights").read().splitlines()
    lines[2], lines[3] = lines[3], lines[2]          # swap two words, keep counts
    open(bent + ".weights", "w").write("\n".join(lines) + "\n")
    try:
        read_weight_stem(bent)
        bad("a stem whose two files disagree on ORDER was accepted -- the weights "
            "would then be attached to the wrong words")
    except SystemExit:
        ok("a stem whose .txt and .weights disagree on order is refused")

    # ---- 2. uniform really is all-ones, and differs from the weighting ------
    g = game(ANSWERS)
    uni = g.expected_guesses(None)
    ones = g.expected_guesses([1.0] * len(ANSWERS))
    if abs(uni - ones) > 1e-12:
        bad("weights=None is not the all-ones vector (%.12f vs %.12f)" % (uni, ones))
    else:
        ok("--weights uniform is exactly the all-ones vector")

    wt = g.expected_guesses([float(x) for x in WEIGHTS])
    if abs(wt - uni) < 1e-12:
        bad("COVERAGE: the weighted and uniform answers are identical, so every "
            "comparison here compared a number with itself")
    else:
        ok("weighted and uniform genuinely differ (%.6f vs %.6f)" % (wt, uni))

    # ---- 3. a zero weight REMOVES a word, it does not merely cost nothing ---
    if not any(x == 0 for x in WEIGHTS):
        bad("COVERAGE: the test weights contain no zero, so the drop is untested")
    else:
        kept = [w for w, x in zip(ANSWERS, WEIGHTS) if x > 0]
        kw = [float(x) for x in WEIGHTS if x > 0]
        dropped = game(kept).expected_guesses(kw)
        if abs(dropped - wt) > 1e-9:
            bad("a zero-weight word changed the answer (%.12f with it, %.12f "
                "without) -- it must be dropped from the candidate set entirely, "
                "since it also steers the word-counting ranking rule"
                % (wt, dropped))
        else:
            ok("a zero-weight word is dropped, not merely charged nothing")

    # ---- 4. the CSV the tool writes, read back ------------------------------
    out = os.path.join(tmp, "r.csv")
    if not os.path.exists(FULL_MATRIX):
        skip("the end-to-end CSV check needs data/local/patterns/patterns_full.npy "
             "-- build it with '../.venv/bin/python build_patterns.py --full'")
        p = None
    else:
        p = run_tool(tmp, ["--k", "1", "--weights", stem, "--no-numba", "--out", out])
    if p is None:
        pass
    elif p.returncode != 0:
        bad("the tool failed on the mini stem:\n%s" % p.stderr[-600:])
    else:
        rows = [l for l in open(out) if not l.startswith("#")]
        hdr, row = rows[0].strip().split(","), rows[1].strip().split(",")
        rec = dict(zip(hdr, row))
        # It uses the REAL matrix for these words, so the value is its own; what
        # is checked here is that the file says what the run said, and that the
        # bookkeeping columns are self-consistent.
        if int(rec["listed"]) != len(ANSWERS):
            bad("CSV `listed` is %s, expected %d" % (rec["listed"], len(ANSWERS)))
        elif int(rec["live"]) != sum(1 for x in WEIGHTS if x > 0):
            bad("CSV `live` is %s, expected %d"
                % (rec["live"], sum(1 for x in WEIGHTS if x > 0)))
        elif abs(float(rec["weighted_total"]) / float(rec["total_weight"])
                 - float(rec["expected_guesses"])) > 1e-9:
            bad("CSV expected_guesses is not weighted_total / total_weight")
        elif "%.6f" % float(rec["expected_guesses"]) not in p.stdout:
            bad("the CSV disagrees with what the run printed")
        else:
            ok("the CSV round-trips, and its columns are self-consistent")

    # ---- 5. the refusals ---------------------------------------------------
    out = os.path.join(tmp, "r.csv")
    cases = [
        (["--k", "1", "--weights", "uniform"], "--out",
         "no --out is refused"),
        (["--k", "1", "--out", out], "--weights",
         "no --weights is refused -- the weighting IS the objective"),
        (["--k", "1", "--weights", "uniform", "--out", out, "--no-out"],
         "mutually exclusive", "--out with --no-out is refused"),
        (["--k", "0", "--weights", "uniform", "--answers",
          "data/shared/words/custom.txt", "--out", out], "--k",
         "k below 1 is refused"),
        (["--k", "1", "--weights", "uniform", "--out", out], "--answers",
         "uniform without --answers is refused"),
        (["--k", "1", "--weights", os.path.join(tmp, "nope"), "--out", out],
         "missing", "a nonexistent weight stem is refused"),
    ]
    for argv, needle, label in cases:
        r = run_tool(tmp, argv)
        if r.returncode == 0 or needle not in (r.stderr + r.stdout):
            bad("%s -- got rc=%d, %r" % (label, r.returncode,
                                         (r.stderr + r.stdout)[-200:]))
        else:
            ok(label)

    print()
    if FAILURES:
        print("FAILED (%d)" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    if SKIPPED:
        print("PASSED, with %d check(s) SKIPPED -- not the same as passing:"
              % len(SKIPPED))
        for m in SKIPPED:
            print("  - %s" % m)
        return 0
    print("ALL topk_eval CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
