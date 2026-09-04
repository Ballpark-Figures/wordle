#!/bin/bash
# Find the opener maximising the chance of the SEA OF GREENS badge, ATTACHED,
# with live output in this terminal.
#
#     bash solver/run-greens.sh                       # from math/, or anywhere
#     bash solver/run-greens.sh --opener salet        # one named opener + its tree
#     bash solver/run-greens.sh --threads 12 --tt-bits 26
#
# Same shape as run-sweep.sh: foreground, output tee'd so the log gets every line
# as well as your terminal.
#
# WHAT THIS SOLVES, precisely:
#
#   MAXIMISE the number of the 2315 answers won with NO YELLOW TILE anywhere in
#   the game, SUBJECT TO the strategy still winning every one of them within 6
#   guesses.  Lexicographic: the win comes first and is absolute; the badge is
#   maximised among strategies that never lose.  Once a yellow appears the badge
#   is gone for that answer and the play is only required to finish the game.
#
# -k K BEAMS IT, and that changes what is being claimed.  With --topk the solver
# recurses into only the K evenest-splitting guesses at every branching point,
# THE ROOT INCLUDED -- so it examines K openers as well, and the answer is the
# best of THOSE, not of all 12972.  Every value is one a real strategy ACHIEVES:
# a LOWER bound on that opener's true optimum, never a proof of optimality.
#
# THE CAP IS THE GAME, NOT A TUNING KNOB.  --depth 6 is what "do not lose" means,
# so the result is an optimum SUBJECT TO a 6-guess guarantee -- never quote it as
# an unconstrained maximum.  Each depth is a different quantity, so each gets its
# own CSV; the depth is in the filename.
#
# THE BADGE RULE IS UNVERIFIED.  "Complete a puzzle with no yellow tiles" was
# read from player reports via web search, not from the NYT and not from a badge
# screen of our own -- see the provenance note in math/greens.py.  Two clauses
# are inferred rather than observed: that a FAILED game with no yellows does not
# earn it, and that a lucky 1/6 does.
#
# Ctrl-C stops it -- openers already finished are in the CSV (flushed per opener)
# and a resume picks up from there, but the table is lost unless --tt-save ran.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOC=data/local/greens
SHR=data/shared/greens

DEPTH=6
THREADS=18          # 18 cores here (6 performance + 12 efficiency)
TTBITS=28           # 8.6 GB of 24 GB
TOPK=0              # 0 = the exact search; K = beam width at every node
OPENERS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --opener)  OPENERS+=("$2"); shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# EACH (depth, K) IS A DIFFERENT STRATEGY, so each gets its own CSV and its own
# table.  A beamed value is not an optimum and must never land in the same file
# as one, or be warm-started from another K's table -- the salt would reject it
# anyway, but the filename is what stops anyone trying.
SUF="d$DEPTH"
KARGS=()
if [ "$TOPK" -gt 0 ]; then
    SUF="${SUF}_k$TOPK"
    KARGS+=(--topk "$TOPK")
fi

cd "$MATH" || exit 1

if pgrep -x greens >/dev/null; then
    echo "greens is already running (pid $(pgrep -x greens | tr '\n' ' '))." >&2
    echo "Attach to its output instead:  tail -F $MATH/$LOC/sweep.log" >&2
    exit 1
fi
[ -x ./solver/greens ] || { echo "no greens binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix -- run 'python3 build_patterns.py' from math/" >&2; exit 1; }

mkdir -p "$SHR" "$LOC" "$SHR/trees"

# A table snapshot is reused when present, so a re-run resumes warm.  The key is
# salted with the word lists AND with this program's own constant, so an
# optturns tt.bin pointed here fails verification rather than answering.
WARM=""
TTBIN="$LOC/tt_$SUF.bin"
[ -f "$TTBIN" ] && WARM="--tt-load $TTBIN"

if [ ${#OPENERS[@]} -gt 0 ]; then
    OUT="$SHR/openers_$SUF.csv"
    ARGS=()
    for w in "${OPENERS[@]}"; do ARGS+=(--opener "$w"); done
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greens: named openers, $SUF $WARM" | tee -a "$LOC/run.log"
    ./solver/greens "${ARGS[@]}" "${KARGS[@]+"${KARGS[@]}"}" \
        --out "$OUT" \
        --trees "$SHR/trees" \
        --depth "$DEPTH" \
        --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
        --tt-save "$TTBIN" \
        2>&1 | tee -a "$LOC/run.log"
    exit "${PIPESTATUS[0]}"
fi

OUT="$SHR/best_opener_$SUF.csv"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greens: opener screen, $SUF $WARM" | tee -a "$LOC/sweep.log"
./solver/greens --sweep "${KARGS[@]+"${KARGS[@]}"}" \
    --out "$OUT" \
    --depth "$DEPTH" \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    --tt-save "$TTBIN" \
    2>&1 | tee -a "$LOC/sweep.log"
