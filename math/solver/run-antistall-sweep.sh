#!/bin/bash
# The antiwordle STALLING ENDGAME for every answer, ATTACHED, live in this terminal.
#
#     bash solver/run-antistall-sweep.sh                    # from math/, or anywhere
#     bash solver/run-antistall-sweep.sh --limit 50         # a prefix, to price it
#     bash solver/run-antistall-sweep.sh --tt-bits 28       # a bigger table
#     bash solver/run-antistall-sweep.sh --guess-list data/shared/words/mystery.txt
#
# WHAT THIS COMPUTES, precisely: for each of the 2315 answers, the longest run of
# legal guesses before the answer must be named, played by someone who knew the
# word from move one. Exact -- no depth cap (antiwordle has none) and no beam.
# The count INCLUDES the final forced naming move.
#
# THIS IS NOT THE GAME'S VALUE. It assumes the answer is known from the start, so
# it is an UPPER BOUND on what that answer can extract from real play, where the
# opening is a search against a word you have not identified yet. Never average
# these and call the result "expected guesses in antiwordle".
#
# USE THIS RATHER THAN CALLING THE BINARY DIRECTLY. It sets --out, so a long run
# cannot print its answer and save nothing, and tees a log. The binary REFUSES to
# start without --out or an explicit --no-out for the same reason.
#
# Each (guess list, --after) pair is a DIFFERENT quantity and gets its own CSV.
# Resumable: one row per answer, flushed as it lands, and a re-run skips what is
# already there. Ctrl-C costs at most the answer in flight.
#
# The Python implementation (tools/antiwordle_stall.py) is the same search and
# stays the REFERENCE -- tools/checkantistall.py diffs the two. It is ~90x slower,
# so use it to check this, not to run sweeps.
#
# RESULTS ARE FOR OUR WORD LISTS, which are NOT verified to be antiwordle.com's --
# and the stalling words are the junk most likely to differ between them.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -x ./solver/antistall ] || {
    echo "no solver/antistall -- run 'sh build.sh' in solver/" >&2
    exit 1
}
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
        --guess-list) TAG="$TAG.$(basename "${ARGS[$((i + 1))]}" .txt)" ;;
        --after)      TAG="$TAG.after-$(echo "${ARGS[$((i + 1))]}" | tr ' ' '-')" ;;
        --no-prune)   TAG="$TAG.unpruned" ;;
    esac
    i=$((i + 1))
done

OUTDIR=data/shared/antiwordle
LOC=data/local/antiwordle
OUT="$OUTDIR/stall${TAG}.csv"
LOG="$LOC/stall${TAG}.log"
mkdir -p "$OUTDIR" "$LOC"

guard_output antistall "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] antistall sweep -> $OUT" | tee -a "$LOG"

# `${ARGS[@]+...}` is not decoration: under `set -u`, bash 3.2 -- which is what
# macOS ships -- treats a bare "${ARGS[@]}" on an EMPTY array as an unbound
# variable and aborts, so the no-argument form documented above would die here.
./solver/antistall --out "$OUT" ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee -a "$LOG"
