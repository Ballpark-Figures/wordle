"""Save and reload the per-letter COVERAGE that `notebooks/letter_explorer.ipynb` computes.

    >>> import letter_coverage
    >>> letter_coverage.save(D)                           # from the notebook
    >>> letter_coverage.load(num_trees=1000)              # anywhere afterwards

WHAT IS SAVED.  For each letter and each k, the number of pooled PATHS (every tree x
every answer) whose first k guesses contain that letter at least once -- the notebook's
`D['prefix_paths']`, cumulative in k, exactly what `opener_letter_counts(stat='paths')`
prints.  The file holds those INTEGER counts plus the path count in its stamp, so a
share is `count / paths` and nothing is rounded on disk.

Guess 1 is fixed within a tree, so `first1` is also the share of pooled OPENERS that
contain the letter (each tree contributes 2315 identical first guesses).

The trees minimise TOTAL guesses subject to resolving every answer within 6, so these
counts describe THAT strategy, not an unconstrained expected-guess minimiser.

THE FILE SELF-DESCRIBES AND A MISMATCHED READ IS REFUSED, exactly as `tier_order.py`:
the stamp carries the tree count, the solver and a digest of the pooled opener list
(reusing `tier_order.openers_digest`), and a file with no stamp is refused.  The write
is atomic.
"""

import csv
import os
import string

import tier_order

STEM = "coverage"


def path(num_trees, solver=None):
    """The one file name for these settings."""
    solver = tier_order._solver(solver)
    stem = "%s_top%d" % (STEM, int(num_trees))
    if solver != "optturns":
        stem += "_%s" % solver
    return os.path.join(tier_order.directory(), stem + ".csv")


def _stamp(num_trees, n_paths, k, solver, digest):
    return ("# settings num_trees=%d paths=%d prefix=%d solver=%s openers_sha=%s"
            % (num_trees, n_paths, k, solver, digest))


def save(D, out=None, overwrite=False):
    """Write `D['prefix_paths']` for the trees `D` pooled (`D` from `collect_paths`)."""
    pre = D["prefix_paths"]
    openers = D["openers"]
    n_paths, K = int(D["n"]), int(pre.shape[0])
    if pre.shape[1] != 26:
        raise ValueError("prefix_paths has %d letter columns, not 26" % pre.shape[1])
    solver = tier_order._solver()
    dest = out or path(len(openers), solver)
    if os.path.exists(dest) and not overwrite:
        raise FileExistsError("%s already exists; pass overwrite=True to replace it" % dest)

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    tmp = dest + ".tmp"
    with open(tmp, "w", newline="") as f:
        f.write("# per-letter coverage over the pooled optimal trees: first<k> = number "
                "of PATHS whose first k guesses contain the letter at least once "
                "(cumulative in k).  Share = count / paths.  Exact, no sampling.\n")
        f.write("# The trees minimise TOTAL guesses subject to resolving every answer "
                "within 6, so these counts describe that constrained strategy.\n")
        f.write(_stamp(len(openers), n_paths, K, solver,
                       tier_order.openers_digest(openers)) + "\n")
        f.write("# openers %s%s\n"
                % (", ".join(w for w, _t in openers[:8]),
                   "" if len(openers) <= 8 else ", +%d more" % (len(openers) - 8)))
        w = csv.writer(f)
        w.writerow(["letter"] + ["first%d" % (k + 1) for k in range(K)])
        for i, c in enumerate(string.ascii_lowercase):
            w.writerow([c] + [int(pre[k, i]) for k in range(K)])
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)
    return dest


def load(num_trees=None, solver=None, file=None):
    """Read a saved coverage back.

    Returns `{"paths": int, "settings": {...}, "counts": {letter: [first1, ...]}}`.
    Refuses an unstamped file, or one whose stamp disagrees with `num_trees`/`solver`.
    """
    if file is None:
        if num_trees is None:
            raise ValueError("give num_trees (or file)")
        file = path(num_trees, solver)
    settings = None
    counts = {}
    with open(file) as f:
        lines = f.read().splitlines()
    for line in lines:
        if line.startswith("# settings "):
            settings = dict(kv.split("=", 1) for kv in line[len("# settings "):].split())
    if settings is None:
        raise ValueError("%s has no '# settings' stamp; refusing it" % file)
    if num_trees is not None and int(settings["num_trees"]) != int(num_trees):
        raise ValueError("%s pools %s trees, not %s" % (file, settings["num_trees"], num_trees))
    if solver is not None and settings["solver"] != solver:
        raise ValueError("%s is %s trees, not %s" % (file, settings["solver"], solver))
    rows = csv.reader(l for l in lines if not l.startswith("#"))
    header = next(rows)
    for r in rows:
        counts[r[0]] = [int(v) for v in r[1:]]
    assert sorted(counts) == list(string.ascii_lowercase), "coverage is not 26 letters"
    assert len(header) - 1 == int(settings["prefix"])
    return {"paths": int(settings["paths"]), "settings": settings, "counts": counts}
