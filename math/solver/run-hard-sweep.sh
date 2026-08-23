#!/bin/bash
# Start the HARD-MODE sweep (solver/hardturns) ATTACHED, live output in this
# terminal.  Companion to run-sweep.sh, which does the same for normal Wordle;
# same flags, same resume behaviour, its own data directory.
#
# It takes a PHASE, because the hard sweep is meant to start while the normal
# optturns sweep still owns the machine and then take the machine over:
#
#     bash solver/run-hard-sweep.sh phase1    # share: spare cores, no big table
#     bash solver/run-hard-sweep.sh phase2    # own it: all cores, full table
#
# PHASE1 -- coexist with a running optturns.  Runs at nice 19 so the normal
#   sweep keeps every core it actually wants and hardturns only fills idle
#   capacity, and takes NO transposition table by default (--tt-bits 0), since
#   optturns is holding ~17 GB of the machine's RAM.  Both are overridable:
#
#     bash solver/run-hard-sweep.sh phase1 --threads 8 --tt-bits 24
#
#   NOTE --tt-bits 0 means literally no memoisation: every recurrence of a deep
#   state is recomputed.  That is orders of magnitude slower than even a small
#   table.  --tt-bits 24 costs 512 MB and buys back most of it; --tt-bits 26 is
#   2.1 GB.  Prefer the smallest table that fits rather than none.
#
# PHASE2 -- the normal sweep is done and the machine is yours.  All 20 threads,
#   --tt-bits 29 (17.2 GB), warm-started from tt.bin if a snapshot exists.
#   Refuses to start while optturns is still running, since the two tables do
#   not fit at once.
#
# Resume is automatic in BOTH phases: finished openers are read from the CSV and
# skipped, so stopping phase 1 and starting phase 2 simply continues the sweep.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal -- the
# tools PARSE that log for the run's start time, resume count and elapsed
# seconds, so a run that never reaches the log makes the IN FLIGHT section
# report the PREVIOUS run's numbers.  Read the report with:
#
#     WORDLE_SOLVER=hardturns python3 tools/report.py
#
# Ctrl-C stops the sweep.  Finished words are already in the CSV (flushed per
# word), but the transposition table is lost -- there is no save on SIGINT.  To
# keep the table, snapshot it FIRST with tools/ttdump.py while the solver is
# still live; see "Saving / restoring the table" in README.md.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=data/shared/hardturns/opener_totals.csv
LOC=data/local/hardturns

cd "$MATH" || exit 1

PHASE=${1:-}
shift 2>/dev/null
case "$PHASE" in
    phase1) THREADS=12; TTBITS=0;  NICE=(nice -n 19) ;;
    phase2) THREADS=20; TTBITS=29; NICE=() ;;
    *) echo "usage: bash solver/run-hard-sweep.sh {phase1|phase2} [--threads N] [--tt-bits N]" >&2
       echo "  phase1  share the machine with a running optturns sweep" >&2
       echo "  phase2  take the whole machine once optturns has finished" >&2
       exit 1 ;;
esac

while [ $# -gt 0 ]; do
    case "$1" in
        --threads) THREADS=$2; shift 2 ;;
        --tt-bits) TTBITS=$2; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if pgrep -x hardturns >/dev/null; then
    echo "hardturns is already running (pid $(pgrep -x hardturns | tr '\n' ' '))." >&2
    echo "Attach to its output instead:  tail -F $MATH/$LOC/sweep.log" >&2
    exit 1
fi
if [ "$PHASE" = phase2 ] && pgrep -x optturns >/dev/null; then
    echo "optturns is STILL RUNNING (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "phase2 wants 17.2 GB for its table; the two do not fit at once." >&2
    echo "Wait for it to finish, or run phase1 to keep sharing." >&2
    exit 1
fi
[ -x ./solver/hardturns ] || { echo "no hardturns binary -- run 'sh build.sh' in solver/" >&2; exit 1; }

mkdir -p "$(dirname "$OUT")" "$LOC/trees"
[ -f "$OUT" ] || echo "word,total,expected,seconds" > "$OUT"

# reuse a table snapshot if present, so we resume warm rather than cold
WARM=""
[ "$TTBITS" -gt 0 ] && [ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

# the timestamped header is what inflight.py uses to find the run boundary
echo "[$(date -Is)] resuming wordle HARD sweep ($PHASE, threads=$THREADS, tt-bits=$TTBITS) $WARM" \
    | tee -a "$LOC/sweep.log"

"${NICE[@]}" ./solver/hardturns --sweep \
    --out "$OUT" \
    --trees "$LOC/trees" \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
