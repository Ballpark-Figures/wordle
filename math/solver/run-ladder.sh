#!/bin/bash
# THE LADDER: five committed words, each fired by its own threshold on how many
# letters you have matched.
#
#     bash solver/run-ladder.sh --ladder 5 -k 5
#     bash solver/run-ladder.sh --ladder 5 -k 20 --opener clint
#     bash solver/run-ladder.sh --ladder 5 -k 20 --words mystery
#     bash solver/run-ladder.sh --ladder 3 -k 50 --dry-run
#
# --words RESTRICTS WHICH WORDS MAY BE COMMITTED TO, at every level AND at the
# root -- `--words mystery` is the answers-only variant, every word of the ladder
# drawn from the 2315.  It is a DIFFERENT OBJECTIVE, not a setting: a strictly
# smaller strategy space, so its totals are weakly worse and must never share a
# table with the unrestricted run.  It is in the filename and in the settings
# stamp, and a resume refuses a file from the other.  The random TAIL is
# untouched -- it always draws from the consistent answers, which is the
# strategy's definition rather than a pool anyone chose.
#   NB restrict with --words, NOT with `--openers mystery.txt`: a named opener
#   list is exempt from the root beam, so that would walk all 2315 openers
#   rather than the K best, which at depth 5 is a different kind of run entirely.
#
# THE STRATEGY, exactly (math/ladder.py states it and IS the source of truth):
#
#     guess 1     w1                                       always
#     guess d     matched < T_d ?  w_d  :  a uniformly random consistent ANSWER,
#                                          and the LADDER IS OVER
#     guess N+1   a uniformly random consistent ANSWER
#
# `matched` is the CUMULATIVE number of letters proved present -- tree_states'
# greens + yellows, counted again per proved copy -- which is the one thing a
# player can read straight off the board.  It is a function of the words and
# replies alone, never of the answer, so it is constant within a bucket and is a
# legal thing to branch on.
#
# DECLINING ENDS THE LADDER (the user's call, 2026-09-22): once a level is over
# its threshold every remaining guess is random, so word d is played only when
# levels 2..d-1 all fired.  That is what makes the whole strategy N words and
# N-1 thresholds rather than a tree.
#
# IT IS EXACT, NOT SIMULATED.  The random tail's cost depends only on the live
# candidate SET, so it is summed by the memoised recursion secondexact.c states
# -- no seed, no standard error, and a re-run reproduces the file byte for byte.
#
# WHAT THE NUMBER IS.  Expected guesses OUTRIGHT: play is never truncated, so it
# sits with wordlesim / multiwordle / foximax and NOT with any optturns-family
# total, every one of which is an optimum SUBJECT TO a 6-guess guarantee.  Never
# put the two in one table.  Guess 6 being random is not a cap -- it is simply
# where a 5-word ladder runs out of committed words.
#
# -k K IS REQUIRED AND IT MAKES THIS A SCREEN.  Five words over 12972 each is not
# a space anything enumerates.  ONE K governs both ends, as in every other solver
# here: the K best OPENERS by ascending expected answers remaining, and the K
# best words at EVERY level below by the one-ply sum-of-squares score
# (secondword's rule, the same code path).  So every total is an UPPER BOUND and
# the winner is the best of the openers EXAMINED, never the optimum.  A NAMED
# opener (--opener) is exempt from the root beam: there you have chosen the root
# and K beams only the levels below it.
#
# THRESHOLDS ARE ENUMERATED, NOT BEAMED.  A threshold is part of the objective,
# and only the values inducing a DIFFERENT firing set are tried -- at most seven
# at level 2, usually two or three further down.
#
# COST is the beam width TIMES the thresholds, per level: roughly (3k)^(N-1)
# ladders per opener before the bound cuts.  So a deep run wants a far smaller k
# than a shallow one -- price it with --opener on one word first.
#
# IT IS A DIFFERENT STRATEGY FROM --max-level, not a cheaper search for the same
# one.  There every matched count at a level gets its OWN word; here they share
# one and a threshold decides who plays it, so this family is strictly contained
# in that one at the same beam.  Their numbers do not belong in one table.
#
# IT IS TIED TO THE `answer` FOLLOW-UP -- the tail draws from consistent ANSWERS,
# so a state is a subset of the 2315.
#
# IT RESUMES.  Each opener's rows are appended the moment it finishes, so the CSV
# IS the checkpoint: re-run the same command and it skips what is on file and
# seeds the bound with the best total already proved.  Depth and any pinning are
# in the name AND in the settings stamp, and a resume refuses a file written for
# a different question.
#
# Output: data/shared/ladder/, log under data/local/ladder/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LEVELS=""
TOPK=""
OPENER=""
OPENERS=""
WORDS=""
PIN=""
LIMIT=""
THREADS=""
MEMOBITS=""
REPORT=30
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --ladder)     LEVELS="$2";   shift 2 ;;
        --topk|-k)    TOPK="$2";     shift 2 ;;
        --opener)     OPENER="$2";   shift 2 ;;
        --openers)    OPENERS="$2";  shift 2 ;;
        --words)      WORDS="$2";    shift 2 ;;
        --pin-thresholds) PIN="$2";  shift 2 ;;
        --limit)      LIMIT="$2";    shift 2 ;;
        --threads)    THREADS="$2";  shift 2 ;;
        --memo-bits)  MEMOBITS="$2"; shift 2 ;;
        --report)     REPORT="$2";   shift 2 ;;
        --dry-run)    DRYRUN=1;      shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# NEITHER IS DEFAULTED.  The depth and the beam are both part of what the run
# MEANS -- a 3-word ladder and a 5-word one are different strategies, and K
# decides whether a total is worth anything -- so refusing to run is the only
# safe default.
[ -n "$LEVELS" ] || { echo "--ladder N is required: N is how many committed words the" >&2
                      echo "ladder has, and 3 words and 5 words are different strategies" >&2
                      exit 1; }
[ -n "$TOPK" ] || { echo "-k K is required: the search is k words per level, so it only" >&2
                    echo "exists inside a beam, and K is part of what the total claims" >&2
                    exit 1; }

cd "$MATH" || exit 1

BIN=solver/secondexact
[ -x "$BIN" ] || { echo "no $BIN -- build it with 'sh build.sh' from math/solver/" >&2
                   exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix at data/local/patterns/patterns.npy" >&2
    echo "  Build it with 'python3 build_patterns.py' from math/ (~2s, 30 MB)." >&2
    exit 1; }

OUTDIR=data/shared/ladder
LOC=data/local/ladder

# --words: a STEM under data/shared/words, or a path -- the repo's convention
# (run-singles.sh resolves it the same way).
WLIST=""
if [ -n "$WORDS" ]; then
    case "$WORDS" in
        */*|*.txt) WLIST="$WORDS" ;;
        *)         WLIST="data/shared/words/$WORDS.txt" ;;
    esac
    [ -f "$WLIST" ] || { echo "--words: no such list: $WLIST" >&2; exit 1; }
fi

FLAGS="--ladder $LEVELS --topk $TOPK --report $REPORT"
[ -z "$WLIST" ]    || FLAGS="$FLAGS --words $WLIST"
[ -z "$PIN" ]      || FLAGS="$FLAGS --pin-thresholds $PIN"

# ASK THE BINARY WHAT THE RUN IS CALLED.  The depth and the pinning are the
# quantity, and the binary is the one place that knows how they are spelled --
# deriving the stem here would be that rule written a second time, in a second
# language, and the resume stamp is checked against it.
LABEL=$($BIN $FLAGS --print-label) || exit 1
STEM="$LABEL"
[ -z "$OPENER" ]  || STEM="${STEM}_${OPENER}"
[ -z "$OPENERS" ] || STEM="${STEM}_$(basename "$OPENERS" .txt)"
STEM="${STEM}_k${TOPK}"
[ -z "$LIMIT" ]   || STEM="${STEM}_limit${LIMIT}"
OUT="$OUTDIR/$STEM.csv"

[ -z "$OPENER" ]   || FLAGS="$FLAGS --opener $OPENER"
[ -z "$OPENERS" ]  || FLAGS="$FLAGS --openers $OPENERS"
[ -z "$LIMIT" ]    || FLAGS="$FLAGS --limit $LIMIT"
[ -z "$THREADS" ]  || FLAGS="$FLAGS --threads $THREADS"
[ -z "$MEMOBITS" ] || FLAGS="$FLAGS --memo-bits $MEMOBITS"

echo "ladder: $LEVELS committed words, one threshold each"
echo "  rule       guess d plays its word while the CUMULATIVE matched letters"
echo "             are BELOW that level's threshold; going over ENDS the ladder"
echo "             and every guess after it is a random consistent ANSWER"
echo "  openers    ${OPENER:-${OPENERS:-the $TOPK best by expected answers remaining}}${LIMIT:+ (first $LIMIT)}"
if [ -n "$WLIST" ]; then
    echo "  WORDS      every committed word -- the opener included -- comes from"
    echo "             $WLIST"
    echo "             ^ a DIFFERENT objective, not a setting: a strictly smaller"
    echo "               strategy space, so its expected is weakly WORSE and its"
    echo "               numbers never share a table with the 12972-word run."
    echo "             ^ the random tail still draws from the consistent ANSWERS;"
    echo "               that is the strategy's definition, not a pool."
else
    echo "  words      every committed word from the full 12972 guess list"
fi
echo "  follow-up  answer (a uniformly random consistent answer)"
if [ -n "$PIN" ]; then
    echo "  PINNED     thresholds $PIN -- not searched.  A DIFFERENT quantity from"
    echo "             the free run, which is why it has its own file."
else
    echo "  thresholds enumerated exactly (only the values that fire differently)"
fi
if [ -n "$OPENER" ] || [ -n "$OPENERS" ]; then
    # A NAMED opener is exempt from the root beam: the root is chosen, so K
    # restricts only the levels below it and the claim is about THAT opener.
    echo "  BEAM k=$TOPK    the $TOPK best words at every level below the named opener"
    echo "             ^ the root is yours, so this bounds THAT opener's price:"
    echo "               an UPPER BOUND on what the best ladder from it costs."
else
    echo "  BEAM k=$TOPK    the $TOPK best OPENERS, and the $TOPK best words at every level"
    echo "             ONE K governs both, as in every other solver here."
    echo "             ^ a SCREEN, not a proof: every total is an UPPER BOUND and"
    echo "               the winner is the best of the openers EXAMINED."
fi
echo "             ^ cost is about (3k)^($LEVELS-1) ladders per opener"
echo "  number     expected guesses OUTRIGHT -- never table it beside an"
echo "             optturns-family total, which is capped at 6"
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
guard_output ladder "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] ladder $STEM" | tee -a "$LOC/$STEM.log"

$BIN $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
