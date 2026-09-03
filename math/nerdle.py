"""NERDLE -- the rules of a valid guess, the exact evaluator, and the enumerator.

THIS FILE IS THE SOURCE OF TRUTH for what counts as a valid 8-symbol Nerdle
GUESS.  Read it before quoting any count.

THE SYMBOL SET is the 15 characters `0123456789+-*/=`, and a guess fills exactly
WIDTH (8) of them.  A `width` parameter exists throughout ONLY so that
tools/checknerdle.py can brute-force small widths exhaustively against an
independent reference; the game is 8.

A GUESS IS VALID iff all of the following hold.  These rules were settled with
the user on 2026-09-03, several of them by trying candidates against the live
game, and they are DELIBERATELY LOOSER than the rules for an ANSWER:

  1. EXACTLY ONE `=`, with at least one symbol on each side of it.
  2. Each side is an arithmetic expression over the binary operators `+ - * /`,
     evaluated with STANDARD PRECEDENCE (`*` and `/` before `+` and `-`, each
     left to right).
  3. A UNARY `-` may precede any number ANYWHERE -- opening a side, right after
     the `=`, or after a binary operator -- and it may be REPEATED, so a double
     negative like `1--2=3` is a legal guess.  `+` is never unary, no other
     operator may follow an operator or open a side, and no side may end with an
     operator.
  4. THE RIGHT SIDE IS A FULL EXPRESSION, not merely a number, so `1+9=0+10` is
     a legal guess.  (An ANSWER's right side is a bare number.  That is one of
     the ways the two sets differ, and it is why the enumeration cannot stop at
     the `=` and count the digits remaining -- it has to keep going and compare
     two expression values.)
  5. LEADING ZEROS ARE ALLOWED and neither side needs an operator at all, so
     `0012=012` and `5=000005` are legal guesses.  The live game accepts
     `0012=012`, which is how this rule was established.
  6. Both sides are compared as EXACT RATIONALS and must be EQUAL.  A division
     need not come out whole, and the shared value need not be a whole number
     (`1/2=2/4` is a legal guess) nor non-negative (`10-20=-10`).  The one
     arithmetic prohibition is DIVISION BY ZERO, which leaves a side undefined
     rather than merely unequal.

THE ANSWER RULES -- a strict SUBSET of the guesses, settled with the user on
2026-09-03 and implemented by is_answer() below.  An answer is a valid guess
that also satisfies:

  A1. THE RIGHT SIDE IS A BARE NUMBER -- digits only, no operator and no minus.
      This is the rule the live game states ("on the right of `=` is only a
      number") and it is what makes an answer's right side terminal where a
      guess's is not.
  A2. NO DIGIT RUN BEGINS WITH `0`, which bans a leading zero (`1+2=03`) and,
      as the user put it, bans the number `0` outright -- so every operand and
      the answer itself are at least 1.  `10` is unaffected: its zero is not
      leading.
  A3. NO UNARY MINUS ANYWHERE, so no negative number is ever written.  Every
      `-` in an answer is a binary subtraction.
  A4. THE LEFT SIDE CONTAINS AT LEAST ONE OPERATOR, so `0012=012` is a guess
      but never an answer.

NOTHING CONSTRAINS THE INTERMEDIATE VALUES, and that was a decision rather than
an oversight: the user settled on 2026-09-03 that an answer's left side MAY pass
through a NEGATIVE value (`1-2+3=2`, whose running total dips to -1) and MAY
pass through a FRACTION (`1/2*4=2`, whose first division is a half).  Only the
number to the right of the `=` is constrained, and A1-A3 already force it to be
a whole number of at least 1.  Both stricter readings were live until then and
both shrink the answer set, so a count computed under either is a DIFFERENT
quantity -- do not quote one as the answer count.

Where a value could go wrong is worth stating, because it is why those two
questions had unambiguous answers: A2 and A3 make every operand at least 1, so
the only way an answer's left side reaches a negative value is a subtraction in
its running left-to-right total, and the only way it reaches a fraction is a
division inside a term.  There is nowhere else to look.

EXACT RATIONALS, NOT FLOATS.  Every value is an `(numerator, denominator)` pair
of ints, normalised so the denominator is positive and the fraction is in lowest
terms.  Normalisation is load-bearing beyond tidiness: walk_guesses_split uses
the pair as a DICTIONARY KEY, so two equal values left unreduced would fail to
join and silently drop guesses.

KNOWN EDGE CASE, recorded rather than decided: rule 3 admits `-0` as a number,
so `0-0=-0` is counted.  It has not been checked against the live game.
"""

from fractions import Fraction
from math import gcd

WIDTH = 8
DIGITS = "0123456789"
BINOPS = "+-*/"
SYMBOLS = DIGITS + BINOPS + "="

_DIGIT = tuple(DIGITS)

# Parser/enumerator states: _S expects a number (the start of a side, just after
# a binary operator, or in a run of unary minuses); _D has just read a digit.
_S, _D = 0, 1

# The multiplicative operator waiting for the next number, if any.
_NONE, _MUL, _DIV = 0, 1, 2

_ZERO = (0, 1)


# --------------------------------------------------------------------------
# Exact rational arithmetic on (numerator, denominator) pairs.
#
# Fraction is the readable form and is what evaluate() below uses, but it is far
# too slow for a walk with hundreds of millions of nodes.  These four helpers
# are the hot path: integer fast paths first, gcd only when a denominator is
# actually in play.  Every result is normalised -- see the module docstring for
# why that is a correctness requirement and not tidiness.
# --------------------------------------------------------------------------

def _norm(n, d):
    if d < 0:
        n, d = -n, -d
    g = gcd(n if n >= 0 else -n, d)
    if g > 1:
        return n // g, d // g
    return n, d


def _add(a, b):
    an, ad = a
    bn, bd = b
    if ad == 1 and bd == 1:
        return an + bn, 1
    return _norm(an * bd + bn * ad, ad * bd)


def _sub(a, b):
    bn, bd = b
    return _add(a, (-bn, bd))


def _mul(a, b):
    an, ad = a
    bn, bd = b
    if ad == 1 and bd == 1:
        return an * bn, 1
    return _norm(an * bn, ad * bd)


def _div(a, b):
    """a / b, or None when b is zero -- an undefined side, not an unequal one."""
    an, ad = a
    bn, bd = b
    if bn == 0:
        return None
    return _norm(an * bd, ad * bn)


# --------------------------------------------------------------------------
# The incremental side evaluator shared by both enumerators.
#
# `total` is the sum of the terms already closed, `term` the multiplicative term
# in progress, `sign` the +1/-1 that the preceding binary operator attaches to
# it, `pending` the `*` or `/` awaiting the number now being read, and
# (`cur`, `neg`) that number's digits and the parity of the unary minuses in
# front of it.  Unary minus is applied to the number itself, which is equivalent
# to applying it to the whole term because a sign commutes through `*` and `/`.
# --------------------------------------------------------------------------

def _close(term, pending, cur, neg):
    """Fold the number just finished into the current term. None = undefined."""
    num = -cur if neg else cur
    if pending == _NONE:
        return (num, 1)              # term is always None here, by construction
    if pending == _MUL:
        return _mul(term, (num, 1))
    return _div(term, (num, 1))


def _finish(total, term, sign, pending, cur, neg):
    """The value of a side that has just ended. None = undefined."""
    t = _close(term, pending, cur, neg)
    if t is None:
        return None
    return _add(total, t) if sign > 0 else _sub(total, t)


# --------------------------------------------------------------------------
# The readable definition of validity, used by the checker and for spot checks.
# It re-parses from scratch with Fraction and shares no code with the walkers
# above, so it doubles as a cheap oracle for them.
# --------------------------------------------------------------------------

def evaluate(side):
    """Exact Fraction value of one side, or None if it is not a legal side.

    None covers both malformed structure (an operator at the end, a `+` after
    an operator, an empty side) and division by zero.
    """
    val, i = _sum(side, 0)
    if val is None or i != len(side):
        return None
    return val


def _sum(s, i):
    val, i = _term(s, i)
    if val is None:
        return None, i
    while i < len(s) and s[i] in "+-":
        op = s[i]
        rhs, i = _term(s, i + 1)
        if rhs is None:
            return None, i
        val = val + rhs if op == "+" else val - rhs
    return val, i


def _term(s, i):
    val, i = _factor(s, i)
    if val is None:
        return None, i
    while i < len(s) and s[i] in "*/":
        op = s[i]
        rhs, i = _factor(s, i + 1)
        if rhs is None:
            return None, i
        if op == "*":
            val = val * rhs
        else:
            if rhs == 0:
                return None, i
            val = val / rhs
    return val, i


def _factor(s, i):
    neg = False
    while i < len(s) and s[i] == "-":      # a repeatable unary minus (rule 3)
        neg = not neg
        i += 1
    j = i
    while j < len(s) and s[j] in DIGITS:   # leading zeros are fine (rule 5)
        j += 1
    if j == i:
        return None, i
    val = Fraction(int(s[i:j]))
    return (-val if neg else val), j


def is_valid_guess(s, width=WIDTH):
    """The rules, stated once, straight through. Slow; use for checks, not sweeps."""
    if len(s) != width or any(c not in SYMBOLS for c in s):
        return False
    if s.count("=") != 1:                  # rule 1
        return False
    lhs, rhs = s.split("=")
    if not lhs or not rhs:
        return False
    a = evaluate(lhs)
    b = evaluate(rhs)
    return a is not None and b is not None and a == b   # rule 6


def digit_runs(s):
    """Yield (start index, text) for every maximal run of digits in s."""
    i = 0
    while i < len(s):
        if s[i] in DIGITS:
            j = i
            while j < len(s) and s[j] in DIGITS:
                j += 1
            yield i, s[i:j]
            i = j
        else:
            i += 1


def lhs_intermediates(lhs):
    """Every value an ANSWER-shaped left side passes through, as Fractions.

    The running left-to-right totals are the values of the prefixes ending at
    each `+` or `-`; a term's accumulations are the values of that term's own
    prefixes ending at each `*` or `/`.  Together those are every value a person
    working the expression out would write down.

    Only meaningful for an answer-shaped side, where every `-` is binary.  This
    is not used by the settled rules -- see the module docstring, where leaving
    the intermediates unconstrained is a decision -- but answer_rules() can
    constrain them, for comparing our rule set against the game's.
    """
    vals = []
    for i, c in enumerate(lhs):
        if c in "+-":
            v = evaluate(lhs[:i])
            if v is not None:
                vals.append(v)
    v = evaluate(lhs)
    if v is not None:
        vals.append(v)
    start = 0
    for i, c in enumerate(lhs + "+"):              # the sentinel closes the last term
        if c in "+-" and i > start:
            term = lhs[start:i]
            for j, d in enumerate(term):
                if d in "*/":
                    tv = evaluate(term[:j])
                    if tv is not None:
                        vals.append(tv)
            tv = evaluate(term)
            if tv is not None:
                vals.append(tv)
            start = i + 1
    return vals


def answer_rules(s, width=WIDTH, zero_operand=False, zero_answer=False,
                 leading_zeros=False, expression_rhs=False,
                 negative_answer=False, no_operator=False,
                 exact_division=False, nonneg_running=False, check_guess=True):
    """The answer rules with every disputed clause exposed as a switch.

    CALLED WITH NO SWITCHES THIS IS is_answer -- A1-A4 exactly, which is the
    settled rule set and the only one whose count may be called the answer
    count.  Every switch produces a DIFFERENT quantity and exists for one
    purpose: comparing our rule set against the live game's, which we cannot
    read.  Do not let a switched count leak into anything as "the answers".

    Loosening: `zero_operand` admits a bare `0` as a left-side operand,
    `zero_answer` admits `0` as the answer, `leading_zeros` drops A2 entirely,
    `expression_rhs` drops A1 so the right side may be an expression,
    `negative_answer` allows a single unary minus on the answer, `no_operator`
    drops A4.  Tightening: `exact_division` requires every division to come out
    whole, `nonneg_running` forbids the running total from going below zero.
    """
    # `check_guess=False` skips re-parsing a line already known to be a valid
    # guess.  A variant sweep tests one line against a dozen rule sets and the
    # parse is the expensive part; the caller validates once instead.
    if check_guess and not is_valid_guess(s, width):
        return False
    lhs, rhs = s.split("=")
    eq = len(lhs)

    if not expression_rhs:                          # A1
        body = rhs
        if negative_answer and body.startswith("-"):
            body = body[1:]                         # one sign only, not a double
        if not body or any(c not in DIGITS for c in body):
            return False

    if not no_operator and not any(c in BINOPS for c in lhs):    # A4
        return False

    for i, c in enumerate(lhs):                     # A3, left side always
        if c == "-" and (i == 0 or lhs[i - 1] in BINOPS):
            return False
    if not negative_answer and not expression_rhs and "-" in rhs:
        return False

    if not leading_zeros:                           # A2
        answer_run = rhs.lstrip("-") if not expression_rhs else None
        for start, text in digit_runs(s):
            if text[0] != "0":
                continue
            if len(text) > 1:
                return False                        # a genuine leading zero
            if start > eq and text == answer_run:
                if not zero_answer:
                    return False
            elif not zero_operand:
                return False

    if exact_division or nonneg_running:
        mids = lhs_intermediates(lhs)
        if exact_division and any(m.denominator != 1 for m in mids):
            return False
        if nonneg_running and any(m < 0 for m in mids):
            return False
    return True


def is_answer(s, width=WIDTH):
    """Is this a legal ANSWER -- a guess that also satisfies A1-A4 above?

    A strict subset of is_valid_guess, so it is the natural filter over an
    enumerated guess list.  Nothing here looks at the intermediate values; see
    the module docstring for why that is a settled decision and not a gap.
    """
    return answer_rules(s, width)


# --------------------------------------------------------------------------
# Enumerator 1: the single-pass DFS over the whole string.
#
# This is the walk as specified: descend position by position over the 15
# symbols and cut a branch the moment it cannot become a guess -- an operator
# that may not follow an operator or open a side, a second `=`, a division by
# zero, or too few positions left to fit an `=` and something after it.
#
# It is the SLOW one, and the reason is structural rather than fixable: the
# right side being a full expression (rule 4) means the walk cannot stop at the
# `=`, and the number of structurally valid 8-symbol strings it must reach the
# bottom of is about 188 million.  walk_guesses_split below computes the same
# set from about 7.6 million side evaluations instead; checknerdle.py proves
# they agree.
# --------------------------------------------------------------------------

def walk_guesses(emit, width=WIDTH):
    """Call emit(equation) once for every valid guess.

    The order is depth-first over the symbols in SYMBOLS order -- digits, then
    `+ - * /`, then `=`.  That is NOT Python's string sort, which orders the
    operators below the digits by ASCII, so do not expect sorted output.
    """
    buf = [""] * width

    def rec(pos, state, lhs, total, term, sign, pending, cur, neg):
        if pos == width:
            if lhs is None or state != _D:     # no `=`, or ends on an operator
                return
            v = _finish(total, term, sign, pending, cur, neg)
            if v is not None and v == lhs:     # rule 6
                emit("".join(buf))
            return

        # Nothing written from here can still leave room for an `=` and at
        # least one symbol after it, so the whole branch is dead.
        if lhs is None and pos >= width - 1:
            return

        for d in range(10):
            buf[pos] = _DIGIT[d]
            rec(pos + 1, _D, lhs, total, term, sign, pending, cur * 10 + d, neg)

        if state == _S:
            # A unary minus in front of a number that has not started yet.  It
            # leaves the state alone, which is what makes it repeatable.
            buf[pos] = "-"
            rec(pos + 1, _S, lhs, total, term, sign, pending, 0, not neg)
            return

        # State is _D, so the number just read can be closed: every binary
        # operator is legal here, the `=` is legal if it is the first, and
        # nothing else is.
        t = _close(term, pending, cur, neg)
        if t is None:
            return                             # divided by zero: dead branch
        closed = _add(total, t) if sign > 0 else _sub(total, t)

        buf[pos] = "+"
        rec(pos + 1, _S, lhs, closed, None, 1, _NONE, 0, False)
        buf[pos] = "-"
        rec(pos + 1, _S, lhs, closed, None, -1, _NONE, 0, False)
        buf[pos] = "*"
        rec(pos + 1, _S, lhs, total, t, sign, _MUL, 0, False)
        buf[pos] = "/"
        rec(pos + 1, _S, lhs, total, t, sign, _DIV, 0, False)

        if lhs is None:
            buf[pos] = "="
            rec(pos + 1, _S, closed, _ZERO, None, 1, _NONE, 0, False)

    rec(0, _S, None, _ZERO, None, 1, _NONE, 0, False)


# --------------------------------------------------------------------------
# Enumerator 2: one walk per SIDE, joined on value.
#
# Same rules, same set, different traversal: enumerate every structurally valid
# side of each length once with its exact value, then for each position of the
# `=` join the two lengths on that value.  The smaller side is the one held in
# the dictionary and the larger is streamed against it, so the memory is a few
# thousand entries whatever the width.
#
# It is a separate recursion from walk_guesses rather than a shared one because
# the two walk different spaces (one string with an `=` in it, versus one side).
# They share the arithmetic and the evaluator state above, which is where a
# discrepancy could actually hide, and checknerdle.py diffs their output sets.
# --------------------------------------------------------------------------

def walk_sides(length, emit):
    """Call emit(side, value) for every structurally valid side of that length."""
    buf = [""] * length

    def rec(pos, state, total, term, sign, pending, cur, neg):
        if pos == length:
            if state != _D:
                return
            v = _finish(total, term, sign, pending, cur, neg)
            if v is not None:
                emit("".join(buf), v)
            return

        for d in range(10):
            buf[pos] = _DIGIT[d]
            rec(pos + 1, _D, total, term, sign, pending, cur * 10 + d, neg)

        if state == _S:
            buf[pos] = "-"
            rec(pos + 1, _S, total, term, sign, pending, 0, not neg)
            return

        t = _close(term, pending, cur, neg)
        if t is None:
            return
        closed = _add(total, t) if sign > 0 else _sub(total, t)

        buf[pos] = "+"
        rec(pos + 1, _S, closed, None, 1, _NONE, 0, False)
        buf[pos] = "-"
        rec(pos + 1, _S, closed, None, -1, _NONE, 0, False)
        buf[pos] = "*"
        rec(pos + 1, _S, total, t, sign, _MUL, 0, False)
        buf[pos] = "/"
        rec(pos + 1, _S, total, t, sign, _DIV, 0, False)

    rec(0, _S, _ZERO, None, 1, _NONE, 0, False)


def walk_guesses_split(emit, width=WIDTH):
    """Call emit(equation) once for every valid guess, grouped by `=` position.

    Same set as walk_guesses, different order: all the guesses with the `=` in
    position 1 first, then position 2, and so on.
    """
    for eq in range(1, width - 1):
        nl, nr = eq, width - 1 - eq
        table = {}

        def collect(side, value):
            table.setdefault(value, []).append(side)

        if nl <= nr:
            def join(side, value):
                for left in table.get(value, ()):
                    emit(left + "=" + side)
            walk_sides(nl, collect)
            walk_sides(nr, join)
        else:
            def join(side, value):
                for right in table.get(value, ()):
                    emit(side + "=" + right)
            walk_sides(nr, collect)
            walk_sides(nl, join)


def enumerate_guesses(width=WIDTH, method="dfs"):
    """Every valid guess as a list. MATERIALISES -- for checks and small widths."""
    out = []
    (walk_guesses if method == "dfs" else walk_guesses_split)(out.append, width)
    return out
