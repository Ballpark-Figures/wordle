#!/bin/bash
# Sweep every OPENER through single-board wordle games, attached, live output.
#
#     # STAGE 1: a wide screen, every one of the 12972 openers, 100 games each
#     bash solver/run-wordle-sweep.sh --fallback answer -t 100          # from math/
#     bash solver/run-wordle-sweep.sh --fallback guess  -t 100
#
#     # STAGE 2: re-run only the words the screen left standing, at a FRESH seed
#     bash solver/run-wordle-sweep.sh --fallback answer -t 1000 --seed 1 \
#         --shortlist-from data/shared/wordlesim/sweep_answer_t100_s0_guess.csv
#
# WHAT THIS MEASURES:
#
#   Every word of the list opens -t games.  The word is played on turn 1 and the
#   FOLLOW-UP plays the rest -- a random word still consistent with every reply,
#   drawn from the 2315 answers (--fallback answer) or the 12972 legal guesses
#   (--fallback guess).  Each word gets a mean number of guesses AND a win rate
#   (the fraction of games finished within six), each with a standard error.
#
#   THE FOLLOW-UP IS PART OF THE QUESTION.  "Which opener is best" has a different
#   answer under each, because the opener is feeding a different player.  So it is
#   required, it is in the filename, and the two sweeps are two different screens.
#   The hidden answer is drawn from the 2315 either way.
#
#   COMMON RANDOM NUMBERS: every opener faces the IDENTICAL -t answers (the draw
#   stream is re-seeded per word and kept separate from the follow-up's pick
#   stream), so differences between words are far less noisy than their individual
#   standard errors suggest.  A sweep cell and a run-wordle-sim.sh run at the same
#   seed are therefore different samples and will not match to the last digit.
#
# THE HEAD OF A SWEEP IS A SHORTLIST, NOT A WINNER.  With 12972 words at -t games
# each, the best-looking mean belongs to whichever word drew the kindest sample,
# and at t=100 that noise dwarfs one word's standard error.  The sound use is
# staged: screen wide and cheap, cut a generous shortlist, re-run the survivors
# larger and at a fresh seed, repeat.  A word leading every stage is a finding.
#
#   --shortlist-from SWEEP.csv does the next stage in one command: it cuts a word
#   list from that sweep (--se N standard errors of the best word's, DEFAULT 5;
#   or --shortlist-top N) and sweeps only those words.  USE A FRESH --seed WITH
#   IT: the draw stream is seeded per word, so stage 2 at the same seed replays
#   stage 1's games as its first -t, re-using the sample that chose the shortlist.
#   The wrapper warns.  It REFUSES a shortlist cut from a sweep run under the
#   OTHER follow-up, which would screen one player and test another.
#
# TWO NUMBERS, SO TWO POSSIBLE SHORTLISTS.  --shortlist-value mean (the default,
# lower is better) or win_rate (higher is better) says which column the cut ranks
# on; they need not agree.  It lands in the shortlist's name, so a stage-2 file
# always records which screen chose its words.
#
# USE THIS RATHER THAN CALLING tools/wordle_sweep.py DIRECTLY.  It sets --out so
# the rows outlive the terminal, names the file after every parameter that defines
# the sweep, and tees a log.  The sweep is RESUMABLE per word, so a Ctrl-C costs
# at most the word in flight and re-running the same command picks up where it
# stopped.
#
# WHY THE DEFAULT CUT IS 5 STANDARD ERRORS (user's call, 2026-09-08).  It started
# at 10, multiwordle's default, and MEASURED on the first pass that was too wide to
# screen: at t=100 a word's standard error is ~0.10, so ten of them span a full
# guess and the cut kept 12367 of 12972 words under the answer follow-up (12911
# under guess).  5 SE keeps the net generous while actually narrowing the field.
# The cut is in every filename, so stages cut differently can never be confused.
# NOTE this is the WORDLE wrapper's default; multiwordle's wrapper keeps its own
# 10, and tools/sweep_shortlist.py -- shared by both -- is unchanged.  Each wrapper
# carries a default a human reads, rather than a shared one that moves under them.
#
# Each (follow-up, t, seed, word list) is a different sweep and gets its own file.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

T=""
FALLBACK=""
SEED=0
WORDS="guess"
LIMIT=""
WIN=6
PROGRESS=""
SHORTFROM=""
# 5 standard errors: generous, but narrow enough to screen.  See the note above.
SHORTSE=5
SHORTTOP=""
SHORTVALUE="mean"

while [ $# -gt 0 ]; do
    case "$1" in
        -t|--trials)        T="$2";          shift 2 ;;
        --fallback)         FALLBACK="$2";   shift 2 ;;
        --seed)             SEED="$2";       shift 2 ;;
        --words)            WORDS="$2";      shift 2 ;;
        --limit)            LIMIT="$2";      shift 2 ;;
        --win-within)       WIN="$2";        shift 2 ;;
        --progress)         PROGRESS="$2";   shift 2 ;;
        --shortlist-from)   SHORTFROM="$2";  shift 2 ;;
        --se)               SHORTSE="$2";    shift 2 ;;
        --shortlist-top)    SHORTTOP="$2";   shift 2 ;;
        --shortlist-value)  SHORTVALUE="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (games per word)" >&2; exit 1 ;;
esac
case "$FALLBACK" in
    answer|guess) ;;
    '') echo "--fallback is required: 'answer' or 'guess', which random word the" >&2
        echo "  opener hands the rest of the game to.  It is part of the question." >&2
        exit 1 ;;
    *) echo "--fallback must be 'answer' or 'guess'" >&2; exit 1 ;;
esac
case "$SEED" in
    ''|*[!0-9]*) echo "--seed must be a non-negative number" >&2; exit 1 ;;
esac
case "$SHORTVALUE" in
    mean|win_rate) ;;
    *) echo "--shortlist-value must be 'mean' or 'win_rate'" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }
if [ "$FALLBACK" = guess ]; then
    [ -f data/local/patterns/patterns_full.npy ] || {
        echo "the guess follow-up needs the square guess x guess matrix." >&2
        echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
        exit 1; }
fi

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
mkdir -p "$OUTDIR" "$LOC"

if [ -n "$SHORTFROM" ]; then
    [ -f "$SHORTFROM" ] || { echo "no such sweep: $SHORTFROM" >&2; exit 1; }
    [ "$WORDS" = "guess" ] || {
        echo "--shortlist-from replaces --words; pass only one" >&2; exit 1; }
    SRCSTEM=$(basename "$SHORTFROM" .csv)
    # A screen run under one follow-up cannot choose the words for the other:
    # the opener is feeding a different player, so the ranking does not carry.
    SRCFB=$(sed -n 's/^# wordle opener sweep:.*follow-up \([a-z]*\),.*/\1/p' "$SHORTFROM" | head -1)
    if [ -n "$SRCFB" ] && [ "$SRCFB" != "$FALLBACK" ]; then
        echo "REFUSING: $SRCSTEM was swept under the '$SRCFB' follow-up, but this" >&2
        echo "  run uses '$FALLBACK'.  That would screen one player and test" >&2
        echo "  another; the ranking does not carry between them." >&2
        exit 1
    fi
    CUTNAME="se${SHORTSE}"
    CUT="--se ${SHORTSE}"
    if [ -n "$SHORTTOP" ]; then
        CUT="--top $SHORTTOP"; CUTNAME="top$SHORTTOP"
    fi
    if [ "$SHORTVALUE" != mean ]; then
        CUT="$CUT --value $SHORTVALUE --maximise"
        CUTNAME="${CUTNAME}-win"
    fi
    WORDS="$OUTDIR/shortlist_${SRCSTEM#sweep_}_$CUTNAME.txt"
    "$PY" tools/sweep_shortlist.py --from "$SHORTFROM" $CUT --out "$WORDS" \
        || exit 1
    # A later stage at the earlier seed replays the games that chose the
    # shortlist.  Loud, not fatal: it is a judgement about what the run means.
    SRCSEED=$(echo "$SRCSTEM" | sed -n 's/.*_s\([0-9][0-9]*\)_.*/\1/p')
    if [ "$SRCSEED" = "$SEED" ]; then
        echo "WARNING: this stage is using seed $SEED, the same seed as $SRCSTEM." >&2
        echo "  The draw stream is seeded per word, so its first $T games REPLAY" >&2
        echo "  that stage's games -- re-using the very sample that chose the" >&2
        echo "  shortlist.  Pass a fresh --seed for an independent test." >&2
    fi
fi

STEM="sweep_${FALLBACK}_t${T}_s${SEED}_$(basename "$WORDS" .txt)"
[ -n "$LIMIT" ] && STEM="${STEM}_lim${LIMIT}"
[ "$WIN" = 6 ] || STEM="${STEM}_w${WIN}"
OUT="$OUTDIR/$STEM.csv"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wordle_sweep.py "$OUT" || exit 1

FLAGS="-t $T --fallback $FALLBACK --seed $SEED --words $WORDS --win-within $WIN --out $OUT"
[ -n "$LIMIT" ] && FLAGS="$FLAGS --limit $LIMIT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle opener sweep $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/wordle_sweep.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
