#!/bin/bash
# The antiwordle GREEDY heuristic (uncertainty phase), ATTACHED with a tee'd log.
#
#     bash solver/run-antiwordle-greedy.sh --opener-only     # from math/, or anywhere
#     bash solver/run-antiwordle-greedy.sh --sample 40       # a random 40-answer game
#     bash solver/run-antiwordle-greedy.sh --limit 40        # first 40 answers, list order
#     bash solver/run-antiwordle-greedy.sh --full            # all 2315 -- SLOW recursion
#
# WHAT THIS COMPUTES: the greedy "keep the pool big" player's first guess and,
# unless --opener-only, its expected game length averaged over the answers in
# scope. It is a HEURISTIC's expected length, not the game's value, over OUR word
# lists -- see antiwordle_greedy.py. The exact endgame counterpart is
# run-antiwordle-stall.sh.
#
# SCOPE IS REQUIRED (--opener-only / --sample / --limit / --full): the full
# recursion is slow, so the tool refuses to start without one rather than launch
# it silently. Output is unbuffered to the terminal and appended to a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1

LOC=data/local/antiwordle
LOG="$LOC/greedy.log"
mkdir -p "$LOC"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] antiwordle greedy heuristic" | tee -a "$LOG"
# `${ARGS[@]+...}` guards the empty-array-under-set-u abort on macOS bash 3.2;
# the tool itself errors on no scope, so an argless run reaches it and is refused.
ARGS=("$@")
python3 tools/antigreedy.py ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee -a "$LOG"
