#!/bin/bash
# Start the ANSWERS-ONLY sweep ATTACHED, with live output in this terminal.
#
#     bash solver/run-ans-sweep.sh                     # from math/, or anywhere
#     bash solver/run-ans-sweep.sh --threads 12 --tt-bits 26
#
# Same shape as run-sweep.sh: foreground, output tee'd so sweep.log gets every
# line as well as your terminal.  The tee matters -- tools/report.py and
# tools/inflight.py PARSE that log, so a bare run makes them silently report the
# PREVIOUS run's numbers.
#
# WHAT THIS SOLVES, precisely:
#
#   Minimise the TOTAL guesses summed over all 2315 answers, where EVERY guess
#   -- the opener and every follow-up -- must itself be one of the 2315 answer
#   words, SUBJECT TO resolving every answer within 6 guesses.
#
# It is the same binary as the normal sweep; --guess-list mystery.txt is what
# restricts it.  Shrinking the guess list shrinks NG, and since every guess loop
# and --sweep itself enumerate 0..NG-1, that restricts BOTH the follow-up guesses
# AND the set of openers swept -- so this sweeps 2315 openers, not 12972.
#
# THE DEPTH CAP BINDS HERE, AND THAT IS THE POINT.  Normal mode justifies its
# --depth 6 with "any opener can follow SALET's tree afterwards" -- but SALET is
# NOT an answer word (nor is REAST), so that escape is illegal under these rules
# and the feasibility argument does not transfer.  INFEASIBLE openers are
# therefore an EXPECTED result here, exactly as in hard mode: a `word,,,,secs`
# CSV row is data, not a bug.  The cap is a deliberate, user-chosen part of the
# objective -- these are optima SUBJECT TO a 6-guess guarantee, never
# "unconstrained minimum expected guesses".
#
# The per-word line omits exp= (it is just total/2315); the CSV still carries it
# for tools/report.py.  Ctrl-C stops the sweep -- finished words are already in
# the CSV (flushed per word), but the table is lost; snapshot it first with
# tools/ttdump.py if you want to keep it.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=data/shared/ansturns/opener_totals.csv
LOC=data/local/ansturns
LIST=data/shared/words/mystery.txt

THREADS=18          # 18 cores here (6 performance + 12 efficiency)
TTBITS=28           # 8.6 GB of 24 GB -- 29 would be 17.2 GB and far too tight

while [ $# -gt 0 ]; do
    case "$1" in
        --threads) THREADS="$2"; shift 2 ;;
        --tt-bits) TTBITS="$2";  shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

cd "$MATH" || exit 1

if pgrep -x optturns >/dev/null; then
    echo "optturns is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "NB the normal sweep uses the same binary name -- check which it is:" >&2
    echo "  ps -Ao pid,command | grep optturns" >&2
    echo "Attach to this sweep's output instead:  tail -F $MATH/$LOC/sweep.log" >&2
    exit 1
fi
[ -x ./solver/optturns ] || { echo "no solver binary -- run 'sh build.sh' in solver/" >&2; exit 1; }
[ -f "$LIST" ]           || { echo "no guess list at $LIST" >&2; exit 1; }

mkdir -p "$(dirname "$OUT")" "$LOC"

# reuse a table snapshot if present, so we resume warm rather than cold.  The TT
# key is salted with the guess set, so a tt.bin from the FULL-list sweep cannot
# be mistaken for one of ours even if it is pointed here by accident.
WARM=""
[ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"

# the timestamped header is what inflight.py uses to find the run boundary
# KEEP THE MACHINE AWAKE.  macOS measures idleness by USER INPUT, not load, so a
# solver pinning every core does NOTHING to prevent sleep.  This Mac sleeps 1
# minute after the display sleeps (10 min on AC), which would suspend the sweep
# mid-run.  `-i` blocks idle SYSTEM sleep while still letting the DISPLAY sleep.
# No-op where caffeinate does not exist (the WSL desktop).
CAFF=""
command -v caffeinate >/dev/null 2>&1 && CAFF="caffeinate -i"

echo "[$(date -Is)] resuming wordle ANSWERS-ONLY sweep (depth 6) $WARM" | tee -a "$LOC/sweep.log"

$CAFF ./solver/optturns --sweep \
    --guess-list "$LIST" \
    --out "$OUT" \
    --trees "$LOC/trees" \
    --depth 6 \
    --tt-bits "$TTBITS" --threads "$THREADS" $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
