#!/bin/bash
# Start the MASTERMIND-FEEDBACK sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-mm-sweep.sh --depth 8              # the top-k 1 run
#     bash solver/run-mm-sweep.sh --depth 8 -k 20
#     bash solver/run-mm-sweep.sh --depth 8 --guesses mystery   # answers-only guesses
#
# WHAT THIS SOLVES: minimise the TOTAL guesses over the 2315 mystery answers,
# where the codebreaker plays one of the 12972 legal words and the reply is
# MASTERMIND'S PEG COUNTS -- how many letters are right in place (blacks) and how
# many are right in the wrong place (whites) -- SUBJECT TO resolving every answer
# within --depth.  Wordle's per-tile colouring is never shown.
#
# NOT COMPARABLE WITH ANY optturns NUMBER.  Peg feedback is strictly coarser: 20
# outcomes against Wordle's 238, because the colouring says WHICH positions were
# right and the pegs only say HOW MANY.  Every total here is the optimum of a
# different game, not a harder-mode variant of the same one.
#
# --depth IS REQUIRED AND IT BINDS.  optturns' slack default of 6 is not slack
# here -- with at most 19 non-winning bins per guess the tree is deeper -- so a
# depth-7 pass and a depth-9 pass are DIFFERENT QUANTITIES and get different
# CSVs.  The binary refuses to start without it.  An opener that cannot fit the
# cap reports INFEASIBLE, which is a result, not a bug.
#
# --topk K restricts branching to the K evenest splits AT EVERY BRANCHING POINT
# INCLUDING THE ROOT, so -k 1 examines exactly one opener -- the best of the
# 12972 by root sum of squared bin sizes -- and the total is an UPPER BOUND, the
# best of the K examined.  There is no opener literal anywhere; the ranking picks
# it.  Each K is a different strategy and gets its own CSV and its own TT salt.
#
# EVERY OPENER PRINTS.  The wrapper passes --print-openers, so each of the K
# openers gets a terminal line as it finishes -- not just the ones that improve
# on the running best, which is all --optimal-only shows by default.  An opener
# CUT by the incumbent prints too, since it writes no CSV row and would otherwise
# be missing from the printout altogether.
#
# NO TREES FROM THIS RUN.  --optimal-only never calls write_tree, so the winner's
# tree needs a follow-up at the SAME depth:
#     ./solver/mmturns --opener <winner> --depth <D> --trees data/shared/mmturns/trees
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
TOPK=1
GUESSES=guess
THREADS=18
TTBITS=27

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        --guesses) GUESSES="$2"; shift 2 ;;   # guess (12972) | mystery (2315)
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-mm-sweep.sh --depth <d> [-k K] [--guesses guess|mystery]" >&2
        echo "--depth is required and must be a number (the cap IS the objective)" >&2
        exit 1 ;;
esac
case "$TOPK" in
    ''|*[!0-9]*|0) echo "-k must be a positive number" >&2; exit 1 ;;
esac
case "$GUESSES" in
    guess|mystery) ;;
    *) echo "--guesses must be guess (12972) or mystery (2315)" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
[ -x ./solver/mmturns ] || { echo "no ./solver/mmturns -- run 'sh build.sh' in solver/" >&2; exit 1; }

TAG=d${DEPTH}_k${TOPK}
[ "$GUESSES" = mystery ] && TAG=${TAG}_ansonly

OUTDIR=data/shared/mmturns
LOC=data/local/mmturns/$TAG
OUT=$OUTDIR/optimal_$TAG.csv
mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output mmturns "$OUT" || exit 1

FLAGS="--sweep --optimal-only --topk $TOPK --print-openers"
[ "$GUESSES" = mystery ] && FLAGS="$FLAGS --guess-list data/shared/words/mystery.txt"
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

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle MASTERMIND-feedback sweep (depth $DEPTH, $FLAGS) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/mmturns --depth "$DEPTH" $FLAGS \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
