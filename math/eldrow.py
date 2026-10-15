"""Eldrow — longest-stall search over the NARROWING game (exact + beam).

A third antiwordle method, ported from the user's old `Puzzles/Eldrow.py`, and a
different objective from both siblings:

  - `antiwordle.py`     EXACT longest stall in the |S| = 1 endgame — the answer is
                        already KNOWN, guesses come from the whole dictionary, and
                        it is a longest path over the audited constraint DAG.
  - `antiwordle_greedy` the greedy EXPECTED-length heuristic for the uncertainty
                        phase (keep the pool big, average over answers).
  - THIS FILE           longest stall over the NARROWING game: at each step you play
                        a word FROM THE CURRENT CANDIDATE LIST and follow a feedback
                        branch, maximising how deep the chain goes. Two flavours: an
                        EXACT branch-and-bound (`longest_chain`, small lists only) and
                        a heuristic level BEAM (`beam_stall`) that scales to the full
                        list by targeting a specific depth.

WHAT THE NUMBER IS, precisely.  `longest_chain(cand)` returns the maximum, over all
choices of guess (drawn from the live candidate list) AND feedback branch at every
step, of the number of guesses played before the list collapses to a single word.
It does NOT count the final forced naming of that word — the old code returned
`level - 1`, i.e. guesses-until-a-singleton, and that is preserved.  So it is one
LESS than a "guesses to finish" count; add 1 if you want that.

GUESSES ARE RESTRICTED TO THE CURRENT CANDIDATES — the old code's `split(l, l[i])`
only ever tries `l[i]` in `l`.  This is a real modelling choice and NOT the same as
antiwordle.py, which plays from all 12972.  A different guess space is a different
objective; this one is the old file's, kept as-is.

BOUNDS ARE PART OF THE OBJECTIVE — do not assume either is free.
  - `bound="size"` is the original `allSplit`: prune when `len(prev) + len(cand)`
    cannot beat the incumbent.  Since the chain from `cand` adds at most `len(cand)`
    more guesses, this is a sound upper bound, so the search stays EXACT.
  - `bound="letters"` is the original `betterAllSplit`: prune at the ROOT on
    `len(prev) + max(letterscore(cand))` instead, then recurse with the `size`
    bound below (a faithful port of the original, quirk and all — its recursion
    calls the size-bounded search, so the tighter test only fires once).  Whether
    `max(letterscore)` is a valid upper bound on remaining depth is NOT proved
    here, so this option can in principle prune the optimum and report LOW.  It is
    offered because the old code had it; `tools/checkeldrow.py` diffs both against
    the verbatim originals, which is a check of PORT FIDELITY, not of the bound.

`beam_stall(cand, target)` is a HEURISTIC.  It does a level-indexed beam search
seeking a chain of length `target`, keeping states ranked by positional letter
diversity (`sorted_letterscore`) and capping each level's width.  It returns the
deepest chain it FOUND — a LOWER bound on the true longest stall, never an upper
one.  With the width cap and depth-reachability filter removed it becomes the
exhaustive search and agrees with `longest_chain`; that is the fidelity anchor.

WORD LISTS ARE OURS, NOT ANTIWORDLE.COM's (the 12972/2315 Wordle lists), so a
number here is a fact about OUR lists — the stalling junk is the most likely to
differ from the live game.

EFFICIENCIES over the original, none of which change a returned value: feedback via
`wordle.pattern` (encoded, so split keys are ints); `prev + [w]` shallow copies in
place of `copy.deepcopy` (the lines hold immutable strings); and the branch-and-
bound incumbent threaded through return values exactly as the original did, so the
same subtree is proven worse and skipped.

    from eldrow import longest_chain, beam_stall, load_words
    best_len, line = longest_chain(sample)              # exact, small lists
    depth, line = beam_stall(load_words("guess"), 17)   # beam, full dictionary
"""

import random

from wordle import WORD_LEN, load_words, pattern


def split(candidates, guess):
    """Partition `candidates` by `guess`'s feedback. Keys are encoded patterns.

    The old `split` keyed on the pattern TUPLE; an encoded int is the same
    partition by a cheaper key, so every downstream count and line is identical.
    """
    buckets = {}
    for word in candidates:
        buckets.setdefault(pattern(guess, word), []).append(word)
    return buckets


def letterscore(candidates, word_len=WORD_LEN):
    """Distinct letters appearing in each square, across `candidates`.

    A per-position spread measure: `letterscore(cand)[i]` is how many different
    letters sit in square i somewhere in the list. Verbatim port (the old hard-coded
    5 is now `word_len`).
    """
    seen = [set() for _ in range(word_len)]
    for w in candidates:
        for i in range(word_len):
            seen[i].add(w[i])
    return [len(s) for s in seen]


def sorted_letterscore(candidates, word_len=WORD_LEN):
    """`letterscore` sorted descending, as a tuple — the beam's ranking key."""
    return tuple(sorted(letterscore(candidates, word_len), reverse=True))


# --- exact branch-and-bound: the longest achievable chain ---------------------

def _all_split(prev, cand, level, bestsofar):
    """Faithful port of the old `allSplit` (the `size` bound). Returns (line, len)."""
    if len(cand) == 1:
        return (prev, level - 1)
    if len(prev) + len(cand) <= bestsofar:          # sound: <= len(cand) more moves
        return ([], 0)
    best_len, best_line = 0, []
    for w in cand:
        for branch in split(cand, w).values():
            line, val = _all_split(prev + [w], branch, level + 1, bestsofar)
            if val > best_len:
                best_len, best_line = val, line
                if val > bestsofar:
                    bestsofar = val                 # incumbent, threaded as original
    return (best_line, best_len)


def _better_all_split(prev, cand, level, bestsofar, word_len):
    """Faithful port of `betterAllSplit`: the `letters` bound at the root only.

    Preserves the original's quirk exactly — its recursion drops back to the
    size-bounded `_all_split`, so the `max(letterscore)` test fires just once.
    """
    if len(cand) == 1:
        return (prev, level - 1)
    if len(prev) + max(letterscore(cand, word_len)) <= bestsofar:
        return ([], 0)
    best_len, best_line = 0, []
    for w in cand:
        for branch in split(cand, w).values():
            line, val = _all_split(prev + [w], branch, level + 1, bestsofar)
            if val > best_len:
                best_len, best_line = val, line
                if val > bestsofar:
                    bestsofar = val
    return (best_line, best_len)


def longest_chain(candidates, bound="size", word_len=WORD_LEN):
    """Exact longest narrowing chain from `candidates`: (length, line).

    `length` is guesses-until-a-singleton (NOT counting the final naming — see the
    module docstring). `bound` selects the pruning test: "size" (exact) or "letters"
    (the old better-bounded variant; see the bound note above). Exponential in the
    worst case — for small lists only; use `beam_stall` on the full dictionary.
    """
    if bound == "letters":
        line, length = _better_all_split([], list(candidates), 1, 0, word_len)
    else:
        line, length = _all_split([], list(candidates), 1, 0)
    return length, line


def longest_run(plays, answers):
    """Exact longest run when only the LAST word must be an answer: (length, line).

    The rule (the user's, 2026-10-14): every word played must be in `plays` AND
    consistent with every clue so far; the run ends by playing the answer, which
    must be in `answers` (itself a subset of `plays`).  Clues are taken against
    that final answer, so a branch is only followable while it still holds an
    answer.  `length` COUNTS THE FINAL ANSWER, as eldrowmax does -- unlike
    `longest_chain` above, which counts guesses-until-a-singleton.

    The REFERENCE for `eldrowmax --answers`.  It recomputes the legal set FROM THE
    STRINGS, over the whole of `plays`, from the history at every step, and
    memoises only on the result.  Exponential: small lists only.
    """
    plays = list(plays)
    answers = set(answers)
    if not answers <= set(plays):
        raise ValueError("every answer must be playable")
    memo = {}

    def legal(history):
        return tuple(w for w in plays
                     if all(pattern(g, w) == p for g, p in history))

    def best(history):
        live = legal(history)
        if live in memo:
            return memo[live]
        poss = [w for w in live if w in answers]
        out = (1, [poss[0]])                     # name an answer now
        for g in live:
            for p in sorted({pattern(g, a) for a in poss}):
                if p == ALL_GREEN_CODE:
                    continue
                n, line = best(history + ((g, p),))
                if 1 + n > out[0]:
                    out = (1 + n, [g] + line)
        memo[live] = out
        return out

    if not answers:
        return 0, []
    n, line = best(())
    return n, line


ALL_GREEN_CODE = 3 ** WORD_LEN - 1


# --- heuristic level searches: scale to the full dictionary -------------------
#
# All the old beam controllers (sizePassLevelSearch, passLevelSearch, levelSearch,
# sumLevelSearch, newLevelSearch, randSizePassLevelSearch) share ONE inner move:
# expand a state -> append its reachable children to the next level -> re-rank ->
# drop it. `_expand` is that move, so each controller below is just a different
# rule for WHICH state to expand next. They differ only in the controller, never
# in the expansion, which is why they all agree with the exact search in the limit.

def _lex_key(state):
    return state[2]                                 # sorted_letterscore, desc tuple


def _sum_key(state):
    return sum(state[2])


def _expand(levels, lvl, idx, target, keyfn, cap, word_len):
    """Expand `levels[lvl][idx]`: append reachable children to lvl+1, re-rank, drop it.

    A branch is kept only if it could still reach `target` (`s[0] + lvl + 1 >=
    target`, the original reachability filter) and its guess is not already in the
    line. Returns the expanded state's candidate count — the budget unit the
    size-limited controllers spend. `cap` truncates the re-ranked level, or None
    leaves it whole (the uncapped controllers).
    """
    line, cand, _ = levels[lvl][idx]
    for w in cand:
        for branch in split(cand, w).values():
            s = sorted_letterscore(branch, word_len)
            if s[0] + lvl + 1 >= target and w not in line:
                levels[lvl + 1].append((line + [w], branch, s))
    levels[lvl].pop(idx)
    levels[lvl + 1] = sorted(levels[lvl + 1], key=keyfn, reverse=True)
    if cap is not None:
        levels[lvl + 1] = levels[lvl + 1][:cap]
    return len(cand)


def _new_levels(candidates, target, word_len):
    levels = [[] for _ in range(target + 1)]
    levels[0] = [([], list(candidates), sorted_letterscore(candidates, word_len))]
    return levels


def beam_stall(candidates, target, size=1000, beam_cap=1_000_000, key="lex",
               rand_top=None, rng=random, word_len=WORD_LEN):
    """Pass-sweep beam for a stall of length `target`: (deepest_depth, line).

    Faithful port of the old `sizePassLevelSearch`, and — with `rand_top` set — of
    `randSizePassLevelSearch`. `levels[k]` holds states reached at depth k, each a
    `(line, candidate_list, sorted_letterscore)`; a pass walks the levels, spending a
    per-level `size` budget of candidates, keeping each level ranked by `key` and
    capped at `beam_cap`.

    `rand_top` chooses which state to expand: None takes the front (best by `key`,
    the sizePass behaviour); an int r picks a RANDOM state among the top r (the
    randSizePass behaviour, which keeps NO cap — pass `beam_cap=None` to match it
    exactly). `rng` is the source of randomness (the `random` module by default, so
    `random.seed(...)` makes a run reproducible). `key` is "lex" or "sum".

    Returns the deepest chain FOUND — a lower bound on the true longest stall.
    """
    n = target
    keyfn = _sum_key if key == "sum" else _lex_key
    levels = _new_levels(candidates, n, word_len)

    best_depth, best_line = 0, []
    while max((len(x) for x in levels), default=0) > 0 and len(levels[-1]) == 0:
        for lvl in range(len(levels) - 1):
            count = 0
            while count < size and levels[lvl]:
                if rand_top is None:
                    idx = 0
                elif len(levels[lvl]) >= rand_top:
                    idx = int(rng.random() * rand_top)
                else:
                    idx = int(rng.random() * len(levels[lvl]))
                if lvl > best_depth:
                    best_depth, best_line = lvl, levels[lvl][idx][0]
                count += _expand(levels, lvl, idx, n, keyfn, beam_cap, word_len)
    if len(levels[-1]) > 0:
        best_depth, best_line = n, levels[-1][0][0]
    return best_depth, best_line


# --- single-level controllers: pick ONE level per step, by a drop heuristic ----

def best_level(levels, drop=5):
    """First level whose successor is empty or `drop` behind on the top score[0].

    Verbatim port of the old `bestLevel`: scans levels for the frontier to work on
    next. Returns None if none qualifies (the original would then index `None` and
    crash; `heuristic_search` stops instead — see its note).
    """
    for i in range(len(levels) - 1):
        if len(levels[i]) > 0 and (len(levels[i + 1]) == 0
                                   or levels[i + 1][0][2][0] < levels[i][0][2][0] - drop):
            return i
    return None


def sum_best_level(levels, drop=35):
    """`best_level` measured by the SUM of the score tuple (old `sumBestLevel`)."""
    for i in range(len(levels) - 1):
        if len(levels[i]) > 0 and (len(levels[i + 1]) == 0
                                   or sum(levels[i + 1][0][2]) < sum(levels[i][0][2]) - drop):
            return i
    return None


def new_best_level(levels, counts, drop=5, count_cap=100):
    """`best_level` with a visit counter so it rotates off a stuck level.

    Verbatim port of `newBestLevel`, quirks preserved: it also fires when a level
    has been picked `count_cap` times, bumps that level's counter, and (as written)
    zeroes only the NEXT level's counter before returning. `counts` is mutated.
    """
    for i in range(len(levels) - 1):
        if len(levels[i]) > 0 and (len(levels[i + 1]) == 0 or counts[i + 1] >= count_cap
                                   or levels[i + 1][0][2][0] < levels[i][0][2][0] - drop):
            counts[i] += 1
            for j in range(i + 1, len(levels)):
                counts[j] = 0
                return i
    return None


def heuristic_search(candidates, target, selector="best", drop=None,
                     count_cap=100, word_len=WORD_LEN):
    """Single-level stall search: expand one front state per step, by `selector`.

    Faithful port of the old `levelSearch` / `sumLevelSearch` / `newLevelSearch`:
    each step picks ONE level via a drop heuristic and expands its front state, with
    NO width cap. `selector` is "best" (bestLevel + lex ranking), "sum" (sumBestLevel
    + sum ranking) or "new" (newBestLevel + lex ranking). `drop` overrides the
    heuristic's threshold (defaults: 5 for best/new, 35 for sum, the originals).

    Returns (deepest_depth, line). ONE intentional deviation from the originals: if
    the selector qualifies no level it returns None, where the original would crash
    on `levels[None]`; here the search stops and returns what it has. That case is
    effectively unreachable under the while guard (the frontier always qualifies),
    so it changes no reachable result — it just fails safe instead of raising.
    """
    keyfn = _sum_key if selector == "sum" else _lex_key
    default_drop = 35 if selector == "sum" else 5
    d = default_drop if drop is None else drop
    levels = _new_levels(candidates, target, word_len)
    counts = [0] * len(levels)                       # used only by "new"

    best_depth, best_line = 0, []
    while max((len(x) for x in levels), default=0) > 0 and len(levels[-1]) == 0:
        if selector == "sum":
            lvl = sum_best_level(levels, d)
        elif selector == "new":
            lvl = new_best_level(levels, counts, d, count_cap)
        else:
            lvl = best_level(levels, d)
        if lvl is None:
            break
        if lvl > best_depth:
            best_depth, best_line = lvl, levels[lvl][0][0]
        _expand(levels, lvl, 0, target, keyfn, None, word_len)
    if len(levels[-1]) > 0:
        best_depth, best_line = target, levels[-1][0][0]
    return best_depth, best_line


__all__ = ["beam_stall", "best_level", "heuristic_search", "letterscore",
           "load_words", "longest_chain", "new_best_level", "sorted_letterscore",
           "split", "sum_best_level"]
