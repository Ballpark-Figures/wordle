"""Run the antiwordle GREEDY heuristic (antiwordle_greedy.py) from the shell.

A quick, approximate figure for the UNCERTAINTY phase: the greedy first guess and,
optionally, the expected game length of the greedy "keep the pool big" player. This
is a HEURISTIC strategy's expected length over OUR word lists, not the game's value
and not antiwordle.com's dictionary -- see antiwordle_greedy.py's docstring.

    python3 tools/antigreedy.py --opener-only            # greedy first guess, full 2315 (a minute-ish)
    python3 tools/antigreedy.py --sample 40              # a random 40-answer game, full recursion
    python3 tools/antigreedy.py --limit 40               # the first 40 answers in list order
    python3 tools/antigreedy.py --full                   # all 2315, recursion -- SLOW, opt in explicitly

The candidate list and the answer set are the same list here (the start-of-game
state, where every possible answer is still alive). SCOPE IS REQUIRED: a bare run
would launch the slow full recursion silently, so ask for --sample / --limit /
--full / --opener-only explicitly, the way the stall tool insists on --out.
"""
import argparse
import csv
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle_greedy import greedy_expected, greedy_opener
from wordle import load_words


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--sample", type=int, default=0,
                       help="random N-answer game (seeded, so reproducible)")
    scope.add_argument("--limit", type=int, default=0,
                       help="the first N answers in word-list order")
    scope.add_argument("--full", action="store_true",
                       help="all 2315 answers -- the full recursion is SLOW")
    ap.add_argument("--opener-only", action="store_true",
                    help="just the greedy first guess (no recursion); pairs with "
                         "any scope, and is the fast path on the full list")
    ap.add_argument("--seed", type=int, default=0,
                    help="--sample seed (default 0, for a stable answer)")
    ap.add_argument("--verbose", action="store_true",
                    help="print the greedy player's progress")
    ap.add_argument("--out", help="CSV to append the run's results to")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, save nothing (must be explicit)")
    args = ap.parse_args()

    if not (args.sample or args.limit or args.full or args.opener_only):
        ap.error("give a scope: --sample N, --limit N, --full, or --opener-only.\n"
                 "A bare run would silently start the slow full recursion.")
    if not args.out and not args.no_out:
        ap.error("give --out FILE, or --no-out to save nothing.\n"
                 "A --full recursion can run for a long time, and a run with nowhere "
                 "to put its answer is a run thrown away; prefer the wrapper, "
                 "solver/run-antiwordle-greedy.sh.")
    if args.out and args.no_out:
        ap.error("--out and --no-out are mutually exclusive")

    answers = load_words("mystery")
    if args.sample:
        answers = random.Random(args.seed).sample(answers, args.sample)
    elif args.limit:
        answers = answers[:args.limit]
    # --full and --opener-only (with no other scope) use the whole 2315.
    answer_set = set(answers)

    print("candidates = answers = %d words" % len(answers))

    t0 = time.time()
    word, keep = greedy_opener(answers, answer_set)
    open_secs = time.time() - t0
    print("greedy opener: %s  (expected surviving set %.4f, %.1f%% of %d)"
          % (word, keep, 100 * keep / len(answers), len(answers)))
    print("  opener in %.1fs" % open_secs)

    exp = rec_secs = None
    if not args.opener_only:
        t0 = time.time()
        exp = greedy_expected(answers, answer_set, args.verbose)
        rec_secs = time.time() - t0
        print("greedy expected guesses: %.4f" % exp)
        print("  recursion in %.1fs" % rec_secs)

    if args.out:
        # One row per run. The SCOPE is a column rather than only a filename, so a
        # row can never be read as applying to a different answer set than the one
        # it was computed over.
        scope = ("full" if args.full else
                 "sample%d/seed%d" % (args.sample, args.seed) if args.sample else
                 "limit%d" % args.limit if args.limit else "opener-only")
        fresh = not os.path.exists(args.out) or os.path.getsize(args.out) == 0
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "a", newline="") as fh:
            w = csv.writer(fh)
            if fresh:
                w.writerow(["scope", "answers", "opener", "expected_keep",
                            "expected_guesses", "opener_secs", "recursion_secs"])
            w.writerow([scope, len(answers), word, "%.6f" % keep,
                        "" if exp is None else "%.6f" % exp,
                        "%.3f" % open_secs,
                        "" if rec_secs is None else "%.3f" % rec_secs])
        print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
