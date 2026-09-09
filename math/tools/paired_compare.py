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
import re
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


def next_t(t):
    """The next rung of the 1-2-3-5 ladder above `t` -- the sweeps' own ladder."""
    d = 100
    while d <= 10 ** 12:
        for m in (1, 2, 3, 5):
            if m * d > t:
                return m * d
        d *= 10
    return t * 10


def read_sweep_settings(path):
    """A sweep CSV's own account of itself: openings, follow-up, adapt, t, seed.

    The `# settings` line is authoritative where it exists.  Older files predate
    it, so the follow-up/trials/seed fall back to the first line and `adapt` to
    the prose ("ABANDONED once the follow-up is down to N or fewer words"), which
    is the only place it was recorded.  Parsing prose is a fallback, never the
    plan -- hence the settings line.
    """
    head, rows, sigma, header = [], [], {}, None
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                head.append(line.rstrip("\n"))
                continue
            cols = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None and cols[0] == "word":
                header = cols
                continue
            if not cols[0]:
                continue
            rows.append(cols[0])
            # a PAIRED source carries how many paired sigma each opening sits
            # behind the leader; that, not the unpaired stderr in the same file,
            # is what a cut here has to mean
            if header and "sigma" in header:
                try:
                    sigma[cols[0]] = float(cols[header.index("sigma")])
                except (ValueError, IndexError):
                    pass
    blob = "\n".join(head)
    out = {"openings": rows}
    r = re.search(r"# settings .*rank=(\w+)", blob)
    out["rank"] = r.group(1) if r else "mean"
    m = re.search(r"# settings follow_up=(\w+) pair_adaptive=(\d+) "
                  r"win_within=(\d+) trials=(\d+) seed=(\d+)", blob)
    if m:
        out.update(fallback=m.group(1), adapt=int(m.group(2)),
                   win_within=int(m.group(3)), trials=int(m.group(4)),
                   seed=int(m.group(5)))
    else:
        m = re.search(r"# wordle opener sweep: (\d+) trials per word, "
                      r"follow-up (\w+), seed (\d+)", blob)
        if not m:
            # a PAIRED file written before the settings line existed states the
            # same facts in its own first line
            pm = re.search(r"# paired comparison of \d+ openings, (\d+) games, "
                           r"follow-up (\w+), pair-adaptive (\d+), seed (\d+)",
                           blob)
            if pm:
                out.update(trials=int(pm.group(1)), fallback=pm.group(2),
                           adapt=int(pm.group(3)), seed=int(pm.group(4)),
                           win_within=6)
                m = None
            else:
                raise SystemExit("%s does not look like a sweep or paired CSV"
                                 % path)
        if m:
            out.update(trials=int(m.group(1)), fallback=m.group(2),
                       seed=int(m.group(3)), win_within=6)
            a = re.search(r"ABANDONED once the follow-up is down to (\d+)", blob)
            out["adapt"] = int(a.group(1)) if a else 0
    m = re.search(r"# lineage root=(\S+) pass=(\d+)", blob)
    if not m:
        # a paired file written before the lineage line states the same thing in
        # its prose: "... taken from <file> (root <root>, pass <n>)"
        m = re.search(r"\(root (\S+), pass (\d+)\)", blob)
    out["root"] = m.group(1) if m else "unknown"
    out["pass"] = int(m.group(2)) if m else 0
    if not rows:
        raise SystemExit("%s has no openings" % path)
    out["sigma"] = sigma
    m = re.search(r"# lineage .*round=(\d+)", blob)
    out["round"] = int(m.group(1)) if m else 0
    return out


def parse_args(argv):
    src = sweep = out = None
    fallback = None
    adapt = None
    t = None
    seed = None
    top = None
    rank = None
    sigma_cut = 5.0
    max_openings = 50
    openings = []
    progress = 20000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--from-sweep":
            sweep = argv[i + 1]; i += 2
        elif a == "--top":
            top = int(argv[i + 1]); i += 2
        elif a == "--max-openings":
            max_openings = int(argv[i + 1]); i += 2
        elif a == "--rank":
            rank = argv[i + 1]; i += 2
        elif a == "--sigma":
            sigma_cut = float(argv[i + 1]); i += 2
        elif a == "--print-stem":
            out = "--print-stem"; i += 1
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
    meta = None
    if sweep:
        meta = read_sweep_settings(sweep)
        openings.extend(meta["openings"])
        # the sweep's OWN settings are the defaults: comparing finalists under a
        # different strategy from the one that selected them would be a different
        # experiment wearing the same filename.
        if fallback is None:
            fallback = meta["fallback"]
        if adapt is None:
            adapt = meta["adapt"]
        if rank is None:
            # the ranking belongs to the CASCADE, not to one command
            rank = meta.get("rank", "mean")
        if meta["sigma"]:
            # CHAINING a paired round: cut on the PAIRED sigma.  Everything within
            # --sigma of the leader survives; the leader's own row carries no
            # sigma and always does.
            keep = [w for w in openings if meta["sigma"].get(w, 0.0) <= sigma_cut]
            # stderr, not stdout: --print-stem's output is READ by the wrapper,
            # and a stray line on stdout became the filename.
            print("cut at %g paired sigma: %d of %d openings kept"
                  % (sigma_cut, len(keep), len(openings)), file=sys.stderr)
            openings = keep
            if t is None:
                t = next_t(meta["trials"])   # and more games each round
        if t is None:
            t = meta["trials"]
        if seed is None:
            # a FRESH seed by default: the finalists were chosen by the source's
            # own games, so re-using its seed would judge them on that sample
            seed = meta["seed"] + 1
    if adapt is None:
        adapt = 0
    if rank is None:
        rank = "mean"
    if rank not in ("mean", "win_rate"):
        raise SystemExit("--rank must be 'mean' or 'win_rate'")
    if seed is None:
        seed = 100
    if top is not None:
        openings = openings[:top]
    if len(openings) < 2:
        raise SystemExit("give at least two openings "
                         "(--from-sweep CSV, --from FILE or --opening)")
    if len(openings) > max_openings:
        raise SystemExit(
            "%d openings is more than --max-openings %d: this compares FINALISTS, "
            "and every pair costs a column.\nCut it with --top N, or raise the "
            "limit deliberately." % (len(openings), max_openings))
    if fallback not in ("answer", "guess"):
        raise SystemExit("--fallback answer|guess is required")
    if t is None or t < 1:
        raise SystemExit("-t is required")
    if out is None:
        raise SystemExit("--out is required")
    if out == "--print-stem":
        # The wrapper asks HERE what the file should be called, so the derivation
        # lives in one place rather than being re-implemented in shell.
        root = meta["root"] if meta else "openings"
        rnd = (meta["round"] + 1) if meta else 1
        stem = "paired_%s_%s_p%d_r%d_t%d_s%d" % (
            fallback, root, meta["pass"] if meta else 0, rnd, t, seed)
        if adapt:
            stem += "_adapt%d" % adapt
        if rank != "mean":
            stem += "_win"
        print(stem)
        print(len(openings))
        raise SystemExit(0)
    return (sweep or src, openings, fallback, adapt, t, seed, out, progress,
            meta, sigma_cut, rank)


def main(argv):
    (src, openings, fallback, adapt, t, seed, out, progress, meta,
     sigma_cut, rank) = parse_args(argv)

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
    win_within = meta.get("win_within", 6) if meta else 6
    for g in range(t):
        a = draw_answer(len(answers), answer_rng)
        for k, rule in enumerate(rules):
            # the SAME stream for every opening in this game: that is the coupling
            rng = np.random.default_rng([seed, g])
            played, _ = _play(pat, ans2g, a, rule, tail, rng)
            # THE SCORE IS WHATEVER IS BEING RANKED.  Under win_rate it is the
            # 0/1 indicator, so the paired difference is a per-game win/lose
            # difference -- which never has the proportion's zero-error problem,
            # because its error comes from how often the two DISAGREE.
            score[k] = (len(played) <= win_within if rank == "win_rate"
                        else len(played))
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
    order = np.argsort(-mean if rank == "win_rate" else mean)

    dmean = dsum / t
    dsd = np.sqrt(np.maximum(dsq / t - dmean * dmean, 0.0) * t / (t - 1))
    dse = dsd / np.sqrt(t)

    lead = order[0]
    lines = []
    lines.append("paired comparison of %d openings, %d games, follow-up %s, "
                 "pair-adaptive %d, seed %d, ranked on %s"
                 % (n, t, fallback, adapt, seed,
                    "WIN RATE" if rank == "win_rate" else "mean guesses"))
    if meta:
        lines.append("settings and finalists taken from %s (root %s, pass %d)"
                     % (os.path.basename(src), meta["root"], meta["pass"]))
    lines.append("leader %s, %s %.5f +/- %.5f (its own error)"
                 % (openings[lead], "win rate" if rank == "win_rate" else "mean",
                    mean[lead], se[lead]))
    lines.append("")
    lines.append("%-24s %10s %9s %12s %9s %7s" %
                 ("opening", "win rate" if rank == "win_rate" else "mean",
                  "own se", "vs leader", "paired se", "sigma"))
    for k in order:
        if k == lead:
            lines.append("%-24s %10.5f %9.5f %12s %9s %7s"
                         % (openings[k], mean[k], se[k], "-", "-", "-"))
            continue
        # always "how much WORSE than the leader", whichever way better points
        diff = (dmean[lead, k] if rank == "win_rate" else dmean[k, lead])
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
    rnd = (meta["round"] + 1) if meta else 1
    with open(out, "w") as f:
        for line in lines:
            f.write("# " + line + "\n")
        # the same machine-readable lines a sweep writes, so THIS file can be the
        # source of the next round: settings, lineage, and which round it is
        f.write("# settings follow_up=%s pair_adaptive=%d win_within=6 "
                "trials=%d seed=%d words=%d rank=%s\n"
                % (fallback, adapt, t, seed, n, rank))
        f.write("# lineage root=%s pass=%d round=%d source=%s\n"
                % (meta["root"] if meta else "openings",
                   meta["pass"] if meta else 0, rnd,
                   os.path.basename(src) if src else "(none)"))
        # THE SAME LEADING COLUMNS AS A SWEEP -- word, trials, mean, stderr -- so
        # tools/sweep_shortlist.py and every reader of a sweep CSV can read this
        # file too.  The paired columns follow; they are the point, but they do
        # not get in the way of the format everything else already speaks.
        # NAME THE VALUE COLUMN FOR WHAT IT IS.  It used to be `mean` whatever was
        # being ranked, so a win-rate paired file carried a win rate in a column
        # called `mean` and every reader asking for `win_rate` failed on it.  The
        # header's `rank=` said so, but a column name that lies is worse than one
        # that is merely terse.
        vcol = "mean" if rank == "mean" else rank
        ecol = "stderr" if rank == "mean" else rank + "_stderr"
        f.write("word,trials,%s,%s,diff_vs_leader,paired_stderr,sigma\n"
                % (vcol, ecol))
        for k in order:
            f.write("%s,%d,%.6f,%.6f,%.6f,%.6f,%.3f\n"
                    % (openings[k], t, mean[k], se[k],
                       dmean[lead, k] if rank == "win_rate" else dmean[k, lead],
                       dse[k, lead],
                       abs(dmean[k, lead]) / dse[k, lead] if dse[k, lead] > 0 else 0.0))
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
