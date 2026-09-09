/* eldrowmax.c -- THE LONGEST CONSISTENT CHAIN, exactly.
 *
 * THE QUESTION.  How long can a Wordle game be dragged out if every word played
 * must itself still be a POSSIBLE ANSWER -- consistent with every clue seen so
 * far?  Not antiwordle's legality (greens in place, yellows reused, greys as count
 * caps), which is a strictly LOOSER rule that admits words the answer could not
 * be; here a play must be a live candidate, so the sequence is a chain of words
 * each of which could, at the moment it was played, have been the answer.
 *
 * This is `math/eldrow.py`'s `longest_chain` objective, which is that module's own
 * statement of the rule and stays the REFERENCE -- tools/checkeldrowmax.py diffs
 * this program against it.  eldrow's exact search is Python branch-and-bound and
 * is only viable on tiny lists; its full-list mode is a beam, which FINDS chains
 * and never proves one longest.  This program is the exact search made to scale.
 *
 * -------------------------------------------------------------- the model
 *
 * THE STATE IS THE CANDIDATE SET AND NOTHING ELSE.  Playing g from the live set S
 * splits S by the feedback each member would give, and exactly one bucket survives
 * -- whichever holds the answer.  So a move is (g, pattern) and the child is that
 * bucket.  Everything a continuation depends on is in the bucket: the words still
 * playable ARE the words still possible.  Two different moves reaching the same
 * bucket are therefore the same subgame, which is what the pass-1 dedup exploits.
 *
 * THERE IS NO ANSWER TO FIX, and that is what makes this cheap.  Choosing which
 * feedback branch to follow IS choosing which answer survives, so the maximum over
 * answers and the maximum over branches are the same maximum, taken in one search
 * from the full list.  The answer is simply the last word of the chain -- the sole
 * survivor, which the final move names.
 *
 * TERMINATION.  pattern(g, g) is all-green, so g is in the all-green bucket and in
 * no other; every non-all-green child therefore EXCLUDES the word just played and
 * is a strict subset.  The state graph is a DAG, the search terminates, and the
 * longest path is well defined.  (The all-green bucket is the case "the word you
 * just played was the answer", which ends the game on that move -- worth exactly
 * the `best = 1` the search starts from, never more, so it is not searched.)
 *
 * THE COUNT INCLUDES THE FINAL NAMING MOVE: a chain of k words is k, and a set
 * already down to one word scores 1.  eldrow.py counts guesses-until-a-singleton
 * instead, so its number is exactly one LESS; the gate asserts that relation
 * rather than papering over it.
 *
 * ---------------------------------------------------------------- bounds
 *
 * ONE bound, and it is the only sound one here: value(S) <= |S|.  Each move drops
 * at least the word played, so a chain from S cannot outlast S.  Exact by
 * induction, and it is what both searches prune on.
 *
 * ANTISTALL'S OTHER TWO BOUNDS DO NOT TRANSFER and are deliberately absent.  Its
 * RESOURCE bound counts count-pins and square-bans a line can still spend, and its
 * LETTERS bound counts untouched letters plus non-green squares; both are facts
 * about how antiwordle's constraint tightens, not about how a candidate set
 * shrinks, and a chain here can revisit letters freely.  Carrying either across
 * would have silently cut correct lines -- the exact failure the shared rules call
 * "copying the shape of an existing program".
 *
 * ------------------------------------------------------------ what it runs on
 *
 * THE POOL IS A MODELLING CHOICE AND IS IN THE OUTPUT.  --words names the list
 * that is both the candidate set and the guess set; it defaults to the 2315
 * mystery answers, and every word in it must appear in the pattern matrix's answer
 * list (that is where its feedback comes from).  A different pool is a different
 * quantity, so it is recorded in every row.
 *
 * WORD LISTS ARE OURS.  The 2315/12972 Wordle lists the rest of this video runs
 * on, which are not the NYT's current ones; a chain length here is a fact about
 * OUR lists.
 *
 * ---------------------------------------------------------------- running
 *
 *     bash solver/run-eldrowmax.sh                  # from math/ -- USE THIS
 *
 * The binary REFUSES to start without --out or an explicit --no-out: a run that
 * prints its answer and saves nothing is a run thrown away, and this repo has
 * already lost a day of multi-hour runs that way.
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

/* MAXP bounds the POOL -- the list that is both the candidates and the guesses.
 * 2315 at the default mystery list, with slack for a subset or a small test list. */
#ifndef MAXP
#define MAXP       2400
#endif

#define BSW  ((MAXP + 63) / 64)          /* uint64 words spanning the whole pool */

/* MAXD bounds the RECURSION, and it is an array bound, NOT a modelling cap: this
 * game has no depth limit and the program imposes none.  A chain cannot outlast
 * the pool (every move drops the word it played), so MAXP + 2 is unreachable by
 * construction.  Overrunning it is a hard error, never a silent truncation. */
#define MAXD       (MAXP + 2)

/* Candidate entries a single recursion PATH may hold at once.  A node with n live
 * words has at most n * 243 children before dedup, but only the frames on the
 * current path are live at any moment and n falls fast with depth.  Exceeding this
 * is a hard error naming the flag to raise, never a wrong answer. */
#ifndef CANDPOOL
#define CANDPOOL   (1 << 20)
#endif

typedef uint8_t pat_t;

static int      NP;                      /* pool size: candidates == guesses */
static char   (*PWORD)[WBUF];            /* the pool's words */
static pat_t   *APAT;                    /* NP * NP: APAT[g * NP + w] */

static int      PRUNE = 1;               /* --no-prune drops the size bound */
static long long MAXNODES = 0;           /* --max-nodes, 0 = unlimited */
static double   REPORT = 30.0;           /* heartbeat seconds */

/* --------------------------------------------------------------- loading
 * load_words and load_npy are optturns.c's, unchanged -- same files, same
 * format, and a second copy of a parser is a second place for it to drift. */

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
 *
 * optturns' design: 128 bits of key per entry, the second half stored XORed with
 * the payload, so an entry torn by a concurrent writer fails verification and
 * reads as a miss rather than a wrong value.  With 128-bit keys a collision is not
 * a practical concern, which matters here because the true key -- the candidate
 * set, up to 2315 bits -- is far too big to store.
 *
 * NOTHING IS SAVED OR LOADED.  A table is worth persisting when a run resumes into
 * the same states; this program answers one question about one pool in one run, so
 * there is nothing to resume into and a snapshot would only be a way to feed a
 * FOREIGN table (an antistall or optturns one, keying the same words under a
 * different meaning) into this search. */

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

/* ------------------------------------------------------------------ context */

/* CPU time is the wrong clock once threads exist: clock() sums across them and
 * would report a 20-thread run as taking 20x as long as it did. */
static double wall_time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

/* A child move, awaiting pass 2.  `gp` packs the played word and the surviving
 * feedback as g * NPAT + p, which fits an int32 for any pool this program can
 * hold (2400 * 243), so the whole entry stays 8 bytes and sorts cheaply. */
typedef struct { int32_t bound, gp; } Cand;

typedef struct {
    uint64_t arena[MAXD][BSW];    /* the candidate set at each recursion level */
    uint16_t widx[MAXD][BSW];     /* ...and its non-empty bitset-word indices */
    int      nwid[MAXD];
    uint64_t scratch[BSW];        /* one child, built then measured */
    uint16_t swidx[BSW];
    int      snwid;
    uint16_t sort[MAXP];          /* members counting-sorted by feedback */
    int      cnt[NPAT];           /* counting-sort counts, then fill offsets */
    int      start[NPAT + 1];     /* run boundaries in `sort` */
    Cand    *cpool;               /* candidate stack arena, shared down the path */
    int      ctop;
    uint64_t *dedup;              /* one node's child hashes; see below */
    uint32_t *dstamp;             /* which node wrote each slot */
    uint32_t  stamp;              /* bumped per node instead of clearing dedup */
    int       dedup_mask;
    long long nodes, edges, pruned;
    int       overflow;           /* recursion hit MAXD -- a hard error */
    int       budget_blown;       /* --max-nodes hit; the verdict is UNKNOWN */
    /* Heartbeat: a single test can search for a long time, and silence that long
     * is indistinguishable from a hang. Per-thread, so each says what it is on. */
    double    next_beat;
} Ctx;

/* The run's start, shared: the heartbeat reports elapsed WALL time, and every
 * thread has to agree on when the clock started. */
static double T_START;

/* One dedup table per THREAD, not per depth: pass 1 at a level finishes entirely
 * before pass 2 starts recursing, and pass 2 never consults it again, so a deeper
 * level is free to reuse the same memory.
 *
 * Slots are STAMPED with a per-node counter rather than cleared.  Clearing would
 * mean a 256 KB memset at every node -- larger than the work the node itself does,
 * and it would quietly have become the whole runtime. */
#define DEDUP_BITS 15
#define DEDUP_SIZE (1 << DEDUP_BITS)

static void ctx_free(Ctx *c) {
    free(c->cpool); free(c->dedup); free(c->dstamp);
    free(c);
}

static Ctx *ctx_new(void) {
    Ctx *c = calloc(1, sizeof(Ctx));
    if (!c) { fprintf(stderr, "out of memory for a search context\n"); exit(1); }
    c->cpool  = malloc((size_t)CANDPOOL * sizeof(Cand));
    c->dedup  = malloc((size_t)DEDUP_SIZE * sizeof(uint64_t));
    c->dstamp = calloc((size_t)DEDUP_SIZE, sizeof(uint32_t));
    c->dedup_mask = DEDUP_SIZE - 1;
    if (!c->cpool || !c->dedup || !c->dstamp) {
        fprintf(stderr, "out of memory for a search context\n"); exit(1);
    }
    return c;
}

/* Descending by bound, ties on the lowest packed move -- so the played word, and
 * then its feedback, break ties by lowest index, which is the ranking rule
 * everywhere else in this repo and is what makes the reported LINE reproducible
 * and diffable against the Python reference. */
static int cand_cmp(const void *x, const void *y) {
    const Cand *p = x, *q = y;
    if (p->bound != q->bound) return q->bound - p->bound;
    return p->gp - q->gp;
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

/* Build a child set from an ASCENDING list of member indices, fingerprinting it in
 * the same pass.
 *
 * `out` is left STALE at words outside the child's live list -- correct only
 * because every reader goes through that list, never over the raw bitset.
 *
 * THE FINGERPRINT IS THE MEMO KEY, since the true key (the candidate set) is far
 * too big to store, so a collision silently returns another position's value.  Its
 * two halves must therefore stay INDEPENDENT: antistall.c shipped a version that
 * folded both from the same per-word quantity with near-identical FNV steps, which
 * left them correlated and collided on a real search (mummy came back 11 against a
 * true 12).  This is that file's corrected fold, verbatim -- each word avalanched
 * once, accumulated into the two halves by DIFFERENT operations, both finalized. */
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

/* Counting-sort the live members of a set by the feedback `g` gives them, leaving
 * each bucket a contiguous run `sort[start[p] .. start[p+1])`.
 *
 * Members are walked in ASCENDING index order (live bitset words ascend, and ctz
 * takes the bits of each word in ascending order), and a counting sort is stable,
 * so every run ascends too -- which is what build_child requires. */
static void split_by(Ctx *c, const uint64_t *L, const uint16_t *LW, int LNW, int g) {
    memset(c->cnt, 0, sizeof c->cnt);
    const pat_t *row = APAT + (size_t)g * NP;
    for (int kk = 0; kk < LNW; kk++) {
        int wbase = LW[kk] << 6;
        uint64_t bits = L[LW[kk]];
        while (bits) {
            c->cnt[row[wbase + __builtin_ctzll(bits)]]++;
            bits &= bits - 1;
        }
    }
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { c->start[p] = acc; acc += c->cnt[p]; c->cnt[p] = c->start[p]; }
    c->start[NPAT] = acc;
    for (int kk = 0; kk < LNW; kk++) {
        int wbase = LW[kk] << 6;
        uint64_t bits = L[LW[kk]];
        while (bits) {
            int w = wbase + __builtin_ctzll(bits);
            bits &= bits - 1;
            c->sort[c->cnt[row[w]]++] = (uint16_t)w;
        }
    }
}

/* PASS 1 -- expand every move into its child, deduplicating by the child's SET.
 *
 * Two moves that leave the same words alive leave the same game, whatever word or
 * feedback produced them, so this is a coarser and strictly better collapse than
 * deduplicating by the feedback.  Returns the number of candidates written to
 * `cand`, or -1 if the candidate arena is exhausted. */
static int expand(Ctx *c, int depth, Cand *cand, int room) {
    if (room < 0) room = 0;
    const uint64_t *L = c->arena[depth];
    const uint16_t *LW = c->widx[depth];
    int LNW = c->nwid[depth];
    int ncand = 0;
    uint32_t stamp = ++c->stamp;
    for (int kk = 0; kk < LNW; kk++) {
        int wbase = LW[kk] << 6;
        uint64_t bits = L[LW[kk]];
        while (bits) {
            int g = wbase + __builtin_ctzll(bits);
            bits &= bits - 1;
            split_by(c, L, LW, LNW, g);
            for (int p = 0; p < NPAT; p++) {
                int lo = c->start[p], hi = c->start[p + 1];
                if (lo == hi || p == ALL_GREEN) continue;   /* see the header: the
                       all-green bucket is "you just played the answer", worth the
                       best = 1 the search starts from and never more */
                uint64_t ch0, ch1;
                build_child(c->sort + lo, hi - lo, c->scratch,
                            c->swidx, &c->snwid, &ch0, &ch1);
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
                /* A hard error, not a truncation: dropping children would turn a
                 * maximum into an under-count that looks like an answer. */
                if (ncand >= room) {
                    fprintf(stderr, "the candidate arena (%d entries) is exhausted --\n"
                                    "  rebuild with a larger -DCANDPOOL\n", CANDPOOL);
                    exit(1);
                }
                cand[ncand].bound = hi - lo;      /* value(child) <= |child| */
                cand[ncand].gp = g * NPAT + p;
                ncand++;
            }
        }
    }
    return ncand;
}

/* Rebuild one move's child into level `depth + 1`.  Cheaper than keeping pass 1's
 * bitsets around: one counting sort plus one build, both O(live words). */
static int descend(Ctx *c, int depth, int gp, uint64_t *h0, uint64_t *h1) {
    int g = gp / NPAT, p = gp % NPAT;
    split_by(c, c->arena[depth], c->widx[depth], c->nwid[depth], g);
    int lo = c->start[p], hi = c->start[p + 1];
    build_child(c->sort + lo, hi - lo, c->arena[depth + 1],
                c->widx[depth + 1], &c->nwid[depth + 1], h0, h1);
    return hi - lo;
}

static void heartbeat(Ctx *c, const char *what) {
    double now = wall_time();
    if (now < c->next_beat) return;
    c->next_beat = now + REPORT;
    fprintf(stderr, "        ... %s: %lld nodes, %.0fs\n",
            what, c->nodes, now - T_START);
}

/* The exact value: the longest chain from this set, the naming move included. */
static int value(Ctx *c, int depth, int n, uint64_t h0, uint64_t h1) {
    int val, bestg;
    if (tt_get(h0, h1, &val, &bestg)) return val;
    if (n <= 1) return 1;                     /* only the answer is left to name */
    if (depth + 1 >= MAXD) { c->overflow = 1; return 1; }
    if (MAXNODES && c->nodes >= MAXNODES) { c->budget_blown = 1; return -1; }
    if ((c->nodes & 0xFFFF) == 0) heartbeat(c, "exact");

    c->nodes++;
    Cand *cand = c->cpool + c->ctop;
    int ncand = expand(c, depth, cand, CANDPOOL - c->ctop);
    c->ctop += ncand;
    qsort(cand, ncand, sizeof(Cand), cand_cmp);

    int best = 1, best_move = -1;             /* name the answer now and be done */
    for (int i = 0; i < ncand; i++) {
        if (PRUNE && 1 + cand[i].bound <= best) { c->pruned += ncand - i; break; }
        uint64_t ch0, ch1;
        int nC = descend(c, depth, cand[i].gp, &ch0, &ch1);
        c->edges++;
        int v = value(c, depth + 1, nC, ch0, ch1);
        if (v < 0) { c->ctop -= ncand; return -1; }
        v += 1;
        if (v > best) {
            best = v; best_move = cand[i].gp;
            if (PRUNE && best >= n) break;    /* value(S) <= |S|, so this is it */
        }
    }
    c->ctop -= ncand;
    tt_put(h0, h1, best, best_move);
    return best;
}

/* Is there a chain of at least `need` words (the naming move included)?
 *
 * A DECISION problem, and that is the point: a subtree dies the moment it cannot
 * reach the target rather than when it has been fully measured, which prunes
 * vastly harder than the optimisation.
 *
 * THE MEMO KEY CARRIES THE BUDGET, so every entry stays EXACT -- "this set can /
 * cannot reach b" is a fact about (set, b), not a bound that depends on where the
 * search happened to be when it was written.  Seeding a maximising search with a
 * floor instead makes its memoised values upper bounds rather than values, and
 * storing those as if exact silently corrupts every later lookup. */
static int can_reach(Ctx *c, int depth, int n, uint64_t h0, uint64_t h1, int need) {
    if (need <= 1) return 1;                  /* the last word is always playable */
    if (n < need) return 0;                   /* the size bound */
    if (depth + 1 >= MAXD) { c->overflow = 1; return 0; }
    if (MAXNODES && c->nodes >= MAXNODES) { c->budget_blown = 1; return 0; }
    if ((c->nodes & 0xFFFF) == 0) heartbeat(c, "deciding");

    uint64_t k0 = h0 ^ (uint64_t)need * 0x9E3779B97F4A7C15ULL;
    uint64_t k1 = h1 ^ (uint64_t)need * 0xC2B2AE3D27D4EB4FULL;
    int val, bestg;
    if (tt_get(k0, k1, &val, &bestg)) return val;

    c->nodes++;
    Cand *cand = c->cpool + c->ctop;
    int ncand = expand(c, depth, cand, CANDPOOL - c->ctop);
    c->ctop += ncand;
    qsort(cand, ncand, sizeof(Cand), cand_cmp);

    for (int i = 0; i < ncand; i++) {
        if (cand[i].bound < need - 1) { c->pruned += ncand - i; break; }
        uint64_t ch0, ch1;
        int nC = descend(c, depth, cand[i].gp, &ch0, &ch1);
        c->edges++;
        if (can_reach(c, depth + 1, nC, ch0, ch1, need - 1)) {
            c->ctop -= ncand;
            tt_put(k0, k1, 1, cand[i].gp);
            return 1;
        }
        /* A budget-blown search proves nothing, so its "no" must NOT be memoised
         * as a fact -- it would retire a set that can in truth reach the target. */
        if (c->budget_blown) { c->ctop -= ncand; return 0; }
    }
    c->ctop -= ncand;
    tt_put(k0, k1, 0, -1);
    return 0;
}

/* ------------------------------------------------------------- the root state
 *
 * Held apart from any Ctx because every thread builds its own children FROM it,
 * and a thread that also owned it would clobber the shared copy. */
static uint64_t ROOT[BSW];
static uint16_t ROOTW[BSW];
static int      ROOTNW, ROOTN;
static uint64_t ROOTH0, ROOTH1;

static void root_init(void) {
    uint16_t *mem = malloc((size_t)NP * sizeof(uint16_t));
    for (int i = 0; i < NP; i++) mem[i] = (uint16_t)i;
    build_child(mem, NP, ROOT, ROOTW, &ROOTNW, &ROOTH0, &ROOTH1);
    ROOTN = NP;
    free(mem);
}

/* Load a Ctx's level 0 with a set given as an ascending member list. */
static int ctx_set_root(Ctx *c, const uint16_t *mem, int n, uint64_t *h0, uint64_t *h1) {
    build_child(mem, n, c->arena[0], c->widx[0], &c->nwid[0], h0, h1);
    return n;
}

/* Greedy playout: always follow the branch that keeps the most words alive.
 *
 * Cheap, and it does two jobs -- it is an ACHIEVABLE lower bound, so the decision
 * ladder starts high instead of at 1, and it gives a real line to print
 * immediately rather than after however long the first exact test takes.  Greedy
 * quality affects only SPEED; the ladder is what establishes the answer. */
static int greedy_len(Ctx *c, char *out, size_t outsz) {
    uint64_t cur[BSW];
    uint16_t curw[BSW];
    int curnw = ROOTNW, n = ROOTN;
    memcpy(cur, ROOT, sizeof cur);
    memcpy(curw, ROOTW, (size_t)ROOTNW * sizeof(uint16_t));
    size_t used = 0;
    out[0] = 0;
    int len = 0;
    while (n > 1) {
        int bestgp = -1, bestn = -1;
        for (int kk = 0; kk < curnw; kk++) {
            int wbase = curw[kk] << 6;
            uint64_t bits = cur[curw[kk]];
            while (bits) {
                int g = wbase + __builtin_ctzll(bits);
                bits &= bits - 1;
                split_by(c, cur, curw, curnw, g);
                for (int p = 0; p < NPAT; p++) {
                    if (p == ALL_GREEN) continue;
                    int sz = c->start[p + 1] - c->start[p];
                    if (sz > bestn) { bestn = sz; bestgp = g * NPAT + p; }
                }
            }
        }
        if (bestgp < 0) break;                /* unreachable while n > 1 */
        int g = bestgp / NPAT, p = bestgp % NPAT;
        split_by(c, cur, curw, curnw, g);
        int lo = c->start[p], hi = c->start[p + 1];
        uint64_t h0, h1;
        build_child(c->sort + lo, hi - lo, c->scratch, c->swidx, &c->snwid, &h0, &h1);
        memcpy(cur, c->scratch, sizeof cur);
        memcpy(curw, c->swidx, (size_t)c->snwid * sizeof(uint16_t));
        curnw = c->snwid;
        n = hi - lo;
        used += (size_t)snprintf(out + used, used < outsz ? outsz - used : 0,
                                 "%s%s", len ? " " : "", PWORD[g]);
        len++;
    }
    /* the survivor, named */
    for (int kk = 0; kk < curnw; kk++)
        if (cur[curw[kk]]) {
            int w = (curw[kk] << 6) + __builtin_ctzll(cur[curw[kk]]);
            snprintf(out + used, used < outsz ? outsz - used : 0,
                     "%s%s", len ? " " : "", PWORD[w]);
            break;
        }
    return len + 1;
}

/* ------------------------------------------------------- the root dispatcher
 *
 * The root's children are independent decision problems sharing only the
 * (self-verifying) table, so they parallelise directly.  Only the ROOT is split:
 * below it the recursion is sequential, which keeps the search order -- and so the
 * reported line -- identical whatever the thread count.  --threads 1 and --threads
 * N must agree on the answer; the gate checks that they do. */
static int root_can_reach(Ctx **ctxs, int nthreads, int need, int *witness) {
    Ctx *c0 = ctxs[0];
    memcpy(c0->arena[0], ROOT, sizeof ROOT);
    memcpy(c0->widx[0], ROOTW, (size_t)ROOTNW * sizeof(uint16_t));
    c0->nwid[0] = ROOTNW;

    if (ROOTN < need) return 0;

    Cand *cand = malloc((size_t)CANDPOOL * sizeof(Cand));
    if (!cand) { fprintf(stderr, "out of memory for the root candidate list\n"); exit(1); }
    int ncand = expand(c0, 0, cand, CANDPOOL);
    qsort(cand, ncand, sizeof(Cand), cand_cmp);

    int found = 0, found_gp = -1;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 1) if (nthreads > 1)
#endif
    for (int i = 0; i < ncand; i++) {
        int done;
#ifdef _OPENMP
#pragma omp atomic read
#endif
        done = found;
        if (done) continue;
        if (cand[i].bound < need - 1) continue;   /* sorted, so this is the tail */

        int tid = 0;
#ifdef _OPENMP
        tid = omp_get_thread_num();
#endif
        Ctx *c = ctxs[tid];
        int g = cand[i].gp / NPAT, p = cand[i].gp % NPAT;
        split_by(c, ROOT, ROOTW, ROOTNW, g);
        int lo = c->start[p], hi = c->start[p + 1];
        uint64_t ch0, ch1;
        int nC = ctx_set_root(c, c->sort + lo, hi - lo, &ch0, &ch1);
        if (can_reach(c, 0, nC, ch0, ch1, need - 1)) {
#ifdef _OPENMP
#pragma omp critical (eldrowmax_found)
#endif
            {
                if (!found || cand[i].gp < found_gp) found_gp = cand[i].gp;
                found = 1;
            }
        }
    }
    free(cand);
    if (found && witness) *witness = found_gp;
    return found;
}

/* Rebuild a witness line of exactly `need` words by RE-SEARCHING at each step
 * rather than trusting a stored move: the table evicts, but a repeat search of an
 * already-searched position is nearly free, and a wrong line would be worse than a
 * slow one. */
static void walk_line(Ctx *c, int need, char *out, size_t outsz) {
    uint16_t mem[MAXP];
    int n = ROOTN;
    for (int i = 0; i < NP; i++) mem[i] = (uint16_t)i;
    size_t used = 0;
    out[0] = 0;
    int left = need;
    while (left > 1) {
        uint64_t h0, h1;
        n = ctx_set_root(c, mem, n, &h0, &h1);
        Cand *cand = c->cpool + c->ctop;
        int ncand = expand(c, 0, cand, CANDPOOL - c->ctop);
        /* The reserve is not optional: can_reach below allocates its own frames
         * from the same arena, and without it they would overwrite this list. */
        c->ctop += ncand;
        qsort(cand, ncand, sizeof(Cand), cand_cmp);
        int picked = -1;
        for (int i = 0; i < ncand && picked < 0; i++) {
            if (cand[i].bound < left - 1) break;
            uint64_t ch0, ch1;
            int nC = descend(c, 0, cand[i].gp, &ch0, &ch1);
            if (can_reach(c, 1, nC, ch0, ch1, left - 1)) picked = cand[i].gp;
        }
        c->ctop -= ncand;
        if (picked < 0) {
            fprintf(stderr, "internal: no move reaches %d from a state that does\n", left);
            exit(1);
        }
        int g = picked / NPAT, p = picked % NPAT;
        split_by(c, c->arena[0], c->widx[0], c->nwid[0], g);
        int lo = c->start[p], hi = c->start[p + 1];
        for (int k = lo; k < hi; k++) mem[k - lo] = c->sort[k];
        n = hi - lo;
        used += (size_t)snprintf(out + used, used < outsz ? outsz - used : 0,
                                 "%s%s", used ? " " : "", PWORD[g]);
        left--;
    }
    if (n != 1) {
        fprintf(stderr, "internal: a longest line ended with %d words alive, not 1 --\n"
                        "  it could have been extended, so it was not longest\n", n);
        exit(1);
    }
    snprintf(out + used, used < outsz ? outsz - used : 0,
             "%s%s", used ? " " : "", PWORD[mem[0]]);
}

/* -------------------------------------------------------------------- main */

static void usage(void) {
    fprintf(stderr,
        "usage: eldrowmax --out FILE [options]   (prefer solver/run-eldrowmax.sh)\n"
        "  --out FILE       CSV to append one row per run to\n"
        "  --no-out         print only, save NOTHING -- must be explicit\n"
        "  --words PATH     the pool: candidates AND guesses (default mystery.txt)\n"
        "  --exact          compute the value outright instead of the decision\n"
        "                   ladder -- the same number, the slower way, kept as an\n"
        "                   oracle for the ladder\n"
        "  --target N       ask only whether a chain of N words exists, and stop\n"
        "  --floor N        start the ladder at N instead of the greedy playout\n"
        "  --greedy         print the greedy playout and stop (a lower bound)\n"
        "  --tt-bits B      transposition table size, 2^B entries (default 26)\n"
        "  --max-nodes N    abandon past N states; the result is then a LOWER bound\n"
        "  --threads N      threads for the root split (default: all cores)\n"
        "  --report S       heartbeat every S seconds (default 30)\n"
        "  --no-prune       drop the size bound in --exact -- the exhaustive oracle\n"
        "  --data DIR       data directory (default data, i.e. run from math/)\n");
    exit(2);
}

int main(int argc, char **argv) {
    /* Line-buffered: the wrapper pipes stdout through `tee`, and block buffering
     * on a pipe means a long run shows NOTHING in its log until it ends. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    const char *outpath = NULL, *datadir = "data", *poolpath = NULL;
    int no_out = 0, ttbits = 26, exact = 0, target = 0, floor_at = 0, greedy_only = 0;
    int nthreads = 1;

    for (int i = 1; i < argc; i++) {
        if      (!strcmp(argv[i], "--out") && i + 1 < argc)        outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out"))                     no_out = 1;
        else if (!strcmp(argv[i], "--words") && i + 1 < argc)      poolpath = argv[++i];
        else if (!strcmp(argv[i], "--exact"))                      exact = 1;
        else if (!strcmp(argv[i], "--target") && i + 1 < argc)     target = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--floor") && i + 1 < argc)      floor_at = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--greedy"))                     greedy_only = 1;
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc)    ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--max-nodes") && i + 1 < argc)  MAXNODES = atoll(argv[++i]);
        else if (!strcmp(argv[i], "--report") && i + 1 < argc)     REPORT = atof(argv[++i]);
        else if (!strcmp(argv[i], "--no-prune"))                   PRUNE = 0;
        else if (!strcmp(argv[i], "--data") && i + 1 < argc)       datadir = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) {
#ifdef _OPENMP
            omp_set_num_threads(atoi(argv[++i]));
#else
            i++;
            fprintf(stderr, "built without OpenMP; --threads ignored\n");
#endif
        }
        else usage();
    }
    if (!outpath && !no_out) {
        fprintf(stderr, "eldrowmax: give --out FILE, or --no-out to save NOTHING.\n"
                        "  A run with nowhere to put its answer is a run thrown away.\n"
                        "  Prefer the wrapper: bash solver/run-eldrowmax.sh\n");
        return 2;
    }
    if (!PRUNE && !exact) {
        fprintf(stderr, "--no-prune drops the bound the decision ladder IS. Use it\n"
                        "  with --exact, which is where the oracle lives.\n");
        return 2;
    }

    /* ------------------------------------------------------------ the lists.
     *
     * The pool words are looked up in BOTH lists the matrix is built from: the
     * guess list gives the ROW (the word as a guess), the answer list the COLUMN
     * (the word as a possible answer).  A pool word missing from either has no
     * feedback to read, so it is refused rather than skipped. */
    char path[512];
    char (*gword)[WBUF] = malloc(sizeof(*gword) * 16384);
    char (*aword)[WBUF] = malloc(sizeof(*aword) * 16384);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    int ng = load_words(path, gword, 16384);
    snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    int na = load_words(path, aword, 16384);
    snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, cc;
    pat_t *pat = load_npy(path, &r, &cc);
    if (r != ng || cc != na) {
        fprintf(stderr, "pattern matrix is %dx%d but the lists are %dx%d\n", r, cc, ng, na);
        return 1;
    }

    PWORD = malloc(sizeof(*PWORD) * MAXP);
    if (poolpath) NP = load_words(poolpath, PWORD, MAXP);
    else {
        NP = na;
        if (NP > MAXP) { fprintf(stderr, "pool %d exceeds MAXP %d\n", NP, MAXP); return 1; }
        memcpy(PWORD, aword, (size_t)NP * sizeof(*PWORD));
    }
    if (NP < 1) { fprintf(stderr, "the pool is empty\n"); return 1; }

    int *prow = malloc((size_t)NP * sizeof(int));
    int *pcol = malloc((size_t)NP * sizeof(int));
    for (int i = 0; i < NP; i++) {
        prow[i] = pcol[i] = -1;
        for (int j = 0; j < ng; j++) if (!strcmp(gword[j], PWORD[i])) { prow[i] = j; break; }
        for (int j = 0; j < na; j++) if (!strcmp(aword[j], PWORD[i])) { pcol[i] = j; break; }
        if (prow[i] < 0) {
            fprintf(stderr, "%s is not a legal guess -- it could never be played\n", PWORD[i]);
            return 1;
        }
        if (pcol[i] < 0) {
            fprintf(stderr, "%s is not in the answer list, so the matrix holds no\n"
                            "  feedback against it -- the pool must be a subset\n", PWORD[i]);
            return 1;
        }
    }
    APAT = malloc((size_t)NP * NP * sizeof(pat_t));
    if (!APAT) { fprintf(stderr, "out of memory for the %dx%d feedback matrix\n", NP, NP); return 1; }
    for (int g = 0; g < NP; g++)
        for (int w = 0; w < NP; w++)
            APAT[(size_t)g * NP + w] = pat[(size_t)prow[g] * na + pcol[w]];
    /* A word against itself is all green, and the whole termination argument rests
     * on it: it is what puts the played word in the bucket no child follows. */
    for (int g = 0; g < NP; g++)
        if (APAT[(size_t)g * NP + g] != ALL_GREEN) {
            fprintf(stderr, "internal: %s against itself is not all green\n", PWORD[g]);
            return 1;
        }
    free(pat); free(gword); free(aword); free(prow); free(pcol);

#ifdef _OPENMP
    nthreads = omp_get_max_threads();
#endif
    tt_init(ttbits);
    root_init();
    fprintf(stderr, "pool %d words (%s), threads %d\n", NP,
            poolpath ? poolpath : "mystery.txt", nthreads);

    Ctx **ctxs = malloc((size_t)nthreads * sizeof(Ctx *));
    for (int t = 0; t < nthreads; t++) ctxs[t] = ctx_new();
    Ctx *c = ctxs[0];
    T_START = wall_time();
    for (int t = 0; t < nthreads; t++) ctxs[t]->next_beat = T_START + REPORT;

    char line[65536];
    char gline[65536];
    double t_start = T_START;
    int length = 0, greedy = 0;
    const char *kind = "exact";

    greedy = greedy_len(c, gline, sizeof gline);
    printf("greedy playout: %d  %s\n", greedy, gline);
    fflush(stdout);
    snprintf(line, sizeof line, "%s", gline);
    length = greedy;

    if (greedy_only) {
        kind = "lower";
    } else if (target) {
        /* A single decision, for pricing a run before committing to the ladder. */
        int witness = -1;
        int ok = root_can_reach(ctxs, nthreads, target, &witness);
        printf("target %d: %s\n", target, ok ? "REACHED" : "not reachable");
        if (ok) { walk_line(c, target, line, sizeof line); length = target; printf("  %s\n", line); }
        else    { length = 0; }
        kind = ok ? "reached" : "unreachable";
    } else if (exact) {
        memcpy(c->arena[0], ROOT, sizeof ROOT);
        memcpy(c->widx[0], ROOTW, (size_t)ROOTNW * sizeof(uint16_t));
        c->nwid[0] = ROOTNW;
        int v = value(c, 0, ROOTN, ROOTH0, ROOTH1);
        if (v < 0) { printf("ABANDONED at --max-nodes\n"); kind = "lower"; }
        else { length = v; walk_line(c, v, line, sizeof line); }
    } else {
        int incumbent = greedy > floor_at ? greedy : floor_at;
        int verified = greedy;               /* the longest length we hold a LINE for */
        if (floor_at > greedy)
            printf("starting from --floor %d rather than the greedy %d\n", floor_at, greedy);
        for (;;) {
            int need = incumbent + 1;
            printf("trying %d ...\n", need);
            fflush(stdout);
            int witness = -1;
            double tt = wall_time();
            int ok = root_can_reach(ctxs, nthreads, need, &witness);
            long long nodes = 0;
            for (int t = 0; t < nthreads; t++) nodes += ctxs[t]->nodes;
            printf("  %d: %s  (%lld nodes, %.1fs)\n", need, ok ? "REACHED" : "no",
                   nodes, wall_time() - tt);
            fflush(stdout);
            if (!ok) break;
            incumbent = need;
            walk_line(c, incumbent, line, sizeof line);
            verified = incumbent;
            printf("        NEW LONGEST: %d  %s\n", incumbent, line);
            fflush(stdout);
        }
        /* A --floor is a CLAIM the run has not tested: the ladder only ever asked
         * about floor + 1. Make it produce its line, which re-searches and dies
         * loudly if the floor was not in fact reachable -- reporting a length with
         * a shorter run's line beside it would be the worst of both. */
        if (incumbent > verified) {
            printf("verifying the --floor %d ...\n", incumbent);
            fflush(stdout);
            walk_line(c, incumbent, line, sizeof line);
        }
        length = incumbent;
    }

    long long nodes = 0;
    int blown = 0, over = 0;
    for (int t = 0; t < nthreads; t++) {
        nodes += ctxs[t]->nodes;
        blown |= ctxs[t]->budget_blown;
        over  |= ctxs[t]->overflow;
    }
    if (over) {
        fprintf(stderr, "internal: recursion hit MAXD=%d -- raise it\n", MAXD);
        return 1;
    }
    if (blown && !strcmp(kind, "exact")) kind = "lower";
    double secs = wall_time() - t_start;

    if (target)
        printf("\nTARGET %d: %s\n%s%s\n", target, kind,
               length ? "  " : "", length ? line : "  (no line)");
    else
        printf("\nLONGEST CHAIN: %d words (%s)\n  %s\n", length, kind, line);
    if (blown)
        printf("  WARNING: --max-nodes was hit, so this is a LOWER bound, not the maximum.\n");
    printf("done in %.1fs (wall), %lld nodes\n", secs, nodes);

    if (outpath) {
        int fresh = 1;
        FILE *t = fopen(outpath, "r");
        if (t) { fresh = fgetc(t) == EOF; fclose(t); }
        FILE *out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
        if (fresh) fprintf(out, "pool,words,mode,kind,length,greedy,nodes,threads,secs,line\n");
        fprintf(out, "%s,%d,%s,%s,%d,%d,%lld,%d,%.3f,%s\n",
                poolpath ? poolpath : "mystery.txt", NP,
                greedy_only ? "greedy" : target ? "target" : exact ? "exact" : "ladder",
                kind, length, greedy, nodes, nthreads, secs, line);
        fclose(out);
    }

    for (int t = 0; t < nthreads; t++) ctx_free(ctxs[t]);
    free(ctxs);
    return 0;
}
