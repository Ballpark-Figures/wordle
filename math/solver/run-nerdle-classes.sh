#!/bin/bash
# Collapse the NERDLE answers into commutative equivalence classes -- pass two.
#
#     bash solver/run-nerdle-classes.sh                   # from math/, or anywhere
#     bash solver/run-nerdle-classes.sh --width 6
#
# WHAT THIS COMPUTES, precisely:
#
#   Nerdle accepts a rearrangement of the day's answer as a win -- a SETTING, on
#   by default -- so the answers fall into classes any member of which wins the
#   same day.  ONLY `+` AND `*` COMMUTE: the operator sequence is preserved, and
#   within it the operands joined by `+` permute among themselves and those
#   joined by `*` permute among themselves, so a subtracted term and a divisor
#   stay where they are written.  math/nerdle.py states it exactly.
#
#   `12+34=46` = `34+12=46` and `9-8+7=8` = `7-8+9=8` (the two `+`-signed terms
#   swap while `-8` holds its slot), but NOT `9-8+7=8` = `9+7-8=8` and NOT
#   `12/3/2=2` = `12/2/3=2`.
#
#   DO NOT re-adopt the FAQ's own wording as the test.  "Your guess must still
#   have all the same numbers, the same operators and the same answer" is a
#   NECESSARY condition; read as a SUFFICIENT one it merges `1*2+8=10` with
#   `1*8+2=10`, whose products are `1*2` and `1*8` and which are not
#   rearrangements of each other at all.
#
#   THE CLASS COUNT AND THE ANSWER COUNT ARE DIFFERENT QUANTITIES.  The answer
#   count says what the hidden equation may be as written; the class count says
#   how many DISTINCT puzzles those answers really represent.  Neither
#   substitutes for the other, so never quote one as the other.
#
#   Exact and integral -- no sampling, no seed -- so one width means one file
#   and a re-run reproduces it.  It REQUIRES the answer list for that width;
#   run solver/run-nerdle-answers.sh first if it is missing.
#
# USE THIS RATHER THAN CALLING tools/nerdle_classes.py DIRECTLY.  It sets --out,
# points --answers at the right file, writes a .meta sidecar recording the
# equivalence used, and tees a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8

while [ $# -gt 0 ]; do
    case "$1" in
        --width) WIDTH="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$WIDTH" in
    ''|*[!0-9]*) echo "--width must be a number" >&2; exit 1 ;;
esac
[ "$WIDTH" -ge 3 ] || { echo "--width must be at least 3" >&2; exit 1; }

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/nerdle
LOC=data/local/nerdle
ANSWERS="$OUTDIR/answers_w${WIDTH}.txt.gz"
STEM="classes_w${WIDTH}"
OUT="$OUTDIR/$STEM.txt.gz"
mkdir -p "$OUTDIR" "$LOC"

if [ ! -f "$ANSWERS" ]; then
    echo "no answer list at $ANSWERS" >&2
    echo "  run: bash solver/run-nerdle-answers.sh --width $WIDTH" >&2
    exit 1
fi

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output nerdle_classes.py "$OUT" || exit 1

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle classes $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/nerdle_classes.py --width "$WIDTH" --answers "$ANSWERS" --out "$OUT" \
    2>&1 | tee -a "$LOC/$STEM.log"
