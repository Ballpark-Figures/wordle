"""Antiwordle — the GREEDY heuristic for the uncertainty phase (fast, approximate).

This is the piece `antiwordle.py` deliberately leaves out.  That module models the
rules exactly and solves the |S| = 1 STALLING ENDGAME (the longest legal chain once
the answer is already known — a longest path over the constraint DAG).  The other
half of the game is the UNCERTAINTY PHASE: several candidates still alive, so a
guess partitions them and the objective averages over answers.  The exact version
of that is a max-expectimax and is expensive.  What lives here instead is a fast
GREEDY approximation to it — the code the user wrote years ago in `Puzzles/Wordle.py`
(`antiwordleAverage`), ported faithfully, cleaned up, and sped up WITHOUT changing
the number it returns.  Keep both: this gives a good answer quickly, `antiwordle.py`
gives the exact endgame.

WHAT THE NUMBER IS, precisely.  `greedy_expected(candidates, answers)` is the
EXPECTED number of guesses, averaged uniformly over the `answers` still possible,
that a SPECIFIC greedy player takes.  That player, at every step:

  1. plays the word (drawn from the CURRENT candidate list — not the full guess
     space) that MAXIMISES the expected size of the surviving candidate set, i.e.
     tries hardest to keep the pool big and avoid being cornered into the answer;
  2. then the recursion averages the continuation over the answers, weighting each
     feedback branch by how many answers actually produce it.

So it is the expected length of ONE fixed strategy, NOT the game's optimal value.
It is a heuristic: a real optimal antiwordle player could do better, and a player
restricted to guessing only current candidates (as here) could do worse than one
allowed the whole dictionary.  Both restrictions are the original code's modelling
choices, preserved on purpose.  Do not report this as "the antiwordle value."

THE RULE MODEL HERE IS THE OLD ONE, PRESERVED VERBATIM — and it is NOT the audited
model in `antiwordle.py`.  `consistent()` below is a direct transcription of the
old `antiwordleCompare`: a LOOSE consistency test that asks "could guess `g` have
produced feedback `pattern` if the answer were `w`?" and, crucially, lets one word
satisfy MANY feedback patterns.  So `antiwordle_split` is an OVERLAPPING cover, not
a partition — a word lands in every bucket it is consistent with.  `antiwordle.py`'s
`Cons`/`step`/`legal_mask` instead carry an exact green/minc/maxc/yban constraint and
give a clean partition.

THE BIGGEST DIVERGENCE IS NOT A DUPLICATE-LETTER EDGE CASE: this model has no
"a yellow must MOVE" rule at all.  `consistent()` tests only `guess[i] in word` for
a yellow tile -- presence, never position -- so it permits replaying a yellow letter
on the very square it was yellow on.  Measured example: `aahed` against `crane`
returns `y..y.`, putting `a` yellow on square 0; this model calls the follow-up
`abase` legal, and `antiwordle.py` calls it illegal.  That rule is what separates
antiwordle from ordinary hard mode, so the game modelled here is a LAXER one, its
legal sets are larger, and its numbers are NOT comparable with the stall values in
`antiwordle.py`.  Kept deliberately so this reproduces the old answers; if you want
the audited semantics, that is a different computation, not a bug to fix here.

WORD LISTS ARE OURS, NOT ANTIWORDLE.COM's — the 12972/2315 Wordle lists this whole
video runs on (`load_words`).  antiwordle.com's dictionary is not ours, so a number
here is a fact about OUR lists.

EFFICIENCIES over the original, each proven not to change the returned value:
  - `answers` is a set, so membership is O(1) (the original scanned a list);
  - the winning guess's split is materialised ONCE, not rebuilt for every candidate
    (selection needs only bucket SIZES, computed as a histogram);
  - a feedback branch with zero answers is skipped, because its contribution is
    `0 * continuation == 0` (the original still recursed into it);
  - the selection average is summed in the SAME float order as the original, so the
    argmax — and therefore the whole value — is bit-identical.
`tools/checkantigreedy.py` diffs this module against a verbatim copy of the old
functions on random inputs to keep that guarantee honest.

    from antiwordle_greedy import greedy_expected, greedy_opener, load_words
    ans = load_words("mystery")                 # the 2315
    word, keep = greedy_opener(ans, set(ans))   # fast: the greedy first guess
    exp = greedy_expected(ans, set(ans))         # full recursion (slow on 2315)
"""

from wordle import N_PATTERNS, WORD_LEN, decode, load_words, pattern

# decode() per call would dominate; 243 codes is a trivial table (same trick as
# antiwordle.py). TRITS[code] is the pattern as a WORD_LEN-tuple of tile codes.
TRITS = tuple(decode(code) for code in range(N_PATTERNS))


def consistent(guess, word, trits):
    """Could `guess` have shown feedback `trits` if the answer were `word`?

    Verbatim transcription of the old `antiwordleCompare` (loose consistency, so a
    single word satisfies many patterns — see the module docstring). `guess` and
    `word` are equal-length strings; `trits` is a per-square tile tuple, 0 grey /
    1 yellow / 2 green (e.g. `TRITS[code]`).
    """
    word_len = len(guess)
    for i in range(word_len):
        if trits[i] == 2 and guess[i] != word[i]:
            return False
        elif trits[i] == 1 and guess[i] not in word:
            return False
        elif trits[i] == 0 and guess[i] in word:
            found = False
            for j in range(word_len):
                if word[j] == guess[i] and trits[j] != 2:
                    found = True
            if found:
                for j in range(i):
                    if guess[j] == guess[i]:
                        found = False
            if found:
                return False
    return True


def antiwordle_split(candidates, guess):
    """Overlapping cover of `candidates` by every feedback `guess` is consistent with.

    Verbatim port of the old `antiwordleSplit`: for each candidate and each of the
    N_PATTERNS codes, if the candidate is `consistent` with that code, it joins that
    code's bucket. A candidate therefore appears in SEVERAL buckets — this is a
    cover, not a partition (the whole point of the old rule model).
    """
    buckets = {}
    for word in candidates:
        for code in range(N_PATTERNS):
            if consistent(guess, word, TRITS[code]):
                buckets.setdefault(code, []).append(word)
    return buckets


def _bucket_sizes(candidates, guess):
    """For `guess`, the size of each feedback bucket, over only the codes that occur.

    Selection needs `len(bucket[feedback(guess, x)])` for every candidate x; that is
    a bucket SIZE, not its contents, so we count instead of materialising lists (the
    single biggest saving over the original, which built a full split per guess). We
    only ever ask about codes that some candidate's TRUE feedback lands in, so we
    size exactly those.
    """
    needed = {pattern(guess, x) for x in candidates}
    sizes = dict.fromkeys(needed, 0)
    tri = {code: TRITS[code] for code in needed}
    for word in candidates:
        for code in needed:
            if consistent(guess, word, tri[code]):
                sizes[code] += 1
    return sizes


def greedy_opener(candidates, answers):
    """The greedy guess and the expected surviving-set size it achieves.

    Picks, from `candidates`, the word maximising the expected size of the surviving
    candidate set — the single step of the greedy strategy, with no
    recursion. MEASURED at about n**2.2, which is ~2.3 minutes on the full 2315 --
    affordable, but not instant. Returns `(word, expected_keep)`. Ties break to the
    first such word in `candidates` order, exactly as the original.
    """
    n = len(candidates)
    best, best_word = -1.0, None
    for guess in candidates:
        sizes = _bucket_sizes(candidates, guess)
        # Summed in the ORIGINAL order (one term per candidate) so the float value —
        # and hence the argmax — matches the old code bit for bit.
        keep = 0.0
        for x in candidates:
            keep += sizes[pattern(guess, x)] / n
        if keep > best:
            best, best_word = keep, guess
    return best_word, best


def greedy_expected(candidates, answers, _verbose=False):
    """Expected guesses of the greedy player, averaged over `answers` (a set).

    Faithful port of the old `antiwordleAverage` (its dead `guess` argument, threaded
    but never read, is dropped). `answers` is the set of words that are possible
    solutions; `candidates` is the current live list the player guesses from. Recurses
    to termination — the state graph is a DAG under the old model too — so on the full
    2315 this is slow by construction; hand it a reduced list (post-opening state, or
    a sample) for a quick figure, as the original did.
    """
    mystery_count = sum(1 for w in candidates if w in answers)
    if len(candidates) == 1 and mystery_count == 1:
        return 1.0
    if mystery_count == 0:
        return 0.0

    # --- greedy selection: keep the pool as big as possible ------------------
    n = len(candidates)
    best, best_word = -1.0, None
    for guess in candidates:
        if _verbose:
            print(guess, len(candidates))
        sizes = _bucket_sizes(candidates, guess)
        keep = 0.0
        for x in candidates:
            keep += sizes[pattern(guess, x)] / n
        if keep > best:
            best, best_word = keep, guess

    # --- average the continuation over the answers ---------------------------
    split = antiwordle_split(candidates, best_word)
    total = 0.0
    for code, bucket in split.items():
        if best_word in bucket:
            bucket.remove(best_word)
        mc = sum(1 for j in bucket if j in answers and pattern(best_word, j) == code)
        if mc:                                  # 0 * continuation == 0 — skip it
            total += mc * greedy_expected(bucket, answers, _verbose)
    total /= mystery_count
    total += 1.0
    if _verbose:
        print(total, best_word)
    return total


__all__ = ["TRITS", "antiwordle_split", "consistent",
           "greedy_expected", "greedy_opener", "load_words", "pattern"]
