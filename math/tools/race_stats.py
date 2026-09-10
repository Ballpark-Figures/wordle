"""The ESTIMATOR and the CUT a race runs on -- shared, so they cannot drift.

A race replaces the staged cascade (sweep, cut, re-sweep the survivors larger,
repeat) with ONE resumable process: every entry starts on a block of games,
anything more than `sigma` PAIRED standard errors behind the leader leaves the
moment that becomes true, and the survivors keep playing on a doubling schedule.
`tools/multiwordle_race.py` races multiwordle openings; `tools/wordle_race.py`
races single-board wordlesim openers.  The two play different GAMES, so each owns
its own driver -- how a chunk of games is played, what setup it needs, what the
coin flips look like -- but the arithmetic that turns those scores into a
standing and an elimination is one thing, and it lives here.

WHAT IS SHARED IS EXACTLY WHAT MUST NOT DIFFER: the paired difference against the
leader, the two standard errors, the block schedule and the cut itself.  A second
copy of any of those would be a second definition of what "5 sigma behind" means.
What is NOT shared is the loop, deliberately -- multiwordle's has to amortise a
per-opening setup table and wordlesim's has none, so one loop serving both would
be the shared-helper failure the rules warn about.

THE PAIRING IS THE POINT.  Every entry plays the IDENTICAL games -- same answers,
same coin flips -- so an entry is judged on `d_i = score_it - score_leadt` game by
game, and the error on that DIFFERENCE is far smaller than either entry's own
standard error, because almost all the variance is the game and cancels.  Both
are reported; only the paired one decides.

A RACE ELIMINATES AGAINST A MOVING LEADER, so an entry that draws a lucky first
block can push a better one out.  The generous default cut is a mitigation, not a
proof: a race is a SCREEN, and its winner is the best of the entries entered,
judged on the games actually played.
"""

import numpy as np


def _col_chunk(m):
    """Columns of history to take at once, so a pass stays around 32 MB."""
    return max(1, (1 << 22) // max(1, m))


def history_sums(hist, n):
    """Per-entry sum and sum of squares of the scores."""
    m = hist.shape[0]
    tot = np.zeros(m)
    sq = np.zeros(m)
    step = _col_chunk(m)
    for i in range(0, n, step):
        s = hist[:, i:min(n, i + step)].astype(np.float64)
        tot += s.sum(axis=1)
        sq += (s * s).sum(axis=1)
    return tot, sq


def history_paired(hist, n, lead):
    """sum(d) and sum(d^2) against one entry, d_i = score_it - score_leadt.

    Expanded as sum(a^2) - 2 sum(a b) + sum(b^2) rather than materialising the
    difference, so the leader can move every block without the memory moving too.
    """
    m = hist.shape[0]
    tot, sq = history_sums(hist, n)
    cross = np.zeros(m)
    step = _col_chunk(m)
    for i in range(0, n, step):
        s = hist[:, i:min(n, i + step)].astype(np.float64)
        cross += s @ s[lead]
    return tot, sq, tot - tot[lead], sq - 2.0 * cross + sq[lead]


def pairwise_from_history(hist, n):
    """(sum_d, sumsq_d, tot, sq) for EVERY pair, computed from the history once.

    The phase switch: while the field is wide the per-game scores are kept, which
    makes any pairwise comparison exact even as the leader changes; once it is
    narrow these sums replace the history and memory stops depending on the game
    count.  Nothing is estimated across the switch -- these are the same numbers
    `history_paired` would give for any leader.
    """
    tot, sq = history_sums(hist, n)
    s = hist[:, :n].astype(np.float64)
    return (tot[:, None] - tot[None, :],
            sq[:, None] + sq[None, :] - 2.0 * (s @ s.T), tot, sq)


def accumulate_pairwise(paired, sc):
    """Fold one chunk of scores into the pairwise sums.  `sc` is (entries, games)."""
    sum_d, sumsq_d, tot, sq = paired
    f = np.asarray(sc, dtype=np.float64)
    rs = f.sum(axis=1)
    rq = (f * f).sum(axis=1)
    tot = tot + rs
    sq = sq + rq
    sum_d = sum_d + (rs[:, None] - rs[None, :])
    sumsq_d = sumsq_d + (rq[:, None] + rq[None, :] - 2.0 * (f @ f.T))
    return sum_d, sumsq_d, tot, sq


def paired_error(sum_d, sumsq_d, n):
    """Mean and standard error of the per-game difference against the leader.

    Zero variance is a real answer, not a degenerate one: two entries that scored
    identically in EVERY game have a difference of exactly 0 with no spread, and an
    entry strictly worse in every game is eliminated on the mean alone.  This is
    also where the win-rate ceiling problem of a proportion cannot arise -- the
    difference of two guess COUNTS has no ceiling to be pinned against.
    """
    md = sum_d / n
    if n < 2:
        return md, np.zeros_like(md)
    var = (sumsq_d - n * md * md) / (n - 1)
    np.clip(var, 0.0, None, out=var)
    return md, np.sqrt(var / n)


def own_error(tot, sq, n):
    """Each entry's OWN standard error -- reported, never used for the cut.

    It is the conservative unpaired number the old cascade cut on, so keeping it
    in every row makes the gain from pairing visible rather than asserted.
    """
    mean = tot / n
    if n < 2:
        return mean, np.zeros_like(mean)
    var = (sq - n * mean * mean) / (n - 1)
    np.clip(var, 0.0, None, out=var)
    return mean, np.sqrt(var / n)


def block_targets(block, growth, max_games):
    """100, 200, 400, ... -- each block multiplies the total game count."""
    n = block
    while True:
        if max_games is not None and n >= max_games:
            yield max_games
            return
        yield n
        n = max(n + 1, int(round(n * growth)))


def eliminate(md, se, sigma, lead):
    """Who leaves: everything more than `sigma` PAIRED sigma behind the leader.

    STRICTLY behind, and the leader itself never leaves -- so a field that is all
    ties keeps everybody, and the cut can never empty the race.  `md` is measured
    against `lead`, so `md[lead]` is 0 by construction; it is cleared anyway
    rather than relied on, since a caller passing the wrong leader index should
    lose an entry it can see rather than the leader it cannot.
    """
    drop = md - sigma * se > 0
    drop[lead] = False
    return drop
