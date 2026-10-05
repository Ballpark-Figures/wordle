#!/bin/bash
# ONE example of the hard-mode all-grey loss, attached, with output here.
#
#     bash solver/run-disjoint-words.sh            # from math/, or anywhere
#
# Seven legal guesses sharing no letter -- one with no vowel, one per vowel
# A E I O U Y -- at least one an answer.  Play the other six against it and every
# reply is all grey, so every guess stays hard-mode legal and the sixth grey row
# loses.  tools/disjoint_words.py states the construction and the visit order;
# it stops at the FIRST set, so the result is an example, not the only one.
#
# Output: data/shared/disjoint/hardmode_allgrey_example.csv, log under
# data/local/disjoint/.  The tool refuses to overwrite a file with content.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ $# -eq 0 ] || { echo "takes no arguments" >&2; exit 1; }

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/disjoint
LOC=data/local/disjoint
mkdir -p "$OUTDIR" "$LOC"
OUT="$OUTDIR/hardmode_allgrey_example.csv"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] hard-mode all-grey example" | tee -a "$LOC/example.log"
"$PY" -u tools/disjoint_words.py --out "$OUT" 2>&1 | tee -a "$LOC/example.log"
