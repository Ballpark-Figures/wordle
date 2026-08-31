#!/bin/bash
# Rank openers by SINGLETON COUNT -- single words, blind pairs, blind triples --
# and save each ranking.  Attached, with live output in this terminal.
#
#     bash solver/run-singles.sh                  # from math/, or anywhere: words + pairs
#     bash solver/run-singles.sh words            # just the single-word ranking
#     bash solver/run-singles.sh pairs            # just the pair ranking
#     bash solver/run-singles.sh triples          # extend the top pairs to triples
#     bash solver/run-singles.sh all              # all three stages
#     bash solver/run-singles.sh pairs --top 250000
#     bash solver/run-singles.sh triples --pairs-top 20000
#
# WHAT THIS COMPUTES, precisely:
#
#   For each opener -- one word, or two or three words committed to BLIND up
#   front -- count the feedback patterns that exactly ONE of the 2315 answers
#   produces.
#   Seeing such a pattern names the answer outright, so the count is "how many
#   of the answers does this opener single out on the spot".
#
# For a PAIR or TRIPLE the pattern is the JOINT pattern: two answers share a
# bucket iff they return the same pattern to EVERY word of the opener.  The words
# are blind, so the partition -- and therefore this count -- cannot depend on the
# order they are played in, and only unordered sets are enumerated.
#
# WORDS AND PAIRS ARE EXHAUSTIVE.  Every one of the 12972 words and all
# C(12972, 2) = 84,129,906 pairs are evaluated, so the head of those two files is
# the exact top of the ranking.  That is the opposite of run-*-sweep.sh's pair
# screens, which rank by ssq as a HEURISTIC feeding a later exact stage.
#
# TRIPLES ARE NOT, AND CANNOT BE.  C(12972, 3) is 3.6e11 -- a thousand times the
# pair count -- so the triple stage extends only the top --pairs-top pairs by
# every third word.  That is a GREEDY screen: a triple is reachable only if one
# of its three word PAIRS ranks inside the cut, so a strong triple built from
# three individually mediocre pairs cannot be found AT ANY WIDTH.  Its head is
# "best of the triples screened", never "the best triple".  Widening --pairs-top
# and watching the head stop moving is evidence, not proof -- on the ssq side
# that convergence was called twice and was wrong twice.
#
# The emitted `minparent` is the best rank among the triple's parent pairs, in
# THIS ranking, so filtering one wide run to minparent <= N reconstructs exactly
# what an N-pair run would have produced -- no need to re-run to narrow the cut.
#
# WHAT IT IS NOT.  A singleton count is not a claim about guesses-to-solve.  An
# opener can lead the singleton ranking and lose on total guesses -- singling out
# many answers says nothing about how well the REST of the field splits.  Do not
# report a top entry here as a best opener.
#
# THE ANSWER SET IS PART OF THE QUESTION.  All three stages count over the 2315
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
# Output is tee'd, so the log gets every line as well as your terminal.  Each
# stage overwrites its CSV in full -- there is no resume, because none of them
# takes long enough to need one (about 0.1s, 22s, and 11 min here).

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED=data/shared/singletons
LOC=data/local/singletons
PATS=data/local/patterns/patterns.npy

STAGE=both
TOP=100000          # rows kept; the full ranking is far too large to store
PAIRSTOP=100000     # pairs fed to the triple stage; about 11 min at this width
THREADS=0           # 0 = let OpenMP pick, which is right on both machines

while [ $# -gt 0 ]; do
    case "$1" in
        words|pairs|triples|both|all) STAGE="$1"; shift ;;
        --top)       TOP="$2";      shift 2 ;;
        --pairs-top) PAIRSTOP="$2"; shift 2 ;;
        --threads)   THREADS="$2";  shift 2 ;;
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
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] singleton ranking, stage=$STAGE top=$TOP pairs-top=$PAIRSTOP" \
    | tee -a "$LOC/singles.log"

if [ "$STAGE" = words ] || [ "$STAGE" = both ] || [ "$STAGE" = all ]; then
    # PYTHON, not the C binary: 12972 rows of a 243-bin histogram is a tenth of a
    # second in numpy, so a second C path would buy nothing and be one more thing
    # to keep in step with the pattern loader.
    PY=python3
    [ -x ../.venv/bin/python ] && PY=../.venv/bin/python
    "$PY" tools/singletons.py 2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = pairs ] || [ "$STAGE" = both ] || [ "$STAGE" = all ]; then
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

if [ "$STAGE" = triples ] || [ "$STAGE" = all ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    [ -f "$SHARED/pair_singletons.csv" ] || {
        echo "no pair ranking at $SHARED/pair_singletons.csv" >&2
        echo "run the pair stage first:  bash solver/run-singles.sh pairs" >&2
        exit 1
    }
    # The cut is taken here rather than inside pairsplit so that one wide pair
    # run serves every width: --extend reads whatever file it is handed, and its
    # line order IS the rank the minparent column is reported against.
    CUT="$LOC/pairs_top$PAIRSTOP.csv"
    head -n $((PAIRSTOP + 1)) "$SHARED/pair_singletons.csv" > "$CUT"
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    ./solver/pairsplit --metric singles --extend "$CUT" --top "$TOP" \
        --out "$SHARED/triple_singletons.csv" $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

echo "wrote:" | tee -a "$LOC/singles.log"
[ -f "$SHARED/guess_singletons.csv" ] && echo "  $SHARED/guess_singletons.csv" | tee -a "$LOC/singles.log"
[ -f "$SHARED/pair_singletons.csv" ]   && echo "  $SHARED/pair_singletons.csv"   | tee -a "$LOC/singles.log"
[ -f "$SHARED/triple_singletons.csv" ] && echo "  $SHARED/triple_singletons.csv" | tee -a "$LOC/singles.log"
