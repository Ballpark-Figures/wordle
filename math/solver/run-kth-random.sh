#!/bin/bash
# What does ONE random guess cost, played at turn k of an otherwise perfect game?
#
#     bash solver/run-kth-random.sh --depth 6 -k 3
#     bash solver/run-kth-random.sh --depth 6 --all
#     bash solver/run-kth-random.sh --depth 6 -k 2 --opener crane
#     bash solver/run-kth-random.sh --depth 6 --all --dry-run
#
# THE EXPERIMENT.  Guesses 1..k-1 follow the committed OPTIMAL TREE of --opener
# (salet by default).  Guess k is a word drawn UNIFORMLY FROM ALL 12972 LEGAL
# WORDS -- consistent with the replies or not, which is what "completely random"
# means here and what makes k=1 the average over every possible starting word.
# From guess k+1 the exact solver plays optimally again.
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
# k=1 TAKES NO OPENER.  With no prefix to play there is nothing opener-specific
# about it, so its row records the opener as `-`.  --all still writes it into
# this opener's file, since it is the left-hand end of the same curve.
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
THREADS=18
TTBITS=27
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        -k|--kth)  KVAL="$2";    shift 2 ;;
        --all)     ALL=1;        shift ;;
        --opener)  OPENER="$2";  shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --dry-run) DRY=1;        shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

usage() {
    echo "usage: bash solver/run-kth-random.sh --depth D (-k K | --all) [--opener W] [--dry-run]" >&2
}
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
LOC=data/local/kthrandom/${OPENER}_d${DEPTH}
OUT=$OUTDIR/${OPENER}_d${DEPTH}.csv
LOG=$LOC/run.log

if [ "$ALL" = 1 ]; then KLIST=$(seq 1 "$DEPTH"); else KLIST=$KVAL; fi

if [ "$DRY" = 1 ]; then
    echo "dry run -- nothing computed, nothing written"
    echo "  opener   : $OPENER"
    echo "  tree     : $TREE ($(shasum "$TREE" | cut -c1-12))"
    echo "  depth    : $DEPTH"
    echo "  k values : $(echo $KLIST | tr '\n' ' ')"
    echo "  csv      : $OUT"
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

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] kth-random: opener=$OPENER depth=$DEPTH k=$(echo $KLIST | tr '\n' ' ')" \
    | tee -a "$LOG"
echo "  tree: $TREE  sha=$(shasum "$TREE" | cut -c1-12)" | tee -a "$LOG"

for K in $KLIST; do
    # k=1 has no prefix, so the binary REFUSES a tree there rather than filing an
    # opener-independent number under an opener's name.
    if [ "$K" = 1 ]; then TREEFLAG=""; else TREEFLAG="--tree-file $TREE"; fi
    ./solver/optturns --kth-random "$K" --depth "$DEPTH" $TREEFLAG \
        --out "$OUT" --tt-bits "$TTBITS" --threads "$THREADS" \
        $WARM \
        2>&1 | tee -a "$LOG"
done
