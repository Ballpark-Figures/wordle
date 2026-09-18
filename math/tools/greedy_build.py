"""Build an opening letter by letter.  math/greedybuild.py states the rule.

    bash solver/run-greedy-build.sh --search branch -k 2
    bash solver/run-greedy-build.sh --search beam   -k 2

TWO SEARCHES OVER ONE CONSTRUCTION, and `--search` is required because they are
different questions, not two speeds of one:

  branch  RECURSE INTO THE K BEST placements at every step and keep the best
          opening any of them reaches.  This is what `--topk` means everywhere
          else in this repo (strturns, greens, wturns, mmturns, ultraturns,
          secondexact all say it).  K=1 is the plain greedy and IS the leftmost
          path of the K=2 tree, so a wider K contains a narrower one BY
          CONSTRUCTION and can never return worse.  Cost is exponential in the
          number of placements, tamed only by memoisation.

  beam    Carry K partial openings forward, expand them all, keep K.  Cost is
          LINEAR in K, which is the whole reason to want it -- but a beam
          replaces its states each step rather than nesting them, so plain
          top-K selection is NOT monotone in K: slot 1's best child can rank
          third once slot 2's children join the pool, and the K=1 trajectory is
          evicted.  MEASURED at `-n 8`: k=2 came back WORSE than k=1.  The
          selection here is therefore NESTED -- slot i is filled from the
          children of slots 0..i -- which makes beam_K's first K-1 slots
          identical to beam_{K-1} by induction, so wider is never worse.

Exact and deterministic -- no sampling, no seed -- so a re-run reproduces the
file.  The search, K and `--ssq-first` are all part of the question and all land
in the filename.
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

COLUMNS = "found_at,nodes,opening,unsolved,ssq"
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def parse_args(argv):
    a = {"pool": None, "words": None, "topk": None, "out": None, "progress": 1,
         "ssq_first": 0, "search": None, "max_nodes": 0}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k in ("k", "topk"):
            k = "topk"
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = (int(v) if k in ("topk", "words", "progress", "ssq_first",
                                "max_nodes") else v)
        i += 2
    if a["pool"] is None:
        raise SystemExit("--pool is required")
    if a["words"] is None:
        raise SystemExit("--words N is required: how many words the opening has")
    if a["topk"] is None:
        raise SystemExit("--topk K is required; K=1 is the plain greedy")
    if a["search"] not in ("branch", "beam"):
        raise SystemExit(
            "--search branch|beam is required.  They are different searches, "
            "not two speeds of one:\n"
            "  branch  recurse into the K best at every step (what --topk means "
            "everywhere else here);\n"
            "          K=1 is contained in K=2, so wider is never worse.  "
            "Exponential in the placements.\n"
            "  beam    carry K states forward, nested selection.  Linear in K.")
    if a["out"] is None:
        raise SystemExit("--out is required (or --no-out).  Use the wrapper: "
                         "bash solver/run-greedy-build.sh")
    return a


class Ctx:
    """Everything the scorer needs that never changes, in one place."""

    def __init__(self, full, pool_codes, cols, ans_pool_idx, nw, L, ssq_first):
        self.full, self.pool_codes, self.cols = full, pool_codes, cols
        self.ans_pool_idx, self.nw, self.L = ans_pool_idx, nw, L
        self.ssq_first = ssq_first

    def ssq_only(self, depth):
        return depth < self.ssq_first

    def rank(self, depth):
        if self.ssq_only(depth):
            return lambda x: (x[1], x[5])
        return lambda x: (x[0], x[1], x[5])

    def full_score(self, words, rows):
        return score(words, (self.full, self.pool_codes, self.cols,
                             self.ans_pool_idx, rows))


def children(words, rows, ctx, depth, seen):
    """Every LEGAL placement from this state, canonicalised and scored.

    ONE definition, shared by both searches -- the legality rule, the
    word-order canonicalisation and the scoring must not exist twice.
    """
    out = []
    ssq_only = ctx.ssq_only(depth)
    for wi in range(ctx.nw):
        for j in range(ctx.L):
            if words[wi][j] is not None:
                continue
            for c in LETTERS:
                nwords = [list(w) for w in words]
                nwords[wi][j] = c
                if not completions(ctx.pool_codes, nwords[wi]).any():
                    continue
                # THE WORDS ARE INTERCHANGEABLE, so a state is their MULTISET.
                # Without this canonicalisation the search wastes its width on
                # relabellings of one opening: k=2 once returned `craps until
                # fjord often` where k=1 returned `craps until often fjord`.
                perm = sorted(range(ctx.nw), key=lambda t: spell(nwords[t]))
                keyw = tuple(tuple(nwords[t]) for t in perm)
                if keyw in seen:
                    continue
                seen.add(keyw)
                nrows = [rows[t] for t in perm]
                nrows[perm.index(wi)] = pattern_row(spell(nwords[wi]),
                                                    ctx.pool_codes)
                uns, ssq = score(keyw, (ctx.full, ctx.pool_codes, ctx.cols,
                                        ctx.ans_pool_idx, nrows),
                                 want_unsolved=not ssq_only)
                out.append((uns, ssq, keyw, nrows, (c, wi, j),
                            "".join(spell(w) for w in keyw)))
    return out


def run_branch(state, rows, ctx, k, st):
    """Best opening reachable by recursing into the K best at every step.

    Memoised on the STATE, which is what makes it affordable: the order of
    placements does not matter, so an enormous number of paths converge on the
    same set of assignments and are searched once.
    """
    depth = sum(1 for w in state for c in w if c is not None)
    if depth == ctx.nw * ctx.L:
        uns, ssq = ctx.full_score(state, rows)
        st["leaves"] += 1
        return (uns, ssq, state)
    if state in st["memo"]:
        return st["memo"][state]
    kids = sorted(children(state, rows, ctx, depth, set()), key=ctx.rank(depth))
    best = None
    for kid in kids[:k]:
        st["nodes"] += 1
        if st["cap"] and st["nodes"] > st["cap"]:
            break
        r = run_branch(kid[2], kid[3], ctx, k, st)
        if best is None or r[:2] < best[:2]:
            best = r
        st["report"](st, best)
    st["memo"][state] = best
    return best


def run_beam(state, rows, ctx, k, st):
    """Best opening from a NESTED fixed-width beam (linear in K)."""
    beam = [(state, rows)]
    for step in range(ctx.nw * ctx.L):
        seen, cand = set(), []
        for slot, (w, r) in enumerate(beam):
            for kid in children(w, r, ctx, step, seen):
                cand.append(kid + (slot,))
        if not cand:
            raise SystemExit("step %d: no legal placement remains" % (step + 1))
        cand.sort(key=ctx.rank(step))
        # NESTED, not top-K overall: slot i draws from the children of slots
        # 0..i, so beam_K's first K-1 slots are beam_{K-1} and wider is never
        # worse.  Plain top-K is not monotone -- measured, k=2 beat by k=1.
        chosen, taken = [], set()
        for i in range(min(k, len(cand))):
            for idx, c in enumerate(cand):
                if idx not in taken and c[6] <= i:
                    chosen.append(c)
                    taken.add(idx)
                    break
        beam = [(c[2], c[3]) for c in chosen]
        st["nodes"] += len(cand)
    best = None
    for w, r in beam:
        uns, ssq = ctx.full_score(w, r)
        st["leaves"] += 1
        if best is None or (uns, ssq) < best[:2]:
            best = (uns, ssq, w)
        st["report"](st, best)
    return best


def main(argv):
    a = parse_args(argv)
    guesses, answers = load_words("guess"), load_words("mystery")
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
    ctx = Ctx(full, pool_codes, cols, ans_pool_idx, nw, L, a["ssq_first"])

    print("greedy build: search=%s  %d words  pool %s (%d)  answers %d  k=%d"
          "  ssq-first=%d"
          % (a["search"], nw, a["pool"], len(pool), len(answers), a["topk"],
             a["ssq_first"]))

    fh = None
    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        fh = open(a["out"], "w")
        fh.write("# greedy letter-by-letter build (see math/greedybuild.py)\n")
        fh.write("# settings search=%s pool=%s words=%d topk=%d ssq_first=%d "
                 "answers=%d\n"
                 % (a["search"], a["pool"], nw, a["topk"], a["ssq_first"],
                    len(answers)))
        fh.write(COLUMNS + "\n")

    t0 = time.time()
    st = {"nodes": 0, "leaves": 0, "memo": {}, "best": None,
          "cap": a["max_nodes"], "last": [0.0]}

    def report(st, best):
        """Only a STRICT improvement prints -- a plateau would flood the log."""
        if best is None:
            return
        if st["best"] is None or best[:2] < st["best"][:2]:
            st["best"] = best
            line = " ".join(spell(w) for w in best[2])
            print("[%6.0fs] %-34s unsolved=%5d  ssq=%8d  NEW BEST  "
                  "(%d nodes, %d complete)"
                  % (time.time() - t0, line, best[0], best[1],
                     st["nodes"], st["leaves"]), flush=True)
            if fh:
                fh.write("%.1f,%d,%s,%d,%d\n"
                         % (time.time() - t0, st["nodes"], line,
                            best[0], best[1]))
                fh.flush()
        elif time.time() - st["last"][0] > 30:
            st["last"][0] = time.time()
            print("  ... %d nodes, %d complete openings, %d states memoised "
                  "(%.0fs)" % (st["nodes"], st["leaves"], len(st["memo"]),
                               time.time() - t0), flush=True)

    st["report"] = report
    blank = tuple(tuple([None] * L) for _ in range(nw))
    rows0 = [pattern_row(BLANK * L, pool_codes) for _ in range(nw)]
    go = run_branch if a["search"] == "branch" else run_beam
    best = go(blank, rows0, ctx, a["topk"], st)

    print("\nopening: %s" % " ".join(spell(w) for w in best[2]))
    print("  unsolved %d of %d answers,  ssq %d" % (best[0], len(answers),
                                                    best[1]))
    print("  %d nodes, %d complete openings examined, %d states memoised, %.0fs"
          % (st["nodes"], st["leaves"], len(st["memo"]), time.time() - t0))
    if st["cap"] and st["nodes"] > st["cap"]:
        print("  STOPPED at --max-nodes: this is the best of what was searched")
    if fh:
        fh.close()
    if a["out"]:
        print("wrote %s" % a["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
