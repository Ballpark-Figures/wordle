#!/bin/bash
# Simulate single-board WORDLE games attached, with live output in this terminal.
#
#     bash solver/run-wordle-sim.sh --strategy random -t 10000     # from math/, or anywhere
#     bash solver/run-wordle-sim.sh --strategy random -t 10000 --seed 7
#
# WHAT THIS MEASURES, precisely:
#
#   One hidden answer is drawn uniformly from the 2315 mystery words.  The named
#   STRATEGY plays guesses (any of the 12972 legal words) until the answer is
#   actually played -- narrowing the candidates to one word does not end the
#   game, the naming guess still costs a turn.  The score is the number of
#   guesses.  Two numbers come out: the MEAN score, and the WIN RATE, the
#   fraction of games that finished within six guesses.
#
#   PLAY IS NEVER TRUNCATED.  A game that has not found the word by guess six
#   keeps going until it does, so the mean is expected guesses OUTRIGHT -- not
#   the "optimum subject to a 6-guess guarantee" that every optturns / hardturns
#   / ansall number in this repo reports.  The two are different quantities; do
#   not put them in one table.  Six enters only as the threshold the win rate is
#   read off, and --win-within moves it.
#
#   Both reported numbers are Monte Carlo estimates over -t random games and
#   come with a standard error.  Two runs differing by less than a couple of SEs
#   have not measured a difference.
#
# THE STRATEGY IS AN INPUT, NOT A RESULT, and there is NO DEFAULT -- naming it is
# how a result file says which experiment produced it.  The strategies live in
# math/wordlesim.py's registry; `--strategy list` prints them.  Today:
#
#   random    guess a word drawn UNIFORMLY AT RANDOM from the answers still
#             consistent with every reply so far, from the first guess to the
#             last.  Nothing is hardcoded and no opener is an input: on turn one
#             every answer is alive, so the opening word is itself a uniform draw.
#             It is the shared TAIL every other strategy here falls through to
#             once its own part is over, so it is also the baseline they are
#             measured against.
#
# USE THIS RATHER THAN CALLING tools/wordle_sim.py DIRECTLY.  It sets --out so the
# games outlive the terminal, names the file after every parameter that defines
# the experiment, and tees a log.  The script refuses to start without --out and
# --strategy for the same reason.
#
# Each (strategy, t, seed) is a different sample and gets its OWN file; re-running
# the same three reproduces that file exactly.  A --win-within other than 6 is a
# different reported quantity, so it lands in its own file too.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STRATEGY=""
SARGS=""
T=""
SEED=0
WIN=6
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -s|--strategy)     STRATEGY="$2";                       shift 2 ;;
        --strategy-arg)    SARGS="${SARGS:+$SARGS }$2";         shift 2 ;;
        -t|--trials)       T="$2";                              shift 2 ;;
        --seed)            SEED="$2";                           shift 2 ;;
        --win-within)      WIN="$2";                            shift 2 ;;
        --progress)        PROGRESS="$2";                       shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

if [ "$STRATEGY" = "list" ]; then
    "$PY" -c 'import sys; sys.path.insert(0, "."); import wordlesim; print("\n".join(sorted(wordlesim.STRATEGIES)))'
    exit 0
fi
[ -n "$STRATEGY" ] || {
    echo "--strategy is required (it names the experiment); '--strategy list' shows them" >&2
    exit 1; }
case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (how many games)" >&2; exit 1 ;;
esac
case "$SEED" in
    ''|*[!0-9]*) echo "--seed must be a non-negative number" >&2; exit 1 ;;
esac
case "$WIN" in
    ''|*[!0-9]*|0) echo "--win-within must be a positive number of guesses" >&2; exit 1 ;;
esac

[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
# strategy args join the name with '-', so a plain run keeps a clean stem
STEM="$(echo "$STRATEGY $SARGS" | sed 's/  *$//' | tr ' ' '-')_t${T}_s${SEED}"
[ "$WIN" = 6 ] || STEM="${STEM}_w${WIN}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wordle_sim.py "$OUT" || exit 1

FLAGS="--strategy $STRATEGY -t $T --seed $SEED --win-within $WIN --out $OUT"
for a in $SARGS; do FLAGS="$FLAGS --strategy-arg $a"; done
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle sim $STEM" \
    | tee -a "$LOC/sim_$STEM.log"

"$PY" -u tools/wordle_sim.py $FLAGS 2>&1 | tee -a "$LOC/sim_$STEM.log"
