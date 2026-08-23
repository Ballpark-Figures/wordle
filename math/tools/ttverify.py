"""Sanity-check a tt.bin snapshot WITHOUT loading 16 GiB into RAM.

Checks the file is exactly the right size for its --tt-bits, then samples blocks
across it and confirms the entries parse: live slots should carry depth 2..5,
and occupancy should match what the solver was reporting.

    python3 ttverify.py [path] [tt_bits]
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import LOCAL

PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(LOCAL, "tt.bin")
BITS = int(sys.argv[2]) if len(sys.argv) > 2 else 29
WANT = (1 << BITS) * 32
ENTRY = np.dtype([("h0", "<u8"), ("h1x", "<u8"), ("val", "<i4"),
                  ("d", "<i4"), ("work", "<u4"), ("pad", "<u4")])

if not os.path.exists(PATH):
    sys.exit("MISSING: %s does not exist -- the dump did not run" % PATH)
sz = os.path.getsize(PATH)
print("file  : %s" % PATH)
print("size  : %d bytes (%.3f GiB)" % (sz, sz / 2**30))
print("expect: %d bytes (%.3f GiB) for --tt-bits %d" % (WANT, WANT / 2**30, BITS))
if sz != WANT:
    sys.exit("FAIL: size mismatch -- the loader will reject this file")
print("size  : OK\n")

NBLOCK, BLK = 200, 1 << 20
stride = (WANT // NBLOCK) // 32 * 32
live = scanned = 0
dhist = np.zeros(8, dtype=np.int64)
with open(PATH, "rb") as f:
    for i in range(NBLOCK):
        f.seek(stride * i)
        buf = f.read(BLK)
        if len(buf) < BLK:
            continue
        a = np.frombuffer(buf, dtype=ENTRY)
        L = a[(a["h0"] != 0) | (a["h1x"] != 0)]
        live += len(L)
        scanned += len(a)
        for k in range(8):
            dhist[k] += int((L["d"] == k).sum())

occ = 100.0 * live / scanned
legal = int(dhist[2:6].sum())
tot = int(dhist.sum())
print("sampled %d entries, %d live -> occupancy %.2f%%" % (scanned, live, occ))
print("depth histogram of live entries:")
for k in range(8):
    if dhist[k]:
        print("   d=%d %12d  %6.3f%%" % (k, dhist[k], 100.0 * dhist[k] / tot))
print("\nlegal depths (2-5): %.4f%% of live entries" % (100.0 * legal / tot))
if legal / tot > 0.999 and occ > 1:
    print("\nPASS - snapshot looks well-formed and non-empty.")
    print("A small fraction of odd depths is expected: entries caught mid-write")
    print("fail verification on lookup and are simply treated as misses.")
else:
    print("\nFAIL - entries do not parse cleanly; delete tt.bin and start cold.")
