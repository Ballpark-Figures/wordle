#!/bin/bash
# The Eldrow longest-stall search, ATTACHED with a tee'd log.
#
#     bash solver/run-eldrow.sh --beam --target 17           # from math/, or anywhere
#     bash solver/run-eldrow.sh --beam --target 12 --words mystery --size 200
#     bash solver/run-eldrow.sh --exact --sample 8           # exact, tiny list
#
# WHAT THIS COMPUTES: the longest NARROWING chain of guesses (guesses drawn from
# the live candidate list) before the set collapses to one word -- either the
# heuristic beam (--beam, a lower bound over a whole list) or the exact branch-and-
# bound (--exact, small lists only). Counts guesses-to-a-singleton, not the final
# naming. Over OUR word lists, not the game's value -- see eldrow.py. The exact
# known-answer endgame counterpart is run-antiwordle-stall.sh; the greedy
# expected-length heuristic is run-antiwordle-greedy.sh.
#
# MODE IS REQUIRED (--beam or --exact): the tool refuses a bare run rather than
# hang on an exact full-list search. Output is unbuffered and appended to a log.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1

LOC=data/local/eldrow
LOG="$LOC/eldrow.log"
mkdir -p "$LOC"

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] eldrow longest-stall search" | tee -a "$LOG"
# `${ARGS[@]+...}` guards the empty-array-under-set-u abort on macOS bash 3.2;
# the tool errors on a missing mode, so an argless run reaches it and is refused.
ARGS=("$@")
python3 tools/eldrow_run.py ${ARGS[@]+"${ARGS[@]}"} 2>&1 | tee -a "$LOG"
