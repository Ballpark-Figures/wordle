"""Enumerate every "Wordle in One" game and break it down by tile composition.

A "Wordle in One" is a feedback ROW that names its answer outright: a guess and
a pattern that exactly ONE answer produces (a SINGLETON). Seeing that row, the
answer is forced, so it can be won in a single guess. This tool lists every such
(guess, answer, pattern) and tallies them by how many GREEN, YELLOW and GRAY
tiles the row has, AND reports what FRACTION of the rows of each composition are
singletons.

    python3 tools/wordle_in_one.py --guesses answers   # the 2315 answer words
    python3 tools/wordle_in_one.py --guesses all       # all 12972 legal guesses

Prefer `bash solver/run-wordle-in-one.sh --guesses ...` (from math/), which tees
a log and names the outputs after the guess set.

THE GUESS SET IS PART OF THE QUESTION AND IS NEVER DEFAULTED. `answers` is the
2315 mystery words (the user's original call: "every singleton produced by every
answer word, not all guesses"); `all` is the 12972 legal guesses. They are
DIFFERENT QUANTITIES over the same answer set, so each gets its own output files
and the two must never share a table. The ANSWER set is always the 2315 mystery
answers, and a pattern is a singleton for a guess when its bucket over those
2315 answers has size exactly one.

THE RATE IS PAIR-WEIGHTED, and that is the user's call (2026-09-08). The
denominator of a (greens, yellows) cell is every (guess, answer) PAIR whose
feedback row has that composition -- so `pct` answers "I played a word and saw
this many greens and yellows: how often is the answer already forced?", with the
answer drawn uniformly from the 2315. It is NOT the fraction of DISTINCT
(guess, pattern) rows of that shape that are singletons, which weights a
2-answer bucket the same as a 300-answer one and is a different number.

THE TWO RANDOM-GUESS COLUMNS ARE THE SAME QUESTION ONE STEP WEAKER. `pct` asks
how often the row FORCES the answer (one candidate left); `pct_rand_answers` and
`pct_rand_guesses` ask how often you would be right if you now guessed at random
from the words the row leaves alive -- the ANSWER words still consistent with it
(a pool of at most 2315), and the LEGAL GUESS words still consistent with it (at
most 12972). A pair whose row leaves n such words contributes 1/n, and the cell
reports the MEAN over its pairs, so both are >= `pct` (a forced answer is 1/1)
and `pct_rand_guesses` <= `pct_rand_answers` (the legal-word pool is a superset,
and contains every consistent answer). "Consistent" is `ultraturns`' notion: a
word the answer could still be. A pick from the WHOLE list, ignoring the row, is
a flat 1/2315 or 1/12972 and is not what these columns report.

  A tidy identity worth knowing: summing 1/n over the n pairs of one bucket gives
  exactly 1, so `pct_rand_answers` is also the count of DISTINCT non-empty
  (guess, pattern) rows of that composition over its pair count.

`avg_answers` and `avg_guesses` ARE THE SAME TWO POOLS COUNTED RATHER THAN
INVERTED: the mean of n, and of m, over the SAME pairs -- how many words the row
leaves alive on average. They are NOT 100/pct_rand_*: the mean of n and the mean
of 1/n are different aggregations of the same distribution (the first is
dominated by the wide buckets, the second by the narrow ones), so a composition
can rank differently under the two and both are reported.

  THE WEIGHTING IS ANSWER-WEIGHTED, matching every other column here (the user's
  call, 2026-09-09): a bucket holding n answers contributes n pairs, so it enters
  the mean n times and `avg_answers` is sum(n^2)/sum(n) over the composition's
  buckets. The other reading -- every DISTINCT (guess, pattern) row counted once,
  giving pairs/rows -- is a different number, and it stays recoverable, since
  `pct_rand_answers` is exactly rows/pairs.

THE ANSWER-POOL COLUMN NEEDS ONLY patterns.npy; THE GUESS-POOL COLUMN NEEDS THE
SQUARE 12972x12972 MATRIX (`python3 build_patterns.py --full`, ~18s/168 MB),
which is gitignored under data/local/ and so is MISSING ON A FRESH CLONE. The
tool refuses with that command rather than dying inside numpy.

THE ALL-GREEN ROW IS A SPECIAL CASE. When the guess is itself the answer the row
is all green, a singleton by the definition above but one that tells you nothing
you did not already know by typing the word. It lands in the (green=5) bin, so it
is visible and separable in the breakdown; the summary reports the totals both
with and without it (matching `singletons` vs `singletons_nowin` in the
guess_singletons CSVs, which this tool's per-guess totals are checked against).
Note its denominator is exactly the 2315 self-pairs, so `pct` there is 100% and
`pct_nowin` is 0% by construction, not by measurement.

CELLS WITH NO SINGLETONS AT ALL ARE STILL PRINTED whenever any pair lands in
them (all-gray rows, say) -- a 0.00% cell is a result about that composition.
A cell absent from the table had no pairs at all: (4 green, 1 yellow) is
impossible, which is why only 238 of the 243 codes ever occur.

Outputs, under data/shared/singletons/:
  wordle_in_one_games[_allguesses].csv[.gz]   one row per game: guess,answer,
                                 pattern,greens,yellows,grays (pattern G/Y/B)
  wordle_in_one_breakdown[_allguesses].csv    per (greens,yellows) composition:
                                 games, games_nowin, pairs, pct, pct_nowin,
                                 pct_rand_answers, pct_rand_guesses,
                                 avg_answers, avg_guesses
The all-guesses games file is gzipped (264778 rows).
A pure function of the committed word lists, so it regenerates anywhere.
"""

import argparse
import gzip
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import all_green, decode, load_words  # noqa: E402

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(_MATH, "data", "shared", "singletons")

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--guesses", choices=("answers", "all"), required=True,
                help="which words may be PLAYED: the 2315 answer words, or all "
                     "12972 legal guesses. Different quantities, separate files.")
args = ap.parse_args()

if args.guesses == "answers":
    GAMES_OUT = os.path.join(OUT_DIR, "wordle_in_one_games.csv")
    BREAK_OUT = os.path.join(OUT_DIR, "wordle_in_one_breakdown.csv")
    REF_OUT = os.path.join(OUT_DIR, "guess_singletons_answers.csv")
    GZIP_GAMES = False
else:
    GAMES_OUT = os.path.join(OUT_DIR, "wordle_in_one_games_allguesses.csv.gz")
    BREAK_OUT = os.path.join(OUT_DIR, "wordle_in_one_breakdown_allguesses.csv")
    REF_OUT = os.path.join(OUT_DIR, "guess_singletons.csv")
    GZIP_GAMES = True

guesses = load_words("guess")
answers = load_words("mystery")
PAT = load_patterns()
if PAT.shape != (len(guesses), len(answers)):
    raise SystemExit("pattern matrix is %s, expected %s -- rebuild with "
                     "build_patterns.py" % (PAT.shape, (len(guesses), len(answers))))
L = len(guesses[0])
NPAT = 3 ** L
WIN = all_green(L)

# The SQUARE guess x guess matrix, for the legal-word random-pick column. It is
# a SEPARATE artifact from the 12972x2315 one every other tool here reads, and
# it lives under the gitignored data/local/, so it is missing on a fresh clone.
try:
    PATF = load_patterns(full=True)
except FileNotFoundError:
    raise SystemExit(
        "the random-guess columns need the SQUARE guess x guess pattern "
        "matrix.\nBuild it with 'python3 build_patterns.py --full' "
        "(about 18s, 168 MB).")
if PATF.shape != (len(guesses), len(guesses)):
    raise SystemExit("patterns_full.npy is %s, not %d x %d -- rebuild it"
                     % (PATF.shape, len(guesses), len(guesses)))

# For each of the 243 codes, its (greens, yellows, grays) counts. tile 2=green,
# 1=yellow, 0=gray in the base-3 encoding (see wordle.decode).
comp = np.zeros((NPAT, 3), dtype=np.int64)   # columns: greens, yellows, grays
for code in range(NPAT):
    tiles = decode(code, L)
    comp[code, 0] = sum(t == 2 for t in tiles)
    comp[code, 1] = sum(t == 1 for t in tiles)
    comp[code, 2] = sum(t == 0 for t in tiles)

_TILE = {2: "G", 1: "Y", 0: "B"}


def pat_str(code):
    return "".join(_TILE[t] for t in decode(code, L))


answer_set = set(answers)
if args.guesses == "answers":
    guess_idx = [i for i, g in enumerate(guesses) if g in answer_set]
else:
    guess_idx = list(range(len(guesses)))

# tally[(g, y)] -> count of singleton games with g greens, y yellows (grays=L-g-y)
tally = np.zeros((L + 1, L + 1), dtype=np.int64)
tally_nowin = np.zeros((L + 1, L + 1), dtype=np.int64)
code_pairs = np.zeros(NPAT, dtype=np.int64)   # (guess, answer) pairs per pattern
# Sum of 1/(words the row leaves alive) over the pairs in each pattern, once for
# the answer pool and once for the legal-guess pool.
rand_ans_code = np.zeros(NPAT, dtype=np.float64)
rand_gss_code = np.zeros(NPAT, dtype=np.float64)
# Sum of (words the row leaves alive) over those same pairs -- the numerator of
# the answer-weighted mean, so a bucket of n answers contributes n * n and n * m.
sum_ans_code = np.zeros(NPAT, dtype=np.int64)
sum_gss_code = np.zeros(NPAT, dtype=np.int64)
per_guess = {}          # guess word -> singleton count (for the gate)
games = []              # (guess, answer, pattern_code)

gidx = {w: i for i, w in enumerate(guesses)}
ans_cols = np.array([gidx[a] for a in answers], dtype=np.int64)

for gi in guess_idx:
    row = np.asarray(PAT[gi], dtype=np.int64)            # pattern per answer
    counts = np.bincount(row, minlength=NPAT)
    code_pairs += counts                                 # the DENOMINATOR
    # the same row over all 12972 legal words. GATE: restricted to the answer
    # columns it must BE the 12972x2315 matrix's row -- that pins both the
    # column order and the two matrices agreeing, and it is what makes the
    # legal-word bucket a superset of the answer bucket.
    row_full = np.asarray(PATF[gi], dtype=np.int64)
    if not np.array_equal(row_full[ans_cols], row):
        raise SystemExit("GATE FAILED: patterns_full.npy disagrees with "
                         "patterns.npy on the row for %s" % guesses[gi])
    counts_full = np.bincount(row_full, minlength=NPAT)
    nz = counts > 0
    # summing 1/n over the n pairs of a bucket gives exactly 1 for the answer
    # pool, and n/m for the legal-word pool (m >= n by the gate above)
    rand_ans_code[nz] += 1.0
    rand_gss_code[nz] += counts[nz] / counts_full[nz]
    sum_ans_code[nz] += counts[nz] * counts[nz]
    sum_gss_code[nz] += counts[nz] * counts_full[nz]
    is_single = counts[row] == 1                         # boolean over answers
    ai = np.nonzero(is_single)[0]
    per_guess[guesses[gi]] = len(ai)
    for a in ai:
        code = int(row[a])
        games.append((guesses[gi], answers[a], code))
        g, y = comp[code, 0], comp[code, 1]
        tally[g, y] += 1
        if code != WIN:
            tally_nowin[g, y] += 1

# every (guess, answer) pair of this run, bucketed by tile composition
pairs = np.zeros((L + 1, L + 1), dtype=np.int64)
np.add.at(pairs, (comp[:, 0], comp[:, 1]), code_pairs)
assert int(pairs.sum()) == len(guess_idx) * len(answers)

rand_ans = np.zeros((L + 1, L + 1), dtype=np.float64)
rand_gss = np.zeros((L + 1, L + 1), dtype=np.float64)
np.add.at(rand_ans, (comp[:, 0], comp[:, 1]), rand_ans_code)
np.add.at(rand_gss, (comp[:, 0], comp[:, 1]), rand_gss_code)

sum_ans = np.zeros((L + 1, L + 1), dtype=np.int64)
sum_gss = np.zeros((L + 1, L + 1), dtype=np.int64)
np.add.at(sum_ans, (comp[:, 0], comp[:, 1]), sum_ans_code)
np.add.at(sum_gss, (comp[:, 0], comp[:, 1]), sum_gss_code)
# every pair leaves at least the answer itself alive, and the legal-word pool is
# a superset of the answer pool bucket by bucket (the gate above pins that)
assert (sum_ans >= pairs).all(), "a cell averaged under one answer alive"
assert (sum_gss >= sum_ans).all(), "the legal-word pool was smaller than the answers"
# a forced answer is a pick of 1 from 1, and the legal-word pool contains every
# consistent answer, so these orderings hold cell by cell
assert (rand_ans >= tally - 1e-9).all(), "random-pick rate below the singleton rate"
assert (rand_gss <= rand_ans + 1e-9).all(), "legal-word pool beat the answer pool"
assert (rand_ans <= pairs + 1e-9).all(), "a random-pick rate exceeded 100%"

total = int(tally.sum())
total_nowin = int(tally_nowin.sum())
total_pairs = int(pairs.sum())
total_rand_ans = float(rand_ans.sum())
total_rand_gss = float(rand_gss.sum())
total_sum_ans = int(sum_ans.sum())
total_sum_gss = int(sum_gss.sum())


def pct(num, den):
    return 100.0 * num / den if den else 0.0


def avg(num, den):
    return num / den if den else 0.0


# --- GATE: per-guess totals must match the committed guess_singletons CSV
if os.path.exists(REF_OUT):
    ref = {}
    with open(REF_OUT) as f:
        for line in f:
            if line.startswith("#") or line.startswith("word,"):
                continue
            w, singles, nowin, _rank = line.strip().split(",")
            ref[w] = (int(singles), int(nowin))
    bad = [w for w in per_guess if w in ref and per_guess[w] != ref[w][0]]
    if bad:
        raise SystemExit("GATE FAILED: per-guess singleton counts disagree with "
                         "%s for %d words, e.g. %s"
                         % (os.path.basename(REF_OUT), len(bad), bad[:5]))
    ref_nowin_total = sum(v[1] for w, v in ref.items() if w in per_guess)
    if ref_nowin_total != total_nowin:
        raise SystemExit("GATE FAILED: no-win total %d != committed sum %d"
                         % (total_nowin, ref_nowin_total))
    print("gate OK: per-guess totals match %s (%d words, %d no-win games)"
          % (os.path.basename(REF_OUT), len(per_guess), total_nowin))
else:
    print("gate SKIPPED: %s not found" % REF_OUT)

os.makedirs(OUT_DIR, exist_ok=True)
games.sort()
_open = gzip.open if GZIP_GAMES else open
with _open(GAMES_OUT, "wt") as f:
    f.write("# every Wordle-in-One game: guess is one of the %d %s words, "
            "answer is the unique one giving that feedback row over the 2315 "
            "mystery answers\n"
            % (len(guess_idx),
               "answer" if args.guesses == "answers" else "legal guess"))
    f.write("guess,answer,pattern,greens,yellows,grays\n")
    for g, a, code in games:
        f.write("%s,%s,%s,%d,%d,%d\n"
                % (g, a, pat_str(code), comp[code, 0], comp[code, 1], comp[code, 2]))

with open(BREAK_OUT, "w") as f:
    f.write("# Wordle-in-One games by tile composition (grays = %d - greens - "
            "yellows), guess set = %d %s words, answers = the 2315 mystery "
            "answers\n"
            % (L, len(guess_idx),
               "answer" if args.guesses == "answers" else "legal guess"))
    f.write("# games=all singletons, games_nowin excludes the all-green "
            "self-answer; pairs=every (guess, answer) pair whose row has this "
            "composition; pct=100*games/pairs, pct_nowin=100*games_nowin/pairs\n")
    f.write("# pct_rand_answers/pct_rand_guesses=mean over those pairs of "
            "1/(words the row leaves consistent), drawing from the 2315 answers "
            "and from the 12972 legal guesses respectively -- how often a random "
            "pick from what is still alive would be right\n")
    f.write("# avg_answers/avg_guesses=mean over those same pairs of the NUMBER "
            "of words the row leaves consistent, from the 2315 answers and from "
            "the 12972 legal guesses -- the same two pools counted rather than "
            "inverted, so these are NOT 100/pct_rand_*\n")
    f.write("greens,yellows,grays,games,games_nowin,pairs,pct,pct_nowin,"
            "pct_rand_answers,pct_rand_guesses,avg_answers,avg_guesses\n")
    for g in range(L + 1):
        for y in range(L + 1 - g):
            if not (tally[g, y] or pairs[g, y]):
                continue
            f.write("%d,%d,%d,%d,%d,%d,%.5f,%.5f,%.5f,%.5f,%.5f,%.5f\n"
                    % (g, y, L - g - y, tally[g, y], tally_nowin[g, y],
                       pairs[g, y], pct(tally[g, y], pairs[g, y]),
                       pct(tally_nowin[g, y], pairs[g, y]),
                       pct(rand_ans[g, y], pairs[g, y]),
                       pct(rand_gss[g, y], pairs[g, y]),
                       avg(sum_ans[g, y], pairs[g, y]),
                       avg(sum_gss[g, y], pairs[g, y])))

print("wrote %s (%d games)" % (os.path.relpath(GAMES_OUT, _MATH), total))
print("wrote %s" % os.path.relpath(BREAK_OUT, _MATH))
print("\nguess set: %d %s words; answers: %d; pairs: %d"
      % (len(guess_idx), "answer" if args.guesses == "answers" else "legal guess",
         len(answers), total_pairs))
print("%d games total (%.4f%% of all pairs); %d excluding the all-green "
      "self-answer (%.4f%%)"
      % (total, pct(total, total_pairs), total_nowin,
         pct(total_nowin, total_pairs)))
print("a random pick from what the row leaves alive is right %.4f%% of the time "
      "(answer pool) / %.4f%% (legal-guess pool)"
      % (pct(total_rand_ans, total_pairs), pct(total_rand_gss, total_pairs)))
print("a row leaves %.2f answer words alive on average / %.2f legal guess words\n"
      % (avg(total_sum_ans, total_pairs), avg(total_sum_gss, total_pairs)))

# printed breakdown
print("singleton RATE by (greens, yellows, grays), the rate a RANDOM pick from "
      "what the row leaves alive is right, and how many words that is:")
print("%6s %7s %6s %10s %12s %12s %9s %10s %11s %11s %10s %11s"
      % ("green", "yellow", "gray", "games", "games_nowin", "pairs", "pct",
         "pct_nowin", "rand_ans", "rand_guess", "avg_ans", "avg_guess"))
for g in range(L + 1):
    for y in range(L + 1 - g):
        if not (tally[g, y] or pairs[g, y]):
            continue
        print("%6d %7d %6d %10d %12d %12d %8.4f%% %9.4f%% %10.4f%% %10.4f%% "
              "%10.2f %11.2f"
              % (g, y, L - g - y, tally[g, y], tally_nowin[g, y], pairs[g, y],
                 pct(tally[g, y], pairs[g, y]),
                 pct(tally_nowin[g, y], pairs[g, y]),
                 pct(rand_ans[g, y], pairs[g, y]),
                 pct(rand_gss[g, y], pairs[g, y]),
                 avg(sum_ans[g, y], pairs[g, y]),
                 avg(sum_gss[g, y], pairs[g, y])))

# the same cells again, ordered by how many answer words the row leaves alive --
# the sort the table above cannot show, since it is laid out by composition
print("\nby avg_answers (fewest words left first):")
print("%6s %7s %6s %12s %9s %11s %10s %11s"
      % ("green", "yellow", "gray", "pairs", "pct", "rand_ans", "avg_ans",
         "avg_guess"))
cells = [(g, y) for g in range(L + 1) for y in range(L + 1 - g)
         if tally[g, y] or pairs[g, y]]
for g, y in sorted(cells, key=lambda c: avg(sum_ans[c], pairs[c])):
    print("%6d %7d %6d %12d %8.4f%% %10.4f%% %10.2f %11.2f"
          % (g, y, L - g - y, pairs[g, y], pct(tally[g, y], pairs[g, y]),
             pct(rand_ans[g, y], pairs[g, y]),
             avg(sum_ans[g, y], pairs[g, y]), avg(sum_gss[g, y], pairs[g, y])))


def marginal(label, k, won, pr, ra, rg, sa, sg):
    print("  %d %s: %8d games / %10d pairs = %7.4f%%   rand %7.4f%% / %7.4f%%"
          "   avg %8.2f / %8.2f"
          % (k, label, won, pr, pct(won, pr), pct(ra, pr), pct(rg, pr),
             avg(sa, pr), avg(sg, pr)))


print("\nmarginal by greens (rand and avg = answer pool / legal-guess pool):")
for g in range(L + 1):
    if int(pairs[g].sum()):
        marginal("green", g, int(tally[g].sum()), int(pairs[g].sum()),
                 float(rand_ans[g].sum()), float(rand_gss[g].sum()),
                 int(sum_ans[g].sum()), int(sum_gss[g].sum()))
print("marginal by yellows:")
for y in range(L + 1):
    if int(pairs[:, y].sum()):
        marginal("yellow", y, int(tally[:, y].sum()), int(pairs[:, y].sum()),
                 float(rand_ans[:, y].sum()), float(rand_gss[:, y].sum()),
                 int(sum_ans[:, y].sum()), int(sum_gss[:, y].sum()))
print("marginal by grays:")
gray_games = np.zeros(L + 1, dtype=np.int64)
gray_pairs = np.zeros(L + 1, dtype=np.int64)
gray_ra = np.zeros(L + 1, dtype=np.float64)
gray_rg = np.zeros(L + 1, dtype=np.float64)
gray_sa = np.zeros(L + 1, dtype=np.int64)
gray_sg = np.zeros(L + 1, dtype=np.int64)
for g in range(L + 1):
    for y in range(L + 1 - g):
        gray_games[L - g - y] += tally[g, y]
        gray_pairs[L - g - y] += pairs[g, y]
        gray_ra[L - g - y] += rand_ans[g, y]
        gray_rg[L - g - y] += rand_gss[g, y]
        gray_sa[L - g - y] += sum_ans[g, y]
        gray_sg[L - g - y] += sum_gss[g, y]
for k in range(L + 1):
    if gray_pairs[k]:
        marginal("gray", k, int(gray_games[k]), int(gray_pairs[k]),
                 float(gray_ra[k]), float(gray_rg[k]),
                 int(gray_sa[k]), int(gray_sg[k]))
