/* strguess.c -- the S -> A and S -> W cells: EVERY 26**5 string is a legal guess,
 * the answers are a word list.
 *
 *     sh build.sh                     (from solver/)
 *     bash solver/run-strguess-sweep.sh --depth 6            # S -> A, 2315 answers
 *     bash solver/run-strguess-sweep.sh --depth 7 --answers guess.txt   # S -> W
 *
 * WHAT IT MINIMISES: the TOTAL guesses summed over the answer list, where the
 * codebreaker may play ANY length-5 string, SUBJECT TO resolving every answer
 * within --depth.
 *
 * NO PHANTOM RULE HERE.  The guess set is all 26**5 strings, so it CONTAINS the
 * answer set outright -- every answer is playable and wins by being guessed.
 * That is what makes this simpler than strturns rather than harder: no unsolved
 * accounting, and n == 2 is a plain 3 again.
 *
 * WHY NOT optturns.  Its guess side is a dense NG x NA pattern matrix with
 * uint16 indices and guess ordinals packed into 20 bits.  At 11881376 guesses the
 * matrix alone would be 27.5 GB and 2**20 cannot hold the index.  So patterns are
 * computed INLINE and guesses are plain uint32 ordinals into the base-26
 * enumeration.  MEASURED: scanning all 11881376 guesses against 2315 candidates
 * costs 12.7 s on 18 threads, and the cost is linear in the candidate count -- so
 * a greedy tree over 2315 answers is minutes, not days.
 *
 * WHY NOT THE SYMMETRY COLLAPSE either.  --by-class works in strturns because the
 * ANSWER set 26**5 is invariant under letter permutation.  A word answer list is
 * NOT, so two guesses related by a permutation partition it differently and
 * nothing collapses -- least of all at the root, where every letter is live and
 * the scan is most expensive.  Brute force is the right tool here.
 *
 * A FREE CORRECTNESS CHECK.  The guess set here is a superset of the 12972 words,
 * so the exact S -> A optimum can never exceed optturns' W -> A optimum of 7920.
 * A run that beats 7920 is behaving; one that cannot is wrong.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define L          5
#define ALPHA      26
#define NPAT       243
#define ALL_GREEN  242
#define MAXA       13000
#define MAXD       32
#define MAXK       4096                 /* largest --topk we will hold */
#define NSTR       11881376L            /* 26**5, the guess space */
#define INF        ((long long)1 << 60)

static char    (*AWORD)[8];
static uint8_t (*ACODE)[L];
static int      NA;
static int      BRANCH = NPAT - 1;
static int      TOPK = 1;
/* Below this many candidates a parallel region costs more than the scan. */
static int      PAR_MIN = 64;

static double now_s(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

/* ---------------------------------------------------- guesses as ordinals */

static inline void gcode(long g, uint8_t *out) {
    for (int i = L - 1; i >= 0; i--) { out[i] = (uint8_t)(g % ALPHA); g /= ALPHA; }
}
static inline long gindex(const uint8_t *w) {
    long v = 0;
    for (int i = 0; i < L; i++) v = v * ALPHA + w[i];
    return v;
}
static void gword(long g, char *out) {
    uint8_t c[L]; gcode(g, c);
    for (int i = 0; i < L; i++) out[i] = (char)('a' + c[i]);
    out[L] = 0;
}

static inline int pat_of(const uint8_t *g, const uint8_t *a) {
    int t[L] = {0}, u[L] = {0}, code = 0;
    for (int i = 0; i < L; i++) if (g[i] == a[i]) { t[i] = 2; u[i] = 1; }
    for (int i = 0; i < L; i++)
        if (!t[i])
            for (int j = 0; j < L; j++)
                if (!u[j] && g[i] == a[j]) { t[i] = 1; u[j] = 1; break; }
    for (int i = 0; i < L; i++) code = code * 3 + t[i];
    return code;
}

/* ------------------------------------------------------------- key + bound */

/* ONE ranking rule, as in strturns: --topk ranks by ascending sum of squared bin
 * sizes, the exact search by lower bound, ties ALWAYS on the lowest guess
 * ordinal (which is lexicographic order on the string).  The key is never packed
 * beside the ordinal -- 2**20 cannot hold 11881376, and packing is what produced
 * two silent bugs in strturns. */
typedef struct { long long key; long g; } GuessKey;

/* Bounded top-K selection.  Storing a key per guess would be 190 MB PER DEPTH
 * LEVEL at 11881376 guesses, so nothing is stored: candidates are offered one at
 * a time and only the best K are kept. */
typedef struct { GuessKey e[MAXK]; int n, k; } TopK;

static void topk_init(TopK *t, int k) { t->n = 0; t->k = k > MAXK ? MAXK : k; }

static void topk_offer(TopK *t, long long key, long g) {
    if (t->n == t->k) {
        GuessKey worst = t->e[t->n - 1];
        if (key > worst.key || (key == worst.key && g > worst.g)) return;
        t->n--;
    }
    int i = t->n++;
    while (i > 0 && (t->e[i - 1].key > key ||
                     (t->e[i - 1].key == key && t->e[i - 1].g > g))) {
        t->e[i] = t->e[i - 1]; i--;
    }
    t->e[i].key = key; t->e[i].g = g;
}

static void topk_merge(TopK *dst, const TopK *src) {
    for (int i = 0; i < src->n; i++) topk_offer(dst, src->e[i].key, src->e[i].g);
}

static long long lbound(int n, int d) {
    if (n == 0) return 0;
    long long rem = n, cap = 1, total = 0;
    for (int k = 1; k <= d; k++) {
        long long take = rem < cap ? rem : cap;
        total += take * k;
        rem -= take;
        if (!rem) return total;
        if (cap < NA) cap *= BRANCH;
    }
    return INF;
}

/* --------------------------------------------- transposition table (by state) */

typedef struct { uint64_t h0, h1x; long long val; int32_t d, pad; long bestg; } Entry;
static Entry   *TT;
static uint64_t TT_BUCKETS;
static int      TT_OFF = 0;
static uint64_t ZOB0[MAXA], ZOB1[MAXA];

static uint64_t splitmix64(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static void hash_state(const uint16_t *S, int n, int d, uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0, b = 0;
    for (int i = 0; i < n; i++) { a ^= ZOB0[S[i]]; b ^= ZOB1[S[i]]; }
    a ^= (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    b += (uint64_t)d;
    *h0 = a ? a : 1; *h1 = b;
}

static int tt_get(uint64_t h0, uint64_t h1, int d, long long *val, long *bestg) {
    if (TT_OFF) return 0;
    Entry *bk = TT + (h0 & (TT_BUCKETS - 1)) * 2;
    for (int i = 0; i < 2; i++)
        if (bk[i].h0 == h0 && bk[i].h1x == (h1 ^ (uint64_t)bk[i].val) && bk[i].d == d) {
            *val = bk[i].val; if (bestg) *bestg = bk[i].bestg; return 1;
        }
    return 0;
}

static void tt_put(uint64_t h0, uint64_t h1, int d, long long val, long bestg) {
    if (TT_OFF) return;
    Entry e; e.h0 = h0; e.val = val; e.h1x = h1 ^ (uint64_t)val;
    e.d = d; e.pad = 0; e.bestg = bestg;
    Entry *bk = TT + (h0 & (TT_BUCKETS - 1)) * 2;
    if (bk[0].h0 == 0) { bk[0] = e; return; }
    bk[1] = bk[0]; bk[0] = e;
}

/* --------------------------------------------------------------- progress */

static double    G_T0, G_LAST;
static long long G_NODES, G_SOLVED, G_ANS_TOTAL;
static int       G_DEPTH, G_BUCKETS_DONE, G_BUCKETS_TOTAL;
static long long G_CUR_SIZE;

static void progress(void) {
    double now = now_s();
    if (now - G_LAST < 5.0) return;
    G_LAST = now;
    double el = now - G_T0;
    char eta[32];
    if (G_SOLVED > 0)
        snprintf(eta, sizeof eta, "%.0fs", el * (G_ANS_TOTAL - G_SOLVED) / (double)G_SOLVED);
    else
        snprintf(eta, sizeof eta, "?");
    fprintf(stderr, "[%7.0fs] d=%d %5.1f%%  %lld/%lld answers settled"
            "  bucket %d/%d (%lld answers)  |  %lld nodes, %.1f/s, eta %s\n",
            el, G_DEPTH, G_ANS_TOTAL ? 100.0 * G_SOLVED / G_ANS_TOTAL : 0.0,
            G_SOLVED, G_ANS_TOTAL, G_BUCKETS_DONE, G_BUCKETS_TOTAL, G_CUR_SIZE,
            G_NODES, G_NODES / (el + 1e-9), eta);
    fflush(stderr);
}

static void settle(long long k) {
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_SOLVED += k;
    progress();
}

/* ------------------------------------------------------------------ search */

typedef struct {
    uint16_t buf[MAXD][MAXA];
    int      cnt[MAXD][NPAT];
    int      touched[MAXD][NPAT];
    long long nodes;
} Ctx;

static long long solve(const uint16_t *S, int n, int d, Ctx *ctx);

/* Partition S by guess g and return its profile: bin count, sum of squares, the
 * per-bin lower bound, and whether g is itself a candidate.  Patterns are
 * computed inline -- there is no matrix at this guess-set size. */
static inline long long profile(const uint16_t *S, int n, int d, long g,
                                int *cnt, int *touched, long long *ss_out) {
    uint8_t gc[L]; gcode(g, gc);
    int nt = 0;
    for (int i = 0; i < n; i++) {
        int p = pat_of(gc, ACODE[S[i]]);
        if (cnt[p]++ == 0) touched[nt++] = p;
    }
    long long lv = n, ss = 0;
    int dead = (nt == 1 && cnt[touched[0]] == n);
    for (int k = 0; k < nt; k++) {
        int p = touched[k], c = cnt[p];
        ss += (long long)c * c;
        if (p != ALL_GREEN && !dead) {
            long long v = lbound(c, d - 1);
            if (v >= INF) dead = 1; else lv += v;
        }
        cnt[p] = 0;
    }
    *ss_out = ss;
    return dead ? INF : lv;
}

static long long eval_guess(const uint16_t *S, int n, int d, long g,
                            long long best, Ctx *ctx) {
    uint8_t gc[L]; gcode(g, gc);
    int *cnt = ctx->cnt[d], *touched = ctx->touched[d];
    uint16_t *buf = ctx->buf[d];
    int nt = 0;
    for (int i = 0; i < n; i++) {
        int p = pat_of(gc, ACODE[S[i]]);
        if (cnt[p]++ == 0) touched[nt++] = p;
    }
    if (nt == 1 && cnt[touched[0]] == n) { cnt[touched[0]] = 0; return INF; }

    int start[NPAT], fill[NPAT];
    int acc = 0;
    for (int k = 0; k < nt; k++) { start[touched[k]] = acc; fill[touched[k]] = acc; acc += cnt[touched[k]]; }
    for (int i = 0; i < n; i++) {
        int p = pat_of(gc, ACODE[S[i]]);
        buf[fill[p]++] = S[i];
    }

    long long lbrest = 0;
    for (int k = 0; k < nt; k++) {
        int p = touched[k];
        if (p == ALL_GREEN) continue;
        long long v = lbound(cnt[p], d - 1);
        if (v >= INF) { for (int j = 0; j < nt; j++) cnt[touched[j]] = 0; return INF; }
        lbrest += v;
    }
    long long total = n;
    long long r = 0;
    for (int k = 0; k < nt; k++) {
        int p = touched[k];
        if (p == ALL_GREEN) continue;
        long long own = lbound(cnt[p], d - 1);
        lbrest -= own;
        if (total + lbrest + own >= best) { r = INF; break; }
        long long v = solve(buf + start[p], cnt[p], d - 1, ctx);
        if (v >= INF) { r = INF; break; }
        total += v;
        if (total + lbrest >= best) { r = INF; break; }
    }
    for (int k = 0; k < nt; k++) cnt[touched[k]] = 0;
    return r ? r : total;
}

static long long solve(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (n == 1) return d >= 1 ? 1 : INF;
    if (d <= 1) return INF;
    if (n == 2) return 3;                     /* a candidate is always playable here */
    if (d > n) d = n;

    long long lb0 = lbound(n, d);
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(S, n, d, &h0, &h1);
    long long cached;
    if (tt_get(h0, h1, d, &cached, NULL)) return cached;

    ctx->nodes++;
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_NODES++;

    /* Scan EVERY 26**5 guess, keeping only the best K.  This is the whole cost of
     * the program and it is linear in n, which is why it is affordable: 12.7 s at
     * n = 2315 on 18 threads, and almost nothing at the small n where most nodes
     * live. */
    TopK top;
    topk_init(&top, TOPK > 0 ? TOPK : MAXK);
#ifdef _OPENMP
#pragma omp parallel if (n >= PAR_MIN)
#endif
    {
        TopK loc; topk_init(&loc, top.k);
        int cnt[NPAT] = {0}, touched[NPAT];
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long g = 0; g < NSTR; g++) {
            long long ss;
            long long lv = profile(S, n, d, g, cnt, touched, &ss);
            if (lv >= INF) continue;
            topk_offer(&loc, TOPK > 0 ? ss : lv, g);
        }
#ifdef _OPENMP
#pragma omp critical
#endif
        topk_merge(&top, &loc);
    }
    if (!top.n) { tt_put(h0, h1, d, INF, -1); return INF; }

    long long best = INF;
    long bestg = -1;
    for (int i = 0; i < top.n; i++) {
        long long v = eval_guess(S, n, d, top.e[i].g, best, ctx);
        if (v < best) { best = v; bestg = top.e[i].g; }
        if (best <= lb0) break;               /* provably optimal */
    }
    tt_put(h0, h1, d, best, bestg);
    return best;
}

/* ------------------------------------------------------------ root driver */

static long long solve_opener(long g, int depth, Ctx *ctx) {
    uint8_t gc[L]; gcode(g, gc);
    static uint16_t root[MAXA];
    int cnt[NPAT] = {0}, touched[NPAT], nt = 0;
    for (int a = 0; a < NA; a++) {
        int p = pat_of(gc, ACODE[a]);
        if (cnt[p]++ == 0) touched[nt++] = p;
    }
    int start[NPAT], fill[NPAT], acc = 0;
    for (int k = 0; k < nt; k++) { start[touched[k]] = acc; fill[touched[k]] = acc; acc += cnt[touched[k]]; }
    for (int a = 0; a < NA; a++) { int p = pat_of(gc, ACODE[a]); root[fill[p]++] = (uint16_t)a; }

    G_DEPTH = depth;
    G_ANS_TOTAL = NA;
    G_SOLVED = 0; G_BUCKETS_DONE = 0; G_BUCKETS_TOTAL = nt - (cnt[ALL_GREEN] > 0);
    if (cnt[ALL_GREEN]) settle(1);            /* the opener names itself */

    long long total = NA;
    for (int k = 0; k < nt; k++) {
        int p = touched[k];
        if (p == ALL_GREEN) continue;
        G_CUR_SIZE = cnt[p];
        progress();
        long long v = solve(root + start[p], cnt[p], depth - 1, ctx);
        if (v >= INF) return INF;
        total += v;
        G_BUCKETS_DONE++;
        settle(cnt[p]);
    }
    return total;
}

/* An opener's root profile, used to RANK openers -- the root is a branching
 * point like any other, so --topk restricts which openers are examined. */
static int measure_branching(void) {
    int best = 1;
#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        int loc = 1, cnt[NPAT] = {0}, touched[NPAT];
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
        for (long g = 0; g < NSTR; g++) {
            uint8_t gc[L]; gcode(g, gc);
            int nt = 0;
            for (int a = 0; a < NA; a++) {
                int p = pat_of(gc, ACODE[a]);
                if (cnt[p]++ == 0) touched[nt++] = p;
            }
            int k = nt - (cnt[ALL_GREEN] > 0);
            for (int j = 0; j < nt; j++) cnt[touched[j]] = 0;
            if (k > loc) loc = k;
        }
#ifdef _OPENMP
#pragma omp critical
#endif
        if (loc > best) best = loc;
    }
    return best;
}

/* ------------------------------------------------------------------- main */

static int load_words(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char buf[64]; int n = 0;
    while (fgets(buf, sizeof buf, f)) {
        int len = 0;
        while (buf[len] >= 'a' && buf[len] <= 'z') len++;
        if (len != L) continue;
        if (n >= MAXA) { fprintf(stderr, "more than %d answers\n", MAXA); exit(1); }
        memcpy(AWORD[n], buf, L); AWORD[n][L] = 0;
        for (int i = 0; i < L; i++) ACODE[n][i] = (uint8_t)(buf[i] - 'a');
        n++;
    }
    fclose(f);
    return n;
}

int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL, *answers = NULL;
    const char *openers[64]; int nopen = 0;
    int depth = 6, depthmax = -1, ttbits = 26, threads = 0, no_out = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth-max") && i + 1 < argc) depthmax = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if ((!strcmp(argv[i], "--topk") || !strcmp(argv[i], "-k")) && i + 1 < argc)
            TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--answers") && i + 1 < argc) answers = argv[++i];
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out")) no_out = 1;
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (depth < 1 || depth >= MAXD) {
        fprintf(stderr, "--depth %d out of range (1..%d)\n", depth, MAXD - 1); return 1;
    }
    if (depthmax >= MAXD) {
        fprintf(stderr, "--depth-max %d out of range (1..%d)\n", depthmax, MAXD - 1); return 1;
    }
    if (depthmax < depth) depthmax = depth;
    if (TOPK > MAXK) { fprintf(stderr, "--topk above %d\n", MAXK); return 1; }
    if (!outpath && !no_out) {
        fprintf(stderr, "no --out: this run would save NOTHING.\n"
                        "  use  bash solver/run-strguess-sweep.sh ...\n"
                        "  or   --out FILE / --no-out\n");
        return 1;
    }

    char path[1024];
    AWORD = malloc(sizeof(char[8]) * MAXA);
    ACODE = malloc(sizeof(uint8_t[L]) * MAXA);
    if (answers) snprintf(path, sizeof path, "%s", answers);
    else snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path);
    fprintf(stderr, "loaded %ld guesses (all %d-letter strings) x %d answers from %s\n",
            NSTR, L, NA, path);

    uint64_t seed = 0xD1B54A32D192ED03ULL;
    for (int a = 0; a < NA; a++) { ZOB0[a] = splitmix64(&seed); ZOB1[a] = splitmix64(&seed); }

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#else
    (void)threads; fprintf(stderr, "threads: 1 (no OpenMP)\n");
#endif

    double tb = now_s();
    BRANCH = measure_branching();
    fprintf(stderr, "branching: %d non-winning bins (max over all %ld guesses, %.1fs)\n",
            BRANCH, NSTR, now_s() - tb);
    fprintf(stderr, "root LB(d=%d, n=%d) = %lld  (%.5f avg)\n",
            depth, NA, lbound(NA, depth), (double)lbound(NA, depth) / NA);

    if (ttbits <= 0) { TT_OFF = 1; fprintf(stderr, "TT: disabled\n"); }
    else {
        TT_BUCKETS = 1ULL << ttbits;
        TT = calloc(TT_BUCKETS * 2, sizeof(Entry));
        if (!TT) { fprintf(stderr, "cannot allocate TT\n"); return 1; }
        fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", ttbits,
                TT_BUCKETS * 2.0 * sizeof(Entry) / 1e9);
    }

    /* NO DEFAULT OPENER.  This program exists to find good openers; a literal
     * here would assert an answer instead of deriving one.  With none given the
     * openers are RANKED by the same rule every other level uses, and --topk says
     * how many are examined -- the root is a branching point like any other. */
    FILE *out = fopen(outpath ? outpath : "/dev/null", "a");
    if (!out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
    if (outpath) { fprintf(out, "word,total,expected,depth,seconds\n"); fflush(out); }

    G_T0 = G_LAST = now_s();
    Ctx *ctx = calloc(1, sizeof(Ctx));

    long cand[MAXK]; int ncand = 0;
    if (nopen) {
        for (int i = 0; i < nopen; i++) {
            const char *w = openers[i];
            if (strlen(w) != L) { fprintf(stderr, "%s is not %d letters\n", w, L); continue; }
            uint8_t c[L];
            for (int j = 0; j < L; j++) c[j] = (uint8_t)(w[j] - 'a');
            cand[ncand++] = gindex(c);
        }
    } else {
        /* Rank all 26**5 openers by root sum of squares and keep the best K. */
        double t0 = now_s();
        TopK top; topk_init(&top, TOPK > 0 ? TOPK : 1);
#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            TopK loc; topk_init(&loc, top.k);
            int cnt[NPAT] = {0}, touched[NPAT];
#ifdef _OPENMP
#pragma omp for schedule(static)
#endif
            for (long g = 0; g < NSTR; g++) {
                uint8_t gc[L]; gcode(g, gc);
                int nt = 0;
                for (int a = 0; a < NA; a++) {
                    int p = pat_of(gc, ACODE[a]);
                    if (cnt[p]++ == 0) touched[nt++] = p;
                }
                long long ss = 0;
                for (int k = 0; k < nt; k++) {
                    ss += (long long)cnt[touched[k]] * cnt[touched[k]];
                    cnt[touched[k]] = 0;
                }
                topk_offer(&loc, ss, g);
            }
#ifdef _OPENMP
#pragma omp critical
#endif
            topk_merge(&top, &loc);
        }
        for (int i = 0; i < top.n; i++) cand[ncand++] = top.e[i].g;
        char w[L + 1]; gword(cand[0], w);
        fprintf(stderr, "opener ranking: %d of %ld examined (best %s, sum of squares %lld) "
                "in %.1fs\n", ncand, NSTR, w, top.e[0].key, now_s() - t0);
    }

    for (int i = 0; i < ncand; i++) {
        char w[L + 1]; gword(cand[i], w);
        double s0 = now_s();
        long long total = INF; int used = depthmax;
        for (int dd = depth; dd <= depthmax; dd++) {
            double d0 = now_s();
            total = solve_opener(cand[i], dd, ctx);
            if (total < INF) { used = dd; break; }
            printf("%s  INFEASIBLE at depth %d  (%.1fs)%s\n", w, dd, now_s() - d0,
                   dd < depthmax ? " -- escalating" : " -- that was --depth-max");
            fflush(stdout);
        }
        double dt = now_s() - s0;
        if (total < INF) {
            printf("%s  total=%lld  expected=%.5f  d=%d  (%.1fs, %lld nodes)\n",
                   w, total, (double)total / NA, used, dt, ctx->nodes);
            /* The <= 7920 bound holds for the EXACT optimum only: the guess set
             * here contains the 12972 words, so opt(S->A) <= opt(W->A) = 7920.
             * Under --topk this is a greedy UPPER BOUND and may legitimately
             * exceed it -- sum of squares is a heuristic, and a larger guess
             * space can lead it to a better-splitting but globally worse move.
             * Firing the check regardless reported SOMETHING IS WRONG on a
             * perfectly good run. */
            if (NA == 2315 && TOPK == 0)
                printf("  %s 7920 (optturns W->A optimum; an EXACT S->A run cannot "
                       "exceed it)\n",
                       total <= 7920 ? "PASS: <=" : "FAIL: EXCEEDS");
            else if (NA == 2315)
                printf("  (upper bound from --topk %d; the <= 7920 check applies only "
                       "to an exact --topk 0 run)\n", TOPK);
            if (outpath) {
                fprintf(out, "%s,%lld,%.5f,%d,%.1f\n", w, total, (double)total / NA, used, dt);
                fflush(out);
            }
        }
        fflush(stdout);
    }
    fclose(out);
    free(ctx);
    return 0;
}
