#!/bin/bash
# Start the WEIGHTED sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-wturns-sweep.sh --weights data/shared/freqsearch/adv_topk1 --depth 6
#     bash solver/run-wturns-sweep.sh --weights ... --depth 6 --opener slate   # price one
#     bash solver/run-wturns-sweep.sh --weights ... --depth 6 -k 50            # beam
#
# WHAT THIS SOLVES.  The answers carry a WEIGHT, and the objective is
#
#     minimise  sum over answers of  w_a * (guesses spent on a)
#     subject to resolving EVERY answer within --depth
#
# reported as `expected` = that total divided by the summed weight.  It exists to
# answer "what does an OPTIMAL guesser spend against these weights?", the
# companion to `math/topk.py`, which is the GREEDY guesser the adversarial search
# (`math/freq_search.py`) tunes those weights against.
#
# --weights TAKES A STEM, not a file: <stem>.txt is the answer list and
# <stem>.weights the weights, both written by tools/freqweights.py.  They must
# AGREE position for position, and the solver checks that they do rather than
# assuming it.
#
# The PATTERN MATRIX for those answer columns is built automatically on the first
# run and cached under data/local/wturns/ -- it is a deterministic 12972 x NA
# derivation of the two lists, so it is regenerable bulk and follows the
# shared/local split rather than being committed beside them.
#
# THE CAP IS PART OF THE OBJECTIVE, so --depth is REQUIRED and every depth gets
# its OWN CSV.  A weighted optimum may deliberately spend a deeper line on a light
# answer to shorten a heavy one, so a depth-6 pass and a depth-7 pass are
# DIFFERENT QUANTITIES -- report a total as an optimum SUBJECT TO a <depth>-guess
# guarantee, never as minimum expected guesses.  INFEASIBLE is an expected result.
#
# NOT COMPARABLE WITH ANY optturns-FAMILY TOTAL, and not with a `topk.py` number
# either.  optturns minimises a COUNT over a different answer set; topk.py reports
# expected guesses OUTRIGHT with no cap.  Three objectives, three tables.
#
# THE OPENER ORDER IS THE WEIGHTED SPLIT SCORE (`--order ssq`): ascending
# sum over losing bins of (bin size x bin weight) -- the expected number of
# candidate WORDS still alive, which is topk.py's own ranking rule.  EVERY opener
# is still examined and the result is still exact; the order only decides WHEN.
# It is the right order for a run that may be stopped early: the openers most
# likely to win are visited first, so a halted run probably already holds the
# optimum -- but it has NOT PROVED it, because that proof needs the ascending
# LOWER-BOUND order (`--order lb`), under which the first opener bounding above
# the incumbent proves the whole tail is worse.  A partial run's leader is
# "the best of those examined so far", stated that way.
#
# EVERY OPENER PRINTS (--print-openers), so the terminal shows progress rather
# than only improvements.
#
# NO TREES FROM THE SWEEP.  --optimal-only never calls write_tree, so the
# winner's tree needs a follow-up at the SAME depth and weights:
#     ./solver/wturns --opener <winner> --depth <D> [--topk <K>] \
#         --answer-list <stem>.txt --weights <stem>.weights \
#         --patterns <stem>.patterns.npy --trees <dir>
#
# at the SAME depth, weights AND K -- a tree from a different K is a different
# strategy, so it would not sum to the total it is meant to explain.
#
# --opener W (repeatable) prices ONE opener exactly instead of sweeping: much
# cheaper, still exact for that opener, and an upper bound on the optimum.  Do
# this before launching the full sweep.
#
# ------------------------------------------------------------------ -k / --topk
#
# -k K RESTRICTS BRANCHING to the K evenest splits at EVERY branching point, and
# THE ROOT IS A BRANCHING POINT LIKE ANY OTHER -- so it also examines only K
# OPENERS, not all 12972.  Two consequences, and both must be stated whenever a
# number from such a run is quoted:
#
#   1. The total is an UPPER BOUND on the weighted optimum, not the optimum.
#   2. The winner is the best of the K openers EXAMINED, chosen by the same
#      weighted split score the sweep orders by -- never "the optimal opener".
#
# So a -k run answers "what can a good strategy do against these weights?", which
# is a different question from the exact sweep's "what is the least any strategy
# can spend?".  It is the right first move when the exact cost is unknown, which
# it is: price a beam, then decide whether the exact run is worth its time.
#
# EACH K IS A DIFFERENT STRATEGY, so it gets its OWN CSV, log and table --
# optimal_<stem>_d<D>_k<K>.csv -- exactly as each depth does.  K is in the TT
# salt too, so a table from one K cannot be read by another K or by the exact
# solver: under -k the stored values are the best found within the restricted
# branching, NOT exact optima, and a shared table would return a confidently
# wrong value that is merely a bound.  K=0 (the default) is the exact sweep and
# keeps the unsuffixed filenames, so existing runs are untouched.
#
# It composes with --opener: `--opener W -k K` prices that ONE opener under the
# beam, which is a bound on that opener's exact price rather than on the sweep's.
#
# --dry-run RESOLVES EVERYTHING and stops before the solver is called: which
# weights, which depth, which K, and above all which FILES it would write.  Use
# it for every change to this wrapper.  A partial CSV from a "quick check" is
# indistinguishable from a real result that died, and a bare invocation "just to
# see if the flags parse" starts a real multi-hour run.  It does NOT build the
# pattern matrix either, so it is free even on a fresh clone.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STEM=""
DEPTH=""
THREADS=18
TTBITS=28
OPENERS=""
TAGEXTRA=""
TOPK=0           # 0 = exact.  K > 0 beams branching AND the opener set; see above.
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --weights) STEM="$2";   shift 2 ;;
        --depth)   DEPTH="$2";  shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2"; shift 2 ;;
        --opener)  OPENERS="$OPENERS --opener $2"; shift 2 ;;
        -k|--topk) TOPK="$2";   shift 2 ;;
        --tag)     TAGEXTRA="_$2"; shift 2 ;;
        --dry-run) DRYRUN=1;    shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$STEM" ]; then
    echo "usage: bash solver/run-wturns-sweep.sh --weights <stem> --depth <d> [-k K] [--opener W]" >&2
    echo "--weights is required: the weights ARE the objective, so there is no default" >&2
    exit 1
fi
case "$DEPTH" in
    ''|*[!0-9]*)
        echo "usage: bash solver/run-wturns-sweep.sh --weights <stem> --depth <d>" >&2
        echo "--depth is required and must be a number (the cap IS part of the objective)" >&2
        exit 1 ;;
esac

case "$TOPK" in
    ''|*[!0-9]*) echo "-k must be a non-negative whole number (0 = the exact sweep)" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
[ -x ./solver/wturns ] || { echo "no ./solver/wturns -- run 'sh build.sh' in solver/" >&2; exit 1; }

ANSWERS="$STEM.txt"
WEIGHTS="$STEM.weights"
for f in "$ANSWERS" "$WEIGHTS"; do
    [ -f "$f" ] || { echo "missing $f -- write both with:" >&2
                     echo "  python3 tools/freqweights.py --from <freqsearch csv> --stem $STEM" >&2
                     exit 1; }
done

STEMNAME=$(basename "$STEM")
PATS=data/local/wturns/$STEMNAME.patterns.npy
mkdir -p data/local/wturns
if [ ! -f "$PATS" ] && [ "$DRYRUN" -eq 0 ]; then
    echo "building the pattern matrix for $ANSWERS (once, ~10s) -> $PATS"
    python3 build_patterns.py --answer-list "$ANSWERS" --out "$PATS" || exit 1
fi
# K IS IN THE FILENAME because each K is a different strategy -- a bound from
# one K read as another, or as the exact optimum, is a wrong number under a
# right-looking name.  K=0 keeps the unsuffixed names, so the exact sweep's files
# are exactly where they always were.
KTAG=""
[ "$TOPK" -gt 0 ] && KTAG="_k${TOPK}"
TAG=${STEMNAME}_d${DEPTH}${KTAG}${TAGEXTRA}
OUTDIR=data/shared/wturns
LOC=data/local/wturns/$TAG
[ "$DRYRUN" -eq 0 ] && mkdir -p "$OUTDIR" "$LOC"

KFLAG=""
[ "$TOPK" -gt 0 ] && KFLAG="--topk $TOPK"

# The warning differs by PATH, because -k means a different thing in each.  On
# the sweep the root is a branching point like any other, so the beam picks the
# openers too; with --opener the openers are the ones NAMED and only the
# follow-up branching is restricted.  Saying "only K openers are examined" in
# that second case would be simply false.
if [ "$TOPK" -gt 0 ]; then
    echo "*** -k $TOPK: branching is restricted to the $TOPK evenest splits at every" >&2
    if [ -n "$OPENERS" ]; then
        echo "*** node below the opener.  Each named opener's total is therefore an" >&2
        echo "*** UPPER BOUND on that opener's exact weighted price, not the price." >&2
    else
        echo "*** node INCLUDING THE ROOT, so only $TOPK openers are examined.  The total" >&2
        echo "*** is an UPPER BOUND and the winner is the best of those $TOPK -- never" >&2
        echo "*** report it as the optimum or as the optimal opener." >&2
    fi
fi

if [ -n "$OPENERS" ]; then
    OUT=$OUTDIR/openers_$TAG.csv
    FLAGS="$OPENERS $KFLAG"
    if [ "$TOPK" -gt 0 ]; then
        WHAT="named openers, beamed at k=$TOPK (upper bound per opener)"
    else
        WHAT="named openers, exact"
    fi
else
    OUT=$OUTDIR/optimal_$TAG.csv
    FLAGS="--sweep --optimal-only --order ssq --print-openers $KFLAG"
    if [ "$TOPK" -gt 0 ]; then
        WHAT="beam, best of the $TOPK openers examined, UPPER BOUND"
    else
        WHAT="full sweep, all openers examined, exact"
    fi
fi

if [ "$DRYRUN" -eq 1 ]; then
    echo "DRY RUN -- resolved, nothing written, no solver started"
    echo "  weights      $WEIGHTS"
    echo "  answers      $ANSWERS"
    echo "  patterns     $PATS"
    [ -f "$PATS" ] || echo "               (would be built on the real run)"
    echo "  depth        $DEPTH"
    echo "  topk         $TOPK  ($([ "$TOPK" -gt 0 ] && echo "UPPER BOUND, best of $TOPK openers examined" || echo "exact, every opener examined"))"
    echo "  threads      $THREADS"
    echo "  tt-bits      $TTBITS"
    echo "  what         $WHAT"
    echo "  results  ->  $OUT"
    echo "  log      ->  $LOC/sweep.log"
    echo "  flags        $FLAGS"
    exit 0
fi

. "$MATH/solver/_guard.sh"
guard_output wturns "$OUT" || exit 1

# --tt-save is deliberately absent -- see the long note in run-ultra-sweep.sh.
# It fires only on NORMAL completion, exactly when the table is worthless, and
# never on the interrupted run that would pay; 302 such snapshots once filled
# 728 GB of disk.  --tt-load stays, so a table made deliberately (tools/ttdump.py
# on a LIVE run) can still warm this one.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wturns weighted sweep ($WHAT)" \
    | tee -a "$LOC/sweep.log"
echo "  weights $WEIGHTS  answers $ANSWERS  depth $DEPTH  ->  $OUT" \
    | tee -a "$LOC/sweep.log"

./solver/wturns --depth "$DEPTH" $FLAGS \
    --answer-list "$ANSWERS" --weights "$WEIGHTS" --patterns "$PATS" \
    --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
    $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
