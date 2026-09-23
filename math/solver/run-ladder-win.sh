#!/bin/sh
# EXACT expected guesses AND win rate for a committed-word LADDER -- no simulation.
# math/ladder.py states the strategy and IS the source of truth; math/openexact.py
# holds the two recursions; tools/ladder_win.py is the driver.
#
#     bash solver/run-ladder-win.sh --from data/shared/ladder/ladderL5_k200.csv \
#         --opener trine --opener crane
#     bash solver/run-ladder-win.sh --from data/shared/ladder/ladderL5_wmystery_k100.csv --top 5
#     bash solver/run-ladder-win.sh --ladder "trine clasp:3 dough:1"
#
# WHAT IT ADDS TO run-ladder.sh.  That run SEARCHES for a ladder and reports
# `expected` only -- expected guesses OUTRIGHT, play never truncated -- because
# the ladder obeys no cap.  This prices a ladder it is HANDED and reports both:
#
#   mean      expected guesses OUTRIGHT.  The same quantity run-ladder.sh
#             reports, and the driver ASSERTS the two agree to 1e-6.
#   win_rate  the fraction of those SAME untruncated games finishing in --cap
#             guesses or fewer.  A REPORTING THRESHOLD on one play, not a rule
#             the strategy obeys.
#
# Neither belongs in a table with an optturns-family total, every one of which
# is an optimum SUBJECT TO a 6-guess guarantee.
#
# IT PRICES, IT DOES NOT SEARCH.  A ladder found by `run-ladder.sh -k K` is the
# best of the K openers EXAMINED and its total an UPPER BOUND; evaluating it
# exactly here does not make it the optimum, so that caveat travels with it.
#
# --from IS THE PREFERRED INPUT because it brings a free oracle: nothing is
# retyped, and the run's own `expected` came out of secondexact.c while this
# walks the same ladder in numpy off the committed pattern matrix.  The two
# share no code, so a mismatch EXITS rather than reporting.
#
# THE TAIL IS THE ANSWER LIST, always -- that is the strategy's definition, not
# a pool anyone chose -- so there is no --pool knob here.
set -u
MATH=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

SRC=""
CAP=6
TOP=""
DRYRUN=0
PICKS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --from)     SRC="$2";  shift 2 ;;
        --opener)   PICKS="$PICKS --opener '$2'"; shift 2 ;;
        --ladder)   PICKS="$PICKS --ladder '$2'"; shift 2 ;;
        --top)      TOP="$2";  shift 2 ;;
        --cap)      CAP="$2";  shift 2 ;;
        --dry-run)  DRYRUN=1;  shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$SRC" ] && [ -z "$PICKS" ]; then
    echo "give --from a ladder CSV (with --opener or --top), or --ladder" >&2
    echo "  'opener w2:T2 w3:T3'" >&2
    exit 1
fi
if [ -n "$SRC" ] && [ -z "$TOP" ] && [ -z "$PICKS" ]; then
    echo "--from needs --opener WORD (repeatable) or --top N: which ladders" >&2
    echo "  are priced IS the run's content, so it is named, not defaulted." >&2
    exit 1
fi

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the SQUARE guess x guess matrix (a committed word need" >&2
    echo "  not be an answer -- 'trine' is not -- so its replies come from the" >&2
    echo "  square matrix)." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

if [ -n "$SRC" ]; then
    [ -f "$SRC" ] || { echo "no such ladder CSV: $SRC" >&2; exit 1; }
    STEM="win_$(basename "$SRC" .csv)_cap${CAP}"
else
    STEM="win_named_cap${CAP}"
fi
OUTDIR=data/shared/ladder
LOC=data/local/ladder
OUT="$OUTDIR/$STEM.csv"

FLAGS="--cap $CAP"
[ -z "$SRC" ] || FLAGS="$FLAGS --from $SRC"
[ -z "$TOP" ] || FLAGS="$FLAGS --top $TOP"

echo "exact ladder win rates"
echo "  ladders    ${SRC:-named on the command line}${TOP:+ (best $TOP)}"
echo "  strategy   opener, then each rung while matched letters are below its"
echo "             threshold, then a uniformly random consistent ANSWER"
echo "  computes   expected guesses (UNCAPPED) and the win rate at <= $CAP"
echo "  exact      no sampling, no seed; a re-run reproduces the file"
[ -z "$SRC" ] || echo "  checked    every mean against $SRC's own expected"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"
[ -f "$OUT" ] && echo "  RESUMING from $OUT"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/ladder_win.py $FLAGS$PICKS --out $OUT"
    exit 0
fi

# Shared refuse-if-something-else-writes-this-file guard: two runs appending to
# one CSV would each read the other's rows as work already done.
. "$(dirname -- "$0")/_guard.sh"
guard_output ladder_win.py "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ladder-win $STEM" >> "$LOC/$STEM.log"
eval "\"$PY\" -u tools/ladder_win.py $FLAGS$PICKS --out \"$OUT\"" 2>&1 \
    | tee -a "$LOC/$STEM.log"
