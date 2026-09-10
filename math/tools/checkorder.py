"""GATE: the opener DISPATCH ORDER changes WHEN a result lands, never WHAT it is.

    python3 tools/checkorder.py          # from math/

`--order` picks how `--sweep` and `--sweep --optimal-only` walk the opener list:

    lb      ascending root lower bound   (optimal-only only; lets a cutoff prove
                                          the whole tail is worse)
    ssq     ascending split score        (DEFAULT -- best splitters first)
    bisect  the ssq sort, DISPATCHED     (ends, median, quartiles, odd eighths:
            by bisection                  a stopped run is a stratified sample
                                          of the difficulty range, not a prefix
                                          of the easy end)

WHY THIS EXISTS.  The bisection was written for the hard-mode sweep, where the
partial distribution is read while the run is in flight, and was then hardcoded
into BOTH sweep call sites -- so every other sweep silently paid its cost (the
second opener dispatched is the worst-partitioned word in the list, so the
incumbent that drives every lower-bound cutoff arrives late) while three wrapper
headers went on describing ascending order.  Nothing asserted any of it, which
is why it survived.  So the checks below are as much about the DEFAULT as about
the orders themselves.

THE ORACLE IS FREE, which is the point: the orders are permutations of one
another, so the multiset of result rows must be IDENTICAL under all three, and
`--optimal-only` must name the same winner.  Anything else is a real bug, not a
tolerance.

WITH `--threads 1` THE CSV APPEND ORDER *IS* THE DISPATCH ORDER, which is what
makes the sequence observable at all -- so the C's bisection can be diffed
against inflight.py's Python mirror of it, the mirror that names which opener
each thread is on and would otherwise drift silently.

COVERAGE IS ASSERTED, not hoped for: the run FAILS if the three orders never
actually differed from each other, since a check that compared three identical
sequences would prove nothing at all.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkweighted import MINI_GUESSES, make_mini_data          # noqa: E402
from inflight import bisect as py_bisect                        # noqa: E402
from wordle import pattern                                      # noqa: E402

MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BINARY = os.path.join(MATH, "solver", "optturns")
NPAT = 243
DEPTH = "6"

# The mini answer list.  Unlike checkweighted's it needs no weight ordering --
# this binary is the unweighted one -- so it is simply the guesses that are
# answers, in guess-list order, which is what the real mystery.txt is too.
MINI_ANSWERS = [
    "crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame",
    "mimic", "puppy", "abbey", "llama", "salad", "onion", "kayak", "level",
]

FAILURES = []


def bad(msg):
    FAILURES.append(msg)
    print("FAIL: %s" % msg)


def ok(msg):
    print("ok: %s" % msg)


def run(data, out, extra):
    """One sweep, single-threaded so the CSV order IS the dispatch order."""
    cmd = [BINARY, "--data", data, "--threads", "1", "--tt-bits", "20",
           "--depth", DEPTH, "--out", out] + extra
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        bad("solver failed for %s:\n%s" % (" ".join(extra), p.stderr[-800:]))
        return None, ""
    rows = []
    with open(out) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("word,"):
                continue
            rows.append(line.split(","))
    return rows, p.stderr


def logged_order(stderr):
    """The `order:` line the run printed -- what inflight.py/passes.py read."""
    for line in stderr.splitlines():
        if line.startswith("order:"):
            return line.split(":", 1)[1].strip()
    return None


def expected_sorted_order():
    """The ssq sort, re-derived here rather than read out of the C: ascending
    sum of squared bin sizes over the answers, ties by index in the guess list."""
    mat = np.array([[pattern(g, a) for a in MINI_ANSWERS] for g in MINI_GUESSES],
                   dtype=np.uint8)
    ss = np.empty(len(MINI_GUESSES), dtype=np.int64)
    for g in range(len(MINI_GUESSES)):
        c = np.bincount(mat[g], minlength=NPAT).astype(np.int64)
        ss[g] = int((c * c).sum())
    return [MINI_GUESSES[g] for g in np.lexsort((np.arange(len(MINI_GUESSES)), ss))]


def results(rows):
    """word -> the RESULT fields (total, expected, depth); seconds excluded, as
    it is wall time and varies run to run."""
    return {r[0]: tuple(r[1:4]) for r in rows}


def main():
    tmp = tempfile.mkdtemp(prefix="checkorder-")
    make_mini_data(tmp, MINI_ANSWERS)

    srt = expected_sorted_order()
    bis = py_bisect(srt)

    # ---- 1. the plain sweep under each order -------------------------------
    seqs, res = {}, {}
    for name, extra in (("default", []),
                        ("ssq", ["--order", "ssq"]),
                        ("bisect", ["--order", "bisect"])):
        out = os.path.join(tmp, "sweep_%s.csv" % name)
        rows, err = run(tmp, out, ["--sweep"] + extra)
        if rows is None:
            break
        seqs[name] = [r[0] for r in rows]
        res[name] = results(rows)
        want = {"default": "ssq", "ssq": "ssq", "bisect": "bisect"}[name]
        got = logged_order(err)
        if got != want:
            bad("the run logged `order: %s` for %s, expected %s -- inflight.py "
                "and passes.py read that line to reproduce the dispatch" % (got, name, want))
    if len(seqs) < 3:
        return finish()
    ok("plain sweep ran under all three orders")

    # ---- 2. THE REGRESSION: the default is NOT the bisection ----------------
    if seqs["default"] == bis and bis != srt:
        bad("THE DEFAULT IS STILL THE BISECTION -- the whole point of the flag "
            "is that it is opt-in")
    elif seqs["default"] != srt:
        bad("the default dispatch is neither the ssq sort nor anything expected:\n"
            "  got  %s\n  want %s" % (seqs["default"][:8], srt[:8]))
    else:
        ok("the DEFAULT dispatch is the ascending split score, best splitters first")

    if seqs["ssq"] != srt:
        bad("--order ssq did not walk the ascending split-score sort:\n"
            "  got  %s\n  want %s" % (seqs["ssq"][:8], srt[:8]))
    else:
        ok("--order ssq walks the ascending split-score sort")

    # ---- 3. the C bisection against inflight.py's Python mirror ------------
    if seqs["bisect"] != bis:
        bad("--order bisect disagrees with inflight.py's bisect() mirror -- the "
            "mirror is what names which opener each thread is on, so a divergence "
            "reports the WRONG WORDS rather than failing:\n"
            "  C      %s\n  python %s" % (seqs["bisect"][:8], bis[:8]))
    else:
        ok("--order bisect matches inflight.py's bisect() index sequence exactly")

    # ---- 4. COVERAGE: the orders must actually differ ----------------------
    if seqs["bisect"] == seqs["ssq"]:
        bad("bisect and ssq produced the SAME sequence, so every comparison "
            "above compared a sequence with itself and proved nothing")
    else:
        first_diff = next(i for i, (a, b) in enumerate(zip(seqs["bisect"], seqs["ssq"]))
                          if a != b)
        ok("the two orders genuinely differ (first at position %d: %s vs %s)"
           % (first_diff, seqs["bisect"][first_diff], seqs["ssq"][first_diff]))

    # ---- 5. ORDER CHANGES WHEN, NOT WHAT ----------------------------------
    if set(seqs["bisect"]) != set(seqs["ssq"]):
        bad("the orders examined DIFFERENT opener sets -- an order is a "
            "permutation, so this is a dropped or duplicated opener")
    elif res["bisect"] != res["ssq"] or res["default"] != res["ssq"]:
        diff = [w for w in res["ssq"] if res["ssq"][w] != res["bisect"].get(w)]
        bad("the same openers got DIFFERENT results under different orders "
            "(%d words, e.g. %s) -- the order must not touch a total"
            % (len(diff), diff[:5]))
    else:
        ok("all %d openers, identical totals under every order" % len(res["ssq"]))

    # ---- 6. --optimal-only names the same winner --------------------------
    winners = {}
    for name, extra in (("ssq", ["--order", "ssq"]), ("bisect", ["--order", "bisect"])):
        out = os.path.join(tmp, "opt_%s.csv" % name)
        rows, _ = run(tmp, out, ["--sweep", "--optimal-only"] + extra)
        if rows is None:
            return finish()
        # --optimal-only writes a row per IMPROVEMENT, so the winner is the last.
        winners[name] = (rows[-1][0], rows[-1][1])
    if winners["ssq"] != winners["bisect"]:
        bad("--optimal-only named different winners: ssq %s, bisect %s"
            % (winners["ssq"], winners["bisect"]))
    else:
        ok("--optimal-only names the same winner under both orders (%s total=%s)"
           % winners["ssq"])

    # ---- 7. RESUME reports the same answer as a fresh run -------------------
    # A resumed --optimal-only run seeds its incumbent from the CSV and then cuts
    # every remaining opener against it -- so nothing is searched, and the tie
    # list used to come out EMPTY: "0 openers attain it", printed for the very
    # value the same line reports as best.  The number was right and the list was
    # a lie.  The invariant is simply that resuming changes nothing it reports.
    fresh_out = os.path.join(tmp, "resume.csv")
    rows, err = run(tmp, fresh_out, ["--sweep", "--optimal-only", "--order", "ssq"])
    if rows is None:
        return finish()

    def attain(text):
        """(count, words) off the `N opener(s) attain it: a b c` line."""
        for line in text.splitlines():
            if "attain it" in line:
                head, _, tail = line.partition(":")
                return int(head.split()[0]), sorted(tail.split())
        return None, None

    p1 = subprocess.run([BINARY, "--data", tmp, "--threads", "1", "--tt-bits", "20",
                         "--depth", DEPTH, "--out", fresh_out, "--sweep",
                         "--optimal-only", "--order", "ssq"],
                        capture_output=True, text=True)
    n1, w1 = attain(p1.stdout)
    # p1 above already IS the resumed run (the file exists from the call before
    # it), so re-read the fresh numbers from a clean copy of the same work.
    fresh2 = os.path.join(tmp, "resume_fresh.csv")
    p0 = subprocess.run([BINARY, "--data", tmp, "--threads", "1", "--tt-bits", "20",
                         "--depth", DEPTH, "--out", fresh2, "--sweep",
                         "--optimal-only", "--order", "ssq"],
                        capture_output=True, text=True)
    n0, w0 = attain(p0.stdout)

    if n0 is None or n1 is None:
        bad("could not find the `attain it` line in the run output")
    elif n0 == 0:
        bad("COVERAGE: even the FRESH run reported 0 openers attaining, so the "
            "resume comparison proves nothing")
    elif "resume:" not in p1.stderr:
        bad("COVERAGE: the second run did not actually resume, so this checked "
            "two fresh runs against each other")
    elif (n1, w1) != (n0, w0):
        bad("a RESUMED run reports a different tie list from a fresh one:\n"
            "  fresh   %d: %s\n  resumed %d: %s" % (n0, w0, n1, w1))
    else:
        ok("a resumed run reports the same %d-opener tie list as a fresh one (%s)"
           % (n0, " ".join(w0)))

    # ---- 8. the refusals ---------------------------------------------------
    p = subprocess.run([BINARY, "--data", tmp, "--sweep", "--optimal-only",
                        "--order", "bisect", "--topk", "5", "--depth", DEPTH,
                        "--out", os.path.join(tmp, "never.csv")],
                       capture_output=True, text=True)
    if p.returncode == 0:
        bad("--order bisect with --topk was ACCEPTED; at K=2 that examines the "
            "single worst-partitioned opener while claiming the top K")
    else:
        ok("--order bisect with --topk is refused")

    p = subprocess.run([BINARY, "--data", tmp, "--order", "bogus"],
                       capture_output=True, text=True)
    if "must be lb, ssq or bisect" not in (p.stderr + p.stdout):
        bad("an unknown --order value was not rejected with a usage message")
    else:
        ok("an unknown --order value is rejected")

    return finish()


def finish():
    print()
    if FAILURES:
        print("FAILED (%d)" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("ALL ORDER CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
