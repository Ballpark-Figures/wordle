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
POWERS = [1, 2, 4, 8, 16, 32]
FIELDS = {1: "guess", 2: "pair_singletons_top10000", 3: "triple_singletons_top10000"}
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
    best = min(live, key=lambda r: float(r["mean"]))
    return (best["opening"], float(best["mean"]), float(best["stderr"]),
            int(best["games"]), len(live))


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
    pts, missing = [], []
    for k in KS:
        w = winners.get(_bracket(k))
        if w is None:
            pts.append({"k": k, "misses": None, "source": "no winner"})
            missing.append(k)
            continue
        got = _sim(k, w["opening"], trials, suffix)
        if got is not None:
            pts.append({"k": k, "misses": round(got[0] - k, 4), "stderr": got[1],
                        "opening": w["opening"], "source": "run"})
        elif k == _bracket(k) and w.get("mean") is not None:
            pts.append({"k": k, "misses": round(w["mean"] - k, 4), "opening": w["opening"],
                        "source": w["source"]})
        else:
            pts.append({"k": k, "misses": None, "opening": w["opening"], "source": "missing"})
            missing.append(k)
    return pts, missing


def _build():
    out = {"ks": KS, "lines": {}, "notes": []}
    for n, field in FIELDS.items():
        winners = {}
        for p in POWERS:
            r = _race("greedy", p, field)
            if r is None:
                continue
            settled = r[4] == 1 or r[3] >= RACE_MIN_GAMES
            winners[p] = {"opening": r[0], "mean": r[1] if settled else None,
                          "source": "race"}
            if r[4] > 1:
                out["notes"].append(f"greedy {n}-word race at k={p} still has {r[4]} live")
        pts, missing = _line(winners, T_GREEDY, "")
        out["lines"][str(n)] = {"winners": {str(p): w["opening"] for p, w in winners.items()},
                                "points": pts, "missing": missing}

    winners = {}
    ex = _exact_k1()
    if ex is not None:
        winners[1] = {"opening": ex[0], "mean": ex[1], "source": "exact"}
    for p in POWERS[1:]:
        r = _race("minavg", p, MINAVG_FIELD.get(p, "guess"))
        if r is not None:
            settled = r[4] == 1 or r[3] >= RACE_MIN_GAMES
            winners[p] = {"opening": r[0], "mean": r[1] if settled else None,
                          "source": "race"}
            if not settled:
                out["notes"].append(f"minavg race at k={p} not settled ({r[4]} live, "
                                    f"{r[3]} games): its leader is not plotted")
    pts, missing = _line(winners, T_MINAVG, "_minavg")
    out["lines"]["improved"] = {"winners": {str(p): w["opening"] for p, w in winners.items()},
                                "points": pts, "missing": missing}
    return out


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
        print(f"{name}: winners " + ", ".join(f"k{p}={w}" for p, w in ln["winners"].items()))
        stop = [p["k"] for p in ln["points"] if p["source"] in ("race", "exact")]
        print(f"   from fill-in runs: {sum(p['source'] == 'run' for p in ln['points'])}/32"
              f"   race/exact stand-ins at k={stop}   MISSING k={ln['missing']}")
    for note in data["notes"]:
        print("NOTE", note)
    print(f"wrote {CACHE}")
