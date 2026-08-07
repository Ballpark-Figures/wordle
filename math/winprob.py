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
import json
import multiprocessing as mp
import os
import pickle
import time
from pathlib import Path

import numpy as np

from wordle import load_words, to_codes, pattern_row, ALL_GREEN, N_PATTERNS, decode
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
        # (12972, 5) letter codes for the guess words -- lets hard mode split the
        # legal-guess set by pattern(played_guess, legal_word) via pattern_row.
        self.guess_codes = to_codes(self.guesses)
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
        self._hits = 0                                  # memo exact hits (transposition reuse)
        self._lbhits = 0                                # alpha-beta lower-bound prunes on revisit
        self._ckpt_path = None                          # if set, _beat periodically saves the memo
        self._ckpt_interval = 3600.0
        self._last_ckpt = 0.0
        self._r2_closed = True                          # closed-form r==2 (off = validate vs recursion)
        self._dedup = True                              # regular-mode partition dedup (off = validate)

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
        tot = self._calls + self._hits + self._lbhits
        hpct = 100.0 * (self._hits + self._lbhits) / tot if tot else 0.0
        print(f"    [n={self._n}] {frac}{nst:,} states | P<= so far {self._best_p:.4f} "
              f"| {rate:,.0f} calls/s | hits {hpct:.0f}% ({self._hits:,} memo / {self._lbhits:,} lb) "
              f"| {now - self._t0:.0f}s", flush=True)
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

    def _order(self, rows, S):
        """Move ordering over `rows` (guess indices) against candidate set S.
        Returns (sub, distinct, order): the (len(rows) x |S|) pattern block, the
        distinct-pattern count per guess, and an argsort that tries the best
        splitters first (more distinct patterns, then smaller worst-case bucket)
        so alpha-beta gets a tight incumbent early. Ordering only -- NOT the
        objective. Vectorized via one offset-bincount over all guesses at once.
        (A sort-based path scaling with |S| was tried for small buckets but ran
        ~2x SLOWER — the single bincount is one C pass, the sort adds 12972 per-row
        sorts + a cumsum + a second bincount. The 243-wide histogram is not the
        bottleneck.)"""
        # Gather (m, |S|) directly. `PAT[rows][:, S]` with rows = all 12972 first
        # copies the WHOLE 30 MB matrix (~4x slower); a plain column slice avoids
        # that, and np.ix_ gathers a genuine row subset without the intermediate.
        if rows.shape[0] == self.PAT.shape[0]:
            sub = self.PAT[:, S]                         # regular: all guesses legal
        else:
            sub = self.PAT[np.ix_(rows, S)]              # hard: legal subset L
        m = sub.shape[0]
        offs = (np.arange(m, dtype=np.int32) * N_PATTERNS)[:, None]
        counts = np.bincount((sub + offs).ravel(),
                             minlength=m * N_PATTERNS).reshape(m, N_PATTERNS)
        distinct = (counts > 0).sum(1)
        worst = counts.max(1)
        order = np.lexsort((worst, -distinct))           # -distinct primary, worst secondary
        return sub, distinct, order

    def _solve_r2(self, sub, distinct, order):
        """Exact (lost, cost, best_pos) for r == 2 in closed form -- no recursion.
        With two turns left, guess g wins `distinct(g)` answers: the all-green word
        now (iff g is a candidate) plus one per other feedback bucket next turn. So
        won(S,2) = D = max distinct-pattern count. Among max-D guesses, one that is
        itself a candidate (has an all-green bucket) wins its own word a turn
        earlier, so cost = 2D - 1 if such a guess exists, else 2D. This kills the
        entire second-to-last recursion layer (the most numerous nodes)."""
        n = sub.shape[1]
        D = int(distinct.max())
        has_ag = (sub == ALL_GREEN).any(axis=1)          # guess is itself a candidate
        ag = bool((has_ag & (distinct == D)).any())      # a max-D guess in S exists?
        lost = float(n - D)
        cost = float(2 * D - 1) if ag else float(2 * D)
        best_pos = -1                                    # first best-ordered guess at D
        for oi in order:                                 # order is -distinct sorted
            if distinct[oi] != D:
                break
            if (not ag) or has_ag[oi]:
                best_pos = int(oi)
                break
        return lost, cost, best_pos

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
            self._hits += 1
            return ex
        lbv = self.lb.get(key)
        if lbv is not None and not self._lex_less(lbv, (bl, bc), eps):
            self._lbhits += 1
            return lbv
        self._beat()

        rows = self._legal_rows(S)
        sub, distinct, order = self._order(rows, S)

        # Closed form (no recursion) when it is provably optimal: always at r==2,
        # and at any r once some guess FULLY separates S (max distinct == n) --
        # then everything is won and cost = 2n-1 (separator in S) / 2n is minimal
        # regardless of remaining turns, so deeper budget can't do better.
        if (r == 2 or int(distinct.max()) == n) and self._r2_closed:
            lost, cost, bp = self._solve_r2(sub, distinct, order)
            self.memo[key] = (lost, cost)
            if bp >= 0:
                self.move[key] = int(rows[bp])
            return lost, cost

        is_root = n == self.n_ans
        best_l, best_c, best_g = bl, bc, -1
        seen = set()                                     # partition dedup (regular mode)
        for rank, oi in enumerate(order):
            if distinct[oi] <= 1:                        # guess doesn't split S -> useless
                continue
            pats = sub[oi]
            if self._dedup:
                # Two guesses with an identical PAT[g,S] vector induce identical
                # buckets -> identical (lost, cost). Evaluate one per distinct
                # vector. Exact in regular mode (value depends only on S's split);
                # NOT applied in hard mode, where g also splits the legal set L.
                sig = pats.tobytes()
                if sig in seen:
                    continue
                seen.add(sig)
            g = int(rows[oi])
            if is_root:                                  # feeds the heartbeat's opener progress
                self._op = (self.guesses[g], rank + 1, order.shape[0])
                self._beat()
            # all-green bucket is the guessed word itself, nonempty iff g is a candidate
            has_ag = np.any(pats == ALL_GREEN)
            acc_l = 0.0
            acc_c = 1.0 if has_ag else 0.0               # the self-win word spends this turn
            pruned = False
            uniq, cnts = np.unique(pats, return_counts=True)
            for bi in np.argsort(-cnts):                 # largest buckets first -> prune sooner
                pv = uniq[bi]
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
                if best_l <= eps and best_c <= eps:      # perfect on BOTH -> can't improve
                    break                                # (never fires for Wordle: won => cost>=1)

        if self._lex_less((best_l, best_c), (bl, bc), eps):
            self.memo[key] = (best_l, best_c)
            self.move[key] = best_g
        elif lbv is None or self._lex_less(lbv, (bl, bc), eps):
            self.lb[key] = (bl, bc)
        return best_l, best_c

    def _solve_hard(self, S, L, r, bl, bc):
        """True (NYT) hard-mode recurrence. Same objective as `_solve`, but the
        legal guesses at this node are exactly `L` = the allowed words still
        CONSISTENT with the clues (a superset of the candidate answers S, since a
        consistent non-answer word is a legal guess too). L is not a function of S
        -- two feedback paths can reach the same S with different L -- so it is
        part of the memo key. Playing guess g and observing pattern p narrows BOTH
        sets: answers to S[PAT[g]==p], legal guesses to L[pattern(g, L)==p]. The
        latter split is computed on the fly with pattern_row over the guess words."""
        n = S.shape[0]
        if n == 0:
            return 0.0, 0.0
        if r <= 0:                          # no turn to submit -> all lost
            return float(n), 0.0
        if n == 1:                          # lone candidate (always legal) -> win, 1 turn
            return 0.0, 1.0
        if r == 1:                          # uniform last turn: any candidate is legal, win 1
            return float(n - 1), 1.0
        if r >= n:                          # slack budget: candidates are always legal to try
            r = n

        eps = self.eps
        key = (S.tobytes(), L.tobytes(), r)
        ex = self.memo.get(key)
        if ex is not None:
            self._hits += 1
            return ex
        lbv = self.lb.get(key)
        if lbv is not None and not self._lex_less(lbv, (bl, bc), eps):
            self._lbhits += 1
            return lbv
        self._beat()

        sub, distinct, order = self._order(L, S)         # legal guesses vs S
        # r==2, or any r where a legal guess fully separates S (see _solve). The
        # separator and each isolated answer are all consistent candidates, hence
        # legal in hard mode too, so the same closed form and cost apply.
        if (r == 2 or int(distinct.max()) == n) and self._r2_closed:
            lost, cost, bp = self._solve_r2(sub, distinct, order)
            self.memo[key] = (lost, cost)
            if bp >= 0:
                self.move[key] = int(L[bp])
            return lost, cost

        is_root = n == self.n_ans and L.shape[0] == self.PAT.shape[0]
        best_l, best_c, best_g = bl, bc, -1
        for rank, oi in enumerate(order):
            g = int(L[oi])
            if distinct[oi] <= 1:                        # doesn't split S -> useless
                continue
            if is_root:
                self._op = (self.guesses[g], rank + 1, order.shape[0])
                self._beat()
            pats = sub[oi]                               # PAT[g, S]
            has_ag = np.any(pats == ALL_GREEN)
            # The child legal-set split is only consulted when a child recurses on
            # L (budget r-1 >= 2). At the r==2 frontier children resolve at r==1
            # without touching L, so skip the pattern_row entirely.
            pg = pattern_row(self.guesses[g], self.guess_codes[L]) if r >= 3 else None
            acc_l = 0.0
            acc_c = 1.0 if has_ag else 0.0
            pruned = False
            uniq, cnts = np.unique(pats, return_counts=True)
            for bi in np.argsort(-cnts):                 # largest buckets first -> prune sooner
                pv = uniq[bi]
                if pv == ALL_GREEN:
                    continue
                grp = S[pats == pv]
                Lp = L[pg == pv] if pg is not None else L   # unused when r-1 < 2
                cl, cc = self._solve_hard(grp, Lp, r - 1, best_l - acc_l, INF)
                acc_l += cl
                acc_c += cc + (grp.shape[0] - cl)
                if not self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                    pruned = True
                    break
            if not pruned and self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                best_l, best_c, best_g = acc_l, acc_c, g
                if is_root:
                    self._best_p = (self.n_ans - best_l) / self.n_ans
                if best_l <= eps and best_c <= eps:      # perfect on BOTH -> can't improve
                    break                                # (never fires for Wordle: won => cost>=1)

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
        rk = n if n < self.n_ans else self.n_ans         # r is capped at |S| inside
        if self.mode == "hard":
            L = np.arange(self.PAT.shape[0], dtype=np.int32)   # all guesses legal at root
            lost, cost = self._solve_hard(root, L, n, float(self.n_ans) + 1.0, INF)
            g = self.move.get((root.tobytes(), L.tobytes(), rk), -1)
        else:
            lost, cost = self._solve(root, n, float(self.n_ans) + 1.0, INF)
            g = self.move.get((root.tobytes(), rk), -1)
        won = self.n_ans - lost
        p = won / self.n_ans
        e_turns = cost / won if won > self.eps else 0.0
        opener = self.guesses[g] if g >= 0 else "-"
        return p, e_turns, opener

    # --- parallel root sweep ---------------------------------------------

    def _sweep_openers(self, opener_rows, n, init_l, init_c, L=None):
        """Evaluate a SUBSET of root openers at budget n against an initial
        incumbent (init_l, init_c); return the best (lost, cost, opener_row).
        This is exactly the serial root loop restricted to `opener_rows` -- the
        unit of parallelism. Recursion into each opener's buckets uses this
        process's OWN memo (workers don't share one). The incumbent is a valid
        achievable bound, so pruning against it is exact: any opener that can beat
        it is computed exactly; the rest are correctly cut. Hard mode threads the
        legal set L (all guesses at the root) and splits it per opener."""
        S = np.arange(self.n_ans, dtype=np.int32)
        eps = self.eps
        hard = self.mode == "hard"
        best_l, best_c, best_g = init_l, init_c, -1
        for gi in range(int(opener_rows.shape[0])):
            g = int(opener_rows[gi])
            pats = self.PAT[g, S]
            uniq, cnts = np.unique(pats, return_counts=True)
            if uniq.shape[0] <= 1:                       # doesn't split -> useless
                continue
            has_ag = bool(np.any(pats == ALL_GREEN))
            pg = pattern_row(self.guesses[g], self.guess_codes[L]) if hard else None
            acc_l = 0.0
            acc_c = 1.0 if has_ag else 0.0
            pruned = False
            for bi in np.argsort(-cnts):                 # largest buckets first
                pv = uniq[bi]
                if pv == ALL_GREEN:
                    continue
                grp = S[pats == pv]
                if hard:
                    cl, cc = self._solve_hard(grp, L[pg == pv], n - 1, best_l - acc_l, INF)
                else:
                    cl, cc = self._solve(grp, n - 1, best_l - acc_l, INF)
                acc_l += cl
                acc_c += cc + (grp.shape[0] - cl)
                if not self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                    pruned = True
                    break
            if not pruned and self._lex_less((acc_l, acc_c), (best_l, best_c), eps):
                best_l, best_c, best_g = acc_l, acc_c, g
                self._best_p = (self.n_ans - best_l) / self.n_ans
        return float(best_l), float(best_c), int(best_g)

    def solve_root_parallel(self, n, workers=None, seed_k=64, dispatch=1):
        """Same result as solve_root(n), but the ~12972 root openers are swept in
        parallel (both regular and hard mode). Seed a strong incumbent from the top
        `seed_k` openers serially, then hand the rest to a worker pool ONE AT A TIME
        (imap_unordered), each worker pruning against the incumbent with its OWN
        (persistent) memo; take the global best. Exact: every opener that could beat
        the incumbent is evaluated exactly; ties keep the earliest. n<=2 falls back
        to serial (instant). `dispatch` is the IPC batch size (1 = truest per-opener
        progress; raise it to trade a little tracking granularity for less overhead)."""
        if n <= 2:
            return self.solve_root(n)
        root = np.arange(self.n_ans, dtype=np.int32)
        # Hard mode: at the root every allowed word is a legal guess -> L = all.
        L_root = np.arange(self.PAT.shape[0], dtype=np.int32) if self.mode == "hard" else None
        rk = n if n < self.n_ans else self.n_ans
        rkey = (root.tobytes(), L_root.tobytes(), rk) if self.mode == "hard" else (root.tobytes(), rk)
        if rkey in self.memo and rkey in self.move:      # already solved (e.g. resumed) -> skip sweep
            best_l, best_c = self.memo[rkey]
            best_g = self.move[rkey]
            won = self.n_ans - best_l
            p = won / self.n_ans
            e_turns = best_c / won if won > self.eps else 0.0
            if self._verbose:
                print(f"    budget {n} already solved (cached root) -> reused, sweep skipped", flush=True)
            return p, e_turns, (self.guesses[best_g] if best_g >= 0 else "-")
        rows = np.arange(self.PAT.shape[0])
        _, distinct, order = self._order(rows, root)
        openers = rows[order][distinct[order] > 1]       # splitting openers, best first
        workers = workers or max(1, (os.cpu_count() or 2))
        self._n = n
        self._op = ("", 0, 0)
        self._best_p = 0.0

        # Opener-level resume: which openers we've tried + the best so far. (The memo
        # checkpoint barely helps a mid-sweep here, so this is the real resume.)
        sweep_path = (Path(__file__).resolve().parent / "data" / "local" / "winprob"
                      / f"{self.mode}_n{n:02d}.sweep.pkl")
        tried, best_l, best_c, best_g = set(), None, None, -1
        if sweep_path.exists():
            try:
                with open(sweep_path, "rb") as fh:
                    st = pickle.load(fh)
                tried, best_l, best_c, best_g = set(st["tried"]), st["l"], st["c"], st["g"]
            except Exception:
                tried, best_l, best_c, best_g = set(), None, None, -1
        if best_l is None:                               # fresh: seed incumbent from top openers
            k = int(min(seed_k, openers.shape[0]))
            best_l, best_c, best_g = self._sweep_openers(openers[:k], n, float(self.n_ans) + 1.0, INF, L_root)
            tried.update(int(g) for g in openers[:k])
            if self._verbose:
                print(f"    seed: P<= {(self.n_ans - best_l) / self.n_ans:.4f} "
                      f"('{self.guesses[best_g] if best_g >= 0 else '-'}') from top {k}; "
                      f"fanning openers over {workers} workers ({self.mode})", flush=True)
        elif self._verbose:
            print(f"    resuming sweep: {len(tried):,} openers tried, best P<= "
                  f"{(self.n_ans - best_l) / self.n_ans:.4f} "
                  f"('{self.guesses[best_g] if best_g >= 0 else '-'}')", flush=True)

        todo = [int(g) for g in openers.tolist() if int(g) not in tried]
        if todo:
            tasks = [(g, n, best_l, best_c) for g in todo]   # prune against the incumbent
            total = len(tasks)
            ctx = mp.get_context("spawn")
            done = 0
            t0 = last = tsave = time.perf_counter()
            with ctx.Pool(workers, initializer=_init_worker, initargs=(self.mode,)) as pool:
                for (g, l, c, beat) in pool.imap_unordered(_solve_one_opener, tasks, chunksize=dispatch):
                    done += 1
                    tried.add(g)
                    if beat and self._lex_less((l, c), (best_l, best_c), self.eps):
                        best_l, best_c, best_g = l, c, g
                    now = time.perf_counter()
                    if now - tsave >= 10.0:               # periodic resume checkpoint
                        tsave = now
                        with open(str(sweep_path) + ".tmp", "wb") as fh:
                            pickle.dump({"tried": tried, "l": best_l, "c": best_c, "g": best_g}, fh)
                        os.replace(str(sweep_path) + ".tmp", sweep_path)
                    if self._verbose and (now - last >= 2.0 or done == total):
                        last = now
                        eta = (now - t0) / done * (total - done)
                        print(f"    {done:,}/{total:,} openers ({100 * done // total}%) | best P<= "
                              f"{(self.n_ans - best_l) / self.n_ans:.4f} "
                              f"('{self.guesses[best_g] if best_g >= 0 else '-'}') | "
                              f"{now - t0:.0f}s, ~{eta:.0f}s left", flush=True)

        self.memo[rkey] = (best_l, best_c)               # lets build_tree reuse the winner
        self.move[rkey] = best_g
        try:
            sweep_path.unlink()                          # budget done -> drop the resume file
        except OSError:
            pass
        won = self.n_ans - best_l
        p = won / self.n_ans
        e_turns = best_c / won if won > self.eps else 0.0
        opener = self.guesses[best_g] if best_g >= 0 else "-"
        return p, e_turns, opener

    def solve_all_openers(self, n, workers=None, dispatch=1):
        """Evaluate EVERY opener fully (no cross-opener pruning) at budget n, and for
        each save its full optimal tree to gitignored data/local/winprob/trees/, plus
        a committed per-opener summary (opener, p_win, e_turns) to data/shared/. Much
        heavier than the optimal solve (no pruning), but embarrassingly parallel. The
        optimal opener falls out as the best row. Returns (p, e, opener) of the best."""
        if n <= 2:                                       # trivial: one row, still emit outputs
            self.solve_root(n)
        root = np.arange(self.n_ans, dtype=np.int32)
        rows = np.arange(self.PAT.shape[0])
        _, distinct, order = self._order(rows, root)
        openers = rows[order][distinct[order] > 1]
        workers = workers or max(1, (os.cpu_count() or 2))
        data = Path(__file__).resolve().parent / "data"
        tree_dir = data / "local" / "winprob" / "trees" / f"{self.mode}_n{n:02d}"
        shared_dir = data / "shared" / "winprob"
        tree_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)

        # Resume: openers already in the summary CSV are done (their trees exist).
        summary_path = shared_dir / f"{self.mode}_n{n:02d}_openers.csv"
        done_words = set()
        if summary_path.exists():
            for line in summary_path.read_text().splitlines()[1:]:
                if line:
                    done_words.add(line.split(",")[0])
        todo = [int(g) for g in openers.tolist() if self.guesses[int(g)] not in done_words]
        if self._verbose and done_words:
            print(f"    resuming: {len(done_words):,} openers done, {len(todo):,} to go", flush=True)

        tasks = [(g, n, str(tree_dir)) for g in todo]
        total = len(tasks)
        ctx = mp.get_context("spawn")
        done = 0
        t0 = last = time.perf_counter()
        # Append each opener's summary row as its worker finishes (so a kill is resumable).
        with open(summary_path, "a") as csv:
            if not done_words:
                csv.write("opener,p_win,e_turns_given_won\n")
            with ctx.Pool(workers, initializer=_init_worker, initargs=(self.mode,)) as pool:
                for (g, l, c) in pool.imap_unordered(_eval_opener_full, tasks, chunksize=dispatch):
                    won = self.n_ans - l
                    csv.write(f"{self.guesses[g]},{won / self.n_ans:.6f},"
                              f"{c / won if won > self.eps else 0.0:.6f}\n")
                    csv.flush()
                    done += 1
                    now = time.perf_counter()
                    if self._verbose and (now - last >= 2.0 or done == total):
                        last = now
                        eta = (now - t0) / done * (total - done) if done else 0.0
                        print(f"    {done:,}/{total:,} openers ({100 * done // max(total, 1)}%) | "
                              f"{now - t0:.0f}s, ~{eta:.0f}s left", flush=True)

        # Sort the (complete) CSV best-first: P desc, then E asc.
        rows = summary_path.read_text().splitlines()
        body = sorted((r for r in rows[1:] if r),
                      key=lambda r: (-float(r.split(",")[1]), float(r.split(",")[2])))
        summary_path.write_text(rows[0] + "\n" + "\n".join(body) + "\n")
        best = body[0].split(",")
        return float(best[1]), float(best[2]), best[0]

    # --- optimal decision tree (committed to shared/) ---------------------

    def build_tree(self, S, r, n0, L=None):
        """Nested optimal decision tree for (S, r); a guess made here is turn
        n0-r+1. Leaves: {"word","turn"} (a won answer) or {"lost":[...]} (can't be
        won within the budget). Internal: {"guess","turn","n","branches": {pattern
        -> subtree}}. Follows the solved optimal move at each node (memoized), so
        it's fast once solve_root(n) has run; fully-separable/last-turn nodes are
        expanded directly without re-solving."""
        k = int(S.shape[0])
        turn = int(n0 - r + 1)
        if k == 0:
            return {}
        if r <= 0:                                       # no turn left to submit
            return {"lost": [self.answers[int(i)] for i in S]}
        if k == 1:                                       # submit it, won this turn
            return {"word": self.answers[int(S[0])], "turn": turn}
        if r == 1:                                       # uniform last turn: win any one
            g = int(self.ans2grow[int(S[0])])
        elif self.mode == "hard":
            self._solve_hard(S, L, r, float(k) + 1.0, INF)   # ensure exact + move recorded
            g = self.move.get((S.tobytes(), L.tobytes(), min(r, k)), -1)
        else:
            self._solve(S, r, float(k) + 1.0, INF)
            g = self.move.get((S.tobytes(), min(r, k)), -1)
        if g < 0:                                        # safety net (never on an optimal path)
            return {"lost": [self.answers[int(i)] for i in S]}
        pats = self.PAT[g, S]
        pg = pattern_row(self.guesses[g], self.guess_codes[L]) if (self.mode == "hard" and r > 1) else None
        branches = {}
        for pv in np.unique(pats):
            grp = S[pats == pv]
            tmpl = _pattern_str(int(pv))
            if int(pv) == ALL_GREEN:                     # guessed the answer -> won now
                branches[tmpl] = {"word": self.guesses[g], "turn": turn}
            else:
                Lp = (L[pg == pv] if pg is not None else L) if self.mode == "hard" else None
                branches[tmpl] = self.build_tree(grp, r - 1, n0, Lp)
        return {"guess": self.guesses[g], "turn": turn, "n": k, "branches": branches}

    def build_tree_for_opener(self, g, n, L=None):
        """Tree that FORCES opener g at the root, then plays optimally. Requires g's
        subtree to already be solved (memoized) in this process. Same node format as
        build_tree; turn 1 is the forced guess g."""
        root = np.arange(self.n_ans, dtype=np.int32)
        pats = self.PAT[g, root]
        pg = pattern_row(self.guesses[g], self.guess_codes[L]) if self.mode == "hard" else None
        branches = {}
        for pv in np.unique(pats):
            grp = root[pats == pv]
            tmpl = _pattern_str(int(pv))
            if int(pv) == ALL_GREEN:
                branches[tmpl] = {"word": self.guesses[g], "turn": 1}
            else:
                Lp = (L[pg == pv] if pg is not None else L) if self.mode == "hard" else None
                branches[tmpl] = self.build_tree(grp, n - 1, n, Lp)   # optimal continuation
        return {"guess": self.guesses[g], "turn": 1, "n": int(self.n_ans), "branches": branches}

    def save_tree(self, n, path, *, p_win, e_turns, opener):
        """Write the optimal decision tree for budget n to a self-describing,
        committed JSON (data/shared/winprob/). Atomic (tmp + replace)."""
        root = np.arange(self.n_ans, dtype=np.int32)
        L = np.arange(self.PAT.shape[0], dtype=np.int32) if self.mode == "hard" else None
        payload = {
            "mode": self.mode,
            "n": n,
            "answers": self.n_ans,
            "guesses": len(self.guesses),
            "distribution": "uniform",
            "objective": "max P(finish within n turns); tie-break min E[turns|won]",
            "p_win": p_win,
            "e_turns_given_won": e_turns,
            "opener": opener,
            "tree": self.build_tree(root, n, n, L),
        }
        tmp = str(path) + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)


# --- process-pool worker (module level so it is picklable) ----------------

_WORKER = None                              # one WinProbSolver per worker process


def _init_worker(mode):
    global _WORKER
    _WORKER = WinProbSolver(mode)
    _WORKER._verbose = False


def _solve_one_opener(args):
    g, n, init_l, init_c = args
    # Root legal set is deterministic (all guesses), so reconstruct it per worker.
    L = np.arange(_WORKER.PAT.shape[0], dtype=np.int32) if _WORKER.mode == "hard" else None
    l, c, bg = _WORKER._sweep_openers(np.array([g], dtype=np.int32), n, init_l, init_c, L)
    # Always report g (so the master can mark it tried for resume); (l, c) are this
    # opener's exact value only when it beat the incumbent (bg == g), else the bound.
    return (g, l, c, bg == g)


def _eval_opener_full(args):
    """Solve one opener FULLY (no pruning), write its tree JSON, return (g, lost, cost).
    Clears the worker memo afterward so peak memory stays at one opener's subtree."""
    g, n, tree_dir = args
    wp = _WORKER
    L = np.arange(wp.PAT.shape[0], dtype=np.int32) if wp.mode == "hard" else None
    lost, cost, _ = wp._sweep_openers(np.array([g], dtype=np.int32), n, INF, INF, L)
    won = wp.n_ans - lost
    payload = {
        "mode": wp.mode, "n": n, "opener": wp.guesses[g],
        "p_win": won / wp.n_ans,
        "e_turns_given_won": (cost / won if won > wp.eps else 0.0),
        "tree": wp.build_tree_for_opener(g, n, L),
    }
    path = os.path.join(tree_dir, wp.guesses[g] + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh)
    os.replace(tmp, path)
    wp.memo.clear(); wp.lb.clear(); wp.move.clear()      # bound memory to one opener
    return (g, float(lost), float(cost))


def _main():
    import sys
    args = sys.argv[1:]
    mode = "hard" if "--hard" in args else "regular"
    fresh = "--fresh" in args                            # ignore any saved memo, start cold
    all_openers = "--all-openers" in args                # evaluate EVERY opener (summary + trees)
    pos = [a for a in args if not a.startswith("--")]
    N = int(pos[0]) if pos else 6

    wp = WinProbSolver(mode=mode)
    wp._t0 = wp._last_beat = wp._last_ckpt = time.perf_counter()

    # Committed deliverable (optimal trees) -> data/shared/winprob/, synced via git.
    # The resume memo is a regenerable checkpoint -> gitignored data/local/winprob/.
    data = Path(__file__).resolve().parent / "data"
    shared_dir = data / "shared" / "winprob"
    local_dir = data / "local" / "winprob"
    shared_dir.mkdir(parents=True, exist_ok=True)
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

    if all_openers:
        # EVERY opener: per-opener summary (committed) + full trees (gitignored local).
        # No cross-opener pruning, so this is far heavier than the optimal solve.
        print("--all-openers: evaluating EVERY opener (summary -> shared/, trees -> local/)")
        print(f"{'n':>3}  {'best P(win<=n)':>14}  {'E[turns|won]':>13}  {'opener':>7}")
        for n in range(1, N + 1):
            t = time.perf_counter()
            p, em, opener = wp.solve_all_openers(n)
            print(f"{n:>3}  {p:>14.5f}  {em:>13.4f}  {opener:>7}   "
                  f"[+{time.perf_counter() - t:.1f}s]", flush=True)
            print(f"     wrote {mode}_n{n:02d}_openers.csv (summary) + "
                  f"trees/{mode}_n{n:02d}/*.json", flush=True)
        return

    print(f"{'n':>3}  {'P(win<=n)':>10}  {'E[turns|won]':>13}  {'opener':>7}")
    for n in range(1, N + 1):
        t = time.perf_counter()
        p, em, opener = wp.solve_root_parallel(n)        # fans root openers over workers (both modes)
        print(f"{n:>3}  {p:>10.5f}  {em:>13.4f}  {opener:>7}   "
              f"[{len(wp.memo) + len(wp.lb):,} states, +{time.perf_counter() - t:.1f}s]",
              flush=True)
        # Save the TREE first (the committed deliverable), so it survives even if
        # the memo checkpoint below is interrupted.
        tree_path = shared_dir / f"{mode}_n{n:02d}.json"
        wp.save_tree(n, tree_path, p_win=p, e_turns=em, opener=opener)
        wp.save_memo(memo_path)                          # resume checkpoint after each budget
        print(f"     saved tree -> {tree_path.name} + checkpoint (n={n})", flush=True)
        if p >= 1.0 - 1e-9:
            print(f"     (all answers winnable at n={n}; higher n is identical)")
            break


if __name__ == "__main__":
    _main()
