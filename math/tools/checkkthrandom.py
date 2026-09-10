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

Five checks:

  A. THE DEGENERATE END, on the REAL lists and free.  A k past the tree's own
     depth leaves no live game for the random guess to spoil, so the total must
     be exactly the opener's own total times the guess count -- salet: 7920 x
     12972.  Instant, and it exercises the real tree reader.

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
     computed, it must equal the committed opener_totals.csv summed over every
     opener: with no prefix to play, k=1 IS the opener sweep averaged.  Skipped
     with a note when that row does not exist yet, since computing it is a run
     of its own.

Run it alongside `bash solver/validate.sh` and `python3 tools/checkpatterns.py`.
"""

from __future__ import annotations

import functools
import gzip
import os
import subprocess
import sys
import tempfile

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


def reference(tree, K, depth):
    """The whole quantity, per PAIR, with the state re-derived by FILTERING.

    Returns (feasible total, infeasible pair count, coverage tally)."""
    na, ng = len(MINI_ANSWERS), len(MINI_GUESSES)
    kpre = K - 1
    dres = depth - K
    total, infeas = 0, 0
    cov = {"early": 0, "won_at_k": 0, "infeasible": 0, "big_state": 0}
    for a, aw in enumerate(MINI_ANSWERS):
        n, steps = tree[aw]
        if n <= kpre:
            total += n * ng                     # r is never played
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
        for r in range(ng):
            if MINI_GUESSES[r] == aw:
                total += K                      # the random word WAS the answer
                cov["won_at_k"] += 1
                continue
            B = _bucket(r, a, S)
            c = play_cost(B, dres, a) if dres >= 1 else None
            if c is None:
                infeas += 1
                cov["infeasible"] += 1
            else:
                total += K + c
    return total, infeas, cov


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
        out = os.path.join(tmp, "k.csv")
        r = run(["--kth-random", "6", "--depth", "6", "--tree-file", tree,
                 "--out", out, "--tt-bits", "20"])
        if r.returncode != 0 or not os.path.exists(out):
            bad("k=6 on the real lists: %s" % (r.stderr.strip().splitlines() or [""])[-1])
            return
        row = read_csv(out)[0]
        want = 7920 * 12972
        if int(row["total"]) != want:
            bad("k=6 total %s, expected %d (salet 7920 x 12972)" % (row["total"], want))
        elif int(row["infeasible_pairs"]) != 0:
            bad("k=6 reported %s infeasible pairs; the tree resolves every answer"
                % row["infeasible_pairs"])
        else:
            ok("k=6 = 7920 x 12972 = %d, mean %s" % (want, row["mean"]))


def check_search(tmp, tree_path, tree, cases, label, seen):
    """B: the C against the per-pair reference, folding into the coverage tally."""
    for K, depth in cases:
        opt.cache_clear()
        want_total, want_infeas, cov = reference(tree, K, depth)
        for k in seen:
            seen[k] += cov[k]
        out = os.path.join(tmp, "%s_k%d_d%d.csv" % (label, K, depth))
        args = ["--kth-random", str(K), "--depth", str(depth), "--out", out]
        if K > 1:
            args += ["--tree-file", tree_path]
        r = run(args, data=tmp)
        if r.returncode != 0 or not os.path.exists(out):
            bad("%s k=%d depth=%d did not run: %s"
                % (label, K, depth, (r.stderr.strip().splitlines() or [""])[-1]))
            continue
        row = read_csv(out)[0]
        got_total, got_infeas = int(row["total"]), int(row["infeasible_pairs"])
        if got_total != want_total or got_infeas != want_infeas:
            bad("%s k=%d depth=%d: total %d/%d, infeasible %d/%d (C/reference)"
                % (label, K, depth, got_total, want_total, got_infeas, want_infeas))
        else:
            ok("%s k=%d depth=%d: total %d, %d infeasible pairs"
               % (label, K, depth, got_total, got_infeas))
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


def check_refusals(tmp, tree_path):
    """D: every input that would quietly mean something else must EXIT."""
    print("D. the refusals")
    out = os.path.join(tmp, "refuse.csv")
    cases = [
        ("no --out", ["--kth-random", "2", "--depth", "4",
                      "--tree-file", tree_path], OPTTURNS),
        ("no --depth", ["--kth-random", "2", "--tree-file", tree_path,
                        "--out", out], OPTTURNS),
        ("k past the cap", ["--kth-random", "5", "--depth", "4",
                            "--tree-file", tree_path, "--out", out], OPTTURNS),
        ("k=1 with a tree", ["--kth-random", "1", "--depth", "4",
                             "--tree-file", tree_path, "--out", out], OPTTURNS),
        ("k>1 with no tree", ["--kth-random", "2", "--depth", "4",
                              "--out", out], OPTTURNS),
        ("--topk", ["--kth-random", "2", "--depth", "4", "--topk", "3",
                    "--tree-file", tree_path, "--out", out], OPTTURNS),
        ("a non-normal binary", ["--kth-random", "2", "--depth", "4",
                                 "--tree-file", tree_path, "--out", out], HARDTURNS),
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
                 "--tree-file", path, "--out", out], data=tmp)
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
    totals = {r["word"]: r["total"] for r in paths.read_rows(paths.CSV_PATH)
              if r.get("total")}
    want = sum(int(v) for v in totals.values())
    for name, row in found:
        if len(totals) != int(row["pairs"]) // 2315:
            print("   skip  %s: the sweep CSV is not complete" % name)
            continue
        if int(row["total"]) != want:
            bad("%s k=1 total %s, but the opener sweep sums to %d"
                % (name, row["total"], want))
        else:
            ok("%s k=1 = %d = every opener's own optimal total, summed" % (name, want))


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
        for opener, cases in (("crane", [(1, 4), (2, 4), (3, 4), (4, 4), (2, 3), (3, 3)]),
                              ("roast", [(2, 4), (3, 4), (4, 4), (2, 3)])):
            check_search(tmp, paths_by_opener[opener], read_tree(paths_by_opener[opener]),
                         cases, opener, seen)
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
