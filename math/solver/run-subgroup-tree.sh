#!/bin/bash
# The OPTIMAL TREE of one group of an opener's tree, for each of several FORCED
# next guesses. ATTACHED, tee'd log.
#
#     bash solver/run-subgroup-tree.sh --path first:30 --guess after --guess plane
#     bash solver/run-subgroup-tree.sh --path first:30 --guess after --dry-run
#
# WHAT THIS SOLVES, for each --guess W:
#
#   The answers left after the line of play --path (e.g. first:30 = FIRST scored
#   - Y - Y -, 48 answers). W is played next, FORCED; from there the solver plays
#   optimally: fewest total guesses over those answers, SUBJECT TO finishing
#   every one of them within the whole game's --cap (6 by default) -- so the
#   solver gets `cap - (guesses in --path)` guesses, W included.
#
# It is the ordinary optturns single-opener solve on a restricted answer list
# (--answer-list + a matching --patterns matrix, as the Lingo cell does): no new
# solver code. Every legal guess (all 12972) may be played. Totals count guesses
# FROM W ON; the guesses in --path are not in them.
#
# THE CAP IS PART OF THE OBJECTIVE and is in every filename. Each tree is ONE
# optimal tree -- where moves tie, it is one of them.
#
# FREE CHECK: the opener's committed tree (data/shared/optturns/trees/<opener>)
# already holds the optimal continuation of every group. Pass that group's own
# next guess as a --guess and its total must equal the committed tree's count for
# the group -- same solver, same objective, reached two ways.
#
# Output (committed):  data/shared/subtree/<path>_cap<C>/{answers.txt,totals.csv,trees/<W>.txt.gz}
#        (local):      data/local/subtree/<path>_cap<C>/{patterns.npy,run.log}

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PATHSPEC=""
GUESSES=""
CAP=6               # the game's own six guesses
DRY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --path)    PATHSPEC="$2"; shift 2 ;;
        --guess)   GUESSES="$GUESSES $2"; shift 2 ;;
        --cap)     CAP="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done
[ -n "$PATHSPEC" ] || { echo "run-subgroup-tree.sh: --path is REQUIRED (e.g. first:30)" >&2; exit 1; }
[ -n "$GUESSES" ] || { echo "run-subgroup-tree.sh: at least one --guess is REQUIRED" >&2; exit 1; }

cd "$MATH" || exit 1
NPATH=$(( ( $(echo "$PATHSPEC" | tr -cd ':' | wc -c) + 1 ) / 2 ))
DEPTH=$(( CAP - NPATH ))
[ "$DEPTH" -ge 1 ] || { echo "cap $CAP leaves no guesses after $NPATH" >&2; exit 1; }
NAME="$(echo "$PATHSPEC" | tr ':' '_')_cap${CAP}"
SHARED="data/shared/subtree/$NAME"
LOCAL="data/local/subtree/$NAME"
BIN=./solver/optturns

echo "group    : $PATHSPEC  ($NPATH guess(es) already played)"
echo "guesses  :$GUESSES  (each forced next, then optimal)"
echo "cap      : $CAP for the whole game -> solver --depth $DEPTH"
echo "writes   : $SHARED/{answers.txt,totals.csv,trees/}  log $LOCAL/run.log"
[ "$DRY" -eq 1 ] && { echo "dry run: nothing written"; exit 0; }
[ -x "$BIN" ] || { echo "no solver binary $BIN -- run 'sh build.sh' in solver/" >&2; exit 1; }

mkdir -p "$SHARED/trees" "$LOCAL"
python3 tools/subgroup_answers.py --path "$PATHSPEC" --out "$SHARED/answers.txt" || exit 1
if [ ! -f "$LOCAL/patterns.npy" ] || [ "$SHARED/answers.txt" -nt "$LOCAL/patterns.npy" ]; then
    python3 build_patterns.py --answer-list "$SHARED/answers.txt" --out "$LOCAL/patterns.npy" || exit 1
fi
CSV="$SHARED/totals.csv"
[ -s "$CSV" ] || echo "guess,total,expected,depth_used,answers" > "$CSV"
NA=$(wc -l < "$SHARED/answers.txt" | tr -d ' ')

for W in $GUESSES; do
    if grep -q "^$W," "$CSV"; then
        echo "$W: already in $CSV -- skipped (delete its row to re-solve)"
        continue
    fi
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $PATHSPEC then $W, depth $DEPTH" | tee -a "$LOCAL/run.log"
    LINE=$($BIN --opener "$W" --answer-list "$SHARED/answers.txt" --patterns "$LOCAL/patterns.npy" \
               --depth "$DEPTH" --trees "$SHARED/trees" --tt-bits 22 --threads 4 2>&1 \
           | tee -a "$LOCAL/run.log" | grep -E "^$W ")
    echo "$LINE"
    TOTAL=$(echo "$LINE" | sed -n 's/.*total=\([0-9]*\).*/\1/p')
    if [ -z "$TOTAL" ]; then
        echo "$W,,,,$NA" >> "$CSV"          # INFEASIBLE within the cap
    else
        EXP=$(echo "$LINE" | sed -n 's/.*expected=\([0-9.]*\).*/\1/p')
        D=$(echo "$LINE" | sed -n 's/.*  d=\([0-9]*\).*/\1/p')
        echo "$W,$TOTAL,$EXP,$D,$NA" >> "$CSV"
    fi
done
echo "done: $CSV"
