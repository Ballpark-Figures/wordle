"""Build Letroso's word lists from LETROSO'S OWN client dictionary.

WHY THIS EXISTS, and why it changed (2026-09-07).  Letroso is played on
letroso.com, and the ONE thing about it that is knowable client-side is which
words it will accept as a guess: its bundle ships a validation list,
`assets/all-en-<hash>.js`, a single JSON array of ~93k lowercase words, lengths
2..10 (`Pa`, the longest word that can be typed, is 10).  We now take our GUESS
list from THAT list -- so a word we accept is a word letroso accepts, and a word
letroso rejects (e.g. `clarionets`, which is in hello's Scrabble dictionary but
NOT in letroso's) we reject too.  This REPLACES the earlier decision to guess
from hello wordl's per-length dictionaries; that mismatch is exactly what made
us diverge from the live game.  The output now lives under
`data/shared/words/letroso/len<L>/`, NOT `hello/` -- the Wordle length-sweeps
still read hello's lists and must not be disturbed.

  * len<L>/guess.txt   -- letroso's own words of length L, cleaned to a-z.  No
    decision involved: it is letroso's list verbatim.
  * len<L>/mystery.txt -- the ANSWER list, and it is OURS.  Letroso's real
    answer set is SERVER-SIDE and we do not have it, so we model it, exactly as
    before, from hello wordl's curated `targets.json` (Norvig-frequency,
    hand-pruned) -- INTERSECTED with letroso's guess list so every answer is a
    word the game would actually accept (`ANS2G` indexes answers into guesses).

THE SHORT LENGTHS.  hello's answer curation starts at length 4, so lengths 2 and
3 have no hello answers.  For those two we build the answer list ourselves with
the SAME rule the length-3 list has always used: keep the guess words whose
`wordfreq zipf_frequency(w, 'en') >= ZIPF_BAR`.  ZIPF_BAR = 3.0 was chosen (see
history below) to put the answers/guesses ratio in line with lengths 4..10.  The
pool it now filters is LETROSO's short-word list, not hello's -- recorded in
each `mystery.txt.meta` so it can never be mistaken for hello's curation.

  `wordfreq` is the same package + "large" English list build_freq_wordlist.py
  uses, so a zipf here means what it means there.

PROVENANCE.  Letroso's bundle hash changes on every deploy, so this is NOT
pinned like hello's SHA.  The build discovers the current `all-en-<hash>.js`
from the live site (or reads a cached/`--bundle` copy), and records the hash and
fetch date in the top-level README + each meta.

Run:  python3 build_letroso_lists.py                 # fetch live, settled rule
      python3 build_letroso_lists.py --bar 2.5       # a different, recorded bar
      python3 build_letroso_lists.py --bundle FILE    # build from a local .js
"""

import argparse
import datetime
import json
import os
import re
import urllib.request

from build_wordlists import _clean  # the shared a-z cleaner

SITE = "https://letroso.com"

# The curation bar for the SHORT lengths (2, 3), in zipf.  Chosen to put their
# answers/guesses ratio in line with lengths 4..10; NOT copied from anywhere.
ZIPF_BAR = 3.0
SHORT_LENGTHS = (2, 3)          # lengths hello does not curate answers for
LENGTHS = range(2, 11)          # letroso serves 2..10 (Pa = 10)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_HERE, "data", "local", "letroso")
_WORDS = os.path.join(_HERE, "data", "shared", "words")
_OUT = os.path.join(_WORDS, "letroso")


def _hello_answers(length):
    """hello wordl's committed answer list at `length` (the length-sweep set)."""
    path = os.path.join(_WORDS, "hello", "len%d" % length, "mystery.txt")
    if not os.path.exists(path):
        raise SystemExit("missing %s -- run build_wordlists.py first" % path)
    with open(path) as f:
        return {w.strip() for w in f if w.strip()}

TOP_README = """\
# Letroso word lists -- READ THIS BEFORE COMPARING WITH hello/ OR WITH THE GAME

`guess.txt` at each length is LETROSO'S OWN validation list (letroso.com's
`assets/all-en-<hash>.js`), cleaned to a-z.  A word we accept as a guess is a
word letroso accepts; a word letroso rejects, we reject.  This is the point of
the list -- it is NOT hello wordl's dictionary (that is `../hello/`, used by the
Wordle length-sweeps).

`mystery.txt` (the ANSWER list) IS OURS.  Letroso's real answer set is
server-side and unknown to us, so we model it from hello wordl's curated
`targets.json`, intersected with letroso's guess list.  Lengths 2 and 3 have no
hello answers and are built by our own frequency rule -- see each
`len<L>/mystery.txt.meta`.

source bundle: %s
fetched: %s
"""


def _find_bundle_url():
    """Discover the current all-en-<hash>.js URL from the live site."""
    with urllib.request.urlopen(SITE + "/", timeout=30) as r:
        index_ref = re.search(rb'/assets/index-[A-Za-z0-9_-]+\.js', r.read())
    if not index_ref:
        raise SystemExit("could not find index-*.js on %s" % SITE)
    index_url = SITE + index_ref.group().decode()
    with urllib.request.urlopen(index_url, timeout=30) as r:
        chunk = re.search(rb'all-en-[A-Za-z0-9_-]+\.js', r.read())
    if not chunk:
        raise SystemExit("could not find all-en-*.js referenced by %s" % index_url)
    return SITE + "/assets/" + chunk.group().decode()


def _load_bundle(bundle):
    """Return (words, provenance_string).  `bundle` is a local path or None.

    None -> use the newest cached all-en-*.js under data/local/letroso, or fetch
    the live site if there is no cache.  A local path is read verbatim.
    """
    os.makedirs(_CACHE, exist_ok=True)
    if bundle:
        path, prov = bundle, "local file %s" % os.path.basename(bundle)
    else:
        cached = sorted(f for f in os.listdir(_CACHE) if f.startswith("all-en-"))
        if cached:
            path = os.path.join(_CACHE, cached[-1])
            prov = "cached %s" % cached[-1]
        else:
            url = _find_bundle_url()
            path = os.path.join(_CACHE, os.path.basename(url))
            print("  downloading %s" % url)
            urllib.request.urlretrieve(url, path)
            prov = url
    with open(path, encoding="utf-8") as f:
        src = f.read()
    # The bundle is `var e=JSON.parse(`[ ... ]`);export{e as default};`.
    m = re.search(r"JSON\.parse\(`(.*)`\)", src, re.S)
    if m:
        words = json.loads(m.group(1))
    else:                                   # format changed: fall back to tokens
        words = re.findall(r'"([a-z]+)"', src)
        if not words:
            raise SystemExit("could not extract words from %s" % path)
    return words, prov


def build(bar=ZIPF_BAR, bundle=None):
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        raise SystemExit("needs `wordfreq` -- pip install wordfreq")

    raw, prov = _load_bundle(bundle)

    print("bundle: %s  (%d raw words)" % (prov, len(raw)))
    print("%4s %9s %9s   %s" % ("len", "guesses", "answers", "answer source"))

    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "README.md"), "w") as f:
        f.write(TOP_README % (prov, datetime.date.today().isoformat()))

    for length in LENGTHS:
        guesses = _clean(raw, length)       # letroso's words of this length, a-z
        if not guesses:
            raise SystemExit("letroso bundle has no length-%d words" % length)

        if length in SHORT_LENGTHS:
            answers = [w for w in guesses
                       if zipf_frequency(w, "en") >= bar]
            src = "OURS: wordfreq zipf >= %.2f" % bar
        else:
            hello_ans = _hello_answers(length)
            answers = sorted(hello_ans & set(guesses))
            dropped = len(hello_ans) - len(answers)
            src = "hello targets, %d dropped (not letroso-legal)" % dropped
        if not answers:
            raise SystemExit("length %d: no answers -- refusing to write an "
                             "empty answer list" % length)

        # Every answer must be a legal guess (ANS2G indexes answers into the
        # guess list); true by construction here, asserted so it can't drift.
        missing = sorted(set(answers) - set(guesses))
        if missing:
            raise SystemExit("length %d: answers not in guess list: %s"
                             % (length, missing[:5]))

        d = os.path.join(_OUT, "len%d" % length)
        os.makedirs(d, exist_ok=True)
        for name, words in (("guess", guesses), ("mystery", answers)):
            with open(os.path.join(d, "%s.txt" % name), "w") as f:
                f.write("\n".join(words) + "\n")
        with open(os.path.join(d, "mystery.txt.meta"), "w") as f:
            f.write("# length-%d ANSWER list.  See ../README.md.\n" % length)
            f.write("built: %s\n" % datetime.date.today().isoformat())
            f.write("guess source: letroso bundle (%s)\n" % prov)
            if length in SHORT_LENGTHS:
                f.write("answer rule: OURS -- wordfreq zipf_frequency(w,'en') "
                        ">= %.2f over letroso's length-%d guesses\n"
                        % (bar, length))
            else:
                f.write("answer rule: hello wordl mystery list (length %d), "
                        "intersected with letroso's guess list\n" % length)
            f.write("guesses: %d\nanswers: %d\nratio: %.1f%%\n"
                    % (len(guesses), len(answers),
                       100.0 * len(answers) / len(guesses)))

        print("%4d %9d %9d   %s" % (length, len(guesses), len(answers), src))

    print("\nwrote %s/len<L>/{guess,mystery}.txt + meta + README.md" % _OUT)
    print("NOTE: the cached root ranking is fingerprinted over both lists, so "
          "it is now stale -- re-run run-letroso-rank.sh.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bar", type=float, default=ZIPF_BAR,
                    help="zipf cutoff for length-2/3 answers (default %.1f)"
                         % ZIPF_BAR)
    ap.add_argument("--bundle", metavar="FILE",
                    help="build from a local all-en-*.js instead of fetching")
    args = ap.parse_args()
    build(args.bar, args.bundle)
