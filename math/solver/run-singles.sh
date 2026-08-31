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
#     bash solver/run-singles.sh all --answers               # answer words only
#     bash solver/run-singles.sh triples --answers --exhaustive
#
#     bash solver/run-singles.sh pairs   --disjoint --exhaustive
#     bash solver/run-singles.sh triples --disjoint --exhaustive
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
# --answers RESTRICTS WHICH WORDS MAY OPEN to the 2315 answers, the same
# restriction `optturns --guess-list mystery.txt` applies to the solver, and
# writes to its own *_answers.csv files -- it never overwrites the unrestricted
# ones, because they answer a different question.  The ANSWER SET is untouched:
# every count is still over the same 2315 words.  There are only
# C(2315, 2) = 2,678,455 answer pairs, 31x fewer than the unrestricted 84M.
#
# --disjoint KEEPS ONLY OPENERS WHOSE WORDS SHARE NO LETTER and repeat none: 10
# distinct letters for a pair, 15 for a triple.  Of the 12972 guesses, 8322 have
# 5 distinct letters, and they form 5,020,842 disjoint pairs -- 6% of the 84M --
# and roughly 139 million disjoint triples against 3.6e11 unrestricted.  THAT
# 2600x cut is what makes an exhaustive triple sweep possible over the full guess
# list, which is otherwise about a day and a half of work.
#
# The result is then the best DISJOINT opener, which is a DIFFERENT AND SMALLER
# CLAIM than the best opener.  Nothing here shows the unrestricted optimum is
# disjoint; the restriction is a modelling choice, so say "the best 15-distinct-
# letter triple", never "the best triple".  --disjoint composes with --answers.
#
# --exhaustive makes the TRIPLE stage a PROOF rather than a screen: it feeds
# EVERY pair the pair stage ranked to the extension, so every triple reachable
# within the current restriction is scored and the top of the file is the true
# maximum for that restriction.  This is the one configuration here where the greedy caveat
# above does NOT apply, and it is worth the wait for exactly that reason.  The
# full pair list is ~70 MB, too big to commit, so it goes to data/local/ and only
# the triple ranking lands in data/shared/.  EXTRAPOLATED at about 40-45 minutes:
# 2000 parent pairs extend in ~2s here (18 threads), and the work is linear in the
# parent count.  The run prints its own ETA from real progress -- trust that over
# this figure, which was not measured end to end.
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
ANSWERS=0           # --answers: only the 2315 answer words may open
DISJOINT=0          # --disjoint: 10 distinct letters per pair, 15 per triple
EXHAUSTIVE=0        # --exhaustive: feed EVERY pair to the triple stage

while [ $# -gt 0 ]; do
    case "$1" in
        words|pairs|triples|both|all) STAGE="$1"; shift ;;
        --top)        TOP="$2";      shift 2 ;;
        --pairs-top)  PAIRSTOP="$2"; shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --answers)    ANSWERS=1;     shift ;;
        --disjoint)   DISJOINT=1;    shift ;;
        --exhaustive) EXHAUSTIVE=1;  shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# The exhaustive widths are no longer a constant: --answers and --disjoint each
# change how many pairs exist, so the count comes from the pair stage's own
# sidecar rather than from a number written here that a new flag would silently
# invalidate.  BIGTOP just has to exceed any of them.
BIGTOP=100000000

if [ "$EXHAUSTIVE" = 1 ] && [ "$ANSWERS" = 0 ] && [ "$DISJOINT" = 0 ]; then
    echo "--exhaustive needs --answers or --disjoint: extending all 84129906" >&2
    echo "unrestricted pairs by 12972 words each is roughly a day and a half," >&2
    echo "which is not a run anyone should start by accident." >&2
    exit 1
fi

# --answers gets its own file names throughout.  Sharing them would let a
# restricted run silently overwrite an unrestricted one -- different question,
# same filename, and no way to tell afterwards which produced the file.
SUF=""
GLIST=""
DFLAG=""
if [ "$ANSWERS" = 1 ]; then
    SUF="_answers"
    GLIST="--guess-list data/shared/words/mystery.txt"
fi
if [ "$DISJOINT" = 1 ]; then
    SUF="${SUF}_disjoint"
    DFLAG="--disjoint"
fi

# Exhaustive means EVERY pair is a parent, so the pair stage must keep them all,
# and 2.7M rows is ~70 MB -- regenerable in seconds, so it goes to local/ rather
# than into the committed tree.
PAIROUT="$SHARED/pair_singletons$SUF.csv"
PAIRKEEP="$TOP"
if [ "$EXHAUSTIVE" = 1 ]; then
    PAIRKEEP="$BIGTOP"
    PAIRSTOP="$BIGTOP"
    PAIROUT="$LOC/pair_singletons${SUF}_all.csv"
fi

cd "$MATH" || exit 1

[ -f "$PATS" ] || {
    echo "no pattern matrix at $PATS" >&2
    echo "build it first:  python3 build_patterns.py" >&2
    exit 1
}

mkdir -p "$SHARED" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] singleton ranking, stage=$STAGE top=$TOP pairs-top=$PAIRSTOP answers=$ANSWERS exhaustive=$EXHAUSTIVE" \
    | tee -a "$LOC/singles.log"

if [ "$STAGE" = words ] || [ "$STAGE" = both ] || [ "$STAGE" = all ]; then
    # PYTHON, not the C binary: 12972 rows of a 243-bin histogram is a tenth of a
    # second in numpy, so a second C path would buy nothing and be one more thing
    # to keep in step with the pattern loader.
    PY=python3
    [ -x ../.venv/bin/python ] && PY=../.venv/bin/python
    AFLAG=""
    [ "$ANSWERS" = 1 ] && AFLAG="--answers"
    "$PY" tools/singletons.py $AFLAG 2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = pairs ] || [ "$STAGE" = both ] || [ "$STAGE" = all ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    ./solver/pairsplit --metric singles --top "$PAIRKEEP" \
        --out "$PAIROUT" $GLIST $DFLAG $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = triples ] || [ "$STAGE" = all ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    # WHICH PARENT FILE TO CUT FROM.  The exhaustive list is the same ranking as
    # the shared one, just longer -- same metric, same restriction, same
    # comparator -- so its first K rows ARE the shared file's first K rows, and a
    # narrow run can read it directly.  Preferring it means one exhaustive pair
    # run serves every width, instead of demanding a second, narrower run that
    # would recompute a prefix already on disk.
    ALLPAIRS="$LOC/pair_singletons${SUF}_all.csv"
    if [ "$EXHAUSTIVE" = 1 ]; then
        PAIRSRC="$ALLPAIRS"
    elif [ -f "$PAIROUT" ]; then
        PAIRSRC="$PAIROUT"
    else
        PAIRSRC="$ALLPAIRS"
    fi
    [ -f "$PAIRSRC" ] || {
        echo "no pair ranking at $PAIROUT" >&2
        [ "$EXHAUSTIVE" = 1 ] && echo "(nor the exhaustive list at $ALLPAIRS)" >&2
        echo "run the pair stage first, with the SAME flags:" >&2
        echo "  bash solver/run-singles.sh pairs$([ "$ANSWERS" = 1 ] && echo ' --answers')$([ "$EXHAUSTIVE" = 1 ] && echo ' --exhaustive')" >&2
        exit 1
    }
    echo "parents: $PAIRSRC" | tee -a "$LOC/singles.log"
    # The cut is taken here rather than inside pairsplit so that one wide pair
    # run serves every width: --extend reads whatever file it is handed, and its
    # line order IS the rank the minparent column is reported against.
    CUT="$LOC/pairs${SUF}_top$PAIRSTOP.csv"
    head -n $((PAIRSTOP + 1)) "$PAIRSRC" > "$CUT"
    # The EFFECTIVE width, which is what the name has to carry: asking for more
    # parents than the file holds is not an error, it just gives you every pair
    # there is, and naming that file after the request rather than the reality
    # would be the same untraceability this scheme exists to prevent.
    NPAR=$(( $(grep -c . "$CUT") - 1 ))
    if [ "$EXHAUSTIVE" = 1 ]; then
        TRISUF="_exhaustive"
    else
        TRISUF="_p$NPAR"
    fi
    TRIOUT="$SHARED/triple_singletons${SUF}${TRISUF}.csv"
    # Completeness comes from the pair run's OWN sidecar, not from counting lines
    # against a constant here: only that run knows how many candidates its flags
    # left to score.
    if [ "$EXHAUSTIVE" = 1 ]; then
        META="$PAIRSRC.meta"
        [ -f "$META" ] || {
            echo "no coverage sidecar at $META -- that pair file predates the" >&2
            echo "completeness check, so it cannot be shown to be exhaustive." >&2
            echo "rerun the pair stage with the same flags plus --exhaustive." >&2
            exit 1
        }
        grep -q "^complete=1$" "$META" || {
            echo "$PAIRSRC is a TRUNCATED ranking, per $META:" >&2
            sed -n 's/^scored=/  candidates scored: /p;s/^written=/  rows written:     /p' "$META" >&2
            echo "extending it would be a screen, not a proof -- rerun the pair" >&2
            echo "stage with --exhaustive first." >&2
            exit 1
        }
    fi
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    # --top bounds what is WRITTEN, never what is searched, so even an exhaustive
    # run emits a file that fits in the repo while still visiting every triple.
    ./solver/pairsplit --metric singles --extend "$CUT" --top "$TOP" \
        --out "$TRIOUT" $GLIST $DFLAG $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

echo "wrote:" | tee -a "$LOC/singles.log"
for f in "$SHARED/guess_singletons$SUF.csv" "$PAIROUT" "$LOC/pair_singletons${SUF}_all.csv" ${TRIOUT:-}; do
    [ -f "$f" ] && echo "  $f" | tee -a "$LOC/singles.log"
done
# Every triple file for this restriction, so a run that did NOT touch the widest
# one still shows you it is there -- the whole point of the per-width names.
ls -1 "$SHARED"/triple_singletons${SUF}_*.csv 2>/dev/null | while read -r f; do
    m="$f.meta"
    if [ -f "$m" ]; then
        echo "  (on disk) $f -- $(sed -n 's/^scored=/scored /p' "$m") candidates" \
            | tee -a "$LOC/singles.log"
    else
        # A file with no sidecar predates the coverage check.  It still gets
        # listed -- silence here would hide exactly the wide old result this
        # listing exists to protect.
        echo "  (on disk) $f -- coverage unknown, no sidecar" | tee -a "$LOC/singles.log"
    fi
done
