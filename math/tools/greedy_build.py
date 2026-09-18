"""Build an opening letter by letter.  math/greedybuild.py states the rule.

    bash solver/run-greedy-build.sh -k 1 --words 4

Exact and deterministic -- no sampling, no seed -- so a re-run reproduces the
file.  `-k` is a BEAM over (letter, slot) placements: at each step the K best
states are kept and each is extended, so K=1 is the plain greedy and the result
is the best of what the beam examined, never the best opening.  Each K is a
different search and gets its own file.
"""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_patterns import load_patterns                                # noqa: E402
from greedybuild import BLANK, completions, score, spell                # noqa: E402
from opening_list import resolve_word_set                              # noqa: E402
from wordle import load_words, pattern_row, to_codes                   # noqa: E402

COLUMNS = "step,opening,unsolved,ssq,placed_letter,placed_word,placed_pos"


def parse_args(argv):
    a = {"pool": None, "words": None, "topk": None, "out": None, "progress": 1}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k in ("k", "topk"):
            k = "topk"
        elif k == "nwords":
            k = "words"
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = int(v) if k in ("topk", "words", "progress") else v
        i += 2
    if a["pool"] is None:
        raise SystemExit("--pool is required: which words the follow-up draws "
                         "from, and which the opening is built out of")
    if a["words"] is None:
        raise SystemExit("--words N is required: how many words the opening has")
    if a["topk"] is None:
        raise SystemExit("--topk K is required: the beam width.  K=1 is the "
                         "plain greedy; it is part of the search, not a knob")
    if a["out"] is None:
        raise SystemExit("--out is required (or --no-out).  Use the wrapper: "
                         "bash solver/run-greedy-build.sh")
    return a


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    pool = sorted(resolve_word_set(a["pool"]))
    pset, gpos = set(pool), {w: i for i, w in enumerate(guesses)}
    missing = [w for w in answers if w not in pset]
    if missing:
        raise SystemExit("the pool is missing %d answer(s): %s"
                         % (len(missing), ", ".join(missing[:5])))

    full = np.array(load_patterns(full=True))
    cols = np.array([gpos[w] for w in pool])
    pool_codes = to_codes(pool)
    ppos = {w: i for i, w in enumerate(pool)}
    ans_pool_idx = np.array([ppos[w] for w in answers])
    nw, L = a["words"], len(pool[0])

    print("greedy build: %d words, pool %s (%d), answers %d, beam k=%d"
          % (nw, a["pool"], len(pool), len(answers), a["topk"]))

    # a state is (words, per-word reply rows); rows are cached so a placement
    # recomputes only the ONE word it touched
    blank = tuple(tuple([None] * L) for _ in range(nw))
    rows0 = [pattern_row(BLANK * L, pool_codes) for _ in range(nw)]
    beam = [(blank, rows0)]
    fh = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        fh = open(a["out"], "w")
        fh.write("# greedy letter-by-letter build (see math/greedybuild.py)\n")
        fh.write("# settings pool=%s words=%d topk=%d answers=%d\n"
                 % (a["pool"], nw, a["topk"], len(answers)))
        fh.write(COLUMNS + "\n")

    t0 = time.time()
    for step in range(nw * L):
        seen, cand = set(), []
        for words, rows in beam:
            for wi in range(nw):
                for j in range(L):
                    if words[wi][j] is not None:
                        continue
                    for c in "abcdefghijklmnopqrstuvwxyz":
                        nwords = list(list(w) for w in words)
                        nwords[wi][j] = c
                        if not completions(pool_codes, nwords[wi]).any():
                            continue
                        keyw = tuple(tuple(w) for w in nwords)
                        if keyw in seen:
                            continue
                        seen.add(keyw)
                        nrows = list(rows)
                        nrows[wi] = pattern_row(spell(nwords[wi]), pool_codes)
                        ctx = (full, pool_codes, cols, ans_pool_idx, nrows)
                        uns, ssq = score(keyw, ctx)
                        cand.append((uns, ssq, keyw, nrows, (c, wi, j)))
        if not cand:
            raise SystemExit("step %d: no legal placement remains" % (step + 1))
        cand.sort(key=lambda x: (x[0], x[1], "".join(spell(w) for w in x[2])))
        beam = [(c[2], c[3]) for c in cand[:a["topk"]]]
        best = cand[0]
        opening = " ".join(spell(w) for w in best[2])
        if fh:
            fh.write("%d,%s,%d,%d,%s,%d,%d\n"
                     % (step + 1, opening, best[0], best[1],
                        best[4][0], best[4][1], best[4][2]))
            fh.flush()
        if a["progress"] and (step + 1) % a["progress"] == 0:
            print("  %2d/%d  %-34s unsolved=%5d  ssq=%9d  (%.0fs, %d examined)"
                  % (step + 1, nw * L, opening, best[0], best[1],
                     time.time() - t0, len(cand)), flush=True)
    if fh:
        fh.close()
    print("\nopening: %s" % " ".join(spell(w) for w in beam[0][0]))
    print("  unsolved %d of %d answers" % (cand[0][0], len(answers)))
    if a["out"]:
        print("wrote %s" % a["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
