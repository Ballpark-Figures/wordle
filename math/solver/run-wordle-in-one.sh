#!/bin/bash
# Break every "Wordle in One" down by tile composition, attached, with live
# output in this terminal.
#
#     bash solver/run-wordle-in-one.sh --guesses answers   # from math/, or anywhere
#     bash solver/run-wordle-in-one.sh --guesses all
#
# WHAT THIS COMPUTES, precisely:
#
#   A "Wordle in One" is a feedback ROW that names its answer outright -- a
#   guess and a pattern that exactly ONE of the 2315 mystery answers produces.
#   Seeing that row, the answer is forced.  For every (greens, yellows) tile
#   composition the tool reports how many such games exist AND what FRACTION of
#   the rows of that shape they are.
#
#   THE RATE IS PAIR-WEIGHTED (the user's call, 2026-09-08): the denominator of
#   a cell is every (guess, answer) PAIR whose row has that composition, so pct
#   answers "I played a word and saw this many greens and yellows -- how often
#   is the answer already forced?", with the answer uniform over the 2315.  It
#   is NOT the fraction of DISTINCT (guess, pattern) rows of that shape that are
#   singletons, which weights a 2-answer bucket like a 300-answer one and is a
#   different number.  Do not put the two in one table.
#
#   THE GUESS SET IS PART OF THE QUESTION.  --guesses answers plays only the
#   2315 mystery words (the original call: "every singleton produced by every
#   answer word, not all guesses"); --guesses all plays any of the 12972 legal
#   words.  Two different quantities over the same answer set, so each writes
#   its OWN files and their numbers must never share a table.
#
#   The all-green row is a singleton that tells you nothing you did not already
#   know by typing the word.  Its denominator is exactly the 2315 self-pairs, so
#   its 100% is arithmetic, not a measurement -- read pct_nowin there.
#
#   Nothing here searches or samples: the whole thing is a pure function of the
#   committed word lists and the pattern matrix, so it is exact and a re-run
#   reproduces its files byte for byte.
#
# USE THIS RATHER THAN CALLING tools/wordle_in_one.py DIRECTLY.  It forwards the
# guess set EXPLICITLY (the script itself refuses to run without it, so the one
# decision has one owner) and tees a log naming the run.
#
# Outputs under data/shared/singletons/:
#   --guesses answers : wordle_in_one_games.csv, wordle_in_one_breakdown.csv
#   --guesses all     : wordle_in_one_games_allguesses.csv.gz,
#                       wordle_in_one_breakdown_allguesses.csv
# Log under data/local/singletons/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# A default a HUMAN reads, forwarded explicitly -- never one the program falls
# back on.  It matches the committed files, which were built this way.
GUESSES=answers

while [ $# -gt 0 ]; do
    case "$1" in
        --guesses) GUESSES="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$GUESSES" in
    answers|all) ;;
    *) echo "--guesses must be 'answers' (the 2315) or 'all' (the 12972)" >&2
       exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

MARKER="wordle_in_one.py --guesses $GUESSES"
RUNNING=$(pgrep -f -- "$MARKER" 2>/dev/null | tr '\n' ' ')
if [ -n "$RUNNING" ]; then
    echo "REFUSING: the same run is already going (pid $RUNNING)." >&2
    echo "  Two copies would write the same files at once." >&2
    exit 1
fi

LOC=data/local/singletons
mkdir -p "$LOC" data/shared/singletons

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle-in-one breakdown, guesses=$GUESSES" \
    | tee -a "$LOC/wordle_in_one_$GUESSES.log"

"$PY" -u tools/wordle_in_one.py --guesses "$GUESSES" 2>&1 \
    | tee -a "$LOC/wordle_in_one_$GUESSES.log"
