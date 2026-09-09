"""How often the OPTIMAL TREES play a word that could still be the answer.

Every line of an emitted tree is one game: an opener, some number of middle
guesses, and a final guess equal to the answer. This asks, of the MIDDLE guesses
only, how often the strategy played a word that was itself still CONSISTENT with
every clue on the board -- a word that could have won there and then.

    python3 tools/compatible_guesses.py --top 1000 --out FILE

Prefer `bash solver/run-compatible-guesses.sh --top 1000` (from math/), which
sets --out, names the file after the sweep and the opener count, and tees a log.

THE QUESTION, STATED EXACTLY (the user's, 2026-09-09):

  For each of the top N openers' trees, and each of the 2315 answers, walk that
  answer's line. The OPENER (guess 1) and the FINAL guess (which equals the
  answer, so it is compatible by construction) are EXCLUDED; every guess between
  them is examined. Count the examined guesses that are compatible, and average
  that count over ALL N * 2315 paths -- not over the examined guesses, and not
  over the paths that had any. So a line of length 3 contributes one examined
  guess and a count of 0 or 1; a line of length 1 or 2 contributes 0 examined
  guesses and a count of 0, and still counts in the denominator.

TWO READINGS OF "COMPATIBLE", AND BOTH ARE REPORTED.

  * `answer` (THE HEADLINE) -- the guess is one of the 2315 mystery answers AND
    is consistent with every clue so far, i.e. it is a live CANDIDATE: playing it
    could have ended the game. This is the tree's own candidate set.
  * `legal` -- the guess is consistent with every clue so far, without requiring
    it to be a mystery word. Every `answer` hit is a `legal` hit; the extra ones
    are guess-only words like `courd` that the answer list can never contain, so
    they could not actually have won. Reported because "compatible" can be read
    as a property of the CLUES alone, and the two are different quantities.

  Consistency is `ultraturns`' legality notion: `w` is consistent with the rows
  so far iff `pattern(g_j, w) == p_j` for every earlier row j. It is computed
  from the SQUARE 12972x12972 pattern matrix, which is gitignored under
  data/local/ and so missing on a fresh clone (`build_patterns.py --full`).

THE TOP N ARE N DIFFERENT STRATEGIES POOLED, best first by `total` in the sweep's
own CSV, ties on the word -- the same selection `tree_states.py` uses. Each
contributes its own 2315 answers, so every opener carries EQUAL weight however
good it is. A single opener's number needs `--top 1` at that opener's rank.

THE TREES ARE THE CONSTRAINED OPTIMA -- minimum total guesses over the 2315
answers SUBJECT TO resolving every answer within 6 -- so this is a property of
THAT strategy, never of an unconstrained expected-guess minimiser.

Nothing here searches or samples: it is a pure function of the committed trees
and word lists, so a re-run reproduces its file exactly.

THREE GATES, ALL ALWAYS ON:
  * every line is replayed against the recorded patterns: the answer itself must
    be consistent with every clue in its own line, or the line is not a game.
  * sampled lines have every compatibility decision recomputed FROM THE STRINGS
    with `wordle.pattern`, so a matrix or indexing mistake cannot be shared.
  * on the first few openers, compatibility under the `answer` reading is checked
    against the TREE'S OWN candidate sets -- the answers that reach that node --
    which is a route through the tree's structure rather than through any
    pattern lookup.
  * a COVERAGE tally fails the run if no examined guess was ever compatible, or
    none was ever incompatible, or the two readings never disagreed, so a pass
    cannot silently mean the distinction was never exercised.
"""

import argparse
import gzip
import os
import random
import sys
import time
from collections import defaultdict

import numpy as np

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_MATH = os.path.dirname(_TOOLS)
sys.path.insert(0, _MATH)
sys.path.insert(0, _TOOLS)

from build_patterns import load_patterns          # noqa: E402
from wordle import pattern                        # noqa: E402
from paths import (ANSWER_WORDS, FULL_GUESS_WORDS,  # noqa: E402
                   SOLVER, TREES, load_totals)

L = 5
MAXMID = 8          # array bound only; a depth-6 tree has at most 4 middles


def read_list(path):
    with open(path) as f:
        return [w.strip() for w in f if w.strip()]


def code_of(pat):
    """'gybbb' -> the base-3 code wordle.pattern returns (first tile is high)."""
    code = 0
    for ch in pat:
        code = code * 3 + (2 if ch == "g" else 1 if ch == "y" else 0)
    return code


def read_tree(path, word, n_answers):
    """One tree as [(answer, guesses, patterns)], with its shape checked."""
    lines = []
    with gzip.open(path, "rt") as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            ans, n = p[0], int(p[1])
            gs, ps = tuple(p[2::2]), tuple(p[3::2])
            if len(gs) != n or gs[-1] != ans or len(ps) != n - 1:
                raise SystemExit("malformed line for %s in %s" % (ans, word))
            lines.append((ans, gs, ps))
    if len(lines) != n_answers:
        raise SystemExit("%s tree has %d lines, expected %d"
                         % (word, len(lines), n_answers))
    return lines


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, required=True,
                    help="how many openers, best first by total from the sweep CSV")
    ap.add_argument("--out", help="output CSV (the wrapper sets this)")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, write nothing -- say so deliberately")
    ap.add_argument("--check-lines", type=int, default=25,
                    help="lines per opener whose decisions are recomputed from "
                         "the strings (default 25; 0 disables, not advised)")
    ap.add_argument("--check-openers", type=int, default=3,
                    help="openers checked against the tree's own candidate sets "
                         "(default 3)")
    ap.add_argument("--progress", type=int, default=25,
                    help="print a line every N openers")
    args = ap.parse_args()
    if not args.out and not args.no_out:
        raise SystemExit("--out FILE is required (or --no-out to print only). "
                         "Prefer 'bash solver/run-compatible-guesses.sh --top N'.")
    if args.top < 1:
        raise SystemExit("--top must be at least 1")

    answers = read_list(ANSWER_WORDS)
    answer_set = set(answers)
    full_words = read_list(FULL_GUESS_WORDS)
    fidx = {w: i for i, w in enumerate(full_words)}

    try:
        PATF = np.asarray(load_patterns(full=True))
    except FileNotFoundError:
        raise SystemExit(
            "this needs the SQUARE guess x guess pattern matrix.\nBuild it with "
            "'python3 build_patterns.py --full' (about 18s, 168 MB).")
    if PATF.shape != (len(full_words), len(full_words)):
        raise SystemExit("patterns_full.npy is %s, not %d x %d -- rebuild it"
                         % (PATF.shape, len(full_words), len(full_words)))

    totals = load_totals()
    if not totals:
        raise SystemExit("no totals in the %s CSV -- nothing to rank" % SOLVER)
    ranked = sorted(totals, key=lambda w: (totals[w], w))[:args.top]
    if len(ranked) < args.top:
        raise SystemExit("asked for the top %d openers but the %s CSV holds only "
                         "%d" % (args.top, SOLVER, len(ranked)))

    paths = midd = hit_ans = hit_leg = 0
    dist_ans = np.zeros(MAXMID + 1, dtype=np.int64)     # per-path compatible count
    dist_leg = np.zeros(MAXMID + 1, dtype=np.int64)
    pos_mid = np.zeros(MAXMID + 1, dtype=np.int64)      # by 1-based guess number
    pos_ans = np.zeros(MAXMID + 1, dtype=np.int64)
    pos_leg = np.zeros(MAXMID + 1, dtype=np.int64)
    by_len_paths = np.zeros(MAXMID + 3, dtype=np.int64)  # by line length
    by_len_ans = np.zeros(MAXMID + 3, dtype=np.int64)
    rows_out = []

    disagreed = 0
    rng = random.Random(0)
    t0 = time.time()

    for oi, word in enumerate(ranked):
        path = os.path.join(TREES, word + ".txt.gz")
        if not os.path.exists(path):
            raise SystemExit("no tree for %s at %s -- the committed trees may "
                             "not cover this opener" % (word, path))
        lines = read_tree(path, word, len(answers))

        # The tree's own candidate sets, for the structural gate: the answers
        # reaching a node are keyed by the pattern prefix, which identifies the
        # node uniquely once the opener is fixed.
        node_answers = None
        if oi < args.check_openers:
            node_answers = defaultdict(set)
            for ans, gs, ps in lines:
                for d in range(len(ps) + 1):
                    node_answers[ps[:d]].add(ans)

        o_mid = o_ans = o_leg = 0
        for ans, gs, ps in lines:
            n = len(gs)
            paths += 1
            by_len_paths[min(n, MAXMID + 2)] += 1
            codes = [code_of(p) for p in ps]
            gi = [fidx[g] for g in gs]

            # gate: the answer must itself be consistent with every clue in its
            # own line, or the recorded patterns are not a playable game.
            for j in range(n - 1):
                if PATF[gi[j], gi[n - 1]] != codes[j]:
                    raise SystemExit("GATE FAILED: %s tree, answer %s is not "
                                     "consistent with its own row %d"
                                     % (word, ans, j + 1))

            c_ans = c_leg = 0
            for k in range(1, n - 1):
                legal = all(PATF[gi[j], gi[k]] == codes[j] for j in range(k))
                is_ans = legal and gs[k] in answer_set
                if legal != is_ans:
                    disagreed += 1
                pos_mid[min(k + 1, MAXMID)] += 1
                if legal:
                    c_leg += 1
                    pos_leg[min(k + 1, MAXMID)] += 1
                if is_ans:
                    c_ans += 1
                    pos_ans[min(k + 1, MAXMID)] += 1
            o_mid += max(0, n - 2)
            o_ans += c_ans
            o_leg += c_leg
            dist_ans[min(c_ans, MAXMID)] += 1
            dist_leg[min(c_leg, MAXMID)] += 1
            by_len_ans[min(n, MAXMID + 2)] += c_ans

            # gate: the same `answer` decision, straight from the tree's
            # candidate sets -- a different route entirely.
            if node_answers is not None:
                for k in range(1, n - 1):
                    ref = gs[k] in node_answers[ps[:k]]
                    got = all(PATF[gi[j], gi[k]] == codes[j] for j in range(k)) \
                        and gs[k] in answer_set
                    if ref != got:
                        raise SystemExit(
                            "GATE FAILED: %s tree, guess %d (%s) on line %s: "
                            "candidate set says %s, pattern replay says %s"
                            % (word, k + 1, gs[k], ans, ref, got))

        # gate: the same decisions recomputed FROM THE STRINGS.
        if args.check_lines:
            for ans, gs, ps in rng.sample(lines, min(args.check_lines, len(lines))):
                n = len(gs)
                for k in range(n - 1):
                    if pattern(gs[k], ans) != code_of(ps[k]):
                        raise SystemExit("GATE FAILED: %s tree records %s for "
                                         "%s vs %s" % (word, ps[k], gs[k], ans))
                for k in range(1, n - 1):
                    ref = all(pattern(gs[j], gs[k]) == code_of(ps[j])
                              for j in range(k))
                    got = all(PATF[fidx[gs[j]], fidx[gs[k]]] == code_of(ps[j])
                              for j in range(k))
                    if ref != got:
                        raise SystemExit(
                            "GATE FAILED: %s tree, guess %d (%s) on line %s: "
                            "strings say %s, matrix says %s"
                            % (word, k + 1, gs[k], ans, ref, got))

        midd += o_mid
        hit_ans += o_ans
        hit_leg += o_leg
        rows_out.append((word, totals[word], len(lines), o_mid, o_ans, o_leg))

        if args.progress and (oi + 1) % args.progress == 0:
            el = time.time() - t0
            print("  %5d/%d openers  %.1fs  running avg %.4f"
                  % (oi + 1, len(ranked), el, hit_ans / paths), flush=True)

    # COVERAGE: a pass must mean the distinction was actually exercised.
    if hit_ans == 0:
        raise SystemExit("COVERAGE FAILED: no examined guess was ever a candidate")
    if hit_ans == midd:
        raise SystemExit("COVERAGE FAILED: every examined guess was a candidate")
    if disagreed == 0:
        raise SystemExit("COVERAGE FAILED: the two readings never disagreed")

    avg_ans = hit_ans / paths
    avg_leg = hit_leg / paths

    print()
    print("top %d %s trees, %d paths (%d openers x %d answers)"
          % (args.top, SOLVER, paths, len(ranked), len(answers)))
    print("guesses examined (opener and final guess excluded): %d" % midd)
    print()
    print("AVERAGE COMPATIBLE GUESSES PER PATH")
    print("  answer pool (a live candidate -- could have won):  %.6f" % avg_ans)
    print("  legal pool  (consistent with the clues only):      %.6f" % avg_leg)
    print()
    print("  of the %d examined guesses, %d (%.2f%%) were live candidates"
          % (midd, hit_ans, 100.0 * hit_ans / midd))
    print("  and %d (%.2f%%) were consistent but not mystery words"
          % (hit_leg - hit_ans, 100.0 * (hit_leg - hit_ans) / midd))
    print()
    print("PER PATH -- how many of a game's examined guesses were candidates")
    print("  count |      answer pool |       legal pool")
    for c in range(MAXMID + 1):
        if dist_ans[c] or dist_leg[c]:
            print("  %5d | %8d %6.2f%% | %8d %6.2f%%"
                  % (c, dist_ans[c], 100.0 * dist_ans[c] / paths,
                     dist_leg[c], 100.0 * dist_leg[c] / paths))
    print()
    print("BY GUESS NUMBER")
    print("  guess | examined |   candidate |  consistent")
    for k in range(MAXMID + 1):
        if pos_mid[k]:
            print("  %5d | %8d | %6.2f%%     | %6.2f%%"
                  % (k, pos_mid[k], 100.0 * pos_ans[k] / pos_mid[k],
                     100.0 * pos_leg[k] / pos_mid[k]))
    print()
    print("BY GAME LENGTH")
    print("  guesses |    paths |  examined | candidates | per path")
    for n in range(MAXMID + 3):
        if by_len_paths[n]:
            ex = by_len_paths[n] * max(0, n - 2)
            print("  %7d | %8d | %9d | %10d | %.4f"
                  % (n, by_len_paths[n], ex, by_len_ans[n],
                     by_len_ans[n] / by_len_paths[n]))
    print()
    print("done in %.1fs" % (time.time() - t0))

    if args.out:
        with open(args.out, "w") as f:
            f.write("# compatible guesses in the top %d %s trees, opener and "
                    "final guess excluded\n" % (args.top, SOLVER))
            f.write("# compatible_answers: the guess was a live CANDIDATE (a "
                    "mystery word consistent with every clue)\n")
            f.write("# compatible_legal: the guess was consistent with every "
                    "clue, mystery word or not\n")
            f.write("word,total,paths,examined,compatible_answers,"
                    "compatible_legal,avg_answers,avg_legal\n")
            for w, tot, np_, om, oa, ol in rows_out:
                f.write("%s,%d,%d,%d,%d,%d,%.6f,%.6f\n"
                        % (w, tot, np_, om, oa, ol, oa / np_, ol / np_))
            f.write("# paths %d\n" % paths)
            f.write("# examined %d\n" % midd)
            f.write("# compatible_answers %d\n" % hit_ans)
            f.write("# compatible_legal %d\n" % hit_leg)
            f.write("# avg_answers %.6f\n" % avg_ans)
            f.write("# avg_legal %.6f\n" % avg_leg)
        print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
