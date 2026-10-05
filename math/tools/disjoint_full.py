"""EVERY set of K legal guesses sharing no letter, at least one of them an
answer -- the full search, with no assumption about vowels.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-disjoint-full.sh             # from math/, K = 7
    bash solver/run-disjoint-full.sh -k 6

WHY K = 7 MATTERS.  Seven such words, one the answer: play the other six against
it in hard mode and every reply is all grey, every guess stays legal, and the
sixth grey row loses.  tools/disjoint_words.py finds sets of ONE particular form
(a vowelless word plus one word per vowel); this finds them ALL, so that form is
a subset of what this reports -- a set here may, say, hold two vowelless words.

THE SEARCH (the user's method).  Words with the same LETTER SET are
interchangeable, so everything runs over distinct letter sets ("masks") and
expands back to words in the output.
  * OUTER LOOP: every letter set holding at least one answer, with a progress
    bar.  For answer set number i, the candidates are the guess letter sets
    disjoint from it -- EXCLUDING answer sets numbered below i, so a set with two
    answers is reported once, under its first answer, not twice.
  * INNER: pick the next word from the candidates, keep only the candidates
    disjoint from it (and later in the order, so each set is found once), and
    repeat until K words are chosen.
  * PRUNING, each a bound that only cuts branches that CANNOT finish:
      - fewer candidates left than words still needed;
      - the letters: letters used + (words needed x the fewest letters any
        candidate has) > 26;
      - the vowels: every word without a vowel (A E I O U Y) is "vowelless", and
        every other word uses up at least one vowel nobody else can then use.
        So the words still needed can be at most the unused vowels plus the
        vowelless candidates left.  Nothing is assumed about which words are
        vowelless -- they are counted from the list.
  So the enumeration is complete.

OUTPUT, streamed and flushed per answer letter set, so results appear as they
are found: one row per combination of letter sets --
    set,answer_set,slot,letters,words,answers
`words` is every legal word with that letter set ('|'-joined), `answers` those
that are answers.  The number of distinct WORD sets is the product of the slot
sizes; the running total is printed.

CHECKS, built in:
  * before the real run, the search against a brute force over itertools
    combinations of word STRINGS on several random samples, exactly;
  * every set written is replayed with wordle.pattern -- every pair all grey
    both ways -- using one word per letter set (words with the same letters
    give the same reply, since a reply here depends only on shared letters).
It exits nonzero rather than reporting a set that fails.
"""
import itertools
import os
import random
import sys
import time

import numpy as np
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csvout import fresh_file  # noqa: E402
from wordle import load_words, pattern  # noqa: E402

VOWEL_MASK = sum(1 << (ord(c) - 97) for c in "aeiouy")


def mask_of(word):
    m = 0
    for c in word:
        m |= 1 << (ord(c) - 97)
    return m


def popcount(m):
    return bin(m).count("1")


class Search:
    def __init__(self, words, answers, k):
        self.k = k
        self.by_mask = {}
        for w in words:
            self.by_mask.setdefault(mask_of(w), []).append(w)
        for ws in self.by_mask.values():
            ws.sort()
        # answer letter sets first, in a fixed order, then the rest
        ans = sorted(m for m, ws in self.by_mask.items() if any(w in answers for w in ws))
        rest = sorted(m for m in self.by_mask if m not in set(ans))
        self.masks = np.array(ans + rest, dtype=np.int64)
        self.n_ans = len(ans)
        self.pops = np.array([popcount(int(m)) for m in self.masks], dtype=np.int64)
        self.novowel = (self.masks & VOWEL_MASK) == 0

    def run(self, on_found=None, progress=False):
        found = []
        it = range(self.n_ans)
        if progress:
            it = tqdm(it, desc="answer letter sets", unit="set")
        idx_all = np.arange(len(self.masks))
        for i in it:
            a = int(self.masks[i])
            keep = ((self.masks & a) == 0) & (idx_all > i)
            cand = idx_all[keep]
            before = len(found)
            self._rec(cand, a, int(self.pops[i]), [i], found)
            if on_found and len(found) > before:
                on_found(found[before:])
            if progress:
                it.set_postfix(found=len(found))
        return found

    def _rec(self, cand, used, nused, chosen, found):
        need = self.k - len(chosen)
        if need == 0:
            found.append(tuple(chosen))
            return
        if len(cand) < need:
            return
        if nused + need * int(self.pops[cand].min()) > 26:
            return
        free_vowels = popcount(VOWEL_MASK & ~used)
        if need > free_vowels + int(self.novowel[cand].sum()):
            return
        cm = self.masks[cand]
        for j in range(len(cand) - need + 1):
            m = int(cm[j])
            tail = cand[j + 1:]
            nxt = tail[(self.masks[tail] & m) == 0]
            chosen.append(int(cand[j]))
            self._rec(nxt, used | m, nused + int(self.pops[cand[j]]), chosen, found)
            chosen.pop()

    def words(self, combo):
        return [self.by_mask[int(self.masks[i])] for i in combo]


def brute(words, answers, k):
    """Reference: combinations of word STRINGS, set intersection, no masks."""
    out = set()
    for combo in itertools.combinations(sorted(set(words)), k):
        if not any(w in answers for w in combo):
            continue
        sets = [set(w) for w in combo]
        if all(not (x & y) for x, y in itertools.combinations(sets, 2)):
            out.add(frozenset(combo))
    return out


def expand(search, found):
    out = set()
    for combo in found:
        for ws in itertools.product(*search.words(combo)):
            out.add(frozenset(ws))
    return out


def gate_brute(guesses, answers):
    rng = random.Random(0)
    total = 0
    for n, k in ((60, 3), (90, 3), (150, 2), (70, 4)):
        sample = rng.sample(guesses, n)
        # make sure the sample holds answers, or the answer filter goes untested
        sample += rng.sample(sorted(answers), 15)
        s = Search(sample, answers, k)
        got = expand(s, s.run())
        ref = brute(sample, answers, k)
        if got != ref:
            raise SystemExit(f"GATE FAIL: search vs brute force, n={len(sample)} "
                             f"k={k}: {len(got)} vs {len(ref)}")
        total += len(ref)
    # A deeper case, where the letter and vowel bounds can actually bite: few-
    # letter words, the vowelless ones, and some answers, at k = 5.
    few = [w for w in guesses if len(set(w)) <= 3]
    nov = [w for w in guesses if not (set(w) & set("aeiouy"))]
    fa = [w for w in guesses if w in answers and len(set(w)) <= 4]
    sample = rng.sample(few, 38) + nov + rng.sample(fa, 8)
    s = Search(sample, answers, 5)
    got, ref = expand(s, s.run()), brute(sample, answers, 5)
    if got != ref or not ref:
        raise SystemExit(f"GATE FAIL: deep case k=5: {len(got)} vs {len(ref)}")
    total += len(ref)
    print(f"gate: search == brute force on 5 samples ({total} sets between them)")


def check_set(search, combo):
    reps = [ws[0] for ws in search.words(combo)]
    for x, y in itertools.permutations(reps, 2):
        if pattern(x, y) != 0:
            raise SystemExit(f"CHECK FAIL: {x} against {y} is not all grey")


def main(argv):
    k, out = None, None
    i = 0
    while i < len(argv):
        if argv[i] == "-k":
            k = int(argv[i + 1]); i += 2
        elif argv[i] == "--out":
            out = argv[i + 1]; i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])
    if k is None:
        raise SystemExit("-k is required (the set size IS the question)")
    if out is None:
        raise SystemExit("--out is required; use solver/run-disjoint-full.sh")
    if not fresh_file(out):
        raise SystemExit(f"{out} already has content; refusing to overwrite")

    guesses = load_words("guess")
    answers = set(load_words("mystery"))
    gate_brute(guesses, answers)

    s = Search(guesses, answers, k)
    print(f"{len(guesses)} guesses, {len(s.masks)} distinct letter sets, "
          f"{s.n_ans} of them hold an answer; searching for {k}", flush=True)
    f = open(out, "w")
    f.write(f"# EVERY set of {k} legal guesses, pairwise letter-disjoint, >= 1 of the\n")
    f.write("# 2315 answers. One row per slot of each letter-set combination; the\n")
    f.write("# word sets it stands for are the product of the slot sizes.\n")
    f.write("set,answer_set,slot,letters,words,answers\n")
    f.flush()
    state = {"sets": 0, "word_sets": 0}

    def on_found(new):
        for combo in new:
            check_set(s, combo)
            state["sets"] += 1
            wl = s.words(combo)
            state["word_sets"] += int(np.prod([len(ws) for ws in wl]))
            first = "".join(sorted(set(wl[0][0])))
            for j, ws in enumerate(wl, 1):
                letters = "".join(sorted(set(ws[0])))
                ans = [w for w in ws if w in answers]
                f.write(f"{state['sets']},{first},{j},{letters},{'|'.join(ws)},"
                        f"{'|'.join(ans)}\n")
            tqdm.write("  " + "  ".join("/".join(w.upper() if w in answers else w
                                                  for w in ws) for ws in wl))
        f.flush()

    t0 = time.time()
    s.run(on_found=on_found, progress=True)
    f.close()
    print(f"done in {time.time() - t0:.1f}s: {state['sets']} letter-set combinations, "
          f"{state['word_sets']} word sets (answers in CAPITALS above)")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
