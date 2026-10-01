"""Scene 16i-r's candidate sets — every board's remaining answers after every guess,
for the two Octordle games the scene plays. SOURCED, then cached.

    ../../.venv/bin/python multi_data.py      # (from this directory) rewrites the cache

TWO GAMES on the same eight answers (game_data.py's MULTI["octordle"]):

  replay  — 16i-m: the scripted game again, SOLVE EIGHT WORDS then the answers in
            order (the guesses are game_data's; nothing is chosen here).
  greedy  — 16r: SOLVE, then the strategy the voiceover describes — "figure out which
            of our boards has the fewest options left, and we guess there" — which IS
            math/multiwordle.py's `greedy` rule, played by its own `play_game`:
            fewest candidates (ties on the lowest board index), a guess drawn
            UNIFORMLY AT RANDOM from that board's candidates. Random, so it is one
            draw, fixed by GREEDY_SEED; a different seed is a different game.

"Candidates" are the 2315 mystery answers consistent with every reply a board has
had (`wordle.pattern`, filtered from the strings' pattern matrix). A board stops
taking guesses when it is solved, and from then on its one candidate is its answer.

Cache layout (per game): guesses; for each guess j, every board's `members` (its
candidates AFTER guess j, alphabetical), its `code` for guess j (None once solved
before it), and for greedy the `target` board guess j was chosen for (None for the
opener).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
CACHE = os.path.join(HERE, "multi_cache.json")
GREEDY_SEED = 0          # the one draw shown in 16r (its first seed, not a pick)
OPENER = "solve"


def _build():
    sys.path.insert(0, os.path.join(ROOT, "math"))
    sys.path.insert(0, HERE)
    import multiwordle as mw
    import game_data

    words = os.path.join(ROOT, "math", "data", "shared", "words")
    G = [w.strip() for w in open(os.path.join(words, "guess.txt")) if w.strip()]
    A = [w.strip() for w in open(os.path.join(words, "mystery.txt")) if w.strip()]
    gi = {w: i for i, w in enumerate(G)}
    ai = {w: i for i, w in enumerate(A)}
    P = np.load(os.path.join(ROOT, "math", "data", "local", "patterns", "patterns.npy"))

    answers, replay = game_data.MULTI["octordle"]
    for a in answers:
        assert a in ai, f"{a} is not one of the 2315: no candidate set to show"
    aidx = np.array([ai[a] for a in answers])

    rng = np.random.default_rng(GREEDY_SEED)
    greedy = [G[g] for g in mw.play_game(P, mw.answer_to_guess(A, G), aidx,
                                         [gi[OPENER]], rng)]
    assert greedy[0] == OPENER

    def walk(guesses):
        alive = np.ones((len(answers), len(A)), dtype=bool)
        solved = [False] * len(answers)
        steps = []
        for g in guesses:
            row = P[gi[g]]
            # the board each guess was CHOSEN for: the greedy rule's own choice
            # (fewest candidates, ties on lowest index), recomputed from the state
            # before the guess; checked to contain the guess
            counts = [int(alive[k].sum()) if not solved[k] else len(A) + 1
                      for k in range(len(answers))]
            target = int(np.argmin(counts))
            step = {"word": g, "target": target, "boards": []}
            for k, a in enumerate(answers):
                if solved[k]:
                    step["boards"].append({"code": None, "members": [a]})
                    continue
                code = int(row[aidx[k]])
                alive[k] &= row == code
                if g == a:
                    solved[k] = True
                members = [a] if solved[k] else [A[i] for i in np.flatnonzero(alive[k])]
                step["boards"].append({"code": code, "members": members})
            steps.append(step)
        assert all(solved), "a game ended with a board unsolved"
        return steps

    out = {"answers": answers}
    for name, guesses in (("replay", replay), ("greedy", greedy)):
        steps = walk(guesses)
        if name == "greedy":
            steps[0]["target"] = None          # the opener is blind
            for j, st in enumerate(steps[1:], 1):
                prev = steps[j - 1]["boards"][st["target"]]["members"]
                assert st["word"] in prev, f"greedy guess {st['word']} not a candidate"
        else:
            for st in steps:
                st["target"] = None
        out[name] = {"guesses": guesses, "steps": steps}
    out["greedy"]["seed"] = GREEDY_SEED
    return out


def load(name):
    with open(CACHE) as f:
        return json.load(f)[name]


def answers():
    with open(CACHE) as f:
        return json.load(f)["answers"]


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f)
        f.write("\n")
    for name in ("replay", "greedy"):
        g = data[name]
        print(f"{name}: " + " ".join(w.upper() for w in g["guesses"]))
        for st in g["steps"]:
            counts = [len(b["members"]) for b in st["boards"]]
            t = "" if st["target"] is None else f"  (for board {st['target'] + 1})"
            print(f"  {st['word'].upper()}  {counts}{t}")
    print(f"wrote {CACHE}")
