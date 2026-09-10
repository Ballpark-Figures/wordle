"""Evaluate the top-K guesser ONCE over a candidate list and a weighting.

    python3 tools/topk_eval.py --k 1 --weights uniform \
        --answers data/shared/words/custom.txt --out FILE      # from math/

USE solver/run-topk-eval.sh RATHER THAN CALLING THIS DIRECTLY -- it sets --out
and tees a log.  This script REFUSES to start without --out (or an explicit
--no-out) for the same reason every other tool here does: a run that prints its
answer to a terminal and saves nothing is a result that dies with the scrollback.

WHAT IT COMPUTES.  `math/topk.py` IS the source of truth and this only drives it:
the guesser ranks every legal guess by the expected number of candidate WORDS
still alive, recurses into the K best, and keeps whichever actually minimises
expected guesses.  Reported `expected_guesses` is the weighted mean over the live
candidates.

  THERE IS NO DEPTH CAP.  This is expected guesses OUTRIGHT -- the same footing
  as multiwordle / foximax / wordlesim, and NOT the "optimum subject to a
  6-guess guarantee" that every optturns / hardturns / ansall / wturns total
  reports.  Never put the two in one table.

THE WEIGHTING IS THE OBJECTIVE, SO THERE IS NO DEFAULT.  --weights is required
and takes either

    uniform      every listed candidate equally likely -- the hill-climb's
                 all-ones starting point, and the baseline an adversarial
                 number is quoted against
    <stem>       a weight stem written by tools/freqweights.py: <stem>.weights
                 paired with <stem>.txt.  Zero-weight words are DROPPED, exactly
                 as topk.py drops them -- a weight of 0 means the word cannot be
                 the answer and the guesser knows it.

Two weightings over one word list are two different questions, so each lands in
its own file and the weighting is in the name.  So is K: each K is a different
guesser.

THE ORACLE, and it is free.  At `--k 1 --weights data/shared/freqsearch/adv_topk1`
this must reproduce the FINAL `expected_guesses` of the run that produced those
weights -- the last row of data/shared/freqsearch/topk1.csv -- because that is
the same guesser over the same weights.  A disagreement means the weight
reconstruction or this driver is wrong, not that the number moved.  Checked by
tools/checktopkeval.py on a mini problem, which needs no big matrix.

NOTE it slices the SQUARE 12972x12972 matrix (`python3 build_patterns.py --full`,
~18s / 168 MB), which is gitignored under data/local/ and so absent on a fresh
clone.  The wrapper checks and refuses with that command.
"""
import argparse
import os
import sys
import time
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from topk import TopKGame, read_words  # noqa: E402

UNIFORM = "uniform"


def read_weight_stem(stem):
    """(words, weights) from <stem>.txt / <stem>.weights, order checked.

    The two files are written together by freqweights.py precisely so their order
    cannot drift, but they are two files -- so verify rather than assume, the same
    way the C loader does.
    """
    wpath, xpath = stem + ".txt", stem + ".weights"
    for p in (wpath, xpath):
        if not os.path.exists(p):
            sys.exit("missing %s -- write both with:\n"
                     "  python3 tools/freqweights.py --from <freqsearch csv> --stem %s"
                     % (p, stem))
    words = read_words(wpath)
    pairs = []
    with open(xpath, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2:
                sys.exit("bad weight line in %s: %r" % (xpath, line))
            pairs.append((parts[0], float(Fraction(parts[1]))))
    if len(pairs) != len(words):
        sys.exit("%s has %d words but %s has %d -- they must agree position for "
                 "position" % (wpath, len(words), xpath, len(pairs)))
    for i, (w, _) in enumerate(pairs):
        if w != words[i]:
            sys.exit("position %d: %s says %r, %s says %r -- the two files must "
                     "list the same words in the same order"
                     % (i, wpath, words[i], xpath, w))
    return words, [x for _, x in pairs]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, required=True,
                    help="the guesser's beam width; each K is a different "
                         "strategy, so it is never defaulted here")
    ap.add_argument("--weights", required=True,
                    help="'uniform', or a stem written by tools/freqweights.py")
    ap.add_argument("--answers",
                    help="candidate list; required with --weights uniform, and "
                         "defaults to <stem>.txt otherwise")
    ap.add_argument("--out", help="CSV to write the result to")
    ap.add_argument("--no-out", action="store_true",
                    help="explicitly discard the result (for a smoke test)")
    ap.add_argument("--no-numba", action="store_true",
                    help="use topk.py's pure-numpy reference path (the oracle)")
    args = ap.parse_args(argv)

    if args.k < 1:
        sys.exit("--k must be at least 1")
    if not args.out and not args.no_out:
        sys.exit("--out FILE is required (or --no-out to discard the result).\n"
                 "Use solver/run-topk-eval.sh, which sets it for you.")
    if args.out and args.no_out:
        sys.exit("--out and --no-out are mutually exclusive")

    if args.weights == UNIFORM:
        if not args.answers:
            sys.exit("--answers is required with --weights uniform -- the "
                     "candidate list is part of the question")
        words, weights, wname = read_words(args.answers), None, UNIFORM
        answers_path = args.answers
    else:
        words, weights = read_weight_stem(args.weights)
        wname = os.path.basename(args.weights)
        answers_path = args.weights + ".txt"
        if args.answers and os.path.abspath(args.answers) != os.path.abspath(answers_path):
            sys.exit("--answers %s disagrees with the stem's own %s -- the weights "
                     "are paired with that list position for position"
                     % (args.answers, answers_path))

    t0 = time.perf_counter()
    game = TopKGame(answers=words, k=args.k, use_numba=not args.no_numba)
    t_build = time.perf_counter() - t0

    t0 = time.perf_counter()
    total = game.total_cost(weights)
    avg = game.expected_guesses(weights)
    t_solve = time.perf_counter() - t0

    live = len(words) if weights is None else sum(1 for x in weights if x > 0)
    wsum = float(live) if weights is None else float(sum(weights))
    # The opener is a property of the strategy, not an input -- read it off the
    # trace of any live candidate rather than naming a word anywhere.
    first_live = words[0] if weights is None else \
        next(w for w, x in zip(words, weights) if x > 0)
    opener = game.trace(first_live)[0][0]

    print("topk %d over %s: %d listed, %d live, %d legal guesses"
          % (args.k, os.path.basename(answers_path), len(words), live, game.NG))
    print("weighting            %s" % wname)
    print("opens with           %s" % opener)
    print("expected guesses     %.6f   (NO depth cap: outright, not subject to a "
          "guarantee)" % avg)
    print("weighted total       %.6f over summed weight %.6f" % (total, wsum))
    print("build %.0f ms, solve %.0f ms%s"
          % (t_build * 1e3, t_solve * 1e3, "  [numpy reference]" if args.no_numba else ""))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write("# topk_eval: expected guesses OUTRIGHT, no depth cap -- not "
                     "comparable with any optturns-family total\n")
            fh.write("# settings k=%d weighting=%s answers=%s numba=%d\n"
                     % (args.k, wname, os.path.relpath(answers_path),
                        0 if args.no_numba else 1))
            fh.write("k,weighting,answers,listed,live,guesses,opener,"
                     "expected_guesses,weighted_total,total_weight,seconds\n")
            fh.write("%d,%s,%s,%d,%d,%d,%s,%.12f,%.12f,%.12f,%.1f\n"
                     % (args.k, wname, os.path.relpath(answers_path), len(words),
                        live, game.NG, opener, avg, total, wsum, t_solve))
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
