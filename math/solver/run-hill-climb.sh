#!/bin/sh
# Random 4-word starts, each improved by SWAPPING ONE WORD at a time.
# math/hillclimb.py states the rule and IS the source of truth.
#
#     bash solver/run-hill-climb.sh -t 100
#     bash solver/run-hill-climb.sh -t 50 --candidates guess
#
# Draw k random words, then repeatedly take the single-word swap that lowers the
# number of UNSOLVED answers the most, until none does.  That is a LOCAL
# optimum: two words might have to change together to get past it, and this
# never tries that.  So a result is the best of --trials random starts, never
# the best opening.
#
# Every accepted swap prints.  Each (pool, candidates, words, cap, seed) is a
# different experiment and gets its own file; trials APPEND, so a second run at
# a later seed adds to the same record.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=custom
CANDS=
NWORDS=4
TRIALS=""
CAP=6
SEED=0
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)       POOL="$2";   shift 2 ;;
        --candidates) CANDS="$2";  shift 2 ;;
        --words)      NWORDS="$2"; shift 2 ;;
        -t|--trials)  TRIALS="$2"; shift 2 ;;
        --cap)        CAP="$2";    shift 2 ;;
        --seed)       SEED="$2";   shift 2 ;;
        --dry-run)    DRYRUN=1;    shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TRIALS" in
    ''|*[!0-9]*|0) echo "-t N is required and must be positive: how many random" >&2
                   echo "  restarts to climb.  The restarts are the only thing" >&2
                   echo "  exploring; the climb itself is deterministic." >&2
                   exit 1 ;;
esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (a live set is pool words," >&2
    echo "  and a candidate may come from outside the pool)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

STEM="climb_${POOL}"
[ -z "$CANDS" ] || STEM="${STEM}-from-${CANDS}"
STEM="${STEM}_w${NWORDS}_s${SEED}"
[ "$CAP" = 6 ] || STEM="${STEM}_cap${CAP}"
OUTDIR=data/shared/hillclimb
LOC=data/local/hillclimb
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pool $POOL --words $NWORDS --trials $TRIALS --cap $CAP --seed $SEED"
[ -z "$CANDS" ] || FLAGS="$FLAGS --candidates $CANDS"

echo "hill climb"
echo "  pool       $POOL -- what the opening partitions AND what the 5th guess draws"
echo "  words      the $NWORDS come from ${CANDS:-$POOL}$([ -z "$CANDS" ] && echo " (the pool itself)")"
echo "  objective  fewest answers UNSOLVED after the opening and the 5th draw"
echo "  move       swap ONE word; steepest improvement; stop at a local optimum"
echo "  trials     $TRIALS random restarts from seed $SEED"
echo "  out        $OUT (appended)"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/hill_climb.py $FLAGS --out $OUT"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] hill climb $STEM" >> "$LOC/$STEM.log"
"$PY" -u tools/hill_climb.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
