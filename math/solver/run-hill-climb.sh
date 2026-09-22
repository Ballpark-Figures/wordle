#!/bin/sh
# Random 4-word starts, each improved by SWAPPING ONE WORD at a time.
# math/hillclimb.py states the rule and IS the source of truth.
#
#     bash solver/run-hill-climb.sh -t 100
#     bash solver/run-hill-climb.sh -t 50 --candidates guess
#     bash solver/run-hill-climb.sh -t 50 --objective singles --pool mystery --words 3
#     bash solver/run-hill-climb.sh -t 20 --objective mean --pool mystery --words 4
#
# THREE OBJECTIVES, and they are different quantities over the same openings --
# never put their numbers in one table.  `guarantee` (the default here, a human
# reading a default rather than a program falling back on one) minimises the
# answers a random tail can be made to lose; `singles` maximises the answers a
# reply names outright, which is what data/shared/singletons ranks by; `mean`
# minimises EXPECTED GUESSES exactly (math/openexact.py), which is the number
# run-wordle-race.sh --fallback answer estimates by Monte Carlo for this same
# strategy.  The objective leads the filename and is stamped in the CSV, and a
# run refuses a file written under another one.
#
# COST DEPENDS ON THE WORD COUNT, and for `mean` it is the PREFIX that decides:
# a swap scan holds k-1 words fixed, so a 2-word opening prices candidates
# against ONE-word buckets of up to 221 answers, while a 4- or 5-word opening
# prices them against buckets of 16 or fewer.  Small openings are the expensive
# ones here.  Price one trial before launching a batch.
#
# Draw k random words, then repeatedly take the single-word swap that lowers the
# number of UNSOLVED answers the most, until none does.  That is a LOCAL
# optimum: two words might have to change together to get past it, and this
# never tries that.  So a result is the best of --trials random starts, never
# the best opening.
#
# Trials are independent and seeded by INDEX, so --workers changes only the
# order lines appear in -- never the result.
#
# Every accepted move prints.  Each (pool, candidates, words, cap, seed) is a
# different experiment and gets its own file; trials APPEND, so a second run at
# the SAME seed would repeat trial numbers -- advance --seed for a new batch.
# A file written by a different SET OF SECTIONS is refused, not appended to.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

POOL=custom
OBJ=guarantee
CANDS=
NWORDS=4
TRIALS=""
CAP=6
SEED=0
WORKERS=18          # 18 cores here; --workers overrides
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --pool)       POOL="$2";   shift 2 ;;
        --objective)  OBJ="$2";    shift 2 ;;
        --candidates) CANDS="$2";  shift 2 ;;
        --words)      NWORDS="$2"; shift 2 ;;
        -t|--trials)  TRIALS="$2"; shift 2 ;;
        --cap)        CAP="$2";    shift 2 ;;
        --seed)       SEED="$2";   shift 2 ;;
        --workers)    WORKERS="$2"; shift 2 ;;
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

# THE OBJECTIVE LEADS THE NAME, and `guarantee` keeps the historical `climb_`
# so every committed file stays readable under the name it was written with.
case "$OBJ" in
    guarantee) STEM="climb_${POOL}" ;;
    singles)   STEM="singles_${POOL}" ;;
    mean)      STEM="mean_${POOL}" ;;
    *) echo "--objective must be guarantee, singles or mean" >&2; exit 1 ;;
esac
[ -z "$CANDS" ] || STEM="${STEM}-from-${CANDS}"
STEM="${STEM}_w${NWORDS}_s${SEED}"
[ "$CAP" = 6 ] || STEM="${STEM}_cap${CAP}"
OUTDIR=data/shared/hillclimb
LOC=data/local/hillclimb
OUT="$OUTDIR/$STEM.csv"

FLAGS="--pool $POOL --objective $OBJ --words $NWORDS --trials $TRIALS"
FLAGS="$FLAGS --cap $CAP --seed $SEED"
FLAGS="$FLAGS --workers $WORKERS"
[ -z "$CANDS" ] || FLAGS="$FLAGS --candidates $CANDS"

echo "hill climb"
echo "  objective  $OBJ"
echo "  pool       $POOL -- what the opening partitions; for guarantee it is"
echo "             also what the random tail draws from"
echo "  words      the $NWORDS come from ${CANDS:-$POOL}$([ -z "$CANDS" ] && echo " (the pool itself)")"
case "$OBJ" in
  guarantee) echo "  target     fewest answers UNSOLVED after the opening and the tail" ;;
  singles)   echo "  target     MOST answers alone in their bucket (--cap unused)" ;;
  mean)      echo "  target     fewest EXPECTED GUESSES, computed exactly -- the number"
             echo "             run-wordle-race.sh --fallback answer samples for"
             echo "             this same strategy.  Expected guesses OUTRIGHT." ;;
esac
echo "  moves      one word, then anagram PAIRS, then pairs within one letter,"
echo "             then anagram TRIPLES -- each to exhaustion, then round again"
echo "             until a whole pass moves nothing.  Steepest within a section."
echo "  trials     $TRIALS random restarts from seed $SEED"
echo "  workers    $WORKERS -- whole TRIALS in parallel; each holds its own"
echo "             168 MB matrix, and the seed is per trial so the RESULT does"
echo "             not depend on this number"
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
