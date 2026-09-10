"""Differential gate for `optturns --kth-random` -- the cost of ONE random guess.

The mode plays a committed optimal tree for k-1 guesses, then a word drawn
uniformly from ALL legal guesses, then optimal play again, and totals that over
every (answer, random word) pair.  Three things in it can be wrong while still
printing a plausible number, so none of them is trusted:

  1. THE STATE.  Reading the tree file and turning its lines into the candidate
     set alive at ply k-1.  A misread prefix gives a state that is merely
     PLAUSIBLE, never an error.
  2. THE ACCOUNTING.  Which pairs pay k, which pay their tree line, which pay
     nothing because the random word won, and what an infeasible bucket does to
     the mean.  The C aggregates PER BUCKET (summing solve()'s value over a
     whole bucket at once); the reference below plays PER PAIR, walking one
     answer down an optimal continuation and counting its guesses.  Two routes
     to one integer, which is what makes the diff worth running.
  3. THE CAP.  It is counted from the START of the game, so the continuation
     gets depth-k guesses and INFEASIBLE is an expected result -- and an
     infeasible pair has no optimum at all, so it must leave the mean rather
     than enter it at some large value.
  4. THE POOL.  `--random-pool all` draws from every legal word and is a
     RECTANGLE -- every answer sees the same 12972, so the total is an integer.
     `compatible` draws from the words still consistent, i.e. the state itself,
     so each answer's draw has its own denominator |S_a| and the mean is a sum
     of fractions.  The C sums that in long double; the reference below rebuilds
     it as an exact Fraction and they must agree.

Five checks:

  A. THE DEGENERATE END, on the REAL lists and free.  A k past the tree's own
     depth leaves no live game for the random guess to spoil, so the mean must
     be exactly the opener's own -- salet 7920/2315 = 3.42117 -- under BOTH
     pools, since there is no random guess left to draw.  Instant, and it
     exercises the real tree reader.

  B. THE SEARCH AND THE ACCOUNTING, against brute force.  A miniature complete
     `--data` directory, so the mode reads a small problem by its NORMAL path,
     diffed against a plain memoised min-over-guesses recursion that shares none
     of the C's bounds, ordering or closed forms -- and that recomputes every
     pattern FROM THE STRINGS with `wordle.pattern` rather than reading the
     matrix.  Several k, several depths, both the solved and INFEASIBLE branches.

  C. COVERAGE, ASSERTED.  A run that never met the awkward cases proves nothing,
     so this FAILS unless an INFEASIBLE pair actually occurred, unless an answer
     actually finished before guess k, unless a random word actually WAS the
     answer, and unless a state with two or more candidates actually arose.

  D. THE REFUSALS.  Seven ways to be handed an input that would silently mean
     something else: no --out, no --depth, k past the cap, k=1 with a tree, k>1
     without one, --topk, and a non-normal binary.  Each must EXIT, not absorb.

  E. THE TREE CHECKS.  The two always-on checks inside the C -- that the file is
     one STRATEGY, and that each group IS the consistent set -- are exercised by
     handing it trees deliberately broken in each way.

  F. THE STANDING ORACLE, opportunistically.  If a real k=1 row has been
     computed, it must equal the committed opener_totals.csv averaged over the
     right opener set: with no prefix to play, k=1 IS the opener sweep averaged
     -- over all 12972 under `all`, over the 2315 answer words under
     `compatible`.  Skipped with a note when no such row exists yet, since
     computing one is a run of its own.

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

from wordle import pattern                                    # noqa: E402

OPTTURNS = os.path.join(MATH, "solver", "optturns")
HARDTURNS = os.path.join(MATH, "solver", "hardturns")

FAILED = []


def bad(msg):
    print("   FAIL " + msg)
    FAILED.append(msg)


def ok(msg):
    print("   ok   " + msg)


# ------------------------------------------------------------ the mini problem
#
# Sized so the checks BITE.  A problem the greedy solves perfectly, or one whose
# cap never binds, would pass check B four times over while exercising nothing --
# so the answer list is deliberately full of near-anagrams and repeated-letter
# words, and check C fails if the awkward cases still did not fire.

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


def make_mini_data(tmp):
    """A complete miniature `--data` directory: the mode then reads a small
    problem by its ordinary path, with no special flags, so the code under test
    is the code that runs for real."""
    words = os.path.join(tmp, "shared", "words")
    pats = os.path.join(tmp, "local", "patterns")
    os.makedirs(words, exist_ok=True)
    os.makedirs(pats, exist_ok=True)
    with open(os.path.join(words, "guess.txt"), "w") as f:
        f.write("\n".join(MINI_GUESSES) + "\n")
    with open(os.path.join(words, "mystery.txt"), "w") as f:
        f.write("\n".join(MINI_ANSWERS) + "\n")
    mat = np.array([[pattern(g, a) for a in MINI_ANSWERS] for g in MINI_GUESSES],
                   dtype=np.uint8)
    np.save(os.path.join(pats, "patterns.npy"), mat)


def run(args, data=None, binary=OPTTURNS):
    cmd = [binary, "--threads", "1"] + (["--data", data] if data else [])
    if "--tt-bits" not in args:
        cmd += ["--tt-bits", "20"]
    return subprocess.run(cmd + args, capture_output=True, text=True)


def read_csv(path):
    rows = []
    with open(path) as f:
        head = f.readline().strip().split(",")
        for line in f:
            rows.append(dict(zip(head, line.strip().split(","))))
    return rows


# ----------------------------------------------------------------- the reference
#
# Everything below recomputes patterns FROM THE STRINGS with wordle.pattern, so
# it shares no matrix, no index and no bound with the C.

MAT = None                       # MAT[g][a], filled per problem
# Answer index -> that word's index in the GUESS list.  A candidate is picked out
# of an answer-indexed set and then PLAYED, so it has to cross into guess space
# first; skipping the map reads the wrong row and scores a different game.
ANS2G = None


def _bucket(g, a, cands):
    p = MAT[g][a]
    return tuple(x for x in cands if MAT[g][x] == p)


@functools.lru_cache(maxsize=None)
def opt(cands, d):
    """(minimum total guesses over `cands` within `d`, one attaining guess).

    A plain memoised min-over-guesses recursion -- no lower bound, no ordering,
    no closed forms, no transposition subtleties.  (None, None) when the cap
    cannot be met, which is the C's INFEASIBLE."""
    n = len(cands)
    if n == 0:
        return 0, None
    if d < 1:
        return None, None
    if n == 1:
        return 1, ANS2G[cands[0]]               # play it: an ANSWER index is not a guess
    best, bestg = None, None
    for g in range(len(MINI_GUESSES)):
        parts = {}
        for a in cands:
            parts.setdefault(MAT[g][a], []).append(a)
        if len(parts) == 1 and WIN not in parts:
            continue                            # splits nothing, cannot help
        total, good = n, True                   # everyone alive pays this guess
        for p, kids in parts.items():
            if p == WIN:
                continue                        # that answer is done, already paid
            sub, _ = opt(tuple(kids), d - 1)
            if sub is None:
                good = False
                break
            total += sub
        if good and (best is None or total < best):
            best, bestg = total, g
    return best, bestg


def play_cost(cands, d, a):
    """Guesses this ONE answer spends under an optimal continuation, or None.

    Per-answer, deliberately: the C never computes this, it sums whole buckets.
    Which optimal guess `opt` returns can change an individual answer's depth,
    but never the sum over a whole bucket -- and every comparison here is over
    whole buckets."""
    v, g = opt(cands, d)
    if v is None:
        return None
    if MINI_GUESSES[g] == MINI_ANSWERS[a]:
        return 1
    sub = play_cost(_bucket(g, a, cands), d - 1, a)
    assert sub is not None, "an optimal guess left an infeasible child"
    return 1 + sub


def read_tree(path):
    """{answer: (nguesses, [(guess, patternstring), ...])} straight from the file."""
    out = {}
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            ans, n, rest = t[0], int(t[1]), t[2:]
            steps = [(rest[i], rest[i + 1]) for i in range(0, len(rest) - 1, 2)]
            out[ans] = (n, steps)
    return out


def pat_str(code):
    """The solver's own pattern spelling: base 3, position 0 the MOST significant."""
    out = []
    for _ in range(5):
        out.append("byg"[code % 3])
        code //= 3
    return "".join(reversed(out))


def reference(tree, K, depth, pool):
    """The whole quantity, per PAIR, with the state re-derived by FILTERING.

    Returns (exact mean as a Fraction, exact integer total or None, infeasible
    pair count, coverage tally).

    The ANSWER-weighted mean is the honest one under either pool: each answer
    carries weight 1 and spreads it evenly over the words ITS OWN pool offers.
    Under `all` every pool is the same 12972, so that collapses to a plain
    integer total over the rectangle -- returned alongside, because the C
    computes it that way and the two must agree."""
    kpre = K - 1
    dres = depth - K
    num, den, inf_w = Fraction(0), Fraction(0), Fraction(0)
    total, infeas = 0, 0
    cov = {"early": 0, "won_at_k": 0, "infeasible": 0, "big_state": 0}
    for a, aw in enumerate(MINI_ANSWERS):
        n, steps = tree[aw]
        if n <= kpre:
            total += n * len(MINI_GUESSES)      # r is never played
            num += n
            den += 1
            cov["early"] += 1
            continue
        prefix = steps[:kpre]
        # the state, by FILTERING the answer list through the prefix from the
        # strings -- nothing to do with how the C grouped the file's lines
        S = tuple(i for i, x in enumerate(MINI_ANSWERS)
                  if all(pat_str(pattern(g, x)) == p for g, p in prefix))
        assert a in S
        if len(S) >= 2:
            cov["big_state"] += 1
        pool_g = (range(len(MINI_GUESSES)) if pool == "all"
                  else [MINI_GUESSES.index(MINI_ANSWERS[x]) for x in S])
        m = len(pool_g)
        for r in pool_g:
            if MINI_GUESSES[r] == aw:
                total += K                      # the random word WAS the answer
                num += Fraction(K, m)
                den += Fraction(1, m)
                cov["won_at_k"] += 1
                continue
            B = _bucket(r, a, S)
            c = play_cost(B, dres, a) if dres >= 1 else None
            if c is None:
                infeas += 1
                inf_w += Fraction(1, m)
                cov["infeasible"] += 1
            else:
                total += K + c
                num += Fraction(K + c, m)
                den += Fraction(1, m)
    mean = num / den if den else Fraction(0)
    lb = (num + (depth + 1) * inf_w) / len(MINI_ANSWERS)
    return mean, lb, (total if pool == "all" else None), infeas, cov


# --------------------------------------------------------------------- checks

def check_degenerate_end():
    """A: on the REAL lists, a k past the tree's depth must reproduce the
    opener's own total exactly -- there is no live game left to spoil."""
    print("A. the degenerate end, on the real lists")
    tree = os.path.join(MATH, "data", "shared", "optturns", "trees", "salet.txt.gz")
    if not os.path.exists(tree):
        print("   skip  no committed salet tree")
        return
    with tempfile.TemporaryDirectory(prefix="checkkth-real-") as tmp:
        for pool in ("all", "compatible"):
            out = os.path.join(tmp, "k_%s.csv" % pool)
            r = run(["--kth-random", "6", "--depth", "6", "--random-pool", pool,
                     "--tree-file", tree, "--out", out, "--tt-bits", "20"])
            if r.returncode != 0 or not os.path.exists(out):
                bad("k=6 %s on the real lists: %s"
                    % (pool, (r.stderr.strip().splitlines() or [""])[-1]))
                continue
            row = read_csv(out)[0]
            if abs(float(row["mean"]) - 7920 / 2315) > 5.01e-7:
                bad("k=6 %s mean %s, expected salet's own 3.421166" % (pool, row["mean"]))
            elif pool == "all" and int(row["total"]) != 7920 * 12972:
                bad("k=6 all total %s, expected %d (salet 7920 x 12972)"
                    % (row["total"], 7920 * 12972))
            elif float(row["pct_infeasible"]) != 0.0:
                bad("k=6 %s reported infeasible weight; the tree resolves every answer"
                    % pool)
            else:
                ok("k=6 %s = salet's own 7920/2315 = %s" % (pool, row["mean"]))


SEEN_MEANS = {}          # (opener, k, depth) -> {pool: exact mean}


def check_search(tmp, tree_path, tree, cases, label, seen, pool):
    """B: the C against the per-pair reference, folding into the coverage tally."""
    for K, depth in cases:
        opt.cache_clear()
        want_mean, want_lb, want_total, want_infeas, cov = reference(tree, K, depth, pool)
        for k in seen:
            seen[k] += cov[k]
        SEEN_MEANS.setdefault((label, K, depth), {})[pool] = want_mean
        tag = "%s_%s_k%d_d%d" % (label, pool, K, depth)
        out = os.path.join(tmp, tag + ".csv")
        states = os.path.join(tmp, tag + "_states.csv")
        args = ["--kth-random", str(K), "--depth", str(depth), "--random-pool", pool,
                "--out", out, "--kth-states", states]
        if K > 1:
            args += ["--tree-file", tree_path]
        r = run(args, data=tmp)
        if r.returncode != 0 or not os.path.exists(out):
            bad("%s %s k=%d depth=%d did not run: %s"
                % (label, pool, K, depth, (r.stderr.strip().splitlines() or [""])[-1]))
            continue
        row = read_csv(out)[0]
        why = []
        # The CSV carries six decimals, so the most it can be out by is half a
        # unit in the last place.  That is all this compares; the EXACT value is
        # checked against the per-state integers just below, which is where a
        # real disagreement would show.
        SIXDP = 5.01e-7
        if abs(float(row["mean"]) - float(want_mean)) > SIXDP:
            why.append("mean %s/%.9f" % (row["mean"], float(want_mean)))
        if abs(float(row["lb_mean"]) - float(want_lb)) > SIXDP:
            why.append("lb_mean %s/%.9f" % (row["lb_mean"], float(want_lb)))
        if want_total is not None and int(row["total"]) != want_total:
            why.append("total %s/%d" % (row["total"], want_total))
        if want_total is None and row["total"] != "":
            why.append("an integer grid total was written for a pool that has none")
        # THE EXACT CHECK.  Rebuild the mean as a Fraction from the per-state
        # INTEGERS the C wrote, which is the only representation of it that is
        # not a double, and require it to be the reference's exact value.
        exact = exact_from_states(states, K, tree, depth)
        if exact is None:
            why.append("no per-state file")
        elif exact != want_mean:
            why.append("exact %s/%s" % (exact, want_mean))
        got_infeas = row["infeasible_pairs"]
        if pool == "all" and int(got_infeas) != want_infeas:
            why.append("infeasible %s/%d" % (got_infeas, want_infeas))
        if why:
            bad("%s %s k=%d depth=%d: %s (C/reference)"
                % (label, pool, K, depth, "; ".join(why)))
        else:
            ok("%s %s k=%d depth=%d: mean %s exact %s"
               % (label, pool, K, depth, row["mean"], want_mean))


def exact_from_states(path, K, tree, depth):
    """The mean rebuilt as an exact Fraction from the C's per-state INTEGERS.

    This is what makes the long-double summary trustworthy: the committed
    per-state file is integers only, so the rational value is recoverable
    however it was printed.  The early-finishing answers are not in that file --
    they never reach the random guess -- so they come from the tree."""
    if not os.path.exists(path):
        return None
    num, den = Fraction(0), Fraction(0)
    for row in read_csv(path):
        n, m = int(row["n"]), int(row["m"])
        u, inf = int(row["u"]), int(row["infeasible"])
        num += Fraction(K * (n * m - inf) + u, m)
        den += Fraction(n * m - inf, m)
    for aw, (n, steps) in tree.items():
        if n <= K - 1:
            num += n
            den += 1
    return num / den if den else None
def check_coverage(seen):
    """C: a run that never met the awkward cases proves nothing about them."""
    print("C. coverage, asserted")
    for name, msg in (("early", "an answer finishing before guess k"),
                      ("won_at_k", "the random word BEING the answer"),
                      ("infeasible", "a pair the cap rules out"),
                      ("big_state", "a state with two or more candidates")):
        if seen[name]:
            ok("%s occurred (%d)" % (msg, seen[name]))
        else:
            bad("%s NEVER occurred -- the check proves nothing about it" % msg)
    # THE POOL HAS TO MATTER SOMEWHERE.  If every case happened to give the same
    # answer under both pools, twenty passing diffs would say nothing at all
    # about which pool the C actually drew from.
    differed = [key for key, v in SEEN_MEANS.items()
                if len(v) == 2 and v["all"] != v["compatible"]]
    if differed:
        ok("the two pools gave different answers (%d of %d cases)"
           % (len(differed), len(SEEN_MEANS)))
    else:
        bad("the two pools NEVER differed -- nothing here distinguishes them")


def check_refusals(tmp, tree_path):
    """D: every input that would quietly mean something else must EXIT."""
    print("D. the refusals")
    out = os.path.join(tmp, "refuse.csv")
    P = ["--random-pool", "all"]
    cases = [
        ("no --out", ["--kth-random", "2", "--depth", "4",
                      "--tree-file", tree_path] + P, OPTTURNS),
        ("no --depth", ["--kth-random", "2", "--tree-file", tree_path,
                        "--out", out] + P, OPTTURNS),
        ("no --random-pool", ["--kth-random", "2", "--depth", "4",
                              "--tree-file", tree_path, "--out", out], OPTTURNS),
        ("an unknown --random-pool", ["--kth-random", "2", "--depth", "4",
                                      "--random-pool", "answers",
                                      "--tree-file", tree_path, "--out", out], OPTTURNS),
        ("k past the cap", ["--kth-random", "5", "--depth", "4",
                            "--tree-file", tree_path, "--out", out] + P, OPTTURNS),
        ("k=1 with a tree", ["--kth-random", "1", "--depth", "4",
                             "--tree-file", tree_path, "--out", out] + P, OPTTURNS),
        ("k>1 with no tree", ["--kth-random", "2", "--depth", "4",
                              "--out", out] + P, OPTTURNS),
        ("--topk", ["--kth-random", "2", "--depth", "4", "--topk", "3",
                    "--tree-file", tree_path, "--out", out] + P, OPTTURNS),
        ("a non-normal binary", ["--kth-random", "2", "--depth", "4",
                                 "--tree-file", tree_path, "--out", out] + P, HARDTURNS),
    ]
    for name, args, binary in cases:
        if not os.path.exists(binary):
            print("   skip  %s (no %s)" % (name, os.path.basename(binary)))
            continue
        r = run(args, data=tmp, binary=binary)
        if r.returncode == 0:
            bad("%s was ACCEPTED" % name)
        else:
            ok("%s refused" % name)
    if os.path.exists(out):
        bad("a refused run still wrote %s" % out)


def _parse_line(ln):
    """(answer, n, [guesses], [patterns]) -- n guesses and n-1 patterns."""
    t = ln.split()
    ans, n, rest = t[0], int(t[1]), t[2:]
    return ans, n, rest[0::2], rest[1::2]


def _render(ans, n, gs, ps):
    out = [ans, str(n)]
    for i, g in enumerate(gs):
        out.append(g)
        if i < len(ps):
            out.append(ps[i])
    return " ".join(out)


def check_broken_trees(tmp, tree_path):
    """E: the two always-on tree checks, each handed a tree broken its own way.

    The checks live inside the C and always run, so nothing else here would ever
    exercise them -- a correct tree passes them silently.  Each case below is
    CONSTRUCTED rather than waited for."""
    print("E. the tree checks")
    lines = [_parse_line(ln) for ln in
             gzip.open(tree_path, "rt").read().splitlines() if ln.strip()]
    out = os.path.join(tmp, "broken.csv")

    def try_tree(name, rows, K, depth):
        path = os.path.join(tmp, name + ".txt")
        with open(path, "w") as f:
            f.write("\n".join(_render(*r) for r in rows) + "\n")
        r = run(["--kth-random", str(K), "--depth", str(depth),
                 "--random-pool", "all", "--tree-file", path, "--out", out], data=tmp)
        if r.returncode == 0:
            bad("%s was ACCEPTED" % name)
        else:
            ok("%s refused" % name)

    # (1) two openers: the file is not one strategy at all
    rows = [list(r) for r in lines]
    rows[0][2] = [next(w for w in MINI_GUESSES if w != rows[0][2][0])] + rows[0][2][1:]
    try_tree("two-openers", rows, 2, 4)

    # (2) one strategy at the root but two different SECOND guesses inside a
    # group -- the deeper half of the same check
    groups = {}
    for i, (ans, n, gs, ps) in enumerate(lines):
        if n >= 3:
            groups.setdefault((ps[0], ps[1]), []).append(i)
    pair = next((v for v in groups.values() if len(v) >= 2), None)
    if pair is None:
        bad("the deeper mini tree has no ply-2 group of two, so the deeper half "
            "of the strategy check went unexercised -- pick another opener")
    else:
        rows = [list(r) for r in lines]
        i = pair[0]
        gs = list(rows[i][2])
        gs[1] = next(w for w in MINI_GUESSES if w != gs[1])
        rows[i][2] = gs
        try_tree("two-second-guesses", rows, 3, 4)

    # (3) a group that is NOT the consistent set: refile one answer under
    # another first-level pattern
    withpat = [i for i, (a, n, gs, ps) in enumerate(lines) if ps]
    pats = {lines[i][3][0] for i in withpat}
    if len(pats) < 2:
        print("   skip  the mini tree has only one first-level bucket")
    else:
        i = withpat[0]
        rows = [list(r) for r in lines]
        ps = list(rows[i][3])
        ps[0] = next(p for p in pats if p != ps[0])
        rows[i][3] = ps
        try_tree("misfiled-answer", rows, 2, 4)

    # (4) a file that does not cover every answer
    try_tree("missing-answer", [list(r) for r in lines[:-1]], 2, 4)

    if os.path.exists(out):
        bad("a refused run still wrote %s" % out)


def check_standing_oracle():
    """F: a real k=1 row, if one exists, must be the opener sweep averaged."""
    print("F. the standing oracle (k=1 against opener_totals.csv)")
    sys.path.insert(0, os.path.join(MATH, "tools"))
    import paths                                              # noqa: E402
    found = []
    d = os.path.join(MATH, "data", "shared", "kthrandom")
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if not name.endswith(".csv"):
                continue
            for row in read_csv(os.path.join(d, name)):
                if row.get("k") == "1":
                    found.append((name, row))
    if not found:
        print("   skip  no k=1 row computed yet "
              "(bash solver/run-kth-random.sh --depth 6 -k 1)")
        return
    totals = {r["word"]: int(r["total"]) for r in paths.read_rows(paths.CSV_PATH)
              if r.get("total")}
    if len(totals) < 12972:
        print("   skip  the opener sweep CSV is not complete (%d rows)" % len(totals))
        return
    answers = set(open(paths.MYSTERY_WORDS).read().split())
    # `all` draws from every legal word, so k=1 is the sweep over all 12972;
    # `compatible` draws from the words still consistent, which at k=1 is the
    # 2315 answers -- so it is the SAME sweep averaged over a different opener
    # set, and quoting one for the other is the mistake this catches.
    want = {"all": sum(totals.values()) / len(totals) / 2315,
            "compatible": (sum(v for w, v in totals.items() if w in answers)
                           / len(answers) / 2315)}
    for name, row in found:
        pool = row.get("pool")
        if pool not in want:
            bad("%s has a k=1 row with pool %r" % (name, pool))
            continue
        if abs(float(row["mean"]) - want[pool]) > 5.01e-7:
            bad("%s k=1 %s mean %s, but the opener sweep averages to %.6f"
                % (name, pool, row["mean"], want[pool]))
        else:
            ok("%s k=1 %s = %.6f = the opener sweep averaged" % (name, pool, want[pool]))


def main():
    global MAT, ANS2G
    if not os.path.exists(OPTTURNS):
        raise SystemExit("no solver/optturns -- run 'sh build.sh' in solver/")
    check_degenerate_end()

    with tempfile.TemporaryDirectory(prefix="checkkth-") as tmp:
        make_mini_data(tmp)
        MAT = [[pattern(g, a) for a in MINI_ANSWERS] for g in MINI_GUESSES]
        ANS2G = [MINI_GUESSES.index(w) for w in MINI_ANSWERS]
        # TWO trees, because one is not enough.  `crane` solves the mini
        # problem in three guesses, so its states at ply 2 are all singletons and
        # a k=3 diff against it exercises nothing but the early-finish path.
        # `roast` needs four, so it has real states down there -- and it is the
        # only tree whose ply-2 groups can break the deeper strategy check.
        paths_by_opener = {}
        for opener in ("crane", "roast"):
            trees = os.path.join(tmp, "trees_" + opener)
            r = run(["--opener", opener, "--depth", "4", "--trees", trees], data=tmp)
            tp = os.path.join(trees, opener + ".txt.gz")
            if r.returncode != 0 or not os.path.exists(tp):
                raise SystemExit("could not emit the mini tree for %s:\n%s"
                                 % (opener, r.stderr))
            paths_by_opener[opener] = tp

        print("B. the search and the accounting, against brute force")
        seen = {"early": 0, "won_at_k": 0, "infeasible": 0, "big_state": 0}
        for pool in ("all", "compatible"):
            for opener, cases in (("crane", [(1, 4), (2, 4), (3, 4), (4, 4),
                                             (2, 3), (3, 3)]),
                                  ("roast", [(2, 4), (3, 4), (4, 4), (2, 3)])):
                check_search(tmp, paths_by_opener[opener],
                             read_tree(paths_by_opener[opener]),
                             cases, opener, seen, pool)
        check_coverage(seen)
        check_refusals(tmp, paths_by_opener["crane"])
        check_broken_trees(tmp, paths_by_opener["roast"])

    check_standing_oracle()

    print()
    if FAILED:
        print("FAILED %d check(s)" % len(FAILED))
        for m in FAILED:
            print("  - " + m)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
