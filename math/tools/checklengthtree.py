"""Verify ONE emitted tree at ANY word length, independently of the solver.

    python3 tools/checklengthtree.py --length 7 --tree <file.txt.gz> [--expect-total N]

`tools/checktrees.py` is the 5-letter equivalent and cannot serve here: it reaches
its trees through `paths.py` (which is keyed to a WORDLE_SOLVER name, not a length)
and asserts the 2315 mystery answers by construction.  This checks the same
properties, length-generally, against the hello wordl lists a length sweep uses.

WHAT IT CHECKS, all by REPLAYING the file rather than trusting it:

  * every answer of that length's mystery list appears exactly once, and nothing
    outside it appears at all;
  * each line's recorded guess count equals the guesses actually on it;
  * each line's final guess IS the answer -- a line that never names its answer
    has not won;
  * every recorded pattern is reproduced by `wordle.pattern` from the two STRINGS,
    so the encoding, the matrix and the solver's bookkeeping are all pinned;
  * one NEXT GUESS per prefix -- two answers agreeing on every reply so far must
    be played the same way, or the file is not a single strategy, just a
    per-answer fabrication;

NOT CHECKED, DELIBERATELY: that each guess is still CONSISTENT with the earlier
replies.  That is ultra mode's rule, not normal Wordle's -- an optimal normal-mode
tree plays PROBE words that prior feedback has already ruled out, which is most of
what makes it optimal.  `checktrees.py` applies its green/min-count constraint only
under hard mode for the same reason.  Asserting it here failed a correct length-11
tree on its first run (`cappuccinos` after `meteoritics`), which is exactly the
kind of borrowed-rule error a gate should not introduce.
  * the summed guess counts equal `--expect-total`, tying the tree to the number
    the CSV reports for that opener.

Exits nonzero on the first failure, so it works as a gate.
"""

import argparse
import gzip
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import decode, load_words, pattern  # noqa: E402


def tiles(code, length):
    """The tree's own spelling of a reply: b/y/g per position.

    write_tree stores the reply as letters, not the base-3 code, so the
    comparison is made in the FILE's alphabet rather than by parsing its
    text as a number -- `decode` is the repo's own inverse of the encoding.
    """
    return "".join("byg"[t] for t in decode(code, length))


def read_lines(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        for n, line in enumerate(f, 1):
            parts = line.split()
            if parts:
                yield n, parts


def check(length, tree, expect_total=None):
    answers = set(load_words("mystery", length))
    seen, total, prefixes = set(), 0, {}

    for n, parts in read_lines(tree):
        answer, nguess, rest = parts[0], int(parts[1]), parts[2:]
        guesses, pats = rest[0::2], rest[1::2]

        if answer not in answers:
            raise SystemExit("line %d: %r is not a length-%d answer" % (n, answer, length))
        if answer in seen:
            raise SystemExit("line %d: %r appears twice" % (n, answer))
        seen.add(answer)

        if len(guesses) != nguess:
            raise SystemExit("line %d (%s): says %d guesses, carries %d"
                             % (n, answer, nguess, len(guesses)))
        if guesses[-1] != answer:
            raise SystemExit("line %d (%s): last guess is %r, not the answer"
                             % (n, answer, guesses[-1]))
        if len(pats) != nguess - 1:
            raise SystemExit("line %d (%s): %d guesses but %d patterns"
                             % (n, answer, nguess, len(pats)))
        total += nguess

        # Every pattern re-derived FROM THE STRINGS, and the prefix -> next guess
        # map accumulated, which is what makes the file ONE strategy.
        history = []
        for i, g in enumerate(guesses):
            key = tuple(history)
            if prefixes.setdefault(key, g) != g:
                raise SystemExit("line %d (%s): prefix %s is played as %r here "
                                 "and %r elsewhere -- not one strategy"
                                 % (n, answer, key or "(root)", g, prefixes[key]))
            if i < len(pats):
                want = pattern(g, answer)
                if tiles(want, length) != pats[i]:
                    raise SystemExit("line %d (%s): reply to %r recorded as %s, "
                                     "recomputed as %s"
                                     % (n, answer, g, pats[i], tiles(want, length)))
                history.append((g, want))

    missing = answers - seen
    if missing:
        raise SystemExit("%d answer(s) never appear, e.g. %s"
                         % (len(missing), " ".join(sorted(missing)[:5])))
    if expect_total is not None and total != expect_total:
        raise SystemExit("tree sums to %d, the CSV says %d" % (total, expect_total))

    print("tree ok: %d answers, %d total guesses (%.5f avg), one next guess per "
          "prefix, every pattern re-derived from the strings"
          % (len(seen), total, total / len(seen)))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--length", type=int, required=True)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--expect-total", type=int, default=None)
    a = ap.parse_args()
    check(a.length, a.tree, a.expect_total)


if __name__ == "__main__":
    main()
