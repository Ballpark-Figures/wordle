#!/usr/bin/env bash
# Race every opening at once, eliminating as the evidence lands.  From math/:
#
#   bash solver/run-multiwordle-race.sh --strategy srank  -k 16
#   bash solver/run-multiwordle-race.sh --strategy minavg -k 4
#   bash solver/run-multiwordle-race.sh --strategy srank  -k 16 --pairs
#   bash solver/run-multiwordle-race.sh --strategy minavg -k 16 --dry-run
#
# Attached, tee'd to a log, and resumable: Ctrl-C whenever you like and re-run the
# SAME command to carry on from the last checkpoint (verified byte-identical to an
# uninterrupted run, including a kill part-way through a block).
#
# --strategy IS REQUIRED AND NAMES THE EXPERIMENT.  The three rules are stated in
# math/multiwordle.py:
#   srank   pick the board showing the best colour composition by the all-levels
#           pooled singleton ranking, ties at random, then guess one of that
#           board's candidates at random.  The human-usable one.
#   minavg  pick the WORD minimising the smallest average answers remaining across
#           the boards, ties on the next smallest and so on.  Deterministic, and
#           the expensive one.
#   greedy  the original: fewest candidates, ties by board index, random candidate.
#
# --pairs is shorthand for the top 10000 of the pair ranking:
#   --openings-from data/shared/singletons/pair_singletons.csv --top 10000
# THAT IS A SCREEN AND THE RANKING IS FOR A DIFFERENT QUESTION -- it ranks pairs by
# how many answers a blind opening isolates to a singleton, not by guesses at k
# boards.  A pair outside the top 10000 is never examined at all, so report such a
# run as "the best of the 10000 screened", never "the best pair".  Pairs are taken
# in the file's own order, one ordering each: under a blind opening the partition
# cannot depend on play order, and order reaches the score only through an
# incidental solve.
#
# THE HEAD OF A RACE IS THE BEST OF THE OPENINGS ENTERED, judged on the games
# actually played.  Elimination is against a MOVING leader, so a lucky early
# hundred games can push a better opening out; --sigma 5 is a generous cut, not a
# proof.  Widen it if you want more caution, never narrow it to "decide" sooner.
#
# MEASURED COST of the first 100-game block over all 12972 openings (18 threads):
# srank is seconds at every k; minavg runs about 0.1 h at k=1 or 2, 0.3 h at k=4,
# 0.6 h at k=8 and 1.9 h at k=16.  Later blocks double the games but the field
# shrinks, usually by much more.
#
# USE THIS RATHER THAN CALLING tools/multiwordle_race.py DIRECTLY.  It sets --out
# so a multi-day race outlives the terminal, names the file after every parameter
# that defines the experiment, tees a log, and refuses to start if something else
# is already writing that file.  The tool refuses to start without --out or
# --strategy for the same reason.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STRATEGY=""
K=""
SEED=0
SIGMA=5
BLOCK=100
GROWTH=2
OPENINGS="guess"
TOP=""
EXTRA=""
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --strategy)      STRATEGY="$2"; shift 2 ;;
        -k|--boards)     K="$2";        shift 2 ;;
        --seed)          SEED="$2";     shift 2 ;;
        --sigma)         SIGMA="$2";    shift 2 ;;
        --block)         BLOCK="$2";    shift 2 ;;
        --growth)        GROWTH="$2";   shift 2 ;;
        --openings|--words) OPENINGS="$2"; shift 2 ;;
        --openings-from) OPENINGS="$2"; shift 2 ;;
        --top)           TOP="$2";      shift 2 ;;
        --pairs)         OPENINGS="data/shared/singletons/pair_singletons.csv"
                         TOP=10000;     shift ;;
        --max-games)     EXTRA="$EXTRA --max-games $2"; shift 2 ;;
        --pair-at)       EXTRA="$EXTRA --pair-at $2";   shift 2 ;;
        --chunk)         EXTRA="$EXTRA --chunk $2";     shift 2 ;;
        --max-mem)       EXTRA="$EXTRA --max-mem $2";   shift 2 ;;
        --report)        EXTRA="$EXTRA --report $2";    shift 2 ;;
        --dry-run)       DRY=1;         shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# The strategy is a domain choice, so the WRAPPER carries no default for it: a
# defaulted objective is the greens scar, where one flag's default silently
# changed what a run meant while the filename went on claiming the other thing.
case "$STRATEGY" in
    srank|minavg|greedy) ;;
    "") echo "--strategy is required: srank, minavg or greedy." >&2
        echo "  The three are different strategies, not settings of one -- see" >&2
        echo "  math/multiwordle.py, which states each of them exactly." >&2
        exit 1 ;;
    *)  echo "unknown --strategy '$STRATEGY' (srank, minavg or greedy)" >&2
        exit 1 ;;
esac
case "$K" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (how many boards)" >&2; exit 1 ;;
esac
case "$SEED" in
    ''|*[!0-9]*) echo "--seed must be a non-negative number" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }
if [ "$STRATEGY" = srank ]; then
    [ -f data/shared/treestates/states_optturns_top1000.csv ] || {
        echo "srank needs data/shared/treestates/states_optturns_top1000.csv" >&2
        echo "  -- rebuild it with 'bash solver/run-tree-states.sh --top 1000'" >&2
        exit 1; }
fi
case "$OPENINGS" in
    guess|mystery) ;;
    *) [ -f "$OPENINGS" ] || { echo "no such openings file: $OPENINGS" >&2; exit 1; } ;;
esac

# The list's name, matching what the tool puts in the stem.
case "$OPENINGS" in
    guess|mystery) LIST="$OPENINGS" ;;
    *) LIST="$(basename "$OPENINGS")"; LIST="${LIST%.csv}"; LIST="${LIST%.txt}"
       [ -n "$TOP" ] && LIST="${LIST}_top${TOP}" ;;
esac

OUTDIR=data/shared/multiwordle
LOC=data/local/multiwordle
STEM="race_${STRATEGY}_k${K}_${LIST}_sig${SIGMA}_s${SEED}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is by
# process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output multiwordle_race.py "$OUT" || exit 1

FLAGS="--strategy $STRATEGY -k $K --seed $SEED --sigma $SIGMA --block $BLOCK"
FLAGS="$FLAGS --growth $GROWTH --openings $OPENINGS --out $OUT$EXTRA"
[ -n "$TOP" ] && FLAGS="$FLAGS --top $TOP"
[ "$DRY" = 1 ] && FLAGS="$FLAGS --dry-run"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] multiwordle race $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/multiwordle_race.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
