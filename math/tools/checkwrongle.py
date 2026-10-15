"""checkwrongle.py -- the GATE for solver/wrongle.c and math/wrongle.py.

Run it after any change to either, alongside `tools/checkpatterns.py`.  Every
check diffs the C against something that shares none of its machinery:

  A. THE VALUE, exact, against `wrongle.py` -- which recomputes every legal set
     FROM THE STRINGS, from the whole guess list, at every step, so it never
     relies on "the legal set is the state" the way the C does.  Small
     guess/answer lists plus their own square matrix; per-opener values must be
     EQUAL (integers), both objectives, several caps.
  B. PRUNING changes nothing: --no-prune gives the same numbers.
  C. THE BEAM against the reference's beam at several K -- per opener, and the
     sweep's root selection (which K openers, and the best of them).
  D. THE SWEEP: best value and tie list equal the reference's maximum over all
     openers, with cuts actually taken.
  E. Beam <= exact, opener by opener (the beam is a lower bound).
  F. RESUME from a half-written CSV gives the same final answer; a CSV written
     for a different question is REFUSED.
  G. The refusals: no objective, lose without --depth, expect with --depth, no
     --out.
  H. The real square matrix the binary loads by default, spot-checked against
     `wordle.pattern` from the strings.
  T. --trace: every traced losing line replayed FROM THE STRINGS -- legal and
     consistent at every step, the recorded tiles the real feedback, the lost
     answers never played and exactly the answers consistent with the line, and
     the traced openers/values the ones the run reported.

COVERAGE is asserted at the end: it FAILS unless the beam fell below the exact
value somewhere, an opener lost everything AND one lost nothing, the sweep cut
something, and an exact tie between openers occurred.
"""
import argparse
import os
import random
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.dirname(HERE)
sys.path.insert(0, MATH)

import wordle                                         # noqa: E402
import wrongle                                        # noqa: E402

SOLVER = os.path.join(MATH, "solver", "wrongle")
FAILS = []
COVER = {"beam below exact": 0, "opener lost nothing": 0, "opener lost some": 0,
         "sweep cut": 0, "tied openers": 0, "non-answer opener solved": 0,
         "traced lines": 0, "traced line losing several": 0}


def fail(msg):
    FAILS.append(msg)
    print("FAIL " + msg)


# ------------------------------------------------------------- small problems

def make_case(rng, nguess, nans):
    """A CLUSTER of similar words, so consistent play lasts several guesses --
    random words split each other to singletons at once and exercise nothing."""
    guess = wordle.load_words("guess")
    mystery = set(wordle.load_words("mystery"))
    while True:
        centre = rng.choice(sorted(mystery))
        near = [w for w in guess if sum(a == b for a, b in zip(w, centre)) >= 2]
        ans = [w for w in near if w in mystery]
        if len(ans) >= nans and len(near) >= nguess:
            break
    answers = sorted(rng.sample(ans, nans))
    rest = [w for w in near if w not in answers]
    guesses = sorted(set(answers) | set(rng.sample(rest, nguess - nans)))
    return guesses, answers


def write_case(tmp, guesses, answers, tag):
    gpath = os.path.join(tmp, "g_%s.txt" % tag)
    apath = os.path.join(tmp, "a_%s.txt" % tag)
    ppath = os.path.join(tmp, "p_%s.npy" % tag)
    with open(gpath, "w") as f:
        f.write("\n".join(guesses) + "\n")
    with open(apath, "w") as f:
        f.write("\n".join(answers) + "\n")
    codes = wordle.to_codes(guesses)
    pat = np.stack([wordle.pattern_row(g, codes) for g in guesses]).astype(np.uint8)
    np.save(ppath, pat)
    return gpath, apath, ppath


_ROW = re.compile(r"^(\w+) (lost|total)=(\d+)")
_BEST = re.compile(r"^BEST \w+ = (\d+).*attained by:(.*)$")


def run(case, objective, depth=None, topk=0, openers=(), prune=True, out=None,
        expect_rc=0, extra=()):
    gpath, apath, ppath = case
    cmd = [SOLVER, "--guess-list", gpath, "--answer-list", apath,
           "--patterns", ppath, "--objective", objective,
           "--tt-bits", "18", "--threads", "1"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    if topk:
        cmd += ["--topk", str(topk)]
    for w in openers:
        cmd += ["--opener", w]
    if not prune:
        cmd += ["--no-prune"]
    cmd += ["--out", out] if out else ["--no-out"]
    cmd += list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MATH)
    if p.returncode != expect_rc:
        fail("wrongle exited %d (wanted %d): %s" % (p.returncode, expect_rc,
                                                    p.stderr.strip()[-300:]))
        return {}, None, []
    vals, best, ties = {}, None, []
    for line in p.stdout.splitlines():
        m = _ROW.match(line)
        if m:
            vals[m.group(1)] = int(m.group(3))
        m = _BEST.match(line)
        if m:
            best, ties = int(m.group(1)), m.group(2).split()
    return vals, best, ties


def settings(depths):
    return [("lose", d) for d in depths] + [("expect", None)]


def check_exact(case, game, depths):
    guesses = game.guesses
    exact = {}
    for obj, d in settings(depths):
        vals, _, _ = run(case, obj, d, openers=guesses)
        raw, _, _ = run(case, obj, d, openers=guesses, prune=False)
        tag = "%s d=%s" % (obj, d)
        if vals != raw:
            fail("B %s: pruned and --no-prune disagree" % tag)
        ref = {g: game.opener_value(obj, g, d) for g in guesses}
        bad = [g for g in guesses if vals.get(g) != ref[g]]
        if bad:
            fail("A %s: %d openers differ, e.g. %s C=%s ref=%s"
                 % (tag, len(bad), bad[0], vals.get(bad[0]), ref[bad[0]]))
        else:
            print("ok A/B %s: %d openers equal the reference (max %d)"
                  % (tag, len(guesses), max(ref.values())))
        if obj == "lose":
            na = len(game.answers)
            COVER["opener lost nothing"] += sum(v == 0 for v in ref.values())
            COVER["opener lost some"] += sum(0 < v for v in ref.values())
            del na
        exact[(obj, d)] = ref
    return exact


def check_beam(case, game, depths, exact, ks):
    guesses = game.guesses
    for obj, d in settings(depths):
        for k in ks:
            tag = "%s d=%s K=%d" % (obj, d, k)
            vals, _, _ = run(case, obj, d, topk=k, openers=guesses)
            ref = {g: game.opener_value(obj, g, d, topk=k) for g in guesses}
            bad = [g for g in guesses if vals.get(g) != ref[g]]
            if bad:
                fail("C %s: %d openers differ, e.g. %s C=%s ref=%s"
                     % (tag, len(bad), bad[0], vals.get(bad[0]), ref[bad[0]]))
            ex = exact[(obj, d)]
            over = [g for g in guesses if ref[g] > ex[g]]
            if over:
                fail("E %s: beam above exact for %s" % (tag, over[:3]))
            COVER["beam below exact"] += sum(ref[g] < ex[g] for g in guesses)
            # the sweep: the root is beamed too
            _, best, ties = run(case, obj, d, topk=k)
            roots = game.openers(topk=k)
            rbest = max(ref[g] for g in roots)
            rties = sorted(g for g in roots if ref[g] == rbest)
            if best != rbest or sorted(ties) != rties:
                fail("C %s sweep: C best %s %s, ref %s %s" % (tag, best, ties, rbest, rties))
            else:
                print("ok C/E %s: per opener and sweep (best %d of %d examined)"
                      % (tag, rbest, len(roots)))


def check_sweep(case, game, depths, exact, tmp):
    for obj, d in settings(depths):
        tag = "%s d=%s" % (obj, d)
        ex = exact[(obj, d)]
        rbest = max(ex.values())
        rties = sorted(g for g, v in ex.items() if v == rbest)
        out = os.path.join(tmp, "sweep_%s_%s.csv" % (obj, d))
        if os.path.exists(out):
            os.remove(out)
        _, best, ties = run(case, obj, d, out=out)
        if best != rbest or sorted(ties) != rties:
            fail("D %s: C %s %s, ref %s %s" % (tag, best, ties, rbest, rties))
            continue
        rows = open(out).read().splitlines()
        cuts = sum(",cut," in r for r in rows)
        COVER["sweep cut"] += cuts
        if len(rties) > 1:
            COVER["tied openers"] += 1
        COVER["non-answer opener solved"] += sum(
            1 for r in rows[2:] if ",solved," in r and r.split(",")[0] not in game.answers)
        print("ok D %s: best %d, ties %s, %d cut" % (tag, rbest, rties, cuts))

        # F: resume from a half-written file
        keep = rows[:2] + rows[2:2 + max(1, (len(rows) - 2) // 2)]
        with open(out, "w") as f:
            f.write("\n".join(keep) + "\n")
        _, best2, ties2 = run(case, obj, d, out=out)
        if best2 != rbest or sorted(ties2) != rties:
            fail("F %s: resume gave %s %s, wanted %s %s" % (tag, best2, ties2, rbest, rties))
        else:
            print("ok F %s: resumed from %d rows to the same answer" % (tag, len(keep) - 2))
        if obj == "lose":
            run(case, obj, d + 1, out=out, expect_rc=2)       # foreign stamp: refused


def tiles_of(code):
    """The G/Y/- string of a pattern code, position 0 first (the C's format)."""
    s = []
    for _ in range(5):
        s.append("-YG"[code % 3])
        code //= 3
    return "".join(reversed(s))


def check_trace(case, game, depths, ks, tmp):
    """T: every --trace line, replayed FROM THE STRINGS.  For each opener that
    loses answers: the line starts with it and has exactly D guesses; every guess
    is in the guess list and consistent with every earlier clue (the legality
    rule); every recorded tile string is the real feedback against each lost
    answer; no lost answer is ever played; and the lost set is EXACTLY the
    answers consistent with the whole line.  The traced openers and their values
    must be the ones the run itself reported."""
    gset, aset = set(game.guesses), set(game.answers)
    for d in depths:
        for k in [0] + list(ks):
            tag = "lose d=%d K=%d" % (d, k)
            tpath = os.path.join(tmp, "trace_%d_%d.csv" % (d, k))
            if os.path.exists(tpath):
                os.remove(tpath)
            vals, _, _ = run(case, "lose", d, topk=k, openers=game.guesses,
                             extra=["--trace", tpath])
            want = {g: v for g, v in vals.items() if v > 0}
            rows = open(tpath).read().splitlines()[1:] if os.path.exists(tpath) else []
            got = {}
            bad = []
            for r in rows:
                opener, lost, line, lost_ans = r.split(",")
                got[opener] = int(lost)
                steps = [s.split(":") for s in line.split()]
                words = [w for w, _ in steps]
                lost_set = set(lost_ans.split())
                if words[0] != opener or len(words) != d:
                    bad.append("%s: line %s" % (opener, line)); continue
                for i, (w, t) in enumerate(steps):
                    if w not in gset:
                        bad.append("%s: %s not a guess" % (opener, w))
                    for j in range(i):
                        if tiles_of(wordle.pattern(steps[j][0], w)) != steps[j][1]:
                            bad.append("%s: guess %d %s breaks clue %d" % (opener, i + 1, w, j + 1))
                    for a in lost_set:
                        if tiles_of(wordle.pattern(w, a)) != t:
                            bad.append("%s: %s against lost %s is not %s" % (opener, w, a, t))
                if lost_set & set(words):
                    bad.append("%s: a lost answer was played" % opener)
                consistent = {a for a in aset
                              if all(tiles_of(wordle.pattern(w, a)) == t for w, t in steps)}
                if consistent != lost_set or not lost_set:
                    bad.append("%s: lost %s, consistent %s" % (opener, sorted(lost_set), sorted(consistent)))
                COVER["traced lines"] += 1
                if len(lost_set) > 1:
                    COVER["traced line losing several"] += 1
            if got != want:
                fail("T %s: traced %s, run reported %s" % (tag, got, want))
            elif bad:
                fail("T %s: %d bad, e.g. %s" % (tag, len(bad), bad[0]))
            else:
                print("ok T %s: %d losing lines replayed from the strings" % (tag, len(rows)))


def check_refusals(case):
    gpath, apath, ppath = case
    base = [SOLVER, "--guess-list", gpath, "--answer-list", apath, "--patterns", ppath]
    for extra, why in [(["--no-out"], "no objective"),
                       (["--objective", "lose", "--no-out"], "lose without --depth"),
                       (["--objective", "expect", "--depth", "3", "--no-out"], "expect with --depth"),
                       (["--objective", "lose", "--depth", "3"], "no --out"),
                       (["--objective", "expect", "--opener", "aahed", "--no-out",
                         "--trace", "/dev/null"], "--trace under expect"),
                       (["--objective", "lose", "--depth", "3", "--no-out",
                         "--trace", "/dev/null"], "--trace without --opener")]:
        p = subprocess.run(base + extra, capture_output=True, text=True, cwd=MATH)
        if p.returncode != 2:
            fail("G %s: exited %d, wanted 2" % (why, p.returncode))
    print("ok G: refusals")


def check_real_matrix(rng, n=3000):
    path = os.path.join(MATH, "data", "local", "patterns", "patterns_full.npy")
    if not os.path.exists(path):
        fail("H: %s missing -- python3 build_patterns.py --full" % path)
        return
    m = np.load(path, mmap_mode="r")
    guess = wordle.load_words("guess")
    if m.shape != (len(guess), len(guess)):
        fail("H: matrix shape %s" % (m.shape,))
        return
    bad = 0
    for _ in range(n):
        i, j = rng.randrange(len(guess)), rng.randrange(len(guess))
        bad += int(m[i, j]) != wordle.pattern(guess[i], guess[j])
    if bad:
        fail("H: %d of %d sampled entries disagree with wordle.pattern" % (bad, n))
    else:
        print("ok H: %d sampled square-matrix entries match the strings" % n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guesses", type=int, default=40)
    ap.add_argument("--answers", type=int, default=16)
    ap.add_argument("--depth", type=int, nargs="+", default=[2, 3, 4])
    ap.add_argument("--k", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--cases", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261014)
    args = ap.parse_args()
    if not os.path.exists(SOLVER):
        raise SystemExit("no solver/wrongle -- run 'sh build.sh' in solver/")
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "checkwrongle")
    os.makedirs(tmp, exist_ok=True)
    rng = random.Random(args.seed)

    for ci in range(args.cases):
        guesses, answers = make_case(rng, args.guesses, args.answers)
        print("\ncase %d: %d guesses, %d answers, e.g. %s"
              % (ci, len(guesses), len(answers), " ".join(answers[:6])))
        case = write_case(tmp, guesses, answers, str(ci))
        game = wrongle.Game(guesses, answers)
        exact = check_exact(case, game, args.depth)
        check_beam(case, game, args.depth, exact, args.k)
        check_sweep(case, game, args.depth, exact, tmp)
        check_trace(case, game, args.depth, args.k, tmp)
        if ci == 0:
            check_refusals(case)
    check_real_matrix(rng)

    print("\ncoverage: " + ", ".join("%s %d" % kv for kv in COVER.items()))
    for k, v in COVER.items():
        if v == 0:
            fail("coverage: '%s' never happened -- the check proves less than it looks" % k)
    if FAILS:
        print("\n%d FAILURES" % len(FAILS))
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
