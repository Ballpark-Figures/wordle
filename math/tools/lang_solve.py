"""Run the top-K Wordle beam over EVERY other-language word list, one K.

WHAT THIS MEASURES, precisely. For each language, the EXPECTED NUMBER OF GUESSES
to finish, over that language's answer list taken UNIFORMLY, under the top-K
guesser in `math/topk.py` -- which is the source of truth for the strategy and
should be read before quoting any number. Every legal guess is playable at every
node; guesses are ranked by the expected number of candidates still alive
(winning bin excluded), ties on the lowest guess index; the search recurses into
the K best and keeps whichever actually minimises expected guesses.

THERE IS NO DEPTH CAP. This is expected guesses OUTRIGHT -- the same footing as
the multiwordle, foximax and adversarial numbers, and NOT the footing of any
optturns/hardturns/ansall total, every one of which is an optimum SUBJECT TO a
6-guess guarantee. Never put the two in one table.

IT IS NOT AN OPTIMUM. `-k K` examines K guesses at every node, THE ROOT
INCLUDED, so the opener reported is the best of the K examined, not the best of
the language's whole guess list. Each K is a different strategy and gets its own
file.

THE LISTS ARE NOT ANY REAL CLONE'S. They are `build_lang_wordlists.py`'s output:
wordfreq cut at a zipf calibrated on the English lists. That consistency is the
only reason a cross-language comparison means anything, and it is also why these
numbers describe OUR lists rather than fr/de/es Wordle as anyone plays it. Say
so whenever one is quoted.

LENGTH 5 ONLY, and the refusal is real rather than laziness: `topk.py`'s numba
kernels close over the module-level `ALL_GREEN` (242), which numba bakes in as a
compile-time constant. At another length the winning bin would be a different
code, so the kernel would exclude the wrong one and return a wrong number
silently. Parameterising it is a change to the adversarial video's hot path and
has not been made.

Run (prefer the wrapper, which sets --out and tees a log):
    bash solver/run-lang-solve.sh -k 1
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from topk import TopKGame                                  # noqa: E402
from wordle import pattern_dtype, pattern_row, to_codes    # noqa: E402


_MATH = os.path.dirname(_HERE)
LANG_WORDS = os.path.join(_MATH, "data", "shared", "words", "lang", "ascii")

# See the module docstring -- this is topk.py's baked-in ALL_GREEN, not a choice.
ONLY_LENGTH = 5


def read_words(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def read_meta(path: str) -> dict:
    out = {}
    if os.path.exists(path):
        for line in read_words(path):
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
    return out


def discover(root: str, length: int) -> list[str]:
    """Language codes that have a list pair at `length`, alphabetical."""
    if not os.path.isdir(root):
        raise SystemExit(
            f"no language lists at {root}\n"
            "build them first:  .venv/bin/python math/build_lang_wordlists.py")
    out = []
    for lg in sorted(os.listdir(root)):
        d = os.path.join(root, lg, f"len{length}")
        if all(os.path.exists(os.path.join(d, f)) for f in ("guess.txt", "mystery.txt")):
            out.append(lg)
    return out


def build_patterns(guesses: list[str], answers: list[str],
                   alphabet: list[str]) -> np.ndarray:
    """[NG, NA] feedback of every guess against every answer, for THIS language.

    `wordle.pattern_row` is the same vectorised primitive `build_patterns.py`
    uses for English; the alphabet argument is what lets it take a list whose
    letters are not a..z (an --accents keep list). Nothing is cached: one
    language's matrix is ~30 MB and takes a few seconds, against a per-language
    file nobody else would read.
    """
    ans_codes = to_codes(answers, alphabet=alphabet)
    word_len = ans_codes.shape[1]
    P = np.empty((len(guesses), len(answers)), dtype=pattern_dtype(word_len))
    for i, g in enumerate(guesses):
        P[i] = pattern_row(g, ans_codes, alphabet=alphabet)
    return P


def solve_language(lg: str, root: str, length: int, k: int) -> dict:
    d = os.path.join(root, lg, f"len{length}")
    guesses = read_words(os.path.join(d, "guess.txt"))
    answers = read_words(os.path.join(d, "mystery.txt"))
    meta = read_meta(os.path.join(d, "wordlists.meta"))
    alphabet = sorted({c for w in guesses for c in w})

    t0 = time.time()
    P = build_patterns(guesses, answers, alphabet)
    game = TopKGame(answers=answers, guesses=guesses, k=k, patterns=P)
    total = game.total_cost()
    opener = game.trace(answers[0])[0][0]
    return {
        "lang": lg,
        "guesses": len(guesses),
        "answers": len(answers),
        "alphabet_size": len(alphabet),
        "accents": meta.get("accents", ""),
        "opener": opener,
        "total_guesses": f"{total:.0f}",
        "expected_guesses": f"{total / len(answers):.4f}",
        "seconds": f"{time.time() - t0:.1f}",
    }


COLUMNS = ["lang", "guesses", "answers", "alphabet_size", "accents",
           "opener", "total_guesses", "expected_guesses", "seconds"]


def write_meta(path: str, k: int, length: int, langs: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("kind=lang-topk-solve\n")
        fh.write(f"k={k}\n")
        fh.write(f"length={length}\n")
        fh.write(f"languages={len(langs)}\n")
        fh.write("objective=expected-guesses-outright\n")
        fh.write("depth_cap=none\n")
        fh.write("strategy=topk-beam-ranked-by-expected-candidates-alive\n")
        fh.write("root_restricted_by_k=1\n")
        fh.write("optimum=0\n")
        fh.write("weights=uniform\n")
        fh.write("wordlists=build_lang_wordlists.py\n")
        fh.write("comparable_with_optturns=0\n")


def main(argv: list[str]) -> None:
    k, length, root, out = 1, ONLY_LENGTH, LANG_WORDS, None
    langs = None
    it = iter(argv)
    for a in it:
        if a in ("-k", "--topk"):
            k = int(next(it))
        elif a == "--length":
            length = int(next(it))
        elif a == "--langs":
            langs = [x.strip() for x in next(it).split(",") if x.strip()]
        elif a == "--words":
            root = next(it)
        elif a == "--out":
            out = next(it)
        else:
            raise SystemExit(f"unknown arg {a!r} (-k/--length/--langs/--words/--out)")

    if out is None:
        raise SystemExit(
            "refusing to run without --out: the result would print and vanish.\n"
            "use the wrapper:  bash solver/run-lang-solve.sh -k 1")
    if k < 1:
        raise SystemExit(f"k must be at least 1, got {k}")
    if length != ONLY_LENGTH:
        raise SystemExit(
            f"--length {length}: this driver is {ONLY_LENGTH}-letter only. topk.py's "
            "numba kernels bake in ALL_GREEN=242, so another length would exclude "
            "the wrong winning bin and return a wrong number silently.")

    if langs is None:
        langs = discover(root, length)
    if not langs:
        raise SystemExit(f"no language lists found under {root}")

    done = set()
    if os.path.exists(out):                       # resume: skip finished languages
        rows = read_words(out)
        done = {line.split(",")[0] for line in rows[1:]}
        if done:
            print(f"resuming {out}: {len(done)} language(s) already done")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if not os.path.exists(out):
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(",".join(COLUMNS) + "\n")

    print(f"top-{k} beam, length {length}, expected guesses OUTRIGHT (no depth cap)")
    print(f"{'lang':<6}{'guesses':>9}{'answers':>9}{'alpha':>7}"
          f"{'opener':>12}{'expected':>10}{'secs':>8}")
    for lg in langs:
        if lg in done:
            continue
        row = solve_language(lg, root, length, k)
        print(f"{row['lang']:<6}{row['guesses']:>9}{row['answers']:>9}"
              f"{row['alphabet_size']:>7}{row['opener']:>12}"
              f"{row['expected_guesses']:>10}{row['seconds']:>8}")
        with open(out, "a", encoding="utf-8") as fh:   # flush per language
            fh.write(",".join(str(row[c]) for c in COLUMNS) + "\n")

    write_meta(out + ".meta", k, length, langs)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
