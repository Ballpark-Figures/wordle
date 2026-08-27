"""Build the per-length word lists from hello wordl's published lists.

Wordle itself is 5 letters only, so a length sweep needs a source that curates
BOTH a guess list and an answer list at every length under one rule. `hello
wordl` (https://github.com/lynn/hello, MIT) is that source:

  * `src/dictionary.json` -- valid guesses. Scrabble stock (TWL/NWL family) at
    every length EXCEPT 5, where it is Wordle's own 12972 (a Collins list). That
    inconsistency is inherited, not introduced here; see the table in the repo
    CLAUDE.md.
  * `src/targets.json`    -- possible answers. Curated from Peter Norvig's
    English frequency list, hand-pruned. A LOOSER bar than the NYT's 2315:
    at 5 letters it holds 3238 words, of which 2077 are among the NYT 2315.

So `math/data/shared/words/hello/len<L>/mystery.txt` is NOT the NYT answer list
at L=5, and the top-level `guess.txt`/`mystery.txt` (12972/2315) are left alone.

Two things need cleaning out of `targets.json` before a solver ever sees it:
profanity is masked as ALL-ASTERISK entries ("****", "*****", ... -- 551 of
them, no partial masks), and there are duplicates. Both would be treated as
real words. `dictionary.json` has neither, but it is deduped the same way so
the two paths cannot diverge.

Run:  python3 build_wordlists.py            # lengths 4..11 (what the game offers)
      python3 build_wordlists.py 4 5 6      # just these

Output is COMMITTED (it is what the solver reads and must sync between
machines); the two source JSONs are cached under data/local/ and are not.
"""

import json
import os
import sys
import urllib.request

# Pinned so a regeneration is reproducible rather than "whatever main is today".
HELLO_SHA = "835db051e78d0dba4e38bc4b19ae5560b8efbbc3"
HELLO_RAW = f"https://raw.githubusercontent.com/lynn/hello/{HELLO_SHA}/src"

# hello's own UI clamps to 4..11 (minLength/maxLength in src/Game.tsx); the
# lists themselves run to 15, so raising this ceiling is the only change needed.
LENGTHS = range(4, 12)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_HERE, "data", "local", "hello")
_OUT = os.path.join(_HERE, "data", "shared", "words", "hello")


def _fetch(name):
    """Return hello's <name>.json, caching the download under data/local/."""
    os.makedirs(_CACHE, exist_ok=True)
    path = os.path.join(_CACHE, name)
    if not os.path.exists(path):
        url = f"{HELLO_RAW}/{name}"
        print(f"  downloading {url}")
        urllib.request.urlretrieve(url, path)
    with open(path) as f:
        return json.load(f)


def _clean(words, length):
    """Words of exactly `length`, lowercase a-z only, deduped and sorted.

    The a-z filter is what drops the masked-profanity entries; it is written as
    a positive character test rather than a "no asterisk" test so any other
    stray punctuation is caught by the same line.
    """
    keep = {
        w for w in (s.strip().lower() for s in words)
        if len(w) == length and w.isascii() and w.isalpha()
    }
    return sorted(keep)


def build(lengths=LENGTHS):
    guesses_all = _fetch("dictionary.json")
    targets_all = _fetch("targets.json")

    print(f"{'len':>4} {'guesses':>9} {'answers':>9}   {'dropped (non a-z)':>18}")
    for length in lengths:
        guesses = _clean(guesses_all, length)
        answers = _clean(targets_all, length)

        raw_targets = sum(1 for w in targets_all if len(w.strip()) == length)
        dropped = raw_targets - len(answers)

        # Every answer must be a legal guess -- the solver indexes answers into
        # the guess list (ANS2G) and would silently mis-key if one were missing.
        missing = sorted(set(answers) - set(guesses))
        if missing:
            raise SystemExit(
                f"length {length}: {len(missing)} answers are not legal guesses, "
                f"e.g. {missing[:5]} -- refusing to write a list the solver "
                f"cannot index"
            )

        d = os.path.join(_OUT, f"len{length}")
        os.makedirs(d, exist_ok=True)
        for name, words in (("guess", guesses), ("mystery", answers)):
            with open(os.path.join(d, f"{name}.txt"), "w") as f:
                f.write("\n".join(words) + "\n")

        print(f"{length:>4} {len(guesses):>9} {len(answers):>9}   {dropped:>18}")

    print(f"\nwrote {_OUT}/len<L>/{{guess,mystery}}.txt")


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    build(args or LENGTHS)
