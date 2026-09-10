#!/bin/bash
# RACE every opener against every other one, attached, with live output in this
# terminal.  One resumable process in place of the staged cascade.
#
#     bash solver/run-wordle-race.sh --fallback answer          # from math/, or anywhere
#     bash solver/run-wordle-race.sh --fallback answer \
#         --second-from data/shared/secondword/second_guess_g3.csv
#     bash solver/run-wordle-race.sh --fallback guess --words mystery \
#         --second-from data/shared/secondword/second_mystery_g3.csv
#
# WHAT IT REPLACES.  The cascade -- sweep every word at 100 games, cut to those
# within 5 standard errors of the best, re-sweep the survivors at the next rung
# with a fresh seed, repeat, then settle the finalists with a paired comparison --
# was one command and one file per pass, with the ladder and the seed advanced by
# hand.  This is the same statistics as ONE process: every opener starts on 100
# games, anything more than --sigma PAIRED standard errors behind the leader is
# dropped the moment that becomes true, and the survivors keep playing on a
# doubling schedule.  Ctrl-C whenever you like and re-run the same command; it
# checkpoints continuously and resumes where it stopped.
#
# PAIRED FROM THE FIRST GAME, which is why it can cut this early: every opener
# plays the identical games AND the identical coin flips, so the error on the
# DIFFERENCE is far smaller than either opener's own.  Both are reported; the
# paired one decides.  A race cell will therefore NOT match a sweep cell at the
# same seed -- the coupling is a different sampler, deliberately.
#
# IT IS STILL A SCREEN.  A race eliminates against a MOVING leader, so an opener
# that draws a lucky first hundred games can push a better one out.  The head of
# a race is the best of the openers ENTERED, judged on the games actually played
# -- never "the best opener".
#
# --fallback IS REQUIRED and is part of the question: `answer` hands the rest of
# the game to a random compatible ANSWER, `guess` to a random compatible LEGAL
# WORD.  Two different players, two different races, and it is in the filename.
#
# --second-from TABLE is the other half of the strategy.  With it, every opener
# plays its OWN predetermined second word whenever the reply shows enough greys
# (math/secondword.py; build the table with solver/run-second-word.sh).  Without
# it the opener is played blind and the follow-up takes over immediately.  The
# threshold comes off the table's own stamp and lands in the filename, and the
# race REFUSES a table with no row for an opener in the field -- which is what
# stops the answers-only table being raced over the 12972.
#
# IT RANKS ON THE MEAN.  The win rate is reported per opener but nothing cuts on
# it; the sweep's parallel --rank win_rate has no analogue here and is left out
# rather than half-built.
#
# THE TAIL IS THE EXPENSIVE PART, not the field.  The first block is every opener
# x 100 games and takes a couple of minutes; the field then collapses, and what
# remains is two or three openers playing millions of games until one is 5 sigma
# clear.  --max-games N bounds that deliberately, and stopping early is fine: the
# standings are a real ranking of whatever has been played.
#
# Output: standings + eliminations under data/shared/wordlesim/race_*, checkpoint
# and log under data/local/wordlesim/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FALLBACK=""
WORDS="guess"
OPENFROM=""
TOP=""
SECONDFROM=""
SEED=0
SIGMA=5
BLOCK=100
GROWTH=2
MAXGAMES=""
PAIRAT=""
CHUNK=""
REPORT=""
DRYRUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --fallback)       FALLBACK="$2";   shift 2 ;;
        --words)          WORDS="$2";      shift 2 ;;
        --openings-from)  OPENFROM="$2";   shift 2 ;;
        --top)            TOP="$2";        shift 2 ;;
        --second-from)    SECONDFROM="$2"; shift 2 ;;
        --seed)           SEED="$2";       shift 2 ;;
        --sigma)          SIGMA="$2";      shift 2 ;;
        --block)          BLOCK="$2";      shift 2 ;;
        --growth)         GROWTH="$2";     shift 2 ;;
        --max-games)      MAXGAMES="$2";   shift 2 ;;
        --pair-at)        PAIRAT="$2";     shift 2 ;;
        --chunk)          CHUNK="$2";      shift 2 ;;
        --report)         REPORT="$2";     shift 2 ;;
        --dry-run)        DRYRUN=1;        shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

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

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }
# The guess follow-up keeps its own live set over the 12972, which needs the
# SQUARE matrix -- a separate artifact, gitignored like the rest of data/local/.
if [ "$FALLBACK" = guess ]; then
    [ -f data/local/patterns/patterns_full.npy ] || {
        echo "the 'guess' follow-up needs the square guess x guess matrix." >&2
        echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
        exit 1; }
fi
if [ -n "$SECONDFROM" ]; then
    [ -f "$SECONDFROM" ] || {
        echo "no such second-word table: $SECONDFROM" >&2
        echo "  Build one: bash solver/run-second-word.sh" >&2
        exit 1; }
fi

FLAGS="--fallback $FALLBACK --seed $SEED --sigma $SIGMA --block $BLOCK --growth $GROWTH"
[ -z "$OPENFROM" ]   || FLAGS="$FLAGS --openings-from $OPENFROM"
[ -n "$OPENFROM" ]   || FLAGS="$FLAGS --words $WORDS"
[ -z "$TOP" ]        || FLAGS="$FLAGS --top $TOP"
[ -z "$SECONDFROM" ] || FLAGS="$FLAGS --second-from $SECONDFROM"
[ -z "$MAXGAMES" ]   || FLAGS="$FLAGS --max-games $MAXGAMES"
[ -z "$PAIRAT" ]     || FLAGS="$FLAGS --pair-at $PAIRAT"
[ -z "$CHUNK" ]      || FLAGS="$FLAGS --chunk $CHUNK"
[ -z "$REPORT" ]     || FLAGS="$FLAGS --report $REPORT"

# ASK THE TOOL WHAT THE FILE IS CALLED, rather than re-deriving the name in
# shell: stem_for() is the one owner, and it is the only thing that knows the
# table's threshold without the wrapper parsing the table itself.
RESOLVED=$("$PY" tools/wordle_race.py $FLAGS --print-stem) || exit 1
STEM=$(echo "$RESOLVED" | head -1)
NOPEN=$(echo "$RESOLVED" | tail -1)

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
OUT="$OUTDIR/$STEM.csv"

echo "wordle opener race"
echo "  openers    $NOPEN from ${OPENFROM:-$WORDS}${TOP:+ (top $TOP)}"
echo "  follow-up  $FALLBACK"
[ -z "$SECONDFROM" ] && echo "  rule       blind opener, then the follow-up" \
                     || echo "  rule       gray-second, table $SECONDFROM"
echo "  cut        $SIGMA paired sigma; blocks of $BLOCK then x$GROWTH; seed $SEED"
echo "  out        $OUT"
echo "  log        $LOC/$STEM.log"
[ -f "$LOC/$STEM.npz" ] && echo "  RESUMING from $LOC/$STEM.npz"

if [ "$DRYRUN" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $PY -u tools/wordle_race.py $FLAGS --out $OUT"
    exit 0
fi

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is by
# process NAME, which is "python" here, so only the output-file half applies --
# and that is the half that matters: two races appending to one checkpoint would
# each resume from the other's state.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wordle_race.py "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle opener race $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/wordle_race.py $FLAGS --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
