#!/bin/bash
# Run the top-K Wordle beam over EVERY other-language word list, ANSWERS ONLY.
#
#     bash solver/run-lang-ans-solve.sh -k 1          # from math/, or anywhere
#     bash solver/run-lang-ans-solve.sh -k 3
#     bash solver/run-lang-ans-solve.sh -k 1 --langs fr,de,es
#     bash solver/run-lang-ans-solve.sh -k 1 --accents keep
#
# The ANSWERS-ONLY companion to run-lang-solve.sh.  EVERYTHING is identical --
# same top-K beam, same ranking, same length-5-only rule, same expected-guesses-
# OUTRIGHT objective with NO depth cap, same 13 languages, same CSV shape --
# EXCEPT that the guess set is restricted to each language's answer (mystery)
# list, so every guess (opener and follow-up) is itself a possible answer.  It is
# the language analogue of run-ans-sweep.sh, which restricts English's guesses to
# the 2315 answers with --guess-list mystery.txt.
#
# WHAT THIS MEASURES, precisely:
#
#   The EXPECTED NUMBER OF GUESSES to finish, over each language's answer list
#   taken UNIFORMLY, under the top-K guesser in math/topk.py -- which states the
#   strategy exactly and is the source of truth.  Guesses are ranked by the
#   expected number of candidates still alive (the winning bin excluded), ties on
#   the lowest guess index; the search recurses into the K best and keeps
#   whichever actually minimises expected guesses.  Here EVERY guess must itself
#   be an answer word for that language.
#
#   THERE IS NO DEPTH CAP.  This is expected guesses OUTRIGHT, the same footing
#   as run-lang-solve.sh and the multiwordle/foximax/adversarial numbers, and NOT
#   the footing of any optturns/hardturns/ansall total -- those are optima
#   subject to a 6-guess guarantee.  Never put the two in one table.  NB the
#   English answers-only sweep (run-ans-sweep.sh) IS capped and its cap binds;
#   that caveat does NOT transfer here, because this beam has no cap.
#
#   IT IS A DIFFERENT STRATEGY FROM run-lang-solve.sh, not the same numbers with
#   a smaller list -- the beam ranks and recurses over a different guess set -- so
#   it lands in its own directory (data/shared/langans) and its own log.
#
#   IT IS NOT AN OPTIMUM.  -k K examines K guesses at every node, THE ROOT
#   INCLUDED, so the opener is the best of the K examined and not the best of the
#   language's whole answer list.  Each K is a different strategy and its own file.
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
# USE THIS RATHER THAN CALLING tools/lang_solve.py DIRECTLY.  It sets --out and
# --answers-only, names the file after the K and accent mode that define the run,
# and tees a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

K=1
LANGS=""
ACCENTS="ascii"

while [ $# -gt 0 ]; do
    case "$1" in
        -k|--topk)  K="$2";       shift 2 ;;
        --langs)    LANGS="$2";   shift 2 ;;
        --accents)  ACCENTS="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$K" in ''|*[!0-9]*|0) echo "-k must be a positive number" >&2; exit 1 ;; esac
case "$ACCENTS" in ascii|keep) ;; *) echo "--accents takes 'ascii' or 'keep'" >&2; exit 1 ;; esac

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

WORDS=data/shared/words/lang/$ACCENTS
OUTDIR=data/shared/langans
LOC=data/local/langans

if [ ! -d "$WORDS" ]; then
    echo "no language word lists at $MATH/$WORDS" >&2
    echo "  build them first: ../.venv/bin/python build_lang_wordlists.py --accents $ACCENTS" >&2
    exit 1
fi

# The accent mode changes the ALPHABET, so it changes the game -- it belongs in
# the filename beside K, not just in the .meta.  answers-only lives in its own
# directory, so the stem matches run-lang-solve.sh's.
STEM="topk${K}_len5_${ACCENTS}"
OUT="$OUTDIR/$STEM.csv"
mkdir -p "$OUTDIR" "$LOC"

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
# Sourced through $MATH, which is absolute: BASH_SOURCE is the path AS INVOKED,
# so a relative one stops resolving the moment we cd above.
. "$MATH/solver/_guard.sh"
guard_output lang_solve.py "$OUT" || exit 1

FLAGS="-k $K --words $WORDS --out $OUT --answers-only"
[ -n "$LANGS" ] && FLAGS="$FLAGS --langs $LANGS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] lang solve (answers-only) $STEM" | tee -a "$LOC/$STEM.log"

"$PY" -u tools/lang_solve.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
