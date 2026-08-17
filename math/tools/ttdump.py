"""Snapshot the live transposition table to disk so a restart resumes warm.

Safe to run against the RUNNING solver. Entries caught mid-write fail the
h1x XOR verification on lookup and are treated as misses, so a torn snapshot
costs a recompute at worst -- it can never return a wrong value.

    sudo env PYTHONPATH=/home/pliscio/.local/lib/python3.10/site-packages \
         python3 ttdump.py [tt_bits] [outfile]
"""
import os, subprocess, sys, time
import numpy as np

TT_BITS = int(sys.argv[1]) if len(sys.argv) > 1 else 29
OUT = sys.argv[2] if len(sys.argv) > 2 else \
    "/home/pliscio/projects/ballpark-figures/wordle/math/data/local/optturns/tt.bin"
TT_BYTES = (1 << TT_BITS) * 32
ENTRY = np.dtype([("h0", "<u8"), ("h1x", "<u8"), ("val", "<i4"),
                  ("d", "<i4"), ("work", "<u4"), ("pad", "<u4")])

pid = subprocess.check_output(["pgrep", "-x", "optturns"]).decode().split()[0]
base = None
for line in open("/proc/%s/maps" % pid):
    p = line.split()
    lo, hi = [int(x, 16) for x in p[0].split("-")]
    if hi - lo >= TT_BYTES and p[1].startswith("rw"):
        base, mapsize = lo, hi - lo
        break
if base is None:
    sys.exit("could not find the %.2f GiB TT mapping" % (TT_BYTES / 2**30))
print("pid %s  mapping 0x%x  %.3f GiB" % (pid, base, mapsize / 2**30))

mem = open("/proc/%s/mem" % pid, "rb", buffering=0)

# find the byte phase where entries parse (aligned_alloc leaves slack)
mem.seek(base + (mapsize // 2 // 4096) * 4096)
probe = mem.read((1 << 22) + 64)
phase, best = None, -1.0
for ph in range(0, 64, 8):
    a = np.frombuffer(probe[ph:ph + (1 << 22)], dtype=ENTRY)
    live = a[(a["h0"] != 0) | (a["h1x"] != 0)]
    if len(live) < 50:
        continue
    s = float(((live["d"] >= 2) & (live["d"] <= 5)).mean())
    if s > best:
        phase, best = ph, s
if phase is None or best < 0.95:
    sys.exit("could not locate a valid entry phase (best %.2f)" % best)
print("phase %d (%.1f%% legal depth)" % (phase, 100 * best))

CHUNK = 64 << 20
t0, written = time.time(), 0
with open(OUT, "wb") as f:
    while written < TT_BYTES:
        n = min(CHUNK, TT_BYTES - written)
        mem.seek(base + phase + written)
        buf = mem.read(n)
        if len(buf) != n:
            sys.exit("short read at offset %d" % written)
        f.write(buf)
        written += n
        if written % (2 << 30) == 0:
            print("  %.1f / %.1f GiB  (%.0f MB/s)"
                  % (written / 2**30, TT_BYTES / 2**30,
                     written / 1e6 / (time.time() - t0)))
dt = time.time() - t0
print("wrote %s  %.2f GiB in %.0fs (%.0f MB/s)"
      % (OUT, TT_BYTES / 2**30, dt, TT_BYTES / 1e6 / dt))
print("\nrestart later with:  --tt-bits %d --tt-load %s" % (TT_BITS, OUT))
