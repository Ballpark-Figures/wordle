#!/bin/bash
# Sets of K legal guesses sharing no letter, at least one an answer -- attached,
# with live output in this terminal.
#
#     bash solver/run-disjoint-words.sh            # from math/, or anywhere; K = 7
#     bash solver/run-disjoint-words.sh -k 6
#
# K = 7 IS THE HARD-MODE ALL-GREY LOSS: six guesses and an answer, no letter in
# common anywhere, so every reply is all grey, every guess stays hard-mode legal,
# and the sixth grey row loses.  tools/disjoint_words.py states the question and
# the search exactly; read it before quoting a number.  Exact and deterministic:
# a pure function of the committed word lists.
#
# Output: data/shared/disjoint/disjoint_k<K>.csv, log under data/local/disjoint/.
# The tool refuses to overwrite a file with content -- move the old one first.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=7                       # a default a HUMAN reads, forwarded explicitly
while [ $# -gt 0 ]; do
    case "$1" in
        -k|--k) K="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done
case "$K" in ''|*[!0-9]*) echo "-k must be a positive integer" >&2; exit 1 ;; esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/disjoint
LOC=data/local/disjoint
mkdir -p "$OUTDIR" "$LOC"
OUT="$OUTDIR/disjoint_k$K.csv"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] disjoint words k=$K" | tee -a "$LOC/disjoint_k$K.log"
"$PY" -u tools/disjoint_words.py -k "$K" --out "$OUT" 2>&1 | tee -a "$LOC/disjoint_k$K.log"
