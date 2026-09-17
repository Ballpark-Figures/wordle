"""Rank every guess word by how many of its feedback patterns are SINGLETONS.

A pattern is a singleton for a guess when exactly one answer produces it, so
seeing it identifies the answer outright -- the guess after it is a formality.
This counts them, per guess, over the whole guess list.

    python3 tools/singletons.py            # 12972 guesses vs the 2315 answers
    python3 tools/singletons.py --full     # ... vs all 12972 words as answers
    python3 tools/singletons.py --answers  # rank only the 2315 answer words
    python3 tools/singletons.py --top 50   # longer printed head

--answers RESTRICTS WHICH WORDS ARE RANKED, not what they are counted against.
It drops every guess that is not itself one of the 2315 answers, which is the
same restriction `optturns --guess-list mystery.txt` applies to the solver. The
counts are unchanged -- a word scores what it always scored -- so this is a
filter on the rows, and ranks shift only because the field is smaller. Do not
confuse it with --full, which changes the answer set and therefore the counts.

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
ANSWERS_ONLY = "--answers" in sys.argv
# --word-list is the general form of --answers: restrict WHICH WORDS ARE RANKED
# to a named list, leaving what they are counted against alone.  --answers is
# exactly --word-list mystery, kept under its own name because every committed
# `_answers` file is named by it.
WORD_LIST = None
if "--word-list" in sys.argv:
    WORD_LIST = sys.argv[sys.argv.index("--word-list") + 1]
    if ANSWERS_ONLY:
        raise SystemExit("--answers and --word-list are the same choice; "
                         "pass only one (--answers is --word-list mystery)")
TOP = 25
if "--top" in sys.argv:
    TOP = int(sys.argv[sys.argv.index("--top") + 1])


def _read_list(spec):
    """A word list from a stem in data/shared/words, or from a path."""
    if os.sep in spec or spec.endswith(".txt"):
        with open(spec) as fh:
            return [ln.strip() for ln in fh if ln.strip()]
    return load_words(spec)

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(_MATH, "data", "shared", "singletons")
_NAME = "guess_singletons"
if FULL:
    _NAME += "_full"
if ANSWERS_ONLY:
    _NAME += "_answers"
if WORD_LIST:
    _stem = os.path.basename(WORD_LIST)
    _stem = _stem[:-4] if _stem.endswith(".txt") else _stem
    # the same search --answers already names keeps that name
    _NAME += "_answers" if _stem == "mystery" else "_" + _stem
OUT = os.path.join(OUT_DIR, _NAME + ".csv")

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

keep = range(len(guesses))
if ANSWERS_ONLY or WORD_LIST:
    rank_set = set(load_words("mystery") if ANSWERS_ONLY
                   else _read_list(WORD_LIST))
    missing = rank_set - set(guesses)
    if missing:
        raise SystemExit(
            "%d word(s) in the ranking list are not legal guesses, so they "
            "could never be played: %s"
            % (len(missing), ", ".join(sorted(missing)[:5])))
    keep = [i for i in keep if guesses[i] in rank_set]
order = sorted(keep, key=lambda i: (-singles[i], guesses[i]))
os.makedirs(OUT_DIR, exist_ok=True)
with open(OUT, "w") as f:
    f.write("# singleton feedback patterns per guess, over %d answers (%s)%s\n"
            % (len(answers), "all words" if FULL else "the 2315 mystery answers",
               ("; ranking restricted to answer words" if ANSWERS_ONLY else
                "; ranking restricted to %s" % WORD_LIST if WORD_LIST else "")))
    f.write("word,singletons,singletons_nowin,rank\n")
    for r, i in enumerate(order, 1):
        f.write("%s,%d,%d,%d\n" % (guesses[i], singles[i], nowin[i], r))

print("%d guesses x %d answers, %d patterns, %.1fs%s" %
      (len(guesses), len(answers), NPAT, time.time() - t0,
       "  (ranking %d of %d words)" % (len(order), len(guesses))
       if (ANSWERS_ONLY or WORD_LIST) else ""))
print("wrote %s\n" % os.path.relpath(OUT, _MATH))
print("%7s %12s %14s %8s" % ("word", "singletons", "singletons_nowin", "rank"))
for r, i in enumerate(order[:TOP], 1):
    print("%7s %12d %14d %8d" % (guesses[i], singles[i], nowin[i], r))
print("...")
for r, i in list(enumerate(order, 1))[-3:]:
    print("%7s %12d %14d %8d" % (guesses[i], singles[i], nowin[i], r))
kept = singles[list(order)]
print("\nmean %.1f, median %d, max %d, min %d over %d %s"
      % (kept.mean(), int(np.median(kept)), kept.max(), kept.min(), len(kept),
         "answer words" if ANSWERS_ONLY else
         (WORD_LIST + " words") if WORD_LIST else "guesses"))
