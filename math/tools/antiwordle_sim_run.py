"""Sweep every legal opener, measuring antiwordle length under RANDOM play.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-antiwordle-sim.sh -t 200                  # from math/, or anywhere
    bash solver/run-antiwordle-sim.sh -t 5000 --openers-from data/shared/antiwordle/sim.t200.s0.csv --top 200
    bash solver/run-antiwordle-sim.sh -t 200 --limit 500 --seed 7

WHAT THIS MEASURES, precisely: for each opening word, the MEAN number of guesses a
player takes who opens with it and then plays UNIFORMLY AT RANDOM among the legal
words, over `-t` games with the answer drawn uniformly from the 2315.  The count
includes the guess that lands on the answer.  The model, and what the random player
does and does not know, are in math/antiwordle_sim.py -- read that first; this file
is the sweep around it.

IT IS A MONTE CARLO ESTIMATE, so every row carries a standard error and the summary
prints one.  TWO OPENERS CLOSER TOGETHER THAN A COUPLE OF SEs HAVE NOT BEEN SHOWN TO
DIFFER, and with 12972 of them the best-looking row is partly luck: at 12972 draws
the extreme of the sampling noise is several SEs wide, so the top of a small-`t`
sweep is a SHORTLIST, never a winner.  The intended use is two-stage -- screen
everything cheaply, then re-run the head with many more trials via --openers-from.

RANDOM PLAY IS A FLOOR, NOT A STRATEGY.  The player can end the game by stumbling
onto the answer, and never deliberately avoids candidate words the way a real player
does.  So these numbers are far below skilled play, and far below `antistall`'s
clairvoyant maxima.  A high-ranking opener here is a HYPOTHESIS about the real game.

Reproducible from (trials, seed, opener set), which is why trials and seed are in the
output filename: a re-run of the same pair reproduces the file exactly, and a
different seed is a different sample that gets its own file rather than being
appended to this one.  Rows are flushed as each opener finishes, so a Ctrl-C keeps
everything measured so far and a re-run skips it.
"""
import argparse
import csv
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import GuessSpace
from antiwordle_sim import simulate_opener
from build_patterns import load_patterns
from wordle import load_words

FIELDS = ["opener", "trials", "mean", "se", "min", "max", "lucky", "secs"]


def openers_from(path, top):
    """The `top` best-scoring openers of a previous sweep's CSV, best mean first.

    Reads this tool's own output, so a cheap wide screen can hand its head to an
    expensive narrow one. Sorted here rather than trusting the file's order.
    """
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("mean"):
                rows.append((float(r["mean"]), r["opener"]))
    if not rows:
        raise SystemExit("%s has no scored rows" % path)
    rows.sort(reverse=True)
    return [w for _, w in rows[:top]]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-t", "--trials", type=int,
                    help="random games per opener (required: it sets the precision)")
    ap.add_argument("--seed", type=int, default=0,
                    help="base seed; each opener's stream is derived from it")
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N openers of the set (a cheap partial run)")
    ap.add_argument("--openers-from", dest="openers_from",
                    help="a previous sweep CSV to take the best openers from")
    ap.add_argument("--top", type=int, default=200,
                    help="how many to take from --openers-from (default 200)")
    ap.add_argument("--progress", type=int, default=500,
                    help="print a progress line every N openers")
    ap.add_argument("--out", help="CSV to append one row per opener to")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, save nothing (must be explicit)")
    args = ap.parse_args()

    if not args.trials or args.trials < 1:
        # Trials set the precision, and the precision is what the result MEANS.
        # A default would make every output file ambiguous about how much noise
        # is in it.
        ap.error("-t (trials per opener) is required and must be >= 1.\n"
                 "It sets the standard error, so it is part of the experiment.")
    if not args.out and not args.no_out:
        ap.error("give --out FILE, or --no-out to save nothing.\n"
                 "Prefer the wrapper, solver/run-antiwordle-sim.sh, which sets it.")
    if args.out and args.no_out:
        ap.error("--out and --no-out are mutually exclusive")

    guesses = load_words("guess")
    answers = load_words("mystery")
    space = GuessSpace(guesses)
    pat = np.asarray(load_patterns())

    if args.openers_from:
        openers = openers_from(args.openers_from, args.top)
        source = "%s top %d" % (os.path.basename(args.openers_from), args.top)
    else:
        openers = list(guesses)
        source = "all %d legal words" % len(guesses)

    done = set()
    if args.out and os.path.exists(args.out):
        with open(args.out, newline="") as fh:
            done = {r["opener"] for r in csv.DictReader(fh)}
    # --limit narrows the opener SET, before resume subtracts what is done, so it
    # is idempotent: `--limit 40` twice measures the same 40 and the second run
    # does nothing. Applying it afterwards would make a re-run quietly measure the
    # NEXT 40 instead, and the file would then hold 80 rows for a "--limit 40" run.
    if args.limit:
        openers = openers[:args.limit]
    todo = [w for w in openers if w not in done]

    print("openers: %s; %d to run (%d already in the CSV)"
          % (source, len(todo), len(done)))
    print("trials per opener: %d   seed: %d" % (args.trials, args.seed))
    if not todo:
        print("nothing to do")
        return 0

    fh = writer = None
    if args.out:
        fresh = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        fh = open(args.out, "a", newline="")
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if fresh:
            writer.writeheader()

    best = []
    t_start = time.time()
    for k, word in enumerate(todo, 1):
        gi = space.index[word]
        # Each opener gets its OWN stream, derived from (seed, guess index), so a
        # row does not depend on how many openers ran before it -- a resumed run
        # reproduces the same numbers as an uninterrupted one.
        rng = np.random.default_rng([args.seed, gi])
        t0 = time.time()
        mean, se, lo, hi, lucky = simulate_opener(
            space, pat, gi, args.trials, rng, len(answers))
        secs = time.time() - t0
        best.append((mean, word))
        if writer:
            writer.writerow({"opener": word, "trials": args.trials,
                             "mean": "%.4f" % mean, "se": "%.4f" % se,
                             "min": lo, "max": hi, "lucky": lucky,
                             "secs": "%.3f" % secs})
            fh.flush()
        if args.progress and (k % args.progress == 0 or k == len(todo)):
            el = time.time() - t_start
            rate = k / el if el else 0
            print("  [%d/%d] %s mean=%.3f  %.0f openers/s  eta %.1f min"
                  % (k, len(todo), word, mean, rate,
                     (len(todo) - k) / rate / 60 if rate else 0), flush=True)
    if fh:
        fh.close()

    best.sort(reverse=True)
    print("\nlongest average under RANDOM play (this run's openers):")
    for mean, word in best[:15]:
        print("  %-6s %.4f" % (word, mean))
    print("\n%d openers in %.1f min" % (len(todo), (time.time() - t_start) / 60))
    print("A shortlist, not a winner: with %d openers the top rows are partly "
          "sampling noise." % len(openers))
    print("Re-run the head with many more trials: --openers-from <this file> --top N")
    return 0


if __name__ == "__main__":
    sys.exit(main())
