/* pairsplit -- rank every PAIR of opening words by how evenly the two of them,
 * played BLIND, split the answer set.
 *
 * A pair opener is two words committed to up front: the second is NOT chosen in
 * response to the first one's feedback.  Playing both partitions the answers by
 * the JOINT pattern -- two answers share a bucket iff they return the same
 * pattern to g1 AND the same pattern to g2.  The score is
 *
 *     ssq(g1, g2) = sum over joint buckets of |bucket|^2
 *
 * which is proportional to the expected number of candidates still standing
 * after two guesses.  Lower is evener is better.  Because both words are blind
 * the joint partition cannot depend on their order, so only unordered pairs are
 * enumerated: C(12972, 2) = 84,129,906 of them at the standard 5-letter problem.
 *
 * THIS IS A HEURISTIC SCREEN, NOT A BOUND.  Unlike the solver's root lower bound
 * it proves nothing: the pair with the lowest true total can sit outside the top
 * N.  Whatever comes out of the exact stage that follows is "best of the N pairs
 * screened", never "the optimal pair".  Say it that way.
 *
 * --metric singles RANKS BY A DIFFERENT QUANTITY, and the sentence above applies
 * to it differently in each mode.  A joint bucket of size one is a SINGLETON:
 * that combination of patterns is returned by exactly one answer, so seeing it
 * names the answer outright.  Ranking by how many singletons an opener produces
 * is not a proxy for anything -- it IS the quantity being asked for.
 *
 *   PAIR mode is EXHAUSTIVE.  Every unordered pair is enumerated, so the emitted
 *   head is the exact top of the ranking, not a screen for a later stage.
 *
 *   --extend (TRIPLE mode) is NOT.  It only ever sees triples reachable from a
 *   pair in the file it is given, so the greedy caveat above applies in full: a
 *   triple whose every two-word prefix missed the pair cut cannot be found, at
 *   any width.  Its head is "best of the triples screened", never "the best
 *   triple", whichever metric is steering.
 *
 * Neither is a claim about guesses-to-solve: an opener can win the singleton
 * count and lose on total.
 *
 * Both quantities come out of the same pass -- ssq sums |bucket|^2 while the
 * singleton count sums (|bucket| == 1) -- so --metric only decides which one
 * ORDERS the heap and which columns are written.  singles_nowin excludes a
 * bucket whose pattern is all-green on either word: a pair word that is itself
 * an answer always contributes one such singleton, and it tells you nothing you
 * did not know by winning.
 *
 * Build:  see build.sh   Run:  ./pairsplit --top 10000 --out pairs.csv
 *                             ./pairsplit --metric singles --out singles.csv
 *
 * WHY IT IS FAST ENOUGH.  84M pairs x 2315 answers is ~2e11 inner steps, so the
 * inner loop has to stay in L1.  For a fixed g1 the answers are reordered once
 * into contiguous RUNS, one per g1-bucket; each g2 is then histogrammed run by
 * run into a 243-entry counter (972 bytes, L1-resident), cleared through a
 * touched-list rather than a memset.  The alternative -- keying on
 * g1_bucket*243 + g2_pattern -- needs a ~58k-entry table per pair and thrashes.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <time.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define NPAT  243
#define WBUF  8

#define ALL_GREEN (NPAT - 1)         /* 242 == "22222", the winning pattern */

static int      NG, NA;
static uint8_t *PAT;                 /* NG * NA, row-major */
static char   (*GWORD)[WBUF];
static int      SINGLES = 0;         /* --metric singles: rank by singleton count */
static int      DISJOINT = 0;        /* --disjoint: no letter may repeat across the opener */
static uint32_t *LMASK;              /* per word, bit i set iff letter i occurs */

/* ---- letter masks, for --disjoint ---------------------------------------
 * bit i of LMASK[g] is set iff word g contains letter i, so a word with a
 * REPEATED letter has fewer than WORDLEN bits.  Two words share no letter iff
 * their masks AND to zero, and a pair reaches 10 distinct letters iff both have
 * 5 bits and overlap nowhere -- which makes the whole test one AND and one
 * branch, cheap enough to sit in front of the scoring loop and reject 94% of
 * pairs before any work happens. */
static int popcount32(uint32_t x) {
    int n = 0;
    while (x) { x &= x - 1; n++; }
    return n;
}

static void build_masks(int wordlen) {
    LMASK = malloc(sizeof(uint32_t) * NG);
    for (int g = 0; g < NG; g++) {
        uint32_t m = 0;
        for (int i = 0; i < wordlen && GWORD[g][i]; i++)
            m |= 1u << (GWORD[g][i] - 'a');
        LMASK[g] = m;
    }
}

/* g3 is -1 in pair mode and a real index in --extend (triple) mode */
/* g3 is -1 in pair mode and a real index in --extend (triple) mode.
 * minpar (triple mode) is the BEST rank, 1-based, among the triple's parent
 * pairs that are present in the list -- i.e. the smallest --extend cut at which
 * this triple becomes reachable at all.  Recording it means ONE run at a large
 * cut reconstructs exactly what any smaller cut would have produced: filter to
 * minpar <= N.  That is not an approximation; reachability is per-triple.
 *
 * `key` is what the heap and the sort ORDER BY, and lower is better in both
 * metrics: it is ssq itself under --metric ssq, and MINUS the singleton count
 * under --metric singles, so one comparator serves both without the ordering
 * code knowing which metric is live.  ssq / singles / nowin always carry their
 * own real values, whichever one is steering. */
typedef struct {
    int64_t key, ssq;
    int32_t g1, g2, g3, minpar, singles, nowin;
} Pair;

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static int load_words(const char *path, char (*out)[WBUF]) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[64];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        int len = 0;
        while (line[len] && !isspace((unsigned char)line[len])) len++;
        if (len == 0) continue;
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
        hlen = (size_t)b[0] | ((size_t)b[1] << 8) | ((size_t)b[2] << 16) | ((size_t)b[3] << 24);
    }
    char *hdr = malloc(hlen + 1);
    if (fread(hdr, 1, hlen, f) != hlen) exit(1);
    hdr[hlen] = 0;
    if (!strstr(hdr, "u1")) { fprintf(stderr, "patterns not uint8: %s\n", hdr); exit(1); }
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

/* ---- bounded max-heap of the N SMALLEST ssq seen -------------------------
 * Root is the WORST kept pair, so a candidate is admitted iff it beats the root,
 * which is O(1) to test and O(log N) to insert.  Ties are kept by the same rule
 * the rest of the pipeline uses: a candidate equal to the root is NOT admitted,
 * but only because the heap is already full of equally good pairs -- the cut is
 * about capacity, not about the score. */
static void heap_sift_down(Pair *h, int n, int i) {
    for (;;) {
        int l = 2*i + 1, r = l + 1, m = i;
        if (l < n && h[l].key > h[m].key) m = l;
        if (r < n && h[r].key > h[m].key) m = r;
        if (m == i) return;
        Pair t = h[i]; h[i] = h[m]; h[m] = t;
        i = m;
    }
}

/* Returns 1 if the candidate was KEPT.  Callers use that to decide whether it is
 * even worth testing against the global running best: a candidate good enough to
 * beat the global leader is better than everything, so it necessarily beats this
 * thread's own worst kept entry and lands here first.  Gating on the return value
 * therefore cannot miss an improvement -- and it keeps the clock read and the
 * shared load out of the 84M-iteration path, where they cost more than the
 * scoring loop itself. */
static int heap_push(Pair *h, int *n, int cap, Pair v) {
    if (*n < cap) {
        int i = (*n)++;
        h[i] = v;
        while (i > 0) {                      /* sift up */
            int p = (i - 1) / 2;
            if (h[p].key >= h[i].key) break;
            Pair t = h[i]; h[i] = h[p]; h[p] = t;
            i = p;
        }
        return 1;
    } else if (v.key < h[0].key) {
        h[0] = v;
        heap_sift_down(h, *n, 0);
        return 1;
    }
    return 0;
}

static int find_word(char (*list)[WBUF], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* ---- word -> index, in O(1) ---------------------------------------------
 * find_word is a LINEAR scan, which is fine for a --guess-list read once but
 * quadratic where it matters: a parent file is one lookup per row against 12972
 * words, so 5,020,842 disjoint parents cost ~65 BILLION string compares before
 * any scoring starts -- long enough to look like a hang.  This is the same table
 * keyed by the word text, built once.
 *
 * Open addressing, power-of-two mask, load factor under 25%: no deletions, no
 * resizing, and the keys are 5 bytes, so nothing fancier earns its complexity. */
static int32_t *WIDX;
static int      WIDX_MASK;

static uint64_t whash(const char *w) {
    uint64_t h = 1469598103934665603ULL;          /* FNV-1a */
    for (const unsigned char *p = (const unsigned char *)w; *p; p++)
        h = (h ^ *p) * 1099511628211ULL;
    return h;
}

static void widx_build(void) {
    int bits = 1;
    while ((1 << bits) < NG * 4) bits++;
    WIDX_MASK = (1 << bits) - 1;
    WIDX = malloc(sizeof(int32_t) * ((size_t)WIDX_MASK + 1));
    for (int i = 0; i <= WIDX_MASK; i++) WIDX[i] = -1;
    for (int g = 0; g < NG; g++) {
        uint64_t h = whash(GWORD[g]);
        while (WIDX[h & WIDX_MASK] >= 0) h++;
        WIDX[h & WIDX_MASK] = g;
    }
}

static int lookup_word(const char *w) {
    uint64_t h = whash(w);
    for (;;) {
        int32_t g = WIDX[h & WIDX_MASK];
        if (g < 0) return -1;
        if (!strcmp(GWORD[g], w)) return g;
        h++;
    }
}

static int cmp_pair(const void *a, const void *b) {
    const Pair *x = a, *y = b;
    if (x->key != y->key) return x->key < y->key ? -1 : 1;
    if (x->g1 != y->g1)   return x->g1 < y->g1 ? -1 : 1;
    if (x->g2 != y->g2)   return x->g2 < y->g2 ? -1 : 1;
    return x->g3 < y->g3 ? -1 : (x->g3 > y->g3);
}

/* by WORD INDICES, for the duplicate pass -- a triple can be reached from up to
 * three different parent pairs, and good triples tend to be built from good
 * pairs, so near the top duplicates are the rule rather than the exception */
static int cmp_words(const void *a, const void *b) {
    const Pair *x = a, *y = b;
    if (x->g1 != y->g1) return x->g1 < y->g1 ? -1 : 1;
    if (x->g2 != y->g2) return x->g2 < y->g2 ? -1 : 1;
    return x->g3 < y->g3 ? -1 : (x->g3 > y->g3);
}

/* ---- set of the parent pairs, keyed (lo << 32 | hi) ---------------------
 * A triple {i<j<k} is reachable from (i,j), (i,k) and (j,k), but only from the
 * ones that are actually IN the pair list.  Emitting it from the FIRST present
 * parent in that fixed order means every distinct triple is produced exactly
 * once, by exactly one (pair, third word) combination.
 *
 * This replaces generating duplicates and removing them afterwards.  Dedup after
 * the fact needs a guessed over-collection factor, and if the guess is low the
 * output is quietly short of what was asked for -- the same shape of mistake as
 * counting a word list before deduping it. Here the emitted count IS the number
 * of distinct reachable triples, with nothing to tune. */
static uint64_t *PSET;
static int32_t  *PSET_RANK;      /* 1-based rank of that pair in the input file */
static int       PSET_MASK;

static void pset_build(const Pair *pairs, int n) {
    int bits = 1;
    while ((1 << bits) < n * 4) bits++;      /* keep it under 25% loaded */
    PSET_MASK = (1 << bits) - 1;
    PSET = calloc((size_t)PSET_MASK + 1, sizeof(uint64_t));
    PSET_RANK = calloc((size_t)PSET_MASK + 1, sizeof(int32_t));
    for (int i = 0; i < n; i++) {
        int32_t a = pairs[i].g1, b = pairs[i].g2;
        if (a > b) { int32_t t = a; a = b; b = t; }
        uint64_t key = ((uint64_t)a << 32) | (uint32_t)b;
        uint64_t h = (key * 0x9E3779B97F4A7C15ULL) >> 40;
        while (PSET[h & PSET_MASK]) {
            if (PSET[h & PSET_MASK] == key + 1) break;   /* already present */
            h++;
        }
        PSET[h & PSET_MASK] = key + 1;       /* +1 so 0 stays the empty marker */
        PSET_RANK[h & PSET_MASK] = i + 1;    /* the file is in ascending-ssq order */
    }
}

/* returns the pair's 1-based rank, or 0 if it is not in the list */
static int pset_rank(int32_t a, int32_t b) {
    if (a > b) { int32_t t = a; a = b; b = t; }
    uint64_t key = ((uint64_t)a << 32) | (uint32_t)b;
    uint64_t h = (key * 0x9E3779B97F4A7C15ULL) >> 40;
    for (;;) {
        uint64_t v = PSET[h & PSET_MASK];
        if (!v) return 0;
        if (v == key + 1) return PSET_RANK[h & PSET_MASK];
        h++;
    }
}

static int pset_has(int32_t a, int32_t b) { return pset_rank(a, b) != 0; }

static void sort3(int32_t *a, int32_t *b, int32_t *c) {
    int32_t t;
    if (*a > *b) { t = *a; *a = *b; *b = t; }
    if (*b > *c) { t = *b; *b = *c; *c = t; }
    if (*a > *b) { t = *a; *a = *b; *b = t; }
}

/* ---- the running best, announced as it improves ------------------------
 * Every thread keeps its own heap, so nothing here knew the GLOBAL leader until
 * the merge at the end -- a long run showed progress percentages and no results.
 * BEST_KEY is that leader's sort key, shared.
 *
 * The hot path reads it WITHOUT taking a lock and only enters the critical
 * section when the candidate looks better.  A stale read is harmless in both
 * directions: too high costs one needless critical entry, which then re-checks
 * and does nothing; too low can only happen if another thread just improved the
 * best, in which case that thread already printed a better line.  Improvements
 * are bounded by the metric's range (a few hundred), so this cannot flood.
 *
 * TIES ARE NOT ANNOUNCED, unlike the solver's sweep: at 84M candidates a metric
 * with a few hundred distinct values ties constantly, and printing those would
 * bury the improvements they are tied with.  The heap still KEEPS ties; this is
 * only about what gets printed. */
static int64_t BEST_KEY = INT64_MAX;
static double  T0;

static void announce(Pair v) {
    int64_t seen;
#ifdef _OPENMP
#pragma omp atomic read
#endif
    seen = BEST_KEY;
    if (v.key >= seen) return;
#ifdef _OPENMP
#pragma omp critical (bestline)
#endif
    {
        if (v.key < BEST_KEY) {
            BEST_KEY = v.key;
            double dt = now_s() - T0;
            if (v.g3 >= 0)
                fprintf(stderr, "[%6.0fs] %s %s %s  ", dt, GWORD[v.g1], GWORD[v.g2],
                        GWORD[v.g3]);
            else
                fprintf(stderr, "[%6.0fs] %s %s  ", dt, GWORD[v.g1], GWORD[v.g2]);
            if (SINGLES)
                fprintf(stderr, "singles=%d  nowin=%d  ssq=%lld  NEW BEST\n",
                        v.singles, v.nowin, (long long)v.ssq);
            else
                fprintf(stderr, "ssq=%lld  NEW BEST\n", (long long)v.ssq);
            fflush(stderr);
        }
    }
}

int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL, *patpath = NULL, *guesslist = NULL;
    const char *extend = NULL;
    int top = 10000, threads = 0, maxg1 = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--top") && i + 1 < argc) top = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        /* Restrict which words may OPEN.  Pointed at mystery.txt this ranks only
         * pairs of answer words, matching the solver's --guess-list restriction
         * for the rest of the game.  The pattern matrix is unchanged: the score
         * is still about how the pair splits the same answer set. */
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc) guesslist = argv[++i];
        /* --extend PAIRS.csv: score TRIPLES instead, by taking every pair in that
         * file and adding every allowed word as a third.  This is a GREEDY
         * extension of a screen that was itself heuristic, so a strong triple
         * whose best 2-word prefix missed the pair cut cannot be found here. */
        else if (!strcmp(argv[i], "--extend") && i + 1 < argc) extend = argv[++i];
        /* --metric singles ranks by the number of SINGLETON joint buckets --
         * pattern combinations exactly one answer produces -- instead of by ssq.
         * Both are computed in the same pass; this only picks the sort key and
         * the output columns.  Higher is better, so the heap's key is negated. */
        /* --disjoint: keep only openers whose words share no letter and repeat
         * none -- 10 distinct letters for a pair, 15 for a triple.  It shrinks
         * the space by ~17x for pairs and ~2600x for triples, which is what
         * makes an EXHAUSTIVE triple sweep possible at all; the answer is then
         * the best DISJOINT opener, a different and smaller claim. */
        else if (!strcmp(argv[i], "--disjoint")) DISJOINT = 1;
        else if (!strcmp(argv[i], "--metric") && i + 1 < argc) {
            const char *m = argv[++i];
            if (!strcmp(m, "singles")) SINGLES = 1;
            else if (strcmp(m, "ssq")) {
                fprintf(stderr, "--metric must be ssq or singles, not %s\n", m);
                return 1;
            }
        }
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        /* TESTING ONLY: restrict the FIRST word to the first N of the guess list,
         * so a correctness check costs seconds instead of the full quadratic run.
         * The output is then NOT a ranking of all pairs -- it is a ranking of the
         * pairs whose lower-indexed word falls in that prefix. */
        else if (!strcmp(argv[i], "--max-g1") && i + 1 < argc) maxg1 = atoi(argv[++i]);
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (!outpath) { fprintf(stderr, "pairsplit needs --out FILE\n"); return 1; }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * 13000);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    if (patpath) snprintf(path, sizeof path, "%s", patpath);
    else         snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    NA = c;
    if (r != NG) { fprintf(stderr, "pattern rows %d != guesses %d\n", r, NG); return 1; }
    widx_build();
    fprintf(stderr, "loaded %d guesses x %d answers\n", NG, NA);

    if (maxg1 > 0)
        fprintf(stderr, "*** --max-g1 %d: TEST MODE, not a ranking of all pairs ***\n", maxg1);
    /* SEL is the set of words allowed to open, as indices into the full guess
     * list -- everything by default. */
    int *sel = malloc(sizeof(int) * NG), nsel = 0;
    if (guesslist) {
        char (*rw)[WBUF] = malloc(sizeof(char[WBUF]) * 13000);
        int nr = load_words(guesslist, rw);
        for (int i = 0; i < nr; i++) {
            int g = find_word(GWORD, NG, rw[i]);
            if (g < 0) {
                fprintf(stderr, "--guess-list word %s is not a legal guess\n", rw[i]);
                return 1;
            }
            sel[nsel++] = g;
        }
        free(rw);
        fprintf(stderr, "openers restricted to %d words from %s\n", nsel, guesslist);
    } else {
        for (int g = 0; g < NG; g++) sel[nsel++] = g;
    }

    build_masks(5);
    if (DISJOINT) {
        /* A word with a repeated letter can never be in a disjoint opener, so
         * drop it from the opener set once here rather than testing it inside
         * the quadratic loop. */
        int kept = 0;
        for (int i = 0; i < nsel; i++)
            if (popcount32(LMASK[sel[i]]) == 5) sel[kept++] = sel[i];
        fprintf(stderr, "--disjoint: %d of %d openers have 5 distinct letters\n",
                kept, nsel);
        nsel = kept;
    }

    int64_t npairs = (int64_t)nsel * (nsel - 1) / 2;
    fprintf(stderr, "ranking %lld unordered pairs by %s, keeping the best %d\n",
            (long long)npairs, SINGLES ? "SINGLETON COUNT" : "ssq", top);

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    int nth = omp_get_max_threads();
#else
    int nth = 1;
#endif
    fprintf(stderr, "threads: %d\n", nth);

    Pair **heaps = calloc(nth, sizeof(Pair *));
    int   *hn    = calloc(nth, sizeof(int));
    /* How many candidates were actually SCORED, per thread.  Not derivable from
     * the inputs once --disjoint or the canonical-parent filter is in play, and
     * it is what tells a later run whether a parent file is complete. */
    int64_t *ranked = calloc(nth, sizeof(int64_t));
    for (int t = 0; t < nth; t++) heaps[t] = malloc(sizeof(Pair) * top);

    double t0 = now_s();
    T0 = t0;
    int64_t done_g1 = 0;

    /* ------------------------------------------------------- TRIPLE MODE ----
     * --extend takes a pair file and adds every allowed word to each pair.
     *
     * The score is the same quantity, one level deeper: the answers are grouped
     * by the JOINT pattern of the two parent words, and each candidate third
     * word is histogrammed inside those groups.  As with pairs the joint
     * partition cannot depend on the order the words are played, so a triple has
     * ONE score, not six, and is emitted once as an unordered set.
     *
     * ORDER STILL MATTERS FOR THE ANSWER, just not for this screen: the exact
     * evaluation that consumes this file must expand each triple to all SIX
     * orderings, exactly as the pair driver expands each pair to two.  Emitting
     * unordered here is a statement about the SCORE, not a claim that order is
     * irrelevant downstream. */
    if (extend) {
        /* GROWS.  This was a fixed 4,000,000 entries with no bounds check, which
         * was silently fine while every parent file came from a --top cut at or
         * below that, and became a heap overflow the moment --disjoint produced
         * 5,020,842 parents: the run died with no message and no output, looking
         * for all the world like it had finished.  A parent count is an INPUT,
         * so it gets no compile-time ceiling. */
        int pcap = 1 << 20, npl = 0;
        Pair *plist = malloc(sizeof(Pair) * pcap);
        if (!plist) { fprintf(stderr, "out of memory for the parent list\n"); return 1; }
        FILE *pf = fopen(extend, "r");
        if (!pf) { fprintf(stderr, "cannot open %s\n", extend); return 1; }
        char line[256];
        while (fgets(line, sizeof line, pf)) {
            char w1[64], w2[64];
            if (sscanf(line, "%63[^,],%63[^,],", w1, w2) != 2) continue;
            int a = lookup_word(w1), b = lookup_word(w2);
            if (a < 0 || b < 0) continue;            /* the header lands here */
            if (npl == pcap) {
                pcap *= 2;
                Pair *grown = realloc(plist, sizeof(Pair) * (size_t)pcap);
                if (!grown) {
                    fprintf(stderr, "out of memory growing the parent list to %d\n", pcap);
                    return 1;
                }
                plist = grown;
            }
            plist[npl].g1 = a; plist[npl].g2 = b; plist[npl].g3 = -1;
            plist[npl].key = 0; plist[npl].ssq = 0; npl++;
        }
        fclose(pf);
        if (!npl) { fprintf(stderr, "no usable pairs in %s\n", extend); return 1; }
        pset_build(plist, npl);
        fprintf(stderr, "extending %d pairs by %d words each = %lld triples "
                "(before canonical-parent filtering)\n",
                npl, nsel, (long long)npl * nsel);

#ifdef _OPENMP
#pragma omp parallel
#endif
        {
#ifdef _OPENMP
            int tid = omp_get_thread_num();
#else
            int tid = 0;
#endif
            Pair *heap = heaps[tid];
            int  *n    = &hn[tid];

            int      *jcnt = calloc((size_t)NPAT * NPAT, sizeof(int));
            int      *jk   = malloc(sizeof(int) * (NA + 1));
            int      *jrs  = malloc(sizeof(int) * (NA + 1));
            int      *jrl  = malloc(sizeof(int) * (NA + 1));
            int      *jfl  = malloc(sizeof(int) * (NA + 1));
            uint16_t *ord  = malloc(sizeof(uint16_t) * NA);
            int      *cnt  = calloc(NPAT, sizeof(int));
            int      *tin  = malloc(sizeof(int) * NPAT);

#ifdef _OPENMP
#pragma omp for schedule(dynamic, 4)
#endif
            for (int pi = 0; pi < npl; pi++) {
                int g1 = plist[pi].g1, g2 = plist[pi].g2;
                const uint8_t *row1 = PAT + (size_t)g1 * NA;
                const uint8_t *row2 = PAT + (size_t)g2 * NA;

                /* group the answers by the pair's JOINT pattern, once */
                int nj = 0;
                for (int a = 0; a < NA; a++) {
                    int key = (int)row1[a] * NPAT + (int)row2[a];
                    if (jcnt[key]++ == 0) jk[nj++] = key;
                }
                int acc = 0;
                for (int t = 0; t < nj; t++) {
                    jrs[t] = acc; jrl[t] = jcnt[jk[t]]; acc += jrl[t];
                }
                for (int t = 0; t < nj; t++) { jcnt[jk[t]] = t; jfl[t] = jrs[t]; }
                for (int a = 0; a < NA; a++)
                    ord[jfl[jcnt[(int)row1[a] * NPAT + (int)row2[a]]]++] = (uint16_t)a;
                for (int t = 0; t < nj; t++) jcnt[jk[t]] = 0;

                int32_t ca = g1 < g2 ? g1 : g2, cb = g1 < g2 ? g2 : g1;

                /* A parent pair that is not itself disjoint can produce no
                 * disjoint triple, so it is skipped whole rather than per word. */
                uint32_t pmask = LMASK[g1] | LMASK[g2];
                if (DISJOINT && popcount32(pmask) != 10) continue;

                for (int sk = 0; sk < nsel; sk++) {
                    int g3 = sel[sk];
                    if (g3 == g1 || g3 == g2) continue;
                    if (DISJOINT && (pmask & LMASK[g3])) continue;

                    /* emit this triple only from its FIRST present parent pair,
                     * so each distinct triple is produced exactly once */
                    int32_t i3 = g1, j3 = g2, k3 = g3;
                    sort3(&i3, &j3, &k3);
                    int rij = pset_rank(i3, j3), rik = pset_rank(i3, k3),
                        rjk = pset_rank(j3, k3);
                    int32_t pa, pb;
                    if      (rij) { pa = i3; pb = j3; }
                    else if (rik) { pa = i3; pb = k3; }
                    else          { pa = j3; pb = k3; }
                    if (pa != ca || pb != cb) continue;
                    /* smallest cut at which this triple becomes reachable */
                    int minpar = 0;
                    if (rij && (!minpar || rij < minpar)) minpar = rij;
                    if (rik && (!minpar || rik < minpar)) minpar = rik;
                    if (rjk && (!minpar || rjk < minpar)) minpar = rjk;

                    ranked[tid]++;
                    const uint8_t *row3 = PAT + (size_t)g3 * NA;
                    int64_t ssq = 0;
                    int32_t singles = 0, nowin = 0;
                    for (int t = 0; t < nj; t++) {
                        int s2 = jrs[t], e2 = s2 + jrl[t], nt = 0;
                        /* jk[t] is the PARENT PAIR's joint key, g1's pattern in
                         * the high trit-block and g2's in the low one -- still
                         * intact here, since only jcnt was cleared. A bucket
                         * already all-green on either parent word is a singleton
                         * the triple did not earn. */
                        int win12 = jk[t] / NPAT == ALL_GREEN || jk[t] % NPAT == ALL_GREEN;
                        for (int i = s2; i < e2; i++) {
                            int pp = row3[ord[i]];
                            if (cnt[pp]++ == 0) tin[nt++] = pp;
                        }
                        for (int i = 0; i < nt; i++) {
                            int pp = tin[i];
                            int64_t v = cnt[pp];
                            ssq += v * v;
                            int one = v == 1;
                            singles += one;
                            nowin += one & !(win12 | (pp == ALL_GREEN));
                            cnt[pp] = 0;
                        }
                    }
                    Pair pv = { SINGLES ? -(int64_t)singles : ssq, ssq,
                                g1, g2, g3, minpar, singles, nowin };
                    if (heap_push(heap, n, top, pv)) announce(pv);
                }

#ifdef _OPENMP
#pragma omp atomic
#endif
                done_g1++;
                if ((done_g1 & 255) == 0) {
                    double el = now_s() - t0;
                    double frac = (double)done_g1 / npl;
                    fprintf(stderr, "  pair %lld/%d  %.1f%%  (%.0fs, eta %.1f min)\n",
                            (long long)done_g1, npl, 100.0 * frac, el,
                            frac > 0 ? (el / frac - el) / 60.0 : 0.0);
                }
            }
            free(jcnt); free(jk); free(jrs); free(jrl); free(jfl);
            free(ord); free(cnt); free(tin);
        }
        goto merge;
    }


#ifdef _OPENMP
#pragma omp parallel
#endif
    {
#ifdef _OPENMP
        int tid = omp_get_thread_num();
#else
        int tid = 0;
#endif
        Pair *heap = heaps[tid];
        int  *n    = &hn[tid];

        int      *cnt   = calloc(NPAT, sizeof(int));
        int      *touch = malloc(sizeof(int) * NPAT);   /* g1 buckets */
        int      *tin   = malloc(sizeof(int) * NPAT);   /* g2 patterns, inner loop */
        uint16_t *ord   = malloc(sizeof(uint16_t) * NA);   /* answers, g1-bucket order */
        int      *rs    = malloc(sizeof(int) * (NPAT + 1));/* run starts */
        int      *rl    = malloc(sizeof(int) * (NPAT + 1));/* run lengths */

        /* schedule(dynamic) because the g2 loop shrinks as g1 grows -- a static
         * split would leave the high-g1 threads idle for most of the run. */
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 8)
#endif
        for (int si = 0; si < (maxg1 > 0 ? maxg1 : nsel); si++) {
            int g1 = sel[si];
            const uint8_t *row1 = PAT + (size_t)g1 * NA;

            /* bucket the answers by g1 once, into contiguous runs */
            int nb = 0;
            for (int a = 0; a < NA; a++)
                if (cnt[row1[a]]++ == 0) touch[nb++] = row1[a];
            int acc = 0;
            for (int k = 0; k < nb; k++) {
                rs[k] = acc; rl[k] = cnt[touch[k]]; acc += rl[k];
            }
            /* reuse cnt[] as pattern -> run index while filling, then clear */
            int *fill = malloc(sizeof(int) * nb);
            for (int k = 0; k < nb; k++) { cnt[touch[k]] = k; fill[k] = rs[k]; }
            for (int a = 0; a < NA; a++) ord[fill[cnt[row1[a]]]++] = (uint16_t)a;
            for (int k = 0; k < nb; k++) cnt[touch[k]] = 0;
            free(fill);

            for (int sj = si + 1; sj < nsel; sj++) {
                int g2 = sel[sj];
                if (DISJOINT && (LMASK[g1] & LMASK[g2])) continue;
                ranked[tid]++;
                const uint8_t *row2 = PAT + (size_t)g2 * NA;
                int64_t ssq = 0;
                int32_t singles = 0, nowin = 0;
                for (int k = 0; k < nb; k++) {
                    int s = rs[k], e = s + rl[k], nt = 0;
                    int win1 = touch[k] == ALL_GREEN;
                    for (int i = s; i < e; i++) {
                        int p = row2[ord[i]];
                        if (cnt[p]++ == 0) tin[nt++] = p;
                    }
                    for (int i = 0; i < nt; i++) {
                        int p = tin[i];
                        int64_t v = cnt[p];
                        ssq += v * v;
                        /* branchless: the drain loop runs once per DISTINCT
                         * pattern, so this rides along with the clear rather
                         * than adding a pass. A bucket that is all-green on
                         * either word is a singleton the pair did not earn --
                         * the answer IS one of the two words -- so nowin drops
                         * it while singles keeps it. */
                        int one = v == 1;
                        singles += one;
                        nowin += one & !(win1 | (p == ALL_GREEN));
                        cnt[p] = 0;
                    }
                }
                Pair pv = { SINGLES ? -(int64_t)singles : ssq, ssq,
                            g1, g2, -1, 0, singles, nowin };
                if (heap_push(heap, n, top, pv)) announce(pv);
            }

#ifdef _OPENMP
#pragma omp atomic
#endif
            done_g1++;
            if ((done_g1 & 255) == 0) {
                /* Work is QUADRATIC in the remaining g1 range -- g1 near NG has
                 * almost no g2 partners left -- so progress must be measured in
                 * PAIRS retired, not in g1 values retired.  Scaling by g1/NG
                 * would report a wildly pessimistic ETA throughout. */
                double el = now_s() - t0;
                double left = (double)(nsel - done_g1) / nsel;
                double frac = 1.0 - left * left;
                fprintf(stderr, "  g1 %lld/%d  %.1f%% of pairs  (%.0fs, eta %.1f min)\n",
                        (long long)done_g1, nsel, 100.0 * frac, el,
                        frac > 0 ? (el / frac - el) / 60.0 : 0.0);
            }
        }
        free(cnt); free(touch); free(tin); free(ord); free(rs); free(rl);
    }

merge: ;   /* a label must precede a statement, not a declaration, before C23 */
    /* merge the per-thread heaps and keep the global best `top` */
    int total = 0;
    for (int t = 0; t < nth; t++) total += hn[t];
    Pair *all = malloc(sizeof(Pair) * total);
    int m = 0;
    for (int t = 0; t < nth; t++)
        for (int i = 0; i < hn[t]; i++) all[m++] = heaps[t][i];
    qsort(all, total, sizeof(Pair), cmp_pair);
    int keep = total < top ? total : top;

    FILE *out = fopen(outpath, "w");
    if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
    if (extend && SINGLES) {
        fprintf(out, "word1,word2,word3,singles,singles_nowin,ssq,minparent\n");
        for (int i = 0; i < keep; i++)
            fprintf(out, "%s,%s,%s,%d,%d,%lld,%d\n", GWORD[all[i].g1], GWORD[all[i].g2],
                    GWORD[all[i].g3], all[i].singles, all[i].nowin,
                    (long long)all[i].ssq, all[i].minpar);
    } else if (extend) {
        fprintf(out, "word1,word2,word3,ssq,minparent\n");
        for (int i = 0; i < keep; i++)
            fprintf(out, "%s,%s,%s,%lld,%d\n", GWORD[all[i].g1], GWORD[all[i].g2],
                    GWORD[all[i].g3], (long long)all[i].ssq, all[i].minpar);
    } else if (SINGLES) {
        /* its own schema, so the ssq screens every downstream tool already reads
         * keep the exact three columns they expect */
        fprintf(out, "word1,word2,singles,singles_nowin,ssq\n");
        for (int i = 0; i < keep; i++)
            fprintf(out, "%s,%s,%d,%d,%lld\n", GWORD[all[i].g1], GWORD[all[i].g2],
                    all[i].singles, all[i].nowin, (long long)all[i].ssq);
    } else {
        fprintf(out, "word1,word2,ssq\n");
        for (int i = 0; i < keep; i++)
            fprintf(out, "%s,%s,%lld\n", GWORD[all[i].g1], GWORD[all[i].g2],
                    (long long)all[i].ssq);
    }
    fclose(out);

    /* ---- the sidecar --------------------------------------------------
     * `<out>.meta` records what this run actually COVERED: how many candidates
     * were scored and how many were written.  A consumer cannot recompute the
     * first from the inputs -- --disjoint and the canonical-parent filter both
     * remove candidates by a rule, not by a count -- so without it there is no
     * way to tell a complete ranking from a truncated one after the fact, and a
     * screen looks exactly like a proof.  It is a SEPARATE file rather than a
     * header line because the CSVs are read by tools that want plain columns. */
    int64_t nranked = 0;
    for (int t = 0; t < nth; t++) nranked += ranked[t];
    char metapath[1200];
    snprintf(metapath, sizeof metapath, "%s.meta", outpath);
    FILE *mf = fopen(metapath, "w");
    if (mf) {
        fprintf(mf, "mode=%s\n", extend ? "triple" : "pair");
        fprintf(mf, "metric=%s\n", SINGLES ? "singles" : "ssq");
        fprintf(mf, "disjoint=%d\n", DISJOINT);
        fprintf(mf, "guesslist=%s\n", guesslist ? guesslist : "");
        fprintf(mf, "openers=%d\n", nsel);
        fprintf(mf, "scored=%lld\n", (long long)nranked);
        fprintf(mf, "written=%d\n", keep);
        fprintf(mf, "complete=%d\n", keep >= nranked ? 1 : 0);
        fclose(mf);
    }
    fprintf(stderr, "scored %lld candidates, wrote %d (%s)\n",
            (long long)nranked, keep,
            keep >= nranked ? "COMPLETE -- every candidate is in the file"
                            : "TRUNCATED -- the file is the head of the ranking");

    if (extend && SINGLES)
        fprintf(stderr, "wrote %d DISTINCT triples to %s in %.0fs (most singletons %d: %s %s %s)\n",
                keep, outpath, now_s() - t0, all[0].singles,
                GWORD[all[0].g1], GWORD[all[0].g2], GWORD[all[0].g3]);
    else if (extend)
        fprintf(stderr, "wrote %d DISTINCT triples to %s in %.0fs (best ssq %lld: %s %s %s)\n",
                keep, outpath, now_s() - t0, (long long)all[0].ssq,
                GWORD[all[0].g1], GWORD[all[0].g2], GWORD[all[0].g3]);
    else if (SINGLES)
        fprintf(stderr, "wrote %d pairs to %s in %.0fs (most singletons %d: %s %s)\n",
                keep, outpath, now_s() - t0, all[0].singles,
                GWORD[all[0].g1], GWORD[all[0].g2]);
    else
        fprintf(stderr, "wrote %d pairs to %s in %.0fs (best ssq %lld: %s %s)\n",
                keep, outpath, now_s() - t0, (long long)all[0].ssq,
                GWORD[all[0].g1], GWORD[all[0].g2]);
    return 0;
}
