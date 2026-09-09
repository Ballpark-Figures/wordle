#!/bin/bash
# Start the WEIGHTED sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-wturns-sweep.sh --weights data/shared/freqsearch/adv_topk1 --depth 6
#     bash solver/run-wturns-sweep.sh --weights ... --depth 6 --opener slate   # price one
#
# WHAT THIS SOLVES.  The answers carry a WEIGHT, and the objective is
#
#     minimise  sum over answers of  w_a * (guesses spent on a)
#     subject to resolving EVERY answer within --depth
#
# reported as `expected` = that total divided by the summed weight.  It exists to
# answer "what does an OPTIMAL guesser spend against these weights?", the
# companion to `math/topk.py`, which is the GREEDY guesser the adversarial search
# (`math/freq_search.py`) tunes those weights against.
#
# --weights TAKES A STEM, not a file: <stem>.txt is the answer list and
# <stem>.weights the weights, both written by tools/freqweights.py.  They must
# AGREE position for position, and the solver checks that they do rather than
# assuming it.
#
# The PATTERN MATRIX for those answer columns is built automatically on the first
# run and cached under data/local/wturns/ -- it is a deterministic 12972 x NA
# derivation of the two lists, so it is regenerable bulk and follows the
# shared/local split rather than being committed beside them.
#
# THE CAP IS PART OF THE OBJECTIVE, so --depth is REQUIRED and every depth gets
# its OWN CSV.  A weighted optimum may deliberately spend a deeper line on a light
# answer to shorten a heavy one, so a depth-6 pass and a depth-7 pass are
# DIFFERENT QUANTITIES -- report a total as an optimum SUBJECT TO a <depth>-guess
# guarantee, never as minimum expected guesses.  INFEASIBLE is an expected result.
#
# NOT COMPARABLE WITH ANY optturns-FAMILY TOTAL, and not with a `topk.py` number
# either.  optturns minimises a COUNT over a different answer set; topk.py reports
# expected guesses OUTRIGHT with no cap.  Three objectives, three tables.
#
# THE OPENER ORDER IS THE WEIGHTED SPLIT SCORE (`--order ssq`): ascending
# sum over losing bins of (bin size x bin weight) -- the expected number of
# candidate WORDS still alive, which is topk.py's own ranking rule.  EVERY opener
# is still examined and the result is still exact; the order only decides WHEN.
# It is the right order for a run that may be stopped early: the openers most
# likely to win are visited first, so a halted run probably already holds the
# optimum -- but it has NOT PROVED it, because that proof needs the ascending
# LOWER-BOUND order (`--order lb`), under which the first opener bounding above
# the incumbent proves the whole tail is worse.  A partial run's leader is
# "the best of those examined so far", stated that way.
#
# EVERY OPENER PRINTS (--print-openers), so the terminal shows progress rather
# than only improvements.
#
# NO TREES FROM THE SWEEP.  --optimal-only never calls write_tree, so the
# winner's tree needs a follow-up at the SAME depth and weights:
#     ./solver/wturns --opener <winner> --depth <D> \
#         --answer-list <stem>.txt --weights <stem>.weights \
#         --patterns <stem>.patterns.npy --trees <dir>
#
# --opener W (repeatable) prices ONE opener exactly instead of sweeping: much
# cheaper, still exact for that opener, and an upper bound on the optimum.  Do
# this before launching the full sweep.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STEM=""
DEPTH=""
THREADS=18
TTBITS=28
OPENERS=""
TAGEXTRA=""

while [ $# -gt 0 ]; do
    case "$1" in
        --weights) STEM="$2";   shift 2 ;;
        --depth)   DEPTH="$2";  shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2"; shift 2 ;;
        --opener)  OPENERS="$OPENERS --opener $2"; shift 2 ;;
        --tag)     TAGEXTRA="_$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$STEM" ]; then
    echo "usage: bash solver/run-wturns-sweep.sh --weights <stem> --depth <d> [--opener W]" >&2
    echo "--weights is required: the weights ARE the objective, so there is no default" >&2
    exit 1
fi
case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-wturns-sweep.sh --weights <stem> --depth <d>" >&2
        echo "--depth is required and must be a number (the cap IS part of the objective)" >&2
        exit 1 ;;
esac

cd "$MATH" || exit 1
[ -x ./solver/wturns ] || { echo "no ./solver/wturns -- run 'sh build.sh' in solver/" >&2; exit 1; }

ANSWERS="$STEM.txt"
WEIGHTS="$STEM.weights"
for f in "$ANSWERS" "$WEIGHTS"; do
    [ -f "$f" ] || { echo "missing $f -- write both with:" >&2
                     echo "  python3 tools/freqweights.py --from <freqsearch csv> --stem $STEM" >&2
                     exit 1; }
done

STEMNAME=$(basename "$STEM")
PATS=data/local/wturns/$STEMNAME.patterns.npy
mkdir -p data/local/wturns
if [ ! -f "$PATS" ]; then
    echo "building the pattern matrix for $ANSWERS (once, ~10s) -> $PATS"
    python3 build_patterns.py --answer-list "$ANSWERS" --out "$PATS" || exit 1
fi
TAG=${STEMNAME}_d${DEPTH}${TAGEXTRA}
OUTDIR=data/shared/wturns
LOC=data/local/wturns/$TAG
mkdir -p "$OUTDIR" "$LOC"

if [ -n "$OPENERS" ]; then
    OUT=$OUTDIR/openers_$TAG.csv
    FLAGS="$OPENERS"
    WHAT="named openers"
else
    OUT=$OUTDIR/optimal_$TAG.csv
    FLAGS="--sweep --optimal-only --order ssq --print-openers"
    WHAT="full sweep, all openers examined, exact"
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wturns "$OUT" || exit 1

# --tt-save is deliberately absent -- see the long note in run-ultra-sweep.sh.
# It fires only on NORMAL completion, exactly when the table is worthless, and
# never on the interrupted run that would pay; 302 such snapshots once filled
# 728 GB of disk.  --tt-load stays, so a table made deliberately (tools/ttdump.py
# on a LIVE run) can still warm this one.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wturns weighted sweep ($WHAT)" \
    | tee -a "$LOC/sweep.log"
echo "  weights $WEIGHTS  answers $ANSWERS  depth $DEPTH  ->  $OUT" \
    | tee -a "$LOC/sweep.log"

./solver/wturns --depth "$DEPTH" $FLAGS \
    --answer-list "$ANSWERS" --weights "$WEIGHTS" --patterns "$PATS" \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
