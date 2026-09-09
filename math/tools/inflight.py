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
from paths import (CSV_PATH, FULL_GUESS_WORDS, GUESS_WORDS, LOG, N_ANSWERS,
                   PATTERNS, read_rows)

NPAT = 243
THREADS = 20          # fallback only; log_threads() below reads the real value


def log_threads(default=THREADS):
    """The thread count the RUNNING sweep actually used.

    This is the width of the in-flight window, so a wrong value invents openers
    that are not running (or hides ones that are). The solver prints `threads: N`
    at startup and that is tee'd into sweep.log, so read it rather than assume a
    machine: the desktop runs 20, this Mac runs 18. Last occurrence wins -- the
    log accumulates across runs.
    """
    n = default
    try:
        with open(LOG) as f:
            for line in f:
                if line.startswith("threads:"):
                    try: n = int(line.split(":", 1)[1])
                    except ValueError: pass
    except OSError:
        pass
    return n


def log_order(default="bisect"):
    """The DISPATCH order the running sweep actually used: "bisect", "ssq" or "lb".

    The bisection is no longer wired into every sweep -- it is `--order bisect`,
    which only the hard-mode sweep passes -- so this can no longer be assumed.
    Getting it wrong is silent and total: bisect() and the straight sort agree on
    the SET and on almost nothing else, so the in-flight window would name the
    wrong openers rather than fail.

    The solver prints `order: NAME` at startup beside `threads:`, and that is
    tee'd into sweep.log.  Last occurrence wins, as with the thread count.

    A log with NO `order:` line predates the flag, and every sweep was bisected
    then -- so the default reproduces those runs.  Callers that show the order to
    a human should say when it was assumed rather than read.
    """
    order = default
    try:
        with open(LOG) as f:
            for line in f:
                if line.startswith("order:"):
                    name = line.split(":", 1)[1].strip()
                    if name in ("bisect", "ssq", "lb"):
                        order = name
    except OSError:
        pass
    return order


def order_was_logged():
    """True if the log states its dispatch order -- i.e. it is not a guess."""
    try:
        with open(LOG) as f:
            return any(line.startswith("order:") for line in f)
    except OSError:
        return False


def bisect(seq):
    """Ends, median, quartiles, odd eighths, ... -- mirror of bisect_emit() plus
    the level loop in optturns.c.

    The rounding and the already-emitted skip must match the C EXACTLY: this is
    what reconstructs which opener each thread is on, so a divergence names the
    wrong words rather than failing loudly. Python's // is floor division and
    every term here is positive, so it agrees with C's truncating division.
    """
    n = len(seq)
    out, seen = [], bytearray(n)

    def emit(idx):
        idx = 0 if idx < 0 else (n - 1 if idx >= n else idx)
        if not seen[idx]:
            seen[idx] = 1
            out.append(seq[idx])

    emit(0)
    emit(n - 1)
    for k in range(1, 21):
        if len(out) >= n:
            break
        den = 1 << k
        for i in range(den // 2):
            if len(out) >= n:
                break
            emit((n * (2 * i + 1) + den // 2) // den)
    for i in range(n):
        if len(out) >= n:
            break
        emit(i)
    return out


def sweep_order(order=None):
    """Mirror of `sweep_order()` in optturns.c: the opener list sorted by fewest
    expected survivors (sum of squared pattern-class sizes, ties by index in
    guess.txt), then dispatched in the order THIS RUN asked for.

    `order` defaults to whatever the log says (log_order()): "bisect" walks ends,
    median, quartiles, odd eighths; anything else walks the sort straight down,
    best splitters first, which is the solver's default.  Passing it explicitly
    is for the checks, which compare the two.

    Already-solved openers keep their slot in this order -- the dispatch is over
    the whole list, so the sequence does not shift as the CSV fills; the solver
    skips them at dispatch via done[].
    """
    import numpy as np

    words = [w.strip() for w in open(GUESS_WORDS) if w.strip()]
    pat = np.load(PATTERNS, allow_pickle=False)
    if len(words) != pat.shape[0]:
        # A RESTRICTED sweep (--guess-list): patterns.npy rows are indexed by the
        # FULL guess list, so row g is not this word's row. Select the real rows,
        # mirroring the row compaction --guess-list does in the C. Ties then break
        # by index in the RESTRICTED list, which is what the solver sorts on too.
        full = [w.strip() for w in open(FULL_GUESS_WORDS) if w.strip()]
        idx = {w: i for i, w in enumerate(full)}
        pat = pat[[idx[w] for w in words]]
    ss = np.empty(len(words), dtype=np.int64)
    for g in range(len(words)):
        cnt = np.bincount(pat[g], minlength=NPAT).astype(np.int64)
        ss[g] = (cnt * cnt).sum()
    srt = [words[g] for g in np.lexsort((np.arange(len(words)), ss))]
    if order is None:
        order = log_order()
    return bisect(srt) if order == "bisect" else srt


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


def status(threads=None):
    """Also recovers how long each IN-FLIGHT word has been running. Start times
    are not logged, but dispatch follows sweep order and `schedule(dynamic, 1)`
    hands a freed slot the next word, so the i-th dispatched word starts at the
    (i - threads)-th completion. Checked against all 2430 completed words of the
    current run: median error 0.3 s, worst 1.0 s (log rounding).

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
    if threads is None:
        threads = log_threads()
    order = sweep_order()
    done_order, info = csv_rows_in_order()
    done_now = set(done_order)
    done_at_resume = set(done_order[:resumed])
    remaining = [w for w in order if w not in done_now]
    times = completion_times()
    dispatch = [w for w in order if w not in done_at_resume]
    pos = {w: i for i, w in enumerate(dispatch)}
    runtimes = {}
    for w in remaining[:threads]:
        i = pos.get(w)
        if i is not None:
            runtimes[w] = elapsed - (0 if i < threads else times[i - threads])
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
    threads = log_threads()
    if "--threads" in sys.argv:
        threads = int(sys.argv[sys.argv.index("--threads") + 1])
    st = status(threads)
    if st is None:
        sys.exit("no reconstructable run (need %s, %s and %s)"
                 % (LOG, PATTERNS, CSV_PATH))
    print_status(st)


if __name__ == "__main__":
    main()
