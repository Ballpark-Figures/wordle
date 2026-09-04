"""Enumerate every valid Nerdle GUESS of a given width, pass one: as written.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-enumerate.sh                    # from math/, or anywhere
    bash solver/run-nerdle-enumerate.sh --width 8
    bash solver/run-nerdle-enumerate.sh --method split

WHAT THIS COMPUTES: the set of 8-symbol strings that Nerdle accepts as a legal
GUESS -- every equation AS WRITTEN, with `1+9=0+10` and `9+1=0+10` counted
separately.  Collapsing commutative equivalents is a SEPARATE second pass and
nothing here does it.  math/nerdle.py states the rules exactly and is the source
of truth; read it before quoting any count.

THESE ARE GUESSES, NOT ANSWERS.  The answer rules are strictly tighter (a bare
number on the right, no leading zeros, no negatives, an operator required) and
two of them are still open, so no answer filter exists yet -- see the "WHAT THIS
FILE DOES NOT DECIDE" section of math/nerdle.py.  Do not describe this output as
the answer list.

TWO METHODS, ONE ANSWER.  `--method dfs` is the specified walk: one depth-first
descent over the whole string, cutting a branch as soon as it cannot become a
guess.  `--method split` enumerates each side once with its exact value and
joins the two sides of each `=` position on that value.  They produce the same
set in different orders, which tools/checknerdle.py verifies exhaustively at
every width small enough to brute-force.  The split method is far cheaper at
width 8 -- about 7.6 million side evaluations against roughly 188 million
bottomed-out branches -- because rule 4 (the right side is a full expression)
stops the walk from ending at the `=`.

The count is exact and integral, so there is no sampling error and no seed: one
width means one file, and re-running reproduces it exactly.
"""

import gzip
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nerdle import WIDTH, walk_guesses, walk_guesses_split  # noqa: E402

RULES = "2026-09-03"      # the rule set in math/nerdle.py this output obeys


def parse_args(argv):
    width = WIDTH
    method = "dfs"
    out = None
    progress = 1000000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a == "--method":
            method = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if width < 3:
        raise SystemExit("--width must be at least 3 (a side, an `=`, a side)")
    if method not in ("dfs", "split"):
        raise SystemExit("--method must be dfs or split, not %r" % method)
    if out is None:
        # The strturns lesson: a run that prints its answer and saves nothing is
        # a run lost.  Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-enumerate.sh")
    return width, method, out, progress


def open_out(path):
    return gzip.open(path, "wt") if path.endswith(".gz") else open(path, "w")


def main(argv):
    width, method, out, progress = parse_args(argv)

    print("nerdle guess enumeration: width=%d method=%s rules=%s"
          % (width, method, RULES))
    print("GUESSES, not answers -- see math/nerdle.py for the rules and for the")
    print("two answer rules still open.  Equations are counted AS WRITTEN;")
    print("commutative equivalents are a separate second pass.")
    sys.stdout.flush()

    fh = open_out(out) if out else None
    by_eq = [0] * width
    state = {"n": 0, "t0": time.time()}

    def emit(eq):
        state["n"] += 1
        by_eq[eq.index("=")] += 1
        if fh is not None:
            fh.write(eq)
            fh.write("\n")
        if progress and state["n"] % progress == 0:
            print("  %12d found  %8.1fs" % (state["n"], time.time() - state["t0"]))
            sys.stdout.flush()
            if fh is not None:
                fh.flush()

    try:
        (walk_guesses if method == "dfs" else walk_guesses_split)(emit, width)
    finally:
        if fh is not None:
            fh.close()

    secs = time.time() - state["t0"]
    print("\n%d valid guesses at width %d in %.1fs" % (state["n"], width, secs))
    print("by position of the `=`:")
    for p, c in enumerate(by_eq):
        if c:
            print("  %d | %12d" % (p, c))

    if out:
        with open(out + ".meta", "w") as m:
            m.write("kind=guesses\n")
            m.write("width=%d\n" % width)
            m.write("method=%s\n" % method)
            m.write("rules=%s\n" % RULES)
            m.write("as_written=1\n")
            m.write("commutative_collapsed=0\n")
            m.write("answers_filtered=0\n")
            m.write("count=%d\n" % state["n"])
            m.write("seconds=%.1f\n" % secs)
            for p, c in enumerate(by_eq):
                if c:
                    m.write("eq_at_%d=%d\n" % (p, c))
        print("\nwrote %s (+ .meta)" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
