"""The standing status report for the optturns sweep — one command.

    python3 math/tools/report.py            # everything
    python3 math/tools/report.py --brief    # progress + extremes, no histogram

Replaces stitching extremes.py + histogram.py + a log tail together by hand.
The IN FLIGHT section comes from inflight.py (which words the current run is
chewing on); --brief collapses it to just the long-running stragglers.
"""
import csv
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inflight
from paths import CSV_PATH, LOG, N_ANSWERS, N_GUESSES, load_totals

BIN = 0.01
BRIEF = "--brief" in sys.argv
TOP = 10


def rule(title):
    print("\n" + title)
    print("-" * len(title))


totals = load_totals()
if not totals:
    sys.exit("no results yet at %s" % CSV_PATH)
n = len(totals)
order = sorted(totals.items(), key=lambda kv: kv[1])

print("optturns sweep - %d of %d openers solved (%.1f%%)"
      % (n, N_GUESSES, 100 * n / N_GUESSES))
lo, hi = order[0][1], order[-1][1]
print("range %.5f .. %.5f   spread %.5f turns (%d guesses)"
      % (lo / N_ANSWERS, hi / N_ANSWERS, (hi - lo) / N_ANSWERS, hi - lo))

rule("BEST")
for i, (w, t) in enumerate(order[:TOP], 1):
    print("%3d  %-6s %5d  %.5f" % (i, w, t, t / N_ANSWERS))

rule("WORST")
for i, (w, t) in enumerate(order[-TOP:][::-1], 1):
    print("%3d  %-6s %5d  %.5f" % (i, w, t, t / N_ANSWERS))

if not BRIEF:
    rule("HISTOGRAM (%.2f-wide bins)" % BIN)
    bins = {}
    for t in totals.values():
        bins[int(math.floor(t / N_ANSWERS / BIN))] = \
            bins.get(int(math.floor(t / N_ANSWERS / BIN)), 0) + 1
    peak = max(bins.values())
    cum = 0
    print("%14s %7s %7s %8s %8s" % ("bin", "count", "pct", "cum", "pctile"))
    for b in range(min(bins), max(bins) + 1):
        c = bins.get(b, 0)
        cum += c
        print("[%.2f, %.2f) %7d %6.1f%% %8d %7.2f%%  %s"
              % (b * BIN, (b + 1) * BIN, c, 100 * c / n, cum, 100 * cum / n,
                 "#" * int(round(40 * c / peak))))

# slowest solves come only from the live CSV -- archived runs used older code
if os.path.exists(CSV_PATH):
    times = []
    with open(CSV_PATH) as f:
        for r in csv.DictReader(f):
            if r.get("word") and r.get("seconds") and r.get("total"):
                times.append((float(r["seconds"]), r["word"], int(r["total"])))
    if times:
        times.sort(reverse=True)
        rule("SLOWEST TO SOLVE")
        for s, w, t in times[:TOP]:
            print("  %-6s %8.1fs (%5.1f h)  expected %.5f"
                  % (w, s, s / 3600, t / N_ANSWERS))

st = inflight.status()
if st:
    rule("IN FLIGHT")
    inflight.print_status(st, verbose=not BRIEF)
    if not BRIEF and st["remaining"]:
        rule("REMAINING (dispatch order)")
        inflight.print_remaining(st)

if os.path.exists(LOG):
    last = None
    with open(LOG) as f:
        for line in f:
            if re.match(r"\[\s*\d+", line):
                last = line.rstrip()
    if last:
        rule("LATEST LOG LINE")
        print("  " + last)
        m = re.search(r"tt ([\d.]+)%/([\d.]+)%", last)
        if m:
            print("\n  NOTE: the occupancy figure under-reports while long words are")
            print("  in flight (thread-local fill counters fold in only on completion).")
            print("  Use tools/ttscan.py against the live process for the true value.")
