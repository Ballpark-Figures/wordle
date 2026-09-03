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


# The ANSWER rules (A1-A4) as a single regular expression: a number, then at
# least one operator-and-number, then `=`, then a number, with `(?!0)` in front
# of every number so no digit run can begin with a zero.  No `-` can be unary
# because a number never starts with one.  The right side is `0|(?!0)\d+`, which
# is A2's exception: the ANSWER alone may be a bare zero.  Deliberately one flat
# pattern rather than the four separate tests the implementation uses.
ANS_RE = re.compile(r"^(?!0)\d+(?:[-+*/](?!0)\d+)+=(?:0|(?!0)\d+)$")


def ref_answer(s, width):
    if len(s) != width or not ANS_RE.match(s):
        return False
    lhs, rhs = s.split("=")
    a, b = ref_side(lhs), ref_side(rhs)
    return a is not None and b is not None and a == b


def ref_class(s):
    """Every answer commutatively equal to s, by ENUMERATION rather than
    canonicalisation.

    nerdle.commutative_key sorts the operands in the commuting slots into one
    canonical order; this instead generates every permutation of them and
    returns the whole class as a set.  The two share no code and answer
    different questions, so they can be diffed three ways: the class of a is the
    class of b exactly when the keys match, the key must itself lie in the class,
    and the class must be closed (every member generates the same class).
    """
    lhs, rhs = s.split("=")
    terms = re.split(r"(?=[-+])|(?<=[-+])", lhs)      # keep the operators
    toks = [t for t in re.split(r"([-+])", lhs) if t]
    term_ops = [""] + [t for t in toks if t in "+-"]
    term_vals = [t for t in toks if t not in "+-"]

    def factor_forms(term):
        ftoks = [t for t in re.split(r"([*/])", term) if t]
        fops = [""] + [t for t in ftoks if t in "*/"]
        fvals = [t for t in ftoks if t not in "*/"]
        slots = [i for i in range(len(fvals)) if fops[i] in ("", "*")]
        out = set()
        for perm in itertools.permutations(sorted(fvals[i] for i in slots)):
            vals = list(fvals)
            for i, v in zip(slots, perm):
                vals[i] = v
            out.add("".join(fops[i] + vals[i] for i in range(len(vals))))
        return out

    per_term = [sorted(factor_forms(t)) for t in term_vals]
    slots = [i for i in range(len(term_vals)) if term_ops[i] in ("", "+")]
    out = set()
    for perm in itertools.permutations(slots):
        for combo in itertools.product(*per_term):
            vals = list(combo)
            for src_i, dst_i in zip(slots, perm):
                vals[dst_i] = combo[src_i]
            out.add("".join(term_ops[i] + vals[i] for i in range(len(vals))) + "=" + rhs)
    return out


def ref_intermediates(lhs):
    """Every intermediate value of an ANSWER's left side, via prefix eval.

    The running left-to-right totals are the values of the prefixes ending at
    each `+` or `-`; the term accumulations are the values of each term's
    prefixes ending at each `*` or `/`.  Both are read off with ref_side, so
    Python's parser does the arithmetic and nothing is shared with nerdle.py.
    This is what makes the two settled decisions -- an answer MAY pass through a
    negative value and MAY pass through a fraction -- independently checkable
    rather than merely asserted.
    """
    vals = []
    cuts = [i for i, c in enumerate(lhs) if c in "+-"]
    for pre in [lhs[:i] for i in cuts] + [lhs]:
        vals.append(ref_side(pre))
    for term in re.split(r"[-+]", lhs):
        tcuts = [j for j, c in enumerate(term) if c in "*/"]
        for pre in [term[:j] for j in tcuts] + [term]:
            vals.append(ref_side(pre))
    return [v for v in vals if v is not None]


# --------------------------------------------------------------------- coverage
FEATURES = ("unary minus", "double negative", "leading zero", "division",
            "expression on the right", "no operator", "negative value",
            "non-integer value", "answer", "answer through a negative",
            "answer through a fraction", "class of more than one",
            "class with a term that moved")
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
    if ref_answer(s, len(s)):
        seen["answer"] += 1
        mids = ref_intermediates(lhs)
        if any(m < 0 for m in mids):
            seen["answer through a negative"] += 1
        if any(m.denominator != 1 for m in mids):
            seen["answer through a fraction"] += 1


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

# The answer rules are a strict subset, so every accept below must ALSO be a
# valid guess -- checked, because a bug that widened the guess rules could
# otherwise hide behind a passing answer filter.  `1-2+3=2` and `1/2*4=2` are
# here specifically to pin the two decisions settled on 2026-09-03: an answer
# may pass through a negative value and through a fraction.
ANS_ACCEPT = ["12+34=46", "1+1=2", "10-3=7", "9+8-7=10", "1+2*3=7",
              "8/2*3=12", "9*8/6=12", "1-2+3=2", "1/2*4=2", "12-3*4=0"]
ANS_REJECT = ["0012=012", "1+9=0+10", "10-20=-10", "1+2=03", "5=000005",
              "1--2=3", "1+2+3=06", "1+0=1", "1+2=3+0", "12+34=45", "1*0+7=7"]

print("1b. the named ANSWER cases")
for s in ANS_ACCEPT:
    w = len(s)
    if not N.is_answer(s, w):
        bad("%r should be a valid answer, is_answer says no" % s)
    if not ref_answer(s, w):
        bad("%r should be a valid answer, the reference says no" % s)
    if not N.is_valid_guess(s, w):
        bad("%r is accepted as an answer but is not even a valid guess" % s)
    note_features(s)
for s in ANS_REJECT:
    w = len(s)
    if N.is_answer(s, w):
        bad("%r should be rejected as an answer, is_answer accepts it" % s)
    if ref_answer(s, w):
        bad("%r should be rejected as an answer, the reference accepts it" % s)
print("   ok   %d accepts, %d rejects" % (len(ANS_ACCEPT), len(ANS_REJECT)))

# The switches on answer_rules() exist to compare our rule set with the live
# game's, so a switch that silently does nothing would not fail any count -- it
# would just quietly make a variant look identical to the settled rules and send
# the comparison the wrong way.  Each case below is chosen so that exactly the
# listed switches turn it from rejected to accepted, and nothing else does.
SWITCH_CASES = [
    ("1+0=1",    ["zero_operand", "leading_zeros"]),
    ("1+2=03",   ["leading_zeros"]),
    ("1-4=-3",   ["negative_answer", "expression_rhs"]),
]
ALL_SWITCHES = ["zero_operand", "zero_answer", "leading_zeros", "expression_rhs",
                "negative_answer", "no_operator", "exact_division",
                "nonneg_running"]

print("1c. every rule switch flips exactly the cases it should")
for s, expect in SWITCH_CASES:
    w = len(s)
    if N.answer_rules(s, w):
        bad("%r should be rejected by the settled rules" % s)
    got = [k for k in ALL_SWITCHES if N.answer_rules(s, w, **{k: True})]
    if got != [k for k in ALL_SWITCHES if k in expect]:
        bad("%r is admitted by switches %s, expected %s" % (s, got, expect))
# The two tightenings must REMOVE the witnesses of the decisions they undo.
for s, k in (("1/2*4=2", "exact_division"), ("1-2+3=2", "nonneg_running")):
    if not N.answer_rules(s, len(s)):
        bad("%r should be a settled answer" % s)
    if N.answer_rules(s, len(s), **{k: True}):
        bad("%r should be removed by %s" % (s, k))
# A2's exception is a switch too, in the other direction: it is ON by default,
# and withdrawing it must remove exactly the zero-answer case.
if not N.answer_rules("12-3*4=0", 8):
    bad("'12-3*4=0' should be a settled answer -- A2 admits a zero ANSWER")
if N.answer_rules("12-3*4=0", 8, zero_answer=False):
    bad("'12-3*4=0' should be removed by zero_answer=False")
# No switch may change an answer that the settled rules already accept.
for s in ANS_ACCEPT:
    for k in ("zero_operand", "zero_answer", "leading_zeros", "expression_rhs",
              "negative_answer", "no_operator"):
        if not N.answer_rules(s, len(s), **{k: True}):
            bad("loosening %s dropped the settled answer %r" % (k, s))
print("   ok   %d switch cases, %d loosenings keep every settled answer"
      % (len(SWITCH_CASES) + 3, len(ANS_ACCEPT) * 6))

# -------------------------------------------------------------- 2. evaluator
# Pass two.  SAME[i] is a set of answers that must all share one class; DIFF is
# pairs that must not.  The `-` and `/` groups are the load-bearing ones: the
# FAQ's test is about tokens, so they move even though neither operator
# commutes, and a canonicaliser built on algebra would split them.
SAME = [
    ["12+34=46", "34+12=46"],
    ["1*2+8=10", "8+1*2=10"],
    ["1+2*3=7", "3*2+1=7", "1+3*2=7", "2*3+1=7"],
    ["9-8+7=8", "7-8+9=8"],      # the two `+`-signed terms swap, `-8` holds
]
DIFF = [
    ("1*2+8=10", "1*8+2=10"),    # the case that sank the FAQ's literal test
    ("2+1*3=5", "3+2*1=5"),      # likewise: the products are 1*3 and 2*1
    ("9-8+7=8", "9+7-8=8"),      # `-8` would have to move
    ("12/3/2=2", "12/2/3=2"),    # divisors are pinned
    ("1+2*3=7", "1*2+3=5"),      # same tokens, different answer
    ("1+2*3=7", "1+6*1=7"),      # same operators and answer, different numbers
]

print("1d. the commutative classes")
for group in SAME:
    for s in group:
        if not N.is_answer(s, len(s)):
            bad("%r is used as a class witness but is not an answer" % s)
        if N.commutative_key(s) not in ref_class(s):
            bad("the key of %r is not itself in its enumerated class" % s)
    keys = {N.commutative_key(s) for s in group}
    cls = ref_class(group[0])
    if len(keys) != 1:
        bad("%s should be one class, got %d" % (group, len(keys)))
    elif not set(group) <= cls:
        bad("%s is one class by key, but %s is missing from the enumeration"
            % (group, sorted(set(group) - cls)))
    else:
        seen["class of more than one"] += 1
        if any(c in "-+" for c in group[0].split("=")[0]):
            seen["class with a term that moved"] += 1
for a, b in DIFF:
    if N.commutative_key(a) == N.commutative_key(b):
        bad("%r and %r should be different classes" % (a, b))
    if b in ref_class(a):
        bad("%r turns up in %r's enumerated class" % (b, a))
print("   ok   %d classes hold together, %d pairs stay apart" % (len(SAME), len(DIFF)))

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
    ref_ans = {s for s in ref if ref_answer(s, w)}
    mine_ans = {s for s in ref if N.is_answer(s, w)}
    if mine_ans != ref_ans:
        bad("width %d: is_answer differs from the reference (missing %s, extra %s)"
            % (w, sorted(ref_ans - mine_ans)[:3], sorted(mine_ans - ref_ans)[:3]))
    groups = {}
    for s in sorted(ref_ans):
        cls = ref_class(s)
        if N.commutative_key(s) not in cls:
            bad("width %d: the key of %r is not itself in its class" % (w, s))
        for t in cls & ref_ans:
            if N.commutative_key(t) != N.commutative_key(s):
                bad("width %d: %r and %r are one class but key differently" % (w, s, t))
            if ref_class(t) != cls:
                bad("width %d: the class of %r is not closed (%r differs)" % (w, s, t))
        groups.setdefault(N.commutative_key(s), []).append(s)
    if sum(len(g) for g in groups.values()) != len(ref_ans):
        bad("width %d: the classes do not partition the answers" % w)
    for s in ref:
        note_features(s)
    print("   ok   width %d: %d guesses out of %d strings, both walkers exact; "
          "%d answers in %d classes, keys exact"
          % (w, len(ref), 15 ** w, len(ref_ans), len(groups)))

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
