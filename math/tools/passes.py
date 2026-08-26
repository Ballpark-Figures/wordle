"""How far the sweep has got through each PASS of the dispatch bisection.

The solver does not walk the opener list end to end. `sweep_order()` sorts the
12972 openers by fewest expected survivors and then DISPATCHES them by bisecting
that sorted list: both ends first, then the median, then the quartiles, then the
octiles, and so on down. Each of those is a "pass" -- a level of the bisection
that samples the whole list at twice the previous resolution.

That makes progress two-dimensional. The headline count says how many openers
are done; this says WHERE they are. A level that is 100% complete means the
whole sorted list has been sampled at that resolution, so the distribution seen
so far is a uniform sample of the list at that spacing rather than a prefix of
it. The level currently filling is the sweep's working front.

    WORDLE_SOLVER=hardturns python3 tools/passes.py

The level bookkeeping mirrors `bisect()` in inflight.py, which in turn mirrors
`bisect_emit()` plus the level loop in optturns.c. It reproduces only the INDEX
sequence -- which depends on n alone -- so it needs no second copy of the sort:
the j-th word of sweep_order() belongs to whichever level emitted the j-th
index. Keep the two loops identical; a divergence here silently attributes words
to the wrong pass rather than failing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inflight import run_header, sweep_order
from paths import CSV_PATH, read_rows


def level_label(k, den):
    """Human name for bisection level k (denominator den = 2**k)."""
    return {1: "median", 2: "quartiles", 3: "octiles"}.get(k, "1/%d" % den)


def emit_levels(n):
    """Per OUTPUT POSITION of bisect(), the label of the level that emitted it.

    Mirrors bisect() exactly, tracking only indices and the emitting level, so
    position j of sweep_order() carries label levels[j].
    """
    seen = bytearray(n)
    labels = []

    def emit(idx, label):
        idx = 0 if idx < 0 else (n - 1 if idx >= n else idx)
        if not seen[idx]:
            seen[idx] = 1
            labels.append(label)

    emit(0, "ends")
    emit(n - 1, "ends")
    for k in range(1, 21):
        if len(labels) >= n:
            break
        den = 1 << k
        label = level_label(k, den)
        for i in range(den // 2):
            if len(labels) >= n:
                break
            emit((n * (2 * i + 1) + den // 2) // den, label)
    for i in range(n):
        if len(labels) >= n:
            break
        emit(i, "fill")
    return labels


def passes():
    """[(label, words, done, done_this_run)] per bisection level, in dispatch order.

    `done` is every word with a row in the LIVE results CSV -- the same set the
    solver skips at dispatch, and the same one inflight.py counts, so these
    numbers agree with the REMAINING section. INFEASIBLE rows count as done: the
    opener was attempted and settled.

    The run split matters because the dispatch order CHANGED. Everything before
    the current run was dispatched straight down the sorted list, so those words
    form a prefix of the SORT and are spread evenly over the deep bisection
    levels -- they are why every deep level starts at the overall completion
    rate rather than zero. Only the `run` column is this run walking the
    bisection from its front.
    """
    rows = [r["word"] for r in read_rows(CSV_PATH)]
    done = set(rows)
    _, resumed, _, _ = run_header()
    this_run = set(rows[resumed:])
    order = sweep_order()
    labels = emit_levels(len(order))
    out, seen = [], {}
    for word, label in zip(order, labels):
        if label not in seen:
            seen[label] = len(out)
            out.append([label, 0, 0, 0])
        row = out[seen[label]]
        row[1] += 1
        if word in done:
            row[2] += 1
        if word in this_run:
            row[3] += 1
    return [tuple(r) for r in out]


def check():
    """Is `done` a PREFIX of sweep_order()? Prints the answer instead of
    assuming it.

    If dispatch follows sweep_order(), the finished words are its first K (bar
    the handful still in flight), so done-in-prefix should track the prefix
    length. A flat fraction instead means the reconstructed order is not the
    order the solver actually used, and every per-pass number below is
    meaningless. Left in permanently: it is one glance, and it is the only thing
    that distinguishes the two cases.
    """
    done = {r["word"] for r in read_rows(CSV_PATH)}
    order = sweep_order()
    n, d = len(order), len(done)
    print("done=%d of %d (%.1f%%)  -- expect ~100%% inside a prefix of %d"
          % (d, n, 100.0 * d / n, d))
    import numpy as np
    from inflight import NPAT
    from paths import GUESS_WORDS, PATTERNS
    raw = [w.strip() for w in open(GUESS_WORDS) if w.strip()]
    pat = np.load(PATTERNS, allow_pickle=False)
    ss = np.empty(len(raw), dtype=np.int64)
    for g in range(len(raw)):
        cnt = np.bincount(pat[g], minlength=NPAT).astype(np.int64)
        ss[g] = (cnt * cnt).sum()
    srt = [raw[g] for g in np.lexsort((np.arange(len(raw)), ss))]

    srt_pos = {w: i for i, w in enumerate(srt)}
    bis_pos = {w: i for i, w in enumerate(order)}
    recent = [r["word"] for r in read_rows(CSV_PATH)][-8:]
    print("  last 8 completions   sorted-pos / bisected-pos:")
    for w in recent:
        print("    %-6s %7d %8d" % (w, srt_pos[w], bis_pos[w]))
    live = [w for w in srt if w not in done][:6]
    print("  next 6 in SORTED order (undone): %s" % " ".join(live))
    liveb = [w for w in order if w not in done][:6]
    print("  next 6 in BISECTED order (undone): %s" % " ".join(liveb))

    for name, seq in (("bisected", order), ("sorted", srt), ("guess.txt", raw)):
        line = []
        for k in (100, 500, 1000, 1807, 4000, 8000, n):
            k = min(k, n)
            hit = sum(1 for w in seq[:k] if w in done)
            line.append("%5.1f%%" % (100.0 * hit / k))
        print("  %-10s prefix-done at 100/500/1k/1807/4k/8k/all: %s"
              % (name, " ".join(line)))


def main():
    if "--check" in sys.argv:
        check()
        return
    rows = passes()
    width = max(len(r[0]) for r in rows)
    print("PASS PROGRESS (dispatch bisection: ends, median, quartiles, ...)")
    print("-" * 64)
    print("  %-*s %7s %7s %7s %7s" % (width, "pass", "words", "done", "pct", "run"))
    front = None
    for label, total, done, run in rows:
        pct = 100.0 * done / total
        if front is None and done < total:
            front = label
        bar = "#" * int(pct / 5 + 0.5)
        print("  %-*s %7d %7d %6.1f%% %7d  %s"
              % (width, label, total, done, pct, run, bar))
    deep = [r for r in rows if r[3] == 0]
    print("\n  first incomplete pass: %s" % (front or "none -- sweep finished"))
    if deep:
        print("  passes untouched by this run start at the overall %.1f%% -- those"
              % (100.0 * sum(r[2] for r in rows) / sum(r[1] for r in rows)))
        print("  are earlier runs' sorted-order prefix, spread evenly over them.")


if __name__ == "__main__":
    main()
