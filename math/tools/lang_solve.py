"""Run the top-K Wordle beam over EVERY other-language word list, one K.

WHAT THIS MEASURES, precisely. For each language, the EXPECTED NUMBER OF GUESSES
to finish, over that language's answer list taken UNIFORMLY, under the top-K
guesser in `math/topk.py` -- which is the source of truth for the strategy and
should be read before quoting any number. Every legal guess is playable at every
node; guesses are ranked by the expected number of candidates still alive
(winning bin excluded), ties on the lowest guess index; the search recurses into
the K best and keeps whichever actually minimises expected guesses.

--answers-only RESTRICTS THE GUESS SET to that language's answer (mystery) list,
so every guess -- opener and follow-up -- is itself a possible answer. This is
the language analogue of the English answers-only sweep (run-ans-sweep.sh), and
everything else is unchanged: same beam, same ranking, same length-5-only rule,
same expected-guesses-outright objective with NO depth cap. It is a DIFFERENT
strategy from the full-guess-list run and lands in its own files, so the two are
never mixed. (No feasibility caveat transfers from the English answers-only
sweep: that one is capped at 6 guesses and the cap binds; this one has no cap.)

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


def solve_pair(label: str, answers: list[str], guesses: list[str], k: int,
               meta: dict | None = None) -> dict:
    """One (answers, guesses) pair through the top-K guesser, weights UNIFORM.

    THE ONE PLACE the objective is evaluated. `solve_language` reads a language
    directory and calls this; `--answers/--guesses` names a pair directly and
    calls the same. Two entry points, one computation -- so an explicitly named
    list cannot drift from a discovered one.

    Uniform weighting IS `topk.py`'s default (`_coerce(None)` returns all-ones),
    so this is the weighted evaluation with every weight 1, not a separate mode.
    """
    meta = meta or {}
    alphabet = sorted({c for w in guesses for c in w})

    t0 = time.time()
    P = build_patterns(guesses, answers, alphabet)
    game = TopKGame(answers=answers, guesses=guesses, k=k, patterns=P)
    total = game.total_cost()
    opener = game.trace(answers[0])[0][0]
    return {
        "lang": label,
        "guesses": len(guesses),
        "answers": len(answers),
        "alphabet_size": len(alphabet),
        "accents": meta.get("accents", ""),
        "opener": opener,
        "total_guesses": f"{total:.0f}",
        "expected_guesses": f"{total / len(answers):.4f}",
        "seconds": f"{time.time() - t0:.1f}",
    }


def solve_language(lg: str, root: str, length: int, k: int,
                   answers_only: bool = False) -> dict:
    d = os.path.join(root, lg, f"len{length}")
    answers = read_words(os.path.join(d, "mystery.txt"))
    # answers_only: guesses ARE the answer list, the language analogue of
    # --guess-list mystery.txt in the English answers-only sweep. Every answer is
    # trivially a legal guess, so TopKGame's playability guard is satisfied, and
    # the alphabet covers every letter in play since guesses == answers.
    guesses = answers if answers_only else read_words(os.path.join(d, "guess.txt"))
    return solve_pair(lg, answers, guesses, k,
                      read_meta(os.path.join(d, "wordlists.meta")))


COLUMNS = ["lang", "guesses", "answers", "alphabet_size", "accents",
           "opener", "total_guesses", "expected_guesses", "seconds"]


def print_header(k: int, length: int, answers_only: bool) -> None:
    """The ONE screen header, shared by the language sweep and a named pair.

    Both are the same measurement, so they get the same header and the same
    columns; only the row label differs. Printing a bespoke line for one of them
    would make two identical results look like two different quantities.
    """
    guess_set = "answers only" if answers_only else "full guess list"
    print(f"top-{k} beam, length {length}, {guess_set}, "
          "average guesses OUTRIGHT (no depth cap)")
    print(f"{'lang':<6}{'opener':>10}{'avg guesses':>14}"
          f"{'answers':>9}{'guesses':>9}{'secs':>8}")


def show(row: dict, note: str = "") -> None:
    """One result row, in the shared column layout."""
    print(f"{row['lang']:<6}{row['opener']:>10}{row['expected_guesses']:>14}"
          f"{row['answers']:>9}{row['guesses']:>9}{row['seconds']:>8}{note}",
          flush=True)


def write_meta(path: str, k: int, length: int, langs: list[str],
               answers_only: bool = False, lists: tuple | None = None) -> None:
    """`lists` = (answers_path, guesses_path) for an explicitly named pair.

    A named pair is NOT a language result, and the meta must not claim it is --
    it did not come from build_lang_wordlists.py and there is no language to
    compare it across. The rest of the file is identical, because the objective
    and the strategy are identical.
    """
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("kind=%s\n" % ("topk-solve" if lists else "lang-topk-solve"))
        fh.write(f"k={k}\n")
        fh.write(f"length={length}\n")
        if lists:
            fh.write(f"label={langs[0]}\n")
            fh.write(f"answers_list={os.path.relpath(lists[0])}\n")
            fh.write(f"guesses_list={os.path.relpath(lists[1]) if lists[1] else 'same-as-answers'}\n")
        else:
            fh.write(f"languages={len(langs)}\n")
        fh.write("objective=expected-guesses-outright\n")
        fh.write("depth_cap=none\n")
        fh.write("strategy=topk-beam-ranked-by-expected-candidates-alive\n")
        fh.write("root_restricted_by_k=1\n")
        fh.write("optimum=0\n")
        fh.write("weights=uniform\n")
        # answers_only: the guess set is the answer (mystery) list, so a guess is
        # always a possible answer. A DIFFERENT strategy from the full run.
        fh.write(f"answers_only={1 if answers_only else 0}\n")
        fh.write(f"guess_set={'answers' if answers_only else 'full'}\n")
        if not lists:
            fh.write("wordlists=build_lang_wordlists.py\n")
        fh.write("comparable_with_optturns=0\n")


def main(argv: list[str]) -> None:
    k, length, root, out = 1, ONLY_LENGTH, LANG_WORDS, None
    langs = None
    answers_only = False
    ans_path = gue_path = label = None
    it = iter(argv)
    for a in it:
        if a in ("-k", "--topk"):
            k = int(next(it))
        elif a == "--answers":
            ans_path = next(it)
        elif a == "--guesses":
            gue_path = next(it)
        elif a == "--label":
            label = next(it)
        elif a == "--length":
            length = int(next(it))
        elif a == "--langs":
            langs = [x.strip() for x in next(it).split(",") if x.strip()]
        elif a == "--words":
            root = next(it)
        elif a == "--out":
            out = next(it)
        elif a == "--answers-only":
            answers_only = True
        else:
            raise SystemExit(
                f"unknown arg {a!r} (-k/--length/--langs/--words/--out/"
                "--answers-only/--answers/--guesses/--label)")

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

    # ---- an explicitly named pair, instead of discovering language dirs ----
    # The English baseline goes through HERE rather than through a second tool:
    # same driver, same objective, same columns, same CSV.
    if ans_path is not None:
        if langs is not None:
            raise SystemExit("--answers names ONE list pair; --langs discovers "
                             "several. Pick one.")
        if gue_path is None and not answers_only:
            raise SystemExit(
                "--guesses PATH is required with --answers (or --answers-only to "
                "make the answer list its own guess set).\n"
                "The guess set is part of the question -- a 12972-word guesser and "
                "a 4282-word one are different strategies, so it is never defaulted.")
        answers = read_words(ans_path)
        guesses = answers if answers_only else read_words(gue_path)
        if label is None:
            label = os.path.basename(ans_path)
            if label.endswith(".txt"):
                label = label[:-4]
        print_header(k, length, answers_only)
        row = solve_pair(label, answers, guesses, k)
        show(row)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(",".join(COLUMNS) + "\n")
            fh.write(",".join(str(row[c]) for c in COLUMNS) + "\n")
        write_meta(out + ".meta", k, length, [label], answers_only,
                   lists=(ans_path, None if answers_only else gue_path))
        print(f"\nwrote {out}")
        return

    if langs is None:
        langs = discover(root, length)
    if not langs:
        raise SystemExit(f"no language lists found under {root}")

    done = {}
    if os.path.exists(out):                       # resume: skip finished languages
        rows = read_words(out)
        for line in rows[1:]:
            done[line.split(",")[0]] = dict(zip(COLUMNS, line.split(",")))
        if done:
            print(f"resuming {out}: {len(done)} language(s) already done")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if not os.path.exists(out):
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(",".join(COLUMNS) + "\n")

    print_header(k, length, answers_only)
    for lg in langs:
        # A resumed language still prints, so the table on screen is the whole
        # run rather than only the part this invocation happened to compute.
        if lg in done:
            show(done[lg], "  (done earlier)")
            continue
        row = solve_language(lg, root, length, k, answers_only)
        show(row)
        with open(out, "a", encoding="utf-8") as fh:   # flush per language
            fh.write(",".join(str(row[c]) for c in COLUMNS) + "\n")

    write_meta(out + ".meta", k, length, langs, answers_only)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
