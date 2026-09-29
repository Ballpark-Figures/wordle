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
  full                   — scene 06b/c: EVERY group of each FULL_GUESSES guess, all
                           members, largest first (ties by code)

THE GUESSES: the first is "the topmost guess" of the list (04d), read from
guess.txt, never typed; PIGGY and CODES are the script's own choices (04e).

EVERY GROUP SHOWN IS SHOWN WHOLE — every member, never a sample (bpkfigures
CLAUDE.md, "never depict a part as the whole"). A guess makes 54-150 groups of up
to 981 answers, far more than a frame holds, so what is chosen is WHICH groups:
only ones small enough to show complete. Three rules, for three situations:

  groups[guess] — SIZE TARGETS (04d from the column, 04i). For each size in
    TARGETS, the group whose size is NEAREST it, ties to the alphabetically earliest
    first member (so words already on screen tend to be picked); never the same
    group twice. Every member is shown, so the ovals really differ in size.

  chain[guess] — CARRY-OVER (04e, PIGPEN guess after guess; 06a). Among the groups
    of at most CHAIN_MAX answers, the ones holding the most on-screen words (at most
    CHAIN_GROUPS, ties to the smaller group), each with ALL its members; few small
    groups carry anything over, so the rest of the CHAIN_GROUPS are filled by the
    size targets among the small groups. Words carried over stay on screen and
    move between ovals; the rest come and go.

  groups_edge / chain_edge — EDGE groups (`_edges`), hung off the frame's edges by
    the scene so the grouping reads as covering every answer: further real groups of
    at most EDGE_MAX answers, each with ALL its members, those holding on-screen
    words first, then the largest. The carry-over chain does NOT count edge words as
    on screen.

  (Until 2026-09-28 the carry-over and edge groups were CAPPED — CODES's 302-answer
  all-grey group appeared as 16 words, PIGGY's 981 as 9. That misrepresented them
  and is gone.)
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
CHAIN_MAX = 16                    # largest group the carry-over rule may show
N_EDGE = 8                        # edge groups cached (the scene uses as many as fit)
EDGE_MAX = 9                      # largest group hung off an edge
COLUMN = 12                       # answers in the on-screen column (scene N_ROWS)
FULL_GUESSES = ["codes", "trace", "roate", "arise", "aurei"]   # guesses whose EVERY group is cached (06b/c's dots)


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
    carried = [(g, sum(w in on_screen for w in g["members"]))
               for g in groups if g["size"] <= CHAIN_MAX]
    carried = [(g, n) for g, n in carried if n]
    carried.sort(key=lambda gn: (-gn[1], gn[0]["size"], gn[0]["code"]))
    out = [g for g, _ in carried[:CHAIN_GROUPS]]
    # few small groups carry words over, so fill up to CHAIN_GROUPS by the size
    # targets, among the small groups not already taken
    for t in TARGETS:
        if len(out) >= CHAIN_GROUPS:
            break
        rest = [g for g in groups if g["size"] <= CHAIN_MAX and g not in out]
        if rest:
            out.append(min(rest, key=lambda g: (abs(g["size"] - t), g["members"][0])))
    assert all(len(g["members"]) == g["size"] for g in out)
    return sorted(out, key=lambda g: g["size"])


def _edges(groups, shown, on_screen):
    """EDGE groups — ovals hanging off the frame's edges, so it reads as if every
    group is out there somewhere. Real groups not already `shown`: those holding the
    most words on screen first, then the largest, of at most EDGE_MAX answers —
    each shown whole."""
    taken = {g["code"] for g in shown}
    rest = [g for g in groups if g["code"] not in taken and g["size"] <= EDGE_MAX]
    rest.sort(key=lambda g: (-sum(w in on_screen for w in g["members"]), -g["size"],
                             g["code"]))
    out = rest[:N_EDGE]
    assert all(len(g["members"]) == g["size"] for g in out)
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
    def partition(g):
        assert g in guesses, f"{g} is not a legal guess"
        by_code = {}
        for a in answers:                          # answers is alphabetical, so
            by_code.setdefault(wordle.pattern(g, a), []).append(a)   # members are too
        return [{"code": int(c), "tiles": [(c // 3 ** (4 - i)) % 3 for i in range(5)],
                 "size": len(m), "members": m} for c, m in by_code.items()]

    full = {}
    for g in order:
        full[g] = partition(g)
        out["groups"][g] = _pick(full[g])
    # size-target selections start from the answer column (04d, 04i)
    column = set(answers[:COLUMN])
    out["groups_edge"] = {g: _edges(full[g], out["groups"][g], column) for g in order}
    # 06b/c: every group of each dotted guess, largest first
    out["full"] = {g: sorted(full.get(g) or partition(g),
                             key=lambda grp: (-grp["size"], grp["code"]))
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
    # every group any scene shows is whole — never a part standing for the whole
    for key in ("groups", "groups_edge", "chain", "chain_edge", "full"):
        for g, grps in out[key].items():
            for grp in grps:
                assert len(grp["members"]) == grp["size"], (key, g, grp["code"])
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
