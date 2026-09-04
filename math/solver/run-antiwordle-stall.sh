#!/bin/bash
# The antiwordle STALLING ENDGAME, per answer word, ATTACHED with live output.
#
#     bash solver/run-antiwordle-stall.sh                     # from math/, or anywhere
#     bash solver/run-antiwordle-stall.sh --limit 50          # a prefix, to price it
#     bash solver/run-antiwordle-stall.sh --guess-list mystery
#     bash solver/run-antiwordle-stall.sh --max-nodes 2000000
#
# WHAT THIS COMPUTES, precisely: for each of the 2315 answers, the longest run of
# legal guesses before the answer must be named -- the |S| = 1 endgame, where the
# word is already known so every reply is determined and "survive longest" is an
# exact longest path over the constraint DAG. The count INCLUDES the final forced
# naming move. There is no depth cap in the search, because antiwordle has none.
#
# THIS IS NOT THE GAME'S VALUE. It assumes the answer is known from move one, so
# it is an UPPER BOUND on what that answer can extract from real play, where the
# opening is a max-expectimax over an unknown word. Never average these and call
# the result "expected guesses in antiwordle".
#
# USE THIS RATHER THAN CALLING THE TOOL DIRECTLY. It sets --out, so a multi-hour
# run cannot print its answer and save nothing, and tees a log. The tool REFUSES
# to start without --out or an explicit --no-out for the same reason.
#
# Each (guess list, --after) pair is a DIFFERENT quantity and gets its own CSV.
# Resumable: one row per answer, flushed as it lands, and a re-run skips the
# answers already there. Ctrl-C costs at most the answer in flight.
#
# RESULTS ARE FOR OUR WORD LISTS, which are NOT verified to be antiwordle.com's --
# and the stalling words are the junk most likely to differ between them.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' first" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

# The output name carries every knob that changes WHAT is computed, so two runs
# under different settings can never interleave rows into one file.  Scanned by
# INDEX rather than with shift, so the arguments survive to be passed through.
# (Indexed arrays are bash 3.2 clean; associative ones are not -- macOS ships
# bash 3.2, so `declare -A` here would break the Mac and work on WSL.)
ARGS=("$@")
TAG=""
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        --guess-list) TAG="$TAG.${ARGS[$((i + 1))]}" ;;
        --after)      TAG="$TAG.after-$(echo "${ARGS[$((i + 1))]}" | tr ' ' '-')" ;;
    esac
    i=$((i + 1))
done

OUTDIR=data/shared/antiwordle
LOC=data/local/antiwordle
OUT="$OUTDIR/stall${TAG}.csv"
LOG="$LOC/stall${TAG}.log"
mkdir -p "$OUTDIR" "$LOC"

guard_output antiwordle_stall.py "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] antiwordle stall sweep -> $OUT" | tee -a "$LOG"
# `${ARGS[@]+...}` is not decoration: under `set -u`, bash 3.2 -- which is what
# macOS ships -- treats a bare "${ARGS[@]}" on an EMPTY array as an unbound
# variable and aborts, so the no-argument form documented above would die here.
python3 tools/antiwordle_stall.py --out "$OUT" ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee -a "$LOG"
