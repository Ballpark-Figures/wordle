#!/bin/bash
# Simulate FOXIMAX games attached, with live output in this terminal.
#
#     bash solver/run-foximax.sh -t 1000               # from math/, or anywhere
#     bash solver/run-foximax.sh -t 10000 --seed 7
#     bash solver/run-foximax.sh -t 10000 --words guess
#
# WHAT THIS MEASURES, precisely:
#
#   One hidden word starts on the grid.  Each turn guesses a LETTER, never a
#   word.  The letter HITS if it appears in at least one word in play, and its
#   positions are then revealed in every word at once; it MISSES if it appears
#   in none, and a miss ADDS a new word to the grid, drawn from the same list.
#   A newcomer arrives with every letter guessed so far already shown in it,
#   hits and earlier misses alike.  The game ends when every word in play is
#   fully revealed, and the score is the NUMBER OF WORDS -- 1 + the misses.
#
#   The strategy is GREEDY and one step deep: guess the unguessed letter most
#   likely to appear in at least one word in play, each board taken as uniform
#   over its own remaining candidates and the boards taken as independent, ties
#   broken alphabetically.  Nothing searches; this is a heuristic being
#   measured, not an optimum being computed.  math/foximax.py states both the
#   game and the strategy exactly -- read it before quoting any number.
#
#   THE REAL SITE CAPS THE GRID AT EIGHT WORDS AND THAT IS NOT MODELLED: play
#   always runs to completion, so no game here is a loss and the reported mean
#   is an UNCONSTRAINED expected word count.  It is therefore not comparable
#   with any optturns/hardturns/ansall total, which are all optima subject to a
#   guarantee; do not put them in one table.
#
#   THE WORD LIST IS OURS, NOT FOXIMAX'S -- the 2315 NYT answers, the list
#   every other sweep in this video uses.  The site's list is unknown to us and
#   its daily puzzles are not random draws, so a number here describes this
#   game on this list, not foximax.com.
#
#   The reported number is the MEAN over -t random games, with a standard
#   error, because this is a Monte Carlo estimate and not an exact computation.
#   Two runs differing by less than a couple of SEs have not measured a
#   difference.
#
# USE THIS RATHER THAN CALLING tools/foximax_sim.py DIRECTLY.  It sets --out so
# the games outlive the terminal, names the file after every parameter that
# defines the experiment, and tees a log.  The script refuses to start without
# --out for the same reason.
#
# Each (word list, t, seed) is a different sample and gets its OWN file;
# re-running the same three reproduces that file exactly.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

T=""
SEED=0
WORDS=mystery
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -t|--trials) T="$2";        shift 2 ;;
        --seed)      SEED="$2";     shift 2 ;;
        --words)     WORDS="$2";    shift 2 ;;
        --progress)  PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (how many games)" >&2; exit 1 ;;
esac
case "$SEED" in
    ''|*[!0-9]*) echo "--seed must be a non-negative number" >&2; exit 1 ;;
esac
case "$WORDS" in
    *[[:space:]]*) echo "--words path must not contain spaces" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

case "$WORDS" in
    mystery|guess) TAG="" ;;
    *) [ -f "$WORDS" ] || { echo "no such word list: $WORDS" >&2; exit 1; }
       TAG="_$(basename "$WORDS" | sed 's/\.[^.]*$//')" ;;
esac
# the default list is the one every other sweep uses, so it stays unlabelled
[ "$WORDS" = guess ] && TAG="_guess"

OUTDIR=data/shared/foximax
LOC=data/local/foximax
STEM="t${T}_s${SEED}${TAG}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$MATH/solver/_guard.sh"
guard_output foximax_sim.py "$OUT" || exit 1

FLAGS="-t $T --seed $SEED --words $WORDS --out $OUT"
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] foximax sim $STEM" \
    | tee -a "$LOC/sim_$STEM.log"

"$PY" -u tools/foximax_sim.py $FLAGS 2>&1 | tee -a "$LOC/sim_$STEM.log"
