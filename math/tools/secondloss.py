"""Where the EV loss goes: the gap to optimal, split by the opener's grey count.

Run it through the wrapper, which sets --out and tees a log:

    bash solver/run-second-loss.sh --opener spilt \\
        --second-from data/shared/secondword/second_guess_g3.csv

WHAT IT COMPUTES.  For one opener and one second-word table, the gap to optimal
is split by the opener's grey count AND, within each grey bucket, into WHY the
gap is there -- picking the wrong second word versus playing the followup badly.
Three per-answer quantities, per grey bucket g:

    A  optimal play for the SAME opener (the committed tree)
    B  our FORCED second word, then OPTIMAL continuation (capped, same footing)
    C  our second word, then the random followup (the actual strategy, simulated)

and A <= B <= C, so

    word-choice loss(g)  = B - A   (the second word was wrong, played perfectly after)
    followup loss(g)     = C - B   (random tail instead of optimal, given our word)
    contribution(g)      = (answers with g greys / 2315) x (C - A)
                         = word contribution(g) + followup contribution(g)

A comes from the committed tree; C from the stratified simulation; B from a small
exact optimal solve of each residual set after the two guesses (`solve_total`),
run at the SAME depth cap as A so the two are comparable.  Below the table's firing
threshold no word is forced, so B = A there and the whole gap is followup loss.

TWO THINGS ABOUT "OPTIMAL", BOTH OF WHICH MATTER.

  * IT IS THE OPTIMUM FOR THE SAME OPENER, not the best opener.  That is the only
    comparison that decomposes: each grey bucket's gap is then attributable to how
    the strategy plays THAT bucket, with the choice of opener held fixed.  The
    opener's own cost is reported separately as a single number -- `spilt` is
    3.48121 against `salet`'s 3.42117 -- and it does not belong to any bucket.

  * IT IS THE CAPPED OPTIMUM: minimum total guesses SUBJECT TO resolving every
    answer within six, which is what optturns computed and what the committed
    trees are.  The strategy here is UNCAPPED -- play continues past six until the
    word is found.  A capped optimum is >= the unconstrained one, so every gap
    below is a LOWER BOUND on the loss against true optimal play.  Whether the cap
    binds for this opener is open (see the solver section of CLAUDE.md); nothing
    here settles it.

THE ESTIMATOR IS STRATIFIED, and that is why it is per ANSWER rather than a
uniform draw.  Every answer is played the same number of times, so the answer
weights are EXACT (each is 1/2315) and the only randomness left is the strategy's
own coin flips.  The reported standard error is therefore the error on those
flips alone -- the spread BETWEEN answers is the thing being decomposed, not
noise in it -- and it shrinks as `-n` grows even though the answer set never
changes.  A uniform-draw simulation would put sampling noise into the bucket
shares as well, which are exactly known.

THE GATE IS BUILT IN and always runs: the per-answer optimal costs must sum to
the total the committed CSV records for this opener, the tree must cover every
answer exactly once, the grey counts are recomputed FROM THE STRINGS, and the
bucket contributions (both the total and the word+followup split) must sum to the
overall gap.  The load-bearing one for B: forcing each reply's OWN optimal second
move (read from the committed tree) and re-solving the residuals with `solve_total`
must reproduce A exactly, per bucket -- that is what proves the residual solver
computes optimal play.  It exits nonzero rather than reporting.
"""

import gzip
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths  # noqa: E402
from build_patterns import load_patterns  # noqa: E402
from secondword import read_table, word_by_code  # noqa: E402
from wordle import load_words, pattern  # noqa: E402
from wordlesim import (answer_to_guess, make_opening_rule, make_tail,  # noqa: E402
                       play_game, second_rule_for)

# The default report: one row per grey count.  With --split-matched-vowels the
# 3- and 4-grey rows are split by how many MATCHED (green/yellow) tiles sit on a
# vowel of the opener, and a `matched_vowels` column is added (-1 = the whole grey
# bucket, unsplit).  The two formats differ only by that one column.
COLUMNS = ("grays,answers,share,opt_mean,optword_mean,sim_mean,sim_stderr,gap,"
           "word_gap,followup_gap,contribution,word_contrib,followup_contrib,"
           "pct_of_gap,fires")
COLUMNS_MV = "grays,matched_vowels," + COLUMNS[len("grays,"):]

INF = 10 ** 9
VOWELS = "aeiouy"                            # y is a vowel; matches secondword.py


def parse_args(argv):
    a = {"opener": None, "second_from": "", "fallback": "answer", "n": 100,
         "seed": 0, "out": None, "progress": 500, "split_matched_vowels": False}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-").replace("-", "_")
        if k == "no_out":
            a["out"] = False
            i += 1
            continue
        if k == "split_matched_vowels":
            a[k] = True
            i += 1
            continue
        if k not in a:
            raise SystemExit("unknown argument: %s" % argv[i])
        v = argv[i + 1]
        a[k] = int(v) if k in ("n", "seed", "progress") else v
        i += 2
    if not a["opener"]:
        raise SystemExit("--opener is required: the decomposition is for ONE "
                         "opener, against the optimal tree for that same opener")
    if a["fallback"] not in ("answer", "guess"):
        raise SystemExit("--fallback must be 'answer' or 'guess'")
    if a["n"] < 2:
        raise SystemExit("-n must be at least 2 (a standard error needs two)")
    if a["out"] is None:
        raise SystemExit(
            "--out is required (or --no-out to discard it deliberately).\n"
            "Use the wrapper, which sets it: bash solver/run-second-loss.sh")
    return a


def optimal_costs(opener, answers):
    """Per-answer guess counts under the committed OPTIMAL tree for this opener.

    A tree line is `<answer> <guesses> <opener> <pattern> <guess> ...`, one per
    answer.  Read the count rather than the line, and check the coverage: a tree
    missing an answer would silently shift every mean it is compared against.
    """
    path = os.path.join(paths.TREES, opener + ".txt.gz")
    if not os.path.exists(path):
        raise SystemExit(
            "no optimal tree for %r at %s\n"
            "The committed trees are one file per opener; if this one is "
            "missing, produce it with\n"
            "  ./solver/optturns --opener %s --trees <dir>   (from math/)"
            % (opener, path, opener))
    cost = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            if parts[0] in cost:
                raise SystemExit("%s lists the answer %s twice" % (path, parts[0]))
            cost[parts[0]] = int(parts[1])
            if parts[2] != opener:
                raise SystemExit("%s plays %s first, not %s"
                                 % (path, parts[2], opener))
    missing = [w for w in answers if w not in cost]
    if missing:
        raise SystemExit("%s covers %d of the %d answers (missing e.g. %s)"
                         % (path, len(cost), len(answers), missing[0]))
    extra = set(cost) - set(answers)
    if extra:
        raise SystemExit("%s lists %d words that are not answers, e.g. %s"
                         % (path, len(extra), sorted(extra)[0]))
    return cost


def committed_total(opener):
    """What the sweep recorded for this opener, or None if it is not on file."""
    path = paths.CSV_PATH
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            if line.startswith(opener + ","):
                parts = line.split(",")
                return int(parts[1]), float(parts[2])
    return None


def solve_total(S, d, memo, pat, allgreen):
    """Min TOTAL guesses to resolve the answer set S within d further guesses,
    over ALL legal guesses.  Exact branch-and-bound: the 2|P|-1 counting bound
    orders and prunes candidates, and results are memoised on (S, d).  S is a
    sorted tuple of answer indices; these are residual sets after two guesses, so
    they are small.  Returns INF if S cannot be resolved within d.

    This is the same min-total, capped objective optturns computed for A, so the
    two are comparable -- the gate proves it by reproducing A with this solver.
    """
    n = len(S)
    if n == 1:
        return 1 if d >= 1 else INF
    if n == 2:
        return 3 if d >= 2 else INF        # 1 to name one, 2 for the other
    if d <= 1:
        return INF
    key = (S, d)
    hit = memo.get(key)
    if hit is not None:
        return hit
    Sidx = np.array(S)
    codes = pat[:, Sidx]                    # (NG, n): each guess's reply on S
    has_ag = (codes == allgreen).any(axis=1)
    sc = np.sort(codes, axis=1)
    nuniq = np.concatenate(
        [np.ones((sc.shape[0], 1), bool), sc[:, 1:] != sc[:, :-1]],
        axis=1).sum(axis=1)
    valid = nuniq > 1                       # a guess must actually split S
    agi = has_ag.astype(np.int64)
    lb = n + 2 * (n - agi) - (nuniq - agi)  # <= true total for that guess
    cand = np.where(valid)[0]
    cand = cand[np.argsort(lb[cand], kind="stable")]
    best = INF
    for gi in cand:
        if int(lb[gi]) >= best:
            break                          # ascending lb: the rest are worse too
        row = codes[gi]
        buckets = defaultdict(list)
        for li in range(n):
            buckets[int(row[li])].append(int(Sidx[li]))
        total = n                          # everyone plays this guess
        ok = True
        for c, members in buckets.items():
            if c == allgreen:
                continue                   # that answer (== the guess) is named
            sub = solve_total(tuple(members), d - 1, memo, pat, allgreen)
            if sub >= INF:
                ok = False
                break
            total += sub
            if total >= best:
                break
        if ok and total < best:
            best = total
    memo[key] = best
    return best


def second_moves(opener, answers, gi, pat, guesses):
    """A's own 2nd guess for each opener reply, read from the committed tree.
    Keyed by the reply code pat[gi, answer]; a strategy plays one 2nd guess per
    reply, so a disagreement means the tree is not a strategy."""
    path = os.path.join(paths.TREES, opener + ".txt.gz")
    gidx = {w: i for i, w in enumerate(guesses)}
    aidx = {w: i for i, w in enumerate(answers)}
    a2 = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 5:
                continue                   # solved by the opener itself: no 2nd
            r1 = int(pat[gi, aidx[parts[0]]])
            g2i = gidx[parts[4]]
            if a2.setdefault(r1, g2i) != g2i:
                raise SystemExit("the tree for %s plays two different 2nd guesses "
                                 "for one opener reply -- not a strategy" % opener)
    return a2


def bucket_B_sums(gi, na, bkey, nb, pat, opt, second_of, allgreen, cap, memo):
    """Per report bucket, the sum of B = the forced 2nd word then OPTIMAL play.

    `bkey[ai]` is the answer's report-bucket index (0..nb-1) -- by grey count, or
    by (grey count, matched vowels) when the report is split.  Both keys are a
    function of the opener's REPLY, hence constant within a reply and within a
    residual set, so a residual set lands wholly in one bucket and only bucket
    SUMS are needed; per-answer depths (which are tie-dependent) never enter.

    `second_of(r1)` returns the 2nd guess index for reply r1, or -1 when no word
    is forced (below the firing threshold, or the plain opener) -- those answers
    get B = A, so they add nothing to the word-choice loss.  Returns
    (Bsum[nb], infeasible_count)."""
    Bsum = np.zeros(nb)
    infeasible = 0
    grp = defaultdict(list)
    for ai in range(na):
        r1 = int(pat[gi, ai])
        if r1 == allgreen:                 # the opener is the answer: solved in 1
            Bsum[bkey[ai]] += 1
            continue
        g2i = second_of(r1)
        if g2i < 0:
            Bsum[bkey[ai]] += opt[ai]      # not forced: B = A
            continue
        r2 = int(pat[g2i, ai])
        if r2 == allgreen:
            Bsum[bkey[ai]] += 2            # the forced 2nd word named it
            continue
        grp[(r1, g2i, r2)].append(ai)
    for (r1, g2i, r2), mem in grp.items():
        b = int(bkey[mem[0]])              # all of one reply share a bucket
        t = solve_total(tuple(sorted(mem)), cap - 2, memo, pat, allgreen)
        if t >= INF:
            infeasible += len(mem)
            continue
        Bsum[b] += 2 * len(mem) + t        # 2 played guesses + optimal remainder
    return Bsum, infeasible


def main(argv):
    a = parse_args(argv)
    guesses = load_words("guess")
    answers = load_words("mystery")
    na = len(answers)
    if a["opener"] not in guesses:
        raise SystemExit("%r is not one of the %d legal guesses"
                         % (a["opener"], len(guesses)))

    # --- the optimal side, exact
    cost = optimal_costs(a["opener"], answers)
    opt = np.array([cost[w] for w in answers], dtype=np.int64)
    total = int(opt.sum())
    rec = committed_total(a["opener"])
    if rec is not None and rec[0] != total:
        raise SystemExit("the tree for %s sums to %d guesses, but the sweep "
                         "recorded %d -- one of them is not this opener's"
                         % (a["opener"], total, rec[0]))

    # --- the buckets, recomputed FROM THE STRINGS so the key owes nothing to the
    # pattern matrix or to the encoding
    grays = np.array([_gray_count(a["opener"], w) for w in answers],
                     dtype=np.int8)

    pat = np.array(load_patterns())
    ans2g = answer_to_guess(answers, guesses)
    tail = make_tail(a["fallback"], guesses, answers, ans2g)
    gi = guesses.index(a["opener"])
    # the all-green reply code, tied to the matrix (guess word == answer word)
    allgreen = int(pat[ans2g[0], 0])
    if a["second_from"]:
        table = read_table(a["second_from"])
        if a["opener"] not in table.rows:
            raise SystemExit("%s has no row for %r -- it was built over the %s "
                             "opener pool" % (a["second_from"], a["opener"],
                                              table.openers))
        rule = second_rule_for([gi], table, guesses)
        label = table.fire
        # ONCE, not per game: this is the rule's own lookup, and rebuilding it
        # inside the loop made the measurement cost more than the games did.
        by_code = word_by_code(table, a["opener"], guesses)
    else:
        rule = make_opening_rule([gi], tail=tail, adapt=0)
        label = "(none: the plain opener)"
        by_code = None

    print("EV loss vs optimal, by the opener's grey count")
    print("  opener     %s   (optimal total %d, expected %.5f, capped at 6)"
          % (a["opener"], total, total / na))
    print("  strategy   second word from %s, firing on %s"
          % (a["second_from"] or "(none)", label))
    print("  follow-up  %s;  %d games per answer x %d answers = %d games"
          % (a["fallback"], a["n"], na, a["n"] * na))

    # --- the strategy side, stratified: every answer played the same number of
    # times, so the answer weights are exact and the error is the coin flips'
    rng = np.random.default_rng(a["seed"])
    mean_a = np.zeros(na)
    var_a = np.zeros(na)
    fired_a = np.zeros(na)
    t0 = time.time()
    for ai in range(na):
        sc = np.empty(a["n"], dtype=np.int32)
        fired = 0
        for k in range(a["n"]):
            played, replies = play_game(pat, ans2g, ai, rule, tail, rng)
            sc[k] = len(played)
            if len(played) > 1 and by_code is not None:
                fired += int(by_code[replies[0]] == played[1])
        mean_a[ai] = sc.mean()
        var_a[ai] = sc.var(ddof=1)
        fired_a[ai] = fired / a["n"]
        if a["progress"] and (ai + 1) % a["progress"] == 0:
            print("  %d/%d answers  (%.0fs)" % (ai + 1, na, time.time() - t0))

    sim_mean = float(mean_a.mean())
    sim_se = float(np.sqrt(var_a.sum() / a["n"]) / na)
    opt_mean = total / na
    gap = sim_mean - opt_mean

    # --- the report BUCKETS.  By grey count, or -- with --split-matched-vowels --
    # the 3- and 4-grey buckets are split by how many MATCHED (green/yellow) tiles
    # sit on a vowel of the opener (y a vowel).  Both keys are a function of the
    # opener's REPLY, so each is constant within a reply and a residual set.
    split = a["split_matched_vowels"]
    if split:
        mvow = np.array([_matched_vowels(a["opener"], w) for w in answers],
                        dtype=np.int8)
        # 3 greys leaves 2 matched tiles, 4 greys leaves 1; all-grey has none and
        # stays whole.  Empty combinations (2 matched vowels for a one-vowel
        # opener) simply hold no answers and are dropped below.
        order = ([(g, -1) for g in (0, 1, 2)]
                 + [(3, v) for v in range(3)] + [(4, v) for v in range(2)]
                 + [(5, -1)])
    else:
        mvow = np.zeros(na, dtype=np.int8)
        order = [(g, -1) for g in range(6)]
    idx_of = {d: i for i, d in enumerate(order)}
    nb = len(order)

    def desc(ai):
        g = int(grays[ai])
        return (g, int(mvow[ai])) if split and g in (3, 4) else (g, -1)

    bkey = np.array([idx_of[desc(ai)] for ai in range(na)], dtype=np.int32)

    # --- B: our forced 2nd word, then OPTIMAL continuation (capped, same footing
    # as the committed trees).  Only bucket SUMS are needed -- the key is constant
    # within a residual set, and the min-total of each set is unique.
    CAP = 6                                 # the committed trees' depth cap
    memo = {}
    if by_code is not None:
        strat_second = lambda r1: int(by_code[r1])   # -1 below the threshold
    else:
        strat_second = lambda r1: -1                 # plain opener: nothing forced
    Bsum, infeasible = bucket_B_sums(gi, na, bkey, nb, pat, opt, strat_second,
                                     allgreen, CAP, memo)

    # --- the gate: forcing each reply's OWN optimal 2nd move (from the tree) must
    # reproduce A, per GREY bucket.  That is what validates solve_total; if it
    # holds, the same solver run on our word (and any finer split) is trustworthy.
    a2 = second_moves(a["opener"], answers, gi, pat, guesses)
    gcoarse = grays.astype(np.int64)
    gateB, _ = bucket_B_sums(gi, na, gcoarse, 6, pat, opt, lambda r1: a2[r1],
                             allgreen, CAP, memo)
    for g in range(6):
        sel = grays == g
        if not sel.any():
            continue
        want = int(opt[sel].sum())
        if abs(gateB[g] - want) > 0.5:
            raise SystemExit(
                "GATE FAILED at grey=%d: forcing the tree's own 2nd move sums to "
                "%.0f, but the optimal tree sums to %d -- solve_total does not "
                "reproduce optimal play, so B cannot be trusted"
                % (g, gateB[g], want))
    if infeasible:
        print("  WARNING: %d firing answers have no capped-optimal continuation "
              "within depth %d after the forced word (excluded from B)"
              % (infeasible, CAP))

    rows = []
    for b, (g, mvk) in enumerate(order):
        sel = grays == g if mvk == -1 else (grays == g) & (mvow == mvk)
        k = int(sel.sum())
        if not k:
            continue
        bm = float(mean_a[sel].mean())
        bse = float(np.sqrt(var_a[sel].sum() / a["n"]) / k)
        om = float(opt[sel].mean())
        wm = Bsum[b] / k                    # B per answer: our word, optimal after
        rows.append(dict(grays=g, mv=mvk, answers=k, share=k / na, opt=om,
                         optword=wm, sim=bm, se=bse, gap=bm - om, word_gap=wm - om,
                         foll_gap=bm - wm, contrib=(k / na) * (bm - om),
                         word_contrib=(k / na) * (wm - om),
                         foll_contrib=(k / na) * (bm - wm),
                         fires=float(fired_a[sel].mean())))

    # --- the built-in gate: the parts must be the whole
    csum = sum(r["contrib"] for r in rows)
    if abs(csum - gap) > 1e-9:
        raise SystemExit("the bucket contributions sum to %.12f but the gap is "
                         "%.12f -- the decomposition is not one" % (csum, gap))
    if abs(sum(r["word_contrib"] + r["foll_contrib"] for r in rows) - gap) > 1e-9:
        raise SystemExit("the word and followup contributions do not sum to the "
                         "gap -- the two-way split is not one")
    if abs(sum(r["share"] for r in rows) - 1.0) > 1e-12:
        raise SystemExit("the bucket shares do not sum to 1")
    if abs(sum(r["share"] * r["opt"] for r in rows) - opt_mean) > 1e-9:
        raise SystemExit("the bucket optimal means do not average to the total")
    for w, g in zip(answers[:200], grays[:200]):
        if int(g) != sum(1 for t in _tiles(a["opener"], w) if t == 0):
            raise SystemExit("the grey count for %s was not computed from the "
                             "strings" % w)

    word_total = sum(r["word_contrib"] for r in rows)
    foll_total = sum(r["foll_contrib"] for r in rows)
    print()
    print("  A  optimal (same opener, capped)   %.5f" % opt_mean)
    print("  B  our 2nd word, then optimal       %.5f   (word-choice loss %.5f)"
          % (opt_mean + word_total, word_total))
    print("  C  strategy (our word + followup)   %.5f +/- %.5f   (followup loss "
          "%.5f)" % (sim_mean, sim_se, foll_total))
    print("  gap  C - A = %.5f  =  %.5f (word choice)  +  %.5f (followup)"
          % (gap, word_total, foll_total))
    print()
    if split:
        print("  %5s %4s %8s %7s %9s %9s %9s %9s %9s %10s %10s %6s"
              % ("grays", "mvow", "answers", "share", "A opt", "B our g2",
                 "C strat", "word", "followup", "w-contrib", "f-contrib", "fires"))
    else:
        print("  %5s %8s %7s %9s %9s %9s %9s %9s %10s %10s %6s"
              % ("grays", "answers", "share", "A opt", "B our g2", "C strat",
                 "word", "followup", "w-contrib", "f-contrib", "fires"))
    for r in rows:
        mvs = (" %4s" % ("-" if r["mv"] == -1 else r["mv"])) if split else ""
        print(("  %5d" + mvs + " %8d %6.1f%% %9.4f %9.4f %9.4f %9.4f %9.4f %10.5f "
               "%10.5f %5.0f%%")
              % (r["grays"], r["answers"], 100 * r["share"], r["opt"], r["optword"],
                 r["sim"], r["word_gap"], r["foll_gap"], r["word_contrib"],
                 r["foll_contrib"], 100 * r["fires"]))

    if a["out"]:
        os.makedirs(os.path.dirname(a["out"]) or ".", exist_ok=True)
        with open(a["out"], "w") as f:
            head = ("by grey count and matched vowels (3- and 4-grey split)"
                    if split else "by grey count")
            f.write("# EV loss vs optimal for the opener %s, %s, split into "
                    "word-choice and followup loss\n" % (a["opener"], head))
            f.write("# strategy: second word from %s firing on %s, follow-up "
                    "%s\n" % (a["second_from"] or "(none)", label, a["fallback"]))
            f.write("# %d games per answer x %d answers, seed %d; answer weights "
                    "are EXACT\n" % (a["n"], na, a["seed"]))
            if split:
                f.write("# matched_vowels = MATCHED (green/yellow) tiles on a "
                        "vowel of the opener (y a vowel); -1 = the whole grey "
                        "bucket, unsplit\n")
            f.write("# A = capped optimum for the SAME opener (total %d, %.5f/ans),"
                    " min guesses within six.  B = our forced 2nd word then the "
                    "SAME\n# capped-optimal continuation.  C = the uncapped "
                    "strategy.  A <= B <= C, so word-choice loss B-A and followup "
                    "loss C-B\n# are each LOWER BOUNDS on the loss against "
                    "unconstrained optimal play.\n" % (total, opt_mean))
            f.write("# gap %.6f = word-choice loss %.6f (B-A) + followup loss "
                    "%.6f (C-B)\n" % (gap, word_total, foll_total))
            f.write("# gate: forcing each reply's own optimal 2nd move reproduces "
                    "A per grey bucket, validating the residual solver\n")
            f.write((COLUMNS_MV if split else COLUMNS) + "\n")
            for r in rows:
                pre = "%d,%d," % (r["grays"], r["mv"]) if split \
                    else "%d," % r["grays"]
                f.write((pre + "%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,"
                         "%.6f,%.6f,%.4f,%.6f\n")
                        % (r["answers"], r["share"], r["opt"], r["optword"],
                           r["sim"], r["se"], r["gap"], r["word_gap"],
                           r["foll_gap"], r["contrib"], r["word_contrib"],
                           r["foll_contrib"],
                           100 * r["contrib"] / gap if gap else 0, r["fires"]))
        print("\nwrote %s" % a["out"])


def _tiles(guess, answer):
    """The reply as tiles, from the STRINGS, by the multiset rule."""
    tiles = [2 if g == x else 0 for g, x in zip(guess, answer)]
    left = Counter(x for g, x in zip(guess, answer) if g != x)
    for i, g in enumerate(guess):
        if tiles[i] == 0 and left[g] > 0:
            tiles[i] = 1
            left[g] -= 1
    return tiles


def _gray_count(guess, answer):
    return sum(1 for t in _tiles(guess, answer) if t == 0)


def _matched_vowels(guess, answer):
    """MATCHED (green/yellow) tiles sitting on a vowel of the guess, from the
    strings.  y is a vowel (VOWELS), matching secondword.  A function of the
    reply, so constant within one opener reply."""
    return sum(1 for pos, t in enumerate(_tiles(guess, answer))
               if t != 0 and guess[pos] in VOWELS)


if __name__ == "__main__":
    main(sys.argv[1:])
