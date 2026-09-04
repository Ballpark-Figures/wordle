#!/bin/bash
# Start the ANSWER-GUESSES / ALL-WORD-ANSWERS sweep ATTACHED, live in this terminal.
#
#     bash solver/run-ansall-sweep.sh --depth 7                 # from math/, or anywhere
#     bash solver/run-ansall-sweep.sh --depth 8 --optimal-only
#     bash solver/run-ansall-sweep.sh --depth 7 -k 50
#
# WHAT THIS SOLVES, precisely:
#
#   Minimise the TOTAL guesses summed over all 12972 legal words as ANSWERS,
#   where the only legal GUESSES are the 2315 mystery words, SUBJECT TO
#   resolving every answer within --depth guesses.
#
# THE SCORING RULE FOR AN UNGUESSABLE ANSWER.  10657 of the 12972 answers are
# not in the guess list, so they can never be played.  Those are charged
# "narrow the candidates down to that one word, then add one" -- a PHANTOM final
# guess standing in for the naming move.  The 2315 answers that ARE legal
# guesses are charged normally: they must actually be played to be won.  That is
# what --phantom-final selects; the two rules coincide arithmetically at a
# singleton, so nothing else in the recursion changes.
#
# THE CAP BINDS, AND IS PART OF THE OBJECTIVE -- which is why --depth is
# REQUIRED and why every depth gets its OWN CSV.  A depth-7 pass and a depth-8
# pass are different quantities and must never share a file or seed each other.
# Normal mode's "any opener can follow SALET's tree afterwards" argument is
# unavailable here twice over: the answer set is the 12972, not the 2315, and
# SALET is not even a legal guess.  The all-words cell (12972 guesses AND 12972
# answers) already needs depth 7; this one has a strictly weaker guess set, so
# expect 7 to be tight at best.  INFEASIBLE is an expected result.  Report any
# number as optimal SUBJECT TO the stated guarantee, never as minimum expected
# guesses.
#
# --optimal-only reports THE optimal opener and merely bounds the rest, which is
# what makes a 12972-answer problem tractable; without it this is a full
# per-opener sweep over the 2315 openers and is far more expensive.
# -k K restricts branching to the K evenest splits: an UPPER BOUND, not an
# optimum -- "best found within the restricted branching".
#
# PREREQUISITE: the SQUARE pattern matrix, not the default one.  The answer set
# is guess.txt, so the matrix must be 12972 x 12972 before --guess-list compacts
# its rows down to the 2315.
#     python3 build_patterns.py --full      # from math/, ~18s, 168 MB
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.
# Ctrl-C stops it; re-running resumes from the CSV.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
DEPTHMAX=""      # empty = pin --depth; set = escalate up to this
OPTONLY=0
TOPK=0
THREADS=18
TTBITS=28

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)        DEPTH="$2";    shift 2 ;;
        --depth-max)    DEPTHMAX="$2"; shift 2 ;;
        --optimal-only) OPTONLY=1;     shift 1 ;;
        -k|--topk)      TOPK="$2";     shift 2 ;;
        --threads)      THREADS="$2";  shift 2 ;;
        --tt-bits)      TTBITS="$2";   shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-ansall-sweep.sh --depth <d> [--optimal-only] [-k K]" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac

cd "$MATH" || exit 1

GUESSES=data/shared/words/mystery.txt
ANSWERS=data/shared/words/guess.txt
PATS=data/local/patterns/patterns_full.npy
LOC=data/local/ansall
OUTDIR=data/shared/ansall

[ -x ./solver/optturns ] || { echo "no solver binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f "$GUESSES" ] || { echo "no guess list at $GUESSES" >&2; exit 1; }
[ -f "$ANSWERS" ] || { echo "no answer list at $ANSWERS" >&2; exit 1; }
[ -f "$PATS" ] || {
    echo "no square pattern matrix at $PATS" >&2
    echo "build it first:  python3 build_patterns.py --full" >&2
    exit 1
}

if pgrep -x optturns >/dev/null; then
    echo "optturns is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "NB every sweep uses this same binary name -- check which one:" >&2
    echo "  ps -Ao pid,command | grep optturns" >&2
    exit 1
fi

# EVERY (depth, K, mode) COMBINATION GETS ITS OWN FILES.  Each is a different
# objective or a different search space, so sharing a CSV would interleave
# incomparable totals and let a resume seed one run from another's numbers.
TAG=d$DEPTH
[ "$TOPK" -gt 0 ] && TAG=${TAG}_k$TOPK
if [ "$OPTONLY" -eq 1 ]; then
    OUT=$OUTDIR/optimal_$TAG.csv
    LOC=$LOC/optimal_$TAG
else
    OUT=$OUTDIR/opener_totals_$TAG.csv
    LOC=$LOC/$TAG
fi

mkdir -p "$OUTDIR" "$LOC"

WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

KFLAG=""
[ "$TOPK" -gt 0 ] && KFLAG="--topk $TOPK"
OFLAG=""
[ "$OPTONLY" -eq 1 ] && OFLAG="--optimal-only"
DMFLAG=""
[ -n "$DEPTHMAX" ] && DMFLAG="--depth-max $DEPTHMAX"

# BSD date has no -Is; this form works on both macOS and Linux. inflight.py parses
# this timestamp to find the run boundary, so an empty one breaks its run detection.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle ANSWER-GUESSES sweep (2315 guesses, 12972 answers, depth $DEPTH, topk=$TOPK, optimal-only=$OPTONLY) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/optturns --sweep $OFLAG \
    --guess-list "$GUESSES" \
    --answer-list "$ANSWERS" \
    --patterns "$PATS" \
    --phantom-final \
    --out "$OUT" \
    --depth "$DEPTH" $DMFLAG $KFLAG \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
