"""Rank specific openers among everything solved so far.

    python3 lookup.py                    # a default set of popular openers
    python3 lookup.py adieu audio salet  # named words
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import N_ANSWERS, N_GUESSES, load_totals

WANT = sys.argv[1:] or ["salet", "trace", "slate", "crane", "stare", "soare",
                        "roate", "tears", "raise", "irate", "learn", "arise",
                        "adept", "adieu", "audio", "ouija", "queue"]

rows = load_totals()
order = sorted(rows.items(), key=lambda kv: kv[1])
rank = {w: i + 1 for i, (w, _) in enumerate(order)}
n = len(order)
print("solved: %d of %d\n" % (n, N_GUESSES))
print("%7s %7s %10s %13s %8s" % ("word", "total", "expected", "rank", "pctile"))
for w in WANT:
    if w in rows:
        t = rows[w]
        print("%7s %7d %10.5f %6d/%-6d %7.1f%%"
              % (w, t, t / N_ANSWERS, rank[w], n, 100 * rank[w] / n))
    else:
        print("%7s %7s %10s" % (w, "--", "not yet solved"))

print("\nNOTE: percentiles are over the SOLVED subset, which the best-first sweep")
print("order biases toward good openers. A word's rank improves as worse openers")
print("land, without its total changing.")
