"""Gate for `solver/antistall` — the C search against the Python one it ports.

`antiwordle.py` is the REFERENCE: slower by about 90x, but checked in its own
right by tools/checkantiwordle.py (legality two ways, the three invariants the
search rests on, the bounds against exact values, the pruned search against the
exhaustive one, and the whole thing against brute force on small lists). That
makes it exactly the oracle a port needs — a second implementation, written
differently, whose answers are already trusted.

WHAT IS DIFFED, per case:

  THE VALUE.  The only thing that has to match. A port that agrees on lengths has
  the objective, the legality rules and the bounds all right.

  THE LINE.  Not required to match — an optimum is rarely unique — but both sides
  break ties on the lowest guess index at every branching point, so they SHOULD
  agree, and a divergence means the orders have drifted apart even if the values
  have not. Reported, and treated as a warning rather than a failure.

  THE UNPRUNED RUN.  --no-prune re-runs the C search with both bounds off. If a
  bound in the C port is inadmissible in a way the Python bounds are not, the
  pruned and unpruned C values differ and this catches it without needing Python
  to be able to reach the state at all.

  THE LINE'S LENGTH AGAINST THE VALUE.  A reported maximum of N with an N-1 word
  witness is self-refuting, and this is free to check. It is here because it was
  the first symptom of a real bug (a memo-key collision, 2026-09-03) and would
  have caught it instantly, where the value-only comparison passed for days.

  THE ANSWER AGAINST TABLE SIZE.  The transposition table is pure memoisation:
  every entry is an exact value, so its SIZE can change how long a search takes
  and must not change what it returns. Running each case with a deliberately tiny
  table forces heavy eviction and re-search, and a value that moves means keys are
  colliding. That is precisely the failure that got past the value-only diff --
  the fingerprint's two halves were correlated, so 128 nominal key bits were worth
  far fewer, and one position quietly returned another's value.

RUN FROM MID-GAME, always. The Python reference cannot search an empty board —
that is the entire reason the C port exists — so a shared starting state is the
only place the two can be compared. The prefix is arbitrary and stated in the
output; cases are chosen as the ROOMIEST of a sample, because a state throttled
to two nodes agrees trivially and proves nothing.

    python3 tools/checkantistall.py [--seed N] [--cases N] [--quick]
"""
import os
import random
import re
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import GuessSpace, StallSearch, cons_none, replay_prefix
from build_patterns import load_patterns
from wordle import load_words

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(MATH, "solver", "antistall")
PREFIX = "sulky tempo"          # arbitrary, and stated wherever a number is shown

FAILS = []
WARNS = []


# "[1/1] crane = 8  nodes=1351 edges=4450 0.01s  didie gaffe ... crane"
ROW = re.compile(r"\] (?P<answer>\w+) = (?P<val>\S+)\s+nodes=(?P<nodes>\d+) "
                 r"edges=\d+ (?P<secs>[\d.]+)s\s*(?P<line>.*)$")


def run_c(answer, after, extra=()):
    """(value, line, search seconds) from the C binary; value None if it aborted.

    The reported time is the binary's OWN measurement of the search, not the wall
    clock of the subprocess: a fresh process loads a 30 MB pattern matrix before it
    starts, which on the small cases is most of the elapsed time and would make the
    speed comparison against Python meaningless.
    """
    cmd = [BINARY, "--answer", answer, "--no-out", "--data", "data"]
    if after:
        cmd += ["--after", after]
    cmd += list(extra)
    p = subprocess.run(cmd, cwd=MATH, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"antistall failed ({p.returncode}):\n{p.stderr}")
    for row in p.stdout.splitlines():
        m = ROW.search(row)
        if m and m.group("answer") == answer:
            if m.group("val") == "ABORTED":
                return None, "", float(m.group("secs"))
            return int(m.group("val")), m.group("line").strip(), float(m.group("secs"))
    raise SystemExit(f"no result line for {answer} in:\n{p.stdout}")


def run_python(space, PAT, answers, answer, after):
    """(value, line, seconds) from the reference implementation."""
    col = np.asarray(PAT[:, answers.index(answer)])
    cons = replay_prefix(space, col, after.split())
    search = StallSearch(space, col, space.index[answer])
    t0 = time.time()
    val = search.value(cons)
    line = " ".join(search.line(cons))
    return val, line, time.time() - t0


def roomiest(space, PAT, answers, rng, cases):
    """The sampled answers with the most legal words left after the prefix.

    Answers the prefix could never have been PLAYED against are dropped, not just
    ranked low: if the opening turned a letter yellow, a follow-up lacking it was
    an illegal move, so that state cannot occur in a game and the C binary
    rightly refuses to start there.
    """
    def room(answer):
        col = np.asarray(PAT[:, answers.index(answer)])
        try:
            cons = replay_prefix(space, col, PREFIX.split())
        except ValueError:
            return None
        return int(space.legal_mask(cons).sum())

    scored = [(room(w), w) for w in rng.sample(answers, 20 * cases)]
    live = [(n, w) for n, w in scored if n is not None]
    return [w for _, w in sorted(live, key=lambda t: -t[0])[:cases]]


def main():
    argv = sys.argv[1:]
    seed = int(argv[argv.index("--seed") + 1]) if "--seed" in argv else 20260902
    quick = "--quick" in argv
    cases = int(argv[argv.index("--cases") + 1]) if "--cases" in argv else (2 if quick else 5)
    rng = random.Random(seed)

    if not os.path.exists(BINARY):
        raise SystemExit("no solver/antistall -- run 'sh build.sh' in solver/")

    answers = load_words("mystery")
    space = GuessSpace(load_words("guess"))
    PAT = load_patterns()
    print(f"antistall gate: C vs antiwordle.py, {cases} cases after '{PREFIX}', "
          f"seed {seed}\n")

    for answer in roomiest(space, PAT, answers, rng, cases):
        cv, cline, csecs = run_c(answer, PREFIX)
        pv, pline, psecs = run_python(space, PAT, answers, answer, PREFIX)
        uv, _, _ = run_c(answer, PREFIX, ["--no-prune"])
        tv, _, _ = run_c(answer, PREFIX, ["--tt-bits", "18"])   # forced eviction
        nline = len(cline.split())

        ok = cv == pv and cv == uv and cv == tv and nline == cv
        speed = f"{psecs / csecs:.0f}x" if csecs > 0.005 else "too fast to time"
        print(f"  {'PASS' if ok else 'FAIL'}  {answer}: C={cv} py={pv} "
              f"unpruned={uv} tiny-tt={tv} line={nline}w"
              f"   {csecs:.2f}s vs {psecs:.2f}s ({speed})")
        if not ok:
            why = []
            if cv != pv: why.append(f"py={pv}")
            if cv != uv: why.append(f"unpruned={uv}")
            if cv != tv: why.append(f"tiny-tt={tv} (KEY COLLISION)")
            if nline != cv: why.append(f"line is {nline} words for a value of {cv}")
            FAILS.append(f"{answer}: C={cv} but " + ", ".join(why))
        elif cline != pline:
            WARNS.append(f"{answer}: lines differ (both length {cv})")
            print(f"        warn: lines differ\n          C  {cline}\n          py {pline}")

    print()
    for w in WARNS:
        print(f"WARN: {w}")
    if FAILS:
        print(f"FAILED: {len(FAILS)} case(s): " + "; ".join(FAILS))
        return 1
    print("C port agrees with the reference on every case")
    return 0


if __name__ == "__main__":
    sys.exit(main())
