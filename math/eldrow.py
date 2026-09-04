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


# --- heuristic level beam: scales to the full dictionary ----------------------

def _lex_key(state):
    return state[2]                                 # sorted_letterscore, desc tuple


def _sum_key(state):
    return sum(state[2])


def beam_stall(candidates, target, size=1000, beam_cap=1_000_000, key="lex",
               word_len=WORD_LEN):
    """Beam search for a stall of length `target`: (deepest_depth, line).

    Faithful port of the old `sizePassLevelSearch`. `levels[k]` holds states reached
    at depth k, each a `(line, candidate_list, sorted_letterscore)`; a pass walks the
    levels, expanding front states (best by `key`) until a per-level `size` budget of
    candidates is consumed, keeping each level ranked and capped at `beam_cap`. A
    branch is kept only if it could still reach `target` (`s[0] + level + 1 >=
    target`) and the guess is not already in the line.

    Returns the deepest chain FOUND — a lower bound on the true longest stall.
    `key` is "lex" (positional-diversity tuple, the original's ordering) or "sum".
    """
    n = target
    keyfn = _sum_key if key == "sum" else _lex_key
    levels = [[] for _ in range(n + 1)]
    levels[0] = [([], list(candidates), sorted_letterscore(candidates, word_len))]

    best_depth, best_line = 0, []
    while max((len(x) for x in levels), default=0) > 0 and len(levels[-1]) == 0:
        for lvl in range(len(levels) - 1):
            count = 0
            while count < size and levels[lvl]:
                line, cand, _ = levels[lvl][0]
                if lvl > best_depth:
                    best_depth, best_line = lvl, line
                count += len(cand)
                for w in cand:
                    for branch in split(cand, w).values():
                        s = sorted_letterscore(branch, word_len)
                        if s[0] + lvl + 1 >= n and w not in line:
                            levels[lvl + 1].append((line + [w], branch, s))
                levels[lvl].pop(0)
                levels[lvl + 1] = sorted(levels[lvl + 1], key=keyfn,
                                         reverse=True)[:beam_cap]
    if len(levels[-1]) > 0:
        best_depth, best_line = n, levels[-1][0][0]
    return best_depth, best_line


__all__ = ["beam_stall", "letterscore", "load_words", "longest_chain",
           "sorted_letterscore", "split"]
