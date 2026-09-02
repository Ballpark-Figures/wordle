"""Gate for `absurdle.py` — the host rule, against a brute-force reference.

    python3 tools/checkabsurdle.py

Exits nonzero on any failure, so it works as a gate. Run it alongside
solver/validate.sh, tools/checkpatterns.py and tools/checkstrspace.py.

WHAT IT CAN AND CANNOT ESTABLISH. It checks that the fast, matrix-and-bincount
implementation agrees with an obviously-correct one built from `wordle.pattern`
and plain dicts, on states from the full 2315 down to pairs, and that the
tie-break shortcuts hold. It CANNOT check the RULE: that Absurdle really picks
the largest bucket and breaks ties this way is transcribed from qntm's FAQ, and
only playing the live game can confirm it.

The reference is deliberately written the slow, literal way — bucket into a
dict, sort by the FAQ's stated key, take the first — so the two implementations
share no logic beyond `wordle.pattern` itself.
"""

import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from absurdle import (ALL_GREEN, N_PATTERNS, RANK, choose, respond,  # noqa: E402
                      respond_all, sizes_all, tiebreak_key)
from build_patterns import load_patterns  # noqa: E402
from wordle import load_words, pattern  # noqa: E402

fail = 0


def bad(msg):
    global fail
    print("  FAIL: %s" % msg)
    fail = 1


def reference(cand_words, guess_word):
    """The host's reply, the slow literal way. Returns (code, surviving words)."""
    buckets = {}
    for w in cand_words:
        buckets.setdefault(pattern(guess_word, w), []).append(w)
    # largest bucket; ties by fewest greens, then fewest yellows, then the
    # pattern read as a decimal number
    code = min(buckets, key=lambda c: (-len(buckets[c]), tiebreak_key(c)))
    return code, buckets[code]


print("1. tie-break key orders exactly as the pattern code does")
# The third key is "read the pattern left-to-right as a number". Both it and the
# base-3 code compare the same fixed-length digit tuple, so `code` may be used
# directly; assert that rather than trusting it.
by_key = sorted(range(N_PATTERNS), key=tiebreak_key)
by_code = sorted(range(N_PATTERNS), key=lambda c: (tiebreak_key(c)[0], tiebreak_key(c)[1], c))
if by_key != by_code:
    bad("decimal-reading order differs from base-3 code order")
else:
    print("   ok   243 codes, both orders identical")

print("2. all-green is the LAST preference, so a win is never handed over early")
if int(RANK[ALL_GREEN]) != N_PATTERNS - 1:
    bad("all-green rank is %d, expected %d" % (RANK[ALL_GREEN], N_PATTERNS - 1))
else:
    print("   ok   rank[all-green] = %d of %d" % (RANK[ALL_GREEN], N_PATTERNS - 1))

pat = load_patterns()
answers = load_words("mystery")
guesses = load_words("guess")
gindex = {w: i for i, w in enumerate(guesses)}

print("3. respond() vs the brute-force reference, over shrinking states")
rng = random.Random(20260902)
checked = 0
for trial in range(12):
    cand = np.arange(len(answers))
    for _ in range(6):
        g = rng.randrange(len(guesses))
        code, nxt = respond(pat, cand, g)
        rcode, rwords = reference([answers[i] for i in cand], guesses[g])
        if code != rcode:
            bad("code %d vs reference %d (guess %s, %d candidates)"
                % (code, rcode, guesses[g], len(cand)))
        if sorted(answers[i] for i in nxt) != sorted(rwords):
            bad("surviving set differs (guess %s, %d candidates)" % (guesses[g], len(cand)))
        checked += 1
        cand = nxt
        if len(cand) <= 1:
            break
print("   ok   %d (state, guess) pairs agree" % checked)

print("4. respond_all() agrees with respond() guess by guess")
cand = np.arange(len(answers))
for step, word in enumerate(["salet", "courd"] if "courd" in gindex else ["salet"]):
    codes, sizes = respond_all(pat, cand)
    for g in rng.sample(range(len(guesses)), 300):
        code, nxt = respond(pat, cand, g)
        if code != codes[g] or len(nxt) != sizes[g]:
            bad("bulk (%d, %d) vs single (%d, %d) for %s"
                % (codes[g], sizes[g], code, len(nxt), guesses[g]))
    _, cand = respond(pat, cand, gindex[word])
print("   ok   600 guesses match in bulk and singly")

print("5. the win rule: all-green only from a singleton")
# Two candidates, guess one of them: both buckets are singletons, and the
# tie-break hands back the OTHER word rather than conceding.
pairs = 0
for _ in range(200):
    a, b = rng.sample(range(len(answers)), 2)
    if answers[a] not in gindex:
        continue
    cand = np.asarray(sorted((a, b)))
    code, nxt = respond(pat, cand, gindex[answers[a]])
    if code == ALL_GREEN:
        bad("conceded from a 2-candidate state (%s vs %s)" % (answers[a], answers[b]))
    if len(nxt) != 1 or nxt[0] != b:
        bad("expected the other word to survive (%s vs %s)" % (answers[a], answers[b]))
    pairs += 1
    # ... and from the singleton, guessing it wins
    code, nxt = respond(pat, nxt, gindex[answers[b]]) if answers[b] in gindex else (ALL_GREEN, nxt)
    if code != ALL_GREEN:
        bad("did not concede from the singleton %s" % answers[b])
print("   ok   %d two-candidate states behaved" % pairs)

print("6. choose() picks the largest bucket, and the tie-break only on ties")
for _ in range(2000):
    counts = np.zeros(N_PATTERNS, dtype=np.int32)
    for c in rng.sample(range(N_PATTERNS), rng.randrange(1, 8)):
        counts[c] = rng.randrange(1, 5)
    code, size = choose(counts)
    if size != counts.max():
        bad("chose a bucket of %d when %d was available" % (size, counts.max()))
    tied = [c for c in range(N_PATTERNS) if counts[c] == counts.max()]
    if code != min(tied, key=tiebreak_key):
        bad("tie-break picked %d, expected %d" % (code, min(tied, key=tiebreak_key)))
print("   ok   2000 synthetic bucket tables")


print("7. sizes_all() matches respond_all()'s sizes — size is tie-break-free")
cand = np.arange(len(answers))
for word in ["salet", "aesir"]:
    _, sizes = respond_all(pat, cand)
    if not np.array_equal(sizes, sizes_all(pat, cand)):
        bad("sizes_all disagrees at %d candidates" % len(cand))
    _, cand = respond(pat, cand, gindex[word])
print("   ok   two states, all 12972 guesses each")

print("FAIL" if fail else "PASS")
sys.exit(1 if fail else 0)
