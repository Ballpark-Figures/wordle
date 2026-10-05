#!/bin/bash
# The hard-mode all-grey loss, attached, with output here.
#
#     bash solver/run-disjoint-words.sh            # from math/: ONE example
#     bash solver/run-disjoint-words.sh --all      # EVERY set of this form
#
# Seven legal guesses sharing no letter -- one with no vowel, one per vowel
# A E I O U Y -- at least one an answer.  Play the other six against it and every
# reply is all grey, so every guess stays hard-mode legal and the sixth grey row
# loses.  tools/disjoint_words.py states the construction and the visit order.
# Without --all it stops at the FIRST set, so that result is an example, not the
# only one.
#
# Output: data/shared/disjoint/hardmode_allgrey_example.csv (one) or
# hardmode_allgrey_all.csv (--all); log under data/local/disjoint/.  The tool
# refuses to overwrite a file with content.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALL=""
while [ $# -gt 0 ]; do
    case "$1" in
        --all) ALL=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/disjoint
LOC=data/local/disjoint
mkdir -p "$OUTDIR" "$LOC"
if [ -n "$ALL" ]; then
    OUT="$OUTDIR/hardmode_allgrey_all.csv"; LOG="$LOC/all.log"; FLAG="--all"; WHAT="every set"
else
    OUT="$OUTDIR/hardmode_allgrey_example.csv"; LOG="$LOC/example.log"; FLAG=""; WHAT="one example"
fi

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] hard-mode all-grey, $WHAT" | tee -a "$LOG"
"$PY" -u tools/disjoint_words.py --out "$OUT" $FLAG 2>&1 | tee -a "$LOG"
