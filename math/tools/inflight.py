"""Which openers the CURRENT sweep run picked up, and which are still running.

The sweep is an `omp for schedule(dynamic, 1)` over `sweep_order()` (fewest
expected survivors first), skipping words already in the CSV. So at t=0 the N
threads grab the first N not-yet-done words in that order, and each slot pulls
the next one down the list as it frees. That makes both sets recoverable:

  words in flight now  = first N words in sweep order missing from the CSV
  words in flight at t=0 = first N missing from the CSV as it stood at resume
                           (the CSV is append-only, so that is its first
                            `resume: K openers already done` rows)

    python3 inflight.py              # 20 threads (the standing sweep)
    python3 inflight.py --threads 12
"""
import csv
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import CSV_PATH, GUESS_WORDS, LOG, N_ANSWERS, PATTERNS

NPAT = 243

threads = 20
if "--threads" in sys.argv:
    threads = int(sys.argv[sys.argv.index("--threads") + 1])


def sweep_order(words):
    """Mirror of `sweep_order()` in optturns.c: ascending sum-of-squares of the
    pattern-class sizes, ties broken by index in guess.txt."""
    pat = np.load(PATTERNS, allow_pickle=False)
    ss = np.empty(len(words), dtype=np.int64)
    for g in range(len(words)):
        cnt = np.bincount(pat[g], minlength=NPAT).astype(np.int64)
        ss[g] = (cnt * cnt).sum()
    return [words[g] for g in np.lexsort((np.arange(len(words)), ss))]


def csv_rows_in_order():
    """The live CSV only (not the archive) -- append order is dispatch history."""
    order, info = [], {}
    with open(CSV_PATH) as f:
        for r in csv.DictReader(f):
            w = r.get("word")
            if not w:
                continue
            order.append(w)
            info[w] = (int(r["total"]) if r.get("total") else None,
                       float(r["seconds"]) if r.get("seconds") else None)
    return order, info


def run_header():
    """Resume count, wall-clock start, and elapsed seconds of the current run."""
    started, resumed, elapsed = None, 0, None
    with open(LOG) as f:
        for line in f:
            m = re.match(r"\[(\d{4}-\d\d-\d\dT[\d:+-]+)\] resuming", line)
            if m:
                started, resumed, elapsed = m.group(1), 0, None
                continue
            m = re.match(r"resume: (\d+) openers already done", line)
            if m:
                resumed = int(m.group(1))
                continue
            m = re.match(r"\[\s*(\d+)s\]", line)
            if m:
                elapsed = int(m.group(1))
    return started, resumed, elapsed


def hrs(s):
    return "%.1f h" % (s / 3600.0)


words = [w.strip() for w in open(GUESS_WORDS) if w.strip()]
order = sweep_order(words)
done_order, info = csv_rows_in_order()
started, resumed, elapsed = run_header()

done_now = set(done_order)
done_at_resume = set(done_order[:resumed])

initial = [w for w in order if w not in done_at_resume][:threads]
current = [w for w in order if w not in done_now][:threads]

print("run started %s  --threads %d" % (started, threads))
print("resumed with %d done; last log line at %ss (%s)\n"
      % (resumed, elapsed, hrs(elapsed)))

fin = [w for w in initial if w in done_now]
print("THE %d OPENERS IN FLIGHT AT t=0 -- %d finished, %d still running"
      % (threads, len(fin), threads - len(fin)))
print("-" * 62)
for w in initial:
    if w in done_now:
        total, secs = info[w]
        print("  %-7s done   total=%5d  exp=%.5f  %8.0fs  (%s)"
              % (w, total, total / N_ANSWERS, secs, hrs(secs)))
    else:
        print("  %-7s RUNNING  %s so far" % (w, hrs(elapsed)))

still = [w for w in current if w not in initial]
print("\nIN FLIGHT NOW (%d): %s" % (len(current), " ".join(current)))
print("  %d of them are t=0 holdovers; %d picked up later: %s"
      % (len(current) - len(still), len(still), " ".join(still)))
