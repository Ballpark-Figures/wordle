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
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                                  # noqa: E402
from guarantee_sweep import check_opening                                 # noqa: E402
from hillclimb import climb, neighbourhood                                # noqa: E402
from opening_list import resolve_word_set                                 # noqa: E402
from paircover import cand_matrix, pool_matrix                            # noqa: E402
from wordle import load_words                                             # noqa: E402

COLUMNS = "trial,opening,unsolved,ssq,steps,secs"


def parse_args(argv):
    a = {"pool": None, "candidates": None, "words": 4, "trials": None,
         "cap": 6, "seed": 0, "out": None}
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
        a[k] = (int(v) if k in ("words", "trials", "cap", "seed") else v)
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
    print("  each     climbed by single-word swaps until none improves")

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
    for trial in range(1, a["trials"] + 1):
        rng = np.random.default_rng(a["seed"] + trial)
        start = [int(x) for x in rng.choice(len(cands), size=a["words"],
                                            replace=False)]
        t0 = time.time()
        print("\ntrial %d   start %s" % (trial, " ".join(cands[c] for c in start)),
              flush=True)

        def on_step(step, pos, old, new, uns, ssq, _t0=t0):
            print("  step %-3d %-7s -> %-7s   unsolved %5d  ssq %7d   (%.0fs)"
                  % (step, cands[old], cands[new], uns, ssq, time.time() - _t0),
                  flush=True)

        uns, ssq, words, steps = climb(full, cols, M, start, ans, on_step)
        names = [cands[c] for c in words]

        # --- the gate, both halves, every trial --------------------------
        if neighbourhood(full, cols, M, words, ans, (uns, ssq)) is not None:
            raise SystemExit("GATE FAILED: the climb stopped at %s but a swap "
                             "still improves it" % " ".join(names))
        _, losing, _, _, _ = check_opening(names, gctx)
        if len(losing) != uns:
            raise SystemExit("GATE FAILED: %s scores %d unsolved here and %d "
                             "losing in guarantee_sweep"
                             % (" ".join(names), uns, len(losing)))

        print("  local optimum after %d step(s): %s   unsolved %d  ssq %d  (%.0fs)"
              % (steps, " ".join(names), uns, ssq, time.time() - t0))
        if best_ever is None or (uns, ssq) < best_ever[:2]:
            best_ever = (uns, ssq, names, trial)
            print("  NEW BEST across trials")
        else:
            print("  best so far: trial %d, unsolved %d (%s)"
                  % (best_ever[3], best_ever[0], " ".join(best_ever[2])))
        if fh:
            fh.write("%d,%s,%d,%d,%d,%.1f\n"
                     % (trial, " ".join(names), uns, ssq, steps,
                        time.time() - t0))
            fh.flush()

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
