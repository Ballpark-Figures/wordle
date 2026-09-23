#!/bin/sh
# The answer families hard mode has to walk one word at a time.
# math/tools/deep_families.py states the derivation and IS the source of truth.
#
#     bash solver/run-deep-families.sh                    # from math/, or anywhere
#     bash solver/run-deep-families.sh --min-depth 8
#     bash solver/run-deep-families.sh --min-fixed 3
#
# WHY IT EXISTS.  Hard mode keeps every green in place, so an opener that pins a
# skeleton without locating the varying letter leaves the legal set EQUAL to a
# family of answers -- and the solver names them one at a time.  `wight` costs 10
# guesses because `.ight` holds nine words and w sorts last.  That is the whole
# mechanism behind every hard-mode depth past 6.
#
# HARD MODE ONLY, and that is not a default but the question.  Normal mode caps
# every answer at 6 by construction, so the same scan over optturns' trees
# returns nothing -- which would read as "no deep families" rather than as the
# wrong question being asked.  The tool does not honour WORDLE_SOLVER.
#
# EXACT AND DETERMINISTIC -- a pure function of the committed trees, no sampling
# and no seed, so a re-run reproduces the CSV byte for byte.  Cost is ~16s for
# the full 12972-tree scan.
#
# THE `size` COLUMN CAN OVERSTATE A FAMILY: it counts answers matching the
# template, while `walk` counts the guesses actually spent inside it.  A loose
# row like `...er` (141 matched, walk 7) is not a family in the sense the tight
# ones are -- use --min-fixed to exclude them.  The selection kept for the video
# is recorded in data/shared/FAMILIES.md.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

MINDEPTH=7
MINFIXED=0
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --min-depth) MINDEPTH="$2"; shift 2 ;;
        --min-fixed) MINFIXED="$2"; shift 2 ;;
        --dry-run)   DRYRUN=1;      shift 1 ;;
        *) echo "usage: bash solver/run-deep-families.sh [--min-depth N] [--min-fixed N] [--dry-run]" >&2; exit 1 ;;
    esac
done

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -d data/shared/hardturns/trees ] || {
    echo "no hardturns trees at data/shared/hardturns/trees -- this reads the" >&2
    echo "  committed hard-mode tree set, which is what carries the deep lines." >&2
    exit 1; }

STEM="deep_families_d${MINDEPTH}"
[ "$MINFIXED" = 0 ] || STEM="${STEM}_f${MINFIXED}"
OUTDIR=data/shared/families
LOC=data/local/families
OUT="$OUTDIR/$STEM.csv"

echo "deep families (hard mode)"
echo "  trees      data/shared/hardturns/trees"
echo "  reports    families whose deepest member costs >= $MINDEPTH guesses"
echo "  min-fixed  $MINFIXED  (template positions that must be pinned)"
echo "  exact      no sampling, no seed; a re-run reproduces the file"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/deep_families.py --min-depth $MINDEPTH --min-fixed $MINFIXED --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] deep-families $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/deep_families.py --min-depth "$MINDEPTH" --min-fixed "$MINFIXED" \
    --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
