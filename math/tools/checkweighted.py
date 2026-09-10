"""Differential gate for `wturns` -- the WEIGHTED mode of optturns.c.

Weighted mode keeps optturns' search and changes what a guess COSTS: every alive
candidate pays its WEIGHT rather than 1, so the objective is

    sum over answers of  w_a * (guesses spent on a)

minimised subject to resolving every answer within --depth.  Everything that
makes the unweighted solver fast -- the counting lower bound, the n==1 / n==2
leaves, the d==2 closed form, the depth normalisation -- had to be re-derived
for that cost, and each one silently returns a WRONG NUMBER rather than an error
when it is off by a little.  So none of it is trusted.

Five checks, in increasing order of what they can catch:

  1. THE UNIFORM IDENTITY.  With every weight 1 the objective IS the guess
     count, so `wturns` must reproduce `optturns` -- same totals AND same node
     counts, i.e. the same search tree, not merely the same answer.  Free, and
     it pins the whole weighted path against a solver validated against
     Bertsimas & Paskov.  It cannot, however, catch an error that is symmetric
     in the weights, which is what checks 2 and 3 are for.

  2. THE SEARCH, against brute force.  A miniature complete `--data` directory
     (a handful of real words) so `wturns` reads a small problem by its NORMAL
     path, diffed against a plain memoised min-over-guesses recursion with no
     bound, no ordering and no transposition table -- independent of every
     optimisation the C makes.  Several weight vectors, several depths, and both
     the solved and the INFEASIBLE branches.

  3. COVERAGE, ASSERTED.  A weighted check that never sees the weights matter
     proves nothing, so this FAILS unless the weighted optimum actually DIFFERS
     from the unweighted one somewhere, unless an INFEASIBLE actually occurred,
     and unless the n==2 and d==2 closed forms were actually exercised.

  4. THE TREE.  The emitted tree is replayed from the STRINGS with
     `wordle.pattern` and its weighted sum must equal the reported total -- the
     one check that reaches the answer-by-answer accounting rather than the
     aggregate.

  5. THE REFUSALS.  Weighted mode has five ways to be handed an input that would
     silently produce a wrong number: no --weights, no --depth, a weight file
     out of order, a zero weight, a non-dyadic weight.  Each must EXIT, not
     absorb.  (The order one is load-bearing: the lower bound assigns the
     shallowest levels to the heaviest answers and gets each bucket in that
     order only because the answer indices are weight-descending.)

Run it alongside `bash solver/validate.sh` and `python3 tools/checkpatterns.py`.
"""

from __future__ import annotations

import functools
import gzip
import os
import subprocess
import sys
import tempfile
from fractions import Fraction

import numpy as np

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MATH)

from wordle import decode, pattern                            # noqa: E402

WTURNS = os.path.join(MATH, "solver", "wturns")
OPTTURNS = os.path.join(MATH, "solver", "optturns")

FAILED = []


def bad(msg):
    print("   FAIL " + msg)
    FAILED.append(msg)


def ok(msg):
    print("   ok   " + msg)


# --------------------------------------------------------------- the mini problem

MINI_GUESSES = [
    "crane", "slate", "trace", "adieu", "audio", "roast", "stern", "pilot",
    "brick", "flame", "gouty", "vixen", "wharf", "zesty", "mimic", "puppy",
    "abbey", "eerie", "llama", "salad", "tepee", "onion", "kayak", "level",
]
MINI_ANSWERS = [
    "crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame",
    "mimic", "puppy", "abbey", "llama", "salad", "onion", "kayak", "level",
]
WIN = 3 ** 5 - 1

# Weight vectors, as exact dyadic rationals.  "uniform" must reproduce the
# unweighted solver; the others must not (check 3 asserts that they do not).
WEIGHT_SETS = {
    "uniform": [Fraction(1)] * len(MINI_ANSWERS),
    "spiky": [Fraction(x) for x in
              (64, 32, 16, 8, 4, 2, 1, 1,
               Fraction(1, 2), Fraction(1, 2), Fraction(1, 4), Fraction(1, 4),
               Fraction(1, 8), Fraction(1, 8), Fraction(1, 16), Fraction(1, 16))],
    "twotier": [Fraction(9)] * 5 + [Fraction(1, 8)] * 11,
    "neartie": [Fraction(3)] * 8 + [Fraction(5, 2)] * 8,
}


def scaled(weights):
    """(integer weights, scale) -- the exact scaling the C does on load."""
    scale = 1
    for w in weights:
        d = w.denominator
        assert d & (d - 1) == 0, "weight %s is not dyadic" % w
        scale = max(scale, d)
    return [int(w * scale) for w in weights], scale


def ordered_answers(weights):
    """The answers and weights sorted weight-DESCENDING, as the C requires."""
    pairs = sorted(zip(MINI_ANSWERS, weights), key=lambda t: (-t[1], t[0]))
    return [w for w, _ in pairs], [x for _, x in pairs]


def make_mini_data(tmp, answers, guesses=None):
    """A complete miniature `--data` directory, so wturns reads a small problem
    by its NORMAL path -- no special flags, so the code under test is the code
    that runs for real.

    `guesses` defaults to MINI_GUESSES; checkwturnsobjective.py passes a larger
    list, because a problem this small is solved optimally by the greedy and so
    cannot exercise a beam at all."""
    guesses = MINI_GUESSES if guesses is None else guesses
    words = os.path.join(tmp, "shared", "words")
    pats = os.path.join(tmp, "local", "patterns")
    os.makedirs(words, exist_ok=True)
    os.makedirs(pats, exist_ok=True)
    with open(os.path.join(words, "guess.txt"), "w") as f:
        f.write("\n".join(guesses) + "\n")
    with open(os.path.join(words, "mystery.txt"), "w") as f:
        f.write("\n".join(answers) + "\n")
    mat = np.array([[pattern(g, a) for a in answers] for g in guesses],
                   dtype=np.uint8)
    np.save(os.path.join(pats, "patterns.npy"), mat)


def write_weights(path, answers, weights):
    with open(path, "w") as f:
        for w, x in zip(answers, weights):
            f.write("%s %d/%d\n" % (w, x.numerator, x.denominator))


def mini_matrix(answers):
    return [[pattern(g, a) for a in answers] for g in MINI_GUESSES]


# --------------------------------------------------------------- the reference

def brute(mat, iw, opener, depth):
    """Exact minimum WEIGHTED total, subject to the cap, in scaled integer units.

    A plain memoised min-over-guesses recursion: no lower bound, no ordering, no
    transposition subtleties, no closed forms -- so it shares none of the
    machinery it is checking.  None means the opener cannot fit the cap (the C's
    INFEASIBLE).  `stats` records which leaf shapes were reached, so check 3 can
    assert the closed forms were actually exercised."""
    ng = len(MINI_GUESSES)
    stats = {"n1": 0, "n2": 0, "d2": 0}

    @functools.lru_cache(maxsize=None)
    def solve(cands, d):
        n = len(cands)
        if n == 0:
            return 0
        w = sum(iw[a] for a in cands)
        if n == 1:
            stats["n1"] += 1
            return w if d >= 1 else None
        if d <= 1:
            return None
        if n == 2:
            stats["n2"] += 1
        if d == 2:
            stats["d2"] += 1
        best = None
        for g in range(ng):
            buckets = {}
            for a in cands:
                buckets.setdefault(mat[g][a], []).append(a)
            if len(buckets) == 1 and WIN not in buckets:
                continue                       # splits nothing, cannot help
            total, good = w, True              # this guess, charged by weight
            for p, kids in buckets.items():
                if p == WIN:
                    continue                   # that answer is done, already paid
                sub = solve(tuple(kids), d - 1)
                if sub is None:
                    good = False
                    break
                total += sub
            if good and (best is None or total < best):
                best = total
        return best

    root = tuple(range(len(iw)))
    g = MINI_GUESSES.index(opener)
    buckets = {}
    for a in root:
        buckets.setdefault(mat[g][a], []).append(a)
    total = sum(iw)
    for p, kids in buckets.items():
        if p == WIN:
            continue
        sub = solve(tuple(kids), depth - 1)
        if sub is None:
            return None, stats
        total += sub
    return total, stats


# --------------------------------------------------------------- running the C

def run(binary, args, data=None):
    cmd = [binary, "--threads", "1"] + (["--data", data] if data else [])
    if data and "--tt-bits" not in args:
        cmd += ["--tt-bits", "20"]          # the mini problem needs no 8.6 GB table
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True)


def parse_openers(text):
    """{word: (total, nodes)} from the solver's per-opener lines."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[1].startswith("total="):
            continue
        total = int(parts[1].split("=", 1)[1])
        nodes = None
        for i, tok in enumerate(parts):
            if tok.isdigit() and i + 1 < len(parts) and parts[i + 1].startswith("node"):
                nodes = int(tok)
        out[parts[0]] = (total, nodes)
    return out


def infeasible_words(text):
    return {l.split()[0] for l in text.splitlines() if "INFEASIBLE" in l}


# --------------------------------------------------------------- 1. uniform identity

def check_uniform(full):
    print("1. uniform weights reproduce the unweighted solver")
    for b, name in ((WTURNS, "wturns"), (OPTTURNS, "optturns")):
        if not os.path.exists(b):
            bad("no solver/%s -- run `sh build.sh` in solver/" % name)
            return
    tmp = tempfile.mkdtemp(prefix="checkwgt-uni-")
    answers, weights = ordered_answers(WEIGHT_SETS["uniform"])
    make_mini_data(tmp, answers)
    wpath = os.path.join(tmp, "w.txt")
    write_weights(wpath, answers, weights)
    op = ["--depth", "5"] + sum([["--opener", g] for g in MINI_GUESSES[:8]], [])
    a = run(OPTTURNS, op, data=tmp)
    b = run(WTURNS, op + ["--weights", wpath], data=tmp)
    ra, rb = parse_openers(a.stdout), parse_openers(b.stdout)
    if not ra:
        bad("optturns produced no openers on the mini problem:\n" + a.stderr[-500:])
        return
    if ra != rb:
        bad("uniform-weight wturns differs from optturns: %r vs %r" % (ra, rb))
    else:
        ok("%d openers agree on total AND node count" % len(ra))
    if infeasible_words(a.stdout) != infeasible_words(b.stdout):
        bad("the two disagree on which openers are INFEASIBLE")

    if not full:
        print("      (--full also runs salet on the real 12972x2315 lists)")
        return
    from wordle import load_words
    real = os.path.join(tmp, "real.weights")
    with open(real, "w") as f:
        for w in load_words("mystery"):
            f.write(w + " 1\n")
    r = run(WTURNS, ["--depth", "6", "--tt-bits", "25",
                     "--weights", real, "--opener", "salet"])
    got = parse_openers(r.stdout).get("salet", (None, None))[0]
    if got == 7920:
        ok("salet on the real lists = 7920 (Bertsimas & Paskov)")
    else:
        bad("salet on the real lists = %r, expected 7920" % got)


# --------------------------------------------------------------- 2/3. search + coverage

def check_search(depths, full):
    print("2. wturns vs a brute-force weighted solver on a %dx%d problem (depths %s)"
          % (len(MINI_GUESSES), len(MINI_ANSWERS), ", ".join(map(str, depths))))
    if not os.path.exists(WTURNS):
        bad("no solver/wturns -- run `sh build.sh` in solver/")
        return
    cover = {"differs": 0, "infeasible": 0, "n2": 0, "d2": 0, "cases": 0}
    openers = MINI_GUESSES if full else MINI_GUESSES[:8]

    for name, wts in WEIGHT_SETS.items():
        answers, weights = ordered_answers(wts)
        iw, scale = scaled(weights)
        mat = mini_matrix(answers)
        tmp = tempfile.mkdtemp(prefix="checkwgt-")
        make_mini_data(tmp, answers)
        wpath = os.path.join(tmp, "w.txt")
        write_weights(wpath, answers, weights)
        # the same problem with every weight 1, to prove the weights MATTER
        upath = os.path.join(tmp, "u.txt")
        write_weights(upath, answers, [Fraction(1)] * len(answers))

        for depth in depths:
            args = ["--depth", str(depth)] + sum([["--opener", g] for g in openers], [])
            r = run(WTURNS, args + ["--weights", wpath], data=tmp)
            if r.returncode != 0:
                bad("%s d%d: wturns exited %d\n%s" % (name, depth, r.returncode,
                                                      r.stderr[-500:]))
                continue
            got = parse_openers(r.stdout)
            inf = infeasible_words(r.stdout)
            ru = run(WTURNS, args + ["--weights", upath], data=tmp)
            gotu = parse_openers(ru.stdout)

            for g in openers:
                want, stats = brute(mat, iw, g, depth)
                cover["cases"] += 1
                cover["n2"] += stats["n2"]
                cover["d2"] += stats["d2"]
                if want is None:
                    if g in inf:
                        cover["infeasible"] += 1
                    else:
                        bad("%s d%d %s: brute force says INFEASIBLE, wturns says %r"
                            % (name, depth, g, got.get(g)))
                    continue
                if g in inf or g not in got:
                    bad("%s d%d %s: wturns says INFEASIBLE, brute force says %d"
                        % (name, depth, g, want))
                    continue
                if got[g][0] != want:
                    bad("%s d%d %s: wturns %d, brute force %d"
                        % (name, depth, g, got[g][0], want))
                # did the weights change the answer at all?
                if name != "uniform" and g in gotu:
                    scale_free = Fraction(got[g][0], scale)
                    if scale_free != gotu[g][0]:
                        cover["differs"] += 1
        print("   %-8s checked" % name)

    if not FAILED:
        ok("%d (weights, depth, opener) cases match exactly" % cover["cases"])

    print("3. coverage -- a check that never exercised the weights proves nothing")
    for key, msg in (("differs", "no weighted optimum ever differed from the unweighted one"),
                     ("infeasible", "no opener was ever INFEASIBLE"),
                     ("n2", "the n == 2 leaf never fired"),
                     ("d2", "the d == 2 closed form never fired")):
        if cover[key] == 0:
            bad(msg + " -- the differential is vacuous")
        else:
            ok("%s: %d" % (key, cover[key]))


# --------------------------------------------------------------- 4. the tree

def check_tree():
    print("4. the emitted tree replays from the strings and sums to the total")
    if not os.path.exists(WTURNS):
        return
    answers, weights = ordered_answers(WEIGHT_SETS["spiky"])
    iw, scale = scaled(weights)
    wof = dict(zip(answers, iw))
    tmp = tempfile.mkdtemp(prefix="checkwgt-tree-")
    make_mini_data(tmp, answers)
    wpath = os.path.join(tmp, "w.txt")
    write_weights(wpath, answers, weights)
    treedir = os.path.join(tmp, "trees")
    r = run(WTURNS, ["--depth", "5", "--weights", wpath, "--opener", "slate",
                     "--trees", treedir], data=tmp)
    got = parse_openers(r.stdout).get("slate")
    path = os.path.join(treedir, "slate.txt.gz")
    if not got or not os.path.exists(path):
        bad("no tree written for slate (%s)" % r.stderr[-300:])
        return
    total, seen = 0, set()
    for line in gzip.open(path, "rt"):
        parts = line.split()
        answer, nguess, plays = parts[0], int(parts[1]), parts[2:]
        seen.add(answer)
        # replay: every recorded pattern must be what the strings produce
        guesses = plays[0::2]
        pats = plays[1::2]
        for g, p in zip(guesses, pats):
            want = "".join("byg"[t] for t in decode(pattern(g, answer)))
            if p != want:
                bad("%s: guess %s recorded %s, strings give %s" % (answer, g, p, want))
                return
        if guesses[-1] != answer:
            bad("%s: line does not end on the answer" % answer)
            return
        if nguess != len(guesses):
            bad("%s: says %d guesses, line has %d" % (answer, nguess, len(guesses)))
            return
        total += wof[answer] * nguess
    if seen != set(answers):
        bad("tree covers %d of %d answers" % (len(seen), len(answers)))
    elif total != got[0]:
        bad("tree sums to %d, reported total is %d" % (total, got[0]))
    else:
        ok("%d lines, weighted sum %d == reported total" % (len(seen), total))


# --------------------------------------------------------------- 5. refusals

def check_refusals():
    print("5. inputs that would silently give a wrong number are REFUSED")
    if not os.path.exists(WTURNS):
        return
    answers, weights = ordered_answers(WEIGHT_SETS["spiky"])
    tmp = tempfile.mkdtemp(prefix="checkwgt-ref-")
    make_mini_data(tmp, answers)
    good = os.path.join(tmp, "w.txt")
    write_weights(good, answers, weights)

    def refuses(label, args, wfile=None, body=None):
        if body is not None:
            wfile = os.path.join(tmp, label + ".txt")
            open(wfile, "w").write(body)
        full = list(args) + (["--weights", wfile] if wfile else [])
        r = run(WTURNS, full + ["--opener", "slate"], data=tmp)
        if r.returncode == 0:
            bad("accepted %s" % label)
        else:
            ok("refused %s" % label)

    refuses("no --weights", ["--depth", "5"])
    refuses("no --depth", [], wfile=good)
    refuses("unsorted weights", ["--depth", "5"],
            body="".join("%s %d\n" % (w, i + 1) for i, w in enumerate(answers)))
    refuses("a zero weight", ["--depth", "5"],
            body="".join("%s %d\n" % (w, 0 if i == 3 else 8) for i, w in enumerate(answers)))
    refuses("a non-dyadic weight", ["--depth", "5"],
            body="".join("%s %s\n" % (w, "5/3" if i == 0 else "1") for i, w in enumerate(answers)))
    refuses("a word out of position", ["--depth", "5"],
            body="".join("%s 1\n" % w for w in reversed(answers)))
    if os.path.exists(OPTTURNS):
        r = run(OPTTURNS, ["--depth", "5", "--weights", good, "--opener", "slate"], data=tmp)
        if r.returncode == 0:
            bad("unweighted optturns accepted --weights")
        else:
            ok("refused --weights on the unweighted binary")


def main():
    argv = sys.argv[1:]
    full = "--full" in argv
    # depth 2 is in the default list so the cap actually BINDS somewhere and the
    # INFEASIBLE branch is compared, not merely available (check 3 asserts it).
    depths = [2, 3, 4, 5]
    if "--depths" in argv:
        depths = [int(x) for x in argv[argv.index("--depths") + 1].split(",")]
    check_uniform(full)
    check_search(depths, full)
    check_tree()
    check_refusals()
    print()
    if FAILED:
        print("FAILED (%d)" % len(FAILED))
        return 1
    print("all weighted checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
