"""Simulate single-board Wordle games under one named strategy.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-wordle-sim.sh --strategy random -t 10000        # from math/, or anywhere
    bash solver/run-wordle-sim.sh --strategy random -t 10000 --seed 7

WHAT THIS MEASURES, precisely: the EXPECTED NUMBER OF GUESSES to find the hidden
word, over uniform random draws of the answer AND over the strategy's own coin
flips, together with the WIN RATE -- the fraction of those games that finished
within six guesses.  Play is NEVER truncated: a game that has not found the word
by guess six keeps going until it does, so the mean is an unconstrained
expected-guess count and the win rate is read off the same untruncated scores.
The game, the strategy protocol and the reason no cap is needed are all written
out in math/wordlesim.py -- read that first; this file is the trial loop.

IT IS A MONTE CARLO ESTIMATE, so both headline numbers come with a standard
error and the summary always prints one (the win rate's is the binomial
sqrt(p(1-p)/t)).  Two runs differing by less than a couple of SEs have not
measured a difference.  Everything is reproducible from (strategy, t, seed),
which is why all three are in the output filename: a re-run of the same three
reproduces the file exactly, and a different seed is a different sample that
gets its own file rather than being appended to an existing one.

Rows are flushed as they are played, so a Ctrl-C keeps every game finished so
far; the trailing `#` summary lines are written only on a clean finish.

THE STRATEGY IS REQUIRED AND NEVER DEFAULTED -- it is the parameter that defines
the experiment, and a defaulted one would make every result file ambiguous about
which strategy produced it.  --strategy-arg passes an argument through to a
strategy that takes one; the two baselines take none.

SO IS THE FOLLOW-UP.  A strategy is a RULE plus the FOLLOW-UP that fills in
wherever the rule declines (math/wordlesim.py has the protocol), and the two
follow-ups -- a random compatible ANSWER or a random compatible GUESS -- are
different strategies with different numbers.  --fallback names it.  The two
baselines pin their own by name (`random` is the answer follow-up with no rule,
`random-guess` the guess one), so they take no --fallback; every other strategy
requires it, and it is recorded in the header and in the filename.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402
from wordlesim import (WIN_WITHIN, answer_to_guess, draw_answer,  # noqa: E402
                       make_strategy, make_tail, play_game)

COLUMNS = "game,guesses,won,answer,sequence"


def parse_args(argv):
    strategy = None
    fallback = None
    adapt = 0
    sargs = []
    t = None
    seed = 0
    win_within = WIN_WITHIN
    resolve = False
    out = None
    progress = 1000
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-s", "--strategy"):
            strategy = argv[i + 1]; i += 2
        elif a == "--pair-adaptive":
            adapt = int(argv[i + 1]); i += 2
        elif a == "--fallback":
            fallback = argv[i + 1]; i += 2
        elif a == "--strategy-arg":
            sargs.append(argv[i + 1]); i += 2
        elif a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--win-within":
            win_within = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--resolve":
            resolve = True; i += 1
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if not strategy:
        # The strategy IS the experiment, so it is never defaulted.
        raise SystemExit(
            "--strategy is required: it is the parameter that defines the run.\n"
            "Use the wrapper: bash solver/run-wordle-sim.sh --strategy random -t 10000")
    if resolve:
        # A dry run of the strategy resolution alone: no trials, no output.  The
        # wrapper calls this BEFORE it creates a log or a CSV, so a strategy that
        # will be refused is refused before it leaves anything behind -- and the
        # refusal still comes from the registry, the one place that owns it.
        return strategy, fallback, sargs, 0, seed, win_within, "--resolve", progress
    if t is None or t < 1:
        raise SystemExit("-t (number of trials) is required and must be >= 1")
    if win_within < 1:
        raise SystemExit("--win-within must be >= 1")
    if out is None:
        # The strturns lesson: a run that prints its answer and saves nothing is
        # a run lost.  Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-wordle-sim.sh")
    return strategy, fallback, adapt, sargs, t, seed, win_within, out, progress


def summarise(scores, win_within):
    """Mean guesses and win rate, each with its Monte Carlo standard error."""
    s = np.asarray(scores, dtype=np.float64)
    n = len(s)
    mean = s.mean()
    sd = s.std(ddof=1) if n > 1 else 0.0
    wins = int((s <= win_within).sum())
    p = wins / n
    return {
        "trials": n,
        "mean_guesses": mean,
        "stderr": sd / np.sqrt(n) if n > 1 else 0.0,
        "sd": sd,
        "min": int(s.min()),
        "median": float(np.median(s)),
        "max": int(s.max()),
        "win_within": win_within,
        "wins": wins,
        "win_rate": p,
        "win_stderr": np.sqrt(p * (1.0 - p) / n) if n > 1 else 0.0,
    }


def main(argv):
    (strategy_name, fallback, adapt, sargs, t, seed, win_within, out,
     progress) = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    ans2g = answer_to_guess(answers, guesses)
    # resolved first, and before anything heavy is loaded, so --resolve is cheap
    # The follow-up is built FIRST when the rule is adaptive: the rule asks it how
    # many words it would be choosing between, so it cannot exist without it.
    rule, tail_name = make_strategy(strategy_name, guesses, answers, ans2g,
                                    sargs, fallback)
    if out == "--resolve":
        print(tail_name)
        return
    pat = np.array(load_patterns())          # 12972 x 2315, ~30 MB, wants RAM
    tail = make_tail(tail_name, guesses, answers, ans2g)
    if adapt:
        rule, tail_name = make_strategy(strategy_name, guesses, answers, ans2g,
                                        sargs, fallback, tail=tail, adapt=adapt)
    rng = np.random.default_rng(seed)

    label = " ".join([strategy_name] + list(sargs))
    if adapt:
        label += " (pair-adaptive %d)" % adapt
    fh = None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fh = open(out, "w")
        fh.write("# wordle single-board simulation (see math/wordlesim.py)\n")
        fh.write("# strategy=%s follow_up=%s trials=%d seed=%d win_within=%d\n"
                 % (label, tail_name, t, seed, win_within))
        fh.write("# the follow-up fills in wherever the rule declines; it draws a "
                 "random word still\n# consistent with every reply, from the %s "
                 "list\n"
                 % ("2315 mystery" if tail_name == "answer" else "12972 legal guess"))
        fh.write("# answers drawn uniformly from the 2315 mystery words; guesses "
                 "from the 12972 legal words\n")
        fh.write("# NO guess cap: play continues past %d until the word is found, "
                 "so the mean is unconstrained\n" % win_within)
        fh.write("# and the win rate is the fraction of those untruncated scores "
                 "that came in at %d or fewer\n" % win_within)
        fh.write(COLUMNS + "\n")

    print("wordle sim: strategy=%s  follow-up=%s  trials=%d  seed=%d  win within %d"
          % (label, tail_name, t, seed, win_within))
    scores = []
    t0 = time.time()
    for game in range(t):
        answer_idx = draw_answer(len(answers), rng)
        played, _ = play_game(pat, ans2g, answer_idx, rule, tail, rng)
        scores.append(len(played))
        if fh:
            fh.write("%d,%d,%d,%s,%s\n" % (
                game, len(played), int(len(played) <= win_within),
                answers[answer_idx], " ".join(guesses[g] for g in played)))
            fh.flush()
        if progress and (game + 1) % progress == 0:
            done = np.asarray(scores)
            print("  %d/%d games  mean %.4f  win %.2f%%  (%.1fs)"
                  % (game + 1, t, done.mean(),
                     100.0 * (done <= win_within).mean(), time.time() - t0))

    st = summarise(scores, win_within)
    lines = [
        "strategy %s, follow-up %s, trials %d, seed %d"
        % (label, tail_name, t, seed),
        "mean guesses %.4f  +/- %.4f (standard error)"
        % (st["mean_guesses"], st["stderr"]),
        "win rate (within %d) %.4f%%  +/- %.4f%%  (%d of %d games)"
        % (win_within, 100.0 * st["win_rate"], 100.0 * st["win_stderr"],
           st["wins"], st["trials"]),
        "sd %.4f   min %d   median %.1f   max %d"
        % (st["sd"], st["min"], st["median"], st["max"]),
    ]
    counts = np.bincount(np.asarray(scores))
    dist = ["  %3d guesses  %6d  %6.2f%%%s" % (v, c, 100.0 * c / t,
                                               "" if v <= win_within else "   (loss)")
            for v, c in enumerate(counts) if c]

    print()
    for line in lines:
        print(line)
    print("distribution of guesses:")
    for line in dist:
        print(line)
    print("\n%.1fs" % (time.time() - t0))

    if fh:
        for line in lines:
            fh.write("# " + line + "\n")
        for line in dist:
            fh.write("#" + line + "\n")
        fh.close()
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
