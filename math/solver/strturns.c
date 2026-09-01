/* strturns.c -- the W -> S cell: 12972 word guesses, ALL 26**5 strings as answers.
 *
 *     sh build.sh strturns          (from solver/)
 *     ./strturns --opener salet --depth 6
 *     ./strturns --sweep --depth 6 --out ../data/shared/strturns/opener_totals_d6.csv
 *
 * WHAT IT MINIMISES, precisely: the TOTAL guesses summed over all 11,881,376
 * length-5 strings, where the legal guesses are the 12972 words, SUBJECT TO
 * resolving every answer within --depth. All but 12972 of the answers can never
 * be PLAYED, so they are scored narrow-to-one-plus-one -- the phantom final
 * guess, exactly as optturns --phantom-final does it. The two rules agree at a
 * singleton, so `n == 1` costs 1 either way.
 *
 * WHY A SEPARATE BINARY. optturns carries the candidate set as a list of answer
 * indices: uint16_t elements, a dense NG x NA pattern matrix, arenas sized by
 * MAXA/MAXG, guess ordinals packed into 20 bits. None of that survives an answer
 * set of 11,881,376 -- the matrix alone would be 154 GB. So the candidate set is
 * carried as CONSTRAINTS instead (see ../strspace.py, the reference
 * implementation this file mirrors and is checked against):
 *
 *     allow[i]  bitmask of letters legal at position i
 *     lo[c]     how many copies of letter c the answer must hold
 *     hi[c]     how many it may hold
 *
 * 72 bytes whatever the candidate count, and hashable as-is so it doubles as the
 * transposition key.
 *
 * THE STRUCTURAL FACT THAT MAKES IT FAST. Refinement is a pure MEET: it only
 * ANDs position masks, raises floors and lowers ceilings, and its one validity
 * test (yellows are a prefix of a letter's non-green copies) depends solely on
 * the (guess, pattern) pair. So the state after any history is the meet of one
 * ATOM per (guess, pattern) played, order-independent -- which lets every atom
 * be precomputed once (12972 x 243, 227 MB) and a split become 243 meets rather
 * than 243 rederivations.
 *
 * WHY THE COUNTING DP IS TINY. A letter is tracked only if lo[c] > 0: a letter
 * with hi[c] < L and hi[c] > 0 must have been seen non-grey, so its floor is
 * already positive, and hi[c] == 0 is canonicalised out of every position mask.
 * Since sum(lo) <= 5, AT MOST FIVE letters are ever tracked, so the DP key is
 * five base-6 digits -- a direct index into 7776 slots, no hashing.
 *
 * DEPTH IS AT LEAST 6, and that is a proof, not a guess: after all-grey feedback
 * the survivors are exactly the strings over the UNGUESSED letters, (26-|L|)**5,
 * so reaching a single candidate needs 25 letters seen, hence 5 guesses, plus one
 * to name it. The measured chain confirms it: 21**5, 16**5, 11**5, 6**5, 1.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#ifdef _OPENMP
#include <omp.h>
#endif

#define L          5
#define ALPHA      26
#define NPAT       243
#define ALL_GREEN  242
#define MAXG       13000
#define MAXD       20
#define NSTR       11881376L            /* 26**5 */
#define INF        ((long long)1 << 60)

typedef struct {
    uint32_t allow[L];
    uint8_t  lo[ALPHA], hi[ALPHA];
} State;

static char    (*GWORD)[8];
static uint8_t (*GCODE)[L];
static int      NG;
static State   *ATOM;                   /* [g * NPAT + p] */
static uint8_t *AOK;                    /* atom is reachable at all */
static int32_t *WORDIDX;                /* string index -> guess index, or -1 */
static int      BRANCH = NPAT - 1;
static int      TOPK = 0;

static double now_s(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

/* ------------------------------------------------------------- state core */

/* Canonical form, or 0 if contradictory.  Mirrors strspace._canon: a letter
 * capped at zero is cleared from every mask (not just the position it was
 * guessed at), and a position with one legal letter lifts that letter's floor.
 * Both are implied, so the SET is unchanged -- but the representation becomes
 * unique, which is what makes the transposition table hit. */
static int canon(State *s) {
    for (int c = 0; c < ALPHA; c++)
        if (s->hi[c] == 0) {
            uint32_t clear = ~(1u << c);
            for (int i = 0; i < L; i++) s->allow[i] &= clear;
        }
    int forced[ALPHA] = {0}, avail[ALPHA] = {0};
    for (int i = 0; i < L; i++) {
        uint32_t m = s->allow[i];
        if (!m) return 0;
        if ((m & (m - 1)) == 0) forced[__builtin_ctz(m)]++;
        while (m) { avail[__builtin_ctz(m)]++; m &= m - 1; }
    }
    int sumlo = 0;
    for (int c = 0; c < ALPHA; c++) {
        if (forced[c] > s->lo[c]) s->lo[c] = (uint8_t)forced[c];
        if (s->lo[c] > s->hi[c] || s->lo[c] > avail[c]) return 0;
        sumlo += s->lo[c];
    }
    return sumlo <= L;
}

static int meet(State *out, const State *a, const State *b) {
    for (int i = 0; i < L; i++) {
        out->allow[i] = a->allow[i] & b->allow[i];
        if (!out->allow[i]) return 0;
    }
    for (int c = 0; c < ALPHA; c++) {
        out->lo[c] = a->lo[c] > b->lo[c] ? a->lo[c] : b->lo[c];
        out->hi[c] = a->hi[c] < b->hi[c] ? a->hi[c] : b->hi[c];
        if (out->lo[c] > out->hi[c]) return 0;
    }
    return canon(out);
}

static const int POW6[L] = {1, 6, 36, 216, 1296};

/* Exact candidate count.  Never enumerates: a DP across positions whose key is
 * the count vector of the tracked letters, packed as base-6 digits.  At most
 * five letters are ever tracked (see the header), so the key fits 7776 slots and
 * only the touched ones are cleared between levels. */
static uint64_t count_state(const State *s) {
    int con[L], nc = 0;
    uint32_t conmask = 0;
    for (int c = 0; c < ALPHA; c++)
        if (s->lo[c]) {
            if (nc == L) return 0;              /* sum(lo) > L: canon rejects */
            con[nc++] = c;
            conmask |= 1u << c;
        }
    if (!nc) {
        uint64_t t = 1;
        for (int i = 0; i < L; i++) t *= (uint64_t)__builtin_popcount(s->allow[i]);
        return t;
    }

    static __thread uint64_t dp[7776], nd[7776];
    static __thread int act[7776], nact2[7776];
    int na = 0;
    dp[0] = 1; act[na++] = 0;

    for (int i = 0; i < L; i++) {
        uint32_t m = s->allow[i];
        int free_here = __builtin_popcount(m & ~conmask);
        int nb = 0;
        for (int k = 0; k < na; k++) {
            int key = act[k];
            uint64_t w = dp[key];
            dp[key] = 0;
            if (!w) continue;
            if (free_here) {
                if (!nd[key]) nact2[nb++] = key;
                nd[key] += w * (uint64_t)free_here;
            }
            for (int j = 0; j < nc; j++) {
                if (!(m >> con[j] & 1)) continue;
                if ((key / POW6[j]) % 6 >= s->hi[con[j]]) continue;
                int nk = key + POW6[j];
                if (!nd[nk]) nact2[nb++] = nk;
                nd[nk] += w;
            }
        }
        for (int k = 0; k < nb; k++) { dp[nact2[k]] = nd[nact2[k]]; nd[nact2[k]] = 0; act[k] = nact2[k]; }
        na = nb;
        if (!na) return 0;
    }

    uint64_t total = 0;
    for (int k = 0; k < na; k++) {
        int key = act[k];
        int ok = 1;
        for (int j = 0; j < nc; j++)
            if ((key / POW6[j]) % 6 < s->lo[con[j]]) { ok = 0; break; }
        if (ok) total += dp[key];
        dp[key] = 0;
    }
    return total;
}

/* Every candidate, up to `limit`.  Only ever called on states already known to
 * be tiny (the n == 2 base case), never on the real space. */
static int enum_small(const State *s, uint8_t out[][L], int limit) {
    uint8_t cnt[ALPHA] = {0}, cur[L];
    int found = 0;
    int stack[L + 1]; uint32_t rem[L + 1];
    int i = 0; rem[0] = s->allow[0]; stack[0] = -1;
    while (i >= 0) {
        if (stack[i] >= 0) cnt[cur[i]]--;
        if (!rem[i]) { i--; continue; }
        int c = __builtin_ctz(rem[i]);
        rem[i] &= rem[i] - 1;
        if (cnt[c] >= s->hi[c]) { stack[i] = -1; continue; }
        cur[i] = (uint8_t)c; cnt[c]++; stack[i] = c;
        int need = 0;
        for (int d = 0; d < ALPHA; d++) if (s->lo[d] > cnt[d]) need += s->lo[d] - cnt[d];
        if (need > L - 1 - i) { cnt[c]--; stack[i] = -1; continue; }
        if (i == L - 1) {
            if (found < limit) memcpy(out[found], cur, L);
            found++;
            cnt[c]--; stack[i] = -1;
            if (found > limit) return found;
            continue;
        }
        i++; rem[i] = s->allow[i]; stack[i] = -1;
    }
    return found;
}

static long strindex(const uint8_t *w) {
    long v = 0;
    for (int i = 0; i < L; i++) v = v * ALPHA + w[i];
    return v;
}

/* --------------------------------------------------------------- patterns */

static int pattern_codes(const uint8_t *g, const uint8_t *a) {
    int tiles[L] = {0}, used[L] = {0};
    for (int i = 0; i < L; i++) if (g[i] == a[i]) { tiles[i] = 2; used[i] = 1; }
    for (int i = 0; i < L; i++)
        if (!tiles[i])
            for (int j = 0; j < L; j++)
                if (!used[j] && g[i] == a[j]) { tiles[i] = 1; used[j] = 1; break; }
    int code = 0;
    for (int i = 0; i < L; i++) code = code * 3 + tiles[i];
    return code;
}

/* The atom for (guess, pattern): the constraint that feedback imposes, applied
 * to the unconstrained root.  Returns 0 when the pattern is UNREACHABLE. */
static int build_atom(State *s, const uint8_t *g, int code) {
    int tiles[L], c = code;
    for (int i = L - 1; i >= 0; i--) { tiles[i] = c % 3; c /= 3; }

    /* Yellows are a PREFIX of a letter's non-green copies: pattern() hands out
     * the answer's spare copies left to right, so a grey followed by a yellow of
     * the SAME letter can never be produced.  The count bounds cannot see this
     * (both orders give identical lo/hi), so without this test `abbey` reports
     * patterns that do not exist.  A distinct-letter guess never exercises it. */
    int seen_grey[ALPHA] = {0};
    for (int i = 0; i < L; i++) {
        if (tiles[i] == 2) continue;
        if (tiles[i] == 0) seen_grey[g[i]] = 1;
        else if (seen_grey[g[i]]) return 0;
    }

    uint32_t full = (1u << ALPHA) - 1;
    for (int i = 0; i < L; i++) s->allow[i] = full;
    for (int cc = 0; cc < ALPHA; cc++) { s->lo[cc] = 0; s->hi[cc] = L; }

    int nongrey[ALPHA] = {0}, grey[ALPHA] = {0};
    for (int i = 0; i < L; i++) {
        if (tiles[i]) nongrey[g[i]]++;
        else grey[g[i]] = 1;
    }
    for (int i = 0; i < L; i++) {
        if (tiles[i] == 2) s->allow[i] &= 1u << g[i];
        else               s->allow[i] &= ~(1u << g[i]);
        if (!s->allow[i]) return 0;
    }
    for (int cc = 0; cc < ALPHA; cc++) {
        if (nongrey[cc] > s->lo[cc]) s->lo[cc] = (uint8_t)nongrey[cc];
        if (grey[cc] && nongrey[cc] < s->hi[cc]) s->hi[cc] = (uint8_t)nongrey[cc];
        if (s->lo[cc] > s->hi[cc]) return 0;
    }
    return canon(s);
}

/* --------------------------------------------- transposition table + bound */

typedef struct { uint64_t h0, h1x; long long val; int32_t d; uint32_t work; } Entry;
static Entry   *TT;
static uint64_t TT_BUCKETS;
static int      TT_OFF = 0;

static void hash_state(const State *s, int d, uint64_t *h0, uint64_t *h1) {
    uint64_t a = 0xcbf29ce484222325ULL ^ (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    uint64_t b = 0x9ae16a3b2f90404fULL + (uint64_t)d;
    const uint8_t *p = (const uint8_t *)s;
    for (size_t i = 0; i < sizeof(State); i++) {
        a = (a ^ p[i]) * 0x100000001b3ULL;
        b = (b + p[i]) * 0xff51afd7ed558ccdULL;
        b ^= b >> 29;
    }
    *h0 = a ? a : 1; *h1 = b;
}

static int tt_get(uint64_t h0, uint64_t h1, int d, long long *val) {
    if (TT_OFF) return 0;
    Entry *bk = TT + (h0 & (TT_BUCKETS - 1)) * 2;
    for (int i = 0; i < 2; i++)
        if (bk[i].h0 == h0 && bk[i].h1x == (h1 ^ (uint64_t)bk[i].val) && bk[i].d == d) {
            *val = bk[i].val; return 1;
        }
    return 0;
}

static void tt_put(uint64_t h0, uint64_t h1, int d, long long val, uint32_t work) {
    if (TT_OFF) return;
    Entry e; e.h0 = h0; e.val = val; e.h1x = h1 ^ (uint64_t)val; e.d = d; e.work = work;
    Entry *bk = TT + (h0 & (TT_BUCKETS - 1)) * 2;
    if (bk[0].h0 == 0) { bk[0] = e; return; }
    if (bk[1].h0 == 0) { bk[1] = e; return; }
    if (work >= bk[0].work) { bk[1] = bk[0]; bk[0] = e; } else bk[1] = e;
}

/* Counting lower bound: one guess resolves at most 1 candidate, then at most
 * BRANCH per level.  Blind to bin SIZES, so it is loose -- but sound, and it is
 * what orders the guess loop and cuts hopeless branches. */
static long long lbound(uint64_t n, int d) {
    if (n == 0) return 0;
    unsigned long long rem = n, cap = 1;
    long long total = 0;
    for (int k = 1; k <= d; k++) {
        unsigned long long take = rem < cap ? rem : cap;
        total += (long long)take * k;
        rem -= take;
        if (!rem) return total;
        if (cap < (unsigned long long)NSTR) cap *= (unsigned)BRANCH;
    }
    return INF;
}

typedef struct {
    State    subs[MAXD][NPAT];
    uint64_t cn[MAXD][NPAT];
    int      pats[MAXD][NPAT];
    long long lbg[MAXD][MAXG];
    int64_t  ord[MAXD][MAXG];
    long long nodes;
} Ctx;

static long long solve(const State *st, uint64_t n, int d, Ctx *ctx);

static long long eval_guess(const State *st, uint64_t n, int d, int g,
                            long long best, Ctx *ctx) {
    State *subs = ctx->subs[d];
    uint64_t *cn = ctx->cn[d];
    int np = 0;
    const State *at = ATOM + (size_t)g * NPAT;
    const uint8_t *ok = AOK + (size_t)g * NPAT;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p] || p == ALL_GREEN) continue;
        State tmp;
        if (!meet(&tmp, st, &at[p])) continue;
        uint64_t c = count_state(&tmp);
        if (!c) continue;
        subs[np] = tmp; cn[np] = c; np++;
    }
    if (np == 1 && cn[0] == n) return INF;      /* reveals nothing */

    long long lbrest = 0;
    for (int k = 0; k < np; k++) {
        long long v = lbound(cn[k], d - 1);
        if (v >= INF) return INF;
        lbrest += v;
    }
    long long total = (long long)n;
    for (int k = 0; k < np; k++) {
        long long own = lbound(cn[k], d - 1);
        lbrest -= own;
        if (total + lbrest + own >= best) return INF;
        long long v = solve(&subs[k], cn[k], d - 1, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest >= best) return INF;
    }
    return total;
}

static long long solve(const State *st, uint64_t n, int d, Ctx *ctx) {
    if (n == 1) return 1;                       /* played, or the phantom naming move */
    if (d <= 1) return INF;
    if (n == 2) {
        /* Either candidate playable: guess it -- 1 if right, 2 if not.  Neither
         * playable: the pair must be SPLIT and each half then costs its own
         * phantom move, so 2 + 1 + 1 = 4, and the first separating guess proves
         * it because one guess cannot resolve a candidate it cannot name. */
        uint8_t two[2][L];
        if (enum_small(st, two, 2) == 2) {
            if (WORDIDX[strindex(two[0])] >= 0 || WORDIDX[strindex(two[1])] >= 0) return 3;
            for (int g = 0; g < NG; g++)
                if (pattern_codes(GCODE[g], two[0]) != pattern_codes(GCODE[g], two[1]))
                    return 4;
            return INF;                         /* no guess separates them */
        }
    }
    /* Depth normalisation: n candidates always resolve within n guesses (any
     * splitting guess drops the largest bucket to n-1, so f(n) <= 1 + f(n-1)),
     * so beyond that the budget cannot bind and f(S,d) == f(S,n).  Collapsing
     * the key is what makes small states hit in the table. */
    if ((uint64_t)d > n) d = (int)n;

    long long lb0 = lbound(n, d);
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(st, d, &h0, &h1);
    long long cached;
    if (tt_get(h0, h1, d, &cached)) return cached;

    long long nodes0 = ctx->nodes++;
    long long best = INF;

    /* Pass 1: each guess's partition profile gives its lower bound, and (under
     * --topk) its sum of squared bin sizes -- the split-quality score the K
     * survivors are chosen by, computed from the same counts. */
    long long *lbg = ctx->lbg[d];
    int64_t *ord = ctx->ord[d];
    int m = 0;
    for (int g = 0; g < NG; g++) {
        const State *at = ATOM + (size_t)g * NPAT;
        const uint8_t *ok = AOK + (size_t)g * NPAT;
        long long lv = (long long)n;
        int dead = 0, np = 0;
        unsigned long long ss = 0, biggest = 0;
        for (int p = 0; p < NPAT; p++) {
            if (!ok[p] || p == ALL_GREEN) continue;
            State tmp;
            if (!meet(&tmp, st, &at[p])) continue;
            uint64_t c = count_state(&tmp);
            if (!c) continue;
            np++;
            if (c > biggest) biggest = c;
            ss += (unsigned long long)c * c;
            long long v = lbound(c, d - 1);
            if (v >= INF) { dead = 1; break; }
            lv += v;
        }
        if (dead || (np == 1 && biggest == n)) { lbg[g] = INF; continue; }
        lbg[g] = lv;
        ord[m++] = ((int64_t)(TOPK > 0 ? (int64_t)(ss >> 12) : lv) << 20) | g;
    }
    if (!m) { tt_put(h0, h1, d, INF, 1); return INF; }

    for (int i = 1; i < m; i++) {                /* ascending by key */
        int64_t k = ord[i]; int j = i - 1;
        while (j >= 0 && ord[j] > k) { ord[j + 1] = ord[j]; j--; }
        ord[j + 1] = k;
    }
    int lim = (TOPK > 0 && TOPK < m) ? TOPK : m;
    for (int i = 0; i < lim; i++) {
        int g = (int)(ord[i] & 0xFFFFF);
        if (TOPK == 0 && lbg[g] >= best) break;  /* sorted by lb: none left can win */
        long long v = eval_guess(st, n, d, g, best, ctx);
        if (v < best) best = v;
        if (best <= lb0) break;                  /* provably optimal */
    }
    long long work = ctx->nodes - nodes0;
    tt_put(h0, h1, d, best, work > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)work);
    return best;
}

/* ------------------------------------------------------------ root driver */

static void root_state(State *s) {
    uint32_t full = (1u << ALPHA) - 1;
    for (int i = 0; i < L; i++) s->allow[i] = full;
    for (int c = 0; c < ALPHA; c++) { s->lo[c] = 0; s->hi[c] = L; }
}

static long long solve_opener(int g, int depth, Ctx *ctx) {
    State root; root_state(&root);
    const State *at = ATOM + (size_t)g * NPAT;
    const uint8_t *ok = AOK + (size_t)g * NPAT;
    long long total = NSTR;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p] || p == ALL_GREEN) continue;
        State sub;
        if (!meet(&sub, &root, &at[p])) continue;
        uint64_t c = count_state(&sub);
        if (!c) continue;
        long long v = solve(&sub, c, depth - 1, ctx);
        if (v >= INF) return INF;
        total += v;
    }
    return total;
}

static int measure_branching(void) {
    State root; root_state(&root);
    int best = 1;
    for (int g = 0; g < NG; g++) {
        const State *at = ATOM + (size_t)g * NPAT;
        const uint8_t *ok = AOK + (size_t)g * NPAT;
        int k = 0;
        for (int p = 0; p < NPAT; p++) {
            if (!ok[p] || p == ALL_GREEN) continue;
            State sub;
            if (meet(&sub, &root, &at[p]) && count_state(&sub)) k++;
        }
        if (k > best) best = k;
    }
    return best;
}


/* ------------------------------------------------------------- self test */

/* Replay a DETERMINISTIC pseudo-random walk of (guess, pattern) refinements and
 * print the candidate count at every step.  `tools/checkstrturns.py` reproduces
 * the identical walk through strspace.py -- which is itself checked exhaustively
 * against brute force -- so any divergence between this file's meet/canon/count
 * and the reference shows up as a differing NUMBER rather than as a plausible
 * wrong total buried in a sweep.  The arithmetic below must stay bit-identical
 * to the Python side.
 */
static void selftest(int nwalk) {
    for (int seed = 0; seed < nwalk; seed++) {
        State st; root_state(&st);
        printf("%d root %llu\n", seed, (unsigned long long)count_state(&st));
        for (int step = 0; step < 4; step++) {
            unsigned long long r = (unsigned long long)seed * 2654435761ULL
                                 + (unsigned long long)step * 40503ULL + 12345ULL;
            r ^= r >> 17; r *= 0x9E3779B97F4A7C15ULL; r ^= r >> 31;
            int g = (int)(r % (unsigned)NG);
            int p = (int)((r >> 20) % NPAT);
            State nx;
            if (!AOK[(size_t)g * NPAT + p] || !meet(&nx, &st, &ATOM[(size_t)g * NPAT + p])) {
                printf("%d %s %d DEAD\n", seed, GWORD[g], p);
                break;
            }
            st = nx;
            printf("%d %s %d %llu\n", seed, GWORD[g], p,
                   (unsigned long long)count_state(&st));
        }
    }
}

/* ------------------------------------------------------------------- main */

static int load_words(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char buf[64];
    int n = 0;
    while (fgets(buf, sizeof buf, f)) {
        int len = 0;
        while (buf[len] >= 'a' && buf[len] <= 'z') len++;
        if (len != L) continue;
        if (n >= MAXG) { fprintf(stderr, "more than %d guesses\n", MAXG); exit(1); }
        memcpy(GWORD[n], buf, L); GWORD[n][L] = 0;
        for (int i = 0; i < L; i++) GCODE[n][i] = (uint8_t)(buf[i] - 'a');
        n++;
    }
    fclose(f);
    return n;
}

int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL;
    const char *openers[64]; int nopen = 0;
    int depth = 6, depthmax = -1, ttbits = 26, threads = 0, sweep = 0, selftest_n = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--selftest") && i + 1 < argc) selftest_n = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth-max") && i + 1 < argc) depthmax = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if ((!strcmp(argv[i], "--topk") || !strcmp(argv[i], "-k")) && i + 1 < argc)
            TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (depth < 1 || depth >= MAXD) { fprintf(stderr, "--depth out of range\n"); return 1; }
    if (depthmax < depth) depthmax = depth;

    char path[1024];
    GWORD = malloc(sizeof(char[8]) * MAXG);
    GCODE = malloc(sizeof(uint8_t[L]) * MAXG);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path);
    fprintf(stderr, "loaded %d guesses x %ld strings (%d letters)\n", NG, NSTR, L);

    WORDIDX = malloc(sizeof(int32_t) * NSTR);
    for (long i = 0; i < NSTR; i++) WORDIDX[i] = -1;
    for (int g = 0; g < NG; g++) WORDIDX[strindex(GCODE[g])] = g;

    double t0 = now_s();
    ATOM = malloc(sizeof(State) * (size_t)NG * NPAT);
    AOK  = calloc((size_t)NG * NPAT, 1);
    if (!ATOM || !AOK) { fprintf(stderr, "out of memory for atoms\n"); return 1; }
    long nat = 0;
    for (int g = 0; g < NG; g++)
        for (int p = 0; p < NPAT; p++)
            if (build_atom(&ATOM[(size_t)g * NPAT + p], GCODE[g], p)) {
                AOK[(size_t)g * NPAT + p] = 1; nat++;
            }
    fprintf(stderr, "atoms: %ld reachable of %ld (%.0f MB, %.1fs)\n",
            nat, (long)NG * NPAT, sizeof(State) * (double)NG * NPAT / 1e6, now_s() - t0);

    if (selftest_n) { selftest(selftest_n); return 0; }

    BRANCH = measure_branching();
    fprintf(stderr, "branching: %d non-winning bins (max over %d guesses)\n", BRANCH, NG);
    fprintf(stderr, "root LB(d=%d, n=%ld) = %lld  (%.5f avg)\n",
            depth, NSTR, lbound(NSTR, depth), (double)lbound(NSTR, depth) / NSTR);

    if (ttbits <= 0) { TT_OFF = 1; fprintf(stderr, "TT: disabled\n"); }
    else {
        TT_BUCKETS = 1ULL << ttbits;
        TT = calloc(TT_BUCKETS * 2, sizeof(Entry));
        if (!TT) { fprintf(stderr, "cannot allocate TT\n"); return 1; }
        fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", ttbits,
                TT_BUCKETS * 2.0 * sizeof(Entry) / 1e9);
    }
#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#else
    (void)threads; fprintf(stderr, "threads: 1 (no OpenMP)\n");
#endif
    fprintf(stderr, "phantom-final: %ld of %ld answers are not legal guesses\n",
            NSTR - NG, NSTR);

    FILE *out = outpath ? fopen(outpath, "a") : NULL;
    if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
    if (out) { fprintf(out, "word,total,expected,depth,seconds\n"); fflush(out); }

    if (!sweep && nopen == 0) { openers[nopen++] = "salet"; }

    if (!sweep) {
        Ctx *ctx = calloc(1, sizeof(Ctx));
        for (int i = 0; i < nopen; i++) {
            int g = -1;
            for (int k = 0; k < NG; k++) if (!strcmp(GWORD[k], openers[i])) { g = k; break; }
            if (g < 0) { fprintf(stderr, "%s is not a legal guess\n", openers[i]); continue; }
            /* Escalate the cap one guess at a time up to --depth-max, so the
             * run reports the MINIMUM FEASIBLE depth as well as the total.
             * NOTE what that is and is not: f(S,d) is non-increasing in d, so a
             * still-deeper cap may admit a LOWER total by letting one answer run
             * long to save guesses elsewhere.  The number is optimal SUBJECT TO
             * the depth reported, not an unconstrained minimum. */
            double s0 = now_s();
            long long total = INF;
            int used = 0;
            for (int dd = depth; dd <= depthmax; dd++) {
                double d0 = now_s();
                total = solve_opener(g, dd, ctx);
                if (total < INF) { used = dd; break; }
                printf("%s  INFEASIBLE at depth %d  (%.1fs, %lld nodes)%s\n",
                       GWORD[g], dd, now_s() - d0, ctx->nodes,
                       dd < depthmax ? " -- escalating" : " -- that was --depth-max");
                fflush(stdout);
            }
            double dt = now_s() - s0;
            if (total < INF)
                printf("%s  total=%lld  expected=%.5f  d=%d  (%.1fs, %lld nodes)\n",
                       GWORD[g], total, (double)total / NSTR, used, dt, ctx->nodes);
            fflush(stdout);
            depth = used ? used : depth;
            if (out) {
                if (total >= INF) fprintf(out, "%s,,,,%.1f\n", GWORD[g], dt);
                else fprintf(out, "%s,%lld,%.5f,%d,%.1f\n",
                             GWORD[g], total, (double)total / NSTR, depth, dt);
                fflush(out);
            }
        }
        free(ctx);
    } else {
        double sw = now_s();
        int completed = 0;
#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            Ctx *ctx = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
            for (int g = 0; g < NG; g++) {
                double s0 = now_s();
                long long total = solve_opener(g, depth, ctx);
                double dt = now_s() - s0;
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    completed++;
                    double el = now_s() - sw;
                    if (total >= INF)
                        printf("[%7.0fs] %5d/%d  %s  INFEASIBLE d>%d  %7.1fs\n",
                               el, completed, NG, GWORD[g], depth, dt);
                    else
                        printf("[%7.0fs] %5d/%d  %s  total=%lld  exp=%.5f  %7.1fs\n",
                               el, completed, NG, GWORD[g], total,
                               (double)total / NSTR, dt);
                    fflush(stdout);
                    if (out) {
                        if (total >= INF) fprintf(out, "%s,,,,%.1f\n", GWORD[g], dt);
                        else fprintf(out, "%s,%lld,%.5f,%d,%.1f\n",
                                     GWORD[g], total, (double)total / NSTR, depth, dt);
                        fflush(out);
                    }
                }
            }
            free(ctx);
        }
    }
    if (out) fclose(out);
    return 0;
}
