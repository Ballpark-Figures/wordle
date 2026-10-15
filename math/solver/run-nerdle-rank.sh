#!/bin/bash
# Rank every legal NERDLE guess by its root sum of squares, once, and store it.
#
#     bash solver/run-nerdle-rank.sh                    # from math/, or anywhere
#     bash solver/run-nerdle-rank.sh --width 6
#
# WHAT THIS COMPUTES, precisely:
#
#   For each of the 374246 legal guesses, the sum of squared bin sizes of the
#   partition it induces on the 17723 answers, with the answers it WINS excluded
#   -- they are resolved, not binned.  Ascending, ties on the lowest guess index
#   in canonical symbol order.  math/nerdle_topk.py defines the score and is the
#   source of truth.
#
#   RUN THIS FIRST.  The solver and the pair screen both start from this ranking
#   and read it from disk; without it they compute it themselves, which is about
#   110 seconds each time.
#
#   IT IS A RANKING, NOT A RESULT.  A good first-guess score does not make a
#   guess a good opener -- it says nothing about what happens after the reply.
#   The solver's own number is the one to quote.
#
#   THE FILE CARRIES A FINGERPRINT over the width and both word lists, and the
#   readers refuse a ranking that does not match rather than using it.  So
#   re-enumerating the answers retires this file automatically; reusing it
#   silently would leave every score confidently wrong rather than missing.
#
# USE THIS RATHER THAN CALLING tools/nerdle_rank.py DIRECTLY.  It sets --out,
# names the file after the width, and tees a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8
SHOW=""

while [ $# -gt 0 ]; do
    case "$1" in
        --width) WIDTH="$2"; shift 2 ;;
        --show)  SHOW="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$WIDTH" in ''|*[!0-9]*) echo "--width must be a number" >&2; exit 1 ;; esac
[ "$WIDTH" -ge 3 ] || { echo "--width must be at least 3" >&2; exit 1; }

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/nerdle
LOC=data/local/nerdle
STEM="root_rank_w${WIDTH}"
OUT="$OUTDIR/$STEM.csv.gz"
mkdir -p "$OUTDIR" "$LOC"

for f in "$OUTDIR/guesses_w${WIDTH}.txt.gz" "$OUTDIR/answers_w${WIDTH}.txt.gz"; do
    [ -f "$f" ] && continue
    echo "missing $f" >&2
    echo "  run: bash solver/run-nerdle-enumerate.sh --width $WIDTH" >&2
    echo "  then: bash solver/run-nerdle-answers.sh --width $WIDTH" >&2
    exit 1
done

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output nerdle_rank.py "$OUT" || exit 1

FLAGS="--width $WIDTH --out $OUT"
[ -n "$SHOW" ] && FLAGS="$FLAGS --show $SHOW"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle rank $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/nerdle_rank.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
