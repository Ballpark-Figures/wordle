#!/bin/sh
# Rank PAIRS OF ANSWERS by how FEW words can tell them apart.
# tools/answer_pairs.py states the question and IS the source of truth.
#
#     bash solver/run-answer-pairs.sh
#     bash solver/run-answer-pairs.sh --splitters guess
#     bash solver/run-answer-pairs.sh --top 100000
#
# For every unordered pair of words from the PAIR list, count the SPLITTER-pool
# words `g` with pattern(g, a) != pattern(g, b), and rank ascending -- fewest
# splitters first, so the head is the pairs the follow-up can least often
# separate.  Exact and deterministic: no sampling, no seed, so a re-run
# reproduces the file byte for byte.
#
# Both lists are part of the QUESTION and are in the filename.  The tool refuses
# without them; the defaults below are ones a human reads, forwarded explicitly.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

PAIRS=mystery
SPLITTERS=custom
TOP=0
SHOW=20
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pairs)      PAIRS="$2";      shift 2 ;;
        --splitters)  SPLITTERS="$2";  shift 2 ;;
        --top)        TOP="$2";        shift 2 ;;
        --show)       SHOW="$2";       shift 2 ;;
        --dry-run)    DRYRUN=1;        shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOP" in
    ''|*[!0-9]*) echo "--top must be a non-negative number (0 = every pair)" >&2
                 exit 1 ;;
esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "this needs the default 12972 x 2315 matrix, which is gitignored:" >&2
    echo "  $PY build_patterns.py" >&2
    exit 1; }

STEM="pairsplit_${PAIRS}_by-${SPLITTERS}"
[ "$TOP" = 0 ] || STEM="${STEM}_top${TOP}"
OUTDIR=data/shared/answerpairs
LOC=data/local/answerpairs
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pairs $PAIRS --splitters $SPLITTERS --show $SHOW"
[ "$TOP" = 0 ] || FLAGS="$FLAGS --top $TOP"

echo "answer-pair splitting"
echo "  pairs      $PAIRS -- every unordered pair of these words"
echo "  splitters  $SPLITTERS -- the words that may separate a pair"
echo "  rank       ASCENDING: fewest splitters first"
echo "  rows       $([ "$TOP" = 0 ] && echo "every pair" || echo "the hardest $TOP")"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/answer_pairs.py $FLAGS --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] answer pairs $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/answer_pairs.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
