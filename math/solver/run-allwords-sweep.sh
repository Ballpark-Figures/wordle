#!/bin/bash
# Start the ALL-WORDS sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-allwords-sweep.sh                    # from math/, or anywhere
#     bash solver/run-allwords-sweep.sh --threads 12 --tt-bits 26
#
# WHAT THIS SOLVES, precisely:
#
#   Minimise the TOTAL guesses summed over all 12972 legal words, where every one
#   of those words is BOTH a possible answer and a legal guess, SUBJECT TO
#   resolving every answer within 6 guesses.
#
# It reports THE OPTIMAL OPENER ONLY -- not a total per opener.  That is the
# point of --optimal-only, and it is what makes the run tractable: a full sweep
# spends nearly all its time proving exact totals for openers that were never
# going to win.
#
# HOW THE PRUNING WORKS.  Each opener has a root lower bound -- NA plus the LB of
# every surviving partition -- computable in O(NA) with no search at all.  The
# run screens all 12972 openers by that bound, sorts ASCENDING, and walks them
# with a running incumbent.  Two cuts follow:
#
#   1. If an opener's LB exceeds the incumbent, skip it.  Because the order is
#      ascending, that also proves every opener AFTER it is worse -- the tail
#      costs O(1) each.
#   2. Within an opener, partitions are solved largest-first and abandoned as
#      soon as (solved so far + LB of the rest) exceeds the incumbent.
#
# TIES ARE KEPT.  Both cuts test `> incumbent`, never `>=`, so every opener that
# attains the optimum is searched and reported.
#
# THE CAP BINDS, AND IS PART OF THE OBJECTIVE.  --depth 6 here is a deliberate,
# user-chosen strict guarantee, NOT an inherited default: with 12972 answers
# instead of 2315 it is a far stronger demand, and normal mode's "any opener can
# follow SALET's tree" argument establishes feasibility for the 2315-answer
# problem only -- it says nothing about this one.  If no opener can solve all
# 12972 words within 6, the run says so explicitly rather than returning a
# number.  Report any result as optimal SUBJECT TO a 6-guess guarantee.
#
# PREREQUISITE: the SQUARE pattern matrix, which is not the default one.
#     python3 build_patterns.py --full      # from math/, ~18s, 168 MB
# It is written to a separate file; the 12972x2315 default that the normal, hard
# and answers-only sweeps read is left alone.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.
# Ctrl-C stops it; re-running resumes, and the CSV's best total re-seeds the
# incumbent so the pruning restarts at full strength rather than rediscovering it.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORDS=data/shared/words/guess.txt
PATS=data/local/patterns/patterns_full.npy

THREADS=18
TTBITS=28           # 8.6 GB of 24 GiB. 29 would be 16 GiB and would swap here.
TOPK=0              # 0 = exact (and intractable here); pass -k N for the heuristic

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--topk) TOPK="$2";    shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# EVERY K GETS ITS OWN FILES.  Different K values are different search spaces
# producing different (upper-bound) totals, so sharing a CSV would interleave
# incomparable results and let resume seed one run from another's numbers. The TT
# is salted by K as well, so a shared tt.bin would fail verification anyway.
if [ "$TOPK" -gt 0 ]; then
    OUT=data/shared/allwords/opener_totals_k${TOPK}.csv
    LOC=data/local/allwords/k${TOPK}
else
    OUT=data/shared/allwords/opener_totals.csv
    LOC=data/local/allwords
fi

cd "$MATH" || exit 1

if pgrep -x optturns >/dev/null; then
    echo "optturns is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "NB every sweep uses this same binary name -- check which one:" >&2
    echo "  ps -Ao pid,command | grep optturns" >&2
    exit 1
fi
[ -x ./solver/optturns ] || { echo "no solver binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f "$WORDS" ] || { echo "no word list at $WORDS" >&2; exit 1; }
[ -f "$PATS" ]  || {
    echo "no square pattern matrix at $PATS" >&2
    echo "build it first:  python3 build_patterns.py --full" >&2
    exit 1
}

mkdir -p "$(dirname "$OUT")" "$LOC"

# The TT is salted with (guess set, answer set), so a tt.bin from another sweep
# cannot be mistaken for one of ours even if it is pointed here by accident.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

KFLAG=""
[ "$TOPK" -gt 0 ] && KFLAG="--topk $TOPK"

# BSD date has no -Is; this form works on both macOS and Linux. inflight.py parses
# this timestamp to find the run boundary, so an empty one breaks its run detection.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] resuming wordle ALL-WORDS sweep (optimal-only, depth 6, topk=$TOPK) $WARM" \
    | tee -a "$LOC/sweep.log"

./solver/optturns --sweep --optimal-only \
    --answer-list "$WORDS" \
    --patterns "$PATS" \
    --out "$OUT" \
    --depth 6 $KFLAG \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
