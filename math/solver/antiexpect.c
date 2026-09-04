/* antiexpect.c -- antiwordle: maximise EXPECTED turns, top-K per node.
 *
 * THE OBJECTIVE, and it is not any of its siblings'.  antistall fixes an ANSWER and
 * finds its longest game, choosing the line clairvoyantly -- a per-answer maximum and
 * an upper bound on real play.  antiwordle_sim plays uniformly at random -- a floor.
 * THIS program searches for a STRATEGY played WITHOUT knowing the answer, scored as
 * the EXPECTED number of turns averaged over the still-possible answers.  That is
 * the quantity a player actually wants, and the three are never comparable.
 *
 * THE STATE IS TWO SETS, and conflating them is the mistake this whole family had to
 * unlearn:
 *
 *     L   the words that may legally be PLAYED here      (over the 12972)
 *     A   the answers still POSSIBLE here                (over the 2315)
 *
 * They genuinely differ.  With `goose` the only possible answer, `goofs`, `gooks` and
 * `goops` are still legal plays -- and playing them is how a game gets long.  A is
 * always a subset of L; never the reverse.
 *
 * THE RECURSION:
 *
 *     value(L, A) = max over g in L of
 *                   1 + SUM over p != all-green  (|A_p| / |A|) * value(L & D(g,p), A_p)
 *
 * Every answer pays 1 for the guess; those for which g WAS the answer stop there, and
 * the rest continue weighted by how many produce each feedback.
 *
 * NO SPECIAL CASE AT ONE SURVIVING ANSWER.  Playing a non-answer word then leaves A
 * unchanged and L smaller, so the recursion degenerates to 1 + value(...) and its max
 * IS the longest stall -- the quantity antistall computes.  The endgame falls out of
 * the same code instead of being delegated.
 *
 * TOP-K IS PART OF THE OBJECTIVE.  Only the K best-scoring legal words are examined at
 * each node -- the K best of what is legal THERE, never a global top-K filtered by
 * what happens to still be legal, which would run dry a few guesses in.  Restricting
 * the search can only miss a better strategy, never invent one, so what comes back is
 * a REAL ACHIEVABLE STRATEGY and its value is a LOWER BOUND on the optimum.  Report it
 * as "best found examining K guesses per node", never as the maximum.  K is in the
 * output filename for the same reason --depth is elsewhere: a different K is a
 * different quantity.
 *
 * THE RANKING IS AN INPUT, NEVER A LITERAL.  --rank names a CSV of per-word scores
 * (tools/antiwordle_sim_run.py's output: an `opener` column and a `mean` column).
 * Words absent from it rank last.  The file used is echoed into the output, so a row
 * is traceable to the ranking that produced it.  Nothing about which words are good
 * is compiled in.
 *
 * math/antiwordle_expect.py is the reference implementation and the ORACLE;
 * tools/checkantiexpect.py diffs this against it.  Read the Python first.
 *
 *     bash solver/run-antiexpect.sh -k 5 --rank data/shared/antiwordle/sim.t1000.s0.csv
 *
 * RESULTS ARE FOR OUR WORD LISTS, which are not antiwordle.com's.
 */

#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define WORDLEN    5
#define NPAT       243
#define ALL_GREEN  242
#define WBUF       8

#ifndef MAXG
#define MAXG       13000
#endif
#ifndef MAXA
#define MAXA       13000
#endif

#define BSW  ((MAXG + 63) / 64)      /* uint64 words spanning the guess list */

/* MAXD bounds the RECURSION, not the game: antiwordle has no turn cap and none is
 * imposed. Every legal non-answer guess strictly shrinks L, so a line cannot exceed
 * the letters and squares available -- about 51 -- and 64 leaves headroom. Overrun
 * is a hard error, never a silently truncated answer. */
#define MAXD       64

typedef uint8_t pat_t;

static int      NG, NA;
/* The matrix ROW STRIDE, which is the FULL answer count and stays that way even
 * when --answers narrows the problem. NA is how many answers are in play; NASTRIDE
 * is how the rows are laid out on disk. Using NA for both silently reads the wrong
 * patterns the moment they differ. */
static int      NASTRIDE;
static pat_t   *PAT;                 /* NG * NA, row-major: PAT[g*NA + a] */
static char   (*GWORD)[WBUF];
static char   (*AWORD)[WBUF];
static double  *SCORE;               /* per-word ranking, from --rank */

static uint64_t BS_POS[WORDLEN][26][BSW];      /* guesses with letter c at square i */
static uint64_t BS_CNT[26][WORDLEN + 1][BSW];  /* guesses with >= k copies of c */
static uint64_t BS_ALL[BSW];

static int      TOPK = 0;            /* -k: guesses examined per node (required) */
static long long MAXNODES = 0;       /* --max-nodes, 0 = unlimited */

/* --------------------------------------------------------------- loading
 * load_words and load_npy are optturns.c's, unchanged -- same files, same
 * format, and a second copy of a parser is a second place for it to drift. */

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
    if (!strstr(hdr, "|u1")) {
        fprintf(stderr, "pattern matrix dtype is not |u1: %s\n", hdr); exit(1);
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

static void build_bitsets(void) {
    for (int g = 0; g < NG; g++) {
        BS_ALL[g >> 6] |= 1ULL << (g & 63);
        int cnt[26] = { 0 };
        for (int i = 0; i < WORDLEN; i++) {
            int c = GWORD[g][i] - 'a';
            BS_POS[i][c][g >> 6] |= 1ULL << (g & 63);
            cnt[c]++;
        }
        for (int c = 0; c < 26; c++)
            for (int k = 1; k <= cnt[c]; k++)
                BS_CNT[c][k][g >> 6] |= 1ULL << (g & 63);
    }
}


/* ------------------------------------------------- transposition table
 *
 * optturns' design, with a DOUBLE payload: 128 bits of key, the second half stored
 * XORed with the value so an entry torn by a concurrent writer fails verification
 * and reads as a miss rather than a wrong number. The true key is the PAIR of sets,
 * far too big to store, so the fingerprint is the key and its two halves must stay
 * independent -- correlated halves collided for real in antistall. */

typedef struct { uint64_t h0, h1x; double val; int32_t bestg, pad; } Entry;

static Entry   *TT;
static uint64_t TT_BUCKETS;
static int      TT_OFF = 0;

static void tt_init(int bits) {
    if (bits <= 0) { TT_OFF = 1; fprintf(stderr, "TT: DISABLED\n"); return; }
    if (bits < 2) bits = 2;
    TT_BUCKETS = (uint64_t)1 << (bits - 1);
    size_t bytes = (size_t)TT_BUCKETS * 2 * sizeof(Entry);
    TT = aligned_alloc(64, bytes);
    if (!TT) { fprintf(stderr, "cannot allocate %.2f GB TT\n", bytes / 1e9); exit(1); }
    memset(TT, 0, bytes);
    fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", bits, bytes / 1e9);
}

static inline uint64_t tt_payload(double val, int bestg) {
    uint64_t v;
    memcpy(&v, &val, sizeof v);
    return v ^ ((uint64_t)(uint32_t)bestg << 32);
}

static inline int tt_get(uint64_t h0, uint64_t h1, double *val, int *bestg) {
    if (TT_OFF) return 0;
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++) {
        Entry e = b[j];
        if (e.h0 == h0 && (e.h1x ^ tt_payload(e.val, e.bestg)) == h1) {
            *val = e.val;
            if (bestg) *bestg = e.bestg;
            return 1;
        }
    }
    return 0;
}

static inline void tt_put(uint64_t h0, uint64_t h1, double val, int bestg) {
    if (TT_OFF) return;
    Entry e;
    e.h0 = h0; e.val = val; e.bestg = bestg; e.pad = 0;
    e.h1x = h1 ^ tt_payload(val, bestg);
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    b[1] = b[0];
    b[0] = e;
}

/* Murmur3's 64-bit finalizer: full avalanche. */
static inline uint64_t mix64(uint64_t z) {
    z ^= z >> 33; z *= 0xFF51AFD7ED558CCDULL;
    z ^= z >> 33; z *= 0xC4CEB9FE1A85EC53ULL;
    z ^= z >> 33;
    return z;
}

/* -------------------------------------------------------------- the search */

typedef struct { double score; int g; } Cand;

static int cand_cmp(const void *x, const void *y) {
    const Cand *p = x, *q = y;
    if (p->score > q->score) return -1;      /* descending by score */
    if (p->score < q->score) return 1;
    return p->g - q->g;                      /* ties on the lowest guess index */
}

typedef struct {
    uint64_t  legal[MAXD][BSW];   /* L at each level */
    uint16_t  lw[MAXD][BSW];      /* its live (non-empty) bitset words */
    int       lnw[MAXD];
    uint16_t *alive;              /* MAXD * MAXA -- A at each level, ascending */
    int       nalive[MAXD];
    uint64_t  scratch[BSW];
    uint16_t  swidx[BSW];
    int       snwid;
    Cand     *cand;               /* MAXD * MAXG */
    /* PER DEPTH, not shared. try_guess reads its partition AFTER recursing into each
     * branch, so one shared buffer gets overwritten by the child before the parent
     * has finished walking it -- which made whole subtrees return as if the game had
     * ended immediately. */
    int      *bucket;             /* MAXD * NPAT: pattern -> count */
    uint16_t *part;               /* MAXD * MAXA: answers regrouped by pattern */
    long long nodes;
    int       overflow, blown;
} Ctx;

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    c->alive  = malloc((size_t)MAXD * MAXA * sizeof(uint16_t));
    c->cand   = malloc((size_t)MAXD * MAXG * sizeof(Cand));
    c->bucket = malloc((size_t)MAXD * NPAT * sizeof(int));
    c->part   = malloc((size_t)MAXD * MAXA * sizeof(uint16_t));
    if (!c->alive || !c->cand || !c->bucket || !c->part) {
        fprintf(stderr, "out of memory\n"); exit(1);
    }
    return c;
}

/* The constraint one guess+feedback imposes, as a list of bitsets to AND and to
 * AND-NOT.  Built per (g, p) rather than precomputed: a guess here can produce ANY
 * of the 243 feedbacks (unlike antistall, where the answer is fixed and each guess
 * has exactly one), so the 12972 x 243 table would be far too large. */
typedef struct {
    const uint64_t *pos_and[WORDLEN];   int n_and;
    const uint64_t *cnt_and[26];        int n_cnt;
    const uint64_t *not_terms[WORDLEN + 26]; int n_not;
} Delta;

static void delta_build(Delta *d, int g, int p) {
    d->n_and = d->n_cnt = d->n_not = 0;
    int req[26] = { 0 }, grey[26] = { 0 };
    for (int i = 0, div = NPAT / 3; i < WORDLEN; i++, div /= 3) {
        int t = (p / div) % 3;                 /* 0 grey, 1 yellow, 2 green */
        int ch = GWORD[g][i] - 'a';
        if (t == 2) {
            d->pos_and[d->n_and++] = BS_POS[i][ch];
            req[ch]++;
        } else if (t == 1) {
            d->not_terms[d->n_not++] = BS_POS[i][ch];   /* the square is banned */
            req[ch]++;
        } else {
            grey[ch] = 1;
        }
    }
    for (int ch = 0; ch < 26; ch++) {
        if (req[ch]) d->cnt_and[d->n_cnt++] = BS_CNT[ch][req[ch]];
        /* a grey tile pins the count EXACTLY at what the guess revealed */
        if (grey[ch]) d->not_terms[d->n_not++] = BS_CNT[ch][req[ch] + 1];
    }
}

/* L & D(g,p), walking only L's live words and fingerprinting in the same pass. */
static inline int intersect(const uint64_t *L, const uint16_t *LW, int LNW,
                            const Delta *d, uint64_t *out, uint16_t *ow, int *onw,
                            uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0x243F6A8885A308D3ULL, b = 0x13198A2E03707344ULL;
    int n = 0, m = 0;
    for (int k = 0; k < LNW; k++) {
        int w = LW[k];
        uint64_t x = L[w];
        for (int t = 0; t < d->n_and && x; t++) x &= d->pos_and[t][w];
        for (int t = 0; t < d->n_cnt && x; t++) x &= d->cnt_and[t][w];
        for (int t = 0; t < d->n_not && x; t++) x &= ~d->not_terms[t][w];
        if (x) {
            out[w] = x;
            ow[m++] = (uint16_t)w;
            n += __builtin_popcountll(x);
            uint64_t mm = mix64(x ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(w + 1)));
            a ^= mm; a = a * 0x100000001B3ULL + 0x9E3779B97F4A7C15ULL;
            b += mm; b ^= b >> 29; b *= 0xBF58476D1CE4E5B9ULL;
        }
    }
    *onw = m;
    *h0 = mix64(a);
    *h1 = mix64(b ^ 0xC2B2AE3D27D4EB4FULL);
    return n;
}

/* The answer set's own fingerprint. The memo key is the PAIR of sets, so both
 * halves are folded in -- keying on L alone would merge positions that share the
 * legal words but differ in which answers remain, and they have different values. */
static inline void hash_alive(const uint16_t *A, int nA, uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0x9E3779B97F4A7C15ULL, b = 0xC2B2AE3D27D4EB4FULL;
    for (int i = 0; i < nA; i++) {
        uint64_t m = mix64((uint64_t)A[i] * 0x100000001B3ULL + (uint64_t)i);
        a ^= m; a *= 0xBF58476D1CE4E5B9ULL;
        b += m; b ^= b >> 31;
    }
    *h0 = mix64(a);
    *h1 = mix64(b);
}

static double value(Ctx *c, int depth, int nL, const uint16_t *A, int nA,
                    uint64_t lh0, uint64_t lh1, int *best_out);

/* One guess's contribution: 1 + sum over feedbacks of (share) * child value. */
static double try_guess(Ctx *c, int depth, int g, const uint16_t *A, int nA) {
    const uint64_t *L = c->legal[depth];
    const uint16_t *LW = c->lw[depth];
    int LNW = c->lnw[depth];

    /* Partition A by this guess's feedback. counting-sort into c->part, which keeps
     * each bucket ASCENDING -- hash_alive is order-sensitive, so a stable order is
     * what makes the same set hash the same however it was reached. */
    int *bucket = c->bucket + (size_t)depth * NPAT;
    uint16_t *part = c->part + (size_t)depth * MAXA;
    memset(bucket, 0, (size_t)NPAT * sizeof(int));
    const pat_t *row = PAT + (size_t)g * NASTRIDE;
    for (int i = 0; i < nA; i++) bucket[row[A[i]]]++;
    int offset[NPAT + 1], run = 0;
    for (int p = 0; p < NPAT; p++) { offset[p] = run; run += bucket[p]; }
    offset[NPAT] = run;
    {
        int cur[NPAT];
        memcpy(cur, offset, sizeof(int) * NPAT);
        for (int i = 0; i < nA; i++) part[cur[row[A[i]]]++] = A[i];
    }

    double total = 1.0;                    /* every answer pays for this guess */
    for (int p = 0; p < NPAT; p++) {
        int cnt = bucket[p];
        if (!cnt || p == ALL_GREEN) continue;   /* all-green answers finish here */
        Delta d;
        delta_build(&d, g, p);
        uint64_t ch0, ch1;
        int nC = intersect(L, LW, LNW, &d, c->legal[depth + 1],
                           c->lw[depth + 1], &c->lnw[depth + 1], &ch0, &ch1);
        uint16_t *childA = c->alive + (size_t)(depth + 1) * MAXA;
        memcpy(childA, part + offset[p], (size_t)cnt * sizeof(uint16_t));
        double v = value(c, depth + 1, nC, childA, cnt, ch0, ch1, NULL);
        if (v < 0) return -1.0;            /* node budget blown; unwind */
        total += ((double)cnt / (double)nA) * v;
    }
    return total;
}

static double value(Ctx *c, int depth, int nL, const uint16_t *A, int nA,
                    uint64_t lh0, uint64_t lh1, int *best_out) {
    uint64_t ah0, ah1;
    hash_alive(A, nA, &ah0, &ah1);
    uint64_t h0 = lh0 ^ ah0, h1 = lh1 ^ mix64(ah1);

    double val;
    int bestg;
    if (tt_get(h0, h1, &val, &bestg)) {
        if (best_out) *best_out = bestg;
        return val;
    }
    if (depth + 1 >= MAXD) { c->overflow = 1; return 1.0; }
    if (MAXNODES && c->nodes >= MAXNODES) { c->blown = 1; return -1.0; }
    c->nodes++;

    /* Rank the words legal HERE by their score and keep the best K. Never a global
     * top-K filtered by legality -- that runs dry once play has narrowed. */
    Cand *cand = c->cand + (size_t)depth * MAXG;
    int ncand = 0;
    const uint64_t *L = c->legal[depth];
    for (int k = 0; k < c->lnw[depth]; k++) {
        int wbase = c->lw[depth][k] << 6;
        uint64_t bits = L[c->lw[depth][k]];
        while (bits) {
            int g = wbase + __builtin_ctzll(bits);
            bits &= bits - 1;
            cand[ncand].score = SCORE[g];
            cand[ncand].g = g;
            ncand++;
        }
    }
    if (TOPK && ncand > TOPK) {
        qsort(cand, ncand, sizeof(Cand), cand_cmp);
        ncand = TOPK;
    }

    double best = -1.0;
    int best_g = -1;
    for (int i = 0; i < ncand; i++) {
        double v = try_guess(c, depth, cand[i].g, A, nA);
        if (v < 0) return -1.0;
        if (v > best) { best = v; best_g = cand[i].g; }
    }
    tt_put(h0, h1, best, best_g);
    if (best_out) *best_out = best_g;
    return best;
}

/* ------------------------------------------------------------- the ranking */

/* Load per-word scores from a sweep CSV: an `opener` column and a `mean` column,
 * located BY HEADER NAME rather than position so a future column cannot silently
 * shift the parse. Words absent from the file rank last.
 *
 * The ranking is an INPUT. Nothing about which words are good is compiled in, and
 * the file's name is echoed into the output so a result is traceable to it. */
static int load_ranking(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open ranking %s\n", path); exit(1); }
    char line[8192];
    if (!fgets(line, sizeof line, f)) {
        fprintf(stderr, "%s is empty\n", path); exit(1);
    }
    int col_word = -1, col_mean = -1, ncol = 0;
    for (char *t = strtok(line, ",\r\n"); t; t = strtok(NULL, ",\r\n"), ncol++) {
        if (!strcmp(t, "opener") || !strcmp(t, "word")) col_word = ncol;
        else if (!strcmp(t, "mean")) col_mean = ncol;
    }
    if (col_word < 0 || col_mean < 0) {
        fprintf(stderr, "%s needs an `opener` (or `word`) column and a `mean` one\n",
                path);
        exit(1);
    }
    int found = 0;
    while (fgets(line, sizeof line, f)) {
        char *w = NULL, *m = NULL;
        int k = 0;
        for (char *t = strtok(line, ",\r\n"); t; t = strtok(NULL, ",\r\n"), k++) {
            if (k == col_word) w = t;
            else if (k == col_mean) m = t;
        }
        if (!w || !m || !*m) continue;
        for (int g = 0; g < NG; g++)
            if (!strcmp(GWORD[g], w)) { SCORE[g] = atof(m); found++; break; }
    }
    fclose(f);
    return found;
}

/* -------------------------------------------------------------------- main */

static void usage(void) {
    fprintf(stderr,
      "usage: antiexpect -k K --rank FILE --out FILE   (prefer solver/run-antiexpect.sh)\n"
      "  -k K             guesses examined per node (REQUIRED: it is the objective)\n"
      "  --rank FILE      per-word ranking CSV (opener,mean) -- e.g. a sim sweep\n"
      "  --rank-none      rank by guess index instead; a BASELINE, not a strategy\n"
      "  --out FILE       CSV to write the result to\n"
      "  --no-out         print only, save NOTHING -- must be explicit\n"
      "  --tt-bits B      transposition table size, 2^B entries (default 26)\n"
      "  --max-nodes N    give up past N states, reporting no number\n"
      "  --answers N      use only the first N answers (a cheap partial problem)\n"
      "  --data DIR       data directory (default data, i.e. run from math/)\n");
    exit(2);
}

int main(int argc, char **argv) {
    setvbuf(stdout, NULL, _IOLBF, 0);
    const char *outpath = NULL, *datadir = "data", *rankpath = NULL;
    int no_out = 0, ttbits = 26, nanswers = 0, ranknone = 0;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "-k") && i + 1 < argc)            TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--rank") && i + 1 < argc)        rankpath = argv[++i];
        else if (!strcmp(argv[i], "--rank-none"))                   ranknone = 1;
        else if (!strcmp(argv[i], "--out") && i + 1 < argc)         outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out"))                      no_out = 1;
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc)     ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--max-nodes") && i + 1 < argc)   MAXNODES = atoll(argv[++i]);
        else if (!strcmp(argv[i], "--answers") && i + 1 < argc)     nanswers = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--data") && i + 1 < argc)        datadir = argv[++i];
        else usage();
    }
    if (TOPK < 1) {
        fprintf(stderr, "antiexpect: -k is required and must be >= 1.\n"
                        "  It bounds the search, so it is PART OF THE OBJECTIVE: a\n"
                        "  different K is a different quantity, not a faster run.\n");
        return 2;
    }
    if (!rankpath && !ranknone) {
        fprintf(stderr, "antiexpect: --rank FILE is required (or --rank-none).\n"
                        "  Which K guesses get examined depends entirely on the\n"
                        "  ranking, so leaving it implicit would make a result\n"
                        "  untraceable to the ordering that produced it.\n");
        return 2;
    }
    if (!outpath && !no_out) {
        fprintf(stderr, "antiexpect: give --out FILE, or --no-out to save NOTHING.\n"
                        "  A run with nowhere to put its answer is a run thrown away.\n"
                        "  Prefer the wrapper: bash solver/run-antiexpect.sh\n");
        return 2;
    }

    char path[512];
    GWORD = malloc(sizeof(*GWORD) * MAXG);
    AWORD = malloc(sizeof(*AWORD) * MAXA);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path, AWORD);
    snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, cc;
    PAT = load_npy(path, &r, &cc);
    if (r != NG || cc != NA) {
        fprintf(stderr, "pattern matrix is %dx%d, lists are %dx%d\n", r, cc, NG, NA);
        return 1;
    }
    NASTRIDE = NA;                       /* rows are laid out over ALL answers */
    if (nanswers > 0 && nanswers < NA) NA = nanswers;   /* a cheaper sub-problem */

    SCORE = calloc((size_t)NG, sizeof(double));
    if (rankpath) {
        int found = load_ranking(rankpath);
        fprintf(stderr, "ranking: %s (%d of %d words scored; the rest rank last)\n",
                rankpath, found, NG);
    } else {
        /* --rank-none is a BASELINE, not a strategy: it ranks by guess index, i.e.
         * alphabetically, which is arbitrary. It exists so the value of a real
         * ranking can be measured against having none. */
        fprintf(stderr, "ranking: NONE (alphabetical -- a baseline, not a strategy)\n");
        for (int g = 0; g < NG; g++) SCORE[g] = (double)(NG - g);
    }

    build_bitsets();
    tt_init(ttbits);

    Ctx *c = ctx_new();
    memcpy(c->legal[0], BS_ALL, sizeof BS_ALL);
    for (int w = 0; w < BSW; w++) c->lw[0][w] = (uint16_t)w;
    c->lnw[0] = BSW;
    uint16_t *A0 = c->alive;
    for (int a = 0; a < NA; a++) A0[a] = (uint16_t)a;

    uint64_t lh0, lh1;
    {   /* fingerprint the full legal set the same way a child would be */
        Delta d; d.n_and = d.n_cnt = d.n_not = 0;
        intersect(BS_ALL, c->lw[0], BSW, &d, c->legal[0], c->lw[0], &c->lnw[0],
                  &lh0, &lh1);
    }

    fprintf(stderr, "k=%d, %d guesses, %d answers\n", TOPK, NG, NA);
    double t0 = (double)clock() / CLOCKS_PER_SEC;
    int opener = -1;
    double val = value(c, 0, NG, A0, NA, lh0, lh1, &opener);
    double secs = (double)clock() / CLOCKS_PER_SEC - t0;

    if (c->overflow) {
        fprintf(stderr, "internal: recursion hit MAXD=%d -- raise it\n", MAXD);
        return 1;
    }
    if (val < 0) {
        printf("ABANDONED after %lld nodes (--max-nodes); no number reported\n",
               c->nodes);
        return 1;
    }
    printf("expected turns = %.10f   opener %s   k=%d   nodes=%lld   %.1fs\n",
           val, opener >= 0 ? GWORD[opener] : "(none)", TOPK, c->nodes, secs);
    printf("  best found examining %d guesses per node -- a LOWER bound on the\n"
           "  optimum, and an achievable strategy, not the maximum.\n", TOPK);

    if (outpath) {
        int fresh = 1;
        FILE *t = fopen(outpath, "r");
        if (t) { fresh = fgetc(t) == EOF; fclose(t); }
        FILE *out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
        if (fresh)
            fprintf(out, "k,ranking,answers,expected_turns,kind,opener,nodes,secs\n");
        fprintf(out, "%d,%s,%d,%.10f,lower-bound,%s,%lld,%.3f\n",
                TOPK, rankpath ? rankpath : "none", NA, val,
                opener >= 0 ? GWORD[opener] : "", c->nodes, secs);
        fclose(out);
        printf("wrote %s\n", outpath);
    }
    return 0;
}
