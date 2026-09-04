"""CLI for the Letroso top-K solver.  Use the wrappers, not this directly.

    bash solver/run-letroso-rank.sh  --length-prior lengths
    bash solver/run-letroso-solve.sh --length-prior lengths -k 1

math/letroso_topk.py states the objective and the strategy exactly and is the
source of truth; math/letroso.py states the game's rules.  Read those before
quoting any number from here.
"""

import argparse
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import letroso
import letroso_topk as T


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--length-prior", required=True, choices=T.PRIORS,
                    help="how the game is assumed to pick the answer's LENGTH; "
                         "part of the objective, so there is no default")
    ap.add_argument("-k", "--topk", type=int, default=1)
    ap.add_argument("--rank-only", action="store_true",
                    help="score every opener and stop; writes the cached ranking")
    ap.add_argument("--rank-file", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-out", action="store_true")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    if not args.out and not args.no_out:
        raise SystemExit(
            "refusing to run without --out: a multi-hour run that prints its\n"
            "answer and saves nothing is how a day of results got lost next\n"
            "door.  Pass --out PATH, or --no-out if you really mean it.")
    if args.topk < 1:
        raise SystemExit("-k must be at least 1")

    guesses = letroso.load_words("guess")
    answers = letroso.load_words("mystery")
    w = T.weights(answers, args.length_prior)
    fp = T.fingerprint(guesses, answers, args.length_prior)

    print("letroso: %d guesses, %d answers, prior=%s, k=%d"
          % (len(guesses), len(answers), args.length_prior, args.topk))
    print("fingerprint %s" % fp)

    rank_file = args.rank_file or os.path.join(
        T.DATA, "root_rank_%s.csv.gz" % args.length_prior)

    cached = T.load_ranking(rank_file, fp)
    if cached is None:
        if os.path.exists(rank_file):
            print("ranking at %s does not match this fingerprint -- REFUSING to\n"
                  "use it; it would make every score confidently wrong."
                  % rank_file)
        print("scoring all %d openers against all %d answers "
              "(this is the slow step)..." % (len(guesses), len(answers)))
        t0 = time.time()

        def progress(done, total):
            el = time.time() - t0
            rate = done / el if el else 0
            eta = (total - done) / rate if rate else 0
            sys.stdout.write("\r  %d/%d openers  %.0f/s  elapsed %.1fh  eta %.1fh   "
                             % (done, total, rate, el / 3600, eta / 3600))
            sys.stdout.flush()

        ckpt = os.path.join(T.DATA.replace("shared", "local"),
                            "root_rank_%s.ckpt.npz" % args.length_prior)
        scores = T.rank_root(guesses, answers, w, progress=progress,
                             checkpoint=ckpt, fp=fp)
        print()
        T.save_ranking(rank_file, guesses, scores, fp, args.length_prior)
        T.clear_checkpoint(ckpt)
        print("wrote %s" % rank_file)
    else:
        words, scores_sorted = cached
        print("reusing cached ranking %s" % rank_file)
        idx = {g: i for i, g in enumerate(guesses)}
        scores = np.empty(len(guesses), np.float64)
        for wd, sc in zip(words, scores_sorted):
            scores[idx[wd]] = sc

    order = np.argsort(scores, kind="stable")
    print("\ntop %d openers by expected candidates left alive "
          "(A RANKING, NOT A RESULT):" % args.top)
    for i in range(min(args.top, len(order))):
        gi = int(order[i])
        print("  %2d. %-11s %.4f" % (i + 1, guesses[gi], scores[gi]))

    if args.rank_only:
        # The full ranking is already in rank_file; --out gets the readable head
        # of it, so the file the wrapper names actually exists.
        if args.out:
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w") as f:
                f.write("# letroso opener ranking, top %d of %d.\n"
                        % (min(args.top, len(order)), len(guesses)))
                f.write("# A RANKING, NOT A RESULT: a good first-guess score says\n")
                f.write("# nothing about what happens after the reply.\n")
                f.write("# full ranking: %s\n" % rank_file)
                f.write("# prior=%s fingerprint=%s\n" % (args.length_prior, fp))
                f.write("rank,guess,score\n")
                for i in range(min(args.top, len(order))):
                    gi = int(order[i])
                    f.write("%d,%s,%.6f\n" % (i + 1, guesses[gi], scores[gi]))
            print("wrote %s" % args.out)
        return 0

    print("\nsolving (k=%d)..." % args.topk)
    t0 = time.time()
    solver = T.Solver(guesses, answers, args.length_prior, k=args.topk,
                      root_scores=scores)
    cost, opener = solver.solve()
    secs = time.time() - t0
    print("opener %s   expected guesses %.6f   (%.1f s)" % (opener, cost, secs))

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w") as f:
            f.write("opener,expected_guesses,prior,k,guesses,answers\n")
            f.write("%s,%.6f,%s,%d,%d,%d\n"
                    % (opener, cost, args.length_prior, args.topk,
                       len(guesses), len(answers)))
        with open(args.out + ".meta", "w") as f:
            f.write("# letroso top-K solve\n")
            f.write("built: %s\n" % datetime.date.today().isoformat())
            f.write("objective: expected guesses OUTRIGHT, no cap "
                    "(unlimited guesses); NOT comparable with any "
                    "optturns/hardturns/ansall total\n")
            f.write("ranking rule: sum over bins != win of n_b * W_b, "
                    "ties on lowest guess index\n")
            f.write("length prior: %s\n" % args.length_prior)
            f.write("k: %d  (a BEAM -- the opener is the best of the k "
                    "examined, not of all %d)\n" % (args.topk, len(guesses)))
            f.write("guesses: %d  answers: %d\n" % (len(guesses), len(answers)))
            f.write("fingerprint: %s\n" % fp)
            f.write("lists: hello wordl len3-10; len3 answers are OURS "
                    "(see data/shared/words/hello/len3/README.md)\n")
            f.write("seconds: %.1f\n" % secs)
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
