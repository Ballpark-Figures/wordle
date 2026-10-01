"""Feedback codes for scripted Wordle games — SOURCED, then cached.

The tile colours of a guess are a computed quantity, so they come from the pipeline's
own `math/wordle.py:pattern()` rather than being worked out by hand and typed in. This
module calls it and writes `game_cache.json`; the SCENE reads that cache, so a render
imports no solver and the numbers sync between machines through git.

SEVERAL GAMES, ONE CACHE, keyed by name — `load("snowy")` for scene 97's test game,
`load("rules")` for scene 02, `load("antiwordle")` for scene 03. The last is a
CHAIN read from a committed solver result (see CHAINS), not a hand-picked list. A new scripted game is a new entry in GAMES, not a
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

# name -> (answers, guesses in order): ONE set of guesses played on every board at
# once, the multi-Wordle games. A board stops at the guess that solves it (Octordle
# takes no more guesses on a solved board), so each board's rows are a prefix.
MULTI = {
    # Scene 16h -- "Start with SOLVE EIGHT WORDS and then do the 8 words in order."
    # The opener and the answers are the user's (worked out in the scene-16 thread
    # so every board is down to ONE candidate when its answer is played).
    "octordle": (["first", "halve", "third", "forth", "fifth", "sixth", "seven", "octet"],
                 ["solve", "eight", "words",
                  "first", "halve", "third", "forth", "fifth", "sixth", "seven", "octet"]),
}

# name -> committed result file whose chain IS the game. Read, never typed in: the
# line is the solver's output, and a re-run of it can legitimately emit a DIFFERENT
# chain of the same length (eldrowmax's witness depends on thread timing).
CHAINS = {
    # Scene 03 — "every word is an actual Wordle answer that matches all of the
    # clues leading up to it": eldrowmax's longest consistent chain over the 2315.
    # NOT antistall's 16-word `bully` line, which is a looser game (11 of its plays
    # are not answer words at all).
    "antiwordle": ("math/data/shared/eldrow/eldrowmax.mystery.csv", "final"),
}


def _chain(relpath, status):
    """The `line` of the LAST row with this status; its last word is the answer."""
    import csv
    path = os.path.join(HERE, "..", "..", relpath)
    rows = [r for r in csv.DictReader(open(path)) if r["status"] == status]
    assert rows, f"{relpath}: no row with status {status!r}"
    words = rows[-1]["line"].split()
    assert len(words) == int(rows[-1]["length"]), f"{relpath}: length/line mismatch"
    return words[-1], words


def _build():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "math"))
    import wordle

    words = os.path.join(HERE, "..", "..", "math", "data", "shared", "words")
    legal = {w.strip() for w in open(os.path.join(words, "guess.txt"))}
    answers = {w.strip() for w in open(os.path.join(words, "mystery.txt"))}

    games = dict(GAMES)
    for name, (relpath, status) in CHAINS.items():
        games[name] = _chain(relpath, status)

    out = {}
    for name, (answer, guesses) in games.items():
        assert answer in legal, f"{name}: {answer} is not a legal word"
        for g in guesses:
            assert g in legal, f"{name}: {g} is not a legal guess"
        game = {"answer": answer, "in_mystery": answer in answers, "guesses": []}
        for g in guesses:
            code = wordle.pattern(g, answer)
            tiles = [(code // 3 ** (4 - i)) % 3 for i in range(5)]
            game["guesses"].append({"word": g, "code": int(code), "tiles": tiles})
        if name in CHAINS:
            # The claim the scene makes, checked from the pattern function: every
            # play is an answer word and reproduces every clue before it.
            for j, w in enumerate(guesses):
                assert w in answers, f"{name}: {w} is not one of the 2315"
                for g in guesses[:j]:
                    assert wordle.pattern(g, w) == wordle.pattern(g, answer), \
                        f"{name}: {w} contradicts the clue from {g}"
        out[name] = game

    for name, (answers_, guesses) in MULTI.items():
        for w in answers_ + guesses:
            assert w in legal, f"{name}: {w} is not a legal word"
        assert all(a in guesses for a in answers_), f"{name}: an answer is never played"
        boards = []
        for a in answers_:
            played = guesses[:guesses.index(a) + 1]
            rows = []
            for g in played:
                code = wordle.pattern(g, a)
                rows.append({"word": g, "code": int(code),
                             "tiles": [(code // 3 ** (4 - i)) % 3 for i in range(5)]})
            boards.append({"answer": a, "in_mystery": a in answers, "guesses": rows})
        out[name] = {"answers": answers_, "guesses": guesses, "boards": boards}
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
        if "boards" in game:
            print(f"{name}: {len(game['boards'])} boards, guesses "
                  + " ".join(g.upper() for g in game["guesses"]))
            for b in game["boards"]:
                print(f"  {b['answer'].upper()}: solved on guess {len(b['guesses'])}")
            continue
        note = "" if game["in_mystery"] else "  (not one of the 2315 answers)"
        print(f"{name}: answer {game['answer'].upper()}{note}")
        for g in game["guesses"]:
            shown = "  ".join(f"{c.upper()}={names[t]}"
                              for c, t in zip(g["word"], g["tiles"]))
            print(f"  {g['word'].upper()}  code={g['code']:3d}  {shown}")
    print(f"\nwrote {CACHE}")
