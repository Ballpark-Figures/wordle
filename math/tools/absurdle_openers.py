"""Stage 2: which OPENERS still admit a shortest (4-guess) win against Absurdle.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-absurdle-openers.sh              # from math/, or anywhere
    bash solver/run-absurdle-openers.sh --limit 200  # a prefix of the order

THE QUESTION, precisely. Stage 1 proved the floor is 4 guesses on our lists. This
asks, for every one of the 12972 legal openers, whether a 4-guess win exists AFTER
it — so the openers answering yes are exactly the ones tied for optimal. It reports
ONE witness continuation per opener, not all of them; enumerating every tied
sequence is stage 3.

WHY THE TEST IS EXACT, not a screen. A 4-guess win from opener g1 needs the
candidate set to be a SINGLETON after three guesses, and one guess can reduce a
set to a singleton only by giving every candidate a DISTINCT pattern — so the set
it acts on holds at most 238 words, the attainable-pattern count. Hence: take the
state S1 after g1, keep only the second guesses leaving |S2| <= 238 (the rest
cannot possibly finish in time), and for each ask whether ANY of the 12972 guesses
shatters S2 into singletons. Nothing is discarded that could have won.

ORDER, named because a stopped run reports a prefix of it: openers are visited by
ASCENDING |S1| — the size of the state they leave — ties by guess index. Within an
opener, second guesses are visited by ascending |S2|, so the ascending order also
supplies the cutoff: once |S2| exceeds 238 every later guess does too. --limit
takes a PREFIX of that order, so a limited run is "the openers that shrink the set
most", never a sample.

RESUMABLE. One CSV row per opener, flushed as it is decided; re-running skips the
words already in the file, so a Ctrl-C costs at most the opener in flight. States
are memoised by content, which matters more than it looks: openers that are
anagrams of each other leave the SAME all-grey state and therefore share their
whole continuation.

Results are for OUR word lists (2315 answers / 12972 guesses), which are NOT
verified to be Absurdle's -- see the Absurdle section of the repo CLAUDE.md.
"""

import hashlib
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from csvout import fresh_file                                             # noqa: E402
from absurdle import respond, sizes_all  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402

# Attainable feedback patterns: 3**5 = 243 encodings, less the five with 4 greens
# and 1 yellow, which cannot occur. An upper bound on how many buckets one guess
# can make, hence on the size of a set one guess can shatter into singletons.
MAX_PATTERNS = 238

COLUMNS = "word,wins4,g2,g3,g4,seconds"


def digest(idx):
    """Content key for a candidate set — 16 bytes whatever its size."""
    return hashlib.blake2b(np.ascontiguousarray(idx, dtype=np.int32).tobytes(),
                           digest_size=16).digest()


def parse_args(argv):
    out, limit, self_test = None, None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 2
        elif a == "--self-test":
            self_test = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if out is None and not self_test:
        # The strturns lesson: a search that prints its answer and saves nothing
        # loses the run. Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-absurdle-openers.sh")
    return out, limit, self_test


def load_done(path):
    """Openers already decided in a previous run."""
    done = set()
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("word,"):
                    continue
                w = line.split(",", 1)[0].strip()
                if w:
                    done.add(w)
    return done


def solve_state(pat, s1, ng, memo2):
    """A 4-guess win from state s1? Returns (g2, g3) or None.

    Exact: every second guess leaving 238 or fewer candidates is tried, and each
    resulting state is tested against all `ng` guesses for a shatter.
    """
    sizes1 = sizes_all(pat, s1)
    order = np.lexsort((np.arange(ng), sizes1))
    for g2 in order:
        g2 = int(g2)
        if sizes1[g2] > MAX_PATTERNS:
            break                      # ascending, so no later guess qualifies
        _, s2 = respond(pat, s1, g2)
        key = digest(s2)
        g3 = memo2.get(key)
        if g3 is None:
            sizes2 = sizes_all(pat, s2)
            # a shatterer leaves exactly one candidate; ties break on the lowest
            # guess index, which is what argmin returns
            g3 = int(sizes2.argmin()) if sizes2.min() == 1 else -1
            memo2[key] = g3
        if g3 >= 0:
            return g2, g3
    return None


def run(pat, guesses, answers, out, limit):
    ng, na = len(guesses), len(answers)
    root = np.arange(na)
    t0 = time.time()

    sizes0 = sizes_all(pat, root)
    order0 = np.lexsort((np.arange(ng), sizes0))
    if limit is not None:
        order0 = order0[:limit]

    done = load_done(out)
    fresh = out and fresh_file(out)
    f = open(out, "a") if out else None
    if f and fresh:
        f.write("# Openers admitting a SHORTEST (4-guess) win against Absurdle.\n")
        f.write("# Word lists: OUR original Wordle %d answers / %d guesses, NOT\n"
                % (na, ng))
        f.write("# verified to match Absurdle's. Host rule from qntm's FAQ,\n")
        f.write("# unverified against the live game. See CLAUDE.md.\n")
        f.write("# Exact per opener: every 2nd guess leaving <= %d candidates is\n"
                % MAX_PATTERNS)
        f.write("# tried against all %d 3rd guesses. One witness per opener.\n" % ng)
        f.write("# Visit order: ascending candidates-left after the opener.\n")
        f.write(COLUMNS + "\n")
        f.flush()
        f.flush()

    memo1, memo2 = {}, {}
    wins = skipped = 0
    for n, g1 in enumerate(order0, 1):
        g1 = int(g1)
        word = guesses[g1]
        if word in done:
            skipped += 1
            continue
        t1 = time.time()
        _, s1 = respond(pat, root, g1)
        key = digest(s1)
        if key in memo1:
            found = memo1[key]
        else:
            found = solve_state(pat, s1, ng, memo2)
            memo1[key] = found

        if found:
            g2, g3 = found
            _, s2 = respond(pat, s1, g2)
            _, s3 = respond(pat, s2, g3)
            if len(s3) != 1:
                raise SystemExit("shatterer left %d candidates for %s" % (len(s3), word))
            g4 = answers[int(s3[0])]
            row = "%s,1,%s,%s,%s,%.2f" % (word, guesses[g2], guesses[g3], g4,
                                          time.time() - t1)
            wins += 1
        else:
            row = "%s,0,,,,%.2f" % (word, time.time() - t1)

        if f:
            f.write(row + "\n")
            f.flush()
        elapsed = time.time() - t0
        rate = (n - skipped) / elapsed if elapsed > 0 else 0
        left = (len(order0) - n) / rate if rate > 0 else 0
        print("[%5d/%5d] %-6s %s  %d left after it | %d wins | %.2f openers/s | "
              "eta %.1fh" % (n, len(order0), word, "WIN " if found else "none",
                             sizes0[g1], wins, rate, left / 3600.0))
        sys.stdout.flush()

    if f:
        f.close()
    print("\n%d openers examined, %d admit a 4-guess win, %d skipped as already done"
          % (len(order0) - skipped, wins, skipped))
    print("%.1fs total" % (time.time() - t0))
    if out:
        print("wrote %s" % out)


def self_test(pat, guesses, answers):
    """Exercise the whole loop on a TOY slice — not the real sweep."""
    import tempfile
    ng, na = 400, 120
    small = np.ascontiguousarray(pat[:ng, :na])
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "toy.csv")
        run(small, guesses[:ng], answers[:na], out, limit=6)
        rows = [l for l in open(out) if not l.startswith("#") and not l.startswith("word,")]
        assert len(rows) == 6, "expected 6 rows, got %d" % len(rows)
        run(small, guesses[:ng], answers[:na], out, limit=6)   # resume: adds none
        rows2 = [l for l in open(out) if not l.startswith("#") and not l.startswith("word,")]
        assert len(rows2) == 6, "resume rewrote rows: %d" % len(rows2)
    print("\nself-test PASS: 6 toy openers decided, resume skipped all 6")


if __name__ == "__main__":
    out, limit, testing = parse_args(sys.argv[1:])
    pat = load_patterns()
    guesses = load_words("guess")
    answers = load_words("mystery")
    if testing:
        self_test(pat, guesses, answers)
    else:
        run(pat, guesses, answers, out if out else None, limit)
