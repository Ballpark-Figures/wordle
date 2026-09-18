"""Per opening: does it GUARANTEE a win?  math/guarantee.py states the question.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-guarantee.sh --pool custom --openings-from RANKING.csv --top 10000

EXACT AND DETERMINISTIC -- no sampling, no seed, no standard error -- so a re-run
reproduces the file byte for byte.  One row per opening:

    word, worst_case, guaranteed, losing_answers, losing_share, worst_answer,
    worst_line

`worst_case` is the most guesses the random follow-up can be made to spend, over
every answer and every draw it could make; `guaranteed` is 1 exactly when that is
within the cap.  `losing_answers` counts the answers for which SOME draw sequence
breaches it, and `losing_share` is their share of the 2315 -- an upper bound on
the loss rate, since only some draws lose.  `worst_line` is the witness: the
actual sequence of words, so the row can be checked by hand.

THE POOL AND THE ADAPTIVE THRESHOLD ARE PART OF THE QUESTION, never defaulted in
here -- the wrapper carries defaults a human reads and forwards them explicitly,
and both land in the filename.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                          # noqa: E402
from guarantee import joint_keys, stop_levels, worst_case          # noqa: E402
from opening_list import read_openings, resolve_word_set           # noqa: E402
from wordle import load_words                                      # noqa: E402

COLUMNS = ("word,worst_case,guaranteed,losing_answers,losing_share,"
           "worst_answer,worst_line,losing_words")


def worst_line(sub_rows, answer_pos, names):
    """The witness for `worst_case`: the longest sequence of draws, as words."""
    n = sub_rows.shape[0]
    if n == 1:
        return [names[answer_pos]]
    best = []
    for g in range(n):
        if g == answer_pos:
            continue
        keep = np.flatnonzero(sub_rows[g] == sub_rows[g][answer_pos])
        pos = int(np.searchsorted(keep, answer_pos))
        sub = worst_line(sub_rows[np.ix_(keep, keep)], pos,
                         [names[i] for i in keep])
        if len(sub) + 1 > len(best):
            best = [names[g]] + sub
    return best


def check_opening(opening, ctx):
    """(worst_case, losing_answers, worst_answer, worst_line) for one opening."""
    full, cidx, pool, apool, answers, adapt, cap, gpos = ctx
    gi = [gpos[w] for w in opening]
    pool_rows = np.stack([full[g][cidx] for g in gi])        # (k, npool)
    ans_rows = pool_rows[:, apool]                            # answers are in the pool
    level, _ = stop_levels(pool_rows, ans_rows, adapt)

    # The losing answers are NAMED, not just counted: which words can be made to
    # lose is what says whether an opening is one bad bucket away or hopeless,
    # and the count alone cannot be read that way.  It is bounded and small --
    # MEASURED over 10000 openings: median 19, max 39 -- so keeping the list
    # costs a short field per row rather than an unbounded one.
    worst, wans, wline, losing, groups = 0, "", [], [], []
    # Group the answers by (level, joint key at that level): every answer in one
    # group sees the identical live set, so the recursion runs ONCE per group.
    for lv in np.unique(level):
        sel = np.flatnonzero(level == lv)
        pkey = joint_keys(pool_rows[:lv])
        akey = joint_keys(ans_rows[:lv])[sel]
        order = np.argsort(pkey, kind="stable")
        skey = pkey[order]
        for key in np.unique(akey):
            lo = int(np.searchsorted(skey, key, "left"))
            hi = int(np.searchsorted(skey, key, "right"))
            members = order[lo:hi]                  # pool indices still live
            names = [pool[i] for i in members]
            sub = full[np.ix_(cidx[members], cidx[members])]
            # A LOSS IS A PROPERTY OF THE BUCKET, NOT OF THE WORD.  Two answers
            # sharing a bucket can differ -- one may be isolated by every other
            # live word and its neighbour not -- so the bucket is recorded whole,
            # the words that CANNOT lose included, because that is what shows why
            # it fails: a near-anagram family sitting in one group.
            bucket_losers = []
            for a in sel[akey == key]:
                aw = answers[a]
                if aw in opening[:lv]:
                    total = opening.index(aw) + 1   # an opening word WAS the answer
                    line = list(opening[:total])
                else:
                    pos = names.index(aw)
                    total = int(lv) + worst_case(sub, pos)
                    line = None
                if total > cap:
                    losing.append(aw)
                    bucket_losers.append(aw)
                if total > worst:
                    worst = total
                    wans = aw
                    wline = (line if line is not None else
                             list(opening[:lv]) + worst_line(sub, pos, names))
            if bucket_losers:
                groups.append((list(names), set(bucket_losers)))
    return worst, losing, wans, wline, groups


def parse_args(argv):
    a = {"pool": None, "openings_from": None, "openings_in": None, "top": None,
         "words": None, "adapt": None, "cap": 6, "out": None, "progress": 100}
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
        a[k] = int(v) if k in ("top", "adapt", "cap", "progress") else v
        i += 2
    if a["pool"] is None:
        raise SystemExit(
            "--pool is required: which words the follow-up may draw from "
            "(custom, mystery, guess, or a path).\n"
            "It is part of the question -- a pool holding words that can never "
            "be the answer is what makes a worst case worse.")
    if a["adapt"] is None:
        raise SystemExit(
            "--adapt N is required: the --pair-adaptive threshold the opening is "
            "abandoned at (0 for a purely blind opening).\n"
            "It changes how many guesses the tail has, so it changes the answer.")
    if not a["openings_from"] and not a["words"]:
        raise SystemExit("--openings-from RANKING.csv or --words LIST.txt")
    if a["out"] is None:
        raise SystemExit(
            "--out is required (or --no-out to discard it deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-guarantee.sh")
    return a


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}

    pool = sorted(resolve_word_set(a["pool"]))
    missing = [w for w in answers if w not in set(pool)]
    if missing:
        raise SystemExit(
            "the pool is missing %d ANSWER word(s), so the follow-up could never "
            "name them: %s" % (len(missing), ", ".join(missing[:5])))
    if a["openings_from"]:
        restrict = (resolve_word_set(a["openings_in"]) if a["openings_in"]
                    else None)
        field = read_openings(a["openings_from"], a["top"], restrict)
    else:
        with open(a["words"]) as f:
            field = [ln.split() for ln in f if ln.strip()]
        if a["top"]:
            field = field[:a["top"]]

    full = np.array(load_patterns(full=True))
    cidx = np.array([gpos[w] for w in pool])
    ppos = {w: i for i, w in enumerate(pool)}
    apool = np.array([ppos[w] for w in answers])
    ctx = (full, cidx, pool, apool, answers, a["adapt"], a["cap"], gpos)

    # THE INCUMBENT IS REBUILT FROM THE CSV ON A RESUME, not started fresh.
    # Without that a resumed run re-announces openings WORSE than ones already on
    # file as "NEW BEST" -- the same scar greens.c and wturns carry, where a
    # resumed run reported a tie list it had not actually searched for.
    done, best = set(), None
    if a["out"] and os.path.exists(a["out"]):
        with open(a["out"]) as f:
            for ln in f:
                if ln.startswith("#") or ln.startswith("word,"):
                    continue
                c = ln.rstrip("\n").split(",")
                done.add(c[0])
                try:
                    cand = (int(c[1]), int(c[3]))
                except (IndexError, ValueError):
                    continue
                if best is None or cand < best[0]:
                    best = (cand, c[0])
        print("resuming: %d opening(s) already on file%s"
              % (len(done),
                 "" if best is None else
                 ", best so far %s (worst %d, %d can lose)"
                 % (best[1], best[0][0], best[0][1])))
    fh = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        new = not done
        fh = open(a["out"], "a")
        if new:
            fh.write("# guarantee sweep (see math/guarantee.py): the WORST case "
                     "over every answer and\n# every draw the random follow-up "
                     "could make -- exact, no sampling, no seed\n")
            fh.write("# settings pool=%s adapt=%d cap=%d openings=%d source=%s\n"
                     % (a["pool"], a["adapt"], a["cap"], len(field),
                        a["openings_from"] or a["words"]))
            fh.write(COLUMNS + "\n")

    print("guarantee: %d openings of %d words, pool %s (%d), adapt %d, cap %d"
          % (len(field), len(field[0]), a["pool"], len(pool), a["adapt"], a["cap"]))
    t0, nguar, ndone = time.time(), 0, 0
    for n, opening in enumerate(field):
        name = " ".join(opening)
        if name in done:
            continue
        worst, losers, wans, wline, groups = check_opening(opening, ctx)
        losing = len(losers)
        guaranteed = int(worst <= a["cap"])
        nguar += guaranteed
        ndone += 1
        # WHAT "BEST" MEANS: fewest guesses in the worst case, ties broken by how
        # many answers can lose at all.  Both are exact, so a tie is a real tie
        # and only a STRICT improvement prints -- a plateau would otherwise
        # flood the log, which is why pairsplit's incumbent line does the same.
        cand = (worst, losing)
        if best is None or cand < best[0]:
            best = (cand, name)
            # One line per GROUP that can lose: the whole live set after the
            # opening, with the answers that can actually lose marked.  Sorted
            # widest first, since a big group is the harder thing to fix.
            shown = []
            for names, bad in sorted(groups, key=lambda g: (-len(g[0]), g[0])):
                shown.append("              " + " ".join(
                    w + "*" if w in bad else w for w in sorted(names)))
            print("[%7.0fs] %-26s worst=%d  %2d of %d can lose  NEW BEST%s%s"
                  % (time.time() - t0, name, worst, losing, len(answers),
                     "  -- GUARANTEED" if guaranteed else "",
                     ("\n" + "\n".join(shown)) if shown else ""), flush=True)
        if fh:
            fh.write("%s,%d,%d,%d,%.8f,%s,%s,%s\n"
                     % (name, worst, guaranteed, losing,
                        losing / len(answers), wans, " ".join(wline),
                        " ".join(sorted(losers))))
            fh.flush()
        if a["progress"] and ndone % a["progress"] == 0:
            el = time.time() - t0
            print("  %d/%d  %.1f/s  %d guaranteed so far  eta %.1f min"
                  % (n + 1, len(field), ndone / el, nguar,
                     (len(field) - n - 1) / (ndone / el) / 60), flush=True)
    if fh:
        fh.close()
    print("%d of %d examined openings guarantee a win within %d"
          % (nguar, ndone, a["cap"]))
    if best is not None:
        print("best: %s -- worst case %d guesses, %d of %d answers can lose"
              % (best[1], best[0][0], best[0][1], len(answers)))
    if a["out"]:
        print("wrote %s" % a["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
