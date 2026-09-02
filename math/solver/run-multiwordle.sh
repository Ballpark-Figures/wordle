#!/bin/bash
# Simulate MULTIWORDLE games attached, with live output in this terminal.
#
#     bash solver/run-multiwordle.sh -k 4 -t 10000            # from math/, or anywhere
#     bash solver/run-multiwordle.sh -k 4 -t 10000 --seed 7
#     bash solver/run-multiwordle.sh -k 4 -t 10000 --openers "clint soare"
#     bash solver/run-multiwordle.sh -k 4 -t 10000 --openers-from PAIRS_CSV
#
# WHAT THIS MEASURES, precisely:
#
#   k hidden answers are drawn without replacement from the 2315 mystery words,
#   one per BOARD.  Every guess is played on every unsolved board at once.  A
#   fixed OPENING SEQUENCE of one or more words goes first, played BLIND in
#   order -- each of its words is played whatever the boards look like, and the
#   sequence stops early only if every board is already solved.  After that,
#   each turn takes the unsolved board with the FEWEST remaining candidates
#   (ties by board index) and guesses one of its candidates UNIFORMLY AT
#   RANDOM.  A board is solved only when its answer is
#   actually played -- a board narrowed to one word still costs the naming
#   guess -- and a word played for one board solves any other board it happens
#   to match.  The score is the TOTAL guesses until all k boards are solved.
#
#   The reported number is the MEAN of that over -t random games, with a
#   standard error, because this is a Monte Carlo estimate and not an exact
#   computation.  Two runs differing by less than a couple of SEs have not
#   measured a difference.
#
#   THERE IS NO GUESS CAP, and none is needed -- the targeted board shrinks
#   every turn, so the process terminates on its own.  So this is expected
#   guesses OUTRIGHT, not the "optimum subject to a k-guess guarantee" that
#   every optturns/hardturns/ansall number in this repo reports.  The two are
#   different quantities; do not put them in one table.
#
# THE OPENING IS AN INPUT, NOT A RESULT.  The default below is the top of the
# single-word SINGLETON ranking (tools/singletons.py) -- but that is a
# SINGLE-BOARD quantity, it optimises nothing about the k-board total, and it is
# not even unique (laten and rotan both score 41).  It is the strategy the video
# is currently exploring, chosen deliberately; change it and the result lands in
# its own file.
#
# THREE WAYS TO NAME THE OPENING, all landing in their own output file:
#
#   --opener WORD          one word; repeat the flag for more
#   --openers "A B"        the whole sequence in one argument
#   --openers-from FILE    the FIRST DATA ROW of a singletons ranking CSV, using
#                          every leading word column -- so the same flag gives a
#                          word, a pair, a triple or a quad, and the run records
#                          which file it came from.  Prefer this over retyping a
#                          result: the ranking stays the source of truth.
#
# THE RANKING BEHIND --openers-from IS NOT ALWAYS AN OPTIMUM.  run-singles.sh
# evaluates every word and every one of the 84,129,906 pairs, so those two heads
# are exact; TRIPLES AND QUADS ARE GREEDY SCREENS and their heads are "best of
# those screened", never the best opening.  Nothing here checks that, so do not
# describe a triple/quad run as using "the best" opening.
#
# USE THIS RATHER THAN CALLING tools/multiwordle_sim.py DIRECTLY.  It sets --out
# so the games outlive the terminal, names the file after every parameter that
# defines the experiment, and tees a log.  The script refuses to start without
# --out and --opener for the same reason.
#
# Each (k, opener, t, seed) is a different sample and gets its OWN file; re-running
# the same four reproduces that file exactly.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=""
T=""
SEED=0
# The user's current choice (2026-09-02), rank 1 by singletons over the 2315.
# The first --opener/--openers/--openers-from REPLACES it; further --opener
# flags then append, so "--opener a --opener b" is the pair a b, not just b.
OPENING=laten
DEFAULTED=1
SOURCE=""
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--boards)  K="$2";        shift 2 ;;
        -t|--trials)  T="$2";        shift 2 ;;
        --seed)       SEED="$2";     shift 2 ;;
        --opener)     [ "$DEFAULTED" = 1 ] && OPENING=""
                      DEFAULTED=0
                      OPENING="${OPENING:+$OPENING }$2"; shift 2 ;;
        --openers)    DEFAULTED=0; OPENING="$2";  shift 2 ;;
        --openers-from) DEFAULTED=0; SOURCE="$2"; OPENING=""; shift 2 ;;
        --progress)   PROGRESS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$K" in
    ''|*[!0-9]*|0) echo "-k must be a positive number (how many boards)" >&2; exit 1 ;;
esac
case "$T" in
    ''|*[!0-9]*|0) echo "-t must be a positive number (how many games)" >&2; exit 1 ;;
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

if [ -n "$SOURCE" ] && [ -n "$OPENING" ]; then
    echo "--openers-from cannot be combined with --opener/--openers" >&2; exit 1
fi
if [ -n "$SOURCE" ]; then
    [ -f "$SOURCE" ] || { echo "no such ranking file: $SOURCE" >&2; exit 1; }
    case "$SOURCE" in
        *[[:space:]]*) echo "--openers-from path must not contain spaces" >&2; exit 1 ;;
    esac
    # Resolve it HERE so the output filename can name the opening it used; the
    # simulator re-reads the same first data row and records the source path.
    OPENING=$(awk -F, '!/^#/ && NF { if (h == "") { for (i = 1; i <= NF; i++) if ($i ~ /^word/) c = c " " i; h = 1; next } n = split(c, ix, " "); for (i = 1; i <= n; i++) printf "%s%s", (i > 1 ? " " : ""), $(ix[i]); print ""; exit }' "$SOURCE")
    [ -n "$OPENING" ] || { echo "could not read an opening from $SOURCE" >&2; exit 1; }
    echo "opening from $SOURCE: $OPENING"
fi
[ -n "$OPENING" ] || { echo "no opening words given" >&2; exit 1; }

OUTDIR=data/shared/multiwordle
LOC=data/local/multiwordle
# words joined by '-', so a single-word run keeps the filename it always had
STEM="k${K}_$(echo "$OPENING" | tr ' ' '-')_t${T}_s${SEED}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output multiwordle_sim.py "$OUT" || exit 1

# One --opener per word: FLAGS is word-split unquoted below, so a single
# --openers "a b" would arrive as two arguments and be rejected.
FLAGS="-k $K -t $T --seed $SEED --out $OUT"
if [ -n "$SOURCE" ]; then
    FLAGS="$FLAGS --openers-from $SOURCE"
else
    for w in $OPENING; do FLAGS="$FLAGS --opener $w"; done
fi
[ -n "$PROGRESS" ] && FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] multiwordle sim $STEM" \
    | tee -a "$LOC/sim_$STEM.log"

"$PY" -u tools/multiwordle_sim.py $FLAGS 2>&1 | tee -a "$LOC/sim_$STEM.log"
