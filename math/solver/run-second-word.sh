#!/bin/bash
# Build the PREDETERMINED SECOND WORD table -- one row per opener -- attached,
# with live output in this terminal.
#
#     bash solver/run-second-word.sh                          # from math/, or anywhere
#     bash solver/run-second-word.sh --variant mystery
#     bash solver/run-second-word.sh --min-grays 4
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
LIMIT=0
THREADS=0
DRY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --variant)    VARIANT="$2"; shift 2 ;;
        --min-grays)  MINGRAYS="$2"; shift 2 ;;
        --fire)       FIRE="$FIRE --fire $2"; shift 2 ;;
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
case "$MINGRAYS" in
    ''|*[!0-9]*) echo "--min-grays must be a number of grey tiles (0-5)" >&2; exit 1 ;;
esac
if [ "$MINGRAYS" -lt 1 ] || [ "$MINGRAYS" -gt 5 ]; then
    echo "--min-grays $MINGRAYS: a reply has 5 tiles, and 0 would fire every game" >&2
    exit 1
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
LABEL=$($BIN --min-grays $MINGRAYS$FIRE --print-label) || exit 1
STEM="second_${VARIANT}_${LABEL}"
[ "$LIMIT" = 0 ] || STEM="${STEM}_limit${LIMIT}"
OUT="$OUTDIR/$STEM.csv"
LOG="$LOC/$STEM.log"

FLAGS="--min-grays $MINGRAYS$FIRE --openers $POOL --seconds $POOL"
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
