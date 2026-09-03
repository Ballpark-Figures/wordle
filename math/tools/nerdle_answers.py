"""Filter an enumerated Nerdle GUESS list down to the legal ANSWERS.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-nerdle-answers.sh                    # from math/, or anywhere
    bash solver/run-nerdle-answers.sh --width 6

WHAT THIS COMPUTES: the answers are a strict SUBSET of the guesses -- every
answer is something you are allowed to type -- so this reads the guess list
enumerated by tools/nerdle_enumerate.py and keeps the ones satisfying the four
answer rules A1-A4, which math/nerdle.py states exactly and is the source of
truth for.  In short: the right side is a bare number, no digit run begins with
a zero (so no leading zeros and no bare `0` anywhere), no unary minus appears,
and the left side contains at least one operator.

THE INTERMEDIATE VALUES ARE DELIBERATELY UNCONSTRAINED.  The user settled on
2026-09-03 that an answer's left side may pass through a negative value
(`1-2+3=2`) and through a fraction (`1/2*4=2`).  Both stricter readings were
live until then and both give a SMALLER set, so a count computed under either is
a different quantity and must not be quoted as the answer count.

Equations are counted AS WRITTEN, exactly as in pass one: `12+34=46` and
`34+12=46` are two answers.  Collapsing commutative equivalents is pass two and
nothing here does it.

Re-verifying costs nothing worth saving, so every line read is put back through
is_valid_guess as well.  That makes this a free check on the guess file: if its
count disagrees with the file's .meta, something upstream is wrong and the run
says so rather than quietly filtering a corrupt list.
"""

import gzip
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nerdle import WIDTH, answer_rules, is_answer, is_valid_guess  # noqa: E402

# Nerdle's own published figures, quoted from its FAQ (read 2026-09-03,
# https://www.nerdlegame.com/faqs.html?faq=commutativity):
#
#   "As far as we can work out, there are over 100,000 valid solutions but...
#    we have chosen 17,723 of these as there are quite a lot we thought you
#    wouldn't like."
#
# BOTH FIGURES ARE NOW REPRODUCED, which is how A2's zero-answer exception was
# established (2026-09-03, and the reasoning is written out in math/nerdle.py):
# the settled rules give exactly 17723, and dropping A2 entirely gives 112566,
# the "over 100,000".  That was a genuine prediction rather than a fit -- the
# switch was picked as the likeliest single explanation of a 367 gap before the
# run -- but it remains an inference from two published counts, so treat a
# future mismatch as evidence about the rules and not as a reason to add
# switches until the number comes back.
NERDLE_CHOSEN = 17723
NERDLE_VALID = 100000

# Each disputed clause on its own, then the combinations worth seeing.  The
# first row is the settled rule set and is the only count that may be called
# the answer count.
VARIANTS = [
    ("settled rules A1-A4",          {}),
    ("- 0 as the answer",            {"zero_answer": False}),
    ("+ bare 0 as an operand",       {"zero_operand": True}),
    ("+ negative answer",            {"negative_answer": True}),
    ("+ operator-free left side",    {"no_operator": True}),
    ("+ leading zeros anywhere",     {"leading_zeros": True}),
    ("+ expression right side",      {"expression_rhs": True}),
    ("- fractional intermediates",   {"exact_division": True}),
    ("- negative intermediates",     {"nonneg_running": True}),
    ("- both intermediate kinds",    {"exact_division": True, "nonneg_running": True}),
    ("everything loosened",          {"zero_operand": True, "leading_zeros": True,
                                      "expression_rhs": True, "negative_answer": True,
                                      "no_operator": True}),
]

RULES = "2026-09-03"      # the rule set in math/nerdle.py this output obeys


def parse_args(argv):
    width = WIDTH
    guesses = None
    out = None
    variants = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--variants":
            variants = True; i += 1
        elif a == "--width":
            width = int(argv[i + 1]); i += 2
        elif a == "--guesses":
            guesses = argv[i + 1]; i += 2
        elif a == "--out":
            out = argv[i + 1]; i += 2
        elif a == "--no-out":
            out = False; i += 1
        else:
            raise SystemExit("unknown argument: %s" % a)
    if width < 3:
        raise SystemExit("--width must be at least 3")
    if guesses is None:
        raise SystemExit("--guesses (the pass-one guess list) is required")
    if out is None:
        raise SystemExit(
            "--out is required (or --no-out to discard results deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-nerdle-answers.sh")
    return width, guesses, out, variants


def open_maybe_gz(path, mode):
    return gzip.open(path, mode) if path.endswith(".gz") else open(path, mode)


def meta_count(path):
    """The count the guess file recorded for itself, or None if unavailable."""
    try:
        with open(path + ".meta") as f:
            for line in f:
                if line.startswith("count="):
                    return int(line.split("=", 1)[1])
    except OSError:
        pass
    return None


def run_variants(width, guesses, out):
    """Count the answers under each disputed rule set, for comparison with the
    live game's published figures.  Diagnostic only -- see NERDLE_CHOSEN."""
    print("nerdle answer-rule variants: width=%d" % width)
    print("reading %s" % guesses)
    print()
    print("Nerdle's FAQ: over %d valid solutions, of which they CHOSE %d"
          % (NERDLE_VALID, NERDLE_CHOSEN))
    print("as \"there are quite a lot we thought you wouldn't like\".  Their")
    print("chosen list is a matter of taste, so treat it as a sanity check on")
    print("the order of magnitude, NOT as a number to tune switches until we hit.")
    print()
    sys.stdout.flush()

    t0 = time.time()
    counts = [0] * len(VARIANTS)
    read = 0
    with open_maybe_gz(guesses, "rt") as src:
        for line in src:
            s = line.strip()
            if not s or not is_valid_guess(s, width):
                continue
            read += 1
            for k, (_, opts) in enumerate(VARIANTS):
                if answer_rules(s, width, check_guess=False, **opts):
                    counts[k] += 1

    base = counts[0]
    print("%-30s %10s %10s" % ("rule set", "answers", "vs A1-A4"))
    for (name, _), c in zip(VARIANTS, counts):
        delta = c - base
        print("%-30s %10d %10s" % (name, c, "" if not delta else "%+d" % delta))
    print("\n%d valid guesses read in %.1fs" % (read, time.time() - t0))

    if out:
        with open(out, "w") as f:
            f.write("rule_set,answers,delta_vs_settled\n")
            for (name, _), c in zip(VARIANTS, counts):
                f.write("%s,%d,%+d\n" % (name, c, c - base))
        print("wrote %s" % out)
    return 0


def main(argv):
    width, guesses, out, variants = parse_args(argv)
    if variants:
        return run_variants(width, guesses, out)

    print("nerdle answer filter: width=%d rules=%s" % (width, RULES))
    print("reading %s" % guesses)
    print("answers are a strict subset of the guesses; intermediate values are")
    print("deliberately unconstrained (see math/nerdle.py A1-A4).")
    sys.stdout.flush()

    t0 = time.time()
    read = kept = malformed = 0
    by_eq = [0] * width
    fh = open_maybe_gz(out, "wt") if out else None
    try:
        with open_maybe_gz(guesses, "rt") as src:
            for line in src:
                s = line.strip()
                if not s:
                    continue
                read += 1
                if not is_valid_guess(s, width):
                    malformed += 1
                    if malformed <= 5:
                        print("  NOT A VALID GUESS: %r" % s)
                    continue
                if is_answer(s, width):
                    kept += 1
                    by_eq[s.index("=")] += 1
                    if fh is not None:
                        fh.write(s)
                        fh.write("\n")
    finally:
        if fh is not None:
            fh.close()

    secs = time.time() - t0
    print("\n%d guesses read, %d are legal answers (%.2f%%) in %.1fs"
          % (read, kept, 100.0 * kept / read if read else 0.0, secs))
    print("by position of the `=`:")
    for p, c in enumerate(by_eq):
        if c:
            print("  %d | %12d" % (p, c))

    expected = meta_count(guesses)
    if expected is not None and expected != read:
        print("\nMISMATCH: %s.meta records %d guesses, %d were read."
              % (guesses, expected, read))
        print("The guess list is incomplete or truncated -- fix it before")
        print("quoting this answer count.")
    if malformed:
        print("\n%d lines were not valid guesses at width %d." % (malformed, width))
        print("The guess list does not match these rules -- re-enumerate it.")

    if out:
        with open(out + ".meta", "w") as m:
            m.write("kind=answers\n")
            m.write("width=%d\n" % width)
            m.write("rules=%s\n" % RULES)
            m.write("as_written=1\n")
            m.write("commutative_collapsed=0\n")
            m.write("intermediates_constrained=0\n")
            m.write("from=%s\n" % guesses)
            m.write("guesses_read=%d\n" % read)
            m.write("count=%d\n" % kept)
            m.write("seconds=%.1f\n" % secs)
            for p, c in enumerate(by_eq):
                if c:
                    m.write("eq_at_%d=%d\n" % (p, c))
        print("\nwrote %s (+ .meta)" % out)

    if malformed or (expected is not None and expected != read):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
