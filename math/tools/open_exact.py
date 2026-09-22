"""EXACT expected guesses and win rate for blind openings -- no simulation.

    python3 tools/open_exact.py --pool answer --opening "crane spilt" \\
        --out data/shared/openexact/probe.csv

`math/openexact.py` states the strategy and the two recursions and IS the source
of truth; read it before quoting a number.  This is the driver: it resolves a
field of openings, evaluates each exactly, and appends a row per opening.

WHAT IT REPLACES, AND WHAT IT DOES NOT.  `run-wordle-race.sh --fallback answer`
ESTIMATES these two numbers by Monte Carlo over coupled games; this COMPUTES
them, so there is no seed, no standard error and no winner's curse, and a re-run
reproduces the file byte for byte.  What it does NOT replace is the race's
SEARCH: a race screens thousands of openings against each other and eliminates,
where this prices the openings it is handed.  Feed it a shortlist, or a race's
survivors, or a ranking's head.

VERIFIED AGAINST THE RACES, which is the check that matters most because the two
share no machinery -- one enumerates states, the other plays games.  MEASURED
2026-09-22, exact against the committed Monte Carlo cell and its standard error:

    crane spilt                      3.699156  vs 3.698408 +/- 0.000783  (0.96 sd)
    parse clint                      3.693496  vs 3.692743 +/- 0.000781  (0.96 sd)
    dance horst blimp                4.164319  vs 4.164442 +/- 0.000133  (0.92 sd)
    champ flint rugby sowed          5.021922  vs 5.021944 +/- 0.000089  (0.25 sd)
    clove rugby spank whift mozed    6.000864  vs 6.000883 +/- 0.000030  (0.63 sd)
    bugle champ downy first          5.023218  vs 5.023256 +/- 0.000146  (0.26 sd)
    slate                            3.821367  vs 3.821830 +/- 0.000999  (0.46 sd)

COST IS ALL IN THE BUCKET SIZES, so it is governed by k and nothing else.
MEASURED on this machine: a 1-word opening is ~4 s (147 buckets, largest 221), a
2-word one ~0.08 s, and 3, 4 and 5 words are milliseconds.  **The two quantities
cost the SAME** -- 4.1 s and 4.5 s for `slate` -- which was worth measuring,
because the shapes suggest otherwise: the win rate carries a BUDGET in its memo
key that expected guesses does not, but it also stops after `cap - k` levels
where expected guesses recurses to singletons.  At k = 1 those cancel; above it
both are free.

THE POOL IS PART OF THE QUESTION and is not defaulted here (the greens scar --
the WRAPPER carries a default a human reads and forwards it explicitly).

  **ONLY `answer` IS IMPLEMENTED, and the others are REFUSED rather than
  approximated.**  With pool == the answer list a bucket's live set and its
  answers are the same set, which is what lets both recursions carry a single
  index.  Under `guess` or `custom` the pool is a strict superset, so a bucket
  holds words that can never BE the answer and both recursions need to carry the
  answer subset alongside the live set -- a real change, not a flag.  Returning
  the `answer` number under a `guess` banner would be confidently wrong, so it
  exits instead.
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns                                  # noqa: E402
from csvout import fresh_file                                             # noqa: E402
from opening_list import read_openings, resolve_word_set                  # noqa: E402
from openexact import evaluate                                            # noqa: E402
from paircover import pool_matrix                                         # noqa: E402
from wordle import load_words                                             # noqa: E402

HEADER = ("word,words,mean,win_rate,total,lost,answers,buckets,budget,seconds")


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pool", required=True,
                   help="which words the follow-up draws from; only 'answer' "
                        "is implemented (see the module docstring)")
    p.add_argument("--opening", action="append", default=[],
                   help="one opening, words space separated; repeatable")
    p.add_argument("--openings-from", help="a ranking CSV with word* columns")
    p.add_argument("--openings-in",
                   help="keep only openings whose EVERY word is in this list")
    p.add_argument("--top", type=int, help="how many openings to take")
    p.add_argument("--cap", type=int, default=6,
                   help="the win-rate reporting threshold (default 6)")
    p.add_argument("--out", help="CSV to append to; resumable")
    p.add_argument("--no-out", action="store_true",
                   help="print only, write nothing -- say so deliberately")
    p.add_argument("--report", type=float, default=30.0,
                   help="seconds between progress lines")
    a = p.parse_args(argv)
    if a.pool != "answer":
        raise SystemExit(
            "--pool %r is not implemented: only 'answer' is.  Under 'guess' or "
            "'custom' the pool is a strict superset of the answers, so a "
            "bucket's live set and its answers differ and both recursions need "
            "a second index.  Refusing rather than reporting the 'answer' "
            "number under another name." % a.pool)
    if not a.out and not a.no_out:
        raise SystemExit("--out is required (or --no-out, said deliberately): "
                         "a run whose answer is only on the terminal is a run "
                         "that has to be done again")
    if a.out and a.no_out:
        raise SystemExit("--out and --no-out are the same choice; pass one")
    if not a.opening and not a.openings_from:
        raise SystemExit("give --opening 'a b' (repeatable) or --openings-from "
                         "a ranking CSV")
    if a.cap < 1:
        raise SystemExit("--cap must be at least 1")
    return a


def load_field(a):
    """The openings to price, as lists of words, in the order given."""
    field = [w.split() for w in a.opening]
    if a.openings_from:
        restrict = resolve_word_set(a.openings_in) if a.openings_in else None
        field += read_openings(a.openings_from, a.top, restrict, {})
    sizes = {len(f) for f in field}
    if len(sizes) > 1:
        raise SystemExit("the field mixes opening sizes %s -- ranking a 1-word "
                         "opening against a 2-word one compares two different "
                         "strategies" % sorted(sizes))
    return field


def done_already(path):
    """Openings already on file, so a re-run continues instead of repeating."""
    if fresh_file(path):
        return set()
    seen = set()
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("word,"):
                continue
            seen.add(line.split(",")[0])
    return seen


def main(argv):
    a = parse_args(argv)
    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(answers)}

    field = load_field(a)
    bad = sorted({w for f in field for w in f if w not in gpos})
    if bad:
        raise SystemExit("%d opening word(s) are not legal guesses: %s"
                         % (len(bad), ", ".join(bad[:5])))
    k = len(field[0])
    if k >= a.cap:
        raise SystemExit("a %d-word opening leaves no guesses under --cap %d"
                         % (k, a.cap))

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in answers])
    M = pool_matrix(full, cols)
    ans = np.arange(len(answers))

    seen = done_already(a.out) if a.out else set()
    todo = [f for f in field if " ".join(f) not in seen]

    print("open-exact: %d openings of %d word(s), pool %s (%d), cap %d "
          "(budget %d)" % (len(field), k, a.pool, len(answers), a.cap, a.cap - k))
    print("  EXACT -- no sampling, no seed; the mean is expected guesses "
          "OUTRIGHT and the")
    print("  win rate is the fraction of those untruncated scores at %d or "
          "fewer." % a.cap)
    if seen:
        print("  resuming: %d already on file, %d to do" % (len(seen), len(todo)))
    if a.out:
        print("  out  %s" % a.out)

    out = None
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        new = fresh_file(a.out)
        out = open(a.out, "a")
        if new:
            out.write("# exact expected guesses and win rate for blind "
                      "openings (math/openexact.py)\n")
            out.write("# settings pool=%s cap=%d words=%d answers=%d\n"
                      % (a.pool, a.cap, k, len(answers)))
            out.write("# EXACT: no sampling and no seed, so there is no "
                      "standard error and a re-run reproduces this file\n")
            out.write("# mean is expected guesses OUTRIGHT (play is never "
                      "truncated); win_rate is the fraction at <= cap\n")
            out.write(HEADER + "\n")
            out.flush()          # before any work: a kill must not lose it

    best, last = None, time.time()
    for i, words in enumerate(todo, start=1):
        t0 = time.time()
        rows = np.ascontiguousarray(full[np.ix_([gpos[w] for w in words], cols)])
        at = [ppos.get(w, -1) for w in words]
        r = evaluate(M, rows, at, ans, cap=a.cap)
        secs = time.time() - t0
        name = " ".join(words)
        if out:
            out.write("%s,%d,%.9f,%.9f,%.1f,%.9f,%d,%d,%d,%.3f\n"
                      % (name, k, r["mean"], r["win_rate"], r["total"],
                         r["lost"], r["answers"], r["buckets"], r["budget"],
                         secs))
            out.flush()
        if best is None or r["mean"] < best[1]:
            best = (name, r["mean"], r["win_rate"])
            print("  %-34s mean %.6f  win %.6f   NEW BEST" % (name, r["mean"],
                                                             r["win_rate"]))
        elif len(todo) <= 20:
            print("  %-34s mean %.6f  win %.6f" % (name, r["mean"],
                                                   r["win_rate"]))
        if time.time() - last >= a.report and len(todo) > 20:
            print("  %d/%d done, %.1fs each, best %s %.6f"
                  % (i, len(todo), secs, best[0], best[1]))
            last = time.time()
    if out:
        out.close()
    if best:
        print("best of the %d priced: %s  mean %.6f  win %.6f"
              % (len(todo), best[0], best[1], best[2]))
    print("THE FIELD IS WHAT WAS HANDED IN -- this prices openings, it does "
          "not search for them.")


if __name__ == "__main__":
    main(sys.argv[1:])
