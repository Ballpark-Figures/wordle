#!/bin/bash
# Score every Letroso opener against every answer, once, and cache the ranking.
#
#     bash solver/run-letroso-rank.sh --length-prior lengths
#
# WHAT THIS COMPUTES.  For each of the 139072 legal guesses, the expected number
# of candidate WORDS still alive after playing it:
#
#     score(g) = SUM over feedback bins b != the winning bin of  n_b * W_b
#
# ascending, ties on the lowest guess index.  That is topk.py's rule -- the one
# the adversarial hill-climb uses -- and it is used here rather than sum of
# squared bin sizes because the answers are NOT equally likely under a length
# prior.  math/letroso_topk.py is the source of truth.
#
# IT IS A RANKING, NOT A RESULT.  A good first-guess score says nothing about
# what happens after the reply.  Quote the solver's number, not this one.
#
# --length-prior IS REQUIRED and has no default.  Letroso's answer length varies
# and we do not know how the game picks it, so `lengths` (uniform over the 8
# lengths) and `words` (uniform over the pooled list) are DIFFERENT OBJECTIVES
# with different optima.  Each gets its own file.
#
# COST.  4.23e9 feedback evaluations, each an LCS alignment DP rather than a
# symbol compare -- measured 15.9 us, so about 19 core-hours, under an hour on
# 20 threads.  The run is chunked so Ctrl-C works and progress prints; an
# interrupt leaves NO partial file, the save happens only on completion.
#
# The cached ranking carries a FINGERPRINT over both word lists and the prior.
# A mismatch is REFUSED, never used -- a foreign ranking would make every score
# confidently wrong rather than missing.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PRIOR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --length-prior) PRIOR="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done
[ -n "$PRIOR" ] || { echo "--length-prior is REQUIRED (lengths|words) -- it is part of the objective" >&2; exit 1; }
case "$PRIOR" in lengths|words) ;; *) echo "--length-prior must be lengths or words" >&2; exit 1 ;; esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/letroso
LOC=data/local/letroso
mkdir -p "$OUTDIR" "$LOC"
STEM="root_rank_${PRIOR}"

[ -f data/shared/words/hello/len3/mystery.txt ] || {
    echo "missing the length-3 lists" >&2
    echo "  run: python3 build_letroso_lists.py" >&2; exit 1; }

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output letroso_solve.py "$OUTDIR/$STEM.csv.gz" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] letroso rank $STEM" | tee -a "$LOC/$STEM.log"
"$PY" -u tools/letroso_solve.py --length-prior "$PRIOR" --rank-only \
    --out "$OUTDIR/${STEM}_top.csv" 2>&1 | tee -a "$LOC/$STEM.log"
