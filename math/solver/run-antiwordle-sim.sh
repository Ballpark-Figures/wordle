#!/bin/bash
# Sweep every legal OPENER, measuring antiwordle length under RANDOM play.
# Attached, with live output in this terminal.
#
#     bash solver/run-antiwordle-sim.sh -t 200                 # from math/, or anywhere
#     bash solver/run-antiwordle-sim.sh -t 200 --limit 500      # a cheap partial run
#     bash solver/run-antiwordle-sim.sh -t 5000 \
#         --openers-from data/shared/antiwordle/sim.t200.s0.csv --top 200
#
# WHAT THIS MEASURES, precisely: for each of the 12972 legal opening words, the MEAN
# guesses taken by a player who opens with it and then plays UNIFORMLY AT RANDOM
# among the legal words, over -t games with the answer drawn uniformly from the 2315.
# The count includes the guess that lands on the answer.
#
# THE PLAYER KNOWS NOTHING. It does not know the answer and does not consult the
# answer list, so it can end a game by stumbling onto the answer. That is the point
# of this measure -- it is a FLOOR, not a strategy. Real play is longer, because a
# real player deliberately guesses words that cannot be the answer; and the
# clairvoyant maxima from run-antistall-sweep.sh are longer still. Do not put the
# three in one table.
#
# IT IS A MONTE CARLO ESTIMATE. Every row carries a standard error, and two openers
# closer than a couple of SEs have not been shown to differ. With 12972 of them, the
# top of a small -t sweep is mostly sampling noise: treat it as a SHORTLIST and
# re-run its head with many more trials via --openers-from. -t is required for that
# reason -- it sets the precision, which is what the result means.
#
# Results append to a COMMITTED CSV whose name carries the TRIALS and SEED, because
# those define the experiment: the same pair reproduces the same file, a different
# seed is a different sample and gets its own. Rows are flushed as each opener
# finishes, so a Ctrl-C keeps everything measured and a re-run skips it.
#
# COMMIT THE CSV. data/shared is the committed, synced location by convention, but
# writing there does not commit it -- and until it is committed a long run is one
# cleanup away from gone, with no history to recover it from.
#
# RESULTS ARE FOR OUR WORD LISTS: openers and later guesses from the 12972
# guess.txt, answers from the 2315 mystery.txt. antiwordle.com's dictionary is not
# ours, so these are facts about OUR lists.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' first" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

# TRIALS and SEED name the file: they are what makes a row reproducible, so two
# runs at different precision can never interleave into one CSV.  Scanned by INDEX
# rather than with shift, so the arguments survive to be passed through.  (Indexed
# arrays are bash 3.2 clean; associative ones are not -- macOS ships bash 3.2.)
ARGS=("$@")
TRIALS=""
SEED=0
TAG=""
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        -t|--trials)     TRIALS="${ARGS[$((i + 1))]}" ;;
        --seed)          SEED="${ARGS[$((i + 1))]}" ;;
        --openers-from)  TAG="$TAG.refine" ;;
    esac
    i=$((i + 1))
done
[ -n "$TRIALS" ] || { echo "-t (trials per opener) is required" >&2; exit 1; }

OUTDIR=data/shared/antiwordle
LOC=data/local/antiwordle
OUT="$OUTDIR/sim.t${TRIALS}.s${SEED}${TAG}.csv"
LOG="$LOC/sim.t${TRIALS}.s${SEED}${TAG}.log"
mkdir -p "$OUTDIR" "$LOC"

guard_output antiwordle_sim_run.py "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] antiwordle random-play opener sweep -> $OUT" \
    | tee -a "$LOG"

# `${ARGS[@]+...}` guards the empty-array-under-set-u abort on macOS bash 3.2.
python3 tools/antiwordle_sim_run.py --out "$OUT" ${ARGS[@]+"${ARGS[@]}"} 2>&1 \
    | tee -a "$LOG"
