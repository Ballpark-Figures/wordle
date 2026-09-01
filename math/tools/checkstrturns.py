"""Cross-check the C solver's state arithmetic against `strspace.py`.

`solver/strturns.c` reimplements the constraint representation in C -- meet,
canonicalisation, the counting DP, and the (guess, pattern) atoms. `strspace.py`
is the reference for all four, and `tools/checkstrspace.py` has already checked
IT exhaustively against brute force on small alphabets and against a real filter
of 26**5. So the remaining question is only whether the port agrees, and that is
answered by making both walk the SAME path and comparing numbers.

`strturns --selftest N` replays N deterministic pseudo-random walks of up to four
(guess, pattern) refinements, printing the candidate count at each step. This
reproduces the identical walk in Python and diffs line for line. The arithmetic
generating the walk is duplicated on purpose -- it has to be bit-identical, and
that is easier to see side by side than to share.

    python3 tools/checkstrturns.py           # 300 walks
    python3 tools/checkstrturns.py 2000

Exit status is nonzero on any divergence, so it works as a gate. Run it after
any change to either file, alongside tools/checkstrspace.py.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.dirname(HERE)
sys.path.insert(0, MATH)
import strspace
from wordle import load_words

M64 = (1 << 64) - 1
NPAT = 243


def walk_python(nwalk, words):
    ng = len(words)
    out = []
    for seed in range(nwalk):
        st = strspace.initial()
        out.append("%d root %d" % (seed, strspace.count(st)))
        for step in range(4):
            r = (seed * 2654435761 + step * 40503 + 12345) & M64
            r ^= r >> 17
            r = (r * 0x9E3779B97F4A7C15) & M64
            r ^= r >> 31
            g = r % ng
            p = (r >> 20) % NPAT
            w = words[g]
            nx = strspace.refine(st, [ord(c) - ord("a") for c in w], p)
            if nx is None or strspace.count(nx) == 0:
                # C reports DEAD only for a contradictory meet; an empty-but-
                # consistent state still has a count, so distinguish them.
                if nx is None:
                    out.append("%d %s %d DEAD" % (seed, w, p))
                    break
                out.append("%d %s %d 0" % (seed, w, p))
                st = nx
                continue
            st = nx
            out.append("%d %s %d %d" % (seed, w, p, strspace.count(st)))
    return out


def main():
    nwalk = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    binary = os.path.join(MATH, "solver", "strturns")
    if not os.path.exists(binary):
        sys.exit("no %s -- run 'sh build.sh' in solver/" % binary)
    res = subprocess.run([binary, "--selftest", str(nwalk), "--data",
                          os.path.join(MATH, "data")],
                         capture_output=True, text=True, cwd=MATH)
    if res.returncode:
        sys.exit("strturns --selftest failed:\n" + res.stderr[-2000:])
    got = [l for l in res.stdout.splitlines() if l.strip()]
    want = walk_python(nwalk, load_words("guess"))

    if len(got) != len(want):
        print("FAIL: C emitted %d lines, Python %d" % (len(got), len(want)))
        for i in range(min(len(got), len(want))):
            if got[i] != want[i]:
                print("  first divergence at line %d:\n    C:      %s\n    Python: %s"
                      % (i, got[i], want[i]))
                break
        sys.exit(1)
    bad = [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b]
    print("%d walks, %d refinement steps compared" % (nwalk, len(got)))
    if bad:
        print("FAIL: %d line(s) differ" % len(bad))
        for i, a, b in bad[:10]:
            print("  line %d\n    C:      %s\n    Python: %s" % (i, a, b))
        sys.exit(1)
    print("PASS: C state arithmetic matches strspace.py exactly")


if __name__ == "__main__":
    main()
