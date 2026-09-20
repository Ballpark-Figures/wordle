"""Opening a results file for appending, so a KILL cannot lose its header.

THE SCAR (2026-09-19).  Every tool here writes a header when it creates its CSV
and then flushes only per ROW.  Python buffers, so a run killed before its first
row finishes leaves a **ZERO-BYTE file** -- and the next run sees a file that
exists, decides it is not fresh, and refuses to append to it.  MEASURED: nine of
the fourteen halted singles hill-climb runs left an empty file each, and the
restart reported them as holding "PRE-objective (so: guarantee)" results.  The
file held nothing at all.

Two rules, and they belong together because either alone still fails:

  * a header is FLUSHED the moment it is written, so it is on disk before any
    work starts;
  * a file that EXISTS BUT IS EMPTY counts as FRESH, since there is nothing in
    it to conflict with -- which also repairs every empty file already on disk,
    without deleting anything.

`fresh_file` is the second rule in one place.  It is deliberately not a whole
open-and-write-the-header helper: the six callers' headers differ in shape and
rewriting them all would be a much larger diff for no more safety.
"""

import os


def fresh_file(path):
    """Has this path no content yet?  Missing and empty both count.

    An empty file is what a kill between `open` and the first flush leaves, so
    treating it as anything other than fresh turns a crash into a permanent
    refusal.
    """
    return (not os.path.exists(path)) or os.path.getsize(path) == 0
