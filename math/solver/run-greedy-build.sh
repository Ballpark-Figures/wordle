#!/bin/sh
# Build an opening LETTER BY LETTER against the guarantee objective.
# math/greedybuild.py states the rule and IS the source of truth.
#
#     bash solver/run-greedy-build.sh -k 1
#     bash solver/run-greedy-build.sh -k 50 --nwords 5
#
# Exact and deterministic -- no sampling, no seed -- so a re-run reproduces the
# file.  -k is a BEAM over (letter, slot) placements: K=1 is the plain greedy,
# and the result is the best of what the beam examined, never the best opening.
# K and the word count are part of the search, so both are in the filename.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=custom
NWORDS=4
TOPK=""
PROGRESS=""
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)      POOL="$2";     shift 2 ;;
        --nwords)    NWORDS="$2";   shift 2 ;;
        -k|--topk)   TOPK="$2";     shift 2 ;;
        --progress)  PROGRESS="$2"; shift 2 ;;
        --dry-run)   DRYRUN=1;      shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOPK" in
    ''|*[!0-9]*|0) echo "-k K is required and must be positive: the beam width." >&2
                   echo "  K=1 is the plain greedy; it is part of the search." >&2
                   exit 1 ;;
esac
case "$NWORDS" in
    ''|*[!0-9]*|0) echo "--nwords must be a positive number of words" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (the buckets are over the" >&2
    echo "  follow-up's own pool, not the answers)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

STEM="greedy_${POOL}_w${NWORDS}_k${TOPK}"
OUTDIR=data/shared/greedybuild
LOC=data/local/greedybuild
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pool $POOL --words $NWORDS --topk $TOPK"
[ -z "$PROGRESS" ] || FLAGS="$FLAGS --progress $PROGRESS"

echo "greedy build"
echo "  opening    $NWORDS words, built one letter at a time"
echo "  pool       $POOL -- the words it may use AND the words the follow-up draws"
echo "  objective  fewest answers UNSOLVED (some live word fails to split them)"
echo "  ties       sum of squared bucket sizes over the pool"
echo "  beam       k=$TOPK$([ "$TOPK" = 1 ] && echo " (plain greedy)")"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/greedy_build.py $FLAGS --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greedy $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/greedy_build.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
