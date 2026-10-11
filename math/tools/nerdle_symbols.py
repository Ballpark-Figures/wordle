"""How often each of the 15 nerdle symbols appears, and where.

    python3 tools/nerdle_symbols.py                  # from math/, the answers
    python3 tools/nerdle_symbols.py --set guesses
    python3 tools/nerdle_symbols.py --set classes    # one member per class
    python3 tools/nerdle_symbols.py --width 6

THREE COUNTS, because they answer different questions and routinely disagree:

  * OCCURRENCES -- how many tiles in the whole set carry the symbol.  `=` scores
    exactly one per equation by construction; a digit can score several.
  * EQUATIONS -- how many equations contain the symbol AT LEAST ONCE.  This is
    the one that matters for a guess: a green or purple tile tells you the
    symbol is present, not how many times.
  * PER EQUATION -- occurrences divided by the equation count, so a symbol that
    turns up twice in a few equations is distinguishable from one that turns up
    once in many.

Then a POSITION table: how often each symbol falls in each of the 8 columns.
That is the analogue of the letter-position views in the Wordle work, and it is
where the structure shows -- `=` cannot appear in the first two columns, an
operator cannot open an equation, and the digits are far from uniform across the
board.

WHICH SET IS THE RIGHT DENOMINATOR depends on the question and none of the three
is a default worth hiding: ANSWERS is what the hidden equation is drawn from and
is what a solver is trying to pin down; GUESSES is what you are allowed to type,
and is 21 times larger and much stranger (leading zeros, unary minus); CLASSES
takes one canonical member per commutative class, which is the right denominator
if you think of the puzzle space as classes rather than as written equations.
Answers is the default because it is the set the game draws from.

Counts only -- nothing here is an optimum, a ranking of guesses, or a strategy.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nerdle import SYMBOLS, WIDTH, commutative_key  # noqa: E402
from nerdle_topk import load_list  # noqa: E402


def parse_args(argv):
    which, width = "answers", WIDTH
    i = 0
    while i < len(argv):
        if argv[i] == "--set":
            which = argv[i + 1]; i += 2
        elif argv[i] == "--width":
            width = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % argv[i])
    if which not in ("answers", "guesses", "classes"):
        raise SystemExit("--set must be answers, guesses or classes, not %r" % which)
    return which, width


def load_set(which, width):
    if which == "guesses":
        return load_list("guesses", width)
    answers = load_list("answers", width)
    if which == "answers":
        return answers
    seen, out = set(), []
    for a in answers:                       # one canonical member per class
        key = commutative_key(a)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def counts(words, width=WIDTH):
    """(occurrences, equations containing, per-position counts) for each symbol --
    the three counts the report prints (the bonus video's symbol table reads it)."""
    occ = {c: 0 for c in SYMBOLS}
    has = {c: 0 for c in SYMBOLS}
    pos = {c: [0] * width for c in SYMBOLS}
    for w in words:
        for i, c in enumerate(w):
            occ[c] += 1
            pos[c][i] += 1
        for c in set(w):
            has[c] += 1
    return occ, has, pos


def main(argv):
    which, width = parse_args(argv)
    words = load_set(which, width)
    n = len(words)
    if not n:
        raise SystemExit("the %s set is empty at width %d" % (which, width))

    occ, has, pos = counts(words, width)

    print("nerdle symbol frequencies: set=%s width=%d, %d equations"
          % (which, width, n))
    print("\n%6s %12s %12s %10s %12s"
          % ("symbol", "occurrences", "equations", "% of eqs", "per equation"))
    for c in sorted(SYMBOLS, key=lambda c: (-occ[c], c)):
        print("%6s %12d %12d %9.2f%% %12.3f"
              % (c, occ[c], has[c], 100.0 * has[c] / n, occ[c] / n))

    print("\nby position (share of all equations, per cent)")
    print("%6s %s" % ("symbol", "".join("%8d" % (i + 1) for i in range(width))))
    for c in sorted(SYMBOLS, key=lambda c: (-occ[c], c)):
        print("%6s %s" % (c, "".join("%8.2f" % (100.0 * v / n) for v in pos[c])))

    total = sum(occ.values())
    if total != n * width:
        raise SystemExit("counted %d tiles, expected %d -- the set is malformed"
                         % (total, n * width))
    print("\n%d tiles counted over %d equations of %d symbols" % (total, n, width))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
