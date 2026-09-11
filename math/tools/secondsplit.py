"""The gap to optimal, split by grey count AND by CAUSE.

    python3 tools/secondsplit.py --opener slant \\
        --second e3=cripe --second e4=drice --second e5=drice --out FILE

Prefer the wrapper: bash solver/run-second-split.sh (from math/).

tools/secondloss.py answers "how much does each grey count cost us"; this answers
"and WHY".  Within each grey count the gap to optimal is split into the two
things that can be wrong with the strategy there:

    A   our second word, then a uniformly random consistent ANSWER   (the strategy)
    B   our second word, then OPTIMAL play                           (new here)
    C   optimal play throughout                        (the committed optimal tree)

    A - B   THE RANDOM TAIL.  What playing at random after the second word costs,
            with the word held fixed -- so it is purely the follow-up's fault.
    B - C   THE WORD CHOICE.  What committing to that one word costs, judged with
            the continuation held OPTIMAL -- so it is purely the word's fault.
    A - C   the whole gap, and the two parts sum to it exactly.

BELOW THE THRESHOLD THERE IS NO WORD, so B = C there by construction and the
entire gap is the random tail's.  That is not a special case in the arithmetic;
it falls out of there being nothing committed to blame.

ALL THREE ARE EXACT -- no simulation anywhere.

  * A is the memoised recursion solver/secondexact.c uses (and this file states
    again, in Python, which is what checksecondexact.py diffs it against):
    T(S) = |S| + (1/|S|) * sum over g in S of sum over parts P != {g} of T(P).
  * B needs the OPTIMAL total from each state our word leaves, which is a real
    search -- but those states are tiny (a handful of answers after two guesses),
    and guesses giving the same partition of a small set are interchangeable, so
    deduping the 12972 by their partition leaves a few dozen distinct moves.
  * C is read from the committed optimal tree for this opener.

ONE ASYMMETRY, STATED BECAUSE IT IS REAL: C is the CAPPED optimum -- the minimum
subject to solving every answer within six, which is what optturns computed --
while A and B are uncapped.  A capped optimum is never below the unconstrained
one, so `B - C` is if anything a slight UNDER-statement of the word's cost.  The
run reports any bucket where B < C, which would mean the cap is binding there.
"""

import gzip
import os
import sys
import time
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from wordle import ALL_GREEN, load_words  # noqa: E402

COLUMNS = ("grays,second,answers,share,optimal,with_word_optimal,strategy,"
           "gap,from_random_tail,from_word_choice,contrib,pct_of_gap")


def parse_args(argv):
    a = {"opener": None, "out": None, "seconds": {}, "min_grays": 3}
    i = 0
    while i < len(argv):
        k = argv[i]
        if k == "--second":
            spec = argv[i + 1]
            g, _, w = spec.partition("=")
            if not w:
                raise SystemExit("--second takes GROUP=WORD, e.g. --second e3=cripe")
            a["seconds"][g] = w
            i += 2
            continue
        if k == "--no-out":
            a["out"] = False
            i += 1
            continue
        kk = k.lstrip("-").replace("-", "_")
        if kk not in a:
            raise SystemExit("unknown argument: %s" % k)
        a[kk] = int(argv[i + 1]) if kk == "min_grays" else argv[i + 1]
        i += 2
    if not a["opener"]:
        raise SystemExit("--opener is required")
    if not a["seconds"]:
        raise SystemExit(
            "at least one --second GROUP=WORD is required: the split is about "
            "which word was committed to, so there is nothing to attribute "
            "without one")
    if a["out"] is None:
        raise SystemExit("--out is required (or --no-out).  Use the wrapper: "
                         "bash solver/run-second-split.sh")
    return a


def tiles(guess, answer):
    """The reply as tiles, from the STRINGS, by the multiset rule."""
    out = [2 if g == a else 0 for g, a in zip(guess, answer)]
    left = Counter(a for g, a in zip(guess, answer) if g != a)
    for i, g in enumerate(guess):
        if out[i] == 0 and left[g]:
            out[i] = 1
            left[g] -= 1
    return out


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    na = len(answers)
    pat = np.array(load_patterns())
    pos = {w: i for i, w in enumerate(guesses)}
    if a["opener"] not in pos:
        raise SystemExit("%r is not a legal guess" % a["opener"])
    og = pos[a["opener"]]
    ans2g = np.array([pos[w] for w in answers])

    # --- C: the committed optimal tree
    tree = os.path.join(paths.TREES, a["opener"] + ".txt.gz")
    if not os.path.exists(tree):
        raise SystemExit("no optimal tree for %r at %s" % (a["opener"], tree))
    cost = {}
    with gzip.open(tree, "rt") as f:
        for line in f:
            p = line.split()
            if len(p) >= 3:
                cost[p[0]] = int(p[1])
    if sorted(cost) != sorted(answers):
        raise SystemExit("%s does not cover the answers exactly" % tree)
    opt = np.array([cost[w] for w in answers], dtype=np.int64)

    grays = np.array([sum(1 for t in tiles(a["opener"], w) if t == 0)
                      for w in answers], dtype=np.int8)

    memoT, memoO = {}, {}

    def T(S):
        """Total guesses over S, playing a uniform random consistent answer."""
        n = len(S)
        if n <= 1:
            return float(n)
        v = memoT.get(S)
        if v is not None:
            return v
        tot = float(n)
        for g in S:
            parts = {}
            for x in S:
                if x != g:
                    parts.setdefault(int(pat[ans2g[g]][x]), []).append(x)
            for p in parts.values():
                tot += T(tuple(p)) / n
        memoT[S] = tot
        return tot

    def OPT(S):
        """Total guesses over S under OPTIMAL play, any legal guess, no cap.

        Guesses that partition S identically are interchangeable, so the 12972
        collapse to the distinct rows of the matrix restricted to S -- a few dozen
        for the small states this is asked about, which is what makes an exact
        search affordable here at all.
        """
        n = len(S)
        if n <= 1:
            return float(n)
        v = memoO.get(S)
        if v is not None:
            return v
        cols = pat[:, list(S)]
        rows = np.unique(cols, axis=0)
        # ORDER THE MOVES AND BOUND THE REST, which is what makes this a search
        # rather than an enumeration.  Without both, a state of a few dozen
        # answers never returns: the distinct partitions number in the thousands
        # and each spawns its own subtree.  Evenest split first (sum of squared
        # part sizes, the repo's one ranking rule), and OPT(P) >= 2|P| - 1 by the
        # same induction the random tail's bound uses -- the best a guess can do
        # is shatter, which costs one for the word played and two for the rest.
        scored = []
        for r in rows:
            parts = {}
            for i, code in enumerate(r):
                if int(code) == ALL_GREEN:
                    continue                    # that answer is found by playing it
                parts.setdefault(int(code), []).append(S[i])
            # A GUESS THAT SPLITS NOTHING RECURSES ON ITS OWN SET, and is never
            # optimal anyway: it spends a turn and leaves the state as it was.
            if any(len(p) == n for p in parts.values()):
                continue
            ps = list(parts.values())
            scored.append((sum(len(p) * len(p) for p in ps), ps))
        scored.sort(key=lambda t: t[0])
        best = None
        for _, ps in scored:
            floor = float(n) + sum(2.0 * len(p) - 1.0 for p in ps)
            if best is not None and floor >= best:
                continue                        # cannot beat what we have
            tot = float(n)
            for i, p in enumerate(ps):
                tot += OPT(tuple(p))
                if best is not None:
                    rest = sum(2.0 * len(q) - 1.0 for q in ps[i + 1:])
                    if tot + rest >= best:
                        tot = None
                        break
            if tot is not None and (best is None or tot < best):
                best = tot
        memoO[S] = best
        return best

    print("EV loss for %s, by grey count and by CAUSE" % a["opener"])
    print("  committed words: %s"
          % "  ".join("%s=%s" % (g, w) for g, w in sorted(a["seconds"].items())))
    t0 = time.time()

    rows = []
    total_gap = 0.0
    for k in range(6):
        sel = np.flatnonzero(grays == k)
        if not len(sel):
            continue
        word = a["seconds"].get("e%d" % k)
        if word is None and k >= a["min_grays"]:
            word = a["seconds"].get("g%d" % a["min_grays"])
        C = float(opt[sel].sum())
        # group the bucket's answers by the opener's reply
        first = {}
        for i in sel:
            first.setdefault(int(pat[og][i]), []).append(int(i))
        A = B = 0.0
        if word is None:
            # no word committed: the follow-up plays straight away, and the
            # optimal alternative is simply the tree -- so B is C by definition
            for p, grp in first.items():
                A += len(grp)                       # the opener itself
                if p != ALL_GREEN:
                    A += T(tuple(sorted(grp)))
            B = C
        else:
            wg = pos[word]
            for p, grp in first.items():
                A += 2 * len(grp)
                B += 2 * len(grp)
                sub = {}
                for i in grp:
                    sub.setdefault(int(pat[wg][i]), []).append(i)
                for q, part in sub.items():
                    if q == ALL_GREEN:
                        continue                    # the word itself won
                    t = tuple(sorted(part))
                    A += T(t)
                    B += OPT(t)
        rows.append(dict(grays=k, word=word or "", n=len(sel), C=C, B=B, A=A))
        total_gap += A - C
        print("  grays %d: %d answers  (%.0fs)" % (k, len(sel), time.time() - t0))

    print()
    print("  %5s %-7s %8s %8s %9s %9s %9s %9s %9s %8s"
          % ("grays", "word", "answers", "share", "optimal", "w/ word",
             "strategy", "tail", "word", "% of gap"))
    for r in rows:
        share = r["n"] / na
        gap, tail, choice = r["A"] - r["C"], r["A"] - r["B"], r["B"] - r["C"]
        if choice < -1e-9:
            print("  NOTE: grays %d has B < C by %.4f -- the six-guess cap binds "
                  "on the optimal side there" % (r["grays"], -choice / r["n"]))
        print("  %5d %-7s %8d %7.1f%% %9.4f %9.4f %9.4f %9.4f %9.4f %7.1f%%"
              % (r["grays"], r["word"] or "-", r["n"], 100 * share,
                 r["C"] / r["n"], r["B"] / r["n"], r["A"] / r["n"],
                 tail / r["n"], choice / r["n"],
                 100 * gap / total_gap if total_gap else 0))
    tot_tail = sum(r["A"] - r["B"] for r in rows)
    tot_choice = sum(r["B"] - r["C"] for r in rows)
    print()
    print("  optimal (capped, same opener)   %.5f" % (float(opt.sum()) / na))
    print("  strategy                        %.5f"
          % (sum(r["A"] for r in rows) / na))
    print("  gap                             %.5f   = %.5f from the random tail "
          "+ %.5f from the word choice"
          % (total_gap / na, tot_tail / na, tot_choice / na))

    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        with open(a["out"], "w") as f:
            f.write("# EV loss for the opener %s, by grey count and by CAUSE\n"
                    % a["opener"])
            f.write("# words: %s\n" % "  ".join("%s=%s" % kv for kv in
                                                sorted(a["seconds"].items())))
            f.write("# optimal = the committed tree (CAPPED at six); with_word_"
                    "optimal = our word then OPTIMAL play;\n# strategy = our word "
                    "then a random consistent answer.  All three exact.\n")
            f.write("# gap = from_random_tail + from_word_choice, per answer in "
                    "the bucket; contrib is share-weighted.\n")
            f.write(COLUMNS + "\n")
            for r in rows:
                share = r["n"] / na
                gap = r["A"] - r["C"]
                f.write("%d,%s,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.4f\n"
                        % (r["grays"], r["word"] or "", r["n"], share,
                           r["C"] / r["n"], r["B"] / r["n"], r["A"] / r["n"],
                           gap / r["n"], (r["A"] - r["B"]) / r["n"],
                           (r["B"] - r["C"]) / r["n"], gap / na,
                           100 * gap / total_gap if total_gap else 0))
        print("\nwrote %s" % a["out"])


if __name__ == "__main__":
    main(sys.argv[1:])
