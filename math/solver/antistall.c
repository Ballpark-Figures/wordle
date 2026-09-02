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

typedef struct { int bound, g; } Cand;

typedef struct {
    uint64_t *delta;              /* NG * BSW -- the words each guess still allows */
    int      *spent;              /* NG -- resource units each guess costs */
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
    int       overflow;           /* recursion hit MAXD -- a hard error, not a cap */
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

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    c->delta  = malloc((size_t)NG * BSW * sizeof(uint64_t));
    c->spent  = malloc((size_t)NG * sizeof(int));
    c->cand   = malloc((size_t)MAXD * NG * sizeof(Cand));
    c->dedup  = malloc((size_t)DEDUP_SIZE * sizeof(uint64_t));
    c->dstamp = calloc((size_t)DEDUP_SIZE, sizeof(uint32_t));
    c->dedup_mask = DEDUP_SIZE - 1;
    c->stamp = 0;
    if (!c->delta || !c->spent || !c->cand || !c->dedup || !c->dstamp) {
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

/* Intersect the parent's legal set with DELTA[g], returning the popcount and
 * hashing the result in the same pass.
 *
 * The hash is over the bitset WORDS, not the member indices: that is O(BSW) = 203
 * regardless of how many words are live, where a Zobrist-style fold over members
 * would be O(n) and cost thousands of operations near the top of a game. */
static inline int intersect(const uint64_t *parent, const uint64_t *d,
                            uint64_t *out, uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0x243F6A8885A308D3ULL, b = 0x13198A2E03707344ULL;
    int n = 0;
    for (int w = 0; w < BSW; w++) {
        uint64_t x = parent[w] & d[w];
        out[w] = x;
        if (x) {
            n += __builtin_popcountll(x);
            a = (a ^ (x + (uint64_t)w * 0x9E3779B97F4A7C15ULL)) * 0x100000001B3ULL;
            b = (b ^ (x * 0xC2B2AE3D27D4EB4FULL) ^ (uint64_t)w) * 0xD6E8FEB86659FD93ULL;
        }
    }
    *h0 = a; *h1 = b;
    return n;
}

static int value(Ctx *c, int depth, int nL, uint64_t h0, uint64_t h1, int pool) {
    int val, bestg;
    if (tt_get(h0, h1, &val, &bestg)) return val;
    if (nL <= 1) return 1;                    /* only the answer is playable */
    if (depth + 1 >= MAXD) { c->overflow = 1; return 1; }
    if (MAXNODES && c->nodes >= MAXNODES) return -1;   /* abandoned; see solve_one */

    c->nodes++;
    const uint64_t *L = c->arena[depth];
    int ceiling = PRUNE ? (nL < pool + 1 ? nL : pool + 1) : nL + 1;

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
            int bound = PRUNE ? (nC < cpool + 1 ? nC : cpool + 1) : nC;
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
                      pool - c->spent[g]);
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

/* Replay a prefix of already-played words into the starting state.
 *
 * Not a convenience: it is what makes this program diffable against
 * antiwordle.py, whose exhaustive search cannot reach an empty board.  A shared
 * mid-game state is the only place the two can be compared at all. */
static int start_state(Ctx *c, int ai, char **after, int nafter,
                       uint64_t *h0, uint64_t *h1, int *pool) {
    int nL = intersect(BS_ALL, BS_ALL, c->arena[0], h0, h1);
    *pool = pool_start(ai);
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
    int nL = start_state(c, ai, after, nafter, &h0, &h1, &pool);
    size_t used = 0;
    int depth = 0;
    for (;;) {
        int total = value(c, depth, nL, h0 ^ c->salt, h1 ^ c->salt, pool);
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
        depth++;
        if (depth + 1 >= MAXD) return -1;
    }
}

static int solve_one(Ctx *c, int ai, char **after, int nafter,
                     char *line, size_t linesz) {
    ctx_load_answer(c, ai);
    uint64_t h0, h1;
    int pool;
    int nL = start_state(c, ai, after, nafter, &h0, &h1, &pool);
    int v = value(c, 0, nL, h0 ^ c->salt, h1 ^ c->salt, pool);
    if (c->overflow) {
        fprintf(stderr, "internal: recursion hit MAXD=%d on %s -- raise it\n",
                MAXD, AWORD[ai]);
        exit(1);
    }
    if (v >= 0 && line) line_of(c, ai, after, nafter, line, linesz);
    return v;
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
        "  --no-prune       disable both bounds -- the exhaustive oracle\n"
        "  --after \"W W\"    words already played, to start from a mid-game state\n"
        "  --guess-list F   word list that may be PLAYED (default guess.txt)\n"
        "  --data DIR       data directory (default data, i.e. run from math/)\n");
    exit(2);
}

int main(int argc, char **argv) {
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

    /* Which answers to solve, and resume: a row already in the CSV is done. */
    static char done[MAXA];
    if (outpath) {
        FILE *rf = fopen(outpath, "r");
        if (rf) {
            char lb[512];
            while (fgets(lb, sizeof lb, rf)) {
                char *comma = strchr(lb, ',');
                if (!comma) continue;
                *comma = 0;
                for (int a = 0; a < NA; a++) if (!strcmp(lb, AWORD[a])) { done[a] = 1; break; }
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
        if (fresh) fprintf(out, "answer,status,guesses,nodes,edges,secs,line\n");
    }

    Ctx *c = ctx_new();
    double t_start = (double)clock() / CLOCKS_PER_SEC;
    for (int k = 0; k < ntodo; k++) {
        int ai = todo[k];
        char line[4096];
        line[0] = 0;
        double t0 = (double)clock() / CLOCKS_PER_SEC;
        int v = solve_one(c, ai, after, nafter, line, sizeof line);
        double secs = (double)clock() / CLOCKS_PER_SEC - t0;
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
    printf("done: %d answers in %.1fs\n", ntodo,
           (double)clock() / CLOCKS_PER_SEC - t_start);
    if (out) fclose(out);
    return 0;
}
