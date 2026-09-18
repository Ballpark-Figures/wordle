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

**`--from-ranked` BUILDS THE SAME KIND OF LIST AT OTHER CUTOFFS, from the
COMMITTED ranking** (the user's, 2026-09-18).  `custom.txt` is one member of a
family -- answers plus every guess word at or above a bar -- and the bar is the
only thing that varies, so a different candidate set is a different cutoff and
nothing else.  Under that flag nothing is re-ranked and `guess_by_freq.txt` is
NOT rewritten: the frequencies are read back from the committed artifact, so the
new lists cannot disagree with `custom.txt` about any word's zipf, and `wordfreq`
is not needed at all.  `--cutoff` repeats, one list per value.

  THE NAME ENCODES THE BAR IN HUNDREDTHS -- `zipf025` is 0.25 and `zipf250` is
  2.50 -- because `custom25` would be unreadable for both 0.25 and 2.5.  It is
  derived by `list_name`, the one place that rule lives, so a filename cannot
  drift from the cutoff that made it.  **`zipf250.txt` is `custom.txt`**, byte
  for byte, which is the free check that the family is built the same way.

Run:  .venv/bin/python math/build_freq_wordlist.py
      .venv/bin/python math/build_freq_wordlist.py --cutoff 3.0
      .venv/bin/python math/build_freq_wordlist.py --from-ranked \
          --cutoff 0.25 --cutoff 0.5 --cutoff 0.75
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


def list_name(cutoff: float) -> str:
    """The committed filename for the candidate set at this cutoff.

    Hundredths, zero-padded to three digits, so `zipf025` and `zipf250` sort and
    read unambiguously -- `custom25` would mean either 0.25 or 2.5.  This is the
    ONE place the rule lives; a caller spelling it out in shell would be the same
    rule written twice.
    """
    hundredths = int(round(cutoff * 100))
    if abs(hundredths - cutoff * 100) > 1e-9:
        raise SystemExit("cutoff %r is finer than a hundredth, which the name "
                         "cannot express" % cutoff)
    return "zipf%03d.txt" % hundredths


def rank(path: str) -> list[tuple[str, float]]:
    """Every word in `path` with its zipf, most common first (ties alphabetical)."""
    from wordfreq import zipf_frequency  # heavy + a data download; only rank() needs it

    rows = [(w, zipf_frequency(w, "en", wordlist=WORDLIST)) for w in read_words(path)]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows


def write_list(rows, answers, cutoff, out) -> int:
    """One candidate set: every word at or above `cutoff`, PLUS every answer.

    The answer floor is not a nicety -- the game can pick a word the bar would
    drop, and a pool missing an answer is a pool the follow-up can never win
    from.  Returns the word count.
    """
    over = {w for w, z in rows if z >= cutoff}
    ans = set(read_words(answers))
    missing = sorted(ans - {w for w, _ in rows})
    if missing:
        raise SystemExit(f"{len(missing)} answer words are missing from the "
                         f"ranking: {missing[:5]}")
    below = sorted(ans - over)
    words = sorted(over | ans)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for word in words:
            fh.write(f"{word}\n")
    print(f"wrote {len(words):,} words to {out}  (cutoff zipf >= {cutoff})")
    print(f"  guess words at or above the cutoff: {len(over):,}")
    print(f"  answer words below it, kept anyway: {len(below):,}")
    return len(words)


def main(argv: list[str]) -> None:
    src, answers = DEFAULT_IN, DEFAULT_ANSWERS
    ranked_out, custom_out = DEFAULT_RANKED, DEFAULT_CUSTOM
    cutoffs: list[float] = []
    from_ranked = False
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
            cutoffs.append(float(next(it)))
        elif a == "--from-ranked":
            from_ranked = True
        else:
            raise SystemExit(f"unknown arg {a!r} (--in/--answers/--out/"
                             f"--custom-out/--cutoff/--from-ranked)")

    if not from_ranked:
        # UNCHANGED: re-rank from wordfreq, rewrite the committed ranking, and
        # write ONE custom list.  Several cutoffs would have nowhere to go here,
        # since `--custom-out` names a single file.
        if len(cutoffs) > 1:
            raise SystemExit("several --cutoff values need --from-ranked, which "
                             "derives a filename per cutoff; --custom-out names "
                             "only one file")
        cutoff = cutoffs[0] if cutoffs else CUTOFF
        rows = rank(src)
        os.makedirs(os.path.dirname(ranked_out), exist_ok=True)
        with open(ranked_out, "w", encoding="utf-8") as fh:
            for word, z in rows:
                fh.write(f"{word}\t{z:.2f}\n")
        print(f"wrote {len(rows):,} words to {ranked_out}  (source {src}, wordfreq {WORDLIST!r})")
        for cut in (5.0, 4.0, 3.5, 3.0, 2.5, 2.0, 1.0):
            print(f"  zipf >= {cut}: {sum(1 for _, z in rows if z >= cut):,} words")
        print(f"  zipf == 0.00 (not in wordfreq): {sum(1 for _, z in rows if z == 0.0):,} words")
        print()
        write_list(rows, answers, cutoff, custom_out)
        return

    # THE FAMILY: read the COMMITTED ranking and write one list per cutoff.
    # Nothing is re-ranked, so these cannot disagree with custom.txt about a
    # word's zipf, and `wordfreq` is never imported.
    if not cutoffs:
        raise SystemExit("--from-ranked needs at least one --cutoff")
    rows = sorted(load_zipf(ranked_out).items(), key=lambda r: (-r[1], r[0]))
    print(f"read {len(rows):,} words with their zipf from {ranked_out}")
    for cutoff in cutoffs:
        out = os.path.join(_WORDS, list_name(cutoff))
        print()
        write_list(rows, answers, cutoff, out)


if __name__ == "__main__":
    main(sys.argv[1:])
