"""Rank the 12972 Wordle guess words by English word frequency, and build the
custom wordlist for the adversarial video from that ranking.

Same source as the hangman video's wordlist: the `wordfreq` package (3.1.1),
its "large" English list -- so a zipf here means the same thing it does there.
`zipf` is log10(occurrences per billion words); higher = more common. Anchors:
4.0 ~ 10 per million, 3.0 ~ 1 per million, 0.0 = not in wordfreq's list at all.

TWO outputs, both committed:

  words/guess_by_freq.txt -- EVERY guess word as `word<TAB>zipf`, most common
      first (ties alphabetical). No curation, no cutoff, so a different cutoff
      needs no regeneration of the frequency data.

  words/custom.txt -- the custom wordlist: every guess word at or above
      --cutoff, PLUS every NYT answer word regardless of its frequency (216 of
      the 2315 answers sit below the cutoff and would otherwise be dropped from
      a list the game itself can pick). One word per line, alphabetical, same
      format as guess.txt/mystery.txt so a solver can read it directly.

CUTOFF 2.5 is hangman's `DEFAULT_ZIPF` -- its chosen "familiar to about half of
players" bar (hangman/math/wordlist.py). Note hangman applies it on top of a
hunspell spellcheck plus curated block/allow lists; this list has no such
curation, only the frequency bar and the answer-word floor.

Run:  .venv/bin/python math/build_freq_wordlist.py
      .venv/bin/python math/build_freq_wordlist.py --cutoff 3.0
"""

from __future__ import annotations

import os
import sys

WORDLIST = "large"  # wordfreq's deep English list, as hangman uses

# hangman's DEFAULT_ZIPF: "familiar to about half of players".
CUTOFF = 2.5

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORDS = os.path.join(_HERE, "data", "shared", "words")
DEFAULT_IN = os.path.join(_WORDS, "guess.txt")
DEFAULT_ANSWERS = os.path.join(_WORDS, "mystery.txt")
DEFAULT_RANKED = os.path.join(_WORDS, "guess_by_freq.txt")
DEFAULT_CUSTOM = os.path.join(_WORDS, "custom.txt")


def read_words(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def load_zipf(path: str = DEFAULT_RANKED) -> dict[str, float]:
    """Read the COMMITTED ranking: {word: zipf} from `word<TAB>zipf` lines.

    THE READER OF guess_by_freq.txt, and it lives here because this module owns
    that file's format -- a second copy of the parse is how the two drift. It
    imports nothing from wordfreq, so a consumer that only wants the numbers
    (green_templates.py) does not take on that dependency or its data download;
    the frequencies are SOURCED from the committed artifact, never recomputed.

    A zipf of 0.00 is a real value, not a gap: it means wordfreq's "large" list
    does not contain the word at all, which is true of thousands of the 12972.
    """
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            word, _, zipf = line.partition("\t")
            out[word.strip()] = float(zipf)
    return out


def rank(path: str) -> list[tuple[str, float]]:
    """Every word in `path` with its zipf, most common first (ties alphabetical)."""
    from wordfreq import zipf_frequency  # heavy + a data download; only rank() needs it

    rows = [(w, zipf_frequency(w, "en", wordlist=WORDLIST)) for w in read_words(path)]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows


def main(argv: list[str]) -> None:
    src, answers = DEFAULT_IN, DEFAULT_ANSWERS
    ranked_out, custom_out = DEFAULT_RANKED, DEFAULT_CUSTOM
    cutoff = CUTOFF
    it = iter(argv)
    for a in it:
        if a == "--in":
            src = next(it)
        elif a == "--answers":
            answers = next(it)
        elif a == "--out":
            ranked_out = next(it)
        elif a == "--custom-out":
            custom_out = next(it)
        elif a == "--cutoff":
            cutoff = float(next(it))
        else:
            raise SystemExit(f"unknown arg {a!r} (--in/--answers/--out/--custom-out/--cutoff)")

    rows = rank(src)
    os.makedirs(os.path.dirname(ranked_out), exist_ok=True)
    with open(ranked_out, "w", encoding="utf-8") as fh:
        for word, z in rows:
            fh.write(f"{word}\t{z:.2f}\n")
    print(f"wrote {len(rows):,} words to {ranked_out}  (source {src}, wordfreq {WORDLIST!r})")
    for cut in (5.0, 4.0, 3.5, 3.0, 2.5, 2.0, 1.0):
        print(f"  zipf >= {cut}: {sum(1 for _, z in rows if z >= cut):,} words")
    print(f"  zipf == 0.00 (not in wordfreq): {sum(1 for _, z in rows if z == 0.0):,} words")

    over = {w for w, z in rows if z >= cutoff}
    ans = set(read_words(answers))
    missing = sorted(ans - {w for w, _ in rows})
    if missing:
        raise SystemExit(f"{len(missing)} answer words are not in {src}: {missing[:5]}")
    below = sorted(ans - over)
    custom = sorted(over | ans)
    with open(custom_out, "w", encoding="utf-8") as fh:
        for word in custom:
            fh.write(f"{word}\n")
    print(f"\nwrote {len(custom):,} words to {custom_out}  (cutoff zipf >= {cutoff})")
    print(f"  guess words at or above the cutoff: {len(over):,}")
    print(f"  answer words below it, kept anyway: {len(below):,}")


if __name__ == "__main__":
    main(sys.argv[1:])
