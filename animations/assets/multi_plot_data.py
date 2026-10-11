"""Scene 16s-v's chart — average MISSES against the number of Wordles. SOURCED, then
cached.

    ../../.venv/bin/python multi_plot_data.py     # (from this directory)

AVERAGE MISSES = MEAN TOTAL GUESSES - k. Every board takes exactly one correct guess
(the answers are distinct, so no guess solves two), so whatever a game spends past k
is a miss. That subtraction is the only arithmetic here; every mean is a number a run
wrote itself.

THE PLAN (user's, 2026-10-01): find the best single, pair and triple opener at each
power of two, k = 1, 2, 4, 8, 16, 32 -- multiwordle races -- then run each winner at
every k from its power of two up to just below the next, and plot those.

  1/2/3-word lines -- math/multiwordle.py's `greedy` rule (the scene's strategy:
      fewest candidates, a random candidate). Winner at 2^j = the leader of
      race_greedy_k<2^j>_<field>; the value at k = that winner's fixed-opener run
      k<k>_<opener>_t1000000_s0.csv.
  Improved Strategy -- `minavg`. Winner at 2^j = race_minavg_k<2^j>_guess's leader
      (k = 1: exact_minavg_k1_guess.csv's best row, an EXACT optimum); the value at
      k = k<k>_<opener>_t100000_s0_minavg.csv.

WHERE A FILL-IN RUN IS NOT ON DISK YET, the race's own estimate stands in at the
power of two itself (source "race"), and any other missing k is left OUT -- the line
is drawn straight across the gap. Every point records its source, and the build
prints what is still missing, so a stopgap cannot pass for the finished chart.
Re-run this as results land; the scene needs no change.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MATH = os.path.join(HERE, "..", "..", "math")
DIR = os.path.join(MATH, "data", "shared", "multiwordle")
CACHE = os.path.join(HERE, "multi_plot_cache.json")

KS = list(range(1, 33))
# The winner at each of these k covers every k up to the next one. Powers of two
# first (user's plan, 2026-10-01), then 3 x powers of two added to smooth the jumps
# where the winner changes (user, 2026-10-02).
# 5 x and 7 x powers of two were added for the 1-word line only (user, 2026-10-02);
# a line with no race at a k simply has no winner there, so its bracket below covers
# it -- adding a k here cannot change a line that was never raced at it.
# ... and 9, 11, 13, 15 x {1, 2} for the 1-word line as well (user, 2026-10-02).
POWERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26,
          28, 30, 32]
# EVERY race field for a line competes at each k, and the lowest race mean wins
# (user's rule, 2026-10-02: "if we find something better than what's used in the
# chart, we should just put it in the chart"). The unrestricted fields are each a
# SCREEN of a ranking built for another question, so an answers-only race can find
# an opener the unrestricted one never examined (CLAMP TREND at k=8 was outside the
# top 10000 pairs). Add any new field here and it competes automatically.
FIELDS = {1: ["guess", "mystery"],
          2: ["pair_singletons_top10000", "pair_singletons_answers_top100000_top10000"],
          3: ["triple_singletons_top10000", "triple_singletons_answers_exhaustive_top10000"]}
T_GREEDY, T_MINAVG = 1000000, 100000
# A race's estimate stands in for a missing fill-in ONLY once it means something: the
# race has finished (one opening left) or its leader has played this many games. A
# race still in its first rounds has a leader by noise -- 200 games, standard error
# 0.04, thousands still in -- and plotting that would be a confident wrong point.
RACE_MIN_GAMES = 1000000
# A minavg race may be finished over a SHORTLIST: the LAST 50 OPENERS STILL IN that
# k's own full race (user's rule, 2026-10-02), raced on their own. Map k to that
# race's field name here once one is built; until then the full race is read.
# (A first k=32 shortlist -- the top 50 by mean at 200 games -- broke that rule and
# was withdrawn.)
MINAVG_FIELD = {k: f"shortlist_greedy_k{k}_last50_top50" for k in (3, 6, 12, 24, 32)}   # the plain 1-word race's last 50
MEAN = re.compile(r"# mean total guesses ([\d.]+)\s+\+/- ([\d.]+)")


def _bracket(k):
    return max(p for p in POWERS if p <= k)


def _race(strategy, k, field):
    """The race's leader: (opening, mean, stderr, games, n_live). Several still live
    means the race has not finished; the best of them by mean is taken."""
    path = os.path.join(DIR, f"race_{strategy}_k{k}_{field}_sig5_s0.csv")
    if not os.path.exists(path):
        return None
    rows = [l.strip().split(",") for l in open(path) if not l.startswith("#")]
    head, rows = rows[0], [dict(zip(rows[0], r)) for r in rows[1:]]
    live = [r for r in rows if r["status"] == "live" and r["mean"]]
    if not live:
        return None
    live.sort(key=lambda r: float(r["mean"]))
    best = live[0]
    # [5]: every opening still in, best first -- a provisional leader's stand-ins
    return (best["opening"], float(best["mean"]), float(best["stderr"]),
            int(best["games"]), len(live), [r["opening"] for r in live])


def _exact_k1():
    path = os.path.join(DIR, "exact_minavg_k1_guess.csv")
    if not os.path.exists(path):
        return None
    rows = [l.strip().split(",") for l in open(path) if not l.startswith("#")]
    rows = [dict(zip(rows[0], r)) for r in rows[1:]]
    if not rows:
        return None
    best = min(rows, key=lambda r: float(r["mean"]))
    return best["word"], float(best["mean"])


def _sim(k, opener, trials, suffix):
    """(mean, stderr) of a finished fixed-opener run, else None (absent or running)."""
    base = os.path.join(DIR, f"k{k}_{opener.replace(' ', '-')}_t{trials}_s0{suffix}.csv")
    for path in (base, base + ".summary"):
        if os.path.exists(path):
            with open(path, "rb") as f:
                f.seek(max(0, os.path.getsize(path) - 4000))
                m = MEAN.search(f.read().decode("utf-8", "replace"))
            if m:
                return float(m.group(1)), float(m.group(2))
    return None


def _line(winners, trials, suffix):
    """Each k uses the winner of the highest bracket at or below it. A race that has
    not settled names NO winner (it is left out of `winners`), so an unconfirmed
    leader never decides which opener a k is run with.

    WHILE A NEW WINNER'S RUN AT k IS NOT FINISHED, THE PREVIOUS WINNER'S STANDS IN
    (user's call, 2026-10-02): the brackets below are tried in turn, nearest first,
    and the first with a finished run at k is used -- "fallback" in its source. Only
    if none has one does a race estimate (at the bracket's own k) or a gap appear."""
    pts, missing = [], []
    for k in KS:
        below = sorted((p for p in winners if p <= k), reverse=True)
        if not below:
            pts.append({"k": k, "misses": None, "source": "no winner"})
            missing.append(k)
            continue
        b, w = below[0], winners[below[0]]
        got = _sim(k, w["opening"], trials, suffix)
        if got is not None:
            pts.append({"k": k, "misses": round(got[0] - k, 4), "stderr": got[1],
                        "opening": w["opening"], "source": "run"})
            continue
        # stand-ins: this bracket's other race winners (best first), then each
        # bracket below in turn with its winner and its alternates
        chain = list(w.get("alts", []))
        for p in below[1:]:
            chain += [winners[p]["opening"]] + list(winners[p].get("alts", []))
        for op in chain:
            old = _sim(k, op, trials, suffix)
            if old is not None:
                pts.append({"k": k, "misses": round(old[0] - k, 4), "stderr": old[1],
                            "opening": op, "source": "fallback", "pending": w["opening"]})
                break
        else:
            if k == b and w.get("mean") is not None:
                pts.append({"k": k, "misses": round(w["mean"] - k, 4),
                            "opening": w["opening"], "source": w["source"]})
            else:
                pts.append({"k": k, "misses": None, "opening": w["opening"],
                            "source": "missing"})
                missing.append(k)
    return pts, missing


def _build():
    out = {"ks": KS, "lines": {}, "notes": []}
    for n, fields in FIELDS.items():
        winners = {}
        for p in POWERS:
            best, settled_here, unsettled_here = None, [], []
            for field in fields:
                r = _race("greedy", p, field)
                if r is None:
                    continue
                if r[4] > 1:
                    out["notes"].append(f"greedy {n}-word {field} race at k={p} still has "
                                        f"{r[4]} live")
                if not (r[4] == 1 or r[3] >= RACE_MIN_GAMES):
                    unsettled_here.append(r)
                    continue
                settled_here.append(r)
                if best is None or r[1] < best[1]:
                    best = r + (field,)
            if best is None and unsettled_here:
                # PROVISIONAL (user's call, 2026-10-02): a race still running names
                # its current leader, but with no estimate -- it is used only where
                # that leader's own runs exist, and the opener it would replace
                # stands in everywhere else. If the lead changes, so does this.
                lead = min(unsettled_here, key=lambda r: r[1])
                winners[p] = {"opening": lead[0], "mean": None, "source": "race",
                              "provisional": True, "alts": lead[5][1:]}
            if best is not None:
                winners[p] = {"opening": best[0], "mean": best[1], "source": "race",
                              "field": best[-1],
                              # the other fields' settled winners, best first: the
                              # first stand-ins while this one's runs land
                              "alts": [r[0] for r in sorted(settled_here, key=lambda r: r[1])
                                       if r[0] != best[0]]}
        pts, missing = _line(winners, T_GREEDY, "")
        out["lines"][str(n)] = {"winners": {str(p): w["opening"] for p, w in winners.items()},
                                "provisional": [p for p, w in winners.items()
                                                if w.get("provisional")],
                                "points": pts, "missing": missing}

    winners = {}
    ex = _exact_k1()
    if ex is not None:
        winners[1] = {"opening": ex[0], "mean": ex[1], "source": "exact"}
    for p in POWERS[1:]:
        cands = [r for r in (_race("minavg", p, f) for f in
                             ["guess"] + ([MINAVG_FIELD[p]] if p in MINAVG_FIELD else []))
                 if r is not None]
        settled_c = [r for r in cands if r[4] == 1 or r[3] >= RACE_MIN_GAMES]
        # nothing settled: the SHORTLIST race (when there is one) is the one being run
        # to a winner, so its leader is the provisional one -- not the abandoned full race
        r = min(settled_c, key=lambda r: r[1]) if settled_c else (cands[-1] if cands else None)
        if r is not None:
            settled = r[4] == 1 or r[3] >= RACE_MIN_GAMES
            if settled:
                winners[p] = {"opening": r[0], "mean": r[1], "source": "race"}
            else:
                # PROVISIONAL -- see the greedy loop above. While the race runs, the
                # openings still in it stand in before any lower bracket, best first:
                # a lead flipping between two tied openers must not throw away the
                # one whose runs exist (FILET overtook ROTAN at k=24 by 0.0004).
                winners[p] = {"opening": r[0], "mean": None, "source": "race",
                              "provisional": True, "alts": r[5][1:]}
                out["notes"].append(f"minavg race at k={p} not settled ({r[4]} live, "
                                    f"{r[3]} games): leader {r[0]} used only where its "
                                    f"runs exist")
    pts, missing = _line(winners, T_MINAVG, "_minavg")
    out["lines"]["improved"] = {"winners": {str(p): w["opening"] for p, w in winners.items()},
                                "provisional": [p for p, w in winners.items()
                                                if w.get("provisional")],
                                "points": pts, "missing": missing}
    return out


ANSWER_FIELDS = {1: ["mystery"],
                 2: ["pair_singletons_answers_top100000_top10000"],
                 3: ["triple_singletons_answers_exhaustive_top10000"]}


def best_opener(k, fields):
    """The greedy winner at THIS k among `fields`' races, by the chart's rule: the
    settled races compete on race mean (a race is settled when one opening is left or
    its leader has RACE_MIN_GAMES), and with none settled the best unsettled leader
    stands in. Its average misses come from its fixed-opener run at k when that has
    finished (more games), else from the race. `unfinished` is True when the chosen
    race still has more than one opening live. None if no race at k. For the bonus
    video's opener tables; the chart itself is built by _build."""
    settled, unsettled = [], []
    for field in fields:
        r = _race("greedy", k, field)
        if r is not None:
            (settled if r[4] == 1 or r[3] >= RACE_MIN_GAMES else unsettled).append(r)
    pool = settled or unsettled
    if not pool:
        return None
    r = min(pool, key=lambda r: r[1])
    got = _sim(k, r[0], T_GREEDY, "")
    mean = got[0] if got is not None else r[1]
    return {"opening": r[0], "misses": round(mean - k, 4),
            "source": "run" if got is not None else "race", "unfinished": r[4] > 1}


def load():
    with open(CACHE) as f:
        return json.load(f)


if __name__ == "__main__":
    data = _build()
    with open(CACHE, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    for key, ln in data["lines"].items():
        name = "Improved Strategy" if key == "improved" else f"{key}-word"
        print(f"{name}: winners " + ", ".join(f"k{p}={w}" for p, w in ln["winners"].items())
              + ("" if not ln.get("provisional") else
                 "   (PROVISIONAL, race still running: "
                 + ", ".join(f"k{p}" for p in ln["provisional"]) + ")"))
        stop = [p["k"] for p in ln["points"] if p["source"] in ("race", "exact")]
        fb = [f"{p['k']}:{p['opening']}" for p in ln["points"] if p["source"] == "fallback"]
        print(f"   from fill-in runs: {sum(p['source'] == 'run' for p in ln['points'])}/32"
              f"   race/exact stand-ins at k={stop}   MISSING k={ln['missing']}")
        if fb:
            print(f"   OLDER WINNER standing in (new one's run not finished): {' '.join(fb)}")
    for note in data["notes"]:
        print("NOTE", note)
    print(f"wrote {CACHE}")
