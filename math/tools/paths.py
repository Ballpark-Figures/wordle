"""Canonical locations for the optturns sweep, in one place.

Follows the repo data convention: results meant to sync between machines live in
`math/data/shared/<solver>/` (committed); regenerable bulk lives in
`math/data/local/<solver>/` (gitignored). Import from here rather than
hardcoding paths, so a layout change is a one-line edit.
"""
import csv
import glob
import os

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(MATH, "data", "shared", "optturns")
LOCAL = os.path.join(MATH, "data", "local", "optturns")

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
    win; the live CSV is read last. Rows without a total (an INFEASIBLE opener)
    are skipped -- none exist in practice, since any opener can win within 6 by
    playing SALET's tree after it.
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
