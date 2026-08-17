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
#define MAXA       2400
#define MAXD       7
#define INF        1000000000

static int      NG, NA;
static uint8_t *PAT;             /* NG * NA, row-major: PAT[g*NA + a] */
static uint64_t ZOB0[MAXA], ZOB1[MAXA];
static int      ANS2G[MAXA];
static char   (*GWORD)[8];
static char   (*AWORD)[8];
static int      LBTAB[MAXD][MAXA + 1];

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

static inline void hash_state(const uint16_t *S, int n, int d, uint64_t *h0, uint64_t *h1) {
    uint64_t a = (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    uint64_t b = (uint64_t)d * 0xC2B2AE3D27D4EB4FULL;
    for (int i = 0; i < n; i++) { a ^= ZOB0[S[i]]; b ^= ZOB1[S[i]]; }
    *h0 = a; *h1 = b;
}

/* h1 is stored XORed with the payload, so a write torn by a concurrent writer
 * fails verification instead of returning a wrong value. */
static inline uint64_t tt_payload(int val, int d, int bestg) {
    return ((uint64_t)(uint32_t)val << 32) ^ (uint64_t)(uint32_t)d
         ^ ((uint64_t)(uint32_t)bestg << 16);
}

static inline int tt_get(uint64_t h0, uint64_t h1, int d, int *val, int *bestg) {
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
    long long nodes, probe, hit, fill;
} Ctx;

static int cmp_i64(const void *a, const void *b) {
    int64_t x = *(const int64_t *)a, y = *(const int64_t *)b;
    return (x > y) - (x < y);
}

/* ---------------------------------------------------------------- solver */

static int solve(const uint16_t *S, int n, int d, Ctx *ctx);

/* Cost of playing guess g at state S.  Returns INF if it cannot finish, or if
 * it provably cannot beat `best` (then the value is a bound, not the true cost
 * -- callers only use it to improve `best`, never to memoise). */
static int eval_guess(const uint16_t *S, int n, int d, int g, int best, Ctx *ctx) {
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
        int v = solve(buf + bstart[k], bcnt[k], d - 1, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest >= best) return INF;
    }
    return total;
}

static int solve(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (n == 1) return 1;
    if (d <= 1) return INF;
    if (n == 2) return 3;                       /* guess one: 1 + 2 */

    /* Depth normalisation: every guess in an optimal line strictly shrinks the
     * candidate set, so n candidates are always resolved within n guesses --
     * beyond that the budget cannot bind and f(S,d) == f(S,n).  Collapsing the
     * key raises the TT hit rate for small sets reached with lots of budget. */
    if (d > n) d = n;

    int lb0 = LBTAB[d][n];
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(S, n, d, &h0, &h1);
    int cached, cachedg;
    ctx->probe++;
    if (tt_get(h0, h1, d, &cached, &cachedg)) { ctx->hit++; return cached; }

    long long nodes0 = ctx->nodes++;
    int best = INF, bestg = -1;

    /* d == 2 closed form: the only finisher is a guess whose non-green buckets
     * are all singletons, costing 2n - (1 if g is itself in S). */
    if (d == 2) {
        int *cnt = ctx->cnt[d];
        for (int pass = 0; pass < 2; pass++) {
            int lim = (pass == 0) ? n : NG;
            for (int t = 0; t < lim; t++) {
                int g = (pass == 0) ? ANS2G[S[t]] : t;
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
    for (int g = 0; g < NG; g++) {
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
    int v0 = eval_guess(S, n, d, bestlb_g, INF, ctx);
    if (v0 < best) { best = v0; bestg = bestlb_g; }

    if (best > lb0) {
        int64_t *ord = ctx->ord[d];
        int m = 0;
        for (int g = 0; g < NG; g++)
            if (lbg[g] < best && g != bestlb_g)
                ord[m++] = ((int64_t)lbg[g] << 20) | (int64_t)g;
        qsort(ord, m, sizeof(int64_t), cmp_i64);
        for (int i = 0; i < m; i++) {
            if ((int)(ord[i] >> 20) >= best) break;   /* sorted: none left can win */
            int g = (int)(ord[i] & 0xFFFFF);
            int v = eval_guess(S, n, d, g, best, ctx);
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
static int best_move(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (n == 1 || n == 2) return ANS2G[S[0]];
    int v = solve(S, n, d, ctx);
    if (v >= INF) return -1;
    if (d > n) d = n;
    uint64_t h0, h1;
    hash_state(S, n, d, &h0, &h1);
    int val, bg;
    if (tt_get(h0, h1, d, &val, &bg) && bg >= 0 && val == v) return bg;
    for (int pass = 0; pass < 2; pass++) {
        int lim = (pass == 0) ? n : NG;
        for (int t = 0; t < lim; t++) {
            int g = (pass == 0) ? ANS2G[S[t]] : t;
            if (eval_guess(S, n, d, g, v + 1, ctx) == v) return g;
        }
    }
    return -1;
}

/* Emit one line per answer: "<answer> <nguesses> <g1> <p1> <g2> <p2> ... <answer>"
 * The final guess always equals the answer, so each line is a complete replay. */
static int emit_tree(FILE *out, const uint16_t *S, int n, int d,
                     char *path, int plen, int ply, Ctx *ctx) {
    int g = best_move(S, n, d, ctx);
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
        if (emit_tree(out, buf + start[p], cnt[p], d - 1, path, plen + add, ply + 1, ctx) < 0)
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
        int v = solve(root + start[p], cnt[p], depth - 1, ctx);
        if (v >= INF) return INF;
        total += v;
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
        rc = emit_tree(out, buf + start[p], cnt[p], depth - 1, path, plen, 1, ctx);
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
    const char *ttload = NULL, *ttsave = NULL;
    int depth = 6, ttbits = 28, threads = 0, sweep = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--trees") && i + 1 < argc) treedir = argv[++i];
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-load") && i + 1 < argc) ttload = argv[++i];
        else if (!strcmp(argv[i], "--tt-save") && i + 1 < argc) ttsave = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }

    char path[1024];
    GWORD = malloc(sizeof(char[8]) * MAXG);
    AWORD = malloc(sizeof(char[8]) * MAXA);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path, AWORD);
    snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    if (r != NG || c != NA) {
        fprintf(stderr, "pattern matrix %dx%d != words %dx%d\n", r, c, NG, NA);
        return 1;
    }
    fprintf(stderr, "loaded %d guesses x %d answers\n", NG, NA);

    for (int a = 0; a < NA; a++) {
        ANS2G[a] = find_word(GWORD, NG, AWORD[a]);
        if (ANS2G[a] < 0) { fprintf(stderr, "answer %s not a legal guess\n", AWORD[a]); return 1; }
    }
    uint64_t seed = 0xD1B54A32D192ED03ULL;
    for (int a = 0; a < NA; a++) { ZOB0[a] = splitmix64(&seed); ZOB1[a] = splitmix64(&seed); }

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
            int total = solve_opener(g, depth, ctx);
            if (total < INF && treedir) write_tree(treedir, g, depth, ctx);
            double dt = now_s() - t0;
            if (total >= INF)
                printf("%s  INFEASIBLE within %d guesses  (%.1fs)\n", openers[k], depth, dt);
            else
                printf("%s  total=%d  expected=%.5f  (%.1fs, %lld nodes, TT %.3f%% hit)\n",
                       openers[k], total, (double)total / NA, dt, ctx->nodes,
                       100.0 * ctx->hit / (ctx->probe ? ctx->probe : 1));
            fflush(stdout);
        }
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
    if (ndone == 0) fprintf(out, "word,total,expected,seconds\n");

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
            int total = solve_opener(g, depth, ctx);
            int tree_ok = 1;
            if (total < INF && treedir) tree_ok = (write_tree(treedir, g, depth, ctx) == 0);
            double dt = now_s() - s0;
#pragma omp critical
            {
                /* fold this thread's counters into the globals, then reset */
                g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                ctx->probe = ctx->hit = ctx->fill = 0;

                if (total >= INF) fprintf(out, "%s,,,%.1f\n", GWORD[g], dt);
                else              fprintf(out, "%s,%d,%.5f,%.1f\n", GWORD[g], total,
                                          (double)total / NA, dt);
                fflush(out);
                completed++;
                double el = now_s() - t0;
                int left = NG - ndone - completed;
                double hit = 100.0 * g_hit / (g_probe ? g_probe : 1);
                double occ = 100.0 * g_fill / (double)TT_SLOTS;
                if (total >= INF)
                    printf("[%7.0fs] %5d/%d  %s  INFEASIBLE          %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], dt,
                           el / completed * left / 3600.0, hit, occ);
                else
                    printf("[%7.0fs] %5d/%d  %s  total=%5d  exp=%.5f%s %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], total, (double)total / NA,
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
