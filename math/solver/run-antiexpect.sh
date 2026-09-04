#!/bin/bash
# Antiwordle: search for the strategy maximising EXPECTED TURNS, top-K per node.
# Attached, with live output in this terminal.
#
#     bash solver/run-antiexpect.sh -k 5 --rank data/shared/antiwordle/sim.t1000.s0.csv
#     bash solver/run-antiexpect.sh -k 10 --rank <sweep csv> --tt-bits 28
#     bash solver/run-antiexpect.sh -k 5 --rank-none          # the baseline
#
# WHAT THIS COMPUTES: a STRATEGY played WITHOUT knowing the answer, scored as the
# EXPECTED number of turns averaged over all 2315 answers. That is a different
# quantity from either sibling and the three never belong in one table:
#
#   run-antistall-sweep.sh   fixes an answer, finds its LONGEST game clairvoyantly.
#                            A per-answer maximum, and an upper bound on real play.
#   run-antiwordle-sim.sh    plays uniformly at random. A floor, not a strategy.
#   THIS                     the quantity a player actually wants, in between.
#
# -k IS PART OF THE OBJECTIVE, not a speed knob. Only the K best-scoring legal words
# are examined at each node -- the K best of what is legal THERE, never a global
# top-K filtered by what happens to still be legal. Restricting the search can only
# miss a better strategy, so the result is a REAL ACHIEVABLE STRATEGY and a LOWER
# BOUND on the optimum. Report it as "best found examining K guesses per node".
# A different K is a different quantity, so K is in the output filename.
#
# --rank NAMES THE RANKING, and is required (or --rank-none). Which K guesses get
# examined depends entirely on it, so leaving it implicit would make a result
# untraceable to the ordering that produced it. The natural input is a random-play
# opener sweep (run-antiwordle-sim.sh), whose `opener` and `mean` columns this
# reads. --rank-none ranks alphabetically: a BASELINE to measure a real ranking
# against, never a strategy.
#
# COMMIT THE CSV. data/shared is the committed, synced location by convention, but
# writing there does not commit it -- and until it is committed a long run is one
# cleanup away from gone, with no history to recover it from.
#
# RESULTS ARE FOR OUR WORD LISTS, which are not antiwordle.com's.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -x ./solver/antiexpect ] || {
    echo "no solver/antiexpect -- run 'sh build.sh' in solver/" >&2
    exit 1
}
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' first" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

# K and the RANKING name the file: both change WHAT is computed, so two runs under
# different settings can never interleave rows.  Scanned by INDEX rather than with
# shift, so the arguments survive to be passed through.  (Indexed arrays are bash
# 3.2 clean; associative ones are not -- macOS ships bash 3.2.)
ARGS=("$@")
K=""
TAG=""
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        -k)           K="${ARGS[$((i + 1))]}" ;;
        --rank)       TAG=".$(basename "${ARGS[$((i + 1))]}" .csv)" ;;
        --rank-none)  TAG=".ranknone" ;;
        --answers)    TAG="$TAG.a${ARGS[$((i + 1))]}" ;;
    esac
    i=$((i + 1))
done
[ -n "$K" ] || { echo "-k (guesses examined per node) is required" >&2; exit 1; }

OUTDIR=data/shared/antiwordle
LOC=data/local/antiwordle
OUT="$OUTDIR/expect.k${K}${TAG}.csv"
LOG="$LOC/expect.k${K}${TAG}.log"
mkdir -p "$OUTDIR" "$LOC"

guard_output antiexpect "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] antiwordle expected-turns search -> $OUT" \
    | tee -a "$LOG"

# `${ARGS[@]+...}` guards the empty-array-under-set-u abort on macOS bash 3.2.
./solver/antiexpect --out "$OUT" ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee -a "$LOG"
