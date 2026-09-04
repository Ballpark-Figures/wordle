"""Simulate FoxiMax games under the greedy most-likely-to-hit letter strategy.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-foximax.sh -t 10000              # from math/, or anywhere
    bash solver/run-foximax.sh -t 10000 --seed 7

WHAT THIS MEASURES, precisely: the EXPECTED NUMBER OF WORDS (1 + misses) needed
to clear the grid, over random draws of the hidden words.  The game, the
strategy and the reason no cap is needed are written out in math/foximax.py --
read that first; this file is the trial loop around it.  Note the real site's
eight-word limit is NOT modelled, so no game here is ever a loss.

IT IS A MONTE CARLO ESTIMATE, so the summary always prints a standard error.
Two runs differing by less than a couple of SEs have not measured a difference.
The strategy itself is deterministic, so the only randomness is the word draws:
everything is reproducible from (word list, t, seed), which is why all three are
in the output filename.  A different seed is a different sample and gets its own
file rather than being appended to an existing one.

Rows are flushed as they are played, so a Ctrl-C keeps every game finished so
far; the trailing `#` summary lines are written only on a clean finish.

Hidden words are drawn WITHOUT REPLACEMENT from the 2315 mystery words -- our
list, not FoxiMax's, which we cannot read.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from foximax import play_game, position_masks, to_letters  # noqa: E402
from wordle import load_words  # noqa: E402

COLUMNS = "game,words,guesses,letters,hits,answers"


def parse_args(argv):
    t = None
    seed = 0
    words = "mystery"
    out = None
    progress = 1000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--words":
            words = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if t is None or t < 1:
        raise SystemExit("-t (number of trials) is required and must be >= 1")
    if out is None:
        # The strturns lesson: a run that prints its answer and saves nothing is
        # a run lost.  Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-foximax.sh")
    return t, seed, words, out, progress


def load_pool(which):
    """The hidden-word pool: a canonical list name, or a path to a word file."""
    if which in ("mystery", "guess"):
        return load_words(which)
    with open(which) as f:
        return [line.strip() for line in f if line.strip()]


def summarise(scores, guesses):
    """Mean words and its Monte Carlo standard error, plus the spread."""
    s = np.asarray(scores, dtype=np.float64)
    n = len(s)
    sd = s.std(ddof=1) if n > 1 else 0.0
    return {
        "trials": n,
        "mean_words": s.mean(),
        "stderr": sd / np.sqrt(n) if n > 1 else 0.0,
        "sd": sd,
        "min": int(s.min()),
        "median": float(np.median(s)),
        "max": int(s.max()),
        "mean_guesses": float(np.mean(guesses)),
    }


def main(argv):
    t, seed, which, out, progress = parse_args(argv)

    pool = load_pool(which)
    lengths = {len(w) for w in pool}
    if len(lengths) != 1:
        raise SystemExit("the word list mixes lengths: %s" % sorted(lengths))
    masks = position_masks(pool)
    rng = np.random.default_rng(seed)

    fh = None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fh = open(out, "w")
        fh.write("# foximax, greedy most-likely-to-hit letter "
                 "(see math/foximax.py)\n")
        fh.write("# words=%s (%d words, %d letters) trials=%d seed=%d\n"
                 % (which, len(pool), lengths.pop(), t, seed))
        fh.write("# hidden words drawn without replacement; no word cap, so no "
                 "game is a loss; score is the WORD COUNT\n")
        fh.write("# hits: 1 per letter that appeared in a word then in play, "
                 "0 for a miss (each 0 added a word)\n")
        fh.write(COLUMNS + "\n")

    print("foximax: trials=%d  words=%s (%d)  seed=%d"
          % (t, which, len(pool), seed))
    scores, guesses = [], []
    t0 = time.time()
    for game in range(t):
        letters, hits, played = play_game(masks, rng)
        scores.append(len(played))
        guesses.append(len(letters))
        if fh:
            fh.write("%d,%d,%d,%s,%s,%s\n" % (
                game, len(played), len(letters),
                to_letters(letters),
                "".join("1" if h else "0" for h in hits),
                " ".join(pool[w] for w in played)))
            fh.flush()
        if progress and (game + 1) % progress == 0:
            print("  %d/%d games  mean words %.4f  (%.1fs)"
                  % (game + 1, t, np.mean(scores), time.time() - t0))

    st = summarise(scores, guesses)
    lines = [
        "trials %d, words %s (%d), seed %d" % (t, which, len(pool), seed),
        "mean words %.4f  +/- %.4f (standard error)"
        % (st["mean_words"], st["stderr"]),
        "sd %.4f   min %d   median %.1f   max %d"
        % (st["sd"], st["min"], st["median"], st["max"]),
        "mean letters guessed %.4f" % st["mean_guesses"],
    ]
    counts = np.bincount(np.asarray(scores))
    dist = ["  %3d words  %6d  %6.2f%%" % (v, c, 100.0 * c / t)
            for v, c in enumerate(counts) if c]

    print()
    for line in lines:
        print(line)
    print("distribution of word counts:")
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
