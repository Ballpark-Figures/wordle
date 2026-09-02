#!/bin/bash
# Sweep OPENERS for multiwordle: the same fixed number of trials for each word.
# Attached, with live output in this terminal.
#
#     bash solver/run-multiwordle-sweep.sh -k 4 -t 1000        # from math/, or anywhere
#     bash solver/run-multiwordle-sweep.sh -k 4 -t 1000 --words mystery
#     bash solver/run-multiwordle-sweep.sh -k 4 -t 5000 --limit 500
#     bash solver/run-multiwordle-sweep.sh -k 4 -t 200 --prefix clint
#
#     # STAGE 2: re-run only the words a wide screen left standing, at a fresh seed
#     bash solver/run-multiwordle-sweep.sh -k 1 -t 10000 --seed 1 \
#         --shortlist-from data/shared/multiwordle/sweep_k1_t1000_s0_guess.csv
#
# WHAT THIS COMPUTES: for every word of the list, the mean total guesses over -t
# multiwordle games at -k boards, under the strategy in math/multiwordle.py.  It
# is the multiwordle analogue of an opener sweep -- which opener is best AT THIS
# GAME, rather than borrowing a ranking computed for a single board.
#
# TWO THINGS TO KNOW BEFORE READING A RESULT:
#
#   COMMON RANDOM NUMBERS.  Every opener faces the IDENTICAL sequence of -t
#   answer draws (the draw stream is re-seeded per word and kept separate from
#   the strategy's random picks), so DIFFERENCES between words are far less noisy
#   than their individual standard errors suggest.  The flip side: a sweep cell
#   and a run-multiwordle.sh run at the same seed are different samples and will
#   not match to the last digit.
#
#   THE WINNER'S CURSE.  The best-looking mean over 12972 words is biased
#   optimistic -- it belongs to whichever word drew the kindest sample.  THE HEAD
#   OF A SWEEP IS A SHORTLIST, NOT A WINNER.  Screen wide at small -t, then
#   re-run the top few at large -t or a fresh --seed and compare those.
#
#   --shortlist-from SWEEP.csv does that second stage in one command: it cuts a
#   word list from that sweep (--se N standard errors of the best word's mean,
#   default 10; or --shortlist-top N) and sweeps only those words.  USE A FRESH
#   --seed WITH IT: the draw stream is seeded per word, so stage 2 at the same
#   seed replays stage 1's games as its first -t, re-using the sample that chose
#   the shortlist and carrying its selection bias forward.  The wrapper says so
#   if you forget.
#
# COST, measured: a game costs roughly 30us at k=1 rising to ~95us at k=6, so
# 12972 words is about
#
#     k=4, -t 1000    ~15 min          k=4, -t 10000   ~2.5 h
#     k=6, -t 1000    ~21 min          k=6, -t 10000   ~3.4 h
#
# --limit N takes a PREFIX of the list in ITS OWN ORDER (alphabetical for the
# word lists, best-first for a shortlist), and the run is RESUMABLE per word, so
# a Ctrl-C costs at most the word in flight.
#
# --prefix "W..." fixes the opening words BEFORE the swept one, so the sweep can
# ask "given clint, which second word is best".
#
# Each (k, t, seed, word list, prefix) is a different sweep and gets its own file.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=""
T=""
SEED=0
WORDS=guess
PREFIX=""
LIMIT=""
PROGRESS=""
SHORTFROM=""
SHORTSE=10
SHORTTOP=""

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--boards)  K="$2";        shift 2 ;;
        -t|--trials)  T="$2";        shift 2 ;;
        --seed)       SEED="$2";     shift 2 ;;
        --words)      WORDS="$2";    shift 2 ;;
        --prefix)     PREFIX="${PREFIX:+$PREFIX }$2"; shift 2 ;;
        --limit)      LIMIT="$2";    shift 2 ;;
        --shortlist-from) SHORTFROM="$2"; shift 2 ;;
        --se)             SHORTSE="$2";   shift 2 ;;
        --shortlist-top)  SHORTTOP="$2";  shift 2 ;;
        --progress)   PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$K" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (how many boards)" >&2; exit 1 ;;
esac
case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (trials PER WORD)" >&2; exit 1 ;;
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
mkdir -p "$OUTDIR"

if [ -n "$SHORTFROM" ]; then
    [ -f "$SHORTFROM" ] || { echo "no such sweep file: $SHORTFROM" >&2; exit 1; }
    [ "$WORDS" = guess ] || {
        echo "--shortlist-from replaces --words; pass only one" >&2; exit 1; }
    SRCSTEM=$(basename "$SHORTFROM" .csv)
    if [ -n "$SHORTTOP" ]; then
        CUT="--top $SHORTTOP"; CUTNAME="top$SHORTTOP"
    else
        CUT="--se $SHORTSE"; CUTNAME="se$SHORTSE"
    fi
    WORDS="$OUTDIR/shortlist_${SRCSTEM#sweep_}_$CUTNAME.txt"
    "$PY" tools/multiwordle_shortlist.py --from "$SHORTFROM" $CUT --out "$WORDS" \
        || exit 1
    # Stage 2 at stage 1's seed replays stage 1's games as its first -t, which
    # re-uses the sample that chose the shortlist.  Loud, not fatal: it is a
    # legitimate thing to do deliberately.
    SRCSEED=$(echo "$SRCSTEM" | sed -n 's/.*_s\([0-9][0-9]*\)_.*/\1/p')
    if [ "$SRCSEED" = "$SEED" ]; then
        echo "WARNING: stage 2 is using seed $SEED, the same seed as $SRCSTEM." >&2
        echo "  Its first $T draws ARE stage 1's, so this re-uses the sample that" >&2
        echo "  chose the shortlist.  Pass a fresh --seed for an independent test." >&2
    fi
fi

STEM="sweep_k${K}_t${T}_s${SEED}_$(basename "$WORDS" .txt)"
[ -n "$PREFIX" ] && STEM="${STEM}_after-$(echo "$PREFIX" | tr ' ' '-')"
[ -n "$LIMIT" ] && STEM="${STEM}_lim$LIMIT"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output multiwordle_sweep.py "$OUT" || exit 1

# One --prefix per word: FLAGS is word-split unquoted below, so a single
# --prefix "a b" would arrive as two arguments and be rejected.
FLAGS="-k $K -t $T --seed $SEED --words $WORDS --out $OUT"
for w in $PREFIX; do FLAGS="$FLAGS --prefix $w"; done
[ -n "$LIMIT" ] && FLAGS="$FLAGS --limit $LIMIT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] multiwordle opener sweep $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/multiwordle_sweep.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
