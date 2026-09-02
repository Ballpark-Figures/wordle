"""Standing status report for the multiwordle simulations: a table by k and n.

    python3 tools/multiwordle_report.py            # from math/
    python3 tools/multiwordle_report.py --stderr   # show each mean's standard error
    python3 tools/multiwordle_report.py --trials 1000000   # only that sample size
    python3 tools/multiwordle_report.py --all      # every file, one row each

It READS the summary lines each run wrote into its own CSV and tabulates them.
Nothing is recomputed here -- the mean and its standard error are the numbers the
run itself reported, so this cannot disagree with the file it came from.  A run
still in flight has no summary yet and is listed as RUNNING.

THE GRID SHOWS BARE MEANS.  These are Monte Carlo estimates and every one of them
has a standard error -- `--stderr` puts them back, `--all` always carries them,
and each CSV records its own -- so before calling a difference real, check it
against them rather than against the digits shown here.

THE GRID IS BY (k, n), and n is the number of words in the OPENING, read off the
filename.  Rows are only comparable down a column: a different opening is a
different strategy, and openings of the same size can come from rankings of very
different quality (words and pairs are exhaustive, triples and quads are greedy
screens -- see solver/run-singles.sh).  Cells at different sample sizes are not
put in the same grid; --trials picks which sample size to show, defaulting to the
largest one present.
"""

import os
import re
import sys

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DIR = os.path.join(_MATH, "data", "shared", "multiwordle")
NAME = re.compile(r"k(\d+)_(.+)_t(\d+)_s(\d+)\.csv$")
MEAN = re.compile(r"# mean total guesses ([\d.]+)\s+\+/- ([\d.]+)")
SPREAD = re.compile(r"# sd [\d.]+\s+min (\d+)\s+median ([\d.]+)\s+max (\d+)")


def scan():
    """Every result file, as (k, opening, trials, seed) -> summary or None."""
    out = {}
    for fn in sorted(os.listdir(DIR)):
        m = NAME.match(fn)
        if not m:
            continue
        path = os.path.join(DIR, fn)
        with open(path, "rb") as f:                 # the summary is the tail
            f.seek(max(0, os.path.getsize(path) - 4000))
            tail = f.read().decode("utf-8", "replace")
        mean, spread = MEAN.search(tail), SPREAD.search(tail)
        out[(int(m.group(1)), m.group(2).replace("-", " "),
             int(m.group(3)), int(m.group(4)))] = (
                 (mean.groups() + spread.groups()) if mean and spread else None)
    return out


def grid(rows, trials, seed=0):
    """The (k, n) table at one sample size, plus the openings each n used."""
    openings, cells = {}, {}
    for (k, opening, t, s), summary in rows.items():
        if t != trials or s != seed:
            continue
        n = len(opening.split())
        openings.setdefault(n, set()).add(opening)
        cells[(k, n)] = summary
    return openings, cells


def main(argv):
    show_err = "--stderr" in argv
    if not os.path.isdir(DIR):
        raise SystemExit("no %s -- nothing has been run yet" % DIR)
    rows = scan()
    if not rows:
        raise SystemExit("no result files in %s" % DIR)

    if "--all" in argv:
        print("%-4s %-24s %-3s %-9s %-9s %-9s %s"
              % ("k", "opening", "n", "trials", "mean", "stderr", "min/med/max"))
        for (k, opening, t, s), v in sorted(
                rows.items(), key=lambda x: (len(x[0][1].split()), x[0][0], x[0][2])):
            n = len(opening.split())
            if v is None:
                print("%-4d %-24s %-3d %-9d RUNNING" % (k, opening, n, t))
            else:
                print("%-4d %-24s %-3d %-9d %-9s %-9s %s/%s/%s"
                      % (k, opening, n, t, v[0], v[1], v[2], v[3], v[4]))
        return 0

    sizes = sorted({t for (_, _, t, _) in rows})
    trials = int(argv[argv.index("--trials") + 1]) if "--trials" in argv else sizes[-1]
    openings, cells = grid(rows, trials)
    if not cells:
        raise SystemExit("no runs at t=%d (have: %s)"
                         % (trials, ", ".join(str(x) for x in sizes)))

    ns = sorted(openings)
    print("multiwordle: mean total guesses, t=%d, seed 0%s"
          % (trials, "" if show_err else "  (--stderr for the standard errors)"))
    print("openings by n (the head of that size's singletons ranking):")
    for n in ns:
        for opening in sorted(openings[n]):
            print("  n=%d  %s" % (n, opening))
    print()
    w = 19 if show_err else 12
    print("k    " + "".join(("n=%-" + str(w - 2) + "d") % n for n in ns))
    for k in sorted({k for (k, _) in cells}):
        line = "%-5d" % k
        for n in ns:
            v = cells.get((k, n), "absent")
            line += ("%-" + str(w) + "s") % (
                "--" if v == "absent" else "RUNNING" if v is None
                else "%s +/- %s" % (v[0], v[1]) if show_err else v[0])
        print(line.rstrip())
    print()
    print("min / median / max")
    print("k    " + "".join("n=%-15d" % n for n in ns))
    for k in sorted({k for (k, _) in cells}):
        line = "%-5d" % k
        for n in ns:
            v = cells.get((k, n), "absent")
            line += "%-17s" % ("--" if v == "absent" else "RUNNING" if v is None
                               else "%s/%s/%s" % (v[2], v[3], v[4]))
        print(line.rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
