/* wrongle.c -- WRONGLE: only compatible guesses, and try NOT to find the answer.
 *
 * math/wrongle.py states the rule, the state and both value functions, and is
 * the REFERENCE: tools/checkwrongle.py diffs this program against it.  Read it
 * first.  In one paragraph:
 *
 *   A guess is legal iff it is one of the guess-list words AND consistent with
 *   every clue so far (ultraturns' legality, over the 12972 -- not eldrowmax's
 *   2315).  The answer is uniform over the answer list.  THE STATE IS THE LEGAL
 *   SET L: the answers still possible are L restricted to the answer list, and
 *   one more clue just filters L.
 *
 *   --objective lose --depth D   maximise the answers NOT found within D guesses
 *   --objective expect           maximise the TOTAL guesses over the answers,
 *                                uncapped (the mean is that over the answer count)
 *
 * TWO DIFFERENT QUANTITIES; neither goes in a table beside the other, nor beside
 * any optturns-family total (those minimise).  THE OBJECTIVE HAS NO DEFAULT IN
 * THIS BINARY -- the greens scar: a defaulted objective is a domain answer hiding
 * in configuration.  The wrapper carries the default a human reads.
 *
 * ------------------------------------------------------------------ porting
 *
 * Built from eldrowmax.c (the candidate-set bitset, the counting-sort split, the
 * fingerprint fold, the self-verifying table) and greens.c (a COUNT over answers
 * under a cap, the opener sweep with a shared incumbent, resume, the stamp).
 * What did NOT transfer, said once so it is not rediscovered:
 *
 *   - eldrowmax's state is one bucket (the chain follows one branch); here the
 *     value SUMS over every branch holding an answer, as greens' does.
 *   - eldrowmax's pool is both candidates and guesses.  Here they differ: L is
 *     over the guess list, the answers a subset of it, so every state carries
 *     both counts and the matrix is the SQUARE guess x guess one
 *     (`build_patterns.py --full`).
 *   - greens' `if (d > n) d = n` trap does not arise; the exact shortcut here is
 *     the reverse one, `|L| <= d  ->  0 lost` (see wrongle.py).
 *   - greens' two-ply bound and must-win machinery have no counterpart.
 *
 * ---------------------------------------------------------------- bounds
 *
 * Per CHILD, both sound and both cheap from the bucket sizes alone:
 *   lose    lose(L_p, d) <= |A_p|, and is 0 when |L_p| <= d
 *   expect  total(L_p)   <= |A_p| * |L_p|   (no game outlasts the legal set)
 * A guess's bound is the sum over its children.  Exact search walks guesses in
 * descending bound and stops at the first whose bound cannot beat the best; a
 * guess is also abandoned part-way once what it has plus what it could still
 * add cannot beat the best.  --no-prune drops both, which is the oracle.
 *
 * ---------------------------------------------------------------- the beam
 *
 * --topk K examines only the K legal guesses with the LARGEST sum of squared
 * answer-bin sizes (every bin, all-green included), ties on the LOWEST guess
 * index -- at EVERY node, THE ROOT INCLUDED, so the opener is the best of the K
 * examined.  Every value is ACHIEVABLE: a LOWER bound on the true maximum.  K is
 * in the stamp and the filename; each K is a different strategy.
 *
 *     bash solver/run-wrongle.sh --objective lose          # from math/ -- USE THIS
 *
 * WORD LISTS ARE OURS (the original Wordle 2315/12972), not Wrongle's.
 */

#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _OPENMP
#include <omp.h>
#endif

#define WORDLEN    5
#define NPAT       243
#define ALL_GREEN  242
#define WBUF       8

#ifndef MAXG
#define MAXG       13000
#endif
#define BSW  ((MAXG + 63) / 64)

/* MAXD bounds the RECURSION and is an array bound, not a modelling cap.  Under
 * `lose` the depth is --depth.  Under `expect` it is the longest consistent chain
 * the search walks, which is finite (every move removes the word played) and far
 * below this; overrunning it is a hard error, never a truncation. */
#ifndef MAXD
#define MAXD       128
#endif

#ifndef CANDPOOL
#define CANDPOOL   (1 << 21)
#endif

enum { OBJ_NONE, OBJ_LOSE, OBJ_EXPECT };

typedef uint8_t pat_t;

static int      NG, NA;
static char   (*GWORD)[WBUF];
static pat_t   *PAT;                 /* NG * NG: PAT[g * NG + w] */
static uint8_t *ISA;                 /* ISA[w] = 1 iff w is an answer */

static int       OBJ = OBJ_NONE;
static int       DEPTH = 0;
static int       TOPK = 0;
static int       PRUNE = 1;
static double    REPORT = 30.0;

/* --------------------------------------------------------------- loading
 * load_words and load_npy are eldrowmax.c's (optturns.c's), unchanged. */

static int load_words(const char *path, char (*out)[WBUF], int cap) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (len == 0) continue;
        if (len > WORDLEN) len = WORDLEN;
        if (n >= cap) { fprintf(stderr, "%s has more than %d words\n", path, cap); exit(1); }
        memcpy(out[n], line, len);
        out[n][len] = 0;
        n++;
    }
    fclose(f);
    return n;
}

static pat_t *load_npy(const char *path, int *rows, int *cols) {
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
    if (!strstr(hdr, "|u1")) {
        fprintf(stderr, "pattern matrix dtype is not |u1: %s\n", hdr); exit(1);
    }
    if (strstr(hdr, "'fortran_order': True")) {
        fprintf(stderr, "%s is Fortran-ordered; expected C order\n", path); exit(1);
    }
    char *p = strchr(hdr, '(');
    if (!p || sscanf(p, "(%d, %d)", rows, cols) != 2) {
        fprintf(stderr, "cannot parse shape from: %s\n", hdr); exit(1);
    }
    free(hdr);
    size_t nbytes = (size_t)(*rows) * (size_t)(*cols) * sizeof(pat_t);
    pat_t *data = malloc(nbytes);
    if (!data) { fprintf(stderr, "out of memory for pattern matrix\n"); exit(1); }
    if (fread(data, 1, nbytes, f) != nbytes) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return data;
}

/* ------------------------------------------------- transposition table
 * eldrowmax's: 128 bits of key, the second half XORed with the payload so a torn
 * entry fails verification.  NOTHING IS SAVED OR LOADED (see § --tt-save in the
 * video CLAUDE.md: a snapshot written at normal completion is worthless). */

typedef struct { uint64_t h0, h1x; int32_t val, bestg; } Entry;

static Entry   *TT;
static uint64_t TT_BUCKETS;
static int      TT_OFF = 0;

static void tt_init(int bits) {
    if (bits <= 0) {
        TT_OFF = 1;
        fprintf(stderr, "TT: DISABLED (--tt-bits 0) -- no memoisation\n");
        return;
    }
    if (bits < 2) bits = 2;
    TT_BUCKETS = (uint64_t)1 << (bits - 1);
    size_t bytes = (size_t)TT_BUCKETS * 2 * sizeof(Entry);
    TT = aligned_alloc(64, bytes);
    if (!TT) { fprintf(stderr, "cannot allocate %.2f GB TT\n", bytes / 1e9); exit(1); }
    memset(TT, 0, bytes);
    fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", bits, bytes / 1e9);
}

static inline uint64_t tt_payload(int val, int bestg) {
    return ((uint64_t)(uint32_t)val << 32) ^ (uint64_t)(uint32_t)bestg;
}

static inline int tt_get(uint64_t h0, uint64_t h1, int *val) {
    if (TT_OFF) return 0;
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++) {
        Entry e = b[j];
        if (e.h0 == h0 && (e.h1x ^ tt_payload(e.val, e.bestg)) == h1) {
            *val = e.val;
            return 1;
        }
    }
    return 0;
}

static inline void tt_put(uint64_t h0, uint64_t h1, int val, int bestg) {
    if (TT_OFF) return;
    Entry e;
    e.h0 = h0; e.val = val; e.bestg = bestg;
    e.h1x = h1 ^ tt_payload(val, bestg);
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    b[1] = b[0];
    b[0] = e;
}

/* ------------------------------------------------------------------ context */

static double wall_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

static double T_START;

/* A guess at a node: its bound (what exact search orders and prunes on) and its
 * beam score (sum of squared answer-bin sizes). */
typedef struct { int32_t bound, ssq, g; } Cand;

typedef struct {
    uint64_t arena[MAXD][BSW];     /* the legal set at each recursion level */
    uint16_t widx[MAXD][BSW];
    int      nwid[MAXD];
    uint16_t memb[MAXD][MAXG];     /* its members, ascending */
    uint16_t sortb[MAXD][MAXG];    /* members counting-sorted by feedback */
    int      start[MAXD][NPAT + 1];
    int      cntA[MAXD][NPAT];     /* answers in each run of sortb */
    int      cL[NPAT], cA[NPAT];   /* scoring scratch, one guess at a time */
    Cand    *cpool;
    int      ctop;
    long long nodes;
    int       overflow;
    double    next_beat;
} Ctx;

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    if (!c) { fprintf(stderr, "out of memory for a search context\n"); exit(1); }
    c->cpool = malloc((size_t)CANDPOOL * sizeof(Cand));
    if (!c->cpool) { fprintf(stderr, "out of memory for a search context\n"); exit(1); }
    return c;
}

static void ctx_free(Ctx *c) { free(c->cpool); free(c); }

static inline uint64_t mix64(uint64_t z) {
    z ^= z >> 33; z *= 0xFF51AFD7ED558CCDULL;
    z ^= z >> 33; z *= 0xC4CEB9FE1A85EC53ULL;
    z ^= z >> 33;
    return z;
}

/* eldrowmax.c's build_child, verbatim (its corrected, independent-halves fold):
 * build a set from an ASCENDING member list, fingerprinting it in the same pass. */
static inline void build_child(const uint16_t *mem, int n, uint64_t *out,
                               uint16_t *cw, int *cnw, uint64_t *h0, uint64_t *h1) {
    int m = 0, curw = -1;
    for (int k = 0; k < n; k++) {
        int w = mem[k] >> 6;
        if (w != curw) { out[w] = 0; cw[m++] = (uint16_t)w; curw = w; }
        out[w] |= 1ULL << (mem[k] & 63);
    }
    uint64_t a = 0x243F6A8885A308D3ULL, b = 0x13198A2E03707344ULL;
    for (int k = 0; k < m; k++) {
        int w = cw[k];
        uint64_t mm = mix64(out[w] ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(w + 1)));
        a ^= mm;
        a = a * 0x100000001B3ULL + 0x9E3779B97F4A7C15ULL;
        b += mm;
        b ^= b >> 29;
        b *= 0xBF58476D1CE4E5B9ULL;
    }
    *cnw = m;
    *h0 = mix64(a);
    *h1 = mix64(b ^ 0xC2B2AE3D27D4EB4FULL);
}

/* Counting-sort `mem` by the feedback g gives each member, into sortb[depth],
 * recording run boundaries and the answers in each run.  Stable over an
 * ascending `mem`, so every run ascends -- which build_child requires. */
static void split_by(Ctx *c, int depth, const uint16_t *mem, int n, int g) {
    int *st = c->start[depth], *ca = c->cntA[depth];
    int cnt[NPAT];
    memset(cnt, 0, sizeof cnt);
    memset(ca, 0, NPAT * sizeof(int));
    const pat_t *row = PAT + (size_t)g * NG;
    for (int k = 0; k < n; k++) { int p = row[mem[k]]; cnt[p]++; ca[p] += ISA[mem[k]]; }
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { st[p] = acc; acc += cnt[p]; cnt[p] = st[p]; }
    st[NPAT] = acc;
    uint16_t *out = c->sortb[depth];
    for (int k = 0; k < n; k++) out[cnt[row[mem[k]]]++] = mem[k];
}

/* The bound of one CHILD from its two sizes -- the one place it is stated. */
static inline long long child_ub(int nL, int nA, int drem_child) {
    if (nA == 0) return 0;
    if (OBJ == OBJ_LOSE) return (drem_child > 0 && nL <= drem_child) ? 0 : nA;
    return (long long)nA * nL;
}

/* Score every member of `mem` as a guess: its bound and its beam score. */
static void score_all(Ctx *c, const uint16_t *mem, int n, int drem, Cand *out) {
    for (int i = 0; i < n; i++) {
        int g = mem[i];
        const pat_t *row = PAT + (size_t)g * NG;
        memset(c->cL, 0, sizeof c->cL);
        memset(c->cA, 0, sizeof c->cA);
        for (int k = 0; k < n; k++) { int p = row[mem[k]]; c->cL[p]++; c->cA[p] += ISA[mem[k]]; }
        long long b = 0, s = 0;
        for (int p = 0; p < NPAT; p++) {
            s += (long long)c->cA[p] * c->cA[p];
            if (p != ALL_GREEN) b += child_ub(c->cL[p], c->cA[p], drem - 1);
        }
        out[i].bound = (int32_t)b;
        out[i].ssq = (int32_t)s;
        out[i].g = g;
    }
}

static int cmp_bound(const void *x, const void *y) {
    const Cand *p = x, *q = y;
    if (p->bound != q->bound) return p->bound > q->bound ? -1 : 1;
    return p->g - q->g;
}

/* THE beam ranking: most answers remaining first, ties on the lowest index. */
static int cmp_ssq(const void *x, const void *y) {
    const Cand *p = x, *q = y;
    if (p->ssq != q->ssq) return p->ssq > q->ssq ? -1 : 1;
    return p->g - q->g;
}

/* Restrict `cand` to what this run examines and put it in evaluation order.
 * Returns how many to walk.  The beam SELECTS by ssq; within the K selected,
 * the walk is by bound so pruning bites -- the order changes no value. */
static int order_moves(Cand *cand, int n) {
    if (TOPK > 0 && TOPK < n) {
        qsort(cand, n, sizeof(Cand), cmp_ssq);
        n = TOPK;
    }
    qsort(cand, n, sizeof(Cand), cmp_bound);
    return n;
}

static void heartbeat(Ctx *c) {
    double now = wall_time();
    if (now < c->next_beat) return;
    c->next_beat = now + REPORT;
    fprintf(stderr, "        ... %lld nodes on this thread, %.0fs elapsed\n",
            c->nodes, now - T_START);
}

static long long solve(Ctx *c, int depth, int nL, int nA, int drem, uint64_t h0, uint64_t h1);

/* The value AFTER playing g from `mem` (drem guesses left, g included): the sum
 * over the children holding an answer.  `beat` >= 0 lets the walk abandon g once
 * it provably cannot exceed it, returning -1; `ub` is g's bound. */
static long long eval_move(Ctx *c, int depth, const uint16_t *mem, int n, int g,
                           int drem, long long beat, long long ub) {
    split_by(c, depth, mem, n, g);
    int *st = c->start[depth], *ca = c->cntA[depth];
    long long sum = 0, rem = ub;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN) continue;
        int lo = st[p], hi = st[p + 1], nAp = ca[p];
        if (nAp == 0) continue;
        int nLp = hi - lo;
        long long cub = child_ub(nLp, nAp, drem - 1), v;
        if (OBJ == OBJ_LOSE && drem - 1 == 0)      v = nAp;
        else if (OBJ == OBJ_LOSE && nLp <= drem - 1) v = 0;
        else {
            if (depth + 1 >= MAXD) { c->overflow = 1; return 0; }
            uint64_t ch0, ch1;
            build_child(c->sortb[depth] + lo, nLp, c->arena[depth + 1],
                        c->widx[depth + 1], &c->nwid[depth + 1], &ch0, &ch1);
            v = solve(c, depth + 1, nLp, nAp, drem - 1, ch0, ch1);
            /* the recursion reused nothing at THIS depth, but re-split anyway if
             * it ever does: sortb/start/cntA[depth] are owned by this frame */
        }
        sum += v;
        rem -= cub;
        if (PRUNE && beat >= 0 && sum + rem <= beat) return -1;
    }
    return sum;
}

/* The exact (or beamed) value of the legal set at arena[depth]: answers lost
 * (lose) or total guesses (expect, this node's guess included). */
static long long solve(Ctx *c, int depth, int nL, int nA, int drem, uint64_t h0, uint64_t h1) {
    if (nA == 0) return 0;
    long long base = (OBJ == OBJ_EXPECT) ? nA : 0;
    if (OBJ == OBJ_LOSE) {
        if (drem == 0) return nA;
        if (nL <= drem) return 0;
    } else if (nL == 1) {
        return nA;                              /* the answer, played */
    }
    uint64_t k0 = h0, k1 = h1;
    if (OBJ == OBJ_LOSE) {
        k0 ^= (uint64_t)drem * 0x9E3779B97F4A7C15ULL;
        k1 ^= (uint64_t)drem * 0xC2B2AE3D27D4EB4FULL;
    }
    int tv;
    if (tt_get(k0, k1, &tv)) return tv;
    if ((++c->nodes & 0x3FFF) == 0) heartbeat(c);

    /* the members, ascending */
    uint16_t *mem = c->memb[depth];
    int n = 0;
    for (int kk = 0; kk < c->nwid[depth]; kk++) {
        int w = c->widx[depth][kk];
        uint64_t bits = c->arena[depth][w];
        while (bits) { mem[n++] = (uint16_t)((w << 6) + __builtin_ctzll(bits)); bits &= bits - 1; }
    }
    if (n != nL) { fprintf(stderr, "internal: set size %d != %d\n", n, nL); exit(1); }

    if (c->ctop + n > CANDPOOL) {
        fprintf(stderr, "the candidate arena (%d) is exhausted -- rebuild with a larger -DCANDPOOL\n",
                CANDPOOL);
        exit(1);
    }
    Cand *cand = c->cpool + c->ctop;
    score_all(c, mem, n, drem, cand);
    int m = order_moves(cand, n);
    c->ctop += n;

    long long best = -1;
    int bestg = -1;
    for (int i = 0; i < m; i++) {
        if (PRUNE && best >= 0 && cand[i].bound <= best) break;
        long long v = eval_move(c, depth, mem, n, cand[i].g, drem,
                                best, cand[i].bound);
        if (c->overflow) break;
        if (v > best) { best = v; bestg = cand[i].g; }
    }
    c->ctop -= n;
    long long val = base + (best < 0 ? 0 : best);
    tt_put(k0, k1, (int)val, bestg);
    return val;
}

/* ------------------------------------------------------------------- trace
 *
 * --trace FILE (lose, named openers only): after an opener is solved, follow THE
 * STRATEGY THE SEARCH CHOSE down one line on which answers are lost, and write
 * it out.  At every node the guess is the one solve() would keep -- the first in
 * the walk order (same beam, same bound order) whose value is the maximum, the
 * same strict `v > best` tie-break -- and the branch is the first feedback bucket
 * (ascending code) whose value is positive.  At the cap the answers left in that
 * bucket are the ones lost on this line.
 *
 * It RE-DERIVES values rather than trusting the table (a TT entry can be evicted
 * and carries no move), and it CHECKS ITSELF: each node's best must equal the
 * value its parent computed for it, or the trace aborts -- a line that disagreed
 * with the search would be a fabrication.  tools/checkwrongle.py replays every
 * traced line from the strings. */

static int trace_node(Ctx *c, int depth, int nL, int nA, int drem, long long want,
                      int *gl, int *pl, FILE *tf);

/* Play g from `mem` (drem guesses left, g included) and descend into the first
 * child that still loses an answer.  Returns the line length, or -1. */
static int trace_move(Ctx *c, int depth, const uint16_t *mem, int n, int g, int drem,
                      int *gl, int *pl, FILE *tf) {
    split_by(c, depth, mem, n, g);
    int *st = c->start[depth], *ca = c->cntA[depth];
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN) continue;
        int lo = st[p], hi = st[p + 1], nAp = ca[p];
        if (nAp == 0) continue;
        int nLp = hi - lo;
        long long v;
        if (drem - 1 == 0)            v = nAp;
        else if (nLp <= drem - 1)     v = 0;
        else {
            uint64_t ch0, ch1;
            build_child(c->sortb[depth] + lo, nLp, c->arena[depth + 1],
                        c->widx[depth + 1], &c->nwid[depth + 1], &ch0, &ch1);
            v = solve(c, depth + 1, nLp, nAp, drem - 1, ch0, ch1);
        }
        if (v <= 0) continue;
        gl[depth] = g; pl[depth] = p;
        if (drem - 1 == 0) {
            /* the cap: these answers were never played */
            fprintf(tf, ",");
            int first = 1;
            for (int k = lo; k < hi; k++) {
                int w = c->sortb[depth][k];
                if (!ISA[w]) continue;
                fprintf(tf, "%s%s", first ? "" : " ", GWORD[w]);
                first = 0;
            }
            return depth + 1;
        }
        /* solve() above may have reused arena[depth+1] below it; rebuild */
        uint64_t ch0, ch1;
        build_child(c->sortb[depth] + lo, nLp, c->arena[depth + 1],
                    c->widx[depth + 1], &c->nwid[depth + 1], &ch0, &ch1);
        return trace_node(c, depth + 1, nLp, nAp, drem - 1, v, gl, pl, tf);
    }
    return -1;
}

/* At the legal set in arena[depth], pick the guess solve() keeps and follow it. */
static int trace_node(Ctx *c, int depth, int nL, int nA, int drem, long long want,
                      int *gl, int *pl, FILE *tf) {
    uint16_t *mem = c->memb[depth];
    int n = 0;
    for (int kk = 0; kk < c->nwid[depth]; kk++) {
        int w = c->widx[depth][kk];
        uint64_t bits = c->arena[depth][w];
        while (bits) { mem[n++] = (uint16_t)((w << 6) + __builtin_ctzll(bits)); bits &= bits - 1; }
    }
    if (n != nL) { fprintf(stderr, "trace: set size %d != %d\n", n, nL); exit(1); }
    Cand *cand = c->cpool + c->ctop;
    score_all(c, mem, n, drem, cand);
    int m = order_moves(cand, n);
    c->ctop += n;
    long long best = -1;
    int bestg = -1;
    for (int i = 0; i < m; i++) {
        if (best >= 0 && cand[i].bound <= best) break;   /* cannot beat it strictly */
        long long v = eval_move(c, depth, mem, n, cand[i].g, drem, -1, cand[i].bound);
        if (v > best) { best = v; bestg = cand[i].g; }
    }
    c->ctop -= n;
    if (best != want) {
        fprintf(stderr, "trace: node at depth %d re-derives %lld, its parent said %lld\n",
                depth, best, want);
        exit(1);
    }
    (void)nA;
    return trace_move(c, depth, mem, n, bestg, drem, gl, pl, tf);
}

/* One CSV row per traced opener: opener,value,line,lost.  `line` is the guesses
 * with their feedback, `word:TILES` space-separated (G green, Y yellow, - grey,
 * position 0 first); `lost` the answers left unplayed at the cap on that line. */
static void trace_opener(Ctx *c, const uint16_t *rootmem, int g, long long value, FILE *tf) {
    int gl[MAXD], pl[MAXD];
    fprintf(tf, "%s,%lld", GWORD[g], value);
    /* the line goes before `lost`, so build it into a buffer first */
    FILE *tmp = tmpfile();
    if (!tmp) { fprintf(stderr, "trace: no temp file\n"); exit(1); }
    int len = trace_move(c, 0, rootmem, NG, g, DEPTH, gl, pl, tmp);
    if (len != DEPTH) {
        fprintf(stderr, "trace: %s gave a line of %d guesses, expected %d\n", GWORD[g], len, DEPTH);
        exit(1);
    }
    fprintf(tf, ",");
    for (int i = 0; i < len; i++) {
        char s[WORDLEN + 1];
        int p = pl[i];
        for (int j = WORDLEN - 1; j >= 0; j--) { int t = p % 3; p /= 3; s[j] = t == 2 ? 'G' : t == 1 ? 'Y' : '-'; }
        s[WORDLEN] = 0;
        fprintf(tf, "%s%s:%s", i ? " " : "", GWORD[gl[i]], s);
    }
    rewind(tmp);
    int ch;
    while ((ch = fgetc(tmp)) != EOF) fputc(ch, tf);   /* ",lost answers" */
    fclose(tmp);
    fprintf(tf, "\n");
    fflush(tf);
}

/* ------------------------------------------------------------------ output */

typedef struct { int status; long long value, bound; double secs; } Res;  /* 0 none, 1 solved, 2 cut */

static const char *objname(void) { return OBJ == OBJ_LOSE ? "lose" : "expect"; }

static void stamp(char *buf, size_t sz, const char *root) {
    snprintf(buf, sz, "# wrongle objective=%s depth=%d topk=%d root=%s guesses=%d answers=%d",
             objname(), OBJ == OBJ_LOSE ? DEPTH : 0, TOPK, root, NG, NA);
}

static int find_word(const char *w) {
    for (int i = 0; i < NG; i++) if (!strcmp(GWORD[i], w)) return i;
    return -1;
}

/* Read a previous run's rows.  A file whose stamp differs, or that has none, is
 * REFUSED: rows from another question would be skipped as work done. */
static int load_resume(const char *path, const char *want, Res *res) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[512];
    if (!fgets(line, sizeof line, f)) { fclose(f); return 0; }   /* empty = fresh */
    line[strcspn(line, "\r\n")] = 0;
    if (strcmp(line, want)) {
        fprintf(stderr, "%s was written for a different question:\n  file: %s\n  this: %s\n"
                        "  refusing to resume into it.\n", path, line, want);
        exit(2);
    }
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        char w[16], st[16];
        long long v, b;
        double s;
        if (sscanf(line, "%15[^,],%15[^,],%lld,%lld,%*[^,],%lf", w, st, &v, &b, &s) != 5) continue;
        int g = find_word(w);
        if (g < 0) continue;
        res[g].status = !strcmp(st, "solved") ? 1 : 2;
        res[g].value = v; res[g].bound = b; res[g].secs = s;
        n++;
    }
    fclose(f);
    return n;
}

static void usage(void) {
    fprintf(stderr,
        "usage: wrongle --objective lose|expect [--depth D] --out FILE [options]\n"
        "       (prefer solver/run-wrongle.sh)\n"
        "  --objective O    lose: max answers NOT found within --depth guesses\n"
        "                   expect: max total guesses, uncapped.  REQUIRED.\n"
        "  --depth D        the cap; required by lose, refused by expect\n"
        "  --topk K         beam: K best guesses per node, ROOT INCLUDED (0 = exact)\n"
        "  --opener W       price only these openers (repeatable)\n"
        "  --out FILE       CSV, resumable; --no-out saves NOTHING and must be explicit\n"
        "  --trace FILE     lose + --opener only: write one losing line per opener\n"
        "  --tt-bits B      table size 2^B (default 26)\n"
        "  --threads N      threads over openers (default: all cores)\n"
        "  --report S       heartbeat seconds (default 30)\n"
        "  --no-prune       drop every bound -- the oracle\n"
        "  --data DIR       data root (default data, i.e. run from math/)\n"
        "  --guess-list/--answer-list/--patterns FILE   restricted runs (the gate);\n"
        "                   --patterns must be square over the guess list\n");
    exit(2);
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);

    const char *outpath = NULL, *datadir = "data", *tracepath = NULL;
    const char *guesslist = NULL, *answerlist = NULL, *patpath = NULL;
    const char *openers[256];
    int nopen = 0, no_out = 0, ttbits = 26, depth_given = 0;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "--objective") && i + 1 < argc) {
            i++;
            if      (!strcmp(argv[i], "lose"))   OBJ = OBJ_LOSE;
            else if (!strcmp(argv[i], "expect")) OBJ = OBJ_EXPECT;
            else { fprintf(stderr, "--objective is lose or expect, not %s\n", argv[i]); return 2; }
        }
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc)     { DEPTH = atoi(argv[++i]); depth_given = 1; }
        else if (!strcmp(argv[i], "--topk") && i + 1 < argc)      TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--opener") && i + 1 < argc)    {
            if (nopen >= 256) { fprintf(stderr, "too many --opener\n"); return 2; }
            openers[nopen++] = argv[++i];
        }
        else if (!strcmp(argv[i], "--out") && i + 1 < argc)       outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out"))                    no_out = 1;
        else if (!strcmp(argv[i], "--trace") && i + 1 < argc)     tracepath = argv[++i];
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc)   ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--report") && i + 1 < argc)    REPORT = atof(argv[++i]);
        else if (!strcmp(argv[i], "--no-prune"))                  PRUNE = 0;
        else if (!strcmp(argv[i], "--data") && i + 1 < argc)      datadir = argv[++i];
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc)  guesslist = argv[++i];
        else if (!strcmp(argv[i], "--answer-list") && i + 1 < argc) answerlist = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc)    patpath = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) {
#ifdef _OPENMP
            omp_set_num_threads(atoi(argv[++i]));
#else
            i++;
#endif
        }
        else usage();
    }
    if (OBJ == OBJ_NONE) {
        fprintf(stderr, "wrongle: --objective lose|expect is REQUIRED -- the two are different\n"
                        "  quantities and this binary will not pick one for you.\n");
        return 2;
    }
    if (OBJ == OBJ_LOSE && (!depth_given || DEPTH < 1)) {
        fprintf(stderr, "wrongle: --objective lose needs --depth D >= 1 -- the cap IS the objective\n");
        return 2;
    }
    if (OBJ == OBJ_LOSE && DEPTH + 1 >= MAXD) {
        fprintf(stderr, "wrongle: --depth %d exceeds MAXD %d\n", DEPTH, MAXD); return 2;
    }
    if (OBJ == OBJ_EXPECT && depth_given) {
        fprintf(stderr, "wrongle: --objective expect is UNCAPPED; --depth would change the question\n");
        return 2;
    }
    if (TOPK < 0) { fprintf(stderr, "--topk must be >= 0\n"); return 2; }
    if (tracepath && OBJ != OBJ_LOSE) {
        fprintf(stderr, "wrongle: --trace follows a line on which answers are LOST; it needs --objective lose\n");
        return 2;
    }
    if (!outpath && !no_out) {
        fprintf(stderr, "wrongle: give --out FILE, or --no-out to save NOTHING.\n"
                        "  Prefer the wrapper: bash solver/run-wrongle.sh\n");
        return 2;
    }

    /* ------------------------------------------------------------ the lists */
    char path[512];
    GWORD = malloc(sizeof(*GWORD) * MAXG);
    char (*aword)[WBUF] = malloc(sizeof(*aword) * MAXG);
    if (guesslist) NG = load_words(guesslist, GWORD, MAXG);
    else { snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir); NG = load_words(path, GWORD, MAXG); }
    if (answerlist) NA = load_words(answerlist, aword, MAXG);
    else { snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir); NA = load_words(path, aword, MAXG); }

    int r, cc;
    if (patpath) {
        PAT = load_npy(patpath, &r, &cc);
        if (r != NG || cc != NG) {
            fprintf(stderr, "--patterns is %dx%d but must be square over the %d-word guess list\n", r, cc, NG);
            return 1;
        }
    } else {
        /* The SQUARE matrix over the full guess list; a restricted guess list is
         * compacted out of it by word. */
        snprintf(path, sizeof path, "%s/local/patterns/patterns_full.npy", datadir);
        pat_t *full = load_npy(path, &r, &cc);
        char (*fw)[WBUF] = malloc(sizeof(*fw) * 16384);
        snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
        int nf = load_words(path, fw, 16384);
        if (r != nf || cc != nf) {
            fprintf(stderr, "patterns_full.npy is %dx%d, the guess list %d -- rebuild with\n"
                            "  python3 build_patterns.py --full\n", r, cc, nf);
            return 1;
        }
        if (!guesslist) PAT = full;
        else {
            int *map = malloc(sizeof(int) * NG);
            for (int i = 0; i < NG; i++) {
                map[i] = -1;
                for (int j = 0; j < nf; j++) if (!strcmp(fw[j], GWORD[i])) { map[i] = j; break; }
                if (map[i] < 0) { fprintf(stderr, "--guess-list word %s is not a legal guess\n", GWORD[i]); return 1; }
            }
            PAT = malloc((size_t)NG * NG);
            for (int g = 0; g < NG; g++)
                for (int w = 0; w < NG; w++)
                    PAT[(size_t)g * NG + w] = full[(size_t)map[g] * nf + map[w]];
            free(full); free(map);
        }
        free(fw);
    }
    for (int g = 0; g < NG; g++)
        if (PAT[(size_t)g * NG + g] != ALL_GREEN) {
            fprintf(stderr, "internal: %s against itself is not all green\n", GWORD[g]); return 1;
        }

    /* Every answer must be a legal guess: it is what keeps the answer inside L,
     * and the whole termination argument with it. */
    ISA = calloc(NG, 1);
    for (int a = 0; a < NA; a++) {
        int g = find_word(aword[a]);
        if (g < 0) { fprintf(stderr, "answer %s is not in the guess list\n", aword[a]); return 1; }
        if (ISA[g]) { fprintf(stderr, "answer %s is listed twice\n", aword[a]); return 1; }
        ISA[g] = 1;
    }
    free(aword);

    int nthreads = 1;
#ifdef _OPENMP
    nthreads = omp_get_max_threads();
#endif
    tt_init(ttbits);

    /* ------------------------------------------------------------- the root */
    uint16_t *rootmem = malloc(sizeof(uint16_t) * NG);
    for (int i = 0; i < NG; i++) rootmem[i] = (uint16_t)i;
    Ctx **ctxs = malloc(sizeof(Ctx *) * nthreads);
    for (int t = 0; t < nthreads; t++) ctxs[t] = ctx_new();
    Cand *rc = malloc(sizeof(Cand) * NG);
    T_START = wall_time();
    score_all(ctxs[0], rootmem, NG, DEPTH, rc);

    Cand *walk = malloc(sizeof(Cand) * NG);
    int nwalk = 0;
    const char *rootmode;
    if (tracepath && !nopen) {
        fprintf(stderr, "wrongle: --trace needs --opener: it traces the openers you name\n");
        return 2;
    }
    if (nopen) {
        rootmode = "named";
        for (int i = 0; i < nopen; i++) {
            int g = find_word(openers[i]);
            if (g < 0) { fprintf(stderr, "--opener %s is not a legal guess\n", openers[i]); return 2; }
            walk[nwalk++] = rc[g];
        }
    } else {
        rootmode = "sweep";
        memcpy(walk, rc, sizeof(Cand) * NG);
        nwalk = order_moves(walk, NG);       /* the beam's K, in bound order */
    }

    char want[256];
    stamp(want, sizeof want, rootmode);
    Res *res = calloc(NG, sizeof(Res));
    int resumed = 0;
    FILE *out = NULL;
    if (outpath) {
        resumed = load_resume(outpath, want, res);
        int fresh = 1;
        FILE *t = fopen(outpath, "r");
        if (t) { fresh = fgetc(t) == EOF; fclose(t); }
        out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
        if (fresh) { fprintf(out, "%s\nopener,status,value,bound,per_answer,secs\n", want); fflush(out); }
    }

    long long incumbent = -1;
    for (int g = 0; g < NG; g++)
        if (res[g].status == 1 && res[g].value > incumbent) incumbent = res[g].value;

    printf("wrongle: objective=%s%s, %s, %d guesses, %d answers, %d threads\n",
           objname(), OBJ == OBJ_LOSE ? "" : " (uncapped)",
           TOPK ? "BEAM (values are LOWER bounds)" : "exact", NG, NA, nthreads);
    if (OBJ == OBJ_LOSE) printf("  maximise answers NOT found within %d guesses\n", DEPTH);
    else                 printf("  maximise total guesses over the answers (mean = total / %d)\n", NA);
    if (TOPK) printf("  beam K=%d at every node, root included: the best of %d openers examined\n",
                     TOPK, nwalk);
    printf("  %d openers to walk%s", nwalk, nopen ? " (named)\n" : "\n");
    if (resumed) printf("  resuming: %d rows already on file, incumbent %lld\n", resumed, incumbent);
    if (nwalk) printf("  root bounds: max %d, min %d\n", walk[0].bound, walk[nwalk - 1].bound);

    int nsolved = 0, ncut = 0, overflow = 0;
    double root_beat = wall_time() + REPORT;
#ifdef _OPENMP
#pragma omp parallel for schedule(monotonic:dynamic, 1)
#endif
    for (int i = 0; i < nwalk; i++) {
        int g = walk[i].g;
        if (res[g].status) continue;
        int tid = 0;
#ifdef _OPENMP
        tid = omp_get_thread_num();
#endif
        Ctx *c = ctxs[tid];
        long long inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
        inc = incumbent;
        double t0 = wall_time();
        int status;
        long long v = 0;
        /* A cut is strict, so a TIE survives: an opener whose bound equals the
         * incumbent is still solved, and can join the tie list. */
        if (!nopen && PRUNE && inc >= 0 && walk[i].bound < inc) status = 2;
        else {
            c->next_beat = wall_time() + REPORT;
            v = eval_move(c, 0, rootmem, NG, g, DEPTH, -1, walk[i].bound);
            if (OBJ == OBJ_EXPECT) v += NA;
            status = 1;
        }
        double secs = wall_time() - t0;
#ifdef _OPENMP
#pragma omp critical (wrongle_out)
#endif
        {
            if (c->overflow) overflow = 1;
            res[g].status = status; res[g].value = v; res[g].bound = walk[i].bound; res[g].secs = secs;
            if (status == 1) {
                nsolved++;
                int better = v > incumbent;
                if (better) incumbent = v;
                printf("%s %s=%lld (%.5f per answer) bound=%d %.1fs%s\n", GWORD[g],
                       OBJ == OBJ_LOSE ? "lost" : "total", v, (double)v / NA,
                       walk[i].bound, secs, better ? "  NEW BEST" : "");
            } else ncut++;
            if (out) {
                fprintf(out, "%s,%s,%lld,%d,%.6f,%.3f\n", GWORD[g], status == 1 ? "solved" : "cut",
                        status == 1 ? v : 0, walk[i].bound, status == 1 ? (double)v / NA : 0.0, secs);
                fflush(out);
            }
            double now = wall_time();
            if (now >= root_beat) {
                root_beat = now + REPORT;
                printf("  ... %d solved, %d cut, best %lld, %.0fs elapsed\n",
                       nsolved, ncut, incumbent, now - T_START);
            }
        }
    }
    if (out) fclose(out);
    if (overflow) { fprintf(stderr, "internal: recursion hit MAXD=%d -- raise it\n", MAXD); return 1; }

    /* The tie list from EVERY row, resumed ones included. */
    long long best = -1;
    int tot_solved = 0, tot_cut = 0;
    for (int i = 0; i < nwalk; i++) {
        int g = walk[i].g;
        if (res[g].status == 1) { tot_solved++; if (res[g].value > best) best = res[g].value; }
        else if (res[g].status == 2) tot_cut++;
    }
    long long nodes = 0;
    for (int t = 0; t < nthreads; t++) nodes += ctxs[t]->nodes;
    printf("\n%s: %d openers solved, %d cut by bound, %lld nodes, %.1fs wall\n",
           TOPK ? "BEAM DONE" : "DONE", tot_solved, tot_cut, nodes, wall_time() - T_START);
    if (best >= 0) {
        printf("BEST %s = %lld (%.5f per answer)%s, attained by:", OBJ == OBJ_LOSE ? "lost" : "total",
               best, (double)best / NA, TOPK ? " -- a LOWER bound, best of the K examined" : "");
        for (int i = 0; i < nwalk; i++)
            if (res[walk[i].g].status == 1 && res[walk[i].g].value == best) printf(" %s", GWORD[walk[i].g]);
        printf("\n");
    }

    if (tracepath) {
        FILE *tf = fopen(tracepath, "w");
        if (!tf) { fprintf(stderr, "cannot write %s\n", tracepath); return 1; }
        fprintf(tf, "opener,lost,line,lost_answers\n");
        for (int i = 0; i < nwalk; i++) {
            int g = walk[i].g;
            if (res[g].status != 1 || res[g].value <= 0) continue;
            double t0 = wall_time();
            trace_opener(ctxs[0], rootmem, g, res[g].value, tf);
            printf("traced %s (%.1fs) -> %s\n", GWORD[g], wall_time() - t0, tracepath);
        }
        fclose(tf);
    }
    for (int t = 0; t < nthreads; t++) ctx_free(ctxs[t]);
    return 0;
}
