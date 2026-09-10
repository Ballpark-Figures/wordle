#!/bin/bash
# Start the ADVERSARIAL WEIGHT SEARCH attached, with live output in this terminal.
#
#     bash solver/run-freq-search.sh              # topk 1, the default guesser
#     bash solver/run-freq-search.sh -k 2
#     bash solver/run-freq-search.sh -k 10 --objective wturns   # same objective,
#                                                               # C solver, threaded
#
# --objective PICKS THE EVALUATOR, NOT THE OBJECTIVE.  The guesser exists twice:
# as topk.py's numba kernels (`topk`, the default), and as solver/wturns under
# --topk K (`wturns`), whose ranking rule IS topk.py's -- ascending sum over
# LOSING bins of bin size x bin weight, ties on the lowest guess index.  At K=1
# neither minimises anything, both just play the top-ranked guess, and on the
# real lists they agree: the k=1 hill-climb ends at 3.978171252747317 and
# `wturns --topk 1` on those weights reports 3.97817.
# tools/checkwturnsobjective.py diffs them EXACTLY, on integer totals.
#
# WHY YOU WOULD SWITCH.  topk.py has no transposition table and runs on one core;
# wturns has both.  MEASURED at k=10 on the real problem: one topk.py evaluation
# takes ~370 s, while wturns solves its ten openers in 4.3-5.3 s each across 18
# threads.  The switch costs one sort and one column permutation of the pattern
# matrix per evaluation (~1.35 s, CONSTANT in K) -- noise beside a k>=2
# evaluation, and MORE than a k=1 evaluation, which is why `topk` stays the
# default and this is for the beam.
#
# THE CAP.  topk.py has no depth cap and wturns always does, so --depth must stay
# slack; a binding cap RAISES rather than quietly answering a different question.
#
# WHAT THIS COMPUTES, precisely:
#
#   A per-(letter, position-pattern) MULTIPLIER for every pattern occurring in
#   the candidate list (data/shared/words/custom.txt).  A word's weight is the
#   PRODUCT of its patterns' multipliers, and the search hill-climbs those
#   multipliers to MAXIMISE the weight-averaged number of guesses a topk-K
#   guesser spends -- a word-setter playing against a guesser that sees the
#   weights.  Ported phase for phase from the hangman video's freq_search.py.
#
#   THERE IS NO DEPTH CAP.  This is expected guesses outright, NOT the "expected
#   guesses subject to a 6-guess guarantee" that every optturns/hardturns number
#   in this repo reports.  The two are not comparable.
#
# USE THIS RATHER THAN CALLING math/freq_search.py DIRECTLY.  It sets --out, so
# the run's accepted changes land in a CSV that outlives the terminal, and tees
# a log.  freq_search.py refuses to start without --out for the same reason.
#
# Each K is a DIFFERENT GUESSER and so a different objective; each gets its own
# CSV and log.  Re-running overwrites that K's CSV -- the search always restarts
# from all-ones, there is no resume.
#
# Output is tee'd, so search.log gets every line as well as your terminal.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TOPK=1
ANSWERS=""
MAXLOOPS=""
OBJECTIVE="topk"        # default a human reads, forwarded explicitly below
DEPTH=9
THREADS=18
TTBITS=24

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--topk)    TOPK="$2";     shift 2 ;;
        --objective)  OBJECTIVE="$2"; shift 2 ;;
        --depth)      DEPTH="$2";    shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --tt-bits)    TTBITS="$2";   shift 2 ;;
        --answers)    ANSWERS="$2";  shift 2 ;;
        --max-loops)  MAXLOOPS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOPK" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (the guesser's beam width)" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/shared/words/custom.txt ] || {
    echo "no custom.txt -- run '$PY build_freq_wordlist.py' first" >&2; exit 1; }
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "no patterns_full.npy -- run '$PY build_patterns.py --full' first" >&2; exit 1; }

if pgrep -f "freq_search.py" >/dev/null; then
    echo "freq_search.py is already running (pid $(pgrep -f freq_search.py | tr '\n' ' '))." >&2
    exit 1
fi

OUTDIR=data/shared/freqsearch
LOC=data/local/freqsearch
OUT=$OUTDIR/topk$TOPK.csv
mkdir -p "$OUTDIR" "$LOC"

case "$OBJECTIVE" in
    topk|wturns) ;;
    *) echo "--objective must be topk or wturns" >&2; exit 1 ;;
esac
if [ "$OBJECTIVE" = wturns ]; then
    [ -x ./solver/wturns ] || { echo "no ./solver/wturns -- run 'sh build.sh' in solver/" >&2; exit 1; }
fi

# The evaluator is forwarded EXPLICITLY, never left to the script's default --
# two places owning one decision is the greens scar.
FLAGS="-k $TOPK --out $OUT --objective $OBJECTIVE"
[ "$OBJECTIVE" = wturns ] && FLAGS="$FLAGS --depth $DEPTH --threads $THREADS --tt-bits $TTBITS"
[ -n "$ANSWERS" ] && FLAGS="$FLAGS --answers $ANSWERS"
[ -n "$MAXLOOPS" ] && FLAGS="$FLAGS --max-loops $MAXLOOPS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] adversarial weight search (topk $TOPK, objective $OBJECTIVE)" \
    | tee -a "$LOC/search_topk$TOPK.log"

"$PY" -u freq_search.py $FLAGS 2>&1 | tee -a "$LOC/search_topk$TOPK.log"
