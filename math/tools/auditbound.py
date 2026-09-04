"""Audit a PROPOSED upper bound against exact values, before it can cut anything.

THE BOUND UNDER TEST (`antiwordle.letters_bound`):

    remaining guesses  <=  (unused letters) + (non-green squares)  [- 1?]

The reasoning behind it: every guess must either introduce a letter never played
before, or — using only letters already seen — move a yellow onto a square it has
not occupied. The first kind is capped by how many letters remain untouched, the
second by how many squares are not yet pinned green.

NOTHING IS SPECIAL-CASED for "no greys left", and the formula is audited exactly
as written. Note that phrase is ambiguous and the two readings differ: a GUESS can
return no grey tiles as early as move one (an anagram of the answer), with 21
letters still unplayed, whereas a STATE where nothing can come back grey needs
every non-answer letter already dead. Only the second shrinks the letters term,
and even it does not zero the term when an answer letter has never been played.

WHY AUDIT RATHER THAN JUST WIRE IT IN.  A bound that is too LARGE only costs
speed. A bound that is too SMALL cuts the winning line and reports a maximum that
is too low — with no error, no crash, and a plausible-looking answer. This search
has already produced one wrong number that way (a memo-key collision), and it
took a long time to notice. So: measure first, on states known to be reachable,
against values known to be exact.

WHAT MAKES THE STATES TRUSTWORTHY.  Every state in a finished search's memo was
arrived at by real play from the starting position, so none of them is a
hand-written constraint that no line can produce — the failure mode that made an
earlier hand-built "counterexample" meaningless. And each carries its EXACT value,
because the memo stores values, never bounds.

Reported per variant: any VIOLATION (bound below the true value, which would make
it unusable), and the slack distribution (how much it over-states, i.e. how much
pruning it would actually buy).

    python3 tools/auditbound.py [--answers N] [--after "w1 w2"] [--guess-list L]
"""
import argparse
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import (GuessSpace, StallSearch, cons_none, letters_bound,
                        replay_prefix)
from build_patterns import load_patterns
from wordle import load_words

def resource_pool(cons, acount, word_len=5):
    """The bound the search uses TODAY: unspent count-pins plus square-bans.

    Reproduced here rather than imported so the audit compares against the same
    arithmetic the C and Python searches actually apply.
    """
    pool = 0
    for c in range(26):
        if cons.maxc[c] > acount[c]:
            pool += 1
    for i in range(word_len):
        for c2 in range(26):
            if acount[c2] and not (cons.yban[c2] >> i & 1):
                pool += 1
    return pool + 1


# Each variant maps (constraint, answer letter counts) to a claimed upper bound.
# The point of the comparison is not whether the new one is SOUND -- both are --
# but whether it is TIGHTER than what the search already applies, since a bound
# only buys pruning to the extent it sits close to the truth.
VARIANTS = [
    ("resource pool + 1  (today)", lambda c, a: resource_pool(c, a)),
    ("unused + nongreen",          lambda c, a: letters_bound(c)),
    ("unused + nongreen - 1",      lambda c, a: letters_bound(c) - 1),
    ("min(both)",                  lambda c, a: min(resource_pool(c, a),
                                                    letters_bound(c) - 1)),
]


def burn_rate_bound(cons, space, answer_gi, word_len=5):
    """The RATE version: charge each guess the letters it must introduce at once.

    `letters_bound` charges one letter per guess. But a guess fills WORD_LEN
    squares and only the required letters come free, so early on every legal word
    drags in three, four or five never-played letters together. Let m be the
    fewest new letters any legal non-answer word introduces here; while m >= 1 no
    guess is cheaper than that, so the untouched pool supports at most u/m of them
    rather than u.

    NOT SOUND AS WRITTEN, and that is the point of measuring it: m is recomputed
    per state and only ever SHRINKS as letters get used, so today's m cannot be
    charged to the whole future. It is audited to see how much there is to gain
    before anyone works out the sound form.
    """
    used = [c for c in range(26)
            if not (cons.minc[c] == 0 and cons.maxc[c] == word_len)]
    umask = 0
    for c in used:
        umask |= 1 << c
    unused = 26 - len(used)
    nongreen = sum(1 for g in cons.green if g < 0)

    legal = space.legal_list(cons)
    m = None
    for gi in legal:
        gi = int(gi)
        if gi == answer_gi:
            continue
        fresh = 0
        seen = 0
        for c in space.letter_tuples[gi]:
            bit = 1 << c
            if not (umask & bit) and not (seen & bit):
                fresh += 1
            seen |= bit
        if m is None or fresh < m:
            m = fresh
            if m == 0:
                break
    if not m:                       # some word introduces nothing; no rate to use
        return unused + nongreen
    return (unused + m - 1) // m + nongreen


def audit_state_space(space, col, answer_gi, cons, acount):
    """Search from `cons`, then check every state the search actually visited."""
    search = StallSearch(space, col, answer_gi)
    total = search.value(cons)
    stats = {name: {"violations": [], "slack": Counter()} for name, _ in VARIANTS}
    for state, (value, _) in search.memo.items():
        for name, fn in VARIANTS:
            b = fn(state, acount)
            if b < value:
                stats[name]["violations"].append((state, value, b))
            else:
                stats[name]["slack"][b - value] += 1

    # The burn-rate bound needs the legal SET per state, far too costly for every
    # one of them, so it is measured on a sample of the same states.
    import random as _random
    rng = _random.Random(0)
    states = list(search.memo.items())
    sample = rng.sample(states, min(1500, len(states)))
    name = "burn rate: unused/m + nongreen"
    stats[name] = {"violations": [], "slack": Counter()}
    for state, (value, _) in sample:
        b = burn_rate_bound(state, space, answer_gi)
        if b < value:
            stats[name]["violations"].append((state, value, b))
        else:
            stats[name]["slack"][b - value] += 1
    return total, len(search.memo), stats


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", type=int, default=6, help="how many answers to audit")
    ap.add_argument("--after", default="", help="opening prefix, to keep runs affordable")
    ap.add_argument("--guess-list", default="mystery", choices=["guess", "mystery"],
                    help="which words may be PLAYED (default: the 2315, so whole "
                         "games are affordable)")
    args = ap.parse_args()

    answers = load_words("mystery")
    space = GuessSpace(load_words(args.guess_list))
    PAT = load_patterns()
    full = {w: i for i, w in enumerate(load_words("guess"))}
    rows = np.array([full[w] for w in space.words])
    prefix = args.after.split()

    print(f"auditing {args.answers} answers, guess list {args.guess_list} "
          f"({space.n} words)" + (f", after {args.after}" if prefix else "")
          + "\n")

    grand = {}
    def bucket(name):
        return grand.setdefault(name, {"violations": 0, "slack": Counter(), "states": 0})
    for answer in answers[:args.answers]:
        col = np.asarray(PAT[:, answers.index(answer)])[rows]
        try:
            cons = replay_prefix(space, col, prefix)
        except ValueError as exc:
            print(f"  {answer}: skipped ({exc})")
            continue
        acount = [0] * 26
        for ch in answer:
            acount[ord(ch) - 97] += 1
        total, nstates, stats = audit_state_space(
            space, col, space.index[answer], cons, acount)
        bits = []
        for name in stats:
            v = len(stats[name]["violations"])
            g = bucket(name)
            g["violations"] += v
            g["slack"] += stats[name]["slack"]
            g["states"] += nstates
            bits.append(f"{name}: {'OK' if not v else str(v) + ' VIOL'}")
        print(f"  {answer} = {total:2d}  ({nstates} states)   " + " | ".join(bits))
        for name in stats:
            for state, value, b in stats[name]["violations"][:2]:
                greens = sum(1 for g in state.green if g >= 0)
                print(f"      {name}: true {value} > bound {b} "
                      f"({greens} greens, {5 - greens} non-green)")

    print("\n" + "=" * 72)
    for name in grand:
        g = grand[name]
        slack = g["slack"]
        n = sum(slack.values())
        print(f"\n{name}")
        print(f"  states audited : {g['states']}")
        print(f"  violations     : {g['violations']}"
              + ("   <-- UNUSABLE as a cutoff" if g["violations"] else "   (none)"))
        if n:
            tight = slack[0]
            mean = sum(k * v for k, v in slack.items()) / n
            print(f"  exactly tight  : {tight} states ({100.0 * tight / n:.1f}%)")
            print(f"  mean slack     : {mean:.2f} guesses")
            top = ", ".join(f"+{k}:{v}" for k, v in sorted(slack.items())[:8])
            print(f"  slack spread   : {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
