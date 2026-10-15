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
# and a resume picks up from there.  The table is not kept -- see below.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOC=data/local/greens
SHR=data/shared/greens

DEPTH=6
THREADS=18          # 18 cores here (6 performance + 12 efficiency)
TTBITS=28           # 8.6 GB of 24 GB
TOPK=0              # 0 = the exact search; K = beam width at every node
MUSTWIN=1           # 1 = must-win (default); 0 = the badge question
SEED=""             # "" = none; "auto" = best contained run; N = explicit
UNCAPPED=0          # 1 = no guess limit (greens --uncapped); refuses --depth
DEPTH_SET=0
OPENERS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)   DEPTH="$2";   DEPTH_SET=1; shift 2 ;;
        --uncapped) UNCAPPED=1;  shift ;;
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        --opener)  OPENERS+=("$2"); shift 2 ;;
        -k|--topk) TOPK="$2";    shift 2 ;;
        --must-win) MUSTWIN=1;   shift ;;
        --may-lose) MUSTWIN=0;   shift ;;
        --seed)    SEED="$2";    shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# EACH (depth, K) IS A DIFFERENT STRATEGY, so each gets its own CSV and its own
# table.  A beamed value is not an optimum and must never land in the same file
# as one, or be warm-started from another K's table -- the salt would reject it
# anyway, but the filename is what stops anyone trying.
# --uncapped: NO GUESS LIMIT.  The binary runs it at depth 32, which it proves
# never binds, so the file is named for what it is -- "uncapped" -- and not d32.
if [ "$UNCAPPED" -eq 1 ]; then
    [ "$DEPTH_SET" -eq 1 ] && { echo "--uncapped sets its own depth; drop --depth" >&2; exit 1; }
    SUF="uncapped"
    DEPTHARGS=(--uncapped)
else
    SUF="d$DEPTH"
    DEPTHARGS=(--depth "$DEPTH")
fi
KARGS=()
if [ "$TOPK" -gt 0 ]; then
    SUF="${SUF}_k$TOPK"
    KARGS+=(--topk "$TOPK")
fi
# ALWAYS FORWARD THE OBJECTIVE, IN BOTH DIRECTIONS.  Passing it only in the
# must-win case and letting the binary's default cover the other is exactly how
# `--may-lose` came to run a MUST-WIN search under a may-lose FILENAME: the
# binary's default moved, and a wrapper that leans on a default inherits every
# future change to it.  The binary now refuses to guess, so this cannot recur,
# but the rule stands on its own: never let two places own one decision.
if [ "$MUSTWIN" -eq 1 ]; then
    SUF="${SUF}_mustwin"
    KARGS+=(--must-win)
else
    KARGS+=(--may-lose)
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

# NOTHING SAVES A TABLE ANY MORE, and the reason is worth writing down.
#
# tt_save runs at the END of main, so it fired ONLY on normal completion -- which
# is exactly when the table is worthless: a finished run's CSV marks every opener
# done, so re-running the same settings resumes, finds nothing to do, and exits
# without ever reading it.  The case where a warm table WOULD pay -- an
# interrupted run -- saved nothing, because Ctrl-C never reaches that line.  So
# the flag was backwards, and at 8.6 GB per settings combination it cost about
# 172 GB of disk to be so.  It was copied from run-ans-sweep.sh, where a snapshot
# IS load-bearing because that sweep runs for weeks and gets killed by reboots,
# without asking whether this solver has the same problem.  It does not.
#
# --tt-load stays: it costs nothing, and a table created deliberately (by hand or
# by the tt* tools) is still worth warming from.  With nothing writing one
# automatically, WARM is simply empty.
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
        "${DEPTHARGS[@]}" \
        --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
        2>&1 | tee -a "$LOG"
    exit "${PIPESTATUS[0]}"
fi

# --seed: START THE INCUMBENT AT A VALUE ANOTHER RUN ALREADY ACHIEVED.
#
# Sound only when that run's strategy lies INSIDE this search, and that means a
# SMALLER BEAM AT THE SAME DEPTH (K' <= K -- every node's top K' splitters are
# among its top K, the root included) under the same objective and word lists.
#
# A SHALLOWER CAP IS NOT CONTAINED, although it looks it.  A strategy winning
# within D' wins within D in the GAME, but not inside the BEAM: at one guess
# left the rule plays a candidate outright (greens.py `depth == 1`), a word the
# top-K splitters at a deeper node usually exclude.  So the beamed value is NOT
# monotone in depth -- measured: d4 K=3 finds 141 where d5..d11 K=3 find 139,
# and the reference shows the same on small cases -- while it IS monotone in K
# (0 of 900 opener x depth cases broke it).  Seeding across depths would inject
# values this beam cannot reach, and every run would report none reached.
#
# UNCAPPED EXACT is the one search that contains EVERY run: any strategy winning
# within some cap wins with no cap, and a beam's value is a real strategy's.  So
# under --uncapped with no -k, `auto` reads every may-lose run at any depth and K.
#
# `auto` takes the best exact row of every such run on disk, partial or
# finished, excluding this run's own file (its rows are the resume's business).
# The binary guarantees
# nothing worth >= the seed is lost; what changes is that a run reaching
# nothing at or above it names NO winner -- and the `.seed` sidecar is what
# lets a reader tell that apart from a run whose best is its highest row.
SEEDARGS=()
if [ -n "$SEED" ]; then
    OBJ=$([ "$MUSTWIN" -eq 1 ] && echo must-win || echo may-lose)
    if [ "$SEED" = auto ]; then
        PICK=$(for f in "$SHR"/best_opener_d*_k*.csv; do
                   [ "$f" = "$OUT" ] && continue
                   awk -F, -v obj="$OBJ" -v D="$DEPTH" -v K="$TOPK" -v U="$UNCAPPED" -v f="$f" '
                       NR == 1 {
                           if ($0 !~ /^# greens /) exit
                           for (i = 1; i <= split($0, t, " "); i++) {
                               split(t[i], kv, "="); s[kv[1]] = kv[2]
                           }
                           ok = s["objective"] == obj && s["guesses"] == 12972 &&
                                s["answers"] == 2315 &&
                                (U + 0 ? K + 0 == 0
                                       : s["depth"] + 0 == D + 0 && s["topk"] + 0 >= 1 &&
                                         (K + 0 == 0 || s["topk"] + 0 <= K + 0))
                           if (!ok) exit
                           next
                       }
                       $5 == "exact" && $2 + 0 > b { b = $2 + 0; w = $1 }
                       END { if (b) print b, f, w }' "$f"
               done | sort -n -k1,1 | tail -1)
        if [ -z "$PICK" ]; then
            echo "seed: no contained run on disk, so no seed" | tee -a "$LOG"
        else
            set -- $PICK
            SEEDV=$1; SEEDSRC="$(basename "$2") $3"
        fi
    else
        SEEDV=$SEED; SEEDSRC="given on the command line"
    fi
    if [ -n "${SEEDV:-}" ]; then
        SEEDARGS=(--seed-incumbent "$SEEDV")
        echo "seed: $SEEDV from $SEEDSRC" | tee -a "$LOG"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] seed=$SEEDV from=$SEEDSRC" >> "$OUT.seed"
    fi
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] greens: opener screen, $SUF $WARM" | tee -a "$LOG"
./solver/greens --sweep "${KARGS[@]+"${KARGS[@]}"}" "${SEEDARGS[@]+"${SEEDARGS[@]}"}" \
    --out "$OUT" \
    --trees "$TREES" \
    "${DEPTHARGS[@]}" \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOG"
# The SOLVER's status, not tee's -- or a crash reads as success, and a loop of
# K values runs straight past it leaving empty CSVs (2026-09-29, a segfault).
exit "${PIPESTATUS[0]}"
