#!/bin/bash
# Enumerate the FREE-STANDING GREEN TEMPLATES that pin a single word --
# attached, with live output in this terminal.
#
#     bash solver/run-green-templates.sh                   # from math/, or anywhere
#     bash solver/run-green-templates.sh --pool guesses
#     bash solver/run-green-templates.sh --greens 3
#     bash solver/run-green-templates.sh --pool guesses --require any
#
# THE TWO CASES ASKED FOR:
#
#     bash solver/run-green-templates.sh --pool answers     # unique among the 2315
#     bash solver/run-green-templates.sh --pool guesses     # unique among the 12972,
#                                                           # and that word is an answer
#
# WHAT THIS COMPUTES, precisely:
#
#   A TEMPLATE is N positions and a letter for each -- `.a..e` means "position 2
#   is a, position 5 is e".  This enumerates every one of them (C(5,N) position
#   sets x 26^N letter assignments) and reports those matching EXACTLY ONE word.
#
#   THE GREENS ARE FREE-STANDING, NOT A GUESS'S FEEDBACK.  The other positions
#   are entirely UNCONSTRAINED: the template asserts nothing about them, so there
#   are no greys, no yellows and no repeated-letter rule, and wordle.pattern is
#   not involved.  "A real board showing exactly N greens" is a DIFFERENT and
#   smaller question -- that board also carries the guess's greys and yellows.
#
#   TWO AXES, BOTH PART OF THE QUESTION.  --pool says which list uniqueness is
#   judged over: `answers` (the 2315 curated answers) or `guesses` (all 12972
#   legal words).  Those are different quantities -- `guesses` is strictly
#   harder, since every answer is a legal guess, so pinning one word of 12972
#   necessarily pins one of 2315.  --require is a SEPARATE axis and changes no
#   count: `answer` keeps only the rows whose word is a mystery answer, `any`
#   keeps them all, exactly as run-maxbucket.sh's --rank restricts its rows.
#   --greens is part of the question too: a 2-green result and a 3-green result
#   are different quantities and get different files.
#
#   Nothing searches or samples: a pure function of the committed word lists, so
#   it is exact, has no standard error, and a re-run reproduces its file byte for
#   byte.  It reads no pattern matrix, so it runs on a fresh clone.
#
#   THE GATE IS BUILT IN and always runs: the whole result is recomputed
#   EXHAUSTIVELY from the STRINGS by a dict of letter tuples (no codes, no
#   bincount, no index arithmetic) and demanded equal template for template;
#   sampled rows are re-verified by scanning the entire pool with plain string
#   comparison; under --pool guesses the survivors must be a subset of the
#   answer-pool ones.  A coverage tally FAILS if nothing was pinned or if the
#   guess pool never dropped a template the answer pool would have kept.  It
#   exits nonzero rather than reporting.
#
# USE THIS RATHER THAN CALLING tools/green_templates.py DIRECTLY.  The tool
# refuses to run without --out and refuses to pick any of the three axes for you;
# this forwards all three EXPLICITLY, so each decision has one owner, and it tees
# a log naming the run.
#
# Outputs data/shared/greentemplates/green_g<N>_<pool>_<require>.csv, columns
# template,positions,letters,word -- positions 1-indexed and hyphen-joined.
# Log under data/local/greentemplates/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults a HUMAN reads, forwarded explicitly -- never ones the program falls
# back on: tools/green_templates.py refuses to run if any is missing.
GREENS=2
POOL=answers
REQUIRE=answer
TOP=20

while [ $# -gt 0 ]; do
    case "$1" in
        --greens)  GREENS="$2";  shift 2 ;;
        --pool)    POOL="$2";    shift 2 ;;
        --require) REQUIRE="$2"; shift 2 ;;
        --top)     TOP="$2";     shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$POOL" in
    answers|guesses) ;;
    *) echo "--pool must be 'answers' (the 2315) or 'guesses' (the 12972)" >&2
       exit 1 ;;
esac
case "$REQUIRE" in
    answer|any) ;;
    *) echo "--require must be 'answer' (keep only rows whose word is a mystery answer) or 'any'" >&2
       exit 1 ;;
esac
case "$GREENS" in
    ''|*[!0-9]*) echo "--greens must be a positive integer" >&2; exit 1 ;;
esac
if [ "$GREENS" -lt 1 ] || [ "$GREENS" -gt 5 ]; then
    echo "--greens must be between 1 and 5" >&2
    exit 1
fi

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

STEM=green_g${GREENS}_${POOL}_${REQUIRE}
OUT=data/shared/greentemplates/${STEM}.csv

MARKER="green_templates.py --pool $POOL --require $REQUIRE --greens $GREENS"
RUNNING=$(pgrep -f -- "$MARKER" 2>/dev/null | tr '\n' ' ')
if [ -n "$RUNNING" ]; then
    echo "REFUSING: the same run is already going (pid $RUNNING)." >&2
    echo "  Two copies would write $OUT at once." >&2
    exit 1
fi

LOC=data/local/greentemplates
mkdir -p "$LOC" data/shared/greentemplates

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] green-templates: greens=$GREENS pool=$POOL require=$REQUIRE" \
    | tee -a "$LOC/${STEM}.log"

"$PY" -u tools/green_templates.py --pool "$POOL" --require "$REQUIRE" \
    --greens "$GREENS" --top "$TOP" --out "$OUT" 2>&1 \
    | tee -a "$LOC/${STEM}.log"
