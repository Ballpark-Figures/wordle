"""Sweep OPENERS: the same fixed number of single-board games for every word.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-wordle-sweep.sh --fallback answer -t 100      # from math/
    bash solver/run-wordle-sweep.sh --fallback guess  -t 100

Every word of the list opens `-t` games, played out by the FOLLOW-UP named by
--fallback (math/wordlesim.py has the protocol; the rule is `opener`, which plays
that word on turn 0 and declines thereafter).  Each word gets a row with its mean
guesses AND its win rate, both with standard errors.

THE FOLLOW-UP IS PART OF THE QUESTION, not a detail: "which opener is best" has a
different answer under a random compatible ANSWER than under a random compatible
GUESS, because the opener is feeding a different player.  So it is required, it
is in the filename, and two sweeps that differ in it are two different screens.

COMMON RANDOM NUMBERS, and why a cell differs slightly from a standalone run.
Every opener faces the IDENTICAL sequence of `-t` answers: the draw stream is
re-seeded per word and kept SEPARATE from the stream the follow-up's random picks
consume, so one opener's picks cannot shift another's answers.  Each word's mean
is still an unbiased estimate of the same quantity, but the DIFFERENCE between
two words is far less noisy than their two standard errors suggest, because they
saw the same games.  tools/wordle_sim.py draws both from one stream, so a sweep
cell and a run-wordle-sim.sh run at the same seed are different samples and will
not match to the last digit.

THE WINNER'S CURSE IS REAL HERE, so read the head of the ranking carefully.  With
12972 words estimated at `-t` trials each, the best-looking mean is biased
optimistic: it belongs to whichever word got the kindest sample, and at small `-t`
the spread of pure noise across 12972 words is many times one word's standard
error.  **The head of a sweep is a SHORTLIST, not a winner.**  The sound use is
two-stage: sweep wide at small `-t` to screen, cut a generous shortlist
(tools/sweep_shortlist.py; the wrapper's default is 5 standard errors, measured
against the alternative -- 10 kept 95% of the field at t=100), then re-run the
survivors at larger `-t` and a FRESH SEED, repeating until the field is small
enough to separate.  A word that leads every stage is a finding; a word that leads only the
screen is a coin flip.

TWO NUMBERS MEANS TWO POSSIBLE SHORTLISTS.  The mean and the win rate are ranked
by different columns and need not agree, so the cut names which one it used
(--value on the shortlist tool) and that lands in the stage-2 filename.  Do not
cut on one and report the other.

ORDER.  Words are visited in the LIST'S OWN ORDER -- alphabetical for the word
lists, best-first for a shortlist -- so --limit takes a prefix of that, never a
sample.  Nothing about the order favours any word: every one gets the same trials
and the same games.

RESUMABLE.  One CSV row per word, flushed as it is finished, and a re-run skips
words already in the file -- so a Ctrl-C costs at most the word in flight.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402
from wordle_sim import summarise  # noqa: E402
from wordlesim import (WIN_WITHIN, answer_to_guess, draw_answer,  # noqa: E402
                       fixed_opener, make_tail, play_game)

COLUMNS = ("word,trials,mean,stderr,sd,min,median,max,"
           "win_rate,win_rate_stderr,wins,seconds")
# Offset for the pick stream so it cannot be the draw stream by another name.
PICK_OFFSET = 1 << 20


def parse_args(argv):
    t = None
    fallback = None
    seed = 0
    words = "guess"
    limit = None
    win_within = WIN_WITHIN
    out = None
    progress = 100          # --progress 1 prints a line per word
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--fallback":
            fallback = argv[i + 1]; i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--words":
            words = argv[i + 1]; i += 2
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 2
        elif a == "--win-within":
            win_within = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if t is None or t < 1:
        raise SystemExit("-t (trials per word) is required and must be >= 1")
    if not fallback:
        raise SystemExit(
            "--fallback is required: the opener feeds a different player under "
            "each follow-up, so it is part of the question.\n"
            "Use the wrapper: bash solver/run-wordle-sweep.sh --fallback answer -t 100")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-wordle-sweep.sh")
    return t, fallback, seed, words, limit, win_within, out, progress


def load_done(path):
    """Words already recorded in an existing CSV, so a re-run resumes."""
    done = set()
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("word,"):
                    continue
                w = line.split(",", 1)[0].strip()
                if w:
                    done.add(w)
    return done


def sweep_word(pat, ans2g, na, t, seed, opener_g, tail, win_within):
    """One word's t games, against the seed's fixed sequence of answer draws."""
    draw_rng = np.random.default_rng(seed)
    pick_rng = np.random.default_rng(seed + PICK_OFFSET)
    rule = fixed_opener(opener_g)
    scores = []
    for _ in range(t):
        answer_idx = draw_answer(na, draw_rng)
        played, _ = play_game(pat, ans2g, answer_idx, rule, tail, pick_rng)
        scores.append(len(played))
    return summarise(scores, win_within)


def main(argv):
    t, fallback, seed, words, limit, win_within, out, progress = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    if words in ("guess", "mystery"):
        sweep_words = load_words(words)
    else:
        with open(words) as f:
            sweep_words = [ln.strip() for ln in f if ln.strip()]
    pos = {w: i for i, w in enumerate(guesses)}
    bad = [w for w in sweep_words if w not in pos]
    if bad:
        raise SystemExit("%d swept words are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    tail = make_tail(fallback, guesses, answers, ans2g)
    na = len(answers)

    if limit is not None:
        sweep_words = sweep_words[:limit]
    done = load_done(out)
    todo = [w for w in sweep_words if w not in done]

    fh = None
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fresh = not os.path.exists(out)
        fh = open(out, "a")
        if fresh:
            fh.write("# wordle opener sweep: %d trials per word, follow-up %s, "
                     "seed %d\n" % (t, fallback, seed))
            fh.write("# strategy in math/wordlesim.py: the word is played on turn "
                     "0, the follow-up plays the rest\n")
            fh.write("# every word faces the SAME %d answers, drawn from the 2315 "
                     "mystery words (common random numbers)\n" % t)
            fh.write("# NO guess cap: win_rate is the fraction of untruncated "
                     "scores at %d guesses or fewer\n" % win_within)
            fh.write("# the head is a SHORTLIST, not a winner -- see the "
                     "winner's-curse note in tools/wordle_sweep.py\n")
            fh.write(COLUMNS + "\n")
        fh.flush()

    print("sweep: %d words x %d trials, follow-up %s, seed %d"
          % (len(todo), t, fallback, seed))
    if done:
        print("  resuming: %d words already in %s" % (len(done), out))

    t0 = time.time()
    best = []
    for i, w in enumerate(todo):
        w0 = time.time()
        st = sweep_word(pat, ans2g, na, t, seed, pos[w], tail, win_within)
        dt = time.time() - w0
        if fh:
            fh.write("%s,%d,%.6f,%.6f,%.6f,%d,%.1f,%d,%.6f,%.6f,%d,%.3f\n"
                     % (w, t, st["mean_guesses"], st["stderr"], st["sd"],
                        st["min"], st["median"], st["max"],
                        st["win_rate"], st["win_stderr"], st["wins"], dt))
            fh.flush()
        best.append((st["mean_guesses"], st["win_rate"], w))
        if progress and (i + 1) % progress == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            bm, bw, bword = min(best)
            print("  %d/%d  %-8s %.4f  %5.1f%%   best %s %.4f  %5.1f%%   "
                  "%.1f/s  eta %.1f min"
                  % (i + 1, len(todo), w, st["mean_guesses"],
                     100.0 * st["win_rate"], bword, bm, 100.0 * bw, rate,
                     (len(todo) - i - 1) / rate / 60))

    print("\n%d words in %.1fs" % (len(todo), time.time() - t0))
    if best:
        print("best %d by mean of the words swept THIS RUN (a shortlist, not a "
              "winner -- see the module docstring):" % min(20, len(best)))
        for mean, wr, w in sorted(best)[:20]:
            print("  %-8s mean %.4f   win %6.2f%%" % (w, mean, 100.0 * wr))
        print("best %d by win rate (a DIFFERENT ranking of the same games):"
              % min(20, len(best)))
        for mean, wr, w in sorted(best, key=lambda r: (-r[1], r[0]))[:20]:
            print("  %-8s win %6.2f%%   mean %.4f" % (w, 100.0 * wr, mean))
    if fh:
        fh.close()
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
