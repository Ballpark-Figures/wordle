"""Random restarts, each climbed by widening swaps.  math/hillclimb.py states
the rule and IS the source of truth.

    bash solver/run-hill-climb.sh -t 100

Every accepted move prints, tagged with its ROUND and its section, because that
is the only thing that happens: the neighbourhood scan between two moves is
seconds of silence.

A GATE RUNS ON EVERY TRIAL, and both halves are free:

  * the climb must END at a local optimum of the SINGLE-WORD neighbourhood --
    which is a real assertion only because the sections LOOP.  Run once each,
    the last section is a pair section, so single-word swaps legitimately
    reopen and this check fires on a correct climb; it did, and the fix was the
    loop, not the check;
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
from hillclimb import (SECTIONS, anagram_index, climb_all,            # noqa: E402
                       letter_counts, neighbourhood)
from opening_list import resolve_word_set                                 # noqa: E402
from paircover import cand_matrix, pool_matrix                            # noqa: E402
from wordle import load_words, to_codes                                   # noqa: E402

COLUMNS = "trial,opening,unsolved,ssq,steps,secs"
# `steps` is the round count plus a per-SECTION breakdown ("rounds 3; swap 6,
# anagram 1, anagram+1 0, anagram3 2"), not one number: which neighbourhood moved,
# and how many passes it took to settle, are what say whether a section earns
# its time.  Steps are SUMMED over rounds.


def sections_stamp():
    """The SEARCH, as a short canonical string for the CSV's settings line.

    `(size, within)` per section, which IS the definition -- the labels are
    derived from it -- so the stamp cannot drift from what actually ran.
    """
    return ";".join(["swap"] + ["%dx%d" % (size, within)
                                for _, size, within in SECTIONS])


def check_stamp(path):
    """REFUSE to append to a file written by a DIFFERENT search.

    A row's `unsolved` is exact and search-independent, but a FILE is a record
    of what the search FINDS, so mixing two searches into one makes it a record
    of neither.  The greens scar in one sentence: a filename cannot check
    itself, so the stamp does.

    **A MISSING `sections=` IS AN OLD FILE, NOT A MATCH.**  Every run since the
    field existed writes it, so absence means the run predates the field -- and
    reading absence as "fine" is exactly how the two get mixed silently.
    """
    want = sections_stamp()
    with open(path) as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            if not line.startswith("# settings"):
                continue
            got = None
            for tok in line[len("# settings"):].split():
                if tok.startswith("sections="):
                    got = tok[len("sections="):]
            if got == want:
                return
            raise SystemExit(
                "%s was written by a %s search (sections=%s), and this one is "
                "sections=%s.\n  A file is a record of what a search FINDS, so "
                "appending would make it a record of neither.\n  Use a fresh "
                "--seed (the seed is in the filename), or move that file aside."
                % (path, "DIFFERENT" if got else "PRE-sections",
                   got or "<absent>", want))
    raise SystemExit("%s has no '# settings' line at all -- it was not written "
                     "by this tool" % path)


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

    def on_swap(rnd, step, pos, old, new, uns, ssq):
        say("  trial %-4d r%-2d swap      %-7s -> %-7s   unsolved %5d  "
            "ssq %7d   (%.0fs)"
            % (trial, rnd, W["cands"][old], W["cands"][new], uns, ssq,
               time.time() - t0))

    def on_move(rnd, label, step, old_words, new_words, u, q2):
        # Joined rather than per-slot, because a section may move two words or
        # three and one printer has to read for both.
        say("  trial %-4d r%-2d %-9s %-23s -> %-23s   unsolved %5d  "
            "ssq %7d   (%.0fs)"
            % (trial, rnd, label,
               " ".join(W["cands"][c] for c in old_words),
               " ".join(W["cands"][c] for c in new_words),
               u, q2, time.time() - t0))

    def score_fn(wl):
        """The objective for a whole opening -- the one in greedybuild."""
        return score(tuple(wl), (W["full"], W["codes"], W["cols"], W["ans"],
                                 [W["M"][c] for c in wl]))

    # THE SECTIONS AND THE LOOP LIVE IN hillclimb.climb_all, which states the
    # rule; this only prints.  Three widening neighbourhoods run in order, each
    # to exhaustion, and then the whole pass repeats until an entire pass moves
    # nothing -- because a pair move reopens single-word swaps.
    uns, ssq, wds, rounds, phases = climb_all(
        W["full"], W["cols"], W["M"], W["ans"], score_fn, W["C"], W["by_sig"],
        start, on_swap=on_swap, on_move=on_move)
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
            "rounds %d; " % rounds
            + ", ".join("%s %d" % (l, n) for l, n in phases),
            time.time() - t0)


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
    print("  sections %s -- each to exhaustion,"
          % ", ".join(["single-word swaps"]
                      + ["%s (%d words%s)"
                         % (lab, size, "" if within == 0
                            else ", within %d letter" % within)
                         for lab, size, within in SECTIONS]))
    print("           then ROUND AGAIN from the first until a WHOLE PASS moves")
    print("           nothing (a wider move reopens the narrower sections)")
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
        if not fresh:
            check_stamp(a["out"])
        fh = open(a["out"], "a")
        if fresh:
            fh.write("# hill climb (see math/hillclimb.py): random starts, "
                     "one-word swaps\n")
            fh.write("# settings pool=%s candidates=%s words=%d cap=%d "
                     "seed=%d sections=%s\n"
                     % (a["pool"], a["candidates"] or a["pool"], a["words"],
                        a["cap"], a["seed"], sections_stamp()))
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
