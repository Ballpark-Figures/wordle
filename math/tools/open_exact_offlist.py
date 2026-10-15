"""Exact (mean, win rate) for a blind opening whose words need NOT be legal guesses.

math/openexact.py states the strategy and the recursions and IS the source of
truth; this is a thin driver beside tools/open_exact.py, which resolves every
opening word through the 12972-word guess list and so cannot price a word from a
NEWER Wordle list.  Nothing here is new math.

WHY AN OFF-LIST WORD IS WELL DEFINED.  Feedback is a function of two strings, so
a word only has to be typeable in the real game; and the random tail draws from
the consistent ANSWERS, which this does not touch.  `evaluate` already documents
both halves it needs: `rows` is just the words' replies against the pool, and
`at_pool` takes -1 for a word that can never be the answer.  So the only thing
the guess list was ever providing is a matrix ROW, and wordle.pattern_row
computes that from the strings (checkpatterns.py validates it against
wordle.pattern).

IT WRITES NOTHING.  The opening is not expressible in the committed openexact
CSV's terms, so a row there would be a number under a name that implies the
standard lists.  Read it off stdout.

    python3 tools/open_exact_offlist.py corbe midst planh
    python3 tools/open_exact_offlist.py --cap 6 crane spilt

THE SELF-CHECK IS NOT OPTIONAL and runs every time: for every opening word that
IS in the guess list, the row computed from the STRINGS must equal the committed
matrix row, bit for bit.  That exercises the off-list code path on the words we
can still cross-check, so the only thing left unverified is the arithmetic being
applied to one more row of the same kind.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openexact import evaluate                                    # noqa: E402
from paircover import pool_matrix                                 # noqa: E402
from build_patterns import load_patterns                          # noqa: E402
from wordle import load_words, pattern_row, to_codes              # noqa: E402


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("words", nargs="+")
    p.add_argument("--cap", type=int, default=6)
    a = p.parse_args(argv)

    words = [w.strip().lower() for w in a.words]
    bad = [w for w in words if len(w) != 5 or not w.isalpha()]
    if bad:
        raise SystemExit("not five-letter alphabetic words: %s" % ", ".join(bad))
    if len(words) >= a.cap:
        raise SystemExit("a %d-word opening leaves no guesses under --cap %d"
                         % (len(words), a.cap))

    guesses, answers = load_words("guess"), load_words("mystery")
    gpos = {w: i for i, w in enumerate(guesses)}
    ppos = {w: i for i, w in enumerate(answers)}

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in answers])
    M = pool_matrix(full, cols)
    ans = np.arange(len(answers))

    # every row from the STRINGS, so on-list and off-list words share one path
    acodes = to_codes(answers)
    rows = np.ascontiguousarray(
        np.stack([np.asarray(pattern_row(w, acodes)) for w in words]))

    # self-check: the on-list words must reproduce the committed matrix exactly
    checked = 0
    for i, w in enumerate(words):
        if w in gpos:
            ref = full[gpos[w]][cols]
            if not np.array_equal(rows[i], ref):
                raise SystemExit("FAIL %s: string row != matrix row" % w)
            checked += 1
    offlist = [w for w in words if w not in gpos]

    r = evaluate(M, rows, [ppos.get(w, -1) for w in words], ans, cap=a.cap)

    print("opening      %s" % " ".join(words))
    print("off-list     %s" % (", ".join(offlist) if offlist else "none"))
    print("row check    %d of %d word(s) matched the committed matrix exactly"
          % (checked, len(words)))
    print("pool         answer (%d)   cap %d   budget %d"
          % (len(answers), a.cap, r["budget"]))
    print()
    print("mean         %.9f  expected guesses OUTRIGHT (never truncated)"
          % r["mean"])
    print("win_rate     %.9f  (fraction at <= %d)" % (r["win_rate"], a.cap))
    print("total        %.4f over %d answers" % (r["total"], r["answers"]))
    print("lost         %.6f" % r["lost"])
    print("buckets      %d" % r["buckets"])


if __name__ == "__main__":
    main(sys.argv[1:])
