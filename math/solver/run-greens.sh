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
# WHAT THIS SOLVES, precisely.  TWO OBJECTIVES, and they are DIFFERENT
# QUANTITIES -- never quote one as the other or put them in one table:
#
#   --may-lose -- THE BADGE QUESTION.  MAXIMISE the number of the 2315 answers
#   WON WITHIN 6 GUESSES WITH NO YELLOW TILE.  One event per answer: it counts
#   iff the play both stays yellow-free AND finishes inside the cap.  An answer
#   that draws a yellow is simply lost, and the strategy owes it nothing
#   afterwards -- it may abandon that game.
#
#   DEFAULT (--must-win) -- the same maximisation SUBJECT TO the strategy still
#   winning EVERY answer within 6, yellow ones included.  A strictly smaller
#   strategy space, so its value is always <= --may-lose's.  It answers "if I
#   refuse to ever lose a game, how often can I win in 6 with all greens?".
#
#   MUST-WIN IS THE DEFAULT ONLY BECAUSE RUNS WERE QUEUED AGAINST IT, not
#   because it is the headline quantity.  It is not.
#
# -k K BEAMS IT, and that changes what is being claimed.  With --topk the solver
# recurses into only the K evenest-splitting guesses at every branching point,
# THE ROOT INCLUDED -- so it examines K openers as well, and the answer is the
# best of THOSE, not of all 12972.  Every value is one a real strategy ACHIEVES:
# a LOWER bound on that opener's true optimum, never a proof of optimality.
#
# THE CAP IS THE GAME.  --depth 6 is the six guesses you get, and under the
# default objective it is part of the event being counted, not a side constraint.
# Each depth is a different quantity, so each gets its own CSV; the depth, the
# beam width and the objective are all in the filename.
#
# THE BADGE RULE IS UNVERIFIED.  "Complete a puzzle with no yellow tiles" was
# read from player reports via web search, not from the NYT and not from a badge
# screen of our own -- see the provenance note in math/greens.py.  Two clauses
# are inferred rather than observed: that a FAILED game with no yellows does not
# earn it, and that a lucky 1/6 does.
#
# THE SWEEP KEEPS THE BEST TREE.  Every time an opener improves the incumbent its
# full strategy is written to trees_<settings>/<opener>.txt.gz, so an interrupted
# run still leaves the best strategy found and not merely its score.  Superseded
# openers keep their files, which makes the directory a record of how the
# incumbent improved; the final report names the winner.
#
# WHAT IS IN A TREE depends on the objective.  Under --may-lose it is the
# badge-alive part only: a yellow ends that branch, so the file holds exactly one
# line per BADGED answer and its line count is the reported score.  Under
# must-win it covers every answer, post-yellow play included, because there the
# strategy really does have to finish those games.
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
MUSTWIN=1           # 1 = must-win (default); 0 = the badge question
OPENERS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --opener)  OPENERS+=("$2"); shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        --must-win) MUSTWIN=1;   shift ;;
        --may-lose) MUSTWIN=0;   shift ;;
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
if [ "$MUSTWIN" -eq 1 ]; then
    SUF="${SUF}_mustwin"
    KARGS+=(--must-win)
fi

cd "$MATH" || exit 1

[ -x ./solver/greens ] || { echo "no greens binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no pattern matrix -- run 'python3 build_patterns.py' from math/" >&2; exit 1; }

TREES="$SHR/trees_$SUF"
mkdir -p "$SHR" "$LOC" "$TREES"

# Output and log names are fixed by (depth, K, objective), so two runs with
# DIFFERENT settings share nothing and may run side by side.
if [ ${#OPENERS[@]} -gt 0 ]; then
    OUT="$SHR/openers_$SUF.csv"
    LOG="$LOC/run_$SUF.log"
else
    OUT="$SHR/best_opener_$SUF.csv"
    LOG="$LOC/sweep_$SUF.log"
fi

# THE CONFLICT IS THE OUTPUT FILE, NOT THE BINARY.  Refusing on the process name
# blocked perfectly safe pairs -- two objectives, or two beam widths, which have
# separate CSVs, tables and logs.  What must never happen is two runs appending
# to ONE CSV: each resumes from it, so they would read each other's rows as work
# already done and silently skip openers neither had solved.  So the check is
# for a live run writing THIS file, which also catches one started before this
# guard existed, since it reads the actual command lines.
CLASH=$(ps -Ao pid,command | grep "solver/greens " | grep -v grep         | grep -F -- "--out $OUT" | awk '{print $1}' | tr '\n' ' ')
if [ -n "$CLASH" ]; then
    echo "a greens run is ALREADY writing $OUT (pid $CLASH)." >&2
    echo "Two runs sharing one CSV would corrupt each other's resume." >&2
    echo "Attach to it instead:  tail -F $MATH/$LOG" >&2
    exit 1
fi

# Different settings: allowed, but say what it costs.  The table is the whole
# memory footprint and it is per-process, and threads are not shared out.
OTHERS=$(pgrep -x greens | tr '\n' ' ')
if [ -n "$OTHERS" ]; then
    GB=$(awk "BEGIN{printf \"%.1f\", 32 * 2^$TTBITS / 1e9}")
    echo "NOTE: greens is already running with other settings (pid $OTHERS)."
    echo "      That is fine -- each (depth, K, objective) has its own CSV, table and log."
    echo "      This run adds ${GB} GB of table and asks for $THREADS threads on top of"
    echo "      whatever those are using.  Pass --tt-bits / --threads to share the"
    echo "      machine deliberately rather than oversubscribing it."
fi

# A table snapshot is reused when present, so a re-run resumes warm.  The key is
# salted with the word lists AND with this program's own constant, so an
# optturns tt.bin pointed here fails verification rather than answering.
WARM=""
TTBIN="$LOC/tt_$SUF.bin"
[ -f "$TTBIN" ] && WARM="--tt-load $TTBIN"

if [ ${#OPENERS[@]} -gt 0 ]; then
    ARGS=()
    for w in "${OPENERS[@]}"; do ARGS+=(--opener "$w"); done
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greens: named openers, $SUF $WARM" | tee -a "$LOG"
    ./solver/greens "${ARGS[@]}" "${KARGS[@]+"${KARGS[@]}"}" \
        --out "$OUT" \
        --trees "$TREES" \
        --depth "$DEPTH" \
        --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
        --tt-save "$TTBIN" \
        2>&1 | tee -a "$LOG"
    exit "${PIPESTATUS[0]}"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greens: opener screen, $SUF $WARM" | tee -a "$LOG"
./solver/greens --sweep "${KARGS[@]+"${KARGS[@]}"}" \
    --out "$OUT" \
    --trees "$TREES" \
    --depth "$DEPTH" \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    --tt-save "$TTBIN" \
    2>&1 | tee -a "$LOG"
