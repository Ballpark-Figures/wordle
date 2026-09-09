"""Gate for `solver/eldrowmax` — the C search against the Python one it makes exact.

`eldrow.longest_chain` is the REFERENCE: the same objective, stated in that module
and itself a faithful port of the user's original, gated by tools/checkeldrow.py.
It is a plain branch-and-bound over LISTS OF WORDS with feedback from
`wordle.pattern`, so it shares no data structure with the C search — no bitsets, no
counting sort, no fingerprint, no memo. That is what makes it an oracle: a second
implementation, written differently, whose answers are already trusted.

THE ONE OFF-BY-ONE, ASSERTED RATHER THAN PAPERED OVER. eldrow counts
guesses-until-a-singleton; eldrowmax counts the WORDS IN THE SEQUENCE, the final
naming move included. So `c == python + 1`, exactly, on every case. Writing that
relation down is the point — the two numbers are one apart on purpose, and a gate
that quietly compared them loosely would hide a real off-by-one.

WHAT IS DIFFED, per case:

  THE VALUE.  The only thing that has to match. A port that agrees on lengths has
  the objective, the move rule and the bound all right.

  THE LINE, REPLAYED FROM THE STRINGS.  Not compared against Python's line (an
  optimum is rarely unique) but CHECKED IN ITS OWN RIGHT, by a route that shares
  nothing with the search: take the last word as the answer, recompute every
  feedback with `wordle.pattern`, and require that each word played was consistent
  with every earlier clue at the moment it was played, and that after the whole
  line exactly ONE candidate survives. A line ending with two words still alive is
  self-refuting — it could have been extended, so it was not longest.

  THE LINE'S LENGTH AGAINST THE VALUE.  A reported maximum of N with an N-1 word
  witness is self-refuting too, and free to check. Cheap checks of this shape are
  what caught a memo-key collision in the sibling solver where a value-only diff
  had passed for days.

  THE LADDER AGAINST --exact.  Two different searches for one number: the decision
  ladder (can_reach at a rising bar) and the outright maximisation. They share the
  expansion and nothing else, so a bug in either one's pruning shows as a
  disagreement.

  --no-prune AGAINST PRUNED.  Re-runs --exact with the size bound off. If the bound
  is inadmissible the two differ, and this catches it without Python having to be
  able to reach the state.

  A DELIBERATELY TINY TABLE.  The transposition table is pure memoisation: every
  entry is an exact value, so its SIZE can change how long a search takes and must
  not change what it returns. A tiny table forces heavy eviction and re-search, and
  a value that moves means the set fingerprints are colliding — precisely the
  failure that got past a value-only diff in antistall.

  THREADS.  The root split is the only parallelism, so --threads 1 and --threads 4
  must agree on the value AND, since below the root the search order is untouched,
  on the line.

COVERAGE IS TALLIED AND FAILS THE RUN, AND THE HARD CASE IS HUNTED FOR RATHER THAN
HOPED FOR. A pool whose greedy playout is already optimal exercises none of the
search — the ladder's first test succeeds against a bar greedy already reached — and
a run made entirely of those would pass while proving nothing. Measured, that is
most pools: on random seeds the tally came up empty as often as not, which makes a
"wait and see" check flaky rather than informative. So when the sampled cases do not
produce one, the gate keeps drawing pools until it finds a state where greedy is
STRICTLY short of the answer, and diffs that one in full. Failing to find one in a
bounded number of draws is itself a finding and fails the run.

POOLS ARE REACHABLE GAME STATES, not random subsets, and that is not a refinement
— it is what makes the gate test anything. A random sample of the mystery list is
2315 words' worth of dissimilar, so the first guess shatters it into singletons and
EVERY case comes back 3 with the recursion barely entered; measured, that is
exactly what happened, and the coverage tally failed the run rather than passing it
quietly. So a pool is built the way the game builds one: play a random word, keep a
random one of its feedback buckets, repeat, and take what is left. Those words share
their clues, which is where long chains come from. Pools stay small because the
reference is exponential — that is the whole reason the C version exists — and the
pool is a knob the binary already takes (--words), so none of this needs a test-only
code path in the solver.

    python3 tools/checkeldrowmax.py [--seed N] [--cases N] [--size N] [--quick]
"""
import argparse
import os
import random
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eldrow import longest_chain
from wordle import ALL_GREEN, load_words, pattern

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(MATH, "solver", "eldrowmax")

FAILS = []
WARNS = []

# Anchored on the leading phrase and the number, tolerant of the prose between
# them: both of these have been reworded once already, and a gate that dies on a
# clarified sentence is a gate that discourages clarifying it. The line is always
# the row beneath.
RESULT = re.compile(r"^LONGEST CHAIN: (?P<val>\d+) words \((?P<kind>[^)]+)\)")
GREEDY = re.compile(r"^greedy playout\b.*?(?P<val>\d+)\s*$")


def run_c(pool, extra=()):
    """(value, line, greedy, seconds) from the C binary on this pool."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(pool) + "\n")
        path = fh.name
    try:
        cmd = [BINARY, "--words", path, "--no-out", "--data", "data",
               "--tt-bits", "20", "--threads", "1"] + list(extra)
        t0 = time.time()
        p = subprocess.run(cmd, cwd=MATH, capture_output=True, text=True)
        secs = time.time() - t0
    finally:
        os.unlink(path)
    if p.returncode != 0:
        raise SystemExit(f"eldrowmax failed ({p.returncode}):\n{p.stdout}\n{p.stderr}")
    val = line = None
    greedy = None
    out = p.stdout.splitlines()
    for i, row in enumerate(out):
        m = GREEDY.match(row)
        if m:
            greedy = int(m.group("val"))
        m = RESULT.match(row)
        if m:
            val = int(m.group("val"))
            line = out[i + 1].strip()
    if val is None:
        raise SystemExit(f"no result line in:\n{p.stdout}")
    return val, line, greedy, secs


def replay(pool, line):
    """Check a line from the STRINGS alone. Returns a list of complaints.

    Nothing here touches the search's machinery: the answer is taken to be the last
    word, every feedback is recomputed with `wordle.pattern`, and the candidate set
    is filtered as a plain list of strings.
    """
    bad = []
    words = line.split()
    if not words:
        return ["empty line"]
    answer = words[-1]
    alive = list(pool)
    for k, w in enumerate(words):
        if w not in alive:
            bad.append(f"guess {k + 1} {w} was not a live candidate")
            return bad
        if k == len(words) - 1:
            break
        p = pattern(w, answer)
        if p == ALL_GREEN:
            bad.append(f"guess {k + 1} {w} was the answer, so the game ended there")
            return bad
        alive = [x for x in alive if pattern(w, x) == p]
    if alive != [answer]:
        bad.append(f"after the line {len(alive)} candidates remain, not 1: "
                   f"{' '.join(alive[:6])}")
    return bad


def sample_pool(answers, size, rng):
    """A REACHABLE state of the real game, cut down to `size` words.

    Play a random live word, keep a random non-all-green bucket of its feedback,
    and repeat while the set is still bigger than `size`; then take `size` of what
    survives. Every word in the result agrees with every other on every clue played
    to get there, which is the similarity long chains are built out of.
    """
    alive = list(answers)
    for _ in range(40):
        if len(alive) <= size:
            break
        g = rng.choice(alive)
        buckets = {}
        for w in alive:
            buckets.setdefault(pattern(g, w), []).append(w)
        usable = [b for p, b in buckets.items() if p != ALL_GREEN and len(b) >= 2]
        if not usable:
            break
        # Prefer the roomiest few: a bucket of two ends the search immediately.
        usable.sort(key=len, reverse=True)
        alive = rng.choice(usable[:3])
    if len(alive) > size:
        alive = rng.sample(alive, size)
    return sorted(alive)


def check_csv(pool, expect_val):
    """The OUTPUT PATH, end to end: run with --out and read the file back.

    Every other check here calls the binary with --no-out, so nothing would
    exercise the header, the incremental rows or the final one -- and a sibling
    solver in this repo shipped a broken format string for exactly that reason,
    crashing every first run AFTER the file had been created. So: run it for real
    into a temp file and parse what lands.

    The rows are the run's own history. `greedy` is written before the search
    starts, `improved` each time the ladder finds a longer chain, and `final` only
    when the ladder has PROVED nothing longer exists -- which is what makes a
    killed run distinguishable from a finished one. Complaints are returned.
    """
    bad = []
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(pool) + "\n")
        wordpath = fh.name
    out = wordpath + ".csv"
    try:
        cmd = [BINARY, "--words", wordpath, "--out", out, "--data", "data",
               "--tt-bits", "20", "--threads", "1"]
        p = subprocess.run(cmd, cwd=MATH, capture_output=True, text=True)
        if p.returncode != 0:
            return [f"the --out run failed ({p.returncode}): {p.stderr.strip()}"]
        if not os.path.exists(out):
            return ["--out was given but no file was written"]
        rows = [r for r in open(out).read().splitlines() if r.strip()]
    finally:
        os.unlink(wordpath)
        if os.path.exists(out):
            os.unlink(out)

    header = rows[0].split(",")
    want_cols = ["pool", "words", "mode", "status", "length", "greedy",
                 "nodes", "threads", "secs", "line"]
    if header != want_cols:
        bad.append(f"header is {header}, want {want_cols}")
        return bad
    body = [r.split(",", len(want_cols) - 1) for r in rows[1:]]
    if not body:
        bad.append("the file has a header and no rows")
        return bad
    if body[0][3] != "greedy":
        bad.append(f"the first row's status is {body[0][3]!r}, want 'greedy' -- the "
                   "greedy line must be on disk before the search starts")
    if body[-1][3] != "final":
        bad.append(f"the last row's status is {body[-1][3]!r}, want 'final'")
    elif int(body[-1][4]) != expect_val:
        bad.append(f"the final row says {body[-1][4]}, the run reported {expect_val}")
    lengths = [int(r[4]) for r in body if r[3] in ("greedy", "improved")]
    if lengths != sorted(set(lengths)):
        bad.append(f"the incremental lengths are not strictly increasing: {lengths}")

    # A `reached` row is the LENGTH, recorded the moment the decision proves it and
    # before the witness is rebuilt -- which is the window a Ctrl-C used to lose.
    # It carries no line by construction, and an `improved` row at the same length
    # must follow it.
    for i, r in enumerate(body):
        if r[3] != "reached":
            continue
        if r[-1].strip():
            bad.append(f"a 'reached' row carries a line ({r[-1]!r}); it is written "
                       "before the line exists and must be empty")
        later = [x for x in body[i + 1:]
                 if x[3] == "improved" and int(x[4]) == int(r[4])]
        if not later:
            bad.append(f"'reached' at {r[4]} is never followed by an 'improved' row "
                       "at the same length, so no witness was ever recorded")
    for r in body:
        if int(r[4]) > expect_val:
            bad.append(f"a {r[3]} row claims {r[4]}, longer than the maximum "
                       f"{expect_val}")
    return bad


def check(tag, got, want, why):
    if got != want:
        FAILS.append(f"{tag}: {why} -- got {got}, want {want}")
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cases", type=int, default=8)
    ap.add_argument("--size", type=int, default=12,
                    help="words per pool; the reference is exponential in this")
    ap.add_argument("--quick", action="store_true",
                    help="fewer, smaller pools")
    args = ap.parse_args()
    if args.quick:
        args.cases, args.size = 3, 9

    if not os.path.exists(BINARY):
        raise SystemExit("no solver/eldrowmax -- run 'sh build.sh' in solver/")

    answers = load_words("mystery")
    rng = random.Random(args.seed)

    saw_search = 0          # greedy strictly below the answer
    saw_long = 0            # a chain of 4 or more
    print(f"eldrowmax vs eldrow.longest_chain: {args.cases} pools of {args.size} "
          f"words, seed {args.seed}\n")
    print(f"{'pool':>7}  {'C':>3} {'py+1':>4} {'greedy':>6}  {'C s':>6} {'py s':>6}  line")

    def diff_case(tag, pool):
        """Every check, on one pool. Returns (value, greedy)."""
        cval, cline, greedy, csecs = run_c(pool)

        t0 = time.time()
        pyval, _ = longest_chain(pool)
        pysecs = time.time() - t0

        check(tag, cval, pyval + 1,
              "the C value against the reference plus one (eldrow counts "
              "guesses-until-a-singleton, this counts the words played)")
        check(tag, len(cline.split()), cval, "the line's length against the value")
        for complaint in replay(pool, cline):
            FAILS.append(f"{tag}: replayed from the strings, {complaint}")

        # The ladder and the outright maximisation are two searches for one number.
        eval_, eline, _, _ = run_c(pool, ("--exact",))
        check(tag, eval_, cval, "--exact against the decision ladder")
        for complaint in replay(pool, eline):
            FAILS.append(f"{tag}: --exact line replayed from the strings, {complaint}")

        # The bound must be admissible: dropping it cannot change the answer.
        uval, _, _, _ = run_c(pool, ("--exact", "--no-prune"))
        check(tag, uval, cval, "--no-prune against the pruned search")

        # The table is pure memoisation, so its size must not move the answer.
        tval, _, _, _ = run_c(pool, ("--tt-bits", "8"))
        check(tag, tval, cval, "a deliberately tiny table against the default one")

        # Only the root is split, so threads change neither value nor line.
        pval, pline, _, _ = run_c(pool, ("--threads", "4"))
        check(tag, pval, cval, "--threads 4 against --threads 1")
        if pline != cline:
            WARNS.append(f"{tag}: --threads 4 reported a different line\n"
                         f"    1: {cline}\n    4: {pline}")

        print(f"{tag:>7}  {cval:>3} {pyval + 1:>4} {greedy:>6}  "
              f"{csecs:>6.2f} {pysecs:>6.2f}  {cline}")
        return cval, greedy

    for case in range(args.cases):
        pool = sample_pool(answers, args.size, rng)
        cval, greedy = diff_case(str(case), pool)
        if case == 0:
            for complaint in check_csv(pool, cval):
                FAILS.append(f"case 0 CSV: {complaint}")
        if greedy is not None and greedy < cval:
            saw_search += 1
        if cval >= 4:
            saw_long += 1

    # The hard case, hunted for rather than hoped for: greedy is optimal on most
    # pools, so a run that merely tallied would pass while the search below the
    # first bar went untested.
    tries = 0
    while not saw_search and tries < 60:
        tries += 1
        pool = sample_pool(answers, args.size, rng)
        cval, _, greedy, _ = run_c(pool)
        if greedy is None or greedy >= cval:
            continue
        cval, greedy = diff_case(f"hunt{tries}", pool)
        saw_search += 1
        if cval >= 4:
            saw_long += 1

    print()
    print(f"coverage: {saw_search} pool(s) where greedy was strictly short of the "
          f"answer{f' (found after {tries} extra draws)' if tries else ''}, "
          f"{saw_long} with a chain of 4 or more")
    if not saw_search:
        FAILS.append(f"coverage: greedy was optimal on every one of {args.cases + tries} "
                     "pools, so the search past the first bar was never exercised -- "
                     "raise --size, or ask why greedy is never beaten")
    if not saw_long:
        FAILS.append("coverage: no pool ran past a 3-word chain, so the recursion "
                     "was barely entered -- raise --size")

    for w in WARNS:
        print(f"WARN {w}")
    if FAILS:
        print(f"\nFAIL ({len(FAILS)}):")
        for f in FAILS:
            print(f"  {f}")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
