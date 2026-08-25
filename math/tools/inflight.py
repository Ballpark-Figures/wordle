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
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import CSV_PATH, GUESS_WORDS, LOG, N_ANSWERS, PATTERNS, read_rows

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
    """The live CSV only (not the archive) -- append order is dispatch history.

    Uses paths.read_rows, not a bare DictReader: the file can carry more than one
    header line and DictReader would misalign every column after the schema
    change. See the note on read_rows in paths.py.
    """
    order, info = [], {}
    for r in read_rows(CSV_PATH):
        w = r["word"]
        order.append(w)
        try:
            total = int(r["total"]) if r.get("total") else None
        except ValueError:
            total = None
        try:
            secs = float(r["seconds"]) if r.get("seconds") else None
        except ValueError:
            secs = None
        info[w] = (total, secs)
    return order, info


def run_header():
    """Resume count, wall-clock start, elapsed seconds, and THREAD COUNT.

    The thread count matters: it is how many openers can be in flight at once,
    so a wrong value makes the IN FLIGHT section report slots that do not exist.
    run-hard-sweep.sh stamps `threads=N` into its header; run-sweep.sh does not,
    so an unstamped run falls back to THREADS and behaves exactly as before.
    """
    started, resumed, elapsed = None, 0, None
    threads = None
    with open(LOG) as f:
        for line in f:
            m = re.match(r"\[(\d{4}-\d\d-\d\dT[\d:+-]+)\] resuming", line)
            if m:
                started, resumed, elapsed = m.group(1), 0, None
                t = re.search(r"threads=(\d+)", line)
                threads = int(t.group(1)) if t else None
                continue
            m = re.match(r"resume: (\d+) openers already done", line)
            if m:
                resumed = int(m.group(1))
                continue
            m = re.match(r"\[\s*(\d+)s\]", line)
            if m:
                elapsed = int(m.group(1))
    return started, resumed, elapsed, threads


def completion_times():
    """Elapsed-seconds stamp of every completion in the CURRENT run, in order.

    The stamp resets to 0 at each resume, so the list is cleared whenever a new
    `resuming` header appears -- pace windows must not straddle a restart.
    """
    times = []
    with open(LOG) as f:
        for line in f:
            if re.match(r"\[\d{4}-\d\d-\d\dT[\d:+-]+\] resuming", line):
                times = []
                continue
            m = re.match(r"\[\s*(\d+)s\]", line)
            if m:
                times.append(int(m.group(1)))
    return times


def status(threads=THREADS):
    """Also recovers how long each IN-FLIGHT word has been running. Start times
    are not logged, but dispatch follows sweep order and `schedule(dynamic, 1)`
    hands a freed slot the next word, so the i-th dispatched word starts at the
    (i - threads)-th completion. Checked against all 2430 completed words of the
    current run: median error 0.3 s, worst 1.0 s (log rounding). Runtimes are
    measured against the WALL CLOCK, not the last log stamp -- see status().

    None if the run can't be reconstructed (no log, or no patterns matrix --
    it's gitignored, so a fresh clone has no sweep order to compute)."""
    if not (os.path.exists(LOG) and os.path.exists(PATTERNS)
            and os.path.exists(CSV_PATH)):
        return None
    started, resumed, elapsed, logthreads = run_header()
    if logthreads:
        threads = logthreads
    if elapsed is None:
        return None
    order = sweep_order()
    done_order, info = csv_rows_in_order()
    done_now = set(done_order)
    done_at_resume = set(done_order[:resumed])
    remaining = [w for w in order if w not in done_now]
    times = completion_times()
    dispatch = [w for w in order if w not in done_at_resume]
    pos = {w: i for i, w in enumerate(dispatch)}

    # `elapsed` is the stamp of the LAST COMPLETION, not now. An in-flight word
    # has been running since then too, so measure against the wall clock: the
    # log is written only on completion, so its mtime IS that completion's wall
    # time, and now - mtime is the extra. Both come from the current clock, so a
    # past clock jump cannot skew it. Without this the runtimes freeze whenever
    # completions stop -- harmless at 20 words in flight, badly wrong at 1.
    since_last = max(0.0, time.time() - os.path.getmtime(LOG))
    now_elapsed = elapsed + since_last

    runtimes = {}
    for w in remaining[:threads]:
        i = pos.get(w)
        if i is not None:
            runtimes[w] = now_elapsed - (0 if i < threads else times[i - threads])
    return {
        "started": started,
        "resumed": resumed,
        "elapsed": elapsed,
        "completed": len(done_order) - resumed,
        "threads": threads,
        "info": info,
        "initial": [w for w in order if w not in done_at_resume][:threads],
        "remaining": remaining,          # every unsolved opener, dispatch order
        "current": remaining[:threads],  # ...of which these hold the threads
        "times": times,
        "runtimes": runtimes,            # in-flight word -> seconds so far
        "now_elapsed": now_elapsed,      # run elapsed NOW, not at last completion
        "since_last": since_last,        # wall seconds since anything completed
    }


def hrs(s):
    return "%.1f h" % (s / 3600.0)


def print_status(st, verbose=True):
    """The IN FLIGHT block, shared by this tool and report.py."""
    print("  run started %s  --threads %d" % (st["started"], st["threads"]))
    print("  resumed with %d done; %d finished since, %s elapsed"
          % (st["resumed"], st["completed"], hrs(st.get("now_elapsed", st["elapsed"]))))
    if st.get("since_last", 0) > 900:
        print("  last completion was %s ago (log stamp %s)"
              % (hrs(st["since_last"]), hrs(st["elapsed"])))

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
    print("\n  in flight now (%d) -- %d t=0 holdovers, %d picked up later"
          % (len(current), len(current) - len(later), len(later)))
    rt = st.get("runtimes", {})
    for w in sorted(current, key=lambda w: -rt.get(w, 0)):
        print("    %-7s running %8.0fs  (%s)" % (w, rt.get(w, 0), hrs(rt.get(w, 0))))


def print_remaining(st, per_row=10):
    """Every unsolved opener in dispatch order. Dispatch follows this order
    strictly; COMPLETION does not, so a word further down can land first."""
    left, threads = st["remaining"], st["threads"]
    print("  %d openers remaining, in sweep dispatch order" % len(left))
    for i in range(0, len(left), per_row):
        print("  %5d  %s%s" % (i + 1, " ".join(left[i:i + per_row]),
                               "   <-- in flight" if i < threads else ""))


PACE_WINDOWS = (1000, 100, 50, 20, 10, 5)


def print_pace(st, windows=PACE_WINDOWS):
    """Remaining wall-clock implied by the pace over each trailing window.

    Pure throughput extrapolation: rate = N / (span of the last N completions),
    remaining / rate. It says nothing about how long any INDIVIDUAL word takes,
    and the sweep ends when the last word lands, not when the queue drains.
    """
    times, left = st["times"], len(st["remaining"])
    print("  %d openers remaining" % left)
    print("  %8s %10s %10s %12s" % ("window", "span", "rate/h", "remaining"))
    for n in windows:
        if len(times) < n + 1:
            continue
        span = times[-1] - times[-(n + 1)]
        if span <= 0:
            continue
        rate = n / (span / 3600.0)
        print("  %8d %8.2f h %10.1f %10.2f h" % (n, span / 3600.0, rate, left / rate))


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
