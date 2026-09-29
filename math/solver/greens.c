/* greens.c -- the SEA OF GREENS badge: the most answers winnable with no yellow
 * tile, over strategies that still win every answer within the cap.
 *
 * THE BADGE.  NYT Wordle awards "Sea of Greens" for COMPLETING a puzzle with no
 * YELLOW tile anywhere in the game.  Greys are fine; one yellow in any row at
 * any point kills it.  PROVENANCE: read from player reports via web search, not
 * from the NYT and not from a verified badge screen -- the same standing as the
 * Absurdle tie-break rules.  `../greens.py` states the rule and its two inferred
 * clauses; say so whenever a number from here is quoted.
 *
 * THE OBJECTIVE IS LEXICOGRAPHIC (the user's call, 2026-09-03):
 *
 *   1. HARD CONSTRAINT -- resolve EVERY answer within --depth guesses.  Chasing
 *      the badge may not cost a game.  So this is NOT "maximise P(badge)": it is
 *      the maximum SUBJECT TO a 6-guess guarantee, and those are two different
 *      quantities.  Report it in those words.
 *   2. Subject to that, MAXIMISE the number of answers won yellow-free.  Once a
 *      yellow appears the badge is gone for that answer and the strategy is only
 *      required to WIN from there -- "once we get a yellow, we stop checking".
 *
 * Both clauses ride in ONE integer per state, which is what makes the search
 * memoisable at all:
 *
 *   v(S, d) = -1                     if nothing resolves all of S within d
 *           = max badges, otherwise
 *   v(S, d) = max over g of  [1 if g in S]  +  sum over yellow-free non-green
 *                            buckets P of v(P, d-1)
 *             subject to v(P, d-1) >= 0 for EVERY bucket, YELLOW ONES INCLUDED.
 *
 * A yellow bucket therefore needs only feas(P, d-1), the decision version, which
 * is far cheaper than v -- it early-exits on the first witness guess.
 *
 * THE CAP IS THE GAME.  --depth 6 here is not an inherited tuning knob: clause 1
 * IS "do not lose a 6-guess game".  A depth-7 run answers a question about a
 * game nobody plays.  It stays a flag because the gate needs small cases, and
 * each depth still gets its own file.
 *
 * ---------------------------------------------------------------------------
 * PORTING AUDIT -- what came from optturns.c and what did NOT (see the "copying
 * the shape of an existing program" rule in the shared CLAUDE.md).  The loader,
 * the transposition table, the arena and the parallel opener walk are lifted
 * essentially verbatim; the SEARCH is not, because the objective is a maximum
 * with a hard feasibility side-condition rather than a minimum of a sum.
 *
 *   TRANSFERS: MAXG/MAXA 13000 (same word lists).  The .npy loader and its dtype
 *     check.  The TT, its 2-way replacement and its self-verifying entries.  The
 *     per-guess partition that never memsets its 243 counters.  The measured
 *     BRANCH constant, reused for the FEASIBILITY table.  --guess-list /
 *     --answer-list / --patterns.  The parallel walk with a shared incumbent.
 *
 *   DOES NOT TRANSFER, and each was a decision:
 *     - MAXD 20 -> 12.  An array bound, not a modelling limit, but depth here is
 *       6 because the game is 6, so 20 levels of arena is memory for nothing.
 *     - LBTAB (the counting LOWER bound on total guesses) -> FEASOK, the same
 *       counting argument used only as the yes/no it answers, plus UBTAB, a
 *       counting UPPER bound on badges over the YELLOW-FREE branching factor.
 *     - `if (d > n) d = n`, optturns' depth normalisation.  IT IS FALSE HERE.
 *       There, n candidates always resolve within n guesses so extra budget
 *       cannot help; here extra budget buys SAFE PROBES -- words whose letters
 *       are all absent or already green -- which can separate candidates that
 *       could only otherwise be separated by risking a yellow.  So f(S,d) is
 *       strictly increasing in d well past n, and collapsing the key would
 *       silently answer a smaller question.  (feas() keeps the equivalent
 *       shortcut, `n <= d`, which IS sound: guess the candidates one at a time.)
 *     - --topk, --order, --depth-max, --phantom-final, --length, the pair and
 *       triple walks, and the escalating cap.  All of them exist to manage a cap
 *       that is a tuning choice; here it is the rules of the game, pinned.
 *     - --sweep's per-opener table.  The ask was THE best opener, so the walk is
 *       a bounded screen and openers cut by the bound are recorded as `cut`,
 *       never as a number.
 *
 * THE UPPER BOUND IS WEAK, AND THAT IS FINE.  UBTAB saturates at d=4 (1, 32,
 * 993, 30784 against 2315 answers), so past that it degenerates to `min(n, ...)`
 * = n.  What actually prunes is the PER-GUESS bound: the answers in a guess's
 * yellow-free buckets are the only ones that can still earn the badge, and that
 * count is both cheap and tight enough to order every guess by.
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

#define WORDLEN    5
#define NPAT       243
#define ALL_GREEN  242
#define PATSTR_BUF 8
typedef uint8_t pat_t;
#define PAT_NPY    "u1"
#define WBUF       8

#ifndef MAXG
#define MAXG       13000
#endif
#ifndef MAXA
#define MAXA       13000
#endif
/* An ARRAY BOUND, not a modelling limit: it sizes the per-depth arena.  Depth is
 * 6 because a Wordle game is 6 guesses. */
#ifndef MAXD
#define MAXD       12
#endif

/* How many of the evenest-splitting guesses feas() tries before falling back to
 * the full sorted scan.  A pure speed knob: the fallback keeps the search
 * exhaustive, so no value of it can change an answer. */
#define FEAS_TRY   12

#define INFEAS     (-1)      /* no strategy wins every candidate within the cap */
#define PRUNED     (-2)      /* provably cannot reach the caller's floor */
#define CUT        (-3)      /* an opener provably worse than the incumbent */

static int      NG, NA;
static pat_t   *PAT;                 /* NG * NA, row-major: PAT[g*NA + a] */
static char   (*GWORD)[WBUF];
static char   (*AWORD)[WBUF];
static int      ANS2G[MAXA];
static uint64_t ZOB0[MAXA], ZOB1[MAXA];
static uint64_t GSALT = 0;

/* has_yellow, by pattern CODE -- the whole badge rule in one table.  32 of the
 * 243 codes are yellow-free (2**5), all of them attainable. */
static uint8_t  YEL[NPAT];

/* FEASOK[d][n]: could ANY strategy resolve n candidates within d guesses?  The
 * counting bound only -- necessary, never sufficient -- so a 1 still has to be
 * proved by search, while a 0 is a proof of impossibility and is free.
 * UBTAB[d][n]: the most badges obtainable from n candidates with d guesses. */
static uint8_t  FEASOK[MAXD][MAXA + 1];
static int      UBTAB[MAXD][MAXA + 1];
/* Progress reporting.  A run of this shape is silent for hours by construction
 * -- the walk only has something to SAY when the incumbent improves -- so every
 * long-running phase needs a heartbeat of its own or there is no way to tell a
 * working solver from a wedged one.
 *
 * TRACE_ROOT is set only while ONE opener is being solved on ONE thread (the
 * serial probe, and any --opener run), so the root of eval_badge can narrate its
 * buckets without the parallel walk's 18 threads interleaving.  d == ROOT_D
 * identifies the root exactly: every recursive call is at a strictly smaller
 * depth. */
static int      TRACE_ROOT = 0;
static int      ROOT_D = 0;
static double   TRACE_T0 = 0;
static double   TRACE_LAST = 0;
static double   REPORT_EVERY = 60.0;

/* --topk K: at every branching point, recurse into only the K guesses that
 * SPLIT the candidates most evenly (ascending sum of squared bin sizes, ties on
 * the lowest guess index -- the one ranking rule this repo uses everywhere).
 *
 * WHAT IT DOES AND DOES NOT RESTRICT, because the difference is the whole
 * definition:
 *   - It restricts which guesses are RECURSED INTO, not which are PROFILED.
 *     Pass 1 still scores all 12972 at every node, so a node costs what it
 *     always did; the saving is in not exploring thousands of subtrees.
 *   - THE ROOT IS A BRANCHING POINT LIKE ANY OTHER, so it restricts OPENERS
 *     too: the sweep examines the K best openers by the same rule and reports
 *     the best of THOSE -- a deliberately weaker claim than the exact sweep's,
 *     and what makes it finish.  ONE K governs both; there is deliberately no
 *     separate opener count.
 *   - IT NEVER MAKES A STATE LOOK UNWINNABLE.  If no guess in the beam keeps
 *     every candidate winnable, the scan CONTINUES past the beam, in the same
 *     order, until one does.  So clause 1 stays EXACT and only clause 2 -- the
 *     badge maximisation -- is approximated.
 *   - The post-yellow play is never beamed at all: feas() only has to WIN, and
 *     restricting it would report INFEASIBLE for openers that are perfectly
 *     winnable.
 *
 * Consequence worth stating plainly: every value it reports is ACHIEVABLE by a
 * real strategy, so it is a LOWER bound on the true optimum -- the opposite
 * direction from every other bound in this file. */
static int      TOPK = 0;

/* --must-win: the OTHER objective, and they are different quantities.
 *
 *   PLAIN (default) -- maximise the answers WON WITHIN --depth WITH NO YELLOW.
 *     One event per answer.  An answer that draws a yellow is simply LOST and
 *     the strategy owes it nothing afterwards; it may abandon that game.  So
 *     yellow branches are never searched at all, and no state is ever
 *     INFEASIBLE -- the value is a count and counts start at zero.
 *
 *   MUST-WIN -- the same maximisation SUBJECT TO still resolving EVERY answer
 *     within --depth, yellow ones included.  A strictly smaller strategy space,
 *     so its value is always <= the plain one.
 *
 * Plain asks "how often can I win in 6 with all greens?".  Must-win asks "if I
 * refuse to ever lose a game, how often can I win in 6 with all greens?".  Only
 * the first is the badge question.
 *
 * THERE IS NO DEFAULT HERE -- one of --must-win or --may-lose is REQUIRED.
 *
 * It had a default, and that is precisely how `--may-lose` once ran a MUST-WIN
 * search under a may-lose FILENAME: the wrapper forwarded the flag only in the
 * must-win case and let this default cover the other, so when the default moved,
 * the two disagreed silently and the file name lied about its contents.  A
 * defaulted objective is a domain ANSWER hiding in configuration.  Refusing to
 * run is the only default that cannot quietly bias a result.
 *
 * The wrapper still has a default -- must-win, because runs were queued against
 * it -- and forwards it explicitly.  That is the right place for a default: one
 * that a human reads, not one a program falls back on. */
static int      MUSTWIN = -1;

static int      BRANCH = NPAT - 1;   /* measured: non-winning bins, any guess */
static int      GBRANCH = 31;        /* measured: yellow-free non-green bins */

/* ------------------------------------------------------------------ utils */

static uint64_t splitmix64(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

/* Same "byg" spelling optturns' trees use, so a greens tree replays with the
 * same parser -- and a yellow in a line is literally a 'y' in a pattern. */
static void pat_str(int code, char *out) {
    for (int i = WORDLEN - 1; i >= 0; i--) { out[i] = "byg"[code % 3]; code /= 3; }
    out[WORDLEN] = 0;
}

static int has_yellow(int code) {
    for (int i = 0; i < WORDLEN; i++) { if (code % 3 == 1) return 1; code /= 3; }
    return 0;
}

static int cmp_i64(const void *a, const void *b) {
    int64_t x = *(const int64_t *)a, y = *(const int64_t *)b;
    return (x > y) - (x < y);
}

/* --------------------------------------------------------------- loading */

static int load_words(const char *path, char (*out)[WBUF]) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (len == 0) continue;
        if (len > WORDLEN) len = WORDLEN;
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
    if (!strstr(hdr, PAT_NPY)) {
        fprintf(stderr, "pattern matrix dtype is not %s: %s\n", PAT_NPY, hdr); exit(1);
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

static int find_word(char (*list)[WBUF], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* ------------------------------------------------------------- the tables */

/* Both branching factors are MEASURED against the actual answer set, never
 * hardcoded: the right constant depends on which words can be answers, so any
 * literal would be wrong for one of the sweeps.  Sound for sub-states too --
 * for S within A a guess's patterns on S are a subset of its patterns on A. */
static void measure_branching(void) {
    int seen[NPAT];
    int best = 1, gbest = 1;
    for (int g = 0; g < NG; g++) {
        memset(seen, 0, sizeof seen);
        int k = 0, gk = 0;
        const pat_t *row = PAT + (size_t)g * NA;
        for (int a = 0; a < NA; a++) {
            int p = row[a];
            if (seen[p]) continue;
            seen[p] = 1;
            if (p != ALL_GREEN) { k++; if (!YEL[p]) gk++; }
        }
        if (k > best) best = k;
        if (gk > gbest) gbest = gk;
    }
    BRANCH = best;
    GBRANCH = gbest;
}

static void build_tables(void) {
    /* cap(d) = most candidates resolvable within d guesses: the guess itself,
     * plus BRANCH bins each resolvable within d-1. */
    for (int n = 0; n <= NA; n++) { FEASOK[0][n] = (n == 0); UBTAB[0][n] = 0; }
    long long cap = 0, ucap = 0;
    for (int d = 1; d < MAXD; d++) {
        cap  = 1 + (long long)BRANCH  * cap;
        ucap = 1 + (long long)GBRANCH * ucap;
        if (cap  > MAXA) cap  = MAXA;
        if (ucap > MAXA) ucap = MAXA;
        for (int n = 0; n <= NA; n++) {
            FEASOK[d][n] = (n <= cap);
            UBTAB[d][n]  = (n < (int)ucap) ? n : (int)ucap;
        }
    }
}

/* ------------------------------------------------- transposition table */

typedef struct { uint64_t h0, h1x; int32_t val, d; uint32_t work, pad; } Entry;

static Entry   *TT;
static uint64_t TT_BUCKETS;
static long long g_probe = 0, g_hit = 0, g_fill = 0;
static size_t   TT_SLOTS = 0, TT_BYTES = 0;
static int      TT_OFF = 0;

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
    size_t got = 0;
    while (got < bytes) {
        size_t n = fread((char *)TT + got, 1, bytes - got, f);
        if (n == 0) { fprintf(stderr, "tt-load: short read at %zu\n", got); fclose(f); return -1; }
        got += n;
    }
    fclose(f);
    size_t live = 0;
    for (size_t i = 0; i < TT_SLOTS; i++) if (TT[i].h0 || TT[i].h1x) live++;
    g_fill = (long long)live;
    fprintf(stderr, "TT: loaded %s, %zu/%zu slots live (%.2f%%)\n",
            path, live, TT_SLOTS, 100.0 * live / TT_SLOTS);
    return 0;
}

static void tt_save(const char *path) {
    if (TT_OFF) { fprintf(stderr, "tt-save: no table to save (--tt-bits 0)\n"); return; }
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "tt-save: cannot write %s\n", path); return; }
    size_t put = 0;
    while (put < TT_BYTES) {
        size_t n = fwrite((char *)TT + put, 1, TT_BYTES - put, f);
        if (n == 0) { fprintf(stderr, "tt-save: short write at %zu\n", put); break; }
        put += n;
    }
    fclose(f);
    fprintf(stderr, "TT: saved %.2f GB to %s\n", put / 1e9, path);
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
    fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", bits, bytes / 1e9);
    if (!loadpath || tt_load(loadpath, bytes) != 0) {
        if (loadpath) fprintf(stderr, "TT: starting cold instead\n");
        memset(TT, 0, bytes);
    }
}

/* `mode` separates the two value functions sharing this table: 0 = badge value,
 * 1 = feasibility.  They are asked about the SAME (S, d) constantly and mean
 * entirely different things, so conflating them would return a confidently
 * wrong value rather than missing. */
static inline void hash_state(const uint16_t *S, int n, int d, int mode,
                              uint64_t *h0, uint64_t *h1) {
    uint64_t a = (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    uint64_t b = (uint64_t)d * 0xC2B2AE3D27D4EB4FULL;
    for (int i = 0; i < n; i++) { a ^= ZOB0[S[i]]; b ^= ZOB1[S[i]]; }
    uint64_t m = (uint64_t)mode * 0xA24BAED4963EE407ULL;
    *h0 = a ^ m ^ GSALT;
    *h1 = b ^ (m * 0xD6E8FEB86659FD93ULL) ^ (GSALT * 0x9E3779B97F4A7C15ULL);
}

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

/* Depth slots 0 and 1 are never touched by the search -- solve_badge, feas and
 * eval_badge all return before reading the arena at d <= 1 -- so root_ub2
 * borrows slot 0 rather than allocating scratch of its own. */
typedef struct {
    uint16_t buf[MAXD][MAXA];
    uint16_t tbuf[MAXD][MAXA];      /* separate scratch for tree extraction */
    int      cnt[MAXD][NPAT];       /* invariant: all zero between uses */
    int      kof[MAXD][NPAT];
    int64_t  ord[MAXD][MAXG];
    int64_t  ord2[MAXD][MAXG];      /* counting-sort destination, see solve_badge */
    int      ubg[MAXD][MAXG];       /* --topk: each guess's bound, kept by index */
    long long nodes, probe, hit, fill;
} Ctx;

/* ------------------------------------------------------------- the search */

static int solve_badge(const uint16_t *S, int n, int d, Ctx *ctx);

/* Clause 1 alone: can SOME strategy resolve every word of S within d guesses?
 * Early-exits on the first witness, which is what makes it much cheaper than
 * the badge value -- and a yellow bucket is held to nothing else. */
static int feas(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (n <= 1) return d >= 1 || n == 0;
    if (d <= 1) return 0;
    /* n <= d is feasible outright: guess the candidates one at a time.  Sound
     * because every answer is a legal guess (no --phantom-final here), and it is
     * what keeps the post-yellow half of the search cheap. */
    if (n <= d) return 1;
    if (!FEASOK[d][n]) return 0;

    uint64_t h0, h1;
    hash_state(S, n, d, 1, &h0, &h1);
    int cached, cachedg;
    ctx->probe++;
    if (tt_get(h0, h1, d, &cached, &cachedg)) { ctx->hit++; return cached; }
    ctx->nodes++;

    int *cnt = ctx->cnt[d];
    int64_t *ord = ctx->ord[d];
    int m = 0;
    /* Rank by ascending sum of squared bin sizes -- the evenest split first,
     * the same rule every other solver in this repo ranks guesses by -- with
     * ties on the LOWEST guess index.  Only the ORDER depends on it; the answer
     * does not, since the loop below is exhaustive when nothing works.
     *
     * ONLY THE BEST FEW ARE SELECTED, and that is a speed decision, not a
     * change of rule.  A witness settles the question, and the evenest splitter
     * almost always is one -- so sorting all 12972 costs a millisecond per node
     * to order guesses nobody will look at.  Selecting the top FEAS_TRY by
     * insertion is O(NG * FEAS_TRY) with an early reject and no sort at all;
     * if none of them works we fall back to the full sorted scan, so the answer
     * is identical either way. */
    int64_t top[FEAS_TRY];
    int ntop = 0;
    for (int g = 0; g < NG; g++) {
        const pat_t *row = PAT + (size_t)g * NA;
        int bp[NPAT], nb = 0;
        for (int i = 0; i < n; i++) {
            int p = row[S[i]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        int64_t ss = 0;
        int dead = (nb == 1);
        for (int k = 0; k < nb; k++) {
            int p = bp[k], c = cnt[p];
            ss += (int64_t)c * c;
            if (p != ALL_GREEN && !FEASOK[d - 1][c]) dead = 1;
            cnt[p] = 0;
        }
        if (dead) continue;
        ord[m++] = (ss << 20) | (int64_t)g;
        int64_t key = (ss << 20) | (int64_t)g;
        if (ntop < FEAS_TRY) {
            int j = ntop++;
            while (j > 0 && top[j - 1] > key) { top[j] = top[j - 1]; j--; }
            top[j] = key;
        } else if (key < top[ntop - 1]) {
            int j = ntop - 1;
            while (j > 0 && top[j - 1] > key) { top[j] = top[j - 1]; j--; }
            top[j] = key;
        }
    }

    int ok = 0, witness = -1;
    int tried = ntop;                    /* the shortlist, then everything */
    for (int i = 0; i < m + tried && !ok; i++) {
        int g;
        if (i < tried) g = (int)(top[i] & 0xFFFFF);
        else {
            if (i == tried) qsort(ord, m, sizeof(int64_t), cmp_i64);
            g = (int)(ord[i - tried] & 0xFFFFF);
        }
        const pat_t *row = PAT + (size_t)g * NA;
        int bp[NPAT], bcnt[NPAT], bstart[NPAT], bfill[NPAT], nb = 0;
        uint16_t *buf = ctx->buf[d];
        for (int i2 = 0; i2 < n; i2++) {
            int p = row[S[i2]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        for (int k = 0; k < nb; k++) { bcnt[k] = cnt[bp[k]]; cnt[bp[k]] = 0; }
        /* largest bucket first: the hardest subproblem gets to fail first */
        for (int a = 1; a < nb; a++) {
            int tp = bp[a], tc = bcnt[a], j = a - 1;
            while (j >= 0 && bcnt[j] < tc) { bp[j + 1] = bp[j]; bcnt[j + 1] = bcnt[j]; j--; }
            bp[j + 1] = tp; bcnt[j + 1] = tc;
        }
        int *kof = ctx->kof[d];
        for (int k = 0; k < nb; k++) kof[bp[k]] = k;
        int acc = 0;
        for (int k = 0; k < nb; k++) { bstart[k] = acc; bfill[k] = acc; acc += bcnt[k]; }
        for (int i2 = 0; i2 < n; i2++) buf[bfill[kof[row[S[i2]]]]++] = S[i2];

        int all = 1;
        for (int k = 0; k < nb && all; k++) {
            if (bp[k] == ALL_GREEN) continue;         /* that answer is won */
            if (!feas(buf + bstart[k], bcnt[k], d - 1, ctx)) all = 0;
        }
        if (all) { ok = 1; witness = g; }
    }
    tt_put(h0, h1, d, ok, witness, 1, &ctx->fill);
    return ok;
}

/* Badge value of playing g at S with d guesses left and the badge still alive.
 *
 * Returns the exact count, INFEAS if some bucket cannot be won within d-1, or
 * PRUNED if it provably cannot reach `floor`.  PRUNED is NOT a value and is
 * never memoised -- the caller may only use it to decide the guess is not worth
 * exploring, exactly as optturns keeps its bound out of solve(). */
static int eval_badge(const uint16_t *S, int n, int d, int g, int floor, Ctx *ctx) {
    int *cnt = ctx->cnt[d], *kof = ctx->kof[d];
    uint16_t *buf = ctx->buf[d];
    const pat_t *row = PAT + (size_t)g * NA;
    /* indexed by BUCKET ORDINAL, and nb <= min(n, NPAT) -- so these are 243
     * entries, not MAXA.  optturns sizes the same arrays by MAXA; at a
     * quarter-megabyte per frame that would not survive this file's deeper
     * recursion on an OpenMP thread stack. */
    int bp[NPAT], bcnt[NPAT], bstart[NPAT], bfill[NPAT], nb = 0;

    for (int i = 0; i < n; i++) {
        int p = row[S[i]];
        if (cnt[p]++ == 0) bp[nb++] = p;
    }
    for (int k = 0; k < nb; k++) { bcnt[k] = cnt[bp[k]]; cnt[bp[k]] = 0; }
    if (nb == 1) return INFEAS;                  /* reveals nothing */

    /* largest first: the costliest subproblem settles the bound earliest */
    for (int a = 1; a < nb; a++) {
        int tp = bp[a], tc = bcnt[a], j = a - 1;
        while (j >= 0 && bcnt[j] < tc) { bp[j + 1] = bp[j]; bcnt[j + 1] = bcnt[j]; j--; }
        bp[j + 1] = tp; bcnt[j + 1] = tc;
    }
    for (int k = 0; k < nb; k++) kof[bp[k]] = k;
    int acc0 = 0;
    for (int k = 0; k < nb; k++) { bstart[k] = acc0; bfill[k] = acc0; acc0 += bcnt[k]; }
    for (int i = 0; i < n; i++) buf[bfill[kof[row[S[i]]]]++] = S[i];

    /* clause 1, counting screen: free, and rejects most hopeless guesses */
    int badges = 0, rest = 0;
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN) { badges = 1; continue; }   /* won, yellow-free */
        if (MUSTWIN && !FEASOK[d - 1][bcnt[k]]) return INFEAS;
        if (!YEL[bp[k]]) rest += UBTAB[d - 1][bcnt[k]];
    }
    if (badges + rest < floor) return PRUNED;

    /* clause 1 proper, on the YELLOW buckets: they score nothing, so this is all
     * that is ever asked of them -- "once we get a yellow, we stop checking". */
    int trace = (TRACE_ROOT && d == ROOT_D), ndone_b = 0, nyel = 0;
    if (trace && MUSTWIN)
        for (int k = 0; k < nb; k++) if (bp[k] != ALL_GREEN && YEL[bp[k]]) nyel++;
    /* Under the PLAIN objective this loop does not run at all: a yellow bucket
     * is worth nothing and is owed nothing, so it is never examined.  That is
     * the whole difference between the two objectives, and it is also why plain
     * is much the cheaper -- feas() is never called. */
    for (int k = 0; MUSTWIN && k < nb; k++)
        if (bp[k] != ALL_GREEN && YEL[bp[k]]) {
            if (!feas(buf + bstart[k], bcnt[k], d - 1, ctx)) return INFEAS;
            if (trace && (++ndone_b % 16 == 0 || ndone_b == nyel)) {
                char ps[PATSTR_BUF];
                pat_str(bp[k], ps);
                printf("    [%6.0fs] winnable: %d/%d yellow branches checked (%s, %d answers)\n",
                       now_s() - TRACE_T0, ndone_b, nyel, ps, bcnt[k]);
                fflush(stdout);
            }
        }

    /* clause 2, on the yellow-free buckets, which are also held to clause 1 */
    int nfree = 0, kfree = 0;
    if (trace)
        for (int k = 0; k < nb; k++) if (bp[k] != ALL_GREEN && !YEL[bp[k]]) nfree++;
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN || YEL[bp[k]]) continue;
        int own = UBTAB[d - 1][bcnt[k]];
        rest -= own;
        if (badges + own + rest < floor) return PRUNED;
        int v = solve_badge(buf + bstart[k], bcnt[k], d - 1, ctx);
        if (v < 0) return INFEAS;
        badges += v;
        if (trace) {
            char ps[PATSTR_BUF];
            pat_str(bp[k], ps);
            printf("    [%6.0fs] badge branch %d/%d (%s, %3d answers): %d badges, "
                   "%d so far, at most %d more\n",
                   now_s() - TRACE_T0, ++kfree, nfree, ps, bcnt[k], v, badges, rest);
            fflush(stdout);
        }
        if (badges + rest < floor) return PRUNED;
    }
    return badges;
}

static int solve_badge(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (d <= 0) return MUSTWIN ? INFEAS : 0;
    if (n == 1) return 1;                        /* play it: green, no yellow */
    if (d == 1) {
        /* One guess left, more than one candidate.  No guarantee is possible,
         * so must-win fails; plain plays a candidate and badges it if right. */
        if (MUSTWIN) return INFEAS;
        return 1;
    }
    if (MUSTWIN && !FEASOK[d][n]) return INFEAS;
    /* NO depth normalisation here -- see the porting audit at the top of the
     * file.  Extra budget buys safe probes, so f(S, d) keeps rising past d = n. */

    uint64_t h0, h1;
    hash_state(S, n, d, 0, &h0, &h1);
    int cached, cachedg;
    ctx->probe++;
    if (tt_get(h0, h1, d, &cached, &cachedg)) { ctx->hit++; return cached; }

    long long nodes0 = ctx->nodes++;
    /* The root trace narrates BRANCHES, and the branches are sorted largest
     * first -- so the very first one is the all-grey bucket, the biggest
     * subproblem in the whole opener, and it would otherwise be silent for as
     * long as it takes.  This is the heartbeat inside it.  Only ever active on
     * the single thread solving one opener, so the globals need no guarding, and
     * the node-count mask keeps it to one clock read per 4096 nodes. */
    if (TRACE_ROOT && (ctx->nodes & 0xFFF) == 0) {
        double el = now_s();
        if (el - TRACE_LAST >= REPORT_EVERY) {
            TRACE_LAST = el;
            printf("      [%6.0fs] working: %lld nodes, %lld TT probes (%.1f%% hit), "
                   "now at %d candidates with %d guesses left\n",
                   el - TRACE_T0, ctx->nodes, ctx->probe,
                   100.0 * ctx->hit / (ctx->probe ? ctx->probe : 1), n, d);
            fflush(stdout);
        }
    }
    int *cnt = ctx->cnt[d];
    int64_t *ord = ctx->ord[d];
    int m = 0;

    /* pass 1: the per-guess upper bound.  Only answers landing in a YELLOW-FREE
     * bucket can still earn the badge, so their count caps the guess outright --
     * cheap, and tight enough to order every guess by.  Keyed as (NA - ub) so an
     * ASCENDING sort visits the best first with ties on the lowest guess index. */
    int64_t *ssq = ctx->ord2[d];
    int *ubg = ctx->ubg[d];
    int nss = 0;
    for (int g = 0; g < NG; g++) {
        const pat_t *row = PAT + (size_t)g * NA;
        int bp[NPAT], nb = 0;
        for (int i = 0; i < n; i++) {
            int p = row[S[i]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        int ub = 0, hopeless = 0;
        int64_t ss = 0;
        for (int k = 0; k < nb; k++) {
            int p = bp[k], c = cnt[p];
            if (TOPK > 0) ss += (int64_t)c * c;
            if (p == ALL_GREEN) ub += 1;
            else if (MUSTWIN && !FEASOK[d - 1][c]) hopeless = 1;
            else if (!YEL[p]) ub += UBTAB[d - 1][c];
            cnt[p] = 0;
        }
        if (nb == 1) continue;               /* reveals nothing, in either mode */
        if (TOPK > 0) {
            /* SELECTION IS BY SPLIT QUALITY ALONE -- deliberately NOT also by the
             * counting bound.  Mixing the two would make the chosen K depend on a
             * bound the reference implementation does not have, and the beam has
             * to be reproducible outside this file to be checkable at all.  A
             * guess the bound rejects still costs only the skip below. */
            ssq[nss++] = (ss << 20) | (int64_t)g;
            ubg[g] = hopeless ? -1 : ub;
        }
        else if (!hopeless) ord[m++] = ((int64_t)(NA - ub) << 20) | (int64_t)g;
    }
    if (TOPK > 0) {
        qsort(ssq, nss, sizeof(int64_t), cmp_i64);
        int K = (TOPK < nss) ? TOPK : nss;
        int best = INFEAS, bestg = -1;
        for (int i = 0; i < nss; i++) {
            /* Past the beam ONLY while nothing feasible has been found: the beam
             * restricts the badge maximisation, never the win. */
            if (i >= K && best >= 0) break;
            int g = (int)(ssq[i] & 0xFFFFF);
            /* Skip, never break: this order is split quality, not the bound, so
             * a later guess can still have a bigger bound. */
            if (ubg[g] <= best) continue;
            int v = eval_badge(S, n, d, g, best + 1, ctx);
            if (v >= 0 && v > best) { best = v; bestg = g; }
            if (best == n) break;            /* every candidate badged */
        }
        long long workk = ctx->nodes - nodes0;
        tt_put(h0, h1, d, best, bestg,
               workk > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)workk, &ctx->fill);
        return best;
    }

    /* COUNTING SORT, not qsort: the key is an integer bound in 0..n, and n is
     * usually tiny while NG is always 12972.  A qsort here was costing ~0.9 ms
     * of function-pointer comparisons per node against a pass-1 that costs
     * 0.04 ms at n = 3 -- so the sort, not the search, was the hot loop.  The
     * ORDER is identical: descending ub, ties on the lowest guess index, which
     * falls out of scanning ord[] in place order within each bucket. */
    {
        int64_t *dst = ctx->ord2[d];
        int hist[MAXA + 2];
        memset(hist, 0, (size_t)(n + 2) * sizeof(int));
        for (int i = 0; i < m; i++) hist[NA - (int)(ord[i] >> 20)]++;
        int acc = 0;
        for (int v = n; v >= 0; v--) { int c = hist[v]; hist[v] = acc; acc += c; }
        for (int i = 0; i < m; i++) dst[hist[NA - (int)(ord[i] >> 20)]++] = ord[i];
        memcpy(ord, dst, (size_t)m * sizeof(int64_t));
    }

    int best = INFEAS, bestg = -1, prev_ub = NA + 1;
    for (int i = 0; i < m; i++) {
        int ub = NA - (int)(ord[i] >> 20);
        /* The break below is only sound while this list is descending, and a
         * mis-sort would not fail loudly -- it would quietly cut guesses that
         * could have won.  One integer compare per guess actually examined. */
        if (ub > prev_ub) {
            fprintf(stderr, "greens: guess order is not descending (%d after %d) "
                            "-- the counting sort is wrong\n", ub, prev_ub);
            abort();
        }
        prev_ub = ub;
        if (ub <= best) break;                   /* sorted: none left can beat it */
        int g = (int)(ord[i] & 0xFFFFF);
        int v = eval_badge(S, n, d, g, best + 1, ctx);
        if (v >= 0 && v > best) { best = v; bestg = g; }
        if (best == n) break;                    /* every candidate badged */
    }
    long long work = ctx->nodes - nodes0;
    tt_put(h0, h1, d, best, bestg, work > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)work,
           &ctx->fill);
    return best;
}

/* ------------------------------------------------------------- the opener */

/* Every answer, in index order -- the root candidate set. */
static void root_set(uint16_t *out) {
    for (int a = 0; a < NA; a++) out[a] = (uint16_t)a;
}

/* Upper bound on an opener's badge count: no search, O(NA).  The screen visits
 * openers in DESCENDING order of it, so the first whose bound falls below the
 * incumbent proves every opener after it is worse too. */
static int root_ub(int g, int depth) {
    int cnt[NPAT];
    memset(cnt, 0, sizeof cnt);
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int ub = 0;
    for (int p = 0; p < NPAT; p++) {
        if (!cnt[p]) continue;
        if (p == ALL_GREEN) ub += 1;
        else if (MUSTWIN && !FEASOK[depth - 1][cnt[p]]) return INFEAS;
        else if (!YEL[p]) ub += UBTAB[depth - 1][cnt[p]];
    }
    return ub;
}

/* ONE MORE PLY on the opener bound, and it is what makes the screen bite.
 *
 * root_ub above counts every answer that survives the opener yellow-free.  That
 * is loose for an obvious reason: surviving ONE guess is not surviving the game
 * -- an answer stays alive only while every LATER guess is yellow-free against
 * it too -- and with a 6-guess cap the counting term is saturated, so ub1
 * degenerates to exactly "answers in the opener's yellow-free buckets".
 *
 * ub2 asks one question deeper: for each of those buckets, how many of it could
 * the BEST SECOND GUESS keep alive?  Since
 *
 *     badge(P, d) = max over h of [ 1 if h in P ] + sum over Q of badge(Q, d-1)
 *                <= max over h of (answers of P that survive h yellow-free)
 *
 * it is still an upper bound, and typically a fraction of |P|.  A guess whose
 * partition of P is already counting-infeasible is skipped, which tightens it
 * again -- and if NOTHING can be played in some bucket, the opener cannot win
 * and is infeasible outright.
 *
 * COST: NG times the answers surviving the opener, ~1e7 per opener, against
 * searches that run far longer.  It is computed for every opener up front and
 * used BOTH to order the screen and to cut it, so the sorted order still proves
 * the whole tail is worse.  It is NOT exact -- it ignores everything below the
 * second guess -- so an opener it does not cut still has to be solved.
 */
static int root_ub2(int g, int depth, Ctx *ctx) {
    if (depth < 3) return root_ub(g, depth);
    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    memset(cnt, 0, sizeof cnt);
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    uint16_t *buf = ctx->buf[0];
    for (int a = 0; a < NA; a++) buf[fill[row[a]]++] = (uint16_t)a;

    int *c2 = ctx->cnt[0];
    int total = 0;
    for (int p = 0; p < NPAT; p++) {
        if (cnt[p] == 0) continue;
        if (p == ALL_GREEN) { total += 1; continue; }   /* the opener wins outright */
        if (MUSTWIN && !FEASOK[depth - 1][cnt[p]]) return INFEAS;
        if (YEL[p]) continue;                           /* badge already gone here */
        if (cnt[p] == 1) { total += 1; continue; }      /* name it: green, no yellow */

        const uint16_t *P = buf + start[p];
        int np = cnt[p], bestp = -1;
        for (int h = 0; h < NG; h++) {
            const pat_t *hr = PAT + (size_t)h * NA;
            int bp[NPAT], nb = 0;
            for (int i = 0; i < np; i++) {
                int q = hr[P[i]];
                if (c2[q]++ == 0) bp[nb++] = q;
            }
            int v = 0, dead = (nb == 1);
            for (int k = 0; k < nb; k++) {
                int q = bp[k], c = c2[q];
                if (q == ALL_GREEN) v += 1;
                else if (MUSTWIN && !FEASOK[depth - 2][c]) dead = 1;
                else if (!YEL[q]) v += UBTAB[depth - 2][c];
                c2[q] = 0;
            }
            if (!dead && v > bestp) bestp = v;
        }
        if (bestp < 0) return INFEAS;      /* nothing legal to play in this bucket */
        total += bestp;
    }
    return total;
}

/* Split quality of an opener over the whole answer set: the sum of squared bin
 * sizes, ascending, which is what --topk selects the K openers by.  Same rule as
 * the per-node beam, so the root really is a branching point like any other. */
static int64_t root_ssq(int g) {
    int cnt[NPAT];
    memset(cnt, 0, sizeof cnt);
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int64_t ss = 0;
    for (int p = 0; p < NPAT; p++) ss += (int64_t)cnt[p] * cnt[p];
    return ss;
}

/* Exact badge count for committing to `g` as the opener, CUT if provably below
 * `floor`, INFEAS if the opener cannot win every answer within `depth`.
 * TIES SURVIVE: the cut is strict, so an opener equalling the incumbent is
 * always still reported. */
static int solve_opener(int g, int depth, int floor, Ctx *ctx) {
    uint16_t *root = malloc(sizeof(uint16_t) * NA);
    root_set(root);
    int v = eval_badge(root, NA, depth, g, floor, ctx);
    free(root);
    if (v == PRUNED) return CUT;
    return v;
}

/* ---------------------------------------------------------------- trees */

/* The guess achieving this state's value.  Prefer the one the TT recorded and
 * VERIFY it; fall back to a scan, since an entry can be evicted. */
static int best_move_badge(const uint16_t *S, int n, int d, Ctx *ctx) {
    int v = solve_badge(S, n, d, ctx);
    if (v < 0) return -1;
    if (n == 1) return ANS2G[S[0]];
    uint64_t h0, h1;
    hash_state(S, n, d, 0, &h0, &h1);
    int val, bg;
    if (tt_get(h0, h1, d, &val, &bg) && val == v && bg >= 0
        && eval_badge(S, n, d, bg, v, ctx) == v) return bg;
    for (int g = 0; g < NG; g++)
        if (eval_badge(S, n, d, g, v, ctx) == v) return g;
    return -1;
}

/* The witness guess for a state whose badge is already lost: any guess keeping
 * every bucket winnable.  Same two-step -- trust the table, then verify. */
static int feas_move(const uint16_t *S, int n, int d, Ctx *ctx) {
    if (n == 1) return ANS2G[S[0]];
    if (!feas(S, n, d, ctx)) return -1;
    int *cnt = ctx->cnt[d];
    uint64_t h0, h1;
    hash_state(S, n, d, 1, &h0, &h1);
    int val, bg = -1;
    int first = (tt_get(h0, h1, d, &val, &bg) && val == 1 && bg >= 0) ? bg : -1;
    for (int t = -1; t < NG; t++) {
        int g = (t < 0) ? first : t;
        if (g < 0 || (t >= 0 && g == first)) continue;
        const pat_t *row = PAT + (size_t)g * NA;
        int bp[NPAT], nb = 0;
        for (int i = 0; i < n; i++) {
            int p = row[S[i]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        int dead = (nb == 1);
        int bpc[NPAT];
        for (int k = 0; k < nb; k++) { bpc[k] = cnt[bp[k]]; cnt[bp[k]] = 0; }
        if (dead) continue;
        /* rebuild the buckets only for a guess still in the running */
        uint16_t *buf = ctx->tbuf[d];
        int *kof = ctx->kof[d], acc = 0, bstart[NPAT], bfill[NPAT];
        for (int k = 0; k < nb; k++) kof[bp[k]] = k;
        for (int k = 0; k < nb; k++) { bstart[k] = acc; bfill[k] = acc; acc += bpc[k]; }
        for (int i = 0; i < n; i++) buf[bfill[kof[row[S[i]]]]++] = S[i];
        int all = 1;
        for (int k = 0; k < nb && all; k++) {
            if (bp[k] == ALL_GREEN) continue;
            if (!feas(buf + bstart[k], bpc[k], d - 1, ctx)) all = 0;
        }
        if (all) return g;
    }
    return -1;
}

/* One line per answer: "<answer> <nguesses> <g1> <p1> <g2> <p2> ... <answer>",
 * the same format optturns emits, so a line replays end to end and a yellow is
 * literally a 'y' in one of its pattern fields.
 *
 * WHAT IT COVERS DIFFERS BY OBJECTIVE, and that is not a knob:
 *   - PLAIN: the badge-alive subtree only.  A yellow ends that branch -- the
 *     strategy owes those answers nothing -- so the file holds exactly one line
 *     per BADGED answer and its line count equals the reported badge count.
 *   - MUST-WIN: every one of the answers, post-yellow play included, because
 *     there the strategy really does have to finish those games and a replay
 *     covering all of them is what lets checkgreens.py verify it independently. */
static int emit_tree(FILE *out, const uint16_t *S, int n, int d, int alive,
                     char *path, int plen, int ply, Ctx *ctx) {
    if (d <= 0) return 0;                  /* out of guesses: nothing to record */
    int g = alive ? best_move_badge(S, n, d, ctx) : feas_move(S, n, d, ctx);
    if (g < 0) return -1;
    const char *gw = GWORD[g];

    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    memset(cnt, 0, sizeof cnt);
    uint16_t *buf = ctx->tbuf[d];
    const pat_t *row = PAT + (size_t)g * NA;
    for (int i = 0; i < n; i++) cnt[row[S[i]]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int i = 0; i < n; i++) buf[fill[row[S[i]]]++] = S[i];

    if (cnt[ALL_GREEN] > 0) {
        int a = buf[start[ALL_GREEN]];
        fprintf(out, "%s %d %.*s%s\n", AWORD[a], ply, plen, path, gw);
    }
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        if (!MUSTWIN && YEL[p]) continue;  /* badge lost, and nothing is owed */
        char ps[PATSTR_BUF];
        pat_str(p, ps);
        int add = snprintf(path + plen, 8192 - plen, "%s %s ", gw, ps);
        if (emit_tree(out, buf + start[p], cnt[p], d - 1, alive && !YEL[p],
                      path, plen + add, ply + 1, ctx) < 0) return -1;
    }
    return 0;
}

/* The tree OF an opener, so the root guess is GIVEN, not chosen: emit_tree picks
 * the best move at every node, which at the root would silently write the global
 * winner's tree under this opener's name. */
static int write_tree(const char *dir, int g, int depth, Ctx *ctx) {
    char cmd[1200];
    snprintf(cmd, sizeof cmd, "gzip -1 > '%s/%s.txt.gz'", dir, GWORD[g]);
    FILE *out = popen(cmd, "w");
    if (!out) return -1;

    int cnt[NPAT], start[NPAT + 1], fill[NPAT];
    memset(cnt, 0, sizeof cnt);
    uint16_t *buf = ctx->tbuf[depth];
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, sizeof fill);
    for (int a = 0; a < NA; a++) buf[fill[row[a]]++] = (uint16_t)a;

    char *path = malloc(8192);
    int rc = 0;
    if (cnt[ALL_GREEN] > 0) fprintf(out, "%s 1 %s\n", GWORD[g], GWORD[g]);
    for (int p = 0; p < NPAT && rc == 0; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        if (!MUSTWIN && YEL[p]) continue;  /* badge lost, and nothing is owed */
        char ps[PATSTR_BUF];
        pat_str(p, ps);
        int plen = snprintf(path, 8192, "%s %s ", GWORD[g], ps);
        rc = emit_tree(out, buf + start[p], cnt[p], depth - 1, !YEL[p],
                       path, plen, 2, ctx);
    }
    free(path);
    pclose(out);
    return rc;
}

/* Write the tree of an opener that has just become the incumbent.
 *
 * WHY ON EVERY IMPROVEMENT rather than once at the end: a screen this long gets
 * interrupted, and a run that kept only the winning NUMBER would leave the
 * strategy behind -- which is the part anyone actually wants to play.  Files are
 * named for the opener, so superseded ones stay too and the sequence is a free
 * record of how the incumbent improved; the final report names the winner.
 *
 * Improvements are rare -- measured, 30 openers solved and a handful of
 * improvements over 8400 processed -- so the cost is noise against the search. */
static void write_best_tree(const char *dir, int g, int depth, Ctx *ctx, double t0) {
    if (!dir) return;
    double s1 = now_s();
    if (write_tree(dir, g, depth, ctx) != 0)
        fprintf(stderr, "%s: TREE FAILED to write\n", GWORD[g]);
    else {
        printf("[%7.0fs]   tree: %s/%s.txt.gz  (%.1fs)\n",
               now_s() - t0, dir, GWORD[g], now_s() - s1);
        fflush(stdout);
    }
}


/* ------------------------------------------------------------------ main */

static void usage(void) {
    fprintf(stderr,
      "greens -- most answers winnable with NO YELLOW TILE, over strategies that\n"
      "          still win every answer within the cap (see greens.py).\n\n"
      "  --opener WORD     evaluate this opener exactly (repeatable)\n"
      "  --sweep           screen every legal opener for THE best one\n"
      "  --out FILE        CSV results (required for --sweep; --no-out to refuse)\n"
      "  --no-out          run without writing a CSV, deliberately\n"
      "  --trees DIR       write the full decision tree of each --opener\n"
      "  --depth D         guess cap (default 6 -- the game); part of the objective\n"
      "  --tt-bits B       transposition table size, 2^B entries (default 28)\n"
      "  --tt-load/--tt-save FILE      warm start / snapshot\n"
      "  --threads N       OpenMP threads for the sweep\n"
      "  --report SECS     heartbeat interval during the walk (default 60, 0 off)\n"
      "  --may-lose        THE BADGE QUESTION: maximise the answers won within the\n"
      "                    cap with no yellow.  An answer that draws a yellow is\n"
      "                    lost and the strategy may abandon that game.\n"
      "  --must-win        the same maximisation SUBJECT TO winning EVERY answer\n"
      "                    within the cap.  Always <= --may-lose.  ONE OF THESE\n"
      "                    TWO IS REQUIRED -- there is no default objective.\n"
      "  --topk K, -k K    beam: recurse into the K evenest splitters at every\n"
      "                    branching point, the ROOT included -- so it examines K\n"
      "                    OPENERS too, and reports the best of THOSE, not of 12972.\n"
      "  --data DIR        data root (default ./data)\n"
      "  --guess-list/--answer-list/--patterns FILE    restricted runs (the gate)\n");
}

int main(int argc, char **argv) {
    const char *datadir = "data";
    const char *openers[64];
    int nopen = 0;
    const char *outpath = NULL, *treedir = NULL, *ttload = NULL, *ttsave = NULL;
    const char *guesslist = NULL, *answerlist = NULL, *patpath = NULL;
    int depth = 6, ttbits = 28, threads = 0, sweep = 0, noout = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out")) noout = 1;
        else if (!strcmp(argv[i], "--trees") && i + 1 < argc) treedir = argv[++i];
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-load") && i + 1 < argc) ttload = argv[++i];
        else if (!strcmp(argv[i], "--tt-save") && i + 1 < argc) ttsave = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--report") && i + 1 < argc) REPORT_EVERY = atof(argv[++i]);
        else if ((!strcmp(argv[i], "--topk") || !strcmp(argv[i], "-k")) && i + 1 < argc)
            TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--must-win")) MUSTWIN = 1;   /* the default */
        else if (!strcmp(argv[i], "--may-lose")) MUSTWIN = 0;
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc) guesslist = argv[++i];
        else if (!strcmp(argv[i], "--answer-list") && i + 1 < argc) answerlist = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n\n", argv[i]); usage(); return 1; }
    }
    if (MUSTWIN < 0) {
        fprintf(stderr,
                "greens: the OBJECTIVE is required -- pass --may-lose or --must-win.\n"
                "  --may-lose  maximise the answers won within the cap with NO YELLOW;\n"
                "              an answer that draws a yellow is lost and may be abandoned\n"
                "  --must-win  the same, SUBJECT TO winning EVERY answer within the cap\n"
                "They are different quantities. Use solver/run-greens.sh, which passes one.\n");
        return 1;
    }
    if (depth < 1 || depth > MAXD - 1) {
        fprintf(stderr, "--depth must be 1..%d (MAXD is %d)\n", MAXD - 1, MAXD);
        return 1;
    }
    if (!nopen && !sweep) { usage(); return 1; }
    /* A run whose answer goes nowhere is a run that has to be repeated.  The
     * wrapper always passes --out; refusing without it is what stops a bare
     * command line printing a multi-hour result to a terminal and saving it
     * nowhere. */
    if (!outpath && !noout) {
        fprintf(stderr, "greens: --out FILE is required (or --no-out to say you meant it)\n"
                        "        use solver/run-greens.sh, which sets it for you\n");
        return 1;
    }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * MAXG);
    AWORD = malloc(sizeof(char[WBUF]) * MAXA);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
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
    for (int i = 0; i < NG; i++)
        if ((int)strlen(GWORD[i]) != WORDLEN) {
            fprintf(stderr, "guess list holds a %d-letter word (%s)\n",
                    (int)strlen(GWORD[i]), GWORD[i]);
            return 1;
        }
    for (int i = 0; i < NA; i++)
        if ((int)strlen(AWORD[i]) != WORDLEN) {
            fprintf(stderr, "answer list holds a %d-letter word (%s)\n",
                    (int)strlen(AWORD[i]), AWORD[i]);
            return 1;
        }

    /* --guess-list restricts the LEGAL GUESSES, compacting GWORD and the matrix
     * to those rows.  Every guess loop and the sweep enumerate 0..NG-1, so this
     * restricts follow-ups AND the openers screened, with no hot-loop change. */
    if (guesslist) {
        char (*rw)[WBUF] = malloc(sizeof(char[WBUF]) * MAXG);
        int nr = load_words(guesslist, rw);
        if (nr < 1 || nr > MAXG) { fprintf(stderr, "--guess-list: %d words\n", nr); return 1; }
        int *map = malloc(sizeof(int) * nr);
        for (int i = 0; i < nr; i++) {
            map[i] = find_word(GWORD, NG, rw[i]);
            if (map[i] < 0) { fprintf(stderr, "--guess-list word %s is not legal\n", rw[i]); return 1; }
        }
        pat_t *np = malloc((size_t)nr * NA * sizeof(pat_t));
        for (int i = 0; i < nr; i++) {
            memcpy(np + (size_t)i * NA, PAT + (size_t)map[i] * NA, (size_t)NA * sizeof(pat_t));
            memcpy(GWORD[i], rw[i], WBUF);
        }
        free(map); free(rw); free(PAT);
        PAT = np;
        NG = nr;
        fprintf(stderr, "guess list: restricted to %d words\n", nr);
    }
    if (NG > MAXG) { fprintf(stderr, "guess list has %d words, MAXG is %d\n", NG, MAXG); return 1; }
    fprintf(stderr, "loaded %d guesses x %d answers\n", NG, NA);

    /* THE SALT IS UNCONDITIONAL, unlike optturns'.  Both programs key states by
     * (candidate set, depth) over the same words, so their tables would AGREE on
     * every key while meaning entirely different things -- a total of guesses
     * against a count of badges.  Salting always is what makes an optturns
     * tt.bin fail verification here instead of answering. */
    /* TOPK is in the salt for the same reason the word lists are, and more
     * urgently: under a beam the stored values are the best found within the
     * restricted branching, NOT exact optima.  A table from one K read by
     * another K -- or by the exact solver -- would hand back a confidently
     * wrong value that is merely a lower bound.  Each K gets its own keyspace. */
    GSALT = 0x5EA0F69EE45ULL
          ^ ((uint64_t)NG * 0xD6E8FEB86659FD93ULL)
          ^ ((uint64_t)NA * 0x9E3779B97F4A7C15ULL)
          ^ ((uint64_t)(unsigned)TOPK * 0xA24BAED4963EE407ULL)
          ^ ((uint64_t)(unsigned)MUSTWIN * 0xF1EA5EED7A9C1B4DULL);
    for (int i = 0; i < NG; i++)
        for (int j = 0; GWORD[i][j]; j++)
            GSALT = (GSALT ^ (uint8_t)GWORD[i][j]) * 0x100000001B3ULL;
    for (int i = 0; i < NA; i++)
        for (int j = 0; AWORD[i][j]; j++)
            GSALT = (GSALT ^ (uint8_t)AWORD[i][j]) * 0x100000001B3ULL;

    for (int a = 0; a < NA; a++) {
        ANS2G[a] = find_word(GWORD, NG, AWORD[a]);
        if (ANS2G[a] < 0) {
            fprintf(stderr, "answer %s is not a legal guess -- the badge needs it "
                            "PLAYED, so there is no phantom rule here\n", AWORD[a]);
            return 1;
        }
    }
    uint64_t seed = 0xD1B54A32D192ED03ULL;
    for (int a = 0; a < NA; a++) { ZOB0[a] = splitmix64(&seed); ZOB1[a] = splitmix64(&seed); }

    for (int p = 0; p < NPAT; p++) YEL[p] = (uint8_t)has_yellow(p);
    measure_branching();
    build_tables();
    fprintf(stderr, "branching: %d non-winning bins, %d of them yellow-free "
                    "(measured over %d guesses; %d yellow-free codes of %d)\n",
            BRANCH, GBRANCH, NG, 32, NPAT);
    if (MUSTWIN)
        fprintf(stderr, "objective: MUST-WIN -- max answers won with NO YELLOW, "
                        "SUBJECT TO winning all %d within %d guesses\n", NA, depth);
    else
        fprintf(stderr, "objective: max answers WON WITHIN %d GUESSES WITH NO "
                        "YELLOW (of %d); an answer that draws a yellow is lost and "
                        "the strategy may abandon it\n", depth, NA);
    fprintf(stderr, "root badge UB(d=%d, n=%d) = %d\n", depth, NA, UBTAB[depth][NA]);
    tt_init(ttbits, ttload);
    if (treedir) mkdir(treedir, 0755);
#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#endif

    /* THE CSV SELF-DESCRIBES, because a FILENAME CANNOT CHECK ITSELF.
     *
     * This is a scar.  Every result from before the two objectives existed was
     * written under a name that later came to mean the OTHER objective, and a
     * resume then continued that search and reported it as its own -- with the
     * right banner printed above it, which is what made it invisible.  Depth was
     * in every row; the objective and K were in the path alone.
     *
     * So the first line records the whole identity of the run, and a resume
     * REFUSES a file whose line disagrees.  Same discipline as the TT salt: a
     * foreign file must fail verification rather than answer. */
    char stamp[320];
    snprintf(stamp, sizeof stamp,
             "# greens objective=%s topk=%d depth=%d guesses=%d answers=%d",
             MUSTWIN ? "must-win" : "may-lose", TOPK, depth, NG, NA);

    FILE *out = NULL;
    if (outpath) {
        int fresh = 1;
        FILE *rf = fopen(outpath, "r");
        if (rf) { char ch; fresh = (fread(&ch, 1, 1, rf) != 1); fclose(rf); }
        if (!fresh) {
            char line[512] = "";
            FILE *vf = fopen(outpath, "r");
            if (vf) { if (!fgets(line, sizeof line, vf)) line[0] = 0; fclose(vf); }
            char *nl = strchr(line, '\n');
            if (nl) *nl = 0;
            if (line[0] != '#') {
                fprintf(stderr,
                        "%s has no objective stamp, so it predates them and its\n"
                        "contents cannot be told from its name.  Rename it to what it\n"
                        "actually holds and prepend this line:\n  %s\n", outpath, stamp);
                return 1;
            }
            if (strcmp(line, stamp) != 0) {
                fprintf(stderr,
                        "%s was written by a DIFFERENT run:\n  file: %s\n  this: %s\n"
                        "Resuming it would continue that search and report it as this one's.\n",
                        outpath, line, stamp);
                return 1;
            }
        }
        out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (fresh) fprintf(out, "%s\nword,badges,prob,depth,status,seconds\n", stamp);
    }

    if (nopen > 0) {
        Ctx *ctx = calloc(1, sizeof(Ctx));
        for (int k = 0; k < nopen; k++) {
            int g = find_word(GWORD, NG, openers[k]);
            if (g < 0) { fprintf(stderr, "no such guess word: %s\n", openers[k]); return 1; }
            double t0 = now_s();
            ROOT_D = depth; TRACE_T0 = TRACE_LAST = t0; TRACE_ROOT = 1;
            int v = solve_opener(g, depth, 0, ctx);
            TRACE_ROOT = 0;
            double dt = now_s() - t0;
            if (v == INFEAS)
                printf("%s  INFEASIBLE -- cannot win every answer within %d  (%.1fs)\n",
                       openers[k], depth, dt);
            else {
                printf("%s  badges=%d of %d  prob=%.5f  d=%d  (%.1fs, %lld nodes, "
                       "TT %.3f%% hit)\n", openers[k], v, NA, (double)v / NA, depth, dt,
                       ctx->nodes, 100.0 * ctx->hit / (ctx->probe ? ctx->probe : 1));
                if (treedir && write_tree(treedir, g, depth, ctx) != 0)
                    fprintf(stderr, "%s: TREE FAILED to write\n", openers[k]);
            }
            if (out) {
                if (v == INFEAS)
                    fprintf(out, "%s,,,%d,infeasible,%.1f\n", GWORD[g], depth, dt);
                else
                    fprintf(out, "%s,%d,%.5f,%d,exact,%.1f\n", GWORD[g], v,
                            (double)v / NA, depth, dt);
                fflush(out);
            }
            fflush(stdout);
        }
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    /* ------------------------------------------------------------- sweep */
    /* THE ASK WAS THE BEST OPENER, so this is a bounded screen, not a per-opener
     * table: openers are visited in DESCENDING upper bound and the first whose
     * bound falls below the incumbent proves the whole tail is worse.  Openers
     * cut that way get a `cut` row and never a number -- they are bounded, not
     * solved, and the two must never be confused. */
    int *ub = malloc(sizeof(int) * NG);
    int64_t *ord = malloc(sizeof(int64_t) * NG);
    int nord = 0, noub = 0;
    double tscreen = now_s();
    long long screened = 0;

    if (TOPK > 0) {
        /* THE ROOT IS A BRANCHING POINT LIKE ANY OTHER, so the openers are
         * selected by the same rule the nodes use: ascending sum of squared bin
         * sizes, ties on the lowest guess index.  The two-ply bound is skipped
         * entirely here -- it costs 21s and MEASURED it tightens the openers
         * that matter by 0.3%, because its maximiser is always a guess that
         * learns nothing (for `bubby` the best second guess is `bubby` again).
         * The cheap one-ply bound is kept for the incumbent cut only. */
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int g = 0; g < NG; g++) ub[g] = root_ub(g, depth);
        for (int g = 0; g < NG; g++) {
            if (ub[g] == INFEAS) { noub++; continue; }
            ord[nord++] = (root_ssq(g) << 20) | (int64_t)g;
        }
        qsort(ord, nord, sizeof(int64_t), cmp_i64);
        /* ONE K GOVERNS BOTH, and that is the point of the convention: the root
         * is a branching point like any other, so the same rule that picks K
         * guesses at a node picks K openers here. */
        if (nord > TOPK) nord = TOPK;
        fprintf(stderr, "root: %d openers examined of %d, by ascending sum of "
                        "squared bins (%d rejected outright)  [%.1fs]\n",
                nord, NG, noub, now_s() - tscreen);
        printf("--topk %d: the best of the %d openers EXAMINED, not of all %d, "
               "and every value is ACHIEVABLE -- a lower bound on the true optimum\n",
               TOPK, nord, NG);
    } else {
    fprintf(stderr, "screening %d openers with the two-ply bound (no search yet; "
                    "this is the part that decides how much the walk can skip)\n", NG);
#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        Ctx *sc = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 16)
#endif
        for (int g = 0; g < NG; g++) {
            ub[g] = root_ub2(g, depth, sc);
            long long k;
#ifdef _OPENMP
#pragma omp atomic capture
#endif
            k = ++screened;
            if (k % 500 == 0)
                fprintf(stderr, "  screening openers: %lld/%d  (%.0fs)\n",
                        k, NG, now_s() - tscreen);
        }
        free(sc);
    }
    fprintf(stderr, "root screen: %.1fs\n", now_s() - tscreen);

    for (int g = 0; g < NG; g++) {
        if (ub[g] == INFEAS) { noub++; continue; }
        ord[nord++] = ((int64_t)(NA - ub[g]) << 20) | (int64_t)g;
    }
    qsort(ord, nord, sizeof(int64_t), cmp_i64);
    fprintf(stderr, "root UB screen: %d openers ranked, %d rejected outright\n",
            nord, noub);
    /* The bound's DISTRIBUTION is what says whether the screen can prune at all:
     * every opener whose bound falls below the eventual winner is cut without
     * being searched, so the gap between the top of this list and the winner is
     * the whole pruning budget. */
    if (nord) {
        int q[5];
        for (int i = 0; i < 5; i++) q[i] = NA - (int)(ord[(int64_t)i * (nord - 1) / 4] >> 20);
        fprintf(stderr, "root UB quartiles: %d %d %d %d %d (of %d answers)\n",
                q[0], q[1], q[2], q[3], q[4], NA);
    }
    }

    /* Resume: an existing CSV marks work done, seeds the incumbent AND rebuilds
     * the tie list.  Rebuilding it matters -- without it a resumed run reports
     * only the ties it happened to find after restarting, which reads as a
     * complete answer and is not one. */
    int incumbent = 0;
    char *done = calloc(NG, 1);
    int *bestlist = malloc(sizeof(int) * NG);
    int nbest = 0, searched = 0, cut = 0, infeas = 0;
    int ndone = 0;
    double last_report = 0;
    FILE *rf = outpath ? fopen(outpath, "r") : NULL;
    if (rf) {
        char line[256];
        while (fgets(line, sizeof line, rf)) {
            if (line[0] == '#') continue;          /* the objective stamp */
            char w[64]; int b;
            int nf = sscanf(line, "%63[^,],%d", w, &b);
            if (nf < 1) continue;
            int g = find_word(GWORD, NG, w);
            if (g < 0) continue;                       /* a header, or a stale word */
            if (!done[g]) { done[g] = 1; ndone++; }
            if (nf < 2) continue;                      /* a cut or infeasible row */
            if (b > incumbent) { incumbent = b; nbest = 0; bestlist[nbest++] = g; }
            else if (b == incumbent) bestlist[nbest++] = g;
        }
        fclose(rf);
        if (ndone) fprintf(stderr, "resume: %d openers done, incumbent %d with %d tied\n",
                           ndone, incumbent, nbest);
    }

    double t0 = now_s();
    printf("sweep: %d openers %s; reporting the best of them\n", nord,
           TOPK > 0 ? "by ascending sum of squared bins (--topk)"
                    : "by descending badge upper bound");
    fflush(stdout);

    /* SOLVE THE TOP-RANKED OPENER FIRST, SERIALLY.  The walk cuts against the
     * incumbent, and with N threads starting at once the first N openers all run
     * with no incumbent at all -- so one opener solved up front is worth more
     * than the thread it costs, and it prices the run in its first line. */
    for (int i = 0; i < nord && nbest == 0; i++) {
        int g = (int)(ord[i] & 0xFFFFF);
        if (done[g]) continue;
        Ctx *c0 = calloc(1, sizeof(Ctx));
        double s0 = now_s();
        printf("[%7.0fs] %s: solving the first opener serially to seed the bound "
               "-- narrating its root branches so this phase is not silent\n",
               now_s() - t0, GWORD[g]);
        fflush(stdout);
        ROOT_D = depth; TRACE_T0 = TRACE_LAST = s0; TRACE_ROOT = 1;
        int v = solve_opener(g, depth, incumbent, c0);
        TRACE_ROOT = 0;                  /* the parallel walk must not interleave */
        double dt = now_s() - s0;
        g_probe += c0->probe; g_hit += c0->hit; g_fill += c0->fill;
        done[g] = 1;
        const char *status = v == INFEAS ? "infeasible" : (v == CUT ? "cut" : "exact");
        if (v >= 0) {
            searched++;
            incumbent = v;
            bestlist[nbest++] = g;
            printf("[%7.0fs] %s  badges=%d of %d  prob=%.5f  FIRST  %6.1fs\n",
                   now_s() - t0, GWORD[g], v, NA, (double)v / NA, dt);
            write_best_tree(treedir, g, depth, c0, t0);
        } else if (v == INFEAS) infeas++;
        else cut++;
        /* Freed only AFTER write_best_tree, which uses c0's arena as scratch.
         * Freeing it first worked by luck on macOS and segfaulted on Linux,
         * where a block this size is unmapped the moment it is freed. */
        free(c0);
        if (out) {
            if (v >= 0) fprintf(out, "%s,%d,%.5f,%d,%s,%.1f\n", GWORD[g], v,
                                (double)v / NA, depth, status, dt);
            else        fprintf(out, "%s,,,%d,%s,%.1f\n", GWORD[g], depth, status, dt);
            fflush(out);
        }
        fflush(stdout);
    }

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
            int myub = ub[g];        /* the key is split quality under --topk */
            if (done[g]) continue;
            int inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
            inc = incumbent;
            /* TIES SURVIVE: strict `<`, so an opener that can only equal the
             * incumbent is still solved and still reported. */
            if (myub < inc) {
                /* Cut without any search: its bound is already below a value
                 * something else achieved.  It gets a `cut` row and never a
                 * number -- bounded is not solved, and a resume must not read
                 * one as the other. */
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    cut++;
                    if (out) {
                        fprintf(out, "%s,,,%d,cut,0.0\n", GWORD[g], depth);
                        fflush(out);
                    }
                }
                continue;
            }
            double s0 = now_s();
            int v = solve_opener(g, depth, inc, ctx);
            double dt = now_s() - s0;
            int newbest = 0;
#ifdef _OPENMP
#pragma omp critical
#endif
            {
                g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                ctx->probe = ctx->hit = ctx->fill = 0;
                double el = now_s() - t0;
                if (REPORT_EVERY > 0 && el - last_report >= REPORT_EVERY) {
                    last_report = el;
                    int seen = searched + cut + infeas;
                    printf("[%7.0fs] %d/%d openers  (%d solved, %d cut, %d infeasible)"
                           "  best %d of %d = %.5f", el, seen, nord, searched, cut,
                           infeas, incumbent, NA, (double)incumbent / NA);
                    if (nbest) printf("  leader %s%s", GWORD[bestlist[0]],
                                      nbest > 1 ? " (tied)" : "");
                    printf("  TT %.1f%% hit\n", 100.0 * g_hit / (g_probe ? g_probe : 1));
                    fflush(stdout);
                }
                const char *status = "exact";
                if (v == INFEAS)   { infeas++;   status = "infeasible"; }
                else if (v == CUT) { cut++;      status = "cut"; }
                else {
                    searched++;
                    if (v > incumbent) {
                        incumbent = v;
                        nbest = 0;
                        bestlist[nbest++] = g;
                        newbest = 1;
                        printf("[%7.0fs] %s  badges=%d of %d  prob=%.5f  NEW BEST  %6.1fs\n",
                               now_s() - t0, GWORD[g], v, NA, (double)v / NA, dt);
                        fflush(stdout);
                    } else if (v == incumbent) {
                        bestlist[nbest++] = g;
                    }
                }
                if (out) {
                    if (v >= 0)
                        fprintf(out, "%s,%d,%.5f,%d,%s,%.1f\n", GWORD[g], v,
                                (double)v / NA, depth, status, dt);
                    else
                        fprintf(out, "%s,,,%d,%s,%.1f\n", GWORD[g], depth, status, dt);
                    fflush(out);
                }
            }
            /* OUTSIDE the critical section deliberately: a tree walk can take a
             * while and there is no reason to stall 17 other threads for it.
             * Nothing is shared -- the arena is per-thread, the table is
             * self-verifying, and the file is named for the opener, so two
             * threads improving at once write two different files. */
            if (newbest) write_best_tree(treedir, g, depth, ctx, t0);
        }
        free(ctx);
    }

    printf("\n=== BEST OPENER (answers %d, guesses %d, depth %d%s) ===\n",
           NA, NG, depth, TOPK > 0 ? ", --topk" : "");
    if (TOPK > 0)
        printf("BEST OF THE %d OPENERS EXAMINED, not of all %d, and every value is a\n"
               "LOWER bound on that opener's true optimum -- the beam only ever finds\n"
               "strategies, never proves one best.\n", nord, NG);
    printf("badges = %d of %d  (%.5f of answers), %d openers tied\n",
           incumbent, NA, (double)incumbent / NA, nbest);
    for (int i = 0; i < nbest; i++) printf("  %s\n", GWORD[bestlist[i]]);
    printf("%d openers solved exactly, %d cut by the bound, %d infeasible, %.0fs\n",
           searched, cut, infeas, now_s() - t0);
    fprintf(stderr, "TT %.3f%% hit over %lld probes\n",
            100.0 * g_hit / (g_probe ? g_probe : 1), g_probe);
    if (ttsave) tt_save(ttsave);
    if (out) fclose(out);
    return 0;
}
