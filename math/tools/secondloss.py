"""Where the EV loss goes: the gap to optimal, split by the opener's grey count.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-second-loss.sh --opener spilt \\
        --second-from data/shared/secondword/second_guess_g3.csv

WHAT IT COMPUTES.  For one opener and one second-word table, every answer is
played `-n` times under the strategy, and its mean guess count is compared with
what that answer costs under the OPTIMAL tree for the SAME opener.  Answers are
then grouped by how many GREYS the opener's reply shows, and each group's share
of the total gap is reported.  The groups' contributions sum to the whole gap, so
this is a decomposition and not a set of unrelated numbers.

    contribution(g) = (answers with g greys / 2315) x (strategy mean - optimal mean)

TWO THINGS ABOUT "OPTIMAL", BOTH OF WHICH MATTER.

  * IT IS THE OPTIMUM FOR THE SAME OPENER, not the best opener.  That is the only
    comparison that decomposes: each grey bucket's gap is then attributable to how
    the strategy plays THAT bucket, with the choice of opener held fixed.  The
    opener's own cost is reported separately as a single number -- `spilt` is
    3.48121 against `salet`'s 3.42117 -- and it does not belong to any bucket.

  * IT IS THE CAPPED OPTIMUM: minimum total guesses SUBJECT TO resolving every
    answer within six, which is what optturns computed and what the committed
    trees are.  The strategy here is UNCAPPED -- play continues past six until the
    word is found.  A capped optimum is >= the unconstrained one, so every gap
    below is a LOWER BOUND on the loss against true optimal play.  Whether the cap
    binds for this opener is open (see the solver section of CLAUDE.md); nothing
    here settles it.

THE ESTIMATOR IS STRATIFIED, and that is why it is per ANSWER rather than a
uniform draw.  Every answer is played the same number of times, so the answer
weights are EXACT (each is 1/2315) and the only randomness left is the strategy's
own coin flips.  The reported standard error is therefore the error on those
flips alone -- the spread BETWEEN answers is the thing being decomposed, not
noise in it -- and it shrinks as `-n` grows even though the answer set never
changes.  A uniform-draw simulation would put sampling noise into the bucket
shares as well, which are exactly known.

THE GATE IS BUILT IN and always runs: the per-answer optimal costs must sum to
the total the committed CSV records for this opener, the tree must cover every
answer exactly once, the grey counts are recomputed FROM THE STRINGS, and the
bucket contributions must sum to the overall gap.  It exits nonzero rather than
reporting.
"""

import gzip
import os
import sys
import time
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from secondword import read_table, word_by_code  # noqa: E402
from wordle import load_words, pattern  # noqa: E402
from wordlesim import (answer_to_guess, make_opening_rule, make_tail,  # noqa: E402
                       play_game, second_rule_for)

COLUMNS = ("grays,answers,share,opt_mean,sim_mean,sim_stderr,gap,contribution,"
           "pct_of_gap,fires")


def parse_args(argv):
    a = {"opener": None, "second_from": "", "fallback": "answer", "n": 100,
         "seed": 0, "out": None, "progress": 500}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = int(v) if k in ("n", "seed", "progress") else v
        i += 2
    if not a["opener"]:
        raise SystemExit("--opener is required: the decomposition is for ONE "
                         "opener, against the optimal tree for that same opener")
    if a["fallback"] not in ("answer", "guess"):
        raise SystemExit("--fallback must be 'answer' or 'guess'")
    if a["n"] < 2:
        raise SystemExit("-n must be at least 2 (a standard error needs two)")
    if a["out"] is None:
        raise SystemExit(
            "--out is required (or --no-out to discard it deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-second-loss.sh")
    return a


def optimal_costs(opener, answers):
    """Per-answer guess counts under the committed OPTIMAL tree for this opener.

    A tree line is `<answer> <guesses> <opener> <pattern> <guess> ...`, one per
    answer.  Read the count rather than the line, and check the coverage: a tree
    missing an answer would silently shift every mean it is compared against.
    """
    path = os.path.join(paths.TREES, opener + ".txt.gz")
    if not os.path.exists(path):
        raise SystemExit(
            "no optimal tree for %r at %s\n"
            "The committed trees are one file per opener; if this one is "
            "missing, produce it with\n"
            "  ./solver/optturns --opener %s --trees <dir>   (from math/)"
            % (opener, path, opener))
    cost = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            if parts[0] in cost:
                raise SystemExit("%s lists the answer %s twice" % (path, parts[0]))
            cost[parts[0]] = int(parts[1])
            if parts[2] != opener:
                raise SystemExit("%s plays %s first, not %s"
                                 % (path, parts[2], opener))
    missing = [w for w in answers if w not in cost]
    if missing:
        raise SystemExit("%s covers %d of the %d answers (missing e.g. %s)"
                         % (path, len(cost), len(answers), missing[0]))
    extra = set(cost) - set(answers)
    if extra:
        raise SystemExit("%s lists %d words that are not answers, e.g. %s"
                         % (path, len(extra), sorted(extra)[0]))
    return cost


def committed_total(opener):
    """What the sweep recorded for this opener, or None if it is not on file."""
    path = paths.CSV_PATH
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            if line.startswith(opener + ","):
                parts = line.split(",")
                return int(parts[1]), float(parts[2])
    return None


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    na = len(answers)
    if a["opener"] not in guesses:
        raise SystemExit("%r is not one of the %d legal guesses"
                         % (a["opener"], len(guesses)))

    # --- the optimal side, exact
    cost = optimal_costs(a["opener"], answers)
    opt = np.array([cost[w] for w in answers], dtype=np.int64)
    total = int(opt.sum())
    rec = committed_total(a["opener"])
    if rec is not None and rec[0] != total:
        raise SystemExit("the tree for %s sums to %d guesses, but the sweep "
                         "recorded %d -- one of them is not this opener's"
                         % (a["opener"], total, rec[0]))

    # --- the buckets, recomputed FROM THE STRINGS so the key owes nothing to the
    # pattern matrix or to the encoding
    grays = np.array([_gray_count(a["opener"], w) for w in answers],
                     dtype=np.int8)

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    tail = make_tail(a["fallback"], guesses, answers, ans2g)
    gi = guesses.index(a["opener"])
    if a["second_from"]:
        table = read_table(a["second_from"])
        if a["opener"] not in table.rows:
            raise SystemExit("%s has no row for %r -- it was built over the %s "
                             "opener pool" % (a["second_from"], a["opener"],
                                              table.openers))
        rule = second_rule_for([gi], table, guesses)
        label = table.fire
        # ONCE, not per game: this is the rule's own lookup, and rebuilding it
        # inside the loop made the measurement cost more than the games did.
        by_code = word_by_code(table, a["opener"], guesses)
    else:
        rule = make_opening_rule([gi], tail=tail, adapt=0)
        label = "(none: the plain opener)"
        by_code = None

    print("EV loss vs optimal, by the opener's grey count")
    print("  opener     %s   (optimal total %d, expected %.5f, capped at 6)"
          % (a["opener"], total, total / na))
    print("  strategy   second word from %s, firing on %s"
          % (a["second_from"] or "(none)", label))
    print("  follow-up  %s;  %d games per answer x %d answers = %d games"
          % (a["fallback"], a["n"], na, a["n"] * na))

    # --- the strategy side, stratified: every answer played the same number of
    # times, so the answer weights are exact and the error is the coin flips'
    rng = np.random.default_rng(a["seed"])
    mean_a = np.zeros(na)
    var_a = np.zeros(na)
    fired_a = np.zeros(na)
    t0 = time.time()
    for ai in range(na):
        sc = np.empty(a["n"], dtype=np.int32)
        fired = 0
        for k in range(a["n"]):
            played, replies = play_game(pat, ans2g, ai, rule, tail, rng)
            sc[k] = len(played)
            if len(played) > 1 and by_code is not None:
                fired += int(by_code[replies[0]] == played[1])
        mean_a[ai] = sc.mean()
        var_a[ai] = sc.var(ddof=1)
        fired_a[ai] = fired / a["n"]
        if a["progress"] and (ai + 1) % a["progress"] == 0:
            print("  %d/%d answers  (%.0fs)" % (ai + 1, na, time.time() - t0))

    sim_mean = float(mean_a.mean())
    sim_se = float(np.sqrt(var_a.sum() / a["n"]) / na)
    opt_mean = total / na
    gap = sim_mean - opt_mean

    rows = []
    for g in range(6):
        sel = grays == g
        k = int(sel.sum())
        if not k:
            continue
        bm = float(mean_a[sel].mean())
        bse = float(np.sqrt(var_a[sel].sum() / a["n"]) / k)
        om = float(opt[sel].mean())
        rows.append(dict(grays=g, answers=k, share=k / na, opt=om, sim=bm,
                         se=bse, gap=bm - om, contrib=(k / na) * (bm - om),
                         fires=float(fired_a[sel].mean())))

    # --- the built-in gate: the parts must be the whole
    csum = sum(r["contrib"] for r in rows)
    if abs(csum - gap) > 1e-9:
        raise SystemExit("the bucket contributions sum to %.12f but the gap is "
                         "%.12f -- the decomposition is not one" % (csum, gap))
    if abs(sum(r["share"] for r in rows) - 1.0) > 1e-12:
        raise SystemExit("the bucket shares do not sum to 1")
    if abs(sum(r["share"] * r["opt"] for r in rows) - opt_mean) > 1e-9:
        raise SystemExit("the bucket optimal means do not average to the total")
    for w, g in zip(answers[:200], grays[:200]):
        if int(g) != sum(1 for t in _tiles(a["opener"], w) if t == 0):
            raise SystemExit("the grey count for %s was not computed from the "
                             "strings" % w)

    print()
    print("  optimal (same opener, capped)  %.5f" % opt_mean)
    print("  strategy                       %.5f +/- %.5f" % (sim_mean, sim_se))
    print("  gap                            %.5f" % gap)
    print()
    print("  %5s %8s %8s %9s %9s %9s %9s %9s %7s"
          % ("grays", "answers", "share", "optimal", "strategy", "gap",
             "contrib", "% of gap", "fires"))
    for r in rows:
        print("  %5d %8d %7.1f%% %9.4f %9.4f %9.4f %9.5f %8.1f%% %6.0f%%"
              % (r["grays"], r["answers"], 100 * r["share"], r["opt"], r["sim"],
                 r["gap"], r["contrib"], 100 * r["contrib"] / gap if gap else 0,
                 100 * r["fires"]))

    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        with open(a["out"], "w") as f:
            f.write("# EV loss vs optimal for the opener %s, by the opener's "
                    "grey count\n" % a["opener"])
            f.write("# strategy: second word from %s firing on %s, follow-up "
                    "%s\n" % (a["second_from"] or "(none)", label, a["fallback"]))
            f.write("# %d games per answer x %d answers, seed %d; the answer "
                    "weights are EXACT\n" % (a["n"], na, a["seed"]))
            f.write("# optimal is the CAPPED optimum for the SAME opener "
                    "(total %d, %.5f per answer): minimum\n# guesses subject to "
                    "solving every answer within six.  The strategy is "
                    "UNCAPPED, so every\n# gap here is a LOWER BOUND on the loss "
                    "against unconstrained optimal play.\n" % (total, opt_mean))
            f.write("# strategy %.6f +/- %.6f, gap %.6f; the contributions sum "
                    "to it\n" % (sim_mean, sim_se, gap))
            f.write(COLUMNS + "\n")
            for r in rows:
                f.write("%d,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.4f,%.6f\n"
                        % (r["grays"], r["answers"], r["share"], r["opt"],
                           r["sim"], r["se"], r["gap"], r["contrib"],
                           100 * r["contrib"] / gap if gap else 0, r["fires"]))
        print("\nwrote %s" % a["out"])


def _tiles(guess, answer):
    """The reply as tiles, from the STRINGS, by the multiset rule."""
    tiles = [2 if g == x else 0 for g, x in zip(guess, answer)]
    left = Counter(x for g, x in zip(guess, answer) if g != x)
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g] > 0:
            tiles[i] = 1
            left[g] -= 1
    return tiles


def _gray_count(guess, answer):
    return sum(1 for t in _tiles(guess, answer) if t == 0)


if __name__ == "__main__":
    main(sys.argv[1:])
