#!/bin/bash
# Where the EV loss goes: the gap to OPTIMAL, split by the opener's grey count.
#
#     bash solver/run-second-loss.sh --opener spilt \
#         --second-from data/shared/secondword/second_guess_g3.csv
#     bash solver/run-second-loss.sh --opener spilt -n 1000     # tighter
#     bash solver/run-second-loss.sh --opener spilt             # the PLAIN opener
#
# WHAT IT COMPUTES.  Every answer is played -n times under the strategy, and its
# mean is compared with what that answer costs under the OPTIMAL tree for the
# SAME opener.  Answers are grouped by how many GREYS the opener's reply shows,
# and each group's share of the whole gap is reported.  The contributions sum to
# the gap, so it is a decomposition rather than a set of separate numbers.
#
# Within each grey bucket the gap is split further into WHY it is there:
#   word-choice loss = B - A   (our forced 2nd word vs the optimal one, both
#                               played optimally afterward)
#   followup loss    = C - B   (our random followup vs optimal, given our word)
# where A is the optimal tree, B is our 2nd word then OPTIMAL continuation (an
# exact small solve, capped at 6 like A), and C is the simulated strategy.  A gate
# forces each reply's own optimal 2nd move and checks that B reproduces A exactly.
#
# "OPTIMAL" MEANS TWO THINGS HERE AND BOTH ARE LOAD-BEARING:
#
#   * THE SAME OPENER, not the best one.  That is the only comparison that
#     decomposes -- each bucket's gap is then about how the strategy plays THAT
#     bucket, with the opener held fixed.  The opener's own cost is a separate
#     single number (spilt 3.48121 against salet's 3.42117) and belongs to no
#     bucket.
#   * THE CAPPED OPTIMUM: minimum guesses SUBJECT TO solving every answer within
#     six, which is what optturns computed and what the committed trees are.  The
#     strategy is UNCAPPED.  A capped optimum is >= the unconstrained one, so
#     every gap reported is a LOWER BOUND on the loss against true optimal play.
#
# THE ESTIMATOR IS STRATIFIED -- every answer played the same number of times --
# so the answer weights are EXACT and the standard error is the strategy's coin
# flips alone.  The spread between answers is the thing being decomposed, not
# noise in it.
#
# It reads the committed optimal tree for the opener, so the opener must be one
# the sweep has finished.  The gate is built into the tool and always runs: the
# tree must sum to the total the CSV records, cover every answer once, and the
# bucket contributions must sum to the gap.
#
# Output: data/shared/secondloss/, log under data/local/secondloss/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OPENER=""
SECONDFROM=""
# Defaults a HUMAN reads, forwarded explicitly.  `answer` is the follow-up every
# second-word race used, so a loss breakdown matches those runs by default.
FALLBACK=answer
N=100
SEED=0
PROGRESS=""
DRYRUN=0
SPLITMV=0
BYCASE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --opener)      OPENER="$2";     shift 2 ;;
        --second-from) SECONDFROM="$2"; shift 2 ;;
        --fallback)    FALLBACK="$2";   shift 2 ;;
        -n|--games)    N="$2";          shift 2 ;;
        --seed)        SEED="$2";       shift 2 ;;
        --progress)    PROGRESS="$2";   shift 2 ;;
        --split-matched-vowels) SPLITMV=1; shift ;;
        --by-case)     BYCASE=1;         shift ;;
        --dry-run)     DRYRUN=1;        shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

[ -n "$OPENER" ] || { echo "--opener is required: the decomposition is for ONE" >&2
                      echo "  opener, against the optimal tree for that same opener" >&2
                      exit 1; }
case "$FALLBACK" in answer|guess) ;; *) echo "--fallback must be answer or guess" >&2; exit 1 ;; esac
case "$N$SEED" in ''|*[!0-9]*) echo "-n and --seed must be numbers" >&2; exit 1 ;; esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }

LABEL=plain
if [ -n "$SECONDFROM" ]; then
    [ -f "$SECONDFROM" ] || { echo "no such second-word table: $SECONDFROM" >&2; exit 1; }
    # the condition's own name, from the table's stamp: one owner for it
    LABEL=$(sed -n 's/^# settings .*fire=\([^ ]*\).*/\1/p' "$SECONDFROM" | head -1)
    [ -n "$LABEL" ] || LABEL=g$(sed -n 's/^# settings .*min_grays=\([0-9]*\).*/\1/p' "$SECONDFROM" | head -1)
fi

OUTDIR=data/shared/secondloss
LOC=data/local/secondloss
# The matched-vowel split is a different report, so it gets its own filename.
MVTAG=""
[ "$SPLITMV" = 0 ] || MVTAG="_mv"
[ "$BYCASE" = 0 ]  || MVTAG="_case"
STEM="loss_${OPENER}_${LABEL}_${FALLBACK}_n${N}_s${SEED}${MVTAG}"
OUT="$OUTDIR/$STEM.csv"

echo "EV-loss breakdown"
echo "  opener     $OPENER"
echo "  strategy   ${SECONDFROM:-(none: the plain opener)}  (fires on $LABEL)"
echo "  follow-up  $FALLBACK"
echo "  games      $N per answer x 2315 answers, seed $SEED"
[ "$SPLITMV" = 0 ] || echo "  report     3- and 4-grey split by matched vowels"
[ "$BYCASE" = 0 ]  || echo "  report     the STRATEGY'S OWN cases, one row per group"
echo "  out        $OUT"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    exit 0
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output secondloss.py "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] second-loss $STEM" | tee -a "$LOC/$STEM.log"

FLAGS="--opener $OPENER --fallback $FALLBACK --n $N --seed $SEED --out $OUT"
[ -z "$SECONDFROM" ] || FLAGS="$FLAGS --second-from $SECONDFROM"
[ -z "$PROGRESS" ]   || FLAGS="$FLAGS --progress $PROGRESS"
[ "$SPLITMV" = 0 ]   || FLAGS="$FLAGS --split-matched-vowels"
[ "$BYCASE" = 0 ]    || FLAGS="$FLAGS --by-case"

"$PY" -u tools/secondloss.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
