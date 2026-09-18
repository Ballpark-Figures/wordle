#!/bin/sh
# Cover the hard pairs, harvest the failures, repeat.
# math/paircover.py states the rule and IS the source of truth.
#
#     bash solver/run-pair-cover.sh -k 5 --rounds 10
#     bash solver/run-pair-cover.sh -k 20 --rounds 25 --seed-top 2000
#
# Each round builds an opening by weighted pair COVERAGE, ranks the leaves by
# UNSOLVED ANSWERS, harvests the pairs that opening actually failed on, and
# folds them back in with a count that is their weight next round.  Every round
# is flushed, so a Ctrl-C keeps the pair set and re-running CONTINUES from it.
#
# Exact and deterministic -- no sampling, no seed -- so a re-run of the same
# rounds from the same pair file reproduces them.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=custom
NWORDS=4
TOPK=""
ROUNDS=10
CAP=6
SEEDTOP=1000
SEEDFROM=""
MAXPAIRS=0
FINALTOP=0
SHOW=8
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)       POOL="$2";     shift 2 ;;
        --words)      NWORDS="$2";   shift 2 ;;
        -k|--topk)    TOPK="$2";     shift 2 ;;
        --rounds)     ROUNDS="$2";   shift 2 ;;
        --cap)        CAP="$2";      shift 2 ;;
        --seed-top)   SEEDTOP="$2";  shift 2 ;;
        --seed-from)  SEEDFROM="$2"; shift 2 ;;
        --max-pairs)  MAXPAIRS="$2"; shift 2 ;;
        --final-top)  FINALTOP="$2"; shift 2 ;;
        --show)       SHOW="$2";     shift 2 ;;
        --dry-run)    DRYRUN=1;      shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOPK" in
    ''|*[!0-9]*|0) echo "-k K is required and must be positive." >&2
                   echo "  K is the BRANCH width: recurse into the K best" >&2
                   echo "  coverage choices at each word.  K=1 is plain greedy." >&2
                   exit 1 ;;
esac
case "$ROUNDS" in
    ''|*[!0-9]*|0) echo "--rounds must be a positive number" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (a pair's second word may" >&2
    echo "  be any pool word, not just an answer)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

# The seed defaults to the answer-pair ranking over this same pool, which is the
# file solver/run-answer-pairs.sh writes.  Named explicitly rather than guessed:
# a different splitter pool is a different ranking and a different question.
[ -n "$SEEDFROM" ] || SEEDFROM="data/shared/answerpairs/pairsplit_mystery_by-${POOL}.csv"
[ -f "$SEEDFROM" ] || {
    echo "no seed ranking at $SEEDFROM" >&2
    echo "build it first:" >&2
    echo "  bash solver/run-answer-pairs.sh --splitters $POOL" >&2
    echo "or name one with --seed-from FILE" >&2
    exit 1; }

if [ "$FINALTOP" = 0 ]; then STEM="cover_${POOL}_w${NWORDS}_k${TOPK}_s${SEEDTOP}_fall"
else STEM="cover_${POOL}_w${NWORDS}_k${TOPK}_s${SEEDTOP}_f${FINALTOP}"; fi
[ "$CAP" = 6 ] || STEM="${STEM}_cap${CAP}"
OUTDIR=data/shared/paircover
LOC=data/local/paircover
OUT="$OUTDIR/$STEM"

FLAGS="--pool $POOL --words $NWORDS --topk $TOPK --rounds $ROUNDS --cap $CAP"
FLAGS="$FLAGS --seed-from $SEEDFROM --seed-top $SEEDTOP --show $SHOW"
FLAGS="$FLAGS --final-top $FINALTOP"
[ "$MAXPAIRS" = 0 ] || FLAGS="$FLAGS --max-pairs $MAXPAIRS"

echo "pair cover"
echo "  pool       $POOL -- the words it builds from AND the follow-up's pool"
echo "  opening    $NWORDS words, chosen by weighted pair coverage"
echo "  objective  fewest answers UNSOLVED after the opening and the 5th draw"
echo "  search     branch, k=$TOPK$([ "$TOPK" = 1 ] && echo " (plain greedy)")"
if [ "$FINALTOP" = 0 ]; then
    echo "  last word  EXHAUSTIVE -- every candidate ranked by UNSOLVED"
    echo "             (coverage chooses words 1..N-1 only; it was weakest last)"
else
    echo "  last word  the $FINALTOP best by coverage, then ranked by UNSOLVED"
fi
echo "  seed       top $SEEDTOP of $SEEDFROM"
echo "  rounds     $ROUNDS"
echo "  pairs      ${OUT}_pairs.csv (resumed if it exists)"
echo "  rounds log ${OUT}_rounds.csv"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/pair_cover.py $FLAGS --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] pair cover $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/pair_cover.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
