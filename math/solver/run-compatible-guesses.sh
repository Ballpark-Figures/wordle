#!/bin/bash
# How often the OPTIMAL TREES play a word that could still be the answer,
# attached, with live output in this terminal.
#
#     bash solver/run-compatible-guesses.sh --top 1000     # from math/, or anywhere
#     bash solver/run-compatible-guesses.sh --top 1000 --skip-allgrey
#     bash solver/run-compatible-guesses.sh --top 1
#     WORDLE_SOLVER=hardturns bash solver/run-compatible-guesses.sh --top 100
#
# WHAT THIS COMPUTES, precisely (the user's question, 2026-09-09):
#
#   Every line of a tree is one game: an opener, some middle guesses, and a
#   final guess equal to the answer.  The OPENER and the FINAL guess are
#   EXCLUDED -- the opener is fixed and the final guess is the answer, so it is
#   compatible by construction.  Of the guesses BETWEEN them, how many were
#   COMPATIBLE, and what is the average over all N * 2315 paths?
#
#   THE DENOMINATOR IS EVERY PATH, not the examined guesses and not the paths
#   that had one: a game won in two guesses examines nothing, contributes 0, and
#   still counts.
#
#   TWO READINGS OF "COMPATIBLE", both reported, both in the CSV:
#     answer (THE HEADLINE) -- the guess was a live CANDIDATE: a mystery word
#       consistent with every clue so far, so playing it could have won there
#       and then.  This is the tree's own candidate set.
#     legal -- the guess was consistent with every clue so far without being a
#       mystery word.  Every answer hit is a legal hit; the extra ones are
#       guess-only words like `courd` that could never have won.
#
#   --skip-allgrey EXCLUDES THE ALL-GREY BOARDS FROM THE NUMERATOR (the user's
#   call, 2026-09-09): a guess played while the board shows no green and no
#   yellow tile -- the opener came back all grey, and every guess since did too
#   -- stops counting as a compatible choice.  THE DENOMINATOR IS UNTOUCHED:
#   every one of the N * 2315 paths still counts, so the number stays directly
#   comparable with the unrestricted one and is weakly smaller.  It is a
#   DIFFERENT QUANTITY, so it gets its own file.
#
#   THE TOP N ARE N DIFFERENT STRATEGIES POOLED, best first by `total` in the
#   sweep's own CSV, ties on the word -- the same selection tree_states.py uses.
#   Each contributes its own 2315 answers, so every opener carries equal weight
#   however good it is.
#
#   THE TREES ARE CONSTRAINED OPTIMA -- minimum total guesses over the 2315
#   answers SUBJECT TO resolving each within 6 -- so this is a property of THAT
#   strategy, not of an unconstrained expected-guess minimiser.
#
#   Nothing here searches or samples: it is a pure function of the committed
#   trees and word lists, so a re-run reproduces its file exactly.
#
# USE THIS RATHER THAN CALLING tools/compatible_guesses.py DIRECTLY.  It sets
# --out so the table outlives the terminal, names the file after the sweep and
# the opener count, and tees a log; the script refuses to start without --out.
#
# Data under data/shared/compatguess/, log under data/local/compatguess/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOLVER="${WORDLE_SOLVER:-optturns}"

TOP=""
PROGRESS=25
SKIPGREY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --top)          TOP="$2";      shift 2 ;;
        --progress)     PROGRESS="$2"; shift 2 ;;
        --skip-allgrey) SKIPGREY=1;    shift ;;
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

# Consistency is tested between two GUESS words, so this reads the SQUARE
# guess x guess matrix -- a separate artifact from the 12972x2315 one, gitignored
# like the rest of data/local/, so it is missing on a fresh clone.
[ -f data/local/patterns/patterns_full.npy ] || {
    echo "this needs the square guess x guess pattern matrix." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1; }

OUTDIR=data/shared/compatguess
LOC=data/local/compatguess
# The restriction changes the quantity, so it is part of the name -- two
# different numbers must never share a file.
STEM="compatible_${SOLVER}_top${TOP}"
[ -n "$SKIPGREY" ] && STEM="${STEM}_skipgrey"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output compatible_guesses.py "$OUT" || exit 1

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] compatible guesses $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/compatible_guesses.py --top "$TOP" --progress "$PROGRESS" \
    ${SKIPGREY:+--skip-allgrey} --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
