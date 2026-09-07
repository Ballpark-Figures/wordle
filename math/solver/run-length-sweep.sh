#!/bin/bash
# Find the optimal opener for a hello wordl game of a given WORD LENGTH, at a
# given DEPTH CAP.
#
#     bash solver/run-length-sweep.sh --length 6 --depth 5      # from math/, or anywhere
#     bash solver/run-length-sweep.sh --length 6 --depth 4
#     bash solver/run-length-sweep.sh --length 7 --depth 4 --order lb
#
# WHAT THIS SOLVES, precisely:
#
#   Over the hello wordl lists at length L -- dictionary.json as the legal
#   guesses, targets.json as the possible answers -- minimise the TOTAL guesses
#   summed over all answers, SUBJECT TO resolving every answer within --depth.
#
# THE CAP IS PART OF THE OBJECTIVE, and it is PINNED: one run answers the
# question for one cap.  A depth-5 pass and a depth-4 pass are two different
# quantities, not two attempts at the same one, and their results are NOT
# comparable as totals -- a tighter cap can only raise the total.  Each gets its
# own CSV for exactly that reason: seeding a depth-4 run's incumbent from a
# depth-5 total would cut every candidate and report nothing found.
#
# It reports THE OPTIMAL OPENER ONLY, not a total per opener (--optimal-only).
#
# ----------------------------------------------------------------- VISIT ORDER
#
# --order ssq (the DEFAULT here) walks openers by ascending sum of squared bin
# sizes -- the evenest splitters first.  --order lb walks by ascending root lower
# bound instead.  BOTH examine every opener, so both are exact; only the order
# differs, and with it what you have when you STOP EARLY.
#
# Why ssq is the default.  Ascending-LB order buys one extra thing: when an
# opener's lower bound exceeds the incumbent, everything after it is worse too,
# so the tail costs nothing.  That is a real advantage when the bound is tight.
# It is a counting bound and runs ~11-14% under the true optimum, so on these
# wider problems almost every opener bounds below the incumbent and the skip
# never fires (measured at length 6: 0 skips in 3596 openers).  With no tail
# proof to be had, the only job left is finding a good incumbent EARLY, which is
# what sum of squares is for.  Both orders keep the per-opener LB skip, which is
# sound regardless of order.
#
# STOPPING EARLY IS EXPECTED.  Ctrl-C at any point is safe: the CSV is flushed
# per improvement, so every opener that ever held the lead is already on disk.
# Re-running resumes -- the CSV re-seeds the incumbent and marks finished openers
# done.  What you do NOT get from a stopped run is a PROOF: the leader is "best
# of those examined, in a heuristic order", not the optimum.  Say it that way.
#
# LENGTH 3 IS NOT ON THE SAME FOOTING.  hello curates answers only at 4+, so the
# length-3 mystery.txt is OURS -- a frequency rule (zipf >= 3.0) applied to hello's
# 3-letter dictionary, built by build_letroso_lists.py, NOT build_wordlists.py.  Do
# not run `build_wordlists.py 3`: it would filter hello's targets.json (which has no
# 3-letter answers) to an EMPTY list and clobber ours.  A length-3 result is a
# modelling decision of ours; say so when quoting it.  See len3/README.md.
#
# PREREQUISITES, both from math/:
#     python3 build_wordlists.py                # once, lengths 4..11 (length 3 is separate; see above)
#     python3 build_patterns.py --length 6      # the matrix for THIS length
#     sh build.sh 6                             # in solver/, the binary for THIS length

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LENGTH=""
DEPTH=""
DEPTHMAX=""      # empty = pin --depth; set = escalate the first opener up to this
ORDER=ssq
TOPK=0           # 0 = exact. K > 0 restricts branching to the K evenest splits
THREADS=18
TTBITS=28

while [ $# -gt 0 ]; do
    case "$1" in
        --length)  LENGTH="$2";  shift 2 ;;
        --depth)     DEPTH="$2";    shift 2 ;;
        --depth-max) DEPTHMAX="$2"; shift 2 ;;
        --order)     ORDER="$2";    shift 2 ;;
        -k|--topk)   TOPK="$2";     shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$LENGTH" in
    3|4|5|6|7|8|9|10|11) ;;
    "") echo "usage: bash solver/run-length-sweep.sh --length <3..11> --depth <d> [--order ssq|lb]" >&2; exit 1 ;;
    *)  echo "unsupported length '$LENGTH' (3..11)" >&2; exit 1 ;;
esac
case "$DEPTH" in
    ''|*[!0-9]*) echo "--depth is required and must be a number (the cap IS the objective)" >&2; exit 1 ;;
esac
case "$ORDER" in
    ssq|lb) ;;
    *) echo "--order must be ssq or lb" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

BIN=./solver/optturns$LENGTH
PATS=data/local/patterns/patterns_len$LENGTH.npy
WORDS=data/shared/words/hello/len$LENGTH/guess.txt
OUTDIR=data/shared/optlen$LENGTH
LOC=data/local/optlen$LENGTH

[ -x "$BIN" ] || { echo "no $BIN -- run 'sh build.sh $LENGTH' in solver/" >&2; exit 1; }
[ -f "$WORDS" ] || { echo "no word lists for length $LENGTH -- run 'python3 build_wordlists.py'" >&2; exit 1; }
[ -f "$PATS" ] || {
    echo "no pattern matrix at $PATS" >&2
    echo "build it first:  python3 build_patterns.py --length $LENGTH" >&2
    exit 1
}

if pgrep -x "optturns$LENGTH" >/dev/null; then
    echo "optturns$LENGTH is already running (pid $(pgrep -x "optturns$LENGTH" | tr '\n' ' '))." >&2
    exit 1
fi

# EVERY K GETS ITS OWN FILES.  Different K values are different search spaces
# producing different (upper-bound) totals, so sharing a CSV would interleave
# incomparable results and let resume seed one run from another's numbers.  The
# TT is salted by K as well, so a shared tt.bin would fail verification anyway.
if [ "$TOPK" -gt 0 ]; then
    OUTDIR=$OUTDIR/k$TOPK
    LOC=$LOC/k$TOPK
fi

mkdir -p "$OUTDIR" "$LOC"

# One CSV per (depth, order).  Depth because the cap is the objective; order
# because a stopped run's partial results are only meaningful alongside the order
# that produced them, and resume would otherwise mix them.
# DISCOVER-THE-DEPTH mode.  With --depth-max the solver solves the FIRST opener
# at an escalating cap, takes the depth it actually needed, and holds every other
# opener to that -- so you do not have to know the right cap in advance.  An
# opener that later solves SHALLOWER still wins and drags the cap down with it,
# so the objective stays lexicographic (fewest worst-case guesses, then total).
#
# The cost is that the working depth then sits above --depth, which switches off
# the LB skip for the rest of the run.  Worth knowing, and worth ignoring wherever
# the bound does not fire anyway -- at length 4 it saturates at depth 3 and cannot
# tell any cap from any other, so there is nothing to lose.
#
# The file is named for the MODE, not a depth: the achieved depth is not known
# when the run starts, and naming it after --depth would label the results with a
# floor they did not run at.  The depth each row achieved is its 4th column.
if [ -n "$DEPTHMAX" ] && [ "$DEPTHMAX" -gt "$DEPTH" ]; then
    OUT=$OUTDIR/opener_totals_escalating_${ORDER}.csv
    DFLAG="--depth $DEPTH --depth-max $DEPTHMAX"
    MODE="depth $DEPTH escalating to $DEPTHMAX"
else
    OUT=$OUTDIR/opener_totals_d${DEPTH}_${ORDER}.csv
    DFLAG="--depth $DEPTH"
    MODE="depth $DEPTH PINNED"
fi

# The TT is salted by (guess set, answer set) but NOT by depth -- depth is part of
# each entry's own key -- so one table serves every depth at this length, and a
# later pass starts warm from an earlier one's work.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

KFLAG=""
if [ "$TOPK" -gt 0 ]; then
    KFLAG="--topk $TOPK"
    echo "*** --topk $TOPK: results are the best found within the RESTRICTED" >&2
    echo "*** branching, NOT optima.  Report them as upper bounds.  An INFEASIBLE" >&2
    echo "*** at a given depth may be an artifact of the restriction rather than a" >&2
    echo "*** fact about the problem, so a discovered depth can come out TOO DEEP." >&2
fi

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] length $LENGTH, $MODE, order $ORDER, topk $TOPK $WARM" \
    | tee -a "$LOC/sweep.log"

"$BIN" --length "$LENGTH" --sweep --optimal-only \
    --order "$ORDER" $KFLAG \
    --out "$OUT" \
    $DFLAG \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    --tt-save "$LOC/tt.bin" \
    2>&1 | tee -a "$LOC/sweep.log"

echo
echo "results: $OUT"
