"""THE GATE for the Nerdle rules and the guess enumerator.

    python3 tools/checknerdle.py            # from math/, seconds
    python3 tools/checknerdle.py --wide     # adds width 6 exhaustive + width 7

Run it after any change to math/nerdle.py or tools/nerdle_enumerate.py,
alongside solver/validate.sh and tools/checkpatterns.py.  Exits nonzero, so it
works as a gate.

WHAT MAKES IT AN ORACLE and not a restatement.  The reference here shares NO
code with math/nerdle.py: it screens a side with a regular expression, then
rewrites every digit run as `Fraction(n)` and hands the string to PYTHON'S OWN
PARSER via eval.  Precedence, left-to-right association, repeated unary minus
and exact rational arithmetic therefore come from CPython and the fractions
module rather than from the code under test, and division by zero surfaces as a
ZeroDivisionError.  Rewriting the digit runs is also what sidesteps Python
refusing `0012` as a literal, so leading zeros (rule 5) survive the trip.

FOUR CHECKS:
  1. NAMED CASES -- every accept/reject settled with the user on 2026-09-03,
     each at its own width, against both nerdle.is_valid_guess and the
     reference.  These are the cases the rules were actually derived from.
  2. THE EVALUATOR -- nerdle.evaluate against the reference on EVERY string of
     length up to 4 over the 14 non-`=` symbols, invalid ones included, so the
     two must agree on what is malformed as well as on what a side is worth.
  3. EXHAUSTIVE ENUMERATION -- at widths 3 to 5 (6 with --wide) all 15**w
     strings are classified by the reference, and that set must equal the
     output of BOTH walkers, exactly.
  4. THE TWO WALKERS AGREE -- at widths 3 to 6 (7 with --wide), where brute
     force is out of reach but both walks still finish, their output sets must
     be identical and duplicate-free.

Then a COVERAGE tally: the awkward features of the rules -- a unary minus, a
double negative, a leading zero, a division, an expression on the right, an
operator-free side, a negative value, a NON-INTEGER value -- must each have
fired somewhere in what was checked, and the run FAILS if any did not.  Without
it a pass could quietly mean the interesting half of the rules was never
exercised: nothing at width 6 or below has a fractional value, for instance, so
that one rides on the named witnesses (and on width 7 under --wide).
"""

import itertools
import os
import re
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import nerdle as N  # noqa: E402

# A side: any number of unary minuses, a digit run, then binary-operator-then-
# number as often as you like.  Deliberately a flat regex rather than a parser.
SIDE_RE = re.compile(r"^-*\d+(?:[-+*/]-*\d+)*$")

fails = []


def bad(msg):
    fails.append(msg)
    print("  FAIL: %s" % msg)


def ref_side(side):
    """Exact value of a side, via Python's own parser. None = not a legal side."""
    if not SIDE_RE.match(side):
        return None
    expr = re.sub(r"\d+", lambda m: "Fraction(%d)" % int(m.group()), side)
    try:
        return eval(expr, {"__builtins__": {}}, {"Fraction": Fraction})
    except ZeroDivisionError:
        return None


def ref_valid(s, width):
    if len(s) != width or any(c not in N.SYMBOLS for c in s):
        return False
    if s.count("=") != 1:
        return False
    lhs, rhs = s.split("=")
    if not lhs or not rhs:
        return False
    a, b = ref_side(lhs), ref_side(rhs)
    return a is not None and b is not None and a == b


# --------------------------------------------------------------------- coverage
FEATURES = ("unary minus", "double negative", "leading zero", "division",
            "expression on the right", "no operator", "negative value",
            "non-integer value")
seen = {f: 0 for f in FEATURES}


def note_features(s):
    lhs, rhs = s.split("=")
    for i, c in enumerate(s):
        if c == "-" and (i == 0 or s[i - 1] in N.BINOPS + "="):
            seen["unary minus"] += 1
            break
    if "--" in s:
        seen["double negative"] += 1
    for run in re.findall(r"\d+", s):
        if len(run) > 1 and run[0] == "0":
            seen["leading zero"] += 1
            break
    if "/" in s:
        seen["division"] += 1
    if any(c in N.BINOPS for c in rhs):
        seen["expression on the right"] += 1
    if not any(c in N.BINOPS for c in s):
        seen["no operator"] += 1
    v = ref_side(lhs)
    if v is not None:
        if v < 0:
            seen["negative value"] += 1
        if v.denominator != 1:
            seen["non-integer value"] += 1


# ------------------------------------------------------------------ 1. named
ACCEPT = ["12+34=46", "1+9=0+10", "0012=012", "5=000005", "1--2=3",
          "10-20=-10", "1/2=2/4", "1/2*4=0+2", "-1+3=0+2", "1---2=-1",
          "0-0=-0", "7/2=7/2"]
REJECT = ["1+1=2=2", "1+=2+34", "12+34=4", "1/0=1/0", "1++2=3", "12345678",
          "1+2*3=6+2", "=1+1", "1+1=", "1+2+3", "1+2=*3", "1-+2=-1"]

print("1. the named cases settled with the user")
for s in ACCEPT:
    w = len(s)
    if not N.is_valid_guess(s, w):
        bad("%r should be a valid guess, is_valid_guess says no" % s)
    if not ref_valid(s, w):
        bad("%r should be a valid guess, the reference says no" % s)
    else:
        note_features(s)
for s in REJECT:
    w = len(s)
    if N.is_valid_guess(s, w):
        bad("%r should be rejected, is_valid_guess accepts it" % s)
    if ref_valid(s, w):
        bad("%r should be rejected, the reference accepts it" % s)
print("   ok   %d accepts, %d rejects" % (len(ACCEPT), len(REJECT)))

# -------------------------------------------------------------- 2. evaluator
print("2. nerdle.evaluate against Python's own parser, every side to length 4")
sides = N.DIGITS + N.BINOPS
n = mismatch = 0
for L in range(1, 5):
    for p in itertools.product(sides, repeat=L):
        s = "".join(p)
        mine, theirs = N.evaluate(s), ref_side(s)
        n += 1
        if (mine is None) != (theirs is None) or (mine is not None and mine != theirs):
            mismatch += 1
            if mismatch <= 5:
                bad("evaluate(%r) = %r, reference = %r" % (s, mine, theirs))
if not mismatch:
    print("   ok   %d strings, exact agreement (values and malformedness)" % n)

# ------------------------------------------------------------- 3. exhaustive
wide = "--wide" in sys.argv[1:]
print("3. exhaustive brute force against both walkers")
for w in range(3, 7 if wide else 6):
    ref = {"".join(p) for p in itertools.product(N.SYMBOLS, repeat=w)
           if ref_valid("".join(p), w)}
    for method in ("dfs", "split"):
        got = N.enumerate_guesses(w, method)
        if len(got) != len(set(got)):
            bad("width %d %s emitted duplicates" % (w, method))
        if set(got) != ref:
            miss = sorted(ref - set(got))[:3]
            extra = sorted(set(got) - ref)[:3]
            bad("width %d %s differs from the reference (missing %s, extra %s)"
                % (w, method, miss, extra))
    for s in ref:
        note_features(s)
    print("   ok   width %d: %d guesses out of %d strings, both walkers exact"
          % (w, len(ref), 15 ** w))

# ----------------------------------------------------------- 4. walkers agree
print("4. the two walkers agree where brute force cannot reach")
for w in range(3, 8 if wide else 7):
    a = N.enumerate_guesses(w, "dfs")
    b = N.enumerate_guesses(w, "split")
    if len(a) != len(set(a)) or len(b) != len(set(b)):
        bad("width %d: a walker emitted duplicates" % w)
    if set(a) != set(b):
        bad("width %d: dfs and split disagree (%d vs %d)" % (w, len(a), len(b)))
    else:
        print("   ok   width %d: %d guesses, both walkers identical" % (w, len(a)))
    for s in a:
        note_features(s)

# -------------------------------------------------------------- 5. coverage
print("5. every awkward feature of the rules actually fired")
for f in FEATURES:
    if seen[f]:
        print("   ok   %-24s %d" % (f, seen[f]))
    else:
        bad("%s never occurred in anything checked -- the pass is hollow" % f)

print()
if fails:
    print("NERDLE CHECK FAILURES (%d) -- see above" % len(fails))
    sys.exit(1)
print("all nerdle checks pass")
