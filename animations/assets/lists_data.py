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
  groups / chain         — the answers partitioned by pattern(guess, answer); code
                           and tiles decoded POSITION 0 MOST SIGNIFICANT, as
                           game_data.py does; `size` is the WHOLE group, `members`
                           the words shown (alphabetical)
  full                   — scene 06b: EVERY group of each FULL_GUESSES guess, all
                           members, largest first (ties by code)

THE GUESSES: the first is "the topmost guess" of the list (04d), read from
guess.txt, never typed; PIGGY and CODES are the script's own choices (04e).

WHICH GROUPS ARE SHOWN IS A DISPLAY CHOICE, NOT A RESULT — flagged for the user.
A guess makes 54-98 groups of up to 981 answers, far more than a frame holds. Two
rules, for two situations:

  groups[guess] — SIZE TARGETS (04d from the column, 04i). For each size in
    TARGETS, the group whose size is NEAREST it, ties to the alphabetically earliest
    first member (so words already on screen tend to be picked); never the same
    group twice. Every member is shown, so the ovals really differ in size.

  chain[guess] — CARRY-OVER (04e, PIGPEN guess after guess). Every word on screen
    lands in SOME group of the next guess, so the groups shown are the ones holding
    the most on-screen words (at most CHAIN_GROUPS, ties to the smaller group).
    Each shows the words it carries over (at most CHAIN_CAP), topped up with up to
    CHAIN_TOP_UP newcomers — its alphabetically first other members. So most words
    stay put and move between ovals, and a few come and go.

  groups_edge / chain_edge — EDGE groups (`_edges`), hung off the frame's edges by
    the scene so the grouping reads as covering every answer: further real groups,
    those holding on-screen words first, then the largest. The carry-over chain
    does NOT count edge words as on screen — they stand for the rest.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "lists_cache.json")
WORDS = os.path.join(HERE, "..", "..", "math", "data", "shared", "words")

HEAD = 20                         # guess-list lines cached (the scene shows fewer)
SCRIPT_GUESSES = ["piggy", "codes"]
TARGETS = [1, 1, 2, 3, 4, 5, 7, 9, 12, 16]   # size-target rule: one group each
CHAIN_GROUPS = 10                 # carry-over rule: most groups shown
CHAIN_CAP = 16                    # most words shown in one group
CHAIN_TOP_UP = 3                  # newcomers added to a group
N_EDGE = 8                        # edge groups cached (the scene uses as many as fit)
EDGE_CAP = 9                      # most words shown in one edge group
COLUMN = 12                       # answers in the on-screen column (scene N_ROWS)
FULL_GUESSES = ["piggy"]          # guesses whose EVERY group is cached (06b's dots)


def _read(name):
    return [w.strip() for w in open(os.path.join(WORDS, name)) if w.strip()]


def _pick(groups):
    """Size-target rule (see the module docstring)."""
    chosen = []
    for t in TARGETS:
        best = min((g for g in groups if g not in chosen),
                   key=lambda g: (abs(len(g["members"]) - t), g["members"][0]))
        chosen.append(best)
    return sorted(chosen, key=lambda g: len(g["members"]))


def _chain(groups, on_screen):
    """Carry-over rule (see the module docstring)."""
    carried = [(g, [w for w in g["members"] if w in on_screen]) for g in groups]
    carried = [(g, c) for g, c in carried if c]
    carried.sort(key=lambda gc: (-len(gc[1]), len(gc[0]["members"])))
    out = []
    for g, c in carried[:CHAIN_GROUPS]:
        keep = c[:CHAIN_CAP]
        room = min(CHAIN_TOP_UP, CHAIN_CAP - len(keep))
        new = [w for w in g["members"] if w not in on_screen][:max(room, 0)]
        out.append(dict(g, members=sorted(keep + new)))
    return sorted(out, key=lambda g: len(g["members"]))


def _edges(groups, shown, on_screen):
    """EDGE groups — ovals hanging off the frame's edges, so it reads as if every
    group is out there somewhere. Real groups not already `shown`: those holding the
    most words on screen first, then the largest. Each shows up to CHAIN_CAP
    members, its on-screen words first."""
    taken = {g["code"] for g in shown}
    rest = [g for g in groups if g["code"] not in taken]
    rest.sort(key=lambda g: (-sum(w in on_screen for w in g["members"]), -g["size"],
                             g["code"]))
    out = []
    for g in rest[:N_EDGE]:
        keep = [w for w in g["members"] if w in on_screen]
        fill = [w for w in g["members"] if w not in on_screen]
        out.append(dict(g, members=sorted((keep + fill)[:EDGE_CAP])))
    return out


def _words(*selections):
    return {w for sel in selections for grp in sel for w in grp["members"]}


def _build():
    sys.path.insert(0, os.path.join(HERE, "..", "..", "math"))
    import wordle

    answers, guesses = _read("mystery.txt"), _read("guess.txt")
    assert answers == sorted(answers) and guesses == sorted(guesses)
    order = [guesses[0]] + SCRIPT_GUESSES
    out = {"n_answers": len(answers), "n_guesses": len(guesses),
           "answers": answers, "guesses_head": guesses[:HEAD], "guesses": order,
           "groups": {}, "chain": {}}
    full = {}
    for g in order:
        assert g in guesses, f"{g} is not a legal guess"
        by_code = {}
        for a in answers:                          # answers is alphabetical, so
            by_code.setdefault(wordle.pattern(g, a), []).append(a)   # members are too
        full[g] = [{"code": int(c), "tiles": [(c // 3 ** (4 - i)) % 3 for i in range(5)],
                    "size": len(m), "members": m} for c, m in by_code.items()]
        out["groups"][g] = _pick(full[g])
    # size-target selections start from the answer column (04d, 04i)
    column = set(answers[:COLUMN])
    out["groups_edge"] = {g: _edges(full[g], out["groups"][g], column) for g in order}
    # 06b: every group of the dotted guess, largest first
    out["full"] = {g: sorted(full[g], key=lambda grp: (-grp["size"], grp["code"]))
                   for g in FULL_GUESSES}
    # 04e: each guess regroups what the one before it left in its INTERIOR ovals —
    # edge words stand for "the rest", and counting them swamped every group
    shown = _words(out["groups"][order[0]])
    out["chain_edge"] = {}
    for g in SCRIPT_GUESSES:
        out["chain"][g] = _chain(full[g], shown)
        out["chain_edge"][g] = _edges(full[g], out["chain"][g], shown)
        now = _words(out["chain"][g])
        out.setdefault("carry", {})[g] = [len(shown & now), len(shown), len(now)]
        shown = now
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

    def show(title, groups):
        print(title)
        for grp in groups:
            tiles = "".join(names[t] for t in grp["tiles"])
            print(f"  {tiles}  {len(grp['members']):2d} of {grp['size']:4d}  "
                  f"{' '.join(grp['members'])}")

    print(f"{data['n_answers']} answers, {data['n_guesses']} guesses")
    for g in data["guesses"]:
        show(f"{g.upper()} (size targets)", data["groups"][g])
        show("  + edge groups", data["groups_edge"][g])
    for g in SCRIPT_GUESSES:
        stay, before, after = data["carry"][g]
        show(f"{g.upper()} (carry-over: {stay} of {before} stay, {after} shown)",
             data["chain"][g])
        show("  + edge groups", data["chain_edge"][g])
    print(f"\nwrote {CACHE}")
