"""The two word lists and the colour groups a guess splits the answers into — cached.

Scene 04 shows the answer and guess lists, then regroups the answers by the feedback
a guess would give. The groups are a computed quantity, so they come from the
pipeline's `math/wordle.py:pattern()`; this module calls it and writes
`lists_cache.json`, and the SCENE reads the cache, so a render imports no solver.

Regenerate (from this directory):

    ../../.venv/bin/python lists_data.py

Provenance:
  n_answers / n_guesses  — line counts of math/data/shared/words/{mystery,guess}.txt
  answers                — mystery.txt in file order (alphabetical); the scene reads
                           a word's ALPHABETICAL RANK from its index here
  guesses_head           — the first HEAD lines of guess.txt
  groups[guess]          — the answers partitioned by pattern(guess, answer); code
                           and tiles decoded POSITION 0 MOST SIGNIFICANT, as
                           game_data.py does

THE GUESSES: the first is "the topmost guess" of the list (04d), read from
guess.txt, never typed; PIGGY and CODES are the script's own choices (04e).

WHICH GROUPS ARE SHOWN IS A DISPLAY CHOICE, NOT A RESULT — flagged for the user.
A guess makes 54-98 groups of up to 981 answers, far more than a frame holds. The
rule: for each target size in TARGETS, the group whose size is NEAREST to it, ties
going to the group whose first member is alphabetically earliest (so the ones
already on screen tend to be picked); a group is never picked twice. Every member of
a picked group is shown, so the ovals really do differ in size.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "lists_cache.json")
WORDS = os.path.join(HERE, "..", "..", "math", "data", "shared", "words")

HEAD = 20                         # guess-list lines cached (the scene shows fewer)
SCRIPT_GUESSES = ["piggy", "codes"]
TARGETS = [1, 2, 4, 7, 11, 16]    # the group sizes to show, one group each


def _read(name):
    return [w.strip() for w in open(os.path.join(WORDS, name)) if w.strip()]


def _pick(groups):
    """The groups nearest each TARGETS size (see the module docstring)."""
    chosen = []
    for t in TARGETS:
        best = min((g for g in groups if g not in chosen),
                   key=lambda g: (abs(len(g["members"]) - t), g["members"][0]))
        chosen.append(best)
    return sorted(chosen, key=lambda g: len(g["members"]))


def _build():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "math"))
    import wordle

    answers, guesses = _read("mystery.txt"), _read("guess.txt")
    assert answers == sorted(answers) and guesses == sorted(guesses)
    out = {"n_answers": len(answers), "n_guesses": len(guesses),
           "answers": answers, "guesses_head": guesses[:HEAD], "groups": {}}
    for g in [guesses[0]] + SCRIPT_GUESSES:
        assert g in guesses, f"{g} is not a legal guess"
        by_code = {}
        for a in answers:                          # answers is alphabetical, so
            by_code.setdefault(wordle.pattern(g, a), []).append(a)   # members are too
        groups = [{"code": int(c), "tiles": [(c // 3 ** (4 - i)) % 3 for i in range(5)],
                   "members": m} for c, m in by_code.items()]
        out["groups"][g] = _pick(groups)
    out["guesses"] = [guesses[0]] + SCRIPT_GUESSES
    return out


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    names = "-YG"
    print(f"{data['n_answers']} answers, {data['n_guesses']} guesses")
    for g in data["guesses"]:
        print(g.upper())
        for grp in data["groups"][g]:
            tiles = "".join(names[t] for t in grp["tiles"])
            print(f"  {tiles}  {len(grp['members']):3d}  {' '.join(grp['members'])}")
    print(f"\nwrote {CACHE}")
