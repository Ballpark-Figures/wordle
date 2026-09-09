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
# PHASE1 -- coexist with a running optturns.  14 threads at nice 19, with a
#   deliberately small 0.54 GB table.  Both are overridable:
#
#     bash solver/run-hard-sweep.sh phase1 --threads 8 --tt-bits 26
#
#   WHY THOSE NUMBERS (measured 2026-08-23, with optturns on its last 6 openers):
#
#   threads 14 -- optturns was using 586% CPU, i.e. 5.9 cores for its 6 in-flight
#     openers, leaving ~13.7 genuinely idle; its finished threads SLEEP at the
#     OpenMP barrier rather than spinning.  6 + 14 = 20, so the two jobs do not
#     actually contend.  Note ps %CPU is a LIFETIME AVERAGE and read 1859% here
#     -- measure with `top -b -n 2 -d 3` instead, or you will size this wrong.
#
#   nice 19 -- CPU scheduling weight ONLY (-20 highest .. +19 lowest, 0 default).
#     It decides who wins when two processes want the SAME core, and costs
#     nothing when cores are idle.  It does NOT limit memory: RAM is governed
#     entirely by --tt-bits.  So this is belt-and-braces for the moments the two
#     jobs might overlap.
#
#   tt-bits 24 -- 0.54 GB of the 4.9 GiB available, leaving ~4.4 GiB.  The thing
#     to protect is optturns' 16 GiB resident table: push THAT into swap and its
#     throughput collapses.  --tt-bits 26 (2.15 GB) leaves ~2.8 GiB against
#     optturns' ~1.4 GiB of still-unfaulted table -- too thin while the normal
#     sweep is the priority.
#
#   NOTE --tt-bits 0 means literally no memoisation: every recurrence of a deep
#   state is recomputed.  Measured on SALET, the EASIEST opener: 119s with the
#   0.54 GB table, still unfinished after 5.5 minutes with none.  The hard
#   openers, where the table matters most, are far worse.  Prefer the smallest
#   table that fits over no table at all.
#
# PHASE2 -- the normal sweep is done and the machine is yours.  All 20 threads,
#   --tt-bits 29 (17.2 GB), warm-started from tt.bin if a snapshot exists.
#   Refuses to start while optturns is still running, since the two tables do
#   not fit at once.
#
# Resume is automatic in BOTH phases: finished openers are read from the CSV and
# skipped, so stopping phase 1 and starting phase 2 simply continues the sweep.
#
# THE CAP ESCALATES.  Normal Wordle can use one fixed 6-guess cap because every
# opener wins within 6 by following SALET's tree afterwards.  Hard mode has no
# such escape, so a fixed cap returns NOTHING for the openers it cannot fit --
# exactly the data we want.  hardturns therefore starts at --depth and raises the
# cap one guess at a time, per opener, until that opener solves; the depth it
# needed is recorded in the CSV and shown as `d=N` in the progress line, with a
# `*` marking any opener that needed more than the starting 6.
#
# WHAT THAT NUMBER IS: the minimum total AT THE FIRST FEASIBLE CAP.  Since f is
# non-increasing in depth, a deeper cap may admit a LOWER total, so this is the
# minimum-DEPTH solution, not necessarily the minimum expected guesses.  The CSV
# carries (total, depth) per opener precisely so a later stabilisation pass can
# seed from it and check whether depth+1 improves anything.
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

DEPTH=6          # where the cap starts
DEPTHMAX=19      # ceiling; MAXD-1 in optturns.c, raise both together

PHASE=${1:-}
shift 2>/dev/null
case "$PHASE" in
    phase1) THREADS=14; TTBITS=24; NICE=(nice -n 19) ;;
    phase2) THREADS=20; TTBITS=29; NICE=() ;;
    *) echo "usage: bash solver/run-hard-sweep.sh {phase1|phase2} [--threads N] [--tt-bits N]" >&2
       echo "  phase1  share the machine with a running optturns sweep" >&2
       echo "  phase2  take the whole machine once optturns has finished" >&2
       exit 1 ;;
esac

while [ $# -gt 0 ]; do
    case "$1" in
        --threads)   THREADS=$2; shift 2 ;;
        --tt-bits)   TTBITS=$2;  shift 2 ;;
        --depth)     DEPTH=$2;   shift 2 ;;
        --depth-max) DEPTHMAX=$2; shift 2 ;;
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

# Only the DIRECTORIES -- the solver writes the CSV header itself, on the run
# that finds no resumable rows.  Writing one here too produced a duplicate (and,
# once the depth column was added, a stale 4-column one on line 1).
mkdir -p "$(dirname "$OUT")" "$LOC/trees"

# reuse a table snapshot if present, so we resume warm rather than cold
WARM=""
[ "$TTBITS" -gt 0 ] && [ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

# the timestamped header is what inflight.py uses to find the run boundary
echo "[$(date -Is)] resuming wordle HARD sweep ($PHASE, threads=$THREADS, tt-bits=$TTBITS, depth=$DEPTH..$DEPTHMAX) $WARM" \
    | tee -a "$LOC/sweep.log"

# --order bisect: THIS SWEEP IS THE ONE THAT WANTS IT, and it is now the only
# one that gets it.  The opener list is still sorted by split score; bisection
# changes the DISPATCH to ends, median, quartiles, odd eighths, so the solved
# subset is a stratified sample of the whole difficulty range at every moment
# rather than a prefix of the easy end.  That is what makes this run's in-flight
# percentiles, histogram and worst-list mean anything -- and reading the partial
# distribution while it runs is the point of the hard sweep.
#
# It COSTS early throughput (the second opener dispatched is the worst-
# partitioned word in the list, so the incumbent that drives the lower-bound
# cutoffs arrives late), which is exactly why it must be asked for and never
# inherited.  It was hardcoded into both sweep call sites for a while, so every
# other sweep silently paid that cost for reporting nobody was reading.
"${NICE[@]}" ./solver/hardturns --sweep --order bisect \
    --out "$OUT" \
    --trees "$LOC/trees" \
    --depth "$DEPTH" --depth-max "$DEPTHMAX" \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
