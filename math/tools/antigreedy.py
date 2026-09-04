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
    args = ap.parse_args()

    if not (args.sample or args.limit or args.full or args.opener_only):
        ap.error("give a scope: --sample N, --limit N, --full, or --opener-only.\n"
                 "A bare run would silently start the slow full recursion.")

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
    print("greedy opener: %s  (expected surviving set %.4f, %.1f%% of %d)"
          % (word, keep, 100 * keep / len(answers), len(answers)))
    print("  opener in %.1fs" % (time.time() - t0))

    if not args.opener_only:
        t0 = time.time()
        exp = greedy_expected(answers, answer_set, args.verbose)
        print("greedy expected guesses: %.4f" % exp)
        print("  recursion in %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
