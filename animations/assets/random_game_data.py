"""The Random Compatible Answers games of scenes 13 and 14 — SOURCED, then cached.

  "13"  the script's 13g-j game against FLUKE: DICEY, GUESS, VALUE, FLUTE, FLUKE
  "14"  14a's game against WOVEN: CHOSE (the "word of our choice"), then VIDEO,
        NOVEL, WOVEN at random from the compatible answers (the user's pick from
        sampled games, 2026-10-01: CHOSE's games run 3.99 guesses on average, and
        4 guesses is their most common length)

Each word after the first is one of the answers still consistent with every reply
so far. This module scores each game with math/wordle.py `pattern`, lists the
compatible answers after each guess, draws the random highlight hops, and writes
one cache per game (`CACHES`); the SCENE reads its cache, so a render imports
nothing from the pipeline.

Regenerate (from this directory):

    ../../.venv/bin/python random_game_data.py

Provenance for everything it writes:
  words, answer — the game's (above)
  codes         — math/wordle.py `pattern(word, answer)`; the build asserts the
                  colourings given here (13: the script's, except GUESS's BYYBB,
                  which the script leaves out)
  alive         — the answers (math/data/shared/words/mystery.txt, in file order)
                  consistent with every reply up to and including that guess. The
                  build asserts the counts, and that each next guess is among them,
                  which is what makes it a Random Compatible Answers game
  hops          — per turn, the words the highlight visits: hops-1 drawn at random
                  from that turn's compatible answers (random.Random(seed), never the
                  same word twice in a row), then the next guess. Scene 14 selects
                  the next guess straight away (its script: "selecting the random
                  words right away instead of after 10 cycles"), so it has one hop
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.join(HERE, "..", "..", "math")

GAMES = {
    "13": {"words": ["dicey", "guess", "value", "flute", "fluke"], "answer": "fluke",
           "codes": ["BBBYB", "BYYBB", "BBYYG", "GGGBG", "GGGGG"],
           "alive": [332, 21, 5, 2, 1], "hops": 6, "seed": 13},   # 5 random + the
                                                         # next guess (was 10; user 2026-10-07)
    "14": {"words": ["chose", "video", "novel", "woven"], "answer": "woven",
           "codes": ["BBYBY", "YBBGY", "YGGGB", "GGGGG"],
           "alive": [66, 5, 1, 1], "hops": 1, "seed": 14},
}
CACHES = {"13": "random_game_cache.json", "14": "random_game_14_cache.json"}


def _build(g):
    sys.path.insert(0, MATH)
    from wordle import pattern, load_words, decode
    answers = list(load_words("mystery"))
    words, answer = g["words"], g["answer"]
    assert len(answers) == 2315 and all(w in answers for w in words)
    codes = [int(pattern(w, answer)) for w in words]
    shown = ["".join("BYG"[t] for t in decode(c)) for c in codes]
    assert shown == g["codes"], shown
    alive, left = [], answers
    for w, c in zip(words, codes):
        left = [a for a in left if int(pattern(w, a)) == c]
        alive.append(left)
    assert [len(a) for a in alive] == g["alive"], [len(a) for a in alive]
    for nxt, pool in zip(words[1:], alive):
        assert nxt in pool, nxt
    rng = random.Random(g["seed"])
    hops = []
    for nxt, pool in zip(words[1:], alive):
        # hops-1 random words, never the same twice in a row, and the LAST of them
        # not the next guess either (the landing must be a move too). With a tiny
        # pool (FLUKE/FLUME) patching the last word could repeat the one before it
        # -- it did, 2026-10-07 -- so a sequence that cannot end legally is redrawn.
        while True:
            seq = []
            while len(seq) < g["hops"] - 1:
                w = rng.choice(pool)
                if not seq or w != seq[-1]:
                    seq.append(w)
            if not seq or seq[-1] != nxt:
                break
        hops.append(seq + [nxt])
    return {"words": words, "answer": answer, "codes": codes, "alive": alive,
            "hops": hops}


def load(game):
    with open(os.path.join(HERE, CACHES[game])) as f:
        return json.load(f)


if __name__ == "__main__":
    for name, g in GAMES.items():
        d = _build(g)
        path = os.path.join(HERE, CACHES[name])
        with open(path, "w") as f:
            json.dump(d, f, separators=(",", ":"))
            f.write("\n")
        print(f"game {name}:")
        for w, c, a in zip(d["words"], g["codes"], d["alive"]):
            print(f"  {w.upper()} {c}: {len(a)} compatible")
        for h in d["hops"]:
            print("  hops:", " ".join(h))
        print(f"wrote {path}")
