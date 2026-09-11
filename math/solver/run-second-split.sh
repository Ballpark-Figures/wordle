#!/bin/bash
# The gap to OPTIMAL for one strategy, split by grey count AND by CAUSE.
#
#     bash solver/run-second-split.sh --opener slant \
#         --second e3=cripe --second e4=drice --second e5=drice
#
# tools/secondloss.py answers "how much does each grey count cost us"; this
# answers "and WHY".  Within each grey count the gap is split in two:
#
#   THE RANDOM TAIL   what playing at random after the second word costs, with
#                     the WORD HELD FIXED -- so it is the follow-up's fault
#   THE WORD CHOICE   what committing to that word costs, with the CONTINUATION
#                     HELD OPTIMAL -- so it is the word's fault
#
# The two sum to the whole gap, exactly.  Below the threshold no word is
# committed, so the whole gap there is the random tail's and the word column is
# zero by construction, not by rounding.
#
# ALL THREE QUANTITIES ARE EXACT -- no simulation.  The strategy's own value is
# the same recursion solver/secondexact.c uses; "with the word, played
# optimally" is a real search over the states that word leaves, which is
# affordable only because those states are tiny and guesses that partition them
# identically are interchangeable.
#
# ONE ASYMMETRY, STATED BECAUSE IT IS REAL: the optimal column is the CAPPED
# optimum -- the committed tree, minimum guesses subject to solving everything
# within six -- while the other two are uncapped.  So the word's share is if
# anything understated.  The run says so if any bucket comes out with the
# with-word value BELOW optimal, which would mean the cap is binding there.
#
# Output: data/shared/secondloss/, log under data/local/secondloss/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OPENER=""
SECONDS_ARG=""
MINGRAYS=3
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --opener)     OPENER="$2"; shift 2 ;;
        --second)     SECONDS_ARG="$SECONDS_ARG --second $2"; shift 2 ;;
        --min-grays)  MINGRAYS="$2"; shift 2 ;;
        --dry-run)    DRYRUN=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

[ -n "$OPENER" ] || { echo "--opener is required" >&2; exit 1; }
[ -n "$SECONDS_ARG" ] || {
    echo "at least one --second GROUP=WORD is required: the split is about which" >&2
    echo "  word was committed to, so there is nothing to attribute without one." >&2
    exit 1; }

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

LABEL=$(echo "$SECONDS_ARG" | tr -d ' ' | sed 's/--second//g; s/=/-/g; s/\([a-z]\)e[0-9]-/\1./g')
STEM="split_${OPENER}$(echo "$SECONDS_ARG" | sed 's/ --second [a-z0-9]*=/_/g' | tr -d ' ')"
OUTDIR=data/shared/secondloss
LOC=data/local/secondloss
OUT="$OUTDIR/$STEM.csv"

echo "EV-loss split by cause"
echo "  opener  $OPENER"
echo "  words  $SECONDS_ARG"
echo "  out     $OUT"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    exit 0
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output secondsplit.py "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] second-split $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/secondsplit.py --opener "$OPENER" $SECONDS_ARG \
    --min-grays "$MINGRAYS" --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
