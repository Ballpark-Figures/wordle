/* antistall.c -- the antiwordle STALLING ENDGAME, exactly, for every answer.
 *
 * THE PROBLEM.  Antiwordle reverses Wordle: the word is fixed, you lose the turn
 * you play it, and the score is how long you survived.  Once the candidate set
 * has collapsed to one word you KNOW the answer, so every reply is already
 * determined and the game stops being probabilistic.  What is left is: how long
 * can you keep playing LEGAL words that are not the answer?  That is a longest
 * path, and this program computes it exactly -- no depth cap, because antiwordle
 * has none, and no beam, because a restricted search would not be the maximum.
 *
 * THIS IS THE |S| = 1 ENDGAME ONLY.  A player who does not yet know the word
 * cannot in general achieve these lengths, so a number here is an UPPER BOUND on
 * what that answer yields in real play.  Never average them and call the result
 * "expected guesses in antiwordle".
 *
 * -------------------------------------------------------------- the model
 *
 * The rules are three constraints on the next guess: a red letter is pinned to
 * its square, a yellow letter must be reused but never again on the square it was
 * yellow on, and a grey tile means THAT COPY of the letter does not exist -- a
 * COUNT CAP, not a letter ban.  (Wordle marks greens first and hands out spare
 * copies left to right, so a grey tile on c means the answer holds exactly as many
 * c's as that guess showed red or yellow.  The familiar "the letter is dead" is
 * just the cap at zero.)  math/antiwordle.py carries the long form and the proofs;
 * tools/checkantiwordle.py gates it.
 *
 * WHY THERE IS NO CONSTRAINT STRUCT HERE, unlike optturns' hard mode.  Playing g
 * turns constraint C into C and D(g), where D(g) -- the greens, ban bits and count
 * caps that guess's feedback imposes -- is fixed by (g, its feedback) and NEVER
 * consults C.  A word already legal under C survives exactly when it satisfies
 * D(g), every field being a conjunction.  So with the answer fixed, D(g) can be
 * precomputed ONCE as a bitset over the word list, and the whole search collapses
 * to intersections:
 *
 *     child legal set = parent legal set & DELTA[g]
 *
 * The state is the LEGAL SET and nothing else -- which is also why the memo is
 * keyed on it.  Keying on the constraint instead re-searches the same position
 * many times over; measured in the Python prototype, that alone was 10x.
 *
 * ---------------------------------------------------------------- bounds
 *
 * Two admissible upper bounds, whichever is smaller, both from the fact that every
 * legal non-answer guess STRICTLY tightens the constraint (a yellow bans a square
 * that cannot already have been banned, or a grey pins a count that can be pinned
 * only once):
 *
 *   THE WORD BOUND, nL.  Legality only tightens, so every word played from here on
 *   is legal now; and a played word is never legal again, so they are all distinct.
 *   The game cannot outlast the legal set.
 *
 *   THE RESOURCE BOUND, pool + 1.  Each guess spends one unit per distinct grey
 *   letter plus one per yellow tile, out of a finite supply -- letters not yet
 *   count-pinned, squares not yet banned for the answer's own letters.  About 50 at
 *   an empty board, where the word bound is a useless 12972.
 *
 * Neither is passed down as a window, so nothing memoised is a bound and the table
 * stays reusable.  --no-prune disables both, leaving the exhaustive search as an
 * oracle; tools/checkantistall.py diffs this program against antiwordle.py.
 *
 * ---------------------------------------------------------------- running
 *
 *     bash solver/run-antistall-sweep.sh              # from math/ -- USE THIS
 *
 * The binary REFUSES to start without --out or an explicit --no-out: a run that
 * prints its answer and saves NOTHING is a run thrown away, and this repo has
 * already lost a day of multi-hour runs that way.
 *
 * RESULTS ARE FOR OUR WORD LISTS, which are NOT verified to be antiwordle.com's,
 * and the stalling words are the junk most likely to differ between them.
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

/* MAXG bounds the GUESS list: 12972 at 5 letters, with slack for a subset list. */
#ifndef MAXG
#define MAXG       13000
#endif
#ifndef MAXA
#define MAXA       13000
#endif

#define BSW  ((MAXG + 63) / 64)          /* uint64 words spanning all guesses */

/* MAXD bounds the RECURSION, and unlike optturns' MAXD it is not a modelling
 * choice: antiwordle has no depth cap and this program imposes none.  It is an
 * array bound only, and the resource bound caps a real line well under it -- every
 * move spends a count-pin (at most 26) or a square-ban (at most 5 answer letters x
 * 5 squares), so no line can exceed about 51 moves.  64 leaves headroom and costs
 * ~104 KB of per-thread arena.  Overrunning it is a hard error, never a silent
 * truncation of the answer. */
#define MAXD       64

typedef uint8_t pat_t;

static int      NG, NA;
static pat_t   *PAT;                     /* NG * NA, row-major: PAT[g*NA + a] */
static char   (*GWORD)[WBUF];
static char   (*AWORD)[WBUF];
static int      ANS2G[MAXA];             /* answer index -> its index in the guess list */

static uint64_t BS_POS[WORDLEN][26][BSW];      /* guesses with letter c at square i */
static uint64_t BS_CNT[26][WORDLEN + 1][BSW];  /* guesses with >= k copies of c */
static uint64_t BS_ALL[BSW];                   /* every legal guess; NG..MAXG-1 clear */

static int PRUNE = 1;                    /* --no-prune drops both bounds */
static int LONGEST = 0;                  /* --longest: the max over answers only */
/* --show-bound prints the letters bound at the START state and exits.
 *
 * It exists because a bound that never fires is INDISTINGUISHABLE from a bound
 * that is silently broken: values, node counts and every gate come out identical
 * either way. So the implementation has to be checked directly against the
 * reference rather than inferred from the search agreeing. */
static int SHOWBOUND = 0;
static long long MAXNODES = 0;           /* --max-nodes, 0 = unlimited */

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
 * optturns' design: 128 bits of key per entry, the second half stored XORed with
 * the payload, so an entry torn by a concurrent writer fails verification and
 * reads as a miss rather than a wrong value.  With 128-bit keys a collision is
 * not a practical concern, which matters here because the true key -- a 12972-bit
 * legal set -- is far too big to store. */

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

static inline int tt_get(uint64_t h0, uint64_t h1, int *val, int *bestg) {
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

static inline void tt_put(uint64_t h0, uint64_t h1, int val, int bestg) {
    if (TT_OFF) return;
    Entry e;
    e.h0 = h0; e.val = val; e.bestg = bestg;
    e.h1x = h1 ^ tt_payload(val, bestg);
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    b[1] = b[0];                          /* slot 0 newest, slot 1 the previous */
    b[0] = e;
}

/* ------------------------------------------------------- per-answer setup */

/* CPU time is the wrong clock once threads exist: clock() sums across them and
 * would report a 20-thread run as taking 20x as long as it did. */
static double wall_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

typedef struct { int bound, g; } Cand;

typedef struct {
    uint64_t *delta;              /* NG * BSW -- the words each guess still allows */
    int      *spent;              /* NG -- resource units each guess costs */
    uint32_t *lmask;              /* NG -- 26-bit set of letters the guess uses */
    uint8_t  *gmask;              /* NG -- squares this guess turns green */
    uint64_t  arena[MAXD][BSW];   /* the legal set at each recursion level */
    uint64_t  scratch[BSW];       /* one child, built then measured */
    Cand     *cand;               /* MAXD * NG -- children awaiting pass 2 */
    uint64_t *dedup;              /* one node's child hashes; see below */
    uint32_t *dstamp;             /* which node wrote each slot */
    uint32_t  stamp;              /* bumped per node instead of clearing dedup */
    int       dedup_mask;
    int       answer_g;           /* the answer's index in the guess list */
    uint64_t  salt;               /* separates one answer's TT entries from another's */
    long long nodes, edges, pruned;
    /* Heartbeat: a single answer can search for half an hour, and silence for
     * that long is indistinguishable from a hang. */
    const char *cur_answer;
    int         cur_need;
    double      cur_t0;
    long long   next_beat;
    int       overflow;           /* recursion hit MAXD -- a hard error, not a cap */
    int       budget_blown;       /* --max-nodes hit; the verdict is UNKNOWN, not "no" */
} Ctx;

/* One dedup table per THREAD, not per depth: pass 1 at a level finishes entirely
 * before pass 2 starts recursing, and pass 2 never consults it again, so a deeper
 * level is free to reuse the same memory.
 *
 * Slots are STAMPED with a per-node counter rather than cleared.  Clearing would
 * mean a 256 KB memset at every node -- larger than the work the node itself does,
 * and it would have quietly become the whole runtime. */
#define DEDUP_BITS 15
#define DEDUP_SIZE (1 << DEDUP_BITS)

static void ctx_free(Ctx *c) {
    free(c->delta); free(c->spent); free(c->cand);
    free(c->dedup); free(c->dstamp); free(c->lmask); free(c->gmask);
    free(c);
}

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    c->delta  = malloc((size_t)NG * BSW * sizeof(uint64_t));
    c->spent  = malloc((size_t)NG * sizeof(int));
    c->lmask  = malloc((size_t)NG * sizeof(uint32_t));
    c->gmask  = malloc((size_t)NG * sizeof(uint8_t));
    c->cand   = malloc((size_t)MAXD * NG * sizeof(Cand));
    c->dedup  = malloc((size_t)DEDUP_SIZE * sizeof(uint64_t));
    c->dstamp = calloc((size_t)DEDUP_SIZE, sizeof(uint32_t));
    c->dedup_mask = DEDUP_SIZE - 1;
    c->stamp = 0;
    if (!c->delta || !c->spent || !c->cand || !c->dedup || !c->dstamp
            || !c->lmask || !c->gmask) {
        fprintf(stderr, "out of memory for a search context\n"); exit(1);
    }
    return c;
}

/* Descending by bound, ties on the lowest guess index -- the same rule the Python
 * reference uses, so the two agree on WHICH optimal line they report and not just
 * on its length. */
static int cand_cmp(const void *x, const void *y) {
    const Cand *p = x, *q = y;
    if (p->bound != q->bound) return q->bound - p->bound;
    return p->g - q->g;
}

/* Build DELTA[g] and spent[g] for one answer.
 *
 * DELTA[g] is the set of words permitted by g's feedback ALONE -- greens pinned,
 * revealed counts as floors, grey tiles as ceilings, yellow squares banned.  The
 * search then never needs the feedback again, only the intersection. */
static void ctx_load_answer(Ctx *c, int ai) {
    c->answer_g = ANS2G[ai];
    c->salt = ((uint64_t)ai + 1) * 0x9E3779B97F4A7C15ULL;
    c->nodes = c->edges = c->pruned = 0;
    c->overflow = 0;
    c->budget_blown = 0;
    c->cur_answer = AWORD[ai];
    c->next_beat = 0;

    const pat_t *col = PAT;
    for (int g = 0; g < NG; g++) {
        int p = col[(size_t)g * NA + ai];
        int req[26] = { 0 }, grey[26] = { 0 }, yban[26] = { 0 };
        int green[WORDLEN];
        int yellows = 0;
        for (int i = 0; i < WORDLEN; i++) green[i] = -1;
        for (int i = 0, div = NPAT / 3; i < WORDLEN; i++, div /= 3) {
            int t = (p / div) % 3;               /* 0 grey, 1 yellow, 2 green */
            int ch = GWORD[g][i] - 'a';
            if (t == 2)      { green[i] = ch; req[ch]++; }
            else if (t == 1) { req[ch]++; yban[ch] |= 1 << i; yellows++; }
            else             grey[ch] = 1;
        }

        uint64_t *d = c->delta + (size_t)g * BSW;
        memcpy(d, BS_ALL, sizeof BS_ALL);
        for (int i = 0; i < WORDLEN; i++)
            if (green[i] >= 0)
                for (int w = 0; w < BSW; w++) d[w] &= BS_POS[i][green[i]][w];
        int greys = 0;
        for (int ch = 0; ch < 26; ch++) {
            if (req[ch])
                for (int w = 0; w < BSW; w++) d[w] &= BS_CNT[ch][req[ch]][w];
            if (grey[ch]) {
                greys++;
                /* a grey tile pins the count EXACTLY at what the guess revealed */
                for (int w = 0; w < BSW; w++) d[w] &= ~BS_CNT[ch][req[ch] + 1][w];
            }
            if (yban[ch])
                for (int i = 0; i < WORDLEN; i++)
                    if (yban[ch] >> i & 1)
                        for (int w = 0; w < BSW; w++) d[w] &= ~BS_POS[i][ch][w];
        }
        c->spent[g] = greys + yellows;

        /* For the LETTERS BOUND. lmask is every letter the guess plays, so OR-ing
         * it down a line tracks which letters have been used at all; gmask is the
         * squares it pins green. Both are per-answer, since greenness is. */
        uint32_t lm = 0;
        uint8_t gm = 0;
        for (int i = 0; i < WORDLEN; i++) {
            lm |= 1u << (GWORD[g][i] - 'a');
            if (green[i] >= 0) gm |= (uint8_t)(1u << i);
        }
        c->lmask[g] = lm;
        c->gmask[g] = gm;

        /* The answer is legal under every feedback it could itself produce; if it
         * were not, play could dead-end and the whole search would be ill-posed. */
        int a = c->answer_g;
        if (g != a && !((d[a >> 6] >> (a & 63)) & 1)) {
            fprintf(stderr, "internal: answer %s excluded by %s's own feedback\n",
                    AWORD[ai], GWORD[g]);
            exit(1);
        }
    }
}

/* The resource pool at an empty board: every letter's count unpinned, every square
 * still open to a yellow of each answer letter that does not already sit there. */
static int pool_start(int ai) {
    const char *a = AWORD[ai];
    int acount[26] = { 0 };
    for (int i = 0; i < WORDLEN; i++) acount[a[i] - 'a']++;
    int pool = 0;
    for (int ch = 0; ch < 26; ch++)
        if (WORDLEN > acount[ch]) pool++;          /* count not yet pinned */
    for (int i = 0; i < WORDLEN; i++)
        for (int ch = 0; ch < 26; ch++)
            if (acount[ch] && ch != a[i] - 'a') pool++;   /* square open to a yellow */
    return pool;
}

/* --------------------------------------------------------------- the search */

/* Murmur3's 64-bit finalizer: full avalanche, so one changed input bit changes
 * about half the output bits. */
static inline uint64_t mix64(uint64_t z) {
    z ^= z >> 33; z *= 0xFF51AFD7ED558CCDULL;
    z ^= z >> 33; z *= 0xC4CEB9FE1A85EC53ULL;
    z ^= z >> 33;
    return z;
}

/* Intersect the parent's legal set with DELTA[g], returning the popcount and
 * fingerprinting the result in the same pass.
 *
 * The fingerprint is over the bitset WORDS, not the member indices: that is
 * O(BSW) = 203 regardless of how many words are live, where a Zobrist-style fold
 * over members would be O(n) and cost thousands of operations near the top of a
 * game.
 *
 * THE TWO HALVES MUST BE INDEPENDENT, and getting that wrong is not a
 * performance question -- the fingerprint IS the memo key, since the true key (a
 * 12972-bit legal set) is far too big to store, so a collision silently returns
 * another position's value.  The first version of this folded both halves from
 * the same per-word quantity with near-identical FNV steps, which left them
 * CORRELATED: nominally 128 bits of key, in practice far fewer, and it collided
 * on a real 2315-word search (mummy came back 11 against a true 12).  So each
 * word is avalanched once, then accumulated into the two halves by DIFFERENT
 * operations, and both are finalized.
 *
 * Cost is one mix64 per NON-ZERO word, and the sets are sparse everywhere except
 * near the root, so it lands where the node counts are smallest. */
static inline int intersect(const uint64_t *parent, const uint64_t *d,
                            uint64_t *out, uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0x243F6A8885A308D3ULL, b = 0x13198A2E03707344ULL;
    int n = 0;
    for (int w = 0; w < BSW; w++) {
        uint64_t x = parent[w] & d[w];
        out[w] = x;
        if (x) {
            n += __builtin_popcountll(x);
            uint64_t m = mix64(x ^ (0x9E3779B97F4A7C15ULL * (uint64_t)(w + 1)));
            a ^= m;
            a = a * 0x100000001B3ULL + 0x9E3779B97F4A7C15ULL;
            b += m;
            b ^= b >> 29;
            b *= 0xBF58476D1CE4E5B9ULL;
        }
    }
    *h0 = mix64(a);
    *h1 = mix64(b ^ 0xC2B2AE3D27D4EB4FULL);
    return n;
}

/* THE LETTERS BOUND: untouched letters, plus squares not yet pinned green.
 *
 * Every guess either introduces a letter never played before, or -- using only
 * letters already seen -- moves a yellow onto a square it has not occupied. The
 * first kind is capped by the letters still untouched, the second by the squares
 * still not green. Counting guesses INCLUSIVE of the final naming move is what
 * makes the constant come out as a plain sum with no -1.
 *
 * It cannot fall below 1 in any reachable state: only the answer itself shows
 * five greens, so at least one square is always non-green.
 *
 * MEASURED (tools/auditbound.py) at mean slack 12.1 against exact values over
 * 186521 reachable states, where the resource bound sits at 29.0 -- and the two
 * taken together are never tighter than this one alone. Carried by OR rather than
 * recomputed, exactly as `pool` is carried by subtraction; neither enters the memo
 * key, since both only ever bound, and the value depends on the legal set alone. */
#define ALPHA_MASK 0x03FFFFFFu           /* 26 bits, one per letter */

static inline int letters_bound(uint32_t used, uint8_t grn) {
    return __builtin_popcount(ALPHA_MASK & ~used)
         + (WORDLEN - __builtin_popcount((uint32_t)grn));
}

static int value(Ctx *c, int depth, int nL, uint64_t h0, uint64_t h1,
                 int pool, uint32_t used, uint8_t grn) {
    int val, bestg;
    if (tt_get(h0, h1, &val, &bestg)) return val;
    if (nL <= 1) return 1;                    /* only the answer is playable */
    if (depth + 1 >= MAXD) { c->overflow = 1; return 1; }
    if (MAXNODES && c->nodes >= MAXNODES) return -1;   /* abandoned; see solve_one */

    c->nodes++;
    const uint64_t *L = c->arena[depth];
    int ceiling = nL;
    if (PRUNE) {
        if (pool + 1 < ceiling) ceiling = pool + 1;
        int lb = letters_bound(used, grn);
        if (lb < ceiling) ceiling = lb;
    } else {
        ceiling = nL + 1;                 /* unreachable: every branch explored */
    }

    /* PASS 1 -- expand every legal guess into its child, deduplicating by the
     * child's LEGAL SET.  Two guesses that leave the same words playable leave the
     * same game, whatever feedback produced them, so this is a coarser and
     * strictly better collapse than deduplicating by the feedback itself. */
    Cand *cand = c->cand + (size_t)depth * NG;
    int ncand = 0;
    uint32_t stamp = ++c->stamp;
    for (int w = 0; w < BSW; w++) {
        uint64_t bits = L[w];
        while (bits) {
            int g = (w << 6) + __builtin_ctzll(bits);
            bits &= bits - 1;
            if (g == c->answer_g) continue;

            uint64_t ch0, ch1;
            int nC = intersect(L, c->delta + (size_t)g * BSW, c->scratch, &ch0, &ch1);
            int slot = (int)(ch0 & c->dedup_mask), seen = 0;
            for (int probe = 0; probe < DEDUP_SIZE; probe++) {
                if (c->dstamp[slot] != stamp) {
                    c->dstamp[slot] = stamp;
                    c->dedup[slot] = ch0;
                    break;
                }
                if (c->dedup[slot] == ch0) { seen = 1; break; }
                slot = (slot + 1) & c->dedup_mask;
            }
            if (seen) continue;

            int cpool = pool - c->spent[g];
            int bound = nC;
            if (PRUNE) {
                if (cpool + 1 < bound) bound = cpool + 1;
                int lb = letters_bound(used | c->lmask[g], grn | c->gmask[g]);
                if (lb < bound) bound = lb;
            }
            cand[ncand].bound = bound;
            cand[ncand].g = g;
            ncand++;
        }
    }

    /* PASS 2 -- best bound first, so the incumbent climbs fast and the tail of
     * the list can be cut wholesale. */
    qsort(cand, ncand, sizeof(Cand), cand_cmp);

    int best = 1, best_move = -1;             /* name the answer now and be done */
    for (int i = 0; i < ncand; i++) {
        if (PRUNE && 1 + cand[i].bound <= best) { c->pruned += ncand - i; break; }
        int g = cand[i].g;
        uint64_t ch0, ch1;
        int nC = intersect(L, c->delta + (size_t)g * BSW, c->arena[depth + 1],
                           &ch0, &ch1);
        c->edges++;
        int v = value(c, depth + 1, nC, ch0 ^ c->salt, ch1 ^ c->salt,
                      pool - c->spent[g], used | c->lmask[g], grn | c->gmask[g]);
        if (v < 0) return -1;                 /* node budget blown, unwind */
        v += 1;
        if (v > best) {
            best = v; best_move = g;
            if (PRUNE && best >= ceiling) break;
        }
    }
    tt_put(h0, h1, best, best_move);
    return best;
}

/* ------------------------------------------- the longest game (--longest)
 *
 * A DIFFERENT QUESTION from the per-answer sweep, and a far cheaper one: not
 * "how long does each answer last" but "how long can ANY game last".  Only the
 * maximum over answers is wanted, so no answer's exact value has to be computed
 * -- each one only has to be asked whether it BEATS the best found so far, and a
 * decision problem prunes vastly harder than an optimisation, because a whole
 * subtree dies the moment it cannot reach the target rather than when it has been
 * fully measured.
 *
 * TWO PHASES.
 *
 *   A. A greedy playout per answer -- always move to the child that keeps the most
 *      words alive.  Cheap, and it does two jobs: it is an achievable LOWER bound,
 *      so the incumbent starts high instead of at 1, and it gives the sweep a
 *      DERIVED visit order (best greedy first) rather than word-list order, which
 *      is what gets the true maximum found early.  Greedy quality affects only
 *      SPEED: the incumbent is achievable whatever it is, and the exact test below
 *      is what establishes the answer.
 *
 *   B. For each answer in that order, `can_reach(need)` with need = incumbent + 1.
 *      A pass raises the incumbent (and is re-tested at the new bar until it
 *      fails); a fail retires that answer for good.
 *
 * ONE PASS SUFFICES EVEN THOUGH THE INCUMBENT RISES MID-SWEEP.  can_reach is
 * monotone in `need`: an answer that cannot reach k cannot reach anything larger,
 * so an answer retired early against a lower bar stays retired against the final
 * one.  Nothing has to be revisited.
 *
 * THE MEMO KEY CARRIES THE BUDGET, so every entry stays EXACT -- "this set can /
 * cannot reach b" is a fact about (set, b), not a bound that depends on where the
 * search happened to be when it was written.  That is deliberate: seeding a
 * maximising search with a floor instead makes its memoised values upper bounds
 * rather than values, and storing those as if exact silently corrupts every later
 * lookup.  Budgeted booleans avoid the whole class of bug.
 */

/* Longest line greedy play finds, and an achievable lower bound on the answer's
 * true value.  Ties on the lowest guess index, as everywhere else. */
static int greedy_len(Ctx *c, int nL, const uint64_t *start) {
    uint64_t cur[BSW];
    memcpy(cur, start, sizeof cur);
    int len = 1;                              /* the forced naming move */
    for (int step = 0; step < MAXD - 2; step++) {
        int bestg = -1, bestn = -1;
        for (int w = 0; w < BSW; w++) {
            uint64_t bits = cur[w];
            while (bits) {
                int g = (w << 6) + __builtin_ctzll(bits);
                bits &= bits - 1;
                if (g == c->answer_g) continue;
                uint64_t d0, d1;
                int nC = intersect(cur, c->delta + (size_t)g * BSW, c->scratch,
                                   &d0, &d1);
                if (nC > bestn) { bestn = nC; bestg = g; }
            }
        }
        if (bestg < 0) return len;            /* only the answer is playable */
        uint64_t d0, d1;
        nL = intersect(cur, c->delta + (size_t)bestg * BSW, c->scratch, &d0, &d1);
        memcpy(cur, c->scratch, sizeof cur);
        len++;
    }
    return len;
}

/* Is there a line of at least `need` guesses (the naming move included)? */
static int can_reach(Ctx *c, int depth, int nL, uint64_t h0, uint64_t h1,
                     int pool, int need, uint32_t used, uint8_t grn) {
    if (need <= 1) return 1;                  /* the answer is always playable */
    if (nL < need) return 0;                  /* word bound */
    if (pool + 1 < need) return 0;            /* resource bound */
    if (letters_bound(used, grn) < need) return 0;   /* letters bound */
    if (depth + 1 >= MAXD) { c->overflow = 1; return 0; }
    if (MAXNODES && c->nodes >= MAXNODES) { c->budget_blown = 1; return 0; }

    /* Heartbeat. One answer can search for half an hour, and silence that long is
     * indistinguishable from a hang. The counter test is a plain compare against a
     * precomputed threshold, so it costs nothing in the hot path. */
    if (c->nodes >= c->next_beat) {
        if (c->next_beat)
            printf("        ... %s still trying for %d: %lld nodes, %.0fs\n",
                   c->cur_answer, c->cur_need, c->nodes,
                   wall_time() - c->cur_t0);
        c->next_beat = c->nodes + 4000000;
        fflush(stdout);
    }

    uint64_t k0 = h0 ^ (uint64_t)need * 0x9E3779B97F4A7C15ULL;
    uint64_t k1 = h1 ^ (uint64_t)need * 0xC2B2AE3D27D4EB4FULL;
    int val, bestg;
    if (tt_get(k0, k1, &val, &bestg)) return val;

    c->nodes++;
    const uint64_t *L = c->arena[depth];
    Cand *cand = c->cand + (size_t)depth * NG;
    int ncand = 0;
    uint32_t stamp = ++c->stamp;
    for (int w = 0; w < BSW; w++) {
        uint64_t bits = L[w];
        while (bits) {
            int g = (w << 6) + __builtin_ctzll(bits);
            bits &= bits - 1;
            if (g == c->answer_g) continue;
            uint64_t ch0, ch1;
            int nC = intersect(L, c->delta + (size_t)g * BSW, c->scratch, &ch0, &ch1);
            int slot = (int)(ch0 & c->dedup_mask), seen = 0;
            for (int probe = 0; probe < DEDUP_SIZE; probe++) {
                if (c->dstamp[slot] != stamp) {
                    c->dstamp[slot] = stamp; c->dedup[slot] = ch0; break;
                }
                if (c->dedup[slot] == ch0) { seen = 1; break; }
                slot = (slot + 1) & c->dedup_mask;
            }
            if (seen) continue;
            int cpool = pool - c->spent[g];
            int bound = nC < cpool + 1 ? nC : cpool + 1;
            int lb = letters_bound(used | c->lmask[g], grn | c->gmask[g]);
            if (lb < bound) bound = lb;
            cand[ncand].bound = bound;
            cand[ncand].g = g;
            ncand++;
        }
    }
    qsort(cand, ncand, sizeof(Cand), cand_cmp);

    for (int i = 0; i < ncand; i++) {
        if (cand[i].bound < need - 1) { c->pruned += ncand - i; break; }
        int g = cand[i].g;
        uint64_t ch0, ch1;
        int nC = intersect(L, c->delta + (size_t)g * BSW, c->arena[depth + 1],
                           &ch0, &ch1);
        c->edges++;
        if (can_reach(c, depth + 1, nC, ch0 ^ c->salt, ch1 ^ c->salt,
                      pool - c->spent[g], need - 1,
                      used | c->lmask[g], grn | c->gmask[g])) {
            tt_put(k0, k1, 1, g);
            return 1;
        }
        if (c->budget_blown) return 0;
    }
    tt_put(k0, k1, 0, -1);
    return 0;
}

/* Replay a prefix of already-played words into the starting state.
 *
 * Not a convenience: it is what makes this program diffable against
 * antiwordle.py, whose exhaustive search cannot reach an empty board.  A shared
 * mid-game state is the only place the two can be compared at all. */
static int start_state(Ctx *c, int ai, char **after, int nafter,
                       uint64_t *h0, uint64_t *h1, int *pool,
                       uint32_t *used, uint8_t *grn) {
    int nL = intersect(BS_ALL, BS_ALL, c->arena[0], h0, h1);
    *pool = pool_start(ai);
    *used = 0;
    *grn = 0;
    for (int k = 0; k < nafter; k++) {
        int g = -1;
        for (int j = 0; j < NG; j++) if (!strcmp(GWORD[j], after[k])) { g = j; break; }
        if (g < 0) { fprintf(stderr, "%s is not a legal guess\n", after[k]); exit(1); }
        if (!((c->arena[0][g >> 6] >> (g & 63)) & 1)) {
            fprintf(stderr, "%s is not legal at that point in the line\n", after[k]);
            exit(1);
        }
        nL = intersect(c->arena[0], c->delta + (size_t)g * BSW, c->scratch, h0, h1);
        memcpy(c->arena[0], c->scratch, sizeof BS_ALL);
        *pool -= c->spent[g];
        *used |= c->lmask[g];
        *grn  |= c->gmask[g];
    }
    return nL;
}

/* Rebuild one optimal line.  Walked by RE-SEARCHING rather than by trusting the
 * stored move: the table evicts, so a bestg may be gone, but a repeat search of an
 * already-solved state is almost entirely TT hits and costs nothing. */
static int line_of(Ctx *c, int ai, char **after, int nafter,
                   char *out, size_t outsz) {
    uint64_t h0, h1;
    int pool;
    uint32_t umask;
    uint8_t gmk;
    int nL = start_state(c, ai, after, nafter, &h0, &h1, &pool, &umask, &gmk);
    size_t used = 0;
    int depth = 0;
    for (;;) {
        int total = value(c, depth, nL, h0 ^ c->salt, h1 ^ c->salt, pool, umask, gmk);
        if (total < 0) return -1;
        int move = -1, val;
        tt_get(h0 ^ c->salt, h1 ^ c->salt, &val, &move);
        if (total <= 1 || move < 0) {
            used += (size_t)snprintf(out + used, outsz - used, "%s%s",
                                     used ? " " : "", AWORD[ai]);
            return 0;
        }
        used += (size_t)snprintf(out + used, outsz - used, "%s%s",
                                 used ? " " : "", GWORD[move]);
        nL = intersect(c->arena[depth], c->delta + (size_t)move * BSW,
                       c->arena[depth + 1], &h0, &h1);
        pool -= c->spent[move];
        umask |= c->lmask[move];
        gmk   |= c->gmask[move];
        depth++;
        if (depth + 1 >= MAXD) return -1;
    }
}

static int solve_one(Ctx *c, int ai, char **after, int nafter,
                     char *line, size_t linesz) {
    ctx_load_answer(c, ai);
    uint64_t h0, h1;
    int pool;
    uint32_t umask;
    uint8_t gmk;
    int nL = start_state(c, ai, after, nafter, &h0, &h1, &pool, &umask, &gmk);
    int v = value(c, 0, nL, h0 ^ c->salt, h1 ^ c->salt, pool, umask, gmk);
    if (c->overflow) {
        fprintf(stderr, "internal: recursion hit MAXD=%d on %s -- raise it\n",
                MAXD, AWORD[ai]);
        exit(1);
    }
    if (v >= 0 && line) line_of(c, ai, after, nafter, line, linesz);
    return v;
}


/* Rebuild the witness line for an answer that reached `need`.
 *
 * Done IMMEDIATELY when a record is set, while that answer's entries are still in
 * the table -- deferring it to the end of the sweep would mean re-searching from
 * cold after 2314 other answers had evicted everything. */
static void longest_line(Ctx *c, int ai, int need, char *out, size_t outsz) {
    /* The node cap is lifted here, and budget_blown cleared. `need` is already
     * KNOWN achievable -- can_reach proved it -- so the line exists and refusing
     * to walk it would report a maximum with no witness. A blown budget during
     * the search is exactly when this matters, because that is when the flag is
     * still set and every probe below would return a spurious "no". */
    long long saved = MAXNODES;
    int saved_blown = c->budget_blown;
    MAXNODES = 0;
    c->budget_blown = 0;

    uint64_t h0, h1;
    int pool;
    uint32_t umask;
    uint8_t gmk;
    int nL = start_state(c, ai, NULL, 0, &h0, &h1, &pool, &umask, &gmk);
    size_t used = 0;
    int depth = 0, budget = need;
    while (budget > 1 && depth + 2 < MAXD) {
        int chosen = -1, chosen_n = 0;
        uint64_t ch0 = 0, ch1 = 0;
        const uint64_t *L = c->arena[depth];
        for (int w = 0; w < BSW && chosen < 0; w++) {
            uint64_t bits = L[w];
            while (bits) {
                int g = (w << 6) + __builtin_ctzll(bits);
                bits &= bits - 1;
                if (g == c->answer_g) continue;
                uint64_t t0, t1;
                int nC = intersect(L, c->delta + (size_t)g * BSW,
                                   c->arena[depth + 1], &t0, &t1);
                if (can_reach(c, depth + 1, nC, t0 ^ c->salt, t1 ^ c->salt,
                              pool - c->spent[g], budget - 1,
                              umask | c->lmask[g], gmk | c->gmask[g])) {
                    chosen = g; chosen_n = nC; ch0 = t0; ch1 = t1;
                    break;
                }
            }
        }
        if (chosen < 0) break;
        used += (size_t)snprintf(out + used, outsz - used, "%s%s",
                                 used ? " " : "", GWORD[chosen]);
        intersect(c->arena[depth], c->delta + (size_t)chosen * BSW,
                  c->arena[depth + 1], &h0, &h1);
        (void)ch0; (void)ch1;
        nL = chosen_n;
        pool -= c->spent[chosen];
        umask |= c->lmask[chosen];
        gmk   |= c->gmask[chosen];
        budget--;
        depth++;
    }
    snprintf(out + used, outsz - used, "%s%s", used ? " " : "", AWORD[ai]);
    MAXNODES = saved;
    c->budget_blown = saved_blown;
}

/* --longest: the longest game any answer admits, over the whole answer list. */
/* --longest, run across THREADS.
 *
 * The answers are independent searches, so they parallelise over the answer list;
 * what they share is the incumbent and the transposition table.
 *
 * WHY RACING THE INCUMBENT IS SAFE.  can_reach is MONOTONE in its target: an
 * answer that cannot reach k cannot reach anything above k. So an answer retired
 * against whatever bar happened to be current stays retired against the final,
 * higher one, and nothing has to be revisited -- exactly the property that made
 * one sequential pass sufficient. Threads may therefore read a stale (lower) bar
 * and merely do redundant work; they can never wrongly retire an answer. Each
 * loop re-reads the bar, so a thread that passes keeps climbing until it fails.
 *
 * The TABLE is shared and salted per answer, and its entries are self-verifying,
 * so concurrent writers cost at worst a recompute, never a wrong value.
 *
 * PER-THREAD COST is one Ctx: the 21 MB DELTA table dominates, plus ~7 MB of
 * candidate arena, so about 28 MB a thread on top of whatever --tt-bits asks for.
 */
static int run_longest(Ctx *proto, FILE *out, int *todo, int ntodo,
                       int nseen, int resumed_floor) {
    (void)proto;
    int nthreads = 1;
#ifdef _OPENMP
    nthreads = omp_get_max_threads();
#endif
    fprintf(stderr, "threads: %d (%d MB of per-thread search state)\n",
            nthreads, (int)(nthreads * ((size_t)NG * BSW * 8
                     + (size_t)MAXD * NG * sizeof(Cand)) / (1024 * 1024)));

    Ctx **ctxs = malloc((size_t)nthreads * sizeof(Ctx *));
    for (int t = 0; t < nthreads; t++) ctxs[t] = ctx_new();

    /* PHASE A -- greedy lower bound per answer, which is also the visit order. */
    fprintf(stderr, "phase A: greedy playout for %d answers\n", ntodo);
    Cand *order = malloc((size_t)ntodo * sizeof(Cand));
    double ta = wall_time();
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 4)
#endif
    for (int k = 0; k < ntodo; k++) {
        int tid = 0;
#ifdef _OPENMP
        tid = omp_get_thread_num();
#endif
        Ctx *c = ctxs[tid];
        ctx_load_answer(c, todo[k]);
        uint64_t h0, h1;
        int nL = intersect(BS_ALL, BS_ALL, c->arena[0], &h0, &h1);
        order[k].bound = greedy_len(c, nL, c->arena[0]);
        order[k].g = todo[k];
    }
    qsort(order, ntodo, sizeof(Cand), cand_cmp);

    int incumbent = resumed_floor;
    int witness = -1;
    for (int k = 0; k < ntodo; k++)
        if (order[k].bound > incumbent) { incumbent = order[k].bound; witness = order[k].g; }
    fprintf(stderr, "phase A done in %.1fs: best greedy %d (%s), worst %d\n",
            wall_time() - ta, order[0].bound, AWORD[order[0].g],
            order[ntodo - 1].bound);

    char line[4096];
    line[0] = 0;
    if (witness >= 0) {
        ctx_load_answer(ctxs[0], witness);
        longest_line(ctxs[0], witness, incumbent, line, sizeof line);
        /* Print it NOW. Greedy has a real playable sequence in hand; withholding
         * it until something beats it can mean hours of silence. */
        printf("        BEST SO FAR (greedy): %d  (%s)  %s\n",
               incumbent, AWORD[witness], line);
        fflush(stdout);
    }

    fprintf(stderr, "phase B: testing against a rising incumbent, best greedy first\n");
    int unknown = 0, done = 0;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 1)
#endif
    for (int k = 0; k < ntodo; k++) {
        int tid = 0;
#ifdef _OPENMP
        tid = omp_get_thread_num();
#endif
        Ctx *c = ctxs[tid];
        int ai = order[k].g;
        double t0 = wall_time();
        ctx_load_answer(c, ai);
        uint64_t h0, h1;
        int pool;
        uint32_t umask;
        uint8_t gmk;
        int nL = start_state(c, ai, NULL, 0, &h0, &h1, &pool, &umask, &gmk);
        c->cur_t0 = t0;

        int floor_tested, record = 0;
        for (;;) {
            int bar;
#ifdef _OPENMP
#pragma omp atomic read
#endif
            bar = incumbent;
            floor_tested = bar;
            c->cur_need = bar + 1;
            if (!can_reach(c, 0, nL, h0 ^ c->salt, h1 ^ c->salt, pool,
                           bar + 1, umask, gmk))
                break;
            /* This answer reaches bar + 1. Publish it, and rebuild the witness
             * here while this answer's entries are still hot in the table. */
#ifdef _OPENMP
#pragma omp critical (antistall_record)
#endif
            {
                if (bar + 1 > incumbent) {
                    incumbent = bar + 1;
                    witness = ai;
                    record = 1;
                    longest_line(c, ai, incumbent, line, sizeof line);
                    printf("        NEW LONGEST: %d  (%s)  %s\n",
                           incumbent, AWORD[ai], line);
                    fflush(stdout);
                }
            }
        }
        if (c->overflow) {
            fprintf(stderr, "internal: recursion hit MAXD=%d on %s -- raise it\n",
                    MAXD, AWORD[ai]);
            exit(1);
        }
        double secs = wall_time() - t0;
        const char *verdict = c->budget_blown ? "unknown" : (record ? "record" : "no");
#ifdef _OPENMP
#pragma omp critical (antistall_report)
#endif
        {
            if (c->budget_blown) unknown++;
            done++;
            printf("[%d/%d] %s greedy=%d %s  nodes=%lld %.2fs\n",
                   nseen + done, nseen + ntodo, AWORD[ai], order[k].bound, verdict,
                   c->nodes, secs);
            fflush(stdout);
            if (out) {
                /* `value` is filled ONLY on a record -- for every other answer the
                 * run never computed one, and writing anything there would invent
                 * it. `floor` says what bar the answer was actually tested
                 * against, which is what makes a resumed run auditable. */
                char val[16];
                if (record) snprintf(val, sizeof val, "%d", incumbent);
                else        val[0] = 0;
                fprintf(out, "%s,%d,%s,%s,%d,%lld,%.3f,%s\n", AWORD[ai],
                        order[k].bound, verdict, val, floor_tested + 1,
                        c->nodes, secs, record ? line : "");
                fflush(out);
            }
        }
    }
    free(order);
    for (int t = 0; t < nthreads; t++) ctx_free(ctxs[t]);
    free(ctxs);

    printf("\nLONGEST GAME: %d guesses, answer %s\n  %s\n", incumbent,
           witness >= 0 ? AWORD[witness] : "(none)", line);
    if (unknown)
        printf("  WARNING: %d answer(s) hit --max-nodes; their verdict is UNKNOWN,\n"
               "           so this is a LOWER BOUND on the longest game, not the maximum.\n",
               unknown);
    return 0;
}

/* -------------------------------------------------------------------- main */

static void usage(void) {
    fprintf(stderr,
        "usage: antistall --out FILE [options]   (prefer solver/run-antistall-sweep.sh)\n"
        "  --out FILE       CSV to append one row per answer to\n"
        "  --no-out         print only, save NOTHING -- must be explicit\n"
        "  --answer WORD    solve just this answer (repeatable)\n"
        "  --limit N        stop after N answers\n"
        "  --tt-bits B      transposition table size, 2^B entries (default 26)\n"
        "  --max-nodes N    abandon an answer past N states, reporting no number\n"
        "  --threads N      threads for --longest (default: all cores)\n"
        "  --longest        find the LONGEST GAME any answer admits, and stop --\n"
        "                   a different, much cheaper question than the per-answer\n"
        "                   sweep, since only the maximum is computed\n"
        "  --show-bound     print the letters bound at the start state and exit\n"
        "  --no-prune       disable both bounds -- the exhaustive oracle\n"
        "  --after \"W W\"    words already played, to start from a mid-game state\n"
        "  --guess-list F   word list that may be PLAYED (default guess.txt)\n"
        "  --data DIR       data directory (default data, i.e. run from math/)\n");
    exit(2);
}

int main(int argc, char **argv) {
    /* Line-buffered: the wrapper pipes stdout through `tee`, and block buffering
     * on a pipe means a multi-hour run shows NOTHING in its log until it ends.
     * That happened -- a 3h24m run wrote three CSV rows and an empty log. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    const char *outpath = NULL, *datadir = "data", *guesslist = NULL;
    int no_out = 0, ttbits = 26, limit = 0;
    char *only[64]; int nonly = 0;
    char *after[MAXD]; int nafter = 0;
    char afterbuf[512]; afterbuf[0] = 0;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "--out") && i + 1 < argc)         outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out"))                      no_out = 1;
        else if (!strcmp(argv[i], "--answer") && i + 1 < argc)      { if (nonly < 64) only[nonly++] = argv[++i]; }
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc)       limit = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc)     ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--max-nodes") && i + 1 < argc)   MAXNODES = atoll(argv[++i]);
        else if (!strcmp(argv[i], "--no-prune"))                    PRUNE = 0;
        else if (!strcmp(argv[i], "--longest"))                     LONGEST = 1;
        else if (!strcmp(argv[i], "--show-bound"))                  SHOWBOUND = 1;
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) {
#ifdef _OPENMP
            omp_set_num_threads(atoi(argv[++i]));
#else
            i++;
            fprintf(stderr, "built without OpenMP; --threads ignored\n");
#endif
        }
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc)  guesslist = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc)        datadir = argv[++i];
        else if (!strcmp(argv[i], "--after") && i + 1 < argc) {
            snprintf(afterbuf, sizeof afterbuf, "%s", argv[++i]);
            for (char *t = strtok(afterbuf, " "); t; t = strtok(NULL, " "))
                if (nafter < MAXD - 1) after[nafter++] = t;
        }
        else usage();
    }
    if (!outpath && !no_out) {
        fprintf(stderr, "antistall: give --out FILE, or --no-out to save NOTHING.\n"
                        "  A run with nowhere to put its answer is a run thrown away.\n"
                        "  Prefer the wrapper: bash solver/run-antistall-sweep.sh\n");
        return 2;
    }

    if (LONGEST && nafter) {
        fprintf(stderr, "--longest searches whole games, so --after does not apply\n");
        return 2;
    }
    if (LONGEST && !PRUNE) {
        fprintf(stderr, "--longest IS the pruned decision search; --no-prune has no\n"
                        "  meaning here. Use the per-answer mode for the oracle.\n");
        return 2;
    }

    char path[512];
    GWORD = malloc(sizeof(*GWORD) * MAXG);
    AWORD = malloc(sizeof(*AWORD) * MAXA);
    if (guesslist) snprintf(path, sizeof path, "%s", guesslist);
    else           snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path, AWORD);
    snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, cc;
    PAT = load_npy(path, &r, &cc);
    if (cc != NA) {
        fprintf(stderr, "pattern matrix is %dx%d but the answer list has %d words\n",
                r, cc, NA);
        return 1;
    }
    if (NG > MAXG) { fprintf(stderr, "guess list %d exceeds MAXG %d\n", NG, MAXG); return 1; }

    /* The matrix rows are the FULL guess list, so a restricted --guess-list has to
     * be mapped back onto them; and every answer must be playable, or it could
     * never be named and the game would not end. */
    if (guesslist) {
        char (*full)[WBUF] = malloc(sizeof(*full) * MAXG);
        snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
        int nfull = load_words(path, full);
        if (nfull != r) {
            fprintf(stderr, "matrix has %d rows but the full guess list has %d\n", r, nfull);
            return 1;
        }
        pat_t *sub = malloc((size_t)NG * NA * sizeof(pat_t));
        for (int g = 0; g < NG; g++) {
            int row = -1;
            for (int j = 0; j < nfull; j++) if (!strcmp(full[j], GWORD[g])) { row = j; break; }
            if (row < 0) { fprintf(stderr, "%s is not in the full guess list\n", GWORD[g]); return 1; }
            memcpy(sub + (size_t)g * NA, PAT + (size_t)row * NA, (size_t)NA * sizeof(pat_t));
        }
        free(PAT); free(full);
        PAT = sub;
    }
    for (int a = 0; a < NA; a++) {
        ANS2G[a] = -1;
        for (int g = 0; g < NG; g++) if (!strcmp(GWORD[g], AWORD[a])) { ANS2G[a] = g; break; }
        if (ANS2G[a] < 0) {
            fprintf(stderr, "answer %s is not a legal guess -- it could never be named\n",
                    AWORD[a]);
            return 1;
        }
    }
    build_bitsets();
    tt_init(ttbits);

    /* Which answers to solve, and resume: a row already in the CSV is done.
     *
     * In --longest mode resume ALSO recovers the incumbent, from the `value`
     * column of the record rows. Skipping an answer tested against a LOWER bar is
     * sound because can_reach is monotone in its target: an answer that could not
     * reach k cannot reach anything above k, so it stays retired. */
    static char done[MAXA];
    int resumed_floor = 0, nseen = 0;
    if (outpath) {
        FILE *rf = fopen(outpath, "r");
        if (rf) {
            char lb[4096];
            while (fgets(lb, sizeof lb, rf)) {
                char *f[8]; int nf = 0;
                for (char *t = lb; nf < 8; ) {
                    f[nf++] = t;
                    char *comma = strchr(t, ',');
                    if (!comma) break;
                    *comma = 0; t = comma + 1;
                }
                if (nf < 3) continue;
                for (int a = 0; a < NA; a++)
                    if (!strcmp(f[0], AWORD[a])) { done[a] = 1; nseen++; break; }
                if (LONGEST && nf >= 4 && !strcmp(f[2], "record")) {
                    int v = atoi(f[3]);
                    if (v > resumed_floor) resumed_floor = v;
                }
            }
            fclose(rf);
        }
    }
    int todo[MAXA], ntodo = 0;
    for (int a = 0; a < NA; a++) {
        if (done[a]) continue;
        if (nonly) {
            int want = 0;
            for (int k = 0; k < nonly; k++) if (!strcmp(only[k], AWORD[a])) want = 1;
            if (!want) continue;
        }
        todo[ntodo++] = a;
        if (limit && ntodo >= limit) break;
    }
    if (nonly) {
        for (int k = 0; k < nonly; k++) {
            int found = 0;
            for (int a = 0; a < NA; a++) if (!strcmp(only[k], AWORD[a])) found = 1;
            if (!found) { fprintf(stderr, "%s is not an answer word\n", only[k]); return 1; }
        }
    }
    fprintf(stderr, "answers %d to solve, guess list %d words%s%s\n", ntodo, NG,
            PRUNE ? "" : ", UNPRUNED (oracle mode)",
            MAXNODES ? ", node-limited" : "");

    FILE *out = NULL;
    if (outpath) {
        int fresh = 1;
        FILE *t = fopen(outpath, "r");
        if (t) { fresh = fgetc(t) == EOF; fclose(t); }
        out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
        if (fresh) fprintf(out, LONGEST
            ? "answer,greedy,verdict,value,floor,nodes,secs,line\n"
            : "answer,status,guesses,nodes,edges,secs,line\n");
    }

    Ctx *c = ctx_new();

    if (SHOWBOUND) {
        for (int k = 0; k < ntodo; k++) {
            int ai = todo[k];
            ctx_load_answer(c, ai);
            uint64_t h0, h1;
            int pool;
            uint32_t umask;
            uint8_t gmk;
            int nL = start_state(c, ai, after, nafter, &h0, &h1, &pool, &umask, &gmk);
            printf("%s letters_bound=%d unused=%d nongreen=%d nL=%d pool=%d\n",
                   AWORD[ai], letters_bound(umask, gmk),
                   __builtin_popcount(ALPHA_MASK & ~umask),
                   WORDLEN - __builtin_popcount((uint32_t)gmk), nL, pool);
        }
        return 0;
    }

    double t_start = wall_time();
    if (LONGEST) {
        if (resumed_floor)
            fprintf(stderr, "resuming with incumbent %d from %d recorded answers\n",
                    resumed_floor, nseen);
        int rc = run_longest(c, out, todo, ntodo, nseen, resumed_floor);
        printf("done in %.1fs (wall)\n", wall_time() - t_start);
        if (out) fclose(out);
        return rc;
    }
    for (int k = 0; k < ntodo; k++) {
        int ai = todo[k];
        char line[4096];
        line[0] = 0;
        double t0 = wall_time();
        int v = solve_one(c, ai, after, nafter, line, sizeof line);
        double secs = wall_time() - t0;
        if (v < 0) {
            printf("[%d/%d] %s = ABORTED  nodes=%lld edges=%lld %.2fs\n",
                   k + 1, ntodo, AWORD[ai], c->nodes, c->edges, secs);
            if (out) fprintf(out, "%s,aborted,,%lld,%lld,%.3f,\n",
                             AWORD[ai], c->nodes, c->edges, secs);
        } else {
            printf("[%d/%d] %s = %d  nodes=%lld edges=%lld %.2fs  %s\n",
                   k + 1, ntodo, AWORD[ai], v, c->nodes, c->edges, secs, line);
            if (out) fprintf(out, "%s,ok,%d,%lld,%lld,%.3f,%s\n",
                             AWORD[ai], v, c->nodes, c->edges, secs, line);
        }
        fflush(stdout);
        if (out) fflush(out);
    }
    printf("done: %d answers in %.1fs (wall)\n", ntodo, wall_time() - t_start);
    if (out) fclose(out);
    return 0;
}
