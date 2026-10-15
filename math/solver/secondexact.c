/* secondexact -- the EXACT best predetermined second word, and the exact value
 * of the strategy it defines.
 *
 * THE STRATEGY, and math/wordlesim.py is the source of truth for it: play an
 * opener; if its reply FIRES the condition (at least --min-grays greys, plus any
 * --fire compositions), play one word committed to in advance; otherwise, and
 * from the third guess on, play a word drawn UNIFORMLY AT RANDOM from the
 * ANSWERS still consistent with every reply.
 *
 * WHY THIS IS EXACT, when the strategy is randomised.  The random tail's cost
 * depends only on the live candidate SET, and playing a uniform random g from S
 * sends the answer into its part of S under g -- a set that never contains g, so
 * it is STRICTLY smaller and the recursion terminates.  Writing T(S) for the
 * total guesses summed over the answers in S:
 *
 *     T(S) = |S| + (1/|S|) * sum over g in S of sum over parts P != {g} of T(P)
 *
 * memoised on the set.  The sets here are tiny -- after two guesses the mean is
 * about five answers -- so this is cheap, and unlike a simulation it has no seed
 * and no standard error.  tools/checksecondexact.py checks it against a
 * brute-force playout.
 *
 * WHY EXACT RATHER THAN SIMULATED.  Choosing between 12972 second words means
 * resolving differences of about 0.005 guesses; at a per-game sd near 0.9 that
 * is ~290000 games EACH, some 3.8 billion games for one opener, and the answer
 * still arrives with an error bar.  The recursion settles the same question in
 * minutes and returns THE argmin.
 *
 * THE BOUND, which is what makes the search a PROOF rather than a screen.
 * T(S) >= 2|S| - 1 for every set, by induction: a guess splits S minus itself
 * into at most |S|-1 parts, so
 *     T(S) >= |S| + (1/|S|) * sum over g of [2(|S|-1) - (|S|-1)] = 2|S| - 1.
 * Summed over the buckets a second word creates, that is a lower bound needing
 * only the bucket SIZES -- one pass, no recursion.  MEASURED on `spilt`: it
 * discards 85% of the second words outright, and more as the incumbent improves.
 *
 * THE SEARCH IS THE REPO'S --optimal-only WALK, TWO LEVELS DEEP.  Openers are
 * ordered by their own lower bound (exact decline branch + the cheapest possible
 * second-word part) and walked against a global incumbent; within an opener the
 * second words are ordered and cut the same way.  Because the order is ASCENDING
 * and the bound is SOUND, the first opener whose bound exceeds the incumbent
 * proves the whole TAIL is worse, and the walk stops.  What comes out is the
 * proven optimum over every (opener, second word) pair -- not "the best of those
 * examined".  Ties are KEPT: every cut tests `>`, never `>=`.
 *
 * IT IS TIED TO THE `answer` FOLLOW-UP.  The tail draws from consistent ANSWERS,
 * so a state is a subset of the 2315.  The `guess` follow-up draws from the
 * consistent legal WORDS, which is a different and much larger recursion, and is
 * not what this computes.
 *
 * FIVE MODES, ONE SEARCH.  A committed SECOND word per group (the above); a
 * fixed THIRD level keyed by matched count (--third-key); a word at EVERY level
 * and every count (--max-level); and THE LADDER (--ladder), which is one word
 * per level fired by a THRESHOLD on the matched letters, with declining ENDING
 * the ladder -- the strategy a player can actually follow.  They are DIFFERENT
 * strategies, not four searches for one answer, so their totals never share a
 * table; what they share is the exact tail, the bound and the walk.
 *
 * Build:  see build.sh      Run:  bash solver/run-second-exact.sh   (from math/)
 *                                 bash solver/run-ladder.sh         (--ladder)
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <time.h>
#include <math.h>
#include "groups.h"
#ifdef _OPENMP
#include <omp.h>
#endif

#define ALL_GREEN (NPAT - 1)
#define MAXDEPTH 64

static int      NG, NA;
static uint8_t *PAT;                 /* NG * NA, row-major */
static char   (*GWORD)[WBUF];
/* THE GROUPS ARE INDEPENDENT, and that is what makes a per-bucket version no
 * harder than the single-word one: they PARTITION the firing replies, so the
 * strategy's total is
 *     decline + sum over groups of (that group's cost with its own word)
 * and each group's best word can be found on its own.  There is no joint search
 * over k words -- k separate argmins, and since every answer still falls in
 * exactly one group the total scanning work barely moves.
 *
 * WHICH REPLIES A GROUP COVERS IS groups.c's ANSWER, not this file's.  The same
 * unit defines it for `secondword`, so a table one writes is a table the other
 * reads and they cannot drift on what `e3_mv1` means.  The vowel atoms make a
 * mask depend on the OPENER, so the masks are rebuilt per opener where they are
 * used rather than once at startup. */
#define MAXGRP MAXGROUP
/* matched letters run 0..5, so a case index is one of six */
#define MAXCASE 6
/* how deep a committed-word ladder may go: --max-level's cap and --ladder's */
#define MAXLVL 8
/* THE PER-LEVEL SCRATCH IS SIZED MAXLVL + 2, NOT MAXLVL.  `expand` writes its
 * children into the arrays at its OWN depth, and depth reaches `maxlvl`, so
 * arrays of MAXLVL entries are one short at the deepest legal cap and the
 * ladder's own expansion needs one more still.  Sized here rather than by
 * lowering the cap, because the cap is the user's knob. */
#define NLVLBUF (MAXLVL + 2)
static uint8_t  GFIRE[MAXGRP][NPAT]; /* the CURRENT opener's group masks */
static uint8_t  FIRE[NPAT];          /* any group at all: the union */
static int      OPENER_DEP;          /* do the masks depend on the opener? */
static int32_t *ANS2G;               /* answer index -> guess index */
/* --words POOL: WHICH WORDS MAY BE COMMITTED TO, at every level and at the root.
 * NULL means all 12972.  It is a DIFFERENT OBJECTIVE, not a setting -- a strictly
 * smaller strategy space, so its totals are weakly worse and must never share a
 * table with an unrestricted run.  Hence it is in the label, hence in the
 * filename and the settings stamp, and a resume refuses a file from the other.
 *
 * It does NOT touch the TAIL, which always draws from the consistent ANSWERS:
 * that is the strategy's definition, not a pool anyone chose. */
static uint8_t *INPOOL;
#define COMMITTABLE(w) (!INPOOL || INPOOL[w])

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

/* ---- the memo: candidate SET -> T(S) ------------------------------------
 * A DIRECT-MAPPED CACHE THAT REPLACES, not a table that must hold everything.
 * A bad opener leaves huge buckets and so an enormous number of distinct
 * subsets; growing to fit them would be gigabytes per thread, and clearing when
 * full thrashes -- measured, it turned four seconds into minutes, because each
 * clear is a memset of the whole table.  Replacement keeps the recently used
 * sets, which are the ones that recur, and bounds the memory exactly.
 *
 * THE KEY IS A 128-BIT FINGERPRINT of the set, not the set itself.  Storing the
 * answer indices inline caps what is cacheable at a couple of dozen, and that is
 * exactly wrong: a BAD opener leaves buckets of hundreds, whose recursion is the
 * expensive part and explodes without a cache -- measured, capping the key at 20
 * turned a four-second job into minutes.  Two independent 64-bit hashes plus the
 * set SIZE are compared instead, so a false hit needs a simultaneous collision in
 * both and the same length: about 2^-128, which across any run this will ever
 * make is nil.  This is the same bargain optturns' transposition table makes, and
 * the same reason it is stated rather than hidden.
 */
typedef struct {
    uint64_t h1, h2;
    double   v;
    uint32_t n;
} Entry;

typedef struct {
    Entry    *e;
    size_t    mask;
    long long hits, misses, stores;
    /* THE SCRATCH IS INDEXED BY DEPTH, all of it.  The recursion partitions a
     * set while walking the parts of its caller's partition, so a single shared
     * counter array is clobbered by the very call that is reading it -- which is
     * a heap overflow within a few levels, not a subtly wrong answer.  Each
     * level gets its own counters, touched list and part offsets. */
    uint16_t *buf;
    int      *cnt, *touch, *start, *len;
    long long nodes;
} Memo;

static void hash_set(const uint16_t *s, int n, uint64_t *a, uint64_t *b) {
    uint64_t h1 = 1469598103934665603ULL, h2 = 14695981039346656037ULL;
    for (int i = 0; i < n; i++) {
        h1 = (h1 ^ s[i]) * 1099511628211ULL;
        h2 = (h2 ^ (uint64_t)s[i] * 0x9E3779B97F4A7C15ULL) * 0xC2B2AE3D27D4EB4FULL;
    }
    *a = h1 ? h1 : 1;
    *b = h2;
}

static void memo_init(Memo *m, size_t bits) {
    m->mask = ((size_t)1 << bits) - 1;
    m->e = calloc(m->mask + 1, sizeof(Entry));
    if (!m->e) { fprintf(stderr, "out of memory for the memo\n"); exit(1); }
    m->buf = malloc(sizeof(uint16_t) * (size_t)MAXDEPTH * NA);
    m->cnt   = calloc((size_t)MAXDEPTH * NPAT, sizeof(int));
    m->touch = malloc(sizeof(int) * (size_t)MAXDEPTH * NPAT);
    m->start = malloc(sizeof(int) * (size_t)MAXDEPTH * NPAT);
    m->len   = malloc(sizeof(int) * (size_t)MAXDEPTH * NPAT);
    m->nodes = m->hits = m->misses = m->stores = 0;
}

static void memo_clear(Memo *m) {
    memset(m->e, 0, (m->mask + 1) * sizeof(Entry));
}

static int memo_get(Memo *m, uint64_t h1, uint64_t h2, int n, double *v) {
    Entry *e = &m->e[h1 & m->mask];
    if (e->h1 == h1 && e->h2 == h2 && e->n == (uint32_t)n) {
        m->hits++;
        *v = e->v;
        return 1;
    }
    m->misses++;
    return 0;
}

static void memo_put(Memo *m, uint64_t h1, uint64_t h2, int n, double v) {
    Entry *e = &m->e[h1 & m->mask];
    e->h1 = h1; e->h2 = h2; e->n = (uint32_t)n; e->v = v;
    m->stores++;
}

/* T(S): the total guesses summed over the answers in S, playing a uniform random
 * consistent ANSWER every turn.  `depth` indexes the scratch arena. */
static double T(Memo *m, const uint16_t *s, int n, int depth) {
    if (n <= 1) return (double)n;
    if (depth >= MAXDEPTH) {
        fprintf(stderr, "recursion deeper than %d -- a part did not shrink\n",
                MAXDEPTH);
        exit(1);
    }
    uint64_t h1, h2;
    hash_set(s, n, &h1, &h2);
    double cached;
    if (memo_get(m, h1, h2, n, &cached)) return cached;
    m->nodes++;

    uint16_t *out = m->buf + (size_t)depth * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int *pstart = m->start + (size_t)depth * NPAT;
    int *plen = m->len + (size_t)depth * NPAT;
    double tot = (double)n;
    for (int gi = 0; gi < n; gi++) {
        const uint8_t *row = PAT + (size_t)ANS2G[s[gi]] * NA;
        /* count the parts of S minus this guess, then lay them out contiguously
         * and recurse into each.  `cnt` doubles as the fill cursor, which is why
         * it is cleared through the touched list rather than memset. */
        int nt = 0;
        for (int i = 0; i < n; i++) {
            if (i == gi) continue;
            int p = row[s[i]];
            if (cnt[p]++ == 0) touch[nt++] = p;
        }
        int acc = 0;
        for (int k = 0; k < nt; k++) {
            int p = touch[k];
            plen[k] = cnt[p];
            pstart[k] = acc;
            cnt[p] = acc;                    /* now the fill cursor */
            acc += plen[k];
        }
        for (int i = 0; i < n; i++) {
            if (i == gi) continue;
            out[cnt[row[s[i]]]++] = s[i];
        }
        for (int k = 0; k < nt; k++)
            tot += T(m, out + pstart[k], plen[k], depth + 1) / (double)n;
        for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
    }
    memo_put(m, h1, h2, n, tot);
    return tot;
}

/* ------------------------------------------------------------ the loader --- */

static int load_words_file(const char *path, char (*out)[WBUF]) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (!len) continue;
        if (len > WBUF - 1) len = WBUF - 1;
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
        hlen = (size_t)b[0] | ((size_t)b[1] << 8) | ((size_t)b[2] << 16)
             | ((size_t)b[3] << 24);
    }
    char *hdr = malloc(hlen + 1);
    if (fread(hdr, 1, hlen, f) != hlen) exit(1);
    hdr[hlen] = 0;
    if (!strstr(hdr, "u1")) { fprintf(stderr, "patterns not uint8\n"); exit(1); }
    char *p = strchr(hdr, '(');
    if (!p || sscanf(p, "(%d, %d)", rows, cols) != 2) {
        fprintf(stderr, "cannot parse shape from: %s\n", hdr); exit(1);
    }
    free(hdr);
    size_t nb = (size_t)(*rows) * (size_t)(*cols);
    uint8_t *d = malloc(nb);
    if (fread(d, 1, nb, f) != nb) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return d;
}


/* ------------------------------------------------------- one opener ------- */

typedef struct {
    int32_t opener;
    int32_t second[MAXGRP];       /* one word per group */
    double  fired[MAXGRP];        /* and that group's exact total */
    int32_t nq[MAXGRP], scanned[MAXGRP], cut[MAXGRP];
    int32_t third[MAXGRP][MAXCASE];   /* the committed third word per case, -1 */
    int32_t ntree[MAXGRP];            /* --max-level: the committed-word tree,
                                       * flattened as (path, word) pairs */
    uint32_t tpath[MAXGRP][24];
    int32_t  tword[MAXGRP][24];
    /* --ladder: ONE word and ONE threshold per level, so the whole strategy is
     * nine numbers rather than a tree.  `lthr[d]` fires `lword[d]` when the
     * cumulative matched letters are strictly below it. */
    int32_t  lword[MAXLVL + 2];
    int8_t   lthr[MAXLVL + 2];
    double  decline;              /* exact total over the replies that do NOT fire */
    double  bound;                /* a sound lower bound on the whole total */
    int     done;
    int     resumed;              /* already on file from an earlier run */
} Row;

/* The exact total over the FIRING answers for one second word -- or a LOWER
 * BOUND on it when `bound_only`, which needs the bucket SIZES alone and so costs
 * one counting pass with no recursion.
 *
 * The qualifying answers arrive already grouped by their reply to the OPENER
 * (`nb` runs of (start, len)), so the joint bucket is one counting pass on the
 * second reply inside each run.  The bucket where w is itself the answer costs
 * no tail at all: the game ended on that guess.
 */
/* `ssq_out`, when given, receives the SUM OF SQUARED JOINT BUCKET SIZES -- the
 * one-ply score `secondword` ranks by.  It is a different aggregation of the
 * very buckets this function already walks, so it costs an add per bucket and
 * needs no second pass.  It counts EVERY bucket, the all-green one included,
 * because that is what secondword.c does (solver/secondword.c, `ssq`). */
static double fired_total(Memo *m, const uint16_t *q, int nq, const int *rstart,
                          const int *rlen, int nb, int w, int bound_only,
                          uint16_t *out, int depth, int64_t *ssq_out) {
    const uint8_t *row2 = PAT + (size_t)w * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int *pstart = m->start + (size_t)depth * NPAT;
    int *plen = m->len + (size_t)depth * NPAT;
    double tot = 2.0 * nq;
    for (int b = 0; b < nb; b++) {
        const uint16_t *s = q + rstart[b];
        int n = rlen[b], nt = 0;
        for (int i = 0; i < n; i++) {
            int p = row2[s[i]];
            if (cnt[p]++ == 0) touch[nt++] = p;
        }
        int acc = 0;
        for (int k = 0; k < nt; k++) {
            int p = touch[k];
            plen[k] = cnt[p];
            pstart[k] = acc;
            cnt[p] = acc;
            acc += plen[k];
        }
        for (int i = 0; i < n; i++) out[cnt[row2[s[i]]]++] = s[i];
        for (int k = 0; k < nt; k++) {
            if (ssq_out) {
                int64_t v = plen[k];
                *ssq_out += v * v;
            }
            if (touch[k] == ALL_GREEN) continue;         /* w won: no tail */
            if (bound_only)
                tot += 2.0 * plen[k] - 1.0;              /* T(S) >= 2|S| - 1 */
            else
                tot += T(m, out + pstart[k], plen[k], depth + 1);
        }
        for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
    }
    return tot;
}

/* The exact total over the answers whose reply does NOT fire: the opener, then
 * the random tail straight away.  Independent of the second word, so it is
 * computed once per opener -- and it is what makes one opener comparable with
 * another rather than only one second word with another. */
/* THE MASKS THIS OPENER FIRES ON.  A condition of grey counts alone has the same
 * masks for every opener and they were built once at startup; a v<N> or mv<N>
 * atom makes them depend on the opener's letters, so they are rebuilt here --
 * into the CALLER'S buffers, because the walk is threaded and a shared mask
 * would be another thread's opener half the time. */
static void masks_for(int og, uint8_t (*gf)[NPAT], uint8_t *fu,
                      int8_t *gvow, int8_t *mvow) {
    if (!OPENER_DEP) {
        memcpy(gf, GFIRE, (size_t)NGROUP * NPAT);
        memcpy(fu, FIRE, NPAT);
        return;
    }
    groups_vowel_counts(og, gvow, mvow);
    for (int p = 0; p < NPAT; p++) fu[p] = 0;
    for (int g = 0; g < NGROUP; g++) {
        groups_mask_for(&GRP[g], gvow, mvow, gf[g]);
        gf[g][ALL_GREEN] = 0;                   /* see never_fire_on_a_win */
        for (int p = 0; p < NPAT; p++) fu[p] |= gf[g][p];
    }
}

static double decline_total(Memo *m, int og, uint16_t *out, int depth,
                            const uint8_t *fu) {
    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int *pstart = m->start + (size_t)depth * NPAT;
    int *plen = m->len + (size_t)depth * NPAT;
    int nt = 0;
    for (int a = 0; a < NA; a++) {
        if (fu[row[a]]) continue;
        int p = row[a];
        if (cnt[p]++ == 0) touch[nt++] = p;
    }
    int acc = 0;
    for (int k = 0; k < nt; k++) {
        int p = touch[k];
        plen[k] = cnt[p];
        pstart[k] = acc;
        cnt[p] = acc;
        acc += plen[k];
    }
    for (int a = 0; a < NA; a++)
        if (!fu[row[a]]) out[cnt[row[a]]++] = (uint16_t)a;
    double tot = 0.0;
    for (int k = 0; k < nt; k++) {
        tot += plen[k];                          /* the opener itself */
        if (touch[k] != ALL_GREEN)               /* the opener won: no tail */
            tot += T(m, out + pstart[k], plen[k], depth + 1);
    }
    for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
    return tot;
}

static int matched_letters(int g1, int p1, int g2, int p2);

/* --------------------------------------------------- the third level ------ *
 * A committed THIRD word, played on the residual set of a joint bucket whose
 * matched-letter count is still low.  The accounting matches the second level's:
 * one guess charged to every answer in the set, then the random tail on whatever
 * that word leaves -- and nothing at all for the answers it wins outright.
 */
static double third_total(Memo *m, const uint16_t *s, int n, int g3,
                          uint16_t *out, int depth) {
    const uint8_t *row3 = PAT + (size_t)g3 * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int *pstart = m->start + (size_t)depth * NPAT;
    int *plen = m->len + (size_t)depth * NPAT;
    double tot = n;                                   /* the third guess itself */
    int nt = 0;
    for (int i = 0; i < n; i++) {
        int p = row3[s[i]];
        if (cnt[p]++ == 0) touch[nt++] = p;
    }
    int acc = 0;
    for (int k = 0; k < nt; k++) {
        int p = touch[k];
        plen[k] = cnt[p];
        pstart[k] = acc;
        cnt[p] = acc;
        acc += plen[k];
    }
    for (int i = 0; i < n; i++) out[cnt[row3[s[i]]]++] = s[i];
    for (int k = 0; k < nt; k++) {
        if (touch[k] == ALL_GREEN) continue;          /* g3 won: no tail */
        tot += T(m, out + pstart[k], plen[k], depth + 1);
    }
    for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
    return tot;
}

/* The JOINT buckets of one group under one second word, each with the
 * matched-letter count that selects its third word.  Answers the second word
 * WINS are dropped -- there is nothing left to play for them.  `jbuf` receives
 * the answers reordered so each bucket is contiguous. */
static int joint_split(Memo *m, int og, const uint16_t *q, const int *rstart,
                       const int *rlen, const int *rpat, int nb, int g2,
                       uint16_t *jbuf, int *jstart, int *jlen, int8_t *jm,
                       int depth) {
    const uint8_t *row2 = PAT + (size_t)g2 * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int nj = 0, fill = 0;
    for (int b = 0; b < nb; b++) {
        const uint16_t *s = q + rstart[b];
        int n = rlen[b], nt = 0;
        for (int i = 0; i < n; i++) {
            int p = row2[s[i]];
            if (cnt[p]++ == 0) touch[nt++] = p;
        }
        int acc = fill;
        for (int k = 0; k < nt; k++) {
            int p = touch[k];
            int len = cnt[p];
            cnt[p] = acc;
            acc += len;
            if (p == ALL_GREEN) continue;
            jstart[nj] = cnt[p];
            jlen[nj] = len;
            jm[nj] = (int8_t)matched_letters(og, rpat[b], g2, p);
            nj++;
        }
        for (int i = 0; i < n; i++) jbuf[cnt[row2[s[i]]]++] = s[i];
        for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
        fill = acc;
    }
    return nj;
}


/* ------------------------------------------------------------- the walk ---- */

typedef struct { double key; int64_t ssq; int32_t w; } Cand;

static int cmp_cand(const void *a, const void *b) {
    const Cand *x = a, *y = b;
    if (x->key != y->key) return x->key < y->key ? -1 : 1;
    return x->w - y->w;                       /* ties on the lowest guess index */
}

/* THE BEAM'S ORDER, and it is secondword.c's rule verbatim: ascending sum of
 * squared JOINT bucket sizes, ties on the lowest guess index.  Keeping the two
 * rankings identical is what makes `--topk` mean "the words the one-ply table
 * would have picked" rather than "some other shortlist". */
static int cmp_cand_ssq(const void *a, const void *b) {
    const Cand *x = a, *y = b;
    if (x->ssq != y->ssq) return x->ssq < y->ssq ? -1 : 1;
    return x->w - y->w;
}

/* THE MATCHED-LETTER STATE, carried down the recursion.
 *
 * At two guesses this could be a function of the two replies; from three guesses
 * on it has to accumulate, so it is a small struct updated one guess at a time.
 * `known[c]` is the most copies of letter c any reply has PROVED (its non-grey
 * tiles of that letter), `pinned` the positions some reply turned green.  The
 * matched count is then greens + yellows in tree_states' sense: every proved
 * copy, with the pinned ones counted as greens.
 *
 * It stays a function of the WORDS AND REPLIES alone, never of the answer, so it
 * is constant within a bucket -- which is what makes it a legal key at any depth.
 */
typedef struct {
    int16_t known[26];
    uint8_t pinch[WORDLEN];       /* the letter pinned at each position */
    uint8_t pinned;               /* bitmask of pinned positions */
} MState;

static void mstate_add(MState *st, int g, int p) {
    const char *w = GWORD[g];
    int cnt[26] = {0}, c = p;
    /* POSITION 0 IS THE MOST SIGNIFICANT TRIT, so this walks from the right. */
    for (int i = WORDLEN - 1; i >= 0; i--) {
        int t = c % 3;
        c /= 3;
        int ch = w[i] - 'a';
        if (t) cnt[ch]++;
        if (t == 2) { st->pinned |= (uint8_t)(1u << i); st->pinch[i] = (uint8_t)ch; }
    }
    for (int ch = 0; ch < 26; ch++)
        if (cnt[ch] > st->known[ch]) st->known[ch] = (int16_t)cnt[ch];
}

static int mstate_matched(const MState *st) {
    int pin[26] = {0}, greens = 0;
    for (int i = 0; i < WORDLEN; i++)
        if (st->pinned & (1u << i)) { greens++; pin[st->pinch[i]]++; }
    int yellows = 0;
    for (int ch = 0; ch < 26; ch++) {
        int y = st->known[ch] - pin[ch];
        if (y > 0) yellows += y;
    }
    return greens + yellows;
}

/* The two-guess case, kept because the gate's --dump-matched diffs it against
 * tree_states and because the third level's key is exactly this. */
static int matched_letters(int g1, int p1, int g2, int p2) {
    MState st;
    memset(&st, 0, sizeof st);
    mstate_add(&st, g1, p1);
    mstate_add(&st, g2, p2);
    return mstate_matched(&st);
}


/* ------------------------------------------------- the level recursion ---- *
 * A CASE is a set of buckets that will share one committed word.  It either
 * plays that word or DECLINES to the random tail -- whichever is cheaper -- and
 * after a committed word the resulting buckets are regrouped by matched-letter
 * count, each group becoming a case one level down.
 *
 * Level 2's cases are the partition's groups; from there the key is the matched
 * count, nested under the path.  Declining at every level is what makes the
 * family CONTAIN every shallower one: decline everywhere at level 2 and the
 * plain opener is back, so no result here can be worse than the strategy it
 * generalises, at the same beam.
 *
 * COST IS k PER LEVEL.  Each case tries `topk` words and each spawns up to six
 * child cases, so the search is k^(levels-1) per group before declining prunes
 * it.  Deep runs want a much smaller k than shallow ones.
 */
typedef struct { int32_t start, len; } Bkt;

typedef struct {
    int32_t word;                 /* -1 = this case declined */
    int32_t kid[MAXCASE];         /* child node per matched count, -1 = none */
} CaseNode;

/* One committed word and the path of matched counts that reaches it.  `path` is
 * 1 for the level-2 word, then path*6+m per level down, so it decodes back to
 * the case and sorts naturally by depth. */
typedef struct { uint32_t path; int32_t word; } TreeEnt;
#define MAXTREE 512

typedef struct {
    CaseNode *node;
    int n, cap;
    TreeEnt ent[MAXTREE];
    int nent;
    uint16_t *buf[NLVLBUF];       /* one answer buffer per level */
    Bkt      *bkt[NLVLBUF];
    MState   *st[NLVLBUF];
    int8_t   *mc[NLVLBUF];
    /* ONE CANDIDATE ARRAY PER LEVEL.  A single shared one is clobbered by the
     * recursion: a case ranks into it, sorts, then walks it calling expand --
     * which recurses and re-ranks the SAME array, so the parent's loop resumes
     * reading its child's list.  Same shape as the per-depth memo scratch. */
    Cand     *cand[NLVLBUF];
    /* THE LADDER'S RANKING PASS, NG x MAXCASE per level: the sum of squared
     * bucket sizes accumulated PER MATCHED COUNT, so every threshold's key is a
     * prefix sum of ONE counting pass rather than one pass per threshold. */
    int64_t  *ssqm[NLVLBUF];
} Levels;

static int node_new(Levels *L) {
    if (L->n == L->cap) {
        L->cap = L->cap ? L->cap * 2 : 1024;
        L->node = realloc(L->node, sizeof(CaseNode) * (size_t)L->cap);
    }
    CaseNode *nd = &L->node[L->n];
    nd->word = -1;
    for (int c = 0; c < MAXCASE; c++) nd->kid[c] = -1;
    return L->n++;
}

static double solve_case(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                         const MState *st, int nbk, int depth, int maxlvl,
                         int topk, uint16_t *out, int *node_out);

static void tree_walk(Levels *L, int node, uint32_t path) {
    if (node < 0 || L->nent >= MAXTREE) return;
    const CaseNode *nd = &L->node[node];
    if (nd->word < 0) return;                  /* declined: nothing below it */
    L->ent[L->nent].path = path;
    L->ent[L->nent].word = nd->word;
    L->nent++;
    for (int c = 0; c < MAXCASE; c++)
        if (nd->kid[c] >= 0) tree_walk(L, nd->kid[c], path * 6 + (uint32_t)c);
}

/* Expand one candidate word over a case's buckets: play it, drop the answers it
 * wins, regroup the rest by matched count and solve each group one level down. */
static double expand(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                     const MState *st, int nbk, int w, int depth, int maxlvl,
                     int topk, uint16_t *out, int node) {
    const uint8_t *row = PAT + (size_t)w * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    uint16_t *nbuf = L->buf[depth];
    Bkt *nb = L->bkt[depth];
    MState *nst = L->st[depth];
    int8_t *nmc = L->mc[depth];
    double tot = 0.0;
    int nn = 0, fill = 0;

    for (int b = 0; b < nbk; b++) {
        const uint16_t *s = buf + bk[b].start;
        int n = bk[b].len, nt = 0;
        tot += n;                                  /* this guess, once per answer */
        for (int i = 0; i < n; i++) {
            int p = row[s[i]];
            if (cnt[p]++ == 0) touch[nt++] = p;
        }
        int acc = fill;
        for (int k = 0; k < nt; k++) {
            int p = touch[k];
            int len = cnt[p];
            cnt[p] = acc;
            acc += len;
            if (p == ALL_GREEN) continue;          /* won outright */
            nb[nn].start = cnt[p];
            nb[nn].len = len;
            nst[nn] = st[b];
            mstate_add(&nst[nn], w, p);
            nmc[nn] = (int8_t)mstate_matched(&nst[nn]);
            nn++;
        }
        for (int i = 0; i < n; i++) nbuf[cnt[row[s[i]]]++] = s[i];
        for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
        fill = acc;
    }

    /* regroup by matched count: every bucket with the same count shares the
     * next word, which is what makes this a rule rather than a lookup table */
    for (int c = 0; c < MAXCASE; c++) {
        int cn = 0;
        for (int j = 0; j < nn; j++) if (nmc[j] == c) cn++;
        if (!cn) continue;
        Bkt *cb = malloc(sizeof(Bkt) * cn);
        MState *cs = malloc(sizeof(MState) * cn);
        int k = 0;
        for (int j = 0; j < nn; j++)
            if (nmc[j] == c) { cb[k] = nb[j]; cs[k] = nst[j]; k++; }
        int kid = -1;
        tot += solve_case(m, L, nbuf, cb, cs, cn, depth + 1, maxlvl, topk,
                          out, &kid);
        if (node >= 0) L->node[node].kid[c] = kid;
        free(cb); free(cs);
    }
    return tot;
}

static double solve_case(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                         const MState *st, int nbk, int depth, int maxlvl,
                         int topk, uint16_t *out, int *node_out) {
    int node = node_new(L);
    if (node_out) *node_out = node;

    /* DECLINING: play no committed word and let the random tail finish it. */
    double declined = 0.0;
    for (int b = 0; b < nbk; b++)
        declined += T(m, buf + bk[b].start, bk[b].len, depth + 1);
    if (depth > maxlvl) return declined;     /* depth = the guess about to be played */

    /* rank candidates by the one-ply score over this case's buckets -- the same
     * rule every other level here ranks by.  A word already played on this path
     * splits nothing (every answer in a bucket replied to it identically), so it
     * scores worst and falls out of the beam without being named. */
    Cand *cand = L->cand[depth];
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    for (int w = 0; w < NG; w++) {
        cand[w].w = w;
        cand[w].key = 0.0;
        if (!COMMITTABLE(w)) { cand[w].ssq = INT64_MAX; continue; }
        const uint8_t *row = PAT + (size_t)w * NA;
        int64_t ssq = 0;
        for (int b = 0; b < nbk; b++) {
            const uint16_t *s = buf + bk[b].start;
            int n = bk[b].len, nt = 0;
            for (int i = 0; i < n; i++) {
                int p = row[s[i]];
                if (cnt[p]++ == 0) touch[nt++] = p;
            }
            for (int k = 0; k < nt; k++) {
                int64_t v = cnt[touch[k]];
                ssq += v * v;
                cnt[touch[k]] = 0;
            }
        }
        cand[w].ssq = ssq;
    }
    qsort(cand, (size_t)NG, sizeof(Cand), cmp_cand_ssq);

    double best = declined;
    int bestnode = -1, bestw = -1;
    int lim = topk < NG ? topk : NG;
    for (int i = 0; i < lim; i++) {
        if (cand[i].ssq == INT64_MAX) break;       /* outside --words: nothing left */
        int trial = node_new(L);
        double v = expand(m, L, buf, bk, st, nbk, cand[i].w, depth, maxlvl,
                          topk, out, trial);
        if (v < best) { best = v; bestnode = trial; bestw = cand[i].w; }
    }
    if (bestw >= 0) {
        L->node[node] = L->node[bestnode];
        L->node[node].word = bestw;
    }
    return best;
}


/* ================================================================ THE LADDER =
 * ONE committed word per LEVEL, each with its own THRESHOLD on the matched
 * letters -- the strategy a human can actually follow, because the only thing it
 * asks you to read off the board is how many letters you have found.
 *
 *     guess 1   w1                              always
 *     guess L   matched < T_L ?  w_L  :  a uniformly random consistent ANSWER,
 *                                        and the ladder is OVER
 *     after it  a uniformly random consistent ANSWER
 *
 * `matched` is the CUMULATIVE count over every reply so far -- tree_states'
 * greens + yellows, the same key --third-max-matched uses, and constant within a
 * bucket, which is what makes it a legal decision variable.
 *
 * DECLINING ENDS THE LADDER (the user's call, 2026-09-22).  Once a level is over
 * its threshold every remaining guess is random, so word `k` is only ever played
 * when levels 2..k-1 all fired.  That is what makes the whole strategy nine
 * numbers -- five words and four thresholds -- rather than a tree.
 *
 * HOW IT DIFFERS FROM --max-level, which is the machinery it reuses.  There, a
 * level splits into one case PER matched count and each picks its own word; here
 * every count below the threshold shares ONE word and every count above it
 * leaves.  So this family is strictly CONTAINED in that one at the same beam --
 * a richer rule can always imitate a threshold -- and the two are different
 * strategies, not two searches for one answer.  Their numbers do not belong in
 * one table.
 *
 * THE LEVELS ARE NOT INDEPENDENT the way --by-grays' groups are: every firing
 * bucket feeds the SAME next word, so the choice at level L+1 depends on which
 * buckets level L let through.  Hence one nested search, and hence the beam.
 *
 * THRESHOLDS ARE ENUMERATED, NOT BEAMED.  A threshold is part of the objective
 * and there are at most seven of them; only the values that induce a DIFFERENT
 * firing set are tried, which deeper down is usually two or three.
 */
typedef struct {
    int32_t word[NLVLBUF];        /* the committed word at each level, -1 = none */
    int8_t  thr[NLVLBUF];         /* and the matched-letter threshold that fires it */
} Ladder;

static double solve_ladder(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                           const MState *st, const int8_t *mc, int nbk,
                           int depth, int maxlvl, int topk,
                           const int32_t *played, int nplayed,
                           const int8_t *pin, Ladder *best,
                           double *dec_out, int *scanned, int *cut);

/* Play `w` on the buckets this level's threshold FIRES on, then hand every
 * child to the next level -- POOLED, because the next level has one word for
 * all of them.  `bound_only` stops after the sizes, which is the cheap sound
 * lower bound (any strategy needs 2n-1 on a live set of n) and is what lets a
 * hopeless (word, threshold) be dropped without the deep recursion. */
static double ladder_expand(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                            const MState *st, const int8_t *mc, int nbk,
                            int w, int thr, int depth, int maxlvl, int topk,
                            const int32_t *played, int nplayed,
                            const int8_t *pin, Ladder *best, int bound_only) {
    const uint8_t *row = PAT + (size_t)w * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    uint16_t *nbuf = L->buf[depth];
    Bkt *nb = L->bkt[depth];
    MState *nst = L->st[depth];
    int8_t *nmc = L->mc[depth];
    double tot = 0.0;
    int nn = 0, fill = 0;

    for (int b = 0; b < nbk; b++) {
        if (mc[b] >= thr) continue;                /* over the threshold: gone */
        const uint16_t *s = buf + bk[b].start;
        int n = bk[b].len, nt = 0;
        tot += n;                                  /* this guess, once per answer */
        for (int i = 0; i < n; i++) {
            int p = row[s[i]];
            if (cnt[p]++ == 0) touch[nt++] = p;
        }
        int acc = fill;
        for (int k = 0; k < nt; k++) {
            int p = touch[k];
            int len = cnt[p];
            cnt[p] = acc;
            acc += len;
            if (p == ALL_GREEN) continue;          /* w was the answer: no tail */
            nb[nn].start = cnt[p];
            nb[nn].len = len;
            nst[nn] = st[b];
            mstate_add(&nst[nn], w, p);
            nmc[nn] = (int8_t)mstate_matched(&nst[nn]);
            nn++;
        }
        if (!bound_only)
            for (int i = 0; i < n; i++) nbuf[cnt[row[s[i]]]++] = s[i];
        for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
        fill = acc;
    }
    if (bound_only) {
        for (int j = 0; j < nn; j++) tot += 2.0 * nb[j].len - 1.0;
        return tot;
    }
    int32_t np[NLVLBUF];
    for (int i = 0; i < nplayed; i++) np[i] = played[i];
    np[nplayed] = (int32_t)w;
    return tot + solve_ladder(m, L, nbuf, nb, nst, nmc, nn, depth + 1, maxlvl,
                              topk, np, nplayed + 1, pin, best, NULL, NULL, NULL);
}

static double solve_ladder(Memo *m, Levels *L, const uint16_t *buf, const Bkt *bk,
                           const MState *st, const int8_t *mc, int nbk,
                           int depth, int maxlvl, int topk,
                           const int32_t *played, int nplayed,
                           const int8_t *pin, Ladder *best,
                           double *dec_out, int *scanned, int *cut) {
    for (int d = depth; d <= maxlvl; d++) { best->word[d] = -1; best->thr[d] = 0; }

    /* WHAT EACH MATCHED COUNT COSTS IF THE LADDER ENDS HERE.  Kept per count,
     * because a threshold is exactly a choice of which counts pay this. */
    double dec[MAXCASE];
    int present[MAXCASE];
    for (int c = 0; c < MAXCASE; c++) { dec[c] = 0.0; present[c] = 0; }
    for (int b = 0; b < nbk; b++) {
        int c = mc[b];
        dec[c] += T(m, buf + bk[b].start, bk[b].len, depth + 1);
        present[c] = 1;
    }
    double all_declined = 0.0;
    for (int c = 0; c < MAXCASE; c++) all_declined += dec[c];
    if (depth > maxlvl || !nbk) {
        if (dec_out) *dec_out = all_declined;
        return all_declined;
    }

    /* THE THRESHOLDS WORTH TRYING.  T and T' do the same thing whenever they
     * bracket the same PRESENT counts, so only 0 (end the ladder) and c+1 for
     * each count actually on the board are distinct.  The canonical name for a
     * firing set is the smallest T that induces it, which is what gets reported
     * -- one rule cannot then have two names. */
    int thr[MAXCASE + 1], nthr = 0;
    thr[nthr++] = 0;
    for (int c = 0; c < MAXCASE; c++) if (present[c]) thr[nthr++] = c + 1;
    if (pin && pin[depth] >= 0) { thr[0] = pin[depth]; nthr = 1; }

    /* ONE COUNTING PASS, every threshold's key.  The sum of squared bucket sizes
     * is additive over buckets, so accumulating it per matched count gives every
     * threshold's score as a prefix sum -- and the score itself is the repo's one
     * ranking rule (secondword's), every bucket counted, all-green included. */
    int64_t *sm = L->ssqm[depth];
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    for (int w = 0; w < NG; w++) {
        const uint8_t *row = PAT + (size_t)w * NA;
        int64_t s[MAXCASE] = {0};
        for (int b = 0; b < nbk; b++) {
            const uint16_t *ss = buf + bk[b].start;
            int n = bk[b].len, nt = 0;
            for (int i = 0; i < n; i++) {
                int p = row[ss[i]];
                if (cnt[p]++ == 0) touch[nt++] = p;
            }
            int64_t acc = 0;
            for (int k = 0; k < nt; k++) {
                int64_t v = cnt[touch[k]];
                acc += v * v;
                cnt[touch[k]] = 0;
            }
            s[mc[b]] += acc;
        }
        for (int c = 0; c < MAXCASE; c++) sm[(size_t)w * MAXCASE + c] = s[c];
    }

    Cand *cand = L->cand[depth];
    Ladder cur;
    /* A PINNED THRESHOLD IS THE STRATEGY, NOT AN OPTION.  Free, the level may
     * always decline (T = 0), which is what makes a deeper ladder contain a
     * shallower one.  Pinned, the threshold is given and only the WORD is being
     * chosen, so declining is not on the table -- otherwise the gate's pinned
     * runs would quietly price a shorter ladder than the one they name. */
    int pinned = pin && pin[depth] >= 0;
    double bestv = all_declined;                   /* T = 0 is always available */
    int lim = topk < NG ? topk : NG;
    for (int ti = 0; ti < nthr; ti++) {
        int t = thr[ti];
        if (t <= 0) continue;                      /* that is all_declined */
        int fires = 0;
        for (int b = 0; b < nbk; b++) if (mc[b] < t) { fires = 1; break; }
        if (!fires) continue;
        /* nothing fires => the level is a no-op whatever its word, and
         * all_declined already IS its cost, pinned or not */
        if (pinned) bestv = HUGE_VAL;
        double leaves = 0.0;
        for (int c = t; c < MAXCASE; c++) leaves += dec[c];
        for (int w = 0; w < NG; w++) {
            cand[w].w = w;
            cand[w].key = 0.0;
            /* A WORD ALREADY PLAYED ON THIS PATH SPLITS NOTHING -- every answer
             * in every live bucket replied to it identically -- so it is dropped
             * rather than left to sort last, which is also what the two-level
             * path does with the opener and is what makes the two agree. */
            int seen = !COMMITTABLE(w);
            for (int i = 0; i < nplayed; i++) if (played[i] == w) { seen = 1; break; }
            if (seen) { cand[w].ssq = INT64_MAX; continue; }
            int64_t ssq = 0;
            for (int c = 0; c < t; c++) ssq += sm[(size_t)w * MAXCASE + c];
            cand[w].ssq = ssq;
        }
        qsort(cand, (size_t)NG, sizeof(Cand), cmp_cand_ssq);
        for (int i = 0; i < lim; i++) {
            if (cand[i].ssq == INT64_MAX) break;   /* nothing left to try */
            /* THE BOUND IS SOUND FOR ANY STRATEGY, not just the random tail: a
             * live set of n needs at least 2n-1 more guesses, since only the one
             * answer equal to the word played can finish in one.  So a cut here
             * never discards a better ladder, and the BEAM stays the single
             * approximation in play. */
            double lb = leaves + ladder_expand(m, L, buf, bk, st, mc, nbk,
                                               cand[i].w, t, depth, maxlvl, topk,
                                               played, nplayed, pin, &cur, 1);
            if (!(lb < bestv)) { if (cut) (*cut)++; continue; }
            double v = leaves + ladder_expand(m, L, buf, bk, st, mc, nbk,
                                              cand[i].w, t, depth, maxlvl, topk,
                                              played, nplayed, pin, &cur, 0);
            if (scanned) (*scanned)++;
            if (v < bestv) {
                bestv = v;
                *best = cur;
                best->word[depth] = cand[i].w;
                best->thr[depth] = (int8_t)t;
                if (dec_out) *dec_out = leaves;
            }
        }
    }
    if (bestv == HUGE_VAL) {                       /* pinned, but no word left */
        bestv = all_declined;
        best->word[depth] = -1;
        best->thr[depth] = 0;
    }
    if (best->word[depth] < 0 && dec_out) *dec_out = all_declined;
    return bestv;
}


/* A CHEAP SOUND BOUND ON A LADDER OPENER, with no word loop and no recursion:
 * every answer pays for the opener, and every bucket the opener leaves pays at
 * least 2n-1 however the ladder continues.  This replaces `opener_bound`'s
 * minimisation over all 12972 second words, which costs a minute over the full
 * list and buys little once the root is beamed to K openers anyway. */
static double ladder_bound(Memo *m, int og) {
    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt, *touch = m->touch;
    int nt = 0;
    for (int a = 0; a < NA; a++)
        if (cnt[row[a]]++ == 0) touch[nt++] = row[a];
    double tot = 0.0;
    for (int k = 0; k < nt; k++) {
        int n = cnt[touch[k]];
        tot += n;                                   /* the opener itself */
        if (touch[k] != ALL_GREEN) tot += 2.0 * n - 1.0;
        cnt[touch[k]] = 0;
    }
    return tot;
}

/* ONE OPENER'S LADDER.  Lay the answers out by the opener's reply, give each
 * bucket the matched-letter state that reply proves, and hand the lot to level
 * 2 as a SINGLE case -- there are no groups here, because the level-2 threshold
 * IS the firing condition and it is what the search is choosing. */
static void solve_ladder_opener(Memo *m, Levels *L, int og, Row *r,
                                int topk, int maxlvl, const int8_t *pin) {
    memo_clear(m);
    r->opener = og;
    r->done = 1;
    for (int d = 0; d < NLVLBUF; d++) { r->lword[d] = -1; r->lthr[d] = 0; }

    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt, *touch = m->touch;
    uint16_t *buf = L->buf[1];
    Bkt *bk = L->bkt[1];
    MState *st = L->st[1];
    int8_t *mc = L->mc[1];
    int nt = 0;
    for (int a = 0; a < NA; a++)
        if (cnt[row[a]]++ == 0) touch[nt++] = row[a];
    int acc = 0, nbk = 0;
    for (int k = 0; k < nt; k++) {
        int p = touch[k], len = cnt[p];
        cnt[p] = acc;
        acc += len;
        if (p == ALL_GREEN) continue;              /* the opener won: no ladder */
        bk[nbk].start = cnt[p];
        bk[nbk].len = len;
        memset(&st[nbk], 0, sizeof st[nbk]);
        mstate_add(&st[nbk], og, p);
        mc[nbk] = (int8_t)mstate_matched(&st[nbk]);
        nbk++;
    }
    for (int a = 0; a < NA; a++) buf[cnt[row[a]]++] = (uint16_t)a;
    for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;

    Ladder best;
    for (int d = 0; d < NLVLBUF; d++) { best.word[d] = -1; best.thr[d] = 0; }
    double leaves = 0.0;
    int scanned = 0, cutn = 0;
    int32_t played[NLVLBUF];
    played[0] = og;
    double below = solve_ladder(m, L, buf, bk, st, mc, nbk, 2, maxlvl, topk,
                                played, 1, pin, &best, &leaves, &scanned, &cutn);
    for (int d = 0; d < NLVLBUF; d++) { r->lword[d] = best.word[d]; r->lthr[d] = best.thr[d]; }
    /* THE SPLIT THE REPORT SHOWS is the two-level one: `decline` is what the
     * answers that leave at level 2 cost, opener included, and `fired` is
     * everything else.  Answers leaving at level 3 or below are inside `fired`,
     * which is the only reading that keeps the column meaning what it means in
     * every other secondexact row. */
    int nleave = 0;
    for (int b = 0; b < nbk; b++) if (mc[b] >= best.thr[2]) nleave += bk[b].len;
    r->decline = nleave + leaves;
    r->fired[0] = (NA - nleave) + (below - leaves);
    r->nq[0] = NA - nleave;
    r->second[0] = best.word[2];
    r->scanned[0] = scanned;
    r->cut[0] = cutn;
    r->ntree[0] = 0;
    for (int c = 0; c < MAXCASE; c++) r->third[0][c] = -1;
}


/* Choose ONE case's third word: rank every candidate by the one-ply score over
 * that case's buckets -- the same sum-of-squares rule the second level ranks by,
 * summed across the buckets the case collects -- then evaluate the best `topk`
 * exactly and keep the cheapest.  `idx` lists which joint buckets belong to the
 * case; the cost returned is the total over all of them.
 *
 * The opener and the second word are excluded as candidates: within a joint
 * bucket every answer replied identically to both, so replaying either splits
 * nothing and simply burns a guess. */
static double choose_third(Memo *m, const uint16_t *jbuf, const int *jstart,
                           const int *jlen, const int *idx, int nidx,
                           int og, int g2, int topk, Cand *cand,
                           uint16_t *out, int depth, int *best,
                           int allow_decline) {
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    for (int w = 0; w < NG; w++) {
        cand[w].w = w;
        if (w == og || w == g2 || !COMMITTABLE(w)) { cand[w].ssq = INT64_MAX; continue; }
        const uint8_t *row3 = PAT + (size_t)w * NA;
        int64_t ssq = 0;
        for (int j = 0; j < nidx; j++) {
            const uint16_t *sb = jbuf + jstart[idx[j]];
            int n = jlen[idx[j]], nt = 0;
            for (int i = 0; i < n; i++) {
                int p = row3[sb[i]];
                if (cnt[p]++ == 0) touch[nt++] = p;
            }
            for (int k = 0; k < nt; k++) {
                int64_t v = cnt[touch[k]];
                ssq += v * v;
                cnt[touch[k]] = 0;
            }
        }
        cand[w].ssq = ssq;
    }
    qsort(cand, (size_t)NG, sizeof(Cand), cmp_cand_ssq);
    int lim = topk < NG ? topk : NG;
    double bestv = HUGE_VAL;
    *best = -1;
    for (int i = 0; i < lim; i++) {
        if (cand[i].ssq == INT64_MAX) break;
        double v = 0.0;
        for (int j = 0; j < nidx; j++)
            v += third_total(m, jbuf + jstart[idx[j]], jlen[idx[j]],
                             cand[i].w, out, depth + 1);
        if (v < bestv) { bestv = v; *best = cand[i].w; }
    }
    /* DECLINING is playing no committed word at all and letting the random tail
     * take the case.  Offering it makes the three-level family CONTAIN the
     * two-level one -- decline everywhere and you have it back -- so the result
     * can never be worse, which is exactly what a forced word cannot promise.
     * It is opt-in because it is a different strategy, not a better search. */
    if (allow_decline) {
        double declined = 0.0;
        for (int j = 0; j < nidx; j++)
            declined += T(m, jbuf + jstart[idx[j]], jlen[idx[j]], depth + 1);
        if (!(bestv < declined)) { bestv = declined; *best = -1; }
    }
    return bestv;
}


/* A CHEAP LOWER BOUND on an opener's total, with no recursion at all: the decline
 * branch bounded by T(S) >= 2|S| - 1 per bucket, plus the cheapest possible
 * second-word part over every candidate word.
 *
 * THIS IS WHAT MAKES THE RUN AFFORDABLE, and skipping it was a real mistake:
 * walked in list order, the first openers are `aahed`, `aalii` and the rest of
 * the alphabet -- all terrible, and each one scans thousands of second words
 * before any incumbent exists to cut them.  MEASURED: `aahed` alone takes 80
 * seconds that way, against `spilt`'s 0.6.  Bounded first and walked ASCENDING,
 * a good incumbent exists before the bad openers are ever reached, and most of
 * them are then cut without a single exact evaluation.  The visit order is a
 * computation, not a detail.
 */
static double opener_bound(Memo *m, int og, uint16_t *q, uint16_t *out,
                           int *rstart, int *rlen, int *rpat, int *nbp, int *nqp,
                           double *gbound, const uint8_t (*gf)[NPAT],
                           const uint8_t *fu) {
    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt, *touch = m->touch;
    double tot = 0.0;

    /* the DECLINE branch, bounded */
    int nt = 0;
    for (int a = 0; a < NA; a++) {
        if (fu[row[a]]) continue;
        if (cnt[row[a]]++ == 0) touch[nt++] = row[a];
    }
    for (int k = 0; k < nt; k++) {
        int n = cnt[touch[k]];
        tot += n;                                  /* the opener itself */
        if (touch[k] != ALL_GREEN) tot += 2.0 * n - 1.0;
        cnt[touch[k]] = 0;
    }

    /* each GROUP separately: its answers, grouped by the opener's reply, then
     * the cheapest possible second word for it.  The groups are independent, so
     * their bounds simply add. */
    for (int g = 0; g < NGROUP; g++) {
        const uint8_t *fire = gf[g];
        int nb = 0, nq = 0;
        for (int a = 0; a < NA; a++) {
            if (!fire[row[a]]) continue;
            nq++;
            if (cnt[row[a]]++ == 0) touch[nb++] = row[a];
        }
        int acc = 0;
        for (int k = 0; k < nb; k++) {
            int p = touch[k];
            rlen[g * NPAT + k] = cnt[p];
            rstart[g * NPAT + k] = acc;
            rpat[g * NPAT + k] = p;      /* the OPENER's reply for this bucket */
            cnt[p] = acc;
            acc += rlen[g * NPAT + k];
        }
        for (int a = 0; a < NA; a++)
            if (fire[row[a]]) q[g * NA + cnt[row[a]]++] = (uint16_t)a;
        for (int k = 0; k < nb; k++) cnt[touch[k]] = 0;
        nbp[g] = nb;
        nqp[g] = nq;
        if (!nq) { gbound[g] = 0.0; continue; }
        double best = HUGE_VAL;
        for (int w = 0; w < NG; w++) {
            /* THE BOUND MINIMISES OVER THE CANDIDATES THAT EXIST.  Restricting
             * the pool can only RAISE this minimum, which keeps it a sound lower
             * bound and makes it a tighter one; leaving it unrestricted would
             * merely be slack. */
            if (w == og || !COMMITTABLE(w)) continue;
            double v = fired_total(m, q + g * NA, nq, rstart + g * NPAT,
                                   rlen + g * NPAT, nb, w, 1, out, 1, NULL);
            if (v < best) best = v;
        }
        if (best == HUGE_VAL) best = 0.0;          /* the pool offers nothing */
        gbound[g] = best;
        tot += best;
    }
    return tot;
}

/* THE POOL'S NAME, appended to the label so it reaches the filename and the
 * settings stamp.  It is a basename, so it can be computed before anything is
 * loaded -- which is what --print-label needs. */
static void append_pool(char *lab, size_t n, const char *poolname) {
    if (!poolname || !*poolname) return;
    size_t k = strlen(lab);
    if (k + 3 < n) snprintf(lab + k, n - k, "_w%s", poolname);
}

/* Evaluate ONE opener exactly: the best second word, and the strategy's total.
 * `incumbent` is the best total seen so far, in guesses over all 2315 answers;
 * a second word whose BOUND is not below it cannot win and is skipped.  Pass
 * HUGE_VAL to evaluate every word. */
/* One group's exact cost under one second word, WITH a committed third word on
 * every joint bucket whose matched-letter count is at most `third_max`.
 *
 * `forced` is the SHARED key: the three words are given from outside and this
 * only prices them.  `chosen` is the PER-GROUP key: each case picks its own word
 * here, which is sound because this group's joint buckets are disjoint from
 * every other group's, so the sum still decomposes exactly.
 */
static double fired_with_third(Memo *m, int og, const uint16_t *q, int nq,
                               const int *rstart, const int *rlen, const int *rpat,
                               int nb, int g2, int third_max, int topk,
                               Cand *cand, uint16_t *jbuf, int *jstart, int *jlen,
                               int8_t *jm, int *idx, uint16_t *out,
                               const int *forced, int *chosen, int allow_decline) {
    int nj = joint_split(m, og, q, rstart, rlen, rpat, nb, g2,
                         jbuf, jstart, jlen, jm, 1);
    /* EVERY case, not just the ones that can fire: the caller copies the whole
     * array into the row, so a case above `third_max` left unwritten is stack
     * garbage read back as a word index. */
    if (chosen) for (int c = 0; c < MAXCASE; c++) chosen[c] = -1;
    double tot = 2.0 * nq;                      /* the opener and the second word */
    for (int j = 0; j < nj; j++)
        if (jm[j] > third_max)                  /* too much known: random tail */
            tot += T(m, jbuf + jstart[j], jlen[j], 2);
    for (int mm = 0; mm <= third_max; mm++) {
        int nidx = 0;
        for (int j = 0; j < nj; j++) if (jm[j] == mm) idx[nidx++] = j;
        if (!nidx) continue;                    /* no answer reaches this case */
        if (forced) {
            if (forced[mm] < 0) {               /* no word for it: random tail */
                for (int j = 0; j < nidx; j++)
                    tot += T(m, jbuf + jstart[idx[j]], jlen[idx[j]], 2);
                continue;
            }
            for (int j = 0; j < nidx; j++)
                tot += third_total(m, jbuf + jstart[idx[j]], jlen[idx[j]],
                                   forced[mm], out, 2);
        } else {
            int best = -1;
            tot += choose_third(m, jbuf, jstart, jlen, idx, nidx, og, g2, topk,
                                cand, out, 1, &best, allow_decline);
            if (chosen) chosen[mm] = best;
        }
    }
    return tot;
}


/* THE WHOLE STRATEGY ON ONE LINE -- every committed word, not just the second
 * ones.  Both the progress line and the final report go through this so the two
 * cannot drift: a nine-word strategy was printing as four words on screen while
 * the CSV held all of it, and the printout is what a watched run is FOR.
 *
 * Unlabelled: `shone +chump +chimp | sonce +chimp | sonce`, groups separated by
 * `|` in the same order the report uses (least informative first), each group's
 * third words following it as `+word`.  Labelled adds each word's case.
 */
static int LADDER_LEVELS = 0;    /* --ladder N, 0 when the mode is off */

static void format_strategy(char *buf, size_t n, const Row *v, int labelled) {
    size_t k = 0;
    if (LADDER_LEVELS) {
        /* `clint<3 dough<2 frizz<2` -- the word and the matched-letter threshold
         * that fires it, one per level.  The threshold is never dropped: two
         * ladders over the same five words are two different strategies. */
        for (int d = 2; d <= LADDER_LEVELS; d++) {
            int r;
            if (v->lword[d] < 0) {
                r = labelled ? snprintf(buf + k, n - k, " -- (L%d: never fires)", d)
                             : snprintf(buf + k, n - k, " -");
            } else if (labelled) {
                r = snprintf(buf + k, n - k, " %s (L%d, matched<%d)",
                             GWORD[v->lword[d]], d, v->lthr[d]);
            } else {
                r = snprintf(buf + k, n - k, " %s<%d", GWORD[v->lword[d]], v->lthr[d]);
            }
            if (r < 0 || (size_t)r >= n - k) break;
            k += (size_t)r;
            if (v->lword[d] < 0) break;         /* declining ENDS the ladder */
        }
        buf[k < n ? k : n - 1] = 0;
        return;
    }
    for (int g = NGROUP - 1; g >= 0; g--) {
        const char *w = v->second[g] >= 0 ? GWORD[v->second[g]] : "-";
        int r = labelled
              ? snprintf(buf + k, n - k, " %s (%s)", w, GSPEC[g])
              : snprintf(buf + k, n - k, "%s %s", g == NGROUP - 1 ? "" : " |", w);
        if (r < 0 || (size_t)r >= n - k) break;
        k += (size_t)r;
        /* --max-level's tree, or the fixed third level -- whichever produced
         * this row.  Both are committed words below the second one, so both
         * belong on the line a watched run prints. */
        for (int i = 1; i < v->ntree[g]; i++) {
            const char *t = GWORD[v->tword[g][i]];
            uint32_t pth = v->tpath[g][i], digits[8];
            int nd = 0;
            while (pth > 1 && nd < 8) { digits[nd++] = pth % 6; pth /= 6; }
            if (labelled) {
                r = snprintf(buf + k, n - k, " %s (%s", t, GSPEC[g]);
                if (r < 0 || (size_t)r >= n - k) break;
                k += (size_t)r;
                for (int d = nd - 1; d >= 0; d--) {
                    r = snprintf(buf + k, n - k, "|m%u", digits[d]);
                    if (r < 0 || (size_t)r >= n - k) break;
                    k += (size_t)r;
                }
                r = snprintf(buf + k, n - k, ")");
            } else {
                r = snprintf(buf + k, n - k, " +%s", t);
            }
            if (r < 0 || (size_t)r >= n - k) break;
            k += (size_t)r;
        }
        for (int c = 0; c < MAXCASE; c++) {
            if (v->third[g][c] < 0) continue;      /* declined, or never fired */
            const char *t = GWORD[v->third[g][c]];
            r = labelled ? snprintf(buf + k, n - k, " %s (%s|m%d)", t, GSPEC[g], c)
                         : snprintf(buf + k, n - k, " +%s", t);
            if (r < 0 || (size_t)r >= n - k) break;
            k += (size_t)r;
        }
    }
    buf[k < n ? k : n - 1] = 0;
}


static void solve_opener(Memo *m, int og, Row *r, double incumbent, int no_prune,
                         uint16_t *q, uint16_t *out, int *rstart, int *rlen,
                         int *rpat, int *nbs, int *nqs, const double *gbound,
                         const uint8_t *fu, int topk, int third_max,
                         const int *shared_third, int third_decline,
                         int maxlvl, Levels *L) {
    memo_clear(m);
    r->opener = og;
    r->decline = decline_total(m, og, out, 0, fu);
    r->done = 1;

    Cand *cand = malloc(sizeof(Cand) * NG);
    /* the third level's scratch, allocated only when it is switched on */
    Cand *cand3 = NULL; uint16_t *jbuf = NULL;
    int *jstart = NULL, *jlen = NULL, *idx3 = NULL; int8_t *jm = NULL;
    if (third_max >= 0) {
        cand3 = malloc(sizeof(Cand) * NG);
        jbuf = malloc(sizeof(uint16_t) * NA);
        jstart = malloc(sizeof(int) * NA);
        jlen = malloc(sizeof(int) * NA);
        idx3 = malloc(sizeof(int) * NA);
        jm = malloc(NA);
    }
    for (int g = 0; g < NGROUP; g++) {
        r->second[g] = -1;
        r->fired[g] = 0.0;
        r->scanned[g] = r->cut[g] = 0;
        r->nq[g] = nqs[g];
        r->ntree[g] = 0;
        for (int c = 0; c < MAXCASE; c++) r->third[g][c] = -1;
        int nq = nqs[g], nb = nbs[g];
        if (!nq) continue;
        const uint16_t *qq = q + g * NA;
        const int *rs = rstart + g * NPAT, *rl = rlen + g * NPAT;
        const int *rp = rpat + g * NPAT;

        for (int w = 0; w < NG; w++) {
            cand[w].w = w;
            cand[w].ssq = INT64_MAX;                  /* the opener itself sorts last */
            if (w == og || !COMMITTABLE(w)) { cand[w].key = HUGE_VAL; continue; }
            cand[w].ssq = 0;
            cand[w].key = fired_total(m, qq, nq, rs, rl, nb, w, 1, out, 1,
                                      topk ? &cand[w].ssq : NULL);
        }
        qsort(cand, (size_t)NG, sizeof(Cand), topk ? cmp_cand_ssq : cmp_cand);

        /* THE BEAM.  Evaluate exactly the `topk` best by the one-ply score and
         * nothing else, so the result is the best of those k -- an UPPER BOUND
         * on this group's true optimum, never the optimum.
         *
         * The within-group incumbent cut is deliberately NOT applied here.  That
         * cut leans on the other groups' costs, and once a group's value is
         * itself only an upper bound the reasoning stops being sound -- so the
         * beam stays the ONE approximation in play and the claim stays exactly
         * "the best of the k examined".  The OPENER-level cut is untouched and
         * still sound: the incumbent is the value of a strategy that exists. */
        /* --max-level: ONE recursion per group, declining at every level
         * including this one.  The opener is charged here, once per qualifying
         * answer; solve_case charges everything from the second guess down. */
        if (maxlvl) {
            Bkt *gb = malloc(sizeof(Bkt) * nb);
            MState *gs = malloc(sizeof(MState) * nb);
            for (int b = 0; b < nb; b++) {
                gb[b].start = rs[b];
                gb[b].len = rl[b];
                memset(&gs[b], 0, sizeof gs[b]);
                mstate_add(&gs[b], og, rp[b]);
            }
            L->n = 0;
            int node = -1;
            double v = solve_case(m, L, qq, gb, gs, nb, 2, maxlvl, topk,
                                  out, &node);
            L->nent = 0;
            tree_walk(L, node, 1);
            r->ntree[g] = L->nent < 24 ? L->nent : 24;
            for (int i = 0; i < r->ntree[g]; i++) {
                r->tpath[g][i] = L->ent[i].path;
                r->tword[g][i] = L->ent[i].word;
            }
            if (L->nent) r->second[g] = L->ent[0].word;   /* path 1 = level 2 */
            r->scanned[g] = topk;
            r->fired[g] = nq + v;
            free(gb); free(gs);
            continue;
        }
        if (topk) {
            int lim = topk < NG ? topk : NG;
            double bestk = HUGE_VAL;
            int chosen[MAXCASE];
            for (int i = 0; i < lim; i++) {
                if (cand[i].ssq == INT64_MAX) break;      /* nothing left to try */
                double v;
                if (third_max < 0) {
                    v = fired_total(m, qq, nq, rs, rl, nb, cand[i].w, 0,
                                    out, 1, NULL);
                } else {
                    v = fired_with_third(m, og, qq, nq, rs, rl, rp, nb,
                                         cand[i].w, third_max, topk, cand3,
                                         jbuf, jstart, jlen, jm, idx3, out,
                                         shared_third, chosen, third_decline);
                }
                r->scanned[g]++;
                if (v < bestk) {
                    bestk = v;
                    r->second[g] = cand[i].w;
                    if (third_max >= 0 && !shared_third)
                        for (int c = 0; c < MAXCASE; c++) r->third[g][c] = chosen[c];
                }
            }
            /* NG - 1: the opener is never a candidate, so a beam at least as
             * wide as the pool must report 0 cut, exactly as the full scan does */
            r->cut[g] = NG - 1 - r->scanned[g];
            r->fired[g] = bestk;
            continue;
        }

        /* TWO CUTS, and the second is what makes this affordable.  The groups
         * are independent, so a word whose bound is not below the best found
         * HERE cannot be this group's word -- that is the single-word cut,
         * applied k times.  But it is weak when a group's words are all close:
         * measured on `spilt`, the e5 group scanned every one of the 12971.
         *
         * The INCUMBENT cuts far harder, and it is still sound: whatever this
         * group ends up costing, the others cost at least their own bounds (or
         * exactly their best, once solved), so
         *     decline + this word's bound + the others' floor
         * is a lower bound on the WHOLE strategy with this word in this group.
         * If that is not below the incumbent, this word cannot be part of a
         * winning opener at all. */
        double floor_other = 0.0;
        for (int h = 0; h < NGROUP; h++)
            if (h != g) floor_other += (h < g) ? r->fired[h] : gbound[h];
        double best = HUGE_VAL;
        for (int i = 0; i < NG; i++) {
            if (cand[i].key == HUGE_VAL) break;
            if (!no_prune && !(cand[i].key < best)
                    && !(r->decline + floor_other + cand[i].key < incumbent)) {
                r->cut[g] = NG - i;
                break;
            }
            double v = fired_total(m, qq, nq, rs, rl, nb, cand[i].w, 0, out, 1, NULL);
            r->scanned[g]++;
            if (v < best) { best = v; r->second[g] = cand[i].w; }
        }
        r->fired[g] = best;
    }
    free(cand);
    free(cand3); free(jbuf); free(jstart); free(jlen); free(idx3); free(jm);
    (void)incumbent;
}

/* ------------------------------------------------ matched letters --------- *
 * THE THIRD LEVEL'S KEY (user's definition, 2026-09-16): how many letters we
 * know are in the answer after two guesses -- distinct letters, but counted
 * AGAIN for every copy a reply proves, so a letter non-grey twice in one guess
 * counts twice and a letter pinned green in two places counts twice.
 *
 * That is exactly `tree_states`' greens + yellows: per letter, the most copies
 * either reply proves (`max over guesses of min(count in guess, count in
 * answer)`, which a reply reports as its non-grey tiles of that letter), summed,
 * with the pinned ones counted as greens.  `tree_states.state_from_strings` is
 * the independent implementation the gate diffs against.
 *
 * IT IS A FUNCTION OF THE TWO REPLIES ALONE, never of the answer beyond them --
 * which is what makes it a legal key: it is CONSTANT within a joint (p1, p2)
 * bucket, so every answer in a bucket gets the same third word.
 */
/* --------------------------------------------------- the root beam -------- *
 * `--topk K` RESTRICTS THE OPENERS TOO -- the root is a branching point like any
 * other, and one K governs both, as in every other solver here (strturns,
 * greens, mmturns, wturns, ultraturns, nerdle).  The rank is the repo's one
 * ranking rule applied to the opener's own partition of the answers: ascending
 * sum of squared bin sizes, ties on the lowest guess index.  It is ONE pass over
 * the answers per opener, so the K best are known long before anything is
 * bounded -- which is the point, since bounding all 12972 is the expensive part.
 */
typedef struct { int64_t ssq; int32_t w; } RootKey;

static int cmp_rootkey(const void *a, const void *b) {
    const RootKey *x = a, *y = b;
    if (x->ssq != y->ssq) return x->ssq < y->ssq ? -1 : 1;
    return x->w - y->w;
}

static int64_t root_ssq(int g, int *cnt) {
    const uint8_t *row = PAT + (size_t)g * NA;
    int touch[NPAT], nt = 0;
    for (int a = 0; a < NA; a++)
        if (cnt[row[a]]++ == 0) touch[nt++] = row[a];
    int64_t ssq = 0;
    for (int k = 0; k < nt; k++) {
        int64_t v = cnt[touch[k]];
        ssq += v * v;
        cnt[touch[k]] = 0;
    }
    return ssq;
}


/* ------------------------------------------------------- resume ---------- *
 * A run is hours long and there is no checkpoint but the CSV itself, so the CSV
 * IS the checkpoint: every opener's rows are appended the moment it finishes.
 * A resume reads them back, skips those openers and -- the part that actually
 * saves time -- SEEDS THE INCUMBENT with the best total already proved, so the
 * bound starts cutting from the first opener instead of after the first dozen.
 *
 * A previously CUT opener is deliberately NOT recorded.  It costs nothing to cut
 * again, and it is still sound to do so: it was cut against an incumbent that is
 * necessarily no better than the one a resume starts with, so `bound >= old`
 * gives `bound >= new`.
 *
 * Returns the number of openers recognised, or -1 if the file is for a DIFFERENT
 * condition -- refused rather than continued, because the rows would be answers
 * to another question wearing this one's filename. */
static int read_resume(const char *path, Row *rows, int nopen, const char *label,
                       int topk, double *incumbent, int *best_i) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[1024];
    int stamped = 0, found = 0;
    /* opener name -> row index, by linear scan; 13k openers x a few thousand
     * resumed rows is nothing beside one exact evaluation. */
    while (fgets(line, sizeof line, f)) {
        if (line[0] == '#') {
            char *fire = strstr(line, "fire=");
            if (fire) {
                stamped = 1;
                /* the WHOLE stamp, topk included: a beam file and an exact one
                 * are different quantities, and a k=10 file read into a k=50 run
                 * would silently mix two of them under one name. */
                char want[512];
                snprintf(want, sizeof want, "fire=%s openers=%d ", label, nopen);
                int ok = !strncmp(fire, want, strlen(want));
                int filek = -1;
                char *tk = strstr(line, "topk=");
                if (tk) filek = atoi(tk + 5);
                if (!ok || filek != topk) {
                    fprintf(stderr, "%s was written for a DIFFERENT run:\n  %s",
                            path, line);
                    fprintf(stderr, "  this run is firing on %s with topk=%d\n",
                            label, topk);
                    fclose(f);
                    return -1;
                }
            }
            continue;
        }
        if (!strncmp(line, "opener,", 7)) continue;
        char ow[32], fires[128], sec[32];
        double expected, total, decline, fired;
        int nq, scanned, cutn;
        int n = sscanf(line, "%31[^,],%127[^,],%31[^,],%lf,%lf,%lf,%lf,%d,%d,%d",
                       ow, fires, sec, &expected, &total, &decline, &fired,
                       &nq, &scanned, &cutn);
        int oi = -1;
        for (int i = 0; i < nopen; i++)
            if (!strcmp(GWORD[rows[i].opener], ow)) { oi = i; break; }
        if (oi < 0) continue;
        /* A LADDER LEVEL ROW carries a word this run will otherwise never
         * recompute, so it is read back for EVERY opener rather than only the
         * leader: a resumed run that could not name its own words would report a
         * total with no strategy attached. */
        if (LADDER_LEVELS && fires[0] == 'L' && strchr(fires, '|')) {
            int d = atoi(fires + 1), t = atoi(strchr(fires, '|') + 2);
            if (d >= 2 && d <= LADDER_LEVELS && n >= 3) {
                rows[oi].lthr[d] = (int8_t)t;
                rows[oi].lword[d] = -1;
                for (int k = 0; k < NG; k++)
                    if (!strcmp(GWORD[k], sec)) { rows[oi].lword[d] = k; break; }
            }
            continue;
        }
        if (!rows[oi].resumed) { rows[oi].resumed = 1; found++; }
        if (n < 7) continue;                       /* a `none` row: no numbers */
        /* the best total on file becomes the starting incumbent */
        if (total < *incumbent) { *incumbent = total; *best_i = oi; }
        /* and the leader's own words, so the final report can name them */
        if (*best_i == oi) {
            for (int g = 0; g < NGROUP; g++)
                if (!strcmp(GSPEC[g], fires)) {
                    for (int k = 0; k < NG; k++)
                        if (!strcmp(GWORD[k], sec)) { rows[oi].second[g] = k; break; }
                    rows[oi].fired[g] = fired;
                    rows[oi].nq[g] = nq;
                    rows[oi].scanned[g] = scanned;
                    rows[oi].cut[g] = cutn;
                    rows[oi].decline = decline;
                    rows[oi].done = 1;
                    break;
                }
        }
    }
    fclose(f);
    if (!stamped && found) {
        fprintf(stderr, "%s has no `# settings fire=` stamp, so it cannot say "
                "which condition it holds -- refusing to resume from it\n", path);
        return -1;
    }
    return found;
}


/* One opener's rows, appended the moment it is known.  The SAME format the
 * end-of-run write uses -- one writer, so a resumed file and a fresh one cannot
 * drift apart. */
static void write_rows(FILE *f, Row *v) {
    if (LADDER_LEVELS) {
        /* ONE SUMMARY ROW plus one row per LEVEL, `L<d>|t<T>` in the `fires`
         * column -- the level and the threshold that fires its word, which
         * together ARE the rule.  A declined level is written too, as `-`, so
         * the file records where the ladder stopped rather than leaving a reader
         * to infer it from a missing row. */
        double tot = v->decline + v->fired[0];
        if (!v->done) {
            fprintf(f, "%s,ladder,,,,,,%d,0,cut\n", GWORD[v->opener], NA);
            fflush(f);
            return;
        }
        /* `-` RATHER THAN AN EMPTY FIELD for a level that never fires: the
         * resume reader's scanf stops at the first empty column, so an empty
         * `second` would make the summary row unparseable and the run would
         * resume without its own incumbent. */
        fprintf(f, "%s,ladder,%s,%.6f,%.4f,%.4f,%.4f,%d,%d,%d\n",
                GWORD[v->opener], v->lword[2] >= 0 ? GWORD[v->lword[2]] : "-",
                tot / NA, tot, v->decline, v->fired[0],
                v->nq[0], v->scanned[0], v->cut[0]);
        for (int d = 2; d <= LADDER_LEVELS; d++) {
            fprintf(f, "%s,L%d|t%d,%s,%.6f,%.4f,,,,,level%d\n",
                    GWORD[v->opener], d, v->lthr[d],
                    v->lword[d] >= 0 ? GWORD[v->lword[d]] : "-", tot / NA, tot, d);
            if (v->lword[d] < 0) break;         /* declining ENDS the ladder */
        }
        fflush(f);
        return;
    }
    double tot = v->decline;
    int any = 0;
    for (int g = 0; g < NGROUP; g++) {
        tot += v->fired[g];
        any |= v->second[g] >= 0;
    }
    for (int g = NGROUP - 1; g >= 0; g--) {
        if (!v->done) {
            fprintf(f, "%s,%s,,,,,,%d,0,cut\n", GWORD[v->opener], GSPEC[g], v->nq[g]);
            continue;
        }
        if (v->second[g] < 0) {
            /* No word for this group -- nothing qualified, or it DECLINED.  The
             * strategy still has a value, so the total is written here too: an
             * opener that declines everywhere is the plain opener, not a blank. */
            fprintf(f, "%s,%s,,%.6f,%.4f,%.4f,%.4f,%d,%d,none\n",
                    GWORD[v->opener], GSPEC[g], tot / NA, tot, v->decline,
                    v->fired[g], v->nq[g], v->scanned[g]);
            continue;
        }
        fprintf(f, "%s,%s,%s,%.6f,%.4f,%.4f,%.4f,%d,%d,%d\n",
                GWORD[v->opener], GSPEC[g], GWORD[v->second[g]],
                any ? tot / NA : 0.0, any ? tot : 0.0, v->decline,
                v->fired[g], v->nq[g], v->scanned[g], v->cut[g]);
        /* --max-level's TREE: one row per committed word below the second, named
         * `<group>|m<a>|m<b>...` -- the path of matched counts that reaches it.
         * `path` is 1 for the level-2 word and path*6+m per level down, so the
         * digits after the leading 1 decode straight back to the case. */
        for (int i = 1; i < v->ntree[g]; i++) {
            char lab[64];
            int k = snprintf(lab, sizeof lab, "%s", GSPEC[g]);
            uint32_t pth = v->tpath[g][i];
            uint32_t digits[8];
            int nd = 0;
            while (pth > 1 && nd < 8) { digits[nd++] = pth % 6; pth /= 6; }
            for (int d = nd - 1; d >= 0; d--)
                k += snprintf(lab + k, sizeof lab - k, "|m%u", digits[d]);
            fprintf(f, "%s,%s,%s,%.6f,%.4f,,,,,level%d\n",
                    GWORD[v->opener], lab, GWORD[v->tword[g][i]],
                    any ? tot / NA : 0.0, any ? tot : 0.0, nd + 2);
        }
        /* THE THIRD LEVEL's own rows, named `<group>|m<matched>` so a reader can
         * tell them from a group's row by the separator and recover both keys.
         * The strategy's expected/total repeat here as they do on every row. */
        for (int c = 0; c < MAXCASE; c++) {
            if (v->third[g][c] < 0) continue;
            fprintf(f, "%s,%s|m%d,%s,%.6f,%.4f,,,,,third\n",
                    GWORD[v->opener], GSPEC[g], c, GWORD[v->third[g][c]],
                    any ? tot / NA : 0.0, any ? tot : 0.0);
        }
    }
    fflush(f);
}


int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL, *patpath = NULL;
    const char *matchpath = NULL;              /* --dump-matched, the gate hook */
    const char *one = NULL, *openpath = NULL, *poolpath = NULL;
    int min_grays = 3, by_grays = -1, threads = 0, limit = 0, no_prune = 0,
        memo_bits = 19, split_v = 0, split_mv = 0, split_nz = 0, print_label = 0, topk = 0;
    int third_max = -1;                        /* -1: no third level at all */
    int maxlvl = 0;                            /* 0: the fixed 2/3-level paths */
    int third_decline = 0;
    int ladder = 0;                            /* --ladder N, 0 = mode off */
    int min_grays_set = 0, ngroupspec = 0;     /* was a GROUP condition asked for? */
    const char *pinspec = NULL;                /* --pin-thresholds, the gate hook */
    int8_t pin[NLVLBUF];
    for (int d = 0; d < NLVLBUF; d++) pin[d] = -1;
    const char *third_key = NULL;
    const int *shared_third = NULL;
    double report = 10.0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else if (!strcmp(argv[i], "--min-grays") && i + 1 < argc) { min_grays = atoi(argv[++i]); min_grays_set = 1; }
        /* --by-grays N: a SEPARATE word for each grey count from 5 down to N,
         * which is secondword's e5.e4....eN partition. */
        else if (!strcmp(argv[i], "--by-grays") && i + 1 < argc) {
            /* -1 is "not given"; a negative typed here must be REFUSED by the
             * range check, not read as "off" */
            by_grays = atoi(argv[++i]);
            if (by_grays < 0) by_grays = WORDLEN + 1;
        }
        /* --every-reply: allow a partition covering EVERY reply, which groups.c
         * otherwise refuses as a blind opening.  With a word per grey count
         * (--by-grays 0) the reply still chooses the word, so it is a strategy,
         * just not one that ever falls back to the random tail on guess 2. */
        else if (!strcmp(argv[i], "--every-reply")) GROUPS_EVERY_REPLY = 1;
        /* --group SPEC: any partition groups.c can express, including the vowel
         * atoms -- the same flag, the same grammar and the same canonical name
         * secondword uses, because it is the same code. */
        else if (!strcmp(argv[i], "--group") && i + 1 < argc) { groups_add(argv[++i]); ngroupspec++; }
        /* --split-vowels / --split-matched-vowels: the cross product of the
         * --by-grays groups with the greyed or matched vowel count, written out
         * here so the flag means the same thing in both solvers. */
        else if (!strcmp(argv[i], "--split-vowels")) split_v = 1;
        else if (!strcmp(argv[i], "--split-matched-vowels")) split_mv = 1;
        /* --split-nongray: cross the --by-grays groups with WHICH tiles came
         * back non-grey (green and yellow alike), not how many. */
        else if (!strcmp(argv[i], "--split-nongray")) split_nz = 1;
        else if (!strcmp(argv[i], "--opener") && i + 1 < argc) one = argv[++i];
        else if (!strcmp(argv[i], "--openers") && i + 1 < argc) openpath = argv[++i];
        /* --words POOL: which words may be COMMITTED to, at every level and at
         * the root.  A different objective, not a setting -- see INPOOL. */
        else if (!strcmp(argv[i], "--words") && i + 1 < argc) poolpath = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--memo-bits") && i + 1 < argc) memo_bits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--report") && i + 1 < argc) report = atof(argv[++i]);
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc) limit = atoi(argv[++i]);
        /* --no-prune evaluates EVERY second word AND every opener, which must
         * give the same answer as the pruned walk.  That equality is the gate's
         * sharpest check, so the flag exists for it rather than for production.
         * WITH --topk it keeps only its opener half -- the beam still restricts
         * the second words, so the pair means "every opener, k words each",
         * which is how the beam gets compared against the exact answer. */
        else if (!strcmp(argv[i], "--no-prune")) no_prune = 1;
        /* --topk K: evaluate only the K best second words per group by the
         * one-ply score, instead of every candidate that survives the bound.
         * It turns a PROOF into a SCREEN -- see solve_opener. */
        else if (!strcmp(argv[i], "--topk") && i + 1 < argc) topk = atoi(argv[++i]);
        /* THE THIRD LEVEL.  --third-max-matched N commits a word wherever the
         * two replies together have proved at most N letters; --third-key says
         * whether that word is per (group, matched count) or shared across the
         * groups by matched count alone. */
        else if (!strcmp(argv[i], "--third-key") && i + 1 < argc) third_key = argv[++i];
        else if (!strcmp(argv[i], "--third-max-matched") && i + 1 < argc)
            third_max = atoi(argv[++i]);
        /* --third-decline lets a case play NO committed word when the random
         * tail is cheaper.  A different strategy, not a better search. */
        else if (!strcmp(argv[i], "--third-decline")) third_decline = 1;
        /* --max-level N: a committed word at EVERY level down to N, each with a
         * decline option.  Supersedes --third-key, which is the N=3 case. */
        else if (!strcmp(argv[i], "--max-level") && i + 1 < argc) maxlvl = atoi(argv[++i]);
        /* --ladder N: ONE committed word per level down to N, each fired by its
         * own THRESHOLD on the matched letters, declining ENDING the ladder.
         * The whole strategy is N words and N-1 thresholds -- see THE LADDER. */
        else if (!strcmp(argv[i], "--ladder") && i + 1 < argc) ladder = atoi(argv[++i]);
        /* --pin-thresholds a,b,c PINS T2,T3,... instead of searching them.  It is
         * how the gate turns this into a quantity another code path can compute:
         * at N=2 a pinned T is exactly the group g<6-T>, because after ONE guess
         * matched is 5 minus the greys. */
        else if (!strcmp(argv[i], "--pin-thresholds") && i + 1 < argc) pinspec = argv[++i];
        /* --print-label resolves the firing condition, prints its CANONICAL name
         * and stops.  The wrapper needs that name for the filename, and groups.c
         * is the one place that knows it -- deriving it in shell would be a
         * second implementation of the rule the two solvers share. */
        else if (!strcmp(argv[i], "--print-label")) print_label = 1;
        /* --dump-matched FILE: a deterministic sample of (g1, g2, answer) triples
         * with the matched-letter count, for the gate to diff against
         * tree_states.state_from_strings.  The key is new machinery, so it gets
         * an independent check rather than being trusted. */
        else if (!strcmp(argv[i], "--dump-matched") && i + 1 < argc) matchpath = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (!outpath && !print_label && !matchpath) {
        fprintf(stderr, "secondexact needs --out FILE -- a run that prints its "
                        "answer and saves NOTHING is a run lost.\n"
                        "Use the wrapper: bash solver/run-second-exact.sh\n");
        return 1;
    }
    if (min_grays < 1 || min_grays > WORDLEN) {
        fprintf(stderr, "--min-grays must be 1..%d\n", WORDLEN);
        return 1;
    }
    if (topk < 0) { fprintf(stderr, "--topk must be at least 1\n"); return 1; }
    if (maxlvl && (maxlvl < 2 || maxlvl >= MAXLVL)) {
        fprintf(stderr, "--max-level must be 2..%d: 2 is a second word then the "
                        "random tail, and each level beyond\n"
                        "multiplies the search by the beam width\n", MAXLVL - 1);
        return 1;
    }
    if (maxlvl && !topk) {
        fprintf(stderr, "--max-level needs --topk: the search is k per level, "
                        "so it only exists inside a beam\n");
        return 1;
    }
    if (maxlvl && third_max >= 0) {
        fprintf(stderr, "--max-level supersedes --third-key: the third level is "
                        "its N=3 case.  Pass one or the other\n");
        return 1;
    }
    if (third_decline && third_max < 0) {
        fprintf(stderr, "--third-decline is an option ON the third level; it "
                        "needs --third-key and --third-max-matched\n");
        return 1;
    }
    if ((third_key != NULL) != (third_max >= 0)) {
        fprintf(stderr, "--third-key and --third-max-matched go together: one "
                        "says WHICH cases share a word, the other WHEN a word\n"
                        "is committed at all, and neither has a default\n");
        return 1;
    }
    if (third_key && strcmp(third_key, "group") && strcmp(third_key, "shared")) {
        fprintf(stderr, "--third-key must be `group` (a word per group and "
                        "matched count) or `shared` (per matched count only)\n");
        return 1;
    }
    if (third_key && !strcmp(third_key, "shared")) {
        fprintf(stderr, "--third-key shared is NOT BUILT YET.  Sharing one word "
                        "across the groups couples them, so the second words\n"
                        "have to be re-chosen inside a search over word TRIPLES "
                        "rather than group by group; `group` is the separable\n"
                        "key and is what works today.\n");
        return 1;
    }
    if (third_max >= 0 && (third_max > WORDLEN || third_max < 0)) {
        fprintf(stderr, "--third-max-matched must be 0..%d\n", WORDLEN);
        return 1;
    }
    if (third_max >= 0 && !topk) {
        fprintf(stderr, "--third-key needs --topk: choosing a third word for "
                        "every candidate second word is a nested search, and\n"
                        "only the beam makes it affordable\n");
        return 1;
    }
    if (by_grays >= 0 && (by_grays < (GROUPS_EVERY_REPLY ? 0 : 1) || by_grays > WORDLEN)) {
        fprintf(stderr, "--by-grays must be 1..%d (0 too under --every-reply, "
                        "which gives every grey count its own word)\n", WORDLEN);
        return 1;
    }
    if (split_v + split_mv + split_nz > 1) {
        fprintf(stderr, "--split-vowels, --split-matched-vowels and "
                        "--split-nongray are three different partitions; "
                        "pick one\n");
        return 1;
    }
    if ((split_v || split_mv || split_nz) && by_grays < 0) {
        fprintf(stderr, "--split-* splits the --by-grays groups; pass "
                        "--by-grays N too\n");
        return 1;
    }
    char poolname[64] = "";
    if (poolpath) {
        const char *b = strrchr(poolpath, '/');
        b = b ? b + 1 : poolpath;
        snprintf(poolname, sizeof poolname, "%s", b);
        char *dot = strstr(poolname, ".txt");
        if (dot) *dot = 0;
    }

    /* ---------------------------------------------------------- the ladder --
     * THE LEVEL-2 THRESHOLD *IS* THE FIRING CONDITION, and it is what the search
     * chooses -- so a group condition would be fixing the very thing being
     * optimised, under a name that says otherwise.  Every group flag is refused
     * rather than ignored. */
    char ladder_label[512];
    if (ladder) {
        if (ladder < 2 || ladder > MAXLVL) {
            fprintf(stderr, "--ladder must be 2..%d: 2 is one committed word then "
                            "the random tail, and each\nlevel beyond multiplies "
                            "the search by the beam width times the thresholds\n",
                    MAXLVL);
            return 1;
        }
        if (!topk) {
            fprintf(stderr, "--ladder needs --topk: five words over 12972 each is "
                            "not a space anything enumerates,\nso the search only "
                            "exists inside a beam\n");
            return 1;
        }
        if (maxlvl || third_max >= 0) {
            fprintf(stderr, "--ladder is a DIFFERENT strategy from --max-level / "
                            "--third-key, not a variant of one:\nthere every "
                            "matched count gets its own word, here they share one "
                            "and a threshold\ndecides who plays it.  Pass one or "
                            "the other\n");
            return 1;
        }
        if (min_grays_set || by_grays >= 0 || ngroupspec || split_v || split_mv || split_nz) {
            fprintf(stderr, "--ladder takes no firing condition: the level-2 "
                            "THRESHOLD is that condition, and it is\nwhat the "
                            "search is choosing.  A group would pin it while the "
                            "filename claimed\notherwise\n");
            return 1;
        }
        if (pinspec) {
            const char *p = pinspec;
            for (int d = 2; d <= ladder; d++) {
                if (!*p) {
                    fprintf(stderr, "--pin-thresholds needs %d values (T2..T%d), "
                            "comma separated\n", ladder - 1, ladder);
                    return 1;
                }
                int t = atoi(p);
                if (t < 0 || t > WORDLEN + 1) {
                    fprintf(stderr, "--pin-thresholds: a threshold is 0..%d "
                            "(0 never fires, %d always)\n", WORDLEN + 1, WORDLEN + 1);
                    return 1;
                }
                pin[d] = (int8_t)t;
                while (*p && *p != ',') p++;
                if (*p == ',') p++;
            }
            if (*p) {
                fprintf(stderr, "--pin-thresholds has more values than --ladder %d "
                        "has levels\n", ladder);
                return 1;
            }
        }
        /* THE LABEL IS THE QUANTITY.  A different depth and a different pinning
         * are different strategies, so both land in the name -- and the resume
         * stamp is checked against it, so a file cannot be continued by a run
         * asking a different question. */
        int k = snprintf(ladder_label, sizeof ladder_label, "ladderL%d", ladder);
        if (pinspec) {
            k += snprintf(ladder_label + k, sizeof ladder_label - k, "_pin");
            for (int d = 2; d <= ladder; d++)
                k += snprintf(ladder_label + k, sizeof ladder_label - k, "%s%d",
                              d == 2 ? "" : "-", pin[d]);
        }
        LADDER_LEVELS = ladder;
    }
    if (pinspec && !ladder) {
        fprintf(stderr, "--pin-thresholds is an option ON --ladder\n");
        return 1;
    }
    /* BOTH BRANCHES APPEND THE POOL, and the second one is easy to forget: the
     * wrapper derives its filename from this label while the settings stamp is
     * written from `label` in main, so a pool reaching one and not the other
     * would put a restricted run under the unrestricted run's NAME, with a stamp
     * that then refuses to resume its own file. */
    if (print_label && ladder) {
        append_pool(ladder_label, sizeof ladder_label, poolname);
        printf("%s\n", ladder_label);
        return 0;
    }
    if (print_label) {
        /* the tiles are all groups_resolve needs (a vowel atom defers its
         * checks to the opener loop), so this answers without loading a thing */
        char lab[512];
        groups_build_tiles();
        if (by_grays >= 0) groups_add_by_grays(by_grays, split_v, split_mv, split_nz);
        groups_resolve(min_grays, lab, sizeof lab);
        append_pool(lab, sizeof lab, poolname);
        printf("%s\n", lab);
        return 0;
    }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * 20000);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words_file(path, GWORD);
    char (*AWORD)[WBUF] = malloc(sizeof(char[WBUF]) * 20000);
    snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    int nans = load_words_file(path, AWORD);
    if (patpath) snprintf(path, sizeof path, "%s", patpath);
    else snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    NA = c;
    if (r != NG || NA != nans) {
        fprintf(stderr, "the matrix is %dx%d but the lists are %dx%d\n",
                r, c, NG, nans);
        return 1;
    }
    ANS2G = malloc(sizeof(int32_t) * NA);
    for (int a = 0; a < NA; a++) {
        ANS2G[a] = -1;
        for (int g = 0; g < NG; g++)
            if (!strcmp(AWORD[a], GWORD[g])) { ANS2G[a] = g; break; }
        if (ANS2G[a] < 0) {
            fprintf(stderr, "the answer %s is not a legal guess\n", AWORD[a]);
            return 1;
        }
    }
    if (poolpath) {
        char (*pw)[WBUF] = malloc(sizeof(char[WBUF]) * 20000);
        int np = load_words_file(poolpath, pw);
        INPOOL = calloc(NG, 1);
        for (int i = 0; i < np; i++) {
            int found = -1;
            for (int g = 0; g < NG; g++)
                if (!strcmp(GWORD[g], pw[i])) { found = g; break; }
            /* REFUSED, NOT SKIPPED.  A mistyped pool file would otherwise run a
             * smaller and different experiment under the name of this one, and
             * the only evidence would be a total nobody could reproduce. */
            if (found < 0) {
                fprintf(stderr, "--words: %s is not a legal guess\n", pw[i]);
                return 1;
            }
            INPOOL[found] = 1;
        }
        free(pw);
        int npool = 0;
        for (int g = 0; g < NG; g++) npool += INPOOL[g];
        if (npool < 2) {
            /* TWO IS THE FLOOR, and it is not fussiness: with one word the
             * opener IS the pool, so the two-level path has no second word to
             * score and its group cost comes back as infinity rather than as a
             * strategy.  Refusing beats reporting that. */
            fprintf(stderr, "--words: %s holds %d word%s -- a pool needs at "
                    "least 2, since the opener is one of them and a level with "
                    "no candidate left is not a strategy\n",
                    poolpath, npool, npool == 1 ? "" : "s");
            return 1;
        }
        fprintf(stderr, "committed words restricted to %d of %d (%s)\n",
                npool, NG, poolpath);
    }
    if (matchpath) {
        FILE *mf = fopen(matchpath, "w");
        fprintf(mf, "g1,g2,answer,matched\n");
        uint64_t st = 88172645463325252ULL;
        for (int n = 0; n < 4000; n++) {
            st ^= st << 13; st ^= st >> 7; st ^= st << 17;
            int a = (int)(st % (uint64_t)NA);
            st ^= st << 13; st ^= st >> 7; st ^= st << 17;
            int w1 = (int)(st % (uint64_t)NG);
            st ^= st << 13; st ^= st >> 7; st ^= st << 17;
            int w2 = (int)(st % (uint64_t)NG);
            fprintf(mf, "%s,%s,%s,%d\n", GWORD[w1], GWORD[w2], AWORD[a],
                    matched_letters(w1, PAT[(size_t)w1 * NA + a],
                                    w2, PAT[(size_t)w2 * NA + a]));
        }
        fclose(mf);
        fprintf(stderr, "dumped 4000 matched-letter samples to %s\n", matchpath);
        return 0;
    }
    groups_build_tiles();
    groups_build_vpos(GWORD, NG);
    /* ONE GROUP, or one per grey count, or anything groups.c can express -- the
     * --group spec is passed straight through, so `--group e3_mv1` means here
     * exactly what it means to secondword. */
    char label[512];
    if (ladder) {
        /* ONE CASE COVERING EVERY REPLY.  groups.c refuses such a condition, and
         * rightly: for the two-level strategy it would be a blind opening.  Here
         * it is not a condition at all -- the ladder's own thresholds do all the
         * deciding -- so the single case is built directly rather than asked for
         * in a grammar whose whole job is to carve the replies up. */
        NGROUP = 1;
        snprintf(GSPEC[0], sizeof GSPEC[0], "ladder");
        snprintf(label, sizeof label, "%s", ladder_label);
        for (int p = 0; p < NPAT; p++) { GFIRE[0][p] = 1; FIRE[p] = 1; }
        OPENER_DEP = 0;
    } else {
        if (by_grays >= 0) groups_add_by_grays(by_grays, split_v, split_mv, split_nz);
        groups_resolve(min_grays, label, sizeof label);
        OPENER_DEP = groups_opener_dependent();
        if (!OPENER_DEP) {
            /* opener-independent: one set of masks serves every opener */
            int8_t zero[NPAT];
            for (int p = 0; p < NPAT; p++) zero[p] = 0;
            /* never_fire_on_a_win: the opener's all-green reply means the game
             * is already WON, so no group may commit a second word there.  Only
             * a group with no greys can contain it (e0, or a 5g0y composition);
             * e0 exists only under --every-reply, which is why this line was not
             * needed before.  The ladder builds its own masks and handles the
             * win itself. */
            for (int g = 0; g < NGROUP; g++) {
                groups_mask_for(&GRP[g], zero, zero, GFIRE[g]);
                GFIRE[g][ALL_GREEN] = 0;
            }
            for (int p = 0; p < NPAT; p++) {
                FIRE[p] = 0;
                for (int g = 0; g < NGROUP; g++) FIRE[p] |= GFIRE[g][p];
            }
        }
    }
    append_pool(label, sizeof label, poolname);
    fprintf(stderr, "loaded %d guesses x %d answers; firing on %s (%d group%s%s)\n",
            NG, NA, label, NGROUP, NGROUP == 1 ? "" : "s",
            OPENER_DEP ? ", per opener" : "");
    if (ladder)
        fprintf(stderr, "LADDER: %d committed words, one per level, each fired "
                "while the CUMULATIVE\n        matched letters are below its own "
                "threshold.  Going over a threshold\n        ENDS the ladder: "
                "every guess from there is a uniformly random consistent\n"
                "        ANSWER, as is guess %d onward.\n", ladder, ladder + 1);
    if (topk && ladder)
        fprintf(stderr, "BEAM k=%d: the %d best OPENERS, and the %d best words at "
                "EVERY level below.\n          Thresholds are ENUMERATED, not "
                "beamed -- only the values that induce a\n          different "
                "firing set.  Every total is an UPPER BOUND and the winner is\n"
                "          the best of the openers EXAMINED, not the optimum.\n",
                topk, topk, topk);
    else if (topk)
        fprintf(stderr, "BEAM k=%d: the %d best OPENERS, and within each the %d "
                "best second words\n          per group -- ONE K governs both, as "
                "in every other solver here.  Every\n          total is an UPPER "
                "BOUND and the winner is the best of the openers\n          "
                "EXAMINED, not the proven optimum.\n", topk, topk, topk);

    int *openers = malloc(sizeof(int) * NG), nopen = 0;
    if (one) {
        for (int g = 0; g < NG; g++) if (!strcmp(GWORD[g], one)) openers[nopen++] = g;
        if (!nopen) { fprintf(stderr, "%s is not a legal guess\n", one); return 1; }
        /* A NAMED OPENER OUTSIDE THE POOL IS A CONTRADICTION, not something to
         * resolve quietly in one direction: --words says which words may be
         * committed to, and the opener is the first of them. */
        if (!COMMITTABLE(openers[0])) {
            fprintf(stderr, "--opener %s is not in --words %s\n", one, poolpath);
            return 1;
        }
    } else if (openpath) {
        char (*rw)[WBUF] = malloc(sizeof(char[WBUF]) * 20000);
        int nr = load_words_file(openpath, rw);
        for (int i = 0; i < nr; i++) {
            int found = -1;
            for (int g = 0; g < NG; g++)
                if (!strcmp(GWORD[g], rw[i])) { found = g; break; }
            if (found < 0) {
                fprintf(stderr, "--openers word %s is not a legal guess\n", rw[i]);
                return 1;
            }
            if (!COMMITTABLE(found)) {
                fprintf(stderr, "--openers word %s is not in --words %s\n",
                        rw[i], poolpath);
                return 1;
            }
            openers[nopen++] = found;
        }
        free(rw);
    } else {
        /* --words RESTRICTS THE ROOT TOO.  The opener is the first committed
         * word, so a pool that did not reach it would be answering a question
         * nobody asked -- and it is the root beam, not --openers, that then
         * keeps the run affordable. */
        for (int g = 0; g < NG; g++) if (COMMITTABLE(g)) openers[nopen++] = g;
    }
    /* THE ROOT BEAM, before phase 1: under --topk only the K best openers are
     * examined at all, so only they are bounded.  A NAMED opener (--opener /
     * --openers) is exempt: there the user has chosen the root and K beams only
     * the branching below it, which is how `wturns` splits the two cases. */
    if (topk && !one && !openpath) {
        int *cnt = calloc(NPAT, sizeof(int));
        RootKey *rk = malloc(sizeof(RootKey) * nopen);
        for (int i = 0; i < nopen; i++) {
            rk[i].w = openers[i];
            rk[i].ssq = root_ssq(openers[i], cnt);
        }
        qsort(rk, (size_t)nopen, sizeof(RootKey), cmp_rootkey);
        int keep = topk < nopen ? topk : nopen;
        for (int i = 0; i < keep; i++) openers[i] = rk[i].w;
        fprintf(stderr, "root beam: the %d best of %d openers by expected answers "
                "remaining\n           (%s %.1f best, %s %.1f worst of those kept)\n",
                keep, nopen, GWORD[rk[0].w], (double)rk[0].ssq / NA,
                GWORD[rk[keep - 1].w], (double)rk[keep - 1].ssq / NA);
        nopen = keep;
        free(rk); free(cnt);
    }
    if (limit > 0 && limit < nopen) nopen = limit;
    fprintf(stderr, "openers: %d%s\n", nopen, no_prune ? "  (--no-prune)" : "");

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    int nth = omp_get_max_threads();
#else
    int nth = 1;
#endif
    fprintf(stderr, "threads: %d\n", nth);

    Row *rows = calloc(nopen, sizeof(Row));
    double t0 = now_s(), last = t0;
    long long done = 0;
    double incumbent = HUGE_VAL;
    int best_i = -1, cut_openers = 0, bounded = 0, resumed = 0;

    for (int oi = 0; oi < nopen; oi++) {
        rows[oi].opener = openers[oi];
        for (int g = 0; g < MAXGRP; g++) rows[oi].second[g] = -1;
        /* -1, NOT the calloc'd 0: index 0 is a perfectly good word, so a level
         * the ladder never reached would read back as a real choice. */
        for (int d = 0; d < NLVLBUF; d++) rows[oi].lword[d] = -1;
    }
    /* RESUME BEFORE ANYTHING IS COMPUTED, so the seeded incumbent is already
     * cutting during phase 2's very first opener. */
    resumed = read_resume(outpath, rows, nopen, label, topk, &incumbent, &best_i);
    if (resumed < 0) return 1;
    /* NOT `out` -- that name is taken by a per-thread scratch buffer inside
     * both parallel regions, which would shadow it exactly where it is used. */
    FILE *outf = fopen(outpath, resumed ? "a" : "w");
    if (!outf) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
    char resumed_note[64] = "";
    if (resumed) snprintf(resumed_note, sizeof resumed_note,
                          ", %d resumed", resumed);
    if (resumed) {
        fprintf(stderr, "resuming: %d openers already on file, best %.6f\n",
                resumed, incumbent / NA);
    } else {
        fprintf(outf, "# secondexact: the EXACT best predetermined second word, "
                "and the exact value of the\n# strategy -- opener, then that word "
                "when the reply fires, then a uniformly random\n# consistent "
                "ANSWER.  No seed and no standard error: the random tail is summed "
                "\n# exactly (math/secondexact.py states the recursion).\n");
        fprintf(outf, "# expected is over all %d answers; decline/fired split it "
                "by whether the rule fired.\n", NA);
        fprintf(outf, "# settings fire=%s openers=%d follow_up=answer topk=%d"
                " third=%d third_key=%s third_decline=%d ladder=%d\n",
                label, nopen, topk, third_max,
                third_key ? third_key : "none", third_decline, ladder);
        if (topk)
            fprintf(outf, "# TOPK=%d: each group's word is the best of the %d "
                    "ranked by the one-ply\n# score, so every total here is an "
                    "UPPER BOUND, not the optimum.\n", topk, topk);
        fprintf(outf, "opener,fires,second,expected,total,decline,fired,"
                "qualifying,scanned,cut\n");
        fflush(outf);
    }

    /* PHASE 1: a cheap sound lower bound for every opener, with no recursion. */
#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        Memo m;
        memo_init(&m, (size_t)memo_bits);
        uint16_t *q = malloc(sizeof(uint16_t) * (size_t)NA * MAXGRP);
        uint16_t *out = malloc(sizeof(uint16_t) * NA);
        int *rstart = malloc(sizeof(int) * NPAT * MAXGRP);
        int *rlen = malloc(sizeof(int) * NPAT * MAXGRP);
        int *rpat = malloc(sizeof(int) * NPAT * MAXGRP);
        int nb[MAXGROUP], nq[MAXGROUP];
        double gb[MAXGROUP];
        /* the opener's own masks: shared when the condition is grey counts
         * alone, rebuilt per opener when a vowel atom makes them depend on the
         * word's letters.  Per THREAD, because the walk is threaded and a shared
         * mask would be another thread's opener half the time. */
        uint8_t (*gf)[NPAT] = malloc(sizeof(uint8_t) * MAXGROUP * NPAT);
        uint8_t *fu = malloc(NPAT);
        int8_t *gvow = malloc(NPAT), *mvow = malloc(NPAT);
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 8)
#endif
        for (int oi = 0; oi < nopen; oi++) {
            /* second[] is -1, NOT the calloc'd 0 (set before the resume read):
             * a cut opener never reaches solve_opener, and index 0 is a
             * perfectly good word, so the zero read back as a real choice. */
            if (ladder) {
                /* NO WORD LOOP HERE.  The ladder's bound needs only the opener's
                 * own bucket sizes, so phase 1 is a pass over the answers rather
                 * than a minimisation over 12972 second words. */
                rows[oi].bound = ladder_bound(&m, openers[oi]);
            } else {
            masks_for(openers[oi], gf, fu, gvow, mvow);
            rows[oi].bound = opener_bound(&m, openers[oi], q, out, rstart, rlen,
                                          rpat, nb, nq, gb, gf, fu);
            }
            /* PHASE 1 NARRATES.  It is a minute of work on the full list, and
             * silence reads as a hang -- the same reason every other phase in
             * this repo prints. */
#ifdef _OPENMP
#pragma omp atomic
#endif
            bounded++;
            if ((bounded & 255) == 0) {
#ifdef _OPENMP
#pragma omp critical (progress)
#endif
                if (now_s() - last >= report) {
                    last = now_s();
                    fprintf(stderr, "  bounding %d/%d openers  (%.0fs)\n",
                            bounded, nopen, now_s() - t0);
                    fflush(stderr);
                }
            }
        }
        free(q); free(out); free(rstart); free(rlen); free(rpat);
        free(gf); free(fu); free(gvow); free(mvow);
        free(m.e); free(m.buf); free(m.cnt); free(m.touch); free(m.start); free(m.len);
    }
    int *order = malloc(sizeof(int) * nopen);
    for (int i = 0; i < nopen; i++) order[i] = i;
    /* ascending by bound: the cheapest possible opener first, so the incumbent
     * is strong before the hopeless ones are reached */
    for (int i = 1; i < nopen; i++) {          /* insertion sort is fine at 13k */
        int v = order[i];
        int j = i - 1;
        while (j >= 0 && rows[order[j]].bound > rows[v].bound) {
            order[j + 1] = order[j];
            j--;
        }
        order[j + 1] = v;
    }
    fprintf(stderr, "bounded %d openers in %.1fs; best possible %.5f\n",
            nopen, now_s() - t0, rows[order[0]].bound / NA);

    /* PHASE 2: walk them in that order against a shared incumbent.  An opener
     * whose BOUND is not below the incumbent cannot win and is never evaluated;
     * because the bound is sound and the order ascending, what survives to the
     * end is the proven optimum over every (opener, second word) pair. */
#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        Memo m;
        memo_init(&m, (size_t)memo_bits);
        uint16_t *q = malloc(sizeof(uint16_t) * (size_t)NA * MAXGRP);
        uint16_t *out = malloc(sizeof(uint16_t) * NA);
        int *rstart = malloc(sizeof(int) * NPAT * MAXGRP);
        int *rlen = malloc(sizeof(int) * NPAT * MAXGRP);
        int *rpat = malloc(sizeof(int) * NPAT * MAXGRP);
        int nbs[MAXGROUP], nqs[MAXGROUP];
        double gbs[MAXGROUP];
        /* the opener's own masks: shared when the condition is grey counts
         * alone, rebuilt per opener when a vowel atom makes them depend on the
         * word's letters.  Per THREAD, because the walk is threaded and a shared
         * mask would be another thread's opener half the time. */
        uint8_t (*gf)[NPAT] = malloc(sizeof(uint8_t) * MAXGROUP * NPAT);
        uint8_t *fu = malloc(NPAT);
        int8_t *gvow = malloc(NPAT), *mvow = malloc(NPAT);
        /* THE LEVEL RECURSION'S WORKSPACE, per thread: one answer buffer,
         * bucket list and state array PER LEVEL, so a level cannot clobber the
         * one above it.  Allocated once per thread, not per opener. */
        Levels lev;
        memset(&lev, 0, sizeof lev);
        for (int d = 0; d < NLVLBUF; d++) {
            lev.cand[d] = malloc(sizeof(Cand) * NG);
            lev.buf[d] = malloc(sizeof(uint16_t) * NA);
            lev.bkt[d] = malloc(sizeof(Bkt) * NA);
            lev.st[d]  = malloc(sizeof(MState) * NA);
            lev.mc[d]  = malloc(NA);
            /* only the ladder ranks per matched count, and the table is 0.6 MB a
             * level a thread -- not something to pay for when it is unused */
            lev.ssqm[d] = ladder ? malloc(sizeof(int64_t) * (size_t)NG * MAXCASE)
                                 : NULL;
        }
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
        for (int k = 0; k < nopen; k++) {
            int oi = order[k];
            Row *rr = &rows[oi];
            if (rr->resumed) continue;           /* already proved, already filed */
            double inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
            inc = incumbent;
            if (!no_prune && !(rr->bound < inc)) {
#ifdef _OPENMP
#pragma omp atomic
#endif
                cut_openers++;
                continue;
            }
            if (ladder) {
                solve_ladder_opener(&m, &lev, rr->opener, rr, topk, ladder, pin);
            } else {
            /* the layout again -- cheap, and it keeps phase 2 independent of
             * whatever phase 1 left in the shared buffers */
            masks_for(rr->opener, gf, fu, gvow, mvow);
            opener_bound(&m, rr->opener, q, out, rstart, rlen, rpat, nbs, nqs,
                         gbs, gf, fu);
            solve_opener(&m, rr->opener, rr, inc, no_prune, q, out, rstart, rlen,
                         rpat, nbs, nqs, gbs, fu, topk, third_max, shared_third,
                         third_decline, maxlvl, &lev);
            }
#ifdef _OPENMP
#pragma omp critical (progress)
#endif
            {
                done++;
                double v = rr->decline;
                /* A LADDER THAT DECLINES EVERYWHERE IS STILL A STRATEGY -- the
                 * plain opener -- and still has a total, so it is never treated
                 * as an empty row the way a group with no qualifying answer is. */
                int any = ladder ? 1 : 0;
                for (int g = 0; g < NGROUP; g++) {
                    v += rr->fired[g];
                    any |= rr->second[g] >= 0;
                }
                if (any && v < incumbent) {
                    incumbent = v;
                    best_i = oi;
                    char line[4096];
                    format_strategy(line, sizeof line, rr, 0);
                    fprintf(stderr, "[%6.0fs] %s%s  %.6f  NEW BEST\n",
                            now_s() - t0, GWORD[rr->opener], line, v / NA);
                    fflush(stderr);
                }
                write_rows(outf, rr);
                if (now_s() - last >= report) {
                    last = now_s();
                    /* PROGRESS IS evaluated + cut, both SHARED and both only
                     * rising.  It used to print this thread's loop index, which
                     * under schedule(dynamic) is wherever the reporting thread
                     * happened to be -- so it jumped 1446, 1451, 735, 5050 and
                     * meant nothing. */
                    fprintf(stderr, "  %d/%d openers  %d evaluated, %d cut%s  "
                            "best %.6f  (%.0fs)\n",
                            (int)done + cut_openers + resumed, nopen, (int)done,
                            cut_openers, resumed_note, incumbent / NA,
                            now_s() - t0);
                    fflush(stderr);
                }
            }
        }
        free(lev.node);
        for (int d = 0; d < NLVLBUF; d++) {
            free(lev.cand[d]); free(lev.buf[d]); free(lev.bkt[d]);
            free(lev.st[d]); free(lev.mc[d]); free(lev.ssqm[d]);
        }
        free(q); free(out); free(rstart); free(rlen); free(rpat);
        free(gf); free(fu); free(gvow); free(mvow);
        free(m.e); free(m.buf); free(m.cnt); free(m.touch); free(m.start); free(m.len);
    }

    /* Everything still unwritten is an opener the bound CUT -- it never reached
     * solve_opener, so it has no numbers and nothing to resume from.  Appended
     * here so the finished file still describes all every opener. */
    for (int oi = 0; oi < nopen; oi++)
        if (!rows[oi].resumed && !rows[oi].done) write_rows(outf, &rows[oi]);
    fclose(outf);
    if (best_i >= 0) {
        char line[4096];
        format_strategy(line, sizeof line, &rows[best_i], 1);
        fprintf(stderr, "\nbest: %s then%s", GWORD[rows[best_i].opener], line);
        fprintf(stderr, " -- %.6f expected guesses (%s)\n", incumbent / NA,
                topk ? "UPPER BOUND, beam" : "exact");
    }
    fprintf(stderr, "%d openers: %lld evaluated exactly, %d cut by the bound%s, "
            "in %.1fs\nwrote %s\n", nopen, done, cut_openers, resumed_note,
            now_s() - t0, outpath);
    return 0;
}
