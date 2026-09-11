#!/bin/bash
# The EXACT best predetermined second word, and the exact value of the strategy.
#
#     bash solver/run-second-exact.sh --opener spilt       # one opener, seconds
#     bash solver/run-second-exact.sh                      # ALL openers: a PROOF
#     bash solver/run-second-exact.sh --limit 200 --dry-run
#
# WHAT IT COMPUTES.  Play an opener; if the reply shows at least --min-grays
# greys play one word committed to in advance; otherwise, and from the third
# guess on, play a uniformly random consistent ANSWER.  The random tail's cost
# depends only on the live candidate SET, so it is SUMMED EXACTLY by a memoised
# recursion rather than simulated -- no seed, no standard error, and a re-run
# reproduces the file.  solver/secondexact.c states the recursion and the bound.
#
# WHY EXACT RATHER THAN SIMULATED.  Choosing between 12972 second words means
# resolving differences of about 0.005 guesses; at a per-game sd near 0.9 that is
# ~290000 games EACH -- some 3.8 billion for ONE opener, hours of work, and the
# answer still has an error bar.  The recursion does it in under a second.
#
# IT IS A PROOF, NOT A SCREEN.  Every opener gets a sound lower bound first
# (T(S) >= 2|S| - 1 per bucket, no recursion), they are walked ASCENDING against
# a shared incumbent, and an opener whose bound is not below it cannot win and is
# never evaluated.  What comes out is the optimum over every (opener, second
# word) pair.  Ties are kept: every cut tests `<`, never `<=`.
#
# IT IS TIED TO THE `answer` FOLLOW-UP -- the tail draws from consistent ANSWERS,
# so a state is a subset of the 2315.  The `guess` follow-up is a different and
# much larger recursion and is not what this computes.
#
# MEASURED: bounding all 12972 openers takes about a minute; one opener's exact
# scan of all 12972 second words is 0.6s (16x faster than without the cut, and
# --no-prune proves the two agree).  A full run is tens of minutes -- watch the
# `evaluated / cut` line, which is the real cost.
#
# Output: data/shared/secondexact/, log under data/local/secondexact/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OPENER=""
OPENERS=""
MINGRAYS=3
LIMIT=""
THREADS=""
MEMOBITS=""
REPORT=30
NOPRUNE=0
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --opener)     OPENER="$2";   shift 2 ;;
        --openers)    OPENERS="$2";  shift 2 ;;
        --min-grays)  MINGRAYS="$2"; shift 2 ;;
        --limit)      LIMIT="$2";    shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --memo-bits)  MEMOBITS="$2"; shift 2 ;;
        --report)     REPORT="$2";   shift 2 ;;
        --no-prune)   NOPRUNE=1;     shift ;;
        --dry-run)    DRYRUN=1;      shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$MINGRAYS" in
    ''|*[!0-9]*) echo "--min-grays must be a number of grey tiles (1-5)" >&2; exit 1 ;;
esac
if [ "$MINGRAYS" -lt 1 ] || [ "$MINGRAYS" -gt 5 ]; then
    echo "--min-grays $MINGRAYS: a reply has 5 tiles, and 0 would fire every game" >&2
    exit 1
fi

cd "$MATH" || exit 1

BIN=solver/secondexact
[ -x "$BIN" ] || { echo "no $BIN -- build it with 'sh build.sh' from math/solver/" >&2
                   exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix at data/local/patterns/patterns.npy" >&2
    echo "  Build it with 'python3 build_patterns.py' from math/ (~2s, 30 MB)." >&2
    exit 1; }

OUTDIR=data/shared/secondexact
LOC=data/local/secondexact
STEM="exact_g${MINGRAYS}"
[ -z "$OPENER" ]  || STEM="${STEM}_${OPENER}"
[ -z "$OPENERS" ] || STEM="${STEM}_$(basename "$OPENERS" .txt)"
[ -z "$LIMIT" ]   || STEM="${STEM}_limit${LIMIT}"
[ "$NOPRUNE" = 0 ] || STEM="${STEM}_noprune"
OUT="$OUTDIR/$STEM.csv"

FLAGS="--min-grays $MINGRAYS --report $REPORT"
[ -z "$OPENER" ]   || FLAGS="$FLAGS --opener $OPENER"
[ -z "$OPENERS" ]  || FLAGS="$FLAGS --openers $OPENERS"
[ -z "$LIMIT" ]    || FLAGS="$FLAGS --limit $LIMIT"
[ -z "$THREADS" ]  || FLAGS="$FLAGS --threads $THREADS"
[ -z "$MEMOBITS" ] || FLAGS="$FLAGS --memo-bits $MEMOBITS"
[ "$NOPRUNE" = 0 ] || FLAGS="$FLAGS --no-prune"

echo "exact second word"
echo "  fires at   $MINGRAYS+ greys"
echo "  openers    ${OPENER:-${OPENERS:-all 12972}}${LIMIT:+ (first $LIMIT)}"
echo "  follow-up  answer (a uniformly random consistent answer)"
[ "$NOPRUNE" = 0 ] || echo "  NO PRUNING: every second word evaluated (the gate's check)"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $BIN $FLAGS --out $OUT"
    exit 0
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output secondexact "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] secondexact $STEM" | tee -a "$LOC/$STEM.log"

$BIN $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
