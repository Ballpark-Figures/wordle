"""Adversarial weight hill-climb -- the Wordle port of hangman's `freq_search.py`.

Weight model. Every distinct (letter, non-empty position-pattern) that occurs in
the candidate list has a real-valued MULTIPLIER (start 1). A word's weight is the
PRODUCT of the multipliers for the patterns it exhibits (one per distinct letter
it contains). All-ones -> all weights 1. A multiplier can reach 0, which deletes
every word carrying that pattern from the game, so the search re-weights the list
AND carves it down.

    salet -> s____ , _a___ , __l__ , ___e_ , ____t
    abbey -> a____ , _bb__ , ___e_ , ____y

Objective. The weight-averaged number of guesses a `topk.TopKGame` guesser
spends, MAXIMISED -- an adversarial word-setter against a guesser that sees the
weights. `k` selects the guesser: k=1 takes the top-ranked guess at every node,
larger k gives it that much lookahead. THERE IS NO DEPTH CAP; see topk.py.

Search. Identical to hangman's, phase for phase (same moves, same floor, same
sequential Gauss-Seidel order, same logging), so the two videos' numbers are
produced the same way:
  1. DOUBLE/HALVE -- for every multiplier try x2 or /2 (down to a floor of 0.125;
     0.125 can drop to 0, and 0 can come back to 0.125), keeping whichever raises
     the average (loop until none benefit).
  2. +/- POWERS OF 2 -- additive steps of powers of two from the largest scale
     reached (>= max multiplier) down to 1; try both m+s and m-s (never below 0).
  3. +/- FINE -- additive steps FINE_STEPS = 0.5, 0.25, 0.125.
Each phase loops in a fixed order, keeping whichever move most increases the
average, until a full pass makes no change. Each accepted change prints
`<pattern> ->x<mult> (<move>) avg=<new>`; each loop prints its change count.

Every accepted change is logged (data/shared/freqsearch/topk<K>.csv) so the
weight state can be reconstructed later -- see ``reconstruct``.

Run it through `solver/run-freq-search.sh`, never bare: the wrapper is what
gives the run a log file and a CSV that survives it.
"""

from __future__ import annotations

import csv
import math
import os

import numpy as np

from topk import CUSTOM, TopKGame, read_words

ALPHABET = "abcdefghijklmnopqrstuvwxyz"
FINE_STEPS = [0.5, 0.25, 0.125]

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data", "shared", "freqsearch")


def _default_log_path(k: int) -> str:
    """Per-K CSV log path -- each k is a different guesser, so a different run."""
    return os.path.join(DATA_DIR, f"topk{k}.csv")


def _double_candidates(b):
    """Double/halve-phase moves for a multiplier b: x2, /2 (floor 0.125),
    0.125 -> 0, and 0 -> 0.125 (revive)."""
    if b == 0.0:
        return (0.125,)                 # revive: 0 -> 0.125
    if b <= 0.125:                       # 0.125 is the smallest positive rung
        return (b * 2.0, 0.0)           # x2, or drop to 0
    return (b * 2.0, b / 2.0)           # x2 or /2


def _pattern_string(word_len: int, letter: str, mask: int) -> str:
    """e.g. length 5, letter 'e', mask {1,3} -> '_e_e_'."""
    return "".join(letter if (mask >> p) & 1 else "_" for p in range(word_len))


class FrequencySearch:
    """Hill-climb per-(letter, pattern) multipliers to maximise expected guesses."""

    def __init__(self, *, k: int = 1, answers: str | list[str] = CUSTOM,
                 game: TopKGame | None = None):
        self.k = k
        self.game = game if game is not None else TopKGame(answers=answers, k=k)
        g = self.game
        self.word_len = len(g.words[0])

        # Enumerate (letter, mask) keys and the keys each word uses.
        keymap: dict[tuple[str, int], int] = {}
        key_letter: list[str] = []
        key_mask: list[int] = []
        word_keys: list[list[int]] = []
        for word in g.words:
            masks: dict[str, int] = {}
            for p, ch in enumerate(word):
                masks[ch] = masks.get(ch, 0) | (1 << p)
            ks = []
            for ch, m in masks.items():
                key = keymap.get((ch, m))
                if key is None:
                    key = len(key_letter)
                    keymap[(ch, m)] = key
                    key_letter.append(ch)
                    key_mask.append(m)
                ks.append(key)
            word_keys.append(ks)
        self.M = len(key_letter)
        self.key_letter = key_letter
        self.key_mask = key_mask
        self._keyidx = keymap
        self.pattern = [_pattern_string(self.word_len, key_letter[i], key_mask[i])
                        for i in range(self.M)]

        # Flat CSR (word -> keys) for a fast exact weight recompute via reduceat.
        counts = np.array([len(ks) for ks in word_keys], dtype=np.int64)
        self.word_ptr = np.zeros(g.N, dtype=np.int64)
        self.word_ptr[1:] = np.cumsum(counts)[:-1]
        self.flat_keys = np.array([kk for ks in word_keys for kk in ks], dtype=np.int64)

        self.mult = np.ones(self.M, dtype=np.float64)
        self.freq = np.ones(g.N, dtype=np.float64)
        self._var = self.mult          # the knob vector the search adjusts
        # Deterministic order: by letter, then mask.
        self.order = sorted(range(self.M), key=lambda i: (key_letter[i], key_mask[i]))
        self.records: list[dict] = []

    # ---- weights from multipliers ------------------------------------------
    def _recompute_freq(self) -> None:
        self.freq = np.multiply.reduceat(
            self.mult[self.flat_keys].astype(np.float64), self.word_ptr)

    def freq_from_multipliers(self, mult: np.ndarray) -> np.ndarray:
        return np.multiply.reduceat(mult[self.flat_keys].astype(np.float64), self.word_ptr)

    # ---- log columns / labels ----------------------------------------------
    _cols = ("move", "loop", "seq", "letter", "pattern", "mask",
             "multiplier", "expected_guesses", "live_words")

    def _make_record(self, i, val, move, loop, avg) -> dict:
        return {"move": move, "loop": loop, "seq": len(self.records),
                "letter": self.key_letter[i], "pattern": self.pattern[i],
                "mask": self.key_mask[i], "multiplier": val,
                "expected_guesses": avg, "live_words": int((self.freq > 0).sum())}

    def _change_str(self, i, val) -> str:
        return f"{self.pattern[i]}  ->x{val:g}"

    # ---- objective ---------------------------------------------------------
    def _score(self, threshold) -> float:
        """The scalar to maximise for the current ``self.freq``. ``threshold``
        (the current best-so-far) is accepted for parity with hangman's pruned
        best_opener scan; the top-K guesser has no such shortcut, so it is unused."""
        if not (self.freq > 0).any():
            return -math.inf            # an empty game is not an improvement
        return self.game.expected_guesses(self.freq)

    # ---- results as DataFrames ---------------------------------------------
    def multipliers_df(self):
        """Every (letter, pattern) multiplier, highest first."""
        import pandas as pd
        n_words = np.bincount(self.flat_keys, minlength=self.M)
        # ...restricted to words with NONZERO final weight. A word's weight is the
        # PRODUCT of its patterns' multipliers, and a multiplier can hit 0 in the
        # sequential phase -- zeroing every word it touches -- so a pattern can carry
        # words yet appear in none with positive weight.
        counts = np.diff(np.append(self.word_ptr, self.flat_keys.size))
        flat_word = np.repeat(np.arange(self.game.N), counts)
        nz_flat = self.freq[flat_word] > 0
        n_nonzero_words = np.bincount(self.flat_keys[nz_flat], minlength=self.M)
        return pd.DataFrame({
            "letter": self.key_letter,
            "pattern": self.pattern,
            "mask": self.key_mask,
            "multiplier": self.mult,
            "n_words": n_words,                    # how many words carry this pattern
            "n_nonzero_words": n_nonzero_words,    # ...of those, how many have weight > 0
        }).sort_values("multiplier", ascending=False).reset_index(drop=True)

    def frequencies_df(self):
        """Every word's weight, heaviest first."""
        import pandas as pd
        return pd.DataFrame({
            "word": self.game.words,
            "frequency": self.freq,
        }).sort_values("frequency", ascending=False).reset_index(drop=True)

    # ---- the search --------------------------------------------------------
    def _phase(self, cand_fn, header, move_label, avg, *, max_loops, verbose, writer, fh, cols):
        """Loop one phase (candidate values from cand_fn) until a pass makes no change.

        move_label(base, new) -> the per-change label (e.g. 'x2', '/2', '+8', '-8').
        """
        if verbose:
            print(f"--- {header} ---", flush=True)
        loop = 0
        while max_loops is None or loop < max_loops:
            changes = 0
            for i in self.order:
                base = float(self._var[i])
                best_val, best_avg = base, avg
                for cand in cand_fn(base):
                    if cand < 0.0:                     # never go below 0
                        continue
                    self._var[i] = cand
                    self._recompute_freq()
                    a = self._score(best_avg)
                    if math.isfinite(a) and a > best_avg:
                        best_avg, best_val = a, cand
                self._var[i] = best_val
                self._recompute_freq()
                if best_val != base:
                    avg = best_avg
                    move = move_label(base, best_val)
                    rec = self._make_record(i, best_val, move, loop, avg)
                    self.records.append(rec)
                    changes += 1
                    if verbose:
                        print(f"  {self._change_str(i, best_val)}  ({move})  "
                              f"avg={avg:.4f}", flush=True)
                    if writer:
                        writer.writerow([rec[c] for c in cols])
                        fh.flush()
            if verbose:
                print(f"  loop {loop}: {changes} changes", flush=True)
            if changes == 0:
                break
            loop += 1
        return avg

    def run(self, *, fine_steps=None, max_loops: int | None = None, log_path=None,
            verbose: bool = True) -> list[dict]:
        fine_steps = list(FINE_STEPS if fine_steps is None else fine_steps)
        g = self.game
        self._var[:] = 1.0
        self._recompute_freq()
        avg = self._score(None)
        start_avg = avg
        self.records = []

        fh = writer = None
        cols = self._cols
        if log_path is not None:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            fh = open(log_path, "w", newline="")
            writer = csv.writer(fh)
            writer.writerow(cols)

        if verbose:
            print(f"topk {self.k}: {g.N} words, {len(self.order)} knobs, "
                  f"{g.NG} legal guesses; start avg = {avg:.4f}", flush=True)

        kw = dict(max_loops=max_loops, verbose=verbose,
                  writer=writer, fh=fh, cols=cols)

        # Phase 1: double / halve (x2, /2, floor 0.125, 0.125 <-> 0).
        avg = self._phase(_double_candidates, "double/halve",
                          lambda base, new: "x2" if new > base else "/2", avg, **kw)

        # Phase 2: +/- powers of 2, from the largest scale reached down to 1.
        p = 1
        top = int(self._var.max())
        while p * 2 <= top:
            p *= 2
        while p >= 1:
            s = float(p)
            avg = self._phase(lambda b, s=s: (b + s, b - s), f"step {s:g}",
                              lambda base, new, s=s: f"+{s:g}" if new > base else f"-{s:g}",
                              avg, **kw)
            p //= 2

        # Phase 3: fine additive steps.
        for s in fine_steps:
            avg = self._phase(lambda b, s=s: (b + s, b - s), f"step {s:g}",
                              lambda base, new, s=s: f"+{s:g}" if new > base else f"-{s:g}",
                              avg, **kw)

        if fh:
            fh.close()
        if verbose:
            print(f"done: {len(self.records)} changes, "
                  f"initial avg = {start_avg:.4f}, final avg = {avg:.4f}", flush=True)
        return self.records

    # ---- reconstruction ----------------------------------------------------
    def multipliers_from_records(self, records, upto: int | None = None) -> np.ndarray:
        """Replay accepted changes into a multiplier vector (upto = # rows to apply)."""
        mult = np.ones(self.M, dtype=np.float64)
        rows = records if upto is None else records[:upto]
        for r in rows:
            letter = r["letter"] if isinstance(r, dict) else r.letter
            mask = int(r["mask"] if isinstance(r, dict) else r.mask)
            multiplier = float(r["multiplier"] if isinstance(r, dict) else r.multiplier)
            mult[self._keyidx[(letter, mask)]] = multiplier
        return mult

    @classmethod
    def reconstruct(cls, csv_path, *, k: int = 1, answers: str | list[str] = CUSTOM,
                    upto: int | None = None) -> "FrequencySearch":
        """Rebuild a search with mult/weights set from a saved CSV log."""
        import pandas as pd
        df = pd.read_csv(csv_path)
        self = cls(k=k, answers=answers)
        self.mult = self.multipliers_from_records(list(df.itertuples(index=False)), upto=upto)
        self._var = self.mult
        self._recompute_freq()
        return self


def main(argv: list[str]) -> None:
    k, answers, log_path, max_loops = 1, CUSTOM, None, None
    it = iter(argv)
    for a in it:
        if a in ("-k", "--topk"):
            k = int(next(it))
        elif a == "--answers":
            answers = next(it)
        elif a == "--out":
            log_path = next(it)
        elif a == "--max-loops":
            max_loops = int(next(it))
        elif a == "--no-out":
            log_path = ""
        else:
            raise SystemExit(f"unknown arg {a!r} "
                             f"(-k/--topk, --answers, --out, --no-out, --max-loops)")
    if log_path is None:
        raise SystemExit(
            "refusing to run without --out: a run that saves nothing is a run lost.\n"
            "Use solver/run-freq-search.sh, or pass --no-out deliberately.")
    s = FrequencySearch(k=k, answers=answers)
    s.run(log_path=log_path or None, max_loops=max_loops)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
