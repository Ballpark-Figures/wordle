#!/bin/bash
# Start the S -> S sweep ATTACHED: every 26**5 string is both a legal guess AND a
# possible answer.
#
#     bash solver/run-strsts-sweep.sh --depth 10
#     bash solver/run-strsts-sweep.sh --depth 9 --depth-max 20 -k 3
#
# WHAT THIS SOLVES: minimise the TOTAL guesses over all 11881376 length-5 strings,
# where any string may be played, SUBJECT TO resolving every answer within --depth.
# No phantom rule -- the guess set contains the answer set, so every answer wins by
# being played.
#
# HOW THE GUESS SPACE IS HANDLED.  11881376 guesses can be neither listed nor have
# their atoms precomputed (208 GB).  They do not need to be: guesses in one
# symmetry orbit have isomorphic partitions, so one representative per class is
# profiled.  MEASURED class counts: 7 at the root, 36 down an all-grey line, and
# 173-174 once a green pins a position -- hundreds, not millions, at every node.
#
# DEPTH IS AT LEAST 9, AND THAT IS PUBLISHED.  Li and Zhu, "Playing Mastermind with
# Wordle-like Feedback" (Amer. Math. Monthly 131(5), 2024, arXiv:2209.13147) define
# F(k,n) as the fewest guesses needed with k letters and n positions under exactly
# Wordle's feedback -- THIS cell, verbatim -- and prove
# floor(k/n) + n - 1 <= F(k,n) <= floor(k/n) + n when n does not divide k.  At
# k=26, n=5 that is 9 <= F(26,5) <= 10.  So --depth below 9 cannot resolve every
# answer, and F is a WORST CASE: the paper says nothing about averages.
#
# --topk K is an UPPER BOUND, best of the K classes examined; the root is a
# branching point too, so -k 1 examines exactly one opener.  --small-n N profiles
# small states by direct patterns instead of 243 atom meets, which is where most
# of the speed comes from -- leave it on.
#
# Output is tee'd; re-running resumes from the CSV and reloads the table.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""; DEPTHMAX=""; TOPK=1; SMALLN=512; THREADS=18; TTBITS=24

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)     DEPTH="$2";    shift 2 ;;
        --depth-max) DEPTHMAX="$2"; shift 2 ;;
        -k|--topk)   TOPK="$2";     shift 2 ;;
        --small-n)   SMALLN="$2";   shift 2 ;;
        --threads)   THREADS="$2";  shift 2 ;;
        --tt-bits)   TTBITS="$2";   shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done
case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-strsts-sweep.sh --depth <d> [--depth-max <d>] [-k K]" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac
if [ "$DEPTH" -lt 9 ]; then
    echo "NOTE: depth $DEPTH is below the proven floor of 9 for this cell" >&2
    echo "      (F(26,5) >= 9, Li and Zhu 2024) -- it CANNOT resolve every answer." >&2
fi

cd "$MATH" || exit 1
[ -x ./solver/strturns ] || { echo "no ./solver/strturns -- run 'sh build.sh' in solver/" >&2; exit 1; }

TAG=d$DEPTH
[ -n "$DEPTHMAX" ] && TAG=${TAG}-$DEPTHMAX
TAG=${TAG}_k${TOPK}_sn${SMALLN}

OUTDIR=data/shared/strsts
LOC=data/local/strsts/$TAG
OUT=$OUTDIR/opener_totals_$TAG.csv
mkdir -p "$OUTDIR" "$LOC"

. "$MATH/solver/_guard.sh"
guard_output strturns "$OUT" || exit 1

FLAGS="--guess-space all --topk $TOPK --allow-unsolved --small-n $SMALLN"
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

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle S-to-S sweep (depth $DEPTH, $FLAGS) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/strturns --sweep --depth "$DEPTH" $FLAGS \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
