"""Where every answer ends up under a Sea of Greens strategy tree.

    python3 tools/greens_outcomes.py                 # every greens CSV, its best opener
    python3 tools/greens_outcomes.py --depth 6 -k 13000
    python3 tools/greens_outcomes.py --tree PATH.txt.gz --depth 6

A tree file is a STRATEGY: `answer n g1 p1 g2 p2 ... gn`, so every prefix of
(guess, reply) pairs maps to one next guess.  Each of the 2315 answers is played
through it -- replies recomputed FROM THE STRINGS with `wordle.pattern` -- until
it is won or the tree has no next guess for its position.  Outcomes:

    badge          won within the depth, no yellow anywhere
    yellow         a yellow appeared (under --may-lose the strategy stops there;
                   under must-win play continues and these are won with a yellow)
    ran out        still yellow-free, all `depth` guesses spent, not won
    abandoned      still yellow-free with guesses left, but the tree has no next
                   guess: the solver found no badge reachable from that position
                   and wrote nothing for it.  NOT a loss the rules imposed -- the
                   strategy simply has no plan there.

Under must-win the tree covers every answer, so `yellow` splits into won/lost and
nothing is abandoned.

GATE, always on: every tree line's recorded replies must equal `wordle.pattern`
from the strings, the tree must be one strategy (one next guess per prefix), and
the badge count must equal the `badges` column the solver wrote.
"""
import argparse
import csv
import glob
import gzip
import os
import re
import sys

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MATH)
from wordle import all_green, pattern  # noqa: E402

GREENS = os.path.join(MATH, "data", "shared", "greens")
TRIT = {"b": 0, "y": 1, "g": 2}


def code_of(s):
    c = 0
    for ch in s:
        c = c * 3 + TRIT[ch]
    return c


def has_yellow(code):
    while code:
        if code % 3 == 1:
            return True
        code //= 3
    return False


def load_tree(path):
    nxt = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            tok = line.split()
            ans, seq = tok[0], tok[2:]
            guesses, reps = seq[0::2], seq[1::2]
            prefix = ()
            for i, g in enumerate(guesses):
                prev = nxt.setdefault(prefix, g)
                if prev != g:
                    sys.exit(f"FAIL {path}: two next guesses after {prefix}")
                if i < len(reps):
                    rc = code_of(reps[i])
                    if rc != pattern(g, ans):
                        sys.exit(f"FAIL {path}: {ans} recorded {reps[i]} for {g}")
                    prefix += ((g, rc),)
            if guesses[-1] != ans:
                sys.exit(f"FAIL {path}: line for {ans} ends on {guesses[-1]}")
    return nxt


def classify(nxt, answers, depth):
    win = all_green()
    out = {"badge": 0, "yellow_won": 0, "yellow_stop": 0, "yellow_lost": 0,
           "ran_out": 0, "abandoned": 0}
    for a in answers:
        prefix, yellow, t = (), False, 0
        while True:
            g = nxt.get(prefix)
            if g is None or t == depth:
                if yellow:
                    out["yellow_stop" if g is None and t < depth else "yellow_lost"] += 1
                else:
                    out["ran_out" if t == depth else "abandoned"] += 1
                break
            t += 1
            p = pattern(g, a)
            if p == win:
                out["yellow_won" if yellow else "badge"] += 1
                break
            yellow = yellow or has_yellow(p)
            prefix += ((g, p),)
    return out


def best_row(csv_path):
    with open(csv_path) as f:
        head = f.readline()
        if not head.startswith("#"):        # an unstamped file: no objective line
            f.seek(0)
            head = ""
        rows = [r for r in csv.DictReader(f) if r["status"] == "exact"]
    if not rows:
        return head, None
    return head, max(rows, key=lambda r: int(r["badges"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int)
    ap.add_argument("-k", "--topk", type=int)
    ap.add_argument("--tree")
    args = ap.parse_args()

    with open(os.path.join(MATH, "data", "shared", "words", "mystery.txt")) as f:
        answers = [w.strip() for w in f if w.strip()]

    jobs = []
    if args.tree:
        if args.depth is None:
            sys.exit("--tree needs --depth")
        jobs.append((os.path.basename(args.tree), args.tree, args.depth, None))
    else:
        for p in sorted(glob.glob(os.path.join(GREENS, "best_opener_d*_k*.csv"))):
            stem = os.path.basename(p)[len("best_opener_"):-4]
            m = re.match(r"d(\d+)_k(\d+)(_mustwin)?$", stem)
            d, k = int(m.group(1)), int(m.group(2))
            if args.depth is not None and d != args.depth:
                continue
            if args.topk is not None and k != args.topk:
                continue
            head, row = best_row(p)
            if row is None:
                continue
            tree = os.path.join(GREENS, f"trees_{stem}", row["word"] + ".txt.gz")
            if not os.path.exists(tree):
                print(f"{stem}: no tree for {row['word']}, skipped")
                continue
            jobs.append((stem, tree, d, (row["word"], int(row["badges"]), head)))
        jobs.sort(key=lambda j: (re.sub(r"_k\d+", "", j[0]),
                                 int(re.search(r"_k(\d+)", j[0]).group(1))))

    print(f"{'settings':22} {'opener':7} {'badge':>6} {'yellow':>7} "
          f"{'ran out':>8} {'abandoned':>9}   (of {len(answers)}; must-win: yellow = won/lost)")
    for stem, tree, d, meta in jobs:
        o = classify(load_tree(tree), answers, d)
        if meta is not None and o["badge"] != meta[1]:
            sys.exit(f"FAIL {stem}: replay gives {o['badge']} badges, CSV says {meta[1]}")
        mustwin = stem.endswith("_mustwin")
        yel = (f"{o['yellow_won']}/{o['yellow_lost'] + o['yellow_stop']}" if mustwin
               else str(o["yellow_stop"] + o["yellow_won"] + o["yellow_lost"]))
        pct = lambda n: f"{100 * n / len(answers):5.1f}%"
        print(f"{stem:22} {meta[0] if meta else '-':7} {o['badge']:>6} {yel:>7} "
              f"{o['ran_out']:>8} {o['abandoned']:>9}   "
              f"badge {pct(o['badge'])}  ran out {pct(o['ran_out'])}  "
              f"abandoned {pct(o['abandoned'])}")


if __name__ == "__main__":
    main()
