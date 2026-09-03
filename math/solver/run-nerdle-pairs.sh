#!/bin/bash
# Screen TWO-EQUATION NERDLE openers, attached, with live output in this terminal.
#
#     bash solver/run-nerdle-pairs.sh                   # from math/, or anywhere
#     bash solver/run-nerdle-pairs.sh --top-n 200
#     bash solver/run-nerdle-pairs.sh --width 6 --top-n 50
#
# WHAT THIS COMPUTES, precisely:
#
#   Two guesses played BLIND, one after the other, before any feedback is used --
#   the convention the multiwordle openings follow.  An answer's joint bin is the
#   PAIR of feedbacks the two guesses give it, and pairs are ranked by the sum of
#   squared joint bin sizes, ascending, exactly as single guesses are.  An answer
#   either guess WINS outright is resolved and joins no bin.
#
#   IT IS A SCREEN, NOT A SEARCH.  Only pairs drawn from the best N SINGLE
#   guesses are examined, so the best pair overall can be missed outright: two
#   guesses that split poorly alone may cover each other's blind spots and would
#   never be looked at.  Report it as "the best pair among the top N", NEVER as
#   "the best pair".  --top-n widens the screen quadratically and never makes it
#   exhaustive, so each N is its own file.
#
#   THE SCORE IS NOT EXPECTED GUESSES.  It measures how finely the pair splits
#   the answers and nothing else -- it does not know that an answer won by the
#   FIRST guess is cheaper than one won by the second.  Run the solver on a
#   promising pair if you want its real cost.
#
#   ONLY THE BEST --write-top PAIRS ARE RECORDED (100000 by default), gzipped.
#   Every pair is scored, but --top-n 10000 is 49,995,000 of them and writing
#   them all came to 1.67 GB in a committed tree.  The .meta records `scored`,
#   `written` and `complete`, so a capped file cannot be mistaken for a full one;
#   --write-top 0 writes every pair.
#
#   Exact and deterministic: no sampling, no seed.  One (width, top-n) means one
#   file and a re-run reproduces it.  It needs the guess and answer lists for the
#   width; run the enumerate and answers wrappers first if they are missing.
#
# USE THIS RATHER THAN CALLING tools/nerdle_pairs.py DIRECTLY.  It sets --out,
# names the file after the width and N that define the screen, writes a .meta
# recording that it is not exhaustive, and tees a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8
TOPN=100
SHOW=""
WRITETOP=""

while [ $# -gt 0 ]; do
    case "$1" in
        --width) WIDTH="$2"; shift 2 ;;
        --top-n) TOPN="$2";  shift 2 ;;
        --show)  SHOW="$2";  shift 2 ;;
        --write-top) WRITETOP="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$WIDTH" in ''|*[!0-9]*) echo "--width must be a number" >&2; exit 1 ;; esac
case "$TOPN" in ''|*[!0-9]*) echo "--top-n must be a number" >&2; exit 1 ;; esac
[ "$WIDTH" -ge 3 ] || { echo "--width must be at least 3" >&2; exit 1; }
[ "$TOPN" -ge 2 ] || { echo "--top-n must be at least 2" >&2; exit 1; }

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/nerdle
LOC=data/local/nerdle
STEM="pairs_w${WIDTH}_n${TOPN}"
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
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output nerdle_pairs.py "$OUT" || exit 1

FLAGS="--width $WIDTH --top-n $TOPN --out $OUT"
[ -n "$SHOW" ] && FLAGS="$FLAGS --show $SHOW"
[ -n "$WRITETOP" ] && FLAGS="$FLAGS --write-top $WRITETOP"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle pairs $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/nerdle_pairs.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
