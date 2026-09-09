"""Export an adversarial hill-climb's final weights as solver input.

`freq_search.py` records the search as a per-change CSV; the final weight of
every word is the PRODUCT of its (letter, position-pattern) multipliers, which
`FrequencySearch.reconstruct` replays.  This turns that state into the two files
the weighted solver needs, and it is the ONLY place that conversion happens.

Two files, written together so their ORDER cannot drift apart:

  <stem>.txt       one word per line -- the ANSWER LIST, for `--answer-list`
                   here and for `build_patterns.py --answer-list`
  <stem>.weights   `<word> <weight>` per line, the same words in the same order

ORDER IS LOAD-BEARING, not cosmetic.  Both files are sorted by weight
DESCENDING (ties on the word, so the output is deterministic).  The weighted
solver's lower bound assigns the shallowest search levels to the heaviest
answers, and it gets each bucket in that order for free ONLY because the answer
INDEX order is already weight-descending -- it verifies this on load and refuses
a file that is not sorted, rather than computing a wrong bound.

ZERO-WEIGHT WORDS ARE DROPPED, matching `topk.py`: "a weight of 0 means the word
cannot be the answer and the guesser knows it, so zero-weight words are dropped
from the candidate set before any search".  A word left in at weight 0 would be
charged nothing yet still branch the search.

WEIGHTS MUST BE DYADIC (k / 2^m) and the tool REFUSES otherwise.  The solver
works in exact integers -- that is what makes an optturns-family result exact
rather than float-compared -- so the weights are scaled by the smallest common
power of two that makes every one of them integral.  freq_search's moves are
x2, /2 and +/- powers of two down to 0.125, so its output is always dyadic;
rounding a non-dyadic weight would silently change the objective, so a different
producer has to be handled deliberately rather than absorbed here.
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

MAX_SCALE_BITS = 30          # refuse a weight needing a finer scale than 2^-30


def dyadic_denominator(x: float) -> int | None:
    """The denominator of ``x`` as an exact fraction, if it is a power of two."""
    d = Fraction(x).denominator
    return d if (d & (d - 1)) == 0 else None


def scale_for(weights) -> int:
    """The smallest power of two making every weight an exact integer."""
    scale = 1
    for w in weights:
        d = dyadic_denominator(float(w))
        if d is None:
            raise SystemExit(
                "weight %r is not dyadic (k / 2^m).  The solver is exact in "
                "integers; rounding it would silently change the objective." % w)
        if d > scale:
            scale = d
    if scale > (1 << MAX_SCALE_BITS):
        raise SystemExit("weights need a scale of %d, past the 2^%d limit"
                         % (scale, MAX_SCALE_BITS))
    return scale


def export(csv_path: str, stem: str, *, k: int = 1, answers=None) -> dict:
    """Reconstruct ``csv_path`` and write ``<stem>.txt`` / ``<stem>.weights``."""
    from freq_search import FrequencySearch, CUSTOM

    s = FrequencySearch.reconstruct(csv_path, k=k,
                                    answers=CUSTOM if answers is None else answers)
    pairs = [(w, float(f)) for w, f in zip(s.game.words, s.freq) if f > 0]
    pairs.sort(key=lambda t: (-t[1], t[0]))
    scale = scale_for(f for _, f in pairs)

    words_path, wts_path = stem + ".txt", stem + ".weights"
    with open(words_path, "w") as fw, open(wts_path, "w") as fx:
        fx.write("# weights from %s\n" % os.path.relpath(csv_path))
        fx.write("# scale %d (every weight x scale is an exact integer)\n" % scale)
        for word, weight in pairs:
            fw.write(word + "\n")
            fx.write("%s %s\n" % (word, Fraction(weight)))

    # ---- gate: read both back and check they agree with the reconstruction ----
    back_words = [l.strip() for l in open(words_path) if l.strip()]
    back = []
    for line in open(wts_path):
        if line.startswith("#") or not line.strip():
            continue
        w, v = line.split()
        back.append((w, Fraction(v)))
    assert back_words == [w for w, _ in back], "the two files disagree on order"
    assert back_words == [w for w, _ in pairs], "words changed on the round trip"
    assert all(float(v) == f for (_, v), (_, f) in zip(back, pairs)), "weights changed"
    assert all(int(v * scale) == v * scale for _, v in back), "scale does not integralise"
    assert all(back[i][1] >= back[i + 1][1] for i in range(len(back) - 1)), \
        "not weight-descending"

    total = sum(v for _, v in back)
    return {"words": words_path, "weights": wts_path, "n": len(back),
            "scale": scale, "total": float(total),
            "total_scaled": int(total * scale), "max": float(back[0][1])}


def main(argv):
    csv_path = stem = None
    k = 1
    it = iter(argv)
    for a in it:
        if a == "--from":
            csv_path = next(it)
        elif a == "--stem":
            stem = next(it)
        elif a in ("-k", "--topk"):
            k = int(next(it))
        else:
            raise SystemExit("unknown arg %r (--from CSV, --stem PATH, -k K)" % a)
    if not csv_path or not stem:
        raise SystemExit("usage: freqweights.py --from <freqsearch csv> --stem <out stem> [-k K]")
    info = export(csv_path, stem, k=k)
    print("wrote %s and %s" % (info["words"], info["weights"]))
    print("  %d words, scale %d, total weight %.6f (scaled %d), max %.6f"
          % (info["n"], info["scale"], info["total"], info["total_scaled"], info["max"]))


if __name__ == "__main__":
    main(sys.argv[1:])
