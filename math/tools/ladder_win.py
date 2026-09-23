#!/usr/bin/env python3
"""EXACT expected guesses AND win rate for a committed-word LADDER -- no simulation.

    python3 tools/ladder_win.py --from data/shared/ladder/ladderL5_k200.csv \\
        --opener trine --opener crane --out data/shared/ladder/win.csv

    python3 tools/ladder_win.py --ladder "trine clasp:3 dough:1" --no-out

`math/ladder.py` states the strategy and IS the source of truth; `math/openexact.py`
holds the two recursions and `evaluate_ladder`, the fast path this drives.  Read
the first before quoting a number.

WHAT THIS ADDS TO `run-ladder.sh`.  That run SEARCHES for a ladder and reports
`expected` -- expected guesses OUTRIGHT, play never truncated.  It computes no
win rate, because the ladder obeys no cap: guess 6 being random is where a
five-word ladder runs out of committed words, not a budget.  This prices a
ladder it is HANDED and reports both numbers:

  * `mean`     expected guesses OUTRIGHT.  The same quantity `run-ladder.sh`
               reports, and the cross-check below asserts they agree.
  * `win_rate` the fraction of those SAME untruncated games finishing in `--cap`
               guesses or fewer.  A REPORTING THRESHOLD on one play, not a rule
               the strategy follows -- exactly the split `openexact.py` states
               for blind openings and `--win-within` carries in the simulation.

Neither belongs in a table with an optturns-family total, every one of which is
an optimum SUBJECT TO a 6-guess guarantee.

IT PRICES, IT DOES NOT SEARCH.  `run-ladder.sh -k K` finds ladders; this
evaluates the ones given to it, so a ladder's own caveat travels with it -- a
`-k` run's winner is the best of the K openers EXAMINED and its total an UPPER
BOUND, and pricing it exactly here does not make it the optimum.

THE FREE CROSS-CHECK, and it is why `--from` is the preferred input.  Reading
the ladder out of the run's own CSV means nothing is retyped, AND the run's
`expected` becomes an oracle: `secondexact.c` summed that total in C over a
tree it searched, this one walks it in numpy from the committed pattern matrix,
and the two share no code.  A mismatch EXITS rather than reporting.

THE TAIL IS THE ANSWER LIST, always.  That is the strategy's definition, not a
pool anyone chose (`ladder.py`: "IT IS TIED TO THE `answer` FOLLOW-UP"), so
there is no `--pool` knob here -- unlike `open_exact.py`, where the opening is
blind and the pool is a real choice.

COST is all in the bucket sizes, so it is governed by how much of the answer set
DECLINES early: a ladder whose level-2 threshold fires widely hands the tail
only small sets, while the answers that decline on the opener go straight to a
bucket of a hundred or more.  Price one ladder before handing it a long list.
"""

import argparse
import csv
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns                                  # noqa: E402
from csvout import fresh_file                                             # noqa: E402
from openexact import evaluate_ladder                                     # noqa: E402
from paircover import pool_matrix                                         # noqa: E402
from wordle import load_words                                             # noqa: E402

HEADER = ("opener,ladder,words,cap,mean,win_rate,total,lost,answers,leaves,"
          "won_outright,source_expected,delta,seconds")


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="src",
                   help="a run-ladder.sh CSV to read the ladders out of")
    p.add_argument("--opener", action="append", default=[],
                   help="which opener's ladder to take from --from; repeatable")
    p.add_argument("--top", type=int,
                   help="instead of --opener, the best N openers in --from")
    p.add_argument("--ladder", action="append", default=[],
                   help="a ladder spelled out: 'opener w2:T2 w3:T3'; repeatable")
    p.add_argument("--cap", type=int, default=6,
                   help="the win-rate reporting threshold (default 6)")
    p.add_argument("--out", help="CSV to append to; resumable")
    p.add_argument("--no-out", action="store_true",
                   help="print only, write nothing -- say so deliberately")
    a = p.parse_args(argv)
    if not a.out and not a.no_out:
        raise SystemExit("--out is required (or --no-out, said deliberately): a "
                         "run whose answer is only on the terminal is a run that "
                         "has to be done again")
    if a.out and a.no_out:
        raise SystemExit("--out and --no-out are the same choice; pass one")
    if not a.src and not a.ladder:
        raise SystemExit("give --from a ladder CSV (with --opener or --top), or "
                         "--ladder 'opener w2:T2 w3:T3'")
    if a.src and not a.opener and a.top is None:
        raise SystemExit("--from needs --opener WORD (repeatable) or --top N: "
                         "which ladders are priced is the run's content, so it "
                         "is named rather than defaulted")
    if (a.opener or a.top is not None) and not a.src:
        raise SystemExit("--opener/--top select out of --from; pass --from too")
    if a.cap < 1:
        raise SystemExit("--cap must be at least 1")
    return a


def read_ladders(path):
    """{opener: (words, thresholds, expected, total)} from a run-ladder.sh CSV.

    The ladder is read from the run's OWN rows rather than retyped: a summary
    row (`fires == 'ladder'`) carries the value, and one `L<d>|t<T>` row per
    level carries that level's word and threshold, `-` where the search chose to
    decline.  A declined level ENDS the ladder, so the words stop there.
    """
    lvl, summ = {}, {}
    with open(path) as f:
        for r in csv.DictReader(l for l in f if not l.startswith("#")):
            if r["fires"] == "ladder":
                if not r["expected"]:
                    continue                          # a row the bound CUT
                summ[r["opener"]] = (float(r["expected"]), float(r["total"]))
            elif r["fires"].startswith("L") and "|t" in r["fires"]:
                d = int(r["fires"][1:r["fires"].index("|")])
                t = int(r["fires"][r["fires"].index("|t") + 2:])
                w = None if r["second"] == "-" else r["second"]
                lvl.setdefault(r["opener"], {})[d] = (w, t)
    out = {}
    for ow, (expected, total) in summ.items():
        words, thr = [ow], []
        for d in sorted(lvl.get(ow, {})):
            w, t = lvl[ow][d]
            if w is None:
                break                                 # declined: the ladder ends
            words.append(w)
            thr.append(t)
        out[ow] = (words, thr, expected, total)
    return out


def parse_spec(spec):
    """'trine clasp:3 dough:1' -> (['trine','clasp','dough'], [3, 1])."""
    parts = spec.split()
    if not parts:
        raise SystemExit("empty --ladder")
    words, thr = [parts[0]], []
    for p in parts[1:]:
        if ":" not in p:
            raise SystemExit("--ladder rung %r must be word:threshold, e.g. "
                             "'clasp:3' -- the threshold IS the strategy" % p)
        w, _, t = p.partition(":")
        words.append(w)
        thr.append(int(t))
    return words, thr


def load_field(a):
    """[(opener, words, thresholds, expected|None, source|None)] to price."""
    field = []
    if a.src:
        got = read_ladders(a.src)
        if a.top is not None:
            picked = sorted(got, key=lambda w: (got[w][2], w))[:a.top]
        else:
            picked = list(a.opener)
        missing = [w for w in picked if w not in got]
        if missing:
            raise SystemExit("%s has no ladder for: %s"
                             % (a.src, " ".join(missing)))
        for ow in picked:
            words, thr, expected, _ = got[ow]
            field.append((ow, words, thr, expected, a.src))
    for spec in a.ladder:
        words, thr = parse_spec(spec)
        field.append((words[0], words, thr, None, None))
    return field


def spell(words, thr):
    """The ladder as one string, the way the strategy reads."""
    return " ".join([words[0]] + ["%s<%d" % (w, t) for w, t in zip(words[1:], thr)])


def done_already(path):
    if fresh_file(path):
        return set()
    seen = set()
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("opener,"):
                continue
            c = line.split(",")
            if len(c) > 1:
                seen.add(c[1])                        # the ladder's own spelling
    return seen


def main(argv):
    a = parse_args(argv)
    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}

    field = load_field(a)
    bad = sorted({w for _, ws, _, _, _ in field for w in ws if w not in gpos})
    if bad:
        raise SystemExit("%d committed word(s) are not legal guesses: %s"
                         % (len(bad), ", ".join(bad[:5])))
    too_long = [ws for _, ws, _, _, _ in field if len(ws) > a.cap]
    if too_long:
        raise SystemExit("a %d-word ladder cannot finish inside --cap %d"
                         % (len(too_long[0]), a.cap))

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in answers])
    M = pool_matrix(full, cols)
    ans = np.arange(len(answers))

    seen = done_already(a.out) if a.out else set()
    todo = [f for f in field if spell(f[1], f[2]) not in seen]

    print("ladder win rates: %d ladder(s), %d answers, cap %d"
          % (len(field), len(answers), a.cap))
    print("  EXACT -- no sampling, no seed.  mean is expected guesses OUTRIGHT")
    print("  (play is never truncated); win_rate is the fraction of those same")
    print("  games at %d guesses or fewer." % a.cap)
    print("  the tail is a uniformly random consistent ANSWER, which is the")
    print("  strategy's definition, not a pool that was chosen.")
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
            out.write("# exact expected guesses and win rate for committed-word "
                      "LADDERS (math/ladder.py, math/openexact.py)\n")
            out.write("# settings cap=%d answers=%d tail=answer%s\n"
                      % (a.cap, len(answers),
                         "" if not a.src else " source=%s" % a.src))
            out.write("# EXACT: no sampling and no seed, so there is no standard "
                      "error and a re-run reproduces this file\n")
            out.write("# mean is expected guesses OUTRIGHT; win_rate is the "
                      "fraction of those same games at <= cap.  NEVER table "
                      "either beside an optturns-family total.\n")
            out.write("# source_expected/delta: the ladder run's own value for "
                      "the same ladder, and this walk minus it -- an independent "
                      "check, since that total came out of secondexact.c\n")
            out.write(HEADER + "\n")
            out.flush()              # before any work: a kill must not lose it

    for ow, words, thr, expected, src in todo:
        t0 = time.time()
        crows = np.ascontiguousarray(full[np.ix_([gpos[w] for w in words], cols)])
        r = evaluate_ladder(M, crows, words, thr, ans, cap=a.cap)
        secs = time.time() - t0
        name = spell(words, thr)

        # THE ORACLE: secondexact.c's own total for this ladder, in C, over a
        # tree it searched.  This walked it in numpy off the committed matrix.
        # A disagreement means one of them is wrong; do not report either.
        delta = ""
        if expected is not None:
            delta = r["mean"] - expected
            if abs(delta) > 1e-6:
                raise SystemExit(
                    "%s: this walk gives mean %.9f, %s records %.6f for the same "
                    "ladder (%s).  They share no code, so one is wrong -- "
                    "refusing to report either." % (ow, r["mean"], src, expected, name))
            delta = "%.2e" % delta

        print("  %-40s mean %.6f  win %.6f  (%d lost of %d, %d leaves, %.2fs)"
              % (name, r["mean"], r["win_rate"], round(r["lost"]), r["answers"],
                 r["leaves"], secs))
        if out:
            out.write("%s,%s,%d,%d,%.9f,%.9f,%.4f,%.9f,%d,%d,%d,%s,%s,%.3f\n"
                      % (ow, name, len(words), a.cap, r["mean"], r["win_rate"],
                         r["total"], r["lost"], r["answers"], r["leaves"],
                         r["won_outright"],
                         "" if expected is None else "%.6f" % expected,
                         delta, secs))
            out.flush()
    if out:
        out.close()
    if any(f[3] is not None for f in todo):
        print("cross-check: every mean reproduced the ladder run's own "
              "`expected` to 1e-6, by a separate implementation.")
    print("THE LADDERS ARE WHAT WAS HANDED IN -- this prices them, it does not "
          "search for them.")


if __name__ == "__main__":
    main(sys.argv[1:])
