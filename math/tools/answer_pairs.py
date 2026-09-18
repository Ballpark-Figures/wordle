"""Rank PAIRS OF ANSWERS by how few words can tell them apart.

Run it through the wrapper, which sets --out, names the run and tees a log:

    bash solver/run-answer-pairs.sh                     # from math/, or anywhere
    bash solver/run-answer-pairs.sh --splitters guess
    bash solver/run-answer-pairs.sh --top 100000

WHAT THIS COMPUTES, precisely.  For every unordered pair of words from the PAIR
list, count the words in the SPLITTER pool that SEPARATE them -- that is, the
`g` for which `pattern(g, a) != pattern(g, b)`.  Rank ASCENDING, fewest
splitters first, so the head of the file is the pairs the follow-up is least
able to distinguish.

IT IS THE INVERSE OF EVERY OTHER RANKING HERE, and that is the point.  The rest
of this repo scores a GUESS by what it does to the answer set; this scores a
PAIR OF ANSWERS by how much of the pool can resolve it.  So a row is a property
of two answers, not of an opener, and it belongs in no table with a singleton
count, an ssq, a max bucket or an optturns total.

WHY THE QUANTITY MATTERS FOR THE GUARANTEE (`math/guarantee.py`).  An answer is
UNSOLVED exactly when some live pool word fails to fully split it -- so a pair
with very few splitters is the raw material a fatal bucket is made of: once two
such answers share a bucket, almost nothing the follow-up can draw will separate
them, and the game comes down to a coin flip.  This ranking says which pairs
those are BEFORE any opening is chosen, which no opener-side screen can do.

THE FLOOR IS 2 WHENEVER BOTH WORDS ARE IN THE POOL, and it is not a convention
-- it is forced.  A word's reply against itself is all-green and against any
other word is not, so `a` splits (a, b) and so does `b`.  `custom.txt` contains
every answer, so under the default pools no pair can score below 2, and the gate
CHECKS that over every pair rather than asserting it.  A pair AT 2 is separated
by nothing except naming one of the two outright.

TWO LISTS, TWO ROLES, and NEITHER IS DEFAULTED HERE (the greens scar -- the
WRAPPER carries defaults a human reads and forwards them explicitly):

  --pairs LIST       which words the PAIRS are drawn from.  Must be answers:
                     they are COLUMNS of the pattern matrix, so this list has to
                     be a subset of the 2315.  C(2315, 2) = 2678455 pairs.
  --splitters LIST   which words may separate a pair.  Must be legal guesses
                     (matrix ROWS).  `custom` is the 4282-word pool the
                     random-compatible follow-up draws from, which is why it is
                     the wrapper's default; `guess` asks the same question of a
                     player who knows all 12972.

Both are in the filename, because they are two different questions.

NO NEW MATRIX IS NEEDED and that is worth knowing: the splitters are a subset of
the 12972 ROWS and the pair words a subset of the 2315 COLUMNS, so this is a
sub-block of the DEFAULT `patterns.npy`.  It does not want `--full`.

Nothing searches and nothing samples: the result is a pure function of the
committed word lists and the pattern matrix, so it is exact, there is no seed
and no standard error, and a re-run reproduces the file byte for byte.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                      # noqa: E402
from opening_list import resolve_word_set                     # noqa: E402
from wordle import load_words, pattern                        # noqa: E402

COLUMNS = "word1,word2,splitters"
GATE_SAMPLE = 200          # pairs recomputed FROM THE STRINGS by the gate


def need(argv, flag):
    if flag not in argv:
        raise SystemExit(
            "%s LIST is REQUIRED -- it is part of the question, so this refuses "
            "to pick for you.  Use solver/run-answer-pairs.sh, which carries a "
            "default a human reads." % flag)
    return argv[argv.index(flag) + 1]


def split_counts(block):
    """Splitters per pair, as a full (n, n) matrix of counts.

    `block` is (splitters x pairwords) of pattern codes.  Column i against
    column j differ in exactly the rows whose word separates the two, so the
    count is one comparison down the column -- no bucketing and no enumeration
    of patterns anywhere.  Done one column at a time: the (n, n, m) broadcast
    would be 23 GB at the real sizes, and this is 2315 passes of 10 MB.
    """
    n = block.shape[1]
    out = np.empty((n, n), dtype=np.int32)
    for i in range(n):
        out[i] = (block != block[:, i:i + 1]).sum(axis=0, dtype=np.int32)
    return out


def gate_strings(counts, pairwords, splitters, rng):
    """Recompute sampled pairs FROM THE STRINGS and demand exact agreement.

    Shares no machinery with the matrix path -- `wordle.pattern` rebuilds each
    reply from the two words -- so this pins the matrix, both index maps and the
    column-comparison trick in one check.
    """
    n = len(pairwords)
    for _ in range(GATE_SAMPLE):
        i, j = rng.integers(n), rng.integers(n)
        if i == j:
            continue
        a, b = pairwords[i], pairwords[j]
        want = sum(1 for g in splitters if pattern(g, a) != pattern(g, b))
        if want != counts[i, j]:
            raise SystemExit("GATE FAILED: %s/%s split by %d words from the "
                             "strings, %d from the matrix"
                             % (a, b, want, counts[i, j]))
        if counts[i, j] != counts[j, i]:
            raise SystemExit("GATE FAILED: %s/%s is not symmetric (%d vs %d)"
                             % (a, b, counts[i, j], counts[j, i]))
    print("gate: %d pairs recomputed from the strings, exact and symmetric"
          % GATE_SAMPLE)


def gate_floor(counts, pairwords, splitters):
    """Every pair of pool words must score at least 2, over ALL pairs.

    Forced, not conventional: a word replies all-green to itself and never to a
    different word, so each of the two splits the pair.  Checked exhaustively
    because it is free -- and it is the one property that would catch an index
    map pointing at the wrong list, which a sampled string check can miss.
    """
    inpool = np.array([w in set(splitters) for w in pairwords])
    both = np.outer(inpool, inpool)
    np.fill_diagonal(both, False)
    if not both.any():
        print("gate: no pair has both words in the splitter pool, floor not checked")
        return
    lo = int(counts[both].min())
    if lo < 2:
        raise SystemExit("GATE FAILED: a pair of pool words is split by only %d "
                         "word(s); the floor is 2 (each splits itself)" % lo)
    print("gate: every pair of pool words is split by at least 2 (min %d)" % lo)


def main(argv):
    pairs_name = need(argv, "--pairs")
    split_name = need(argv, "--splitters")
    if "--out" not in argv and "--no-out" not in argv:
        raise SystemExit("--out PATH is REQUIRED (or an explicit --no-out).  A "
                         "run that prints its answer and saves nothing is how a "
                         "result gets lost; use solver/run-answer-pairs.sh.")
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 0
    show = int(argv[argv.index("--show") + 1]) if "--show" in argv else 20

    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    apos = {w: i for i, w in enumerate(answers)}

    # SORTED, so the tie-break below is alphabetical by construction rather than
    # by whatever order the list file happened to be in.
    pairwords = sorted(resolve_word_set(pairs_name))
    splitters = sorted(resolve_word_set(split_name))

    bad = [w for w in pairwords if w not in apos]
    if bad:
        raise SystemExit(
            "--pairs %s has %d word(s) that are not ANSWERS: %s\n"
            "  the pair words are COLUMNS of the pattern matrix, so the list "
            "must be a subset of the 2315." % (pairs_name, len(bad),
                                               ", ".join(bad[:5])))
    bad = [w for w in splitters if w not in gpos]
    if bad:
        raise SystemExit(
            "--splitters %s has %d word(s) that are not legal guesses: %s\n"
            "  a word that cannot be played cannot split anything."
            % (split_name, len(bad), ", ".join(bad[:5])))

    npair = len(pairwords)
    total = npair * (npair - 1) // 2
    print("answer pairs: %d words from %s -> %d pairs, split by %d words from %s"
          % (npair, pairs_name, total, len(splitters), split_name))

    pat = load_patterns()
    if pat.shape != (len(guesses), len(answers)):
        raise SystemExit("pattern matrix is %s, expected %s -- rebuild with "
                         "python3 build_patterns.py"
                         % (pat.shape, (len(guesses), len(answers))))
    block = np.ascontiguousarray(
        pat[np.array([gpos[w] for w in splitters])][:,
            np.array([apos[w] for w in pairwords])])

    t0 = time.time()
    counts = split_counts(block)
    print("  counted in %.1fs" % (time.time() - t0))

    gate_floor(counts, pairwords, splitters)
    gate_strings(counts, pairwords, splitters, np.random.default_rng(0))

    iu = np.triu_indices(npair, k=1)
    flat = counts[iu]
    # ASCENDING splitters, then alphabetical -- `iu` is already row-major over a
    # sorted list, so a STABLE sort on the count alone leaves ties in
    # (word1, word2) order and no second key is needed.
    order = np.argsort(flat, kind="stable")
    keep = total if top <= 0 else min(top, total)

    print("\n  the %d pairs fewest words can separate:" % show)
    for r in order[:show]:
        print("    %-7s %-7s  %d" % (pairwords[iu[0][r]], pairwords[iu[1][r]],
                                     flat[r]))
    lo, hi = int(flat.min()), int(flat.max())
    print("\n  splitters per pair: min %d, median %d, max %d (of %d)"
          % (lo, int(np.median(flat)), hi, len(splitters)))
    at_floor = int((flat == lo).sum())
    print("  %d pair(s) at the minimum" % at_floor)

    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        t1 = time.time()
        with open(out, "w") as fh:
            fh.write("# pairs of answers ranked by how FEW words split them\n")
            fh.write("# settings pairs=%s splitters=%s npairs=%d nsplitters=%d\n"
                     % (pairs_name, split_name, total, len(splitters)))
            fh.write(COLUMNS + "\n")
            w1, w2 = iu[0][order[:keep]], iu[1][order[:keep]]
            vals = flat[order[:keep]]
            fh.writelines("%s,%s,%d\n" % (pairwords[a], pairwords[b], v)
                          for a, b, v in zip(w1, w2, vals))
        # The sidecar says what the file COVERS, exactly as the singletons runs
        # do: a capped head and a complete ranking look identical from inside.
        with open(out + ".meta", "w") as fh:
            fh.write("pairs=%s\nsplitters=%s\nscored=%d\nwritten=%d\ncomplete=%d\n"
                     % (pairs_name, split_name, total, keep,
                        1 if keep == total else 0))
        print("\nwrote %d rows to %s in %.1fs%s"
              % (keep, out, time.time() - t1,
                 "" if keep == total else "  (TRUNCATED -- the head only)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
