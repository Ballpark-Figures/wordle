#!/usr/bin/env bash
# EXACT expected guesses per opener, for the one cell where sampling is not
# needed: `minavg` at k=1.  From math/:
#
#   bash solver/run-multiwordle-exact.sh --strategy minavg
#   bash solver/run-multiwordle-exact.sh --strategy minavg --dry-run
#
# At k=1 the answer is one word drawn uniformly from the 2315, and `minavg` is
# deterministic -- so those 2315 games ARE the population and their mean is the
# true expected guesses.  No standard error, no 5-sigma cut, no winner's curse:
# the best row is the best opener among the 12972, full stop, which is a stronger
# claim than any race can make.  MEASURED at about 0.24 s per opener, so the whole
# guess list takes well under an hour.
#
# It REFUSES a randomised strategy and it REFUSES k>1, rather than quietly
# returning something weaker under an exact-sounding name -- `greedy` and `srank`
# have a distribution over their own coin flips, and k>1 has a population of
# C(2315, k).  Both belong in run-multiwordle-race.sh, which is honest about
# sampling.
#
# Resumable per opener: one flushed CSV row each, and a re-run skips what is
# already there.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STRATEGY=""
OPENINGS="guess"
TOP=""
EXTRA=""
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --strategy)      STRATEGY="$2"; shift 2 ;;
        --openings|--words|--openings-from) OPENINGS="$2"; shift 2 ;;
        --top)           TOP="$2";      shift 2 ;;
        --progress)      EXTRA="$EXTRA --progress $2"; shift 2 ;;
        --dry-run)       DRY=1;         shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# No default: the strategy is the experiment, and only a deterministic one is
# even eligible here.
case "$STRATEGY" in
    minavg) ;;
    "") echo "--strategy is required, and only 'minavg' is eligible:" >&2
        echo "  exact evaluation needs a DETERMINISTIC rule, and greedy and" >&2
        echo "  srank are randomised.  Use run-multiwordle-race.sh for those." >&2
        exit 1 ;;
    greedy|srank)
        echo "--strategy $STRATEGY is randomised, so enumerating the 2315" >&2
        echo "  answers gives one SAMPLE of its mean, not the mean." >&2
        echo "  Use: bash solver/run-multiwordle-race.sh --strategy $STRATEGY -k 1" >&2
        exit 1 ;;
    *)  echo "unknown --strategy '$STRATEGY'" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }

case "$OPENINGS" in
    guess|mystery) LIST="$OPENINGS" ;;
    *) [ -f "$OPENINGS" ] || { echo "no such openings file: $OPENINGS" >&2; exit 1; }
       LIST="$(basename "$OPENINGS")"; LIST="${LIST%.csv}"; LIST="${LIST%.txt}"
       [ -n "$TOP" ] && LIST="${LIST}_top${TOP}" ;;
esac

OUTDIR=data/shared/multiwordle
LOC=data/local/multiwordle
STEM="exact_${STRATEGY}_k1_${LIST}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output multiwordle_exact.py "$OUT" || exit 1

FLAGS="--strategy $STRATEGY -k 1 --openings $OPENINGS --out $OUT$EXTRA"
[ -n "$TOP" ] && FLAGS="$FLAGS --top $TOP"
[ "$DRY" = 1 ] && FLAGS="$FLAGS --dry-run"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] multiwordle exact $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/multiwordle_exact.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
