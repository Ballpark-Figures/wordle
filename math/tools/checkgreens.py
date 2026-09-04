"""checkgreens.py -- the GATE for solver/greens.c and math/greens.py.

Run it alongside `solver/validate.sh` and `tools/checkpatterns.py` after any
change to either.  Four independent checks, none of which shares code with the
thing it is checking:

  1. THE BADGE PREDICATE.  `has_yellow` over every one of the 243 codes, and over
     real (guess, answer) pairs, against a tile array recomputed here from the
     STRINGS by a second implementation that does not call `wordle.pattern`.
     One predicate is the whole rule, so it gets its own check.

  2. THE VALUE, against `greens.py`.  Small answer and guess lists plus their own
     pattern matrix, so the C solves the same restricted problem a slow,
     string-based, tuple-of-words reference solves -- and the badge counts must
     agree EXACTLY, opener by opener, at several depths.  The values are integers,
     so this is equality, not a tolerance.

  3. CLAUSE 1, against optturns.  `greens` calls an opener INFEASIBLE exactly
     when it cannot win every answer within the cap -- which is the same question
     `optturns` answers, and optturns is validated against Bertsimas & Paskov.
     So the two must agree on feasibility for every opener tried.  This is the
     check that the win constraint is real rather than decorative.

  4. THE TREE, replayed from the strings.  Every answer covered exactly once,
     every line within the cap (clause 1 again, now per answer), every pattern
     field reproduced, the last guess equal to the answer, the tree a CONSISTENT
     STRATEGY (one next guess per prefix, not a per-answer fabrication), and the
     number of yellow-free lines equal to the badge count the solver reported.

It ends with a COVERAGE TALLY and FAILS if the awkward cases never fired -- a
yellow actually appearing, a line surviving yellow-free, an opener coming back
infeasible, and the badge-vs-win conflict biting (a state where the yellow-free
choice would have lost the game).  A pass that never exercised those would mean
nothing.
"""
import argparse
import gzip
import os
import random
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.dirname(HERE)
sys.path.insert(0, MATH)

import greens                                        # noqa: E402
import wordle                                        # noqa: E402

SOLVER = os.path.join(MATH, "solver", "greens")
OPTTURNS = os.path.join(MATH, "solver", "optturns")

FAILS = []
COVER = {"yellow line": 0, "yellow-free line": 0, "infeasible opener": 0,
         "badge-vs-win conflict": 0, "tied openers": 0, "beam below exact": 0}


def fail(msg):
    FAILS.append(msg)
    print("  FAIL " + msg)


# --------------------------------------------------------------- 1. predicate

def tiles_from_strings(guess, answer):
    """Wordle tiles, recomputed here rather than imported.

    Deliberately a different shape from `wordle.pattern`: it counts the answer's
    spare letters up front and spends them left to right, instead of marking a
    used[] array.  Same rule, independent code.
    """
    spare = {}
    out = [0] * len(guess)
    for i, ch in enumerate(answer):
        if guess[i] == ch:
            out[i] = 2
        else:
            spare[ch] = spare.get(ch, 0) + 1
    for i, ch in enumerate(guess):
        if out[i] == 0 and spare.get(ch, 0) > 0:
            out[i] = 1
            spare[ch] -= 1
    return out


def check_predicate(words):
    print("1. the badge predicate")
    for code in range(3 ** wordle.WORD_LEN):
        want = 1 in wordle.decode(code)
        if greens.has_yellow(code) != want:
            fail("has_yellow(%d) disagrees with the decoded tiles" % code)
            break
    rng = random.Random(20260903)
    pairs = [(rng.choice(words), rng.choice(words)) for _ in range(4000)]
    yellow_free = 0
    for g, a in pairs:
        t = tiles_from_strings(g, a)
        code = 0
        for x in t:
            code = code * 3 + x
        if code != wordle.pattern(g, a):
            fail("tiles disagree with wordle.pattern for %s vs %s" % (g, a))
            break
        if greens.has_yellow(code) != (1 in t):
            fail("has_yellow disagrees with the tiles for %s vs %s" % (g, a))
            break
        yellow_free += 1 not in t
    print("   243 codes + 4000 real pairs; %d of the pairs were yellow-free"
          % yellow_free)
    if yellow_free == 0 or yellow_free == len(pairs):
        fail("the sampled pairs were all one way -- the predicate went untested")


# ------------------------------------------------------------- small problems

def build_case(tmp, answers, guesses, tag):
    """Write a restricted (guess list, answer list, pattern matrix) triple.

    The matrix must have a row per word of the FULL guess list, because the
    solver loads guess.txt and only then compacts it with --guess-list.
    """
    full = wordle.load_words("guess")
    apath = os.path.join(tmp, "ans_%s.txt" % tag)
    gpath = os.path.join(tmp, "gue_%s.txt" % tag)
    ppath = os.path.join(tmp, "pat_%s.npy" % tag)
    with open(apath, "w") as f:
        f.write("\n".join(answers) + "\n")
    with open(gpath, "w") as f:
        f.write("\n".join(guesses) + "\n")
    codes = wordle.to_codes(answers)
    pat = np.empty((len(full), len(answers)), dtype=wordle.pattern_dtype())
    for i, g in enumerate(full):
        pat[i] = wordle.pattern_row(g, codes)
    np.save(ppath, pat)
    return apath, gpath, ppath


_LINE = re.compile(r"^(\w+)\s+badges=(\d+) of (\d+)")


def run_greens(apath, gpath, ppath, depth, openers, treedir=None, topk=0):
    cmd = [SOLVER, "--answer-list", apath, "--guess-list", gpath,
           "--patterns", ppath, "--depth", str(depth), "--no-out",
           "--tt-bits", "20", "--threads", "1"]
    if topk:
        cmd += ["--topk", str(topk)]
    for w in openers:
        cmd += ["--opener", w]
    if treedir:
        cmd += ["--trees", treedir]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MATH)
    if p.returncode != 0:
        fail("greens exited %d: %s" % (p.returncode, p.stderr.strip()[-400:]))
        return {}
    out = {}
    for line in p.stdout.splitlines():
        m = _LINE.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
        elif "INFEASIBLE" in line:
            out[line.split()[0]] = greens.INFEASIBLE
    return out


def run_optturns(apath, gpath, ppath, depth, openers):
    """Feasibility only: optturns reports INFEASIBLE on exactly the same question."""
    if not os.path.exists(OPTTURNS):
        return None
    cmd = [OPTTURNS, "--answer-list", apath, "--guess-list", gpath,
           "--patterns", ppath, "--depth", str(depth), "--depth-max", str(depth),
           "--tt-bits", "20", "--threads", "1"]
    for w in openers:
        cmd += ["--opener", w]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MATH)
    if p.returncode != 0:
        fail("optturns exited %d: %s" % (p.returncode, p.stderr.strip()[-400:]))
        return None
    out = {}
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = ("INFEASIBLE" not in line)
    return out


def check_values(tmp, answers, guesses, depths, openers, values):
    print("2. the badge count, C against the Python reference")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "v")
    cands = tuple(sorted(answers))
    gtuple = tuple(guesses)
    for depth in depths:
        got = run_greens(apath, gpath, ppath, depth, openers)
        for w in openers:
            want = greens.solve_opener(w, cands, gtuple, depth)
            have = got.get(w)
            if have is None:
                fail("greens printed nothing for %s at depth %d" % (w, depth))
            elif have != want:
                fail("depth %d opener %s: C says %s, reference says %s"
                     % (depth, w, have, want))
            if want == greens.INFEASIBLE:
                COVER["infeasible opener"] += 1
            values[(depth, w)] = want
            print("   d=%d %-6s badges=%-4s reference=%-4s %s"
                  % (depth, w, have, want, "ok" if have == want else "MISMATCH"))
    return apath, gpath, ppath


def check_feasibility(apath, gpath, ppath, depths, openers):
    print("3. clause 1 (the win constraint), against optturns")
    for depth in depths:
        mine = run_greens(apath, gpath, ppath, depth, openers)
        theirs = run_optturns(apath, gpath, ppath, depth, openers)
        if theirs is None:
            print("   optturns not built -- skipped")
            return
        for w in openers:
            if w not in mine or w not in theirs:
                continue
            gf = mine[w] != greens.INFEASIBLE
            if gf != theirs[w]:
                fail("depth %d opener %s: greens feasible=%s, optturns feasible=%s"
                     % (depth, w, gf, theirs[w]))
        print("   d=%d %d openers agree on feasibility" % (depth, len(openers)))


# ------------------------------------------------------------------ 4. trees

def check_tree(path, answers, guesses, depth, badges, opener):
    """Replay one emitted tree against the strings; return nothing, record fails."""
    seen = {}
    strategy = {}
    yellow_free = 0
    with gzip.open(path, "rt") as f:
        for lineno, line in enumerate(f, 1):
            parts = line.split()
            if len(parts) < 3:
                fail("%s line %d: short line" % (path, lineno))
                continue
            answer, n = parts[0], int(parts[1])
            gs, ps = parts[2::2], parts[3::2]
            if answer in seen:
                fail("%s: answer %s appears twice" % (path, answer))
            seen[answer] = n
            if len(gs) != n or len(ps) != n - 1:
                fail("%s line %d: says %d guesses, carries %d/%d"
                     % (path, lineno, n, len(gs), len(ps)))
                continue
            if n > depth:
                fail("%s line %d (%s): %d guesses exceeds the %d-guess cap"
                     % (path, lineno, answer, n, depth))
            if gs[0] != opener:
                fail("%s line %d: starts with %s, not the opener %s"
                     % (path, lineno, gs[0], opener))
            if gs[-1] != answer:
                fail("%s line %d: last guess %s is not the answer %s"
                     % (path, lineno, gs[-1], answer))
            for g in gs:
                if g not in guesses:
                    fail("%s line %d: %s is not a legal guess" % (path, lineno, g))
            # every pattern reproduced from the strings, by the independent tiles()
            alive = True
            prefix = ()
            for i, p in enumerate(ps):
                t = tiles_from_strings(gs[i], answer)
                want = "".join("byg"[x] for x in t)
                if want != p:
                    fail("%s line %d: %s vs %s gives %s, tree says %s"
                         % (path, lineno, gs[i], answer, want, p))
                if 1 in t:
                    alive = False
                if prefix in strategy and strategy[prefix] != gs[i]:
                    fail("%s line %d: prefix %s plays both %s and %s -- not a strategy"
                         % (path, lineno, prefix, strategy[prefix], gs[i]))
                strategy[prefix] = gs[i]
                prefix = prefix + (gs[i], p)
            if prefix in strategy and strategy[prefix] != gs[-1]:
                fail("%s line %d: prefix %s plays both %s and %s -- not a strategy"
                     % (path, lineno, prefix, strategy[prefix], gs[-1]))
            strategy[prefix] = gs[-1]
            if alive:
                yellow_free += 1
                COVER["yellow-free line"] += 1
            else:
                COVER["yellow line"] += 1
    missing = set(answers) - set(seen)
    if missing:
        fail("%s: %d answers never appear (%s...)"
             % (path, len(missing), sorted(missing)[:3]))
    if yellow_free != badges:
        fail("%s: tree has %d yellow-free lines, solver reported %d badges"
             % (path, yellow_free, badges))
    else:
        print("   %s: %d answers, all within %d, %d yellow-free -- matches"
              % (os.path.basename(path), len(seen), depth, yellow_free))


def check_trees(tmp, answers, guesses, depth, openers):
    print("4. the emitted tree, replayed from the strings")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "t")
    treedir = os.path.join(tmp, "trees")
    os.makedirs(treedir, exist_ok=True)
    got = run_greens(apath, gpath, ppath, depth, openers, treedir=treedir)
    for w in openers:
        if got.get(w, greens.INFEASIBLE) == greens.INFEASIBLE:
            continue
        p = os.path.join(treedir, w + ".txt.gz")
        if not os.path.exists(p):
            fail("no tree written for %s" % w)
            continue
        check_tree(p, answers, guesses, depth, got[w], w)


# ------------------------------------------------- 5. does clause 1 BIND?

def solve_nowin(cands, guesses, depth, memo):
    """THE OBJECTIVE THE USER DID NOT CHOOSE, and it is here for one reason.

    Pure max P(badge): no requirement to win the games the badge is already lost
    in, so a yellow bucket is simply worth nothing and an unwinnable branch costs
    nothing either.  It is an UPPER BOUND on the real objective, never a result
    -- do not report a number from it.

    Its only job is to prove clause 1 is load-bearing.  If the constrained and
    unconstrained values agreed everywhere, every other check in this file could
    pass with the win constraint deleted.
    """
    n = len(cands)
    if n == 0 or depth <= 0:
        return 0
    if n == 1:
        return 1
    key = (cands, depth)
    if key in memo:
        return memo[key]
    memo[key] = 0
    ag = greens.all_green()
    best = 0
    for g in guesses:
        parts = greens.partition(g, cands)
        if len(parts) == 1:
            continue                       # weaker than doing nothing
        val = 0
        for code, sub in parts.items():
            if code == ag:
                val += 1
            elif not greens.has_yellow(code):
                val += solve_nowin(sub, guesses, depth - 1, memo)
        if val > best:
            best = val
    memo[key] = best
    return best


def check_binds(answers, guesses, depths, openers, values):
    print("5. does the win constraint actually bind?")
    cands = tuple(sorted(answers))
    gtuple = tuple(guesses)
    memo = {}
    for depth in depths:
        for w in openers:
            have = values.get((depth, w))
            if have is None:
                continue
            parts = greens.partition(w, cands)
            free = 0
            for code, sub in parts.items():
                if code == greens.all_green():
                    free += 1
                elif not greens.has_yellow(code):
                    free += solve_nowin(sub, gtuple, depth - 1, memo)
            if have > free:
                fail("d=%d %s: constrained %d exceeds the unconstrained bound %d"
                     % (depth, w, have, free))
            if have < free:
                COVER["badge-vs-win conflict"] += 1
                print("   d=%d %-6s constrained %-4s vs unconstrained %-4s -- binds"
                      % (depth, w, have, free))


# ------------------------------------------------------- 6. the SWEEP itself

_BEST = re.compile(r"^badges = (\d+) of (\d+)")


def run_sweep(apath, gpath, ppath, depth, outpath=None, topk=0):
    cmd = [SOLVER, "--sweep", "--answer-list", apath, "--guess-list", gpath,
           "--patterns", ppath, "--depth", str(depth),
           "--out", outpath] if outpath else [
           SOLVER, "--sweep", "--answer-list", apath, "--guess-list", gpath,
           "--patterns", ppath, "--depth", str(depth), "--no-out"]
    cmd += ["--tt-bits", "20", "--threads", "2"]
    if topk:
        cmd += ["--topk", str(topk)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MATH)
    if p.returncode != 0:
        fail("greens --sweep exited %d: %s" % (p.returncode, p.stderr.strip()[-400:]))
        return None, []
    best, ties, collecting = None, [], False
    for line in p.stdout.splitlines():
        m = _BEST.match(line)
        if m:
            best = int(m.group(1))
            collecting = True
        elif collecting:
            if line.startswith("  ") and line.strip().isalpha():
                ties.append(line.strip())
            else:
                collecting = False
    return best, ties


def check_sweep(tmp, answers, guesses, depth):
    """The bounded screen must find the same winner an exhaustive scan does.

    This is the check that covers the PRUNING: the root bound, the incumbent, the
    cut and the tie list are all only exercised here, and a bound that is too
    tight would silently discard the real winner while every --opener check
    carried on passing.
    """
    print("6. the opener screen, against an exhaustive scan")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "s")
    cands = tuple(sorted(answers))
    gtuple = tuple(guesses)
    every = {w: greens.solve_opener(w, cands, gtuple, depth) for w in guesses}
    want = max(every.values())
    want_ties = sorted(w for w, v in every.items() if v == want)
    best, ties = run_sweep(apath, gpath, ppath, depth)
    if len(want_ties) > 1:
        COVER["tied openers"] += 1
    if best != want:
        fail("screen reports %s, an exhaustive scan of %d openers says %s"
             % (best, len(guesses), want))
    elif sorted(ties) != want_ties:
        fail("screen ties %s, exhaustive ties %s" % (sorted(ties), want_ties))
    else:
        print("   %d openers scanned: best %d, %d tied, screen agrees exactly"
              % (len(guesses), want, len(want_ties)))


# --------------------------------------------------------------- 7. resume

def check_resume(tmp, answers, guesses, depth):
    """A long screen WILL be interrupted, so the resume has to give the same
    answer as an uninterrupted run -- including the tie list, which lives only in
    memory and has to be rebuilt from the CSV."""
    print("7. resume, against an uninterrupted run")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "r")
    csv = os.path.join(tmp, "resume.csv")
    if os.path.exists(csv):
        os.remove(csv)
    best1, ties1 = run_sweep(apath, gpath, ppath, depth, csv)

    lines = open(csv).read().splitlines()
    body = lines[1:]
    open(csv, "w").write("\n".join(lines[:1] + body[: len(body) // 2]) + "\n")
    best2, ties2 = run_sweep(apath, gpath, ppath, depth, csv)
    if (best2, sorted(ties2)) != (best1, sorted(ties1)):
        fail("resume from a half-written CSV gives %s/%s, uninterrupted gives %s/%s"
             % (best2, sorted(ties2), best1, sorted(ties1)))
    best3, ties3 = run_sweep(apath, gpath, ppath, depth, csv)
    if (best3, sorted(ties3)) != (best1, sorted(ties1)):
        fail("resume from a COMPLETE CSV gives %s/%s, uninterrupted gives %s/%s"
             % (best3, sorted(ties3), best1, sorted(ties1)))
    if best2 == best1 == best3:
        print("   %d rows, halved and re-run: same best %d, same %d tied"
              % (len(body), best1, len(ties1)))


# --------------------------------------------------------------- 8. the beam

def check_beam(tmp, answers, guesses, depth, openers):
    """--topk is an APPROXIMATION, so it cannot be checked by "is it optimal?".
    Three things can be checked, and together they pin it:

      - it is DETERMINISTIC and its rule is writable down, so the C and the
        Python reference must agree EXACTLY at each K;
      - every value it reports is achievable, so it can never EXCEED the exact
        value -- and it must sometimes fall below it, or the beam is not
        actually restricting anything and the check proves nothing;
      - at K past the guess count the restriction is vacuous, so it must
        reproduce the exact answer exactly.
    """
    print("8. the --topk beam, against the same rule in the reference")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "k")
    cands = tuple(sorted(answers))
    gtuple = tuple(guesses)
    for topk in (1, 3, 10):
        got = run_greens(apath, gpath, ppath, depth, openers, topk=topk)
        for w in openers:
            want = greens.solve_opener(w, cands, gtuple, depth, topk=topk)
            have = got.get(w)
            if have != want:
                fail("--topk %d opener %s: C says %s, reference says %s"
                     % (topk, w, have, want))
            exact = greens.solve_opener(w, cands, gtuple, depth)
            if want > exact:
                fail("--topk %d opener %s: beam %s EXCEEDS the exact %s -- a beam "
                     "can only find strategies, never invent them" % (topk, w, want, exact))
            if want < exact:
                COVER["beam below exact"] += 1
        print("   K=%-3d %s" % (topk, " ".join("%s=%s" % (w, got.get(w)) for w in openers)))
    big = len(guesses) + 1
    got = run_greens(apath, gpath, ppath, depth, openers, topk=big)
    for w in openers:
        exact = greens.solve_opener(w, cands, gtuple, depth)
        if got.get(w) != exact:
            fail("--topk %d (past the guess count) gives %s for %s, exact is %s"
                 % (big, got.get(w), w, exact))
    print("   K=%d (vacuous): reproduces the exact value for every opener" % big)


def check_beam_sweep(tmp, answers, guesses, depth, topk):
    """The beam picks the OPENERS too, so the winner must be the best of exactly
    the K the rule selects -- not of all of them, and not of some other K."""
    print("9. the beamed opener screen")
    apath, gpath, ppath = build_case(tmp, answers, guesses, "b")
    cands = tuple(sorted(answers))
    gtuple = tuple(guesses)
    examined = greens.opener_order(cands, gtuple)[:topk]
    vals = {w: greens.solve_opener(w, cands, gtuple, depth, topk=topk) for w in examined}
    want = max(vals.values())
    want_ties = sorted(w for w, v in vals.items() if v == want)
    best, ties = run_sweep(apath, gpath, ppath, depth, topk=topk)
    if best != want:
        fail("beamed screen reports %s, the same rule over its %d openers says %s"
             % (best, len(examined), want))
    elif sorted(ties) != want_ties:
        fail("beamed screen ties %s, reference ties %s" % (sorted(ties), want_ties))
    else:
        print("   K=%d: %d openers examined, best %d, %d tied -- agrees exactly"
              % (topk, len(examined), want, len(want_ties)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", type=int, default=18,
                    help="answers in the small case (the reference is slow)")
    ap.add_argument("--guesses", type=int, default=90)
    ap.add_argument("--depth", type=int, nargs="+", default=[2, 3, 4],
                    help="shallow caps are what make clause 1 bite")
    ap.add_argument("--openers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260903)
    args = ap.parse_args()

    if not os.path.exists(SOLVER):
        raise SystemExit("no solver/greens binary -- run 'sh build.sh' in solver/")

    tmp = os.environ.get("TMPDIR", "/tmp")
    tmp = os.path.join(tmp, "checkgreens")
    os.makedirs(tmp, exist_ok=True)

    # depth 2 always rides along: with this many answers it is certainly
    # infeasible, which is what keeps the INFEASIBLE path covered whatever
    # --depth was asked for.
    depths = sorted(set(args.depth) | {2})

    mystery = wordle.load_words("mystery")
    guessall = wordle.load_words("guess")
    rng = random.Random(args.seed)
    answers = sorted(rng.sample(mystery, args.answers))
    extra = [w for w in rng.sample(guessall, args.guesses * 3) if w not in answers]
    guesses = sorted(set(answers) | set(extra[:max(0, args.guesses - len(answers))]))
    openers = guesses[:: max(1, len(guesses) // args.openers)][:args.openers]
    print("case: %d answers, %d guesses, depths %s, openers %s\n"
          % (len(answers), len(guesses), depths, openers))

    values = {}
    check_predicate(guessall)
    apath, gpath, ppath = check_values(tmp, answers, guesses, depths, openers, values)
    check_feasibility(apath, gpath, ppath, depths, openers)
    check_trees(tmp, answers, guesses, max(args.depth), openers)
    check_binds(answers, guesses, depths, openers, values)
    check_sweep(tmp, answers, guesses, max(depths))
    # A second, deliberately SMALLER answer set: ties between openers are common
    # there and rare above, and the tie list is its own code path -- every cut in
    # the screen is strict precisely so a tie survives it.
    check_sweep(tmp, answers[: max(6, len(answers) // 2)], guesses, max(depths))
    check_resume(tmp, answers[: max(6, len(answers) // 2)], guesses, max(depths))
    check_beam(tmp, answers, guesses, max(depths), openers)
    check_beam_sweep(tmp, answers, guesses, max(depths), 5)

    print("\ncoverage: " + ", ".join("%s %d" % (k, v) for k, v in COVER.items()))
    for k, v in COVER.items():
        if v == 0:
            fail("coverage: '%s' never happened -- the check proves less than it looks"
                 % k)
    if FAILS:
        print("\n%d FAILURES" % len(FAILS))
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
