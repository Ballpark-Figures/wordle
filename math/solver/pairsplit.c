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
#include <unistd.h>
#if defined(__APPLE__)
#include <sys/sysctl.h>
#endif
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
/* --min-letters M: keep openers whose words cover at least M DISTINCT letters.
 *
 * --disjoint is the maximum of this -- 5 per word, so 20 for a quad -- and is
 * kept as the shorthand for it.  Asking for 19 instead admits one collision
 * anywhere in the opener, which is a much larger space than 20 and a much
 * smaller one than unrestricted, and is not expressible as a disjointness test.
 * MINLET is resolved once the opener size is known, since --disjoint means a
 * different number at every size. */
static int      MINLET = 0;          /* 0 = no letter requirement */
static uint32_t *LMASK;              /* per word, bit i set iff letter i occurs */

/* ---- letter masks, for --disjoint ---------------------------------------
 * bit i of LMASK[g] is set iff word g contains letter i, so a word with a
 * REPEATED letter has fewer than WORDLEN bits.  Two words share no letter iff
 * their masks AND to zero, and a pair reaches 10 distinct letters iff both have
 * 5 bits and overlap nowhere -- which makes the whole test one AND and one
 * branch, cheap enough to sit in front of the scoring loop and reject 94% of
 * pairs before any work happens. */
static int popcount32(uint32_t x) { return __builtin_popcount(x); }

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
#define MAXW 6                   /* words in the largest opener we sweep */

/* The words are an ARRAY, not g1/g2/g3/...  Each time a size was added, every
 * field after the new one shifted under the positional initialisers, which is a
 * silent corruption rather than a compile error.  Unused slots are -1. */
typedef struct {
    int64_t key, ssq;
    int32_t g[MAXW];
    int32_t minpar, singles, nowin;
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
    for (int w = 0; w < MAXW; w++)
        if (x->g[w] != y->g[w]) return x->g[w] < y->g[w] ? -1 : 1;
    return 0;
}


/* ---- set of the PARENT OPENERS, keyed by their sorted word indices --------
 * An opener of k+1 words is reachable from each of its k+1 sub-openers of size
 * k, but only from the ones actually IN the parent list.  Emitting it from the
 * FIRST present sub-opener in a fixed order means every distinct result is
 * produced exactly once, by exactly one (parent, extra word) combination.
 *
 * This replaces generating duplicates and removing them afterwards.  Dedup after
 * the fact needs a guessed over-collection factor, and if the guess is low the
 * output is quietly short of what was asked for -- the same shape of mistake as
 * counting a word list before deduping it. Here the emitted count IS the number
 * of distinct reachable openers, with nothing to tune.
 *
 * The key is positional in base NG, so it is EXACT rather than a hash: with
 * NG <= 12972 a triple key is at most 12972^3 = 2.2e12, well inside 64 bits.
 * Equal keys therefore mean equal openers, and a table hit needs no re-check. */
static uint64_t *PSET;
static int32_t  *PSET_RANK;      /* 1-based rank of that parent in the input file */
static int       PSET_MASK;
static int       PARENTK = 2;    /* words per parent: 2 (pairs) or 3 (triples) */
/* --parents-complete: the parent file holds EVERY parent of its restriction.
 *
 * The hash table above exists to answer "which sub-openers are in the list", so
 * that a result reachable from several of them is emitted exactly once.  When
 * the list is COMPLETE that question has a closed-form answer: every sub-opener
 * is present, so the canonical one is the parent holding the k SMALLEST words,
 * and a result is emitted iff the added word is larger than every word of its
 * parent.  One comparison, no table.
 *
 * Not a micro-optimisation.  For the 138,953,994 disjoint triples the table
 * wants ~12 GB on top of the ~6 GB parent array, which does not fit in 24 GB and
 * turns an exhaustive quad sweep into thrashing; without it the same run is
 * ordinary.  Pass it ONLY when it is true -- on a partial list it silently drops
 * every result whose canonical parent is missing -- which is why the wrapper
 * sets it from the parent's own sidecar rather than from a guess. */
static int       PARENTS_COMPLETE = 0;
/* Total parents in the file, so a STREAMED run can still report a percentage and
 * an ETA.  Streaming does not make the total unknown -- the caller read it from
 * the parent's sidecar before opening the file -- it only means this code cannot
 * derive it by having everything in memory. */
static int64_t   PARENT_COUNT = 0;
/* --top all: keep every scored candidate.
 *
 * The bound is per THREAD, and a fixed one reserves `top` slots in EACH of the
 * 18 threads whether or not they fill -- which is why keeping 25 million rows
 * appeared to need 20 GB and a reduced thread count.  Growing the arrays instead
 * means each thread holds only what it actually produced, so the total is the
 * real row count (about 1.1 GB for those 25 million) no matter how many threads
 * are running.  Everything downstream -- merge, sort, write -- is unchanged. */
static int       TOP_ALL = 0;

/* Physical RAM, or 0 when it cannot be read.  Both hosts this runs on are
 * covered: sysctl on the Macs, sysconf on the WSL desktop. */
static uint64_t phys_mem(void) {
#if defined(__APPLE__)
    uint64_t v = 0; size_t n = sizeof v;
    if (sysctlbyname("hw.memsize", &v, &n, NULL, 0) == 0) return v;
#elif defined(_SC_PHYS_PAGES) && defined(_SC_PAGE_SIZE)
    long pages = sysconf(_SC_PHYS_PAGES), sz = sysconf(_SC_PAGE_SIZE);
    if (pages > 0 && sz > 0) return (uint64_t)pages * (uint64_t)sz;
#endif
    return 0;
}

/* REFUSE A RUN WHOSE KEPT ROWS CANNOT FIT, BEFORE SCORING ANYTHING.
 *
 * Under `--top all` every scored candidate is RETAINED: the per-thread heaps
 * double without bound, so the memory is the candidate count times sizeof(Pair)
 * and it is knowable here, in the first second, from numbers already printed.
 * Nothing downstream can save a run that gets this wrong -- the heap only grows,
 * and on a machine that overcommits `realloc` keeps succeeding while the system
 * thrashes, so the program's own out-of-memory check never fires.
 *
 * MEASURED, 2026-09-17, which is why this exists: a triples run extending
 * 1000000 pairs by 4282 words = 4.28e9 candidates = 223 GB of kept rows, on a
 * 25.8 GB machine with a 3 GB swap file.  It estimated 50 minutes, decayed from
 * 372 parents/s to 2/s as it swapped, and died at 62.8% after 4.75 hours having
 * WRITTEN NOTHING.  Every committed triple ranking was made with an explicit
 * `--top 100000` (their metas say `scored=1288653393 written=100000`); this run
 * inherited the wrapper's `TOP=all`, which is right for the pair stage and
 * ruinous one level down.
 *
 * `--top all` stays legal wherever it fits -- the pair sweep's 9165621 rows are
 * 477 MB and pass -- so this refuses only what could not have worked. */
static void guard_kept_rows(int64_t candidates, const char *what) {
    if (!TOP_ALL || candidates <= 0) return;
    uint64_t need = (uint64_t)candidates * sizeof(Pair);
    uint64_t ram  = phys_mem();
    /* Half of RAM: the pattern matrix, the parent list and the OS also need
     * room, and a run that merely fits would still swap.  A BOUND, not a
     * finding -- it changes what is refused, never what is computed. */
    uint64_t cap = ram ? ram / 2 : (uint64_t)8 << 30;
    if (need <= cap) return;
    fprintf(stderr,
            "\n--top all would keep every one of the %lld %s: %.1f GB of rows\n"
            "  (%zu bytes each), against %.1f GB of RAM.  REFUSING rather than\n"
            "  scoring for hours and dying with nothing written.\n"
            "  Pass --top N to keep the best N instead; every committed triple\n"
            "  ranking here used --top 100000, which costs about %.0f MB.\n",
            (long long)candidates, what, need / 1e9, sizeof(Pair), ram / 1e9,
            100000.0 * sizeof(Pair) * 18 / 1e6);
    exit(1);
}

static void sortk(int32_t *w, int k) {
    for (int i = 1; i < k; i++)              /* k <= 6; insertion is right */
        for (int j = i; j > 0 && w[j - 1] > w[j]; j--) {
            int32_t t = w[j]; w[j] = w[j - 1]; w[j - 1] = t;
        }
}

static uint64_t pkey(const int32_t *sorted, int k) {
    uint64_t key = 0;
    for (int i = 0; i < k; i++) key = key * (uint64_t)NG + (uint64_t)sorted[i];
    return key;
}

/* THE PARENT TABLE IS THE EXPENSIVE PART OF A BIG --extend, AND IT USED TO BE
 * INVISIBLE.  It is a SERIAL open-addressed build -- no OpenMP, nothing to
 * parallelise, since every insert scatters -- sized at four slots per parent,
 * so 12 bytes x 4n of calloc and n random first-touches into it.
 *
 * MEASURED 2026-09-18 on 138953994 disjoint triples: bits = 30, so 8 GB of
 * PSET plus 4 GB of PSET_RANK, and on a 25.8 GB machine with other jobs
 * resident it thrashed at roughly fifty new pages a second -- days, not
 * minutes.  It printed NOTHING while doing it, the parent file was already
 * closed, and `lsof` showed no I/O, so the run looked wedged rather than busy.
 * A stack sample was the only thing that said where it was.
 *
 * So it now REPORTS and it REFUSES.  The refusal names the way out, because
 * there usually is one: the table exists only to deduplicate candidates reached
 * through several parents, and `--parents-complete` replaces it with a rule
 * (the canonical parent holds the smallest PARENTK words) that needs no memory
 * at all.  What blocks that flag is the LETTER LADDER in run-singles.sh's
 * parents_complete_flag, not this code. */
static void pset_build(const Pair *parents, int n) {
    int bits = 1;
    while ((1 << bits) < n * 4) bits++;      /* keep it under 25% loaded */
    PSET_MASK = (1 << bits) - 1;
    uint64_t need = ((uint64_t)PSET_MASK + 1) * (sizeof(uint64_t) + sizeof(int32_t));
    uint64_t ram = phys_mem();
    uint64_t cap = ram ? ram / 3 : (uint64_t)8 << 30;
    fprintf(stderr, "parent table: %d parents -> %llu slots, %.1f GB\n",
            n, (unsigned long long)PSET_MASK + 1, need / 1e9);
    if (need > cap) {
        fprintf(stderr,
            "\nthat table needs %.1f GB of %.1f GB of RAM, and it is built"
            " SERIALLY with\n"
            "one random write per parent -- at this size it thrashes for days"
            " rather than\nminutes.  It exists only to DEDUPLICATE candidates"
            " reachable through several\nparents.\n\n"
            "  --parents-complete replaces it with a rule that needs no memory,"
            " but it is\n"
            "  only sound when every sub-opener of a candidate is in the parent"
            " file.\n"
            "  run-singles.sh checks that (parents_complete_flag) and will say"
            " so.\n\n"
            "  --disjoint instead of --min-letters N is usually the fix: it"
            " lines the\n"
            "  letter demands up, so the shortcut applies and this table is"
            " never built.\n",
            need / 1e9, ram / 1e9);
        exit(1);
    }
    PSET = calloc((size_t)PSET_MASK + 1, sizeof(uint64_t));
    PSET_RANK = calloc((size_t)PSET_MASK + 1, sizeof(int32_t));
    if (!PSET || !PSET_RANK) {
        fprintf(stderr, "out of memory for the %.1f GB parent table\n", need / 1e9);
        exit(1);
    }
    double tb = now_s();
    for (int i = 0; i < n; i++) {
        if ((i & 0xFFFFF) == 0 && i && now_s() - tb >= 1.0) {
            double fr = (double)i / n;
            fprintf(stderr, "  parent table %d/%d  %.1f%%  (%.0fs, eta %.1f min)\n",
                    i, n, 100.0 * fr, now_s() - tb,
                    fr > 0 ? ((now_s() - tb) / fr - (now_s() - tb)) / 60.0 : 0.0);
        }
        int32_t w[MAXW];
        for (int t = 0; t < PARENTK; t++) w[t] = parents[i].g[t];
        sortk(w, PARENTK);
        uint64_t key = pkey(w, PARENTK);
        uint64_t h = (key * 0x9E3779B97F4A7C15ULL) >> 40;
        while (PSET[h & PSET_MASK]) {
            if (PSET[h & PSET_MASK] == key + 1) break;   /* already present */
            h++;
        }
        PSET[h & PSET_MASK] = key + 1;       /* +1 so 0 stays the empty marker */
        PSET_RANK[h & PSET_MASK] = i + 1;    /* the file is in ranked order */
    }
}

/* returns the parent's 1-based rank, or 0 if it is not in the list.  Takes the
 * words already SORTED, since every caller builds them that way. */
static int pset_rank_sorted(const int32_t *sorted) {
    uint64_t key = pkey(sorted, PARENTK);
    uint64_t h = (key * 0x9E3779B97F4A7C15ULL) >> 40;
    for (;;) {
        uint64_t v = PSET[h & PSET_MASK];
        if (!v) return 0;
        if (v == key + 1) return PSET_RANK[h & PSET_MASK];
        h++;
    }
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

/* Progress is TIME-throttled, the same mechanism optturns.c uses (`now_s() -
 * last_report > 30.0`).  The interval differs deliberately: optturns reports on
 * a sweep that runs for days, while these runs finish in seconds to minutes, and
 * a 30s gate would emit two lines for the whole job.  The counter test in front
 * is only there to keep 5 million clock reads out of the loop. */
#define REPORT_SECS 1.0
static double LAST_REPORT;

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
            /* Same shape as optturns.c's NEW BEST lines -- [%7.0fs], two spaces
             * between fields -- so the two solvers read alike.  Two deliberate
             * differences: this stays on stderr, where every other pairsplit
             * status line already goes, and it does NOT print TIED.  optturns
             * can afford TIED because it walks a short candidate list; here a
             * few hundred distinct values across 84M candidates would bury the
             * improvements under their own ties. */
            fprintf(stderr, "[%7.0fs]", dt);
            for (int w = 0; w < MAXW && v.g[w] >= 0; w++)
                fprintf(stderr, " %s", GWORD[v.g[w]]);
            fprintf(stderr, "  ");
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
        if (!strcmp(argv[i], "--top") && i + 1 < argc) {
            const char *v = argv[++i];
            if (!strcmp(v, "all")) { TOP_ALL = 1; top = INT32_MAX; }
            else top = atoi(v);
        }
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
        else if (!strcmp(argv[i], "--min-letters") && i + 1 < argc)
            MINLET = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--parents-complete")) PARENTS_COMPLETE = 1;
        else if (!strcmp(argv[i], "--parent-count") && i + 1 < argc)
            PARENT_COUNT = strtoll(argv[++i], NULL, 10);
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
    if (MINLET > 26) {
        fprintf(stderr, "--min-letters %d is impossible: there are 26 letters\n", MINLET);
        return 1;
    }

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
    /* How many words the RESULT has -- 2 for the pair sweep, parent + 1 when
     * extending.  --disjoint means 5 per word, so it resolves differently at
     * every size and can only be turned into a number here. */
    int nwords_result = extend ? 0 : 2;      /* extend fills this in after the
                                                parent file reveals PARENTK */
    if (DISJOINT && !extend) MINLET = 5 * nwords_result;
    if (MINLET > 0 && !extend) {
        /* A word with a repeated letter can still belong to an opener that only
         * needs M-of-25, so it is dropped ONLY when the demand is the maximum. */
        if (MINLET == 5 * nwords_result) {
            int kept = 0;
            for (int i = 0; i < nsel; i++)
                if (popcount32(LMASK[sel[i]]) == 5) sel[kept++] = sel[i];
            fprintf(stderr, "--min-letters %d: %d of %d openers have 5 distinct letters\n",
                    MINLET, kept, nsel);
            nsel = kept;
        } else {
            fprintf(stderr, "--min-letters %d: repeat-letter words kept, they can "
                    "still reach %d\n", MINLET, MINLET);
        }
    }

    int64_t npairs = (int64_t)nsel * (nsel - 1) / 2;
    fprintf(stderr, "ranking %lld unordered pairs by %s, keeping the best %d\n",
            (long long)npairs, SINGLES ? "SINGLETON COUNT" : "ssq", top);
    guard_kept_rows(npairs, "pairs");

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    int nth = omp_get_max_threads();
#else
    int nth = 1;
#endif
    fprintf(stderr, "threads: %d\n", nth);

    Pair **heaps = calloc(nth, sizeof(Pair *));
    int   *hn    = calloc(nth, sizeof(int));
    int   *hcap  = calloc(nth, sizeof(int));
    /* How many candidates were actually SCORED, per thread.  Not derivable from
     * the inputs once --disjoint or the canonical-parent filter is in play, and
     * it is what tells a later run whether a parent file is complete. */
    int64_t *ranked = calloc(nth, sizeof(int64_t));
    for (int t = 0; t < nth; t++) {
        /* ALWAYS start small and grow. A numeric --top is a CAP on what is kept,
         * not a promise that many will be found, but it used to be allocated in
         * full up front IN EVERY THREAD: --top 100000000 reserved 5.6 GB per
         * thread, 100 GB across 18, which is swap rather than a search. The cap
         * still evicts once the buffer reaches it; it just is not reserved. */
        hcap[t] = 1 << 16;
        if (!TOP_ALL && top < hcap[t]) hcap[t] = top;
        heaps[t] = malloc(sizeof(Pair) * (size_t)hcap[t]);
        if (!heaps[t]) { fprintf(stderr, "out of memory for the result buffer\n"); return 1; }
    }

    double t0 = now_s();
    T0 = t0;
    LAST_REPORT = t0;
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
        /* STREAMED when the parents are complete.
         *
         * Reading the whole list first was fine for a ranked cut someone chose,
         * and absurd for the 138,953,994 disjoint triples: 6 GB of parents held
         * in RAM, several minutes of parsing, and not one candidate scored until
         * all of it was done.  Nothing here needs the list as a WHOLE -- each
         * parent is independent -- so with --parents-complete it is read in
         * chunks and each chunk is worked as it arrives.  Memory is then flat in
         * the parent count and scoring starts immediately.
         *
         * The table path still loads everything, because deciding which
         * sub-opener is canonical genuinely needs to see them all. */
        int pcap = PARENTS_COMPLETE ? (1 << 20) : (1 << 20), npl = 0;
        Pair *plist = malloc(sizeof(Pair) * pcap);
        if (!plist) { fprintf(stderr, "out of memory for the parent list\n"); return 1; }
        FILE *pf = fopen(extend, "r");
        if (!pf) { fprintf(stderr, "cannot open %s\n", extend); return 1; }
        char line[256];
        int64_t nread = 0;          /* parents consumed across every chunk */

        /* fills plist with up to `pcap` parents; returns how many, 0 at EOF */
        #define READ_CHUNK() ({                                                \
            int _n = 0;                                                        \
            while (_n < pcap && fgets(line, sizeof line, pf)) {                \
                char w1[64], w2[64], w3[64], w4[64], w5[64];                    \
                int nf = sscanf(line, "%63[^,],%63[^,],%63[^,],%63[^,],%63[^,],",\
                                w1, w2, w3, w4, w5);                            \
                if (nf < 2) continue;                                          \
                int a = lookup_word(w1), b = lookup_word(w2);                   \
                if (a < 0 || b < 0) continue;      /* the header lands here */  \
                int c = (nf >= 3) ? lookup_word(w3) : -1;                       \
                int d = (nf >= 4) ? lookup_word(w4) : -1;                       \
                int e = (nf >= 5) ? lookup_word(w5) : -1;                       \
                if (nread == 0 && _n == 0)                                      \
                    PARENTK = (e >= 0) ? 5 : (d >= 0) ? 4 : (c >= 0) ? 3 : 2;   \
                if (PARENTK >= 3 && c < 0) continue;                            \
                if (PARENTK >= 4 && d < 0) continue;                            \
                if (PARENTK >= 5 && e < 0) continue;                            \
                plist[_n].g[0] = a; plist[_n].g[1] = b; plist[_n].g[2] = c;      \
                plist[_n].g[3] = d; plist[_n].g[4] = e; plist[_n].g[5] = -1;    \
                plist[_n].key = 0; plist[_n].ssq = 0; _n++;                     \
            }                                                                  \
            _n;                                                                \
        })

        if (!PARENTS_COMPLETE) {
            /* The table needs every parent resident, so read the whole file,
             * growing as it goes.  Deliberately NOT expressed via READ_CHUNK:
             * that fills from index 0, and the pointer juggling needed to make
             * it append was where I put a bug that crashed the load outright. */
            while (fgets(line, sizeof line, pf)) {
                char w1[64], w2[64], w3[64], w4[64], w5[64];
                int nf = sscanf(line, "%63[^,],%63[^,],%63[^,],%63[^,],%63[^,],",
                                w1, w2, w3, w4, w5);
                if (nf < 2) continue;
                int a = lookup_word(w1), b = lookup_word(w2);
                if (a < 0 || b < 0) continue;          /* the header lands here */
                int c = (nf >= 3) ? lookup_word(w3) : -1;
                int d = (nf >= 4) ? lookup_word(w4) : -1;
                int e = (nf >= 5) ? lookup_word(w5) : -1;
                if (npl == 0) PARENTK = (e >= 0) ? 5 : (d >= 0) ? 4 : (c >= 0) ? 3 : 2;
                if (PARENTK >= 3 && c < 0) continue;
                if (PARENTK >= 4 && d < 0) continue;
                if (PARENTK >= 5 && e < 0) continue;
                if (npl == pcap) {
                    pcap *= 2;
                    Pair *grown = realloc(plist, sizeof(Pair) * (size_t)pcap);
                    if (!grown) {
                        fprintf(stderr, "out of memory growing the parent list to %d\n", pcap);
                        return 1;
                    }
                    plist = grown;
                }
                plist[npl].g[0] = a; plist[npl].g[1] = b; plist[npl].g[2] = c;
                plist[npl].g[3] = d; plist[npl].g[4] = e; plist[npl].g[5] = -1;
                plist[npl].key = 0; plist[npl].ssq = 0; npl++;
            }
            fclose(pf);
            if (!npl) { fprintf(stderr, "no usable parents in %s\n", extend); return 1; }
            pset_build(plist, npl);
        } else {
            npl = READ_CHUNK();
            if (!npl) { fprintf(stderr, "no usable parents in %s\n", extend); return 1; }
            fprintf(stderr, "--parents-complete: streaming in chunks of %d, no parent "
                    "table (canonical parent holds the smallest %d words)\n", pcap, PARENTK);
        }
        {
            int nwr = PARENTK + 1;
            if (DISJOINT) MINLET = 5 * nwr;
            if (MINLET == 5 * nwr) {
                int kept = 0;
                for (int i = 0; i < nsel; i++)
                    if (popcount32(LMASK[sel[i]]) == 5) sel[kept++] = sel[i];
                fprintf(stderr, "--min-letters %d: %d of %d openers have 5 distinct letters\n",
                        MINLET, kept, nsel);
                nsel = kept;
            } else if (MINLET > 0) {
                fprintf(stderr, "--min-letters %d over %d words: repeat-letter words kept\n",
                        MINLET, nwr);
            }
        }
        if (PARENTS_COMPLETE)
            fprintf(stderr, "extending %s by %d words each, streaming\n",
                    PARENTK == 5 ? "quints" : PARENTK == 4 ? "quads" :
                    PARENTK == 3 ? "triples" : "pairs", nsel);
        else
            fprintf(stderr, "extending %d %s by %d words each = %lld %s "
                    "(before canonical-parent filtering)\n",
                    npl, PARENTK == 5 ? "quints" : PARENTK == 4 ? "quads" :
                    PARENTK == 3 ? "triples" : "pairs",
                    nsel, (long long)npl * nsel,
                    PARENTK == 5 ? "sextets" : PARENTK == 4 ? "quints" :
                    PARENTK == 3 ? "quads" : "triples");
        guard_kept_rows((int64_t)npl * nsel,
                        PARENTK == 5 ? "sextets" : PARENTK == 4 ? "quints" :
                        PARENTK == 3 ? "quads" : "triples");

      /* One pass over the whole list when it is resident; chunk after chunk when
       * it is streamed.  `pbase` is the running offset, so a parent's rank is
       * still its position in the FILE and not in the chunk it arrived in. */
      int64_t pbase = 0;
      for (;;) {
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

            /* Runs of answers sharing the parent's joint pattern.  Built by
             * SUBDIVIDING one parent word at a time, which needs only the
             * 243-entry counter and works for a parent of any size -- the old
             * dense NPAT*NPAT key was pair-only and could not be extended to
             * triples, where the key space is 14.3 million. */
            int      *jrs  = malloc(sizeof(int) * (NA + 1));
            int      *jrl  = malloc(sizeof(int) * (NA + 1));
            char     *jwin = malloc(NA + 1);   /* run already all-green on a parent word */
            int      *nrs  = malloc(sizeof(int) * (NA + 1));
            int      *nrl  = malloc(sizeof(int) * (NA + 1));
            char     *nwin = malloc(NA + 1);
            int      *jfl  = malloc(sizeof(int) * (NPAT + 1));
            uint16_t *ord  = malloc(sizeof(uint16_t) * NA);
            uint16_t *tmp  = malloc(sizeof(uint16_t) * NA);
            int      *cnt  = calloc(NPAT, sizeof(int));
            int      *tin  = malloc(sizeof(int) * NPAT);

#ifdef _OPENMP
#pragma omp for schedule(dynamic, 4)
#endif
            for (int pi = 0; pi < npl; pi++) {
                int32_t pw[MAXW];
                for (int w = 0; w < PARENTK; w++) pw[w] = plist[pi].g[w];

                /* one run over every answer, then split by each parent word */
                for (int a = 0; a < NA; a++) ord[a] = (uint16_t)a;
                int nj = 1; jrs[0] = 0; jrl[0] = NA; jwin[0] = 0;
                for (int w = 0; w < PARENTK; w++) {
                    const uint8_t *row = PAT + (size_t)pw[w] * NA;
                    int out_nj = 0;
                    for (int t = 0; t < nj; t++) {
                        int st = jrs[t], len = jrl[t], nt = 0;
                        for (int i = st; i < st + len; i++) {
                            int pp = row[ord[i]];
                            if (cnt[pp]++ == 0) tin[nt++] = pp;
                        }
                        int base = st;
                        for (int i = 0; i < nt; i++) { jfl[tin[i]] = base; base += cnt[tin[i]]; }
                        for (int i = st; i < st + len; i++) tmp[jfl[row[ord[i]]]++] = ord[i];
                        int b2 = st;
                        for (int i = 0; i < nt; i++) {
                            int pp = tin[i];
                            nrs[out_nj] = b2; nrl[out_nj] = cnt[pp];
                            /* the flag RIDES the split: once a run is all-green
                             * on some parent word it stays so for every piece */
                            nwin[out_nj] = jwin[t] | (pp == ALL_GREEN);
                            b2 += cnt[pp]; out_nj++;
                            cnt[pp] = 0;
                        }
                    }
                    memcpy(ord, tmp, sizeof(uint16_t) * NA);
                    memcpy(jrs, nrs, sizeof(int) * out_nj);
                    memcpy(jrl, nrl, sizeof(int) * out_nj);
                    memcpy(jwin, nwin, out_nj);
                    nj = out_nj;
                }

                int32_t cw[MAXW];
                for (int w = 0; w < PARENTK; w++) cw[w] = pw[w];
                sortk(cw, PARENTK);

                /* A parent that is not itself disjoint can produce no disjoint
                 * result, so it is skipped whole rather than once per word. */
                uint32_t pmask = 0;
                for (int w = 0; w < PARENTK; w++) pmask |= LMASK[pw[w]];
                /* The best any single word can add is 5 new letters, so a parent
                 * short of MINLET-5 cannot reach the target however it is
                 * extended, and is skipped whole rather than once per word. */
                if (MINLET > 0 && popcount32(pmask) + 5 < MINLET) continue;

                for (int sk = 0; sk < nsel; sk++) {
                    int gx = sel[sk];
                    int dup = 0;
                    for (int w = 0; w < PARENTK; w++) if (gx == pw[w]) dup = 1;
                    if (dup) continue;
                    if (MINLET > 0 && popcount32(pmask | LMASK[gx]) < MINLET) continue;

                    /* Emit only from the FIRST present sub-opener, so each
                     * distinct result is produced exactly once.  Sub-openers are
                     * enumerated by dropping the LAST word first, which is the
                     * order the pair case used and keeps its output unchanged. */
                    int32_t full[MAXW];
                    for (int w = 0; w < PARENTK; w++) full[w] = pw[w];
                    full[PARENTK] = gx;
                    sortk(full, PARENTK + 1);
                    int minpar;
                    if (PARENTS_COMPLETE) {
                        /* every sub-opener is present, so the canonical one is
                         * the k smallest words -- i.e. this parent, iff the
                         * added word is bigger than all of them */
                        if (gx < cw[PARENTK - 1]) continue;
                        /* NOTE the column then means the EMITTING parent's rank,
                         * not the best rank across sub-openers: without the table
                         * the others are unknown.  The sidecar records which. */
                        minpar = (int)(pbase + pi + 1);
                    } else {
                        int32_t canon[MAXW];
                        int chosen = 0;
                        minpar = 0;
                        for (int d = PARENTK; d >= 0; d--) {
                            int32_t sub[MAXW];
                            int m = 0;
                            for (int w = 0; w <= PARENTK; w++) if (w != d) sub[m++] = full[w];
                            int r = pset_rank_sorted(sub);
                            if (!r) continue;
                            if (!minpar || r < minpar) minpar = r;
                            if (!chosen) {
                                chosen = 1;
                                for (int w = 0; w < PARENTK; w++) canon[w] = sub[w];
                            }
                        }
                        int mine = chosen;
                        for (int w = 0; w < PARENTK && mine; w++)
                            if (canon[w] != cw[w]) mine = 0;
                        if (!mine) continue;
                    }

                    ranked[tid]++;
                    const uint8_t *rowx = PAT + (size_t)gx * NA;
                    int64_t ssq = 0;
                    int32_t singles = 0, nowin = 0;
                    for (int t = 0; t < nj; t++) {
                        int s2 = jrs[t], e2 = s2 + jrl[t], nt = 0;
                        int win = jwin[t];
                        for (int i = s2; i < e2; i++) {
                            int pp = rowx[ord[i]];
                            if (cnt[pp]++ == 0) tin[nt++] = pp;
                        }
                        for (int i = 0; i < nt; i++) {
                            int pp = tin[i];
                            int64_t v = cnt[pp];
                            ssq += v * v;
                            int one = v == 1;
                            singles += one;
                            nowin += one & !(win | (pp == ALL_GREEN));
                            cnt[pp] = 0;
                        }
                    }
                    Pair pv;
                    pv.key = SINGLES ? -(int64_t)singles : ssq;
                    pv.ssq = ssq;
                    for (int w = 0; w < PARENTK; w++) pv.g[w] = pw[w];
                    pv.g[PARENTK] = gx;
                    for (int w = PARENTK + 1; w < MAXW; w++) pv.g[w] = -1;
                    pv.minpar = minpar; pv.singles = singles; pv.nowin = nowin;
                    /* Grow while below the cap, then let heap_push evict.
                     * The append MUST go through heap_push: it sifts, and a
                     * plain append would leave the array unheaped, so the first
                     * eviction would compare against a root that is not the
                     * worst kept row and discard the wrong one. */
                    if (hn[tid] == hcap[tid] && (TOP_ALL || hcap[tid] < top)) {
                        int nc = hcap[tid] * 2;
                        if (!TOP_ALL && nc > top) nc = top;
                        hcap[tid] = nc;
                        Pair *g = realloc(heaps[tid], sizeof(Pair) * (size_t)hcap[tid]);
                        if (!g) { fprintf(stderr, "out of memory growing the buffer\n"); exit(1); }
                        heaps[tid] = g;
                    }
                    if (heap_push(heaps[tid], n, TOP_ALL ? hcap[tid] : top, pv))
                        announce(pv);
                }

#ifdef _OPENMP
#pragma omp atomic
#endif
                done_g1++;
                if ((done_g1 & 1023) == 0 && now_s() - LAST_REPORT >= REPORT_SECS) {
                    LAST_REPORT = now_s();
                    double el = now_s() - t0;
                    int64_t tot = PARENT_COUNT > 0 ? PARENT_COUNT : npl;
                    double frac = (double)done_g1 / (double)tot;
                    fprintf(stderr, "  %s %lld/%lld  %.1f%%  (%.0fs, eta %.1f min)\n",
                            PARENTK == 5 ? "quint" : PARENTK == 4 ? "quad" :
                            PARENTK == 3 ? "triple" : "pair",
                            (long long)done_g1, (long long)tot, 100.0 * frac, el,
                            frac > 0 ? (el / frac - el) / 60.0 : 0.0);
                }
            }
            free(jrs); free(jrl); free(jwin); free(nrs); free(nrl); free(nwin);
            free(jfl); free(ord); free(tmp); free(cnt); free(tin);
        }
        pbase += npl;
        if (!PARENTS_COMPLETE) break;          /* the whole list was one pass */
        npl = READ_CHUNK();
        if (!npl) break;
      }
        if (PARENTS_COMPLETE) fclose(pf);
        fprintf(stderr, "extended %lld %s\n", (long long)pbase,
                PARENTK == 5 ? "quints" : PARENTK == 4 ? "quads" :
                PARENTK == 3 ? "triples" : "pairs");
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

            if (MINLET > 0 && popcount32(LMASK[g1]) + 5 < MINLET) continue;
            for (int sj = si + 1; sj < nsel; sj++) {
                int g2 = sel[sj];
                if (MINLET > 0 && popcount32(LMASK[g1] | LMASK[g2]) < MINLET) continue;
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
                Pair pv;
                pv.key = SINGLES ? -(int64_t)singles : ssq;
                pv.ssq = ssq;
                pv.g[0] = g1; pv.g[1] = g2;
                for (int w = 2; w < MAXW; w++) pv.g[w] = -1;
                pv.minpar = 0; pv.singles = singles; pv.nowin = nowin;
                    /* Grow while below the cap, then let heap_push evict.
                 * The append MUST go through heap_push: it sifts, and a
                 * plain append would leave the array unheaped, so the first
                 * eviction would compare against a root that is not the
                 * worst kept row and discard the wrong one. */
                if (hn[tid] == hcap[tid] && (TOP_ALL || hcap[tid] < top)) {
                    int nc = hcap[tid] * 2;
                    if (!TOP_ALL && nc > top) nc = top;
                    hcap[tid] = nc;
                    Pair *g = realloc(heaps[tid], sizeof(Pair) * (size_t)hcap[tid]);
                    if (!g) { fprintf(stderr, "out of memory growing the buffer\n"); exit(1); }
                    heaps[tid] = g;
                }
                if (heap_push(heaps[tid], n, TOP_ALL ? hcap[tid] : top, pv))
                    announce(pv);
            }

#ifdef _OPENMP
#pragma omp atomic
#endif
            done_g1++;
            if ((done_g1 & 63) == 0 && now_s() - LAST_REPORT >= REPORT_SECS) {
                LAST_REPORT = now_s();
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
    /* Merge the per-thread heaps and keep the global best `top`.
     *
     * EACH HEAP IS FREED THE MOMENT IT HAS BEEN COPIED, AND THAT IS WHAT MAKES
     * A LARGE --top RUNNABLE AT ALL.  Every thread holds a bounded heap of
     * `top` entries and at the triple and quad stages they all FILL, so the
     * merge array is the same size again -- holding both at once is
     * `2 x top x sizeof(Pair) x threads`, which at --top 10000000 on 18 threads
     * is 20.2 GB on a 25.8 GB machine.
     *
     * IT IS THE RESIDENT PEAK THIS MOVES, NOT THE RESERVATION, and the
     * distinction is the mechanism: `all` is still malloc'd at full size up
     * front, so the ADDRESS SPACE is 2x either way -- but its pages fault in
     * only as they are written, and each heap (a big allocation, so mmap'd
     * directly and returned to the OS on free) is released as it is drained.
     * So the resident high-water mark is one copy plus one heap, ~10.6 GB at
     * that width instead of 20.2.  Resident is what swaps, which is what
     * killed the --top all run.
     *
     * AND THE TIMING IS THE WHOLE POINT: the merge is the LAST thing a run
     * does, so the old peak arrived AFTER the entire search -- a 30-hour triple
     * stage would have died here having written nothing, the same shape as the
     * --top all death that `guard_kept_rows` exists for.  A heap is dead the
     * instant it is copied and nothing reads `heaps` below this loop, so this
     * cannot change an output. */
    int total = 0;
    for (int t = 0; t < nth; t++) total += hn[t];
    Pair *all = malloc(sizeof(Pair) * total);
    if (!all) {
        fprintf(stderr, "out of memory merging %d kept rows (%.1f GB)\n",
                total, (double)total * sizeof(Pair) / 1e9);
        return 1;
    }
    int m = 0;
    for (int t = 0; t < nth; t++) {
        for (int i = 0; i < hn[t]; i++) all[m++] = heaps[t][i];
        free(heaps[t]);
        heaps[t] = NULL;
    }
    qsort(all, total, sizeof(Pair), cmp_pair);
    int keep = total < top ? total : top;

    FILE *out = fopen(outpath, "w");
    if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
    /* ONE writer for every size.  This was a branch per arity -- pair, triple,
     * quad -- each duplicating the column list, and every new size added another
     * copy to keep in step.  The columns are a function of (how many words, which
     * metric, extend or not), so write them that way. */
    int nw = extend ? PARENTK + 1 : 2;
    for (int w = 0; w < nw; w++) fprintf(out, "%sword%d", w ? "," : "", w + 1);
    if (SINGLES) fprintf(out, ",singles,singles_nowin,ssq");
    else         fprintf(out, ",ssq");
    if (extend)  fprintf(out, ",minparent");
    fprintf(out, "\n");
    for (int i = 0; i < keep; i++) {
        for (int w = 0; w < nw; w++)
            fprintf(out, "%s%s", w ? "," : "", GWORD[all[i].g[w]]);
        if (SINGLES) fprintf(out, ",%d,%d,%lld", all[i].singles, all[i].nowin,
                             (long long)all[i].ssq);
        else         fprintf(out, ",%lld", (long long)all[i].ssq);
        if (extend)  fprintf(out, ",%d", all[i].minpar);
        fprintf(out, "\n");
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
        fprintf(mf, "mode=%s\n", extend ? (PARENTK == 5 ? "sextet" :
                PARENTK == 4 ? "quint" : PARENTK == 3 ? "quad" : "triple") : "pair");
        fprintf(mf, "metric=%s\n", SINGLES ? "singles" : "ssq");
        fprintf(mf, "disjoint=%d\n", DISJOINT);
        /* The letter demand IN FORCE, so a later stage can decide whether this
         * file contains every sub-opener its own targets need. */
        fprintf(mf, "min_letters=%d\n", MINLET);
        fprintf(mf, "guesslist=%s\n", guesslist ? guesslist : "");
        fprintf(mf, "openers=%d\n", nsel);
        fprintf(mf, "scored=%lld\n", (long long)nranked);
        fprintf(mf, "written=%d\n", keep);
        fprintf(mf, "complete=%d\n", keep >= nranked ? 1 : 0);
        fprintf(mf, "parents_complete=%d\n", PARENTS_COMPLETE);
        if (extend)
            fprintf(mf, "minparent_meaning=%s\n",
                    PARENTS_COMPLETE ? "emitting-parent" : "best-of-sub-openers");
        fclose(mf);
    }
    fprintf(stderr, "scored %lld candidates, wrote %d (%s)\n",
            (long long)nranked, keep,
            keep >= nranked ? "COMPLETE -- every candidate is in the file"
                            : "TRUNCATED -- the file is the head of the ranking");

    char lead[80];
    int lp = 0;
    for (int w = 0; w < nw; w++)
        lp += snprintf(lead + lp, sizeof lead - lp, "%s%s", w ? " " : "",
                       GWORD[all[0].g[w]]);
    const char *what = extend ? (PARENTK == 5 ? "sextets" : PARENTK == 4 ? "quints" :
                                 PARENTK == 3 ? "quads" : "triples") : "pairs";
    if (SINGLES)
        fprintf(stderr, "wrote %d %s%s to %s in %.0fs (most singletons %d: %s)\n",
                keep, extend ? "DISTINCT " : "", what, outpath, now_s() - t0,
                all[0].singles, lead);
    else
        fprintf(stderr, "wrote %d %s%s to %s in %.0fs (best ssq %lld: %s)\n",
                keep, extend ? "DISTINCT " : "", what, outpath, now_s() - t0,
                (long long)all[0].ssq, lead);
    return 0;
}
