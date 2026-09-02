"""Replay a guess sequence against Absurdle's host — the SLOW, literal way.

    python3 tools/absurdle_play.py aesir yauld tench whoop

Deliberately shares NO code with `absurdle.py`: it buckets with plain dicts over
`wordle.pattern` and picks with `sorted`, so it is an independent replay of any
sequence the matrix-based search produces, and the natural thing to diff against
a game actually played on absurdle.com.

Prints each reply and the candidates left, and says whether the sequence WINS —
which happens only when the set is already a singleton and you name it.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import ALL_GREEN, decode, load_words, pattern  # noqa: E402

TILES = ".yG"


def host_reply(cand, guess):
    """(pattern code, surviving candidates): largest bucket, FAQ tie-break."""
    buckets = {}
    for w in cand:
        buckets.setdefault(pattern(guess, w), []).append(w)

    def key(code):
        trits = decode(code)
        return (-len(buckets[code]),                  # largest bucket first
                sum(t == 2 for t in trits),           # then fewest greens
                sum(t == 1 for t in trits),           # then fewest yellows
                int("".join(str(t) for t in trits)))  # then lowest as a number

    code = min(buckets, key=key)
    return code, buckets[code]


seq = [w.lower() for w in sys.argv[1:]]
if not seq:
    raise SystemExit(__doc__.strip().splitlines()[2].strip())

legal = set(load_words("guess"))
cand = load_words("mystery")
code = None
for w in seq:
    if w not in legal:
        raise SystemExit("not a legal guess: %s" % w)
    code, cand = host_reply(cand, w)
    tiles = "".join(TILES[t] for t in decode(code))
    print("  %-6s %s  %d left%s" % (w, tiles, len(cand),
                                    "" if len(cand) > 1 else "   (%s)" % cand[0]))

if code == ALL_GREEN:
    print("WIN in %d" % len(seq))
else:
    print("NOT a win: %d candidates still alive" % len(cand))
    sys.exit(1)
