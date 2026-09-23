"""Standing status report for the multiwordle simulations: a table by k and n.

    python3 tools/multiwordle_report.py            # from math/
    python3 tools/multiwordle_report.py --stderr   # show each mean's standard error
    python3 tools/multiwordle_report.py --trials 1000000   # only that sample size
    python3 tools/multiwordle_report.py --all      # every file, one row each
    python3 tools/multiwordle_report.py --strategy minavg  # that strategy's grid
    python3 tools/multiwordle_report.py --rank SWEEP.csv    # every word, ranked

It READS the summary lines each run wrote into its own CSV and tabulates them.
Nothing is recomputed here -- the mean and its standard error are the numbers the
run itself reported, so this cannot disagree with the file it came from.  A run
still in flight has no summary yet and is listed as RUNNING.

THE GRID SHOWS BARE MEANS.  These are Monte Carlo estimates and every one of them
has a standard error -- `--stderr` puts them back, `--all` always carries them,
and each CSV records its own -- so before calling a difference real, check it
against them rather than against the digits shown here.

--rank prints EVERY word of an opener sweep in order, with how far each sits
behind the leader in guesses and in standard errors.  The `ses` column is the gap
divided by the LEADER's standard error, which is a rough yardstick and not a test:
the leader's own mean is biased optimistic (the winner's curse), and because every
word faced the same games the error on a DIFFERENCE is smaller than either word's
standard error.  Read it as "how crowded is the top", not as significance.

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
import signal
import sys

# A full --rank listing is thousands of lines and will usually be piped into
# head/less; without this, closing that pipe raises BrokenPipeError mid-print.
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DIR = os.path.join(_MATH, "data", "shared", "multiwordle")
# The stem is `k<K>_<opening>_t<T>_s<SEED>` plus `_<strategy>` for anything but
# greedy, which keeps the bare name so every file written before --strategy
# existed still reads.  THE STRATEGY GROUP IS WHY THIS PATTERN CHANGED: it used
# to require the stem to END at the seed, so a minavg or srank run matched
# NOTHING and was silently skipped -- the grid looked unchanged after the run.
# Being skipped was at least safe; the hazard to avoid is the opposite, mixing
# two strategies into one column, which is why `strategy` is a KEY below and not
# a label.
NAME = re.compile(r"k(\d+)_(.+?)_t(\d+)_s(\d+)(?:_([a-z]+))?\.csv$")
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
             int(m.group(3)), int(m.group(4)), m.group(5) or "greedy")] = (
                 (mean.groups() + spread.groups()) if mean and spread else None)
    return out


def grid(rows, trials, seed=0, strategy="greedy"):
    """The (k, n) table at one sample size and ONE strategy.

    THE STRATEGY IS A FILTER, NOT A LABEL.  greedy, srank and minavg are three
    different strategies over the same game, so a column holding two of them
    would be a column of nothing -- the same reason cells at different sample
    sizes are never put in one grid.
    """
    openings, cells = {}, {}
    for (k, opening, t, s, strat), summary in rows.items():
        if t != trials or s != seed or strat != strategy:
            continue
        n = len(opening.split())
        openings.setdefault(n, set()).add(opening)
        cells[(k, n)] = summary
    return openings, cells


def rank(path):
    """Every word of a sweep CSV, best mean first."""
    rows = []
    head = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                head.append(line.rstrip("\n"))
                continue
            if line.startswith("word,"):
                continue
            c = line.rstrip("\n").split(",")
            if len(c) >= 8:
                rows.append((c[0], float(c[2]), float(c[3]),
                             int(c[5]), float(c[6]), int(c[7])))
    if not rows:
        raise SystemExit("no data rows in %s" % path)
    rows.sort(key=lambda r: r[1])
    best_mean, best_se = rows[0][1], rows[0][2]
    for line in head:
        print(line)
    print("%d words, ranked by mean total guesses" % len(rows))
    print("%-6s %-8s %-9s %-9s %-9s %-6s %s"
          % ("rank", "word", "mean", "stderr", "vs best", "ses", "min/med/max"))
    for i, (w, mean, se, lo, med, hi) in enumerate(rows):
        print("%-6d %-8s %-9.4f %-9.4f %-9.4f %-6.1f %d/%g/%d"
              % (i + 1, w, mean, se, mean - best_mean,
                 (mean - best_mean) / best_se if best_se else 0.0, lo, med, hi))
    return 0


def main(argv):
    if "--rank" in argv:
        return rank(argv[argv.index("--rank") + 1])
    show_err = "--stderr" in argv
    if not os.path.isdir(DIR):
        raise SystemExit("no %s -- nothing has been run yet" % DIR)
    rows = scan()
    if not rows:
        raise SystemExit("no result files in %s" % DIR)

    if "--all" in argv:
        print("%-8s %-4s %-24s %-3s %-9s %-9s %-9s %s"
              % ("strategy", "k", "opening", "n", "trials", "mean", "stderr",
                 "min/med/max"))
        for (k, opening, t, s, strat), v in sorted(
                rows.items(),
                key=lambda x: (x[0][4], len(x[0][1].split()), x[0][0], x[0][2])):
            n = len(opening.split())
            if v is None:
                print("%-8s %-4d %-24s %-3d %-9d RUNNING" % (strat, k, opening, n, t))
            else:
                print("%-8s %-4d %-24s %-3d %-9d %-9s %-9s %s/%s/%s"
                      % (strat, k, opening, n, t, v[0], v[1], v[2], v[3], v[4]))
        return 0

    strategy = (argv[argv.index("--strategy") + 1] if "--strategy" in argv
                else "greedy")
    have_strats = sorted({st for (_, _, _, _, st) in rows})
    if strategy not in have_strats:
        raise SystemExit("no %s runs (have: %s)"
                         % (strategy, ", ".join(have_strats)))
    sizes = sorted({t for (_, _, t, _, st) in rows if st == strategy})
    trials = int(argv[argv.index("--trials") + 1]) if "--trials" in argv else sizes[-1]
    openings, cells = grid(rows, trials, strategy=strategy)
    if not cells:
        raise SystemExit("no %s runs at t=%d (have: %s)"
                         % (strategy, trials, ", ".join(str(x) for x in sizes)))

    ns = sorted(openings)
    print("multiwordle: mean total guesses, %s, t=%d, seed 0%s"
          % (strategy, trials,
             "" if show_err else "  (--stderr for the standard errors)"))
    if len(have_strats) > 1:
        print("  (also on file: %s -- --strategy switches; never one grid, they"
              " are different strategies)"
              % ", ".join(st for st in have_strats if st != strategy))
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
