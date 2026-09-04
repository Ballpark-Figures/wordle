"""Build the length-3 word lists Letroso needs, which hello wordl does not ship.

WHY THIS EXISTS.  The length sweeps read
`data/shared/words/hello/len<L>/{guess,mystery}.txt`, built by
build_wordlists.py from hello wordl's two published lists.  hello's UI clamps to
4..11, and its ANSWER curation (`targets.json`) accordingly contains NOTHING
below length 4 -- while its GUESS list (`dictionary.json`, the North American
Scrabble stock) does have 1015 three-letter words.  Letroso has no fixed length
and can serve a short answer, so length 3 is needed and only its answer half is
actually missing.

  * len3/guess.txt   -- hello's own 1015 three-letter dictionary words.  Same
    source and same cleaning rule as every other length; no decision involved.
  * len3/mystery.txt -- OURS, and it is a MODELLING DECISION, not hello's
    curation.  Recorded in len3/mystery.txt.meta and in len3/README.md so it can
    never be mistaken for one of hello's hand-pruned answer lists.

THE RULE, and why this one.  hello's answer lists CANNOT be reproduced by a
frequency cut: measured against their own dictionaries, no zipf bar at any
length exceeds ~65% precision, because their hand-pruning (plurals,
conjugations, British spellings) tracks something frequency cannot see.  So
length 3 cannot be made consistent with 4..10 by construction, and the honest
target is to match them in PROPORTION instead -- answers as a fraction of that
length's guess list, which runs 58% at L=4 and rises as words get shorter.

`zipf_frequency >= ZIPF_BAR` with ZIPF_BAR = 3.0 keeps 707 of the 1015 words =
70%, sitting in the band that trend extrapolates to for L=3.  The bar also
removes exactly the Scrabble-only tail that makes a short list unplayable
(`vug vum zuz pya qis suq mho zax pyx`).  It is NOT free: it also cuts some
perfectly ordinary words (`dud zap bib fez hag tut yap lob`).  A hand pass over
the 175 words between zipf 2.5 and 3.0 would recover those; --bar exists so that
choice stays open and always lands in the .meta.

`wordfreq` is the same package and the same "large" English list that
build_freq_wordlist.py uses, so a zipf here means what it means there.

Run:  python3 build_letroso_lists.py            # the settled rule
      python3 build_letroso_lists.py --bar 2.5  # a different, recorded, rule
"""

import argparse
import datetime
import os

from build_wordlists import _clean, _fetch

# The curation bar, in zipf.  See the docstring: chosen to put length 3's
# answers/guesses ratio in line with lengths 4..10, NOT copied from anywhere.
ZIPF_BAR = 3.0
LENGTH = 3

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "data", "shared", "words", "hello", "len%d" % LENGTH)

README = """\
# length 3 -- READ THIS BEFORE COMPARING IT WITH THE OTHER LENGTHS

`guess.txt` is hello wordl's own three-letter dictionary, identical in source
and cleaning to every other `len<L>/guess.txt`.

`mystery.txt` IS NOT hello's.  hello's answer curation starts at length 4, so
this list was built by us with a frequency rule -- see `mystery.txt.meta` for
the exact bar and `build_letroso_lists.py` for why that rule and not another.
It is a modelling decision of ours, and a length-3 answer number is therefore
not on quite the same footing as a length 4..10 one.  Say so when quoting it.
"""


def build(bar=ZIPF_BAR):
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        raise SystemExit("needs `wordfreq` -- pip install wordfreq")

    guesses = _clean(_fetch("dictionary.json"), LENGTH)
    if not guesses:
        raise SystemExit("hello's dictionary has no length-%d words" % LENGTH)

    answers = [w for w in guesses if zipf_frequency(w, "en") >= bar]
    if not answers:
        raise SystemExit("bar %.2f keeps nothing -- refusing to write an empty "
                         "answer list" % bar)

    # Same invariant build_wordlists.py enforces: every answer must be a legal
    # guess, or a solver indexing answers into the guess list mis-keys silently.
    missing = sorted(set(answers) - set(guesses))
    if missing:
        raise SystemExit("answers not in the guess list: %s" % missing[:5])

    os.makedirs(_OUT, exist_ok=True)
    for name, words in (("guess", guesses), ("mystery", answers)):
        with open(os.path.join(_OUT, "%s.txt" % name), "w") as f:
            f.write("\n".join(words) + "\n")
    with open(os.path.join(_OUT, "README.md"), "w") as f:
        f.write(README)
    with open(os.path.join(_OUT, "mystery.txt.meta"), "w") as f:
        f.write(
            "# length-3 ANSWER list -- OURS, not hello's.  See README.md.\n"
            "built: %s\n"
            "source: hello wordl dictionary.json, length %d, cleaned a-z\n"
            "rule: wordfreq zipf_frequency(w, 'en') >= %.2f\n"
            "pool: %d\nkept: %d\nratio: %.1f%%\n"
            % (datetime.date.today().isoformat(), LENGTH, bar,
               len(guesses), len(answers), 100.0 * len(answers) / len(guesses)))

    print("length %d: %d guesses, %d answers (%.0f%% of the pool) at zipf >= %.2f"
          % (LENGTH, len(guesses), len(answers),
             100.0 * len(answers) / len(guesses), bar))
    print("wrote %s/{guess,mystery}.txt + README.md + mystery.txt.meta" % _OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bar", type=float, default=ZIPF_BAR,
                    help="zipf cutoff for the answer list (default %.1f)" % ZIPF_BAR)
    build(ap.parse_args().bar)
