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
CANDS=
SEARCH=branch
PAIRSFROM=
ONCE=0
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
        --candidates) CANDS="$2";    shift 2 ;;
        --search)     SEARCH="$2";   shift 2 ;;
        --pairs-from) PAIRSFROM="$2"; shift 2 ;;
        --once)       ONCE=1;        shift 1 ;;
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

STEM="cover_${POOL}"
[ -z "$CANDS" ] || STEM="${STEM}-from-${CANDS}"
STEM="${STEM}_w${NWORDS}_${SEARCH}_k${TOPK}"
# THE WEIGHT SOURCE IS A BOUNDED TAG, NOT A NESTED STEM.  Folding the source's
# own name in grows the stem by ~40 characters per generation, which is the
# scar that killed a wordlesim cascade at macOS's 255-byte filename limit -- and
# a weight set is exactly the thing that gets chained.  Eight hex of the path
# distinguishes sources without growing; the full path is in the header and in
# the rounds CSV's `source=` field, which is where lineage belongs.
if [ -n "$PAIRSFROM" ]; then
    STEM="${STEM}_w$(printf '%s' "$PAIRSFROM" | shasum | cut -c1-8)"
else
    STEM="${STEM}_s${SEEDTOP}"
fi
STEM="${STEM}_f${FINALTOP}"
[ "$ONCE" = 0 ] || STEM="${STEM}_once"
[ "$CAP" = 6 ] || STEM="${STEM}_cap${CAP}"
OUTDIR=data/shared/paircover
LOC=data/local/paircover
OUT="$OUTDIR/$STEM"

FLAGS="--pool $POOL --words $NWORDS --topk $TOPK --rounds $ROUNDS --cap $CAP"
FLAGS="$FLAGS --seed-from $SEEDFROM --seed-top $SEEDTOP --show $SHOW"
FLAGS="$FLAGS --final-top $FINALTOP --search $SEARCH"
[ "$ONCE" = 0 ] || FLAGS="$FLAGS --once 1"
[ -z "$PAIRSFROM" ] || FLAGS="$FLAGS --pairs-from $PAIRSFROM"
[ -z "$CANDS" ] || FLAGS="$FLAGS --candidates $CANDS"
[ "$MAXPAIRS" = 0 ] || FLAGS="$FLAGS --max-pairs $MAXPAIRS"

echo "pair cover"
echo "  pool       $POOL -- what the opening partitions AND what the 5th guess draws"
echo "  words      the 4 come from ${CANDS:-$POOL}$([ -z "$CANDS" ] && echo " (the pool itself)" || echo " -- a DIFFERENT list")"
echo "  opening    $NWORDS words, chosen by weighted pair coverage"
echo "  objective  fewest answers UNSOLVED after the opening and the 5th draw"
if [ "$SEARCH" = beam ]; then
    echo "  search     BEAM, k=$TOPK -- K states carried forward, k*k openings"
else
    echo "  search     BRANCH, k=$TOPK -- recurse into the K best, k**words openings"
fi
[ -z "$PAIRSFROM" ] || echo "  weights    $PAIRSFROM (kept, not dropped after round 1)"
case "$FINALTOP" in
    all) echo "  last word  EXHAUSTIVE -- every candidate ranked by UNSOLVED" ;;
    0)   echo "  last word  no special case -- the same k as every other level" ;;
    *)   echo "  last word  the $FINALTOP best by coverage, then ranked by UNSOLVED" ;;
esac
echo "  seed       top $SEEDTOP of $SEEDFROM"
if [ "$ONCE" = 1 ]; then
    echo "  rounds     1 -- a SINGLE search; the weights are an INPUT and are"
    echo "             neither fed back nor written"
else
    echo "  rounds     $ROUNDS"
fi
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
