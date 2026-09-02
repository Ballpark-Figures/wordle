"""Absurdle's host — the largest-bucket rule as a PURE FUNCTION of the state.

Absurdle never commits to a secret word. It holds a CANDIDATE SET (initially the
answer list), and for each guess it buckets the candidates by the feedback each
would give, answers with the pattern of the LARGEST bucket, and keeps that bucket
as the new candidate set. It prunes as little as it can, every turn.

TIE-BREAK between equal-sized buckets, in order: fewest GREENS, then fewest
YELLOWS, then the pattern read left-to-right as a decimal number (grey 0,
yellow 1, green 2) — lowest wins. That last key is exactly our base-3 pattern
CODE order: both compare the same fixed-length digit tuple lexicographically, so
`code` is used directly and `tools/checkabsurdle.py` asserts the equivalence.

TWO CONSEQUENCES THE SEARCH IS BUILT ON:

  * ALL-GREEN LOSES EVERY TIE, being the most-green pattern of all. So the host
    concedes only when it has no choice, and you win IFF the candidate set is
    already a singleton and you guess that word. A game therefore costs
    (guesses to drive the set to one word) + 1.
  * THE HOST IS DETERMINISTIC AND FULLY KNOWN, so there is no game tree and no
    minimax: the response is a function of (candidate set, guess), a strategy is
    an OPEN-LOOP SEQUENCE of guesses, and "optimal" means a shortest such
    sequence. None of the optturns expected-turns machinery transfers.

WORD LISTS ARE OURS, NOT ABSURDLE'S. Candidates are the 2315 `mystery.txt`,
guesses the 12972 `guess.txt` — the original Wordle lists this whole video runs
on. qntm describes Absurdle's lists as "very similar" to Wordle's, not
identical, the site is closed-source, and the NYT edited Wordle's lists after
both were built. So a sequence that wins here is NOT guaranteed to win on
absurdle.com. See the Absurdle section of the repo CLAUDE.md.

The host rule itself is transcribed from qntm's Absurdle FAQ and has NOT been
checked against the live game. `tools/checkabsurdle.py` verifies this module
against a brute-force reference; it cannot verify the RULE.

    from absurdle import respond, respond_all, play
"""

import numpy as np

from build_patterns import load_patterns
from wordle import ALL_GREEN, N_PATTERNS, WORD_LEN, decode, load_words

TILES = ".yG"          # grey / yellow / green, for printing a pattern


def tiebreak_key(code, word_len=WORD_LEN):
    """The FAQ's tie-break key for one pattern code. Lower is chosen first.

    (greens, yellows, the pattern as a decimal number). Returned as a tuple so
    the check tool can compare it against the code order directly.
    """
    trits = decode(code, word_len)
    greens = sum(t == 2 for t in trits)
    yellows = sum(t == 1 for t in trits)
    decimal = int("".join(str(t) for t in trits))
    return (greens, yellows, decimal)


def tiebreak_rank(word_len=WORD_LEN):
    """rank[code] = position in the host's preference order, lowest chosen first."""
    n = 3 ** word_len
    order = sorted(range(n), key=lambda c: tiebreak_key(c, word_len))
    rank = np.empty(n, dtype=np.int32)
    rank[np.asarray(order)] = np.arange(n, dtype=np.int32)
    return rank


RANK = tiebreak_rank()
# Higher = preferred, so one score `count * N + PREF` orders by size first and
# breaks ties the host's way. Max is 2315*243 + 242, nowhere near int32.
PREF = (N_PATTERNS - 1 - RANK).astype(np.int32)


def choose(counts):
    """The host's choice from bucket sizes: (code, size), row-wise if 2-D.

    `counts` is (..., N_PATTERNS) of bucket sizes. Empty buckets score below
    every non-empty one (count 0 beats nothing), so they can never be chosen
    unless the state itself is empty, which never happens.
    """
    counts = np.asarray(counts, dtype=np.int32)
    code = (counts * N_PATTERNS + PREF).argmax(axis=-1)
    if counts.ndim == 1:
        return int(code), int(counts[code])
    size = np.take_along_axis(counts, code[..., None], axis=-1)[..., 0]
    return code, size


def respond(pat, cand, g):
    """Host reply to guess index `g` against candidate indices `cand`.

    Returns (pattern code, the new candidate index array).
    """
    row = np.asarray(pat[g, cand], dtype=np.int32)
    code, _ = choose(np.bincount(row, minlength=N_PATTERNS))
    return code, cand[row == code]


def bucket_counts(pat, cand, block=4096):
    """(NG, N_PATTERNS) int32: bucket sizes of every guess against `cand`.

    Blocked over guesses so the temporary stays a few tens of MB whatever the
    candidate count; `pat` is mmap'd, so only the block is ever resident.
    """
    ng = pat.shape[0]
    out = np.empty((ng, N_PATTERNS), dtype=np.int32)
    for lo in range(0, ng, block):
        hi = min(lo + block, ng)
        sub = np.asarray(pat[lo:hi, cand], dtype=np.int32)
        rows = hi - lo
        off = (np.arange(rows, dtype=np.int32) * N_PATTERNS)[:, None]
        flat = np.bincount((sub + off).ravel(), minlength=rows * N_PATTERNS)
        out[lo:hi] = flat.reshape(rows, N_PATTERNS)
    return out


def respond_all(pat, cand, block=4096):
    """(codes, sizes) for EVERY guess against `cand`, in one pass.

    codes[g] is the host's reply to guess g, sizes[g] the candidates left after
    it. This is the search workhorse: one call ranks all 12972 continuations.
    """
    return choose(bucket_counts(pat, cand, block=block))


def show(code, word_len=WORD_LEN):
    """A pattern code as a 5-char string, e.g. `.yG..`."""
    return "".join(TILES[t] for t in decode(code, word_len))


def play(seq, pat=None, guesses=None, answers=None):
    """Replay a guess sequence against the host.

    Returns (transcript, won), where transcript is a list of
    (guess, pattern string, candidates remaining). `won` is True iff the last
    reply was all-green, which — see the module docstring — can only happen from
    a singleton state.
    """
    if pat is None:
        pat = load_patterns()
    if guesses is None:
        guesses = load_words("guess")
    if answers is None:
        answers = load_words("mystery")
    index = {w: i for i, w in enumerate(guesses)}
    cand = np.arange(len(answers))
    transcript, code = [], None
    for w in seq:
        if w not in index:
            raise SystemExit("not a legal guess: %s" % w)
        code, cand = respond(pat, cand, index[w])
        transcript.append((w, show(code), len(cand)))
    return transcript, code == ALL_GREEN
