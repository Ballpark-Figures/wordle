"""Simulate multiwordle games under the fixed-opening / smallest-board strategy.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-multiwordle.sh -k 4 -t 10000            # from math/, or anywhere
    bash solver/run-multiwordle.sh -k 4 -t 10000 --seed 7
    bash solver/run-multiwordle.sh -k 4 -t 10000 --openers "clint soare"
    bash solver/run-multiwordle.sh -k 4 -t 10000 \
        --openers-from data/shared/singletons/pair_singletons.csv

WHAT THIS MEASURES, precisely: the EXPECTED TOTAL GUESSES to solve all k boards,
over random draws of the k answers AND over the strategy's own coin flips.  The
strategy, the game and the reason no guess cap is needed are all written out in
math/multiwordle.py -- read that first; this file is the trial loop around it.

IT IS A MONTE CARLO ESTIMATE, so it comes with a standard error and the summary
always prints one.  Two runs differing by less than a couple of SEs have not
measured a difference.  Everything is reproducible from (k, opening, t, seed),
which is why all four are in the output filename: a re-run of the same four
reproduces the same file exactly, and a different seed is a different sample and
gets its own file rather than being appended to an existing one.

Rows are flushed as they are played, so a Ctrl-C keeps every game finished so
far; the trailing `#` summary lines are written only on a clean finish.

Answers are drawn from the 2315 mystery words; the opening words are the only
guesses that need not be among them, since every later guess is by construction
a candidate of some board.

--openers-from reads the FIRST DATA ROW of a singletons ranking and takes every
leading `word*` column as the opening -- so the same flag supplies a single word,
a pair, a triple or a quad, and the result file records which file it came from.
It relies on that file's own ordering, and the ordering is only as good as the
run behind it: words and pairs are exhaustive, so their heads are exact, but the
triple and quad rankings are GREEDY SCREENS (see solver/run-singles.sh) and their
heads are "best of those screened", never the best opening. Nothing here checks
that, so do not describe such a run as using "the best" pair/triple/quad.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from multiwordle import answer_to_guess, draw_answers, play_game  # noqa: E402
from wordle import load_words  # noqa: E402

COLUMNS = "game,guesses,answers,sequence"


def openers_from(path):
    """The opening named by the first data row of a singletons ranking CSV.

    Takes every leading column whose name starts with `word`, so one file shape
    covers guess_singletons (`word`), pair_ (`word1,word2`), triple_ and quad_.
    """
    header = None
    with open(path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            row = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None:
                header = row
                cols = [i for i, c in enumerate(header) if c.startswith("word")]
                if not cols:
                    raise SystemExit("%s has no word column" % path)
                continue
            return [row[i] for i in cols]
    raise SystemExit("%s has no data row" % path)


def parse_args(argv):
    k = t = None
    seed = 0
    openers = []
    source = None
    out = None
    progress = 1000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-k", "--boards"):
            k = int(argv[i + 1]); i += 2
        elif a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--opener":
            openers.append(argv[i + 1]); i += 2
        elif a == "--openers":
            openers.extend(argv[i + 1].split()); i += 2
        elif a == "--openers-from":
            source = argv[i + 1]
            openers.extend(openers_from(source)); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if k is None or k < 1:
        raise SystemExit("-k (number of boards) is required and must be >= 1")
    if t is None or t < 1:
        raise SystemExit("-t (number of trials) is required and must be >= 1")
    if not openers:
        # The opening is an INPUT to this experiment, not something derived here,
        # so it is never defaulted -- a silent default would make every result
        # file ambiguous about which strategy produced it.
        raise SystemExit(
            "an opening is required: it is a parameter of the experiment.\n"
            "Use the wrapper, which supplies one: bash solver/run-multiwordle.sh")
    if len(set(openers)) != len(openers):
        raise SystemExit("the opening repeats a word: %s" % " ".join(openers))
    if out is None:
        # The strturns lesson: a run that prints its answer and saves nothing is
        # a run lost.  Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-multiwordle.sh")
    return k, t, seed, openers, source, out, progress


def summarise(scores, k):
    """Mean total guesses and its Monte Carlo standard error, plus the spread."""
    s = np.asarray(scores, dtype=np.float64)
    n = len(s)
    mean = s.mean()
    sd = s.std(ddof=1) if n > 1 else 0.0
    return {
        "trials": n,
        "boards": k,
        "mean_guesses": mean,
        "stderr": sd / np.sqrt(n) if n > 1 else 0.0,
        "sd": sd,
        "min": int(s.min()),
        "median": float(np.median(s)),
        "max": int(s.max()),
        "mean_per_board": mean / k,
    }


def main(argv):
    k, t, seed, openers, source, out, progress = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    for w in openers:
        if w not in guesses:
            raise SystemExit("opening word %r is not in the 12972-word guess list" % w)
    if k > len(answers):
        raise SystemExit("k=%d exceeds the %d answer words" % (k, len(answers)))

    pat = np.array(load_patterns())          # 12972 x 2315, ~30 MB, wants RAM
    ans2g = answer_to_guess(answers, guesses)
    openers_g = [guesses.index(w) for w in openers]
    rng = np.random.default_rng(seed)

    fh = None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fh = open(out, "w")
        fh.write("# multiwordle, fixed opening then smallest-board greedy "
                 "(see math/multiwordle.py)\n")
        fh.write("# boards=%d trials=%d opening=%s seed=%d\n"
                 % (k, t, " ".join(openers), seed))
        if source:
            fh.write("# opening taken from the first data row of %s\n" % source)
        fh.write("# answers drawn without replacement from the 2315 mystery words; "
                 "no guess cap\n")
        fh.write(COLUMNS + "\n")

    print("multiwordle: k=%d  trials=%d  opening=%s  seed=%d"
          % (k, t, " ".join(openers), seed))
    if source:
        print("  opening from %s" % source)
    scores = []
    t0 = time.time()
    for game in range(t):
        answer_idx = draw_answers(len(answers), k, rng)
        played = play_game(pat, ans2g, answer_idx, openers_g, rng)
        scores.append(len(played))
        if fh:
            fh.write("%d,%d,%s,%s\n" % (
                game, len(played),
                " ".join(answers[a] for a in answer_idx),
                " ".join(guesses[g] for g in played)))
            fh.flush()
        if progress and (game + 1) % progress == 0:
            print("  %d/%d games  mean %.4f  (%.1fs)"
                  % (game + 1, t, np.mean(scores), time.time() - t0))

    st = summarise(scores, k)
    lines = [
        "trials %d, boards %d, opening %s, seed %d"
        % (t, k, " ".join(openers), seed),
        "mean total guesses %.4f  +/- %.4f (standard error)"
        % (st["mean_guesses"], st["stderr"]),
        "sd %.4f   min %d   median %.1f   max %d"
        % (st["sd"], st["min"], st["median"], st["max"]),
        "mean guesses per board %.4f" % st["mean_per_board"],
    ]
    counts = np.bincount(np.asarray(scores))
    dist = ["  %3d guesses  %6d  %6.2f%%" % (v, c, 100.0 * c / t)
            for v, c in enumerate(counts) if c]

    print()
    for line in lines:
        print(line)
    print("distribution of total guesses:")
    for line in dist:
        print(line)
    print("\n%.1fs" % (time.time() - t0))

    if fh:
        for line in lines:
            fh.write("# " + line + "\n")
        for line in dist:
            fh.write("#" + line + "\n")
        fh.close()
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
