"""Longest antiwordle stall against a KNOWN answer, per answer word.

THE QUESTION.  Once the candidate set has collapsed to one word you know the
answer, and every guess's feedback is already determined — so the game stops
being probabilistic and becomes: how long can you keep playing LEGAL words that
are not the answer, before the answer is the only legal word left?  That is a
longest path over the constraint DAG (see `antiwordle.py`), and this tool
computes it exactly, per answer.

WHAT THE NUMBER IS, precisely: the total guesses the endgame lasts, INCLUDING the
forced final play of the answer, starting from the state named by `--after`
(default: an empty constraint, i.e. the whole game played clairvoyantly).  It is
an EXACT maximum, not a bound — there is no depth cap anywhere in this search,
because there is no depth cap in antiwordle.

WHAT IT IS NOT.  This is the |S| = 1 endgame ONLY.  The real game's opening is a
max-expectimax over an unknown answer, and a player who does not yet know the word
cannot in general achieve these lengths.  So a number here is an UPPER BOUND on
what that answer can extract from real play, never the game's value.  Do not
average these and call it "expected guesses in antiwordle".

RESULTS ARE FOR OUR WORD LISTS, which are not verified to be antiwordle.com's,
and the stalling words are exactly the junk most likely to differ between them.

    bash solver/run-antiwordle-stall.sh              # the sweep, via its wrapper
    python3 tools/antiwordle_stall.py --answer crane --no-out     # one answer

Answers are visited in word-list order.  Unlike a best-of search, order decides
nothing here: every answer is solved independently and exactly, so a prefix
(`--limit`) is a random-ish sample of the same population, not a biased one.
"""
import argparse
import csv
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from antiwordle import TRITS, GuessSpace, StallSearch, cons_none, step
from build_patterns import load_patterns
from wordle import load_words

FIELDS = ["answer", "status", "guesses", "nodes", "edges", "secs", "line"]


class NodeLimit(Exception):
    """Raised to abandon one answer that outran --max-nodes."""


class LimitedSearch(StallSearch):
    """StallSearch that gives up rather than silently running forever.

    An abandoned answer reports NO NUMBER (status `aborted`): a partial longest
    path is a lower bound, and a lower bound written in the column where an exact
    maximum goes is exactly how a bound gets quoted as a result later.
    """

    def __init__(self, *a, max_nodes=0, **kw):
        super().__init__(*a, **kw)
        self.max_nodes = max_nodes

    def value(self, cons, pool=None):
        if self.max_nodes and self.nodes > self.max_nodes:
            raise NodeLimit
        return super().value(cons, pool)


def solve_one(space, PAT, answers, answer, after, max_nodes):
    """(status, guesses, line, nodes, edges, secs) for one answer word."""
    ai = answers.index(answer)
    col = np.asarray(PAT[:, ai])
    gi = space.index[answer]

    cons = cons_none(space.word_len)
    for w in after:                       # replay a prefix of real play, if given
        wi = space.index[w]
        cons = step(cons, space.letter_tuples[wi], TRITS[int(col[wi])])

    search = LimitedSearch(space, col, gi, max_nodes=max_nodes)
    t0 = time.time()
    try:
        total = search.value(cons)
        line = search.line(cons)
        status = "ok"
    except NodeLimit:
        total, line, status = None, [], "aborted"
    return status, total, line, search.nodes, search.edges, time.time() - t0


def load_done(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, newline="") as fh:
        return {r["answer"]: r for r in csv.DictReader(fh)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="CSV to append rows to, one per answer")
    ap.add_argument("--no-out", action="store_true",
                    help="print only, save nothing (must be explicit)")
    ap.add_argument("--answer", action="append", default=[],
                    help="solve only this answer (repeatable)")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many answers")
    ap.add_argument("--after", default="",
                    help="space-separated words already played, to start from a "
                         "mid-game state instead of an empty constraint")
    ap.add_argument("--guess-list", default="guess", choices=["guess", "mystery"],
                    help="which words are legal to PLAY (default: all 12972)")
    ap.add_argument("--max-nodes", type=int, default=0,
                    help="abandon an answer past this many expanded states, "
                         "reporting no number for it (0 = no limit)")
    args = ap.parse_args()

    if not args.out and not args.no_out:
        ap.error("give --out FILE, or --no-out to save nothing.\n"
                 "A run with nowhere to put its answer is a run thrown away; "
                 "prefer the wrapper, solver/run-antiwordle-stall.sh.")
    if args.out and args.no_out:
        ap.error("--out and --no-out are mutually exclusive")

    answers = load_words("mystery")
    space = GuessSpace(load_words(args.guess_list))
    PAT = load_patterns()
    after = args.after.split()

    todo = args.answer or answers
    unknown = [w for w in todo if w not in answers]
    if unknown:
        raise SystemExit("not answer words: " + " ".join(unknown))
    bad = [w for w in after if w not in space.index]
    if bad:
        raise SystemExit("not legal guesses: " + " ".join(bad))

    done = load_done(args.out)
    todo = [w for w in todo if w not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"answers {len(todo)} to solve ({len(done)} already in the CSV), "
          f"guess list {args.guess_list} ({space.n} words)"
          + (f", after {' '.join(after)}" if after else ""), flush=True)

    fh = writer = None
    if args.out:
        fresh = not os.path.exists(args.out)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        fh = open(args.out, "a", newline="")
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if fresh:
            writer.writeheader()

    t_start = time.time()
    for k, answer in enumerate(todo, 1):
        status, total, line, nodes, edges, secs = solve_one(
            space, PAT, answers, answer, after, args.max_nodes)
        shown = total if status == "ok" else status.upper()
        print(f"[{k}/{len(todo)}] {answer} = {shown}"
              f"  nodes={nodes} edges={edges} {secs:.2f}s"
              f"  {' '.join(line)}", flush=True)
        if writer:
            writer.writerow({"answer": answer, "status": status,
                             "guesses": "" if total is None else total,
                             "nodes": nodes, "edges": edges,
                             "secs": f"{secs:.3f}", "line": " ".join(line)})
            fh.flush()
    if fh:
        fh.close()
    print(f"done: {len(todo)} answers in {time.time() - t_start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
