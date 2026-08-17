"""Expected turns grouped by vowel count, plus every solved 4- and 5-vowel word.

    python3 vowels.py           # a,e,i,o,u
    python3 vowels.py aeiouy    # count y as a vowel (shifts the optimum to 1)
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import N_ANSWERS, N_GUESSES, load_totals

V = set(sys.argv[1] if len(sys.argv) > 1 else "aeiou")
print("treating as vowels: %s" % "".join(sorted(V)))

rows = load_totals()
order = sorted(rows.items(), key=lambda kv: kv[1])
rank = {w: i + 1 for i, (w, _) in enumerate(order)}
n = len(order)
nv = lambda w: sum(c in V for c in w)
print("solved: %d of %d (%.1f%%)\n" % (n, N_GUESSES, 100 * n / N_GUESSES))

print("vowel-count trend across everything solved")
print("%7s %6s %9s %9s %9s %9s" % ("vowels", "count", "median", "mean", "best", "worst"))
for k in range(6):
    grp = [t / N_ANSWERS for w, t in rows.items() if nv(w) == k]
    if grp:
        print("%7d %6d %9.5f %9.5f %9.5f %9.5f"
              % (k, len(grp), statistics.median(grp), statistics.mean(grp),
                 min(grp), max(grp)))

for k in (5, 4):
    grp = sorted([w for w in rows if nv(w) == k], key=lambda w: rows[w])
    print("\n" + "=" * 62)
    print("%d-VOWEL WORDS SOLVED: %d" % (k, len(grp)))
    print("=" * 62)
    if not grp:
        continue
    print("%7s %7s %10s %13s %8s" % ("word", "total", "expected", "rank", "pctile"))
    for w in grp:
        t = rows[w]
        print("%7s %7d %10.5f %6d/%-6d %7.1f%%"
              % (w, t, t / N_ANSWERS, rank[w], n, 100 * rank[w] / n))
