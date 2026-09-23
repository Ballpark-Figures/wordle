"""DEEP FAMILIES: the answer families hard mode has to walk one word at a time.

Run it through the wrapper, which sets --out, names the run and tees a log:

    bash solver/run-deep-families.sh                    # from math/, or anywhere
    bash solver/run-deep-families.sh --min-depth 7

WHAT THIS COMPUTES.  In hard mode a guess must keep every green in place, so an
opener that pins a skeleton without locating the varying letter leaves the legal
set EQUAL to a family of answers differing in one position -- and the solver has
no option but to name the members one at a time.  That is the entire reason hard
mode needs depths past 6.  This reads the committed hardturns trees, finds every
line costing more than --min-depth-1 guesses, and reports the FAMILY that caused
each one.

WHY HARD MODE ONLY.  Normal mode caps every answer at 6 by construction (the
committed sweep has zero INFEASIBLE rows), so no line there can exceed the cap
and there is nothing to find.  `WORDLE_SOLVER` is deliberately NOT honoured:
pointed at optturns this would return an empty table, which reads as "no deep
families" rather than as "wrong question".

THE FAMILY IS DERIVED FROM THE LINE, not from the answer list.  A tree line is
"<answer> <nguesses> <g1> <p1> ...", so the guesses are the walk the solver
actually made.  The family is the TIGHTEST trailing run: among trailing runs of
two or more guesses, the one fixing the MOST positions, ties going to the longer
run.

  TIGHTEST, NOT LONGEST, AND THAT IS THE ONE REAL SUBTLETY.  Taking the longest
  run drags the OPENER in, and the opener is by definition the word that did not
  match: `ought eight fight ... wight` over all ten guesses fixes only `..ght`,
  because `ought` has `o` where the other nine have `i`.  That both mislabels the
  family (`..ght` instead of `.ight`) and SPLITS it, since `..ght` matches ten
  answers where `.ight` matches nine -- so `wight` at depth 10 and `right` at
  depth 8 land in different groups though they are the same trap.  Preferring the
  tightest template fixes both at once.

GROUPING IS BY THE MATCHED ANSWER SET, NOT BY THE TEMPLATE STRING.  `.ight` and
`.i.ht` are different strings matching the identical nine answers, so they are
one family; the reported name is re-derived from that set (the positions where
every member agrees), which cannot depend on which line happened to produce it.

ONE ROW PER FAMILY, THE DEEPEST MEMBER ONLY (the user's call, 2026-09-23).  A
family whose deepest member reaches 10 says nothing extra by also listing the
member that reached 9 -- it is the same walk stopping earlier.  `kin` counts the
shallower members folded away, so nothing is silently lost.

THE `size` COLUMN CAN OVERSTATE THE FAMILY.  It counts answers matching the
template; the `walk` column counts the guesses actually spent inside it.  When a
walk hops across a loose template -- `...er` matches 141 answers and the walk was
7 words of seven different shapes -- the row is not a family in the sense the
tight ones are.  `--min-fixed` is the knob for excluding those, and the
selection recorded in data/shared/FAMILIES.md uses it.

IT IS EXACT AND DETERMINISTIC -- a pure function of the committed trees, no
sampling and no seed, so a re-run reproduces the file byte for byte.
"""
import argparse
import collections
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import MATH


def tightest(guesses):
    """The family template of the tightest trailing run (see the header)."""
    best = None
    for k in range(2, len(guesses) + 1):
        run = guesses[-k:]
        t = "".join(run[0][i] if all(g[i] == run[0][i] for g in run) else "."
                    for i in range(5))
        fixed = 5 - t.count(".")
        if fixed >= 2 and (best is None or (fixed, k) > (best[0], best[1])):
            best = (fixed, k, t, run)
    return (best[2], best[3]) if best else (None, None)


def canonical(words):
    """Re-derive the name from the matched SET, so it cannot depend on the line."""
    ws = sorted(words)
    return "".join(ws[0][i] if all(w[i] == ws[0][i] for w in ws) else "."
                   for i in range(5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", default=None,
                    help="hardturns tree directory (default: the committed one)")
    ap.add_argument("--answers", default=None)
    ap.add_argument("--min-depth", type=int, default=7,
                    help="report lines costing this many guesses or more")
    ap.add_argument("--min-fixed", type=int, default=0,
                    help="drop families whose template fixes fewer than this")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-out", action="store_true")
    a = ap.parse_args()
    if not a.out and not a.no_out:
        sys.exit("--out is required (or --no-out to print only): a run whose "
                 "result goes nowhere is the one mistake this wrapper exists "
                 "to prevent")

    trees = a.trees or os.path.join(MATH, "data/shared/hardturns/trees")
    apath = a.answers or os.path.join(MATH, "data/shared/words/mystery.txt")
    answers = set(open(apath).read().split())

    # deepest line per answer, plus how many openers reach that depth
    best, openers = {}, collections.Counter()
    files = sorted(os.listdir(trees))
    for f in files:
        with gzip.open(os.path.join(trees, f), "rt") as fh:
            for line in fh:
                p = line.split()
                n = int(p[1])
                if n < a.min_depth:
                    continue
                ans, guesses = p[0], p[2::2]
                if ans not in best or n > best[ans][0]:
                    best[ans] = (n, f.split(".")[0], guesses)
                openers[(ans, n)] += 1
    print("scanned %d hard-mode trees; %d answers exceed %d guesses"
          % (len(files), len(best), a.min_depth - 1))

    fams = collections.defaultdict(list)
    for ans, (n, op, guesses) in best.items():
        t, run = tightest(guesses)
        if t is None:
            continue
        key = frozenset(w for w in answers
                        if all(c == "." or w[i] == c for i, c in enumerate(t)))
        fams[key].append((n, ans, op, run))

    rows = []
    for key, members in fams.items():
        members.sort(key=lambda x: -x[0])
        n, ans, op, run = members[0]
        name = canonical(key)
        fixed = 5 - name.count(".")
        if fixed < a.min_fixed:
            continue
        rows.append({"depth": n, "family": name, "fixed": fixed,
                     "size": len(key), "walk": len(run), "deepest": ans,
                     "openers": openers[(ans, n)], "kin": len(members) - 1,
                     "opener": op, "line": " ".join(run)})
    # the user's ordering, 2026-09-23: depth, then fixed letters, then size
    rows.sort(key=lambda r: (-r["depth"], -r["fixed"], -r["size"], r["family"]))
    print("families: %d" % len(rows))

    if a.out:
        cols = ["depth", "family", "fixed", "size", "walk", "deepest",
                "openers", "kin", "opener", "line"]
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w") as fh:
            fh.write("# deep families: the answer families hard mode walks one "
                     "word at a time (see tools/deep_families.py)\n")
            fh.write("# EXACT: a pure function of the committed hardturns trees "
                     "-- no sampling, no seed\n")
            fh.write("# settings min_depth=%d min_fixed=%d trees=%s\n"
                     % (a.min_depth, a.min_fixed, os.path.relpath(trees, MATH)))
            fh.write(",".join(cols) + "\n")
            for r in rows:
                fh.write(",".join(str(r[c]) for c in cols) + "\n")
        print("wrote %s" % a.out)
    for r in rows[:12]:
        print("  d%-2d %-7s size %3d  deepest %-6s (%d openers)  %s"
              % (r["depth"], r["family"], r["size"], r["deepest"],
                 r["openers"], r["line"]))


if __name__ == "__main__":
    main()
