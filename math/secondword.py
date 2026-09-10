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
import re
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


def compositions(word_len=WORD_LEN):
    """(greens, yellows, greys) for every pattern CODE, as three int8 arrays.

    2 = green, 1 = yellow, 0 = grey (wordle.py), and the three always sum to the
    word length, so a reply's composition is what a player can read off the board
    without knowing which positions were which.
    """
    n = n_patterns(word_len)
    g = np.zeros(n, dtype=np.int8)
    y = np.zeros(n, dtype=np.int8)
    for code in range(n):
        c = code
        for _ in range(word_len):
            t = c % 3
            if t == 2:
                g[code] += 1
            elif t == 1:
                y[code] += 1
            c //= 3
    return g, y, np.int8(word_len) - g - y


def group_mask(spec, word_len=WORD_LEN):
    """The compositions one GROUP covers: (mask over pattern codes, canonical spec).

    A group spec is one or more TERMS joined by `+`:

        g<N>        greys >= N          (the original threshold)
        e<N>        greys == N exactly  (what a per-grey-count rule wants)
        <G>g<Y>y    exactly that composition, e.g. 0g3y

    So `g3` is everything with three or more greys, `e5` is the all-grey reply
    alone, and `g3+0g3y` is the threshold plus the three-yellow two-grey reply.

    THE SPEC IS CANONICALISED, and a REDUNDANT TERM IS REFUSED rather than
    quietly dropped: `g3+0g0y` covers exactly what `g3` covers, so allowing it
    would give one rule two names -- and therefore two tables that a reader would
    have to tell apart by hand.  Terms are sorted, so order cannot do the same.
    """
    g, y, gr = compositions(word_len)
    terms = {}
    for term in spec.split("+"):
        if re.fullmatch(r"g\d+", term):
            m = gr >= int(term[1:])
            key = (0, int(term[1:]))
        elif re.fullmatch(r"e\d+", term):
            m = gr == int(term[1:])
            key = (1, int(term[1:]))
        elif re.fullmatch(r"\d+g\d+y", term):
            gg, yy = (int(x) for x in re.findall(r"\d+", term))
            if gg + yy > word_len:
                raise SystemExit("(%d green, %d yellow) is more than %d tiles"
                                 % (gg, yy, word_len))
            m = (g == gg) & (y == yy)
            key = (2, gg * (word_len + 1) + yy)
        else:
            raise SystemExit("cannot read the group %r: a term is g<N>, e<N> or "
                             "<G>g<Y>y, joined by +" % spec)
        if not m.any():
            raise SystemExit("the term %r in %r covers no reply at all"
                             % (term, spec))
        if term in terms:
            raise SystemExit("the group %r repeats the term %r" % (spec, term))
        terms[term] = (key, m)
    mask = np.zeros(len(g), dtype=bool)
    for _, m in terms.values():
        mask |= m
    for term, (_, m) in terms.items():
        rest = np.zeros(len(g), dtype=bool)
        for other, (_, om) in terms.items():
            if other != term:
                rest |= om
        if (m & ~rest).sum() == 0:
            raise SystemExit("the term %r adds nothing to the group %r -- one "
                             "rule would have two names" % (term, spec))
    canon = "+".join(sorted(terms, key=lambda t: terms[t][0]))
    return mask, canon


def fire_groups(specs, word_len=WORD_LEN):
    """THE FIRING CONDITION: an ordered list of DISJOINT groups, each of which
    gets its OWN predetermined second word.

    WHY GROUPS AND NOT ONE SET (the user's, 2026-09-10).  This started as "at
    least N greys, play this word", became "at least N greys OR this composition"
    when it turned out two greys with three YELLOWS is nothing like two greys with
    three GREENS, and is now the general form: the reply's bucket SELECTS the
    word.  A separate word for five, four and three greys is `e5 e4 e3`; the old
    single-word rules are the one-group case and still mean exactly what they
    meant.

    THE GROUPS MUST BE DISJOINT, and that is not a nicety: a reply in two groups
    would have two predetermined words and no rule for choosing between them.
    Everything in no group DECLINES to the follow-up.

    Returns (list of (spec, mask), canonical label).  The label is a function of
    the PARTITION, not of how it was typed -- the specs are sorted -- so two
    spellings of one rule cannot make two filenames.
    """
    if not specs:
        raise SystemExit("a firing condition needs at least one --group")
    seen = {}
    for raw in specs:
        m, spec = group_mask(raw, word_len)
        for other, om in seen.items():
            if (m & om).any():
                raise SystemExit(
                    "the groups %r and %r overlap: a reply in both would have "
                    "two predetermined words and no rule for choosing" 
                    % (other, spec))
        if spec in seen:
            continue
        seen[spec] = m
    order = sorted(seen)
    covered = np.zeros(n_patterns(word_len), dtype=bool)
    for k in order:
        covered |= seen[k]
    if covered.all():
        raise SystemExit(
            "this condition fires on EVERY reply, which is a blind two-word "
            "opening rather than a rule that chooses when to commit -- the "
            "`opening` strategy already is that")
    return [(k, seen[k]) for k in order], ".".join(order)


def fire_set(min_grays, extra=(), word_len=WORD_LEN):
    """The ONE-GROUP case, kept because it is the common one: "at least N greys",
    optionally plus whole compositions.  Returns (mask, label), as before.
    """
    spec = "g%d" % min_grays
    g, y, gr = compositions(word_len)
    for gg, yy in sorted({(int(a), int(b)) for a, b in extra}):
        if gg + yy > word_len:
            raise SystemExit("(%d green, %d yellow) is more than %d tiles"
                             % (gg, yy, word_len))
        if word_len - gg - yy >= min_grays:
            continue                      # already fires; not part of the label
        spec += "+%dg%dy" % (gg, yy)
    return group_mask(spec, word_len)


def parse_fire_label(label, word_len=WORD_LEN):
    """The inverse of the canonical label: the GROUPS a table was built under.

    A table records the label, so a reader rebuilds the exact firing condition
    from it rather than being told a threshold and guessing the rest.  Returns
    the same (groups, label) shape `fire_groups` does, and REFUSES a label that
    is not canonical -- it would name a file no rebuild of the rule would produce.
    """
    groups, canon = fire_groups(label.split("."), word_len)
    if canon != label:
        raise SystemExit("the firing condition %r is not canonical (it means "
                         "%r) -- rebuild the table" % (label, canon))
    return groups


def fire_mask(label, word_len=WORD_LEN):
    """Every code that fires, across all groups -- when only "does it fire" matters."""
    m = np.zeros(n_patterns(word_len), dtype=bool)
    for _, gm in parse_fire_label(label, word_len):
        m |= gm
    return m


def qualifying(pat_row, mask):
    """Indices of the answers whose reply to this guess FIRES the rule.

    `pat_row` is one row of the pattern matrix: the guess against every answer.
    """
    return np.flatnonzero(np.asarray(mask)[np.asarray(pat_row)])


def best_second(pat, opener, mask, seconds=None):
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
    if seconds is None:
        seconds = np.arange(pat.shape[0])
    q = qualifying(pat[opener], mask)
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

COLUMNS = "opener,fires,second,expected,score,qualifying,buckets,ties"

Table = namedtuple("Table",
                   "path min_grays fire groups openers seconds answers rows")


def stamp_line(fire, openers, seconds, answers, nsecond, min_grays=None):
    """The machine-readable line every table carries as its second line.

    A FILENAME CANNOT CHECK ITSELF -- the greens scar, where results written
    before an objective split were later read under the name the split gave the
    OTHER objective.  The threshold and both pools are in the name for a human
    and in this line for a program, and a reader refuses a table whose stamp does
    not match what it asked for.
    """
    head = "" if min_grays is None else "min_grays=%d " % min_grays
    return ("# settings %sfire=%s openers=%s seconds=%s answers=%d "
            "second_pool=%d\n"
            % (head, fire, openers, seconds, answers, nsecond))


def read_table(path, fire=None, openers=None, seconds=None):
    """Read a second-word table, refusing one that is not what was asked for.

    Returns a `Table` whose `rows` maps opener word -> {group spec -> second
    word}, with None for a group that had no qualifying cases.  Any of
    `fire`/`openers`/`seconds` given is CHECKED against the stamp rather than
    assumed.

    A table written before the firing condition became a PARTITION has no
    `fires` column and carries a single group, which is exactly what its label
    says -- so every earlier table keeps working and keeps meaning what it meant.
    """
    if not os.path.exists(path):
        raise SystemExit(
            "no second-word table at %s\n"
            "Build it with: bash solver/run-second-word.sh --variant guess "
            "--min-grays 3" % path)
    meta, rows, cols = {}, {}, None
    with open(path) as f:
        for line in f:
            if line.startswith("# settings "):
                for field in line[len("# settings "):].split():
                    k, _, v = field.partition("=")
                    meta[k] = v
                continue
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split(",")
            if cols is None and parts[0] == "opener":
                cols = parts
                continue
            if len(parts) < 2 or not parts[0]:
                continue
            if cols and "fires" in cols:
                spec, second = parts[1], parts[2] or None
            else:
                spec, second = None, parts[1] or None
            rows.setdefault(parts[0], {})[spec] = second
    if "fire" not in meta and "min_grays" not in meta:
        raise SystemExit(
            "%s carries no '# settings' stamp, so it cannot say which condition "
            "or which pools it was built under.\nRefusing it rather than "
            "guessing -- rebuild it with solver/run-second-word.sh." % path)
    got = int(meta["min_grays"]) if "min_grays" in meta else None
    # A table written before the condition became a partition carries only the
    # threshold, which means exactly the one group `g<N>`.
    got_fire = meta.get("fire", "g%s" % got)
    groups = parse_fire_label(got_fire)     # refuse a label we cannot rebuild
    if fire is not None and got_fire != fire:
        raise SystemExit("%s fires on %s, not %s -- a different strategy under "
                         "the same name" % (path, got_fire, fire))
    for name, want in (("openers", openers), ("seconds", seconds)):
        if want is not None and meta.get(name) != want:
            raise SystemExit("%s was built with %s=%s, not %s -- a different "
                             "pool, so a different strategy"
                             % (path, name, meta.get(name), want))
    if not rows:
        raise SystemExit("%s has no rows" % path)
    # A one-group table written before the `fires` column keys its row on None;
    # name it, so every reader downstream sees one shape.
    if len(groups) == 1:
        only = groups[0][0]
        for w in rows:
            if None in rows[w]:
                rows[w] = {only: rows[w][None]}
    missing = [w for w in rows if sorted(rows[w]) != sorted(k for k, _ in groups)]
    if missing:
        raise SystemExit("%s has no row for every group of %s (e.g. %s) -- it "
                         "was not built under this condition"
                         % (path, got_fire, missing[0]))
    return Table(path=path, min_grays=got, fire=got_fire, groups=groups,
                 openers=meta.get("openers", "?"),
                 seconds=meta.get("seconds", "?"),
                 answers=int(meta.get("answers", 0)), rows=rows)


def word_by_code(table, opener, guesses, word_len=WORD_LEN):
    """The rule itself, as a lookup: reply CODE -> guess index, or -1.

    One array, built once from the table's own groups, so the rule is a single
    indexing operation and cannot disagree with the table it came from.  A group
    whose second word is empty -- nothing qualified -- simply declines, exactly
    as an unlisted reply does.
    """
    out = np.full(n_patterns(word_len), -1, dtype=np.int32)
    for spec, mask in table.groups:
        second = table.rows[opener][spec]
        if second is None:
            continue
        try:
            out[mask] = guesses.index(second)
        except ValueError:
            raise SystemExit("%s: the second word %r for group %s is not a legal "
                             "guess" % (table.path, second, spec))
    return out
