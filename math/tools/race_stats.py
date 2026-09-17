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
    entry strictly worse in every game is eliminated on the mean alone.

    THE WIN-RATE CEILING PROBLEM CANNOT ARISE HERE whatever the score is.  For
    guess counts there is no ceiling to be pinned against; for the 0/1 indicator
    the wordlesim race ranks on, the DIFFERENCE is in {-1, 0, 1} and its spread
    is set by how often two entries DISAGREE, not by how close either rate is to
    1 -- which is exactly what a proportion's own `sqrt(p(1-p)/n)` loses at p=1,
    and why the sweep needs a plus-four error there and this does not.
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


# --- THE RACE ITSELF -------------------------------------------------------
#
# ONE driver, run by every race here.  It owns the block schedule, the chunking,
# the two phases and the switch between them, the checkpointing, the cut, the
# elimination lines and the status line -- everything except how a game is
# PLAYED and how the standings are WRITTEN, which is all a game-specific adapter
# supplies.  A race that lived in its own file would drift from its sibling in
# exactly those places: the first wordlesim race did, within a day, by
# summarising eliminations the multiwordle race prints one by one.
#
# AN ADAPTER PROVIDES:
#
#   player.make_games(seed, g0, g1) -> games
#       Whatever one chunk of games is for this game, built from the seed and the
#       GAME INDICES alone -- never from the field, the chunking or the block --
#       so that a resume replays exactly the same games and every entry in the
#       race meets the identical ones.
#   player.play(ids, games) -> (len(ids), n) int16 scores
#       Lower is better.  Raise `Regrow` to say the games object was too small
#       (a coin-flip array that ran out); the driver rebuilds it and retries.
#   player.regrow()
#       Make the next make_games bigger.  Only called after `Regrow`.
#   player.chunk_size(ids, n_games, target, seed) -> int or None
#       How many games to play before checkpointing.  None means "use the
#       measured default".  THE CHUNK IS A CHECKPOINT INTERVAL AND NOTHING ELSE:
#       games are seeded by index, so any chunking plays the same games in the
#       same order.
#   writer(live, mean, ose, md, se, n_games, lead)
#       Write the standings.  Deliberately NOT shared: one race's file feeds the
#       multiwordle report tools and the other's is read as a sweep, so the
#       FORMAT is a property of the family, not of racing.

class Regrow(Exception):
    """The games object was too small for some entry; rebuild it bigger."""


# How long a chunk should take when the adapter has no opinion.  A target, not a
# parameter of the result.
CHUNK_SECONDS = 2.0


def _identity(v):
    return v


def run(cfg, player, names, is_answer, writer, elim_path, ck_path,
        elim_columns, noun="opening", extra=None, stem="", display=_identity,
        tiebreak=None, tiebreak_name=""):
    """Race `names` until one is left, `--max-games` is reached, or it is halted.

    `tiebreak` is an optional callable `(live, n_games) -> array over live
    positions, lower better`, used ONLY to break EXACT ties in the ranked total
    when choosing the leader and when ordering.  It takes the game count so it
    can return a per-game MEAN rather than a running total -- the two order
    identically, but only one of them is a number worth printing.  It exists because a ranked score with few distinct
    values -- a win rate at 100 games, say, where thousands tie at 1 -- otherwise
    makes the leader whichever tied entry happens to sit at the lowest index,
    which is an artifact of the input file's order.

      IT IS NOT PURELY COSMETIC, and the caller should know why.  The leader is
      the reference point the paired difference is measured against, so choosing
      a different one among ties leaves every `md` unchanged (the means are equal
      by definition of a tie) but moves the paired ERRORS, since the variance of
      a difference depends on WHICH entry you difference against.  So a few
      borderline entries can be cut that would not have been, and the reverse.
      The cut is equally sound either way -- it is a valid paired comparison
      against any leader -- and it is better justified against a leader that is
      actually best on a stated secondary key than against an arbitrary one.
      Omit it and the behaviour is exactly what it was.

    `display` maps the RANKED value to the one the console and the elimination
    log show, for an adapter that ranks on an inverted score -- the wordlesim
    race ranks a win rate as a LOSS rate so that lower stays better here, and
    shows `1 - x`.  It defaults to the identity, so a caller that does not pass
    it is byte-identical to before: this is a hook for one caller, NOT a change
    of behaviour for every caller.  GAPS are never passed through it -- a
    difference of ranked values is already "how far behind", in either sense.

    Returns (live, n_games).  `extra` is a dict of per-entry arrays the adapter
    wants carried in the checkpoint (a win count, say); it is updated in place
    from the checkpoint on a resume and handed back to the adapter's writer.
    """
    import os
    import time

    n = len(names)
    extra = {} if extra is None else extra
    live = np.arange(n)
    n_games = 0                # games every live entry has completed
    hist = np.zeros((n, 0), dtype=np.int16)
    paired = None              # (sum_d, sumsq_d, tot, sq) once switched
    status = ["live"] * n
    elim_at = np.zeros(n, dtype=np.int64)

    if ck_path and os.path.exists(ck_path):
        z = np.load(ck_path, allow_pickle=False)
        if int(z["field"]) != n:
            raise SystemExit(
                "%s was written for a field of %d entries, not %d -- a "
                "checkpoint from a different race must never be resumed into "
                "this one" % (ck_path, int(z["field"]), n))
        live = z["live"]
        n_games = int(z["n_games"])
        status = [s.decode() for s in z["status"]]
        elim_at = z["elim_at"]
        for k in extra:
            if k in z:
                # IN PLACE.  The adapter holds a reference to this array and
                # accumulates into it; rebinding the dict entry would leave the
                # adapter writing to the pre-resume copy, so a resumed race would
                # report the wrong extras while every score was right.
                extra[k][...] = z[k]
        if bool(z["paired"]):
            paired = (z["sum_d"], z["sumsq_d"], z["tot"], z["sq"])
        else:
            hist = z["hist"]
        if "filled" in z and int(z["filled"]):
            # written by the openings-outer version, which could leave a block
            # part-played: those extra games belong to some entries and not
            # others, so they are DISCARDED rather than mixed into a comparison
            print("  (checkpoint holds a part-played block from the older "
                  "openings-outer loop; discarding it and resuming from %d "
                  "complete games)" % n_games)
        if hist.shape[1] > n_games:
            hist = hist[:, :n_games].copy()
        print("\nresuming: %d live, every one level at %d games"
              % (len(live), n_games))

    if ck_path:
        os.makedirs(os.path.dirname(ck_path) or ".", exist_ok=True)
    if elim_path and not os.path.exists(elim_path):
        os.makedirs(os.path.dirname(elim_path) or ".", exist_ok=True)
        with open(elim_path, "w") as f:
            f.write("# %s -- one row per %s as it leaves the race\n"
                    % (stem, noun))
            f.write(elim_columns + "\n")

    last_ck = [0.0]

    def checkpoint(force=False):
        """Save the race state.  Cheap to call: it writes at most every
        --checkpoint seconds, because the history grows with the game count and
        the chunks are deliberately short.  The state is consistent at EVERY
        chunk boundary (all live entries level at n_games), so a skipped write
        costs at most that many seconds of games, never correctness."""
        if not ck_path:
            return
        if not force and time.time() - last_ck[0] < cfg["checkpoint"]:
            return
        last_ck[0] = time.time()
        kw = dict(field=n, live=live, n_games=n_games, elim_at=elim_at,
                  status=np.array([s.encode() for s in status]),
                  paired=paired is not None)
        kw.update(extra)
        if paired is None:
            kw["hist"] = hist
        else:
            kw.update(sum_d=paired[0], sumsq_d=paired[1], tot=paired[2],
                      sq=paired[3])
        # atomic: a checkpoint half-written by a Ctrl-C would lose the whole race
        np.savez(ck_path + ".tmp", **kw)
        os.replace(ck_path + ".tmp.npz", ck_path)

    last_report = time.time()
    per_game = [0.0]
    for target in block_targets(cfg["block"], cfg["growth"], cfg["max_games"]):
        if len(live) <= 1:
            break
        if target <= n_games:
            continue

        # GAMES ARE THE OUTER LOOP, so every live entry is always level: stop
        # whenever you like and the standings are a real ranking of the whole
        # field at n_games, not a complete answer for an alphabetical prefix and
        # nothing for the rest.
        if paired is None and hist.shape[1] < target:
            grown = np.zeros((len(live), target), dtype=np.int16)
            grown[:, :hist.shape[1]] = hist
            hist = grown

        while n_games < target:
            step = player.chunk_size(live, n_games, target, cfg["seed"])
            if step is None:
                step = (cfg["chunk"] if cfg["chunk"] else
                        max(1, int(CHUNK_SECONDS
                                   / (per_game[0] * max(1, len(live)))))
                        if per_game[0] > 0 else max(1, min(8, target - n_games)))
            hi = min(target, n_games + step)
            c0 = time.time()
            while True:
                games = player.make_games(cfg["seed"], n_games, hi)
                try:
                    sc = player.play(live, games)
                    break
                except Regrow:
                    player.regrow()
            per_game[0] = (time.time() - c0) / max(1, (hi - n_games) * len(live))
            player.record(live, sc, n_games, hi)
            if paired is None:
                hist[:, n_games:hi] = sc
            else:
                paired = accumulate_pairwise(paired, sc)
            # n_games advances WITH the scores, in both phases, so a resume never
            # replays a chunk and never leaves the field ragged
            n_games = hi
            checkpoint()
            if time.time() - last_report > cfg["report"]:
                print("  %d/%d games of this block, %d %ss each"
                      % (n_games, target, len(live), noun))
                last_report = time.time()

        # --- the cut, on the paired difference against the leader
        tb = (None if tiebreak is None
              else np.asarray(tiebreak(live, n_games), dtype=float))

        def _leader(tot):
            """The best total, ties broken by the secondary key when there is one.

            `tot` is a SUM over a game count every live entry shares, so ties in
            it are exactly ties in the mean -- no division needed to compare.
            """
            if tb is None:
                return int(np.argmin(tot))
            return int(np.lexsort((tb, tot))[0])

        if paired is None:
            tot, sq = history_sums(hist, n_games)
            lead = _leader(tot)
            tot, sq, sum_d_l, sumsq_d_l = history_paired(hist, n_games, lead)
        else:
            sum_d, sumsq_d, tot, sq = paired
            lead = _leader(tot)
            sum_d_l, sumsq_d_l = sum_d[:, lead], sumsq_d[:, lead]
        md, se = paired_error(sum_d_l, sumsq_d_l, n_games)
        mean, ose = own_error(tot, sq, n_games)

        drop = eliminate(md, se, cfg["sigma"], lead)
        keep = ~drop
        rows = []
        for pos in np.flatnonzero(drop):
            c = int(live[pos])
            status[c] = "out"
            elim_at[c] = n_games
            sig = md[pos] / se[pos] if se[pos] > 0 else float("inf")
            rows.append((c, "%s,%d,%.6f,%.6f,%.6f,%.3f,%s"
                         % (names[c], n_games, display(mean[pos]), md[pos],
                            se[pos], sig, names[int(live[lead])])))
            # EVERY elimination prints, one line each, as it happens.  The first
            # block of a full field drops thousands at once and that is a lot of
            # scrollback -- but it is what the run is watched FOR, so it is never
            # summarised or capped.  The log is tee'd, so nothing has to be
            # caught live.
            print("  OUT  %-14s %9.4f   %+.4f +/- %.4f  (%.1f sigma behind %s)"
                  % (names[c], display(mean[pos]), md[pos], se[pos], sig,
                     names[int(live[lead])]))
        if rows and elim_path:
            with open(elim_path, "a") as f:
                f.write("\n".join(r[1] for r in rows) + "\n")
        if rows and is_answer[[c for c, _ in rows]].any() \
                and not is_answer[live[keep]].any():
            last = min((c for c, _ in rows if is_answer[c]),
                       key=lambda c: mean[int(np.flatnonzero(live == c)[0])])
            print("  ^^ %s was the LAST %s made only of answer words, "
                  "out at %d games" % (names[last], noun, n_games))

        mean, ose, md, se = mean[keep], ose[keep], md[keep], se[keep]
        live = live[keep]
        if tb is not None:
            tb = tb[keep]
        lead = _leader(mean)
        if paired is None:
            hist = hist[keep]
        else:
            paired = tuple(x[np.ix_(keep, keep)] if x.ndim == 2 else x[keep]
                           for x in paired)

        order = (np.argsort(mean, kind="stable") if tb is None
                 else np.lexsort((tb, mean)))
        gap = sig2 = float("nan")
        if len(order) > 1:
            j = int(order[1])
            gap = mean[j] - mean[int(order[0])]
            sig2 = md[j] / se[j] if se[j] > 0 else float("inf")
        best_ans = [int(live[p]) for p in order if is_answer[int(live[p])]]
        print("%9d games  %6d live  leader %-14s %.4f%s (own se %.4f)  "
              "2nd is %.4f = %.1f paired sigma back  |  %s"
              % (n_games, len(live), names[int(live[lead])],
                 display(mean[lead]),
                 "" if tb is None else " [%s %.4f]" % (tiebreak_name or "2nd key",
                                                       tb[lead]),
                 ose[lead], gap, sig2,
                 ("best answer %s %s" % (noun, names[best_ans[0]])) if best_ans
                 else "NO answer %ss left" % noun))

        if paired is None:
            mem = len(live) * n_games * 8 / 1e9
            if len(live) <= cfg["pair_at"] or mem > cfg["max_mem"]:
                paired = pairwise_from_history(hist, n_games)
                hist = np.zeros((0, 0), dtype=np.int16)
                print("  (switched to pairwise sums over %d %ss -- memory "
                      "is now independent of the game count)" % (len(live), noun))
        checkpoint(force=True)
        writer(status, elim_at, live, mean, ose, md, se, n_games, lead)
        if len(live) <= 1:
            break

    print("\n%d %ss still live at %d games:" % (len(live), noun, n_games))
    for c in live[:20]:
        print("   %s" % names[int(c)])
    return live, n_games
