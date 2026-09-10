#!/bin/bash
# Run the top-K Wordle beam over EVERY other-language word list, attached.
#
#     bash solver/run-lang-solve.sh -k 1          # from math/, or anywhere
#     bash solver/run-lang-solve.sh -k 3
#     bash solver/run-lang-solve.sh -k 1 --langs fr,de,es
#     bash solver/run-lang-solve.sh -k 1 --accents keep
#
# WHAT THIS MEASURES, precisely:
#
#   The EXPECTED NUMBER OF GUESSES to finish, over each language's answer list
#   taken UNIFORMLY, under the top-K guesser in math/topk.py -- which states the
#   strategy exactly and is the source of truth.  Guesses are ranked by the
#   expected number of candidates still alive (the winning bin excluded), ties on
#   the lowest guess index; the search recurses into the K best and keeps
#   whichever actually minimises expected guesses.
#
#   THERE IS NO DEPTH CAP.  This is expected guesses OUTRIGHT, the same footing
#   as the multiwordle, foximax and adversarial numbers, and NOT the footing of
#   any optturns/hardturns/ansall total -- those are optima subject to a 6-guess
#   guarantee.  Never put the two in one table.
#
#   IT IS NOT AN OPTIMUM.  -k K examines K guesses at every node, THE ROOT
#   INCLUDED, so the opener is the best of the K examined and not the best of the
#   language's whole guess list.  Each K is a different strategy and its own file.
#
#   THE LISTS ARE OURS, NOT ANY REAL CLONE'S -- build_lang_wordlists.py cuts
#   wordfreq at a zipf calibrated on the English lists.  That consistency is what
#   makes a cross-language comparison mean anything, and it is also why these
#   numbers are not fr/de/es Wordle as anyone actually plays it.
#
#   LENGTH 5 ONLY.  topk.py's numba kernels bake in ALL_GREEN=242, so another
#   length would silently exclude the wrong winning bin; the driver refuses.
#
#   Exact and deterministic: no sampling, no seed.  One (k, accents) means one
#   file, and a re-run reproduces it.  Resumable -- a language already in the CSV
#   is skipped, and rows are flushed per language, so a Ctrl-C keeps the finished
#   ones.
#
# USE THIS RATHER THAN CALLING tools/lang_solve.py DIRECTLY.  It sets --out,
# names the file after the K and accent mode that define the run, and tees a log.
#
# ------------------------------------------------- ONE EXPLICITLY NAMED LIST
#
#     bash solver/run-lang-solve.sh --answers data/shared/words/custom.txt \
#         --guesses data/shared/words/guess.txt
#
# --answers/--guesses solve ONE named pair instead of discovering language dirs,
# through the SAME driver and the same columns.  That is what produces the
# ENGLISH baseline: the top-K guesser over the 4282-word frequency-cut candidate
# list with every weight 1 -- uniform weighting being topk.py's own default, not
# a separate mode -- which is the number an adversarial expected_guesses from
# data/shared/freqsearch/topk<K>.csv is quoted against.
#
# THE GUESS SET IS PART OF THE QUESTION and is never defaulted: --guesses is
# required alongside --answers, or --answers-only to make the answer list its own
# guess set.  A 12972-word guesser and a 4282-word one are different strategies.
#
# Named runs land under data/shared/topk/ rather than data/shared/lang/, since
# they are not language results.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=1
LANGS=""
ACCENTS="ascii"
ANSWERS=""
GUESSES=""
LABEL=""
ANSONLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--topk)      K="$2";       shift 2 ;;
        --langs)        LANGS="$2";   shift 2 ;;
        --accents)      ACCENTS="$2"; shift 2 ;;
        --answers)      ANSWERS="$2"; shift 2 ;;
        --guesses)      GUESSES="$2"; shift 2 ;;
        --label)        LABEL="$2";   shift 2 ;;
        --answers-only) ANSONLY=1;    shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$K" in ''|*[!0-9]*|0) echo "-k must be a positive number" >&2; exit 1 ;; esac
case "$ACCENTS" in ascii|keep) ;; *) echo "--accents takes 'ascii' or 'keep'" >&2; exit 1 ;; esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

# ---- one explicitly named list pair -------------------------------------
if [ -n "$ANSWERS" ]; then
    [ -f "$ANSWERS" ] || { echo "missing $ANSWERS" >&2; exit 1; }
    if [ "$ANSONLY" -eq 0 ]; then
        [ -n "$GUESSES" ] || { echo "--guesses PATH is required with --answers (or --answers-only)." >&2
                               echo "  The guess set is part of the question, so it is never defaulted." >&2
                               exit 1; }
        [ -f "$GUESSES" ] || { echo "missing $GUESSES" >&2; exit 1; }
    fi
    if [ -z "$LABEL" ]; then
        LABEL=$(basename "$ANSWERS"); LABEL=${LABEL%.txt}
    fi
    OUTDIR=data/shared/topk
    LOC=data/local/topk
    SUF=""; [ "$ANSONLY" -eq 1 ] && SUF="_answers-only"
    STEM="topk${K}_${LABEL}${SUF}"
    OUT="$OUTDIR/$STEM.csv"
    mkdir -p "$OUTDIR" "$LOC"
    . "$MATH/solver/_guard.sh"
    guard_output lang_solve.py "$OUT" || exit 1
    FLAGS="-k $K --answers $ANSWERS --label $LABEL --out $OUT"
    [ "$ANSONLY" -eq 1 ] && FLAGS="$FLAGS --answers-only" \
                         || FLAGS="$FLAGS --guesses $GUESSES"
    echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] topk solve $STEM (weights uniform)" \
        | tee -a "$LOC/$STEM.log"
    "$PY" -u tools/lang_solve.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
    exit $?
fi

WORDS=data/shared/words/lang/$ACCENTS
OUTDIR=data/shared/lang
LOC=data/local/lang

if [ ! -d "$WORDS" ]; then
    echo "no language word lists at $MATH/$WORDS" >&2
    echo "  build them first: ../.venv/bin/python build_lang_wordlists.py --accents $ACCENTS" >&2
    exit 1
fi

# The accent mode changes the ALPHABET, so it changes the game -- it belongs in
# the filename beside K, not just in the .meta.
STEM="topk${K}_len5_${ACCENTS}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
# Sourced through $MATH, which is absolute: BASH_SOURCE is the path AS INVOKED,
# so a relative one stops resolving the moment we cd above.
. "$MATH/solver/_guard.sh"
guard_output lang_solve.py "$OUT" || exit 1

FLAGS="-k $K --words $WORDS --out $OUT"
[ -n "$LANGS" ] && FLAGS="$FLAGS --langs $LANGS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] lang solve $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/lang_solve.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
