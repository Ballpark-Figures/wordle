"""Rank openers by the SIZE OF THE LARGEST BUCKET their feedback produces.

Run it through the wrapper, which sets --out, names the run and tees a log:

    bash solver/run-maxbucket.sh                                # from math/, or anywhere
    bash solver/run-maxbucket.sh --answer-set all
    bash solver/run-maxbucket.sh --rank answers --top 50

WHAT THIS COMPUTES, precisely.  A guess PARTITIONS the answer set: two answers
land in the same part iff they give that guess the same feedback.  This reports,
per guess, the size of the BIGGEST part -- the worst case, the number of answers
still alive after the unluckiest possible reply -- and ranks ascending, smallest
worst case first.

IT IS THE MINIMAX CRITERION, AND IT IS A DIFFERENT QUANTITY FROM EVERY OTHER
RANKING IN THIS REPO.  It is not the EXPECTED number of answers left (that is a
mean over the parts, weighted by their own sizes, and it ranks differently -- the
mean of n and the max of n are different aggregations of one partition); it is
not the singleton count of `tools/singletons.py`, which looks only at the parts of
size ONE while this looks only at the largest; and it is emphatically not an
`optturns`-family total, which is a minimum number of GUESSES subject to a
6-guess guarantee.  A worst-case bucket size says nothing about how the rest of
the game goes.  Never put a number from here in a table with any of those.

THE ANSWER SET IS PART OF THE QUESTION, not a detail -- a bucket is counted over
whichever answers exist, so `--answer-set mystery` (the 2315 curated answers) and
`--answer-set all` (every one of the 12972 legal words an answer) are answers to
different questions and get different files.  `--rank` is a separate axis: it
restricts which words appear as ROWS, exactly as `singletons.py --answers` does,
and changes no count -- a word scores what it always scored, and ranks move only
because the field is smaller.  Neither flag is defaulted here; the WRAPPER
carries a default a human reads and forwards it explicitly.

THE ALL-GREEN BUCKET CANNOT BE THE LARGEST, so nothing turns on excluding it: it
holds exactly the answers equal to the guess, so its size is 1 when the guess is
itself an answer and 0 otherwise, against maxima in the hundreds.  This is why
there is no `_nowin` column here of the kind `singletons.py` needs.

TIES ARE REAL -- the quantity is an integer and the field is large, so many words
share a value.  The RANKING is on `max_bucket` alone; ties are broken
alphabetically purely to make the file deterministic, and that order carries NO
meaning.  `buckets`, `max_pattern` and `max_ties` are DESCRIPTIVE columns, not
secondary keys: `max_pattern` is the LOWEST-CODED pattern attaining the maximum
and `max_ties` says how many patterns attain it, so a row whose `max_ties` is 1
names its worst reply outright.

THE ABSURDLE CONNECTION, which is where the built-in gate comes from.  Absurdle's
host answers with the pattern of the LARGEST bucket, so `max_bucket` is exactly
the number of candidates an opener leaves against that host -- and the minimum of
this ranking is the figure `data/shared/absurdle/one_shortest_solution.txt`
already records for its witness.  The gate below re-derives that file rather than
trusting this code.  (The Absurdle RESULT carries its own caveats about whose word
lists those are; nothing here depends on them, since this is a statement about
OUR lists either way.)

Nothing searches or samples: the whole thing is a pure function of the committed
word lists and the pattern matrix, so it is exact and a re-run reproduces its file
byte for byte.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from absurdle import bucket_counts, show  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from wordle import load_words, pattern  # noqa: E402

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ABSURDLE_WITNESS = os.path.join(_MATH, "data", "shared", "absurdle",
                                "one_shortest_solution.txt")
GATE_SAMPLE = 12          # guesses re-bucketed from the STRINGS by the gate


def _arg(argv, flag, choices):
    if flag not in argv:
        raise SystemExit("%s is REQUIRED (one of %s) -- it is part of the "
                         "question, so this refuses to pick for you. Use "
                         "solver/run-maxbucket.sh, which carries a default a "
                         "human reads." % (flag, "/".join(choices)))
    val = argv[argv.index(flag) + 1]
    if val not in choices:
        raise SystemExit("%s must be one of %s" % (flag, "/".join(choices)))
    return val


def gate_strings(guesses, answers, counts, rng):
    """Re-bucket sampled guesses FROM THE STRINGS and demand exact agreement.

    Shares no machinery with the matrix path: `wordle.pattern` recomputes each
    feedback from the two words, and the buckets are counted in a dict. This is
    what pins the matrix, its column order and the argmax bookkeeping.
    """
    for g in rng.choice(len(guesses), size=GATE_SAMPLE, replace=False):
        hist = {}
        for a in answers:
            code = pattern(guesses[g], a)
            hist[code] = hist.get(code, 0) + 1
        mx = max(hist.values())
        want_pat = min(c for c, n in hist.items() if n == mx)
        if mx != counts[g].max():
            raise SystemExit("GATE FAILED: %s largest bucket %d from the "
                             "strings, %d from the matrix"
                             % (guesses[g], mx, counts[g].max()))
        if len(hist) != int((counts[g] > 0).sum()):
            raise SystemExit("GATE FAILED: %s has %d non-empty buckets from "
                             "the strings, %d from the matrix"
                             % (guesses[g], len(hist), (counts[g] > 0).sum()))
        if want_pat != int(counts[g].argmax()):
            raise SystemExit("GATE FAILED: %s worst pattern %d from the "
                             "strings, %d from the matrix"
                             % (guesses[g], want_pat, counts[g].argmax()))
    print("gate: %d guesses re-bucketed from the strings, exact" % GATE_SAMPLE)


def gate_absurdle(guesses, mx):
    """Cross-check the minimum against the committed Absurdle witness.

    That file's first line is the opener of a shortest winning sequence, found
    in ascending resulting-size order -- so its opener is a MINIMISER of this
    very quantity and its "N left" is this ranking's minimum. Read from the
    committed file, never typed in here.
    """
    if not os.path.exists(ABSURDLE_WITNESS):
        print("gate: %s absent, minimum not cross-checked"
              % os.path.relpath(ABSURDLE_WITNESS, _MATH))
        return
    word = left = None
    for line in open(ABSURDLE_WITNESS):
        parts = line.split()
        if line.startswith("#") or len(parts) < 4 or parts[-1] != "left":
            continue
        word, left = parts[0], int(parts[-2])
        break
    if word is None:
        raise SystemExit("GATE FAILED: no transcript line in %s" % ABSURDLE_WITNESS)
    i = guesses.index(word)
    if mx[i] != left:
        raise SystemExit("GATE FAILED: %s leaves %d here, %d in the committed "
                         "Absurdle witness" % (word, mx[i], left))
    if mx.min() != left:
        raise SystemExit("GATE FAILED: minimum is %d, but the committed "
                         "Absurdle witness opens on a %d" % (mx.min(), left))
    print("gate: minimum %d agrees with the committed Absurdle witness (%s)"
          % (left, word))


def main(argv):
    answer_set = _arg(argv, "--answer-set", ("mystery", "all"))
    rank = _arg(argv, "--rank", ("all", "answers"))
    if "--out" not in argv and "--no-out" not in argv:
        raise SystemExit("--out PATH is REQUIRED (or an explicit --no-out). A "
                         "run that prints its answer and saves nothing is how a "
                         "result gets lost; use solver/run-maxbucket.sh.")
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 25

    full = answer_set == "all"
    guesses = load_words("guess")
    answers = guesses if full else load_words("mystery")
    pat = load_patterns(full=full)
    if pat.shape != (len(guesses), len(answers)):
        raise SystemExit("pattern matrix is %s, expected %s -- rebuild with "
                         "build_patterns.py%s"
                         % (pat.shape, (len(guesses), len(answers)),
                            " --full" if full else ""))

    t0 = time.time()
    counts = bucket_counts(pat, np.arange(len(answers)))
    mx = counts.max(axis=1)
    worst = counts.argmax(axis=1)                       # lowest code attaining it
    ties = (counts == mx[:, None]).sum(axis=1)
    buckets = (counts > 0).sum(axis=1)
    print("%d guesses x %d answers, %.1fs" % (len(guesses), len(answers),
                                              time.time() - t0))

    gate_strings(guesses, answers, counts, np.random.default_rng(0))
    if not full:
        gate_absurdle(guesses, mx)

    keep = range(len(guesses))
    if rank == "answers":
        answer_set_words = set(load_words("mystery"))
        keep = [i for i in keep if guesses[i] in answer_set_words]
    order = sorted(keep, key=lambda i: (mx[i], guesses[i]))

    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w") as f:
            f.write("# largest feedback bucket per opener, over %d answers "
                    "(%s); ranking %s\n"
                    % (len(answers),
                       "all 12972 legal words" if full else "the 2315 mystery answers",
                       "the 2315 answer words" if rank == "answers"
                       else "all %d legal guesses" % len(guesses)))
            f.write("# ranked ASCENDING by max_bucket; ties broken "
                    "alphabetically and that order carries no meaning.\n")
            f.write("word,max_bucket,max_pattern,max_ties,buckets,rank\n")
            for r, i in enumerate(order, 1):
                f.write("%s,%d,%s,%d,%d,%d\n"
                        % (guesses[i], mx[i], show(int(worst[i])), ties[i],
                           buckets[i], r))
        print("wrote %s" % os.path.relpath(out, _MATH))

    print("\n%7s %11s %12s %10s %8s %6s"
          % ("word", "max_bucket", "max_pattern", "max_ties", "buckets", "rank"))
    for r, i in enumerate(order[:top], 1):
        print("%7s %11d %12s %10d %8d %6d"
              % (guesses[i], mx[i], show(int(worst[i])), ties[i], buckets[i], r))
    print("...")
    for r, i in list(enumerate(order, 1))[-3:]:
        print("%7s %11d %12s %10d %8d %6d"
              % (guesses[i], mx[i], show(int(worst[i])), ties[i], buckets[i], r))
    kept = mx[list(order)]
    print("\nmin %d, median %d, mean %.1f, max %d over %d %s"
          % (kept.min(), int(np.median(kept)), kept.mean(), kept.max(), len(kept),
             "answer words" if rank == "answers" else "guesses"))
    print("%d word(s) tie for the minimum: %s"
          % ((kept == kept.min()).sum(),
             " ".join(guesses[i] for i in order if mx[i] == kept.min())[:200]))


if __name__ == "__main__":
    main(sys.argv[1:])
