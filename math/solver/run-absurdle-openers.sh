#!/bin/bash
# Stage 2 of the Absurdle search, ATTACHED, with live output in this terminal.
#
#     bash solver/run-absurdle-openers.sh                # from math/, or anywhere
#     bash solver/run-absurdle-openers.sh --limit 200    # a prefix of the order
#
# WHAT THIS COMPUTES, precisely:
#
#   For each of the 12972 legal openers, whether a 4-GUESS WIN exists after it --
#   4 being the floor proved by tools/absurdle_shortest.py on our lists. The
#   openers answering yes are exactly those TIED for optimal. One witness
#   continuation is reported per opener; enumerating every tied sequence is a
#   later stage.
#
# USE THIS RATHER THAN CALLING THE TOOL DIRECTLY. It sets --out, so the run
# cannot print its answer and save nothing, and tees a log. The tool REFUSES to
# start without --out for the same reason.
#
# Resumable: one CSV row per opener, flushed as it is decided, and a re-run skips
# the words already there. Ctrl-C costs at most the opener in flight.
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

if pgrep -f absurdle_openers.py >/dev/null; then
    echo "absurdle_openers.py is already running (pid $(pgrep -f absurdle_openers.py | tr '\n' ' '))." >&2
    echo "  ps -Ao pid,command | grep absurdle_openers" >&2
    exit 1
fi

OUTDIR=data/shared/absurdle
LOC=data/local/absurdle
OUT=$OUTDIR/openers_win4.csv
mkdir -p "$OUTDIR" "$LOC"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] absurdle stage 2: openers admitting a 4-guess win" \
    | tee -a "$LOC/openers_win4.log"

python3 tools/absurdle_openers.py --out "$OUT" "$@" 2>&1 | tee -a "$LOC/openers_win4.log"
