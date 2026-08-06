"""First real output: rank opening guesses by how well they split the answers.

For each guess, the pattern matrix row PAT[g] partitions the 2315 answers into
buckets by feedback. Two standard scores (both read straight off the matrix):

  * entropy  = -sum p log2 p   (higher = more informative opener)
  * expected_remaining = sum n_bucket^2 / N   (lower = better; expected size of
    the surviving candidate set after this guess)

This is the fast rebuild of the old sortedGuesses / biggestSplit / maxSpread
family. NOTE: this is an INFORMATION heuristic for a single guess, not the full
optimal-tree solve — that comes later.

Run:  python rank_openers.py            # prints the top openers, both metrics
"""

import numpy as np

from wordle import load_words, N_PATTERNS
from build_patterns import load_patterns


def rank():
    pat = load_patterns()                       # (n_g, n_a) uint8, mmap
    guesses = load_words("guess")
    n_a = pat.shape[1]

    entropy = np.empty(pat.shape[0])
    exp_remaining = np.empty(pat.shape[0])
    for i in range(pat.shape[0]):
        counts = np.bincount(pat[i], minlength=N_PATTERNS).astype(np.float64)
        p = counts[counts > 0] / n_a
        entropy[i] = -(p * np.log2(p)).sum()
        exp_remaining[i] = (counts ** 2).sum() / n_a

    order_e = np.argsort(-entropy)
    order_r = np.argsort(exp_remaining)
    print("top 15 by entropy (bits):")
    for i in order_e[:15]:
        print(f"  {guesses[i]}  {entropy[i]:.4f}  exp_rem={exp_remaining[i]:.1f}")
    print("\ntop 15 by expected remaining candidates:")
    for i in order_r[:15]:
        print(f"  {guesses[i]}  {exp_remaining[i]:.1f}  entropy={entropy[i]:.4f}")
    return entropy, exp_remaining


if __name__ == "__main__":
    rank()
