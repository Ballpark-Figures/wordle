"""Build the guess x answer pattern matrix — the central precomputed artifact.

PAT[g, a] = encoded feedback of guess g against answer a.

Shape and dtype depend on which problem is being built:

  python build_patterns.py              # Wordle: 12972 x 2315 uint8, ~30 MB
  python build_patterns.py --full       # all-words: 12972 x 12972 uint8, ~168 MB
  python build_patterns.py --length 7   # hello wordl at 7 letters: 24028 x 5137 uint16

`--full` is a SEPARATE file, not a replacement: the 12972 x 2315 default is what
the normal, hard and answers-only sweeps all read, and overwriting it would
break them.

`--length L` builds from the hello wordl lists (see build_wordlists.py) rather
than the Wordle ones, into its own `patterns_len<L>.npy`. NOTE `--length 5` is
NOT the default build: it is hello's 12971 x 3238, a different curation from the
Wordle 12972 x 2315, and the two files are deliberately kept apart.

DTYPE IS NOT ALWAYS uint8. There are 3**L codes, so L=5 fits in uint8 but L>=6
needs uint16 and L=11 needs uint32 (`wordle.pattern_dtype`). The C solver picks
the same rule from its compile-time WORDLEN and REJECTS a matrix whose dtype
disagrees, so the two cannot silently drift.

All outputs are deterministic and fully regenerable from the committed word
lists, so they live in the gitignored math/data/local/ per the repo's
shared/local split.

Reads them back with load_patterns() / load_patterns(full=True) /
load_patterns(length=L).
"""

import json
import os
import sys
import time

import numpy as np

from wordle import load_words, pattern_dtype, pattern_row, to_codes

_LOCAL = os.path.join(os.path.dirname(__file__), "data", "local", "patterns")
_PATH = os.path.join(_LOCAL, "patterns.npy")
_FULL_PATH = os.path.join(_LOCAL, "patterns_full.npy")
_META = os.path.join(_LOCAL, "meta.json")
_FULL_META = os.path.join(_LOCAL, "meta_full.json")


def _paths(full=False, length=None):
    if length is not None:
        return (os.path.join(_LOCAL, f"patterns_len{length}.npy"),
                os.path.join(_LOCAL, f"meta_len{length}.json"))
    return (_FULL_PATH, _FULL_META) if full else (_PATH, _META)


def build(full=False, length=None):
    guesses = load_words("guess", length)
    # full: every legal guess is also a possible answer, so the answer axis is
    # the guess list itself and the matrix is square.
    answers = guesses if full else load_words("mystery", length)
    ans_codes = to_codes(answers)
    n_g, n_a = len(guesses), len(answers)
    word_len = len(guesses[0])
    dtype = pattern_dtype(word_len)

    pat = np.empty((n_g, n_a), dtype=dtype)
    t0 = time.time()
    for i, g in enumerate(guesses):
        pat[i] = pattern_row(g, ans_codes)
        if i % 2000 == 0:
            print(f"  {i}/{n_g}  ({time.time() - t0:.1f}s)")
    dt = time.time() - t0

    os.makedirs(_LOCAL, exist_ok=True)
    path, metapath = _paths(full, length)
    np.save(path, pat)
    meta = {
        "shape": [n_g, n_a],
        "guess_words": n_g,
        "mystery_words": n_a,
        "word_len": word_len,
        "word_source": "hello" if length is not None else "wordle",
        "answers": "guess" if full else "mystery",
        "dtype": np.dtype(dtype).name,
        "encoding": f"base-3, pos0=MSB, 0=grey 1=yellow 2=green, "
                    f"ALL_GREEN={3 ** word_len - 1}",
        "build_seconds": round(dt, 1),
        "mb": round(pat.nbytes / 1e6, 1),
    }
    with open(metapath, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {path}  {meta['mb']} MB  {meta['dtype']}  in {dt:.1f}s")
    return pat


def load_patterns(full=False, length=None):
    """Load the matrix (mmap'd — reads don't pull the whole file into RAM)."""
    return np.load(_paths(full, length)[0], mmap_mode="r")


if __name__ == "__main__":
    argv = sys.argv[1:]
    lengths = []
    if "--length" in argv:
        i = argv.index("--length")
        lengths = [int(a) for a in argv[i + 1:] if not a.startswith("-")]
        if not lengths:
            raise SystemExit("--length needs at least one word length")
    if lengths:
        for length in lengths:
            build(length=length)
    else:
        build(full="--full" in argv)
