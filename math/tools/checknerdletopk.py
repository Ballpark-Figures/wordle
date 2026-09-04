"""THE GATE for the top-K Nerdle solver.

    python3 tools/checknerdletopk.py          # from math/, about a minute
    python3 tools/checknerdletopk.py --wide   # adds k=3 and width 7

Run it after any change to math/nerdle_topk.py, alongside tools/checknerdle.py.
Exits nonzero, so it works as a gate.

FOUR CHECKS, and the reason each exists:

  1. THE TWO IMPLEMENTATIONS AGREE.  The numba kernel and the plain-numpy
     reference implement the identical rules and share no code -- the reference
     computes feedback with wordle.pattern from the STRINGS, bins with
     np.bincount and recurses in Python.  They must return the same total and
     pick the same opener at every width and every k.  The objective is an
     integer, so this is exact agreement and not a tolerance.
  2. THE RANKING RULE IS WHAT IT CLAIMS.  The kernel's top-ranked guess is
     checked against an independently computed argmin of the sum of squared bin
     sizes, ties on lowest index.  This is the check that would catch the
     strturns bug the module docstring warns about, where packing the key beside
     the guess index made every guess tie at small nodes and turned the beam
     into alphabetical order.
  3. A GUESS WINS ITS WHOLE CLASS.  Given an answer list that is exactly one
     class of size n, the solver must return n -- one guess, everybody finished.
     Exact-match-only scoring would return n + 1 for a pair (guess one, then the
     other), so this single number separates the two rules sharply.  It is the
     rule with no precedent in the Wordle solvers, so it gets its own check.
  4. NO ALL-GREEN BIN SURVIVES.  An answer showing all-green is the guess
     itself, hence in its class, hence already won.  If a bucket ever carried
     the all-green code the class-mates were not being removed.

Then a coverage tally: the run FAILS if no class of more than one member was
ever won as a group, since a pass would otherwise say nothing about check 3's
rule in the search where it matters.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle_topk as NT  # noqa: E402
from nerdle import commutative_key, enumerate_guesses, is_answer  # noqa: E402
from wordle import pattern  # noqa: E402

_LISTS = {}


def lists(width):
    """The guess and answer lists for a width, enumerated IN MEMORY.

    Deliberately not read from data/shared: the small widths are not committed,
    and a gate that runs on a fresh clone without a prior sweep is worth more
    than one that reuses a file.  They are also fast -- width 6 is 2958 guesses.
    """
    if width not in _LISTS:
        g = enumerate_guesses(width, "split")
        _LISTS[width] = (g, [s for s in g if is_answer(s, width)])
    return _LISTS[width]


def game(width, k, use_numba=True, answers=None):
    g, a = lists(width)
    return NT.NerdleTopK(width=width, k=k, guesses=g,
                         answers=a if answers is None else answers,
                         use_numba=use_numba)

fails = []
wide = "--wide" in sys.argv[1:]


def bad(msg):
    fails.append(msg)
    print("  FAIL: %s" % msg)


# ------------------------------------------------- 1. the two implementations
print("1. the numba kernel against the numpy reference")
if not NT._HAVE_NUMBA:
    print("   SKIP  numba is not installed -- only one path exists to compare")
else:
    widths = [5, 6, 7] if wide else [5, 6]
    ks = [1, 2, 3] if wide else [1, 2]
    for w in widths:
        for k in ks:
            fast = game(w, k)
            slow = game(w, k, use_numba=False)
            tf, ts = fast.total_guesses(), slow.total_guesses()
            of, os_ = fast.opener(), slow.opener()
            if tf != ts:
                bad("width %d k=%d: numba total %d, reference %d" % (w, k, tf, ts))
            elif of != os_:
                bad("width %d k=%d: numba opens %r, reference opens %r" % (w, k, of, os_))
            else:
                print("   ok   width %d k=%d: total %d, expected %.4f, opens %s"
                      % (w, k, tf, tf / fast.NA, of))

# ------------------------------------------- 1b. the two root drivers agree
print("1b. the Python-driven root against the kernel's own recursion")
if not NT._HAVE_NUMBA:
    print("   SKIP  numba is not installed")
else:
    for w in ([5, 6, 7] if wide else [5, 6]):
        for k in ([1, 2] if wide else [1, 2]):
            g = game(w, k)
            S = np.arange(g.NA, dtype=np.int64)
            deep_cost, deep_g = NT._solve(g.G, g.A, S, g.gclass, g.aclass, w, k, 0,
                                          g._cnt, g._bins, g._touched)
            cost, gi = g.solve()
            if cost != int(deep_cost) or gi != int(deep_g):
                bad("width %d k=%d: the Python root gives (%d, %r), the recursion "
                    "gives (%d, %r)" % (w, k, cost, g.guess_words[gi],
                                        int(deep_cost), g.guess_words[int(deep_g)]))
            else:
                print("   ok   width %d k=%d: both roots give %d, opening %s"
                      % (w, k, cost, g.guess_words[gi]))

# ------------------------------------------------- 1c. progress is a fraction
print("1c. progress reports a real completion fraction")
gp = game(6, 1)
seen_calls = []
gp.solve(progress=lambda d, t, e, n: seen_calls.append((d, t)))
if not seen_calls:
    bad("solve() reported no progress at all")
else:
    dones = [d for d, _ in seen_calls]
    total = seen_calls[0][1]
    if total != gp.NA:
        bad("progress reports %d as the total, the answer list holds %d" % (total, gp.NA))
    elif dones != sorted(dones):
        bad("progress went backwards: %s" % dones[:8])
    elif dones[-1] != gp.NA:
        bad("progress ended at %d of %d -- it never reached the whole list"
            % (dones[-1], gp.NA))
    else:
        print("   ok   %d reports, monotone, ending at %d of %d"
              % (len(seen_calls), dones[-1], gp.NA))

# ----------------------------------------------------------- 2. the ranking
print("2. the top-ranked guess is the argmin of the sum of squared bins")
g6 = game(6, 1)
S = np.arange(g6.NA, dtype=np.int64)
scores = np.empty(g6.NG, dtype=np.int64)
for gi in range(g6.NG):
    keep = [a for a in S if g6.aclass[a] != g6.gclass[gi]]
    codes = [pattern(g6.guess_words[gi], g6.answer_words[a]) for a in keep]
    counts = np.bincount(codes) if codes else np.zeros(0, dtype=np.int64)
    scores[gi] = int((counts.astype(np.int64) ** 2).sum())
want = int(np.argsort(scores, kind="stable")[0])
out_g = np.empty(1, dtype=np.int64)
out_s = np.empty(1, dtype=np.int64)
NT._rank(g6.G, g6.A, S, g6.gclass, g6.aclass, 6, 1,
         g6._cnt, g6._bins, g6._touched, out_g, out_s)
if int(out_g[0]) != want:
    bad("the kernel ranks %r first, the independent argmin says %r"
        % (g6.guess_words[int(out_g[0])], g6.guess_words[want]))
elif int(out_s[0]) != scores[want]:
    bad("the kernel scores %d, the independent count says %d"
        % (int(out_s[0]), scores[want]))
else:
    print("   ok   %d guesses ranked, top is %r with score %d, ties on lowest index"
          % (g6.NG, g6.guess_words[want], scores[want]))

# --------------------------------------------------- 3. a guess wins its class
print("3. one guess finishes a whole commutative class")
classes = {}
for a in g6.answer_words:
    classes.setdefault(commutative_key(a), []).append(a)
groups = sorted((m for m in classes.values() if len(m) > 1), key=len, reverse=True)
if not groups:
    bad("width 6 has no class with more than one member -- check 3 cannot run")
else:
    for members in groups[:3]:
        solo = game(6, 1, answers=members)
        got = solo.total_guesses()
        if got != len(members):
            bad("a class of %d should cost %d (one guess wins all), got %d -- "
                "that is the exact-match rule, not the class rule"
                % (len(members), len(members), got))
        else:
            print("   ok   %s -> %d guesses" % (" ".join(members), got))

# ------------------------------------------------- 4. no all-green bin survives
print("4. no surviving bin carries the all-green code")
ALL_GREEN = 3 ** 6 - 1
leaks = 0
for gi in range(0, g6.NG, 97):                   # a stride, not a sample of one
    gc = g6.gclass[gi]
    for a in range(g6.NA):
        if g6.aclass[a] == gc:
            continue
        if pattern(g6.guess_words[gi], g6.answer_words[a]) == ALL_GREEN:
            leaks += 1
if leaks:
    bad("%d answers survive a guess while showing all-green" % leaks)
else:
    print("   ok   no all-green survivor over %d guesses" % len(range(0, g6.NG, 97)))

# --------------------------------------------------------- 5. the pair screen
print("5. the pair screen against numpy, and against a hand count")
if not NT._HAVE_NUMBA:
    print("   SKIP  numba is not installed")
else:
    for w in (5, 6):
        fast = game(w, 1)
        slow = game(w, 1, use_numba=False)
        gs_f, sc_f, _ = fast.pair_scores(10)
        gs_s, sc_s, _ = slow.pair_scores(10)
        if list(gs_f) != list(gs_s) or sc_f != sc_s:
            bad("width %d: the pair screen differs between kernel and reference" % w)
            continue
        # An independent count of ONE pair, from the strings: the joint bin of an
        # answer is the two feedbacks, and an answer either guess wins joins none.
        score, i, j = sc_f[0]
        g1, g2 = fast.guess_words[gs_f[i]], fast.guess_words[gs_f[j]]
        c1, c2 = fast.gclass[gs_f[i]], fast.gclass[gs_f[j]]
        joint = {}
        for a, word in enumerate(fast.answer_words):
            if fast.aclass[a] == c1 or fast.aclass[a] == c2:
                continue
            key = (pattern(g1, word), pattern(g2, word))
            joint[key] = joint.get(key, 0) + 1
        want = sum(v * v for v in joint.values())
        if want != score:
            bad("width %d: %s + %s scores %d, a hand count of the strings says %d"
                % (w, g1, g2, score, want))
        else:
            print("   ok   width %d: %d pairs agree, best %s + %s at %d, hand-counted"
                  % (w, len(sc_f), g1, g2, score))
        # Progress must not change the answer, and must reach every pair.
        calls = []
        gp2 = game(w, 1)
        _, sc_p, _ = gp2.pair_scores(10, progress=lambda d, t, e, n: calls.append((d, t)))
        if sc_p != sc_f:
            bad("width %d: reporting progress changed the pair scores" % w)
        elif not calls or calls[-1][0] != len(sc_f) or calls[-1][1] != len(sc_f):
            bad("width %d: pair progress ended at %s, expected %d pairs"
                % (w, calls[-1] if calls else None, len(sc_f)))
        elif [d for d, _ in calls] != sorted(d for d, _ in calls):
            bad("width %d: pair progress went backwards" % w)

        # The incumbent log must be strictly decreasing and must END on the
        # winner.  Reporting a row's own falling minimum without comparing it to
        # the global best passes a naive eye and fails both of these.
        best_log = []
        gb = game(w, 1)
        _, sc_b, _ = gb.pair_scores(10, on_best=lambda s, f, t_, d, n, e:
                                 best_log.append(s))
        if sc_b != sc_f:
            bad("width %d: the incumbent log changed the pair scores" % w)
        elif not best_log:
            bad("width %d: no best was ever reported" % w)
        elif any(best_log[i] <= best_log[i + 1] for i in range(len(best_log) - 1)):
            bad("width %d: the incumbent log is not strictly decreasing: %s"
                % (w, best_log))
        elif best_log[-1] != sc_f[0][0]:
            bad("width %d: the last reported best is %d, the winner is %d"
                % (w, best_log[-1], sc_f[0][0]))

        # The bounded return must equal the head of the full sort, and the
        # checkpoint stream must be a valid partial result at every point --
        # this is the path a 25-hour run depends on, so it cannot go untested.
        _, top3, n_scored = gp2.pair_scores(10, keep=3)
        if top3 != sc_f[:3]:
            bad("width %d: keep=3 gives %s, the full sort's head is %s"
                % (w, top3, sc_f[:3]))
        if n_scored != len(sc_f):
            bad("width %d: reported %d pairs scored, the full sort has %d"
                % (w, n_scored, len(sc_f)))
        ck = []
        gp3 = game(w, 1)
        _, fin, _ = gp3.pair_scores(10, keep=3, checkpoint_every=0.0,
                                    on_checkpoint=lambda b, d, t, e: ck.append(list(b)))
        if not ck:
            bad("width %d: no checkpoint was ever taken" % w)
        else:
            for c in ck:
                if c != sorted(c) or len(c) > 3:
                    bad("width %d: a checkpoint was unsorted or oversized" % w)
                    break
            else:
                # Each checkpoint is the best so far, so its head can only fall.
                heads = [c[0][0] for c in ck if c]
                if heads != sorted(heads, reverse=True) and len(set(heads)) > 1:
                    if any(heads[i] < heads[i + 1] for i in range(len(heads) - 1)):
                        bad("width %d: a checkpoint's best got WORSE: %s" % (w, heads))
                if ck[-1] != fin:
                    bad("width %d: the last checkpoint is not the final result" % w)

        # A pair must never split WORSE than its better half alone: adding a
        # second blind guess can only refine the partition.
        og = np.empty(10, dtype=np.int64)
        os_ = np.empty(10, dtype=np.int64)
        S = np.arange(fast.NA, dtype=np.int64)
        NT._rank(fast.G, fast.A, S, fast.gclass, fast.aclass, w, 10,
                 fast._cnt, fast._bins, fast._touched, og, os_)
        if score > int(os_[0]):
            bad("width %d: the best pair scores %d, worse than the best single at %d"
                % (w, score, int(os_[0])))

# ------------------------------------------------ 4b. fixed blind openings
print("4b. a fixed opening reproduces the free run, and is accounted correctly")
for w in (5, 6):
    gf = game(w, 1)
    total, gi = gf.solve()
    # The strong tie: FIXING the opening to the one the beam picked must give
    # the beam's own number.  It exercises the whole new code path against the
    # old one, and any slip in the blind accounting shows up as a difference.
    fixed, _ = gf.solve_from([gf.guess_words[gi]])
    if fixed != total:
        bad("width %d: fixing the opening to %r gives %d, the free run gives %d"
            % (w, gf.guess_words[gi], fixed, total))
    else:
        print("   ok   width %d: fixing %s reproduces %d exactly"
              % (w, gf.guess_words[gi], total))

    # An opening that wins everything must cost exactly one guess per answer.
    _, asub = lists(w)
    members = [a for a in asub if commutative_key(a) == commutative_key(asub[0])]
    solo = game(w, 1, answers=members)
    got, _ = solo.solve_from([members[0]])
    if got != len(members):
        bad("width %d: an opening that wins its whole class costs %d, not %d"
            % (w, got, len(members)))

    # A second blind word can only ADD guesses to a class already won by the
    # first: nobody is alive to pay for it, so the total must not move.
    two, _ = solo.solve_from([members[0], gf.guess_words[gi]])
    if two != len(members):
        bad("width %d: a second word was charged to answers already finished "
            "(%d, not %d)" % (w, two, len(members)))
print("   ok   an opening that wins outright costs one guess each, and a "
      "further blind word is not charged")

try:
    game(6, 1).solve_from(["not a guess"])
    bad("solve_from accepted a word that is not a legal guess")
except ValueError:
    print("   ok   an illegal opener is refused")

# --------------------------------------- 5a. the ranking chunks identically
print("5a. block-scoring the ranking changes nothing")
ga = game(6, 1)
gb = game(6, 1)
sa, oa = ga.root_ranking(block=7)          # many tiny blocks
sb, ob = gb.root_ranking(block=10 ** 9)    # one call, as it used to be
if not (np.array_equal(sa, sb) and np.array_equal(oa, ob)):
    bad("scoring in blocks gives a different ranking from one call")
else:
    calls = []
    gc = game(6, 1)
    gc.root_ranking(block=7, progress=lambda d, t, e, n: calls.append((d, t)))
    if not calls:
        bad("block scoring reported no progress")
    elif [d for d, _ in calls] != sorted(d for d, _ in calls):
        bad("ranking progress went backwards")
    elif calls[-1][0] != gc.NG:
        bad("ranking progress ended at %d of %d" % (calls[-1][0], gc.NG))
    else:
        print("   ok   %d guesses, identical in blocks of 7 and in one call, "
              "%d progress reports" % (ga.NG, len(calls)))

# ------------------------------------------------- 5b. the stored ranking
print("5b. the stored ranking round-trips, and a foreign one is refused")
import tempfile  # noqa: E402

g6r = game(6, 1)
scores, order = g6r.root_ranking()
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "root_rank.csv.gz")
    NT.save_ranking(path, g6r)
    back = NT.load_ranking(path, g6r)
    if back is None:
        bad("a ranking just written could not be read back")
    elif not (np.array_equal(back[0], scores) and np.array_equal(back[1], order)):
        bad("the ranking changed across a save and load")
    else:
        print("   ok   %d guesses round-tripped exactly" % g6r.NG)

    # The property that matters: a ranking built for a DIFFERENT answer list must
    # be refused, not reused.  Every score would be wrong -- confidently, and with
    # the file looking perfectly valid.
    gsub, asub = lists(6)
    other = game(6, 1, answers=asub[:-1])
    if other.fingerprint() == g6r.fingerprint():
        bad("dropping an answer left the fingerprint unchanged")
    elif NT.load_ranking(path, other) is not None:
        bad("a ranking built for a different answer list was accepted")
    else:
        print("   ok   a ranking for %d answers is refused for %d"
              % (g6r.NA, other.NA))

    # And an injected ranking must actually be USED, not quietly recomputed.
    fresh = game(6, 1)
    fresh.set_root_ranking(scores, order)
    if not np.array_equal(fresh.root_ranking()[1], order):
        bad("set_root_ranking did not take effect")
    else:
        print("   ok   an installed ranking is the one the search uses")

# ------------------------------------------------------------------ coverage
print("6. the class rule actually fired")
multi = sum(1 for m in classes.values() if len(m) > 1)
if not multi:
    bad("no class of more than one member was ever exercised -- the pass is hollow")
else:
    print("   ok   %d classes of more than one member, largest %d"
          % (multi, max(len(m) for m in classes.values())))

print()
if fails:
    print("NERDLE TOPK CHECK FAILURES (%d) -- see above" % len(fails))
    sys.exit(1)
print("all nerdle topk checks pass")
