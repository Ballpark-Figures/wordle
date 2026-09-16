#!/bin/bash
# Build the PREDETERMINED SECOND WORD table -- one row per opener -- attached,
# with live output in this terminal.
#
#     bash solver/run-second-word.sh                          # from math/, or anywhere
#     bash solver/run-second-word.sh --variant mystery
#     bash solver/run-second-word.sh --min-grays 4
#     bash solver/run-second-word.sh --by-grays 3          # a word PER grey count
#     bash solver/run-second-word.sh --group e5 --group e4+e3
#     bash solver/run-second-word.sh --limit 500 --dry-run
#
# WHAT IT COMPUTES.  For every opener, the one word to commit to in advance for
# the games where that opener's reply shows at least --min-grays GREY tiles: the
# word minimising the expected number of ANSWERS still consistent after both,
# averaged over exactly those games, the answer uniform over the 2315.  It is the
# sum of squared joint-bucket sizes over the qualifying replies, divided by how
# many answers qualify.  math/secondword.py states it exactly and is the source
# of truth; solver/secondword.c implements it.
#
# --split-vowels CROSSES each --by-grays group with the number of GREYED VOWELS,
# so `--by-grays 3 --split-vowels` gives a different second word for every
# (grey count, greyed-vowel count) pair from three greys up.  Y IS ALWAYS A VOWEL
# here (the user's call, 2026-09-10) -- one vowel set, stamped into every table.
# A greyed vowel is counted by POSITION, so this bucket depends on the OPENER's
# letters as well as the reply, and the groups are built per opener.
#
# --split-matched-vowels CROSSES each --by-grays group with the number of MATCHED
# (green or yellow) vowels instead -- "how many vowels we matched versus how many
# consonants" (the consonants matched are (5 - greys) minus the vowels matched).
# So `--by-grays 3 --split-matched-vowels` gives a different second word for every
# (grey count, matched-vowel count) pair, splitting the 3- and 4-grey cases and
# leaving the all-grey reply (no matched tiles) as ONE group `e5`.  The atom is
# `mv<N>`; y is a vowel here too, stamped into the table.  Like `v<N>` it depends
# on the opener's letters, so the groups are built per opener.  It is a DIFFERENT
# partition from --split-vowels (the two cannot be combined) -- and for a fixed
# opener the two are complementary (matched = the opener's vowels minus greyed).
#
# --group SPEC IS THE GENERAL FORM: one bucket of replies with its OWN second
# word, repeated for a partition.  A spec is terms joined by `+`: g<N> (greys >=
# N), e<N> (greys == N exactly), <G>g<Y>y (that composition).  So a separate word
# for five, four and three greys is --group e5 --group e4 --group e3, which
# --by-grays 3 writes out for you.  GROUPS MUST BE DISJOINT -- a reply in two of
# them would have two predetermined words and no rule for choosing -- and a reply
# in no group DECLINES to the follow-up.  --min-grays / --fire are the one-group
# sugar and are unchanged.
#
# --fire G,Y ADDS ONE COMPOSITION to the firing condition, on top of the
# --min-grays threshold.  `--min-grays 3 --fire 0,3` fires on every reply with
# three or more greys AND on the three-yellow two-grey reply, which is nearly
# uninformative despite having only two greys.  The condition is a SET of
# (greens, yellows) compositions; --min-grays is the sugar for "at least N
# greys", and the canonical NAME of the set is what lands in the filename.
#
# --min-grays IS THE OBJECTIVE, not a knob.  A >= 3 table and a >= 4 table pick
# different words and describe different strategies, so it is in the filename AND
# in the file's own stamp, and the reader refuses a table whose stamp disagrees
# with what was asked for.  The default below is a HUMAN's default (the user's
# call, 2026-09-10: three or more greys) and is forwarded EXPLICITLY -- the binary
# itself refuses to run without it, so the one decision has one owner.
#
# --variant IS THE OTHER HALF OF THE OBJECTIVE.  Two pools, always moving
# together, and they are two different experiments whose numbers must never share
# a table:
#
#     guess     openers and second words both the 12972 legal words
#     mystery   openers and second words both the 2315 mystery answers
#
# The `mystery` variant is a strictly smaller strategy space, so its `expected`
# figures are weakly worse.  Sweep it with `--words mystery`; the sweep refuses an
# opener the table has no row for, so the two cannot be crossed by accident.
#
# --limit N IS FOR PRICING ONLY.  It scores the first N openers and stops, and
# because that is a PREFIX of the table rather than the table, the output goes to
# its own filename and its stamp renames the opener pool -- so nothing can read a
# priced run as the finished table.
#
# Exact and deterministic: a pure function of the committed word lists and the
# pattern matrix.  No sampling, no seed, so a re-run reproduces the file byte for
# byte.  It is ONE PLY -- what is left after two guesses, never what the game goes
# on to cost; only the simulation the table feeds can say that.
#
# Output: data/shared/secondword/second_<variant>_g<N>.csv, log under
# data/local/secondword/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$MATH/solver/_guard.sh"

# Defaults a HUMAN reads, forwarded explicitly -- never ones a program falls
# back on.  Both are in the output filename.
VARIANT=guess
MINGRAYS=3
FIRE=""
# NOT `GROUPS`: bash has a BUILT-IN array of that name holding the user's group
# ids, so assigning to it writes element 0 and reading it back gives a gid (20,
# `staff`, on macOS).  It fails silently and looks like a quoting bug.
GSPECS=""
BYGRAYS=""
SPLITV=0
SPLITMV=0
GIVEN=0
LIMIT=0
THREADS=0
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --variant)    VARIANT="$2"; shift 2 ;;
        --min-grays)  MINGRAYS="$2"; shift 2 ;;
        --fire)       FIRE="$FIRE --fire $2"; shift 2 ;;
        --group)      GSPECS="$GSPECS --group $2"; GIVEN=1; shift 2 ;;
        --by-grays)   BYGRAYS="$2"; GIVEN=1; shift 2 ;;
        --split-vowels) SPLITV=1; shift ;;
        --split-matched-vowels) SPLITMV=1; shift ;;
        --limit)      LIMIT="$2"; shift 2 ;;
        --threads)    THREADS="$2"; shift 2 ;;
        --dry-run)    DRY=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$VARIANT" in
    guess)   POOL=data/shared/words/guess.txt ;;
    mystery) POOL=data/shared/words/mystery.txt ;;
    *) echo "--variant must be 'guess' (the 12972) or 'mystery' (the 2315)" >&2
       exit 1 ;;
esac
# THE CROSS PRODUCTS ARE THE BINARY'S, not this script's.  The two splits have
# DIFFERENT bounds -- greyed vowels run 0..n, matched vowels 0..5-n, and the
# all-grey reply has no matched tiles so it stays one group -- and that rule used
# to be written out here in shell as well as in the solver.  Two copies of it
# means one canonical label from secondword and a different one from secondexact
# for the same strategy.  Now both just forward the flags.
if [ "$GIVEN" = 0 ]; then
    case "$MINGRAYS" in
        ''|*[!0-9]*) echo "--min-grays must be a number of grey tiles (0-5)" >&2
                     exit 1 ;;
    esac
    if [ "$MINGRAYS" -lt 1 ] || [ "$MINGRAYS" -gt 5 ]; then
        echo "--min-grays $MINGRAYS: a reply has 5 tiles, and 0 would fire every game" >&2
        exit 1
    fi
    SPEC="--min-grays $MINGRAYS$FIRE"
else
    [ -z "$FIRE" ] || { echo "--fire is sugar for the one-group case; inside a "\
        "--group partition, put the composition in the group's own spec" >&2
        exit 1; }
    SPEC="$GSPECS"
    [ -z "$BYGRAYS" ] || SPEC="$SPEC --by-grays $BYGRAYS"
    [ "$SPLITV" = 0 ]  || SPEC="$SPEC --split-vowels"
    [ "$SPLITMV" = 0 ] || SPEC="$SPEC --split-matched-vowels"
fi
case "$LIMIT" in
    ''|*[!0-9]*) echo "--limit must be a number of openers" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

BIN=solver/secondword
[ -x "$BIN" ] || { echo "no $BIN -- build it with 'sh build.sh' from math/solver/" >&2
                   exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix at data/local/patterns/patterns.npy" >&2
    echo "  Build it with 'python3 build_patterns.py' from math/ (~2s, 30 MB)." >&2
    exit 1; }

OUTDIR=data/shared/secondword
LOC=data/local/secondword
# ASK THE BINARY WHAT THE FIRING CONDITION IS CALLED rather than re-deriving it
# in shell: the canonical label drops an --fire the threshold already covers and
# sorts the rest, so two spellings of one rule cannot make two filenames -- and
# that canonicalisation has exactly one owner.
LABEL=$($BIN $SPEC --print-label) || exit 1
STEM="second_${VARIANT}_${LABEL}"
[ "$LIMIT" = 0 ] || STEM="${STEM}_limit${LIMIT}"
OUT="$OUTDIR/$STEM.csv"
LOG="$LOC/$STEM.log"

FLAGS="$SPEC --openers $POOL --seconds $POOL"
FLAGS="$FLAGS --openers-name $VARIANT --seconds-name $VARIANT"
[ "$LIMIT" = 0 ]   || FLAGS="$FLAGS --limit $LIMIT"
[ "$THREADS" = 0 ] || FLAGS="$FLAGS --threads $THREADS"

echo "second-word table"
echo "  variant    $VARIANT   (openers and second words both from $POOL)"
echo "  fires on   $LABEL   -- part of the objective, in the name and the stamp"
[ "$LIMIT" = 0 ] || echo "  limit      $LIMIT openers: a PRICING prefix, not the table"
echo "  out        $OUT"
echo "  log        $LOG"

if [ "$DRY" = 1 ]; then
    echo
    echo "--dry-run: resolved, nothing run and nothing written."
    echo "  would run: $BIN $FLAGS --out $OUT"
    exit 0
fi

guard_output secondword "$OUT" || exit 1

mkdir -p "$OUTDIR" "$LOC"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] secondword: variant=$VARIANT fire=$LABEL" \
    | tee -a "$LOG"

$BIN $FLAGS --out "$OUT" 2>&1 | tee -a "$LOG"
