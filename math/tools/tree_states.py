"""Break the OPTIMAL TREES down by level and by what the board shows so far.

Where `wordle_in_one.py` asks about ONE row played blind, this walks the emitted
optimal strategies and asks the same two questions at every point of the game:

    at LEVEL k (after k guesses and their feedback), for each cumulative
    (greens, yellows) tile count, how often has the strategy narrowed the answer
    to ONE word, and how often would a random pick from what is still alive be
    right?

    python3 tools/tree_states.py --top 1000 --out FILE

Prefer `bash solver/run-tree-states.sh --top 1000` (from math/), which sets
--out, names it after the run and tees a log.

THE STATE IS CUMULATIVE, AND ITS DEFINITION IS THE USER'S (2026-09-08):
  greens  = POSITIONS pinned green by any guess so far (a position stays pinned;
            a later guess playing a different letter there does not unpin it).
  yellows = COPIES of a letter known to be in the answer but NOT yet pinned --
            summed over letters, so two loose B's count 2, and a letter with one
            copy green and another still loose contributes 1.
  grays   = 5 - greens - yellows.
The repeated-letter reading is "unplaced copies", chosen over "distinct unplaced
letters" and over the literal "appeared yellow and never green" because it is the
one that makes `greens + yellows` the number of ANSWER SLOTS accounted for, hence
`grays` exactly the slots still blank. That invariant is asserted at every node:
a letter's known count is `max over rows of (greens + yellows of it in that row)`
and its pinned count is how many positions it holds, so the two sum to at most 5.

WEIGHTING IS BY ANSWERS, not by nodes (the user's call): a node holding n
candidates contributes n cases, so `pct_single` is the share of ANSWERS sitting
in a node already narrowed to one, and a wide node counts for more than a narrow
one. `nodes` is reported beside `cases` so the other reading stays recoverable.

THE TWO RANDOM-PICK COLUMNS follow `wordle_in_one.py`: a node with n consistent
ANSWERS and m consistent LEGAL GUESSES contributes n * (1/n) and n * (1/m), so
pct_rand_answers is `nodes / cases` and pct_rand_guesses is weakly smaller (the
legal-word pool is a superset containing every consistent answer). A pick from
the whole list ignoring the board is a flat 1/2315 or 1/12972 and is not this.

A WON GAME IS NOT A CASE. A tree line records no pattern for its final guess (it
would be all green), so a game that ends at turn k simply has no level-k state
and drops out of every deeper level -- the same reason `wordle_in_one.py` carries
a games_nowin column.

THESE ARE 1000 DIFFERENT STRATEGIES POOLED, and each contributes its own 2315
answers, so every opener carries equal weight regardless of how good it is. That
is a choice about the aggregate, not a property of any tree: a per-opener number
needs `--top 1` on the opener you want.

THE TREES ARE THE CONSTRAINED OPTIMA. Every one minimises TOTAL guesses over the
2315 answers SUBJECT TO resolving each within 6, so a state here is a state of
that strategy, not of an unconstrained expected-guess minimiser. `--top N` takes
the N best openers by `total` from the sweep's own CSV, ties broken by word.

Gates, both always on and both differential:
  * the cumulative state of sampled lines is recomputed FROM THE STRINGS by a
    different route -- greens as positions where some guess matched the answer,
    known counts as `max over rows of min(count in guess, count in answer)` --
    which never looks at a tile, so a mistake in the tile walk cannot be shared.
    It also re-derives every recorded pattern with `wordle.pattern`.
  * on the first few openers, a node's candidate count n and legal-word count m
    are recomputed by FILTERING THE WORD LISTS with `wordle.pattern`, checking
    the tree's partition really is the consistent set and that the incremental
    matrix filtering inside the walk agrees with it.
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
from paths import (ANSWER_WORDS, FULL_GUESS_WORDS, GUESS_WORDS,  # noqa: E402
                   SOLVER, TREES, load_totals)

L = 5
MAXLVL = 8            # array bound only; a depth-6 sweep fills levels 1..5


def read_list(path):
    with open(path) as f:
        return [w.strip() for w in f if w.strip()]


def code_of(pat):
    """'gybbb' -> the base-3 code wordle.pattern returns (first tile is high)."""
    code = 0
    for ch in pat:
        code = code * 3 + (2 if ch == "g" else 1 if ch == "y" else 0)
    return code


# --- the cumulative state ------------------------------------------------
# (pinned, known): pinned is an L-tuple of letter indices (-1 where unknown),
# known maps a letter to the most copies any single row has proved.

EMPTY = ((-1,) * L, ())


def _known_map(known):
    return dict(known)


def apply_row(state, guess, pat):
    pinned, known = state
    pinned = list(pinned)
    kn = _known_map(known)
    row = {}
    for i, t in enumerate(pat):
        c = ord(guess[i]) - 97
        if t == "g":
            if pinned[i] == -1:
                pinned[i] = c
            elif pinned[i] != c:
                raise SystemExit("two different letters green at position %d" % i)
            row[c] = row.get(c, 0) + 1
        elif t == "y":
            row[c] = row.get(c, 0) + 1
    for c, n in row.items():
        if n > kn.get(c, 0):
            kn[c] = n
    return (tuple(pinned), tuple(sorted(kn.items())))


def greens_yellows(state):
    pinned, known = state
    pc = {}
    greens = 0
    for c in pinned:
        if c >= 0:
            pc[c] = pc.get(c, 0) + 1
            greens += 1
    yellows = 0
    for c, n in known:
        extra = n - pc.get(c, 0)
        if extra > 0:
            yellows += extra
    return greens, yellows


def state_from_strings(answer, guesses):
    """The same state by a route that never looks at a tile -- the gate.

    Wordle hands out exactly min(count in guess, count in answer) non-gray tiles
    of a letter, greens included, so a row's proof about a letter is that min;
    and a position is pinned exactly when some guess had the answer's letter
    there. Neither line needs the feedback string.
    """
    greens = sum(1 for i in range(L)
                 if any(g[i] == answer[i] for g in guesses))
    letters = set(answer)
    yellows = 0
    for c in letters:
        in_answer = answer.count(c)
        known = max([min(g.count(c), in_answer) for g in guesses] or [0])
        pinned = sum(1 for i in range(L)
                     if answer[i] == c and any(g[i] == c for g in guesses))
        yellows += max(0, known - pinned)
    return greens, yellows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, required=True,
                    help="how many openers, best first by total from the sweep CSV")
    ap.add_argument("--out", help="output CSV (the wrapper sets this)")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, write nothing -- say so deliberately")
    ap.add_argument("--check-lines", type=int, default=25,
                    help="lines per opener whose state is re-derived from the "
                         "strings (default 25; 0 disables, which is not advised)")
    ap.add_argument("--check-openers", type=int, default=3,
                    help="openers on which candidate counts are re-derived by "
                         "filtering the word lists (default 3, the slow gate)")
    ap.add_argument("--progress", type=int, default=25,
                    help="print a line every N openers")
    args = ap.parse_args()
    if not args.out and not args.no_out:
        raise SystemExit("--out FILE is required (or --no-out to print only). "
                         "Prefer 'bash solver/run-tree-states.sh --top N'.")
    if args.top < 1:
        raise SystemExit("--top must be at least 1")

    answers = read_list(ANSWER_WORDS)
    full_words = read_list(FULL_GUESS_WORDS)
    pool_words = read_list(GUESS_WORDS)
    fidx = {w: i for i, w in enumerate(full_words)}
    pool_cols = np.array([fidx[w] for w in pool_words], dtype=np.int32)

    try:
        PATF = np.asarray(load_patterns(full=True))
    except FileNotFoundError:
        raise SystemExit(
            "the legal-word random-pick column needs the SQUARE guess x guess "
            "pattern matrix.\nBuild it with 'python3 build_patterns.py --full' "
            "(about 18s, 168 MB).")
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

    nodes = np.zeros((MAXLVL, L + 1, L + 1), dtype=np.int64)
    cases = np.zeros((MAXLVL, L + 1, L + 1), dtype=np.int64)
    singles = np.zeros((MAXLVL, L + 1, L + 1), dtype=np.int64)
    rand_gss = np.zeros((MAXLVL, L + 1, L + 1), dtype=np.float64)

    rng = random.Random(0)
    checked_lines = checked_nodes = 0
    t0 = time.time()

    for oi, word in enumerate(ranked):
        path = os.path.join(TREES, word + ".txt.gz")
        if not os.path.exists(path):
            raise SystemExit("no tree for %s at %s -- the committed trees may "
                             "not cover this opener" % (word, path))
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
        if len(lines) != len(answers):
            raise SystemExit("%s tree has %d lines, expected %d"
                             % (word, len(lines), len(answers)))

        sizes = {}          # prefix -> (candidates, legal words) for the gate

        def walk(rows, d, state, cols):
            if d:
                n = len(rows)
                m = len(cols)
                if m < n:
                    raise SystemExit("%s: %d consistent answers but only %d "
                                     "consistent legal words" % (word, n, m))
                g, y = greens_yellows(state)
                if g + y > L:
                    raise SystemExit("%s: %d greens + %d yellows exceeds %d"
                                     % (word, g, y, L))
                nodes[d, g, y] += 1
                cases[d, g, y] += n
                if n == 1:
                    singles[d, g, y] += 1
                rand_gss[d, g, y] += n / m
                sizes[(rows[0][1][:d], rows[0][2][:d])] = (n, m)
            kids = defaultdict(list)
            for row in rows:
                if len(row[2]) > d:
                    kids[row[2][d]].append(row)
            if not kids:
                return
            guess = rows[0][1][d]
            for row in rows:
                if row[1][d] != guess:
                    raise SystemExit("%s: node at depth %d plays two different "
                                     "guesses -- not a strategy" % (word, d))
            grow = PATF[fidx[guess]]
            for pat, sub in kids.items():
                code = code_of(pat)
                if code == 3 ** L - 1:
                    raise SystemExit("%s: an all-green pattern mid-line" % word)
                walk(sub, d + 1, apply_row(state, guess, pat),
                     cols[grow[cols] == code])

        walk(lines, 0, EMPTY, pool_cols)

        # --- gate 1: the cumulative state, re-derived from the strings
        if args.check_lines:
            for ans, gs, ps in rng.sample(lines, min(args.check_lines, len(lines))):
                state = EMPTY
                for k, pat in enumerate(ps):
                    if pattern(gs[k], ans) != code_of(pat):
                        raise SystemExit("GATE FAILED: %s tree records %s for "
                                         "%s vs %s" % (word, pat, gs[k], ans))
                    state = apply_row(state, gs[k], pat)
                    ref = state_from_strings(ans, gs[:k + 1])
                    if greens_yellows(state) != ref:
                        raise SystemExit(
                            "GATE FAILED: %s line %s after %d rows: tile walk "
                            "says %s, the strings say %s"
                            % (word, ans, k + 1, greens_yellows(state), ref))
                    checked_lines += 1

        # --- gate 2: the candidate counts, by filtering the word lists
        if oi < args.check_openers:
            for ans, gs, ps in rng.sample(lines, min(2, len(lines))):
                for k in range(len(ps)):
                    codes = [code_of(p) for p in ps[:k + 1]]
                    n_ref = sum(1 for a in answers
                                if all(pattern(gs[j], a) == codes[j]
                                       for j in range(k + 1)))
                    m_ref = sum(1 for w in pool_words
                                if all(pattern(gs[j], w) == codes[j]
                                       for j in range(k + 1)))
                    got = sizes.get((gs[:k + 1], ps[:k + 1]))
                    if got != (n_ref, m_ref):
                        raise SystemExit(
                            "GATE FAILED: %s after %d rows of the %s line: walk "
                            "says %s, filtering the lists says %s"
                            % (word, k + 1, ans, got, (n_ref, m_ref)))
                    checked_nodes += 1

        if args.progress and (oi + 1) % args.progress == 0:
            print("  %d/%d openers, %.1fs" % (oi + 1, len(ranked), time.time() - t0),
                  flush=True)

    print("gate OK: %d sampled line-states re-derived from the strings, %d node "
          "candidate counts re-derived by filtering the word lists"
          % (checked_lines, checked_nodes))

    def pct(num, den):
        return 100.0 * num / den if den else 0.0

    levels = [d for d in range(MAXLVL) if cases[d].sum()]
    hdr = ("%5s %6s %7s %6s %10s %12s %10s %11s %11s"
           % ("level", "green", "yellow", "gray", "nodes", "cases", "pct_one",
              "rand_ans", "rand_guess"))
    print("\nopeners: %d (best by total in the %s sweep, %s .. %s)"
          % (len(ranked), SOLVER, ranked[0], ranked[-1]))
    print("cases are ANSWERS: a node holding n candidates counts n times\n")
    print(hdr)
    for d in levels:
        for g in range(L + 1):
            for y in range(L + 1 - g):
                if not cases[d, g, y]:
                    continue
                print("%5d %6d %7d %6d %10d %12d %9.4f%% %10.4f%% %10.4f%%"
                      % (d, g, y, L - g - y, nodes[d, g, y], cases[d, g, y],
                         pct(singles[d, g, y], cases[d, g, y]),
                         pct(nodes[d, g, y], cases[d, g, y]),
                         pct(rand_gss[d, g, y], cases[d, g, y])))
    print("\nby level:")
    for d in levels:
        c, nd = int(cases[d].sum()), int(nodes[d].sum())
        print("  level %d: %8d cases in %7d nodes, narrowed to one %7.4f%%, "
              "random pick right %7.4f%% (answers) / %7.4f%% (legal guesses)"
              % (d, c, nd, pct(int(singles[d].sum()), c), pct(nd, c),
                 pct(float(rand_gss[d].sum()), c)))

    if args.no_out:
        return
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("# %s optimal trees, top %d openers by total (%s .. %s); level k "
                "is the state after k guesses and their feedback\n"
                % (SOLVER, len(ranked), ranked[0], ranked[-1]))
        f.write("# greens=positions pinned so far, yellows=known copies of a "
                "letter not yet pinned, grays=%d-greens-yellows; cases are "
                "ANSWERS (a node with n candidates counts n times), nodes is the "
                "same states counted once each\n" % L)
        f.write("# pct_single=share of cases already narrowed to one word; "
                "pct_rand_answers/pct_rand_guesses=chance a random pick from the "
                "words still consistent is right, drawing from the answers and "
                "from the sweep's legal guesses\n")
        f.write("level,greens,yellows,grays,nodes,cases,singles,pct_single,"
                "pct_rand_answers,pct_rand_guesses\n")
        for d in levels:
            for g in range(L + 1):
                for y in range(L + 1 - g):
                    if not cases[d, g, y]:
                        continue
                    f.write("%d,%d,%d,%d,%d,%d,%d,%.5f,%.5f,%.5f\n"
                            % (d, g, y, L - g - y, nodes[d, g, y], cases[d, g, y],
                               singles[d, g, y],
                               pct(singles[d, g, y], cases[d, g, y]),
                               pct(nodes[d, g, y], cases[d, g, y]),
                               pct(rand_gss[d, g, y], cases[d, g, y])))
    print("\nwrote %s" % os.path.relpath(args.out, _MATH))


if __name__ == "__main__":
    main()
