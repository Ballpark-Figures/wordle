"""Collapse the Nerdle ANSWERS into commutative equivalence classes -- pass two.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-classes.sh                    # from math/, or anywhere
    bash solver/run-nerdle-classes.sh --width 6

WHAT THIS COMPUTES: Nerdle accepts a rearrangement of the day's answer as a win,
so the answers fall into classes any member of which wins the same day.  The
test is the game's own, quoted from its FAQ in math/nerdle.py, which is the
source of truth: same numbers, same operators, same answer.  Two consequences
that surprise people are written out there -- `-` and `/` effectively move, and
the rule is broader than algebraic commutativity.

WHY THE CLASS COUNT IS THE INTERESTING NUMBER: it is how many DISTINCT puzzles
the answer list really holds.  Pass one counted equations as written, which is
the right count for "what may I type"; this is the right count for "how many
different things can the hidden answer be".  They are different quantities and
neither substitutes for the other.

Each class is written as one line, members in order, the first being the
representative.  The representative is simply the alphabetically first member --
a presentation choice with no meaning, not a claim that it is the canonical
form.
"""

import gzip
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nerdle import WIDTH, commutative_key, is_answer  # noqa: E402

RULES = "2026-09-03"


def parse_args(argv):
    width, answers, out = WIDTH, None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a == "--answers":
            answers = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if answers is None:
        raise SystemExit("--answers (the pass-one answer list) is required")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-classes.sh")
    return width, answers, out


def open_maybe_gz(path, mode):
    return gzip.open(path, mode) if path.endswith(".gz") else open(path, mode)


def main(argv):
    width, answers, out = parse_args(argv)

    print("nerdle commutative classes: width=%d rules=%s" % (width, RULES))
    print("reading %s" % answers)
    print("the test is the game's own: same numbers, same operators, same")
    print("answer -- so `-` and `/` move too.  See math/nerdle.py.")
    sys.stdout.flush()

    t0 = time.time()
    classes = {}
    read = bad = 0
    with open_maybe_gz(answers, "rt") as src:
        for line in src:
            s = line.strip()
            if not s:
                continue
            read += 1
            if not is_answer(s, width):
                bad += 1
                if bad <= 5:
                    print("  NOT AN ANSWER: %r" % s)
                continue
            classes.setdefault(commutative_key(s), []).append(s)

    sizes = {}
    for members in classes.values():
        sizes[len(members)] = sizes.get(len(members), 0) + 1
    secs = time.time() - t0

    print("\n%d answers fall into %d classes in %.1fs" % (read, len(classes), secs))
    print("class sizes:")
    for n in sorted(sizes):
        print("  %3d member%s | %8d class%s | %8d answers"
              % (n, " " if n == 1 else "s", sizes[n], "  " if sizes[n] == 1 else "es",
                 n * sizes[n]))
    biggest = sorted(classes.values(), key=lambda m: (-len(m), m[0]))[:3]
    print("largest classes:")
    for members in biggest:
        shown = " ".join(sorted(members)[:6])
        print("  %2d | %s%s" % (len(members), shown,
                                " ..." if len(members) > 6 else ""))

    if bad:
        print("\n%d lines were not answers at width %d -- re-run the filter." % (bad, width))

    if out:
        with open_maybe_gz(out, "wt") as f:
            for key in sorted(classes, key=lambda k: sorted(classes[k])[0]):
                f.write(" ".join(sorted(classes[key])))
                f.write("\n")
        with open(out + ".meta", "w") as m:
            m.write("kind=classes\n")
            m.write("width=%d\n" % width)
            m.write("rules=%s\n" % RULES)
            m.write("equivalence=same-numbers-same-operators-same-answer\n")
            m.write("from=%s\n" % answers)
            m.write("answers=%d\n" % read)
            m.write("count=%d\n" % len(classes))
            m.write("seconds=%.1f\n" % secs)
            for n in sorted(sizes):
                m.write("size_%d=%d\n" % (n, sizes[n]))
        print("\nwrote %s (+ .meta)" % out)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
