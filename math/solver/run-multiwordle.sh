#!/bin/bash
# Simulate MULTIWORDLE games attached, with live output in this terminal.
#
#     bash solver/run-multiwordle.sh -k 4 -t 10000            # from math/, or anywhere
#     bash solver/run-multiwordle.sh -k 4 -t 10000 --seed 7
#     bash solver/run-multiwordle.sh -k 2 -t 50000 --opener rotan
#
# WHAT THIS MEASURES, precisely:
#
#   k hidden answers are drawn without replacement from the 2315 mystery words,
#   one per BOARD.  Every guess is played on every unsolved board at once.  A
#   fixed opener goes first; after that, each turn takes the unsolved board with
#   the FEWEST remaining candidates (ties by board index) and guesses one of its
#   candidates UNIFORMLY AT RANDOM.  A board is solved only when its answer is
#   actually played -- a board narrowed to one word still costs the naming
#   guess -- and a word played for one board solves any other board it happens
#   to match.  The score is the TOTAL guesses until all k boards are solved.
#
#   The reported number is the MEAN of that over -t random games, with a
#   standard error, because this is a Monte Carlo estimate and not an exact
#   computation.  Two runs differing by less than a couple of SEs have not
#   measured a difference.
#
#   THERE IS NO GUESS CAP, and none is needed -- the targeted board shrinks
#   every turn, so the process terminates on its own.  So this is expected
#   guesses OUTRIGHT, not the "optimum subject to a k-guess guarantee" that
#   every optturns/hardturns/ansall number in this repo reports.  The two are
#   different quantities; do not put them in one table.
#
# THE OPENER IS AN INPUT, NOT A RESULT.  The default below is the top of the
# SINGLETON ranking (tools/singletons.py) -- but that is a SINGLE-BOARD
# quantity, it optimises nothing about the k-board total, and it is not even
# unique (laten and rotan both score 41).  It is the strategy the video is
# currently exploring, chosen deliberately; change it with --opener and the
# result lands in its own file.
#
# USE THIS RATHER THAN CALLING tools/multiwordle_sim.py DIRECTLY.  It sets --out
# so the games outlive the terminal, names the file after every parameter that
# defines the experiment, and tees a log.  The script refuses to start without
# --out and --opener for the same reason.
#
# Each (k, opener, t, seed) is a different sample and gets its OWN file; re-running
# the same four reproduces that file exactly.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=""
T=""
SEED=0
# The user's current choice (2026-09-02), rank 1 by singletons over the 2315.
OPENER=laten
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--boards)  K="$2";        shift 2 ;;
        -t|--trials)  T="$2";        shift 2 ;;
        --seed)       SEED="$2";     shift 2 ;;
        --opener)     OPENER="$2";   shift 2 ;;
        --progress)   PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$K" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (how many boards)" >&2; exit 1 ;;
esac
case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (how many games)" >&2; exit 1 ;;
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

OUTDIR=data/shared/multiwordle
LOC=data/local/multiwordle
STEM="k${K}_${OPENER}_t${T}_s${SEED}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output multiwordle_sim.py "$OUT" || exit 1

FLAGS="-k $K -t $T --seed $SEED --opener $OPENER --out $OUT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] multiwordle sim $STEM" \
    | tee -a "$LOC/sim_$STEM.log"

"$PY" -u tools/multiwordle_sim.py $FLAGS 2>&1 | tee -a "$LOC/sim_$STEM.log"
