#!/bin/bash
# The LONGEST CONSISTENT CHAIN, exactly, ATTACHED and live in this terminal.
#
#     bash solver/run-eldrowmax.sh                       # from math/, or anywhere
#     bash solver/run-eldrowmax.sh --greedy              # the lower bound, seconds
#     bash solver/run-eldrowmax.sh --target 20           # one decision, to price it
#     bash solver/run-eldrowmax.sh --floor 18            # skip re-deriving a known one
#     bash solver/run-eldrowmax.sh --exact               # the same number, the slow way
#     bash solver/run-eldrowmax.sh --words <list>.txt    # a different pool
#     bash solver/run-eldrowmax.sh --plays guess         # any legal word may be
#                                                        # played; only the LAST
#                                                        # must be an answer
#     bash solver/run-eldrowmax.sh --dry-run             # resolve and stop
#
# --dry-run STOPS AFTER RESOLUTION -- which pool, which output file -- and before
# anything runs or is written. Use it for every wrapper change: a bare invocation
# to "see if the flags parse" starts a real run, and a partial CSV from a quick
# check is indistinguishable from a real result that died.
#
# WHAT THIS COMPUTES, precisely: the longest sequence of words in which EVERY word
# is still a possible answer at the moment it is played -- consistent with every
# clue so far -- ending when only one word is left and it is named. The count
# INCLUDES that final naming move.
#
# It is `math/eldrow.py`'s `longest_chain` objective, made exact and made to scale;
# that module states the rule and remains the reference. eldrow.py counts
# guesses-until-a-singleton, so ITS NUMBER IS ONE LESS than this one -- never put
# the two in a table without saying which convention each is under.
#
# IT IS NOT THE ANTIWORDLE NUMBER. antistall's chains play any word ANTIWORDLE'S
# rules allow -- greens in place, yellows reused, greys as count caps -- which is a
# strictly LOOSER rule admitting words the answer could not be (11 of the 16 plays
# in its best known line are guess-only junk). Every play here is a live candidate,
# so the legal set is strictly smaller and so is the chain. THREE DIFFERENT GAMES
# -- eldrowmax, antistall, optturns -- and their totals never share a table.
#
# THE POOL IS PART OF THE OBJECTIVE. --words names the list that is both the
# candidates and the guesses; it defaults to the 2315 mystery answers, so a play is
# a word that could genuinely have been the answer. Every pool word must be in the
# pattern matrix's lists. A different pool is a different quantity and lands in its
# own CSV.
#
# --plays guess IS A DIFFERENT QUESTION (added 2026-10-14): every word played must
# still be consistent with every clue, but may be any of the 12972 legal words;
# only the FINAL word must be one of the 2315 answers. It runs the eldrowmaxg build
# (room for 12972 words) with --words guess.txt --answers mystery.txt, needs the
# square matrix (`python3 build_patterns.py --full`), and writes its own CSV. Its
# number is never comparable with the plain one -- a strictly larger play pool.
#
# NO DEPTH CAP AND NO BEAM: the game has no cap and a restricted search would not
# be the maximum. The only bound is that a chain cannot outlast its candidate set.
#
# USE THIS RATHER THAN CALLING THE BINARY DIRECTLY. It sets --out, so a long run
# cannot print its answer and save nothing, and tees a log. The binary REFUSES to
# start without --out or an explicit --no-out for the same reason.
#
# COST IS UNMEASURED. Price it with --greedy (seconds) and then a --target at the
# greedy length plus one before committing to the ladder.
#
# COMMIT THE CSV. data/shared/ is the committed, synced location by convention --
# but writing there does not commit it, and an uncommitted multi-hour result is one
# `git clean` away from gone. That has already happened once in this repo.
#
# RESULTS ARE FOR OUR WORD LISTS, which are not the NYT's current ones.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1
. solver/_guard.sh

[ -x ./solver/eldrowmax ] || {
    echo "no solver/eldrowmax -- run 'sh build.sh' in solver/" >&2
    exit 1
}
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run 'python3 build_patterns.py' first" >&2
    echo "  it is gitignored by design, so a fresh clone never has it" >&2
    exit 1
}

# The output name carries every knob that changes WHAT is computed -- which is the
# POOL and nothing else. --exact, --target, --floor and --threads all change how
# the same number is reached, not the number, so they stay columns rather than
# names and their runs append to one file. Scanned by INDEX rather than with shift,
# so the arguments survive to be passed through. (Indexed arrays are bash 3.2
# clean; associative ones are not -- macOS ships bash 3.2.)
ARGS=("$@")
TAG=""
DRY=0
PLAYS=""
PASS=()
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    case "${ARGS[$i]}" in
        --words)   TAG=".$(basename "${ARGS[$((i + 1))]}" .txt)"
                   PASS+=("${ARGS[$i]}") ;;
        --plays)   case "${ARGS[$((i + 1))]}" in
                       guess) PLAYS=guess ;;
                       *) echo "--plays takes 'guess'" >&2; exit 2 ;;
                   esac
                   i=$((i + 1)) ;;
        --dry-run) DRY=1 ;;
        *)         PASS+=("${ARGS[$i]}") ;;
    esac
    i=$((i + 1))
done
[ -n "$TAG" ] || TAG=".mystery"
BIN=./solver/eldrowmax
if [ "$PLAYS" = guess ]; then
    [ -z "${TAG#.mystery}" ] || { echo "--plays guess sets the pool itself; drop --words" >&2; exit 2; }
    TAG=".plays-guess"
    BIN=./solver/eldrowmaxg
    PASS+=(--words data/shared/words/guess.txt --answers data/shared/words/mystery.txt)
    [ -x "$BIN" ] || { echo "no $BIN -- run 'sh build.sh' in solver/" >&2; exit 1; }
    [ -f data/local/patterns/patterns_full.npy ] || {
        echo "no data/local/patterns/patterns_full.npy -- run 'python3 build_patterns.py --full'" >&2
        exit 1
    }
fi

OUTDIR=data/shared/eldrow
LOC=data/local/eldrow
OUT="$OUTDIR/eldrowmax${TAG}.csv"
LOG="$LOC/eldrowmax${TAG}.log"
if [ "$DRY" = 1 ]; then
    echo "dry run -- nothing started, nothing written"
    echo "  pool:   ${TAG#.}"
    echo "  out:    $MATH/$OUT"
    echo "  log:    $MATH/$LOG"
    echo "  binary: $BIN --out $OUT ${PASS[@]+${PASS[@]}}"
    exit 0
fi

mkdir -p "$OUTDIR" "$LOC"

guard_output "$(basename "$BIN")" "$OUT" || exit 1

# `date -Is` is GNU-only and prints NOTHING on macOS, which is how another wrapper
# here ended up logging an empty timestamp.
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] eldrowmax longest consistent chain -> $OUT" \
    | tee -a "$LOG"

# `${PASS[@]+...}` is not decoration: under `set -u`, bash 3.2 -- which is what
# macOS ships -- treats a bare "${PASS[@]}" on an EMPTY array as an unbound
# variable and aborts, so the no-argument form documented above would die here.
"$BIN" --out "$OUT" ${PASS[@]+"${PASS[@]}"} 2>&1 | tee -a "$LOG"
