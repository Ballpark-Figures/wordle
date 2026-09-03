"""Build Wordle-style guess/answer lists for other languages, at a cutoff
CALIBRATED against English so the lists are comparable.

The rule, stated once:

  * Rank every word of the target length in `wordfreq`'s list for the language,
    most common first.
  * The ANSWER cutoff is the zipf of the Nth-ranked ENGLISH word of that length,
    where N is the size of the English ANSWER list (2315 at length 5). The GUESS
    cutoff is the same construction against the English GUESS list (12972).
  * Every language then gets those two zipf values applied to its own ranking.

So the cutoffs are DERIVED from the English lists at run time, not typed in --
the point is "the frequency bar English's own lists sit at", and a zipf means
the same thing in every language (log10 occurrences per billion words). It is
the same package and the same `large` wordlist `build_freq_wordlist.py` uses,
so a zipf here also means what it means there and in the hangman video.

WHAT THIS IS NOT. These are NOT the word lists any real foreign Wordle clone
plays with -- nobody's answer list is "wordfreq above a cutoff", and every
clone curates its own. They are a CONSISTENT rule applied across languages,
which is the only thing that makes a cross-language number comparable at all.
Say that whenever a number from them is quoted.

ACCENTS ARE A MODELLING CHOICE and they change the game, so they are a flag:

  --accents ascii  (default)  collapse diacritics to their base letter and drop
                              whatever is still non-ASCII, giving a 26-letter
                              board. This is what most real clones do.
  --accents keep              keep the language's own alphabet. Bigger alphabet,
                              truer to the language.

Either way the resulting alphabet and its size are recorded in the .meta -- a
solver reading these needs to know, and it is not 26 by default in `keep` mode.

Collapsing can merge two words into one string (French cote/cote); the merged
entry keeps the HIGHER zipf, and the count of merges is reported and recorded.

Run:  .venv/bin/python math/build_lang_wordlists.py                  # every language
      .venv/bin/python math/build_lang_wordlists.py --langs fr,es,de
      .venv/bin/python math/build_lang_wordlists.py --length 6
      .venv/bin/python math/build_lang_wordlists.py --accents keep
      .venv/bin/python math/build_lang_wordlists.py --dry-run        # counts only

Output (COMMITTED, like every other word list here):
  math/data/shared/words/lang/<code>/len<L>/{guess,mystery}.txt  + a .meta
"""

from __future__ import annotations

import os
import sys
import unicodedata

from wordfreq import available_languages, iter_wordlist, zipf_frequency

# wordfreq's `large` lists cover words down to ~1 per 100 million; the `small`
# ones stop at 1 per million (zipf 3.0), which is ABOVE the guess cutoff -- so a
# small-list language would return its whole list rather than a cut of it. Hence
# `large` only, and a refusal rather than a silently truncated list.
WORDLIST = "large"

# The Latin-alphabet subset of the `large` languages. wordfreq exposes no script
# metadata, so this is a hand-named list; ar/bn/he/ja/mk/ru/uk/zh are the ones it
# leaves out. Nothing here decides an ANSWER -- it selects which languages run.
LATIN = ["ca", "cs", "de", "en", "es", "fi", "fr", "it", "nb", "nl", "pl", "pt", "sv"]

# Latin letters that carry no combining form, so NFD leaves them alone. Only 1:1
# maps are listed: ss/ae/oe/th would change the word's LENGTH, so words holding
# them are dropped in `ascii` mode instead (and counted).
FOLD = {"ø": "o", "ł": "l", "đ": "d", "ð": "d", "ı": "i", "ħ": "h", "ŧ": "t"}

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORDS = os.path.join(_HERE, "data", "shared", "words")


def read_words(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def english_reference(length: int) -> tuple[str, str]:
    """The English (guess, mystery) lists that anchor the cutoffs at `length`.

    Length 5 is Wordle's own 12972/2315; every other length is hello wordl's
    pair, which is the only source curating both at every length. Both are what
    the solvers already read, so the anchor is the video's own reference point.
    """
    if length == 5:
        return os.path.join(_WORDS, "guess.txt"), os.path.join(_WORDS, "mystery.txt")
    d = os.path.join(_WORDS, "hello", f"len{length}")
    return os.path.join(d, "guess.txt"), os.path.join(d, "mystery.txt")


def ranked(lang: str, length: int) -> list[tuple[str, float]]:
    """Every `length`-letter word wordfreq has for `lang`, most common first."""
    rows = [
        (w, zipf_frequency(w, lang, wordlist=WORDLIST))
        for w in iter_wordlist(lang, WORDLIST)
        if len(w) == length and w.isalpha() and w == w.lower()
    ]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows


def nth_zipf(rows: list[tuple[str, float]], n: int) -> float:
    """The zipf of the nth-ranked word -- the cutoff a list of that size sits at."""
    if n > len(rows):
        raise SystemExit(
            f"anchor asks for {n:,} words but the reference list has only {len(rows):,}"
        )
    return rows[n - 1][1]


def fold(word: str) -> str | None:
    """`word` with diacritics collapsed, or None if it cannot reach plain ASCII."""
    w = "".join(FOLD.get(c, c) for c in word)
    w = "".join(c for c in unicodedata.normalize("NFD", w)
                if unicodedata.category(c) != "Mn")
    return w if w.isascii() and w.isalpha() else None


def build(lang: str, length: int, accents: str,
          ans_cut: float, guess_cut: float) -> tuple[list[str], list[str], dict]:
    rows = ranked(lang, length)
    best: dict[str, float] = {}
    dropped = merged = 0
    for word, z in rows:
        if accents == "ascii":
            w = fold(word)
            if w is None or len(w) != length:
                dropped += 1
                continue
        else:
            w = word
        if w in best:
            merged += 1
            best[w] = max(best[w], z)
        else:
            best[w] = z
    guesses = sorted(w for w, z in best.items() if z >= guess_cut)
    answers = sorted(w for w, z in best.items() if z >= ans_cut)
    alphabet = sorted({c for w in guesses for c in w})
    stats = {
        "wordfreq_words": len(rows),
        "dropped_non_ascii": dropped,
        "merged_by_folding": merged,
        "alphabet": "".join(alphabet),
        "alphabet_size": len(alphabet),
    }
    return guesses, answers, stats


def write_lists(lang, length, accents, guesses, answers, stats,
                ans_cut, guess_cut, anchors, out_root) -> str:
    d = os.path.join(out_root, lang, f"len{length}")
    os.makedirs(d, exist_ok=True)
    for name, words in (("guess", guesses), ("mystery", answers)):
        with open(os.path.join(d, f"{name}.txt"), "w", encoding="utf-8") as fh:
            for w in words:
                fh.write(f"{w}\n")
    meta = os.path.join(d, "wordlists.meta")
    with open(meta, "w", encoding="utf-8") as fh:
        fh.write(f"lang={lang}\n")
        fh.write(f"length={length}\n")
        fh.write("source=wordfreq\n")
        fh.write(f"wordlist={WORDLIST}\n")
        fh.write(f"accents={accents}\n")
        fh.write("cutoff_rule=zipf-of-the-nth-english-word-of-this-length\n")
        fh.write(f"anchor_guesses={anchors[0]}\n")
        fh.write(f"anchor_answers={anchors[1]}\n")
        fh.write(f"guess_cutoff={guess_cut:.2f}\n")
        fh.write(f"answer_cutoff={ans_cut:.2f}\n")
        fh.write(f"guesses={len(guesses)}\n")
        fh.write(f"answers={len(answers)}\n")
        for k, v in stats.items():
            fh.write(f"{k}={v}\n")
    return d


def main(argv: list[str]) -> None:
    langs, length, accents = list(LATIN), 5, "ascii"
    out_root = os.path.join(_WORDS, "lang")
    ans_cut = guess_cut = None
    dry = False
    it = iter(argv)
    for a in it:
        if a == "--langs":
            langs = [x.strip() for x in next(it).split(",") if x.strip()]
        elif a == "--length":
            length = int(next(it))
        elif a == "--accents":
            accents = next(it)
            if accents not in ("ascii", "keep"):
                raise SystemExit("--accents takes 'ascii' or 'keep'")
        elif a == "--answer-cutoff":
            ans_cut = float(next(it))
        elif a == "--guess-cutoff":
            guess_cut = float(next(it))
        elif a == "--out":
            out_root = next(it)
        elif a == "--dry-run":
            dry = True
        else:
            raise SystemExit(
                f"unknown arg {a!r} (--langs/--length/--accents/--answer-cutoff/"
                "--guess-cutoff/--out/--dry-run)"
            )

    have = set(available_languages(WORDLIST))
    missing = [lg for lg in langs if lg not in have]
    if missing:
        raise SystemExit(
            f"no {WORDLIST!r} wordfreq list for {missing}; its 'small' lists stop at "
            "zipf 3.0, above the guess cutoff, so they would give an uncut list"
        )

    guess_ref, ans_ref = english_reference(length)
    anchors = (len(read_words(guess_ref)), len(read_words(ans_ref)))
    en = ranked("en", length)
    if guess_cut is None:
        guess_cut = nth_zipf(en, anchors[0])
    if ans_cut is None:
        ans_cut = nth_zipf(en, anchors[1])
    print(f"length {length}, accents {accents!r}, wordfreq {WORDLIST!r}")
    print(f"  anchored on {guess_ref} ({anchors[0]:,}) -> guess cutoff zipf >= {guess_cut:.2f}")
    print(f"  anchored on {ans_ref} ({anchors[1]:,}) -> answer cutoff zipf >= {ans_cut:.2f}")
    print()
    print(f"{'lang':<6}{'guesses':>9}{'answers':>9}{'alpha':>7}{'dropped':>9}{'merged':>8}")

    for lg in langs:
        guesses, answers, stats = build(lg, length, accents, ans_cut, guess_cut)
        print(f"{lg:<6}{len(guesses):>9,}{len(answers):>9,}"
              f"{stats['alphabet_size']:>7}{stats['dropped_non_ascii']:>9,}"
              f"{stats['merged_by_folding']:>8,}")
        if dry:
            continue
        assert set(answers) <= set(guesses), lg
        assert all(len(w) == length for w in guesses), lg
        write_lists(lg, length, accents, guesses, answers, stats,
                    ans_cut, guess_cut, anchors, out_root)

    if dry:
        print("\n--dry-run: nothing written")
    else:
        print(f"\nwrote {len(langs)} languages under {out_root}")


if __name__ == "__main__":
    main(sys.argv[1:])
