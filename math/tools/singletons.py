"""Rank every guess word by how many of its feedback patterns are SINGLETONS.

A pattern is a singleton for a guess when exactly one answer produces it, so
seeing it identifies the answer outright -- the guess after it is a formality.
This counts them, per guess, over the whole guess list.

    python3 tools/singletons.py            # 12972 guesses vs the 2315 answers
    python3 tools/singletons.py --full     # ... vs all 12972 words as answers
    python3 tools/singletons.py --top 50   # longer printed head

THE ANSWER SET IS PART OF THE QUESTION, not a detail. A bucket's size is counted
over whichever answer list the pattern matrix was built against, so the default
(the 2315 mystery words) and `--full` (every legal word an answer) give different
numbers for the same guess -- they are answers to different questions. The header
of the emitted CSV records which one produced it.

TWO COLUMNS, because the winning pattern is a special case. A guess that is
itself an answer always has an all-green bucket of size exactly one -- itself --
which is a singleton by the definition above but tells you nothing you did not
already know by winning. So `singletons` counts every size-1 bucket and
`singletons_nowin` excludes the all-green one; they differ by exactly 1 for the
2315 guesses that are answers, and by 0 for the rest. Which one is the right
denominator is a modelling choice, so both are emitted rather than one being
picked here.

Output: data/shared/singletons/guess_singletons[_full].csv, sorted descending by
`singletons`, ties broken alphabetically. Small enough to commit, and it is a
pure function of the committed word lists, so it regenerates anywhere.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import all_green, load_words  # noqa: E402

FULL = "--full" in sys.argv
TOP = 25
if "--top" in sys.argv:
    TOP = int(sys.argv[sys.argv.index("--top") + 1])

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(_MATH, "data", "shared", "singletons")
OUT = os.path.join(OUT_DIR, "guess_singletons_full.csv" if FULL else "guess_singletons.csv")

guesses = load_words("guess")
answers = guesses if FULL else load_words("mystery")
PAT = load_patterns(full=FULL)
if PAT.shape != (len(guesses), len(answers)):
    raise SystemExit("pattern matrix is %s, expected %s -- rebuild with "
                     "build_patterns.py%s" % (PAT.shape, (len(guesses), len(answers)),
                                              " --full" if FULL else ""))
NPAT = 3 ** len(guesses[0])
WIN = all_green(len(guesses[0]))

# Chunked so the bucket histogram stays small: one bincount over a block of rows,
# each row offset into its own NPAT-wide slot, then reshaped back to (rows, NPAT).
CHUNK = 512
singles = np.zeros(len(guesses), dtype=np.int32)
win_is_single = np.zeros(len(guesses), dtype=bool)
t0 = time.time()
for lo in range(0, len(guesses), CHUNK):
    rows = np.asarray(PAT[lo:lo + CHUNK], dtype=np.int64)
    n = rows.shape[0]
    off = rows + (np.arange(n, dtype=np.int64) * NPAT)[:, None]
    hist = np.bincount(off.ravel(), minlength=n * NPAT).reshape(n, NPAT)
    singles[lo:lo + n] = (hist == 1).sum(axis=1)
    win_is_single[lo:lo + n] = hist[:, WIN] == 1
nowin = singles - win_is_single

order = sorted(range(len(guesses)), key=lambda i: (-singles[i], guesses[i]))
os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT, "w") as f:
    f.write("# singleton feedback patterns per guess, over %d answers (%s)\n"
            % (len(answers), "all words" if FULL else "the 2315 mystery answers"))
    f.write("word,singletons,singletons_nowin,rank\n")
    for r, i in enumerate(order, 1):
        f.write("%s,%d,%d,%d\n" % (guesses[i], singles[i], nowin[i], r))

print("%d guesses x %d answers, %d patterns, %.1fs" %
      (len(guesses), len(answers), NPAT, time.time() - t0))
print("wrote %s\n" % os.path.relpath(OUT, _MATH))
print("%7s %12s %14s %8s" % ("word", "singletons", "singletons_nowin", "rank"))
for r, i in enumerate(order[:TOP], 1):
    print("%7s %12d %14d %8d" % (guesses[i], singles[i], nowin[i], r))
print("...")
for r, i in list(enumerate(order, 1))[-3:]:
    print("%7s %12d %14d %8d" % (guesses[i], singles[i], nowin[i], r))
print("\nmean %.1f, median %d, max %d, min %d over %d guesses"
      % (singles.mean(), int(np.median(singles)), singles.max(), singles.min(), len(guesses)))
