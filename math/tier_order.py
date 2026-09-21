"""Save and reload the greedy TOKEN ORDER that `notebooks/letter_explorer.ipynb` computes.

    >>> import tier_order
    >>> tier_order.save(sel, D, min_gap=MIN_GAP)          # from the notebook
    >>> tier_order.load(max_repeat=2, num_trees=1000)     # anywhere afterwards

WHY THIS EXISTS.  The greedy is expensive and its cost is O(tokens^2 x paths), so a
`MAX_REPEAT = 2` run over 1000 pooled trees is roughly four times a letters-only one and
is not something to re-run every time a later notebook or scene wants the ranking.  The
order is also EXACT and deterministic -- no sampling, no seed -- so it is an artifact
worth committing once and importing thereafter, exactly as `opener_totals.csv` is.

WHAT IS SAVED IS THE ORDER, NOT A TIER LIST, AND THE DIFFERENCE IS THE WHOLE POINT.
The greedy ranking is COMPUTED; where the tier CUTS fall is an EDITORIAL decision the
notebook is explicit about ("read the gaps, then choose the cuts deliberately").  So this
module stores the computed half -- the ranking plus the `top2_diff` gaps the cuts are
read off -- and nothing here invents a boundary.  When the cuts are chosen, `as_tiers`
turns them into the tuple that `tiers.py` records, and `tiers.py` remains what it says it
is: a hand-made ranking, recorded, not computed.

THE FILE SELF-DESCRIBES AND A MISMATCHED READ IS REFUSED.  A saved order is meaningless
without the settings that produced it -- the repeat level, how many trees were pooled,
and WHICH solver's trees those were -- so all of it rides in a `# settings` line, and
`load` refuses a file whose stamp disagrees with what was asked for rather than returning
a confidently wrong ranking.  A file with NO stamp is refused too, never trusted: an
unstamped file is an old file, not a matching one.  The pooled openers are pinned by a
digest of the whole list, so two runs that merely sorted ties differently cannot be
mistaken for each other.

The write is ATOMIC (temp file plus `os.replace`), so an interrupted save leaves the
previous artifact intact rather than a half-written one that later reads as a result.
"""

import csv
import hashlib
import os

DIRNAME = "tiers"
COLUMNS = ("step", "token", "set_before_outside", "pairs_outside_before_set",
           "top2_diff")


def _math_dir():
    return os.path.dirname(os.path.abspath(__file__))


def directory():
    """`math/data/shared/tiers` -- committed, since the laptop cannot regenerate it."""
    return os.path.join(_math_dir(), "data", "shared", DIRNAME)


def _solver(solver=None):
    """The solver whose trees were pooled.  `None` means "whatever this session
    resolves", so a hard-mode session reads its own file rather than the default one."""
    if solver is not None:
        return solver
    import paths as _paths
    return _paths.SOLVER


def path(max_repeat, num_trees, solver=None):
    """The one file name for these settings.  Each is a DIFFERENT ranking, so each
    gets its own file and none can overwrite another."""
    solver = _solver(solver)
    stem = "order_r%d_top%d" % (int(max_repeat), int(num_trees))
    if solver != "optturns":
        stem += "_%s" % solver
    return os.path.join(directory(), stem + ".csv")


def openers_digest(openers):
    """A short digest of the pooled opener list, in order.

    Pins WHICH trees were pooled, not merely how many -- the tie-break at the cut-off
    of a top-N is exactly the kind of thing that changes silently.
    """
    words = [w for w, _ in openers] if openers and isinstance(openers[0], (tuple, list)) \
        else list(openers)
    h = hashlib.sha256("\n".join(words).encode()).hexdigest()
    return h[:16]


def _stamp(max_repeat, num_trees, n_tokens, n_paths, solver, min_gap, digest):
    return ("# settings max_repeat=%d num_trees=%d tokens=%d paths=%d solver=%s "
            "weighting=uniform min_gap=%s openers_sha=%s"
            % (max_repeat, num_trees, n_tokens, n_paths, solver, min_gap, digest))


def save(rows, D, min_gap, out=None, overwrite=False):
    """Write the greedy order for the settings `D` was collected under.

    `rows` is the DataFrame `greedy_min_pairs` returns (or any sequence of dicts with
    the same keys); `D` is the dict `collect_paths` returns, which carries the pooled
    openers, the path count and the token universe -- so the stamp is taken from the
    run itself rather than retyped.
    """
    try:
        records = rows.to_dict("records")
    except AttributeError:
        records = list(rows)
    if not records:
        raise ValueError("no greedy steps to save")

    openers = D["openers"]
    n_tokens, n_paths = int(D["nt"]), int(D["n"])
    if len(records) != n_tokens:
        raise ValueError("the greedy has %d steps but the universe is %d tokens -- "
                         "save a COMPLETE run, or the order is a prefix"
                         % (len(records), n_tokens))
    max_repeat = n_tokens // 26
    if n_tokens % 26:
        raise ValueError("token universe %d is not a whole number of repeat levels"
                         % n_tokens)

    solver = _solver()                     # tools/ is on sys.path in the notebook
    dest = out or path(max_repeat, len(openers), solver)
    if os.path.exists(dest) and not overwrite:
        raise FileExistsError(
            "%s already exists.  These settings have been saved before; pass "
            "overwrite=True only if you mean to replace that ranking." % dest)

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    tmp = dest + ".tmp"
    with open(tmp, "w", newline="") as f:
        f.write("# greedy token order, best first: the ranking "
                "notebooks/letter_explorer.ipynb computes over the pooled optimal "
                "trees.  Exact and deterministic -- no sampling, no seed.\n")
        f.write("# THE ORDER IS COMPUTED; THE TIER CUTS ARE NOT IN THIS FILE.  Read "
                "them off top2_diff and record them in math/tiers.py.\n")
        f.write("# The trees minimise TOTAL guesses subject to resolving every answer "
                "within 6, so any ranking derived here inherits that constraint.\n")
        f.write(_stamp(max_repeat, len(openers), n_tokens, n_paths, solver,
                       min_gap, openers_digest(openers)) + "\n")
        f.write("# openers %s%s\n"
                % (", ".join(w for w, _t in openers[:8]),
                   "" if len(openers) <= 8 else ", +%d more" % (len(openers) - 8)))
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in records:
            w.writerow([r["step"], r["added"], r["set_before_outside"],
                        r["pairs_outside_before_set"],
                        "" if r["top2_diff"] != r["top2_diff"] else r["top2_diff"]])
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)
    return dest


def load(max_repeat=None, num_trees=None, solver=None, file=None):
    """Read a saved order back.  Returns `{"order": [...], "settings": {...},
    "steps": [...]}`; a stamp disagreeing with what was asked for is REFUSED."""
    solver = _solver(solver)
    src = file or path(max_repeat, num_trees, solver)
    if not os.path.exists(src):
        raise FileNotFoundError(
            "%s does not exist -- run notebooks/letter_explorer.ipynb at "
            "MAX_REPEAT=%s, NUM_TREES=%s and call tier_order.save()."
            % (src, max_repeat, num_trees))

    settings, steps = None, []
    with open(src) as f:
        for line in f:
            if line.startswith("#"):
                if line.startswith("# settings "):
                    settings = dict(kv.split("=", 1)
                                    for kv in line[len("# settings "):].split())
                continue
            break
        if settings is None:
            raise ValueError("%s carries no '# settings' line.  That means it is an "
                             "OLD file, not a matching one, so it is refused rather "
                             "than trusted." % src)
        f.seek(0)
        rows = [r for r in csv.DictReader(
            line for line in f if not line.startswith("#"))]

    for key, want in (("max_repeat", max_repeat), ("num_trees", num_trees)):
        if want is not None and int(settings[key]) != int(want):
            raise ValueError("%s was written with %s=%s, not %s"
                             % (src, key, settings[key], want))
    if settings.get("solver") != solver:
        raise ValueError("%s was written from the %s trees, not %s"
                         % (src, settings.get("solver"), solver))

    steps = [{"step": int(r["step"]), "token": r["token"],
              "set_before_outside": float(r["set_before_outside"]),
              "pairs_outside_before_set": float(r["pairs_outside_before_set"]),
              "top2_diff": float(r["top2_diff"]) if r["top2_diff"] else None}
             for r in rows]
    if len(steps) != int(settings["tokens"]):
        raise ValueError("%s holds %d steps but its stamp says %s tokens"
                         % (src, len(steps), settings["tokens"]))
    return {"order": [s["token"] for s in steps], "settings": settings,
            "steps": steps, "path": src}


def gaps(loaded, min_gap=0.5):
    """The candidate tier boundaries: steps whose `top2_diff` exceeds `min_gap`.

    A HINT, not a decision -- cut AFTER the named step, and only where you mean to.
    """
    return [(s["step"], s["token"], s["top2_diff"]) for s in loaded["steps"]
            if s["top2_diff"] is not None and s["top2_diff"] > min_gap]


def as_tiers(order, cuts):
    """Turn a computed `order` plus chosen `cuts` into the tuple `tiers.py` records.

    `cuts` are the step numbers to break AFTER, 1-based, exactly as `gaps` reports
    them -- so `as_tiers(order, [1, 5, 6])` gives three tiers and a remainder.  Every
    token lands in exactly one tier, which is checked here, so a mistyped cut fails
    loudly instead of quietly dropping a token.

    It does NOT choose the cuts.  That is the editorial half and stays yours.
    """
    cuts = sorted(set(int(c) for c in cuts))
    if cuts and (cuts[0] < 1 or cuts[-1] >= len(order)):
        raise ValueError("cuts must be within 1..%d" % (len(order) - 1))
    out, prev = [], 0
    for c in list(cuts) + [len(order)]:
        out.append(tuple(order[prev:c]))
        prev = c
    flat = [t for tier in out for t in tier]
    if len(flat) != len(order) or set(flat) != set(order):
        raise AssertionError("the cuts do not partition the order")
    return tuple(out)
