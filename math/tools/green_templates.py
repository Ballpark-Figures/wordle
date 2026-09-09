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

FIVE AXES, ALL PART OF THE QUESTION, NONE DEFAULTED HERE (the wrapper carries
a default a human reads and forwards it explicitly). --greens is the first;
the other four are:

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

  --letters  WHICH LETTERS A TEMPLATE'S GREENS MAY USE.  `all` is the 26;
             `vowels` keeps only the templates whose every green is a vowel;
             `consonants` only those whose every green is a consonant.  Y IS A
             VOWEL HERE AND IS NOT A CONSONANT (the user's definition,
             2026-09-09), so the two sets PARTITION the alphabet -- 6 + 20 = 26,
             disjoint, union everything -- and that is asserted rather than
             assumed.  Like --require this changes NO count: a template pins
             whatever it pins regardless of which templates we chose to look at,
             so this only restricts the rows.
             THE VOWEL AND CONSONANT ROWS DO NOT SUM TO THE `all` ROWS.  A
             template mixing a vowel and a consonant (`.a..t`) is homogeneous
             under neither and appears only under `all`, and at N greens the
             mixed templates are the bulk of them.

  --positions WHICH POSITION SET THE GREENS SIT IN.  `all` is every C(L,N) of
             them; `1-3` keeps only the templates greening positions 1 and 3.
             1-indexed and hyphen-joined, so it is written exactly as the CSV's
             own `positions` column reads it back.  A third pure row filter --
             it changes no count.  IT MUST NAME EXACTLY --greens POSITIONS and
             this REFUSES otherwise rather than quietly reinterpreting one flag
             in the light of the other.

  --top      HOW MANY ROWS TO PRINT -- an integer, or `all`.  PRESENTATION
             ONLY: it never touches the FILE, which always holds every row, and
             it is not in the filename for that reason.  It also lengthens the
             two summary lists.

  --sort     IS NOT A RESTRICTION AND IS NOT PART OF THE QUESTION -- it reorders
             the very same rows.  `template` is the position-then-letter order
             (the deterministic default); `zipf` is DESCENDING word frequency,
             most common word first.  A TIE FALLS BACK TO THE `template` ORDER
             (position set, then letters), so tied rows keep exactly the relative
             order the default sort would give them and the file stays
             deterministic -- ties are common, since one word is often pinned by
             several templates and they all carry its one frequency.  It lands in the filename anyway, because two runs
             differing only in it would otherwise write different bytes under
             one name.

THE ZIPF IS SOURCED, NEVER RECOMPUTED.  Every row carries the pinned word's zipf,
read from the committed `data/shared/words/guess_by_freq.txt` through
`build_freq_wordlist.load_zipf` -- the module that OWNS that file's format, so
there is no second copy of the parse.  zipf is log10(occurrences per billion),
higher = more common; 4.0 is about 10 per million, 3.0 about 1 per million, and
0.00 is a REAL VALUE meaning wordfreq's "large" list does not contain the word at
all, which is true of thousands of the 12972.  Nothing here imports wordfreq.

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
answer, which is the free oracle the two pools give each other.  Separately the
FINAL ROW SET -- after both filters -- is re-derived straight from that
string-built reference and demanded equal, so the filter chain is checked and not
merely the raw computation, and the vowel/consonant sets are proved to partition
the alphabet.  A coverage tally FAILS if no template pinned anything, if --pool
guesses never actually dropped a template that the answer pool would have kept,
or if a --letters or --positions restriction dropped nothing -- so a pass cannot
silently mean the harder pool or a restriction went untested.  Every pinned word
must carry a zipf or the run fails, and a zipf sort is checked to be a
PERMUTATION of the rows and genuinely non-increasing.

An EMPTY row set after the filters is a legitimate RESULT, not a failure: the
file is still written, so the emptiness is on the record.  Only an empty set
BEFORE the filters -- no template pinning anything at all -- is a broken run.
"""

import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from build_freq_wordlist import load_zipf  # noqa: E402
from wordle import load_words, to_codes  # noqa: E402

_MATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GATE_ROWS = 200           # emitted rows re-verified by a full string scan
ALPHA = 26

# Y IS A VOWEL AND IS NOT A CONSONANT -- the user's definition (2026-09-09), and
# the reason these are spelled out rather than derived from "aeiou".  The two
# sets PARTITION a..z: 6 + 20 = 26, disjoint, union everything.  gate_letter_sets
# proves that on every run rather than trusting the two literals to stay in step.
VOWELS = frozenset("aeiouy")
CONSONANTS = frozenset("bcdfghjklmnpqrstvwxz")
ALPHABET = frozenset("abcdefghijklmnopqrstuvwxyz")
LETTER_SETS = {"all": ALPHABET, "vowels": VOWELS, "consonants": CONSONANTS}
LETTER_DESC = {
    "all": "unrestricted -- any of the 26",
    "vowels": "vowels only: " + " ".join(sorted(VOWELS)) + " (y counts as a vowel)",
    "consonants": ("consonants only: " + " ".join(sorted(CONSONANTS))
                   + " (y is NOT among them -- it is a vowel here)"),
}


def fmt_positions(positions):
    """The CSV's own rendering of a position set: 1-indexed, hyphen-joined."""
    return "-".join(str(p + 1) for p in positions)


def parse_positions(spec, greens, word_len):
    """`all` -> None, else a 0-indexed tuple. Refuses anything inconsistent.

    It must name exactly --greens positions: a `--positions 1-3` beside a
    `--greens 2` agrees, beside a `--greens 3` it does not, and reinterpreting
    either flag in the light of the other would be one decision with two owners.
    """
    if spec == "all":
        return None
    try:
        got = [int(p) for p in spec.split("-")]
    except ValueError:
        raise SystemExit("--positions must be `all` or 1-indexed positions "
                         "joined by hyphens, e.g. 1-3 (as the CSV writes them)")
    if len(set(got)) != len(got):
        raise SystemExit("--positions %s repeats a position" % spec)
    if any(not 1 <= g <= word_len for g in got):
        raise SystemExit("--positions %s is outside 1..%d" % (spec, word_len))
    if len(got) != greens:
        raise SystemExit("--positions %s names %d position(s) but --greens is "
                         "%d -- they must agree; this refuses rather than "
                         "reinterpret one flag in the light of the other"
                         % (spec, len(got), greens))
    return tuple(sorted(g - 1 for g in got))


def keep_positions(rows, positions):
    """Restrict to templates greening exactly this position set."""
    return rows if positions is None else [k for k in rows if k[0] == positions]


def keep_letters(rows, letter_set):
    """Restrict to templates whose greens ALL come from the chosen set.

    A pure row filter: it cannot change what any template pins, only which
    templates are listed. A template mixing classes is homogeneous under neither
    and survives `all` alone.
    """
    allowed = LETTER_SETS[letter_set]
    return [k for k in rows if all(c in allowed for c in k[1])]


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
    return ref


def gate_letter_sets():
    """The vowel and consonant sets must PARTITION the alphabet.

    Two hand-typed literals that are meant to be complementary will drift; this
    is the check that says so instead of silently dropping or double-counting a
    letter. It also pins the y convention, which is the one a reader will doubt.
    """
    if VOWELS & CONSONANTS:
        raise SystemExit("GATE FAILED: vowels and consonants overlap on %s"
                         % "".join(sorted(VOWELS & CONSONANTS)))
    if VOWELS | CONSONANTS != ALPHABET:
        raise SystemExit("GATE FAILED: vowels + consonants miss %s"
                         % "".join(sorted(ALPHABET - (VOWELS | CONSONANTS))))
    if "y" not in VOWELS or "y" in CONSONANTS:
        raise SystemExit("GATE FAILED: y must be a vowel and not a consonant")
    print("gate: %d vowels + %d consonants partition the 26 letters, y a vowel"
          % (len(VOWELS), len(CONSONANTS)))


def gate_rows(ref, words, answer_set, require, letter_set, positions, rows):
    """Re-derive the FINAL row set from the string-built reference.

    The filters are conjunctive and independent of each other, so applying them
    in one comprehension over `ref` shares nothing with the chain that produced
    `rows` -- and `ref` itself never touched numpy. This is what pins the filter
    chain; gate_reference only pins the raw computation.
    """
    allowed = LETTER_SETS[letter_set]
    want = sorted(k for k, i in ref.items()
                  if all(c in allowed for c in k[1])
                  and (positions is None or k[0] == positions)
                  and (require == "any" or words[i] in answer_set))
    if want != sorted(rows):
        raise SystemExit("GATE FAILED: %d rows after the filters, %d re-derived "
                         "from the strings" % (len(rows), len(want)))
    print("gate: the %d-row output re-derived from the strings through every "
          "filter, exact" % len(want))


def gate_sort(rows, zipf_of, order):
    """A sort must REORDER the rows, never change which rows there are.

    Checked as a set, then -- for the zipf order -- that the sequence really is
    non-increasing. A key that silently failed to find a word's frequency would
    otherwise just look like an odd ordering.
    """
    if sorted(set(rows)) != sorted(rows):
        raise SystemExit("GATE FAILED: the sorted rows repeat a template")
    if order == "zipf":
        zs = [zipf_of(k) for k in rows]
        bad = [i for i in range(len(zs) - 1) if zs[i] < zs[i + 1]]
        if bad:
            raise SystemExit("GATE FAILED: zipf sort is not non-increasing at "
                             "row %d (%.2f then %.2f)"
                             % (bad[0], zs[bad[0]], zs[bad[0] + 1]))
        print("gate: %d rows in non-increasing zipf order, %.2f down to %.2f"
              % (len(zs), zs[0], zs[-1]) if zs else "gate: no rows to sort")


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
    letter_set = _arg(argv, "--letters", ("all", "vowels", "consonants"))
    order = _arg(argv, "--sort", ("template", "zipf"))
    if "--positions" not in argv:
        raise SystemExit("--positions is REQUIRED (`all`, or a 1-indexed set "
                         "like 1-3). Use solver/run-green-templates.sh, which "
                         "carries a default a human reads.")
    pos_spec = argv[argv.index("--positions") + 1]
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
    top_spec = argv[argv.index("--top") + 1] if "--top" in argv else "20"
    if top_spec != "all":
        try:
            if int(top_spec) < 0:
                raise ValueError
        except ValueError:
            raise SystemExit("--top must be a non-negative integer or `all`")

    answers = load_words("mystery")
    words = answers if pool_name == "answers" else load_words("guess")
    answer_set = set(answers)
    zipf = load_zipf()
    missing = [w for w in words if w not in zipf]
    if missing:
        raise SystemExit("GATE FAILED: %d pool word(s) carry no zipf in the "
                         "committed guess_by_freq.txt, e.g. %s -- regenerate it "
                         "with build_freq_wordlist.py"
                         % (len(missing), " ".join(missing[:5])))

    gate_letter_sets()
    print("zipf: sourced for all %d pool words from the committed "
          "guess_by_freq.txt" % len(words))
    pos_filter = parse_positions(pos_spec, greens, len(words[0]))
    uniq, word_len, occupied = pin_single(words, greens)
    assert word_len == len(words[0])
    total_templates = len(list(itertools.combinations(range(word_len), greens))) \
        * ALPHA ** greens
    print("%d words, %d greens: %d templates, %d match at least one word, "
          "%d pin exactly one"
          % (len(words), greens, total_templates, occupied, len(uniq)))

    ref = gate_reference(words, greens, uniq)
    gate_scan(words, uniq, np.random.default_rng(0))
    dropped = None
    if pool_name == "guesses":
        _, dropped = gate_subset(uniq, answers, greens)

    if not uniq:
        raise SystemExit("GATE FAILED: no template pinned a word at all; there "
                         "is nothing here to report")

    rows = sorted(uniq)
    if require == "answer":
        rows = [k for k in rows if words[uniq[k]] in answer_set]
    if pool_name == "answers" and len(rows) != len(uniq):
        raise SystemExit("GATE FAILED: --pool answers dropped %d rows under "
                         "--require answer, but every word in that pool IS an "
                         "answer" % (len(uniq) - len(rows)))
    before_letters = len(rows)
    rows = keep_letters(rows, letter_set)
    before_positions = len(rows)
    rows = keep_positions(rows, pos_filter)

    gate_rows(ref, words, answer_set, require, letter_set, pos_filter, rows)

    # Coverage tally -- a pass must not silently mean nothing was exercised.
    if pool_name == "guesses" and not dropped:
        raise SystemExit("GATE FAILED: the guess pool dropped no template the "
                         "answer pool would have kept, so the harder pool was "
                         "never actually exercised")
    if letter_set != "all" and before_positions == before_letters:
        raise SystemExit("GATE FAILED: --letters %s dropped none of the %d rows, "
                         "so the restriction was never exercised"
                         % (letter_set, before_letters))
    if pos_filter is not None and len(rows) == before_positions:
        raise SystemExit("GATE FAILED: --positions %s dropped none of the %d "
                         "rows, so the restriction was never exercised"
                         % (pos_spec, before_positions))
    if not rows:
        # A legitimate RESULT under a restriction, not a bug. The file is still
        # written, so the emptiness is on the record rather than inferred from a
        # missing file.
        print("NO TEMPLATE SURVIVES: %d pinned a word, none kept under "
              "--require %s --letters %s --positions %s"
              % (len(uniq), require, letter_set, pos_spec))
    else:
        if letter_set != "all":
            print("--letters %s kept %d of the %d rows"
                  % (letter_set, before_positions, before_letters))
        if pos_filter is not None:
            print("--positions %s kept %d of the %d rows"
                  % (pos_spec, len(rows), before_positions))

    zipf_of = (lambda k: zipf[words[uniq[k]]])
    rows = (sorted(rows) if order == "template"
            else sorted(rows, key=lambda k: (-zipf_of(k), k)))
    gate_sort(rows, zipf_of, order)

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
            f.write("# green letters: %s.\n" % LETTER_DESC[letter_set])
            f.write("# positions: %s. rows sorted by %s.\n"
                    % ("any of the %d sets"
                       % len(list(itertools.combinations(range(word_len), greens)))
                       if pos_filter is None else fmt_positions(pos_filter),
                       "template (position then letter)" if order == "template"
                       else "zipf DESCENDING, most common word first"))
            f.write("# zipf is log10(occurrences per billion) from the committed "
                    "guess_by_freq.txt; 0.00 means absent from wordfreq's list.\n")
            f.write("# settings greens=%d pool=%s require=%s letters=%s "
                    "positions=%s sort=%s pool_size=%d rows=%d\n"
                    % (greens, pool_name, require, letter_set, pos_spec, order,
                       len(words), len(rows)))
            f.write("template,positions,letters,word,zipf\n")
            for positions, letters in rows:
                word = words[uniq[(positions, letters)]]
                f.write("%s,%s,%s,%s,%.2f\n"
                        % (show(positions, letters, word_len),
                           fmt_positions(positions), "".join(letters), word,
                           zipf[word]))
        print("wrote %s" % os.path.relpath(out, _MATH))

    # PRESENTATION ONLY -- it never changes the FILE, which always holds every
    # row. `all` prints the lot.
    top = len(rows) if top_spec == "all" else int(top_spec)
    print("\n%8s %10s %8s %8s %6s"
          % ("template", "positions", "letters", "word", "zipf"))
    for positions, letters in rows[:top]:
        word = words[uniq[(positions, letters)]]
        print("%8s %10s %8s %8s %6.2f"
              % (show(positions, letters, word_len), fmt_positions(positions),
                 "".join(letters), word, zipf[word]))
    if len(rows) > top:
        print("... %d more of %d (--top %d shown; --top all prints every row, "
              "and the CSV always holds them all)"
              % (len(rows) - top, len(rows), top))

    per_word = {}
    for k in rows:
        w = words[uniq[k]]
        per_word[w] = per_word.get(w, 0) + 1
    print("\n%d of the %d %s are pinned by at least one template"
          % (len(pinned), len(answers) if require == "answer" else len(words),
             "mystery answers" if require == "answer" else "pool words"))
    if pinned:
        zs = sorted((zipf[w] for w in pinned), reverse=True)
        above = sum(1 for z in zs if z >= 2.5)
        print("zipf of the pinned words: %.2f down to %.2f, median %.2f; "
              "%d of %d at or above 2.50"
              % (zs[0], zs[-1], zs[len(zs) // 2], above, len(zs)))
        n_list = len(pinned) if top_spec == "all" else min(len(pinned),
                                                            max(8, int(top_spec)))
        print("most common (%d of %d): %s"
              % (n_list, len(pinned),
                 ", ".join("%s %.2f" % (w, zipf[w])
                           for w in sorted(pinned,
                                           key=lambda w: (-zipf[w], w))[:n_list])))
    best = sorted(per_word.items(), key=lambda kv: (-kv[1], kv[0]))
    n_best = len(best) if top_spec == "all" else min(len(best),
                                                     max(8, int(top_spec)))
    print("most-pinned (%d of %d): %s"
          % (n_best, len(best),
             ", ".join("%s x%d" % (w, c) for w, c in best[:n_best])))
    print("pinned by exactly one template: %d word(s)"
          % sum(1 for c in per_word.values() if c == 1))
    if letter_set == "all":
        klass = {"vowels": 0, "consonants": 0, "mixed": 0}
        for _, tiles in rows:
            if all(c in VOWELS for c in tiles):
                klass["vowels"] += 1
            elif all(c in CONSONANTS for c in tiles):
                klass["consonants"] += 1
            else:
                klass["mixed"] += 1
        print("by letter class: %d all-vowel, %d all-consonant, %d mixed "
              "(y counts as a vowel)"
              % (klass["vowels"], klass["consonants"], klass["mixed"]))

    by_positions = {}
    for positions, _tiles in rows:
        by_positions[positions] = by_positions.get(positions, 0) + 1
    print("\nby position set (1-indexed):")
    for positions in sorted(by_positions):
        print("  %-10s %5d"
              % ("-".join(str(p + 1) for p in positions), by_positions[positions]))


if __name__ == "__main__":
    main(sys.argv[1:])
