"""Build the guess x answer pattern matrix — the central precomputed artifact.

PAT[g, a] = encoded feedback of guess g against answer a.

Shape and dtype depend on which problem is being built:

  python build_patterns.py              # Wordle: 12972 x 2315 uint8, ~30 MB
  python build_patterns.py --full       # all-words: 12972 x 12972 uint8, ~168 MB
  python build_patterns.py --length 7   # hello wordl at 7 letters: 24028 x 5137 uint16

  python build_patterns.py --answer-list PATH --out OUT [--length L]
        # a CUSTOM answer axis: rows = the length's full guess list, columns =
        # exactly the words in PATH, in file order.  Used by the Lingo cell,
        # which needs one small matrix per starting letter (the letter's answers
        # are a subset of the mystery list, and --answer-list in the solver
        # requires a matrix whose COLUMNS match that subset exactly, in order --
        # it is not a runtime column-subset).  Additive and off the default
        # paths, so it cannot touch the shared matrices below.

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


def build_answer_list(answer_list, out, length=None):
    """Build rows = the length's full guess list, columns = the words in
    ``answer_list`` (in file order), and write to ``out`` (+ ``out.meta.json``).

    This is the Lingo per-letter matrix. It reuses the exact same ``pattern_row``
    every other matrix is built with, so it cannot encode feedback differently;
    the one thing it adds is a caller-chosen COLUMN SET and order, which the
    solver's ``--answer-list`` requires to match its answer file byte-for-byte.
    ``tools/checklingo.py`` diffs the result against the shared length matrix to
    prove the columns are the right ones in the right order.
    """
    guesses = load_words("guess", length)
    with open(answer_list) as f:
        answers = [line.strip() for line in f if line.strip()]
    if not answers:
        raise SystemExit("answer list %s is empty" % answer_list)
    word_len = len(guesses[0])
    for w in answers:
        if len(w) != word_len:
            raise SystemExit("answer %r is not %d letters (matrix would be wrong)"
                             % (w, word_len))
    ans_codes = to_codes(answers)
    dtype = pattern_dtype(word_len)
    pat = np.empty((len(guesses), len(answers)), dtype=dtype)
    t0 = time.time()
    for i, g in enumerate(guesses):
        pat[i] = pattern_row(g, ans_codes)
    dt = time.time() - t0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    np.save(out, pat)
    meta = {
        "shape": [len(guesses), len(answers)],
        "guess_words": len(guesses),
        "answer_words": len(answers),
        "word_len": word_len,
        "word_source": "hello" if length is not None else "wordle",
        "answers": os.path.abspath(answer_list),
        "dtype": np.dtype(dtype).name,
        "encoding": f"base-3, pos0=MSB, 0=grey 1=yellow 2=green, "
                    f"ALL_GREEN={3 ** word_len - 1}",
        "build_seconds": round(dt, 2),
        "mb": round(pat.nbytes / 1e6, 2),
    }
    # np.save appends .npy; write the sidecar next to the actual file
    npy = out if out.endswith(".npy") else out + ".npy"
    with open(npy + ".meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {npy}  {meta['mb']} MB  {meta['dtype']}  "
          f"{meta['shape'][0]}x{meta['shape'][1]} in {dt:.2f}s")
    return pat


def load_patterns(full=False, length=None):
    """Load the matrix (mmap'd — reads don't pull the whole file into RAM)."""
    return np.load(_paths(full, length)[0], mmap_mode="r")


def _arg(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


if __name__ == "__main__":
    argv = sys.argv[1:]
    length = None
    if "--length" in argv:
        i = argv.index("--length")
        rest = [int(a) for a in argv[i + 1:] if not a.startswith("-")]
        if not rest:
            raise SystemExit("--length needs at least one word length")
        length = rest

    if "--answer-list" in argv:
        # custom answer axis: a single length only (rows come from one guess list)
        out = _arg(argv, "--out")
        if not out:
            raise SystemExit("--answer-list requires --out PATH")
        one = length[0] if length else None
        if length and len(length) != 1:
            raise SystemExit("--answer-list takes at most one --length")
        build_answer_list(_arg(argv, "--answer-list"), out, length=one)
    elif length:
        for L in length:
            build(length=L)
    else:
        build(full="--full" in argv)
