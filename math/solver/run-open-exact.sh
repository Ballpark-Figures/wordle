#!/bin/sh
# EXACT expected guesses and win rate for blind openings -- no simulation.
# math/openexact.py states the strategy and the two recursions and IS the source
# of truth; tools/open_exact.py is the driver.
#
#     bash solver/run-open-exact.sh --opening "crane spilt"
#     bash solver/run-open-exact.sh --openings-from RANKING.csv --top 200
#     bash solver/run-open-exact.sh --openings-from RACE.csv --top 20
#
# WHAT IT IS FOR.  `run-wordle-race.sh --fallback answer` ESTIMATES these two
# numbers by Monte Carlo; this COMPUTES them.  No seed, no standard error, no
# winner's curse, and a re-run reproduces the file byte for byte.  VERIFIED
# against the committed race cells at k = 1..5, every one inside one standard
# error (the figures are in the driver's docstring).
#
# IT PRICES, IT DOES NOT SEARCH.  A race screens thousands of openings against
# each other and eliminates; this evaluates the openings it is handed.  The two
# compose: race wide and cheap, then price the survivors here exactly.  So the
# head of a run is the best of the openings HANDED IN, and the field's own
# caveat (a ranking's top N is a screen) still applies to it.
#
# COST IS GOVERNED BY THE WORD COUNT and nothing else, because it is all in the
# bucket sizes.  MEASURED: ~4 s for a 1-word opening, ~0.08 s for 2 words, and
# milliseconds for 3, 4 or 5.  So a 10000-opening field of quads is minutes and
# the same field of single words is most of a day -- price the shape first.
#
# THE POOL IS PART OF THE QUESTION.  The default here is a default a human reads
# and it is forwarded explicitly; the TOOL defaults nothing, so it can never be
# inherited silently.  Only `answer` is implemented -- see the driver, which
# REFUSES the others rather than reporting the answer-pool number under their
# name.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=answer
CAP=6
OPENFROM=""
OPENIN=""
TOP=""
REPORT=""
DRYRUN=0
OPENINGS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)           POOL="$2";     shift 2 ;;
        --cap)            CAP="$2";      shift 2 ;;
        --opening)        OPENINGS="$OPENINGS --opening '$2'"; shift 2 ;;
        --openings-from)  OPENFROM="$2"; shift 2 ;;
        --openings-in)    OPENIN="$2";   shift 2 ;;
        --top)            TOP="$2";      shift 2 ;;
        --report)         REPORT="$2";   shift 2 ;;
        --dry-run)        DRYRUN=1;      shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$OPENFROM" ] && [ -z "$OPENINGS" ]; then
    echo "give --opening 'a b' (repeatable) or --openings-from a ranking CSV" >&2
    exit 1
fi
if [ -n "$OPENFROM" ] && [ -z "$TOP" ]; then
    echo "--openings-from needs --top N: how many openings are examined IS the" >&2
    echo "  run's coverage, so it is named rather than defaulted." >&2
    exit 1
fi

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (an opening word need not" >&2
    echo "  be an answer, so its replies come from the square matrix)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

if [ -n "$OPENFROM" ]; then
    SRC=$(basename "$OPENFROM" .csv)_top$TOP
    [ -n "$OPENIN" ] && SRC="${SRC}_in-$(basename "$OPENIN" .txt)"
else
    SRC=named
fi
STEM="exact_${SRC}_${POOL}_cap${CAP}"
OUTDIR=data/shared/openexact
LOC=data/local/openexact
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pool $POOL --cap $CAP"
[ -z "$OPENFROM" ] || FLAGS="$FLAGS --openings-from $OPENFROM --top $TOP"
[ -z "$OPENIN" ]   || FLAGS="$FLAGS --openings-in $OPENIN"
[ -z "$REPORT" ]   || FLAGS="$FLAGS --report $REPORT"

echo "exact opening evaluation"
echo "  openings   ${OPENFROM:-named on the command line}${TOP:+ (top $TOP)}${OPENIN:+, every word in $OPENIN}"
echo "  follow-up  a random compatible word from $POOL, after the whole opening"
echo "  computes   expected guesses (UNCAPPED) and the win rate at <= $CAP"
echo "  exact      no sampling, no seed; a re-run reproduces the file"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"
[ -f "$OUT" ] && echo "  RESUMING from $OUT"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/open_exact.py $FLAGS$OPENINGS --out $OUT"
    exit 0
fi

# Shared refuse-if-something-else-writes-this-file guard: two runs appending to
# one CSV would each read the other's rows as work already done.
. "$(dirname -- "$0")/_guard.sh"
guard_output open_exact.py "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] open-exact $STEM" >> "$LOC/$STEM.log"
eval "\"$PY\" -u tools/open_exact.py $FLAGS$OPENINGS --out \"$OUT\"" 2>&1 \
    | tee -a "$LOC/$STEM.log"
