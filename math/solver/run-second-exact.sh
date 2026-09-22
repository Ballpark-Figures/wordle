#!/bin/bash
# The EXACT best predetermined second word, and the exact value of the strategy.
#
#     bash solver/run-second-exact.sh --opener spilt       # one opener, seconds
#     bash solver/run-second-exact.sh                      # ALL openers: a PROOF
#     bash solver/run-second-exact.sh --by-grays 3        # a word PER grey count
#     bash solver/run-second-exact.sh --limit 200 --dry-run
#
# --by-grays N gives a SEPARATE second word to each grey count from 5 down to N
# -- secondword's e5.e4....eN partition, evaluated exactly.  THE GROUPS ARE
# INDEPENDENT: they partition the firing replies, so the strategy's total is the
# decline branch plus a sum over groups, and each group's best word is found on
# its own.  k separate argmins, not a joint search over k words, and since every
# answer still lands in exactly one group the scanning work barely moves.
#
# WHAT IT COMPUTES.  Play an opener; if the reply shows at least --min-grays
# greys play one word committed to in advance; otherwise, and from the third
# guess on, play a uniformly random consistent ANSWER.  The random tail's cost
# depends only on the live candidate SET, so it is SUMMED EXACTLY by a memoised
# recursion rather than simulated -- no seed, no standard error, and a re-run
# reproduces the file.  solver/secondexact.c states the recursion and the bound.
#
# WHY EXACT RATHER THAN SIMULATED.  Choosing between 12972 second words means
# resolving differences of about 0.005 guesses; at a per-game sd near 0.9 that is
# ~290000 games EACH -- some 3.8 billion for ONE opener, hours of work, and the
# answer still has an error bar.  The recursion does it in under a second.
#
# --topk K MAKES IT A SCREEN, AND IT RESTRICTS THE OPENERS TOO.  ONE K governs
# both: the K best OPENERS by ascending expected answers remaining (the root is a
# branching point like any other, as in strturns / greens / mmturns / wturns /
# ultraturns / nerdle), and within each the K best second words per group by the
# one-ply sum-of-squares score (secondword's rule, the same code path).  So each
# total is an UPPER BOUND and the winner is the best of the openers EXAMINED.
# A NAMED opener (--opener / --openers) is exempt from the root beam: there you
# have chosen the root and K beams only the branching below it.  K is part of the objective: it is in the filename and
# in the settings stamp, and a resume refuses a file written under a different K.
# MEASURED on the completed by-grays run: the exact walk performed 286 million
# second-word evaluations; at K=10 it would perform at most 322800.
#
# IT RESUMES.  Each opener's rows are appended the moment it finishes, so the CSV
# IS the checkpoint: re-run the same command and it skips what is on file and
# seeds the bound with the best total already proved.  A cut opener is not
# recorded -- re-cutting it is free and still sound.
#
# WITHOUT --topk IT IS A PROOF, NOT A SCREEN.  Every opener gets a sound lower bound first
# (T(S) >= 2|S| - 1 per bucket, no recursion), they are walked ASCENDING against
# a shared incumbent, and an opener whose bound is not below it cannot win and is
# never evaluated.  What comes out is the optimum over every (opener, second
# word) pair.  Ties are kept: every cut tests `<`, never `<=`.
#
# IT IS TIED TO THE `answer` FOLLOW-UP -- the tail draws from consistent ANSWERS,
# so a state is a subset of the 2315.  The `guess` follow-up is a different and
# much larger recursion and is not what this computes.
#
# MEASURED: bounding all 12972 openers takes about a minute; one opener's exact
# scan of all 12972 second words is 0.6s (16x faster than without the cut, and
# --no-prune proves the two agree).  A full run is tens of minutes -- watch the
# `evaluated / cut` line, which is the real cost.
#
# Output: data/shared/secondexact/, log under data/local/secondexact/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

OPENER=""
OPENERS=""
WORDS=""
MINGRAYS=3
BYGRAYS=""
SPLITV=0
SPLITMV=0
SPLITNZ=0
GSPECS=""
LIMIT=""
THREADS=""
MEMOBITS=""
REPORT=30
TOPK=""
MAXLVL=""
THIRDKEY=""
THIRDMAX=""
THIRDDEC=0
NOPRUNE=0
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --opener)     OPENER="$2";   shift 2 ;;
        --openers)    OPENERS="$2";  shift 2 ;;
        --words)      WORDS="$2";    shift 2 ;;
        --min-grays)  MINGRAYS="$2"; shift 2 ;;
        --by-grays)   BYGRAYS="$2";  shift 2 ;;
        --split-vowels)         SPLITV=1;  shift ;;
        --split-matched-vowels) SPLITMV=1; shift ;;
        --split-nongray)        SPLITNZ=1; shift ;;
        --group)      GSPECS="$GSPECS --group $2"; shift 2 ;;
        --limit)      LIMIT="$2";    shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --memo-bits)  MEMOBITS="$2"; shift 2 ;;
        --report)     REPORT="$2";   shift 2 ;;
        --topk|-k)    TOPK="$2";     shift 2 ;;
        --max-level)  MAXLVL="$2";   shift 2 ;;
        --third-key)  THIRDKEY="$2"; shift 2 ;;
        --third-max-matched) THIRDMAX="$2"; shift 2 ;;
        --third-decline)     THIRDDEC=1;    shift ;;
        --no-prune)   NOPRUNE=1;     shift ;;
        --dry-run)    DRYRUN=1;      shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$MINGRAYS" in
    ''|*[!0-9]*) echo "--min-grays must be a number of grey tiles (1-5)" >&2; exit 1 ;;
esac
if [ "$MINGRAYS" -lt 1 ] || [ "$MINGRAYS" -gt 5 ]; then
    echo "--min-grays $MINGRAYS: a reply has 5 tiles, and 0 would fire every game" >&2
    exit 1
fi

cd "$MATH" || exit 1

BIN=solver/secondexact
[ -x "$BIN" ] || { echo "no $BIN -- build it with 'sh build.sh' from math/solver/" >&2
                   exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix at data/local/patterns/patterns.npy" >&2
    echo "  Build it with 'python3 build_patterns.py' from math/ (~2s, 30 MB)." >&2
    exit 1; }

OUTDIR=data/shared/secondexact
LOC=data/local/secondexact

# THE FIRING CONDITION, and nothing else -- these are the flags that decide both
# what the run computes and what it is called.
# EVERY condition flag is forwarded, INCLUDING a --split-* with nothing to
# split: the binary refuses that combination, and swallowing it here would
# quietly run the plain --min-grays condition under a flag asking for another.
COND=""
[ -z "$BYGRAYS" ]  || COND="$COND --by-grays $BYGRAYS"
[ "$SPLITV" = 0 ]  || COND="$COND --split-vowels"
[ "$SPLITMV" = 0 ] || COND="$COND --split-matched-vowels"
[ "$SPLITNZ" = 0 ] || COND="$COND --split-nongray"
COND="$COND$GSPECS"
# --min-grays is the SUGAR for "no groups named", so it applies only then.
[ -n "$COND" ] || COND=" --min-grays $MINGRAYS"

# --words RESTRICTS WHICH WORDS MAY BE COMMITTED TO, at every level and at the
# root -- `--words mystery` is the answers-only variant, `secondword`'s
# `--variant mystery` made exact.  A DIFFERENT OBJECTIVE, not a setting: a
# strictly smaller strategy space, so its totals are weakly worse and never share
# a table with the unrestricted run.  It rides in the LABEL, so it reaches the
# filename and the settings stamp and a resume refuses a file from the other --
# which is why it is part of COND rather than a flag added later.
if [ -n "$WORDS" ]; then
    case "$WORDS" in
        */*|*.txt) WLIST="$WORDS" ;;
        *)         WLIST="data/shared/words/$WORDS.txt" ;;
    esac
    [ -f "$WLIST" ] || { echo "--words: no such list: $WLIST" >&2; exit 1; }
    COND="$COND --words $WLIST"
fi

# ASK THE BINARY WHAT THE CONDITION IS CALLED.  groups.c canonicalises a spec --
# it sorts the groups, drops repeats, and collapses a vacuous split (e5_mv0 IS
# e5) -- so the name cannot be derived here without writing that rule a second
# time, in a second language.  It also means an impossible combination is
# refused NOW, before a log or a CSV exists.
LABEL=$($BIN $COND --print-label) || exit 1
STEM="exact_${LABEL}"
[ -z "$OPENER" ]  || STEM="${STEM}_${OPENER}"
[ -z "$OPENERS" ] || STEM="${STEM}_$(basename "$OPENERS" .txt)"
[ -z "$TOPK" ]    || STEM="${STEM}_k${TOPK}"
[ -z "$MAXLVL" ]   || STEM="${STEM}_L${MAXLVL}"
[ -z "$THIRDKEY" ] || STEM="${STEM}_3${THIRDKEY}${THIRDMAX}"
[ "$THIRDDEC" = 0 ] || STEM="${STEM}dec"
[ -z "$LIMIT" ]   || STEM="${STEM}_limit${LIMIT}"
[ "$NOPRUNE" = 0 ] || STEM="${STEM}_noprune"
OUT="$OUTDIR/$STEM.csv"

FLAGS="--report $REPORT$COND"
[ -z "$OPENER" ]   || FLAGS="$FLAGS --opener $OPENER"
[ -z "$OPENERS" ]  || FLAGS="$FLAGS --openers $OPENERS"
[ -z "$TOPK" ]     || FLAGS="$FLAGS --topk $TOPK"
[ -z "$MAXLVL" ]   || FLAGS="$FLAGS --max-level $MAXLVL"
[ -z "$THIRDKEY" ] || FLAGS="$FLAGS --third-key $THIRDKEY"
[ -z "$THIRDMAX" ] || FLAGS="$FLAGS --third-max-matched $THIRDMAX"
[ "$THIRDDEC" = 0 ] || FLAGS="$FLAGS --third-decline"
[ -z "$LIMIT" ]    || FLAGS="$FLAGS --limit $LIMIT"
[ -z "$THREADS" ]  || FLAGS="$FLAGS --threads $THREADS"
[ -z "$MEMOBITS" ] || FLAGS="$FLAGS --memo-bits $MEMOBITS"
[ "$NOPRUNE" = 0 ] || FLAGS="$FLAGS --no-prune"

echo "exact second word"
NGRP=$(echo "$LABEL" | tr '.' '\n' | wc -l | tr -d ' ')
echo "  fires on   $LABEL$([ "$NGRP" -gt 1 ] && echo "  ($NGRP groups, a SEPARATE word for each)")"
echo "  openers    ${OPENER:-${OPENERS:-${TOPK:+the $TOPK best by expected answers remaining}}}${OPENER:-${OPENERS:-${TOPK:+}}}${LIMIT:+ (first $LIMIT)}"
[ -z "$WORDS" ] || {
    echo "  WORDS      every committed word -- the opener included -- from $WLIST"
    echo "             ^ a DIFFERENT objective: a strictly smaller strategy space,"
    echo "               so its expected is weakly WORSE and never shares a table"
    echo "               with the 12972-word run.  The tail is untouched."
}
echo "  follow-up  answer (a uniformly random consistent answer)"
if [ -n "$MAXLVL" ]; then
    echo "  LEVELS     a committed word at every level down to $MAXLVL, each of which"
    echo "             may DECLINE to the random tail where that is cheaper"
    echo "             ^ cost is the beam width PER LEVEL: k^($MAXLVL-1) per group"
fi
if [ -n "$THIRDKEY" ]; then
    echo "  THIRD WORD when the two replies have proved at most $THIRDMAX letters,"
    echo "             keyed per $THIRDKEY$([ "$THIRDDEC" = 1 ] && echo ", declining where the random tail is cheaper" || echo ", FORCED where it fires")"
fi
if [ -n "$TOPK" ]; then
    echo "  BEAM k=$TOPK    the $TOPK best OPENERS, and the $TOPK best second words per group"
    echo "             ONE K governs both, as in every other solver here."
    echo "             ^ a SCREEN, not a proof: every total is an UPPER BOUND and"
    echo "               the winner is the best of the openers EXAMINED."
else
    echo "  beam       none -- every candidate, so the result is PROVEN optimal"
fi
[ "$NOPRUNE" = 0 ] || echo "  NO PRUNING: every second word evaluated (the gate's check)"
[ ! -f "$OUT" ] || echo "  RESUMING   $OUT exists; its openers are skipped and its best seeds the bound"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $BIN $FLAGS --out $OUT"
    exit 0
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output secondexact "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] secondexact $STEM" | tee -a "$LOC/$STEM.log"

$BIN $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
