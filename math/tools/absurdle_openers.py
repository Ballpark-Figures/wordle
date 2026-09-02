"""Stage 2: the OPENERS that tie for optimal against Absurdle — a 4-guess win.

Run it through the wrapper, which sets both output paths and tees a log:

    bash solver/run-absurdle-openers.sh                 # from math/, or anywhere
    bash solver/run-absurdle-openers.sh --order asc     # promising openers first
    bash solver/run-absurdle-openers.sh --limit 200     # a prefix of the order

THE QUESTION, precisely. Stage 1 proved the floor is 4 guesses on our lists. This
asks which openers still admit a 4-guess win, so the emitted list is exactly the
openers TIED for optimal — one witness continuation each. Enumerating every tied
SEQUENCE is stage 3.

TWO FILES, AND THE DELIVERABLE HOLDS ONLY THE OPTIMAL OPENERS.

  --out (committed, data/shared/absurdle/)  the OPTIMA: one row per opener that
      wins in 4, with its witness. Nothing else — an opener that cannot win in 4
      is not a result here, it is search debris.
  --checkpoint (gitignored, data/local/absurdle/)  every opener decided so far
      with its verdict, which is what makes the run resumable. The deliverable is
      a pure projection of it and is REBUILT from it at every startup, so the two
      cannot drift and deleting the shared file costs nothing.

WHY THE TEST IS EXACT, not a screen. A 4-guess win from opener g1 needs the
candidate set to be a SINGLETON after three guesses, and one guess can reduce a
set to a singleton only by giving every candidate a DISTINCT pattern — so the set
it acts on holds at most 238 words, the attainable-pattern count. Hence: take the
state S1 after g1, keep only the second guesses leaving |S2| <= 238 (the rest
cannot possibly finish in time), and for each ask whether ANY of the 12972 guesses
shatters S2 into singletons. Nothing that could have won is discarded, so a `0`
verdict is a PROVED negative, not "not found yet".

ORDER, named because a stopped run covers a prefix of it. `--order` takes the
size of the state an opener leaves — exhaustively known, it is just that opener's
largest bucket — ties alphabetical either way:

    desc (default)  the openers that shrink the set LEAST, first. These are the
                    CHEAP ones: few of their second guesses get under 238, so the
                    scan cuts out early. They are also the ones least likely to
                    win, so early progress is fast but mostly negative.
    asc             the openers that shrink the set most, first — the likely
                    OPTIMA. Winners land in the deliverable early; the openers
                    that turn out to have no 4-guess win are the expensive ones
                    and get pushed to the end.

Neither changes the ANSWER: every opener is decided exhaustively, so the finished
list is identical. The order decides only what a stopped run has covered.

RESUMABLE. One checkpoint row per opener, flushed as it is decided; a re-run
skips the words already there, so a Ctrl-C costs at most the opener in flight.
States are memoised by content, which matters more than it looks: openers that
are anagrams leave the SAME all-grey state and share their whole continuation.

Results are for OUR word lists (2315 answers / 12972 guesses), which are NOT
verified to be Absurdle's -- see the Absurdle section of the repo CLAUDE.md.
"""

import hashlib
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from absurdle import respond, sizes_all  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from wordle import load_words  # noqa: E402

# Attainable feedback patterns: 3**5 = 243 encodings, less the five with 4 greens
# and 1 yellow, which cannot occur. An upper bound on how many buckets one guess
# can make, hence on the size of a set one guess can shatter into singletons.
MAX_PATTERNS = 238

WINNER_COLUMNS = "word,g2,g3,g4,left_after_opener,seconds"
CHECK_COLUMNS = "word,wins4,left,g2,g3,g4,seconds"


def digest(idx):
    """Content key for a candidate set — 16 bytes whatever its size."""
    return hashlib.blake2b(np.ascontiguousarray(idx, dtype=np.int32).tobytes(),
                           digest_size=16).digest()


def parse_args(argv):
    out, check, limit, order, self_test = None, None, None, "desc", False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--checkpoint":
            check = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 2
        elif a == "--order":
            order = argv[i + 1]; i += 2
        elif a == "--self-test":
            self_test = True; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if order not in ("asc", "desc"):
        raise SystemExit("--order must be asc or desc, not %r" % order)
    if out is None and not self_test:
        # The strturns lesson: a search that prints its answer and saves nothing
        # loses the run. Refuse rather than default.
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-absurdle-openers.sh")
    return out, check, limit, order, self_test


def load_checkpoint(path):
    """word -> its decided row, from a previous run."""
    rows = {}
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.startswith("#") or line.startswith("word,"):
                    continue
                parts = line.rstrip("\n").split(",")
                if len(parts) == 7 and parts[0]:
                    rows[parts[0]] = parts
    return rows


def rebuild_winners(path, rows, na, ng):
    """Rewrite the deliverable from the checkpoint — a pure projection of it."""
    if not path:
        return
    with open(path, "w") as f:
        f.write("# Openers TIED FOR OPTIMAL against Absurdle: those admitting a\n")
        f.write("# 4-guess win, 4 being the floor proved by absurdle_shortest.py.\n")
        f.write("# One witness continuation each; every tied SEQUENCE is stage 3.\n")
        f.write("# Word lists: OUR original Wordle %d answers / %d guesses, NOT\n" % (na, ng))
        f.write("# verified to match Absurdle's. Host rule from qntm's FAQ,\n")
        f.write("# unverified against the live game. See CLAUDE.md.\n")
        f.write("# Exact per opener: every 2nd guess leaving <= %d candidates is\n" % MAX_PATTERNS)
        f.write("# tried against all %d 3rd guesses, so an omission is a PROVED\n" % ng)
        f.write("# negative -- but only for the openers reached so far.\n")
        f.write(WINNER_COLUMNS + "\n")
        for word, parts in rows.items():
            if parts[1] == "1":
                # checkpoint: word,wins4,left,g2,g3,g4,seconds -- a superset, so
                # the deliverable is a pure reordering of these fields
                f.write("%s,%s,%s,%s,%s,%s\n" % (word, parts[3], parts[4], parts[5],
                                                 parts[2], parts[6]))


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


def run(pat, guesses, answers, out, check, limit, order):
    ng, na = len(guesses), len(answers)
    root = np.arange(na)
    t0 = time.time()

    sizes0 = sizes_all(pat, root)
    # ties alphabetical in BOTH directions, so `desc` is descending size rather
    # than a literal reversal (which would also flip the tie-break)
    keys = sizes0 if order == "asc" else -sizes0.astype(np.int64)
    order0 = np.lexsort((np.arange(ng), keys))
    if limit is not None:
        order0 = order0[:limit]

    done = load_checkpoint(check)
    rebuild_winners(out, done, na, ng)
    wf = open(out, "a") if out else None
    cf = open(check, "a") if check else None
    if cf and os.path.getsize(check) == 0:
        cf.write("# Every opener decided, with its verdict. Regenerable search\n")
        cf.write("# state, not a deliverable: the shared winners file is rebuilt\n")
        cf.write("# from this at every startup.\n")
        cf.write(CHECK_COLUMNS + "\n")
        cf.flush()

    memo1, memo2 = {}, {}
    wins = skipped = 0
    for n, g1 in enumerate(order0, 1):
        g1 = int(g1)
        word = guesses[g1]
        if word in done:
            skipped += 1
            wins += done[word][1] == "1"
            continue
        t1 = time.time()
        _, s1 = respond(pat, root, g1)
        key = digest(s1)
        if key in memo1:
            found = memo1[key]
        else:
            found = solve_state(pat, s1, ng, memo2)
            memo1[key] = found

        secs = time.time() - t1
        if found:
            g2, g3 = found
            _, s2 = respond(pat, s1, g2)
            _, s3 = respond(pat, s2, g3)
            if len(s3) != 1:
                raise SystemExit("shatterer left %d candidates for %s" % (len(s3), word))
            g4 = answers[int(s3[0])]
            wins += 1
            if wf:
                wf.write("%s,%s,%s,%s,%d,%.2f\n"
                         % (word, guesses[g2], guesses[g3], g4, sizes0[g1], secs))
                wf.flush()
            if cf:
                cf.write("%s,1,%d,%s,%s,%s,%.2f\n"
                         % (word, sizes0[g1], guesses[g2], guesses[g3], g4, secs))
        elif cf:
            cf.write("%s,0,%d,,,,%.2f\n" % (word, sizes0[g1], secs))
        if cf:
            cf.flush()

        elapsed = time.time() - t0
        rate = (n - skipped) / elapsed if elapsed > 0 else 0
        left = (len(order0) - n) / rate if rate > 0 else 0
        print("[%5d/%5d] %-6s %s  %4d left after it | %d optimal so far | "
              "%.2f openers/s | eta %.1fh"
              % (n, len(order0), word, "OPTIMAL" if found else "  no   ",
                 sizes0[g1], wins, rate, left / 3600.0))
        sys.stdout.flush()

    for f in (wf, cf):
        if f:
            f.close()
    print("\n%d openers decided this run, %d skipped as already done" %
          (len(order0) - skipped, skipped))
    print("%d of the %d examined are TIED FOR OPTIMAL (win in 4)" % (wins, len(order0)))
    print("%.1fs total" % (time.time() - t0))
    if out:
        print("optima: %s" % out)


def self_test(pat, guesses, answers):
    """Exercise the whole loop on a TOY slice — not the real sweep."""
    import tempfile
    ng, na = 400, 120
    small = np.ascontiguousarray(pat[:ng, :na])
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "toy.csv")
        chk = os.path.join(d, "toy_checkpoint.csv")
        for order in ("desc", "asc"):
            open(out, "w").close()
            open(chk, "w").close()
            run(small, guesses[:ng], answers[:na], out, chk, 6, order)
            rows = [l for l in open(chk) if l[0] not in "#w"]
            assert len(rows) == 6, "%s: expected 6 checkpoint rows, got %d" % (order, len(rows))
            wins = [l for l in open(out) if l[0] not in "#w"]
            assert len(wins) == sum(r.split(",")[1] == "1" for r in rows), \
                "%s: winners file does not match the checkpoint" % order
            # resume adds nothing, and the deliverable survives being deleted
            os.remove(out)
            run(small, guesses[:ng], answers[:na], out, chk, 6, order)
            rows2 = [l for l in open(chk) if l[0] not in "#w"]
            assert len(rows2) == 6, "%s: resume rewrote rows: %d" % (order, len(rows2))
            wins2 = [l for l in open(out) if l[0] not in "#w"]
            assert wins2 == wins, "%s: rebuild lost winners" % order
    print("\nself-test PASS: both orders decide 6 toy openers, resume skips all 6,")
    print("and the deliverable rebuilds identically after being deleted")


if __name__ == "__main__":
    out, check, limit, order, testing = parse_args(sys.argv[1:])
    pat = load_patterns()
    guesses = load_words("guess")
    answers = load_words("mystery")
    if testing:
        self_test(pat, guesses, answers)
    else:
        run(pat, guesses, answers, out if out else None, check, limit, order)
