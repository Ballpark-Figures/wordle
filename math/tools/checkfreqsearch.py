"""Gate for `freq_search.py` -- the adversarial weight hill-climb.

Runs a SHORT search on a small candidate list, then checks the three things the
search itself cannot check:

  1. WEIGHT MODEL  -- a word's weight equals the product of its patterns'
                      multipliers, recomputed from the word STRINGS (the search
                      gets this from a flat CSR + reduceat, which is fast and
                      easy to mis-index).
  2. MONOTONE      -- the logged objective never decreases. Every row is an
                      ACCEPTED improvement, so a dip means a move was kept that
                      did not actually help.
  3. REPLAY        -- `reconstruct` from the CSV reproduces the final logged
                      objective EXACTLY. Integer guess counts times the weights,
                      so exact is the right bar, not "close".

Exits nonzero on any failure. Run it after any change to freq_search.py,
alongside tools/checktopk.py.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import topk as T
from freq_search import FrequencySearch

RNG = np.random.default_rng(20260902)
FAILS = 0
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "data", "local", "freqsearch", "_check.csv")


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILS
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        FAILS += 1


def main() -> int:
    words = sorted(RNG.choice(T.read_words(T.CUSTOM), size=150, replace=False).tolist())
    s = FrequencySearch(k=1, answers=words)

    print("1. weight model (product of the word's pattern multipliers)")
    s.mult[:] = RNG.choice([0.0, 0.125, 0.5, 1.0, 2.0, 16.0], size=s.M)
    s._recompute_freq()
    worst = 0.0
    for i, word in enumerate(s.game.words):
        masks: dict[str, int] = {}
        for p, ch in enumerate(word):
            masks[ch] = masks.get(ch, 0) | (1 << p)
        want = 1.0
        for ch, m in masks.items():
            want *= s.mult[s._keyidx[(ch, m)]]
        worst = max(worst, abs(want - s.freq[i]))
    check(f"{len(words)} words match a from-strings product", worst == 0.0,
          f"max |diff| = {worst:g}")

    print("2. a short search: monotone log, exact replay")
    os.makedirs(os.path.dirname(TMP), exist_ok=True)
    s2 = FrequencySearch(k=1, answers=words)
    s2.run(log_path=TMP, max_loops=1, fine_steps=[0.5], verbose=False)
    import pandas as pd
    df = pd.read_csv(TMP)
    check(f"{len(df)} accepted changes logged", len(df) > 0)
    if len(df):
        vals = df["expected_guesses"].to_numpy()
        drops = int((np.diff(vals) < 0).sum())
        check("objective never decreases", drops == 0, f"{drops} decreases")
        back = FrequencySearch.reconstruct(TMP, k=1, answers=words)
        got = back.game.expected_guesses(back.freq)
        d = abs(got - vals[-1])
        check("replay reproduces the final value", d == 0.0, f"|diff| = {d:g}")
        check("replay reproduces the multipliers",
              bool(np.array_equal(back.mult, s2.mult)))

    print(f"\n{'ALL CHECKS PASSED' if FAILS == 0 else str(FAILS) + ' CHECK(S) FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
