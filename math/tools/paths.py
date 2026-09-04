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

`ansturns` is the ANSWERS-ONLY sweep -- the same objective, but every guess must
itself be one of the 2315 answers (`optturns --guess-list mystery.txt`). It is
the ONE name here that is NOT a binary: the process is still called `optturns`,
so the tt* tools cannot find it by process name. Reading its results works
normally; snapshotting its table does not.

    WORDLE_SOLVER=ansturns python3 tools/report.py   # the answers-only sweep

`ansall` is the mirror image of that and the one sweep whose ANSWER set is the
LARGER of the two: the 2315 answers are the only legal guesses, but all 12972
words are possible answers (`optturns --guess-list mystery.txt --answer-list
guess.txt --phantom-final`). The 10657 answers that are not legal guesses are
scored as narrow-to-one plus one. Like `ansturns` it is not a binary, and unlike
any of the others its cap lives in the CSV FILENAME -- see `WORDLE_CSV` below.
"""
import csv
import glob
import os

SOLVER = os.environ.get("WORDLE_SOLVER", "optturns")
if SOLVER not in ("optturns", "hardturns", "ansturns", "ansall"):
    raise SystemExit("WORDLE_SOLVER must be optturns, hardturns, ansturns or "
                     "ansall, not %r" % SOLVER)

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(MATH, "data", "shared", SOLVER)
LOCAL = os.path.join(MATH, "data", "local", SOLVER)

# `ansall` (2315 guesses, all 12972 words as answers) pins its CAP in the
# FILENAME, because the cap is part of the objective there and a depth-7 pass and
# a depth-8 pass are different quantities that must never share a file. So it has
# no single canonical CSV and the reader has to be told which one:
#     WORDLE_SOLVER=ansall WORDLE_CSV=data/shared/ansall/opener_totals_d7.csv ...
# The override is general, and unset everywhere else, so the other three sweeps
# read exactly the file they always did.
CSV_PATH = os.environ.get("WORDLE_CSV") or os.path.join(SHARED, "opener_totals.csv")
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

# FULL_GUESS_WORDS is the 12972-word list the pattern matrix ROWS are indexed by
# -- always this file, whatever the sweep. GUESS_WORDS is the OPENER SET of the
# sweep being read, which for ansturns is the answers. A reader that wants a
# pattern row for a word from a restricted set must map it through
# FULL_GUESS_WORDS first; the two differ exactly when a --guess-list is in play.
FULL_GUESS_WORDS = os.path.join(MATH, "data", "shared", "words", "guess.txt")
MYSTERY_WORDS = os.path.join(MATH, "data", "shared", "words", "mystery.txt")

# ansall INVERTS the usual containment: its guesses are the 2315 and its ANSWERS
# are all 12972 words, so it is the one sweep whose answer set is the bigger of
# the two and whose pattern matrix is the SQUARE one.
ANSWER_WORDS = FULL_GUESS_WORDS if SOLVER == "ansall" else MYSTERY_WORDS
GUESS_WORDS = MYSTERY_WORDS if SOLVER in ("ansturns", "ansall") else FULL_GUESS_WORDS
PATTERNS = os.path.join(MATH, "data", "local", "patterns",
                        "patterns_full.npy" if SOLVER == "ansall" else "patterns.npy")

N_ANSWERS = 12972 if SOLVER == "ansall" else 2315

# How many openers a sweep covers -- the DENOMINATOR for every progress figure.
# It is the size of the sweep's GUESS SET, because --sweep enumerates exactly the
# legal guesses. The answers-only sweep restricts that set to the answers, so it
# has 2315 openers to get through, not 12972; using the wrong one here understates
# its progress by 5.6x.
N_GUESSES = 2315 if SOLVER in ("ansturns", "ansall") else 12972


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
