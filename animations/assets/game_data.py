"""Feedback codes for scripted Wordle games — SOURCED, then cached.

The tile colours of a guess are a computed quantity, so they come from the pipeline's
own `math/wordle.py:pattern()` rather than being worked out by hand and typed in. This
module calls it and writes `game_cache.json`; the SCENE reads that cache, so a render
imports no solver and the numbers sync between machines through git.

SEVERAL GAMES, ONE CACHE, keyed by name — `load("snowy")` for scene 97's test game,
`load("rules")` for scene 02. A new scripted game is a new entry in GAMES, not a
second data module.

Regenerate (from this directory):

    ../../.venv/bin/python game_data.py

Provenance for every number it writes:
  guesses/answer  — the script's (or the user's) choice for that scene
  code            — math/wordle.py `pattern(guess, answer)`, the same function the
                    solver and every gate in this repo use
  tiles           — that code decoded with POSITION 0 AS THE MOST SIGNIFICANT TRIT,
                    the convention secondword.py documents; decoding it the other way
                    round silently reverses every row

AN ANSWER NEED NOT BE ONE OF THE 2315. Scene 02's ENDED is a legal guess but not an
NYT answer word — the script picked it to demonstrate the rules, not to be a real
puzzle. So only legality is asserted; `in_mystery` records which it is.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "game_cache.json")

# name -> (answer, guesses in order)
GAMES = {
    # Scene 97 — the user's choice for the first test animation.
    "snowy": ("snowy", ["trace", "loins", "dumpy", "snowy"]),
    # Scene 02 — Script.md 02a-02j: BEGIN, EDITS, MELEE, ENDED against ENDED.
    "rules": ("ended", ["begin", "edits", "melee", "ended"]),
}


def _build():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "math"))
    import wordle

    words = os.path.join(HERE, "..", "..", "math", "data", "shared", "words")
    legal = {w.strip() for w in open(os.path.join(words, "guess.txt"))}
    answers = {w.strip() for w in open(os.path.join(words, "mystery.txt"))}

    out = {}
    for name, (answer, guesses) in GAMES.items():
        assert answer in legal, f"{name}: {answer} is not a legal word"
        for g in guesses:
            assert g in legal, f"{name}: {g} is not a legal guess"
        game = {"answer": answer, "in_mystery": answer in answers, "guesses": []}
        for g in guesses:
            code = wordle.pattern(g, answer)
            tiles = [(code // 3 ** (4 - i)) % 3 for i in range(5)]
            game["guesses"].append({"word": g, "code": int(code), "tiles": tiles})
        out[name] = game
    return out


def load(name):
    with open(CACHE) as f:
        return json.load(f)[name]


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    names = {0: "absent", 1: "present", 2: "correct"}
    for name, game in data.items():
        note = "" if game["in_mystery"] else "  (not one of the 2315 answers)"
        print(f"{name}: answer {game['answer'].upper()}{note}")
        for g in game["guesses"]:
            shown = "  ".join(f"{c.upper()}={names[t]}"
                              for c, t in zip(g["word"], g["tiles"]))
            print(f"  {g['word'].upper()}  code={g['code']:3d}  {shown}")
    print(f"\nwrote {CACHE}")
