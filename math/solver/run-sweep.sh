#!/bin/bash
# Start the optturns sweep ATTACHED, with live output in this terminal.
#
# This is the DEFAULT way to launch when you are at the machine: the solver runs
# in the foreground so you watch completions scroll by directly.  ~/bin/resume-
# jobs.sh is the OTHER path -- detached via nohup, wired to a Windows Scheduled
# Task, for recovering an unattended reboot.  Same flags either way.
#
#     bash solver/run-sweep.sh        # from math/, or from anywhere
#
# solver/run-hard-sweep.sh is the HARD-MODE companion (solver/hardturns, its own
# data/{shared,local}/hardturns/ directory).  It takes a phase argument, because
# it is designed to start while THIS sweep still owns the machine and then take
# over from it -- see "Hard mode" in README.md.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.  That
# matters: tools/report.py and tools/inflight.py PARSE that log for the run's
# start time, resume count and elapsed seconds.  Run the binary bare, with no
# tee, and the IN FLIGHT section silently reports the PREVIOUS run's numbers.
#
# Ctrl-C stops the sweep.  Finished words are already in the CSV (flushed per
# word), but the transposition table is lost -- there is no save on SIGINT.  To
# keep the table, snapshot it FIRST with tools/ttdump.py while the solver is
# still live; see "Saving / restoring the table" in README.md.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=data/shared/optturns/opener_totals.csv
LOC=data/local/optturns

cd "$MATH" || exit 1

if pgrep -x optturns >/dev/null; then
    echo "optturns is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "Attach to its output instead:  tail -F $MATH/$LOC/sweep.log" >&2
    exit 1
fi
[ -x ./solver/optturns ] || { echo "no solver binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f "$OUT" ] || { echo "no $OUT to resume from" >&2; exit 1; }

# reuse a table snapshot if present, so we resume warm rather than cold
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

# the timestamped header is what inflight.py uses to find the run boundary
echo "[$(date -Is)] resuming wordle sweep $WARM" | tee -a "$LOC/sweep.log"

./solver/optturns --sweep \
    --out "$OUT" \
    --trees "$LOC/trees" \
    --tt-bits 29 --threads 20 $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
