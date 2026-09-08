"""THE GATE for the Letroso rules and solver.  Exits nonzero, so it gates.

Run it alongside solver/validate.sh and tools/checkpatterns.py after touching
letroso.py, letroso_kernel.py or letroso_topk.py:

    python3 tools/checkletroso.py           # ~30s
    python3 tools/checkletroso.py --wide    # bigger exhaustive sweeps

WHAT IT PINS, and why each check exists.

  1. THE TWELVE TUTORIAL ROWS.  The game's own instructions modal works three
     examples plus the win in each of its three languages, with the classes
     baked into the markup.  Reproducing all twelve is the ONLY external
     evidence that the recovered algorithm is the game's; everything else here
     checks us against ourselves.
  2. feedback vs feedback_ref, EXHAUSTIVELY on small alphabets.  feedback_ref is
     a literal port of the shipped zT() and enumerates every minimum-cost path;
     feedback explores only optimal alignments.  A greedy left-to-right version
     was tried and was WRONG (see letroso.feedback's docstring), which is
     exactly the class of bug this catches.
  3. THE NUMBA KERNEL vs feedback, on real word pairs.  Same function, third
     implementation, different packing -- so a bit-order slip shows.
  4. THE ROOT SCORING vs an independent python implementation that buckets with
     a dict and never touches the kernel or its hash table.
  5. THE LENGTH PRIOR: both weightings sum to 1, and `lengths` really does give
     every length an equal share.
  6. A COVERAGE TALLY that FAILS if any awkward feature never fired -- repeated
     letters, accents, start, end, present, absent, the one-match downgrade, and
     a genuine alignment tie.  A pass that never exercised the hard cases is not
     a pass, and the tie case is the one with a known ambiguity, so it must be
     seen rather than assumed rare.
"""

import argparse
import itertools
import tempfile
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import letroso as L
import letroso_kernel as K
import letroso_topk as T

TUTORIAL = [
    ("example", "permit",   "p:head e:head r:absent m:present i:absent t:absent"),
    ("example", "imply",    "i:absent m:head p:tail l:tail y:absent"),
    ("example", "excuse",   "e:head+start x:tail c:absent u:absent s:absent e:head+end"),
    ("example", "example",  "e:head+start x:tail a:tail m:tail p:tail l:tail e:tail+end"),
    ("exemplo", "posse",    "p:head o:head s:absent s:absent e:present"),
    ("exemplo", "ampla",    "a:absent m:head p:tail l:tail a:absent"),
    ("exemplo", "existo",   "e:head+start x:tail i:absent s:absent t:absent o:head+end"),
    ("exemplo", "exemplo",  "e:head+start x:tail e:tail m:tail p:tail l:tail o:tail+end"),
    ("ejemplo", "pobre",    "p:head o:head b:absent r:absent e:present"),
    ("ejemplo", "ampla",    "a:absent m:head p:tail l:tail a:absent"),
    ("ejemplo", "ejército", "e:head+start j:tail é:tail r:absent c:absent i:absent t:absent o:head+end"),
    ("ejemplo", "ejemplo",  "e:head+start j:tail e:tail m:tail p:tail l:tail o:tail+end"),
]

seen = {k: 0 for k in ("repeat", "accent", "start", "end", "present",
                       "absent", "one_present", "tie")}
fails = []


def note(pattern, start, end, answer, guess):
    if len(set(guess)) < len(guess) or len(set(answer)) < len(answer):
        seen["repeat"] += 1
    if L.strip_accents(answer) != answer or L.strip_accents(guess) != guess:
        seen["accent"] += 1
    seen["start"] += bool(start)
    seen["end"] += bool(end)
    seen["present"] += L.PRESENT in pattern
    seen["absent"] += L.ABSENT in pattern
    matched = sum(1 for d in pattern if d in (L.HEAD, L.TAIL))
    if matched == 0 and L.PRESENT in pattern:
        seen["one_present"] += 1


def check(name, ok, detail=""):
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wide", action="store_true", help="bigger exhaustive sweeps")
    args = ap.parse_args()

    print("1. the game's own twelve tutorial rows")
    bad = []
    for ans, g, exp in TUTORIAL:
        got = " ".join("%s:%s" % (c, k) for c, k in L.classes(ans, g))
        if got != exp:
            bad.append("%s/%s" % (ans, g))
        pat, st, en = L.feedback(ans, g)
        note(pat, st, en, ans, g)   # the es rows are the only accented data
    check("12 tutorial rows reproduced", not bad, ",".join(bad))

    print("\n2. feedback vs feedback_ref, exhaustive")
    sweeps = [("ab", 6), ("abc", 4), ("abcd", 3)]
    if args.wide:
        sweeps = [("ab", 8), ("abc", 5), ("abcd", 4)]
    total = 0
    for alpha, ml in sweeps:
        words = ["".join(p) for k in range(1, ml + 1)
                 for p in itertools.product(alpha, repeat=k)]
        n = d = 0
        for a in words:
            for g in words:
                n += 1
                fa = L.feedback(a, g)
                if fa != L.feedback_ref(a, g):
                    d += 1
                note(fa[0], fa[1], fa[2], a, g)
        total += n
        check("alpha=%r len<=%d  (%d pairs)" % (alpha, ml, n), d == 0,
              "%d mismatches" % d if d else "")
    print("     %d pairs checked" % total)

    print("\n3. the numba kernel vs feedback, on real words")
    guesses = L.load_words("guess")
    answers = L.load_words("mystery")
    random.seed(11)
    pairs = [(random.choice(answers), random.choice(guesses))
             for _ in range(4000 if not args.wide else 20000)]
    best, stack, left = K.scratch()
    Wa, La = K.encode_words([p[0] for p in pairs])
    Wg, Lg = K.encode_words([p[1] for p in pairs])
    d = 0
    for i, (a, g) in enumerate(pairs):
        pat, st, en = L.feedback(a, g)
        note(pat, st, en, a, g)
        G = len(g)
        want = 0
        for j, dg in enumerate(pat):
            want |= dg << (2 * (G - 1 - j))
        want |= (int(st) << (2 * G)) | (int(en) << (2 * G + 1))
        if K.fb_code(Wa[i], int(La[i]), Wg[i], int(Lg[i]), best, stack, left) != want:
            d += 1
    check("kernel matches feedback on %d real pairs" % len(pairs), d == 0,
          "%d mismatches" % d if d else "")

    print("\n4. root scoring vs an independent python implementation")
    random.seed(12)
    gs = random.sample(guesses, 40)
    ans = random.sample(answers, 400)
    w = T.weights(ans, "lengths")
    sc = T.rank_root(gs, ans, w)
    d = 0
    for i, g in enumerate(gs):
        bins = {}
        for j, a in enumerate(ans):
            key = L.feedback(a, g)
            c, s = bins.get(key, (0, 0.0))
            bins[key] = (c + 1, s + w[j])
        win = L.feedback(g, g)
        ref = sum(c * s for k, (c, s) in bins.items() if k != win)
        if abs(ref - sc[i]) > 1e-9:
            d += 1
    check("root scores match on %d guesses x %d answers" % (len(gs), len(ans)),
          d == 0, "%d mismatches" % d if d else "")

    print("\n5. the length prior")
    for prior in T.PRIORS:
        w = T.weights(answers, prior)
        check("prior %r sums to 1" % prior, abs(w.sum() - 1.0) < 1e-12)
    w = T.weights(answers, "lengths")
    shares = {}
    for i, a in enumerate(answers):
        shares[len(a)] = shares.get(len(a), 0.0) + w[i]
    check("prior 'lengths' gives every length an equal share",
          max(shares.values()) - min(shares.values()) < 1e-12,
          "%d lengths at %.4f" % (len(shares), list(shares.values())[0]))
    check("every answer is a legal guess", not (set(answers) - set(guesses)))

    print("\n6. the tie-break's real exposure")
    random.seed(13)
    multi = several = ambiguous = 0
    for _ in range(5000):
        a_, g_ = random.choice(answers), random.choice(guesses)
        cands = L.candidates(a_, g_)
        if len(cands) > 1:
            multi += 1
        uniq = set(cands)
        if len(uniq) > 1:
            several += 1
            top = cands[0][0]
            if len({(st, en) for pat, st, en in uniq if pat == top}) > 1:
                ambiguous += 1
    print("     %4d of 5000 real pairs had several optimal alignments" % multi)
    print("     %4d produced more than one distinct resolved reply" % several)
    print("     %4d were GENUINELY AMBIGUOUS -- top pattern tied, flags differ"
          % ambiguous)
    # Only the last number is exposure: when the top PATTERNS differ the
    # lexicographic maximum is well defined and the game's sort finds it too.
    # It is 0 on real words, so the one place we could diverge from the live
    # game never comes up; the toy check below keeps the code path tested.
    check("tie-break never decides on real words", ambiguous == 0,
          "%d ambiguous pairs" % ambiguous)
    toy = L.candidates("aa", "a")
    seen["tie"] = 1 if len(set(toy)) > 1 else 0
    check("the ambiguous path still exists and is exercised (aa/a)",
          len(set(toy)) > 1)

    print("\n7. coverage -- every awkward feature must have fired")
    for k, v in sorted(seen.items()):
        check("exercised: %s" % k, v > 0, "%d times" % v)

    print("\n8. the solver's cost accounting, against an independent replay")
    random.seed(7)
    small_a = sorted(random.sample(answers, 60))
    small_g = sorted(set(small_a) | set(random.sample(guesses, 200)))
    solver = T.Solver(small_g, small_a, "lengths", k=1)
    cost, opener = solver.solve()
    # Play the SAME strategy out answer by answer and count real guesses.  This
    # shares no code with the recursion's accounting, so a double-counted or
    # dropped guess shows up as a mismatch.
    w = T.weights(small_a, "lengths")
    tot = 0.0
    for i, ans in enumerate(small_a):
        cand = np.arange(len(small_a))
        n = 0
        while True:
            n += 1
            g = small_g[int(solver._rank(cand, False)[0])]
            if g == ans:
                break
            code = L.encode(*L.feedback(ans, g))
            cand = np.array([c for c in cand
                             if L.encode(*L.feedback(small_a[c], g)) == code])
        tot += w[i] * n
    check("replay reproduces the solver's expected guesses", abs(tot - cost) < 1e-9,
          "replay %.6f vs solver %.6f (opener %s)" % (tot, cost, opener))

    print("\n9. the root scan's checkpoint survives an interruption")
    random.seed(5)
    ca = sorted(random.sample(answers, 300))
    cg = sorted(random.sample(guesses, 1400))
    cw = T.weights(ca, "lengths")
    cfp = T.fingerprint(cg, ca, "lengths")
    ck = os.path.join(tempfile.mkdtemp(), "rank.ckpt.npz")
    base = T.rank_root(cg, ca, cw)

    class _Boom(Exception):
        pass

    hits = [0]

    def _prog(done, total):
        hits[0] += 1
        if hits[0] == 2:
            raise _Boom
    try:
        T.rank_root(cg, ca, cw, progress=_prog, checkpoint=ck, fp=cfp)
    except _Boom:
        pass
    check("a checkpoint was written mid-scan", os.path.exists(ck))
    resumed = T.rank_root(cg, ca, cw, checkpoint=ck, fp=cfp)
    check("resuming reproduces the uninterrupted scan exactly",
          np.array_equal(base, resumed))
    foreign = T.rank_root(cg, ca, cw, checkpoint=ck, fp="deadbeefdeadbeef")
    check("a foreign-fingerprint checkpoint is ignored, not resumed from",
          np.array_equal(base, foreign))
    T.clear_checkpoint(ck)
    check("clear_checkpoint removes it", not os.path.exists(ck))

    # The chunked driver must score each chunk EXACTLY ONCE.  It once passed a
    # running total to a prange that started at zero, so every call re-scored
    # everything from the beginning -- 136x the work over a full run, with a
    # climbing ETA as the only symptom.  Counting is the cheap permanent guard.
    T.rank_root(cg, ca, cw)
    check("a fresh scan scores each chunk exactly once",
          T.rank_root.chunks_scored == T.rank_root.nchunk,
          "%d scorings for %d chunks" % (T.rank_root.chunks_scored,
                                         T.rank_root.nchunk))
    hits[0] = 0
    try:
        T.rank_root(cg, ca, cw, progress=_prog, checkpoint=ck, fp=cfp)
    except _Boom:
        pass
    first = T.rank_root.chunks_scored
    T.rank_root(cg, ca, cw, checkpoint=ck, fp=cfp)
    check("an interrupted-then-resumed scan also scores each chunk once",
          first + T.rank_root.chunks_scored == T.rank_root.nchunk,
          "%d + %d for %d chunks" % (first, T.rank_root.chunks_scored,
                                     T.rank_root.nchunk))
    T.clear_checkpoint(ck)

    print()
    if fails:
        print("FAILED: " + ", ".join(fails))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
