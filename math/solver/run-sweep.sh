#!/bin/bash
# Start the optturns sweep ATTACHED, with live output in this terminal.
#
# This is the DEFAULT way to launch when you are at the machine: the solver runs
# in the foreground so you watch completions scroll by directly.  ~/bin/resume-
# jobs.sh is the OTHER path -- detached via nohup, wired to a Windows Scheduled
# Task, for recovering an unattended reboot.  Same flags either way.
#
#     bash solver/run-sweep.sh        # from math/, or from anywhere
#
# A PINNED CAP gets its own files and is a DIFFERENT QUANTITY:
#
#     bash solver/run-sweep.sh --depth 5 --depth-max 5
#
# With no --depth this is the historic depth-6 sweep, unchanged: same command
# line, same opener_totals.csv, same trees/ directory, same resume.  See "WHERE
# THE RESULTS GO" below for why a pinned cap must not share them.
#
# solver/run-hard-sweep.sh is the HARD-MODE companion (solver/hardturns, its own
# data/{shared,local}/hardturns/ directory).  It takes a phase argument, because
# it is designed to start while THIS sweep still owns the machine and then take
# over from it -- see "Hard mode" in README.md.  The pinned-cap handling here is
# that wrapper's, ported: one rule, two files.
#
# Output is tee'd, so sweep.log gets every line as well as your terminal.  That
# matters: tools/report.py and tools/inflight.py PARSE that log for the run's
# start time, resume count and elapsed seconds.  Run the binary bare, with no
# tee, and the IN FLIGHT section silently reports the PREVIOUS run's numbers.
#
# Ctrl-C stops the sweep.  Finished words are already in the CSV (flushed per
# word), but the transposition table is lost -- there is no save on SIGINT.  To
# keep the table, snapshot it FIRST with tools/ttdump.py while the solver is
# still live; see "Saving / restoring the table" in README.md.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHR=data/shared/optturns
LOC=data/local/optturns

cd "$MATH" || exit 1

DEPTH=6          # optturns' own default; the historic sweep's cap
DEPTHMAX=-1      # -1 means "leave it to the binary", which pins it to DEPTH
DRYRUN=0
TOPK=0           # 0 is the exact search; >0 is a one-sided FEASIBILITY SCREEN

while [ $# -gt 0 ]; do
    case "$1" in
        --depth)     DEPTH=$2;    shift 2 ;;
        --depth-max) DEPTHMAX=$2; shift 2 ;;
        --topk|-k)   TOPK=$2;     shift 2 ;;
        --dry-run)   DRYRUN=1;    shift ;;
        *) echo "unknown arg: $1" >&2
           echo "usage: bash solver/run-sweep.sh [--depth N] [--depth-max N] [-k K] [--dry-run]" >&2
           exit 1 ;;
    esac
done
[ "$DEPTHMAX" = "-1" ] && DEPTHMAX=$DEPTH

# WHERE THE RESULTS GO, and why a PINNED cap gets its own files.  This is
# run-hard-sweep.sh's rule, ported verbatim, and it is load-bearing in exactly
# the same way -- more so here, because the depth-6 sweep is FINISHED.  Resume
# reads the CSV to skip openers already done, so a depth-5 run pointed at
# opener_totals.csv would find all 12972 present, skip every one, and exit
# having measured NOTHING; its trees would meanwhile overwrite the committed
# depth-6 set.  So a cap other than the historic 6 gets its own CSV and its own
# tree directory, exactly as ansall gives each --depth its own file.
#
# NORMAL MODE DOES NOT ESCALATE: optturns.c line 3018 reads
#     if (depthmax < 0) depthmax = HARD ? MAXD - 1 : depth;
# so --depth 5 alone already pins the cap at 5.  --depth-max is accepted and
# forwarded so the command reads the same as the hard-mode one, not because the
# binary needs it.
#
# sweep.log is deliberately NOT stamped -- tools/paths.py hardcodes LOG, so a
# per-depth log would make report.py read the wrong run.  The CSV and trees are
# reachable with the overrides paths.py already provides, printed below.
#
# -k K IS PART OF THE OBJECTIVE, so it joins the stem exactly as every other
# beamed sweep here does (wturns' optimal_<stem>_d<D>_k<K>.csv, mmturns' one
# file set per (depth, K)).  Without it a screen and the exact run would share
# a CSV at the same depth -- and since one holds upper bounds and the other
# optima, resume would read each as the other's finished work.
SUF=""
[ "$DEPTH" = 6 ] && [ "$DEPTHMAX" = 6 ] || SUF="_d$DEPTH"
[ "$TOPK" -gt 0 ] && SUF="${SUF}_k$TOPK"
if [ -z "$SUF" ]; then
    OUT="$SHR/opener_totals.csv"
    TRE="$LOC/trees"
else
    OUT="$SHR/opener_totals$SUF.csv"
    TRE="$LOC/trees$SUF"
fi

if pgrep -x optturns >/dev/null; then
    echo "optturns is already running (pid $(pgrep -x optturns | tr '\n' ' '))." >&2
    echo "Attach to its output instead:  tail -F $MATH/$LOC/sweep.log" >&2
    exit 1
fi
[ -x ./solver/optturns ] || { echo "no solver binary -- run 'sh build.sh' in solver/" >&2; exit 1; }

# The historic sweep RESUMES an existing file and refuses without one, which is
# the guard that catches a mistyped path.  A pinned cap is a new quantity with
# no file yet, so it only needs the directories -- the solver writes the CSV
# header itself on the run that finds no resumable rows.
if [ "$OUT" = "$SHR/opener_totals.csv" ]; then
    [ -f "$OUT" ] || { echo "no $OUT to resume from" >&2; exit 1; }
fi

# reuse a table snapshot if present, so we resume warm rather than cold.
#
# NOT UNDER -k: TOPK is in the TT salt (optturns.c:3149), so every key a beamed
# run computes differs from every key in the exact tt.bin.  Loading it would
# spend 24s and 17.18 GB to achieve a 0% hit rate, which reads as "the warm
# start stopped working" rather than as the salt doing its job.
WARM=""
if [ "$TOPK" -gt 0 ]; then
    [ -f "$LOC/tt.bin" ] && echo "note: skipping $LOC/tt.bin -- -k salts the TT, so it could not hit"
else
    [ -f "$LOC/tt.bin" ] && WARM="--tt-load $LOC/tt.bin"
fi

echo "writing  csv:   $MATH/$OUT"
echo "         trees: $MATH/$TRE"
echo "         log:   $MATH/$LOC/sweep.log"
if [ "$OUT" != "$SHR/opener_totals.csv" ]; then
    echo "cap PINNED at $DEPTH -- INFEASIBLE is an expected result, not a failure."
    echo "read it with:  WORDLE_CSV=$OUT WORDLE_TREES=$TRE python3 tools/report.py"
fi
if [ "$TOPK" -gt 0 ]; then
    echo "-k $TOPK: ONE-SIDED FEASIBILITY SCREEN."
    echo "  a row WITH a total   = a strategy was found -> PROVEN solvable in $DEPTH"
    echo "  INFEASIBLE           = the beam failed -> NO EVIDENCE, needs the exact run"
    echo "  totals are UPPER BOUNDS, not optima -- do not read them as depth-$DEPTH minima"
fi

# --dry-run resolves everything and stops BEFORE the solver starts and before
# anything is appended to sweep.log.  Checking this wrapper's plumbing must not
# cost a sweep: a partial CSV from a "quick check" is indistinguishable from a
# real result that died, and the log header would move the run boundary that
# inflight.py reads.
KFLAG=""
[ "$TOPK" -gt 0 ] && KFLAG="--topk $TOPK"

if [ "$DRYRUN" = 1 ]; then
    echo "would run: ./solver/optturns --sweep --out $OUT --trees $TRE" \
         "--depth $DEPTH --depth-max $DEPTHMAX $KFLAG --tt-bits 29 --threads 20 $WARM"
    echo "(--dry-run: nothing started, nothing written)"
    exit 0
fi

# AFTER the dry-run exit, or "nothing written" would be a lie -- mkdir -p above
# it silently created trees_d5 on the first --dry-run of this change.  Only the
# DIRECTORIES: the solver writes the CSV header itself, on the run that finds no
# resumable rows, and writing one here too produces a duplicate.
mkdir -p "$(dirname "$OUT")" "$TRE"

# the timestamped header is what inflight.py uses to find the run boundary
# PORTABLE TIMESTAMP, and NOT run-greens.sh's form -- run-hard-sweep.sh carries
# the full reasoning.  `date -Is` is a GNU-ism that prints nothing on macOS, so
# this header came out as `[] resuming` there, and inflight.py finds the
# boundary with  \[(\d{4}-\d\d-\d\dT[\d:+-]+)\] resuming , which that does not
# match.  %z gives -0400, which does, and is the same shape GNU's -Is already
# wrote -- so every log already on the desktop still parses.
echo "[$(date +%Y-%m-%dT%H:%M:%S%z)] resuming wordle sweep (depth=$DEPTH..$DEPTHMAX) $WARM" \
    | tee -a "$LOC/sweep.log"

# --trees stays on under -k: a witness tree is what makes "proven feasible"
# CHECKABLE (tools/checktrees.py replays it) rather than asserted, and one
# gzip write is nothing beside the search that produced it.
./solver/optturns --sweep \
    --out "$OUT" \
    --trees "$TRE" \
    --depth "$DEPTH" --depth-max "$DEPTHMAX" $KFLAG \
    --tt-bits 29 --threads 20 $WARM \
    2>&1 | tee -a "$LOC/sweep.log"
