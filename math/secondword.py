"""The PREDETERMINED SECOND WORD: what to play when the opener shows greys.

THE STRATEGY THIS SERVES (the user's, 2026-09-10).  Play an opener.  If its reply
shows at least N grey tiles, play a word committed to IN ADVANCE for that opener
-- one word, chosen before the game, the same one whatever the greys happened to
be.  Otherwise, and from the third guess on, play a random compatible word.  The
simulator side is `wordlesim.SecondWordOnGrays`; this module owns the QUANTITY
that picks the word, and `solver/secondword.c` is the fast implementation of it.

THE OBJECTIVE, STATED EXACTLY.  For an opener `g1`, let

    Q = { answers a : the reply to g1 against a has >= min_grays grey tiles }

Q is grouped by that reply.  For a candidate second word `g2` the answers in Q
are partitioned by the JOINT pattern (reply to g1, reply to g2), and

    score(g1, g2) = sum over joint buckets of |bucket|^2
    expected      = score(g1, g2) / |Q|

`expected` is the expected number of ANSWERS still consistent after both words,
conditional on the opener having shown at least `min_grays` greys, with the
answer uniform over the 2315.  It is ANSWER-WEIGHTED: a reply produced by 300
answers counts 300 times against one produced by 2, because it is 150x more
likely to be the position you are actually in.  The table records the `g2`
minimising it, ties on the LOWEST GUESS INDEX -- the repo's one ranking rule.

  * IT IS THE SAME QUANTITY `pairsplit` CALLS ssq, restricted to the qualifying
    rows.  |Q| is fixed once the opener is, so the argmin is over an INTEGER sum
    and the comparison is exact: TIES ARE REAL TIES, and the table counts them
    rather than letting the tie-break hide them.

  * THE COUNT IS OVER THE 2315 ANSWERS (the user's call, 2026-09-10), not over
    the 12972 legal words.  So the table optimises for a player who knows the
    curated answer list, and it says so; running it under the `guess` follow-up
    is a deliberate mismatch, not an accident, because the follow-up is a
    separate axis of the experiment.

  * `min_grays` IS PART OF THE OBJECTIVE, not a tuning knob.  A >= 3 table and a
    >= 4 table pick different words and describe different strategies, so the
    threshold is in the file's stamp AND in its name, and a run refuses a table
    whose stamp disagrees with what it asked for.

  * SO ARE THE TWO POOLS.  `openers` says which words get a row; `seconds` says
    which words may BE the second word.  The two shipped variants are

        guess    openers and seconds both the 12972 legal words
        mystery  openers and seconds both the 2315 mystery answers

    The second is a strictly smaller strategy space, so its `expected` figures
    are weakly worse and its sweep results are a different experiment.  NEVER put
    numbers from the two in one table.

  * THE SECOND WORD NEED NOT BE CONSISTENT with the reply, and usually is not.
    That is the point of predetermining it: it is chosen to SPLIT what is left,
    not to win.  The opener itself is excluded as its own second word -- a repeat
    reproduces the reply already seen, so it cannot split anything.

  * AN OPENER CAN HAVE NO ROW'S WORTH OF CASES.  If no answer gives it
    `min_grays` greys, Q is empty, there is nothing to minimise, and the table
    records an EMPTY second word.  The rule then never fires for that opener and
    the strategy is the plain opener.  That is a result, not a gap.

WHAT THIS IS NOT.  Nothing here searches beyond one ply: `expected` is what is
left after two guesses, not what the game goes on to cost.  A word that leaves
fewer candidates can still cost more guesses, and the only thing that settles
that is the simulation the table feeds.  Report `expected` as what it is.
"""

import os
from collections import namedtuple

import numpy as np

from wordle import WORD_LEN, n_patterns

# The pools that have a name rather than a path.  Both are word lists `wordle.
# load_words` already knows; anything else is given as a path and recorded by
# its basename, so a table always states what it was built over.
POOLS = ("guess", "mystery")


def gray_counts(word_len=WORD_LEN):
    """grey-tile count for every pattern CODE, as an array of length 3**L.

    A pattern is base 3 with 0 = grey (wordle.py), so this is the number of zero
    trits.  Position order does not matter to a count, so nothing here needs to
    know which end is most significant.
    """
    n = n_patterns(word_len)
    out = np.zeros(n, dtype=np.int8)
    for code in range(n):
        c, grays = code, 0
        for _ in range(word_len):
            if c % 3 == 0:
                grays += 1
            c //= 3
        out[code] = grays
    return out


def qualifying(pat_row, min_grays, grays=None):
    """Indices of the answers whose reply to this guess shows >= min_grays greys.

    `pat_row` is one row of the pattern matrix: the guess against every answer.
    """
    if grays is None:
        grays = gray_counts()
    return np.flatnonzero(grays[np.asarray(pat_row)] >= min_grays)


def best_second(pat, opener, min_grays, seconds=None, grays=None):
    """THE REFERENCE implementation of the objective above, for one opener.

    Returns (second, score, nq, nbuckets, ties) with `second` the winning GUESS
    index or None when nothing qualifies.  Plain numpy, no reordering and no
    running counters -- it exists to be checked against, so it is written for
    obviousness rather than for speed.

    `seconds` is the array of guess indices allowed to be the second word
    (default: every row of the matrix).  The opener is skipped wherever it
    appears: it can only reproduce the reply already seen.
    """
    pat = np.asarray(pat)
    if grays is None:
        grays = gray_counts()
    if seconds is None:
        seconds = np.arange(pat.shape[0])
    q = qualifying(pat[opener], min_grays, grays)
    p1 = pat[opener][q].astype(np.int64)
    nq = int(len(q))
    nbuckets = int(len(np.unique(p1))) if nq else 0
    if not nq:
        return None, 0, 0, 0, 0
    npat = n_patterns()
    best, best_score, ties = None, None, 0
    for g2 in seconds:
        g2 = int(g2)
        if g2 == opener:
            continue
        joint = p1 * npat + pat[g2][q].astype(np.int64)
        counts = np.bincount(joint)
        score = int((counts.astype(np.int64) ** 2).sum())
        if best_score is None or score < best_score:
            best, best_score, ties = g2, score, 1
        elif score == best_score:
            ties += 1
            best = min(best, g2)          # the lowest guess index wins
    if best is None:                      # only reachable if seconds == {opener}
        return None, 0, nq, nbuckets, 0
    return best, best_score, nq, nbuckets, ties


# --- the table -------------------------------------------------------------

COLUMNS = "opener,second,expected,score,qualifying,buckets,ties"

Table = namedtuple("Table", "path min_grays openers seconds answers rows")


def stamp_line(min_grays, openers, seconds, answers, nsecond):
    """The machine-readable line every table carries as its second line.

    A FILENAME CANNOT CHECK ITSELF -- the greens scar, where results written
    before an objective split were later read under the name the split gave the
    OTHER objective.  The threshold and both pools are in the name for a human
    and in this line for a program, and a reader refuses a table whose stamp does
    not match what it asked for.
    """
    return ("# settings min_grays=%d openers=%s seconds=%s answers=%d "
            "second_pool=%d\n" % (min_grays, openers, seconds, answers, nsecond))


def read_table(path, min_grays=None, openers=None, seconds=None):
    """Read a second-word table, refusing one that is not what was asked for.

    Returns a `Table` whose `rows` maps opener word -> second word, with None for
    an opener that had no qualifying cases.  Any of `min_grays`/`openers`/
    `seconds` given is CHECKED against the stamp rather than assumed.
    """
    if not os.path.exists(path):
        raise SystemExit(
            "no second-word table at %s\n"
            "Build it with: bash solver/run-second-word.sh --variant guess "
            "--min-grays 3" % path)
    meta, rows = {}, {}
    with open(path) as f:
        for line in f:
            if line.startswith("# settings "):
                for field in line[len("# settings "):].split():
                    k, _, v = field.partition("=")
                    meta[k] = v
                continue
            if line.startswith("#") or line.startswith("opener,"):
                continue
            parts = line.rstrip("\n").split(",")
            if len(parts) < 2 or not parts[0]:
                continue
            rows[parts[0]] = parts[1] or None
    if "min_grays" not in meta:
        raise SystemExit(
            "%s carries no '# settings' stamp, so it cannot say which threshold "
            "or which pools it was built under.\nRefusing it rather than "
            "guessing -- rebuild it with solver/run-second-word.sh." % path)
    got = int(meta["min_grays"])
    if min_grays is not None and got != min_grays:
        raise SystemExit("%s was built at min_grays=%d, not %d -- a different "
                         "strategy under the same name" % (path, got, min_grays))
    for name, want in (("openers", openers), ("seconds", seconds)):
        if want is not None and meta.get(name) != want:
            raise SystemExit("%s was built with %s=%s, not %s -- a different "
                             "pool, so a different strategy"
                             % (path, name, meta.get(name), want))
    if not rows:
        raise SystemExit("%s has no rows" % path)
    return Table(path=path, min_grays=got, openers=meta.get("openers", "?"),
                 seconds=meta.get("seconds", "?"),
                 answers=int(meta.get("answers", 0)), rows=rows)
