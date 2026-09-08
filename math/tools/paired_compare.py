"""Compare a handful of finalist openings by PAIRED DIFFERENCES, not by two means.

    python3 tools/paired_compare.py --from FINALISTS.txt --fallback answer \\
        --pair-adaptive 2 -t 200000 --seed 100 --out data/shared/wordlesim/paired_x.csv

WHY THIS EXISTS.  A sweep reports each opening's mean with its OWN standard error,
and at the end of a cascade the gaps between finalists are far smaller than those
errors -- 22 openings inside 1.5 SE, leaders trading places at every doubling.
Judging a gap by two individual errors is too conservative, because the openings
PLAY THE SAME GAMES: most of the per-game variance is "which answer got drawn",
and that is shared.  Differencing removes it.

THE ESTIMATOR, exactly.  For game i, every opening scores on the SAME answer;
`d_i = score_A(i) - score_B(i)` and the estimate is `mean(d)` with standard error
`sd(d)/sqrt(t)`.  No new modelling and no assumption: it is the same games, read
as differences.  The absolute means are unchanged and keep their own errors -- this
sharpens COMPARISONS WITHIN the set, nothing else.

TWO LEVELS OF COUPLING, and the second is a deliberate choice (user's call,
2026-09-08: couple them).

  1. THE ANSWER is drawn once per game and handed to every opening.  This is what
     the sweep already did across words, and it removes the dominant variance term.

  2. THE FOLLOW-UP'S COIN FLIPS are coupled too: every opening starts each game
     with a generator seeded from (seed, game), so their candidate draws consume
     the SAME underlying uniforms in the same order.  Each opening's own
     distribution is untouched -- a uniform draw from ITS live set is still uniform
     over ITS live set -- so every mean stays unbiased; only the correlation
     between openings changes, which is the entire point.

     THE DRAW USES `random()` AND AN INDEX, NOT `integers(n)`.  `integers` consumes
     a variable number of bits (rejection sampling), so two openings whose live
     sets differ in SIZE would fall out of step after the first differing draw and
     the coupling would silently decay.  One float per draw keeps them in lockstep
     turn for turn.  That is a different consumption pattern from the sweep's, so
     **a paired mean will not match a sweep cell to the last digit** -- same
     quantity, different sample.

WHAT IT CANNOT DO.  It says nothing about openings outside the set it was given,
and it does not revisit the screen that chose them.  A finalist list is still the
tail of a cascade of cuts.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import ALL_GREEN, load_words  # noqa: E402
from wordlesim import (answer_to_guess, make_opening_rule,  # noqa: E402
                       make_tail, draw_answer)


class CoupledDraw:
    """A follow-up whose draws are one float each, so openings stay in lockstep.

    Wraps the ordinary follow-up: same live set, same uniform distribution over
    it, but the index is taken from `rng.random()` rather than `rng.integers`,
    which consumes a FIXED amount of the stream whatever the set size.
    """

    def __init__(self, tail):
        self.tail = tail

    def live_count(self, alive, played, replies):
        return self.tail.live_count(alive, played, replies)

    def __call__(self, turn, alive, played, replies, rng):
        if hasattr(self.tail, "_refresh"):
            live = self.tail._refresh(played, replies)
            idx = np.flatnonzero(live)
            pick = idx[min(int(rng.random() * len(idx)), len(idx) - 1)]
            return int(pick)
        idx = np.flatnonzero(alive)
        pick = idx[min(int(rng.random() * len(idx)), len(idx) - 1)]
        return int(self.tail.ans2g[pick])


def parse_args(argv):
    src = out = None
    fallback = None
    adapt = 0
    t = None
    seed = 100
    openings = []
    progress = 20000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--opening":
            openings.append(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--fallback":
            fallback = argv[i + 1]; i += 2
        elif a == "--pair-adaptive":
            adapt = int(argv[i + 1]); i += 2
        elif a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if src:
        with open(src) as f:
            openings.extend(ln.strip() for ln in f if ln.strip())
    if len(openings) < 2:
        raise SystemExit("give at least two openings (--from FILE or --opening)")
    if fallback not in ("answer", "guess"):
        raise SystemExit("--fallback answer|guess is required")
    if t is None or t < 1:
        raise SystemExit("-t is required")
    if out is None:
        raise SystemExit("--out is required")
    return src, openings, fallback, adapt, t, seed, out, progress


def main(argv):
    src, openings, fallback, adapt, t, seed, out, progress = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    ans2g = answer_to_guess(answers, guesses)
    pat = np.array(load_patterns())
    pos = {w: i for i, w in enumerate(guesses)}
    for o in openings:
        for w in o.split():
            if w not in pos:
                raise SystemExit("%r is not a legal guess" % w)
    sizes = {len(o.split()) for o in openings}
    if len(sizes) != 1:
        raise SystemExit("the openings are of different sizes: %s" % sorted(sizes))

    base = make_tail(fallback, guesses, answers, ans2g)
    tail = CoupledDraw(base)
    rules = [make_opening_rule([pos[w] for w in o.split()], tail=tail, adapt=adapt)
             for o in openings]
    n = len(openings)

    # pairwise accumulators: no per-game storage, so t can be as large as it likes
    ssum = np.zeros(n)
    ssq = np.zeros(n)
    dsum = np.zeros((n, n))
    dsq = np.zeros((n, n))
    answer_rng = np.random.default_rng(seed)

    print("paired compare: %d openings, %d games each, follow-up %s, "
          "pair-adaptive %d, seed %d" % (n, t, fallback, adapt, seed), flush=True)
    print("  answers AND the follow-up's coin flips are coupled across openings",
          flush=True)
    t0 = time.time()
    score = np.zeros(n)
    for g in range(t):
        a = draw_answer(len(answers), answer_rng)
        for k, rule in enumerate(rules):
            # the SAME stream for every opening in this game: that is the coupling
            rng = np.random.default_rng([seed, g])
            played, _ = _play(pat, ans2g, a, rule, tail, rng)
            score[k] = len(played)
        ssum += score
        ssq += score * score
        d = score[:, None] - score[None, :]
        dsum += d
        dsq += d * d
        if progress and (g + 1) % progress == 0:
            el = time.time() - t0
            print("  %d/%d games  %.0f/s  eta %.1f min"
                  % (g + 1, t, (g + 1) / el, (t - g - 1) / ((g + 1) / el) / 60),
                  flush=True)

    mean = ssum / t
    sd = np.sqrt(np.maximum(ssq / t - mean * mean, 0.0) * t / (t - 1))
    se = sd / np.sqrt(t)
    order = np.argsort(mean)

    dmean = dsum / t
    dsd = np.sqrt(np.maximum(dsq / t - dmean * dmean, 0.0) * t / (t - 1))
    dse = dsd / np.sqrt(t)

    lead = order[0]
    lines = []
    lines.append("paired comparison of %d openings, %d games, follow-up %s, "
                 "pair-adaptive %d, seed %d" % (n, t, fallback, adapt, seed))
    lines.append("leader %s, mean %.5f +/- %.5f (its own error)"
                 % (openings[lead], mean[lead], se[lead]))
    lines.append("")
    lines.append("%-24s %10s %9s %12s %9s %7s" %
                 ("opening", "mean", "own se", "vs leader", "paired se", "sigma"))
    for k in order:
        if k == lead:
            lines.append("%-24s %10.5f %9.5f %12s %9s %7s"
                         % (openings[k], mean[k], se[k], "-", "-", "-"))
            continue
        diff = dmean[k, lead]
        err = dse[k, lead]
        lines.append("%-24s %10.5f %9.5f %12.5f %9.5f %7.1f"
                     % (openings[k], mean[k], se[k], diff, err,
                        diff / err if err > 0 else float("inf")))
    # how much the pairing bought, measured rather than asserted
    naive = np.sqrt(se[order[1]] ** 2 + se[lead] ** 2)
    lines.append("")
    lines.append("pairing gain against the leader's nearest rival: unpaired error "
                 "%.5f, paired %.5f (%.1fx tighter)"
                 % (naive, dse[order[1], lead],
                    naive / dse[order[1], lead] if dse[order[1], lead] > 0 else float("inf")))

    print()
    for line in lines:
        print(line)
    print("\n%.1fs" % (time.time() - t0))

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for line in lines:
            f.write("# " + line + "\n")
        f.write("opening,mean,own_stderr,diff_vs_leader,paired_stderr,sigma\n")
        for k in order:
            f.write("%s,%.6f,%.6f,%.6f,%.6f,%.3f\n"
                    % (openings[k], mean[k], se[k], dmean[k, lead], dse[k, lead],
                       dmean[k, lead] / dse[k, lead] if dse[k, lead] > 0 else 0.0))
    print("wrote %s" % out)


def _play(pat, ans2g, answer_idx, rule, tail, rng):
    """play_game, with the coupled follow-up.  Kept here so wordlesim is untouched."""
    alive = np.ones(pat.shape[1], dtype=bool)
    played, replies = [], []
    while True:
        g = rule(turn=len(played), alive=alive, played=played, replies=replies,
                 rng=rng)
        if g is None:
            g = tail(turn=len(played), alive=alive, played=played,
                     replies=replies, rng=rng)
        g = int(g)
        row = pat[g]
        fb = int(row[answer_idx])
        played.append(g)
        replies.append(fb)
        if fb == ALL_GREEN:
            return played, replies
        alive &= row == fb


if __name__ == "__main__":
    main(sys.argv[1:])
