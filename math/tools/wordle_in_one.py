"""Enumerate every "Wordle in One" game and break it down by tile composition.

A "Wordle in One" is a feedback ROW that names its answer outright: a guess and
a pattern that exactly ONE answer produces (a SINGLETON). Seeing that row, the
answer is forced, so it can be won in a single guess. This tool lists every such
(guess, answer, pattern) and tallies them by how many GREEN, YELLOW and GRAY
tiles the row has.

    python3 tools/wordle_in_one.py            # guesses = the 2315 answer words

THE GUESS SET IS THE 2315 ANSWER WORDS, not all 12972 guesses (the user's call:
"every singleton produced by every answer word, not all guesses"). The answer
set is the 2315 mystery answers. A pattern is a singleton for a guess when its
bucket over those 2315 answers has size exactly one.

THE ALL-GREEN ROW IS A SPECIAL CASE. When the guess is itself the answer the row
is all green, a singleton by the definition above but one that tells you nothing
you did not already know by typing the word. It lands in the (green=5) bin, so it
is visible and separable in the breakdown; the summary reports the totals both
with and without it (matching `singletons` vs `singletons_nowin` in
guess_singletons_answers.csv, which this tool's per-guess totals are checked
against).

Outputs, under data/shared/singletons/:
  wordle_in_one_games.csv        one row per game: guess,answer,pattern,greens,
                                 yellows,grays  (pattern as a G/Y/B string)
  wordle_in_one_breakdown.csv    counts per (greens,yellows,grays) composition
A pure function of the committed word lists, so it regenerates anywhere.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import all_green, decode, load_words  # noqa: E402

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(_MATH, "data", "shared", "singletons")
GAMES_OUT = os.path.join(OUT_DIR, "wordle_in_one_games.csv")
BREAK_OUT = os.path.join(OUT_DIR, "wordle_in_one_breakdown.csv")

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
answer_guess_idx = [i for i, g in enumerate(guesses) if g in answer_set]

# tally[(g, y)] -> count of singleton games with g greens, y yellows (grays=L-g-y)
tally = np.zeros((L + 1, L + 1), dtype=np.int64)
tally_nowin = np.zeros((L + 1, L + 1), dtype=np.int64)
per_guess = {}          # guess word -> singleton count (for the gate)
games = []              # (guess, answer, pattern_code)

for gi in answer_guess_idx:
    row = np.asarray(PAT[gi], dtype=np.int64)            # pattern per answer
    counts = np.bincount(row, minlength=NPAT)
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

total = int(tally.sum())
total_nowin = int(tally_nowin.sum())

# --- GATE: per-guess totals must match the committed guess_singletons_answers.csv
ref_path = os.path.join(OUT_DIR, "guess_singletons_answers.csv")
if os.path.exists(ref_path):
    ref = {}
    with open(ref_path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("word,"):
                continue
            w, singles, nowin, _rank = line.strip().split(",")
            ref[w] = (int(singles), int(nowin))
    bad = [w for w in per_guess if w in ref and per_guess[w] != ref[w][0]]
    if bad:
        raise SystemExit("GATE FAILED: per-guess singleton counts disagree with "
                         "guess_singletons_answers.csv for %d words, e.g. %s"
                         % (len(bad), bad[:5]))
    ref_nowin_total = sum(v[1] for w, v in ref.items())
    if ref_nowin_total != total_nowin:
        raise SystemExit("GATE FAILED: no-win total %d != committed sum %d"
                         % (total_nowin, ref_nowin_total))
    print("gate OK: per-guess totals match guess_singletons_answers.csv "
          "(%d words, %d no-win games)" % (len(per_guess), total_nowin))
else:
    print("gate SKIPPED: %s not found" % ref_path)

os.makedirs(OUT_DIR, exist_ok=True)
games.sort()
with open(GAMES_OUT, "w") as f:
    f.write("# every Wordle-in-One game: guess is one of the 2315 answer words, "
            "answer is the unique one giving that feedback row over the 2315 "
            "mystery answers\n")
    f.write("guess,answer,pattern,greens,yellows,grays\n")
    for g, a, code in games:
        f.write("%s,%s,%s,%d,%d,%d\n"
                % (g, a, pat_str(code), comp[code, 0], comp[code, 1], comp[code, 2]))

with open(BREAK_OUT, "w") as f:
    f.write("# Wordle-in-One games by tile composition (grays = %d - greens - "
            "yellows); games=all singletons, games_nowin excludes the all-green "
            "self-answer\n" % L)
    f.write("greens,yellows,grays,games,games_nowin\n")
    for g in range(L + 1):
        for y in range(L + 1 - g):
            if tally[g, y] or tally_nowin[g, y]:
                f.write("%d,%d,%d,%d,%d\n"
                        % (g, y, L - g - y, tally[g, y], tally_nowin[g, y]))

print("wrote %s (%d games)" % (os.path.relpath(GAMES_OUT, _MATH), total))
print("wrote %s" % os.path.relpath(BREAK_OUT, _MATH))
print("\n%d games total; %d excluding the all-green self-answer\n"
      % (total, total_nowin))

# printed breakdown
print("games by (greens, yellows, grays):")
print("%6s %7s %6s %10s %12s" % ("green", "yellow", "gray", "games", "games_nowin"))
for g in range(L + 1):
    for y in range(L + 1 - g):
        if tally[g, y] or tally_nowin[g, y]:
            print("%6d %7d %6d %10d %12d"
                  % (g, y, L - g - y, tally[g, y], tally_nowin[g, y]))

print("\nmarginal by greens:")
for g in range(L + 1):
    s = int(tally[g].sum())
    if s:
        print("  %d green: %6d games" % (g, s))
print("marginal by yellows:")
for y in range(L + 1):
    s = int(tally[:, y].sum())
    if s:
        print("  %d yellow: %6d games" % (y, s))
print("marginal by grays:")
grays = np.zeros(L + 1, dtype=np.int64)
for g in range(L + 1):
    for y in range(L + 1 - g):
        grays[L - g - y] += tally[g, y]
for k in range(L + 1):
    if grays[k]:
        print("  %d gray: %6d games" % (k, int(grays[k])))
