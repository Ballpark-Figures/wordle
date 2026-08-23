"""Canonical locations for the optturns / hardturns sweeps, in one place.

Follows the repo data convention: results meant to sync between machines live in
`math/data/shared/<solver>/` (committed); regenerable bulk lives in
`math/data/local/<solver>/` (gitignored). Import from here rather than
hardcoding paths, so a layout change is a one-line edit.

There are two sweeps -- normal Wordle (`optturns`) and hard mode (`hardturns`) --
with identical layouts under their own directory. `WORDLE_SOLVER` picks which
one every tool reads, defaulting to `optturns` so existing invocations are
unchanged:

    python3 tools/report.py                          # the normal sweep
    WORDLE_SOLVER=hardturns python3 tools/report.py  # the hard-mode sweep

The name doubles as the BINARY name (`solver/optturns`, `solver/hardturns`), so
the same variable also tells the tt* tools which process to snapshot.
"""
import csv
import glob
import os

SOLVER = os.environ.get("WORDLE_SOLVER", "optturns")
if SOLVER not in ("optturns", "hardturns"):
    raise SystemExit("WORDLE_SOLVER must be optturns or hardturns, not %r" % SOLVER)

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(MATH, "data", "shared", SOLVER)
LOCAL = os.path.join(MATH, "data", "local", SOLVER)

CSV_PATH = os.path.join(SHARED, "opener_totals.csv")
ARCHIVE = os.path.join(LOCAL, "archive")
TREES = os.path.join(LOCAL, "trees")
LOG = os.path.join(LOCAL, "sweep.log")
TT_BIN = os.path.join(LOCAL, "tt.bin")

GUESS_WORDS = os.path.join(MATH, "data", "shared", "words", "guess.txt")
PATTERNS = os.path.join(MATH, "data", "local", "patterns", "patterns.npy")

N_ANSWERS = 2315
N_GUESSES = 12972


def load_totals(include_archive=True):
    """word -> total guesses, deduped across the live CSV and any archived runs.

    Archived runs are supersets-in-progress of earlier attempts, so later files
    win; the live CSV is read last. Rows without a total are INFEASIBLE openers
    and are skipped here -- see load_infeasible() for those.

    In the NORMAL sweep none exist: any opener can win within 6 by playing
    SALET's tree after it. That argument does NOT carry to hard mode, where the
    follow-up is restricted to guesses reusing the revealed hints, so hardturns
    can and does produce genuine INFEASIBLE rows.
    """
    paths = sorted(glob.glob(os.path.join(ARCHIVE, "opener_totals*.csv"))) if include_archive else []
    paths.append(CSV_PATH)
    rows = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for r in csv.DictReader(f):
                if r.get("word") and r.get("total"):
                    rows[r["word"]] = int(r["total"])
    return rows


def load_infeasible(include_archive=True):
    """Openers with a CSV row but no total: no strategy wins within --depth.

    Empty for the normal sweep by construction (any opener can follow SALET's
    tree); a real, expected outcome for hard mode, where the follow-up must
    keep reusing the revealed hints. Read alongside load_totals() so a sweep's
    progress counts solved + infeasible, not solved alone.
    """
    paths = sorted(glob.glob(os.path.join(ARCHIVE, "opener_totals*.csv"))) if include_archive else []
    paths.append(CSV_PATH)
    out = set()
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for r in csv.DictReader(f):
                if r.get("word") and not r.get("total"):
                    out.add(r["word"])
    return out


def load_depths(include_archive=True):
    """word -> the guess cap that opener actually needed.

    hardturns escalates the cap per opener until the opener solves, and records
    the depth it landed on. Normal Wordle uses one fixed cap, so every row there
    reads 6 (or the column is absent on pre-2026-08-23 files, which yield {}).

    NB this is the minimum FEASIBLE depth, and the paired total is optimal only
    SUBJECT TO it -- a deeper cap may admit a lower total. Seeding a stabilisation
    pass from (total, depth) is what this is for; see the bound/cap rule in the
    shared CLAUDE.md.
    """
    paths = sorted(glob.glob(os.path.join(ARCHIVE, "opener_totals*.csv"))) if include_archive else []
    paths.append(CSV_PATH)
    out = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p) as f:
            for r in csv.DictReader(f):
                if r.get("word") and r.get("depth"):
                    out[r["word"]] = int(r["depth"])
    return out
