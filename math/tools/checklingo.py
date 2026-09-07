"""Gate for the Lingo cell -- verify the per-letter word lists, the per-letter
pattern matrices, and any emitted trees, independently of the C solver.

The Lingo cell adds NO search code: it runs the validated `optturns` on a
letter-restricted answer set (`--answer-list`) and guess set (`--guess-list`)
with a purpose-built pattern matrix (`--patterns`). So the only NEW computational
artifact is that per-letter matrix, and if it is correct the solver is correct by
construction (validate.sh already pins the search). This checks exactly that.

  1. LISTS. The letter's guess/mystery files are precisely the length's full
     guess/mystery lists filtered to words starting with that letter, in the same
     order -- so nothing was dropped or reordered.

  2. MATRIX (the load-bearing check). Every column of the per-letter matrix is
     BIT-IDENTICAL to the corresponding column of the shared length matrix
     (`patterns.npy` / `patterns_len<L>.npy`), which `tools/checkpatterns.py`
     already validates against `wordle.pattern`. Bit-identical columns prove the
     matrix encodes true Wordle feedback AND that the columns are the right
     answers in the right order -- the one real risk, since the solver's
     `--answer-list` pairs matrix column j with answer file line j.

  3. TREES (end to end, length-general). For any emitted tree: every answer
     covered exactly once, every guess legal (in the letter's guess list) and
     starting with the letter, each recorded pattern equal to `wordle.pattern`
     of guess against answer, the last guess equal to the answer, one next guess
     per feedback prefix (a strategy, not a per-answer fabrication), and the
     summed guess counts equal to the CSV total.

    python3 tools/checklingo.py --length 5              # lists + matrices, sampled
    python3 tools/checklingo.py --length 5 --all        # every letter
    python3 tools/checklingo.py --length 5 --letter z   # one letter + its trees
    python3 tools/checklingo.py --length 5 --depth 5    # also verify d5 trees

Exit status is nonzero on any failure, so it works as a gate. Run it alongside
`solver/validate.sh` and `tools/checkpatterns.py`.
"""
import glob
import gzip
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wordle import decode, load_words, pattern
from build_patterns import build_answer_list, load_patterns

_TRIT = {0: "b", 1: "y", 2: "g"}
_MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LISTS = os.path.join(_MATH, "data", "shared", "words", "lingo")


def _bygg(code, word_len):
    return "".join(_TRIT[t] for t in decode(code, word_len))


def check_lists_and_matrix(length, letters, fails):
    la = None if length == 5 else length
    full_guesses = load_words("guess", la)
    full_answers = load_words("mystery", la)
    ans_index = {w: i for i, w in enumerate(full_answers)}
    full_mat = load_patterns(length=la) if la else load_patterns()

    for L in letters:
        ldir = os.path.join(_LISTS, "len%d" % length, L)
        gpath = os.path.join(ldir, "guess.txt")
        apath = os.path.join(ldir, "mystery.txt")
        if not (os.path.exists(gpath) and os.path.exists(apath)):
            fails.append("[%s] missing list files (run build_lingo_lists.py)" % L)
            continue
        with open(gpath) as f:
            gw = [x.strip() for x in f if x.strip()]
        with open(apath) as f:
            aw = [x.strip() for x in f if x.strip()]

        # (1) lists are exactly the filtered full lists, in order
        exp_g = [w for w in full_guesses if w[0] == L]
        exp_a = [w for w in full_answers if w[0] == L]
        if gw != exp_g:
            fails.append("[%s] guess list != full guess list filtered to '%s'" % (L, L))
        if aw != exp_a:
            fails.append("[%s] mystery list != full mystery list filtered to '%s'" % (L, L))
        if any(w[0] != L for w in gw + aw):
            fails.append("[%s] a word does not start with '%s'" % (L, L))

        # (2) build the letter's matrix in memory and diff every column against
        #     the shared matrix's column for that same answer -- bit-identical.
        tmp = os.path.join(_MATH, "data", "local", "lingo", "patterns",
                           "len%d" % length, "_check_%s" % L)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        mat = build_answer_list(apath, tmp, length=la)
        os.remove(tmp + ".npy")
        os.remove(tmp + ".npy.meta.json")
        if mat.shape != (len(full_guesses), len(aw)):
            fails.append("[%s] matrix shape %s wrong" % (L, mat.shape))
            continue
        ok = True
        for j, w in enumerate(aw):
            col = full_mat[:, ans_index[w]]
            if not np.array_equal(np.asarray(mat[:, j]), np.asarray(col)):
                fails.append("[%s] matrix column %d (%s) != shared matrix" % (L, j, w))
                ok = False
                break
        if ok:
            print("  [%s] lists ok, matrix %dx%d bit-identical to shared"
                  % (L, mat.shape[0], mat.shape[1]))


def _read_totals(csv_path):
    totals = {}
    if not os.path.exists(csv_path):
        return totals
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("word"):
                continue
            parts = line.split(",")
            if len(parts) >= 2 and parts[1] != "":
                totals[parts[0]] = int(parts[1])
    return totals


def check_trees(length, depth, letters, fails, answers_only=False):
    la = None if length == 5 else length
    word_len = length
    suf = "_ans" if answers_only else ""
    # answers-only trees may ONLY play answer words, so the legal set is the
    # mystery list, not the full guess list -- checking against guess.txt would
    # be a weaker superset test that misses a stray non-answer guess.
    legal_file = "mystery.txt" if answers_only else "guess.txt"
    result_dir = os.path.join(_MATH, "data", "shared", "lingo",
                              "len%d_d%d%s" % (length, depth, suf))
    tree_root = os.path.join(_MATH, "data", "local", "lingo",
                             "len%d_d%d%s" % (length, depth, suf))
    any_tree = False
    for L in letters:
        tree_dir = os.path.join(tree_root, L, "trees")
        files = sorted(glob.glob(os.path.join(tree_dir, "*.txt.gz")))
        if not files:
            continue
        any_tree = True
        with open(os.path.join(_LISTS, "len%d" % length, L, legal_file)) as f:
            legal = {x.strip() for x in f if x.strip()}
        with open(os.path.join(_LISTS, "len%d" % length, L, "mystery.txt")) as f:
            answers = {x.strip() for x in f if x.strip()}
        totals = _read_totals(os.path.join(result_dir, "%s_totals.csv" % L))

        for path in files:
            opener = os.path.basename(path)[:-len(".txt.gz")]
            seen = set()
            prefix_guess = {}
            tree_sum = 0
            with gzip.open(path, "rt") as f:
                for raw in f:
                    parts = raw.split()
                    if not parts:
                        continue
                    ans, n = parts[0], int(parts[1])
                    guesses = parts[2::2]
                    pats = parts[3::2]
                    tree_sum += n
                    seen.add(ans)
                    if len(guesses) != n:
                        fails.append("[%s/%s] %s says %d guesses, has %d"
                                     % (L, opener, ans, n, len(guesses)))
                    if guesses and guesses[-1] != ans:
                        fails.append("[%s/%s] %s ends on %s not the answer"
                                     % (L, opener, ans, guesses[-1]))
                    prefix = ()
                    for g, p in zip(guesses, pats):
                        if g not in legal or g[0] != L:
                            fails.append("[%s/%s] illegal guess %s for answer %s"
                                         % (L, opener, g, ans))
                        want = _bygg(pattern(g, ans), word_len)
                        if want != p:
                            fails.append("[%s/%s] %s: %s vs %s recorded %s"
                                         % (L, opener, ans, g, want, p))
                        if prefix in prefix_guess and prefix_guess[prefix] != g:
                            fails.append("[%s/%s] two next guesses after %s: %s and %s"
                                         % (L, opener, prefix, prefix_guess[prefix], g))
                        prefix_guess[prefix] = g
                        prefix = prefix + ((g, p),)
            if seen != answers:
                miss = answers - seen
                extra = seen - answers
                fails.append("[%s/%s] coverage off: missing %d, extra %d"
                             % (L, opener, len(miss), len(extra)))
            if opener in totals and totals[opener] != tree_sum:
                fails.append("[%s/%s] tree sum %d != CSV total %d"
                             % (L, opener, tree_sum, totals[opener]))
        print("  [%s] %d trees replayed" % (L, len(files)))
    if depth is not None and not any_tree:
        print("  (no trees found for length %d depth %d -- run a sweep first)"
              % (length, depth))


def main():
    argv = sys.argv[1:]
    length = int(argv[argv.index("--length") + 1]) if "--length" in argv else 5
    depth = int(argv[argv.index("--depth") + 1]) if "--depth" in argv else None
    answers_only = "--answers-only" in argv
    listdir = os.path.join(_LISTS, "len%d" % length)
    if not os.path.isdir(listdir):
        raise SystemExit("no lists at %s -- run: python3 build_lingo_lists.py "
                         "--length %d" % (listdir, length))
    present = sorted(d for d in os.listdir(listdir)
                     if len(d) == 1 and d.isalpha())
    if "--letter" in argv:
        letters = [argv[argv.index("--letter") + 1]]
    elif "--all" in argv:
        letters = present
    else:
        random.seed(0)
        letters = sorted(random.sample(present, min(6, len(present))))

    print("checklingo: length %d%s, letters %s"
          % (length, " (answers-only)" if answers_only else "", " ".join(letters)))
    fails = []
    check_lists_and_matrix(length, letters, fails)
    if depth is not None or "--letter" in argv:
        d = depth if depth is not None else 5
        check_trees(length, d, letters, fails, answers_only=answers_only)

    if fails:
        print("\nFAIL (%d):" % len(fails))
        for m in fails[:40]:
            print("  " + m)
        sys.exit(1)
    print("\nPASS")


if __name__ == "__main__":
    main()
