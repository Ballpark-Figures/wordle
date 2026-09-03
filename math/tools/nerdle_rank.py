"""Rank every legal guess by its root sum of squares, once, and store it.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-rank.sh                    # from math/, or anywhere
    bash solver/run-nerdle-rank.sh --width 6

WHY THIS EXISTS AS ITS OWN STEP.  Scoring all 374246 guesses against all 17723
answers is about 110 seconds and it is the first thing the solver, the pair
screen and the printed opener table each wanted.  They used to compute it
separately -- a single solve run paid for it twice -- so it is computed here
once and read from disk by all of them.

WHAT IT IS: for each guess, the sum of squared bin sizes of the partition it
induces on the answers, with the answers it WINS excluded (they are resolved,
not binned).  Ascending, ties on the lowest guess index in canonical symbol
order.  math/nerdle_topk.py defines the score and is the source of truth.

IT IS A RANKING, NOT A RESULT.  A good first-guess score does not make a guess a
good opener: it says nothing about what happens after the reply.  The solver's
own number is the one to quote.

THE FILE CARRIES A FINGERPRINT covering the width and both word lists, and the
readers refuse a ranking that does not match rather than using it.  Re-enumerate
the answers and this file stops being read -- silently reusing it would leave
every score confidently wrong instead of missing.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle_topk as NT  # noqa: E402
from nerdle import WIDTH  # noqa: E402


def parse_args(argv):
    width, out, show = WIDTH, None, 20
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a == "--show":
            show = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-rank.sh")
    return width, out, show


def main(argv):
    width, out, show = parse_args(argv)
    print("nerdle root ranking: width=%d" % width)
    print("every legal guess by ascending sum of squared bins over the answers.")
    print("A RANKING, NOT A RESULT -- a good first-guess score says nothing about")
    print("what happens after the reply.  See math/nerdle_topk.py.")
    sys.stdout.flush()

    t0 = time.time()
    game = NT.NerdleTopK(width=width, k=1)
    print("\n%d guesses, %d answers, %d classes (built in %.1fs)"
          % (game.NG, game.NA, game.nclasses, time.time() - t0))
    print("scoring every guess (this is the slow step)...")
    sys.stdout.flush()

    t1 = time.time()
    scores, order = game.root_ranking()
    secs = time.time() - t1
    print("\nscored %d guesses in %.1fs" % (game.NG, secs))
    print("\n%4s %-11s %14s" % ("rank", "guess", "sum of squares"))
    for r in range(min(show, len(order))):
        g = order[r]
        print("%4d %-11s %14d" % (r + 1, game.guess_words[g], scores[g]))

    if out:
        NT.save_ranking(out, game)
        print("\nwrote %s (+ .meta, fingerprint %s)" % (out, game.fingerprint()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
