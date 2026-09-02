#!/bin/bash
# Simulate MULTIWORDLE games attached, with live output in this terminal.
#
#     bash solver/run-multiwordle.sh -k 4 -t 10000            # from math/, or anywhere
#     bash solver/run-multiwordle.sh -k 4 -t 10000 -n 2        # open with the top PAIR
#     bash solver/run-multiwordle.sh -k 4 -t 10000 -n 3 --seed 7
#     bash solver/run-multiwordle.sh -k 4 -t 10000 --openers "clint soare"
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
# FOUR WAYS TO NAME THE OPENING, all landing in their own output file:
#
#   -n N                   the head of the N-word singletons ranking.  DEFAULT 1,
#                          so a plain run opens with the top single word and no
#                          word is hardcoded anywhere -- the ranking is the source
#                          of truth, and the words it resolved to are echoed and
#                          land in the output filename.
#   --opener WORD          one word; repeat the flag for more
#   --openers "A B"        the whole sequence in one argument
#   --openers-from FILE    the FIRST DATA ROW of any singletons ranking CSV, using
#                          every leading word column.  This is what -n resolves to;
#                          use it directly when a size has several rankings and
#                          you must pick one.
#
# WHICH FILE -n READS.  1, 2 and 3 have one canonical ranking each
# (guess_/pair_/triple_singletons.csv).  FOUR AND UP DO NOT: every quad and quint
# run is written under a name recording its own restriction (--disjoint,
# --min-letters, exhaustive vs truncated), and those are DIFFERENT QUESTIONS, not
# variants of one.  So -n 4 refuses and lists what is on disk rather than guessing;
# pick one with --openers-from.
#
# THE RANKING IS NOT ALWAYS AN OPTIMUM.  run-singles.sh evaluates every word and
# every one of the 84,129,906 pairs, so -n 1 and -n 2 are exact heads; TRIPLES AND
# QUADS ARE GREEDY SCREENS and their heads are "best of those screened", never the
# best opening.  Nothing here checks that, so do not describe a triple/quad run as
# using "the best" opening.
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
# How many words the opening uses, resolved against the singletons rankings.
# No word is defaulted here: -n 1 reads the head of guess_singletons.csv.
NOPEN=1
OPENING=""
SOURCE=""
EXPLICIT=0
PROGRESS=""

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--boards)  K="$2";        shift 2 ;;
        -t|--trials)  T="$2";        shift 2 ;;
        --seed)       SEED="$2";     shift 2 ;;
        -n|--num-openers) NOPEN="$2"; shift 2 ;;
        --opener)     EXPLICIT=1; OPENING="${OPENING:+$OPENING }$2"; shift 2 ;;
        --openers)    EXPLICIT=1; OPENING="$2";  shift 2 ;;
        --openers-from) EXPLICIT=1; SOURCE="$2"; shift 2 ;;
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
case "$NOPEN" in
    ''|*[!0-9]*|0) echo "-n must be a positive number (how many opening words)" >&2; exit 1 ;;
esac
if [ "$EXPLICIT" = 1 ] && [ -n "$OPENING" ] && [ -n "$SOURCE" ]; then
    echo "--openers-from cannot be combined with --opener/--openers" >&2; exit 1
fi

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }

SINGLES=data/shared/singletons
if [ "$EXPLICIT" = 0 ]; then
    # -n names a SIZE; the ranking for that size names the words.
    case "$NOPEN" in
        1) SOURCE=$SINGLES/guess_singletons.csv ;;
        2) SOURCE=$SINGLES/pair_singletons.csv ;;
        3) SOURCE=$SINGLES/triple_singletons.csv ;;
        *) case "$NOPEN" in
               4) PFX=quad ;; 5) PFX=quint ;; 6) PFX=sextet ;; *) PFX="" ;;
           esac
           echo "-n $NOPEN has no single canonical ranking: every run at that size" >&2
           echo "  is written under a name recording its own restriction, and those" >&2
           echo "  are different questions.  Pick one with --openers-from:" >&2
           ls -1 $SINGLES/${PFX:-nothing}_singletons*.csv 2>/dev/null | sed 's/^/    /' >&2
           [ -n "$PFX" ] || echo "    (no ranking of that size exists)" >&2
           exit 1 ;;
    esac
    [ -f "$SOURCE" ] || {
        echo "no $SOURCE -- build it with 'bash solver/run-singles.sh' first" >&2
        exit 1; }
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
    if [ "$EXPLICIT" = 0 ]; then
        # The file must actually rank openings of the size -n asked for.
        GOT=$(echo "$OPENING" | wc -w | tr -d ' ')
        [ "$GOT" = "$NOPEN" ] || {
            echo "$SOURCE ranks $GOT-word openings, but -n asked for $NOPEN" >&2
            exit 1; }
    fi
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
