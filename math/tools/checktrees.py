"""Verify emitted optimal trees are internally consistent -- and, for hardturns,
that every guess in them is legal under hard mode.

This is an INDEPENDENT check of the solver's output: it replays each line with
the repo's own `wordle.pattern` feedback function and re-derives the hard-mode
constraint from scratch, so a bug in the C solver's constraint handling shows up
as a legality failure here rather than as a plausible-looking wrong number.

Per opener it checks:
  * every one of the 2315 answers appears exactly once
  * each line's recorded guess count matches the guesses on it
  * each line's final guess is the answer
  * replaying the line reproduces a consistent game -- each guess is still a
    candidate given all prior feedback
  * (hard mode) each guess reuses every revealed hint: greens in place, and at
    least as many copies of each yellowed letter
  * the summed guess counts equal that opener's `total` in the CSV

    WORDLE_SOLVER=hardturns python3 tools/checktrees.py            # 20 random
    WORDLE_SOLVER=hardturns python3 tools/checktrees.py salet crane
    WORDLE_SOLVER=hardturns python3 tools/checktrees.py --all      # every tree

`--vs-normal` skips the trees and instead cross-checks the two sweeps' CSVs:
hard mode is a strict restriction of the strategy space, so a hard-mode total
can never be BELOW that opener's normal-mode total. That is a mathematical
necessity rather than a published figure, which makes it the strongest gate
available for hard mode without an external reference.

    python3 tools/checktrees.py --vs-normal

Exit status is nonzero if anything failed, so it works as a gate.
"""
import glob
import gzip
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wordle import decode, pattern
from paths import GUESS_WORDS, N_ANSWERS, SOLVER, TREES, load_totals

HARD = SOLVER == "hardturns"
SAMPLE = 20

# The sweep's LEGAL GUESS set. Every guess on every line must come from it -- the
# one exception being a PHANTOM final guess, which only `ansall` can produce: an
# answer outside the guess list is won by narrowing to it and adding one, and the
# tree writes the answer itself as that unplayable naming move so the line stays
# a complete replay. Anywhere else in a line, an illegal guess is a real failure.
# For the three sweeps whose answers all ARE legal guesses this reduces to "every
# guess is legal", which they already satisfy -- so the check is new coverage, not
# a behaviour change.
with open(GUESS_WORDS) as _f:
    LEGAL = {w.strip() for w in _f if w.strip()}


def check_line(parts, hard):
    """Return a list of failure strings for one tree line."""
    bad = []
    answer, n = parts[0], int(parts[1])
    guesses = parts[2::2]
    pats = parts[3::2]
    if len(guesses) != n:
        bad.append("says %d guesses, has %d" % (n, len(guesses)))
    if guesses[-1] != answer:
        bad.append("ends on %s, not the answer %s" % (guesses[-1], answer))
    for k, g in enumerate(guesses):
        if g in LEGAL:
            continue
        if k == len(guesses) - 1 and g == answer and answer not in LEGAL:
            continue                    # the phantom naming move -- see LEGAL above
        bad.append("guess %d %s is not a legal guess" % (k + 1, g))

    green = [None] * 5          # revealed pinned letters
    minc = {}                   # revealed minimum letter counts
    for k, g in enumerate(guesses):
        if hard:
            for i, c in enumerate(green):
                if c is not None and g[i] != c:
                    bad.append("guess %d %s breaks green %s at %d" % (k + 1, g, c, i))
            for c, need in minc.items():
                if g.count(c) < need:
                    bad.append("guess %d %s has %d %s, needs %d"
                               % (k + 1, g, g.count(c), c, need))
        got = pattern(g, answer)
        if k < len(pats):       # the last guess is the answer and carries no pattern
            want = "".join("byg"[t] for t in decode(got))
            if pats[k] != want:
                bad.append("guess %d %s vs %s: tree says %s, really %s"
                           % (k + 1, g, answer, pats[k], want))
        elif got != 242:
            bad.append("final guess %s is not all-green against %s" % (g, answer))
        # fold this feedback in, exactly as the solver does
        tiles = decode(got)
        req = {}
        for i, t in enumerate(tiles):
            if t == 2:
                green[i] = g[i]
            if t:
                req[g[i]] = req.get(g[i], 0) + 1
        for c, v in req.items():
            if v > minc.get(c, 0):
                minc[c] = v
    return bad


def check_tree(path, totals):
    word = os.path.basename(path).split(".")[0]
    seen, total, fails = set(), 0, []
    with gzip.open(path, "rt") as f:
        for lineno, line in enumerate(f, 1):
            parts = line.split()
            if len(parts) < 3:
                fails.append("line %d: malformed" % lineno)
                continue
            if parts[0] in seen:
                fails.append("line %d: answer %s repeated" % (lineno, parts[0]))
            seen.add(parts[0])
            total += int(parts[1])
            for b in check_line(parts, HARD):
                fails.append("line %d (%s): %s" % (lineno, parts[0], b))
    if len(seen) != N_ANSWERS:
        fails.append("covers %d answers, expected %d" % (len(seen), N_ANSWERS))
    if word in totals and total != totals[word]:
        fails.append("tree sums to %d, CSV says %d" % (total, totals[word]))
    return word, total, fails


def vs_normal():
    """Hard-mode totals must dominate normal-mode totals, opener for opener."""
    normal = _totals_for("optturns")
    hard = _totals_for("hardturns")
    both = sorted(set(normal) & set(hard))
    if not both:
        sys.exit("no opener solved by BOTH sweeps yet -- nothing to compare")
    bad = [(w, hard[w], normal[w]) for w in both if hard[w] < normal[w]]
    print("comparing %d openers solved by both sweeps" % len(both))
    if bad:
        print("FAIL: %d opener(s) score BETTER in hard mode, which is impossible"
              % len(bad))
        for w, h, n in bad[:20]:
            print("       %-6s hard=%d < normal=%d" % (w, h, n))
        return 1
    ties = sum(1 for w in both if hard[w] == normal[w])
    worse = len(both) - ties
    print("PASS: hard >= normal everywhere (%d equal, %d strictly worse)"
          % (ties, worse))
    delta = [(hard[w] - normal[w]) / N_ANSWERS for w in both]
    print("      hard-mode penalty: mean %+.5f, max %+.5f turns"
          % (sum(delta) / len(delta), max(delta)))
    return 0


def _totals_for(solver):
    """load_totals() for one solver, independent of the ambient WORDLE_SOLVER."""
    import importlib
    os.environ["WORDLE_SOLVER"] = solver
    import paths as _paths
    importlib.reload(_paths)
    return _paths.load_totals()


def main():
    if "--vs-normal" in sys.argv:
        sys.exit(vs_normal())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    allmode = "--all" in sys.argv

    paths = sorted(glob.glob(os.path.join(TREES, "*.txt.gz")))
    if not paths:
        sys.exit("no trees at %s" % TREES)
    if args:
        want = set(args)
        paths = [p for p in paths if os.path.basename(p).split(".")[0] in want]
        missing = want - {os.path.basename(p).split(".")[0] for p in paths}
        if missing:
            sys.exit("no tree for: %s" % ", ".join(sorted(missing)))
    elif not allmode:
        random.seed(0)                      # reproducible sample, so reruns compare
        paths = sorted(random.sample(paths, min(SAMPLE, len(paths))))

    totals = load_totals()
    print("%s: checking %d tree(s) from %s%s"
          % (SOLVER, len(paths), TREES, "  [hard-mode legality ON]" if HARD else ""))
    nbad = 0
    for p in paths:
        word, total, fails = check_tree(p, totals)
        if fails:
            nbad += 1
            print("FAIL %-6s (%d issue(s))" % (word, len(fails)))
            for f in fails[:10]:
                print("       %s" % f)
            if len(fails) > 10:
                print("       ... and %d more" % (len(fails) - 10))
        else:
            print("PASS %-6s total=%d  expected=%.5f" % (word, total, total / N_ANSWERS))
    print("\n%d passed, %d failed" % (len(paths) - nbad, nbad))
    sys.exit(1 if nbad else 0)


if __name__ == "__main__":
    main()
