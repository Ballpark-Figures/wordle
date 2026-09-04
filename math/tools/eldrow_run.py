"""Run the Eldrow longest-stall search (eldrow.py) from the shell.

Three modes, covering every search in eldrow.py:

  --beam    the pass-sweep level beam over a whole word list, seeking a stall of a
            given --target depth (the old sizePassLevelSearch). With --rand-top R it
            is the randomized randSizePassLevelSearch instead. Returns the deepest
            chain it FOUND -- a lower bound on the true longest.

  --heuristic {best,sum,new}   the single-level searches (levelSearch /
            sumLevelSearch / newLevelSearch): expand one level per step by a drop
            heuristic, no width cap. Also seeks --target.

  --exact   the exact branch-and-bound longest chain on a SMALL list (--sample /
            --limit). Exponential, so it is for tens of words, not thousands.

All maximise a NARROWING chain (guesses drawn from the live candidate list) and
count guesses-until-a-singleton, NOT the final naming -- see eldrow.py. Numbers are
over OUR word lists, not antiwordle.com's, and this is not the game's value.

    python3 tools/eldrow_run.py --beam --target 17                 # full 12972, the old live call
    python3 tools/eldrow_run.py --beam --target 12 --words mystery --size 200
    python3 tools/eldrow_run.py --beam --target 15 --rand-top 50 --seed 1   # randomized
    python3 tools/eldrow_run.py --heuristic sum --target 12 --words mystery
    python3 tools/eldrow_run.py --exact --sample 8                 # exact, tiny list
    python3 tools/eldrow_run.py --exact --limit 8 --bound letters

MODE IS REQUIRED (--beam / --heuristic / --exact): --exact on a big list would
hang, and the searches need a target, so pick one explicitly.
"""
import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random

from eldrow import beam_stall, heuristic_search, longest_chain
from wordle import load_words


def _record(args, mode, words, n_words, target, result, kind, line, secs, settings):
    """Append one row describing this run. One writer, so the three modes cannot
    drift apart in what they record.

    Every knob that changes WHAT was computed is a column, not just a filename: a
    beam to target 15 and an exact search over 8 words are different quantities,
    and `kind` says outright whether the number is exact or a lower bound -- the
    beam and the single-level searches only ever find a chain, never prove one is
    longest.
    """
    if not args.out:
        return
    fresh = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "a", newline="") as fh:
        w = csv.writer(fh)
        if fresh:
            w.writerow(["mode", "words", "n_words", "target", "result", "kind",
                        "settings", "secs", "line"])
        w.writerow([mode, words, n_words, target, result, kind, settings,
                    "%.3f" % secs, " ".join(line)])
    print("wrote %s" % args.out)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--beam", action="store_true",
                      help="pass-sweep beam over a word list, seeking --target depth")
    mode.add_argument("--heuristic", choices=["best", "sum", "new"],
                      help="single-level search (levelSearch/sumLevelSearch/"
                           "newLevelSearch), seeking --target depth")
    mode.add_argument("--exact", action="store_true",
                      help="exact longest chain on a SMALL list (--sample/--limit)")

    ap.add_argument("--words", default="guess", choices=["guess", "mystery"],
                    help="which list the beam/heuristic runs over (default: 12972)")
    ap.add_argument("--target", type=int, default=0,
                    help="the stall depth to search for (beam/heuristic)")
    ap.add_argument("--size", type=int, default=1000,
                    help="beam: per-level candidate budget per pass (default 1000)")
    ap.add_argument("--beam-cap", type=int, default=1_000_000,
                    help="beam: max states kept per level (default 1e6)")
    ap.add_argument("--key", default="lex", choices=["lex", "sum"],
                    help="beam: state ranking (lex = the original's ordering)")
    ap.add_argument("--rand-top", type=int, default=0,
                    help="beam: expand a RANDOM state among the top R (the old "
                         "randSizePassLevelSearch; keeps no width cap)")

    ap.add_argument("--sample", type=int, default=0,
                    help="exact: random N-word list (seeded)")
    ap.add_argument("--limit", type=int, default=0,
                    help="exact: first N words of the mystery list")
    ap.add_argument("--bound", default="size", choices=["size", "letters"],
                    help="exact: pruning bound (see eldrow.py)")
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for --sample and for --rand-top")
    ap.add_argument("--out", help="CSV to append the run's result to")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, save nothing (must be explicit)")
    args = ap.parse_args()

    if not args.out and not args.no_out:
        ap.error("give --out FILE, or --no-out to save nothing.\n"
                 "A beam over the full dictionary can run a long time, and a run "
                 "with nowhere to put its answer is a run thrown away; prefer the "
                 "wrapper, solver/run-eldrow.sh.")
    if args.out and args.no_out:
        ap.error("--out and --no-out are mutually exclusive")

    if args.beam:
        if args.target < 1:
            ap.error("--beam needs --target N (the stall depth to search for)")
        words = load_words(args.words)
        t0 = time.time()
        if args.rand_top:
            random.seed(args.seed)
            print("randomized beam over %d %s words, target %d "
                  "(size %d, rand-top %d, seed %d, key %s, no cap)"
                  % (len(words), args.words, args.target, args.size, args.rand_top,
                     args.seed, args.key))
            depth, line = beam_stall(words, args.target, size=args.size,
                                     beam_cap=None, key=args.key,
                                     rand_top=args.rand_top, rng=random)
        else:
            print("beam over %d %s words, target depth %d (size %d, cap %d, key %s)"
                  % (len(words), args.words, args.target, args.size, args.beam_cap,
                     args.key))
            depth, line = beam_stall(words, args.target, size=args.size,
                                     beam_cap=args.beam_cap, key=args.key)
        print("deepest chain found: %d" % depth)
        print("line: %s" % " ".join(line))
        secs = time.time() - t0
        print("  in %.1fs" % secs)
        if depth < args.target:
            print("(did not reach the target -- a lower bound, not a failure proof)")
        _record(args, "beam-rand" if args.rand_top else "beam", args.words,
                len(words), args.target, depth, "lower-bound", line, secs,
                "size=%d,cap=%s,key=%s,rand_top=%d,seed=%d"
                % (args.size, "none" if args.rand_top else args.beam_cap,
                   args.key, args.rand_top, args.seed))
        return

    if args.heuristic:
        if args.target < 1:
            ap.error("--heuristic needs --target N (the stall depth to search for)")
        words = load_words(args.words)
        print("%s single-level search over %d %s words, target depth %d"
              % (args.heuristic, len(words), args.words, args.target))
        t0 = time.time()
        depth, line = heuristic_search(words, args.target, selector=args.heuristic)
        print("deepest chain found: %d" % depth)
        print("line: %s" % " ".join(line))
        secs = time.time() - t0
        print("  in %.1fs" % secs)
        if depth < args.target:
            print("(did not reach the target -- a lower bound, not a failure proof)")
        _record(args, "heuristic-" + args.heuristic, args.words, len(words),
                args.target, depth, "lower-bound", line, secs, "")
        return

    # --exact
    if not (args.sample or args.limit):
        ap.error("--exact needs --sample N or --limit N (it is exponential)")
    words = load_words("mystery")
    if args.sample:
        words = random.Random(args.seed).sample(words, args.sample)
    else:
        words = words[:args.limit]
    print("exact longest chain over %d words (bound=%s)" % (len(words), args.bound))
    t0 = time.time()
    length, line = longest_chain(words, bound=args.bound)
    print("longest chain (guesses to a singleton): %d" % length)
    print("line: %s" % " ".join(line))
    secs = time.time() - t0
    print("  in %.1fs" % secs)
    scope = ("sample%d/seed%d" % (args.sample, args.seed) if args.sample
             else "limit%d" % args.limit)
    _record(args, "exact", scope, len(words), "", length, "exact", line, secs,
            "bound=%s" % args.bound)


if __name__ == "__main__":
    main()
