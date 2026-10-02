#!/bin/bash
# Settle a sweep's FINALISTS by paired differences, attached, live output.
#
#     bash solver/run-wordle-paired.sh --from data/shared/wordlesim/sweep_....csv
#     bash solver/run-wordle-paired.sh --from ....csv -t 500000 --top 8
#
# WHAT IT DOES.  Takes the openings a sweep's last pass left standing and plays
# them against EACH OTHER over the same games, reporting each one's gap to the
# leader with a PAIRED standard error.  At the end of a cascade the gaps are far
# smaller than the individual errors, and those errors are too conservative
# because the openings played the same games -- the shared variance cancels in a
# difference.  tools/paired_compare.py states the estimator and the couplings.
#
# EVERYTHING IS READ FROM THE SOURCE FILE: the finalists, the follow-up, the
# --pair-adaptive threshold, the SECOND-WORD TABLE (--second-from, if the
# cascade ran under one), the trial count and the seed.  Comparing finalists
# under a different strategy from the one that selected them would be a different
# experiment wearing the same name, so the sweep's own settings are the defaults.
# The SEED is the one exception -- it advances by one, because the finalists were
# chosen by the source's own games and re-using that sample would judge them on
# the very draws that selected them.  -t, --seed, --fallback and --pair-adaptive
# all override.
#
# THE OUTPUT IS A SWEEP-SHAPED CSV: `word,trials,mean,stderr` first, then the
# paired columns, so tools/sweep_shortlist.py and anything else that reads a sweep
# reads this too.
#
# IT COMPARES FINALISTS, NOT FIELDS.  Every opening plays every game, so the cost
# is (openings x trials); --max-openings refuses more than 50 unless raised
# deliberately, and --top N takes the best N of the source instead.
#
# CHAINING ROUNDS.  A paired CSV is itself a valid --from, and then the cut is on
# the PAIRED SIGMA (--sigma, default 5): everything within that many paired sigma
# of the leader survives and the trials advance one rung of the 1-2-3-5 ladder.
# That is the right cut for this file -- its own `stderr` column is the
# conservative unpaired error the pairing exists to replace.
#
# RANKING BY WIN RATE instead of expected turns: --rank win_rate, which is
# INHERITED from the source when the source recorded it, so a win-rate cascade
# stays one all the way down.  The per-game score becomes the 0/1 win indicator,
# so the paired difference is a per-game win/lose difference -- and that has no
# zero-error problem: its error comes from how often the two openings DISAGREE,
# not from how close the rate is to 100%.
#
# --dry-run resolves the name and the count and stops.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FROM=""
T=""
SEED=""
TOP=""
SIGMA=""
RANK=""
MAXOPEN=""
FALLBACK=""
ADAPT=""
PROGRESS=""
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --from)           FROM="$2";     shift 2 ;;
        -t|--trials)      T="$2";        shift 2 ;;
        --seed)           SEED="$2";     shift 2 ;;
        --top)            TOP="$2";      shift 2 ;;
        --sigma)          SIGMA="$2";    shift 2 ;;
        --rank)           RANK="$2";     shift 2 ;;
        --max-openings)   MAXOPEN="$2";  shift 2 ;;
        --fallback)       FALLBACK="$2"; shift 2 ;;
        --pair-adaptive)  ADAPT="$2";    shift 2 ;;
        --progress)       PROGRESS="$2"; shift 2 ;;
        --dry-run)        DRYRUN=1;      shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

[ -n "$FROM" ] || { echo "--from SWEEP.csv is required" >&2; exit 1; }
cd "$MATH" || exit 1
[ -f "$FROM" ] || { echo "no such sweep: $FROM" >&2; exit 1; }

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

FLAGS="--from-sweep $FROM"
[ -n "$T" ]        && FLAGS="$FLAGS -t $T"
[ -n "$SEED" ]     && FLAGS="$FLAGS --seed $SEED"
[ -n "$TOP" ]      && FLAGS="$FLAGS --top $TOP"
[ -n "$SIGMA" ]    && FLAGS="$FLAGS --sigma $SIGMA"
[ -n "$RANK" ]     && FLAGS="$FLAGS --rank $RANK"
[ -n "$MAXOPEN" ]  && FLAGS="$FLAGS --max-openings $MAXOPEN"
[ -n "$FALLBACK" ] && FLAGS="$FLAGS --fallback $FALLBACK"
[ -n "$ADAPT" ]    && FLAGS="$FLAGS --pair-adaptive $ADAPT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# The name is derived by the tool itself, so the rule lives in one place.
RESOLVED=$("$PY" tools/paired_compare.py $FLAGS --print-stem) || exit 1
STEM=$(echo "$RESOLVED" | head -1)
NOPEN=$(echo "$RESOLVED" | tail -1)

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
mkdir -p "$OUTDIR" "$LOC"
OUT="$OUTDIR/$STEM.csv"

if [ "$DRYRUN" = 1 ]; then
    echo "dry run: would write $OUT"
    echo "  $NOPEN openings from $(basename "$FROM")"
    exit 0
fi

. "$MATH/solver/_guard.sh"
guard_output paired_compare.py "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle paired compare $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/paired_compare.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
