#!/bin/bash
# EVERY set of K legal guesses sharing no letter, at least one an answer --
# attached, with a progress bar over the answer letter sets and each set printed
# as it is found.
#
#     bash solver/run-disjoint-full.sh             # from math/, or anywhere; K = 7
#     bash solver/run-disjoint-full.sh -k 6
#
# K = 7 is the hard-mode all-grey loss.  No assumption about vowels: the
# vowel-construction sets of run-disjoint-words.sh are a subset of these.
# tools/disjoint_full.py states the search and its bounds exactly.  It first
# runs a brute-force check on samples (a few seconds), then the real search.
#
# Output: data/shared/disjoint/disjoint_full_k<K>.csv, streamed and flushed per
# answer letter set; log under data/local/disjoint/.  The tool refuses to
# overwrite a file with content.

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
OUT="$OUTDIR/disjoint_full_k$K.csv"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] disjoint full search k=$K" | tee -a "$LOC/full_k$K.log"
"$PY" -u tools/disjoint_full.py -k "$K" --out "$OUT" 2>&1 | tee -a "$LOC/full_k$K.log"
