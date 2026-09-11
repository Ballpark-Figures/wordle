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
 * Build:  see build.sh      Run:  bash solver/run-second-exact.sh   (from math/)
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <time.h>
#include <math.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define NPAT  243
#define WBUF  8
#define WORDLEN 5
#define ALL_GREEN (NPAT - 1)
#define MAXDEPTH 64

static int      NG, NA;
static uint8_t *PAT;                 /* NG * NA, row-major */
static char   (*GWORD)[WBUF];
static int8_t   GRAYS[NPAT], GREENS[NPAT], YELLOWS[NPAT];
static uint8_t  FIRE[NPAT];          /* does this reply fire the rule? */
static int32_t *ANS2G;               /* answer index -> guess index */

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
 * THE KEY IS STORED INLINE AND COMPARED, so a hash collision cannot return
 * another set's value.  That caps what is cacheable at KEYMAX answers; bigger
 * sets are computed without the cache, which costs little because they are rare
 * and their PARTS -- where the reuse actually is -- are small.  A lost entry is
 * only a recomputation: T is a pure function of its set.
 */
/* THE KEY IS A 128-BIT FINGERPRINT of the set, not the set itself.  Storing the
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

static void build_tiles(void) {
    for (int c = 0; c < NPAT; c++) {
        int x = c, gr = 0, gn = 0, y = 0;
        for (int i = 0; i < WORDLEN; i++) {
            int t = x % 3;
            if (t == 0) gr++; else if (t == 2) gn++; else y++;
            x /= 3;
        }
        GRAYS[c] = (int8_t)gr; GREENS[c] = (int8_t)gn; YELLOWS[c] = (int8_t)y;
    }
}

/* ------------------------------------------------------- one opener ------- */

typedef struct {
    int32_t opener, second;
    double  decline;      /* exact total over the replies that do NOT fire */
    double  fired;        /* exact total over the replies that DO, best word */
    double  bound;        /* a sound lower bound on decline + fired */
    int32_t nq, scanned, cut;
    int     done;
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
static double fired_total(Memo *m, const uint16_t *q, int nq, const int *rstart,
                          const int *rlen, int nb, int w, int bound_only,
                          uint16_t *out, int depth) {
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
static double decline_total(Memo *m, int og, uint16_t *out, int depth) {
    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt + (size_t)depth * NPAT;
    int *touch = m->touch + (size_t)depth * NPAT;
    int *pstart = m->start + (size_t)depth * NPAT;
    int *plen = m->len + (size_t)depth * NPAT;
    int nt = 0;
    for (int a = 0; a < NA; a++) {
        if (FIRE[row[a]]) continue;
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
        if (!FIRE[row[a]]) out[cnt[row[a]]++] = (uint16_t)a;
    double tot = 0.0;
    for (int k = 0; k < nt; k++) {
        tot += plen[k];                          /* the opener itself */
        if (touch[k] != ALL_GREEN)               /* the opener won: no tail */
            tot += T(m, out + pstart[k], plen[k], depth + 1);
    }
    for (int k = 0; k < nt; k++) cnt[touch[k]] = 0;
    return tot;
}

/* ------------------------------------------------------------- the walk ---- */

typedef struct { double key; int32_t w; } Cand;

static int cmp_cand(const void *a, const void *b) {
    const Cand *x = a, *y = b;
    if (x->key != y->key) return x->key < y->key ? -1 : 1;
    return x->w - y->w;                       /* ties on the lowest guess index */
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
                           int *rstart, int *rlen, int *nbp, int *nqp) {
    const uint8_t *row = PAT + (size_t)og * NA;
    int *cnt = m->cnt, *touch = m->touch;
    double tot = 0.0;

    /* the DECLINE branch, bounded */
    int nt = 0;
    for (int a = 0; a < NA; a++) {
        if (FIRE[row[a]]) continue;
        if (cnt[row[a]]++ == 0) touch[nt++] = row[a];
    }
    for (int k = 0; k < nt; k++) {
        int n = cnt[touch[k]];
        tot += n;                                  /* the opener itself */
        if (touch[k] != ALL_GREEN) tot += 2.0 * n - 1.0;
        cnt[touch[k]] = 0;
    }

    /* the FIRING answers, grouped by the opener's reply -- kept, because the
     * caller needs exactly this layout if the opener survives */
    int nb = 0, nq = 0;
    for (int a = 0; a < NA; a++) {
        if (!FIRE[row[a]]) continue;
        nq++;
        if (cnt[row[a]]++ == 0) touch[nb++] = row[a];
    }
    int acc = 0;
    for (int k = 0; k < nb; k++) {
        int p = touch[k];
        rlen[k] = cnt[p];
        rstart[k] = acc;
        cnt[p] = acc;
        acc += rlen[k];
    }
    for (int a = 0; a < NA; a++)
        if (FIRE[row[a]]) q[cnt[row[a]]++] = (uint16_t)a;
    for (int k = 0; k < nb; k++) cnt[touch[k]] = 0;
    *nbp = nb;
    *nqp = nq;
    if (!nq) return tot;

    double best = HUGE_VAL;
    for (int w = 0; w < NG; w++) {
        if (w == og) continue;
        double v = fired_total(m, q, nq, rstart, rlen, nb, w, 1, out, 1);
        if (v < best) best = v;
    }
    return tot + best;
}

/* Evaluate ONE opener exactly: the best second word, and the strategy's total.
 * `incumbent` is the best total seen so far, in guesses over all 2315 answers;
 * a second word whose BOUND is not below it cannot win and is skipped.  Pass
 * HUGE_VAL to evaluate every word. */
static void solve_opener(Memo *m, int og, Row *r, double incumbent, int no_prune,
                         uint16_t *q, uint16_t *out, int *rstart, int *rlen) {
    memo_clear(m);
    const uint8_t *row = PAT + (size_t)og * NA;

    /* the firing answers, grouped by their reply to the opener */
    int *cnt0 = m->cnt, *touch0 = m->touch;      /* level 0 is this grouping */
    int nb = 0, nq = 0;
    for (int a = 0; a < NA; a++) {
        if (!FIRE[row[a]]) continue;
        nq++;
        if (cnt0[row[a]]++ == 0) touch0[nb++] = row[a];
    }
    int acc = 0;
    for (int k = 0; k < nb; k++) {
        int p = touch0[k];
        rlen[k] = cnt0[p];
        rstart[k] = acc;
        cnt0[p] = acc;
        acc += rlen[k];
    }
    for (int a = 0; a < NA; a++)
        if (FIRE[row[a]]) q[cnt0[row[a]]++] = (uint16_t)a;
    for (int k = 0; k < nb; k++) cnt0[touch0[k]] = 0;

    r->opener = og;
    r->nq = nq;
    r->decline = decline_total(m, og, out, 0);
    r->second = -1;
    r->fired = 0.0;
    r->scanned = 0;
    r->cut = 0;
    if (!nq) {                                /* nothing ever fires */
        r->done = 1;
        return;
    }

    /* Bound every second word first, then walk them ASCENDING: the cheapest
     * possible one goes first, so the incumbent is strong early and the cut
     * bites hardest.  The bound pass has no recursion at all. */
    Cand *cand = malloc(sizeof(Cand) * NG);
    for (int w = 0; w < NG; w++) {
        cand[w].w = w;
        cand[w].key = (w == og) ? HUGE_VAL      /* a repeat cannot split anything */
                     : fired_total(m, q, nq, rstart, rlen, nb, w, 1, out, 0);
    }
    qsort(cand, (size_t)NG, sizeof(Cand), cmp_cand);

    /* EVERYTHING HERE IS A TOTAL over all NA answers -- the incumbent, the
     * running best and the bound alike.  Comparing a bound that includes the
     * decline branch against a best that did not was a units mismatch that cut
     * every candidate after the first and still printed a plausible answer. */
    double best = HUGE_VAL;
    for (int i = 0; i < NG; i++) {
        if (cand[i].key == HUGE_VAL) break;
        /* THE CUT, and it is what makes this a proof: the list is ascending in a
         * SOUND lower bound, so the first candidate whose bound is not below the
         * best total proves every one after it is worse too.  Strict `<` keeps
         * ties, as everywhere else here. */
        double ceiling = best < incumbent ? best : incumbent;
        if (!no_prune && !(r->decline + cand[i].key < ceiling)) {
            r->cut = NG - i;
            break;
        }
        double v = r->decline
                 + fired_total(m, q, nq, rstart, rlen, nb, cand[i].w, 0, out, 0);
        r->scanned++;
        if (v < best) { best = v; r->second = cand[i].w; }
    }
    r->fired = best - r->decline;
    r->done = 1;
    free(cand);
}

int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL, *patpath = NULL;
    const char *one = NULL, *openpath = NULL;
    int min_grays = 3, threads = 0, limit = 0, no_prune = 0, memo_bits = 19;
    double report = 10.0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else if (!strcmp(argv[i], "--min-grays") && i + 1 < argc) min_grays = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--opener") && i + 1 < argc) one = argv[++i];
        else if (!strcmp(argv[i], "--openers") && i + 1 < argc) openpath = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--memo-bits") && i + 1 < argc) memo_bits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--report") && i + 1 < argc) report = atof(argv[++i]);
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc) limit = atoi(argv[++i]);
        /* --no-prune evaluates EVERY second word, which must give the same answer
         * as the pruned walk.  That equality is the gate's sharpest check, so the
         * flag exists for it rather than for production. */
        else if (!strcmp(argv[i], "--no-prune")) no_prune = 1;
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (!outpath) {
        fprintf(stderr, "secondexact needs --out FILE -- a run that prints its "
                        "answer and saves NOTHING is a run lost.\n"
                        "Use the wrapper: bash solver/run-second-exact.sh\n");
        return 1;
    }
    if (min_grays < 1 || min_grays > WORDLEN) {
        fprintf(stderr, "--min-grays must be 1..%d\n", WORDLEN);
        return 1;
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
    build_tiles();
    for (int p = 0; p < NPAT; p++) FIRE[p] = GRAYS[p] >= min_grays;
    fprintf(stderr, "loaded %d guesses x %d answers; firing at %d+ greys\n",
            NG, NA, min_grays);

    int *openers = malloc(sizeof(int) * NG), nopen = 0;
    if (one) {
        for (int g = 0; g < NG; g++) if (!strcmp(GWORD[g], one)) openers[nopen++] = g;
        if (!nopen) { fprintf(stderr, "%s is not a legal guess\n", one); return 1; }
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
            openers[nopen++] = found;
        }
        free(rw);
    } else {
        for (int g = 0; g < NG; g++) openers[nopen++] = g;
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
    int best_i = -1, cut_openers = 0;

    /* PHASE 1: a cheap sound lower bound for every opener, with no recursion. */
#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        Memo m;
        memo_init(&m, (size_t)memo_bits);
        uint16_t *q = malloc(sizeof(uint16_t) * NA);
        uint16_t *out = malloc(sizeof(uint16_t) * NA);
        int *rstart = malloc(sizeof(int) * NPAT), *rlen = malloc(sizeof(int) * NPAT);
        int nb, nq;
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 8)
#endif
        for (int oi = 0; oi < nopen; oi++) {
            rows[oi].opener = openers[oi];
            /* -1, NOT the calloc'd 0: a cut opener never reaches solve_opener,
             * and index 0 is a perfectly good word, so the zero read back as a
             * real choice and printed as one. */
            rows[oi].second = -1;
            rows[oi].bound = opener_bound(&m, openers[oi], q, out, rstart, rlen,
                                          &nb, &nq);
            rows[oi].nq = nq;
        }
        free(q); free(out); free(rstart); free(rlen);
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
        uint16_t *q = malloc(sizeof(uint16_t) * NA);
        uint16_t *out = malloc(sizeof(uint16_t) * NA);
        int *rstart = malloc(sizeof(int) * NPAT), *rlen = malloc(sizeof(int) * NPAT);
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
        for (int k = 0; k < nopen; k++) {
            int oi = order[k];
            Row *rr = &rows[oi];
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
            solve_opener(&m, rr->opener, rr, inc, no_prune, q, out, rstart, rlen);
#ifdef _OPENMP
#pragma omp critical (progress)
#endif
            {
                done++;
                double v = rr->decline + rr->fired;
                if (rr->second >= 0 && v < incumbent) {
                    incumbent = v;
                    best_i = oi;
                    fprintf(stderr, "[%6.0fs] %s %s  %.6f  NEW BEST\n",
                            now_s() - t0, GWORD[rr->opener], GWORD[rr->second],
                            v / NA);
                    fflush(stderr);
                }
                if (now_s() - last >= report) {
                    last = now_s();
                    fprintf(stderr, "  %d/%d openers  %d evaluated, %d cut  "
                            "best %.6f  (%.0fs)\n", k + 1, nopen, (int)done,
                            cut_openers, incumbent / NA, now_s() - t0);
                    fflush(stderr);
                }
            }
        }
        free(q); free(out); free(rstart); free(rlen);
        free(m.e); free(m.buf); free(m.cnt); free(m.touch); free(m.start); free(m.len);
    }

    FILE *f = fopen(outpath, "w");
    if (!f) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
    fprintf(f, "# secondexact: the EXACT best predetermined second word, and the "
               "exact value of the\n# strategy -- opener, then that word when the "
               "reply shows at least %d greys, then a\n# uniformly random "
               "consistent ANSWER.  No seed and no standard error: the random "
               "tail\n# is summed exactly (math/secondexact.py states the "
               "recursion).\n", min_grays);
    fprintf(f, "# expected is over all %d answers; decline/fired split it by "
               "whether the rule fired.\n", NA);
    fprintf(f, "# settings min_grays=%d openers=%d follow_up=answer\n",
            min_grays, nopen);
    fprintf(f, "opener,second,expected,total,decline,fired,qualifying,scanned,cut\n");
    for (int oi = 0; oi < nopen; oi++) {
        Row *v = &rows[oi];
        double tot = v->decline + v->fired;
        if (v->second < 0)
            fprintf(f, "%s,,,,,,%d,%d,%s\n", GWORD[v->opener], v->nq,
                    v->scanned, v->done ? "none" : "cut");
        else
            fprintf(f, "%s,%s,%.6f,%.4f,%.4f,%.4f,%d,%d,%d\n", GWORD[v->opener],
                    GWORD[v->second], tot / NA, tot, v->decline, v->fired,
                    v->nq, v->scanned, v->cut);
    }
    fclose(f);
    if (best_i >= 0)
        fprintf(stderr, "\nbest: %s then %s -- %.6f expected guesses (exact)\n",
                GWORD[rows[best_i].opener], GWORD[rows[best_i].second],
                incumbent / NA);
    fprintf(stderr, "%d openers: %lld evaluated exactly, %d cut by the bound, "
            "in %.1fs\nwrote %s\n", nopen, done, cut_openers, now_s() - t0,
            outpath);
    return 0;
}
