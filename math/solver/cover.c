/* cover -- find sets of opening words that split EVERY pair of answers apart.
 *
 * THE SAME PROBLEM AS pairsplit's singleton count, stated as SET COVER.  Two
 * answers share a joint bucket iff no chosen word separates them, so "every
 * bucket is a singleton" is exactly "every pair of answers is covered by some
 * word".  Universe: C(2315, 2) = 2,678,455 pairs.  A word covers the pairs it
 * separates.  We want a small cover.
 *
 * WHY THIS RATHER THAN EXTENDING RANKED SCREENS.  pairsplit builds k-word
 * openers by keeping the best (k-1)-word ones and extending them, which assumes
 * a good large opener is built from good small ones.  It is not:
 * catty+frond+rumba+spill+verge+whack splits all 2315 perfectly, yet its best
 * four-word subset scores 1800 singles against a 1985 cut -- the pieces are
 * unremarkable and the screen throws them away.  Covering has no such blind
 * spot: it selects on what is still UNCOVERED, not on standalone quality.
 *
 * WHY IT IS TRACTABLE.  Measured over the 2315 answer words: the median pair is
 * separated by 2151 of them, so nearly every word covers nearly everything --
 * useless for an LP, and the reason the residual collapses so fast.  The whole
 * difficulty lives in a tail of ~400 pairs, of which the hardest, booby/boozy,
 * is separated by just 64 words.  So the search branches on the HARDEST
 * remaining pair: every cover must contain one of its separators, which makes
 * the first level 64 wide instead of 2315.
 *
 *   ./cover --words 6                 # 6-word covers over the 2315 answers
 *   ./cover --words 6 --guess-list data/shared/words/guess.txt
 *   ./cover --words 5 --first 1       # stop at the first one found
 *
 * Build: see build.sh
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <time.h>
#include <limits.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define NPAT 243
#define WBUF 8
#define MAXD 12

static int       NG, NA, NSEL;
static uint8_t  *PAT;                  /* NG x NA */
static char    (*GWORD)[WBUF];
static int      *SEL;                  /* opener indices */
static uint16_t *SEPN;                 /* per pair: how many openers separate it */
static char     *BANNED;               /* per opener, within the current subtree */
static int       WANT = 6, FIRST = 0, FOUND = 0;
static double    T0;

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static size_t pidx(int i, int j) {           /* i < j */
    return (size_t)i * NA - (size_t)i * (i + 1) / 2 + (j - i - 1);
}

static int load_words(const char *path, char (*out)[WBUF]) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64]; int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (!len) continue;
        if (len > WBUF - 1) len = WBUF - 1;
        memcpy(out[n], line, len); out[n][len] = 0; n++;
    }
    fclose(f);
    return n;
}

static uint8_t *load_npy(const char *path, int *rows, int *cols) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char magic[6]; unsigned char ver[2];
    if (fread(magic, 1, 6, f) != 6 || memcmp(magic, "\x93NUMPY", 6)) {
        fprintf(stderr, "%s is not a .npy file\n", path); exit(1);
    }
    if (fread(ver, 1, 2, f) != 2) exit(1);
    size_t hlen;
    if (ver[0] == 1) { unsigned char b[2]; if (fread(b,1,2,f)!=2) exit(1); hlen = b[0]|(b[1]<<8); }
    else { unsigned char b[4]; if (fread(b,1,4,f)!=4) exit(1);
           hlen = (size_t)b[0]|((size_t)b[1]<<8)|((size_t)b[2]<<16)|((size_t)b[3]<<24); }
    char *hdr = malloc(hlen + 1);
    if (fread(hdr, 1, hlen, f) != hlen) exit(1);
    hdr[hlen] = 0;
    if (!strstr(hdr, "u1")) { fprintf(stderr, "patterns not uint8\n"); exit(1); }
    char *p = strchr(hdr, '(');
    if (!p || sscanf(p, "(%d, %d)", rows, cols) != 2) { fprintf(stderr, "bad shape\n"); exit(1); }
    free(hdr);
    size_t nb = (size_t)(*rows) * (size_t)(*cols);
    uint8_t *d = malloc(nb);
    if (!d || fread(d, 1, nb, f) != nb) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return d;
}

static int find_word(char (*list)[WBUF], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* ---- per-depth partition state ----------------------------------------
 * ord[d] lists the answers grouped by the joint pattern of the first d chosen
 * words; rs/rl delimit the groups.  A group of size >= 2 is a set of answers
 * nothing has told apart yet, so its internal pairs are exactly what is still
 * uncovered. */
typedef struct {
    uint16_t *ord[MAXD];
    int      *rs[MAXD], *rl[MAXD], nr[MAXD];
    int       chosen[MAXD];
    int      *cnt, *tin, *fl;
    char     *banned;
    int64_t   nodes, cuts;
    int64_t   cut_at[MAXD];        /* where the bound actually fires */
} Ctx;

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    for (int d = 0; d < MAXD; d++) {
        c->ord[d] = malloc(sizeof(uint16_t) * NA);
        c->rs[d]  = malloc(sizeof(int) * (NA + 1));
        c->rl[d]  = malloc(sizeof(int) * (NA + 1));
    }
    c->cnt = calloc(NPAT, sizeof(int));
    c->tin = malloc(sizeof(int) * NPAT);
    c->fl  = malloc(sizeof(int) * NPAT);
    c->banned = calloc(NG, 1);
    return c;
}

static int split(Ctx *c, int d, int g) {
    const uint8_t *row = PAT + (size_t)g * NA;
    const uint16_t *src = c->ord[d]; uint16_t *dst = c->ord[d + 1];
    int out = 0;
    for (int t = 0; t < c->nr[d]; t++) {
        int st = c->rs[d][t], len = c->rl[d][t], nt = 0;
        if (len == 1) { dst[st] = src[st]; c->rs[d+1][out] = st; c->rl[d+1][out] = 1; out++; continue; }
        for (int i = st; i < st + len; i++) {
            int p = row[src[i]];
            if (c->cnt[p]++ == 0) c->tin[nt++] = p;
        }
        int base = st;
        for (int i = 0; i < nt; i++) { c->fl[c->tin[i]] = base; base += c->cnt[c->tin[i]]; }
        for (int i = st; i < st + len; i++) dst[c->fl[row[src[i]]]++] = src[i];
        int b2 = st;
        for (int i = 0; i < nt; i++) {
            c->rs[d+1][out] = b2; c->rl[d+1][out] = c->cnt[c->tin[i]];
            b2 += c->cnt[c->tin[i]]; out++; c->cnt[c->tin[i]] = 0;
        }
    }
    c->nr[d + 1] = out;
    return out;
}

/* uncovered pairs at depth d, and the hardest one */
static int64_t residual(Ctx *c, int d, int *pa, int *pb) {
    int64_t n = 0; int best = -1, bi = -1, bj = -1;
    for (int t = 0; t < c->nr[d]; t++) {
        int st = c->rs[d][t], len = c->rl[d][t];
        if (len < 2) continue;
        n += (int64_t)len * (len - 1) / 2;
        for (int x = st; x < st + len; x++)
            for (int y = x + 1; y < st + len; y++) {
                int i = c->ord[d][x], j = c->ord[d][y];
                if (i > j) { int s = i; i = j; j = s; }
                int sp = SEPN[pidx(i, j)];
                if (best < 0 || sp < best) { best = sp; bi = i; bj = j; }
            }
    }
    *pa = bi; *pb = bj;
    return n;
}

static void report(Ctx *c, int d) {
    FOUND++;
    printf("[%6.0fs] COVER:", now_s() - T0);
    for (int i = 0; i < d; i++) printf(" %s", GWORD[c->chosen[i]]);
    printf("\n");
    fflush(stdout);
}

static int64_t NODES = 0, CUTS = 0, CUT_AT[MAXD];
static int     ROOT_DONE = 0, ROOT_TOTAL = 0;
static double  LAST_L3 = 0;
static int64_t L3_DONE = 0;
/* Running bests over COMPLETE sets of the requested size. Two metrics because
 * they do not agree: one bucket of three costs 3 pairs but 3 answers, three
 * doubletons cost 3 pairs but 6 answers, so fewest-pairs and most-singletons
 * pick different leaders. */
static int64_t BEST_PAIRS = -1;      /* fewest uncovered pairs by a FULL set */
static int     BEST_SING  = -1;      /* most singleton buckets by a FULL set */
/* The incumbent drives the bound. Searching for a perfect cover asks "can this
 * still reach zero"; searching for the BEST set asks "can this still beat what
 * we have", which is the same test with the target moved. It starts at infinity
 * so the first descent sets it, then tightens as better sets are found. */
static int64_t INCUMBENT = INT64_MAX;
/* --share N: at nodes with N or fewer words left, keep only candidates that
 * break at least R/r of the outstanding pairs.
 *
 * At least ONE of the r remaining words must clear R/r of them, so a word below
 * that share cannot be the big contributor. It can still be a small one, and
 * MRV decides WHICH word is picked here rather than letting us pick the big one
 * first -- so this discards real solutions and the search is no longer
 * exhaustive over its tree. At r = 1 it costs nothing: the last word has to
 * cover everything regardless. Off by default. */
static int SHARE_R = 0;

static int singletons(Ctx *c, int d) {
    int n = 0;
    for (int t = 0; t < c->nr[d]; t++) if (c->rl[d][t] == 1) n++;
    return n;
}

static void note_best(Ctx *c, int d, int64_t R) {
    int sing = singletons(c, d);
    int newp = (BEST_PAIRS < 0 || R < BEST_PAIRS);
    int news = (sing > BEST_SING);
    if (!newp && !news) return;
    if (newp) BEST_PAIRS = R;
    if (news) BEST_SING = sing;
    printf("[%6.0fs] %-11s %d words  pairs=%-7lld singles=%-5d",
           now_s() - T0,
           newp && news ? "BEST both" : newp ? "BEST pairs" : "BEST singles",
           d, (long long)R, sing);
    for (int i = 0; i < d; i++) printf(" %s", GWORD[c->chosen[i]]);
    printf("\n");
    fflush(stdout);
}

/* How many still-uncovered pairs would word g break?  Each run of the current
 * partition contributes C(len,2) pairs; g splits the run into buckets, and the
 * pairs left inside those buckets are the ones it does NOT break. */
static int64_t coverage(Ctx *c, int d, int g) {
    const uint8_t *row = PAT + (size_t)g * NA;
    const uint16_t *src = c->ord[d];
    int64_t got = 0;
    for (int t = 0; t < c->nr[d]; t++) {
        int st = c->rs[d][t], len = c->rl[d][t], nt = 0;
        if (len < 2) continue;
        got += (int64_t)len * (len - 1) / 2;
        for (int i = st; i < st + len; i++) {
            int p = row[src[i]];
            if (c->cnt[p]++ == 0) c->tin[nt++] = p;
        }
        for (int i = 0; i < nt; i++) {
            int64_t v = c->cnt[c->tin[i]];
            got -= v * (v - 1) / 2;
            c->cnt[c->tin[i]] = 0;
        }
    }
    return got;
}

typedef struct { int g; int64_t cov; } Cand;
static int cmp_cand(const void *x, const void *y) {
    int64_t a = ((const Cand *)x)->cov, b = ((const Cand *)y)->cov;
    return a > b ? -1 : (a < b);          /* most pairs broken first */
}

static void search(Ctx *c, int d) {
    if (FIRST && FOUND >= FIRST) return;
    int a, b;
    int64_t R = residual(c, d, &a, &b);

    if (d == WANT) {
        /* A COMPLETE set. This is the only place the incumbent moves, and the
         * only place a best is reported: a partial set always has more pairs
         * outstanding than its completions, so mixing depths would report
         * "improvements" that are only shallower. */
        /* note_best is the ONLY place the bests move. Updating them here as
         * well left it with nothing to report, so it printed nothing at all. */
#pragma omp critical (best)
        {
            if (R < INCUMBENT) INCUMBENT = R;
            note_best(c, d, R);
        }
        if (R == 0) report(c, d);
        return;
    }
    if (R == 0) { report(c, d); return; }

    c->nodes++;
    if ((c->nodes & 0x3FFFF) == 0) {
        int64_t inc;
#pragma omp atomic read
        inc = INCUMBENT;
        fprintf(stderr, "  [%6.0fs] depth %d, %lld pairs left, incumbent %lld, this thread cut at",
                now_s() - T0, d, (long long)R,
                inc == INT64_MAX ? -1 : (long long)inc);
        for (int q = 1; q < WANT; q++)
            fprintf(stderr, " d%d=%lld", q, (long long)c->cut_at[q]);
        fprintf(stderr, "\n");
    }

    Cand *cand = malloc(sizeof(Cand) * NSEL);
    int nc = 0;
    for (int k = 0; k < NSEL; k++) {
        int g = SEL[k];
        if (c->banned[g]) continue;
        if (PAT[(size_t)g * NA + a] == PAT[(size_t)g * NA + b]) continue;
        cand[nc].g = g; cand[nc].cov = coverage(c, d, g); nc++;
    }

    int r = WANT - d;
    if (SHARE_R > 0 && r <= SHARE_R) {
        int keep = 0;
        for (int i = 0; i < nc; i++)
            if (cand[i].cov * (int64_t)r >= R) cand[keep++] = cand[i];
        nc = keep;
    }

    /* THE BOUND, now against the incumbent rather than against zero. No word
     * breaks more pairs than the best one available here, so r words leave at
     * least R - r*best. If that cannot beat what we already have, stop. */
    int64_t best = 0;
    for (int i = 0; i < nc; i++) if (cand[i].cov > best) best = cand[i].cov;
    int64_t floor_ = R - (int64_t)r * best;
    if (floor_ < 0) floor_ = 0;
    int64_t inc;
#pragma omp atomic read
    inc = INCUMBENT;
    if (nc == 0 || floor_ >= inc) { c->cuts++; c->cut_at[d]++; free(cand); return; }

    qsort(cand, nc, sizeof(Cand), cmp_cand);

    int nb = 0;
    int *undo = malloc(sizeof(int) * NSEL);
    for (int k = 0; k < nc; k++) {
        int g = cand[k].g;
        if (c->banned[g]) continue;
        c->chosen[d] = g;
        split(c, d, g);
        search(c, d + 1);
        /* A finished second word is the coarse "still moving" signal. Throttled
         * to one a second: there are hundreds of them per root branch, and the
         * point is progress, not a log of every subtree. */
        /* Completion at level 3, not level 2: a two-word prefix takes so long to
         * exhaust that none finished in the runs so far, so the line never
         * printed. Three-word prefixes close steadily, which is what makes this
         * a heartbeat rather than a rumour. Counted in full, printed at most
         * once a second. */
        if (d == 2) {
            int64_t done;
#pragma omp atomic capture
            done = ++L3_DONE;
            double t = now_s();
            int show = 0;
#pragma omp critical (l3)
            { if (t - LAST_L3 >= 1.0) { LAST_L3 = t; show = 1; } }
            if (show) {
                int64_t ic;
#pragma omp atomic read
                ic = INCUMBENT;
                fprintf(stderr, "  [%6.0fs] finished %s %s %s  (%lld 3-word prefixes done), incumbent %lld\n",
                        t - T0, GWORD[c->chosen[0]], GWORD[c->chosen[1]], GWORD[g],
                        (long long)done, ic == INT64_MAX ? -1 : (long long)ic);
            }
        }
        if (FIRST && FOUND >= FIRST) break;
        c->banned[g] = 1; undo[nb++] = g;
    }
    for (int k = 0; k < nb; k++) c->banned[undo[k]] = 0;
    free(undo); free(cand);
}

int main(int argc, char **argv) {
    const char *datadir = "data", *guesslist = NULL, *patpath = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--words") && i + 1 < argc) WANT = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--first") && i + 1 < argc) FIRST = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--share") && i + 1 < argc) SHARE_R = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc) guesslist = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (WANT >= MAXD) { fprintf(stderr, "--words must be under %d\n", MAXD); return 1; }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * 13000);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    if (patpath) snprintf(path, sizeof path, "%s", patpath);
    else snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    NA = c;
    if (r != NG) { fprintf(stderr, "pattern rows %d != guesses %d\n", r, NG); return 1; }

    /* openers: the answers by default, since a cover is usually wanted from
     * words that could themselves be the answer */
    SEL = malloc(sizeof(int) * NG); NSEL = 0;
    char (*ow)[WBUF] = malloc(sizeof(char[WBUF]) * 13000);
    if (!guesslist) { snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir); guesslist = path; }
    int no = load_words(guesslist, ow);
    for (int i = 0; i < no; i++) {
        int g = find_word(GWORD, NG, ow[i]);
        if (g >= 0) SEL[NSEL++] = g;
    }
    free(ow);
    fprintf(stderr, "%d openers, %d answers, %lld pairs, looking for %d-word covers\n",
            NSEL, NA, (long long)((int64_t)NA * (NA - 1) / 2), WANT);
    if (SHARE_R > 0)
        fprintf(stderr, "--share %d: with %d or fewer words left, only candidates "
                "breaking R/r of the remaining pairs are tried (NOT exhaustive)\n",
                SHARE_R, SHARE_R);

    /* How many openers separate each pair -- counted from the cheap side: for
     * each opener, the pairs INSIDE one of its buckets are the ones it misses.
     * That is ~15k per word rather than 2.7M, so the whole table costs about
     * 35M increments instead of 6 billion comparisons. */
    size_t NP = (size_t)NA * (NA - 1) / 2;
    uint16_t *miss = calloc(NP, sizeof(uint16_t));
    SEPN = malloc(NP * sizeof(uint16_t));
    int *bucket = malloc(sizeof(int) * NPAT * NA), *bn = malloc(sizeof(int) * NPAT);
    double t0 = now_s();
    for (int k = 0; k < NSEL; k++) {
        const uint8_t *row = PAT + (size_t)SEL[k] * NA;
        memset(bn, 0, sizeof(int) * NPAT);
        for (int a = 0; a < NA; a++) bucket[(size_t)row[a] * NA + bn[row[a]]++] = a;
        for (int p = 0; p < NPAT; p++)
            for (int x = 0; x < bn[p]; x++)
                for (int y = x + 1; y < bn[p]; y++)
                    miss[pidx(bucket[(size_t)p * NA + x], bucket[(size_t)p * NA + y])]++;
    }
    for (size_t i = 0; i < NP; i++) SEPN[i] = (uint16_t)(NSEL - miss[i]);
    free(miss); free(bucket); free(bn);
    fprintf(stderr, "separator table built in %.0fs\n", now_s() - t0);

    T0 = now_s();

    /* THE ROOT IS THE PARALLEL LEVEL. Every cover must separate the hardest
     * pair, so the first level is exactly that pair's separators -- 64 of them
     * for booby/boozy over the answers -- and those subtrees are independent.
     * Branch i additionally bans separators 0..i-1, which is what keeps a given
     * cover reachable down exactly one branch; computing that up front is what
     * lets the branches run at the same time instead of in sequence. */
    Ctx *root = ctx_new();
    for (int a = 0; a < NA; a++) root->ord[0][a] = (uint16_t)a;
    root->rs[0][0] = 0; root->rl[0][0] = NA; root->nr[0] = 1;
    int ra, rb;
    residual(root, 0, &ra, &rb);
    int *sep = malloc(sizeof(int) * NSEL), nsep = 0;
    for (int k = 0; k < NSEL; k++) {
        int g = SEL[k];
        if (PAT[(size_t)g * NA + ra] != PAT[(size_t)g * NA + rb]) sep[nsep++] = g;
    }
    fprintf(stderr, "hardest pair: %d separators, so %d root branches\n", nsep, nsep);
    ROOT_TOTAL = nsep;
    fprintf(stderr, "threads: %d\n",
#ifdef _OPENMP
            omp_get_max_threads());
#else
            1);
#endif

    int64_t nodes = 0, cuts = 0;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 1) reduction(+:nodes,cuts)
#endif
    for (int i = 0; i < nsep; i++) {
        if (FIRST && FOUND >= FIRST) continue;
        Ctx *c = ctx_new();
        for (int a = 0; a < NA; a++) c->ord[0][a] = (uint16_t)a;
        c->rs[0][0] = 0; c->rl[0][0] = NA; c->nr[0] = 1;
        for (int j = 0; j < i; j++) c->banned[sep[j]] = 1;
        c->chosen[0] = sep[i];
        split(c, 0, sep[i]);
        search(c, 1);
        nodes += c->nodes; cuts += c->cuts;
#pragma omp critical (rootdone)
        {
            for (int d = 0; d < MAXD; d++) CUT_AT[d] += c->cut_at[d];
            ROOT_DONE++;
            fprintf(stderr, "[%6.0fs] ROOT %d/%d done (%s), incumbent %lld\n",
                    now_s() - T0, ROOT_DONE, ROOT_TOTAL, GWORD[sep[i]],
                    INCUMBENT == INT64_MAX ? -1 : (long long)INCUMBENT);
        }
    }
    NODES = nodes; CUTS = cuts;
    fprintf(stderr, "\n%d cover(s), %lld nodes, %lld cut by the bound, %.0fs\n",
            FOUND, (long long)NODES, (long long)CUTS, now_s() - T0);
    fprintf(stderr, "%lld three-word prefixes fully explored\n", (long long)L3_DONE);
    fprintf(stderr, "best FULL set seen: %lld pairs, %d singletons\n",
            (long long)BEST_PAIRS, BEST_SING);
    fprintf(stderr, "where the bound fired, by depth:");
    for (int d = 0; d < WANT; d++) fprintf(stderr, "  d%d=%lld", d, (long long)CUT_AT[d]);
    fprintf(stderr, "\n");
    return 0;
}
