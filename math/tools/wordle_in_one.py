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
                                 games, games_nowin, pairs, pct, pct_nowin
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
per_guess = {}          # guess word -> singleton count (for the gate)
games = []              # (guess, answer, pattern_code)

for gi in guess_idx:
    row = np.asarray(PAT[gi], dtype=np.int64)            # pattern per answer
    counts = np.bincount(row, minlength=NPAT)
    code_pairs += counts                                 # the DENOMINATOR
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

total = int(tally.sum())
total_nowin = int(tally_nowin.sum())
total_pairs = int(pairs.sum())


def pct(num, den):
    return 100.0 * num / den if den else 0.0


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
    f.write("greens,yellows,grays,games,games_nowin,pairs,pct,pct_nowin\n")
    for g in range(L + 1):
        for y in range(L + 1 - g):
            if not (tally[g, y] or pairs[g, y]):
                continue
            f.write("%d,%d,%d,%d,%d,%d,%.5f,%.5f\n"
                    % (g, y, L - g - y, tally[g, y], tally_nowin[g, y],
                       pairs[g, y], pct(tally[g, y], pairs[g, y]),
                       pct(tally_nowin[g, y], pairs[g, y])))

print("wrote %s (%d games)" % (os.path.relpath(GAMES_OUT, _MATH), total))
print("wrote %s" % os.path.relpath(BREAK_OUT, _MATH))
print("\nguess set: %d %s words; answers: %d; pairs: %d"
      % (len(guess_idx), "answer" if args.guesses == "answers" else "legal guess",
         len(answers), total_pairs))
print("%d games total (%.4f%% of all pairs); %d excluding the all-green "
      "self-answer (%.4f%%)\n"
      % (total, pct(total, total_pairs), total_nowin,
         pct(total_nowin, total_pairs)))

# printed breakdown
print("singleton RATE by (greens, yellows, grays):")
print("%6s %7s %6s %10s %12s %12s %9s %10s"
      % ("green", "yellow", "gray", "games", "games_nowin", "pairs", "pct",
         "pct_nowin"))
for g in range(L + 1):
    for y in range(L + 1 - g):
        if not (tally[g, y] or pairs[g, y]):
            continue
        print("%6d %7d %6d %10d %12d %12d %8.4f%% %9.4f%%"
              % (g, y, L - g - y, tally[g, y], tally_nowin[g, y], pairs[g, y],
                 pct(tally[g, y], pairs[g, y]),
                 pct(tally_nowin[g, y], pairs[g, y])))

print("\nmarginal by greens:")
for g in range(L + 1):
    s, p = int(tally[g].sum()), int(pairs[g].sum())
    if p:
        print("  %d green: %8d games / %10d pairs = %7.4f%%" % (g, s, p, pct(s, p)))
print("marginal by yellows:")
for y in range(L + 1):
    s, p = int(tally[:, y].sum()), int(pairs[:, y].sum())
    if p:
        print("  %d yellow: %8d games / %10d pairs = %7.4f%%" % (y, s, p, pct(s, p)))
print("marginal by grays:")
gray_games = np.zeros(L + 1, dtype=np.int64)
gray_pairs = np.zeros(L + 1, dtype=np.int64)
for g in range(L + 1):
    for y in range(L + 1 - g):
        gray_games[L - g - y] += tally[g, y]
        gray_pairs[L - g - y] += pairs[g, y]
for k in range(L + 1):
    if gray_pairs[k]:
        print("  %d gray: %8d games / %10d pairs = %7.4f%%"
              % (k, int(gray_games[k]), int(gray_pairs[k]),
                 pct(int(gray_games[k]), int(gray_pairs[k]))))
