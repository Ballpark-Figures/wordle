#!/bin/bash
# Filter the enumerated NERDLE guesses down to the legal ANSWERS, attached.
#
#     bash solver/run-nerdle-answers.sh                   # from math/, or anywhere
#     bash solver/run-nerdle-answers.sh --width 6
#
# WHAT THIS COMPUTES, precisely:
#
#   The answers are a strict SUBSET of the guesses -- every answer is something
#   you are allowed to type -- so this reads the pass-one guess list for the
#   same width and keeps the ones satisfying the four ANSWER rules: the right
#   side is a bare number, no digit run begins with a zero (so no leading zeros
#   and no bare `0` anywhere), no unary minus appears, and the left side
#   contains at least one operator.  math/nerdle.py states them as A1-A4 and is
#   the source of truth; read it before quoting any count.
#
#   THE INTERMEDIATE VALUES ARE DELIBERATELY UNCONSTRAINED.  The user settled on
#   2026-09-03 that an answer's left side MAY pass through a negative value
#   (`1-2+3=2`) and MAY pass through a fraction (`1/2*4=2`).  Both stricter
#   readings were live until then and both give a SMALLER set, so a count
#   computed under either is a different quantity -- never quote one as the
#   answer count.
#
#   Equations are counted AS WRITTEN, as in pass one: `12+34=46` and `34+12=46`
#   are two answers.  Collapsing commutative equivalents is pass two.
#
#   The filter is exact and integral -- no sampling, no seed -- so one width
#   means one file and a re-run reproduces it byte for byte.  It REQUIRES the
#   guess list for that width to exist; run solver/run-nerdle-enumerate.sh
#   first if it does not.
#
#   --variants DOES NOT PRODUCE ANSWERS.  It counts the answers under each
#   DISPUTED rule -- a bare `0` as an operand, `0` as the answer, leading zeros,
#   an expression right side, and the two intermediate restrictions we decided
#   against -- so our rule set can be compared with the live game's, which we
#   cannot read.  Only the first row is the answer count; every other row is a
#   different quantity and must never be quoted as one.  Nerdle's published
#   17723 is a list they CHOSE on grounds of taste, so it is a sanity check on
#   the order of magnitude, not a number to tune switches until we match.
#
# USE THIS RATHER THAN CALLING tools/nerdle_answers.py DIRECTLY.  It sets --out,
# points --guesses at the right pass-one file, writes a .meta sidecar recording
# the rule set, and tees a log.  The script refuses to start without --out.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8
VARIANTS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --width)    WIDTH="$2"; shift 2 ;;
        --variants) VARIANTS=1; shift ;;
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
GUESSES="$OUTDIR/guesses_w${WIDTH}.txt.gz"
if [ -n "$VARIANTS" ]; then
    STEM="answer_variants_w${WIDTH}"
    OUT="$OUTDIR/$STEM.csv"
else
    STEM="answers_w${WIDTH}"
    OUT="$OUTDIR/$STEM.txt.gz"
fi
mkdir -p "$OUTDIR" "$LOC"

if [ ! -f "$GUESSES" ]; then
    echo "no guess list at $GUESSES" >&2
    echo "  run: bash solver/run-nerdle-enumerate.sh --width $WIDTH" >&2
    exit 1
fi

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output nerdle_answers.py "$OUT" || exit 1

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle answers $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/nerdle_answers.py --width "$WIDTH" --guesses "$GUESSES" --out "$OUT" \
    ${VARIANTS:+--variants} 2>&1 | tee -a "$LOC/$STEM.log"
