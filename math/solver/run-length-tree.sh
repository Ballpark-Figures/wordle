#!/bin/bash
# Emit ONE opener's optimal TREE for a hello wordl game of a given WORD LENGTH, at
# a PINNED depth cap.
#
#     bash solver/run-length-tree.sh --length 4 --depth max --opener tale   # from math/
#     bash solver/run-length-tree.sh --length 4 --depth 6 --opener tale --dry-run
#     bash solver/run-length-tree.sh --length 4 --depth 6 --opener tale -k 1
#
# WHY THIS EXISTS.  run-length-sweep.sh runs --optimal-only, which emits NO trees
# (write_tree is only called from the single-opener and plain --sweep paths), so a
# sweep's winner has a total on disk and no strategy.  This is the follow-up the
# sweep's own notes call for: the SAME binary, objective and lists, solving the one
# named opener exactly and writing its tree.  Scene 10 needs length 4's TALE tree
# (its all-grey path), and the only TALE tree on disk came from a --topk beam at a
# different cap -- a different strategy with a different total.
#
# THE CAP IS PART OF THE OBJECTIVE and is PINNED here (no escalation).
# `--depth max` asks for as little restriction as the solver can give: the largest
# cap its arrays allow, MAXD - 1 (19, read from optturns.c), far above what any of
# these lengths needs.  That is NOT a proof that no cap binds -- only relaxing
# further could show that -- so the run reports the tree's DEEPEST line for the
# reader to hold against the cap.  The tree lands in
#     data/shared/optlen<L>/trees_d<D>/<opener>.txt.gz
# beside that length's other results, one directory per depth.  A tree already
# there is REFUSED rather than overwritten.
#
# The printed total must equal the sweep row's `total` for that opener and depth;
# the run prints the row to compare against.
#
# -k K RESTRICTS THE BRANCHING BELOW THE OPENER (optturns --topk K): at every
# node only the K evenest splitters by sum of squared bins are searched (plus the
# live candidates once n <= K), and the exact minimum is taken over those.  Not a
# beam -- nothing is carried forward -- but no longer the optimum either: the
# total is an UPPER BOUND on this opener's exact price, the best strategy found
# within that restriction.  Each K is a different strategy, so it gets its own
# directory, exactly as run-length-sweep.sh -k routes it:
#     data/shared/optlen<L>/k<K>/trees_d<D>/<opener>.txt.gz
# and the sweep rows printed for comparison are that K's.  K is in the TT salt,
# so a table from another K (or the exact run) cannot be read by mistake.
#
# PREREQUISITES are run-length-sweep.sh's: the length's word lists, its pattern
# matrix, and the optturns<L> binary.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LENGTH=""
DEPTH=""
OPENER=""
TOPK=0           # 0 = exact. K > 0 restricts branching to the K evenest splits
THREADS=18
TTBITS=28
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --length)  LENGTH="$2";  shift 2 ;;
        --depth)   DEPTH="$2";   shift 2 ;;
        --opener)  OPENER="$2";  shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --dry-run) DRYRUN=1;     shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$LENGTH" in
    3|4|6|7|8|9|10|11) ;;
    5) echo "length 5 is the NYT problem: use optturns's own trees (run-sweep.sh)" >&2; exit 1 ;;
    *) echo "usage: bash solver/run-length-tree.sh --length <3..11> --depth <d> --opener <word> [--dry-run]" >&2; exit 1 ;;
esac
if [ "$DEPTH" = max ]; then
    MAXD=$(awk '/^#define MAXD /{print $3}' "$MATH/solver/optturns.c")
    DEPTH=$((MAXD - 1))
fi
case "$DEPTH" in
    ''|*[!0-9]*) echo "--depth is required: a number, or max (the cap IS the objective)" >&2; exit 1 ;;
esac
case "$TOPK" in
    ''|*[!0-9]*) echo "-k must be a non-negative integer (0 = exact)" >&2; exit 1 ;;
esac
[ -n "$OPENER" ] || { echo "--opener is required: this solves ONE named opener" >&2; exit 1; }
[ "${#OPENER}" -eq "$LENGTH" ] || { echo "--opener '$OPENER' is not $LENGTH letters" >&2; exit 1; }

cd "$MATH" || exit 1

BIN=./solver/optturns$LENGTH
PATS=data/local/patterns/patterns_len$LENGTH.npy
WORDS=data/shared/words/hello/len$LENGTH/guess.txt
OUTDIR=data/shared/optlen$LENGTH
LOC=data/local/optlen$LENGTH
KFLAG=""
if [ "$TOPK" -gt 0 ]; then
    OUTDIR=$OUTDIR/k$TOPK
    LOC=$LOC/k$TOPK
    KFLAG="--topk $TOPK"
fi
TREES=$OUTDIR/trees_d$DEPTH
TREE=$TREES/$OPENER.txt.gz
LOG=$LOC/tree.log

[ -x "$BIN" ] || { echo "no $BIN -- run 'sh build.sh $LENGTH' in solver/" >&2; exit 1; }
[ -f "$WORDS" ] || { echo "no word lists for length $LENGTH -- run 'python3 build_wordlists.py'" >&2; exit 1; }
[ -f "$PATS" ] || { echo "no pattern matrix at $PATS -- python3 build_patterns.py --length $LENGTH" >&2; exit 1; }
grep -qx "$OPENER" "$WORDS" || { echo "'$OPENER' is not a legal length-$LENGTH guess" >&2; exit 1; }
if [ -e "$TREE" ]; then
    echo "$TREE already exists -- refusing to overwrite it" >&2
    exit 1
fi
if pgrep -x "optturns$LENGTH" >/dev/null; then
    echo "optturns$LENGTH is already running (pid $(pgrep -x "optturns$LENGTH" | tr '\n' ' '))." >&2
    exit 1
fi

WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

echo "length $LENGTH, opener $OPENER, depth $DEPTH PINNED, topk $TOPK"
if [ "$TOPK" -gt 0 ]; then
    echo "*** -k $TOPK: branching below $OPENER is restricted, so the total is an UPPER" >&2
    echo "*** BOUND on its exact price and the tree is the best found within that." >&2
fi
echo "tree  -> $TREE"
echo "log   -> $LOG"
echo "sweep rows for this opener and depth, to compare the total against:"
grep -h "^$OPENER," $OUTDIR/opener_totals_*.csv 2>/dev/null \
    | awk -F, -v d="$DEPTH" '$4 == d' | sed 's/^/    /'
if [ "$DRYRUN" -eq 1 ]; then
    echo "--dry-run: nothing run, nothing written"
    exit 0
fi

mkdir -p "$TREES" "$LOC"
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] tree: length $LENGTH, opener $OPENER, depth $DEPTH, topk $TOPK $WARM" \
    | tee -a "$LOG"
"$BIN" --length "$LENGTH" --opener "$OPENER" --depth "$DEPTH" --trees "$TREES" \
    --tt-bits "$TTBITS" --threads "$THREADS" $KFLAG $WARM 2>&1 | tee -a "$LOG"
echo
if [ -f "$TREE" ]; then
    echo "tree: $TREE"
    echo "deepest line: $(gzip -dc "$TREE" | awk '$2 > m {m = $2} END {print m}') guesses (cap $DEPTH)" \
        | tee -a "$LOG"
else
    echo "NO TREE WRITTEN (see above)" >&2; exit 1
fi
