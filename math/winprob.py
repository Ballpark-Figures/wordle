"""Max win-probability Wordle within a HARD turn budget n, uniform answers, with a
lowest-E[turns|won] tie-break.  Regular mode (guess ANY allowed word) by default;
a hard-mode flag (legal guesses = current candidate set) is wired in for later.

Ported from hangman/math/winprob.py, adapted to Wordle:
  * A move is a whole-word guess; the precomputed pattern matrix PAT[g, a]
    (build_patterns.py) is the split oracle -- guess g partitions the candidate
    answers by feedback in one indexed read.
  * The budget is TURNS, not misses; submitting the answer costs a turn.
  * The all-green bucket (pattern 242) is an INSTANT win on the current turn, and
    is nonempty only when the guessed word is itself a candidate.

Uniform weighting => mass == count, which buys two exact shortcuts:
  * Last turn: with r == 1 you guess any candidate and win exactly one word
    (cost 1), so we never enumerate guesses at r == 1.
  * Slack budget: once r >= |S| every candidate is winnable, so extra budget
    beyond |S| never helps -> we cap r at |S| as a memo normalization.

Objective, computed as a lexicographic pair via _solve, at state (S candidates,
r turns left) -- we minimize the DUAL `lost` so alpha-beta can prune whole guesses
(maximizing `won` directly is flat near the top and won't prune):
    primary   lost(S,r) = min answers that CANNOT be won within r turns  (= max win)
    tie-break cost(S,r) = min total turns over the WON words, among min-lost play
Recurrence (a won word "spends" this turn, +1):
    choose guess g; split S by PAT[g,.]; the all-green word (iff g in S) wins now.
      lost = min_g  Σ_{p != AG} lost(S_p, r-1)
      cost = [g in S] + Σ_{p != AG} ( won(S_p, r-1) + cost(S_p, r-1) )   for that g

usage:  python math/winprob.py N [--hard]
"""

import hashlib
import os
import pickle
import time
from pathlib import Path

import numpy as np

from wordle import load_words, ALL_GREEN, N_PATTERNS, decode
from build_patterns import load_patterns

INF = float("inf")
MEMO_FORMAT = 1                        # bump if stored (lost, cost) values change meaning


def _pattern_str(code):
    """Encoded pattern -> readable 5-char b/y/g string (grey/yellow/green)."""
    return "".join("byg"[t] for t in decode(code))


class WinProbSolver:
    def __init__(self, mode="regular"):
        assert mode in ("regular", "hard")
        self.mode = mode
        self.answers = load_words("mystery")            # 2315 possible secrets
        self.guesses = load_words("guess")              # 12972 allowed guesses
        self.n_ans = len(self.answers)
        # PAT[g, a] in RAM (30 MB) for fast repeated indexing during search.
        self.PAT = np.asarray(load_patterns())          # (12972, 2315) uint8
        # answer index a -> its row in the guess list (both lists are sorted, and
        # every answer is an allowed guess). Used to (a) map candidates to guess
        # rows in hard mode, and (b) detect the all-green self-guess.
        self.ans2grow = np.searchsorted(self.guesses, self.answers).astype(np.int32)
        # search state
        self.memo = {}                                  # exact (lost, cost) per (S, r)
        self.move = {}                                  # chosen guess row per exact (S, r)
        self.lb = {}                                    # alpha-beta lower bounds
        self.eps = 1e-9
        # progress
        self._verbose = True
        self._calls = 0
        self._t0 = 0.0
        self._last_beat = 0.0
        self._heartbeat = 60.0                          # matches hangman/winprob.py
        self._n = 0
        self._best_p = 0.0
        self._op = ("", 0, 0)                           # root opener being tried: (word, i, total)
        self._ckpt_path = None                          # if set, _beat periodically saves the memo
        self._ckpt_interval = 3600.0
        self._last_ckpt = 0.0

    # --- helpers ----------------------------------------------------------

    def _legal_rows(self, S):
        """Guess rows the strategy may play at candidate set S."""
        if self.mode == "hard":
            return self.ans2grow[S]                      # only words still possible
        return np.arange(self.PAT.shape[0])              # any allowed word

    # --- checkpoint / resume (mirrors hangman/winprob.py) -----------------

    def _signature(self):
        """Identifies which run a memo file belongs to (mode + exact word lists +
        solver format), so a stale/incompatible checkpoint is never reused."""
        h = hashlib.sha256()
        h.update(f"wordle-winprob-v{MEMO_FORMAT}-{self.mode}".encode())
        h.update("\n".join(self.answers).encode())
        h.update("\n".join(self.guesses).encode())
        return h.hexdigest()

    def save_memo(self, path):
        """Persist the exact (lost, cost) memo + chosen moves so a later run can
        resume. Only exact values are stored -- alpha-beta lower bounds are cheap
        to re-derive and would bloat the file. Atomic (tmp + replace)."""
        data = {"sig": self._signature(), "memo": self.memo, "move": self.move}
        tmp = str(path) + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(data, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
        self._last_ckpt = time.perf_counter()

    def load_memo(self, path):
        """Restore the exact memo + moves from a compatible previous run, if any.
        Returns the number of states loaded, or 0."""
        if not os.path.exists(path):
            return 0
        try:
            with open(path, "rb") as fh:
                data = pickle.load(fh)
        except Exception:
            return 0
        if data.get("sig") != self._signature() or "memo" not in data:
            return 0
        self.memo = data["memo"]
        self.move = data.get("move", {})
        return len(self.memo)

    def _beat(self, force=False):
        # Gate on wall-clock, NOT a call-count mask: each node here runs a
        # ~13k-guess ordering pass (tens of ms), so a coarse call mask would take
        # minutes to trip. A perf_counter() per node is negligible vs. node cost.
        self._calls += 1
        if not self._verbose:
            return
        now = time.perf_counter()
        if not force and now - self._last_beat < self._heartbeat:
            return
        self._last_beat = now
        op, oi, ot = self._op
        frac = f"opener '{op}' {oi:,}/{ot:,} | " if ot else ""
        nst = len(self.memo) + len(self.lb)
        rate = self._calls / (now - self._t0) if now > self._t0 else 0.0
        print(f"    [n={self._n}] {frac}{nst:,} states | P<= so far {self._best_p:.4f} "
              f"| {rate:,.0f} calls/s | {now - self._t0:.0f}s", flush=True)
        if self._ckpt_path and now - self._last_ckpt >= self._ckpt_interval:
            self.save_memo(self._ckpt_path)              # periodic mid-solve checkpoint
            print(f"    checkpointed memo -> {self._ckpt_path}", flush=True)

    @staticmethod
    def _lex_less(a, b, eps):
        if a[0] < b[0] - eps:
            return True
        if a[0] > b[0] + eps:
            return False
        return a[1] < b[1] - eps

    # --- core recurrence --------------------------------------------------

    def _solve(self, S, r, bl, bc):
        """Exact (lost, cost) for (S, r) if it beats the lexicographic bound
        (bl, bc); otherwise a valid lower bound >= (bl, bc). Alpha-beta threads
        the remaining allowance into children so a guess that already can't beat
        the incumbent aborts."""
        n = S.shape[0]
        if n == 0:
            return 0.0, 0.0
        if r <= 0:                          # no turn to submit -> all lost
            return float(n), 0.0
        if n == 1:                          # lone candidate: submit now, win, 1 turn
            return 0.0, 1.0
        if r == 1:                          # uniform last turn: win any one, cost 1
            return float(n - 1), 1.0
        if r >= n:                          # slack budget can't help -> normalize
            r = n

        eps = self.eps
        key = (S.tobytes(), r)
        ex = self.memo.get(key)
        if ex is not None:
            return ex
        lbv = self.lb.get(key)
        if lbv is not None and not self._lex_less(lbv, (bl, bc), eps):
            return lbv
        self._beat()

        rows = self._legal_rows(S)
        # Move ordering: try the best-splitting guesses first so alpha-beta gets a
        # tight incumbent early. Ordering only -- NOT the objective. Key per guess:
        # more distinct feedback patterns first, then smaller worst-case bucket.
        # Vectorized: one offset-bincount gives the (n_rows x 243) histogram of
        # feedback patterns for every guess at once -- same keys as the old per-row
        # Python loop, ~10-100x faster (the loop was the solver's floor cost).
        sub = self.PAT[rows][:, S]                       # (m, n) patterns on S, uint8
        m = sub.shape[0]
        offs = (np.arange(m, dtype=np.int32) * N_PATTERNS)[:, None]
        counts = np.bincount((sub + offs).ravel(),
                             minlength=m * N_PATTERNS).reshape(m, N_PATTERNS)
        distinct = (counts > 0).sum(1)
        worst = counts.max(1)
        order = np.lexsort((worst, -distinct))           # -distinct primary, worst secondary

        is_root = n == self.n_ans
        best_l, best_c, best_g = bl, bc, -1
        for rank, oi in enumerate(order):
            g = int(rows[oi])
            if distinct[oi] <= 1:                        # guess doesn't split S -> useless
                continue
            if is_root:                                  # feeds the heartbeat's opener progress
                self._op = (self.guesses[g], rank + 1, order.shape[0])
                self._beat()
            pats = sub[oi]
            # all-green bucket is the guessed word itself, nonempty iff g is a candidate
            has_ag = np.any(pats == ALL_GREEN)
            acc_l = 0.0
            acc_c = 1.0 if has_ag else 0.0               # the self-win word spends this turn
            pruned = False
            for pv in np.unique(pats):
                if pv == ALL_GREEN:
                    continue                             # won now: 0 lost, its +1 in acc_c
                grp = S[pats == pv]
                cl, cc = self._solve(grp, r - 1, best_l - acc_l, INF)
                acc_l += cl
                acc_c += cc + (grp.shape[0] - cl)        # +1 turn for each WON word in child
                if not self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                    pruned = True
                    break
            if not pruned and self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                best_l, best_c, best_g = acc_l, acc_c, g
                if n == self.n_ans:
                    self._best_p = (self.n_ans - best_l) / self.n_ans
                if best_l <= eps:
                    break                                # everything winnable: primary maxed

        if self._lex_less((best_l, best_c), (bl, bc), eps):
            self.memo[key] = (best_l, best_c)
            self.move[key] = best_g
        elif lbv is None or self._lex_less(lbv, (bl, bc), eps):
            self.lb[key] = (bl, bc)
        return best_l, best_c

    # --- top-level API ----------------------------------------------------

    def solve_root(self, n):
        """Solve budget n from the full answer set. Returns
        (p_win, e_turns_given_won, opener_word)."""
        root = np.arange(self.n_ans, dtype=np.int32)
        self._n = n
        self._best_p = 0.0
        self._op = ("", 0, 0)
        lost, cost = self._solve(root, n, float(self.n_ans) + 1.0, INF)
        won = self.n_ans - lost
        p = won / self.n_ans
        e_turns = cost / won if won > self.eps else 0.0
        g = self.move.get((root.tobytes(), n if n < self.n_ans else self.n_ans), -1)
        opener = self.guesses[g] if g >= 0 else "-"
        return p, e_turns, opener


def _main():
    import sys
    args = sys.argv[1:]
    mode = "hard" if "--hard" in args else "regular"
    fresh = "--fresh" in args                            # ignore any saved memo, start cold
    pos = [a for a in args if not a.startswith("--")]
    N = int(pos[0]) if pos else 6

    wp = WinProbSolver(mode=mode)
    wp._t0 = wp._last_beat = wp._last_ckpt = time.perf_counter()

    # Committed final data would go under data/shared/; the resume memo is a
    # regenerable checkpoint, so it lives in gitignored data/local/winprob/.
    local_dir = Path(__file__).resolve().parent / "data" / "local" / "winprob"
    local_dir.mkdir(parents=True, exist_ok=True)
    memo_path = local_dir / f"{mode}.memo.pkl"
    wp._ckpt_path = memo_path                            # enables periodic mid-solve checkpoints

    print(f"Wordle win-prob ({mode} mode, uniform): {wp.n_ans} answers, "
          f"{len(wp.guesses)} guesses")
    if fresh and memo_path.exists():
        memo_path.unlink()
        print(f"--fresh: cleared {memo_path.name}")
    elif not fresh:
        loaded = wp.load_memo(memo_path)
        if loaded:
            print(f"resumed from {memo_path.name}: {loaded:,} states reused")

    print(f"{'n':>3}  {'P(win<=n)':>10}  {'E[turns|won]':>13}  {'opener':>7}")
    for n in range(1, N + 1):
        t = time.perf_counter()
        p, em, opener = wp.solve_root(n)
        print(f"{n:>3}  {p:>10.5f}  {em:>13.4f}  {opener:>7}   "
              f"[{len(wp.memo) + len(wp.lb):,} states, +{time.perf_counter() - t:.1f}s]",
              flush=True)
        wp.save_memo(memo_path)                          # checkpoint after each budget
        print(f"     saved checkpoint (n={n})", flush=True)
        if p >= 1.0 - 1e-9:
            print(f"     (all answers winnable at n={n}; higher n is identical)")
            break


if __name__ == "__main__":
    _main()
