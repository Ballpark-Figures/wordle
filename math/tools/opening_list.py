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

ANY `word*` COLUMNS WORK, so the same tool reads the pair, triple and quad
rankings.  Every opening in one file must be the same size, which those files
satisfy by construction; the sweep refuses a mixed list, since ranking a one-word
opening against a two-word one compares two different strategies.
"""

import os
import sys


def read_openings(path, top=None):
    """The first `top` openings of a ranking CSV, as lists of words."""
    header, out = None, []
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
            out.append([cols[i] for i in idx])
            if top is not None and len(out) >= top:
                break
    if not out:
        raise SystemExit("no data rows in %s" % path)
    return out


def main(argv):
    src = out = None
    top = None
    both = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--top":
            top = int(argv[i + 1]); i += 2
        elif a == "--both-orders":
            both = True; i += 1
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

    rows = read_openings(src, top=top)
    if both:
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
          % (out, len(rows), sizes[0], " (both orderings)" if both else ""))
    print("  from: %s (its own order, best first)" % src)
    print("  head: %s" % " | ".join(" ".join(r) for r in rows[:4]))
    print("  a SCREEN of that ranking -- the best of these, never the best opening")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
