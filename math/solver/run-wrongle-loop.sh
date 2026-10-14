#!/bin/bash
# WRONGLE K-LADDER for ONE depth: run-wrongle.sh at each K in turn, ascending as
# given. ATTACHED; each run tees to its own log exactly as run-wrongle.sh does.
#
#     bash solver/run-wrongle-loop.sh --depth 6 --threads 2 1 2 3 5 10 20
#     bash solver/run-wrongle-loop.sh --depth 6 --dry-run 1 2 3      # resolve, stop
#
# The K list is REQUIRED -- which beams to run is the experiment, so there is no
# default. Each K is its own run-wrongle.sh call, so its own CSV and log, and the
# usual rules hold: every beam value is a LOWER bound, the best of the K openers
# examined; K >= 12972 is the EXACT search.
#
# FINISHED CELLS COST NOTHING: run-wrongle.sh resumes from its CSV, and a complete
# CSV leaves no opener to walk, so a cell already done exits at once and a
# part-done one resumes. Nothing here decides what counts as finished.
#
# --threads is forwarded to the binary. Several depths' loops are meant to run
# side by side (one per tmux window), so split the cores between them.
#
# A run that fails or is refused (the output guard, a missing binary) is reported
# and the ladder moves on to the next K.
#
# --stop-on-repeat ends the ladder as soon as two CONSECUTIVE K in the list give
# the same best value (answers lost). Off by default. Only a COMPLETE cell counts:
# its CSV must hold every opener the root beam examines, min(K, 12972) rows. The
# exit status cannot say so -- run-wrongle.sh pipes the solver into tee, so a
# crashed solver still "succeeds" -- hence the row count. An incomplete cell
# stops the ladder rather than feed a partial value to the comparison.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1

NG=12972
DEPTH=""
STOP=0
DRY=0
PASS=()
KS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --depth)          DEPTH="$2"; shift ;;
        --threads)        PASS+=(--threads "$2"); shift ;;
        --dry-run)        PASS+=(--dry-run); DRY=1 ;;
        --stop-on-repeat) STOP=1 ;;
        -*)               echo "unknown flag $1" >&2; exit 2 ;;
        *)                KS+=("$1") ;;
    esac
    shift
done

[ -n "$DEPTH" ] || { echo "--depth is required" >&2; exit 2; }
[ ${#KS[@]} -gt 0 ] || { echo "give the K values to run, e.g. 1 2 3 5 10" >&2; exit 2; }

# "rows best" for one cell's CSV: data rows, and the largest solved value.
cell_summary() {
    awk -F, 'NR > 2 { n++; if ($2 == "solved" && ($3 + 0 > b || b == "")) b = $3 + 0 }
             END { printf "%d %s\n", n, (b == "" ? "-" : b) }' "$1"
}

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wrongle ladder: depth $DEPTH, K = ${KS[*]}" \
     "$([ "$STOP" = 1 ] && echo '(stop on repeat)')"
PREV=""
PREVK=""
for K in "${KS[@]}"; do
    echo
    echo "=== depth $DEPTH, K=$K ==="
    bash solver/run-wrongle.sh --objective lose --depth "$DEPTH" -k "$K" \
        ${PASS[@]+"${PASS[@]}"} \
        || echo "!!! depth $DEPTH K=$K exited with status $? -- moving on"

    [ "$STOP" = 1 ] && [ "$DRY" = 0 ] || continue
    CSV="data/shared/wrongle/lose_d${DEPTH}_k${K}.csv"
    WANT=$(( K < NG ? K : NG ))
    if [ ! -f "$CSV" ]; then
        echo "!!! depth $DEPTH K=$K wrote no CSV -- stopping this ladder"
        break
    fi
    read -r ROWS BEST <<< "$(cell_summary "$CSV")"
    if [ "$ROWS" -lt "$WANT" ]; then
        echo "!!! depth $DEPTH K=$K is INCOMPLETE ($ROWS of $WANT openers) -- stopping this ladder"
        break
    fi
    echo "--- depth $DEPTH K=$K complete: best $BEST lost"
    if [ -n "$PREV" ] && [ "$BEST" = "$PREV" ]; then
        echo "--- depth $DEPTH: K=$PREVK and K=$K both give $BEST -- stopping (repeat)"
        break
    fi
    PREV="$BEST"
    PREVK="$K"
done
echo
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wrongle ladder: depth $DEPTH done"
