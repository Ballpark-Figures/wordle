#!/bin/bash
# What does ONE random guess cost, played at turn k of an otherwise perfect game?
#
#     bash solver/run-kth-random.sh --depth 6 -k 3
#     bash solver/run-kth-random.sh --depth 6 --all
#     bash solver/run-kth-random.sh --depth 6 --all --pool compatible
#     bash solver/run-kth-random.sh --depth 6 -k 2 --opener crane
#     bash solver/run-kth-random.sh --depth 6 --all --dry-run
#
# THE EXPERIMENT.  Guesses 1..k-1 follow the committed OPTIMAL TREE of --opener
# (salet by default).  Guess k is a word drawn UNIFORMLY AT RANDOM.  From guess
# k+1 the exact solver plays optimally again.
#
# --pool SAYS WHAT "AT RANDOM" MEANS, AND IT IS PART OF THE OBJECTIVE.  Two
# different experiments, both live, each with its own files:
#
#   all         every one of the 12972 legal words, consistent with the replies
#               or not.  k=1 is then the average over every possible starting
#               word: mean 3.62590.
#   compatible  only words still CONSISTENT with every reply -- i.e. the
#               candidate set itself, which at k=1 is all 2315 answer words.
#               k=1 is then the sweep averaged over the answer words: 3.60730.
#
# COMPATIBLE IS ENORMOUSLY CHEAPER, because the random guess ranges over the
# state (at most a few hundred words) rather than over 12972 -- about 830x less
# work at k=2, which is the only cell `all` finds expensive.
#
# IT ALSO MAKES THE OBJECTIVE RATIONAL RATHER THAN INTEGER.  Under `all` every
# answer draws from the same 12972 words, so the experiment is a rectangle and
# the total is an integer over 2315 x 12972.  Under `compatible` each answer
# draws from ITS OWN state and states differ in size, so answer a carries weight
# 1/|S_a| and there is no small common denominator.  The summary CSV therefore
# leaves its integer grid columns BLANK under `compatible` and the per-state
# file beside it holds the integers the mean was summed from, exactly.
#
# IT IS EXACT, NOT SAMPLED.  Every (answer, random word) pair is enumerated --
# 2315 x 12972 = 30,030,180 of them -- so the result is an integer total over
# that grid with no seed and no standard error, and a re-run reproduces the file.
# That is why this is not a wordlesim strategy: there is nothing to sample.
#
# --depth IS REQUIRED AND THE CAP IS COUNTED FROM THE START OF THE GAME, so the
# continuation gets depth-k further guesses and the whole game fits in --depth.
# A random guess spends a turn without necessarily buying anything, so INFEASIBLE
# IS AN EXPECTED RESULT here in a way it is not for the plain sweep -- and an
# infeasible pair has NO OPTIMUM AT ALL, not merely a large one.  Read `mean` as
# "optimal expected guesses CONDITIONAL on the game being winnable within
# --depth"; `lb_mean` charges every infeasible pair depth+1 and is therefore a
# SOUND LOWER BOUND on the unconditional mean.  When infeasible_pairs is 0 the
# two coincide and it is simply the expected guesses.
#
# NEVER TABLE IT BESIDE AN UNCAPPED NUMBER.  Like every optturns-family total
# this is an optimum SUBJECT TO a guarantee, so it does not belong next to
# wordlesim / multiwordle / foximax means, which are expected guesses outright.
#
# TWO ROWS ARE KNOWN IN ADVANCE AND ARE THE GATE'S ORACLES.  k=1 must reproduce
# the committed opener_totals.csv averaged over all 12972 openers, and any k past
# the tree's depth must reproduce the opener's own total (salet: 7920 / 3.42117),
# there being no live game left for the random guess to spoil.
#
# k=1 TAKES NO OPENER, AND --all DELIBERATELY SKIPS IT.  With no prefix to play
# there is nothing opener-specific about k=1 -- and computing it means solving
# every one of the 12972 openers at depth 6, which IS the full --sweep and took
# this machine weeks.  It is already answered by the committed
# data/shared/optturns/opener_totals.csv (total 8393.9652, mean 3.62590), so
# --all runs k=2..depth and says so.  `-k 1` still works, and running it is the
# end-to-end validation of this whole pipeline against 12972 committed totals --
# which is exactly what tools/checkkthrandom.py check F then compares.  Its row
# records the opener as `-`.
#
# WHICH TREE MATTERS AT k>=3, and the log records the one used.  At k=2 the
# states are the opener's own partition and nothing else can vary; deeper, they
# are the nodes of ONE optimal tree, and an optimal tree is NOT unique.
#
# Output is tee'd, so the log gets every line as well as your terminal.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPTH=""
KVAL=""
ALL=0
OPENER=salet          # a default a HUMAN reads, forwarded explicitly below
POOL=all              # likewise: the binary refuses without it, this passes it on
THREADS=18
TTBITS=27
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        -k|--kth)  KVAL="$2";    shift 2 ;;
        --all)     ALL=1;        shift ;;
        --opener)  OPENER="$2";  shift 2 ;;
        --pool)    POOL="$2";    shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --dry-run) DRY=1;        shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

usage() {
    echo "usage: bash solver/run-kth-random.sh --depth D (-k K | --all)" \
         "[--pool all|compatible] [--opener W] [--dry-run]" >&2
}
case "$POOL" in
    all|compatible) ;;
    *) echo "--pool must be 'all' (every legal word) or 'compatible' (only words" >&2
       echo "  still consistent with the replies) -- they are different experiments" >&2
       exit 1 ;;
esac
case "$DEPTH" in
    ''|*[!0-9]*|0) echo "--depth is required and must be a positive number (the cap IS the objective)" >&2
                   usage; exit 1 ;;
esac
if [ "$ALL" = 1 ] && [ -n "$KVAL" ]; then
    echo "--all and -k are alternatives: --all runs k=1..$DEPTH in turn" >&2; exit 1
fi
if [ "$ALL" = 0 ]; then
    case "$KVAL" in
        ''|*[!0-9]*|0) echo "-k must be a positive number, or use --all" >&2; usage; exit 1 ;;
    esac
    if [ "$KVAL" -gt "$DEPTH" ]; then
        echo "-k $KVAL exceeds --depth $DEPTH: the random guess would be played past the cap" >&2
        exit 1
    fi
fi

cd "$MATH" || exit 1
[ -x ./solver/optturns ] || { echo "no ./solver/optturns -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "missing data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' from math/" >&2
    exit 1; }

# Resolve the tree the SAME way tools/paths.py does -- prefer the live local set
# a running sweep writes, fall back to the committed copy -- so this tool and
# every other tree reader can never disagree about which trees are in play.
TREE=""
for d in data/local/optturns/trees data/shared/optturns/trees; do
    if [ -f "$d/$OPENER.txt.gz" ]; then TREE="$d/$OPENER.txt.gz"; break; fi
done
if [ -z "$TREE" ]; then
    echo "no committed tree for '$OPENER' under data/{local,shared}/optturns/trees/" >&2
    echo "  emit one with: ./solver/optturns --opener $OPENER --depth $DEPTH --trees data/local/optturns/trees" >&2
    exit 1
fi

OUTDIR=data/shared/kthrandom
LOC=data/local/kthrandom/${OPENER}_d${DEPTH}_${POOL}
OUT=$OUTDIR/${OPENER}_d${DEPTH}_${POOL}.csv
LOG=$LOC/run.log

# --all starts at 2, NOT 1 -- see the note at the top.  k=1 is the whole opener
# sweep over again and is already on disk.
if [ "$ALL" = 1 ]; then KLIST=$(seq 2 "$DEPTH"); else KLIST=$KVAL; fi

if [ "$DRY" = 1 ]; then
    echo "dry run -- nothing computed, nothing written"
    echo "  opener   : $OPENER"
    echo "  tree     : $TREE ($(shasum "$TREE" | cut -c1-12))"
    echo "  depth    : $DEPTH"
    echo "  k values : $(echo $KLIST | tr '\n' ' ')"
    [ "$ALL" = 1 ] && echo "             (--all skips k=1: it is the opener sweep over again," \
                          "already in data/shared/optturns/opener_totals.csv)"
    echo "  pool     : $POOL"
    echo "  csv      : $OUT"
    echo "  states   : $OUTDIR/states_${OPENER}_d${DEPTH}_k<K>_${POOL}.csv"
    echo "  log      : $LOG"
    echo "  threads  : $THREADS   tt-bits: $TTBITS"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output optturns "$OUT" || exit 1

# NOTHING SAVES A TABLE HERE, deliberately -- see the long note in
# run-mm-sweep.sh.  --tt-save fires only on NORMAL COMPLETION, which is exactly
# when the table is worthless (the CSV row is written, so a re-run resumes and
# never reads it), and 302 such snapshots once filled 79% of a disk.  --tt-load
# stays because a table made on purpose is still worth warming from.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] kth-random: opener=$OPENER depth=$DEPTH pool=$POOL k=$(echo $KLIST | tr '\n' ' ')" \
    | tee -a "$LOG"
echo "  tree: $TREE  sha=$(shasum "$TREE" | cut -c1-12)" | tee -a "$LOG"

if [ "$ALL" = 1 ]; then
    if [ "$POOL" = all ]; then K1="all 12972 openers"; K1M=3.62590
    else                        K1="the 2315 answer-word openers"; K1M=3.60730; fi
    echo "  note: --all skips k=1 -- it means solving $K1 at depth $DEPTH, which is" \
        | tee -a "$LOG"
    echo "        the opener sweep over again, and is already answered by" \
        | tee -a "$LOG"
    echo "        data/shared/optturns/opener_totals.csv (mean $K1M)." \
        | tee -a "$LOG"
    echo "        Ask for it explicitly with -k 1 if you want it recomputed here." \
        | tee -a "$LOG"
fi

for K in $KLIST; do
    # k=1 has no prefix, so the binary REFUSES a tree there rather than filing an
    # opener-independent number under an opener's name.
    if [ "$K" = 1 ]; then TREEFLAG=""; else TREEFLAG="--tree-file $TREE"; fi
    # The per-state integers are the EXACT record under --pool compatible, where
    # the mean is a sum of fractions with no small common denominator, so they
    # are committed beside the summary rather than left in local/.
    ./solver/optturns --kth-random "$K" --depth "$DEPTH" --random-pool "$POOL" $TREEFLAG \
        --out "$OUT" --kth-states "$OUTDIR/states_${OPENER}_d${DEPTH}_k${K}_${POOL}.csv" \
        --tt-bits "$TTBITS" --threads "$THREADS" \
        $WARM \
        2>&1 | tee -a "$LOG"
done
