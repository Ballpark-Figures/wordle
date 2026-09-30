"""The answers left after a fixed line of play — one group of an opener's tree.

    python3 tools/subgroup_answers.py --path first:30 --out FILE

`--path` is guesses and the pattern codes they got, alternating, colon-separated
(`first:30` = FIRST scored 30, i.e. - Y - Y -; `first:30:plane:81` goes a level
deeper). Codes are math/wordle.py pattern integers, POSITION 0 MOST SIGNIFICANT.
Writes, one per line in mystery.txt's (alphabetical) order, every answer that
gives every listed guess its listed code -- the answer list
`solver/run-subgroup-tree.sh` hands the solver.

Checks itself from the strings: each kept answer is re-scored with
`wordle.pattern`, and the list must be non-empty.
"""
import argparse
import os
import sys

MATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MATH)
import wordle  # noqa: E402

WORDS = os.path.join(MATH, "data", "shared", "words")


def parse_path(text):
    parts = text.split(":")
    if len(parts) % 2:
        raise SystemExit(f"--path {text!r}: want guess:code pairs")
    return [(parts[i], int(parts[i + 1])) for i in range(0, len(parts), 2)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    steps = parse_path(args.path)
    answers = [w.strip() for w in open(os.path.join(WORDS, "mystery.txt")) if w.strip()]
    guesses = set(w.strip() for w in open(os.path.join(WORDS, "guess.txt")) if w.strip())
    for g, _ in steps:
        if g not in guesses:
            raise SystemExit(f"{g!r} is not a legal guess")
    kept = [a for a in answers if all(wordle.pattern(g, a) == c for g, c in steps)]
    if not kept:
        raise SystemExit(f"no answer follows {args.path}")
    with open(args.out, "w") as f:
        f.write("\n".join(kept) + "\n")
    print(f"{args.path}: {len(kept)} answers -> {args.out}")


if __name__ == "__main__":
    main()
