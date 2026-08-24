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
SHARED_TREES = os.path.join(SHARED, "trees")
LOCAL_TREES = os.path.join(LOCAL, "trees")


def _resolve_trees():
    """Pick the tree directory to READ from, preferring the live working copy.

    The emitted trees exist in up to two places. `local/<solver>/trees/` is where
    a RUNNING solver writes (its `--trees` flag), so on a sweep machine it is the
    live, complete set. `shared/<solver>/trees/` is the COMMITTED copy that syncs
    between machines -- the only one present on a machine that does no data
    generation, and on a sweep machine a possibly-stale snapshot of local.

    So prefer LOCAL whenever it actually holds trees, and fall back to SHARED.
    Preferring shared would silently report on a stale snapshot on the very
    machine that has the live one. `WORDLE_TREES` overrides with an explicit path.
    """
    override = os.environ.get("WORDLE_TREES")
    if override:
        return override
    if glob.glob(os.path.join(LOCAL_TREES, "*.txt.gz")):
        return LOCAL_TREES
    return SHARED_TREES


TREES = _resolve_trees()
LOG = os.path.join(LOCAL, "sweep.log")
TT_BIN = os.path.join(LOCAL, "tt.bin")

GUESS_WORDS = os.path.join(MATH, "data", "shared", "words", "guess.txt")
PATTERNS = os.path.join(MATH, "data", "local", "patterns", "patterns.npy")

N_ANSWERS = 2315
N_GUESSES = 12972


# The results CSV is APPENDED TO by a live solver, and its schema gained a
# `depth` column on 2026-08-24, so one file can legitimately carry more than one
# header line. csv.DictReader trusts line 1 -- which then silently MISALIGNS
# every column after the change (reading `depth` as `seconds`). Every reader here
# goes through read_rows instead: it keys each row off its OWN width, so old and
# new rows in the same file both parse correctly. Do not reintroduce a bare
# DictReader on these files.
_SCHEMAS = {
    5: ("word", "total", "expected", "depth", "seconds"),
    4: ("word", "total", "expected", "seconds"),          # pre-depth rows
}


def read_rows(path):
    """Yield result rows as dicts, tolerating repeated or stale header lines."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for parts in csv.reader(f):
            if not parts or parts[0] == "word":
                continue                      # a header, wherever it sits
            cols = _SCHEMAS.get(len(parts))
            if not cols:
                continue                      # torn by a concurrent append
            yield dict(zip(cols, parts))


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _result_files(include_archive=True):
    """Archived runs first (later files win), the live CSV last."""
    paths = sorted(glob.glob(os.path.join(ARCHIVE, "opener_totals*.csv"))) if include_archive else []
    paths.append(CSV_PATH)
    return paths


def load_totals(include_archive=True):
    """word -> total guesses, deduped across the live CSV and any archived runs.

    Archived runs are supersets-in-progress of earlier attempts, so later files
    win; the live CSV is read last. Rows without a total are INFEASIBLE openers
    and are skipped here -- see load_infeasible() for those.

    In the NORMAL sweep none exist: any opener can win within 6 by playing
    SALET's tree after it. That argument does NOT carry to hard mode, where the
    follow-up is restricted to guesses reusing the revealed hints -- which is why
    hardturns ESCALATES its cap per opener instead of using a fixed one, so an
    INFEASIBLE row there means it failed even at --depth-max.
    """
    rows = {}
    for p in _result_files(include_archive):
        for r in read_rows(p):
            t = _int(r.get("total"))
            if t is not None:
                rows[r["word"]] = t
    return rows


def load_infeasible(include_archive=True):
    """Openers with a CSV row but no total: no strategy wins within the cap.

    Empty for the normal sweep by construction. For hardturns, which escalates
    the cap per opener, a row here means the opener failed even at --depth-max.
    """
    out = set()
    for p in _result_files(include_archive):
        for r in read_rows(p):
            if not r.get("total"):
                out.add(r["word"])
    return out


def load_depths(include_archive=True):
    """word -> the guess cap that opener actually needed.

    hardturns escalates the cap per opener until the opener solves, and records
    the depth it landed on. Normal Wordle uses one fixed cap, so every row there
    reads 6 (pre-2026-08-24 files have no depth column and yield {}).

    NB this is the minimum FEASIBLE depth, and the paired total is optimal only
    SUBJECT TO it -- a deeper cap may admit a lower total. Seeding a stabilisation
    pass from (total, depth) is what this is for; see the bound/cap rule in the
    shared CLAUDE.md.
    """
    out = {}
    for p in _result_files(include_archive):
        for r in read_rows(p):
            d = _int(r.get("depth"))
            if d is not None:
                out[r["word"]] = d
    return out


def load_times(include_archive=False):
    """word -> (seconds, total). Live CSV only by default: archived runs used
    older code, so their timings are not comparable."""
    out = {}
    for p in _result_files(include_archive):
        for r in read_rows(p):
            t = _int(r.get("total"))
            try:
                secs = float(r.get("seconds"))
            except (TypeError, ValueError):
                continue
            if t is not None:
                out[r["word"]] = (secs, t)
    return out
