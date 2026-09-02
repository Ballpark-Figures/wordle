#!/bin/bash
# Stage 2 of the Absurdle search, ATTACHED, with live output in this terminal.
#
#     bash solver/run-absurdle-openers.sh                # from math/, or anywhere
#     bash solver/run-absurdle-openers.sh --order asc    # likely optima first
#     bash solver/run-absurdle-openers.sh --limit 200    # a prefix of the order
#
# WHAT THIS COMPUTES, precisely:
#
#   Which of the 12972 legal openers still admit a 4-GUESS WIN -- 4 being the
#   floor proved by tools/absurdle_shortest.py on our lists. Those openers are
#   exactly the ones TIED FOR OPTIMAL, and they are the only thing the committed
#   output holds. One witness continuation each; every tied SEQUENCE is a later
#   stage.
#
# USE THIS RATHER THAN CALLING THE TOOL DIRECTLY. It sets --out, so the run
# cannot print its answer and save nothing, and tees a log. The tool REFUSES to
# start without --out for the same reason.
#
# TWO FILES. The committed one holds only the optima. The gitignored checkpoint
# holds every opener decided so far with its verdict, which is what makes the run
# resumable -- and the committed file is rebuilt from it at every startup, so
# deleting it costs nothing.
#
# Resumable per opener: a Ctrl-C costs at most the opener in flight.
#
# --order desc (the default) visits the openers that shrink the candidate set
# LEAST first. Those are the cheap ones -- few of their second guesses get under
# the 238 cutoff, so the scan cuts out early -- but also the ones least likely to
# be optimal, so early progress is fast and mostly negative. --order asc puts the
# likely optima first instead. Neither changes the finished list.
#
# RESULTS ARE FOR OUR WORD LISTS, which are NOT verified to be Absurdle's.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1

[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' first" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

OUTDIR=data/shared/absurdle
LOC=data/local/absurdle
OUT=$OUTDIR/openers_optimal.csv
CHECK=$LOC/openers_checkpoint.csv
mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output absurdle_openers.py "$CHECK" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] absurdle stage 2: openers tied for optimal" \
    | tee -a "$LOC/openers.log"

python3 tools/absurdle_openers.py --out "$OUT" --checkpoint "$CHECK" "$@" \
    2>&1 | tee -a "$LOC/openers.log"
