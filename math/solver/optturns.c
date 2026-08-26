/* optturns.c -- exact minimum expected turns for Wordle, per first guess,
 * with optional extraction of the full optimal decision tree.
 *
 * Objective (integer, not float): minimise TOTAL guesses summed over all 2315
 * answers.  Bertsimas & Paskov's Table 1 is exactly this integer over 2315 --
 * SALET = 7920, REAST = 7923, TRACE = CRATE = 7926, SLATE = 7928 -- so the
 * solver works in integers throughout and comparisons are exact.
 *
 *   f(S, d) = min total guesses to identify every word in S, d guesses left
 *           = min over g of  |S| + sum_{p != ALL_GREEN, S_p != 0} f(S_p, d-1)
 *
 * (every word in S pays for this guess -> |S|; the all-green bucket, nonempty
 * iff g is itself in S, needs nothing further.)
 *
 * Differences from the paper's section 2.2, all of which make this faster:
 *   - opt 3: the paper precomputes |A|*243*2315 = 6.0e9 booleans (~6 GB).  We
 *     reuse the repo's patterns.npy (12972 x 2315 uint8, 30 MB) and get the
 *     successor bucket by counting-sort on a single row.  Fits in cache.
 *   - opt 4: the paper's bound LB = (2|S|-1)/|S| is 2.000 at the root.  A guess
 *     yields <= 243 patterns, so at most 242^(k-1) words can be resolved at
 *     cost exactly k; the resulting greedy bound is 6701/2315 = 2.895 at the
 *     root.  Much tighter, prunes far harder.
 *   - the paper describes no transposition table.  Deep states recur constantly
 *     across different openers; the shared TT is what makes the full sweep over
 *     all 12972 openers affordable at all.
 *   - early exit: when best == LB(|S|,d) the state is provably done, so we stop
 *     scanning actions immediately.  Very frequent for small |S|.
 *
 * Exactness note: no beta is ever inherited from the parent.  f(S_p, d-1) must
 * be exact because it is SUMMED, not compared -- so every memoised value is a
 * true optimum and is safe to reuse anywhere.  Pruning happens only *within* a
 * state, against that state's own incumbent.
 *
 * Hot-loop notes (these dominate runtime; see git history for the slow version):
 *   - the per-guess partition NEVER memsets the 243-entry counter array.  It
 *     records which patterns it touched and clears only those, so scoring a
 *     guess costs O(n) rather than O(243 + n).  For the small deep states that
 *     make up most of the tree this was a ~50x saving on the inner loop.
 *   - TT counters are per-thread and folded into the globals once per opener.
 *     As shared globals they were a false-sharing hotspot on every probe.
 *   - the TT is 2-way set associative: slot 0 keeps whichever entry cost the
 *     most nodes to compute, slot 1 takes the most recent.  Replace-always let
 *     a 3-candidate leaf evict a 200-candidate node worth seconds of work.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <ctype.h>
#include <sys/stat.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define NPAT       243
#define ALL_GREEN  242
#define MAXG       13000
/* MAXA bounds the ANSWER set.  It is 13000, not 2315, because --answer-list can
 * make every legal guess a possible answer (the all-words sweep).  Sizing it up
 * cannot change any existing result: LBTAB is only read at n <= NA, and the
 * Zobrist keys are drawn for a < NA, so the first NA values are identical
 * whatever MAXA is.  It costs ~0.9 MB more per-thread arena (buf + tbuf), which
 * validate.sh reproducing all five totals confirms is all it costs. */
#define MAXA       13000
/* MAXD bounds --depth, and hard mode ESCALATES the cap per opener until the
 * opener solves (see solve_escalating), so it needs headroom well past 6.  Cost
 * is ~194 KB of per-thread arena per level: 20 levels is ~3.9 MB per thread,
 * ~78 MB across 20 threads.  Normal mode never escalates and is unaffected. */
#define MAXD       20
#define INF        1000000000

/* HARD is a COMPILE-TIME constant, not a runtime flag: build.sh emits two
 * binaries from this one file, `optturns` (HARD 0) and `hardturns` (HARD 1).
 * Every `if (HARD)` below folds away at -O3, so the normal-mode binary is
 * byte-for-byte the solver it always was -- no branch, no extra indirection in
 * the hot loops -- while both modes keep a single source of truth. */
#ifdef HARDMODE
#define HARD 1
#else
#define HARD 0
#endif

static int      NG, NA;
/* Salts the TT key with the identity of the GUESS SET (see --guess-list).  It is
 * 0 for the full 12972-word list, which leaves every hash bit-identical to what
 * it has always been -- so an existing tt.bin stays valid.  A restricted list
 * sets it, so a snapshot taken under one guess set cannot be silently reused
 * under another: the same candidate set genuinely has a different optimum when
 * the legal guesses differ, and a shared key would return that wrong value. */
static uint64_t GSALT = 0;
static uint8_t *PAT;             /* NG * NA, row-major: PAT[g*NA + a] */
static uint64_t ZOB0[MAXA], ZOB1[MAXA];
static int      ANS2G[MAXA];
static char   (*GWORD)[8];
static char   (*AWORD)[8];
static int      LBTAB[MAXD][MAXA + 1];

/* --------------------------------------------------------------- hard mode
 *
 * Hard mode ("any revealed hints must be used in subsequent guesses") is the
 * NYT rule: a green must be repeated in its position, and a yellow letter must
 * appear SOMEWHERE in the guess -- including, legally, the same square it was
 * yellow on.  Greys impose nothing, so an all-black pattern constrains nothing.
 *
 * The accumulated requirement is therefore just:
 *     green[i]  -- the letter that position i is pinned to, or -1
 *     minc[c]   -- how many copies of letter c the guess must contain
 * both monotone down a line of play.  Call that pair the CONSTRAINT, `Cons`.
 *
 * The constraint is REAL EXTRA STATE, not a function of the candidate set S.
 * S determines an upper bound on it -- a green at i means every word in S has
 * that letter at i -- but not the converse: the words in S can happen to share
 * a letter that was never revealed, and hard mode does not pin an unrevealed
 * letter.  Two lines reaching the same S with different revealed hints have
 * genuinely different legal-guess sets, so `Cons` is hashed into the TT key.
 *
 * The legal set L is a pure function of `Cons`, and candidates are always
 * legal (S subset of L): a word consistent with all feedback necessarily has
 * the greens in place and at least the revealed counts.  So a state can always
 * fall back on guessing one of its own candidates, which is what keeps the
 * n == 1, n == 2 and depth-normalisation shortcuts below valid in hard mode.
 *
 * L is materialised on demand by intersecting precomputed bitsets, and only on
 * a TT MISS -- a hit never needs it.  `Cons` itself is 31 bytes and travels
 * down the recursion by value, so the cheap path stays cheap.
 */

#define BSW  ((MAXG + 63) / 64)          /* bitset words spanning all guesses */

typedef struct {
    int8_t  green[5];                    /* pinned letter 0..25, or -1 */
    uint8_t minc[26];                    /* required occurrences of each letter */
} Cons;

static uint64_t BS_POS[5][26][BSW];      /* guesses with letter c at position i */
static uint64_t BS_CNT[26][6][BSW];      /* guesses containing >= k copies of c */
static uint64_t BS_ALL[BSW];             /* every legal guess; NG..MAXG-1 clear */

static const Cons CONS_NONE = { { -1, -1, -1, -1, -1 }, { 0 } };

static void build_bitsets(void) {
    for (int g = 0; g < NG; g++) {
        BS_ALL[g >> 6] |= 1ULL << (g & 63);
        int cnt[26] = { 0 };
        for (int i = 0; i < 5; i++) {
            int c = GWORD[g][i] - 'a';
            BS_POS[i][c][g >> 6] |= 1ULL << (g & 63);
            cnt[c]++;
        }
        for (int c = 0; c < 26; c++)
            for (int k = 1; k <= cnt[c]; k++)
                BS_CNT[c][k][g >> 6] |= 1ULL << (g & 63);
    }
}

/* Fold the feedback (g, p) into a parent constraint. */
static void cons_apply(Cons *out, const Cons *in, int g, int p) {
    static const int POW3[5] = { 81, 27, 9, 3, 1 };   /* position 0 is the MSB */
    int req[26] = { 0 };
    *out = *in;
    for (int i = 0; i < 5; i++) {
        int t = (p / POW3[i]) % 3;                    /* 0 = b, 1 = y, 2 = g */
        int c = GWORD[g][i] - 'a';
        if (t == 2) { out->green[i] = (int8_t)c; req[c]++; }
        else if (t == 1) req[c]++;
    }
    for (int c = 0; c < 26; c++)
        if (req[c] > out->minc[c]) out->minc[c] = (uint8_t)req[c];
}

/* Expand a constraint into the ascending list of guesses it permits. */
static int cons_legal(const Cons *C, uint16_t *out) {
    uint64_t m[BSW];
    memcpy(m, BS_ALL, sizeof m);
    for (int i = 0; i < 5; i++) {
        int c = C->green[i];
        if (c >= 0) for (int w = 0; w < BSW; w++) m[w] &= BS_POS[i][c][w];
    }
    for (int c = 0; c < 26; c++) {
        int k = C->minc[c];
        if (k) for (int w = 0; w < BSW; w++) m[w] &= BS_CNT[c][k][w];
    }
    int n = 0;
    for (int w = 0; w < BSW; w++) {
        uint64_t x = m[w];
        while (x) {
            int b = __builtin_ctzll(x);
            x &= x - 1;
            out[n++] = (uint16_t)((w << 6) + b);
        }
    }
    return n;
}

/* Mixed into the TT key so hard-mode entries can never be confused with
 * normal-mode ones -- including across a tt.bin snapshot loaded into the wrong
 * binary, which then simply fails verification and costs a recompute. */
static inline uint64_t cons_hash(const Cons *C) {
    uint64_t h = 0x243F6A8885A308D3ULL;               /* hard-mode salt */
    for (int i = 0; i < 5; i++)
        h = (h ^ (uint64_t)(uint8_t)(C->green[i] + 1)) * 0x100000001B3ULL;
    for (int c = 0; c < 26; c++)
        h = (h ^ (uint64_t)C->minc[c]) * 0x100000001B3ULL;
    return h;
}

/* ---------------------------------------------------------------- helpers */

static uint64_t splitmix64(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static void pat_str(int code, char *out) {   /* base-3, position 0 = MSB */
    for (int i = 4; i >= 0; i--) { out[i] = "byg"[code % 3]; code /= 3; }
    out[5] = 0;
}

/* --------------------------------------------------------------- loading */

static int load_words(const char *path, char (*out)[8]) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (len == 0) continue;
        if (len > 6) len = 6;
        memcpy(out[n], line, len);
        out[n][len] = 0;
        n++;
    }
    fclose(f);
    return n;
}

static uint8_t *load_npy(const char *path, int *rows, int *cols) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char magic[6];
    if (fread(magic, 1, 6, f) != 6 || memcmp(magic, "\x93NUMPY", 6)) {
        fprintf(stderr, "%s is not a .npy file\n", path); exit(1);
    }
    unsigned char ver[2];
    if (fread(ver, 1, 2, f) != 2) exit(1);
    size_t hlen;
    if (ver[0] == 1) {
        unsigned char b[2];
        if (fread(b, 1, 2, f) != 2) exit(1);
        hlen = b[0] | (b[1] << 8);
    } else {
        unsigned char b[4];
        if (fread(b, 1, 4, f) != 4) exit(1);
        hlen = (size_t)b[0] | ((size_t)b[1] << 8) | ((size_t)b[2] << 16) | ((size_t)b[3] << 24);
    }
    char *hdr = malloc(hlen + 1);
    if (fread(hdr, 1, hlen, f) != hlen) exit(1);
    hdr[hlen] = 0;
    if (!strstr(hdr, "u1")) { fprintf(stderr, "patterns.npy not uint8: %s\n", hdr); exit(1); }
    char *p = strchr(hdr, '(');
    if (!p || sscanf(p, "(%d, %d)", rows, cols) != 2) {
        fprintf(stderr, "cannot parse shape from: %s\n", hdr); exit(1);
    }
    free(hdr);
    size_t nbytes = (size_t)(*rows) * (size_t)(*cols);
    uint8_t *data = malloc(nbytes);
    if (!data) { fprintf(stderr, "out of memory for pattern matrix\n"); exit(1); }
    if (fread(data, 1, nbytes, f) != nbytes) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return data;
}

/* ------------------------------------------------------------ lower bound */

static void build_lb(void) {
    for (int d = 0; d < MAXD; d++)
        for (int n = 0; n <= NA; n++) LBTAB[d][n] = INF;
    for (int d = 0; d < MAXD; d++) {
        LBTAB[d][0] = 0;
        for (int n = 1; n <= NA; n++) {
            long long rem = n, total = 0, cap = 1;
            int ok = 0;
            for (int k = 1; k <= d; k++) {
                long long take = rem < cap ? rem : cap;
                total += take * k;
                rem -= take;
                if (rem == 0) { ok = 1; break; }
                if (cap < MAXA) cap *= 242;
            }
            LBTAB[d][n] = ok ? (int)total : INF;
        }
    }
}

/* ------------------------------------------------- transposition table */

/* 32 bytes; two per 64-byte bucket, so a probe touches exactly one cache line */
typedef struct { uint64_t h0, h1x; int32_t val, d; uint32_t work, pad; } Entry;

static Entry   *TT;
static uint64_t TT_BUCKETS;
static long long g_probe = 0, g_hit = 0, g_fill = 0;
static size_t   TT_SLOTS = 0;

static size_t TT_BYTES = 0;

/* --tt-bits 0 runs with NO transposition table at all.  It exists for the
 * memory-starved phase where another solver owns the RAM; it is enormously
 * slower, because deep states recur constantly and every recurrence is then
 * recomputed from scratch.  A small table (--tt-bits 24 = 512 MB) is worth
 * orders of magnitude over none. */
static int TT_OFF = 0;

/* Load a table snapshot. Entries are self-verifying -- h1x carries h1 XORed
 * with the payload -- so a snapshot taken from a RUNNING solver is safe:
 * anything caught mid-write fails the check on lookup and is treated as a
 * miss, never a wrong value. A size mismatch means a different --tt-bits. */
static int tt_load(const char *path, size_t bytes) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "tt-load: cannot open %s\n", path); return -1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    if ((size_t)sz != bytes) {
        fprintf(stderr, "tt-load: %s is %ld bytes, expected %zu -- wrong --tt-bits?\n",
                path, sz, bytes);
        fclose(f);
        return -1;
    }
    rewind(f);
    double t0 = now_s();
    size_t got = 0;
    while (got < bytes) {
        size_t n = fread((char *)TT + got, 1, bytes - got, f);
        if (n == 0) { fprintf(stderr, "tt-load: short read at %zu\n", got); fclose(f); return -1; }
        got += n;
    }
    fclose(f);
    size_t live = 0;                    /* so occupancy starts from the truth */
    for (size_t i = 0; i < TT_SLOTS; i++)
        if (TT[i].h0 || TT[i].h1x) live++;
    g_fill = (long long)live;
    fprintf(stderr, "TT: loaded %s in %.1fs, %zu/%zu slots live (%.2f%%)\n",
            path, now_s() - t0, live, TT_SLOTS, 100.0 * live / TT_SLOTS);
    return 0;
}

static void tt_save(const char *path) {
    if (TT_OFF) { fprintf(stderr, "tt-save: no table to save (--tt-bits 0)\n"); return; }
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "tt-save: cannot write %s\n", path); return; }
    double t0 = now_s();
    size_t put = 0;
    while (put < TT_BYTES) {
        size_t n = fwrite((char *)TT + put, 1, TT_BYTES - put, f);
        if (n == 0) { fprintf(stderr, "tt-save: short write at %zu\n", put); break; }
        put += n;
    }
    fclose(f);
    fprintf(stderr, "TT: saved %.2f GB to %s in %.1fs\n", put / 1e9, path, now_s() - t0);
}

static void tt_init(int bits, const char *loadpath) {
    if (bits <= 0) {
        TT_OFF = 1;
        fprintf(stderr, "TT: DISABLED (--tt-bits 0) -- no memoisation\n");
        return;
    }
    if (bits < 2) bits = 2;
    TT_BUCKETS = (uint64_t)1 << (bits - 1);
    size_t bytes = (size_t)TT_BUCKETS * 2 * sizeof(Entry);
    TT_BYTES = bytes;
    TT = aligned_alloc(64, bytes);
    if (!TT) { fprintf(stderr, "cannot allocate %.2f GB TT\n", bytes / 1e9); exit(1); }
    TT_SLOTS = (size_t)TT_BUCKETS * 2;
    fprintf(stderr, "TT: 2^%d entries (%llu buckets x2), %.2f GB\n",
            bits, (unsigned long long)TT_BUCKETS, bytes / 1e9);
    if (!loadpath || tt_load(loadpath, bytes) != 0) {
        if (loadpath) fprintf(stderr, "TT: starting cold instead\n");
        memset(TT, 0, bytes);
    }
}

/* In hard mode the constraint is part of the state, so it is part of the key
 * (see the hard-mode block above).  `ch` is 0 in normal mode, leaving the hash
 * bit-identical to what it has always been. */
static inline void hash_state(const uint16_t *S, int n, int d, uint64_t ch,
                              uint64_t *h0, uint64_t *h1) {
    uint64_t a = (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    uint64_t b = (uint64_t)d * 0xC2B2AE3D27D4EB4FULL;
    for (int i = 0; i < n; i++) { a ^= ZOB0[S[i]]; b ^= ZOB1[S[i]]; }
    *h0 = a ^ ch ^ GSALT;
    *h1 = b ^ (ch * 0xD6E8FEB86659FD93ULL) ^ (GSALT * 0x9E3779B97F4A7C15ULL);
}

/* h1 is stored XORed with the payload, so a write torn by a concurrent writer
 * fails verification instead of returning a wrong value. */
static inline uint64_t tt_payload(int val, int d, int bestg) {
    return ((uint64_t)(uint32_t)val << 32) ^ (uint64_t)(uint32_t)d
         ^ ((uint64_t)(uint32_t)bestg << 16);
}

static inline int tt_get(uint64_t h0, uint64_t h1, int d, int *val, int *bestg) {
    if (TT_OFF) return 0;
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++) {
        Entry e = b[j];
        if (e.h0 == h0 && e.d == d
            && (e.h1x ^ tt_payload(e.val, e.d, (int)e.pad)) == h1) {
            *val = e.val;
            if (bestg) *bestg = (int)e.pad;
            return 1;
        }
    }
    return 0;
}

/* slot 0 keeps the costliest entry, slot 1 takes the most recent */
static inline void tt_put(uint64_t h0, uint64_t h1, int d, int val, int bestg,
                          uint32_t work, long long *fills) {
    if (TT_OFF) return;
    Entry e;
    e.h0 = h0; e.val = val; e.d = d; e.work = work; e.pad = (uint32_t)bestg;
    e.h1x = h1 ^ tt_payload(val, d, bestg);
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++)
        if (b[j].h0 == h0 && b[j].d == d) { b[j] = e; return; }
    if (b[0].h0 == 0 && b[0].h1x == 0) { b[0] = e; (*fills)++; return; }
    if (b[1].h0 == 0 && b[1].h1x == 0) { b[1] = e; (*fills)++; return; }
    if (work >= b[0].work) { b[1] = b[0]; b[0] = e; }
    else                     b[1] = e;
}

/* ------------------------------------------------------ per-thread arena */

typedef struct {
    uint16_t buf[MAXD][MAXA];
    uint16_t tbuf[MAXD][MAXA];     /* separate scratch for tree extraction */
    int      cnt[MAXD][NPAT];      /* invariant: all zero between uses */
    int      kof[MAXD][NPAT];      /* pattern -> compact bucket index */
    int      lbg[MAXD][MAXG];
    int64_t  ord[MAXD][MAXG];
    uint16_t leg[MAXD][MAXG];      /* hard mode: guesses this state may play */
    long long nodes, probe, hit, fill;
} Ctx;

static int cmp_i64(const void *a, const void *b) {
    int64_t x = *(const int64_t *)a, y = *(const int64_t *)b;
    return (x > y) - (x < y);
}

/* ---------------------------------------------------------------- solver */

static int solve(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx);

/* Cost of playing guess g at state S.  Returns INF if it cannot finish, or if
 * it provably cannot beat `best` (then the value is a bound, not the true cost
 * -- callers only use it to improve `best`, never to memoise).
 *
 * The caller is responsible for g being legal; in hard mode it comes from the
 * state's legal list.  Each successor bucket inherits the constraint extended
 * by the (g, pattern) feedback that produced it. */
static int eval_guess(const uint16_t *S, int n, int d, int g, int best,
                      const Cons *C, Ctx *ctx) {
    int *cnt = ctx->cnt[d], *kof = ctx->kof[d];
    uint16_t *buf = ctx->buf[d];
    const uint8_t *row = PAT + (size_t)g * NA;
    int bp[NPAT], bcnt[NPAT], bstart[NPAT], bfill[NPAT], nb = 0;

    for (int i = 0; i < n; i++) {
        int p = row[S[i]];
        if (cnt[p]++ == 0) bp[nb++] = p;
    }
    /* snapshot counts and restore cnt[] to all-zero immediately, so every path
     * below is free to return without leaving the arena dirty */
    for (int k = 0; k < nb; k++) { bcnt[k] = cnt[bp[k]]; cnt[bp[k]] = 0; }

    /* largest bucket first: the biggest subproblem settles the bound earliest */
    for (int i = 1; i < nb; i++) {
        int tp = bp[i], tc = bcnt[i], j = i - 1;
        while (j >= 0 && bcnt[j] < tc) { bp[j + 1] = bp[j]; bcnt[j + 1] = bcnt[j]; j--; }
        bp[j + 1] = tp; bcnt[j + 1] = tc;
    }
    for (int k = 0; k < nb; k++) kof[bp[k]] = k;

    int acc = 0;
    for (int k = 0; k < nb; k++) { bstart[k] = acc; bfill[k] = acc; acc += bcnt[k]; }
    for (int i = 0; i < n; i++) buf[bfill[kof[row[S[i]]]]++] = S[i];

    int lbrest = 0;
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN) continue;
        int v = LBTAB[d - 1][bcnt[k]];
        if (v >= INF) return INF;
        lbrest += v;
    }

    int total = n;
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN) continue;
        int own = LBTAB[d - 1][bcnt[k]];
        lbrest -= own;
        if (total + lbrest + own >= best) return INF;
        Cons kid;
        if (HARD) cons_apply(&kid, C, g, bp[k]);
        int v = solve(buf + bstart[k], bcnt[k], d - 1, HARD ? &kid : C, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest >= best) return INF;
    }
    return total;
}

static int solve(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx) {
    if (n == 1) return 1;
    if (d <= 1) return INF;
    if (n == 2) return 3;                       /* guess one: 1 + 2 */

    /* Depth normalisation: every guess in an optimal line strictly shrinks the
     * candidate set, so n candidates are always resolved within n guesses --
     * beyond that the budget cannot bind and f(S,d) == f(S,n).  Collapsing the
     * key raises the TT hit rate for small sets reached with lots of budget.
     * Holds in hard mode too: a candidate is always a legal guess, so guessing
     * candidates one at a time resolves n of them in at most n turns. */
    if (d > n) d = n;

    int lb0 = LBTAB[d][n];
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(S, n, d, HARD ? cons_hash(C) : 0, &h0, &h1);
    int cached, cachedg;
    ctx->probe++;
    if (tt_get(h0, h1, d, &cached, &cachedg)) { ctx->hit++; return cached; }

    /* Only now, past the TT, is the legal set worth materialising. */
    uint16_t *leg = ctx->leg[d];
    int nleg = HARD ? cons_legal(C, leg) : NG;

    long long nodes0 = ctx->nodes++;
    int best = INF, bestg = -1;

    /* d == 2 closed form: the only finisher is a guess whose non-green buckets
     * are all singletons, costing 2n - (1 if g is itself in S). */
    if (d == 2) {
        int *cnt = ctx->cnt[d];
        for (int pass = 0; pass < 2; pass++) {
            int lim = (pass == 0) ? n : nleg;
            for (int t = 0; t < lim; t++) {
                int g = (pass == 0) ? ANS2G[S[t]] : (HARD ? (int)leg[t] : t);
                const uint8_t *row = PAT + (size_t)g * NA;
                /* Count every element -- never break early.  bp[] must end up
                 * holding EVERY touched pattern or the clear loop below leaks
                 * counters into the next call and corrupts the arena. */
                int bp[NPAT], nb = 0, dup = 0;
                for (int i = 0; i < n; i++) {
                    int p = row[S[i]];
                    if (cnt[p]++ == 0) bp[nb++] = p;
                    else if (p != ALL_GREEN) dup = 1;
                }
                int green = cnt[ALL_GREEN] > 0;
                for (int k = 0; k < nb; k++) cnt[bp[k]] = 0;
                if (dup) continue;
                if (green) { best = 2 * n - 1; bestg = g; goto d2done; }
                if (2 * n < best) { best = 2 * n; bestg = g; }
            }
        }
    d2done:
        tt_put(h0, h1, d, best, bestg, 1, &ctx->fill);
        return best;
    }

    /* pass 1: per-guess lower bound from its partition profile */
    int *cnt = ctx->cnt[d], *lbg = ctx->lbg[d];
    int bestlb = INF, bestlb_g = -1, bestlb_in = 0;
    for (int t = 0; t < nleg; t++) {
        int g = HARD ? (int)leg[t] : t;
        const uint8_t *row = PAT + (size_t)g * NA;
        int bp[NPAT], nb = 0;
        for (int i = 0; i < n; i++) {
            int p = row[S[i]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        int lv = n, dead = 0, ing = 0;
        for (int k = 0; k < nb; k++) {
            int p = bp[k], c = cnt[p];
            if (p == ALL_GREEN) { ing = 1; continue; }
            if (c == n) { dead = 1; break; }             /* guess reveals nothing */
            int v = LBTAB[d - 1][c];
            if (v >= INF) { dead = 1; break; }
            lv += v;
        }
        for (int k = 0; k < nb; k++) cnt[bp[k]] = 0;
        lbg[g] = dead ? INF : lv;
        if (!dead && (lv < bestlb || (lv == bestlb && ing && !bestlb_in))) {
            bestlb = lv; bestlb_g = g; bestlb_in = ing;
        }
    }
    if (bestlb_g < 0) { tt_put(h0, h1, d, INF, -1, 1, &ctx->fill); return INF; }

    /* seed the incumbent with the most promising guess; only guesses whose
     * bound still undercuts it are worth sorting or exploring at all */
    int v0 = eval_guess(S, n, d, bestlb_g, INF, C, ctx);
    if (v0 < best) { best = v0; bestg = bestlb_g; }

    if (best > lb0) {
        int64_t *ord = ctx->ord[d];
        int m = 0;
        /* iterate the legal list, not 0..NG: lbg[] was only written for legal
         * guesses this call, so anything else is a stale value from a previous
         * state at this depth */
        for (int t = 0; t < nleg; t++) {
            int g = HARD ? (int)leg[t] : t;
            if (lbg[g] < best && g != bestlb_g)
                ord[m++] = ((int64_t)lbg[g] << 20) | (int64_t)g;
        }
        qsort(ord, m, sizeof(int64_t), cmp_i64);
        for (int i = 0; i < m; i++) {
            if ((int)(ord[i] >> 20) >= best) break;   /* sorted: none left can win */
            int g = (int)(ord[i] & 0xFFFFF);
            int v = eval_guess(S, n, d, g, best, C, ctx);
            if (v < best) { best = v; bestg = g; }
            if (best <= lb0) break;                   /* provably optimal */
        }
    }

    long long work = ctx->nodes - nodes0;
    tt_put(h0, h1, d, best, bestg,
           work > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)work, &ctx->fill);
    return best;
}

/* --------------------------------------------------------- tree extraction */

/* Optimal guess at S.  Fast path is the TT slot written by solve(); if that has
 * been evicted, rescan for a guess achieving the known value (eval_guess with
 * bound v+1 returns v exactly when g is optimal, else INF). */
static int best_move(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx) {
    if (n == 1 || n == 2) return ANS2G[S[0]];   /* a candidate is always legal */
    int v = solve(S, n, d, C, ctx);
    if (v >= INF) return -1;
    if (d > n) d = n;
    uint64_t h0, h1;
    hash_state(S, n, d, HARD ? cons_hash(C) : 0, &h0, &h1);
    int val, bg;
    if (tt_get(h0, h1, d, &val, &bg) && bg >= 0 && val == v) return bg;
    uint16_t *leg = ctx->leg[d];
    int nleg = HARD ? cons_legal(C, leg) : NG;
    for (int pass = 0; pass < 2; pass++) {
        int lim = (pass == 0) ? n : nleg;
        for (int t = 0; t < lim; t++) {
            int g = (pass == 0) ? ANS2G[S[t]] : (HARD ? (int)leg[t] : t);
            if (eval_guess(S, n, d, g, v + 1, C, ctx) == v) return g;
        }
    }
    return -1;
}

/* Emit one line per answer: "<answer> <nguesses> <g1> <p1> <g2> <p2> ... <answer>"
 * The final guess always equals the answer, so each line is a complete replay. */
static int emit_tree(FILE *out, const uint16_t *S, int n, int d,
                     char *path, int plen, int ply, const Cons *C, Ctx *ctx) {
    int g = best_move(S, n, d, C, ctx);
    if (g < 0) return -1;
    const char *gw = GWORD[g];

    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    uint16_t *buf = ctx->tbuf[d];
    const uint8_t *row = PAT + (size_t)g * NA;
    memset(cnt, 0, sizeof cnt);
    for (int i = 0; i < n; i++) cnt[row[S[i]]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int i = 0; i < n; i++) buf[fill[row[S[i]]]++] = S[i];

    if (cnt[ALL_GREEN] > 0) {                    /* guess is itself the answer */
        int a = buf[start[ALL_GREEN]];
        fprintf(out, "%s %d %.*s%s\n", AWORD[a], ply + 1, plen, path, gw);
    }
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        char ps[6];
        pat_str(p, ps);
        int add = snprintf(path + plen, 4096 - plen, "%s %s ", gw, ps);
        Cons kid;
        if (HARD) cons_apply(&kid, C, g, p);
        if (emit_tree(out, buf + start[p], cnt[p], d - 1, path, plen + add, ply + 1,
                      HARD ? &kid : C, ctx) < 0)
            return -1;
    }
    return 0;
}

/* ------------------------------------------------------------ root driver */

static int solve_opener(int g, int depth, Ctx *ctx) {
    uint16_t root[MAXA];
    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    const uint8_t *row = PAT + (size_t)g * NA;
    memset(cnt, 0, sizeof cnt);
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int a = 0; a < NA; a++) root[fill[row[a]]++] = (uint16_t)a;

    int total = NA;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        Cons kid;                                /* the opener itself is unconstrained */
        if (HARD) cons_apply(&kid, &CONS_NONE, g, p);
        int v = solve(root + start[p], cnt[p], depth - 1, HARD ? &kid : &CONS_NONE, ctx);
        if (v >= INF) return INF;
        total += v;
    }
    return total;
}

/* Solve `g` at the SMALLEST cap that admits a solution, starting at `dmin` and
 * raising it one guess at a time up to `dmax`.
 *
 * This is the hard-mode answer to a problem normal mode does not have: there,
 * every opener wins within 6 by following SALET's tree afterwards, so one fixed
 * cap suffices.  Hard mode has no such escape -- the follow-up must keep reusing
 * the revealed hints -- so a fixed cap simply returns NOTHING for the openers it
 * cannot fit, which is exactly the data we want.  Escalating instead yields both
 * the total AND the number of guesses that opener actually requires.
 *
 * NOTE what this does and does not compute.  It returns the minimum total at the
 * FIRST feasible cap.  Because f(S,d) is non-increasing in d, a still-deeper cap
 * may admit a LOWER total -- letting one answer run long to save guesses
 * elsewhere.  So `*used` is the minimum feasible DEPTH and the total is optimal
 * SUBJECT TO that depth; it is not, in general, the unconstrained minimum
 * expected guesses.  Establishing that needs a separate stabilisation pass, for
 * which the per-opener (total, depth) recorded in the CSV is the seed. */
static int solve_escalating(int g, int dmin, int dmax, Ctx *ctx, int *used) {
    for (int d = dmin; d <= dmax; d++) {
        int total = solve_opener(g, d, ctx);
        if (total < INF) { *used = d; return total; }
    }
    *used = 0;
    return INF;
}

/* --------------------------------------------- root branch-and-bound (--optimal-only)
 *
 * For finding THE optimal opener and nothing else.  A full sweep spends nearly
 * all its time proving exact totals for openers that were never going to win;
 * this proves the winner instead, and merely bounds everyone else.
 *
 * CUTOFF is "provably worse than the bound" -- a real answer to the only
 * question being asked, distinct from INF ("cannot solve within the cap"). */
#define CUTOFF (INF - 1)

/* The opener's root lower bound: no search at all, O(NA).
 *
 * Every answer costs the opener itself (NA), plus at least LBTAB[d-1][|P|] for
 * each surviving partition P.  Since the sweep visits openers in ASCENDING LB,
 * the first opener whose LB exceeds the incumbent proves every opener after it
 * is worse too -- so the tail is discarded wholesale, without being solved. */
static int root_lb(int g, int depth) {
    int cnt[NPAT];
    const uint8_t *row = PAT + (size_t)g * NA;
    memset(cnt, 0, sizeof cnt);
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int lb = NA;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        int v = LBTAB[depth - 1][cnt[p]];
        if (v >= INF) return INF;
        lb += v;
    }
    return lb;
}

/* Exact total if it is <= `bound`, CUTOFF if provably above it, INF if the
 * opener cannot solve within `depth`.
 *
 * The bound lives ONLY at this level, between the root's partitions.  It is
 * deliberately NOT passed into solve(): those values are memoised, and the
 * exactness note at the top of this file is explicit that a beta inherited from
 * a parent would store a bound where an exact value belongs and poison every
 * later query.  Cutting between root partitions changes nothing that is stored.
 *
 * Partitions are solved LARGEST FIRST so the costliest subproblem gets the first
 * chance to blow the budget, before the cheap ones have been paid for.
 *
 * TIES SURVIVE.  The test is `> bound`, never `>=`: an opener whose true total
 * equals the incumbent always satisfies partial + lbrest <= true total <= bound,
 * so it is never cut and is still reported. */
static int solve_opener_bounded(int g, int depth, Ctx *ctx, int bound) {
    uint16_t root[MAXA];
    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    const uint8_t *row = PAT + (size_t)g * NA;
    memset(cnt, 0, sizeof cnt);
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int a = 0; a < NA; a++) root[fill[row[a]]++] = (uint16_t)a;

    int ps[NPAT], np = 0;
    for (int p = 0; p < NPAT; p++)
        if (p != ALL_GREEN && cnt[p] > 0) ps[np++] = p;
    for (int i = 1; i < np; i++) {                  /* insertion sort, np <= 242 */
        int key = ps[i], j = i - 1;
        while (j >= 0 && cnt[ps[j]] < cnt[key]) { ps[j + 1] = ps[j]; j--; }
        ps[j + 1] = key;
    }

    int lbrest = 0;
    for (int i = 0; i < np; i++) {
        int v = LBTAB[depth - 1][cnt[ps[i]]];
        if (v >= INF) return INF;
        lbrest += v;
    }

    int total = NA;
    if (total + lbrest > bound) return CUTOFF;
    for (int i = 0; i < np; i++) {
        int p = ps[i];
        lbrest -= LBTAB[depth - 1][cnt[p]];
        Cons kid;
        if (HARD) cons_apply(&kid, &CONS_NONE, g, p);
        int v = solve(root + start[p], cnt[p], depth - 1, HARD ? &kid : &CONS_NONE, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest > bound) return CUTOFF;
    }
    return total;
}

static int write_tree(const char *dir, int g, int depth, Ctx *ctx) {
    char cmd[1200];
    snprintf(cmd, sizeof cmd, "gzip -1 > '%s/%s.txt.gz'", dir, GWORD[g]);
    FILE *out = popen(cmd, "w");
    if (!out) return -1;

    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    uint16_t *buf = ctx->tbuf[depth];
    const uint8_t *row = PAT + (size_t)g * NA;
    memset(cnt, 0, sizeof cnt);
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int a = 0; a < NA; a++) buf[fill[row[a]]++] = (uint16_t)a;

    char path[4096];
    int rc = 0;
    if (cnt[ALL_GREEN] > 0) fprintf(out, "%s 1 %s\n", GWORD[g], GWORD[g]);
    for (int p = 0; p < NPAT && rc == 0; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        char ps[6];
        pat_str(p, ps);
        int plen = snprintf(path, sizeof path, "%s %s ", GWORD[g], ps);
        Cons kid;
        if (HARD) cons_apply(&kid, &CONS_NONE, g, p);
        rc = emit_tree(out, buf + start[p], cnt[p], depth - 1, path, plen, 1,
                       HARD ? &kid : &CONS_NONE, ctx);
    }
    pclose(out);
    return rc;
}

static int find_word(char (*list)[8], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* heuristic sweep order: fewest expected survivors first, so partial results
 * cover the interesting openers and the TT warms on shared deep states */
static int64_t *sweep_order(void) {
    int64_t *ord = malloc(sizeof(int64_t) * NG);
    for (int g = 0; g < NG; g++) {
        const uint8_t *row = PAT + (size_t)g * NA;
        int cnt[NPAT];
        memset(cnt, 0, sizeof cnt);
        for (int a = 0; a < NA; a++) cnt[row[a]]++;
        int64_t ss = 0;
        for (int p = 0; p < NPAT; p++) ss += (int64_t)cnt[p] * cnt[p];
        ord[g] = (ss << 20) | (int64_t)g;
    }
    qsort(ord, NG, sizeof(int64_t), cmp_i64);
    return ord;
}

int main(int argc, char **argv) {
    const char *datadir = "data";
    const char *openers[64];
    int nopen = 0;
    const char *outpath = NULL, *treedir = NULL;
    const char *ttload = NULL, *ttsave = NULL, *guesslist = NULL;
    const char *answerlist = NULL, *patpath = NULL;
    int optonly = 0;
    int depth = 6, ttbits = 28, threads = 0, sweep = 0, depthmax = -1;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--trees") && i + 1 < argc) treedir = argv[++i];
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth-max") && i + 1 < argc) depthmax = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-load") && i + 1 < argc) ttload = argv[++i];
        else if (!strcmp(argv[i], "--tt-save") && i + 1 < argc) ttsave = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc) guesslist = argv[++i];
        else if (!strcmp(argv[i], "--answer-list") && i + 1 < argc) answerlist = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else if (!strcmp(argv[i], "--optimal-only")) optonly = 1;
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }

    /* Hard mode escalates by default; normal mode keeps ONE fixed cap, so its
     * behaviour and its results are exactly what they have always been. */
    if (depthmax < 0) depthmax = HARD ? MAXD - 1 : depth;
    if (depthmax < depth) depthmax = depth;
    if (depthmax > MAXD - 1) {
        fprintf(stderr, "--depth-max %d exceeds MAXD-1 (%d); raise MAXD and rebuild\n",
                depthmax, MAXD - 1);
        return 1;
    }

    char path[1024];
    GWORD = malloc(sizeof(char[8]) * MAXG);
    AWORD = malloc(sizeof(char[8]) * MAXA);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    /* --answer-list replaces the ANSWER set (the thing the total is summed over).
     * Pointed at guess.txt it makes every legal guess a possible answer, which
     * needs the SQUARE pattern matrix -- hence --patterns alongside it. */
    if (answerlist) snprintf(path, sizeof path, "%s", answerlist);
    else            snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path, AWORD);
    if (NA > MAXA) { fprintf(stderr, "answer list has %d words, MAXA is %d\n", NA, MAXA); return 1; }
    if (patpath) snprintf(path, sizeof path, "%s", patpath);
    else         snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    if (r != NG || c != NA) {
        fprintf(stderr, "pattern matrix %dx%d != words %dx%d\n", r, c, NG, NA);
        return 1;
    }
    fprintf(stderr, "loaded %d guesses x %d answers\n", NG, NA);

    /* --guess-list restricts the LEGAL GUESSES to the words in FILE, compacting
     * GWORD and the pattern matrix down to just those rows.  Every guess loop in
     * the solver enumerates 0..NG-1, and --sweep iterates the same range, so
     * shrinking NG here restricts BOTH the follow-up guesses and the set of
     * openers swept -- with no change to any hot loop.
     *
     * The answers are untouched: the objective is still the total over all NA
     * answers, we are only changing what may be PLAYED.  Pointing this at
     * mystery.txt gives the answers-only variant.
     *
     * Resolve every source row against the ORIGINAL list BEFORE overwriting any
     * of it -- compacting in place while still looking words up would let a
     * lookup miss a word whose slot had already been reused. */
    if (guesslist) {
        char (*rw)[8] = malloc(sizeof(char[8]) * MAXG);
        int nr = load_words(guesslist, rw);
        if (nr < 1 || nr > MAXG) {
            fprintf(stderr, "--guess-list %s: %d words\n", guesslist, nr); return 1;
        }
        int *map = malloc(sizeof(int) * nr);
        for (int i = 0; i < nr; i++) {
            map[i] = find_word(GWORD, NG, rw[i]);
            if (map[i] < 0) {
                fprintf(stderr, "--guess-list word %s is not a legal guess\n", rw[i]);
                return 1;
            }
        }
        uint8_t *np = malloc((size_t)nr * NA);
        if (!np) { fprintf(stderr, "out of memory compacting pattern matrix\n"); return 1; }
        for (int i = 0; i < nr; i++) {
            memcpy(np + (size_t)i * NA, PAT + (size_t)map[i] * NA, NA);
            memcpy(GWORD[i], rw[i], 8);
        }
        free(map); free(rw); free(PAT);
        PAT = np;
        NG = nr;
        fprintf(stderr, "guess list: restricted to %d words from %s\n", nr, guesslist);
    }

    /* TT keys are comparable ONLY within one (guess set, answer set) pair, and
     * BOTH halves matter:
     *   - a different GUESS set gives the same candidate set a different optimum;
     *   - a different ANSWER set is worse still, because the Zobrist values are
     *     indexed by ANSWER INDEX, so index 7 is simply a different word and every
     *     key silently means something else.
     * Either way a foreign tt.bin would return confidently wrong values rather
     * than missing, so salt on both. Zero when both lists are the defaults, which
     * keeps the existing hashes bit-identical and existing snapshots valid. */
    if (guesslist || answerlist) {
        GSALT = 0xCBF29CE484222325ULL
              ^ ((uint64_t)NG * 0xD6E8FEB86659FD93ULL)
              ^ ((uint64_t)NA * 0x9E3779B97F4A7C15ULL);
        for (int i = 0; i < NG; i++)
            for (int j = 0; GWORD[i][j]; j++)
                GSALT = (GSALT ^ (uint8_t)GWORD[i][j]) * 0x100000001B3ULL;
        for (int i = 0; i < NA; i++)
            for (int j = 0; AWORD[i][j]; j++)
                GSALT = (GSALT ^ (uint8_t)AWORD[i][j]) * 0x100000001B3ULL;
        fprintf(stderr, "TT salt %016llx (%d guesses, %d answers)\n",
                (unsigned long long)GSALT, NG, NA);
    }

    for (int a = 0; a < NA; a++) {
        ANS2G[a] = find_word(GWORD, NG, AWORD[a]);
        if (ANS2G[a] < 0) { fprintf(stderr, "answer %s not a legal guess\n", AWORD[a]); return 1; }
    }
    uint64_t seed = 0xD1B54A32D192ED03ULL;
    for (int a = 0; a < NA; a++) { ZOB0[a] = splitmix64(&seed); ZOB1[a] = splitmix64(&seed); }

    if (HARD) { build_bitsets(); fprintf(stderr, "mode: HARD\n"); }
    else      fprintf(stderr, "mode: normal\n");

    build_lb();
    fprintf(stderr, "root LB(d=%d, n=%d) = %d  (%.5f avg)\n",
            depth, NA, LBTAB[depth][NA], (double)LBTAB[depth][NA] / NA);
    tt_init(ttbits, ttload);
    if (treedir) mkdir(treedir, 0755);

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#endif

    if (nopen > 0) {
        Ctx *ctx = calloc(1, sizeof(Ctx));
        for (int k = 0; k < nopen; k++) {
            int g = find_word(GWORD, NG, openers[k]);
            if (g < 0) { fprintf(stderr, "no such guess word: %s\n", openers[k]); return 1; }
            double t0 = now_s();
            int used = 0;
            int total = solve_escalating(g, depth, depthmax, ctx, &used);
            if (total < INF && treedir) write_tree(treedir, g, used, ctx);
            double dt = now_s() - t0;
            if (total >= INF)
                printf("%s  INFEASIBLE within %d guesses  (%.1fs)\n", openers[k], depthmax, dt);
            else
                printf("%s  total=%d  expected=%.5f  d=%d  (%.1fs, %lld nodes, TT %.3f%% hit)\n",
                       openers[k], total, (double)total / NA, used, dt, ctx->nodes,
                       100.0 * ctx->hit / (ctx->probe ? ctx->probe : 1));
            fflush(stdout);
        }
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    /* ------------------------------------------------- --optimal-only sweep */
    if (optonly) {
        if (!sweep) { fprintf(stderr, "--optimal-only requires --sweep\n"); return 1; }

        int *lb = malloc(sizeof(int) * NG);
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int g = 0; g < NG; g++) lb[g] = root_lb(g, depth);

        int64_t *ord = malloc(sizeof(int64_t) * NG);
        int nord = 0, nolb = 0;
        for (int g = 0; g < NG; g++) {
            if (lb[g] >= INF) { nolb++; continue; }   /* cannot fit the cap at all */
            ord[nord++] = ((int64_t)lb[g] << 20) | (int64_t)g;
        }
        qsort(ord, nord, sizeof(int64_t), cmp_i64);
        fprintf(stderr, "root LB screen: %d openers ranked, %d rejected outright\n",
                nord, nolb);

        /* Resume: an existing CSV both seeds the incumbent and marks work done.
         * Seeding matters more than skipping -- a good bound from the previous
         * run prunes immediately instead of rediscovering it. */
        int incumbent = INF;
        char *done = calloc(NG, 1);
        int ndone = 0;
        FILE *rf = outpath ? fopen(outpath, "r") : NULL;
        if (rf) {
            char line[256];
            while (fgets(line, sizeof line, rf)) {
                char w[64]; int t;
                if (sscanf(line, "%63[^,],%d", w, &t) != 2) continue;
                int g = find_word(GWORD, NG, w);
                if (g >= 0 && !done[g]) { done[g] = 1; ndone++; }
                if (t > 0 && t < incumbent) incumbent = t;
            }
            fclose(rf);
            if (ndone) fprintf(stderr, "resume: %d searched, incumbent %d\n", ndone, incumbent);
        }
        FILE *out = outpath ? fopen(outpath, "a") : NULL;
        if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (out && ndone == 0) fprintf(out, "word,total,expected,depth,seconds\n");

        int *best = malloc(sizeof(int) * nord);
        /* seen  = reached the critical section (searched + cut + infeasible)
         * lbskip = discarded by the root LB without any search, never reaches it
         * so processed = seen + lbskip, and the two must not be conflated. */
        int nbest = 0, searched = 0, cut = 0, infeas = 0, seen = 0, lbskip = 0;
        double t0 = now_s(), last_report = t0;

        printf("optimal-only: %d openers by ascending root LB (min %d = %.5f avg)\n",
               nord, nord ? (int)(ord[0] >> 20) : 0,
               nord ? (double)(int)(ord[0] >> 20) / NA : 0.0);
        fflush(stdout);

#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            Ctx *ctx = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
            for (int i = 0; i < nord; i++) {
                int g = (int)(ord[i] & 0xFFFFF);
                int mylb = (int)(ord[i] >> 20);
                if (done[g]) continue;
                int inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
                inc = incumbent;
                /* Ascending LB: once this fires it fires for the whole tail. */
                if (mylb > inc) {
#ifdef _OPENMP
#pragma omp atomic
#endif
                    lbskip++;
                    continue;
                }
                double s0 = now_s();
                int total = solve_opener_bounded(g, depth, ctx, inc);
                double dt = now_s() - s0;
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                    ctx->probe = ctx->hit = ctx->fill = 0;
                    seen++;
                    double el = now_s() - t0;
                    double hit = 100.0 * g_hit / (g_probe ? g_probe : 1);
                    double occ = TT_SLOTS ? 100.0 * g_fill / (double)TT_SLOTS : 0.0;
                    if (total >= INF) {
                        infeas++;
                        printf("[%7.0fs] %s  INFEASIBLE within %d   lb=%d  %7.1fs\n",
                               el, GWORD[g], depth, mylb, dt);
                    } else if (total == CUTOFF) {
                        cut++;
                    } else {
                        searched++;
                        if (out) {
                            fprintf(out, "%s,%d,%.5f,%d,%.1f\n",
                                    GWORD[g], total, (double)total / NA, depth, dt);
                            fflush(out);
                        }
                        if (total < incumbent) {
                            incumbent = total;
                            nbest = 0; best[nbest++] = g;
                            printf("[%7.0fs] %s  total=%5d  NEW BEST  lb=%d  %7.1fs  tt %.2f%%/%.2f%%\n",
                                   el, GWORD[g], total, mylb, dt, hit, occ);
                        } else if (total == incumbent) {
                            best[nbest++] = g;
                            printf("[%7.0fs] %s  total=%5d  TIED      lb=%d  %7.1fs  tt %.2f%%/%.2f%%\n",
                                   el, GWORD[g], total, mylb, dt, hit, occ);
                        }
                    }
                    /* Heartbeat on WHICHEVER comes first, count or time.  A count
                     * alone goes silent for many minutes when openers are slow --
                     * which is exactly when you most need to see it moving, and is
                     * indistinguishable from a hang. */
                    if (seen % 100 == 0 || now_s() - last_report >= 30.0) {
                        last_report = now_s();
                        int gone = seen + lbskip, left = nord - gone;
                        printf("[%7.0fs] %5d/%d done (%d searched, %d cut, %d lb-skip, %d infeas)  best=%d  %.1f/min  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                               el, gone, nord, searched, cut, lbskip, infeas, incumbent,
                               gone / (el / 60.0),
                               (left > 0 && gone > 0) ? el / (double)gone * left / 3600.0 : 0.0,
                               hit, occ);
                    }
                    fflush(stdout);
                }
            }
            free(ctx);
        }

        double el = now_s() - t0;
        printf("\n=== OPTIMAL (guesses %d, answers %d, depth %d) ===\n", NG, NA, depth);
        if (incumbent >= INF) {
            printf("NO OPENER solves every answer within %d guesses.\n", depth);
            printf("%d rejected by lower bound, %d proved infeasible by search.\n", nolb, infeas);
        } else {
            printf("total=%d  expected=%.5f  over %d answers\n",
                   incumbent, (double)incumbent / NA, NA);
            printf("%d opener%s attain it:", nbest, nbest == 1 ? "" : "s");
            for (int i = 0; i < nbest; i++) printf(" %s", GWORD[best[i]]);
            printf("\n");
        }
        printf("searched %d, cut %d, lb-skipped %d, infeasible %d, lb-rejected %d, of %d openers in %.0fs\n",
               searched, cut, lbskip, infeas, nolb, NG, el);
        if (out) fclose(out);
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    if (!sweep) { fprintf(stderr, "nothing to do: pass --opener WORD or --sweep\n"); return 1; }
    if (!outpath) { fprintf(stderr, "--sweep needs --out FILE\n"); return 1; }

    char *done = calloc(NG, 1);
    int ndone = 0;
    FILE *rf = fopen(outpath, "r");
    if (rf) {
        char line[256];
        while (fgets(line, sizeof line, rf)) {
            char w[64];
            if (sscanf(line, "%63[^,],", w) != 1) continue;
            int g = find_word(GWORD, NG, w);
            if (g >= 0 && !done[g]) { done[g] = 1; ndone++; }
        }
        fclose(rf);
        fprintf(stderr, "resume: %d openers already done\n", ndone);
    }
    FILE *out = fopen(outpath, "a");
    if (!out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
    if (ndone == 0) fprintf(out, "word,total,expected,depth,seconds\n");

    int64_t *ord = sweep_order();
    double t0 = now_s();
    int completed = 0;

#pragma omp parallel
    {
        Ctx *ctx = calloc(1, sizeof(Ctx));
#pragma omp for schedule(dynamic, 1)
        for (int i = 0; i < NG; i++) {
            int g = (int)(ord[i] & 0xFFFFF);
            if (done[g]) continue;
            double s0 = now_s();
            int used = 0;
            int total = solve_escalating(g, depth, depthmax, ctx, &used);
            int tree_ok = 1;
            if (total < INF && treedir) tree_ok = (write_tree(treedir, g, used, ctx) == 0);
            double dt = now_s() - s0;
#pragma omp critical
            {
                /* fold this thread's counters into the globals, then reset */
                g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                ctx->probe = ctx->hit = ctx->fill = 0;

                if (total >= INF) fprintf(out, "%s,,,,%.1f\n", GWORD[g], dt);
                else              fprintf(out, "%s,%d,%.5f,%d,%.1f\n", GWORD[g], total,
                                          (double)total / NA, used, dt);
                fflush(out);
                completed++;
                double el = now_s() - t0;
                int left = NG - ndone - completed;
                double hit = 100.0 * g_hit / (g_probe ? g_probe : 1);
                double occ = TT_SLOTS ? 100.0 * g_fill / (double)TT_SLOTS : 0.0;
                if (total >= INF)
                    printf("[%7.0fs] %5d/%d  %s  INFEASIBLE d>%-2d          %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], depthmax, dt,
                           el / completed * left / 3600.0, hit, occ);
                else if (guesslist)
                    /* exp= is dropped for a restricted guess set: it is just
                     * total/2315, and the run is read for the OVERALL best
                     * rather than per-word averages.  The trailing tt %/%% is
                     * load-bearing -- report.py and ttscan.py parse it. */
                    printf("[%7.0fs] %5d/%d  %s  total=%5d  d=%d%s%s %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], total,
                           used, used > depth ? " *" : "  ",
                           tree_ok ? "" : " TREE-FAIL", dt,
                           el / completed * left / 3600.0, hit, occ);
                else
                    printf("[%7.0fs] %5d/%d  %s  total=%5d  exp=%.5f  d=%d%s%s %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], total, (double)total / NA,
                           used, used > depth ? " *" : "  ",
                           tree_ok ? "" : " TREE-FAIL", dt,
                           el / completed * left / 3600.0, hit, occ);
                fflush(stdout);
            }
        }
        free(ctx);
    }
    fclose(out);
    if (ttsave) tt_save(ttsave);
    fprintf(stderr, "sweep complete in %.1fs\n", now_s() - t0);
    return 0;
}
