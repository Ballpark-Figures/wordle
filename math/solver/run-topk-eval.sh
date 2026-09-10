#!/bin/bash
# Evaluate the top-K guesser ONCE, attached, with live output in this terminal.
#
#     bash solver/run-topk-eval.sh                                  # uniform, k=1
#     bash solver/run-topk-eval.sh -k 2
#     bash solver/run-topk-eval.sh --weights data/shared/freqsearch/adv_topk1
#
# WHAT THIS ANSWERS.  "What does the topk-K guesser spend against this weighting
# of this candidate list?"  It is the BASELINE an adversarial number is quoted
# against: run it `uniform` to get what the guesser spends before the adversary
# touches anything, then compare with the final expected_guesses of the matching
# data/shared/freqsearch/topk<K>.csv.
#
#   THERE IS NO DEPTH CAP.  Expected guesses OUTRIGHT -- the same footing as
#   multiwordle / foximax / wordlesim, and NOT the "optimum subject to a 6-guess
#   guarantee" that every optturns / hardturns / ansall / wturns total reports.
#   Never put the two in one table.
#
# THE WEIGHTING IS THE OBJECTIVE, so this wrapper carries a DEFAULT A HUMAN READS
# (uniform) and forwards it EXPLICITLY; tools/topk_eval.py itself refuses without
# one.  Two weightings over one list are two different questions:
#
#     uniform    every listed candidate equally likely -- the hill-climb's
#                all-ones starting point
#     <stem>     a weight stem from tools/freqweights.py, e.g.
#                data/shared/freqsearch/adv_topk1.  Zero-weight words are
#                dropped, as topk.py drops them.
#
# K IS PART OF THE STRATEGY and is in the filename too -- each K is a different
# guesser, so a k=1 number and a k=2 number are two results, not one refined.
#
# THE FREE ORACLE: `--weights data/shared/freqsearch/adv_topk1 -k 1` must
# reproduce the LAST expected_guesses in data/shared/freqsearch/topk1.csv.  Same
# guesser, same weights, so a disagreement is a bug in the reconstruction or the
# driver -- not a number that moved.
#
# --dry-run resolves everything and stops before any solve, so checking this
# wrapper's plumbing never costs a run or leaves a half-written CSV.
#
# Output is tee'd, so the log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TOPK=1                                       # default a human reads, forwarded below
WEIGHTS="uniform"                            # ditto
ANSWERS=""                                   # resolved below; stem-dependent
DRYRUN=0
EXTRA=""

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--topk)   TOPK="$2";    shift 2 ;;
        --weights)   WEIGHTS="$2"; shift 2 ;;
        --answers)   ANSWERS="$2"; shift 2 ;;
        --no-numba)  EXTRA="$EXTRA --no-numba"; shift 1 ;;
        --dry-run)   DRYRUN=1;     shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOPK" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (the guesser's beam width)" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1
FULLPAT=data/local/patterns/patterns_full.npy

# The candidate list: the stem's own .txt when weights came from one (they are
# paired position for position), else the frequency-cut list.
if [ "$WEIGHTS" = uniform ]; then
    [ -n "$ANSWERS" ] || ANSWERS=data/shared/words/custom.txt
    [ -f "$ANSWERS" ] || { echo "missing $ANSWERS" >&2; exit 1; }
    WNAME=uniform
    AFLAG="--answers $ANSWERS"
else
    for f in "$WEIGHTS.txt" "$WEIGHTS.weights"; do
        [ -f "$f" ] || { echo "missing $f -- write both with:" >&2
                         echo "  python3 tools/freqweights.py --from <freqsearch csv> --stem $WEIGHTS" >&2
                         exit 1; }
    done
    ANSWERS="$WEIGHTS.txt"
    WNAME=$(basename "$WEIGHTS")
    AFLAG=""
fi

ASTEM=$(basename "$ANSWERS"); ASTEM=${ASTEM%.txt}
# A weight stem names its own list, so WNAME and ASTEM are the same string there
# -- do not repeat it.  The name still carries all three of (k, weighting, list),
# since with a stem the list is implied by the weighting.
if [ "$WNAME" = "$ASTEM" ]; then
    TAG=k${TOPK}_${WNAME}
else
    TAG=k${TOPK}_${WNAME}_${ASTEM}
fi
OUTDIR=data/shared/topkeval
LOC=data/local/topkeval
OUT=$OUTDIR/$TAG.csv

if [ "$DRYRUN" -eq 1 ]; then
    echo "DRY RUN -- resolved, nothing written, no solve started"
    echo "  k            $TOPK"
    echo "  weighting    $WNAME"
    echo "  answers      $ANSWERS"
    echo "  results  ->  $OUT"
    echo "  log      ->  $LOC/$TAG.log"
    if [ -f "$FULLPAT" ]; then
        echo "  matrix       $FULLPAT  (present)"
    else
        echo "  matrix       $FULLPAT  MISSING -- the real run would refuse;"
        echo "               build it once with '../.venv/bin/python build_patterns.py --full'"
    fi
    exit 0
fi

# topk.py slices the SQUARE all-words matrix, which is gitignored under
# data/local/ and so never arrives with a clone.  Refuse with the command rather
# than let numpy fail somewhere less obvious.
if [ ! -f "$FULLPAT" ]; then
    echo "no $FULLPAT -- build it once with:" >&2
    echo "  ../.venv/bin/python build_patterns.py --full     # ~18s, 168 MB" >&2
    exit 1
fi

mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output topk_eval.py "$OUT" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || PY=python3

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] topk eval (k=$TOPK, weighting=$WNAME)" \
    | tee -a "$LOC/$TAG.log"

"$PY" -u tools/topk_eval.py --k "$TOPK" --weights "$WEIGHTS" $AFLAG \
    --out "$OUT" $EXTRA \
    2>&1 | tee -a "$LOC/$TAG.log"
