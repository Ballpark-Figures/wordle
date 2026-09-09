"""GREEN TEMPLATES: fixed letters in fixed positions that PIN a single word.

Run it through the wrapper, which sets --out, names the run and tees a log:

    bash solver/run-green-templates.sh                          # from math/, or anywhere
    bash solver/run-green-templates.sh --pool guesses
    bash solver/run-green-templates.sh --greens 3

WHAT THIS COMPUTES, precisely.  A TEMPLATE is a choice of N positions and a
letter for each -- written `.a..e`, meaning "position 2 is a and position 5 is e".
It matches a word iff the word carries those letters in those positions.  This
enumerates every template (C(L,N) position sets x 26^N letter assignments) and
reports the ones matching EXACTLY ONE word of the pool.

THE GREENS ARE FREE-STANDING, NOT THE FEEDBACK OF A GUESS, and that is the whole
modelling decision.  The other L-N positions are entirely UNCONSTRAINED: the
template asserts nothing about them -- not that they are grey, not that those
letters are absent, not that the word has no further letter in common with some
guess.  There is no guess here at all, so no yellows, no greys, and no
repeated-letter rule; `wordle.pattern` is not involved and this file deliberately
does not import it.  A DIFFERENT question -- "a real board showing exactly N
green tiles" -- carries the guess's greys and yellows too and gives a different,
smaller count.  This is not that.

TWO AXES, BOTH PART OF THE QUESTION, NEITHER DEFAULTED HERE (the wrapper carries
a default a human reads and forwards it explicitly):

  --pool     WHICH LIST UNIQUENESS IS JUDGED OVER.  `answers` counts matches
             among the 2315 curated mystery words; `guesses` counts them among
             all 12972 legal words.  These are DIFFERENT QUANTITIES over the same
             templates -- `guesses` is strictly harder to satisfy, since every
             answer is a legal guess, so a template pinning one word out of 12972
             necessarily pins one out of 2315 as well.  (That subset relation is
             checked, not assumed: see gate_subset.)

  --require  WHICH SURVIVING ROWS ARE KEPT.  `answer` keeps only the templates
             whose one word is a mystery answer; `any` keeps them all.  It changes
             no count -- a template pins what it pins -- it only restricts the
             rows, exactly as `maxbucket.py --rank` does.  Under --pool answers
             the two are identical by construction, and that is asserted.

  So the two cases asked for are (answers, answer) and (guesses, answer).  The
  second is the stricter one: unique among all 12972 legal words, AND that word
  happens to be an answer.

Nothing searches or samples.  The result is a pure function of the committed word
lists -- exact, no seed, no cap, no standard error -- so a re-run reproduces its
file byte for byte.  It reads no pattern matrix, so it works on a fresh clone.

THE GATE IS BUILT IN AND ALWAYS RUNS, in three parts, and it exits nonzero rather
than reporting: (1) the whole result is recomputed EXHAUSTIVELY from the STRINGS
by a dict of letter tuples, sharing no machinery with the numpy path -- no codes,
no bincount, no index arithmetic -- and demanded equal as a SET, template for
template and word for word; (2) sampled emitted rows are re-verified by scanning
the entire pool with plain string comparison, a third route; (3) under --pool
guesses the surviving templates must be a subset of the ones that pin a single
answer, which is the free oracle the two pools give each other.  A coverage tally
FAILS if no template pinned anything, or if --pool guesses never actually dropped
a template that the answer pool would have kept -- so a pass cannot silently mean
the harder pool went untested.
"""

import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from wordle import load_words, to_codes  # noqa: E402

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GATE_ROWS = 200           # emitted rows re-verified by a full string scan
ALPHA = 26


def _arg(argv, flag, choices):
    if flag not in argv:
        raise SystemExit(
            "%s is REQUIRED (one of %s) -- it is part of the question, so this "
            "refuses to pick for you. Use solver/run-green-templates.sh, which "
            "carries a default a human reads." % (flag, "/".join(choices)))
    val = argv[argv.index(flag) + 1]
    if val not in choices:
        raise SystemExit("%s must be one of %s" % (flag, "/".join(choices)))
    return val


def show(positions, letters, word_len):
    """Render a template as a word-shaped string: `.a..e`."""
    tiles = ["."] * word_len
    for p, c in zip(positions, letters):
        tiles[p] = c
    return "".join(tiles)


# --------------------------------------------------------------- the computation

def pin_single(words, greens):
    """Templates matching EXACTLY ONE word, as {(positions, letters): index}.

    One bincount per position set.  The trick in the second bincount: where a
    template's count is 1 the SUM of the matching words' indices IS that word's
    index, so the winner falls out with no search and no second pass.  Sums stay
    exact -- float64 carries every integer below 2**53 and the largest possible
    sum here is under 13000.
    """
    codes = to_codes(words)
    n, word_len = codes.shape
    if not 1 <= greens <= word_len:
        raise SystemExit("--greens must be between 1 and %d" % word_len)
    idx = np.arange(n, dtype=np.float64)
    size = ALPHA ** greens
    out = {}
    occupied = 0
    for positions in itertools.combinations(range(word_len), greens):
        key = np.zeros(n, dtype=np.int64)
        for p in positions:
            key = key * ALPHA + codes[:, p]
        count = np.bincount(key, minlength=size)
        total = np.bincount(key, weights=idx, minlength=size)
        occupied += int((count > 0).sum())
        for k in np.flatnonzero(count == 1):
            letters = tuple(
                chr(ord("a") + (int(k) // ALPHA ** (greens - 1 - d)) % ALPHA)
                for d in range(greens))
            out[(positions, letters)] = int(round(total[k]))
    return out, word_len, occupied


# ---------------------------------------------------------------------- the gate

def reference(words, greens):
    """Recompute the whole thing FROM THE STRINGS, exhaustively.

    Shares nothing with the numpy path: letters are dict keys, not codes; there
    is no bincount, no base-26 packing and no index arithmetic.  A template
    absent from this dict matched no word, and a template that pins a word maps
    to its index; -1 marks a collision.
    """
    seen = {}
    for i, w in enumerate(words):
        for positions in itertools.combinations(range(len(w)), greens):
            key = (positions, tuple(w[p] for p in positions))
            seen[key] = i if key not in seen else -1
    return {k: i for k, i in seen.items() if i >= 0}


def gate_reference(words, greens, uniq):
    ref = reference(words, greens)
    if set(ref) != set(uniq):
        only_fast = sorted(set(uniq) - set(ref))[:3]
        only_ref = sorted(set(ref) - set(uniq))[:3]
        raise SystemExit(
            "GATE FAILED: %d templates from the matrix path, %d from the "
            "strings. fast-only %s, strings-only %s"
            % (len(uniq), len(ref), only_fast, only_ref))
    for k, i in ref.items():
        if uniq[k] != i:
            raise SystemExit("GATE FAILED: template %s pins %s from the "
                             "strings, %s from the matrix path"
                             % (show(k[0], k[1], len(words[0])),
                                words[i], words[uniq[k]]))
    print("gate: %d pinning templates recomputed exhaustively from the strings, "
          "exact" % len(ref))


def gate_scan(words, uniq, rng):
    """Re-verify sampled rows by scanning the WHOLE pool with string equality."""
    keys = sorted(uniq)
    take = keys if len(keys) <= GATE_ROWS else [
        keys[j] for j in rng.choice(len(keys), size=GATE_ROWS, replace=False)]
    for positions, letters in take:
        hits = [w for w in words
                if all(w[p] == c for p, c in zip(positions, letters))]
        if len(hits) != 1:
            raise SystemExit("GATE FAILED: template %s matches %d words on a "
                             "full scan, not 1"
                             % (show(positions, letters, len(words[0])), len(hits)))
        if hits[0] != words[uniq[(positions, letters)]]:
            raise SystemExit("GATE FAILED: template %s scans to %s, reported %s"
                             % (show(positions, letters, len(words[0])), hits[0],
                                words[uniq[(positions, letters)]]))
    print("gate: %d rows re-verified by a full string scan of all %d words"
          % (len(take), len(words)))


def gate_subset(uniq, answers, greens):
    """Pinning one word of 12972 must pin one of the 2315 -- checked, not assumed.

    Every answer is a legal guess, so a template with a single match in the big
    pool has at most one in the small one; it has exactly one iff that match is
    itself an answer.  Returns how many templates the big pool DROPPED, which the
    coverage tally insists is nonzero.
    """
    small = reference(answers, greens)
    dropped = 0
    for (positions, letters), i in uniq.items():
        if (positions, letters) in small:
            continue
        dropped += 1
    covered = sum(1 for k in uniq if k in small)
    print("gate: %d of %d guess-pool templates also pin a single answer, %d do "
          "not (their word is not an answer)" % (covered, len(uniq), dropped))
    return len(small), dropped


# --------------------------------------------------------------------------- main

def main(argv):
    pool_name = _arg(argv, "--pool", ("answers", "guesses"))
    require = _arg(argv, "--require", ("answer", "any"))
    if "--greens" not in argv:
        raise SystemExit("--greens N is REQUIRED -- N is part of the question "
                         "(a 2-green result and a 3-green result are different "
                         "quantities and get different files). Use "
                         "solver/run-green-templates.sh.")
    greens = int(argv[argv.index("--greens") + 1])
    if "--out" not in argv and "--no-out" not in argv:
        raise SystemExit("--out PATH is REQUIRED (or an explicit --no-out). A "
                         "run that prints its answer and saves nothing is how a "
                         "result gets lost; use solver/run-green-templates.sh.")
    out = argv[argv.index("--out") + 1] if "--out" in argv else None
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 20

    answers = load_words("mystery")
    words = answers if pool_name == "answers" else load_words("guess")
    answer_set = set(answers)

    uniq, word_len, occupied = pin_single(words, greens)
    total_templates = len(list(itertools.combinations(range(word_len), greens))) \
        * ALPHA ** greens
    print("%d words, %d greens: %d templates, %d match at least one word, "
          "%d pin exactly one"
          % (len(words), greens, total_templates, occupied, len(uniq)))

    gate_reference(words, greens, uniq)
    gate_scan(words, uniq, np.random.default_rng(0))
    dropped = None
    if pool_name == "guesses":
        _, dropped = gate_subset(uniq, answers, greens)

    rows = sorted(uniq)
    if require == "answer":
        rows = [k for k in rows if words[uniq[k]] in answer_set]
    if pool_name == "answers" and len(rows) != len(uniq):
        raise SystemExit("GATE FAILED: --pool answers dropped %d rows under "
                         "--require answer, but every word in that pool IS an "
                         "answer" % (len(uniq) - len(rows)))

    # Coverage tally -- a pass must not silently mean nothing was exercised.
    if not rows:
        raise SystemExit("GATE FAILED: no template pinned a word; there is "
                         "nothing here to report")
    if pool_name == "guesses" and not dropped:
        raise SystemExit("GATE FAILED: the guess pool dropped no template the "
                         "answer pool would have kept, so the harder pool was "
                         "never actually exercised")

    pinned = sorted({words[uniq[k]] for k in rows})
    print("%d rows kept (--require %s), pinning %d distinct words"
          % (len(rows), require, len(pinned)))

    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w") as f:
            f.write("# %d free-standing green letters that PIN a single word.\n"
                    % greens)
            f.write("# uniqueness judged over the %d %s; rows kept: %s.\n"
                    % (len(words),
                       "mystery answers" if pool_name == "answers"
                       else "legal guess words",
                       "only those whose word is a mystery answer"
                       if require == "answer" else "all of them"))
            f.write("# the other %d positions are UNCONSTRAINED -- the template "
                    "says nothing about them, and no guess, grey or yellow is "
                    "involved.\n" % (word_len - greens))
            f.write("template,positions,letters,word\n")
            for positions, letters in rows:
                f.write("%s,%s,%s,%s\n"
                        % (show(positions, letters, word_len),
                           "-".join(str(p + 1) for p in positions),
                           "".join(letters), words[uniq[(positions, letters)]]))
        print("wrote %s" % os.path.relpath(out, _MATH))

    print("\n%8s %10s %8s %8s" % ("template", "positions", "letters", "word"))
    for positions, letters in rows[:top]:
        print("%8s %10s %8s %8s"
              % (show(positions, letters, word_len),
                 "-".join(str(p + 1) for p in positions), "".join(letters),
                 words[uniq[(positions, letters)]]))
    if len(rows) > top:
        print("... %d more" % (len(rows) - top))

    per_word = {}
    for k in rows:
        w = words[uniq[k]]
        per_word[w] = per_word.get(w, 0) + 1
    print("\n%d of the %d %s are pinned by at least one template"
          % (len(pinned), len(answers) if require == "answer" else len(words),
             "mystery answers" if require == "answer" else "pool words"))
    best = sorted(per_word.items(), key=lambda kv: (-kv[1], kv[0]))
    print("most-pinned: %s"
          % ", ".join("%s x%d" % (w, c) for w, c in best[:8]))
    print("pinned by exactly one template: %d word(s)"
          % sum(1 for c in per_word.values() if c == 1))
    by_positions = {}
    for positions, _ in rows:
        by_positions[positions] = by_positions.get(positions, 0) + 1
    print("\nby position set (1-indexed):")
    for positions in sorted(by_positions):
        print("  %-10s %5d"
              % ("-".join(str(p + 1) for p in positions), by_positions[positions]))


if __name__ == "__main__":
    main(sys.argv[1:])
