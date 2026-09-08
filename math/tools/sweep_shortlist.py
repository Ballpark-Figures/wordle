"""Cut a shortlist out of a stage-1 opener screen.  Shared by the sweeps.

    python3 tools/sweep_shortlist.py --from SWEEP.csv --se 10 --out LIST.txt
    python3 tools/sweep_shortlist.py --from SWEEP.csv --top 200 --out LIST.txt
    python3 tools/sweep_shortlist.py --from SWEEP.csv --se 10 \\
        --value win_rate --maximise --out LIST.txt

The cut logic lives here once and is used by BOTH opener sweeps -- multiwordle's
(tools/multiwordle_sweep.py, via the tools/multiwordle_shortlist.py front end,
whose behaviour is unchanged) and the single-board one (tools/wordle_sweep.py).
Any sweep CSV works: it needs a header row naming the columns, a `word` column,
and a value column with a standard-error column beside it.

WHY A SECOND STAGE EXISTS.  A wide sweep at small -t estimates every word to
within its own standard error, and over 12972 words the best-looking mean belongs
to whichever word drew the kindest sample -- so the head of a screen is biased
optimistic and cannot be read as a winner.  Re-running a SHORTLIST at large -t
gives the survivors estimates precise enough to separate, and a word that leads
both stages has been asked twice.

THE CUT IS A NET, NOT A VERDICT -- KEEP IT GENEROUS.  --se N keeps every word
within N standard errors of the best word's value, using the BEST word's standard
error by default (--own-se uses each word's own, which measures each word in its
own noise -- a DIFFERENT question, which can drop a word a fixed cut keeps).  A
tight cut risks discarding the true best word on one unlucky sample; that error is
unrecoverable, while an over-wide cut only costs time.

N IS THE CALLER'S CHOICE AND EACH WRAPPER CARRIES ITS OWN, deliberately: how wide
a net is generous depends on how big the standard errors are at that stage's -t.
run-multiwordle-sweep.sh passes 10; run-wordle-sweep.sh passes 5, after 10 was
measured to keep 95% of the field at t=100.  This module's own default of 10 is
for a direct invocation only -- both wrappers pass the flag explicitly, so neither
can move under the other.

USE A DIFFERENT --seed FOR STAGE 2.  The draw stream is seeded per word, so a
stage-2 run at the SAME seed replays stage 1's games as its first -t of them --
re-using the very sample that chose the shortlist, and carrying its selection
bias forward.  A fresh seed makes stage 2 an independent test of stage 1's claim.

WHICH COLUMN IS "BEST" IS AN INPUT.  --value names it (default `mean`, lower is
better) and --maximise says a larger value wins, for a column like `win_rate`.
The standard-error column is `<value>_stderr`, or plain `stderr` for `mean`, so a
cut is always measured in the noise of the thing being cut on.  A sweep reporting
two quantities has two different shortlists, and which one a run used belongs in
its filename.

ORDER.  The shortlist is written best-first by the stage-1 value, so a stage-2 run
stopped early has examined the most promising words rather than an alphabetical
prefix.  That ordering is a convenience only: every word still gets the same
trials and the same games, so nothing about it favours a word.
"""

import os
import sys


def read_sweep(path, value="mean"):
    """(word, value, stderr) per row, reading the columns BY NAME from the header.

    The error column is `<value>_stderr`, except for `mean`, whose error column is
    the plain `stderr` every sweep here has always written.
    """
    err = "stderr" if value == "mean" else value + "_stderr"
    header, rows = None, []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = [c.strip() for c in line.rstrip("\n").split(",")]
            if header is None:
                header = cols
                for name in ("word", value, err):
                    if name not in header:
                        raise SystemExit("%s has no %r column (it has: %s)"
                                         % (path, name, ", ".join(header)))
                iw, iv, ie = (header.index(n) for n in ("word", value, err))
                continue
            if len(cols) <= max(iw, iv, ie):
                continue
            rows.append((cols[iw], float(cols[iv]), float(cols[ie])))
    if not rows:
        raise SystemExit("no data rows in %s" % path)
    return rows


def shortlist(rows, se=None, top=None, own_se=False, maximise=False):
    """The surviving words, best first, plus a description of the cut."""
    sign = -1.0 if maximise else 1.0
    rows = sorted(rows, key=lambda r: sign * r[1])
    best_word, best_val, best_se = rows[0]
    if top is not None:
        return rows[:top], "top %d by stage-1 value" % top
    if own_se:
        keep = [r for r in rows if sign * r[1] <= sign * best_val + se * r[2]]
        how = "within %g x EACH word's own standard error of %s (%.6f)" % (
            se, best_word, best_val)
    else:
        cut = best_val + sign * se * best_se
        keep = [r for r in rows if sign * r[1] <= sign * cut]
        how = ("within %g x %s's standard error %.6f of %.6f, i.e. value %s %.6f"
               % (se, best_word, best_se, best_val, ">=" if maximise else "<=", cut))
    return keep, how


def main(argv, prog="tools/sweep_shortlist.py"):
    src = out = None
    se, top, own_se = 10.0, None, False
    value, maximise = "mean", False
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
        elif a == "--value":
            value = argv[i + 1]; i += 2
        elif a == "--maximise":
            maximise = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if src is None:
        raise SystemExit("--from SWEEP.csv is required")
    if out is None:
        raise SystemExit("--out LIST.txt is required")

    rows = read_sweep(src, value=value)
    keep, how = shortlist(rows, se=se, top=top, own_se=own_se, maximise=maximise)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        for w, _, _ in keep:
            f.write(w + "\n")
    print("%s: %d words of %d kept" % (out, len(keep), len(rows)))
    print("  cut: %s (on %s, %s is better)"
          % (how, value, "higher" if maximise else "lower"))
    print("  from: %s" % src)
    print("  head: %s" % " ".join(w for w, _, _ in keep[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
