"""Take the top N openings off a singletons ranking, as a sweep's candidate list.

    python3 tools/opening_list.py --from data/shared/singletons/pair_singletons.csv \\
        --top 10000 --out data/shared/wordlesim/openings_pair_top10000.txt

One opening per line, words space separated, in the SOURCE FILE'S OWN ORDER -- so
the list is best-first by whatever that file ranked on, and a truncated sweep of it
has examined the head of that ranking rather than an arbitrary slice.

IT IS A SCREEN, AND THE RANKING IS FOR A DIFFERENT QUESTION.  There are 84,129,906
pairs and a simulation cannot visit them all, so a pair sweep examines the top N of
an existing ranking.  data/shared/singletons/pair_singletons.csv ranks pairs by how
many of the 2315 answers a blind opening isolates to a SINGLETON -- exhaustively
evaluated (its head is the exact top of that ranking) but a different objective
from expected guesses under random-compatible play.  So:

  * a pair outside the top N is never examined AT ALL, and
  * nothing here shows the two objectives agree even inside it.

Report such a sweep as "the best of the N screened", never "the best pair".
Widening --top widens the net; it never makes the screen exhaustive.

RESTRICTING THE WORDS.  `--openings-in custom` (a list stem in data/shared/words,
or a path) keeps only openings whose EVERY word is in that list -- for pairing an
opening pool with a follow-up that draws from the same one, so the strategy is a
player who knows a single list rather than two.  A rejected row does NOT count
toward `--top`, so the screen keeps its width and reads deeper into the ranking
instead; the scan reports how deep it went and whether the ranking ran out.  It
narrows what is EXAMINED, so it narrows the claim in the same way `--top` does: a
restricted run's head is the best of the qualifying openings screened.

ORDERINGS.  A ranking lists each SET once, because a blind opening's partition
cannot depend on play order.  An adaptive rule breaks that -- it keys on what the
words played so far have left -- so every permutation becomes its own strategy:
`--both-orders` for pairs (2 each), `--all-orders` for any size (n! each, so 6 for
a triple, matching what optturns' --triple-list expands to).  The multiplication
is printed, since n! decides how long the sweep runs.

ANY `word*` COLUMNS WORK, so the same tool reads the pair, triple and quad
rankings.  THE TRIPLE RANKING IS A GREEDY SCREEN, not an exhaustive one: it only
extends pairs that survived the pair stage (solver/run-singles.sh says so), so a
triple whose every two-word prefix missed that cut cannot appear at any --top.
Its head is "best of the triples screened" -- weaker than the pair file's head,
which is the exact top of an exhaustive evaluation.  Every opening in one file must be the same size, which those files
satisfy by construction; the sweep refuses a mixed list, since ranking a one-word
opening against a two-word one compares two different strategies.
"""

import os
import sys
from itertools import permutations
from math import factorial

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import load_words  # noqa: E402


def resolve_word_set(spec):
    """A set of words from a list STEM in data/shared/words, or from a path.

    The same two forms `--words` takes elsewhere, so `custom` means the committed
    custom.txt and a path means that file -- one spelling of "which list" across
    the tools rather than a new one here.
    """
    if os.sep in spec or spec.endswith(".txt"):
        with open(spec) as f:
            return {ln.strip() for ln in f if ln.strip()}
    try:
        return set(load_words(spec))
    except FileNotFoundError:
        raise SystemExit(
            "no word list %r: give a stem in data/shared/words (custom, "
            "mystery, guess) or a path to a .txt" % spec)


def read_openings(path, top=None, restrict=None, stats=None):
    """The first `top` openings of a ranking CSV, as lists of words.

    `restrict` is a set every word of an opening must be in.  **A REJECTED ROW
    DOES NOT COUNT TOWARD `top`**, so `--top N` still means "N openings to
    examine" rather than "N rows read, of which some survived" -- the screen
    keeps its width and simply reads deeper into the ranking to fill it.  That
    is the reading the count is worth having: `--top 10000` should mean the same
    thing with and without the filter.

    `stats`, if given, is filled in with how deep the scan actually went, which
    is what says whether the ranking was EXHAUSTED -- a field smaller than `top`
    means there were no more qualifying rows, not that the file was short.
    """
    header, out, scanned = None, [], 0
    with open(path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None:
                header = cols
                idx = [i for i, c in enumerate(header) if c.startswith("word")]
                if not idx:
                    raise SystemExit("%s has no word column (it has: %s)"
                                     % (path, ", ".join(header)))
                continue
            if len(cols) <= max(idx):
                continue
            scanned += 1
            row = [cols[i] for i in idx]
            if restrict is not None and not all(w in restrict for w in row):
                continue
            out.append(row)
            if top is not None and len(out) >= top:
                break
    if stats is not None:
        stats["scanned"] = scanned
        stats["kept"] = len(out)
        stats["exhausted"] = top is not None and len(out) < top
    if not out:
        raise SystemExit(
            "no openings in %s%s" % (path, "" if restrict is None else
                                     " have every word in the restriction list"))
    return out


def main(argv):
    src = out = None
    top = None
    both = False
    allorders = False
    inlist = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--openings-in":
            inlist = argv[i + 1]; i += 2
        elif a == "--top":
            top = int(argv[i + 1]); i += 2
        elif a == "--both-orders":
            both = True; i += 1
        elif a == "--all-orders":
            allorders = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if src is None:
        raise SystemExit("--from RANKING.csv is required")
    if out is None:
        raise SystemExit("--out LIST.txt is required")
    if top is None or top < 1:
        # How wide the screen is IS the experiment's coverage, so it is named
        # rather than defaulted: a default would silently decide what was never
        # examined.
        raise SystemExit("--top N is required: it says how much of the ranking "
                         "the sweep will examine, and everything below it is "
                         "never looked at")

    stats = {}
    restrict = resolve_word_set(inlist) if inlist else None
    rows = read_openings(src, top=top, restrict=restrict, stats=stats)
    if restrict is not None:
        print("restricted to openings whose every word is in %s (%d words): "
              "%d of the first %d ranked openings qualify (%.2f%%)%s"
              % (inlist, len(restrict), stats["kept"], stats["scanned"],
                 100.0 * stats["kept"] / max(1, stats["scanned"]),
                 " -- THE RANKING WAS EXHAUSTED, so this is every qualifying "
                 "opening in it, not a top-%d" % top if stats["exhausted"]
                 else ""))
    if allorders:
        # EVERY ordering, which is what an adaptive rule needs at any size: it
        # keys on what the words played SO FAR have left, so each permutation is
        # its own strategy.  A pair gives 2 and a triple 6 -- the same expansion
        # optturns' --triple-list does, for the same reason ("evaluating one
        # ordering per triple would leave five of six untried").  The count is
        # printed because n! multiplies the sweep and nobody should discover that
        # from the runtime.
        n = len(rows[0])
        rows = [list(p) for r in rows for p in permutations(r)]
        print("expanded to every ordering: %d! = %d per opening"
              % (n, len(rows) // max(1, len(rows) // factorial(n))
                 if False else factorial(n)))
    elif both:
        # The ranking enumerates each set ONCE, because a BLIND opening's joint
        # partition cannot depend on play order (solver/pairsplit.c says so).  A
        # rule that abandons the opening early breaks that, so every ordering
        # becomes its own strategy and has to be listed.  Pairs give two; larger
        # sets would give more, so only pairs are expanded here rather than
        # silently emitting a number of permutations nobody asked for.
        if any(len(r) != 2 for r in rows):
            raise SystemExit("--both-orders expands PAIRS; %s holds openings of "
                             "another size, whose orderings are a bigger set "
                             "than this flag should decide" % src)
        rows = [w for r in rows for w in (r, [r[1], r[0]])]
    sizes = sorted({len(r) for r in rows})
    if len(sizes) > 1:
        raise SystemExit("%s mixes openings of %s words"
                         % (src, " and ".join(map(str, sizes))))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for r in rows:
            f.write(" ".join(r) + "\n")
    print("%s: %d openings of %d words%s"
          % (out, len(rows), sizes[0],
             " (every ordering)" if allorders else
             " (both orderings)" if both else ""))
    print("  from: %s (its own order, best first)" % src)
    print("  head: %s" % " | ".join(" ".join(r) for r in rows[:4]))
    print("  a SCREEN of that ranking -- the best of these, never the best opening")
    if restrict is not None:
        print("  and a RESTRICTED screen: an opening using any word outside %s "
              "was never examined" % inlist)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
