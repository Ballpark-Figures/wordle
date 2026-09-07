"""Best opener per starting letter for a Lingo sweep.

Reads the per-letter CSVs a run wrote (`data/shared/lingo/len<L>_d<D>/<letter>_
totals.csv`, one `word,total,expected,seconds` row per opener) and prints, for
each letter, the opener with the fewest total guesses -- the best word to lead
with when the game hands you that first letter.

    python3 tools/lingo_report.py --length 5 --depth 5

Ties on total are real (the objective is an integer); all tied openers are shown.
A letter still mid-sweep shows the best opener FOUND SO FAR -- the CSV is flushed
per opener, so this is a live view, not necessarily final. INFEASIBLE openers
(blank total) are ignored for the best-opener pick and counted separately.
"""
import glob
import os
import sys

_MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rows(csv_path):
    out = []
    infeasible = 0
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("word"):
                continue
            p = line.split(",")
            if len(p) < 2:
                continue
            if p[1] == "":
                infeasible += 1
                continue
            out.append((p[0], int(p[1]), float(p[2]) if len(p) > 2 and p[2] else 0.0))
    return out, infeasible


def main():
    argv = sys.argv[1:]
    length = int(argv[argv.index("--length") + 1]) if "--length" in argv else 5
    depth = int(argv[argv.index("--depth") + 1]) if "--depth" in argv else 5
    suf = "_ans" if "--answers-only" in argv else ""
    d = os.path.join(_MATH, "data", "shared", "lingo",
                     "len%d_d%d%s" % (length, depth, suf))
    files = sorted(glob.glob(os.path.join(d, "*_totals.csv")))
    if not files:
        raise SystemExit("no results at %s -- run the sweep first" % d)

    print("Lingo best opener per letter  (length %d, depth %d%s)"
          % (length, depth, ", answers-only" if suf else ""))
    print("%-3s %-8s %6s %9s %8s %6s" %
          ("ltr", "opener", "total", "expected", "openers", "infeas"))
    for path in files:
        letter = os.path.basename(path).split("_")[0]
        rs, infeasible = rows(path)
        if not rs:
            print("%-3s %-8s %6s %9s %8d %6d" %
                  (letter, "-", "-", "-", 0, infeasible))
            continue
        best = min(r[1] for r in rs)
        winners = sorted(r[0] for r in rs if r[1] == best)
        w0 = winners[0]
        exp = [r[2] for r in rs if r[0] == w0][0]
        tie = ("  (+%d tied: %s)" % (len(winners) - 1, " ".join(winners[1:6]))
               if len(winners) > 1 else "")
        print("%-3s %-8s %6d %9.5f %8d %6d%s" %
              (letter, w0, best, exp, len(rs), infeasible, tie))


if __name__ == "__main__":
    main()
