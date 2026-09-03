"""Run the top-K Nerdle solver and record what it found.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-solve.sh                    # from math/, or anywhere
    bash solver/run-nerdle-solve.sh -k 2
    bash solver/run-nerdle-solve.sh --rank-only

WHAT IT REPORTS: the EXPECTED NUMBER OF GUESSES over the answer list taken
uniformly, under a beam that ranks guesses by the sum of squared bin sizes.
math/nerdle_topk.py states the objective and the strategy exactly and is the
source of truth; read it before quoting any number.

THIS IS NOT AN OPTIMUM.  `-k K` examines exactly K guesses at every node, the
ROOT INCLUDED, so the opener is the best of the K examined and not the best of
374246.  A larger K is a different (and never worse) strategy, so every K gets
its own file.  There is also NO DEPTH CAP -- this is expected guesses outright,
unlike the optturns family next door, whose totals are optima subject to a
guarantee.  Never put the two in one table.

--rank-only does the root ranking and stops.  The root is one full pass over
every guess against every answer, which is the single most expensive node in the
search, so this is the cheap way to see what the beam would open with before
committing to a whole solve.
"""

import gzip
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle_topk as NT  # noqa: E402
from nerdle import WIDTH  # noqa: E402

RULES = "2026-09-03"


def resolve_openers(spec, from_file, guess_words):
    """The opening, as a list of words. An INPUT, never defaulted.

    `--openers-from FILE` takes the FIRST DATA ROW of a ranking CSV and keeps
    every field that is a legal guess, in order -- so it reads a pairs file
    (rank,first,second,score) as the two words and a rank file
    (rank,guess,score) as the one, with no per-file column list to maintain.  A
    bare number is never a legal guess, so the rank and score fields cannot be
    mistaken for one.
    """
    words = list(spec)
    if from_file:
        legal = set(guess_words)
        opener = gzip.open if from_file.endswith(".gz") else open
        with opener(from_file, "rt") as f:
            rows = [ln for ln in f if ln.strip()]
        picked = []
        for ln in rows[1:]:                    # skip the header
            for field in ln.strip().split(","):
                if field.strip() in legal:
                    picked.append(field.strip())
            if picked:
                break
        if not picked:
            raise SystemExit("no legal guess found in the first data row of %s"
                             % from_file)
        words += picked
    return words


def parse_args(argv):
    width, k, out, top, rank_only = WIDTH, 1, None, 10, False
    openers, from_file = [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--opener":
            openers.append(argv[i + 1]); i += 2
        elif a == "--openers":
            openers.extend(argv[i + 1].split()); i += 2
        elif a == "--openers-from":
            from_file = argv[i + 1]; i += 2
        elif a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a in ("-k", "--topk"):
            k = int(argv[i + 1]); i += 2
        elif a == "--top":
            top = int(argv[i + 1]); i += 2
        elif a == "--rank-only":
            rank_only = True; i += 1
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if k < 1:
        raise SystemExit("-k must be at least 1")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-solve.sh")
    return width, k, out, top, rank_only, openers, from_file


def root_ranking(game, top):
    """The `top` best-scoring guesses at the root, with their scores.

    Reads the stored ranking -- see nerdle_topk.attach_ranking.  This used to
    call the kernel itself, and then the solve called it AGAIN, so a single run
    paid for the slowest step twice.
    """
    scores, order = game.root_ranking()
    return [(game.guess_words[int(g)], int(scores[g])) for g in order[:top]]


def main(argv):
    width, k, out, top, rank_only, opener_spec, from_file = parse_args(argv)

    print("nerdle top-K solver: width=%d k=%d rules=%s" % (width, k, RULES))
    print("objective: EXPECTED GUESSES outright, no depth cap.  A beam, so the")
    print("result is the best of the K guesses examined at each node, including")
    print("the root -- not an optimum.  See math/nerdle_topk.py.")
    sys.stdout.flush()

    t0 = time.time()
    game = NT.NerdleTopK(width=width, k=k)
    print("\n%d guesses, %d answers, %d commutative classes (built in %.1fs)"
          % (game.NG, game.NA, game.nclasses, time.time() - t0))
    if not NT._HAVE_NUMBA:
        print("NOTE: numba is not installed, so this is the numpy reference path.")
        print("      It implements the same rules and is far slower.")
    sys.stdout.flush()

    openers = resolve_openers(opener_spec, from_file, game.guess_words)
    if openers:
        missing = [w for w in openers if w not in set(game.guess_words)]
        if missing:
            raise SystemExit("not legal guesses at width %d: %s"
                             % (width, ", ".join(missing)))
        print("\nOPENING FIXED, played BLIND in order: %s" % " ".join(openers))
        if from_file:
            print("resolved from %s (first data row)" % from_file)
        print("The beam takes over below it, so this measures THAT opening --")
        print("not the best one.  A blind second guess is played even when the")
        print("first already narrowed the answer, so it can cost more than a")
        print("free run, which adapts after the first reply.")

    t1 = time.time()
    # A fixed opening never consults the root ranking, so do not build one for it.
    NT.attach_ranking(game, progress=NT.progress_printer(10.0),
                      compute=not openers)
    rank_secs = time.time() - t1
    ranking = []
    if game._root is not None:
        ranking = root_ranking(game, top)
        print("\nroot ranking, best %d by sum of squared bins (%.1fs):"
              % (len(ranking), rank_secs))
        for i, (word, score) in enumerate(ranking):
            print("  %2d | %-10s %12d" % (i + 1, word, score))
    sys.stdout.flush()

    total = expected = None
    opener = " ".join(openers) if openers else (ranking[0][0] if ranking else None)
    solve_secs = 0.0
    if not rank_only:
        print("\nsearching:")
        sys.stdout.flush()
        t2 = time.time()
        if openers:
            total, _ = game.solve_from(openers, progress=NT.progress_printer(10.0))
        else:
            # One walk, cached -- asking for the total and the opener separately
            # used to run the whole search twice.
            total = game.total_guesses(progress=NT.progress_printer(10.0))
            opener = game.opener()
        solve_secs = time.time() - t2
        expected = total / game.NA
        print("\ntotal %d guesses over %d answers" % (total, game.NA))
        print("expected %.4f guesses, opening with %s  (%.1fs)"
              % (expected, opener, solve_secs))

    if out:
        with open(out, "w") as f:
            f.write("width,k,guesses,answers,classes,opener,total,expected,seconds\n")
            f.write("%d,%d,%d,%d,%d,%s,%s,%s,%.1f\n"
                    % (width, k, game.NG, game.NA, game.nclasses, opener,
                       "" if total is None else total,
                       "" if expected is None else "%.6f" % expected,
                       solve_secs))
            f.write("\nrank,guess,sum_of_squares\n")
            for i, (word, score) in enumerate(ranking):
                f.write("%d,%s,%d\n" % (i + 1, word, score))
        with open(out + ".meta", "w") as m:
            m.write("kind=topk-solve\n")
            m.write("width=%d\n" % width)
            m.write("k=%d\n" % k)
            m.write("rules=%s\n" % RULES)
            m.write("objective=expected-guesses-no-cap\n")
            m.write("ranking=ascending-sum-of-squared-bins\n")
            m.write("win=commutative-class\n")
            m.write("optimum=0\n")
            m.write("rank_only=%d\n" % int(rank_only))
            m.write("opening_fixed=%d\n" % int(bool(openers)))
            if openers:
                m.write("opening=%s\n" % " ".join(openers))
                m.write("opening_blind=1\n")
                if from_file:
                    m.write("opening_from=%s\n" % from_file)
            m.write("guesses=%d\nanswers=%d\nclasses=%d\n"
                    % (game.NG, game.NA, game.nclasses))
            if total is not None:
                m.write("total=%d\nexpected=%.6f\n" % (total, expected))
            m.write("opener=%s\n" % opener)
            m.write("rank_seconds=%.1f\nsolve_seconds=%.1f\n" % (rank_secs, solve_secs))
        print("\nwrote %s (+ .meta)" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
