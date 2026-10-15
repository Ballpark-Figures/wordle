"""The adversarial frequency search's result as hangman's two tables — the bonus
video's "Hard-to-Guess Words" still. SOURCED, then cached.

    ../../.venv/bin/python adversarial_data.py     # (from this directory)

The search is math/freq_search.py at k=1 over words/custom.txt, logged to
math/data/shared/freqsearch/topk1.csv; `FrequencySearch.reconstruct` replays that log
to the final multipliers and weights. The rows are hangman's
(hangman/animations/assets/long_words_data.py), unchanged:

  patterns  `multipliers_df()` rows with multiplier > 1 that still touch a word of
            nonzero weight, highest first, the top PAT_CAP; pattern uppercased
  words     `frequencies_df()` rows with weight > 0, heaviest first, the top
            WORD_CAP; pct = weight / total weight * 100

GATE: the replayed weights must be proportional to the committed
data/shared/freqsearch/adv_topk1.weights, word for word, or the build stops.
"""
import json
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.join(HERE, "..", "..", "math")
LOG = os.path.join(MATH, "data", "shared", "freqsearch", "topk1.csv")
WEIGHTS = os.path.join(MATH, "data", "shared", "freqsearch", "adv_topk1.weights")
CACHE = os.path.join(HERE, "adversarial_cache.json")
PAT_CAP = 12                      # hangman's pat_cap
WORD_CAP = 12                     # hangman's capped word count (lengths 8, 9, 16)


def _build():
    sys.path.insert(0, MATH)
    os.chdir(MATH)
    from freq_search import FrequencySearch
    s = FrequencySearch.reconstruct(LOG, k=1)
    freq = s.frequencies_df()
    total = float(freq.frequency.sum())

    # gate: the committed weights, exactly (dyadic, so compared as fractions)
    committed = {}
    for line in open(WEIGHTS):
        if line.startswith("#") or not line.strip():
            continue
        w, v = line.split()
        committed[w] = Fraction(v)
    live = {r.word: Fraction(float(r.frequency)).limit_denominator(1 << 20)
            for r in freq.itertuples() if r.frequency > 0}
    assert set(live) == set(committed), "word sets differ"
    w0 = next(iter(committed))
    ratio = live[w0] / committed[w0]
    bad = [w for w in committed if live[w] != committed[w] * ratio]
    assert not bad, f"weights differ for {bad[:5]}"

    mult = s.multipliers_df()
    above = mult[(mult.multiplier > 1) & (mult.n_nonzero_words > 0)]
    words = freq[freq.frequency > 0].head(WORD_CAP)
    return {
        "source": "math/data/shared/freqsearch/topk1.csv (freq_search k=1, custom.txt)",
        "patterns": [{"pattern": r.pattern.upper(), "multiplier": float(r.multiplier)}
                     for r in above.head(PAT_CAP).itertuples()],
        "words": [{"word": r.word.upper(), "pct": round(100.0 * float(r.frequency) / total, 6)}
                  for r in words.itertuples()],
        "n_words": int((freq.frequency > 0).sum()),
    }


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print(f"{data['n_words']} words with weight; top patterns:")
    for p in data["patterns"]:
        print(f"  {p['pattern']}  x{p['multiplier']:g}")
    print("top words:")
    for w in data["words"]:
        print(f"  {w['word']}  {w['pct']:.3f}%")
