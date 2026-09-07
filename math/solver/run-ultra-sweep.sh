#!/bin/bash
# Start the ULTRA HARD MODE sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-ultra-sweep.sh --depth 6 -k 100      # best opener, top-k 100
#     bash solver/run-ultra-sweep.sh --depth 8 -k 50
#
# WHAT THIS SOLVES: minimise the TOTAL guesses over the 2315 mystery answers,
# where every guess -- the opener AND every follow-up -- must itself still be
# CONSISTENT with every clue seen so far (a word the answer could still be),
# SUBJECT TO resolving every answer within --depth.  This is STRICTER than hard
# mode: hard mode only forces greens to be repeated in place and yellow letters
# to reappear somewhere; ultra mode also honours greys (exact letter counts and
# forbidden positions) and yellow POSITION exclusions.  So the legal guess set at
# any node is exactly the set of the 12972 words still consistent with the clues.
#
# NOT COMPARABLE WITH A hardturns OR optturns NUMBER.  A strictly smaller legal
# set can only raise the total, so an ultra total is >= the hard-mode one, which
# is >= the normal one -- three different objectives, not one at three settings.
# Do not put them in one table.
#
# --depth IS REQUIRED AND IT BINDS.  Like hard mode, ultra mode has genuine
# INFEASIBLE openers -- "follow SALET's tree afterwards" is illegal when the
# follow-up must stay consistent -- so the cap is part of the objective and a
# depth-6 pass and a depth-7 pass are DIFFERENT QUANTITIES with different CSVs.
# Unlike hard mode this sweep does NOT escalate the cap; it is pinned to --depth.
#
# --topk K restricts branching to the K evenest splits AT EVERY BRANCHING POINT
# INCLUDING THE ROOT, so -k 1 examines exactly one opener -- the best of the
# 12972 by root sum of squared bin sizes -- and the total is an UPPER BOUND, the
# best of the K examined.  There is no opener literal anywhere; the ranking picks
# it.  Each K is a different strategy and gets its own CSV and its own TT salt.
# The exact solver (no --topk) is correct but slow here, because the legal set is
# large near the root -- topk is the intended mode, hence this wrapper requires it.
#
# EVERY OPENER PRINTS (--print-openers): each of the K openers gets a terminal
# line as it finishes, not just the ones that improve on the running best.
#
# NO TREES FROM THIS RUN.  --optimal-only never calls write_tree, so the winner's
# tree needs a follow-up at the SAME depth and K:
#     ./solver/ultraturns --opener <winner> --depth <D> --topk <K> \
#         --trees data/shared/ultraturns/trees
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
TOPK=""
THREADS=18
TTBITS=27

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-ultra-sweep.sh --depth <d> -k <K>" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac
case "$TOPK" in
    ''|*[!0-9]*|0)
        echo "usage: bash solver/run-ultra-sweep.sh --depth <d> -k <K>" >&2
        echo "-k must be a positive number (topk is the intended, tractable mode)" >&2
        exit 1 ;;
esac

cd "$MATH" || exit 1
[ -x ./solver/ultraturns ] || { echo "no ./solver/ultraturns -- run 'sh build.sh' in solver/" >&2; exit 1; }

TAG=d${DEPTH}_k${TOPK}
OUTDIR=data/shared/ultraturns
LOC=data/local/ultraturns/$TAG
OUT=$OUTDIR/optimal_$TAG.csv
mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output ultraturns "$OUT" || exit 1

FLAGS="--sweep --optimal-only --topk $TOPK --print-openers"
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle ULTRA-hard sweep (depth $DEPTH, $FLAGS) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/ultraturns --depth "$DEPTH" $FLAGS \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM --tt-save "$LOC/tt.bin" \
    2>&1 | tee -a "$LOC/sweep.log"
