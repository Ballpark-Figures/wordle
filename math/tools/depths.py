"""How deep do the optimal trees actually go, and did any opener fail?

Each tree line is "<answer> <nguesses> <g1> <p1> ...", so column 2 is how many
guesses that answer needed. Summing column 2 must equal the opener's total --
the cheapest end-to-end check that a tree matches its reported value.

    python3 depths.py [word ...]
"""
import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import CSV_PATH, TREES, load_totals

import csv

blank = solved = 0
for r in csv.DictReader(open(CSV_PATH)):
    if not r.get("word"):
        continue
    if r.get("total"):
        solved += 1
    else:
        blank += 1
        print("INFEASIBLE within 6:", r["word"])
print("openers solved %d, infeasible %d" % (solved, blank))
print("(infeasible should always be 0: play any opener, then follow SALET's tree,")
print(" which resolves any answer in <=5 more -- so <=6 total, always.)\n")

totals = load_totals()
words = sys.argv[1:] or ["salet", "crane", "adieu", "audio", "asses", "jaxie"]
print("%7s %4s   distribution of guesses needed" % ("word", "max"))
for w in words:
    p = os.path.join(TREES, w + ".txt.gz")
    if not os.path.exists(p):
        print("%7s    -   (no tree yet)" % w)
        continue
    c = {}
    with gzip.open(p, "rt") as f:
        for line in f:
            k = int(line.split()[1])
            c[k] = c.get(k, 0) + 1
    tot = sum(k * v for k, v in c.items())
    flag = "" if totals.get(w) in (None, tot) else "  <-- MISMATCH vs CSV %d" % totals[w]
    print("%7s %4d   %s   (total %d)%s"
          % (w, max(c), "  ".join("%d:%d" % (k, c[k]) for k in sorted(c)), tot, flag))
