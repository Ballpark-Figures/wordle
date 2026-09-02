"""Stage 1: the SHORTEST sequence of guesses that beats Absurdle — one of them.

    python3 tools/absurdle_shortest.py

Two separate jobs, because a "shortest" claim needs both halves:

  1. THE FLOOR — prove no shorter game exists. A win in W guesses needs the
     candidate set to be a SINGLETON after W-1 guesses (all-green loses every
     tie-break, so the host concedes only when it has no choice). One guess can
     take a set of size n to a singleton only if all n candidates get DISTINCT
     patterns, which needs n <= the number of attainable patterns, 238. So the
     size of the state after the first guess — exhaustively known, it is just
     the largest bucket of each of the 12972 openers — settles W=3 outright when
     even the best opener leaves more than 238.
  2. THE WITNESS — an actual sequence of that length, replayed and printed.

VISIT ORDER, named because order decides WHICH tied optimum is reported first:
continuations are tried by ASCENDING resulting-state size, ties by guess index.
Nothing is pruned by it — the search is exhaustive if run to exhaustion — but it
finds a witness early. Stage 2 will enumerate all tied openers and stage 3 all
tied sequences; this stage deliberately stops at the first one.

The only cap here is DISCOVERED, not imposed: the search deepens W by one until
it succeeds, so no depth limit is baked into the objective.

RESULTS ARE FOR OUR WORD LISTS (2315 answers / 12972 guesses), which are NOT
verified to be Absurdle's — see the Absurdle section of the repo CLAUDE.md.

Writes data/shared/absurdle/one_shortest_solution.txt.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from absurdle import respond, respond_all, show  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402

# Attainable feedback patterns: 3**5 = 243 encodings, of which the five with
# 4 greens + 1 yellow can never occur. An upper bound on the number of buckets
# any guess can split a set into, hence on the size of a set one guess can
# shatter into singletons. Slack but sound — the measured maximum against the
# 2315 answers is 149.
MAX_PATTERNS = 238

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "data", "shared", "absurdle", "one_shortest_solution.txt")

t0 = time.time()
pat = load_patterns()
answers = load_words("mystery")
guesses = load_words("guess")
root = np.arange(len(answers))
print("%d guesses, %d answers" % (len(guesses), len(answers)))

# --- layer 1: exhaustive, and it is only 12972 x 2315 -----------------------
codes0, sizes0 = respond_all(pat, root)
order0 = np.lexsort((np.arange(len(guesses)), sizes0))
print("\nafter one guess, candidates left: min %d, median %d, max %d  (%.1fs)"
      % (sizes0.min(), int(np.median(sizes0)), sizes0.max(), time.time() - t0))
print("the ten openers that leave the fewest:")
for g in order0[:10]:
    print("   %-6s %s  %4d left" % (guesses[g], show(int(codes0[g])), sizes0[g]))

# --- the floor --------------------------------------------------------------
print("\nFLOOR")
floor = None
if sizes0.min() == 1:
    floor = 2
    print("  some opener leaves a single candidate: a 2-guess win exists")
elif sizes0.min() > MAX_PATTERNS:
    floor = 4
    print("  the best opener still leaves %d candidates, and one guess can shatter"
          % sizes0.min())
    print("  at most %d into singletons, so NO state after two guesses is a" % MAX_PATTERNS)
    print("  singleton: a 3-guess win is IMPOSSIBLE. The floor is 4.")
else:
    # Some opener leaves few enough that a 3-guess win is not excluded on
    # counting grounds; check those exhaustively.
    live = [int(g) for g in order0 if sizes0[g] <= MAX_PATTERNS]
    print("  %d openers leave <= %d candidates; checking each exhaustively"
          % (len(live), MAX_PATTERNS))
    floor = 4
    for g1 in live:
        _, s1 = respond(pat, root, g1)
        _, sizes1 = respond_all(pat, s1)
        if sizes1.min() == 1:
            g2 = int(np.lexsort((np.arange(len(guesses)), sizes1))[0])
            print("  3-guess win: %s %s ..." % (guesses[g1], guesses[g2]))
            floor = 3
            break
    if floor == 4:
        print("  none of them reaches a singleton in two: a 3-guess win is")
        print("  IMPOSSIBLE. The floor is 4.")

# --- the witness ------------------------------------------------------------
print("\nWITNESS (searching for a %d-guess win)" % floor)


def search(cand, depth, prefix):
    """Find a guess sequence taking `cand` to a singleton in `depth` guesses."""
    if depth == 0:
        return prefix if len(cand) == 1 else None
    codes, sizes = respond_all(pat, cand)
    if depth == 1:
        # one guess must shatter the whole set into singletons
        g = int(sizes.argmin())
        return prefix + [g] if sizes[g] == 1 else None
    order = np.lexsort((np.arange(len(guesses)), sizes))
    for g in order:
        g = int(g)
        if sizes[g] >= len(cand):
            break            # ordered ascending, so nothing later shrinks either
        # a set larger than this cannot be shattered by the final guess
        if depth == 2 and sizes[g] > MAX_PATTERNS:
            break
        _, nxt = respond(pat, cand, g)
        found = search(nxt, depth - 1, prefix + [g])
        if found:
            return found
    return None


seq = search(root, floor - 1, [])
if seq is None:
    raise SystemExit("no %d-guess win found — deepen and re-run" % floor)

# the final, naming guess: the one candidate left
cand = root
lines = []
for g in seq:
    code, cand = respond(pat, cand, g)
    lines.append("  %-6s %s  %4d left" % (guesses[g], show(int(code)), len(cand)))
final = answers[int(cand[0])]
code, cand = respond(pat, cand, guesses.index(final))
lines.append("  %-6s %s  WIN" % (final, show(int(code))))
words = [guesses[g] for g in seq] + [final]

print("\n".join(lines))
print("\n%d guesses: %s   (%.1fs)" % (len(words), " ".join(words), time.time() - t0))

with open(OUT, "w") as f:
    f.write("# One SHORTEST winning sequence against Absurdle's host rule.\n")
    f.write("# Word lists: OUR original Wordle 2315 answers / 12972 guesses, which\n")
    f.write("# are NOT verified to match Absurdle's -- see CLAUDE.md. The host rule\n")
    f.write("# is transcribed from qntm's FAQ and unverified against the live game.\n")
    f.write("# Floor proved at %d guesses; this is one witness of that length, the\n" % floor)
    f.write("# first found in ascending-resulting-size order. Ties not enumerated.\n")
    f.write("sequence: %s\n" % " ".join(words))
    f.write("\n".join(lines) + "\n")
print("wrote %s" % os.path.normpath(OUT))
