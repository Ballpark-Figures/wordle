"""Scene 13g-j's game of Random Compatible Answers — SOURCED, then cached.

The script's game against FLUKE: DICEY, GUESS, VALUE, FLUTE, FLUKE, each word after
DICEY one of the answers still consistent with every reply so far. This module
scores it with math/wordle.py `pattern`, lists the compatible answers after each
guess, draws the random highlight hops, and writes `random_game_cache.json`; the
SCENE reads that cache, so a render imports nothing from the pipeline.

Regenerate (from this directory):

    ../../.venv/bin/python random_game_data.py

Provenance for everything it writes:
  words, answer — the script's 13g-j (the user's; found as one of the 69 such games
                  ending on FLUKE, all of them checked the same way as here)
  codes         — math/wordle.py `pattern(word, answer)`; the build asserts the
                  script's colourings (BBBYB, BYYBB, BBYYG, GGGBG, GGGGG). The script
                  writes GUESS's turn without its colouring; BYYBB is the real one
  alive         — the answers (math/data/shared/words/mystery.txt, in file order)
                  consistent with every reply up to and including that guess: 332,
                  21, 5, 2, 1. The build asserts each next guess is among them, which
                  is what makes this a Random Compatible Answers game
  hops          — per turn, the words the highlight visits: 9 drawn at random from
                  that turn's compatible answers (random.Random(SEED), never the same
                  word twice in a row), then the next guess. With only 2 compatible
                  answers the 9 alternate, since no word repeats back to back
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "random_game_cache.json")
MATH = os.path.join(HERE, "..", "..", "math")

WORDS = ["dicey", "guess", "value", "flute", "fluke"]
ANSWER = "fluke"
SCRIPT_CODES = ["BBBYB", "BYYBB", "BBYYG", "GGGBG", "GGGGG"]
HOPS = 10                  # highlights per turn, the last on the next guess
SEED = 13


def _build():
    sys.path.insert(0, MATH)
    from wordle import pattern, load_words, decode
    answers = list(load_words("mystery"))
    assert len(answers) == 2315 and all(w in answers for w in WORDS)
    codes = [int(pattern(w, ANSWER)) for w in WORDS]
    shown = ["".join("BYG"[t] for t in decode(c)) for c in codes]
    assert shown == SCRIPT_CODES, shown
    alive, left = [], answers
    for w, c in zip(WORDS, codes):
        left = [a for a in left if int(pattern(w, a)) == c]
        alive.append(left)
    assert [len(a) for a in alive] == [332, 21, 5, 2, 1], [len(a) for a in alive]
    for nxt, pool in zip(WORDS[1:], alive):
        assert nxt in pool, nxt
    rng = random.Random(SEED)
    hops = []
    for nxt, pool in zip(WORDS[1:], alive):
        seq = []
        while len(seq) < HOPS - 1:
            w = rng.choice(pool)
            if not seq or w != seq[-1]:
                seq.append(w)
        if seq[-1] == nxt:                  # the landing must be a move too
            seq[-1] = rng.choice([w for w in pool if w != nxt])
        hops.append(seq + [nxt])
    return {"words": WORDS, "answer": ANSWER, "codes": codes, "alive": alive,
            "hops": hops}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    d = _build()
    with open(CACHE, "w") as f:
        json.dump(d, f, separators=(",", ":"))
        f.write("\n")
    for w, c, a in zip(d["words"], SCRIPT_CODES, d["alive"]):
        print(f"  {w.upper()} {c}: {len(a)} compatible")
    for h in d["hops"]:
        print("  hops:", " ".join(h))
    print(f"wrote {CACHE}")
