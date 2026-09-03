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

# ------------------------------------------------------------------ coverage
print("5. the class rule actually fired")
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
