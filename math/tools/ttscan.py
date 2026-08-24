"""Estimate how far the in-flight openers have progressed, by reading the live
transposition table out of the running solver.

The TT key is a Zobrist hash, so WHICH states are cached is unrecoverable. But
the depth field is readable, and depth carries the signal we want:

    solve_opener() calls solve(bucket, n, 5) once per root bucket, and solve()
    normalises d to min(d, n). So an entry with d == 5 can ONLY come from a root
    bucket with n >= 5 -- deeper states are all d <= 4. Counting d == 5 entries
    counts COMPLETED ROOT BUCKETS across every opener since the table was made.

Two things the first version of this script got wrong, both now guarded:
  * block offsets must be 32-byte aligned or the fields splice across entries;
  * the TT does NOT start at the mapping base (aligned_alloc leaves slack), so
    the byte phase is detected rather than assumed.
Validity is checked against the occupancy the solver itself prints, so a bad
read is caught instead of reported as data.

Run as root (needs ptrace):
    sudo env PYTHONPATH=/home/pliscio/.local/lib/python3.10/site-packages \
         python3 ttscan.py [fraction]
"""
import csv, os, re, subprocess, sys
import numpy as np

sys.path.insert(0, "/home/pliscio/projects/ballpark-figures/wordle/math")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wordle import load_words
from build_patterns import load_patterns
from paths import CSV_PATH as CSV, LOG, SOLVER, read_rows

N_AT_REBOOT = 8271          # CSV rows already present when the current run started
FRAC = float(sys.argv[1]) if len(sys.argv) > 1 else 0.10
TT_BITS = int(sys.argv[2]) if len(sys.argv) > 2 else 29     # must match --tt-bits
TT_BYTES = (1 << TT_BITS) * 32          # 2^29 entries x 32 B = 16.00 GiB
ENTRY = np.dtype([("h0", "<u8"), ("h1x", "<u8"), ("val", "<i4"),
                  ("d", "<i4"), ("work", "<u4"), ("pad", "<u4")])
assert ENTRY.itemsize == 32

pid = subprocess.check_output(["pgrep", "-x", SOLVER]).decode().split()[0]
mapbase = mapsize = None
for line in open("/proc/%s/maps" % pid):
    p = line.split()
    lo, hi = [int(x, 16) for x in p[0].split("-")]
    if hi - lo >= TT_BYTES and p[1].startswith("rw"):
        mapbase, mapsize = lo, hi - lo
        break
if mapbase is None:
    sys.exit("could not locate the TT mapping")
print("pid %s   mapping 0x%x   %.3f GiB   (table is %.3f GiB, slack %.1f MB)"
      % (pid, mapbase, mapsize / 2**30, TT_BYTES / 2**30, (mapsize - TT_BYTES) / 2**20))

mem = open("/proc/%s/mem" % pid, "rb", buffering=0)

def read_at(off, n):
    mem.seek(off)
    return mem.read(n)

# --- find the byte phase where entries actually parse ------------------------
# score a candidate by how many non-empty entries carry a legal depth (2..5)
PROBE = 1 << 22                                   # 4 MB probe
probe = read_at(mapbase + (mapsize // 2 // 4096) * 4096, PROBE + 64)
best_phase, best_score = None, -1.0
for phase in range(0, 64, 8):                     # alloc is >= 8-byte aligned
    a = np.frombuffer(probe[phase:phase + PROBE], dtype=ENTRY)
    live = a[(a["h0"] != 0) | (a["h1x"] != 0)]
    if len(live) < 50:
        continue
    score = float(((live["d"] >= 2) & (live["d"] <= 5)).mean())
    print("  phase %2d: %6d live, %.1f%% legal depth" % (phase, len(live), 100 * score))
    if score > best_score:
        best_phase, best_score = phase, score
if best_phase is None or best_score < 0.95:
    sys.exit("could not find a valid entry phase (best %.2f) -- aborting rather "
             "than report noise" % (best_score if best_score >= 0 else -1))
print("using phase %d (%.1f%% legal depth)\n" % (best_phase, 100 * best_score))

# --- scan, with every block offset forced onto the 32-byte entry grid --------
NBLOCK = 200
blk = (int(TT_BYTES * FRAC) // NBLOCK) // 32 * 32
stride = (TT_BYTES // NBLOCK) // 32 * 32
occupied = scanned = 0
dhist = np.zeros(8, dtype=np.int64)
for i in range(NBLOCK):
    buf = read_at(mapbase + best_phase + stride * i, blk)
    if len(buf) < blk:
        continue
    a = np.frombuffer(buf, dtype=ENTRY)
    live = a[(a["h0"] != 0) | (a["h1x"] != 0)]
    occupied += len(live)
    scanned += len(a)
    for k in range(8):
        dhist[k] += int((live["d"] == k).sum())

frac = scanned * 32 / TT_BYTES
occ = 100.0 * occupied / scanned
print("scanned %.1f%% (%d entries), occupancy %.2f%%" % (100 * frac, scanned, occ))

logged = None
for line in open(LOG):
    m = re.search(r"tt ([\d.]+)%/([\d.]+)%", line)
    if m:
        logged = float(m.group(2))
if logged is not None:
    print("solver reports occupancy %.2f%%  -> %s"
          % (logged, "MATCH" if abs(logged - occ) < max(1.0, 0.25 * logged) else "MISMATCH, do not trust"))

print("\ndepth histogram, scaled to full table:")
for k in range(8):
    if dhist[k]:
        print("  d=%d  %12d" % (k, int(dhist[k] / frac)))
d5_total = int(dhist[5] / frac)

# --- denominator: root buckets with n >= 5 per opener -----------------------
guesses = load_words("guess")
PAT = np.asarray(load_patterns())
gidx = {w: i for i, w in enumerate(guesses)}

def big_buckets(word):
    c = np.bincount(PAT[gidx[word]], minlength=243)
    c[242] = 0
    return int((c >= 5).sum())

rows = list(read_rows(CSV))          # not DictReader; see paths.read_rows
since = [r["word"] for r in rows[N_AT_REBOOT:]]
done_at_reboot = {r["word"] for r in rows[:N_AT_REBOOT]}
ss = np.array([np.bincount(r, minlength=243).astype(np.int64).__pow__(2).sum() for r in PAT])
order = sorted(range(len(guesses)), key=lambda g: (int(ss[g]), g))
batch = []
for g in order:
    if guesses[g] in done_at_reboot:
        continue
    batch.append(guesses[g])
    if len(batch) == 20:
        break
inflight = [w for w in batch if w not in set(since)]

done_d5 = sum(big_buckets(w) for w in since)
flight_d5 = sum(big_buckets(w) for w in inflight)
rem = d5_total - done_d5
print("\ncompleted since restart: %3d openers -> %5d root buckets expected" % (len(since), done_d5))
print("still running:           %3d openers -> %5d root buckets total" % (len(inflight), flight_d5))
print("observed d=5 entries:    %5d" % d5_total)
print("attributable to in-flight: %5d" % rem)
if flight_d5 and 0 <= rem <= flight_d5 * 1.2:
    print("=> in-flight progress ~%.0f%% of root buckets (%.0f of %.0f per word)"
          % (100 * rem / flight_d5, rem / len(inflight), flight_d5 / len(inflight)))
else:
    print("=> out of range; the attribution assumption is not holding, ignore it")
print("\nCAVEAT: buckets are not equal cost. Position, not time remaining.")
