"""Stage 2 of an opener sweep: cut a shortlist out of a stage-1 screen.

    python3 tools/multiwordle_shortlist.py --from SWEEP.csv --se 10 --out LIST.txt
    python3 tools/multiwordle_shortlist.py --from SWEEP.csv --top 200 --out LIST.txt

Or let the sweep wrapper do both steps in one command:

    bash solver/run-multiwordle-sweep.sh -k 1 -t 10000 --seed 1 \\
        --shortlist-from data/shared/multiwordle/sweep_k1_t1000_s0_guess.csv

WHY A SECOND STAGE EXISTS.  A wide sweep at small -t estimates every word to
within its own standard error, and over 12972 words the best-looking mean belongs
to whichever word drew the kindest sample -- so the head of a screen is biased
optimistic and cannot be read as a winner.  Re-running a SHORTLIST at large -t
gives the survivors estimates precise enough to separate, and a word that leads
both stages has been asked twice.

THE CUT IS A NET, NOT A VERDICT -- KEEP IT GENEROUS.  --se N keeps every word
whose mean is within N standard errors of the best word's, using the BEST word's
standard error by default (--own-se uses each word's own, which is slightly more
permissive since the losers' errors are larger).  A tight cut risks discarding
the true best word on one unlucky sample; that error is unrecoverable, while an
over-wide cut only costs time.  10 SE at t=1000 is a deliberately wide net.

USE A DIFFERENT --seed FOR STAGE 2.  The draw stream is seeded per word, so a
stage-2 run at the SAME seed replays stage 1's games as its first -t of them --
re-using the very sample that chose the shortlist, and carrying its selection
bias forward.  A fresh seed makes stage 2 an independent test of stage 1's claim.

ORDER.  The shortlist is written best-first by stage-1 mean, so a stage-2 run
that is stopped early has examined the most promising words rather than an
alphabetical prefix.  That ordering is a convenience only: every word still gets
the same trials and the same games, so nothing about it favours a word.
"""

import os
import sys

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def read_sweep(path):
    """(word, mean, stderr) per row of a sweep CSV, in file order."""
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("word,"):
                continue
            c = line.rstrip("\n").split(",")
            if len(c) < 4:
                continue
            rows.append((c[0], float(c[2]), float(c[3])))
    if not rows:
        raise SystemExit("no data rows in %s" % path)
    return rows


def shortlist(rows, se=None, top=None, own_se=False):
    """The surviving words, best mean first, plus a description of the cut."""
    rows = sorted(rows, key=lambda r: r[1])
    best_mean, best_se = rows[0][1], rows[0][2]
    if top is not None:
        return rows[:top], "top %d by stage-1 mean" % top
    if own_se:
        keep = [r for r in rows if r[1] <= best_mean + se * r[2]]
        how = "within %g x EACH word's own standard error of %s (%.4f)" % (
            se, rows[0][0], best_mean)
    else:
        cut = best_mean + se * best_se
        keep = [r for r in rows if r[1] <= cut]
        how = "within %g x %s's standard error %.4f of %.4f, i.e. mean <= %.4f" % (
            se, rows[0][0], best_se, best_mean, cut)
    return keep, how


def main(argv):
    src = out = None
    se, top, own_se = 10.0, None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--from":
            src = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--se":
            se = float(argv[i + 1]); i += 2
        elif a == "--top":
            top = int(argv[i + 1]); i += 2
        elif a == "--own-se":
            own_se = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if src is None:
        raise SystemExit("--from SWEEP.csv is required")
    if out is None:
        raise SystemExit("--out LIST.txt is required")

    rows = read_sweep(src)
    keep, how = shortlist(rows, se=se, top=top, own_se=own_se)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for w, _, _ in keep:
            f.write(w + "\n")
    print("%s: %d words of %d kept" % (out, len(keep), len(rows)))
    print("  cut: %s" % how)
    print("  from: %s" % src)
    print("  head: %s" % " ".join(w for w, _, _ in keep[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
