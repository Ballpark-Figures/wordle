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

import gzip
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle_topk as NT  # noqa: E402
from nerdle import WIDTH  # noqa: E402

RULES = "2026-09-03"


# Every pair is scored, but writing every pair does not scale: --top-n 10000 is
# 49,995,000 of them, which came to 1.67 GB uncompressed in data/shared -- a
# committed tree.  Only the head is ever read, so the file is capped and gzipped,
# and the .meta records `scored`, `written` and `complete` the way the singletons
# files do, so a truncated file can never be mistaken for a full one.
DEFAULT_WRITE_TOP = 100000


def parse_args(argv):
    width, top_n, out, show = WIDTH, 100, None, 20
    write_top = DEFAULT_WRITE_TOP
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--write-top":
            write_top = int(argv[i + 1]); i += 2
        elif a == "--width":
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
    return width, top_n, out, show, write_top


def main(argv):
    width, top_n, out, show, write_top = parse_args(argv)

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
    print("ranking singles, then scoring %d pairs (Ctrl-C stops it within a"
          " second)." % (top_n * (top_n - 1) // 2))
    print("Every improvement on the running best is printed as it is met; ties")
    print("are not, or a plateau would flood the log.")
    sys.stdout.flush()

    NT.attach_ranking(game, progress=NT.progress_printer(10.0))
    def show_best(score, first, second, done, total, elapsed):
        print("  NEW BEST %12d  %-11s %-11s   %6.2f%%  %7.1fs"
              % (score, first, second, 100.0 * done / total, elapsed))
        sys.stdout.flush()

    t1 = time.time()
    gs, scored = game.pair_scores(top_n, progress=NT.progress_printer(10.0),
                                  on_best=show_best)
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
        keep = len(scored) if write_top <= 0 else min(write_top, len(scored))
        opener = gzip.open if out.endswith(".gz") else open
        with opener(out, "wt") as f:
            f.write("rank,first,second,sum_of_squares\n")
            for r, (score, i, j) in enumerate(scored[:keep]):
                f.write("%d,%s,%s,%d\n"
                        % (r + 1, game.guess_words[gs[i]], game.guess_words[gs[j]], score))
        if keep < len(scored):
            print("\nwrote the best %d of %d pairs (--write-top); the rest are"
                  " scored but not recorded" % (keep, len(scored)))
        with open(out + ".meta", "w") as m:
            m.write("kind=pair-opener-screen\n")
            m.write("width=%d\ntop_n=%d\nrules=%s\n" % (width, top_n, RULES))
            m.write("exhaustive=0\n")
            m.write("scope=pairs-drawn-from-the-top-n-singles\n")
            m.write("score=ascending-sum-of-squared-joint-bins\n")
            m.write("blind=1\n")
            m.write("guesses=%d\nanswers=%d\nclasses=%d\n"
                    % (game.NG, game.NA, game.nclasses))
            m.write("scored=%d\n" % len(scored))
            m.write("written=%d\n" % keep)
            m.write("complete=%d\n" % int(keep == len(scored)))
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
