"""Sweep OPENERS: the same fixed number of multiwordle trials for each word.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-multiwordle-sweep.sh -k 4 -t 1000            # from math/
    bash solver/run-multiwordle-sweep.sh -k 4 -t 1000 --words mystery
    bash solver/run-multiwordle-sweep.sh -k 4 -t 200 --prefix clint   # sweep word 2

Every word of the list opens `-t` games at `-k` boards under the strategy in
math/multiwordle.py, and the run reports each word's mean total guesses.  This is
the multiwordle analogue of an opener sweep: it asks which opener does best AT
THIS GAME, rather than borrowing a ranking computed for one board.

COMMON RANDOM NUMBERS, and why the numbers differ slightly from a single run.
Every opener faces the IDENTICAL sequence of `-t` answer draws: the draw stream
is re-seeded per opener and kept SEPARATE from the stream the strategy's random
candidate picks consume, so one opener's picks cannot shift another's answers.
Each word's mean is still an unbiased estimate of the same quantity, but the
DIFFERENCE between two words is far less noisy than their two standard errors
suggest, because the two saw the same games.  tools/multiwordle_sim.py draws both
from one stream, so a sweep cell and a standalone run at the same seed are two
different samples and will not match to the last digit.

THE WINNER'S CURSE IS REAL HERE, so read the head of the ranking carefully.  With
12972 words estimated at `-t` trials each, the best-looking mean is biased
optimistic: it belongs to whichever word got the kindest sample, and at small `-t`
the spread of pure noise across 12972 words is many times one word's standard
error.  **The head of a sweep is a SHORTLIST, not a winner.**  The sound use is
two-stage: sweep wide at small `-t` to screen, then re-run the top few at large
`-t` (or a fresh seed) and compare those.  A word that leads both is a finding; a
word that leads only the screen is a coin flip.

ORDER.  Words are visited in the LIST'S OWN ORDER -- alphabetical for the word
lists, best-first for a shortlist cut by tools/multiwordle_shortlist.py -- so
--limit takes a prefix of that, never a sample.  Nothing about the order favours
any word: every one gets the same trials and the same games.

RESUMABLE.  One CSV row per word, flushed as it is finished, and a re-run skips
words already in the file -- so a Ctrl-C costs at most the word in flight.

--prefix fixes the opening words that come BEFORE the swept one, so a sweep can
ask "given clint, which second word is best" rather than only "which first word".
The swept word is appended to the prefix and the whole opening is played blind.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns  # noqa: E402
from multiwordle import answer_to_guess, draw_answers, play_game  # noqa: E402
from multiwordle_sim import summarise  # noqa: E402
from wordle import load_words  # noqa: E402

COLUMNS = "word,trials,mean,stderr,sd,min,median,max,seconds"
# Offset for the pick stream so it cannot be the draw stream by another name.
PICK_OFFSET = 1 << 20


def parse_args(argv):
    k = t = None
    seed = 0
    words = "guess"
    prefix = []
    limit = None
    out = None
    progress = 100          # --progress 1 prints a line per word
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-k", "--boards"):
            k = int(argv[i + 1]); i += 2
        elif a in ("-t", "--trials"):
            t = int(argv[i + 1]); i += 2
        elif a == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif a == "--words":
            words = argv[i + 1]; i += 2
        elif a == "--prefix":
            prefix.extend(argv[i + 1].split()); i += 2
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--progress":
            progress = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown argument: %s" % a)
    if k is None or k < 1:
        raise SystemExit("-k (number of boards) is required and must be >= 1")
    if t is None or t < 1:
        raise SystemExit("-t (trials PER WORD) is required and must be >= 1")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper: bash solver/run-multiwordle-sweep.sh")
    return k, t, seed, words, prefix, limit, out, progress


def load_done(path):
    """Words already swept in a previous run of the same file."""
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


def sweep_word(pat, ans2g, na, k, t, seed, openers_g):
    """One word's t games, against the seed's fixed sequence of answer draws."""
    draw_rng = np.random.default_rng(seed)
    pick_rng = np.random.default_rng(seed + PICK_OFFSET)
    scores = []
    for _ in range(t):
        answer_idx = draw_answers(na, k, draw_rng)
        scores.append(len(play_game(pat, ans2g, answer_idx, openers_g, pick_rng)))
    return summarise(scores, k)


def main(argv):
    k, t, seed, words, prefix, limit, out, progress = parse_args(argv)

    guesses = load_words("guess")
    answers = load_words("mystery")
    if words in ("guess", "mystery"):
        sweep_words = load_words(words)
    else:
        with open(words) as f:
            sweep_words = [ln.strip() for ln in f if ln.strip()]
    for w in prefix:
        if w not in guesses:
            raise SystemExit("prefix word %r is not in the guess list" % w)
    bad = [w for w in sweep_words if w not in guesses]
    if bad:
        raise SystemExit("%d swept words are not legal guesses, e.g. %s"
                         % (len(bad), " ".join(bad[:5])))
    if k > len(answers):
        raise SystemExit("k=%d exceeds the %d answer words" % (k, len(answers)))

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    na = len(answers)
    prefix_g = [guesses.index(w) for w in prefix]

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
            fh.write("# multiwordle opener sweep: %d trials per word at k=%d, "
                     "seed %d\n" % (t, k, seed))
            fh.write("# strategy in math/multiwordle.py; every word faces the "
                     "SAME %d answer draws\n" % t)
            if prefix:
                fh.write("# opening is '%s' plus the swept word, played blind\n"
                         % " ".join(prefix))
            fh.write("# the head is a SHORTLIST, not a winner -- see the "
                     "winner's-curse note in tools/multiwordle_sweep.py\n")
            fh.write(COLUMNS + "\n")
        fh.flush()

    print("sweep: %d words x %d trials at k=%d, seed %d%s"
          % (len(todo), t, k, seed,
             ("  (opening prefix: %s)" % " ".join(prefix)) if prefix else ""))
    if done:
        print("  resuming: %d words already in %s" % (len(done), out))

    t0 = time.time()
    best = []
    for i, w in enumerate(todo):
        w0 = time.time()
        st = sweep_word(pat, ans2g, na, k, t, seed, prefix_g + [guesses.index(w)])
        dt = time.time() - w0
        if fh:
            fh.write("%s,%d,%.6f,%.6f,%.6f,%d,%.1f,%d,%.3f\n"
                     % (w, t, st["mean_guesses"], st["stderr"], st["sd"],
                        st["min"], st["median"], st["max"], dt))
            fh.flush()
        best.append((st["mean_guesses"], w))
        if progress and (i + 1) % progress == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            # Name the word this tick finished, so --progress 1 is a per-word
            # printout rather than a bare counter.
            print("  %d/%d  %-8s %.4f   best %s %.4f   %.1f/s  eta %.1f min"
                  % (i + 1, len(todo), w, st["mean_guesses"],
                     min(best)[1], min(best)[0], rate,
                     (len(todo) - i - 1) / rate / 60))

    print("\n%d words in %.1fs" % (len(todo), time.time() - t0))
    if best:
        print("best %d of the words swept THIS RUN (a shortlist, not a winner "
              "-- see the module docstring):" % min(20, len(best)))
        for mean, w in sorted(best)[:20]:
            print("  %-8s %.4f" % (w, mean))
    if fh:
        fh.close()
        print("wrote %s" % out)


if __name__ == "__main__":
    main(sys.argv[1:])
