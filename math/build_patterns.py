"""Build the guess x answer pattern matrix — the central precomputed artifact.

PAT[g, a] = encoded feedback (0..242) of guess g against answer a, uint8.
Shape (12972, 2315) ~= 30 MB. Deterministic and fully regenerable from the
committed word lists, so it lives in the gitignored math/data/local/ (per the
repo's shared/local split) rather than being committed.

Run:  python build_patterns.py           # writes patterns.npy + meta
Reads it back elsewhere with load_patterns().
"""

import json
import os
import time

import numpy as np

from wordle import load_words, to_codes, pattern_row

_LOCAL = os.path.join(os.path.dirname(__file__), "data", "local", "patterns")
_PATH = os.path.join(_LOCAL, "patterns.npy")
_META = os.path.join(_LOCAL, "meta.json")


def build():
    guesses = load_words("guess")
    answers = load_words("mystery")
    ans_codes = to_codes(answers)
    n_g, n_a = len(guesses), len(answers)

    pat = np.empty((n_g, n_a), dtype=np.uint8)
    t0 = time.time()
    for i, g in enumerate(guesses):
        pat[i] = pattern_row(g, ans_codes)
        if i % 2000 == 0:
            print(f"  {i}/{n_g}  ({time.time() - t0:.1f}s)")
    dt = time.time() - t0

    os.makedirs(_LOCAL, exist_ok=True)
    np.save(_PATH, pat)
    meta = {
        "shape": [n_g, n_a],
        "guess_words": n_g,
        "mystery_words": n_a,
        "dtype": "uint8",
        "encoding": "base-3, pos0=MSB, 0=grey 1=yellow 2=green, ALL_GREEN=242",
        "build_seconds": round(dt, 1),
        "mb": round(pat.nbytes / 1e6, 1),
    }
    with open(_META, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {_PATH}  {meta['mb']} MB in {dt:.1f}s")
    return pat


def load_patterns():
    """Load the matrix (mmap'd — reads don't pull all 30 MB into RAM)."""
    return np.load(_PATH, mmap_mode="r")


if __name__ == "__main__":
    build()
