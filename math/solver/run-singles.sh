#!/bin/bash
# Rank openers by SINGLETON COUNT -- single words, blind pairs, blind triples --
# and save each ranking.  Attached, with live output in this terminal.
#
#     bash solver/run-singles.sh                  # from math/, or anywhere: words + pairs
#     bash solver/run-singles.sh words            # just the single-word ranking
#     bash solver/run-singles.sh pairs            # just the pair ranking
#     bash solver/run-singles.sh triples          # extend the top pairs to triples
#     bash solver/run-singles.sh quads --disjoint-triples   # disjoint parents, ANY 4th word
#     bash solver/run-singles.sh quads --disjoint            # 20 distinct letters, all four
#     bash solver/run-singles.sh quads --disjoint --triples-top all   # every parent
#     bash solver/run-singles.sh quints --disjoint-quads   # disjoint quads, ANY 5th word
#     bash solver/run-singles.sh quints --disjoint         # 25 distinct letters, all five
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
# --disjoint MEANS THE SAME THING AT EVERY SIZE: no word of the opener shares a
# letter with another, and none repeats one.  That is 10 distinct letters for a
# pair, 15 for a triple, 20 for a quad.
#
# --disjoint-triples is the quads-only variant: take the DISJOINT triple ranking
# as parents but leave the 4th word unrestricted.  It exists because the two are
# very different searches -- see the note on quads below -- and because a single
# flag meaning "disjoint parents" in one stage and "disjoint everything" in
# another is the kind of overload that gets misread later.
#
# The original --disjoint description, still accurate for pairs and triples:  Of the 12972 guesses, 8322 have
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
TRIPSTOP=100000     # triples fed to the quad stage
TRIPFROM=""         # which triple ranking to extend; default is the widest on disk
THREADS=0           # 0 = let OpenMP pick, which is right on both machines
ANSWERS=0           # --answers: only the 2315 answer words may open
DISJOINT=0          # --disjoint: every word of the opener shares no letter
DISJTRI=0           # --disjoint-triples: disjoint PARENTS only, 4th word free
DISJQUAD=0          # --disjoint-quads: disjoint PARENTS only, 5th word free
QUADSTOP=100000     # quads fed to the quint stage; "all" for every one
QUADFROM=""         # which quad ranking to extend
EXHAUSTIVE=0        # --exhaustive: feed EVERY pair to the triple stage

while [ $# -gt 0 ]; do
    case "$1" in
        words|pairs|triples|quads|quints|both|all) STAGE="$1"; shift ;;
        --top)        TOP="$2";      shift 2 ;;
        --pairs-top)  PAIRSTOP="$2"; shift 2 ;;
        --triples-top) TRIPSTOP="$2"; shift 2 ;;
        --triples-from) TRIPFROM="$2"; shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --answers)    ANSWERS=1;     shift ;;
        --disjoint)   DISJOINT=1;    shift ;;
        --disjoint-triples) DISJTRI=1; shift ;;
        --disjoint-quads)   DISJQUAD=1; shift ;;
        --quads-top)   QUADSTOP="$2"; shift 2 ;;
        --quads-from)  QUADFROM="$2"; shift 2 ;;
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
# How many words may open, which --answers changes.  The messages below report
# it rather than the 12972 they used to hardcode: under --answers an
# "unrestricted" last word still comes from the 2315 answers, and saying 12972
# there described a run that was not happening.
NOPEN=12972
[ "$ANSWERS" = 1 ] && NOPEN=2315
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

if [ "$DISJTRI" = 1 ] && [ "$STAGE" != quads ] && [ "$STAGE" != all ]; then
    echo "--disjoint-triples only applies to the quads stage; use --disjoint" >&2
    echo "to restrict the pair or triple stages themselves." >&2
    exit 1
fi
if [ "$DISJQUAD" = 1 ] && [ "$STAGE" != quints ] && [ "$STAGE" != all ]; then
    echo "--disjoint-quads only applies to the quints stage; use --disjoint" >&2
    echo "to restrict the earlier stages themselves." >&2
    exit 1
fi


# Rows in a ranking, WITHOUT rescanning it. The sidecar already records what the
# run wrote, and counting 139M lines of a 4 GB file to rediscover that took
# longer than the work it was guarding.
rows_in() {
    _f="$1"
    if [ -f "$_f.meta" ]; then
        _w=$(sed -n 's/^written=//p' "$_f.meta")
        [ -n "$_w" ] && { echo "$_w"; return; }
    fi
    echo $(( $(grep -c . "$_f") - 1 ))
}


# Is the CUT we are about to extend the complete parent set for its restriction?
# Only then may --parents-complete be passed: on a partial list it silently drops
# every result whose canonical parent is missing.  Both halves are checked -- the
# source ran to completion, AND our cut kept every row of it.
parents_complete_flag() {
    _src="$1"; _ncut="$2"
    [ -f "$_src.meta" ] || { echo ""; return; }
    grep -q "^complete=1$" "$_src.meta" || { echo ""; return; }
    _w=$(sed -n 's/^written=//p' "$_src.meta")
    [ -n "$_w" ] && [ "$_ncut" = "$_w" ] && echo "--parents-complete" || echo ""
}

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
    NSRCP=$(rows_in "$PAIRSRC")
    if [ "$PAIRSTOP" -ge "$NSRCP" ]; then
        CUT="$PAIRSRC"
    else
        CUT="$LOC/pairs${SUF}_top$PAIRSTOP.csv"
        head -n $((PAIRSTOP + 1)) "$PAIRSRC" > "$CUT"
    fi
    # The EFFECTIVE width, which is what the name has to carry: asking for more
    # parents than the file holds is not an error, it just gives you every pair
    # there is, and naming that file after the request rather than the reality
    # would be the same untraceability this scheme exists to prevent.
    NPAR=$(rows_in "$CUT")
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
    PCFLAG=$(parents_complete_flag "$PAIRSRC" "$NPAR")
    [ -n "$PCFLAG" ] && echo "parents are complete: skipping the parent table" \
        | tee -a "$LOC/singles.log"
    # --top bounds what is WRITTEN, never what is searched, so even an exhaustive
    # run emits a file that fits in the repo while still visiting every triple.
    ./solver/pairsplit --metric singles --extend "$CUT" --top "$TOP" \
        --out "$TRIOUT" $GLIST $DFLAG $PCFLAG --parent-count "$NPAR" $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = quads ] || [ "$STAGE" = all ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    # WHICH triple ranking to build on is a real choice, not a default to bury:
    # an exhaustive parent gives a quad screen with a proven base, a narrow one
    # does not.  Absent --triples-from, prefer the exhaustive file and say so.
    QSUF="$SUF"
    QDFLAG="$DFLAG"
    if [ "$DISJTRI" = 1 ]; then
        QSUF="${SUF}_disjoint"      # parents come from the disjoint ranking ...
        QDFLAG=""                   # ... but the 4th word is not restricted
    fi
    if [ -n "$TRIPFROM" ]; then
        TSRC="$TRIPFROM"
    elif [ -f "$SHARED/triple_singletons${QSUF}_exhaustive.csv" ]; then
        TSRC="$SHARED/triple_singletons${QSUF}_exhaustive.csv"
    else
        # An EMPTY $SUF makes triple_singletons_* match the _answers_ and
        # _disjoint_ files too, so an unrestricted run could silently build on a
        # restricted parent -- a different search wearing the same prefix. Keep
        # only names whose restriction is exactly this run's.
        TSRC=$(ls -1S "$SHARED"/triple_singletons${QSUF}_*.csv 2>/dev/null \
               | grep -vE "_(answers|disjoint)" | head -1)
        [ -n "$QSUF" ] && TSRC=$(ls -1S "$SHARED"/triple_singletons${QSUF}_*.csv 2>/dev/null | head -1)
    fi
    [ -n "$TSRC" ] && [ -f "$TSRC" ] || {
        echo "no triple ranking found for this restriction" >&2
        echo "run the triple stage first, or pass --triples-from FILE" >&2
        exit 1
    }
    echo "parent triples: $TSRC" | tee -a "$LOC/singles.log"
    if [ "$DISJOINT" = 1 ]; then
        echo "4th word: DISJOINT -- 20 distinct letters across all four." \
            | tee -a "$LOC/singles.log"
    else
        echo "4th word: unrestricted -- any of the $NOPEN openers." \
            | tee -a "$LOC/singles.log"
    fi
    # Only make a cut when one is actually being taken.  Asking for more parents
    # than the file holds used to copy the whole thing -- 4 GB for the exhaustive
    # disjoint triples -- to produce a byte-identical file.
    NSRC=$(rows_in "$TSRC")
    # "all" beats guessing a number bigger than the file: --triples-top 100000000
    # LOOKS like everything and is a real cut of a 138,953,994-row ranking, which
    # silently turns an exhaustive sweep into a screen and disables the
    # parents-complete fast path with it.
    [ "$TRIPSTOP" = all ] && TRIPSTOP="$NSRC"
    if [ "$TRIPSTOP" -ge "$NSRC" ]; then
        TCUT="$TSRC"
        NTRI="$NSRC"
    else
        TCUT="$LOC/triples${QSUF}_top$TRIPSTOP.csv"
        head -n $((TRIPSTOP + 1)) "$TSRC" > "$TCUT"
        NTRI=$TRIPSTOP
    fi
    # The name records BOTH halves of the search: which parents, and whether the
    # 4th word was restricted. They are different questions with different
    # answers, so they must not share a filename.
    QNAME="$SUF"
    [ "$DISJTRI" = 1 ] && QNAME="${SUF}_disjointtriples"
    QUADOUT="$SHARED/quad_singletons${QNAME}_t$NTRI.csv"
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    QPCFLAG=$(parents_complete_flag "$TSRC" "$NTRI")
    [ -n "$QPCFLAG" ] && echo "parents are complete: skipping the parent table" \
        | tee -a "$LOC/singles.log"
    ./solver/pairsplit --metric singles --extend "$TCUT" --top "$TOP" \
        --out "$QUADOUT" $GLIST $QDFLAG $QPCFLAG --parent-count "$NTRI" $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

if [ "$STAGE" = quints ] || [ "$STAGE" = all ]; then
    [ -x ./solver/pairsplit ] || {
        echo "no pairsplit binary -- run 'sh build.sh' in solver/" >&2
        exit 1
    }
    # Same shape as the quad stage one level up: --disjoint-quads borrows the
    # disjoint quad ranking as parents without inheriting the letter rule, while
    # --disjoint carries it through to the 5th word (25 of 26 letters).
    QQSUF="$SUF"
    QQDFLAG="$DFLAG"
    if [ "$DISJQUAD" = 1 ]; then
        QQSUF="${SUF}_disjoint"
        QQDFLAG=""
    fi
    if [ -n "$QUADFROM" ]; then
        QSRC="$QUADFROM"
    else
        QSRC=$(ls -1S "$SHARED"/quad_singletons${QQSUF}_*.csv 2>/dev/null | head -1)
        [ -z "$QQSUF" ] && QSRC=$(ls -1S "$SHARED"/quad_singletons_*.csv 2>/dev/null \
                                 | grep -vE "_(answers|disjoint)" | head -1)
    fi
    [ -n "$QSRC" ] && [ -f "$QSRC" ] || {
        echo "no quad ranking found for this restriction" >&2
        echo "run the quads stage first, or pass --quads-from FILE" >&2
        exit 1
    }
    echo "parent quads: $QSRC" | tee -a "$LOC/singles.log"
    if [ "$DISJOINT" = 1 ]; then
        echo "5th word: DISJOINT -- 25 distinct letters across all five." \
            | tee -a "$LOC/singles.log"
    else
        echo "5th word: unrestricted -- any of the $NOPEN openers." \
            | tee -a "$LOC/singles.log"
    fi
    NQSRC=$(rows_in "$QSRC")
    [ "$QUADSTOP" = all ] && QUADSTOP="$NQSRC"
    if [ "$QUADSTOP" -ge "$NQSRC" ]; then
        QCUT="$QSRC"; NQUAD="$NQSRC"
    else
        QCUT="$LOC/quads${QQSUF}_top$QUADSTOP.csv"
        head -n $((QUADSTOP + 1)) "$QSRC" > "$QCUT"
        NQUAD="$QUADSTOP"
    fi
    QNAME2="$SUF"
    [ "$DISJQUAD" = 1 ] && QNAME2="${SUF}_disjointquads"
    QUINTOUT="$SHARED/quint_singletons${QNAME2}_q$NQUAD.csv"
    TFLAG=""
    [ "$THREADS" -gt 0 ] && TFLAG="--threads $THREADS"
    QQPCFLAG=$(parents_complete_flag "$QSRC" "$NQUAD")
    [ -n "$QQPCFLAG" ] && echo "parents are complete: skipping the parent table" \
        | tee -a "$LOC/singles.log"
    ./solver/pairsplit --metric singles --extend "$QCUT" --top "$TOP" \
        --out "$QUINTOUT" $GLIST $QQDFLAG $QQPCFLAG --parent-count "$NQUAD" $TFLAG \
        2>&1 | tee -a "$LOC/singles.log"
fi

echo "wrote:" | tee -a "$LOC/singles.log"
for f in "$SHARED/guess_singletons$SUF.csv" "$PAIROUT" "$LOC/pair_singletons${SUF}_all.csv" ${TRIOUT:-} ${QUADOUT:-} ${QUINTOUT:-}; do
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
