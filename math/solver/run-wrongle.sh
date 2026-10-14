#!/bin/bash
# WRONGLE -- compatible guesses only, trying NOT to find the answer. ATTACHED,
# live in this terminal, tee'd to a log.
#
#     bash solver/run-wrongle.sh                               # lose, depth 6, exact
#     bash solver/run-wrongle.sh --depth 5                     # the trophy cap
#     bash solver/run-wrongle.sh -k 10                         # beam, K=10, root included
#     bash solver/run-wrongle.sh --objective expect -k 10      # max expected guesses
#     bash solver/run-wrongle.sh --opener salet --opener crane # price named openers
#     bash solver/run-wrongle.sh --dry-run                     # resolve and stop
#
# math/wrongle.py states the rule and IS the source of truth. In short: a guess
# must be one of the 12972 legal words AND consistent with every clue so far; the
# answer is uniform over the 2315.
#
#   --objective lose    (THIS WRAPPER'S DEFAULT) maximise the answers NOT found
#                       within --depth guesses (default 6 here; 5 is "reach the
#                       Wrongler Trophy"). The cap IS the objective: each depth
#                       gets its own file.
#   --objective expect  maximise EXPECTED guesses, uncapped, reported as the total
#                       over the 2315. Refuses --depth.
#
# TWO DIFFERENT QUANTITIES -- never in one table, and never beside an
# optturns-family total. The BINARY has no default objective and refuses to run
# without one (the greens scar); the default here is one a human reads, and it is
# forwarded explicitly.
#
# -k K IS A BEAM AT EVERY NODE, THE ROOT INCLUDED: the K legal guesses with the
# MOST expected answers remaining (largest sum of squared answer-bin sizes, ties on
# the lowest index). Every value is achievable, so it is a LOWER bound, and the
# winner is the best of the K openers EXAMINED. K is in the filename. With no -k
# the search is EXACT -- price it with --opener first; its cost is UNMEASURED.
#
# --opener W (repeatable) prices those openers only, into a separate file, with no
# root cut: exact for each opener (or beamed below it, under -k).
#
# The CSV is RESUMABLE (re-run the same command) and self-describing: its first
# line stamps the objective, depth, K and root mode, and a run asking a different
# question REFUSES to append to it.
#
# Needs the SQUARE matrix: python3 build_patterns.py --full (gitignored, so a
# fresh clone does not have it).
#
# COMMIT THE CSV -- data/shared/ syncs only once committed.
#
# RESULTS ARE FOR OUR WORD LISTS, which are not Wrongle's.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -x ./solver/wrongle ] || {
    echo "no solver/wrongle -- run 'sh build.sh' in solver/" >&2
    exit 1
}
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "no data/local/patterns/patterns_full.npy -- run 'python3 build_patterns.py --full'" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

ARGS=("$@")
OBJ=lose
DEPTH=""
K=0
NAMED=0
DRY=0
PASS=()
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        --objective) OBJ="${ARGS[$((i + 1))]}"; i=$((i + 1)) ;;
        --depth)     DEPTH="${ARGS[$((i + 1))]}"; i=$((i + 1)) ;;
        -k|--topk)   K="${ARGS[$((i + 1))]}"; i=$((i + 1)) ;;
        --opener)    NAMED=1; PASS+=("${ARGS[$i]}" "${ARGS[$((i + 1))]}"); i=$((i + 1)) ;;
        --dry-run)   DRY=1 ;;
        --out|--no-out)
                     echo "the wrapper sets the output file itself" >&2; exit 2 ;;
        *)           PASS+=("${ARGS[$i]}") ;;
    esac
    i=$((i + 1))
done

case "$OBJ" in
    lose)   [ -n "$DEPTH" ] || DEPTH=6
            STEM="lose_d${DEPTH}_k${K}"
            OBJARGS=(--objective lose --depth "$DEPTH") ;;
    expect) if [ -n "$DEPTH" ]; then
                echo "--objective expect is UNCAPPED; --depth would change the question" >&2
                exit 2
            fi
            STEM="expect_k${K}"
            OBJARGS=(--objective expect) ;;
    *)      echo "--objective is lose or expect, not '$OBJ'" >&2; exit 2 ;;
esac
[ "$NAMED" = 1 ] && STEM="${STEM}_openers"

OUTDIR=data/shared/wrongle
LOC=data/local/wrongle
OUT="$OUTDIR/$STEM.csv"
LOG="$LOC/$STEM.log"
CMD=(./solver/wrongle "${OBJARGS[@]}" --topk "$K" --out "$OUT" ${PASS[@]+"${PASS[@]}"})

if [ "$DRY" = 1 ]; then
    echo "dry run -- nothing started, nothing written"
    echo "  objective: $OBJ${DEPTH:+, depth $DEPTH}, K=$K ($([ "$K" = 0 ] && echo exact || echo 'beam: LOWER bounds'))"
    echo "  out:       $MATH/$OUT"
    echo "  log:       $MATH/$LOG"
    echo "  binary:    ${CMD[*]}"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"
guard_output wrongle "$OUT" || exit 1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wrongle $OBJ${DEPTH:+ depth $DEPTH} K=$K -> $OUT" \
    | tee -a "$LOG"
"${CMD[@]}" 2>&1 | tee -a "$LOG"
