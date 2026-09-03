#!/bin/bash
# Run the top-K NERDLE solver attached, with live output in this terminal.
#
#     bash solver/run-nerdle-solve.sh                   # from math/, or anywhere
#     bash solver/run-nerdle-solve.sh -k 2
#     bash solver/run-nerdle-solve.sh --rank-only
#     bash solver/run-nerdle-solve.sh --width 6 -k 3
#
# WHAT THIS MEASURES, precisely:
#
#   The EXPECTED NUMBER OF GUESSES to finish, over the answer list taken
#   UNIFORMLY, under a beam that ranks every legal guess by the SUM OF SQUARED
#   BIN SIZES of the split it induces -- evenest first, ties on the lowest guess
#   index.  math/nerdle_topk.py states the objective and the strategy exactly
#   and is the source of truth; read it before quoting any number.
#
#   IT IS NOT AN OPTIMUM.  `-k K` examines exactly K guesses at EVERY node, the
#   ROOT INCLUDED, so the opener is the best of the K examined and not the best
#   of all 374246.  Each K is a different strategy and gets its own file.
#
#   THERE IS NO DEPTH CAP.  This is expected guesses OUTRIGHT, which is the same
#   footing as the multiwordle and adversarial numbers and NOT the footing of
#   any optturns/hardturns/ansall total -- those are optima subject to a
#   guarantee.  Never put the two in one table.
#
#   A GUESS WINS AGAINST ITS WHOLE COMMUTATIVE CLASS, because the game accepts a
#   rearrangement of the day's answer (a setting, on by default).  So one guess
#   can finish several candidates at once, which never happens in Wordle, and
#   the winning bin is the class rather than the all-green pattern.
#
#   COST.  There is no pattern matrix -- 374246 x 17723 would be 13.3 GB -- so
#   feedback is computed inside the kernel.  The work in a level is the guess
#   count times the candidates still alive at that level, so each level costs
#   about what the root does instead of decaying.  --rank-only does just the
#   root and stops, which is the cheap way to see the opener first.
#
#   Exact and deterministic: no sampling, no seed.  One (width, k) means one
#   file and a re-run reproduces it.
#
# USE THIS RATHER THAN CALLING tools/nerdle_solve.py DIRECTLY.  It sets --out,
# names the file after the width and K that define the run, writes a .meta
# recording the objective, and tees a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WIDTH=8
K=1
TOP=""
RANKONLY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --width)     WIDTH="$2"; shift 2 ;;
        -k|--topk)   K="$2";     shift 2 ;;
        --top)       TOP="$2";   shift 2 ;;
        --rank-only) RANKONLY=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$WIDTH" in ''|*[!0-9]*) echo "--width must be a number" >&2; exit 1 ;; esac
case "$K" in ''|*[!0-9]*|0) echo "-k must be a positive number" >&2; exit 1 ;; esac
[ "$WIDTH" -ge 3 ] || { echo "--width must be at least 3" >&2; exit 1; }

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/nerdle
LOC=data/local/nerdle
GUESSES="$OUTDIR/guesses_w${WIDTH}.txt.gz"
ANSWERS="$OUTDIR/answers_w${WIDTH}.txt.gz"
if [ -n "$RANKONLY" ]; then
    STEM="solve_w${WIDTH}_k${K}_rank"
else
    STEM="solve_w${WIDTH}_k${K}"
fi
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

for f in "$GUESSES" "$ANSWERS"; do
    [ -f "$f" ] && continue
    echo "missing $f" >&2
    echo "  run: bash solver/run-nerdle-enumerate.sh --width $WIDTH" >&2
    echo "  then: bash solver/run-nerdle-answers.sh --width $WIDTH" >&2
    exit 1
done

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output nerdle_solve.py "$OUT" || exit 1

FLAGS="--width $WIDTH -k $K --out $OUT"
[ -n "$TOP" ] && FLAGS="$FLAGS --top $TOP"
[ -n "$RANKONLY" ] && FLAGS="$FLAGS --rank-only"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] nerdle solve $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/nerdle_solve.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
