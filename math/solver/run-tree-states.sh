#!/bin/bash
# Break the OPTIMAL TREES down by level and by what the board shows so far,
# attached, with live output in this terminal.
#
#     bash solver/run-tree-states.sh --top 1000        # from math/, or anywhere
#     bash solver/run-tree-states.sh --top 1
#     WORDLE_SOLVER=hardturns bash solver/run-tree-states.sh --top 100
#
# WHAT THIS COMPUTES, precisely:
#
#   For each LEVEL k (the state after k guesses and their feedback) and each
#   cumulative (greens, yellows) tile count, how often the strategy has already
#   narrowed the answer to ONE word, and how often a random pick from what is
#   still alive would be right -- from the consistent ANSWERS, and from the
#   consistent LEGAL GUESSES.  `wordle_in_one.py` asks this of one blind row;
#   this asks it of the whole game, as actually played by the optimal trees.
#
#   THE STATE IS CUMULATIVE, and its definition is the user's call (2026-09-08):
#   greens counts POSITIONS pinned green by any guess so far; yellows counts
#   COPIES of a letter known to be in the answer but not yet pinned, summed over
#   letters, so two loose B's count 2 and a letter with one copy green and
#   another loose contributes 1; grays is 5 minus the two.  That reading makes
#   greens + yellows the number of ANSWER SLOTS accounted for, so grays is
#   exactly the slots still blank -- an invariant the tool asserts at every node.
#
#   WEIGHTING IS BY ANSWERS, not by nodes (the user's call): a node holding n
#   candidates counts n times, so pct_single is the share of ANSWERS sitting in
#   a node already narrowed to one.  The node count is reported beside it, so
#   the other reading stays recoverable.
#
#   avg_answers AND avg_guesses ARE THE RANDOM-PICK POOLS COUNTED RATHER THAN
#   INVERTED: the mean NUMBER of words still consistent, under the same answer
#   weighting, so a node of n candidates enters the mean n times.  They are NOT
#   100/pct_rand_*: the mean of n and the mean of 1/n are different aggregations
#   of one distribution.
#
#   THE avg_answers RANKING IS PRINTED TWICE.  WITHIN each level is the default
#   reading -- how narrowed a board is depends heavily on how many rows have
#   been played, so pooling ranks the game's clock as much as the tiles.  POOLED
#   ACROSS the levels asks what a composition is worth with the turn forgotten;
#   its denominator is NOT answers (an answer counts once per level it survives,
#   so those cells are candidate-weighted BOARD STATES and a pooled cell is not
#   a share of the 2315).  The CSV stays per (level, composition), the raw cells
#   both views are built from.
#
#   A WON GAME IS NOT A CASE: a line records no pattern for its final guess, so
#   a game that ends at turn k has no level-k state and leaves every deeper
#   level -- the same accounting as wordle_in_one's games_nowin column.
#
#   THE TOP N ARE N DIFFERENT STRATEGIES POOLED, best first by `total` in the
#   sweep's own CSV, ties on the word.  Each contributes its own 2315 answers,
#   so every opener carries equal weight however good it is.
#
#   THE TREES ARE CONSTRAINED OPTIMA -- minimum total guesses over the 2315
#   answers SUBJECT TO resolving each within 6.  These are states of THAT
#   strategy, not of an unconstrained expected-guess minimiser.
#
#   Nothing here searches or samples: it is a pure function of the committed
#   trees and word lists, so a re-run reproduces its file exactly.
#
# USE THIS RATHER THAN CALLING tools/tree_states.py DIRECTLY.  It sets --out so
# the table outlives the terminal, names the file after the sweep and the opener
# count, and tees a log; the script refuses to start without --out.
#
# Data under data/shared/treestates/, log under data/local/treestates/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOLVER="${WORDLE_SOLVER:-optturns}"

TOP=""
PROGRESS=25

while [ $# -gt 0 ]; do
    case "$1" in
        --top)      TOP="$2";      shift 2 ;;
        --progress) PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$TOP" in
    ''|*[!0-9]*|0)
        echo "--top N is required: how many openers, best first by total." >&2
        echo "  It is part of the question and it names the output file." >&2
        exit 1 ;;
esac
case "$PROGRESS" in
    *[!0-9]*) echo "--progress must be a non-negative number" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

# The legal-word random-pick column reads the SQUARE guess x guess matrix -- a
# separate artifact from the 12972x2315 one, gitignored like the rest of
# data/local/, so it is missing on a fresh clone.
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "the legal-word random-pick column needs the square guess x guess matrix." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

OUTDIR=data/shared/treestates
LOC=data/local/treestates
STEM="states_${SOLVER}_top${TOP}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output tree_states.py "$OUT" || exit 1

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] tree states $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/tree_states.py --top "$TOP" --progress "$PROGRESS" --out "$OUT" 2>&1 \
    | tee -a "$LOC/$STEM.log"
