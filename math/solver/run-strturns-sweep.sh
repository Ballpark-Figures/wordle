#!/bin/bash
# Start the W -> S sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-strturns-sweep.sh --depth 30                 # from math/, or anywhere
#     bash solver/run-strturns-sweep.sh --depth 9 --depth-max 30 -k 1 --by-class
#
# WHAT THIS SOLVES, precisely:
#
#   Minimise the TOTAL guesses summed over ALL 11881376 length-5 strings as
#   answers, where the legal guesses are the 12972 words, SUBJECT TO resolving
#   every answer within --depth.  All but 12972 of the answers can never be
#   PLAYED, so they are scored narrow-to-one-plus-one -- the phantom final guess.
#
# USE THIS RATHER THAN CALLING ./solver/strturns DIRECTLY.  The binary writes a
# CSV only when given --out, and a bare invocation therefore prints its answer
# and saves NOTHING -- which is exactly what happened for a full day of runs
# before this script existed.  It sets --out, tees a log, and saves the table.
#
# DEPTH IS AT LEAST 9, AND THAT IS A PUBLISHED RESULT, not a guess.  Li and Zhu,
# "Playing Mastermind with Wordle-like Feedback" (Amer. Math. Monthly 131(5),
# 2024, arXiv:2209.13147) define F(k,n) as the fewest guesses needed with k
# letters and n positions under exactly Wordle's feedback, and prove
# floor(k/n) + n - 1 <= F(k,n) <= floor(k/n) + n when n does not divide k.  At
# k=26, n=5 that is 9 <= F(26,5) <= 10.  Their codebreaker may guess ANY string;
# restricting guesses to words can only make it worse.  So --depth below 9 is
# provably infeasible and will burn hours proving it.
#
# --topk K limits branching to the K evenest splits: an UPPER BOUND, not an
# optimum.  --by-class additionally collapses guesses the state cannot
# distinguish, which at K = 1 is exact (identical to plain --topk 1, roughly 9x
# faster) and at K > 1 means K distinct CLASSES rather than K tied words.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.
# Ctrl-C stops it; re-running resumes from the CSV and reloads the table.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
DEPTHMAX=""
TOPK=1
BYCLASS=1
ALLOW=1
THREADS=18
TTBITS=24

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)      DEPTH="$2";    shift 2 ;;
        --depth-max)  DEPTHMAX="$2"; shift 2 ;;
        -k|--topk)    TOPK="$2";     shift 2 ;;
        --no-by-class) BYCLASS=0;    shift 1 ;;
        --strict)     ALLOW=0;       shift 1 ;;   # INFEASIBLE instead of an unsolved count
        --threads)    THREADS="$2";  shift 2 ;;
        --tt-bits)    TTBITS="$2";   shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-strturns-sweep.sh --depth <d> [--depth-max <d>] [-k K]" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac
if [ "$DEPTH" -lt 9 ]; then
    echo "NOTE: depth $DEPTH is below the proven floor of 9 for this cell" >&2
    echo "      (F(26,5) >= 9, Li and Zhu 2024) -- it CANNOT resolve every answer." >&2
    echo "      Continuing anyway; pass --depth 9 or more for a feasible run." >&2
fi

cd "$MATH" || exit 1

[ -x ./solver/strturns ] || { echo "no ./solver/strturns -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f data/shared/words/guess.txt ] || { echo "no guess list" >&2; exit 1; }

# EVERY (depth, K, mode) COMBINATION GETS ITS OWN FILES.  Each is a different
# objective or a different search space, so sharing a CSV would interleave
# incomparable totals and let a resume seed one run from another's numbers.
TAG=d$DEPTH
[ -n "$DEPTHMAX" ] && TAG=${TAG}-$DEPTHMAX
TAG=${TAG}_k$TOPK
[ "$BYCLASS" -eq 1 ] && TAG=${TAG}_cls
[ "$ALLOW" -eq 0 ] && TAG=${TAG}_strict

OUTDIR=data/shared/strturns
LOC=data/local/strturns/$TAG
OUT=$OUTDIR/opener_totals_$TAG.csv
mkdir -p "$OUTDIR" "$LOC"

. "$MATH/solver/_guard.sh"
guard_output strturns "$OUT" || exit 1

FLAGS="--topk $TOPK"
[ "$BYCLASS" -eq 1 ] && FLAGS="$FLAGS --by-class"
[ "$ALLOW" -eq 1 ] && FLAGS="$FLAGS --allow-unsolved"
[ -n "$DEPTHMAX" ] && FLAGS="$FLAGS --depth-max $DEPTHMAX"

# NOTHING SAVES A TABLE ANY MORE, and the reason is worth writing down.
#
# tt_save runs at the END of a code path, so it fired ONLY on normal completion --
# which is exactly when the table is worthless: a finished run's CSV marks its work
# done, so re-running the same settings resumes, finds nothing to do, and exits
# without ever reading it.  The case where a warm table WOULD pay -- an interrupted
# run -- saved nothing, because there is no signal handler and Ctrl-C never reaches
# that line.  So the flag was backwards.
#
# MEASURED 2026-09-09: 302 of these snapshots had accumulated at 8 GB each, 728 GB
# in total, which was 79% of the machine's disk and had filled it to the point that
# nothing could write.  One of them was an 8 GB table beside a 4 KB result from a
# run that took 2 SECONDS.  The cost multiplies because each (settings) combination
# gets its own directory and its own table, so a sweep over ~20 values of K leaves
# ~160 GB for one word length.
#
# The genuinely long sweeps -- run-sweep.sh, run-ans-sweep.sh, run-hard-sweep.sh --
# never passed --tt-save at all: they snapshot the LIVE table with tools/ttdump.py,
# which is the mechanism that actually survives a kill.  Use that if a warm table is
# ever wanted here.
#
# --tt-load stays: it costs nothing, and a table created deliberately (by hand or by
# the tt* tools) is still worth warming from.  With nothing writing one
# automatically, WARM is simply empty.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle W-to-S sweep (depth $DEPTH, $FLAGS) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/strturns --sweep \
    --depth "$DEPTH" $FLAGS \
    --out "$OUT" \
    --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
