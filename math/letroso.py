"""Letroso rules -- THE SOURCE OF TRUTH.  Read this before quoting any number.

Letroso (letroso.com, by Daydash -- the Contexto/Conexo/Expresso studio) is a
daily word game that is NOT Wordle and shares none of its feedback structure.
Everything below was recovered from the shipped application bundle
(`assets/index-*.js`, functions `zT` and `BT`) and VERIFIED: the port here
reproduces all twelve worked examples in the game's own instructions modal, in
all three languages it ships (en `example`, pt `exemplo`, es `ejemplo`),
class-for-class.  See tools/checkletroso.py, which pins that.

THE RULES, stated exactly.

  * You type any word of 1..MAXLEN letters.  MAXLEN is 10, and it is the cap on
    what you can TYPE (`Pa=10` in the bundle), which is what bounds the answer
    too -- an 11-letter answer could never be entered.  THE ANSWER'S LENGTH IS
    NOT SHOWN.  There is no grid of known width, so length is something you
    infer, not something you are given.  This is the single biggest structural
    difference from every other solver in this repo.
  * There is NO GUESS LIMIT.  So the objective here is expected guesses
    OUTRIGHT, never "subject to a guarantee"; see letroso_topk.py.
  * Feedback is a MAXIMUM-SCORING LONGEST-COMMON-SUBSEQUENCE ALIGNMENT between
    the guess and the answer.  Each guess letter comes back as one of:
      - `head`/`tail` (2/3): the letter is part of the alignment, i.e. these
        letters occur in the answer IN THAT RELATIVE ORDER.  A maximal run of
        letters that are consecutive in BOTH guess and answer is drawn as one
        connected block -- `head` is its first tile, `tail` the rest.  Those
        blocks are what the game's marketing calls "connection lines".
      - `present` (1): the letter occurs in the answer by MULTISET COUNT but is
        not in the alignment -- "in the word, but out of order".
      - `absent` (0): not in the answer, or its count is already used up.
    plus two flags: `start` when the alignment begins at answer[0] AND guess[0],
    `end` when it ends at the last letter of both.  Those are what render as
    "the word starts with EX and ends with E".
  * Accents are stripped (NFD, combining marks dropped) before ANY comparison,
    so `ejercito` and `ejército` are the same word to the matcher.
  * ONE special case: if the alignment has exactly one matched letter and that
    match is neither at the start nor the end, it is downgraded from `head` to
    `present`.  A lone letter is not a "block".

HOW THE ALIGNMENT IS CHOSEN, which is where all the subtlety lives.  Among all
alignments of MAXIMUM CARDINALITY (the game's DP allows a diagonal step only on
equal letters, so minimum cost == maximum matches == LCS), it maximises

    d = 3 * sum over matches of (position within its run) + start + end

so a contiguous run of length L is worth 3*L*(L+1)/2 -- superlinear, which is
why contiguity dominates.  Among alignments tied on d it takes the
lexicographically LARGEST pattern digit string (3 beats 2 beats 1 beats 0,
compared left to right).

  KNOWN AMBIGUITY, recorded rather than papered over.  The game's tie-break is
  `o.sort((e,t) => e.pattern.join() < t.pattern.join() ? 1 : -1)`, which returns
  -1 for EQUAL patterns and is therefore not a consistent comparator.  When two
  d-optimal alignments produce the identical digit string but differ in their
  start/end flags, which one is displayed is up to the JS engine's sort.  We
  resolve it stably, keeping the first in enumeration order, which is what
  reproduced all twelve tutorial rows.  tools/checkletroso.py MEASURES how often
  the situation can arise at all, so the exposure is a number and not a shrug.

WORD LISTS.  The GUESS list IS letroso's own (letroso.com's client validation
list, `assets/all-en-<hash>.js`) -- a word we accept is a word letroso accepts,
and one it rejects (e.g. `clarionets`) we reject too.  The ANSWER list is still
OURS and is NOT letroso's: the game's real answer set is server-side and we do
not have it, so we model it from hello wordl's curated `targets.json`,
intersected with letroso's guess list.  Lengths 2 and 3 have no hello answers
and their answer lists are built by our own frequency rule.  Everything lives
under `data/shared/words/letroso/len<L>/`; see build_letroso_lists.py.  So a
number here still describes THIS game on THESE lists, never letroso.com -- but
the guess half now matches the live game exactly.
"""

from __future__ import annotations

import os
import unicodedata

MAXLEN = 10        # `Pa` in the bundle: the longest word that can be TYPED
MINLEN = 2         # letroso's list has 532 two-letter words; no minimum is stated

# Pattern digits, in the bundle's own order (it indexes this array literally).
NAMES = ("absent", "present", "head", "tail")
ABSENT, PRESENT, HEAD, TAIL = 0, 1, 2, 3

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORDS = os.path.join(_HERE, "data", "shared", "words")


def strip_accents(s):
    """The bundle's RT(): NFD, then drop combining marks."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


# --------------------------------------------------------------------------
# The reference implementation: a literal port of the bundle's zT().
#
# It enumerates EVERY minimum-cost alignment path, exactly as the shipped code
# does, which makes it the oracle -- and far too slow for a solver inner loop.
# `feedback()` below is the fast exact equivalent; tools/checkletroso.py
# differential-tests the two.
# --------------------------------------------------------------------------
def feedback_ref(answer, guess):
    n, r = strip_accents(answer), strip_accents(guess)
    INF = float("inf")
    tbl = [[None] * (len(r) + 1) for _ in range(len(n) + 1)]
    tbl[0][0] = (0, [()])
    for a in range(1, len(n) + 1):
        tbl[a][0] = (a, [p + ("+",) for p in tbl[a - 1][0][1]])
    for b in range(1, len(r) + 1):
        tbl[0][b] = (b, [p + ("-",) for p in tbl[0][b - 1][1]])
    for a in range(1, len(n) + 1):
        for b in range(1, len(r) + 1):
            diag = tbl[a - 1][b - 1][0] + (0 if n[a - 1] == r[b - 1] else INF)
            up, left = tbl[a - 1][b][0] + 1, tbl[a][b - 1][0] + 1
            best = min(up, left, diag)
            paths = []
            if best == diag:
                paths += [p + (">",) for p in tbl[a - 1][b - 1][1]]
            if best == up:
                paths += [p + ("+",) for p in tbl[a - 1][b][1]]
            if best == left:
                paths += [p + ("-",) for p in tbl[a][b - 1][1]]
            tbl[a][b] = (best, paths)

    best_score, cands = -INF, []
    for path in tbl[len(n)][len(r)][1]:
        start, end = path[0] == ">", path[-1] == ">"
        s, c = [0] * len(r), list(n)
        matches = u = f = 0
        d = (1 if start else 0) + (1 if end else 0)
        for op in path:
            if op == ">":
                matches += 1
                u += 1
                s[f] = HEAD if u == 1 else TAIL
                c.remove(r[f])
                d += 3 * u
                f += 1
            elif op == "+":
                u = 0
            else:
                u = 0
                f += 1
        for e in range(len(r)):
            if s[e] == ABSENT and r[e] in c:
                s[e] = PRESENT
                c.remove(r[e])
        if matches == 1 and not start and not end:
            s[s.index(HEAD)] = PRESENT
        if d == best_score:
            cands.append((s, start, end))
        elif d > best_score:
            best_score, cands = d, [(s, start, end)]
    cands.sort(key=lambda x: tuple(x[0]), reverse=True)
    s, start, end = cands[0]
    return tuple(s), start, end


# --------------------------------------------------------------------------
# The fast exact implementation.
#
# Same answer, without materialising every path.  A DP over
# (answer index, guess index, current run length) finds the optimal
# (matches, d); a pruned DFS then walks only the alignments that achieve it and
# takes the lexicographically largest resulting pattern.  The state space is
# (A+1)(G+1)(min(A,G)+1) <= 11*11*11, and in practice one alignment is optimal.
# --------------------------------------------------------------------------
_BIG = 1000        # > any achievable d (3*10*11/2 + 2 = 167), so (m, d) packs


def _best_table(n, r, A, G, U):
    """best[i][j][u] = max achievable m*_BIG + d from that state, computed back."""
    best = [[[0] * (U + 2) for _ in range(G + 1)] for _ in range(A + 1)]
    for i in range(A, -1, -1):
        for j in range(G, -1, -1):
            match = i < A and j < G and n[i] == r[j]
            b = 0
            if match:
                b = (1 if (i == 0 and j == 0) else 0) + \
                    (1 if (i == A - 1 and j == G - 1) else 0)
            for u in range(U, -1, -1):
                if i == A and j == G:
                    best[i][j][u] = 0
                    continue
                v = -1
                if i < A and best[i + 1][j][0] > v:
                    v = best[i + 1][j][0]
                if j < G and best[i][j + 1][0] > v:
                    v = best[i][j + 1][0]
                if match and u < U:
                    x = _BIG + 3 * (u + 1) + b + best[i + 1][j + 1][u + 1]
                    if x > v:
                        v = x
                best[i][j][u] = v
    return best


def candidates(answer, guess):
    """Every RESOLVED candidate feedback, best first.

    The displayed reply is the first; the rest exist only so the gate can
    measure how often the tie-break actually decides anything.  Returns
    (pattern, start, end) triples.  Exactly equals feedback_ref() -- verified
    exhaustively by tools/checkletroso.py -- but explores only the OPTIMAL
    alignments rather than the reference's every-minimum-cost-path enumeration.

    WHY IT CANNOT BE DONE GREEDILY LEFT TO RIGHT, since that was tried and is
    wrong: the digit at an UNMATCHED guess position is `present` or `absent`
    depending on the leftover multiset, which depends on which letters the
    WHOLE alignment consumed.  So two alignments can tie on every matched
    position and still differ at an earlier unmatched one -- `aab` against
    `babaa` gives (1,0,0,2,3), not the greedy's (0,2,3,1,0).  The lexicographic
    comparison is therefore not decidable position by position, and the
    candidates have to be generated before they can be compared.
    """
    n, r = strip_accents(answer), strip_accents(guess)
    A, G = len(n), len(r)
    if G == 0:
        return (), False, False
    U = min(A, G)
    best = _best_table(n, r, A, G, U)

    out = []
    digits = [ABSENT] * G

    def rec(i, j, u, st, en):
        cur = best[i][j][u]
        if i == A and j == G:
            out.append((tuple(digits), st, en))
            return
        if i < A and best[i + 1][j][0] == cur:            # skip an answer letter
            rec(i + 1, j, 0, st, en)
        if j < G and best[i][j + 1][0] == cur:            # skip a guess letter
            rec(i, j + 1, 0, st, en)
        if i < A and j < G and n[i] == r[j] and u < U:    # match
            b = (1 if (i == 0 and j == 0) else 0) + \
                (1 if (i == A - 1 and j == G - 1) else 0)
            if best[i + 1][j + 1][u + 1] + _BIG + 3 * (u + 1) + b == cur:
                digits[j] = HEAD if u == 0 else TAIL
                rec(i + 1, j + 1, u + 1,
                    st or (i == 0 and j == 0),
                    en or (i == A - 1 and j == G - 1))
                digits[j] = ABSENT

    rec(0, 0, 0, False, False)

    counts = {}
    for ch in n:
        counts[ch] = counts.get(ch, 0) + 1
    scored = []
    for raw, st, en in set(out):
        s = list(raw)
        leftover = dict(counts)
        matched = [j for j in range(G) if s[j] != ABSENT]
        for j in matched:
            leftover[r[j]] -= 1
        for j in range(G):
            if s[j] == ABSENT and leftover.get(r[j], 0) > 0:
                s[j] = PRESENT
                leftover[r[j]] -= 1
        if len(matched) == 1 and not st and not en:
            s[matched[0]] = PRESENT
        scored.append((tuple(s), en, st))
    # Lexicographically largest pattern first.  Among equal patterns the
    # reference's order decides, and it appends the DIAGONAL branch first at
    # every cell, so it prefers the LATEST match -- `end` ahead of `start`.
    scored.sort(reverse=True)
    return [(pat, st, en) for pat, en, st in scored]


def feedback(answer, guess):
    """The displayed feedback: the winner among candidates()."""
    if not guess:
        return (), False, False
    return candidates(answer, guess)[0]


def encode(pattern, start, end):
    """Pack a feedback into an int, for bucketing candidates.

    Two digits per guess position plus the two flags.  Codes are only ever
    compared among replies to the SAME guess, so the length-dependent range is
    not a problem; at MAXLEN=10 the value fits comfortably in 32 bits.
    """
    code = 0
    for i, d in enumerate(pattern):
        code |= d << (2 * i)
    n = 2 * len(pattern)
    return code | (int(start) << n) | (int(end) << (n + 1))


def classes(answer, guess):
    """(letter, class-string) per guess position -- the bundle's BT(), for eyes."""
    pattern, start, end = feedback(answer, guess)
    out = []
    for i, ch in enumerate(guess):
        cl = [NAMES[pattern[i]]]
        if i == 0 and start:
            cl.append("start")
        if i == len(guess) - 1 and end:
            cl.append("end")
        out.append((ch, "+".join(cl)))
    return out


def share_emoji(answer, guess):
    """The bundle's LT(): the row as the game's share text renders it."""
    pattern, start, end = feedback(answer, guess)
    out = ""
    for i, d in enumerate(pattern):
        if d == ABSENT:
            out += "⬛"
        elif (i == 0 and start) or (i == len(pattern) - 1 and end):
            out += "\U0001f7e2"
        elif d in (HEAD, TAIL):
            out += "\U0001f7e9"
        else:
            out += "\U0001f7e8"
    return out


def load_words(kind, lengths=range(MINLEN, MAXLEN + 1)):
    """Union letroso's per-length lists.  `kind` is "guess" or "mystery"."""
    if kind not in ("guess", "mystery"):
        raise ValueError("kind must be 'guess' or 'mystery', not %r" % kind)
    words = []
    for L in lengths:
        path = os.path.join(_WORDS, "letroso", "len%d" % L, "%s.txt" % kind)
        if not os.path.exists(path):
            raise SystemExit(
                "missing %s\n  build it: python3 build_letroso_lists.py" % path)
        with open(path) as f:
            words.extend(w.strip() for w in f if w.strip())
    return sorted(set(words))
