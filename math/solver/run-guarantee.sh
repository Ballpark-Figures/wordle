#!/bin/sh
# Which openings GUARANTEE a win -- exact, no sampling.  math/guarantee.py states
# the question and IS the source of truth.
#
#     bash solver/run-guarantee.sh --openings-from RANKING.csv --top 10000
#     bash solver/run-guarantee.sh --words LIST.txt --pool mystery --adapt 0
#
# A 100% WIN RATE AND A GUARANTEE ARE THE SAME STATEMENT: every reachable draw of
# the random follow-up has positive probability, so "probability 1" and "no
# reachable draw sequence loses" coincide.  This decides the second, exactly --
# no seed, no standard error, and a re-run reproduces the file.
#
# IT IS NOT OPTIMAL PLAY.  The follow-up is the same random rule the race
# measures; the worst case is over what it could unluckily draw, not over what a
# solver would choose.  So never table a number from here beside an optturns
# total, nor beside a wordlesim win rate -- that AVERAGES over these same draws.
#
# THE POOL AND --adapt ARE PART OF THE QUESTION and land in the filename.  The
# defaults here are the strategy currently being raced (custom, adapt 2); the
# TOOL defaults neither, so a default can never be inherited silently.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=custom
ADAPT=2
CAP=6
OPENFROM=""
OPENIN=""
WORDS=""
TOP=""
PROGRESS=""
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)           POOL="$2";     shift 2 ;;
        --adapt)          ADAPT="$2";    shift 2 ;;
        --cap)            CAP="$2";      shift 2 ;;
        --openings-from)  OPENFROM="$2"; shift 2 ;;
        --openings-in)    OPENIN="$2";   shift 2 ;;
        --words)          WORDS="$2";    shift 2 ;;
        --top)            TOP="$2";      shift 2 ;;
        --progress)       PROGRESS="$2"; shift 2 ;;
        --dry-run)        DRYRUN=1;      shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$ADAPT" in
    ''|*[!0-9]*) echo "--adapt must be a non-negative number of words" >&2; exit 1 ;;
esac
case "$CAP" in
    ''|*[!0-9]*|0) echo "--cap must be a positive number of guesses" >&2; exit 1 ;;
esac
if [ -z "$OPENFROM" ] && [ -z "$WORDS" ]; then
    echo "give the openings: --openings-from RANKING.csv (with --top N), or" >&2
    echo "  --words LIST.txt" >&2
    exit 1
fi
if [ -n "$OPENFROM" ] && [ -z "$TOP" ]; then
    echo "--openings-from needs --top N: how much of the ranking to examine is" >&2
    echo "  the experiment's coverage, and everything below it is never looked at" >&2
    exit 1
fi

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (the follow-up's live set is" >&2
    echo "  over its own pool, not the answers)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

if [ -n "$OPENFROM" ]; then
    SRC=$(basename "$OPENFROM" .csv)_top$TOP
    [ -n "$OPENIN" ] && SRC="${SRC}_in-$(basename "$OPENIN" .txt)"
else
    SRC=$(basename "$WORDS" .txt)
fi
STEM="guarantee_${SRC}_${POOL}_adapt${ADAPT}_cap${CAP}"
OUTDIR=data/shared/guarantee
LOC=data/local/guarantee
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pool $POOL --adapt $ADAPT --cap $CAP"
[ -z "$OPENFROM" ]  || FLAGS="$FLAGS --openings-from $OPENFROM --top $TOP"
[ -z "$OPENIN" ]    || FLAGS="$FLAGS --openings-in $OPENIN"
[ -z "$WORDS" ]     || FLAGS="$FLAGS --words $WORDS"
[ -n "$WORDS" ] && [ -n "$TOP" ] && FLAGS="$FLAGS --top $TOP"
[ -z "$PROGRESS" ]  || FLAGS="$FLAGS --progress $PROGRESS"

echo "guarantee sweep"
echo "  openings   ${OPENFROM:-$WORDS}${TOP:+ (top $TOP)}${OPENIN:+, every word in $OPENIN}"
echo "  follow-up  draws at random from $POOL"
echo "  rule       opening$([ "$ADAPT" -gt 0 ] && echo ", abandoned once the follow-up is down to $ADAPT"), then the follow-up"
echo "  asks       is there ANY answer and ANY draw needing more than $CAP guesses"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"
[ -f "$OUT" ] && echo "  RESUMING from $OUT"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/guarantee_sweep.py $FLAGS --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] guarantee $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/guarantee_sweep.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
