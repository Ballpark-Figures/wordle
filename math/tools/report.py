"""The standing status report for the optturns sweep — one command.

    python3 math/tools/report.py            # everything
    python3 math/tools/report.py --brief    # progress + extremes, no histogram

Replaces stitching extremes.py + histogram.py + a log tail together by hand.
The IN FLIGHT section comes from inflight.py (which words the current run is
chewing on); --brief collapses it to just the long-running stragglers.

Section ORDER is deliberate: the report closes with REMAINING, WORST, IN FLIGHT,
then PACE, so the most-read numbers sit at the tail of the output and are visible
without scrolling back. WORST prints worst-LAST for the same reason. Do not
reshuffle these without asking.
"""
import csv
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inflight
from paths import (CSV_PATH, LOG, N_ANSWERS, N_GUESSES, SOLVER,
                   load_depths, load_infeasible, load_times, load_totals)

BIN = 0.01
BRIEF = "--brief" in sys.argv
TOP = 10


def rule(title):
    print("\n" + title)
    print("-" * len(title))


totals = load_totals()
infeasible = load_infeasible()
if not totals:
    sys.exit("no results yet at %s" % CSV_PATH)
n = len(totals)
order = sorted(totals.items(), key=lambda kv: kv[1])

# An INFEASIBLE opener is DONE, just with no total -- it counts as progress but
# not as a data point. Only hard mode ever produces one; see paths.load_totals.
done = n + len(infeasible)
print("%s sweep - %d of %d openers done (%.1f%%)"
      % (SOLVER, done, N_GUESSES, 100 * done / N_GUESSES))
if infeasible:
    print("  %d solved, %d INFEASIBLE within the guess budget" % (n, len(infeasible)))
lo, hi = order[0][1], order[-1][1]
print("range %.5f .. %.5f   spread %.5f turns (%d guesses)"
      % (lo / N_ANSWERS, hi / N_ANSWERS, (hi - lo) / N_ANSWERS, hi - lo))

# hardturns escalates the cap per opener; how far it had to go is a headline
# number for that sweep, so it sits near the top rather than buried.
depths = load_depths()
if depths and len(set(depths.values())) > 1:
    rule("GUESSES REQUIRED (escalated cap)")
    hist = {}
    for d in depths.values():
        hist[d] = hist.get(d, 0) + 1
    nd = len(depths)
    peakd = max(hist.values())
    for d in sorted(hist):
        print("  %2d guesses %7d  %5.1f%%  %s"
              % (d, hist[d], 100 * hist[d] / nd, "#" * int(round(40 * hist[d] / peakd))))
    base = min(hist)
    over = sum(v for k, v in hist.items() if k > base)
    print("\n  %d of %d openers (%.1f%%) needed more than %d guesses"
          % (over, nd, 100 * over / nd, base))
    print("  NB these are minimum-DEPTH solutions; the paired total is optimal")
    print("  SUBJECT TO that depth, not necessarily the minimum expected guesses.")

rule("BEST")
for i, (w, t) in enumerate(order[:TOP], 1):
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

# slowest solves come only from the live CSV -- archived runs used older code.
# Read via paths.load_times, NOT a bare DictReader: the file can carry more than
# one header line and DictReader would misalign every column after the schema
# change. See the note on read_rows in paths.py.
if os.path.exists(CSV_PATH):
    times = [(secs, w, t) for w, (secs, t) in load_times().items()]
    if times:
        times.sort(reverse=True)
        rule("SLOWEST TO SOLVE")
        for s, w, t in times[:TOP]:
            print("  %-6s %8.1fs (%5.1f h)  expected %.5f"
                  % (w, s, s / 3600, t / N_ANSWERS))

st = inflight.status()

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

# The closing sections are the ones read most often -- see the module docstring
# for the order and why.
if st and not BRIEF and len(st["remaining"]) > st["threads"]:
    # once the queue fits in the threads, REMAINING just repeats IN FLIGHT
    rule("REMAINING (dispatch order)")
    inflight.print_remaining(st)

# printed WORST-LAST: the final line of this block is the worst opener, so it
# lands closest to the bottom of the report. Ranks still count 1 = worst.
rule("WORST")
ntop = min(TOP, len(order))
for i, (w, t) in enumerate(order[-ntop:]):
    print("%3d  %-6s %5d  %.5f" % (ntop - i, w, t, t / N_ANSWERS))

if st:
    rule("IN FLIGHT")
    inflight.print_status(st, verbose=not BRIEF)

if st and st["remaining"]:
    rule("PACE (trailing-window extrapolation)")
    inflight.print_pace(st)
