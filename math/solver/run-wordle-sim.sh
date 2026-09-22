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
# A STRATEGY IS A RULE PLUS A FOLLOW-UP, and BOTH are inputs with NO DEFAULT --
# naming them is how a result file says which experiment produced it.  The rule is
# what the strategy does while it has something to say; the FOLLOW-UP fills in
# every position the rule has no rule for, and the two available are:
#
#   --fallback answer   a word drawn UNIFORMLY AT RANDOM from the ANSWERS still
#                       consistent with every reply (the 2315 mystery words)
#   --fallback guess    the same draw from the LEGAL GUESSES still consistent with
#                       them (the 12972 typeable words).  NEEDS the SQUARE guess x
#                       guess matrix: build it once with
#                       'python3 build_patterns.py --full' (~18s, 168 MB).
#
# They are different strategies with different numbers, so the follow-up is part
# of the run's identity and lands in the filename.  THE HIDDEN ANSWER IS DRAWN
# FROM THE 2315 EITHER WAY -- the pool is the STRATEGY's, never the GAME's -- so
# two runs differing only in their follow-up are directly comparable.
#
# The strategies live in math/wordlesim.py's registry; `--strategy list` prints
# them.  The BASELINES are the same EMPTY rule under each follow-up -- so each
# PINS its own and takes no --fallback:
#
#   random         no rule: the ANSWER follow-up plays the whole game.  Nothing is
#                  hardcoded and no opener is an input -- on turn one every answer
#                  is alive, so the opening word is itself a uniform draw.
#
#   random-guess   no rule: the GUESS follow-up plays the whole game.  It plays
#                  words that can never be the answer (10657 of the 12972 are not
#                  mystery words); that is the point, it is what a player without
#                  the curated answer list can do.
#
#   random-custom  no rule: the CUSTOM follow-up (words/custom.txt, 4282) plays
#                  it -- a player who knows ordinary English but not the curated
#                  answer list.  A THIRD quantity, not an interpolation.
#
# One more strategy pins a follow-up, but because of what it draws FROM rather
# than because it has no rule of its own:
#
#   random-blind   the FEEDBACK-BLIND baseline (2026-09-22).  A uniform draw from
#                  ALL 2315 answers every turn -- consistent with the replies or
#                  not, and WITH REPLACEMENT, so a word can be played twice --
#                  until exactly one candidate is left, which it then names.  The
#                  companion to `random`: same pool, same game, and the only
#                  difference is that `random` draws from the answers still ALIVE.
#                  Its rule answers every turn, so the follow-up never fires and
#                  --fallback is refused.  NB it still LEARNS -- an inconsistent
#                  guess is scored against the true answer like any other, so its
#                  reply narrows the candidates; it ignores the board when
#                  CHOOSING, which is not the same as getting no information.
#
# A strategy that DOES have a rule takes --fallback to say which of the two fills
# in the rest; the flag is required there, and refused for the two above, whose
# names already say it.  Those with rules today:
#
#   opener         one fixed word, then the follow-up.  --strategy-arg WORD
#   opening        several words played BLIND in order, then the follow-up
#   gray-second    an opener, then a word committed to IN ADVANCE for that opener
#                  -- but only when the opener's reply shows enough GREY tiles;
#                  otherwise the follow-up takes over there too.  Two arguments:
#                  --strategy-arg WORD --strategy-arg TABLE.csv, the table built
#                  by solver/run-second-word.sh (math/secondword.py states what
#                  it minimises).  Sweep it with run-wordle-sweep.sh
#                  --second-from TABLE.csv.
#
# USE THIS RATHER THAN CALLING tools/wordle_sim.py DIRECTLY.  It sets --out so the
# games outlive the terminal, names the file after every parameter that defines
# the experiment, and tees a log.  The script refuses to start without --out and
# --strategy for the same reason.
#
# Each (strategy, follow-up, t, seed) is a different sample and gets its OWN file;
# re-running the same four reproduces that file exactly.  The follow-up appears in
# the stem only when the flag supplied it, so the two baselines keep the plain
# names their own registry entries already pin.  A --win-within other than 6 is a
# different reported quantity, so it lands in its own file too.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STRATEGY=""
FALLBACK=""
SARGS=""
T=""
SEED=0
WIN=6
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -s|--strategy)     STRATEGY="$2";                       shift 2 ;;
        --fallback)        FALLBACK="$2";                       shift 2 ;;
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
# A strategy drawing from the whole guess list needs the SQUARE matrix, which is
# a separate artifact and gitignored like the rest of data/local/.
case "$FALLBACK" in
    ''|answer|guess|custom) ;;
    *) echo "--fallback must be 'answer', 'guess' or 'custom' (which random word" >&2
       echo "  fills in wherever the strategy's own rule declines)" >&2; exit 1 ;;
esac
# Either the strategy's own name or an explicit --fallback can put the guess-list
# follow-up in play, and it needs the SQUARE matrix -- a separate artifact,
# gitignored like the rest of data/local/.
case "$STRATEGY $FALLBACK" in
    *random-guess*|*guess|*custom)
        [ -f data/local/patterns/patterns_full.npy ] || {
            echo "the $FALLBACK follow-up needs the square guess x guess matrix." >&2
            echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
            exit 1; } ;;
esac

# Resolve the strategy BEFORE creating a log or a CSV, so a run that will be
# refused leaves nothing behind.  The registry stays the one place that decides:
# this just asks it, and prints the follow-up it settled on.
RESOLVED=$("$PY" tools/wordle_sim.py --strategy "$STRATEGY" ${FALLBACK:+--fallback $FALLBACK} $(for a in $SARGS; do echo "--strategy-arg $a"; done) --resolve) || exit 1
echo "strategy $STRATEGY${SARGS:+ $SARGS}, follow-up $RESOLVED"

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
# strategy args join the name with '-', so a plain run keeps a clean stem.
# AN ARGUMENT THAT IS A PATH CONTRIBUTES ITS BASENAME, and that is not cosmetic:
# a strategy taking a file (gray-second's second-word table) put the whole path
# in the stem, and since the path is absolute the "filename" then contained
# slashes -- so the run silently created a directory tree under data/shared/
# wordlesim/ and wrote the CSV at the bottom of it.  Which table it was still
# has to show, hence the basename rather than dropping it.
STEMARGS=""
for a in $SARGS; do
    case "$a" in
        */*) a=$(basename "$a"); a="${a%.csv}" ;;
    esac
    STEMARGS="$STEMARGS $a"
done
STEM="$(echo "$STRATEGY$STEMARGS $FALLBACK" | sed 's/  *$//' | tr ' ' '-')_t${T}_s${SEED}"
[ "$WIN" = 6 ] || STEM="${STEM}_w${WIN}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wordle_sim.py "$OUT" || exit 1

FLAGS="--strategy $STRATEGY -t $T --seed $SEED --win-within $WIN --out $OUT"
[ -n "$FALLBACK" ] && FLAGS="$FLAGS --fallback $FALLBACK"
for a in $SARGS; do FLAGS="$FLAGS --strategy-arg $a"; done
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle sim $STEM" \
    | tee -a "$LOC/sim_$STEM.log"

"$PY" -u tools/wordle_sim.py $FLAGS 2>&1 | tee -a "$LOC/sim_$STEM.log"
