"""Build the guess x answer pattern matrix — the central precomputed artifact.

PAT[g, a] = encoded feedback (0..242) of guess g against answer a, uint8.
Shape (12972, 2315) ~= 30 MB. Deterministic and fully regenerable from the
committed word lists, so it lives in the gitignored math/data/local/ (per the
repo's shared/local split) rather than being committed.

Run:  python build_patterns.py           # writes patterns.npy + meta
      python build_patterns.py --full    # writes patterns_full.npy + meta

`--full` builds the 12972 x 12972 matrix (~168 MB) used by the ALL-WORDS sweep,
where every legal guess is also a possible answer. It is a SEPARATE file, not a
replacement: the 12972 x 2315 default is what the normal, hard and answers-only
sweeps all read, and overwriting it would break them. Both are gitignored.

Reads it back elsewhere with load_patterns() / load_patterns(full=True).
"""

import json
import os
import time

import numpy as np

from wordle import load_words, to_codes, pattern_row

_LOCAL = os.path.join(os.path.dirname(__file__), "data", "local", "patterns")
_PATH = os.path.join(_LOCAL, "patterns.npy")
_FULL_PATH = os.path.join(_LOCAL, "patterns_full.npy")
_META = os.path.join(_LOCAL, "meta.json")
_FULL_META = os.path.join(_LOCAL, "meta_full.json")


def build(full=False):
    guesses = load_words("guess")
    # full: every legal guess is also a possible answer, so the answer axis is
    # the guess list itself and the matrix is square.
    answers = guesses if full else load_words("mystery")
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
    path, metapath = (_FULL_PATH, _FULL_META) if full else (_PATH, _META)
    np.save(path, pat)
    meta = {
        "shape": [n_g, n_a],
        "guess_words": n_g,
        "mystery_words": n_a,
        "answers": "guess" if full else "mystery",
        "dtype": "uint8",
        "encoding": "base-3, pos0=MSB, 0=grey 1=yellow 2=green, ALL_GREEN=242",
        "build_seconds": round(dt, 1),
        "mb": round(pat.nbytes / 1e6, 1),
    }
    with open(metapath, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {path}  {meta['mb']} MB in {dt:.1f}s")
    return pat


def load_patterns(full=False):
    """Load the matrix (mmap'd — reads don't pull the whole file into RAM)."""
    return np.load(_FULL_PATH if full else _PATH, mmap_mode="r")


if __name__ == "__main__":
    import sys
    build(full="--full" in sys.argv)
