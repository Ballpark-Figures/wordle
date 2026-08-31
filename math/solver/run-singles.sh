#!/bin/bash
# Rank openers by SINGLETON COUNT -- single words and blind pairs -- and save
# both rankings.  Attached, with live output in this terminal.
#
#     bash solver/run-singles.sh                  # from math/, or anywhere: both stages
#     bash solver/run-singles.sh words            # just the single-word ranking
#     bash solver/run-singles.sh pairs            # just the pair ranking
#     bash solver/run-singles.sh pairs --top 250000
#
# WHAT THIS COMPUTES, precisely:
#
#   For each opener -- one word, or two words committed to BLIND up front --
#   count the feedback patterns that exactly ONE of the 2315 answers produces.
#   Seeing such a pattern names the answer outright, so the count is "how many
#   of the answers does this opener single out on the spot".
#
# For a PAIR the pattern is the JOINT pattern: two answers share a bucket iff
# they return the same pattern to word 1 AND the same pattern to word 2.  Both
# words are blind, so the partition -- and therefore this count -- cannot depend
# on the order they are played in, and only unordered pairs are enumerated.
#
# THIS IS EXHAUSTIVE, NOT A SCREEN.  Every one of the 12972 words and all
# C(12972, 2) = 84,129,906 pairs are evaluated, so the head of each file is the
# exact top of the ranking.  That is the opposite of run-*-sweep.sh's pair
# screens, which rank by ssq as a HEURISTIC feeding a later exact stage.
#
# WHAT IT IS NOT.  A singleton count is not a claim about guesses-to-solve.  An
# opener can lead the singleton ranking and lose on total guesses -- singling out
# many answers says nothing about how well the REST of the field splits.  Do not
# report a top entry here as a best opener.
#
# THE ANSWER SET IS PART OF THE QUESTION.  Both stages count over the 2315
# mystery answers.  tools/singletons.py --full counts over all 12972 words
# instead; that is a different question with a different answer, and it is not
# what this script runs.
#
# TWO COUNTS PER ROW, because the winning pattern is a special case.  A word that
# is itself an answer always produces an all-green bucket of size one -- a
# singleton that tells you nothing you did not know by winning.  `singles`
# counts every size-1 bucket, `singles_nowin` excludes the all-green ones.
# Which is the right denominator is a modelling choice, so both are emitted.
#
# PREREQUISITE: the default pattern matrix, which is gitignored and does not
# arrive with a clone:
#     python3 build_patterns.py             # from math/, ~2s, 30 MB
#
# Output is tee'd, so the log gets every line as well as your terminal.  Both
# stages overwrite their CSV in full -- there is no resume, because neither takes
# long enough to need one (about 0.1s and about 22s here).

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED=data/shared/singletons
LOC=data/local/singletons
PATS=data/local/patterns/patterns.npy

STAGE=both
TOP=100000          # pairs kept; the full 84M ranking is far too large to store
THREADS=0           # 0 = let OpenMP pick, which is right on both machines

while [ $# -gt 0 ]; do
    case "$1" in
        words|pairs|both) STAGE="$1"; shift ;;
        --top)     TOP="$2";     shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

cd "$MATH" || exit 1

[ -f "$PATS" ] || {
    echo "no pattern matrix at $PATS" >&2
    echo "build it first:  python3 build_patterns.py" >&2
    exit 1
}

mkdir -p "$SHARED" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] singleton ranking, stage=$STAGE top=$TOP" \
    | tee -a "$LOC/singles.log"

if [ "$STAGE" = words ] || [ "$STAGE" = both ]; then
    # PYTHON, not the C binary: 12972 rows of a 243-bin histogram is a tenth of a
    # second in numpy, so a second C path would buy nothing and be one more thing
    # to keep in step with the pattern loader.
    PY=python3
    [ -x ../.venv/bin/python ] && PY=../.venv/bin/python
    "$PY" tools/singletons.py 2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = pairs ] || [ "$STAGE" = both ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    ./solver/pairsplit --metric singles --top "$TOP" \
        --out "$SHARED/pair_singletons.csv" $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

echo "wrote:" | tee -a "$LOC/singles.log"
[ -f "$SHARED/guess_singletons.csv" ] && echo "  $SHARED/guess_singletons.csv" | tee -a "$LOC/singles.log"
[ -f "$SHARED/pair_singletons.csv" ]  && echo "  $SHARED/pair_singletons.csv"  | tee -a "$LOC/singles.log"
