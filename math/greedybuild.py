"""Build a multi-word opening LETTER BY LETTER, against the real objective.

THE CONSTRUCTION (the user's, 2026-09-18).  Start with `k` blank words -- 5k
empty slots.  At each step consider every (letter, slot) placement, keep the
ones that are LEGAL, score each, and take the best; repeat until every slot is
filled.  The result is k complete words drawn from the pool.

  LEGAL means the word receiving the letter can still be COMPLETED: some pool
  word agrees with every letter already placed in it, the new one included.  So
  a half-built word is always a prefix-pattern of something real, and the
  finished opening is k genuine pool words.

WHY THIS IS NOT THE SCREEN WE ALREADY HAVE.  `run-singles.sh` builds a quad by
extending pairs that scored well, so an opening whose two-word prefixes look
mediocre but whose four words combine beautifully is UNREACHABLE by it.  This
searches the other way -- it never commits to a whole word -- and so reaches
openings that screen cannot.

THE OBJECTIVE IS THE GUARANTEE CONDITION ITSELF, not a proxy for it.  An ANSWER
is UNSOLVED when some live pool word fails to fully split it: formally, when
there is a `g` in its bucket, `g != a`, whose reply against `a` is shared by
another live word, so the follow-up can draw `g` at guess 5 and still be
choosing between two or more words at guess 6.  That is exactly
`guarantee.worst_case(S, a) > 2`, and `tools/checkgreedybuild.py` pins the two
against each other rather than asserting they agree.

  TWO LISTS, TWO ROLES, exactly as everywhere else here: the buckets are over
  the POOL the follow-up draws from (custom.txt's 4282), and the count is over
  the ANSWERS (the 2315).  A bucket can pin every answer in it and still leave
  three pool words alive, which is the whole reason the pool is the one that
  partitions.

TIES BREAK ON SUM OF SQUARES (the user's call) -- the sum of squared bucket
sizes over the pool, the repo's one ranking rule.  This matters more than it
looks: for the first several placements almost nothing is split, so `unsolved`
is pinned at every answer and the TIE-BREAK is choosing the whole construction.

A HALF-BUILT WORD IS SPELLED WITH `_` IN THE BLANKS, and that is not a
convention to remember -- it is the real feedback function applied to a real
string.  `wordle.pattern` gives `_` grey everywhere (it is never green, is not
in any answer, and does not consume a spare copy), so the placed letters get
ordinary Wordle treatment among themselves and the blanks contribute a constant
column that cannot affect a partition.  VERIFIED against `pattern` directly.
"""

import numpy as np

from wordle import pattern_row, to_codes

BLANK = "_"


def spell(word):
    """A partial word as the string the feedback function takes."""
    return "".join(c if c else BLANK for c in word)


def completions(pool_codes, word):
    """Mask of pool words that agree with every letter already placed."""
    ok = np.ones(pool_codes.shape[0], dtype=bool)
    for j, c in enumerate(word):
        if c:
            ok &= pool_codes[:, j] == (ord(c) - ord("a"))
    return ok


def joint_key(rows):
    """Fold one reply row per opening word into a single key per pool word."""
    key = np.zeros(rows[0].shape[0], dtype=np.int64)
    for r in rows:
        key = key * 243 + r
    return key


def solved_in_bucket(full, cols, members, answer_pos):
    """Which of this bucket's answers EVERY live word fully splits.

    `members` are pool indices in the bucket, `answer_pos` their positions
    within it that are answers.  Returns the positions still solved.

    IT WALKS THE LIVE WORDS AND STOPS WHEN NOTHING IS LEFT, which is what makes
    the early steps affordable: a solved answer must be isolated by EVERY `g`,
    so one `g` that shares its reply settles it.  In a wide bucket the first
    `g` eliminates nearly everything, so the cost is a couple of passes over the
    bucket rather than the |S|^2 the definition reads like.
    """
    cand = list(answer_pos)
    for g in range(len(members)):
        if not cand:
            break
        row = full[cols[members[g]]][cols[members]]
        cnt = np.bincount(row, minlength=243)
        # g == a is the follow-up DRAWING the answer, which wins; only a wrong
        # word that leaves company behind can make an answer unsolved.
        cand = [a for a in cand if a == g or cnt[row[a]] == 1]
    return cand


def score(state, ctx):
    """(unsolved answers, sum of squared bucket sizes) for a partial opening."""
    full, pool_codes, cols, ans_pool_idx, rows_cache = ctx
    rows = [rows_cache[i] for i in range(len(state))]
    key = joint_key(rows)
    uniq, inv = np.unique(key, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uniq))
    ssq = int((sizes.astype(np.int64) ** 2).sum())

    order = np.argsort(inv, kind="stable")
    starts = np.searchsorted(inv[order], np.arange(len(uniq)), "left")
    ends = np.searchsorted(inv[order], np.arange(len(uniq)), "right")
    abucket = inv[ans_pool_idx]

    solved = 0
    for b in np.unique(abucket):
        members = order[starts[b]:ends[b]]
        where = {int(m): p for p, m in enumerate(members)}
        apos = [where[int(i)] for i in ans_pool_idx[abucket == b]]
        solved += len(solved_in_bucket(full, cols, members, apos))
    return len(ans_pool_idx) - solved, ssq
