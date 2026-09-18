"""Feedback codes for a scripted Wordle game — SOURCED, then cached.

The tile colours of a guess are a computed quantity, so they come from the pipeline's
own `math/wordle.py:pattern()` rather than being worked out by hand and typed in. This
module calls it and writes `game_cache.json`; the SCENE reads that cache, so a render
imports no solver and the numbers sync between machines through git.

Regenerate (from this directory):

    ../../.venv/bin/python game_data.py

Provenance for every number it writes:
  guesses/answer  — the user's choice for the first test animation
  code            — math/wordle.py `pattern(guess, answer)`, the same function the
                    solver and every gate in this repo use
  tiles           — that code decoded with POSITION 0 AS THE MOST SIGNIFICANT TRIT,
                    the convention secondword.py documents; decoding it the other way
                    round silently reverses every row
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "game_cache.json")

# The game being animated — the user's call for this first test.
ANSWER = "snowy"
GUESSES = ["trace", "loins", "dumpy", "snowy"]


def _build():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "math"))
    import wordle

    words = os.path.join(HERE, "..", "..", "math", "data", "shared", "words")
    legal = {w.strip() for w in open(os.path.join(words, "guess.txt"))}
    answers = {w.strip() for w in open(os.path.join(words, "mystery.txt"))}
    assert ANSWER in answers, f"{ANSWER} is not an answer word"
    for g in GUESSES:
        assert g in legal, f"{g} is not a legal guess"

    out = {"answer": ANSWER, "guesses": []}
    for g in GUESSES:
        code = wordle.pattern(g, ANSWER)
        tiles = [(code // 3 ** (4 - i)) % 3 for i in range(5)]
        out["guesses"].append({"word": g, "code": int(code), "tiles": tiles})
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    names = {0: "absent", 1: "present", 2: "correct"}
    print(f"answer {data['answer'].upper()}")
    for g in data["guesses"]:
        shown = "  ".join(f"{c.upper()}={names[t]}"
                          for c, t in zip(g["word"], g["tiles"]))
        print(f"  {g['word'].upper()}  code={g['code']:3d}  {shown}")
    print(f"\nwrote {CACHE}")
