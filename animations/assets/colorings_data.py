"""The colorings scene 05 marks — which are impossible, which TRACE produces — cached.

Scene 05 lays out all 3**5 = 243 colorings, singles out the impossible ones, then
marks the ones TRACE can produce. Which colorings those are is a computed quantity,
so this module takes it from the pipeline (`math/wordle.py`, and the pattern matrix
`build_patterns.py` writes) and writes `colorings_cache.json`; the SCENE reads the
cache, so a render imports no solver and needs no matrix.

Regenerate (from this directory):

    ../../.venv/bin/python colorings_data.py

It needs `math/data/local/patterns/patterns.npy` (gitignored — `python3
build_patterns.py` from `math/` rebuilds it in ~2s).

Provenance:
  impossible   — the codes that appear NOWHERE in patterns.npy, i.e. no legal guess
                 against any possible answer produces them (12972 x 2315). Asserted
                 to be exactly the five "4 greens + 1 yellow" codes, the reason the
                 voiceover gives, derived here independently from the tiles.
  n_valid      — 243 minus those: the voiceover's 238, asserted.
  trace        — the codes pattern("trace", a) takes over the 2315 answers, sorted.
                 Its count is asserted equal to TRACE's `buckets` in the committed
                 maxbucket_mystery_all.csv (150), and that it is the largest there
                 — the voiceover's "the word that produces the most colorings".

Codes are wordle.pattern integers, position 0 the MOST significant trit, 0 grey /
1 yellow / 2 green. How a code maps to a place on screen is the scene's business.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "colorings_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")
MATRIX = os.path.join(MATH, "data", "local", "patterns", "patterns.npy")
MAXBUCKET = os.path.join(MATH, "data", "shared", "maxbucket", "maxbucket_mystery_all.csv")

WORD = "trace"                    # the script's own choice (05i/05j)


def _maxbucket():
    """{word: buckets} from the committed ranking; `#` lines are its header prose."""
    with open(MAXBUCKET) as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        return {r["word"]: int(r["buckets"]) for r in rows}


def _build():
    import numpy as np
    sys.path.insert(0, MATH)
    import wordle

    n = wordle.N_PATTERNS
    seen = np.unique(np.load(MATRIX))
    impossible = sorted(set(range(n)) - {int(c) for c in seen})

    four_one = [c for c in range(n)
                if sorted(wordle.decode(c)) == [1, 2, 2, 2, 2]]
    assert impossible == sorted(four_one), (impossible, four_one)
    assert n - len(impossible) == 238

    answers = wordle.load_words("mystery")
    trace = sorted({int(wordle.pattern(WORD, a)) for a in answers})
    buckets = _maxbucket()
    assert len(trace) == buckets[WORD], (len(trace), buckets[WORD])
    assert buckets[WORD] == max(buckets.values())

    return {"n_colorings": n, "impossible": impossible,
            "n_valid": n - len(impossible), "word": WORD, "trace": trace}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    import wordle
    names = "-YG"
    show = lambda c: "".join(names[t] for t in wordle.decode(c))
    print(f"impossible ({len(data['impossible'])}): "
          + " ".join(show(c) for c in data["impossible"]))
    print(f"valid: {data['n_valid']}")
    print(f"{data['word'].upper()} colorings: {len(data['trace'])}")
    print(f"\nwrote {CACHE}")
