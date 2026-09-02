#!/bin/bash
# Start the S -> A (or S -> W) sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-strguess-sweep.sh --depth 6                    # S -> A, 2315 answers
#     bash solver/run-strguess-sweep.sh --depth 7 --answers guess    # S -> W, 12972 answers
#     bash solver/run-strguess-sweep.sh --depth 6 -k 20
#
# WHAT THIS SOLVES: minimise the TOTAL guesses over the answer list, where the
# codebreaker may play ANY of the 11881376 length-5 strings, SUBJECT TO resolving
# every answer within --depth.  No phantom rule: the guess set contains the answer
# set outright, so every answer wins by being played.
#
# --topk K restricts branching to the K evenest splits AT EVERY BRANCHING POINT
# INCLUDING THE ROOT, so -k 1 examines exactly one opener -- the best of all
# 11881376 by root sum of squares -- and the result is an UPPER BOUND, the best of
# the K examined.  There is no opener literal anywhere; the ranking picks it.
#
# THE FREE CHECK.  The guess set is a superset of the 12972 words, so for the
# 2315-answer run the exact optimum can never exceed optturns' 7920.  The solver
# prints that comparison itself.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
DEPTHMAX=""
TOPK=1
ANSWERS=mystery
THREADS=18
TTBITS=26

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)     DEPTH="$2";    shift 2 ;;
        --depth-max) DEPTHMAX="$2"; shift 2 ;;
        -k|--topk)   TOPK="$2";     shift 2 ;;
        --answers)   ANSWERS="$2";  shift 2 ;;   # mystery | guess
        --threads)   THREADS="$2";  shift 2 ;;
        --tt-bits)   TTBITS="$2";   shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-strguess-sweep.sh --depth <d> [-k K] [--answers mystery|guess]" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac
case "$ANSWERS" in
    mystery|guess) ;;
    *) echo "--answers must be mystery (2315) or guess (12972)" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
[ -x ./solver/strguess ] || { echo "no ./solver/strguess -- run 'sh build.sh' in solver/" >&2; exit 1; }

if pgrep -x strguess >/dev/null; then
    echo "strguess is already running (pid $(pgrep -x strguess | tr '\n' ' '))." >&2
    exit 1
fi

TAG=${ANSWERS}_d$DEPTH
[ -n "$DEPTHMAX" ] && TAG=${TAG}-$DEPTHMAX
TAG=${TAG}_k$TOPK

OUTDIR=data/shared/strguess
LOC=data/local/strguess/$TAG
OUT=$OUTDIR/opener_totals_$TAG.csv
mkdir -p "$OUTDIR" "$LOC"

FLAGS="--topk $TOPK --answers data/shared/words/$ANSWERS.txt"
[ -n "$DEPTHMAX" ] && FLAGS="$FLAGS --depth-max $DEPTHMAX"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle S-to-${ANSWERS} sweep (depth $DEPTH, $FLAGS)" \
    | tee -a "$LOC/sweep.log"

./solver/strguess --depth "$DEPTH" $FLAGS \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    2>&1 | tee -a "$LOC/sweep.log"
