"""Screen two-equation openers: every pair drawn from the top N single guesses.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-pairs.sh                    # from math/, or anywhere
    bash solver/run-nerdle-pairs.sh --top-n 200
    bash solver/run-nerdle-pairs.sh --width 6 --top-n 50

WHAT IT COMPUTES: the two guesses are played BLIND, one after the other, before
any feedback is used -- the same convention the multiwordle openings follow.  An
answer's joint bin is the PAIR of feedbacks the two guesses give it, and the
score is the sum of squared joint bin sizes, ascending, exactly as for a single
guess.  An answer that either guess WINS outright is resolved and joins no bin.

THIS IS A SCREEN, NOT A SEARCH, and the distinction is the whole caveat.  Only
pairs drawn from the best N SINGLE guesses are examined, so the best pair overall
can be missed outright: two guesses that split poorly alone may cover each
other's blind spots, and nothing here would ever look at them.  Report the
result as "the best pair among the top N", never as "the best pair".  Raising
--top-n widens the screen quadratically -- N=1000 is half a million pairs -- and
never makes it exhaustive.

THE SCORE IS NOT EXPECTED GUESSES.  It measures how finely the pair splits the
answers and nothing else; in particular it does not know that an answer won by
the FIRST guess is cheaper than one won by the second, since both simply leave
the partition.  Feed a promising pair to the solver if you want its real cost.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle_topk as NT  # noqa: E402
from nerdle import WIDTH  # noqa: E402

RULES = "2026-09-03"


def parse_args(argv):
    width, top_n, out, show = WIDTH, 100, None, 20
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a == "--top-n":
            top_n = int(argv[i + 1]); i += 2
        elif a == "--show":
            show = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if top_n < 2:
        raise SystemExit("--top-n must be at least 2 to have a pair")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-pairs.sh")
    return width, top_n, out, show


def main(argv):
    width, top_n, out, show = parse_args(argv)

    print("nerdle two-equation opener screen: width=%d top-n=%d rules=%s"
          % (width, top_n, RULES))
    print("A SCREEN over pairs of the best %d SINGLE guesses -- not a search over" % top_n)
    print("all pairs, so this is the best pair AMONG THOSE, never the best pair.")
    print("The score is split quality, not expected guesses.")
    sys.stdout.flush()

    t0 = time.time()
    game = NT.NerdleTopK(width=width, k=1)
    print("\n%d guesses, %d answers, %d classes (built in %.1fs)"
          % (game.NG, game.NA, game.nclasses, time.time() - t0))
    print("ranking singles, then scoring %d pairs..." % (top_n * (top_n - 1) // 2))
    sys.stdout.flush()

    NT.attach_ranking(game, progress=NT.progress_printer(10.0))
    t1 = time.time()
    gs, scored = game.pair_scores(top_n)
    secs = time.time() - t1

    scores, order = game.root_ranking()
    single_best = (game.guess_words[int(order[0])], int(scores[order[0]]))

    print("\nscored %d pairs from the top %d singles in %.1fs"
          % (len(scored), len(gs), secs))
    if single_best:
        print("for scale, the best SINGLE guess: %s at %d"
              % (single_best[0], single_best[1]))
    print("\n%4s %-11s %-11s %14s" % ("rank", "first", "second", "sum of squares"))
    for r, (score, i, j) in enumerate(scored[:show]):
        print("%4d %-11s %-11s %14d"
              % (r + 1, game.guess_words[gs[i]], game.guess_words[gs[j]], score))

    if out:
        with open(out, "w") as f:
            f.write("rank,first,second,sum_of_squares\n")
            for r, (score, i, j) in enumerate(scored):
                f.write("%d,%s,%s,%d\n"
                        % (r + 1, game.guess_words[gs[i]], game.guess_words[gs[j]], score))
        with open(out + ".meta", "w") as m:
            m.write("kind=pair-opener-screen\n")
            m.write("width=%d\ntop_n=%d\nrules=%s\n" % (width, top_n, RULES))
            m.write("exhaustive=0\n")
            m.write("scope=pairs-drawn-from-the-top-n-singles\n")
            m.write("score=ascending-sum-of-squared-joint-bins\n")
            m.write("blind=1\n")
            m.write("guesses=%d\nanswers=%d\nclasses=%d\n"
                    % (game.NG, game.NA, game.nclasses))
            m.write("pairs=%d\n" % len(scored))
            if single_best:
                m.write("best_single=%s\nbest_single_score=%d\n" % single_best)
            if scored:
                s, i, j = scored[0]
                m.write("best_pair=%s %s\nbest_pair_score=%d\n"
                        % (game.guess_words[gs[i]], game.guess_words[gs[j]], s))
            m.write("seconds=%.1f\n" % secs)
        print("\nwrote %s (+ .meta)" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
