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

`report.py` imports `status()` from here for its IN FLIGHT section -- keep the
computation in this module rather than duplicating it there.
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import CSV_PATH, GUESS_WORDS, LOG, N_ANSWERS, PATTERNS

NPAT = 243
THREADS = 20


def sweep_order():
    """Mirror of `sweep_order()` in optturns.c: ascending sum-of-squares of the
    pattern-class sizes, ties broken by index in guess.txt."""
    import numpy as np

    words = [w.strip() for w in open(GUESS_WORDS) if w.strip()]
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


def status(threads=THREADS):
    """None if the run can't be reconstructed (no log, or no patterns matrix --
    it's gitignored, so a fresh clone has no sweep order to compute)."""
    if not (os.path.exists(LOG) and os.path.exists(PATTERNS)
            and os.path.exists(CSV_PATH)):
        return None
    started, resumed, elapsed = run_header()
    if elapsed is None:
        return None
    order = sweep_order()
    done_order, info = csv_rows_in_order()
    done_now = set(done_order)
    done_at_resume = set(done_order[:resumed])
    return {
        "started": started,
        "resumed": resumed,
        "elapsed": elapsed,
        "completed": len(done_order) - resumed,
        "threads": threads,
        "info": info,
        "initial": [w for w in order if w not in done_at_resume][:threads],
        "current": [w for w in order if w not in done_now][:threads],
    }


def hrs(s):
    return "%.1f h" % (s / 3600.0)


def print_status(st, verbose=True):
    """The IN FLIGHT block, shared by this tool and report.py."""
    print("  run started %s  --threads %d" % (st["started"], st["threads"]))
    print("  resumed with %d done; %d finished since, %s elapsed"
          % (st["resumed"], st["completed"], hrs(st["elapsed"])))

    initial, current, info = st["initial"], st["current"], st["info"]
    fin = [w for w in initial if w in info]
    print("\n  of the %d openers in flight at t=0: %d finished, %d still running"
          % (st["threads"], len(fin), len(initial) - len(fin)))
    if verbose:
        for w in initial:
            if w in info:
                total, secs = info[w]
                print("    %-7s done     total=%5d  exp=%.5f  %8.0fs  (%s)"
                      % (w, total, total / N_ANSWERS, secs, hrs(secs)))
            else:
                print("    %-7s RUNNING  %s so far" % (w, hrs(st["elapsed"])))
    else:
        stuck = [w for w in initial if w not in info]
        if stuck:
            print("    still running after %s: %s"
                  % (hrs(st["elapsed"]), " ".join(stuck)))

    later = [w for w in current if w not in initial]
    print("\n  in flight now (%d): %s" % (len(current), " ".join(current)))
    print("  %d t=0 holdovers, %d picked up later"
          % (len(current) - len(later), len(later)))


def main():
    threads = THREADS
    if "--threads" in sys.argv:
        threads = int(sys.argv[sys.argv.index("--threads") + 1])
    st = status(threads)
    if st is None:
        sys.exit("no reconstructable run (need %s, %s and %s)"
                 % (LOG, PATTERNS, CSV_PATH))
    print_status(st)


if __name__ == "__main__":
    main()
