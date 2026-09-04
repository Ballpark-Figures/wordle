"""The GATE for mmturns -- Wordle's word lists under MASTERMIND's peg feedback.

    python3 tools/checkmastermind.py            (from math/)
    python3 tools/checkmastermind.py --wide     (also the full 12972 x 2315 matrix)

Run it alongside `bash solver/validate.sh` and `python3 tools/checkpatterns.py`
after any change to the -DMASTERMIND paths in solver/optturns.c.

WHY IT EXISTS.  `mmturns` is optturns with the feedback swapped, and the swap is
argued rather than implemented: the peg counts are claimed to be a FUNCTION of
the stored Wordle pattern (blacks = greens, whites = yellows).  An argument is
not an oracle.  Four independent ones are assembled here, cheapest first:

  1. THE ENCODING.  A Python mirror of the C's mm_code enumeration -- dense,
     bijective, missing exactly (L-1, 1), with the win (L, 0) last so that
     ALL_GREEN == NPAT - 1 keeps its meaning.  A `>> 1`-style off-by-one in the
     C's ordering silently MERGES two feedbacks; this catches it.

  2. THE IDENTITY.  Peg counts recomputed FROM THE STRINGS by the textbook
     Mastermind rule -- blacks = positions that agree, whites =
     sum_c min(guess_c, answer_c) - blacks -- against the greens/yellows read out
     of `wordle.pattern`.  Exhaustive over every guess x answer pair on a small
     alphabet (so repeated letters, the place these two definitions could part
     company, are covered densely), and over the real matrix under --wide.

  3. THE HOLE.  That (L-1, 1) really is unreachable, and that every other pair is
     reached -- established by enumeration, not by the argument in the source.

  4. THE SEARCH.  A miniature complete data directory (a handful of real words
     plus their pattern matrix) is handed to the actual `mmturns` binary, and its
     per-opener totals are diffed against a brute-force memoised solver written
     here from the strings, sharing no code with the C.  This is the only check
     that exercises the objective, the depth cap and the --topk root pick rather
     than the feedback alone.

Exits nonzero, so it works as a gate.
"""

import argparse
import functools
import itertools
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import load_words, pattern, to_codes  # noqa: E402

MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MMTURNS = os.path.join(MATH, "solver", "mmturns")

_fail = 0


def bad(msg):
    global _fail
    print(f"  FAIL: {msg}")
    _fail = 1


# --------------------------------------------------------------- 1. encoding
# A LINE-FOR-LINE mirror of mm_code() in optturns.c. Kept deliberately literal --
# the point is to restate the C's enumeration, not to find a cleverer one.

def mm_codes(length):
    """[(blacks, whites)] in the C's order: blacks ascending, whites ascending
    within it, skipping the impossible (length-1, 1)."""
    out = []
    for b in range(length + 1):
        for w in range(length + 1 - b):
            if b == length - 1 and w == 1:
                continue
            out.append((b, w))
    return out


def npat(length):
    """The C's NPAT: (L+1)(L+2)/2 - 1."""
    return (length + 1) * (length + 2) // 2 - 1


def check_encoding():
    print("1. the (blacks, whites) encoding")
    for length in range(2, 12):
        codes = mm_codes(length)
        n = npat(length)
        if len(codes) != n:
            bad(f"L={length}: {len(codes)} codes enumerated, NPAT formula gives {n}")
            continue
        if len(set(codes)) != len(codes):
            bad(f"L={length}: the enumeration repeats a pair")
        if codes[-1] != (length, 0):
            bad(f"L={length}: last code is {codes[-1]}, not the win ({length}, 0) "
                f"-- ALL_GREEN = NPAT-1 would name the wrong feedback")
        if (length - 1, 1) in codes:
            bad(f"L={length}: the impossible pair ({length - 1}, 1) got a code")
        every = {(b, w) for b in range(length + 1) for w in range(length + 1 - b)}
        if set(codes) != every - {(length - 1, 1)}:
            bad(f"L={length}: the code set is not every reachable pair")
    if _fail == 0:
        print(f"   ok   L=2..11 dense and bijective; NPAT(5) = {npat(5)}, "
              f"win = code {npat(5) - 1}")


# ------------------------------------------------------------- 2. the identity

def pegs_from_strings(guess, answer):
    """Mastermind's peg counts, by the textbook rule and nothing else.

    blacks = positions where the two agree.
    whites = sum over colours of min(count in guess, count in answer), less the
             blacks already claimed.
    Shares no code with wordle.pattern -- that is the whole point.
    """
    blacks = sum(g == a for g, a in zip(guess, answer))
    gc, ac = Counter(guess), Counter(answer)
    shared = sum(min(gc[c], ac[c]) for c in gc)
    return blacks, shared - blacks


def pegs_from_pattern(code, length):
    """What the C's mm_remap does: count the trits of the base-3 Wordle code."""
    blacks = whites = 0
    for _ in range(length):
        t = code % 3
        code //= 3
        if t == 2:
            blacks += 1
        elif t == 1:
            whites += 1
    return blacks, whites


def check_identity_small():
    print("2. blacks = greens and whites = yellows, from the strings")
    # A small alphabet makes repeated letters the COMMON case rather than a
    # corner, which is exactly where the two definitions could disagree.
    for alpha, length in ((3, 3), (2, 4), (4, 3)):
        letters = "abcdefghij"[:alpha]
        words = ["".join(p) for p in itertools.product(letters, repeat=length)]
        seen = set()
        for g in words:
            for a in words:
                want = pegs_from_strings(g, a)
                got = pegs_from_pattern(int(pattern(g, a)), length)
                if want != got:
                    bad(f"alpha={alpha} L={length}: {g} vs {a} -- "
                        f"pattern says {got}, pegs say {want}")
                    return
                seen.add(want)
        # 3. the hole, on the same sweep: every pair reached except (L-1, 1).
        codes = set(mm_codes(length))
        if (length - 1, 1) in seen:
            bad(f"alpha={alpha} L={length}: the 'impossible' pair "
                f"({length - 1}, 1) actually occurred")
        missing = codes - seen
        if alpha >= length and missing:
            bad(f"alpha={alpha} L={length}: pairs never reached: {sorted(missing)}")
        print(f"   ok   alpha={alpha} L={length}: {len(words)**2} pairs agree, "
              f"{len(seen)} of {len(codes)} feedbacks reached")


def check_identity_full():
    print("2b. the same identity over the real 12972 x 2315 matrix")
    path = os.path.join(MATH, "data", "local", "patterns", "patterns.npy")
    if not os.path.exists(path):
        bad(f"{path} is missing -- run `python3 build_patterns.py` from math/")
        return
    pat = np.load(path, mmap_mode="r")
    guesses, answers = load_words("guess"), load_words("mystery")
    gcodes, acodes = to_codes(guesses), to_codes(answers)

    # Peg counts straight from the letter codes, vectorised over the whole answer
    # axis: blacks by positional equality, shared by summing min() per letter.
    # Never touches the pattern matrix.
    ah = np.zeros((len(answers), 26), np.int16)
    for c in range(26):
        ah[:, c] = (acodes == c).sum(axis=1)

    rows = range(len(guesses))
    for g in rows:
        row = np.asarray(pat[g], dtype=np.int32)
        blacks_p = np.zeros(len(answers), np.int16)
        whites_p = np.zeros(len(answers), np.int16)
        q = row.copy()
        for _ in range(5):
            t = q % 3
            q //= 3
            blacks_p += (t == 2)
            whites_p += (t == 1)

        blacks_s = (acodes == gcodes[g]).sum(axis=1).astype(np.int16)
        gh = np.bincount(gcodes[g], minlength=26).astype(np.int16)
        shared = np.minimum(ah, gh[None, :]).sum(axis=1).astype(np.int16)
        whites_s = shared - blacks_s

        if not np.array_equal(blacks_p, blacks_s) or not np.array_equal(whites_p, whites_s):
            i = int(np.argmax((blacks_p != blacks_s) | (whites_p != whites_s)))
            bad(f"{guesses[g]} vs {answers[i]}: pattern gives "
                f"({blacks_p[i]}, {whites_p[i]}), pegs give ({blacks_s[i]}, {whites_s[i]})")
            return
    print(f"   ok   all {len(guesses) * len(answers)} guess x answer pairs agree")


# --------------------------------------------------------- 4. the search itself

MINI_GUESSES = [
    "crane", "slate", "trace", "adieu", "audio", "roast", "stern", "pilot",
    "brick", "flame", "gouty", "vixen", "wharf", "zesty", "mimic", "puppy",
    "abbey", "eerie", "llama", "salad", "tepee", "onion", "kayak", "level",
]
MINI_ANSWERS = [
    "crane", "slate", "trace", "roast", "stern", "pilot", "brick", "flame",
    "mimic", "puppy", "abbey", "llama", "salad", "onion", "kayak", "level",
]


def make_mini_data(tmp):
    """A complete miniature `--data` directory: two word lists plus the pattern
    matrix they imply.  mmturns then reads a small problem by its NORMAL path --
    no special flags, so the code under test is the code that runs for real."""
    words = os.path.join(tmp, "shared", "words")
    pats = os.path.join(tmp, "local", "patterns")
    os.makedirs(words)
    os.makedirs(pats)
    with open(os.path.join(words, "guess.txt"), "w") as f:
        f.write("\n".join(MINI_GUESSES) + "\n")
    with open(os.path.join(words, "mystery.txt"), "w") as f:
        f.write("\n".join(MINI_ANSWERS) + "\n")
    mat = np.array([[pattern(g, a) for a in MINI_ANSWERS] for g in MINI_GUESSES],
                   dtype=np.uint8)
    np.save(os.path.join(pats, "patterns.npy"), mat)


def mini_peg_table():
    """peg[g][a], as a dense code, computed from the STRINGS via the textbook
    rule -- the reference the C's remapped matrix must reproduce."""
    codes = {p: i for i, p in enumerate(mm_codes(5))}
    return [[codes[pegs_from_strings(g, a)] for a in MINI_ANSWERS] for g in MINI_GUESSES]


def brute_total(peg, opener, depth):
    """Exact minimum total guesses over MINI_ANSWERS, subject to the cap.

    A plain memoised min-over-guesses recursion: no lower bound, no ordering, no
    transposition subtleties -- slow, and independent of every optimisation the C
    makes.  Returns None when the opener cannot fit the cap (the C's INFEASIBLE).
    """
    ng, win = len(MINI_GUESSES), len(mm_codes(5)) - 1

    @functools.lru_cache(maxsize=None)
    def solve(cands, d):
        n = len(cands)
        if n == 0:
            return 0
        if n == 1:
            return 1 if d >= 1 else None
        if d <= 1:
            return None
        best = None
        for g in range(ng):
            buckets = {}
            for a in cands:
                buckets.setdefault(peg[g][a], []).append(a)
            if len(buckets) == 1 and win not in buckets:
                continue                      # splits nothing, cannot help
            total = n                         # this guess, charged to every live answer
            ok = True
            for p, kids in buckets.items():
                if p == win:
                    continue                  # that answer is done, already paid for
                sub = solve(tuple(kids), d - 1)
                if sub is None:
                    ok = False
                    break
                total += sub
            if ok and (best is None or total < best):
                best = total
        return best

    root = tuple(range(len(MINI_ANSWERS)))
    g = MINI_GUESSES.index(opener)
    buckets = {}
    for a in root:
        buckets.setdefault(peg[g][a], []).append(a)
    total = len(root)
    for p, kids in buckets.items():
        if p == win:
            continue
        sub = solve(tuple(kids), depth - 1)
        if sub is None:
            return None
        total += sub
    return total


def run_mmturns(tmp, args):
    out = subprocess.run([MMTURNS, "--data", tmp, "--threads", "1"] + args,
                         capture_output=True, text=True)
    return out


def check_search(depths):
    print(f"4. mmturns vs a brute-force solver on a {len(MINI_GUESSES)}x"
          f"{len(MINI_ANSWERS)} problem (depths {', '.join(map(str, depths))})")
    if not os.path.exists(MMTURNS):
        bad("no solver/mmturns -- run `sh build.sh` in solver/")
        return
    peg = mini_peg_table()
    tmp = tempfile.mkdtemp(prefix="checkmm-")
    try:
        make_mini_data(tmp)

        # --depth is refused when absent: the cap IS the objective here.
        r = run_mmturns(tmp, ["--opener", MINI_GUESSES[0]])
        if r.returncode == 0:
            bad("mmturns ran without --depth; the cap would be an unstated default")
        else:
            print("   ok   refuses to run without --depth")

        # Tallied so a PASS cannot silently mean one of the two outcomes was
        # never produced -- an all-feasible run would leave the INFEASIBLE
        # comparison entirely untested, which is the branch the cap governs.
        checked = n_finite = n_infeasible = 0
        for depth in depths:
            for opener in MINI_GUESSES:
                want = brute_total(peg, opener, depth)
                r = run_mmturns(tmp, ["--opener", opener, "--depth", str(depth)])
                if r.returncode != 0:
                    bad(f"{opener} d{depth}: mmturns exited {r.returncode}\n{r.stderr}")
                    return
                line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
                if "INFEASIBLE" in line:
                    got = None
                else:
                    try:
                        got = int(line.split("total=")[1].split()[0])
                    except (IndexError, ValueError):
                        bad(f"{opener} d{depth}: cannot parse output: {line!r}")
                        return
                if got != want:
                    bad(f"{opener} d{depth}: mmturns says {got}, brute force says {want}")
                    return
                checked += 1
                if want is None:
                    n_infeasible += 1
                else:
                    n_finite += 1
        if not n_finite:
            bad("no opener solved at any depth -- the totals were never compared")
        if not n_infeasible:
            bad("no opener was INFEASIBLE at any depth -- the cap never bound, so "
                "that branch went untested; lower the tightest --depth")
        print(f"   ok   {checked} (opener, depth) cases agree exactly "
              f"({n_finite} solved, {n_infeasible} INFEASIBLE)")
        depth = depths[-1]

        # The --topk 1 root pick must be the lowest sum of squared bin sizes,
        # ties on the lowest guess index -- the rule, restated independently.
        win = len(mm_codes(5)) - 1
        def ssq(g):
            c = Counter(peg[g][a] for a in range(len(MINI_ANSWERS)))
            return sum(v * v for v in c.values())
        want_open = min(range(len(MINI_GUESSES)), key=lambda g: (ssq(g), g))
        out = os.path.join(tmp, "topk1.csv")
        r = run_mmturns(tmp, ["--sweep", "--optimal-only", "--topk", "1",
                              "--depth", str(depth), "--out", out])
        if r.returncode != 0:
            bad(f"--topk 1 sweep exited {r.returncode}\n{r.stderr}")
            return
        rows = [l for l in open(out).read().splitlines()[1:] if l.strip()]
        if len(rows) != 1:
            bad(f"--topk 1 wrote {len(rows)} rows; it must examine exactly one opener")
        elif rows[0].split(",")[0] != MINI_GUESSES[want_open]:
            bad(f"--topk 1 picked {rows[0].split(',')[0]}, "
                f"sum of squares says {MINI_GUESSES[want_open]}")
        else:
            print(f"   ok   --topk 1 examines exactly one opener, "
                  f"the evenest splitter ({MINI_GUESSES[want_open]})")

        # --print-openers must account for EVERY opener examined, not only the
        # ones that improved on the running best. The failure it guards against
        # is silent: the CSV holds all K while the terminal shows a handful, so
        # the count is the thing to assert.
        k = 5
        out5 = os.path.join(tmp, "topk5.csv")
        r = run_mmturns(tmp, ["--sweep", "--optimal-only", "--topk", str(k),
                              "--depth", str(depth), "--print-openers", "--out", out5])
        if r.returncode != 0:
            bad(f"--print-openers run exited {r.returncode}\n{r.stderr}")
            return
        named = [w for w in MINI_GUESSES
                 if any(l.startswith("[") and f" {w} " in l for l in r.stdout.splitlines())]
        if len(named) != k:
            bad(f"--print-openers named {len(named)} of {k} openers examined "
                f"({', '.join(named)}) -- some were examined but never printed")
        else:
            print(f"   ok   --print-openers gives a line for all {k} openers examined")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wide", action="store_true",
                    help="also diff the identity over the real 12972 x 2315 matrix (~1 min)")
    ap.add_argument("--depths", type=int, nargs="+", default=[3, 6],
                    help="depths for the miniature differential search. The default "
                         "pair straddles the cap: 3 forces INFEASIBLE openers, 6 "
                         "solves, so both branches are compared (default 3 6)")
    args = ap.parse_args()

    check_encoding()
    check_identity_small()
    if args.wide:
        check_identity_full()
    else:
        print("2b. real-matrix identity SKIPPED (pass --wide)")
    check_search(args.depths)

    print("FAIL" if _fail else "PASS")
    return _fail


if __name__ == "__main__":
    sys.exit(main())
