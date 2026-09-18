"""Random restarts, each climbed by one-word swaps.  math/hillclimb.py states
the rule and IS the source of truth.

    bash solver/run-hill-climb.sh -t 100

Every accepted swap prints, because that is the only thing that happens: the
neighbourhood scan between two swaps is seconds of silence, and a trial is a
handful of swaps.

A GATE RUNS ON EVERY TRIAL, and both halves are free:

  * the climb must END at a local optimum -- the scan that stopped it is
    re-checked, so a bug that stopped early would have to also lie about the
    neighbourhood;
  * the reported unsolved must equal `guarantee_sweep.check_opening`'s losing
    count for the same opening, which is a different implementation reached by a
    different route (0.06 s, so it costs nothing per trial).
"""

import os
import queue as _queue
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from multiprocessing import Manager

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                                  # noqa: E402
from greedybuild import score                                             # noqa: E402
from guarantee_sweep import check_opening                                 # noqa: E402
from hillclimb import (anagram_index, climb, climb_pairs,              # noqa: E402
                       letter_counts, neighbourhood)
from opening_list import resolve_word_set                                 # noqa: E402
from paircover import cand_matrix, pool_matrix                            # noqa: E402
from wordle import load_words, to_codes                                   # noqa: E402

COLUMNS = "trial,opening,unsolved,ssq,steps,secs"
# `steps` is a per-SECTION breakdown ("swap 6, anagram 1, anagram+1 0"),
# not one number: which neighbourhood actually moved is the thing worth
# knowing when deciding whether a section earns its time.


def parse_args(argv):
    a = {"pool": None, "candidates": None, "words": 4, "trials": None,
         "cap": 6, "seed": 0, "out": None, "workers": 1}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k == "t":
            k = "trials"
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = (int(v) if k in ("words", "trials", "cap", "seed", "workers")
                else v)
        i += 2
    for req in ("pool", "trials"):
        if a[req] is None:
            raise SystemExit("--%s is required" % req)
    if a["out"] is None:
        raise SystemExit("--out is required (or --no-out).  Use the wrapper: "
                         "bash solver/run-hill-climb.sh")
    if a["cap"] - a["words"] < 1:
        raise SystemExit("--cap %d leaves no guesses after %d words"
                         % (a["cap"], a["words"]))
    return a



# ---------------------------------------------------------------------------
# TRIALS ARE INDEPENDENT, so this parallelises by running whole trials at once.
#
# EVERY TRIAL IS SEEDED BY ITS OWN INDEX (`seed + trial`), so the RESULT of a
# run does not depend on `--workers` at all -- only the order lines appear in.
# That is what makes the parallel path checkable against the serial one rather
# than merely faster, and the gate does exactly that.
#
# SPAWN, NOT FORK.  macOS defaults to spawn and forking a numpy process there is
# the kind of thing that works until it does not, so each worker builds its own
# state once in the initializer.  The square matrix is 168 MB per worker; the
# alternative (mmap shared through the page cache) saves that but changes the
# access pattern of the SERIAL path too, and a correctness-preserving change
# should not quietly re-tune the thing it is not about.
# ---------------------------------------------------------------------------
_W = {}


def _init(pool_name, cand_name, words, cap, q):
    guesses, answers = load_words("guess"), load_words("mystery")
    pool = sorted(resolve_word_set(pool_name))
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(pool)}
    cands = pool if cand_name is None else sorted(resolve_word_set(cand_name))
    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    ans = np.array([ppos[w] for w in answers])
    M = (pool_matrix(full, cols) if cands == pool else
         cand_matrix(full, np.array([gpos[w] for w in cands]), cols))
    C = letter_counts(cands)
    _W.update(full=full, cols=cols, ans=ans, M=M, cands=cands, words=words,
              q=q, C=C, by_sig=anagram_index(C), codes=to_codes(pool),
              gctx=(full, cols, pool, ans, answers, 2, cap, gpos))


def _trial(args):
    """One whole climb.  Returns everything the parent needs to print and record."""
    trial, seed = args
    W = _W
    rng = np.random.default_rng(seed + trial)
    start = [int(x) for x in rng.choice(len(W["cands"]), size=W["words"],
                                        replace=False)]
    t0 = time.time()
    def say(msg):
        if W["q"] is None:
            print(msg, flush=True)
        else:
            W["q"].put(msg)

    say("trial %d   start %s"
        % (trial, " ".join(W["cands"][c] for c in start)))

    def on_step(step, pos, old, new, uns, ssq):
        say("  trial %-4d step %-3d %-7s -> %-7s   unsolved %5d  ssq %7d   (%.0fs)"
            % (trial, step, W["cands"][old], W["cands"][new], uns, ssq,
               time.time() - t0))

    def score_fn(wl):
        """The objective for a whole opening -- the one in greedybuild."""
        return score(tuple(wl), (W["full"], W["codes"], W["cols"], W["ans"],
                                 [W["M"][c] for c in wl]))

    # THREE SECTIONS, in order, each run to exhaustion before the next starts
    # (the user's shape).  They widen: one word, then a pair rearranged into the
    # same letters, then a pair with one letter traded.  Each later section can
    # only move where the earlier one is already stuck, which is the point --
    # the survivors of a one-word climb are near-anagram families that need two
    # words to change together.
    uns, ssq, wds, steps = climb(W["full"], W["cols"], W["M"], start, W["ans"],
                                 on_step)
    phases = [("swap", steps)]
    for label, within in (("anagram", 0), ("anagram+1", 1)):
        def on_pair(step, old_pair, new_pair, u, q2, _l=label):
            say("  trial %-4d %-9s %-7s %-7s -> %-7s %-7s   unsolved %5d  "
                "ssq %7d   (%.0fs)"
                % (trial, _l, W["cands"][old_pair[0]], W["cands"][old_pair[1]],
                   W["cands"][new_pair[0]], W["cands"][new_pair[1]], u, q2,
                   time.time() - t0))

        uns, ssq, wds, n = climb_pairs(score_fn, wds, W["C"], W["by_sig"],
                                       within, (uns, ssq), on_pair)
        phases.append((label, n))
    names = [W["cands"][c] for c in wds]
    if neighbourhood(W["full"], W["cols"], W["M"], wds, W["ans"],
                     (uns, ssq)) is not None:
        raise SystemExit("GATE FAILED: the climb stopped at %s but a swap "
                         "still improves it" % " ".join(names))
    _, losing, _, _, _ = check_opening(names, W["gctx"])
    if len(losing) != uns:
        raise SystemExit("GATE FAILED: %s scores %d unsolved here and %d "
                         "losing in guarantee_sweep"
                         % (" ".join(names), uns, len(losing)))
    return (trial, names, uns, ssq,
            ", ".join("%s %d" % (l, n) for l, n in phases), time.time() - t0)


def main(argv):
    a = parse_args(argv)
    guesses, answers = load_words("guess"), load_words("mystery")
    pool = sorted(resolve_word_set(a["pool"]))
    pset, gpos = set(pool), {w: i for i, w in enumerate(guesses)}
    missing = [w for w in answers if w not in pset]
    if missing:
        raise SystemExit("the pool is missing %d answer(s): %s"
                         % (len(missing), ", ".join(missing[:5])))
    ppos = {w: i for i, w in enumerate(pool)}
    cands = pool if a["candidates"] is None else sorted(
        resolve_word_set(a["candidates"]))
    bad = [w for w in cands if w not in gpos]
    if bad:
        raise SystemExit("--candidates has %d word(s) that are not legal "
                         "guesses: %s" % (len(bad), ", ".join(bad[:5])))

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    ans = np.array([ppos[w] for w in answers])
    Mpool = pool_matrix(full, cols)
    same = cands == pool
    M = Mpool if same else cand_matrix(
        full, np.array([gpos[w] for w in cands]), cols)

    print("hill climb: pool %s (%d)  answers %d  words %d  cap %d"
          % (a["pool"], len(pool), len(answers), a["words"], a["cap"]))
    print("  words    the %d come from %s (%d)%s"
          % (a["words"], a["candidates"] or a["pool"], len(cands),
             "" if same else "  -- a DIFFERENT list from the pool"))
    print("  trials   %d random restarts, seed %d" % (a["trials"], a["seed"]))
    print("  sections single-word swaps, then ANAGRAM pair swaps, then pair")
    print("           swaps within ONE LETTER of an anagram -- each to exhaustion")
    print("  workers  %d%s" % (a["workers"], "" if a["workers"] > 1 else
                               "  (serial)"))
    if a["workers"] > 1:
        print("           trials are seeded by INDEX, so --workers changes the "
              "ORDER lines appear")
        print("           in and nothing else -- the same seed gives the same "
              "trials either way")

    fh = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        fresh = not os.path.exists(a["out"])
        fh = open(a["out"], "a")
        if fresh:
            fh.write("# hill climb (see math/hillclimb.py): random starts, "
                     "one-word swaps\n")
            fh.write("# settings pool=%s candidates=%s words=%d cap=%d seed=%d\n"
                     % (a["pool"], a["candidates"] or a["pool"], a["words"],
                        a["cap"], a["seed"]))
            fh.write(COLUMNS + "\n")

    gctx = (full, cols, pool, ans, answers, 2, a["cap"], gpos)
    best_ever = None
    t_all = time.time()

    def record(trial, names, uns, ssq, steps, secs):
        """One finished trial: report it, rank it, write it."""
        nonlocal best_ever
        print("  trial %-4d done [%s]: %s   unsolved %d  ssq %d  (%.0fs)"
              % (trial, steps, " ".join(names), uns, ssq, secs), flush=True)
        if best_ever is None or (uns, ssq) < best_ever[:2]:
            best_ever = (uns, ssq, names, trial)
            print("  NEW BEST across trials", flush=True)
        else:
            print("  best so far: trial %d, unsolved %d (%s)"
                  % (best_ever[3], best_ever[0], " ".join(best_ever[2])),
                  flush=True)
        if fh:
            fh.write("%d,%s,%d,%d,%s,%.1f\n"
                     % (trial, " ".join(names), uns, ssq,
                        steps.replace(",", ";"), secs))
            fh.flush()

    if a["workers"] <= 1:
        _init(a["pool"], a["candidates"], a["words"], a["cap"], None)
        for trial in range(1, a["trials"] + 1):
            print("", flush=True)
            record(*_trial((trial, a["seed"])))
    else:
        # The queue carries STEP lines live, because "a printout after every
        # improvement" is the point of the tool and batching them per trial
        # would hold each one back by a whole climb.  Lines from different
        # trials interleave, so every one names its trial.
        mgr = Manager()
        q = mgr.Queue()
        with ProcessPoolExecutor(max_workers=a["workers"], initializer=_init,
                                 initargs=(a["pool"], a["candidates"],
                                           a["words"], a["cap"], q)) as ex:
            pending = {ex.submit(_trial, (t, a["seed"]))
                       for t in range(1, a["trials"] + 1)}
            while pending:
                while True:
                    try:
                        print(q.get_nowait(), flush=True)
                    except _queue.Empty:
                        break
                done, pending = wait(pending, timeout=0.3,
                                     return_when=FIRST_COMPLETED)
                for f in done:
                    record(*f.result())
            while True:
                try:
                    print(q.get_nowait(), flush=True)
                except _queue.Empty:
                    break

    print("\nbest over %d trial(s): %s" % (a["trials"], " ".join(best_ever[2])))
    print("  unsolved %d of %d,  ssq %d   (trial %d, %.0fs total)"
          % (best_ever[0], len(answers), best_ever[1], best_ever[3],
             time.time() - t_all))
    if fh:
        fh.close()
    if a["out"]:
        print("wrote %s" % a["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
