#!/bin/bash
# Lingo per-starting-letter sweep, ATTACHED, with live output in this terminal.
#
#     bash solver/run-lingo-sweep.sh --depth 5                 # from math/, all letters
#     bash solver/run-lingo-sweep.sh --depth 5 --letter s      # one letter
#     bash solver/run-lingo-sweep.sh --depth 5 --length 6      # 6-letter (hello lists)
#     bash solver/run-lingo-sweep.sh --depth 5 --topk 100      # beam (upper bound)
#
# WHAT THIS SOLVES, precisely, for EACH starting letter L:
#
#   Minimise the TOTAL guesses summed over the letter's answers, where every
#   guess -- opener and follow-ups -- is a legal Wordle guess STARTING WITH L,
#   SUBJECT TO resolving every answer within --depth guesses.
#
# Lingo = Wordle with the first letter GIVEN, so both the answer pool and the
# legal guesses are restricted to words starting with L (position 0 is always
# green; the feedback function is Wordle's, UNCHANGED). The restriction is
# entirely in the word lists -- no new solver code:
#   * --guess-list <L>/guess.txt      restricts follow-ups AND swept openers to L
#   * --answer-list <L>/mystery.txt   makes the total run over L's answers only
#   * --patterns    <L>.npy           the matrix built for exactly those columns
#
# THE FEEDBACK RULE IS UNVERIFIED against the real game show: we assume Lingo's
# marks are Wordle's green/yellow/grey with Wordle's duplicate-letter handling.
# The user confirmed this modelling; a real Lingo board would settle it.
#
# THE DEPTH CAP IS PART OF THE OBJECTIVE, so --depth is REQUIRED and each depth
# gets its own results directory. Lingo gives five guesses (the given first
# letter is not one), so --depth 5 is the game; a tighter cap is a different
# quantity. INFEASIBLE openers (a `word,,,,secs` CSV row) are an expected result,
# not a bug -- report totals as optima SUBJECT TO the guarantee, never as
# unconstrained minimum expected guesses.
#
# Output, per (length, depth, letter):
#   data/shared/lingo/len<L>_d<D>/<letter>_totals.csv   committed (the product)
#   data/local/lingo/len<L>_d<D>/<letter>/{trees,tt.bin,sweep.log}   regenerable
# Resume is automatic: a finished letter's openers come from its CSV and are
# skipped. Ctrl-C is safe (CSV flushed per opener); the table is lost.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LENGTH=5
DEPTH=""
TOPK=0
TTBITS=24           # 0.5 GB -- the per-letter subgames are small
THREADS=8
LETTERS=""          # empty -> every letter that has a list

while [ $# -gt 0 ]; do
    case "$1" in
        --length)  LENGTH="$2"; shift 2 ;;
        --depth)   DEPTH="$2";  shift 2 ;;
        --topk|-k) TOPK="$2";   shift 2 ;;
        --tt-bits) TTBITS="$2"; shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --letter)  LETTERS="$LETTERS $2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$DEPTH" ]; then
    echo "run-lingo-sweep.sh: --depth is REQUIRED (the cap is part of the objective;" >&2
    echo "  Lingo's five guesses is --depth 5, and each depth is a different quantity)" >&2
    exit 1
fi

cd "$MATH" || exit 1

if pgrep -x optturns >/dev/null; then
    echo "an optturns process is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "  Lingo uses the same binary; run this when no other sweep holds it." >&2
    exit 1
fi

# length 5 = the NYT lists + plain optturns; other lengths = hello lists + optturns<L>
if [ "$LENGTH" = "5" ]; then
    BIN=./solver/optturns
    LENGTHFLAG=""
else
    BIN=./solver/optturns${LENGTH}
    LENGTHFLAG="--length ${LENGTH}"
fi
[ -x "$BIN" ] || { echo "no solver binary $BIN -- run 'sh build.sh ${LENGTH}' (or 'sh build.sh') in solver/" >&2; exit 1; }

LISTDIR="data/shared/words/lingo/len${LENGTH}"
if [ ! -d "$LISTDIR" ]; then
    echo "building per-letter word lists for length ${LENGTH} ..." >&2
    python3 build_lingo_lists.py --length "$LENGTH" >&2 || exit 1
fi

# default: every letter that has a list, in alphabetical order
if [ -z "$LETTERS" ]; then
    LETTERS="$(ls "$LISTDIR" 2>/dev/null | grep -E '^[a-z]$' | tr '\n' ' ')"
fi
[ -n "$LETTERS" ] || { echo "no letters found under $LISTDIR" >&2; exit 1; }

MATRIXDIR="data/local/lingo/patterns/len${LENGTH}"
RESULTDIR="data/shared/lingo/len${LENGTH}_d${DEPTH}"
mkdir -p "$MATRIXDIR" "$RESULTDIR"

TOPKFLAG=""
[ "$TOPK" -gt 0 ] && TOPKFLAG="--topk $TOPK"

for L in $LETTERS; do
    AW="$LISTDIR/$L/mystery.txt"
    GW="$LISTDIR/$L/guess.txt"
    if [ ! -f "$AW" ] || [ ! -f "$GW" ]; then
        echo "no lists for letter '$L' at $LISTDIR/$L -- skipping" >&2
        continue
    fi

    MAT="$MATRIXDIR/$L.npy"
    if [ ! -f "$MAT" ]; then
        echo "[$L] building pattern matrix (rows = full guess list, cols = $L answers) ..." >&2
        python3 build_patterns.py --answer-list "$AW" --out "$MAT" $LENGTHFLAG >&2 || exit 1
    fi

    LOC="data/local/lingo/len${LENGTH}_d${DEPTH}/$L"
    mkdir -p "$LOC"
    OUT="$RESULTDIR/${L}_totals.csv"
    WARM=""
    [ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] lingo len${LENGTH} letter '$L' depth ${DEPTH}${TOPKFLAG:+ }${TOPKFLAG} $WARM" \
        | tee -a "$LOC/sweep.log"

    $BIN $LENGTHFLAG --sweep \
        --answer-list "$AW" \
        --patterns "$MAT" \
        --guess-list "$GW" \
        --out "$OUT" \
        --trees "$LOC/trees" \
        --depth "$DEPTH" \
        $TOPKFLAG \
        --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
        2>&1 | tee -a "$LOC/sweep.log"
done

echo "done. best opener per letter:  python3 tools/lingo_report.py --length ${LENGTH} --depth ${DEPTH}"
