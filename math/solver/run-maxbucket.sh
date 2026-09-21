#!/bin/bash
# Rank openers by the SIZE OF THE LARGEST BUCKET their feedback produces,
# attached, with live output in this terminal.
#
#     bash solver/run-maxbucket.sh                      # from math/, or anywhere
#     bash solver/run-maxbucket.sh --answer-set all
#     bash solver/run-maxbucket.sh --rank answers
#     bash solver/run-maxbucket.sh --top 50             # longer printed head
#     bash solver/run-maxbucket.sh --rank-by avg_remaining
#     bash solver/run-maxbucket.sh --rank-by buckets
#
# WHAT THIS COMPUTES, precisely:
#
#   A guess PARTITIONS the answers -- two answers share a part iff they give it
#   the same feedback.  This reports, per guess, the size of the BIGGEST part:
#   the worst case, how many answers are still alive after the unluckiest reply.
#   Ranked ascending, smallest worst case first.
#
#   IT IS THE MINIMAX CRITERION.  It is NOT the singleton count of
#   run-singles.sh (which looks at the parts of size ONE), and emphatically not
#   an optturns-family total, which is a number of GUESSES subject to a 6-guess
#   guarantee.  A worst-case bucket size says nothing about how the rest of the
#   game goes.  Never put these in one table.
#
#   --rank-by CHOOSES WHICH AGGREGATION ORDERS THE FILE.  The partition is
#   computed once and every row carries all of them; they rank DIFFERENTLY and
#   none implies another, so each key gets its own file:
#
#     max_bucket           the MAX part size -- the minimax criterion (default)
#     buckets              HOW MANY distinct colourings the guess can show.
#                          The one key where more is better, so it sorts
#                          DESCENDING.
#     avg_remaining        the answer-weighted MEAN part size, sum(n^2)/NA: the
#                          expected words still consistent after the reply, the
#                          answer drawn uniformly from the answer set.
#     avg_remaining_nowin  the same with the all-green part dropped, so a game
#                          already won contributes nothing and an opener is not
#                          penalised for being answerable.  Both divide by the
#                          full NA, so they differ by (win part)^2 / NA.
#
#   THE SORT IS ON EXACT INTEGERS (ssq / ssq_nowin), never on the printed float,
#   so a tie in the file is a real tie rather than a rounding artefact.
#
#   THE ANSWER SET IS PART OF THE QUESTION.  --answer-set mystery counts buckets
#   over the 2315 curated answers; --answer-set all makes every one of the 12972
#   legal words an answer.  Different questions, different files.  --rank is a
#   SEPARATE axis: it restricts which words are listed as ROWS and changes no
#   count -- a word scores what it always scored, and ranks move only because the
#   field is smaller.
#
#   Nothing searches or samples: a pure function of the committed word lists and
#   the pattern matrix, so it is exact, has no standard error, and a re-run
#   reproduces its file byte for byte.
#
#   THE GATE IS BUILT IN and always runs, in three parts: sampled guesses are
#   re-bucketed FROM THE STRINGS by wordle.pattern (sharing no machinery with the
#   matrix path), pinning the max, the bucket count and both sums of squares;
#   avg_remaining_nowin is diffed against multiwordle_fast.root_values for EVERY
#   guess -- an independent implementation of that exact quantity, the one
#   run-multiwordle-exact.sh already orders openers by, compared as integers;
#   and in the default answer set the minimum is cross-checked against the
#   committed data/shared/absurdle/one_shortest_solution.txt, whose opener is a
#   minimiser of max_bucket.  It exits nonzero rather than reporting.
#
# USE THIS RATHER THAN CALLING tools/maxbucket.py DIRECTLY.  The tool refuses to
# run without --out and refuses to pick either axis for you; this forwards both
# EXPLICITLY, so the one decision has one owner, and it tees a log naming the run.
#
# Outputs data/shared/maxbucket/maxbucket_<answer-set>_<rank>[_by-<key>].csv,
# columns word,max_bucket,max_pattern,max_ties,buckets,ssq,ssq_nowin,
# avg_remaining,avg_remaining_nowin,rank.  max_bucket KEEPS THE HISTORIC
# UNSUFFIXED NAME, so the committed file stays where every reader expects it and
# the other keys cannot collide with it.  max_pattern is the lowest-coded pattern
# attaining the maximum and max_ties how many attain it; both are DESCRIPTIVE --
# the ranking is on the --rank-by key alone, ties broken alphabetically to make
# the file deterministic.  Log under data/local/maxbucket/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults a HUMAN reads, forwarded explicitly -- never ones the program falls
# back on: tools/maxbucket.py refuses to run if either is missing.
ANSWER_SET=mystery
RANK=all
RANK_BY=max_bucket
TOP=25

while [ $# -gt 0 ]; do
    case "$1" in
        --answer-set) ANSWER_SET="$2"; shift 2 ;;
        --rank)       RANK="$2";       shift 2 ;;
        --rank-by)    RANK_BY="$2";    shift 2 ;;
        --top)        TOP="$2";        shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$ANSWER_SET" in
    mystery|all) ;;
    *) echo "--answer-set must be 'mystery' (the 2315) or 'all' (the 12972)" >&2
       exit 1 ;;
esac
case "$RANK" in
    all|answers) ;;
    *) echo "--rank must be 'all' (every legal guess) or 'answers' (the 2315)" >&2
       exit 1 ;;
esac
case "$RANK_BY" in
    max_bucket|buckets|avg_remaining|avg_remaining_nowin) ;;
    *) echo "--rank-by must be max_bucket, buckets, avg_remaining or avg_remaining_nowin" >&2
       exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

# --answer-set all reads the SQUARE guess x guess matrix -- a separate artifact
# from the 12972x2315 one, gitignored under data/local/, so it is missing on a
# fresh clone.
if [ "$ANSWER_SET" = all ] && [ ! -f data/local/patterns/patterns_full.npy ]; then
    echo "--answer-set all needs the square guess x guess matrix." >&2
    echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
    exit 1
fi
if [ ! -f data/local/patterns/patterns.npy ]; then
    echo "the pattern matrix is missing (it is gitignored under data/local/)." >&2
    echo "  Build it with '$PY build_patterns.py' (~2s, 30 MB)." >&2
    exit 1
fi

# max_bucket keeps the historic unsuffixed name; every other key is a DIFFERENT
# ranking of the same partition and gets its own file, so neither can overwrite
# or be mistaken for the other.
STEM=maxbucket_${ANSWER_SET}_${RANK}
[ "$RANK_BY" = max_bucket ] || STEM=${STEM}_by-${RANK_BY}
OUT=data/shared/maxbucket/${STEM}.csv

MARKER="maxbucket.py --answer-set $ANSWER_SET --rank $RANK --rank-by $RANK_BY"
RUNNING=$(pgrep -f -- "$MARKER" 2>/dev/null | tr '\n' ' ')
if [ -n "$RUNNING" ]; then
    echo "REFUSING: the same run is already going (pid $RUNNING)." >&2
    echo "  Two copies would write $OUT at once." >&2
    exit 1
fi

LOC=data/local/maxbucket
mkdir -p "$LOC" data/shared/maxbucket

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] maxbucket: answer-set=$ANSWER_SET rank=$RANK rank-by=$RANK_BY" \
    | tee -a "$LOC/${STEM}.log"

"$PY" -u tools/maxbucket.py --answer-set "$ANSWER_SET" --rank "$RANK" \
    --rank-by "$RANK_BY" --top "$TOP" --out "$OUT" 2>&1 \
    | tee -a "$LOC/${STEM}.log"
