#!/bin/bash
# Run the top-K Letroso solver attached, with live output in this terminal.
#
#     bash solver/run-letroso-solve.sh --length-prior lengths
#     bash solver/run-letroso-solve.sh --length-prior words -k 3
#
# WHAT THIS MEASURES, precisely: the EXPECTED NUMBER OF GUESSES to finish, over
# the answer list under the chosen LENGTH PRIOR, for a beam that ranks guesses
# by the expected number of candidate WORDS still alive (see
# run-letroso-rank.sh).  math/letroso_topk.py is the source of truth.
#
# THERE IS NO GUESS CAP.  Letroso gives unlimited attempts, so this is expected
# guesses OUTRIGHT -- the same footing as the nerdle, multiwordle and
# adversarial numbers, and NOT the footing of any optturns/hardturns/ansall
# total, which are optima subject to a guarantee.  Never put the two in a table.
#
# IT IS A BEAM, NOT AN OPTIMUM.  `-k K` examines K guesses at EVERY node, the
# ROOT INCLUDED, so the opener is the best of the K examined and not the best of
# all 139072.  Each K is a different strategy and gets its own file.
#
# THE LISTS ARE OURS, NOT LETROSO'S.  Answers and guesses come from hello
# wordl's per-length lists (3-10), with length 3 built by us -- hello's answer
# curation starts at 4.  Letroso's real answer set is server-side and we do not
# have it, so a number here describes THIS game on THESE lists, never
# letroso.com.  See data/shared/words/hello/len3/README.md.
#
# RUN run-letroso-rank.sh FIRST, and this REFUSES until you have.  The root scan
# is ~19 core-hours; without the cached ranking this would silently redo all of
# it inline.  That is not a slow path worth taking quietly -- queue the two
# commands back to back in one terminal and the second starts an independent
# 19-core-hour scan the moment the first ends, which is exactly what happened on
# 2026-09-05.  --force-rescan is there if you really do want it to compute the
# ranking itself.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PRIOR=""
K=1
FORCE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --length-prior) PRIOR="$2"; shift 2 ;;
        -k|--topk)      K="$2";     shift 2 ;;
        --force-rescan) FORCE=1;    shift ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done
[ -n "$PRIOR" ] || { echo "--length-prior is REQUIRED (lengths|words) -- it is part of the objective" >&2; exit 1; }
case "$PRIOR" in lengths|words) ;; *) echo "--length-prior must be lengths or words" >&2; exit 1 ;; esac
case "$K" in ''|*[!0-9]*|0) echo "-k must be a positive number" >&2; exit 1 ;; esac

cd "$MATH" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

OUTDIR=data/shared/letroso
LOC=data/local/letroso
mkdir -p "$OUTDIR" "$LOC"
STEM="solve_${PRIOR}_k${K}"
OUT="$OUTDIR/$STEM.csv"

[ -f data/shared/words/hello/len3/mystery.txt ] || {
    echo "missing the length-3 lists" >&2
    echo "  run: python3 build_letroso_lists.py" >&2; exit 1; }

RANK="$OUTDIR/root_rank_${PRIOR}.csv.gz"
if [ -z "$FORCE" ] && [ ! -f "$RANK" ]; then
    echo "REFUSING: no cached opener ranking at $RANK" >&2
    echo "  Without it this recomputes the whole ~19 core-hour root scan inline," >&2
    echo "  duplicating the work run-letroso-rank.sh exists to do once." >&2
    echo "  Run this first, and let it FINISH:" >&2
    echo "    bash solver/run-letroso-rank.sh --length-prior $PRIOR" >&2
    echo "  (or pass --force-rescan if you really want this to compute it)" >&2
    exit 1
fi

# Both wrappers share ONE checkpoint path per prior, so two concurrent scans
# would write over each other's progress.  Refuse while a rank scan is live.
LIVE=$(pgrep -f "letroso_solve.py .*--rank-only" 2>/dev/null | tr '\n' ' ')
if [ -n "$LIVE" ]; then
    echo "REFUSING: a root-rank scan is already running (pid $LIVE)." >&2
    echo "  Wait for it to finish; this will then read its cached ranking." >&2
    exit 1
fi

. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output letroso_solve.py "$OUT" || exit 1

echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] letroso solve $STEM" | tee -a "$LOC/$STEM.log"
"$PY" -u tools/letroso_solve.py --length-prior "$PRIOR" -k "$K" \
    --out "$OUT" 2>&1 | tee -a "$LOC/$STEM.log"
