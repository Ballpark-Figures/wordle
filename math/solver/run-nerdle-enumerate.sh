#!/bin/bash
# Enumerate every valid NERDLE GUESS, attached, with live output in this terminal.
#
#     bash solver/run-nerdle-enumerate.sh                   # from math/, or anywhere
#     bash solver/run-nerdle-enumerate.sh --width 6
#     bash solver/run-nerdle-enumerate.sh --method split
#
# WHAT THIS COMPUTES, precisely:
#
#   The set of 8-symbol strings that Nerdle accepts as a legal GUESS -- every
#   equation AS WRITTEN, so `1+9=0+10` and `9+1=0+10` are two guesses, not one.
#   Collapsing commutative equivalents is a SEPARATE second pass and nothing
#   here does it.  math/nerdle.py states the rules exactly and is the source of
#   truth; read it before quoting any count.
#
#   THESE ARE GUESSES, NOT ANSWERS.  The answer rules are strictly tighter -- a
#   bare number on the right, no leading zeros anywhere, no negatives, an
#   operator required on the left -- and two of them (may an answer's left side
#   pass through a negative or a fractional intermediate?) are still OPEN.  So
#   there is no answer filter yet and this file must not be described as the
#   answer list.
#
#   The count is EXACT and integral.  There is no sampling, no seed and no
#   tolerance, so one width means one file and a re-run reproduces it byte for
#   byte.
#
#   --method chooses the WALK, not the answer.  `dfs` is the specified
#   single-pass descent over the whole string; `split` enumerates each side once
#   with its exact value and joins the sides on it.  Both emit the same set, in
#   different orders, which tools/checknerdle.py verifies exhaustively at every
#   width it can brute-force -- so the method is deliberately NOT part of the
#   filename, unlike every genuine parameter of the experiment.  At width 8
#   `split` is much the cheaper of the two: roughly 7.6 million side
#   evaluations against roughly 188 million bottomed-out branches, because the
#   right side being a full expression stops the walk from ending at the `=`.
#
# USE THIS RATHER THAN CALLING tools/nerdle_enumerate.py DIRECTLY.  It sets
# --out so the result outlives the terminal, names the file after the width,
# writes a .meta sidecar recording the rule set, and tees a log.  The script
# refuses to start without --out for the same reason.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8
METHOD=dfs
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --width)    WIDTH="$2";    shift 2 ;;
        --method)   METHOD="$2";   shift 2 ;;
        --progress) PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$WIDTH" in
    ''|*[!0-9]*) echo "--width must be a number" >&2; exit 1 ;;
esac
[ "$WIDTH" -ge 3 ] || { echo "--width must be at least 3" >&2; exit 1; }
case "$METHOD" in
    dfs|split) ;;
    *) echo "--method must be dfs or split, not $METHOD" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/nerdle
LOC=data/local/nerdle
STEM="guesses_w${WIDTH}"
OUT="$OUTDIR/$STEM.txt.gz"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output nerdle_enumerate.py "$OUT" || exit 1

FLAGS="--width $WIDTH --method $METHOD --out $OUT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle enumerate $STEM method=$METHOD" \
    | tee -a "$LOC/enumerate_$STEM.log"

"$PY" -u tools/nerdle_enumerate.py $FLAGS 2>&1 | tee -a "$LOC/enumerate_$STEM.log"
