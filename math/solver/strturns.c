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
/* Bounds the per-thread arena, which is indexed BY DEPTH so recursion levels
 * cannot clobber each other -- an array bound, not a modelling limit. Costs
 * ~0.23 MB per thread per level (lbg and ord dominate), so headroom is cheap.
 * 20 was carried over from optturns.c, where the answer set is 2315; there is
 * no reason for a problem with 11,881,376 answers to inherit it. */
#define MAXD       32
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

/* --allow-unsolved changes the OBJECTIVE, which is why it is opt-in.
 *
 * By default, failing to resolve an answer within --depth is fatal: solve()
 * returns INF and the whole opener reports INFEASIBLE, with no way to say how
 * much was unreachable.  Under --allow-unsolved, exceeding the cap becomes a
 * COUNTED VIOLATION instead, and the objective becomes LEXICOGRAPHIC: fewest
 * unsolved answers first, then fewest guesses.
 *
 * A total produced this way is NOT the same quantity as the default one and is
 * NOT comparable with the other cells of the grid -- it is "the best coverage
 * achievable at this cap, and the cheapest way to achieve that coverage".  Every
 * line that prints it says `unsolved=` so the two can never be confused.
 *
 * Both halves ride in ONE long long: unsolved * USCALE + guesses.  Guesses can
 * never reach USCALE (at most NSTR * MAXD, about 3.8e8), so the fields do not
 * carry into each other and plain integer add and compare give exactly the
 * lexicographic order.  INF stays far above any real packed value. */
/* --by-class: collapse guesses that the CURRENT state cannot tell apart.
 *
 * Two letters are interchangeable when they have the same (lo, hi) and are
 * allowed at the same positions; two positions are interchangeable when their
 * allow masks are equal.  Each condition is an exact automorphism of the state,
 * so guesses in one orbit have ISOMORPHIC partitions -- identical bucket sizes,
 * hence identical sum of squares and identical lower bound.  Early on the classes
 * are coarse (after one guess, the 21 unmentioned letters are a single class),
 * which is where the collapse is worth the most: 12972 guesses become 5 classes
 * at the root and 16 in the all-grey child.
 *
 * IT IS SOUND FOR PROFILES, NOT FOR VALUES.  The answer set is symmetric under
 * letter permutation; THE WORD LIST IS NOT.  Two guesses in one class produce
 * isomorphic partitions, but their children differ by a letter permutation and a
 * child's value depends on which words are legal guesses inside it -- which no
 * letter permutation preserves.  So a representative's VALUE does not transfer to
 * its class.
 *
 * That is why this is restricted to --topk 1 and refuses to run otherwise.  There
 * it is not even an approximation: --topk ranks by sum of squares, every class
 * member ties, and ties already break on the lowest guess index -- so taking the
 * lowest-index member of each class picks exactly the word plain --topk 1 picks.
 * Same answer, far less work, and plain --topk 1 is its oracle. */
/* --small-n N: below N candidates, PROFILE guesses by computing patterns against
 * the enumerated candidates directly instead of meeting 243 constraint atoms.
 *
 * MEASURED, and it is the reason this exists: the atom path costs ~25 us per
 * guess at ONE candidate and ~119 us at a million -- the floor is building 243
 * atoms, which does not care how many candidates there are.  Direct patterns cost
 * O(n) instead, so at n = 10 the profiling pass drops by two orders of magnitude,
 * and that is where nearly every node lives.
 *
 * Only the PROFILING changes.  The chosen guess's children are still built by
 * meet, so the state representation, the transposition table and every value are
 * untouched -- which is what lets the existing W -> S result serve as its oracle.
 *
 * OFF BY DEFAULT so nothing already running changes behaviour. */
/* --guess-space all: the legal guesses become EVERY 26**5 string rather than the
 * 12972 words -- the S -> S cell.  The guess set cannot be listed and its atoms
 * cannot be precomputed (208 GB), so at each node one representative per symmetry
 * class is enumerated (see enum_reps) and its atoms are built transiently.
 *
 * MEASURED class counts: 7 at the root, 36 down an all-grey line, 173-174 once a
 * green pins a position.  So the guess space stays in the hundreds at every node,
 * which is what makes this affordable at all. */
static int      ALL_GUESSES = 0;
#define MAXREPS 4096
/* The ROOT's guess classes.  Openers are chosen from these under
 * --guess-space all, and they outlive any one node, so they are held here rather
 * than on a stack frame. */
static uint8_t  ROOTREPS[MAXREPS][L];
static int      NROOTREPS = 0;

/* A guess, however it was obtained: its letter codes plus its 243 atoms.  The
 * word-list path points at the precomputed tables; the 26**5 path points at a
 * transient buffer.  ONE representation, so the search has one implementation
 * rather than one per guess source. */
typedef struct { const uint8_t *gc; const State *at; const uint8_t *ok; } Guess;

static int      SMALL_N = 0;
#define SMALL_MAX 512

static int      BY_CLASS = 0;
static int      ALLOW_UNSOLVED = 0;
static int      LIST_UNSOLVED = 100;
#define USCALE      1000000000LL
#define UNS(v)      ((v) / USCALE)
#define GUESSES(v)  ((v) % USCALE)

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

/* ------------------------------------------- representative guesses over 26**5
 *
 * For the S -> S cell the guess set is every length-5 string, so it can neither
 * be listed nor have its atoms precomputed (11881376 x 243 atoms would be 208 GB).
 * It does not need to be: guesses in one symmetry orbit have isomorphic
 * partitions, so only ONE PER CLASS has to be profiled -- and the classes are
 * bounded no matter how deep the search goes.
 *
 * THE BOUND.  A tracked letter needs lo > 0, the floors sum to at most L, greys
 * all collapse into one class (hi == 0 clears them from every mask), and the
 * never-mentioned letters are a second.  So a state has AT MOST L + 2 = 7 letter
 * classes, always.  A representative is then a set partition of the 5 positions
 * with a class assigned to each block, which caps the enumeration at roughly
 * sum_b S(5,b) * 7^b -- tens of thousands, against 11881376 raw guesses.
 *
 * RGS5 holds the 52 restricted-growth strings, i.e. the set partitions of five
 * positions: RGS5[i][j] is the block containing position j. */
static uint8_t RGS5[52][L];
static int     NRGS5 = 0;

static void build_rgs(void) {
    uint8_t a[L];
    a[0] = 0;
    for (;;) {
        memcpy(RGS5[NRGS5++], a, L);
        int i = L - 1;
        for (;;) {
            if (i == 0) return;
            int mx = 0;
            for (int j = 0; j < i; j++) if (a[j] > mx) mx = a[j];
            if (a[i] <= mx) { a[i]++; break; }
            a[i] = 0; i--;
        }
        for (int j = i + 1; j < L; j++) a[j] = 0;
    }
}

static uint8_t PERM5[120][L];
static int     NPERM5 = 0;

static void build_perms(void) {
    uint8_t p[L];
    for (int i = 0; i < L; i++) p[i] = (uint8_t)i;
    /* plain lexicographic next-permutation walk; L is 5, so this is 120 of them */
    for (;;) {
        memcpy(PERM5[NPERM5++], p, L);
        int i = L - 2;
        while (i >= 0 && p[i] >= p[i + 1]) i--;
        if (i < 0) break;
        int j = L - 1;
        while (p[j] <= p[i]) j--;
        uint8_t t = p[i]; p[i] = p[j]; p[j] = t;
        for (int a = i + 1, b = L - 1; a < b; a++, b--) { t = p[a]; p[a] = p[b]; p[b] = t; }
    }
}

/* The state's symmetry: which letters are interchangeable, and which position
 * permutations leave the state fixed. */
typedef struct {
    uint8_t lclass[ALPHA];
    uint8_t perm[120][L];
    int     nperm;
} Sym;

static void build_sym(const State *s, Sym *sy) {
    uint32_t lkey[ALPHA];
    for (int c = 0; c < ALPHA; c++) {
        uint32_t pm = 0;
        for (int i = 0; i < L; i++) if (s->allow[i] >> c & 1) pm |= 1u << i;
        lkey[c] = ((uint32_t)s->lo[c] << 16) | ((uint32_t)s->hi[c] << 8) | pm;
    }
    int nc = 0;
    for (int c = 0; c < ALPHA; c++) {
        int j = 0;
        while (j < c && lkey[j] != lkey[c]) j++;
        sy->lclass[c] = (j < c) ? sy->lclass[j] : (uint8_t)nc++;
    }
    uint8_t pclass[L];
    int np = 0;
    for (int i = 0; i < L; i++) {
        int j = 0;
        while (j < i && s->allow[j] != s->allow[i]) j++;
        pclass[i] = (j < i) ? pclass[j] : (uint8_t)np++;
    }
    sy->nperm = 0;
    for (int k = 0; k < NPERM5; k++) {
        int ok = 1;
        for (int i = 0; i < L && ok; i++) if (pclass[PERM5[k][i]] != pclass[i]) ok = 0;
        if (ok) memcpy(sy->perm[sy->nperm++], PERM5[k], L);
    }
}

/* Canonical key of a guess under `sy`: the lexicographic minimum, over the
 * state's position permutations, of the sequence of (letter class, occurrence
 * within that class in order of first appearance).  Two guesses share a key
 * exactly when the state cannot tell them apart. */
/* The key packs L fields of 8 bits, so it never exceeds 2**40 and is always
 * positive as a long long -- do NOT shift it right to "make room for the sign".
 * A >> 1 drops the low bit of the last field, which silently MERGES two classes
 * whose final letter differs only in its occurrence index. */
static uint64_t canon_guess(const uint8_t *g, const Sym *sy) {
    uint64_t best = ~0ULL;
    for (int k = 0; k < sy->nperm; k++) {
        const uint8_t *pm = sy->perm[k];
        uint8_t lets[L], ids[L];
        int nl = 0;
        uint64_t key = 0;
        for (int i = 0; i < L; i++) {
            int c = g[pm[i]], j = 0;
            while (j < nl && lets[j] != c) j++;
            if (j == nl) {
                int seen = 0;
                for (int q = 0; q < nl; q++)
                    if (sy->lclass[lets[q]] == sy->lclass[c]) seen++;
                lets[nl] = (uint8_t)c; ids[nl] = (uint8_t)seen; nl++;
            }
            key = (key << 8) | ((uint64_t)sy->lclass[c] << 3) | ids[j];
        }
        if (key < best) best = key;
    }
    return best;
}

/* Every guess class of the FULL 26**5 space, one representative each, as letter
 * codes.  Returns how many were written (capped at `max`).
 *
 * For each set partition of the positions, assign a letter class to each block
 * and materialise it with distinct letters drawn from that class.  Distinct
 * assignments can still be the same class -- two blocks both drawn from the
 * "never mentioned" letters -- so the results are canonicalised and deduped, and
 * what comes back is one guess per orbit under the state's symmetry. */
static int enum_reps(const Sym *sy, uint8_t (*out)[L], int max, uint64_t *keys) {
    int member[ALPHA][ALPHA], nmem[ALPHA] = {0}, nclass = 0;
    for (int c = 0; c < ALPHA; c++) {
        int k = sy->lclass[c];
        if (k + 1 > nclass) nclass = k + 1;
        member[k][nmem[k]++] = c;
    }
    int n = 0;
    for (int r = 0; r < NRGS5; r++) {
        const uint8_t *rgs = RGS5[r];
        int nb = 0;
        for (int i = 0; i < L; i++) if (rgs[i] + 1 > nb) nb = rgs[i] + 1;
        int pick[L];                      /* block -> class */
        for (int i = 0; i < nb; i++) pick[i] = 0;
        for (;;) {
            int used[ALPHA] = {0}, ok = 1;
            uint8_t g[L];
            for (int b = 0; b < nb && ok; b++) {
                int cl = pick[b];
                if (used[cl] >= nmem[cl]) ok = 0;   /* class has no letter left */
                else {
                    int letter = member[cl][used[cl]++];
                    for (int i = 0; i < L; i++) if (rgs[i] == b) g[i] = (uint8_t)letter;
                }
            }
            if (ok) {
                uint64_t key = canon_guess(g, sy);
                int seen = 0;
                for (int i = 0; i < n; i++) if (keys[i] == key) { seen = 1; break; }
                if (!seen) {
                    if (n >= max) return n;
                    keys[n] = key;
                    memcpy(out[n], g, L);
                    n++;
                }
            }
            int b = nb - 1;
            while (b >= 0 && ++pick[b] >= nclass) pick[b--] = 0;
            if (b < 0) break;
        }
    }
    return n;
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

typedef struct { uint64_t h0, h1x; long long val; int32_t d, bestg; uint32_t work, pad; } Entry;
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

static int tt_get(uint64_t h0, uint64_t h1, int d, long long *val, int *bestg) {
    if (TT_OFF) return 0;
    Entry *bk = TT + (h0 & (TT_BUCKETS - 1)) * 2;
    for (int i = 0; i < 2; i++)
        if (bk[i].h0 == h0 && bk[i].h1x == (h1 ^ (uint64_t)bk[i].val) && bk[i].d == d) {
            *val = bk[i].val; if (bestg) *bestg = bk[i].bestg; return 1;
        }
    return 0;
}

/* Snapshot the table so a stopped run restarts warm.  At --tt-bits 26 this is
 * 5.4 GB, and rebuilding it is the bulk of a long run's cost.
 *
 * The header records everything the stored VALUES depend on: the guess set size,
 * the answer space, and the three flags that change what a value MEANS (--topk,
 * --allow-unsolved, --by-class).  A table from one configuration read by another
 * would return confidently wrong numbers rather than missing, so a mismatch is
 * refused rather than warned about. */
typedef struct {
    char    magic[8];
    int32_t bits, ng, topk, allow, byclass, pad;
    int64_t nstr;
} TTHead;

static void tt_save(const char *path, int bits) {
    if (TT_OFF) return;
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "cannot write %s\n", path); return; }
    TTHead h;
    memset(&h, 0, sizeof h);
    memcpy(h.magic, "STRTT001", 8);
    h.bits = bits; h.ng = NG; h.topk = TOPK;
    h.allow = ALLOW_UNSOLVED; h.byclass = BY_CLASS; h.nstr = NSTR;
    size_t n = (size_t)TT_BUCKETS * 2;
    if (fwrite(&h, sizeof h, 1, f) != 1 || fwrite(TT, sizeof(Entry), n, f) != n)
        fprintf(stderr, "short write saving %s\n", path);
    else
        fprintf(stderr, "table saved to %s (%.2f GB)\n",
                path, n * sizeof(Entry) / 1e9);
    fclose(f);
}

static int tt_load(const char *path, int bits) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    TTHead h;
    if (fread(&h, sizeof h, 1, f) != 1 || memcmp(h.magic, "STRTT001", 8)) {
        fprintf(stderr, "%s is not a strturns table -- ignoring\n", path);
        fclose(f); return 0;
    }
    if (h.bits != bits || h.ng != NG || h.nstr != NSTR || h.topk != TOPK ||
        h.allow != ALLOW_UNSOLVED || h.byclass != BY_CLASS) {
        fprintf(stderr, "%s was written under a different configuration "
                "(bits %d/%d, topk %d/%d, allow %d/%d, by-class %d/%d) -- REFUSING, "
                "its values would mean something else\n",
                path, h.bits, bits, h.topk, TOPK, h.allow, ALLOW_UNSOLVED,
                h.byclass, BY_CLASS);
        fclose(f); exit(1);
    }
    size_t n = (size_t)TT_BUCKETS * 2;
    size_t got = fread(TT, sizeof(Entry), n, f);
    fclose(f);
    if (got != n) { fprintf(stderr, "%s is truncated -- ignoring\n", path); return 0; }
    fprintf(stderr, "table loaded from %s (%.2f GB)\n", path, n * sizeof(Entry) / 1e9);
    return 1;
}

/* Openers already recorded in the CSV, so a restart continues rather than
 * redoing work that is already on disk. */
static int load_done(const char *path, uint8_t *done) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[512];
    int n = 0;
    while (fgets(line, sizeof line, f)) {
        uint8_t code[L];
        int i = 0;
        while (i < L && line[i] >= 'a' && line[i] <= 'z') { code[i] = (uint8_t)(line[i] - 'a'); i++; }
        if (i != L || line[L] != ',') continue;
        int g = WORDIDX[strindex(code)];
        if (g >= 0 && !done[g]) { done[g] = 1; n++; }
    }
    fclose(f);
    return n;
}

static void tt_put(uint64_t h0, uint64_t h1, int d, long long val, int bestg, uint32_t work) {
    if (TT_OFF) return;
    Entry e; e.h0 = h0; e.val = val; e.h1x = h1 ^ (uint64_t)val; e.d = d;
    e.bestg = bestg; e.work = work; e.pad = 0;
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
    /* `rem` answers cannot fit in d guesses however the tree is built, so under
     * --allow-unsolved that is a floor on the violation count -- a real bound on
     * the leading field, not just on guesses.  The unsolved ones are charged no
     * guesses, which keeps it a lower bound. */
    if (!ALLOW_UNSOLVED) return INF;
    return (long long)rem * USCALE + total;
}

/* THE ranking rule, and the only one.  Every place that orders guesses -- the
 * per-node guess loop, the d == 2 closed form, and the opener sweep -- sorts
 * these, so "what does --topk rank by" and "how are ties broken" have a single
 * answer instead of one per call site.
 *
 * The key is NOT packed alongside the guess index.  Packing is what broke this
 * before: a sum of squares reaches ~1.4e14 at the root, so it had to be shifted
 * down 12 bits to leave room for the index -- which made every guess tie at any
 * node with fewer than about 64 candidates, silently turning --topk into
 * alphabetical order exactly where most nodes are.
 *
 * TIES BREAK ON THE LOWEST GUESS INDEX, everywhere.  That is arbitrary but it is
 * ONE arbitrary rule, so two orderings of the same set never disagree. */
typedef struct { long long key; int g; } GuessKey;

static int cmp_guesskey(const void *a, const void *b) {
    const GuessKey *x = a, *y = b;
    if (x->key != y->key) return (x->key > y->key) - (x->key < y->key);
    return (x->g > y->g) - (x->g < y->g);
}

typedef struct {
    State    subs[MAXD][NPAT];
    uint64_t cn[MAXD][NPAT];
    long long lbg[MAXD][MAXG];
    GuessKey ord[MAXD][MAXG];
    State    atbuf[MAXD][NPAT];        /* --guess-space all: transient atoms */
    uint8_t  okbuf[MAXD][NPAT];
    long long nodes;
} Ctx;

/* Point a Guess at the precomputed tables for word `g`. */
static void guess_of_index(int g, Guess *q) {
    q->gc = GCODE[g];
    q->at = ATOM + (size_t)g * NPAT;
    q->ok = AOK + (size_t)g * NPAT;
}

/* Build a Guess for arbitrary letter codes, into caller-owned scratch.  243
 * atoms at ~100 ns each, so ~25 us -- affordable because only a few hundred
 * representatives are profiled per node, not 11881376 guesses. */
static void guess_of_codes(const uint8_t *gc, State *atbuf, uint8_t *okbuf, Guess *q) {
    for (int p = 0; p < NPAT; p++) okbuf[p] = build_atom(&atbuf[p], gc, p) ? 1 : 0;
    q->gc = gc; q->at = atbuf; q->ok = okbuf;
}

/* The i-th guess AT THIS NODE.  In word mode `id` indexes the 12972 list and the
 * atoms are precomputed; under --guess-space all it indexes this node's
 * representatives and the atoms are built into the caller's scratch.  Either way
 * the search sees a Guess and nothing else changes -- which is what keeps the
 * word-mode behaviour bit-identical. */
static void get_guess(int id, uint8_t (*reps)[L], State *atbuf, uint8_t *okbuf,
                      Guess *q) {
    if (ALL_GUESSES) guess_of_codes(reps[id], atbuf, okbuf, q);
    else             guess_of_index(id, q);
}

static long long solve(const State *st, uint64_t n, int d, Ctx *ctx);

/* A single opener emits NOTHING until it finishes, and at this scale that can be
 * a very long silence -- which reads as a hang rather than as work.
 *
 * The useful thing to report is not the node rate but HOW MUCH OF THE ANSWER
 * SPACE IS SETTLED.  The root partition is walked bucket by bucket and every
 * bucket's size is known up front, so completed buckets give a genuine
 * denominator: what fraction of the 11,881,376 answers have been decided, how
 * many guesses they cost, and how many of them ended up unsolved -- all running
 * totals, all exact for the part finished so far.
 *
 * (The old line reported "deepest live: d=..., n=...", which was whichever node
 * happened to trip the counter -- not the deepest, not representative, and no
 * indication of progress.)
 *
 * Races on these are benign: a duplicated or skipped line, and nothing here
 * feeds a result.  Under a multi-opener sweep the counters aggregate across the
 * openers in flight, which the line says. */
static double    G_T0, G_LAST;
static long long G_NODES;
static long long G_ANS_DONE, G_ANS_TOTAL;
static int       G_BUCKETS_DONE, G_BUCKETS_TOTAL, G_OPENERS, G_DEPTH;
static long long G_GUESSES, G_UNSOLVED;
/* The bucket currently being solved.  Without this the line sits at 0.0% for as
 * long as the FIRST bucket takes -- and the first is the all-grey one, 21**5 =
 * 4084101 answers, a third of the whole space -- which reads as a hang. */
static int       G_CUR_BUCKET;
static long long G_CUR_SIZE;

/* Answers whose fate is DECIDED, counted where it is decided rather than when a
 * whole root bucket finishes.  Root buckets are far too coarse: the first is a
 * third of the space and takes minutes, so the percentage did not move at all.
 *
 * EXACT ONLY UNDER --topk 1, which is why it is gated on it: there, exactly one
 * guess is evaluated per node, so every answer is decided in exactly one place.
 * With a wider beam several guesses are evaluated at the same node and their
 * subtrees would each count the same answers. The totals must add to NSTR, and
 * the final line SAYS whether they did -- so a miscount shows up rather than
 * quietly making a plausible bar. */
static long long G_SOLVED, G_UNRESOLVED;

static void progress(void);

static void decide(long long solved, long long unresolved) {
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_SOLVED += solved;
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_UNRESOLVED += unresolved;
    progress();
}

static void progress(void) {
    double now = now_s();
    if (now - G_LAST < 5.0) return;
    G_LAST = now;
    double el = now - G_T0;
    if (G_ANS_TOTAL > 0) {
        /* Prefer the per-answer counter where it is exact; fall back to whole
         * root buckets otherwise. */
        long long done = (TOPK == 1) ? (G_SOLVED + G_UNRESOLVED) : G_ANS_DONE;
        double pct = 100.0 * (double)done / (double)G_ANS_TOTAL;
        char eta[32];
        if (done > 0)
            snprintf(eta, sizeof eta, "%.0fs",
                     el * (G_ANS_TOTAL - done) / (double)done);
        else
            snprintf(eta, sizeof eta, "?");   /* nothing settled: say so, do not print 0 */
        fprintf(stderr, "[%7.0fs] d=%d %5.1f%%  %lld solved + %lld unsolved = %lld/%lld"
                "  bucket %d/%d (%lld answers)%s  |  %lld nodes, %.0f/s, eta %s\n",
                el, G_DEPTH, pct, G_SOLVED, G_UNRESOLVED, done, G_ANS_TOTAL,
                G_CUR_BUCKET, G_BUCKETS_TOTAL, G_CUR_SIZE,
                G_OPENERS > 1 ? ", summed over openers" : "",
                G_NODES, G_NODES / (el + 1e-9), eta);
    } else {
        fprintf(stderr, "[%7.0fs] %lld nodes, %.0f/s\n", el, G_NODES, G_NODES / (el + 1e-9));
    }
    fflush(stderr);
}

static long long eval_guess(const State *st, uint64_t n, int d, const Guess *q,
                            long long best, Ctx *ctx) {
    State *subs = ctx->subs[d];
    uint64_t *cn = ctx->cn[d];
    int np = 0;
    const State *at = q->at;
    const uint8_t *ok = q->ok;
    /* The all-green bucket is skipped below because this guess RESOLVES it, so
     * nothing recurses into it -- which means it is also the one answer no base
     * case would ever count.  Credit it here. */
    if (ok[ALL_GREEN]) {
        State win;
        if (meet(&win, st, &at[ALL_GREEN]) && count_state(&win) == 1) decide(1, 0);
    }
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
    /* Every candidate is charged this guess.  Children then add their own packed
     * (unsolved, guesses); the fields never carry, so one add does both. */
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
    /* One candidate left: naming it costs a guess, so it is only resolvable if
     * there IS one left.  Without the d >= 1 test this charged a guess the budget
     * did not have, which made --depth 1 and --depth 2 report identical results:
     * at depth 1 the root's children arrive with d == 0 and every singleton was
     * still being resolved. */
    if (n == 1) {
        if (d >= 1) { decide(1, 0); return 1; }  /* played, or the phantom naming move */
        decide(0, 1);
        return ALLOW_UNSOLVED ? USCALE : INF;   /* out of budget: it stays unsolved */
    }
    /* Out of budget with more than one candidate left.  By default that is fatal;
     * under --allow-unsolved every remaining candidate is a violation, and none
     * of them is charged a further guess because none is played. */
    if (d <= 1) {
        decide(0, (long long)n);
        return ALLOW_UNSOLVED ? (long long)n * USCALE : INF;
    }
    if (n == 2) {
        /* Either candidate playable: guess it -- 1 if right, 2 if not.  Neither
         * playable: the pair must be SPLIT and each half then costs its own
         * phantom move, so 2 + 1 + 1 = 4, and the first separating guess proves
         * it because one guess cannot resolve a candidate it cannot name. */
        uint8_t two[2][L];
        if (enum_small(st, two, 2) == 2) {
            /* Under --guess-space all every string is a legal guess, so a
             * candidate is always playable and this is simply 1 + 2. */
            if (ALL_GUESSES ||
                WORDIDX[strindex(two[0])] >= 0 || WORDIDX[strindex(two[1])] >= 0) {
                decide(2, 0); return 3;
            }
            for (int g = 0; g < NG; g++)
                if (pattern_codes(GCODE[g], two[0]) != pattern_codes(GCODE[g], two[1])) {
                    decide(2, 0); return 4;
                }
            /* No guess separates them, so neither can ever be pinned down.
             * Cannot arise for the 12972-word guess set, which provably
             * separates every pair of strings, but the code must not assume it. */
            decide(0, 2);
            return ALLOW_UNSOLVED ? 2 * USCALE : INF;
        }
    }
    /* Depth normalisation: n candidates always resolve within n guesses (any
     * splitting guess drops the largest bucket to n-1, so f(n) <= 1 + f(n-1)),
     * so beyond that the budget cannot bind and f(S,d) == f(S,n).  Collapsing
     * the key is what makes small states hit in the table. */
    if ((uint64_t)d > n) d = (int)n;

    /* --guess-space all: one representative per symmetry class of the FULL 26**5
     * space, enumerated fresh at this node and used by every guess loop below.
     * Measured at 7 classes at the root, 36 down an all-grey line and 174 once a
     * green pins a position, so the list is short however deep the search goes. */
    uint8_t reps[MAXREPS][L];
    int nreps = 0;
    if (ALL_GUESSES) {
        static __thread uint64_t rkeys[MAXREPS];
        Sym sy; build_sym(st, &sy);
        nreps = enum_reps(&sy, reps, MAXREPS, rkeys);
    }
    int nguess = ALL_GUESSES ? nreps : NG;

    long long lb0 = lbound(n, d);
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(st, d, &h0, &h1);
    long long cached;
    if (tt_get(h0, h1, d, &cached, NULL)) return cached;

    long long nodes0 = ctx->nodes++;
    long long best = INF;
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_NODES++;
    if ((G_NODES & 0x3FF) == 0) progress();

    /* d == 2 CLOSED FORM: one guess left after this one, so the only thing a
     * guess can do is FULLY DIVIDE the bucket -- every non-green part must be a
     * singleton, since a part of two or more cannot be resolved by a single
     * remaining guess.  That makes the value computable straight from the
     * partition profile, with no recursion:
     *
     *     guesses  = n + (number of singleton non-green parts)
     *     unsolved = the candidates sitting in parts of size 2 or more
     *
     * and the floor is 2n - 1: every candidate charged this guess, every one
     * charged its naming guess, less the one resolved by an all-green.  So the
     * FIRST guess that attains 2n - 1 is provably optimal and we stop looking --
     * no sort, no second partition pass, no recursion.
     * Build with -DNO_D2 to disable it and re-derive these nodes the general
     * way: that is the DIFFERENTIAL TEST for this optimisation, and it must
     * produce identical values at --topk 0.  (It does NOT match under --topk,
     * and should not: the closed form scans every guess because it is exact and
     * cheap, while the general path honours the beam.  optturns does the same.)
     */
#ifndef NO_D2
    if (d == 2) {
        /* One guess splits into at most BRANCH non-green parts, so it can resolve
         * at most BRANCH singletons plus one all-green: 238 candidates, whatever
         * n is.  Two consequences, and the first is the bigger win:
         *   - by default, where nothing may be left unsolved, n > BRANCH + 1 is
         *     INFEASIBLE outright and needs no scan at all;
         *   - the attainable floor is NOT 2n - 1 once n exceeds that, so the old
         *     floor could never be reached and the early exit never fired -- the
         *     scan ran all 12972 guesses at every d == 2 node. */
        long long smax = ((long long)n - 1 < (long long)BRANCH)
                       ? (long long)n - 1 : (long long)BRANCH;
        if (!ALLOW_UNSOLVED && (long long)n > smax + 1) {
            tt_put(h0, h1, d, INF, -1, 1);
            return INF;
        }
        long long best2 = ALLOW_UNSOLVED ? (long long)n * USCALE : INF;
        int bg2 = -1;
        long long floor2 = ((long long)n - smax - 1) * USCALE
                         + (long long)n + smax;
        /* --topk APPLIES HERE TOO.  It used to not, which meant the beam did not
         * describe the whole search and a --topk run quietly got exact answers at
         * every depth-2 node.  Ranking needs every guess profiled anyway, so the
         * floor's early exit only survives in the exact search below. */
        if (TOPK > 0) {
            GuessKey *ord2 = ctx->ord[d];
            long long *val2 = ctx->lbg[d];
            int nc2 = 0;
            if (BY_CLASS) {
                Sym sy; build_sym(st, &sy);
                for (int g = 0; g < NG; g++) {
                    ord2[nc2].key = (long long)canon_guess(GCODE[g], &sy);
                    ord2[nc2].g = g; nc2++;
                }
                qsort(ord2, nc2, sizeof(GuessKey), cmp_guesskey);
                int nr = 0;
                for (int i = 0; i < nc2; i++)
                    if (i == 0 || ord2[i].key != ord2[i - 1].key) ord2[nr++] = ord2[i];
                nc2 = nr;
            } else {
                for (int g = 0; g < NG; g++) { ord2[nc2].key = 0; ord2[nc2].g = g; nc2++; }
            }
            int m2 = 0;
            for (int ci = 0; ci < nc2; ci++) {
                int g = ord2[ci].g;
                const State *at = ATOM + (size_t)g * NPAT;
                const uint8_t *ok = AOK + (size_t)g * NPAT;
                long long uns = 0, sing = 0, ss = 0;
                for (int p = 0; p < NPAT; p++) {
                    if (!ok[p]) continue;
                    State tmp;
                    if (!meet(&tmp, st, &at[p])) continue;
                    uint64_t c = count_state(&tmp);
                    if (!c) continue;
                    ss += (long long)c * (long long)c;
                    if (p == ALL_GREEN) continue;
                    if (c == 1) sing++; else uns += (long long)c;
                }
                if (uns && !ALLOW_UNSOLVED) continue;
                val2[g] = uns * USCALE + (long long)n + sing;
                ord2[m2].key = ss; ord2[m2].g = g; m2++;
            }
            qsort(ord2, m2, sizeof(GuessKey), cmp_guesskey);
            int lim2 = (TOPK < m2) ? TOPK : m2;
            for (int i = 0; i < lim2; i++)
                if (val2[ord2[i].g] < best2) { best2 = val2[ord2[i].g]; bg2 = ord2[i].g; }
            /* This is the branch --topk takes, and it is where the depth-2 nodes
             * actually return -- crediting only the exact branch below left the
             * counter reading 3253 decided and 0 unsolved on a depth-4 run. */
            decide((long long)n - UNS(best2), UNS(best2));
            tt_put(h0, h1, d, best2, bg2, 1);
            return best2;
        }
        for (int g = 0; g < nguess; g++) {
            Guess q; get_guess(g, reps, ctx->atbuf[d], ctx->okbuf[d], &q);
            const State *at = q.at;
            const uint8_t *ok = q.ok;
            long long uns = 0, sing = 0;
            for (int p = 0; p < NPAT; p++) {
                if (!ok[p] || p == ALL_GREEN) continue;
                State tmp;
                if (!meet(&tmp, st, &at[p])) continue;
                uint64_t c = count_state(&tmp);
                if (!c) continue;
                if (c == 1) sing++;
                else {
                    uns += (long long)c;
                    if (!ALLOW_UNSOLVED) break;   /* cannot finish: abandon it */
                }
            }
            if (uns && !ALLOW_UNSOLVED) continue;
            long long v = uns * USCALE + (long long)n + sing;
            if (v < best2) { best2 = v; bg2 = g; }
            if (best2 <= floor2) break;           /* provably optimal */
        }
        decide((long long)n - UNS(best2), UNS(best2));
        tt_put(h0, h1, d, best2, bg2, 1);
        return best2;
    }
#endif

    /* Pass 1: each guess's partition profile gives its lower bound, and (under
     * --topk) its sum of squared bin sizes -- the split-quality score the K
     * survivors are chosen by, computed from the same counts. */
    long long *lbg = ctx->lbg[d];
    GuessKey *ord = ctx->ord[d];

    /* The guesses worth PROFILING.  Normally all of them; under --by-class one
     * per symmetry class, taking the lowest index in each so the choice matches
     * what the tie-break would have made anyway. */
    int ncand = 0;
    if (ALL_GUESSES) {
        for (int i = 0; i < nreps; i++) { ord[ncand].key = 0; ord[ncand].g = i; ncand++; }
    } else if (BY_CLASS) {
        Sym sy; build_sym(st, &sy);
        for (int g = 0; g < NG; g++) {
            ord[ncand].key = (long long)canon_guess(GCODE[g], &sy);
            ord[ncand].g = g;
            ncand++;
        }
        qsort(ord, ncand, sizeof(GuessKey), cmp_guesskey);
        int nr = 0;
        for (int i = 0; i < ncand; i++)
            if (i == 0 || ord[i].key != ord[i - 1].key) ord[nr++] = ord[i];
        ncand = nr;
    } else {
        for (int g = 0; g < NG; g++) { ord[ncand].key = 0; ord[ncand].g = g; ncand++; }
    }

    /* Small states profile by direct pattern computation; see SMALL_N. */
    uint8_t cand[SMALL_MAX][L];
    int use_small = (SMALL_N > 0 && n <= (uint64_t)SMALL_N && n <= SMALL_MAX);
    if (use_small && enum_small(st, cand, SMALL_MAX) != (int)n) use_small = 0;
    int scnt[NPAT], stouch[NPAT];
    if (use_small) memset(scnt, 0, sizeof scnt);

    int m = 0;
    for (int ci = 0; ci < ncand; ci++) {
        int g = ord[ci].g;
        Guess q; get_guess(g, reps, ctx->atbuf[d], ctx->okbuf[d], &q);
        long long lv = (long long)n;
        int dead = 0, np = 0;
        unsigned long long ss = 0, biggest = 0;
        if (use_small) {
            /* Same buckets as the atom path: a candidate scoring pattern p is
             * exactly a non-empty meet with atom p, so the counts are identical. */
            int nt = 0;
            for (uint64_t i = 0; i < n; i++) {
                int p = pattern_codes(q.gc, cand[i]);
                if (scnt[p]++ == 0) stouch[nt++] = p;
            }
            for (int k = 0; k < nt; k++) {
                int p = stouch[k];
                unsigned long long c = (unsigned long long)scnt[p];
                if (p != ALL_GREEN && !dead) {
                    np++;
                    if (c > biggest) biggest = c;
                    ss += c * c;
                    long long v = lbound((uint64_t)c, d - 1);
                    if (v >= INF) dead = 1; else lv += v;
                }
                scnt[p] = 0;
            }
        } else {
        const State *at = q.at;
        const uint8_t *ok = q.ok;
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
        }
        if (dead || (np == 1 && biggest == n)) { lbg[g] = INF; continue; }
        lbg[g] = lv;
        /* --topk ranks by sum of squared bin sizes (evenest split first), exact
         * -- see GuessKey.  Exact search ranks by the lower bound instead, which
         * is the better order to PROVE in. */
        /* Safe to overwrite in place: m <= ci always, since a profiled guess
         * either lands at or behind the slot it was read from. */
        ord[m].key = (TOPK > 0) ? (long long)ss : lv;
        ord[m].g = g;
        m++;
    }
    if (!m) {
        /* Not one legal guess splits this set.  Same reasoning as the n == 2
         * case: unreachable with the word list, but not assumed. */
        long long v = ALLOW_UNSOLVED ? (long long)n * USCALE : INF;
        decide(0, (long long)n);
        tt_put(h0, h1, d, v, -1, 1);
        return v;
    }

    qsort(ord, m, sizeof(GuessKey), cmp_guesskey);
    int lim = (TOPK > 0 && TOPK < m) ? TOPK : m;
    int bestg = -1;
    for (int i = 0; i < lim; i++) {
        int g = ord[i].g;
        if (TOPK == 0 && lbg[g] >= best) break;  /* sorted by lb: none left can win */
        Guess q; get_guess(g, reps, ctx->atbuf[d], ctx->okbuf[d], &q);
        long long v = eval_guess(st, n, d, &q, best, ctx);
        if (v < best) { best = v; bestg = g; }
        if (best <= lb0) break;                  /* provably optimal */
    }
    /* Under --allow-unsolved nothing is ever unreachable, so a state with no
     * improving guess still has a value: give up here and count the lot. */
    if (best >= INF && ALLOW_UNSOLVED) { best = (long long)n * USCALE; bestg = -1; }
    long long work = ctx->nodes - nodes0;
    tt_put(h0, h1, d, best, bestg, work > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)work);
    return best;
}

/* Gather the answers the chosen strategy leaves unresolved, by walking the line
 * solve() actually picked (the guess is stored in its table entry).  The COUNT
 * never needs this -- it rides in the packed return value and is free -- so this
 * runs only when the count is small enough to be worth listing.
 *
 * `*nout` is capped at `cap`, but `*total` keeps counting, so the caller can say
 * "and N more" honestly rather than silently truncating. */
static void collect_unsolved(const State *st, uint64_t n, int d, Ctx *ctx,
                             uint8_t (*out)[L], int *nout, int cap) {
    if (*nout >= cap) return;                   /* have enough examples: stop */
    if (n == 1) return;
    if ((uint64_t)d > n) d = (int)n;            /* same normalisation solve() uses */

    if (d <= 1) {                               /* out of budget: all of them */
        if (*nout < cap) {
            int got = enum_small(st, out + *nout, cap - *nout);
            if (got > cap - *nout) got = cap - *nout;   /* it may report one past */
            *nout += got;
        }
        return;
    }
    long long val; int bestg = -1;
    uint64_t h0, h1;
    hash_state(st, d, &h0, &h1);
    if (!tt_get(h0, h1, d, &val, &bestg)) {
        val = solve(st, n, d, ctx);
        if (!tt_get(h0, h1, d, &val, &bestg)) bestg = -1;
    }
    if (UNS(val) == 0) return;                  /* nothing unresolved below here */
    if (bestg < 0) {                            /* gave up here, or an n == 2 leaf */
        if (*nout < cap) {
            int got = enum_small(st, out + *nout, cap - *nout);
            if (got > cap - *nout) got = cap - *nout;
            *nout += got;
        }
        return;
    }
    const State *at = ATOM + (size_t)bestg * NPAT;
    const uint8_t *ok = AOK + (size_t)bestg * NPAT;
    for (int pp = 0; pp < NPAT; pp++) {
        if (!ok[pp] || pp == ALL_GREEN) continue;
        State sub;
        if (!meet(&sub, st, &at[pp])) continue;
        uint64_t c = count_state(&sub);
        if (!c) continue;
        collect_unsolved(&sub, c, d - 1, ctx, out, nout, cap);
        if (*nout >= cap) return;
    }
}

static void report_unsolved(const State *root, int g, int depth, long long val, Ctx *ctx) {
    long long un = UNS(val);
    if (un <= 0 || LIST_UNSOLVED <= 0) return;
    /* The COUNT is free -- it rides in the packed value -- so the walk only has
     * to surface EXAMPLES, and can stop the moment it has enough.  That is what
     * makes listing affordable even when millions are unsolved. */
    int cap = LIST_UNSOLVED;
    uint8_t (*out)[L] = malloc((size_t)cap * L);
    int nout = 0;
    const State *at = ATOM + (size_t)g * NPAT;
    const uint8_t *ok = AOK + (size_t)g * NPAT;
    for (int pp = 0; pp < NPAT; pp++) {
        if (!ok[pp] || pp == ALL_GREEN) continue;
        State sub;
        if (!meet(&sub, root, &at[pp])) continue;
        uint64_t c = count_state(&sub);
        if (c) collect_unsolved(&sub, c, depth - 1, ctx, out, &nout, cap);
        if (nout >= cap) break;
    }
    printf("  %lld unsolved", un);
    if (nout) {
        printf(":");
        for (int i = 0; i < nout; i++) {
            printf(" %c%c%c%c%c", 'a' + out[i][0], 'a' + out[i][1], 'a' + out[i][2],
                   'a' + out[i][3], 'a' + out[i][4]);
        }
        if (un > nout) printf(" ... and %lld more", un - nout);
    }
    printf("\n");
    free(out);
}

/* ------------------------------------------------------------ root driver */

static void root_state(State *s) {
    uint32_t full = (1u << ALPHA) - 1;
    for (int i = 0; i < L; i++) s->allow[i] = full;
    for (int c = 0; c < ALPHA; c++) { s->lo[c] = 0; s->hi[c] = L; }
}

static long long solve_opener(const Guess *q, int depth, Ctx *ctx) {
    State root; root_state(&root);
    const State *at = q->at;
    const uint8_t *ok = q->ok;
    /* Count the buckets first so the progress line has a denominator from the
     * outset rather than growing one as it goes. */
    int nb = 0;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p] || p == ALL_GREEN) continue;
        State sub;
        if (meet(&sub, &root, &at[p]) && count_state(&sub)) nb++;
    }
    /* Escalation calls this once per cap, so without a reset the totals would
     * accumulate across passes and pass 2 would open at ~50% settled. */
    if (G_OPENERS == 1) {
        G_ANS_DONE = 0; G_BUCKETS_DONE = 0; G_BUCKETS_TOTAL = 0; G_ANS_TOTAL = 0;
        G_GUESSES = 0; G_UNSOLVED = 0; G_CUR_BUCKET = 0; G_CUR_SIZE = 0;
        G_SOLVED = 0; G_UNRESOLVED = 0;
    }
    G_DEPTH = depth;
    /* The opener is itself an answer -- every word is, in this answer set -- and
     * the root skips its all-green bucket because the opener resolves it.  So it
     * is the one answer no node below ever accounts for.  (The balance check
     * caught this: 11881375 decided against 11881376 expected.) */
    if (ok[ALL_GREEN]) decide(1, 0);
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_BUCKETS_TOTAL += nb;
#ifdef _OPENMP
#pragma omp atomic
#endif
    G_ANS_TOTAL += NSTR;

    long long total = NSTR;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p] || p == ALL_GREEN) continue;
        State sub;
        if (!meet(&sub, &root, &at[p])) continue;
        uint64_t c = count_state(&sub);
        if (!c) continue;
        G_CUR_BUCKET = G_BUCKETS_DONE + 1;
        G_CUR_SIZE = (long long)c;
        progress();
        long long v = solve(&sub, c, depth - 1, ctx);
        if (v >= INF) return INF;
        total += v;
        /* This bucket is decided: fold it into the running totals. */
#ifdef _OPENMP
#pragma omp atomic
#endif
        G_ANS_DONE += (long long)c;
#ifdef _OPENMP
#pragma omp atomic
#endif
        G_BUCKETS_DONE++;
#ifdef _OPENMP
#pragma omp atomic
#endif
        G_GUESSES += GUESSES(v) + (long long)c;
#ifdef _OPENMP
#pragma omp atomic
#endif
        G_UNSOLVED += UNS(v);
        progress();
    }
    return total;
}

/* An opener's root lower bound: NSTR plus the bound on every surviving part, with
 * no search at all.  This is what ORDERS the sweep.  File order -- which is
 * alphabetical -- would let spelling decide what gets examined first, and since
 * the early alphabet is thick with repeated-letter words (aahed, aalii, aargh),
 * a stopped run would report on the structurally worst openers available: a
 * 4-distinct-letter opener leaves an all-grey bucket of 22**5 = 5153632 against
 * 21**5 = 4084101 for a 5-distinct one, and coverage is the binding constraint. */
static long long root_lb(const Guess *q, int depth) {
    State root; root_state(&root);
    const State *at = q->at;
    const uint8_t *ok = q->ok;
    long long lb = NSTR;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p] || p == ALL_GREEN) continue;
        State sub;
        if (!meet(&sub, &root, &at[p])) continue;
        uint64_t c = count_state(&sub);
        if (!c) continue;
        long long v = lbound(c, depth - 1);
        if (v >= INF) return INF;
        lb += v;
    }
    return lb;
}

/* The opener's root sum of squared bin sizes -- the same split-quality score the
 * per-node loop ranks by under --topk, so the sweep and the search agree about
 * what "most promising" means instead of using two different rules. */
static long long root_ssq(const Guess *q) {
    State root; root_state(&root);
    const State *at = q->at;
    const uint8_t *ok = q->ok;
    long long ss = 0;
    for (int p = 0; p < NPAT; p++) {
        if (!ok[p]) continue;
        State sub;
        if (!meet(&sub, &root, &at[p])) continue;
        uint64_t c = count_state(&sub);
        ss += (long long)c * (long long)c;
    }
    return ss;
}

/* Solve `g` at the SMALLEST cap that works, raising it one guess at a time from
 * `dmin` to `dmax`.  ONE function, used by the single-opener path AND the sweep:
 * --depth-max used to be wired into the first only, so it was silently ignored
 * in the very mode a bare run lands in.
 *
 * "Works" means feasible by default, and NOTHING LEFT UNSOLVED under
 * --allow-unsolved -- where nothing is ever INF, so unsolved == 0 is the only
 * sensible stopping test.
 *
 * NOTE WHAT THIS IS NOT.  It returns the best total at the FIRST cap that works.
 * f(S,d) is non-increasing in d, so a deeper cap may admit a LOWER total by
 * letting one answer run long to save guesses elsewhere.  So *used is the
 * minimum working DEPTH and the total is optimal SUBJECT TO it -- not an
 * unconstrained minimum. */
/* Opener `id` as a Guess plus a printable name: a word ordinal normally, an
 * index into the root's guess classes under --guess-space all. */
static void opener_guess(int id, State *atb, uint8_t *okb, Guess *q, char *name) {
    if (ALL_GUESSES) {
        guess_of_codes(ROOTREPS[id], atb, okb, q);
        for (int i = 0; i < L; i++) name[i] = (char)('a' + ROOTREPS[id][i]);
        name[L] = 0;
    } else {
        guess_of_index(id, q);
        memcpy(name, GWORD[id], L + 1);
    }
}

/* Printable name for opener `id`, valid in either guess space. */
static const char *opener_name(int id) {
    static __thread char buf[L + 1];
    if (!ALL_GUESSES) return GWORD[id];
    for (int i = 0; i < L; i++) buf[i] = (char)('a' + ROOTREPS[id][i]);
    buf[L] = 0;
    return buf;
}

static long long solve_escalating(int g, int dmin, int dmax, Ctx *ctx,
                                  int *used, int chatty) {
    long long total = INF;
    State atb[NPAT]; uint8_t okb[NPAT]; Guess q; char nm[L + 1];
    opener_guess(g, atb, okb, &q, nm);
    for (int d = dmin; d <= dmax; d++) {
        double t0 = now_s();
        long long nodes0 = ctx->nodes;
        total = solve_opener(&q, d, ctx);
        if (total < INF && UNS(total) == 0) { *used = d; return total; }
        if (chatty) {
            if (total < INF)
                printf("%s  depth %d: %lld unsolved, %lld guesses  (%.1fs, %lld nodes)%s\n",
                       nm, d, UNS(total), GUESSES(total), now_s() - t0,
                       ctx->nodes - nodes0,
                       d < dmax ? " -- escalating" : " -- that was --depth-max");
            else
                printf("%s  INFEASIBLE at depth %d  (%.1fs, %lld nodes)%s\n",
                       nm, d, now_s() - t0, ctx->nodes - nodes0,
                       d < dmax ? " -- escalating" : " -- that was --depth-max");
            fflush(stdout);
        }
    }
    *used = dmax;                               /* best effort at the ceiling */
    return total;
}

static int measure_branching(void) {
    State root; root_state(&root);
    int best = 1;
    /* Under --guess-space all the guess set is 26**5, but at the ROOT it collapses
     * to a handful of classes and orbit-mates have isomorphic partitions -- so the
     * maximum bin count over the classes IS the maximum over all guesses. */
    static uint8_t rreps[MAXREPS][L];
    static uint64_t rkeys[MAXREPS];
    int nall = NG;
    if (ALL_GUESSES) {
        Sym sy; build_sym(&root, &sy);
        nall = enum_reps(&sy, rreps, MAXREPS, rkeys);
    }
    State atb[NPAT]; uint8_t okb[NPAT];
    for (int g = 0; g < nall; g++) {
        Guess qq; get_guess(g, rreps, atb, okb, &qq);
        const State *at = qq.at;
        const uint8_t *ok = qq.ok;
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
/* Print the guess classes of the FULL 26**5 space at the root and down one
 * all-grey line, so the enumeration can be checked against what is already known:
 * the root must give exactly the 7 integer partitions of 5. */
static void dump_reps(void) {
    static uint8_t reps[200000][L];
    static uint64_t keys[200000];
    /* Two lines, because they cost very differently.  All-grey keeps every
     * position mask identical, so the full position symmetry survives and the
     * class count stays tiny.  Greens PIN positions and break that symmetry,
     * which is the case that decides whether an S -> S run is affordable. */
    struct { const char *name; uint8_t g[L]; int pat[4]; } line[2] = {
        { "all grey",     {18,0,11,4,19}, {0, 0, 0, 0} },
        /* salet scoring: green at 0; then green at 0 + yellow at 1; etc.
         * codes are base 3 with position 0 most significant. */
        { "with greens",  {18,0,11,4,19}, {162, 189, 168, 162} },
    };
    uint8_t probe[4][L] = {{18,0,11,4,19},{17,14,20,13,3},{2,7,8,15,25},{5,6,10,12,21}};
    for (int ln = 0; ln < 2; ln++) {
        printf("=== %s line\n", line[ln].name);
        State st; root_state(&st);
        for (int step = 0; step <= 4; step++) {
            Sym sy; build_sym(&st, &sy);
            int nc = 0;
            for (int c = 0; c < ALPHA; c++) if (sy.lclass[c] + 1 > nc) nc = sy.lclass[c] + 1;
            double t0 = now_s();
            int n = enum_reps(&sy, reps, 200000, keys);
            double te = now_s() - t0;
            printf("  step %d: %12llu candidates, %d letter classes, %3d pos perms"
                   " -> %6d guess classes (%.3fs enum)\n",
                   step, (unsigned long long)count_state(&st), nc, sy.nperm, n, te);
            if (ln == 0 && step == 0) {
                printf("     root reps:");
                for (int i = 0; i < n; i++)
                    printf(" %c%c%c%c%c", 'a'+reps[i][0], 'a'+reps[i][1], 'a'+reps[i][2],
                           'a'+reps[i][3], 'a'+reps[i][4]);
                printf("\n");
            }
            if (step == 4) break;
            State at, nx;
            const uint8_t *g = (step == 0) ? line[ln].g : probe[step];
            int pc = (ln == 0) ? 0 : (step == 0 ? line[ln].pat[0] : 0);
            if (!build_atom(&at, g, pc) || !meet(&nx, &st, &at)) {
                printf("     (line ends: infeasible refinement)\n"); break;
            }
            st = nx;
        }
    }
}

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
    const char *ttload = NULL, *ttsave = NULL;
    int no_out = 0;
    const char *openers[64]; int nopen = 0;
    int depth = 6, depthmax = -1, ttbits = 26, threads = 0, sweep = 0, selftest_n = 0;
    int dump_reps_n = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--allow-unsolved")) ALLOW_UNSOLVED = 1;
        else if (!strcmp(argv[i], "--by-class")) BY_CLASS = 1;
        else if (!strcmp(argv[i], "--guess-space") && i + 1 < argc) {
            const char *v = argv[++i];
            if (!strcmp(v, "all")) ALL_GUESSES = 1;
            else if (strcmp(v, "words")) {
                fprintf(stderr, "--guess-space must be words or all\n");
                return 1;
            }
        }
        else if (!strcmp(argv[i], "--dump-reps")) dump_reps_n = 1;
        else if (!strcmp(argv[i], "--small-n") && i + 1 < argc) SMALL_N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--list-unsolved") && i + 1 < argc)
            LIST_UNSOLVED = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--selftest") && i + 1 < argc) selftest_n = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--depth-max") && i + 1 < argc) depthmax = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if ((!strcmp(argv[i], "--topk") || !strcmp(argv[i], "-k")) && i + 1 < argc)
            TOPK = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--no-out")) no_out = 1;
        else if (!strcmp(argv[i], "--tt-save") && i + 1 < argc) ttsave = argv[++i];
        else if (!strcmp(argv[i], "--tt-load") && i + 1 < argc) ttload = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    /* --by-class needs a BEAM.  The exact solver (--topk 0) must evaluate every
     * guess, and a class representative's VALUE does not transfer to its class --
     * the word list is not symmetric under letter permutation -- so collapsing
     * there would silently break exactness rather than approximate it.
     *
     * With a beam it is fine, and at K = 1 it is not even an approximation: the
     * ranking ties across a class and breaks on the lowest index, so the
     * representative IS the word plain --topk 1 would pick.  At K > 1 it differs
     * deliberately -- plain --topk K takes the K best WORDS, which when a class
     * of thousands ties means K arbitrary members of ONE class, while this takes
     * K distinct CLASSES.  Neither dominates; both are heuristics. */
    /* A run can take hours; without --out its answer reaches stdout and nowhere
     * else.  That happened -- a whole day of runs left no file behind -- so the
     * choice is now explicit rather than defaulted.  --no-out says "throw it
     * away" out loud; solver/run-strturns-sweep.sh sets --out for you. */
    if (!outpath && !no_out && !selftest_n && !dump_reps_n) {
        fprintf(stderr, "no --out: this run would print its answer and save NOTHING.\n"
                        "  use  bash solver/run-strturns-sweep.sh ...   (sets --out and "
                        "tees a log)\n"
                        "  or   --out FILE                              to choose a path\n"
                        "  or   --no-out                                to discard it "
                        "deliberately\n");
        return 1;
    }
    if (BY_CLASS && TOPK <= 0) {
        fprintf(stderr, "--by-class needs --topk K (K >= 1): it collapses guesses the "
                        "state cannot distinguish, which is exact for the beam's "
                        "ranking but NOT for their values, so the exact solver "
                        "cannot use it\n");
        return 1;
    }
    if (depth < 1 || depth >= MAXD) {
        fprintf(stderr, "--depth %d out of range (1..%d; raise MAXD and rebuild)\n",
                depth, MAXD - 1);
        return 1;
    }
    /* --depth-max indexes the SAME per-depth arena, so it needs the SAME bound.
     * Without this an out-of-range --depth-max wrote past lbg/ord and corrupted
     * memory silently, while an out-of-range --depth refused cleanly. */
    if (depthmax >= MAXD) {
        fprintf(stderr, "--depth-max %d out of range (1..%d; raise MAXD and rebuild)\n",
                depthmax, MAXD - 1);
        return 1;
    }
    if (depthmax < depth) depthmax = depth;

    build_perms();

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

    build_rgs();
    if (dump_reps_n) { dump_reps(); return 0; }
    if (selftest_n) { selftest(selftest_n); return 0; }

    if (ALL_GUESSES) {
        static uint64_t rk[MAXREPS];
        State rt; root_state(&rt);
        Sym sy; build_sym(&rt, &sy);
        NROOTREPS = enum_reps(&sy, ROOTREPS, MAXREPS, rk);
        fprintf(stderr, "guess space: ALL %ld strings, %d classes at the root\n",
                NSTR, NROOTREPS);
    }

    BRANCH = measure_branching();
    fprintf(stderr, "branching: %d non-winning bins (max over %d guesses)\n", BRANCH, NG);
    {   /* lbound returns a PACKED (unsolved, guesses) under --allow-unsolved, so
         * it has to be decoded before it is shown -- printing it raw reported a
         * bound of 11881375000000001 with an "average" of 999999915. */
        long long rlb = lbound(NSTR, depth);
        if (rlb >= INF)
            fprintf(stderr, "root LB(d=%d, n=%ld) = INFEASIBLE\n", depth, NSTR);
        else
            fprintf(stderr, "root LB(d=%d, n=%ld): >= %lld guesses (%.5f avg)"
                    ", >= %lld unsolved\n",
                    depth, NSTR, GUESSES(rlb), (double)GUESSES(rlb) / NSTR, UNS(rlb));
    }

    if (ttbits <= 0) { TT_OFF = 1; fprintf(stderr, "TT: disabled\n"); }
    else {
        TT_BUCKETS = 1ULL << ttbits;
        TT = calloc(TT_BUCKETS * 2, sizeof(Entry));
        if (!TT) { fprintf(stderr, "cannot allocate TT\n"); return 1; }
        fprintf(stderr, "TT: 2^%d entries, %.2f GB\n", ttbits,
                TT_BUCKETS * 2.0 * sizeof(Entry) / 1e9);
        if (ttload) tt_load(ttload, ttbits);
    }
#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#else
    (void)threads; fprintf(stderr, "threads: 1 (no OpenMP)\n");
#endif
    fprintf(stderr, "phantom-final: %ld of %ld answers are not legal guesses\n",
            NSTR - NG, NSTR);
    if (ALLOW_UNSOLVED)
        fprintf(stderr, "objective: fewest UNSOLVED answers first, then fewest guesses "
                "-- NOT comparable with a default run\n");
    if (BY_CLASS)
        fprintf(stderr, "by-class: beam picks %d symmetry CLASS%s, lowest-index member "
                "of each%s\n", TOPK, TOPK == 1 ? "" : "ES",
                TOPK == 1 ? " (identical to plain --topk 1)" : "");

    G_T0 = G_LAST = now_s();

    /* Resume: anything already in the CSV is skipped, and the header is only
     * written when the file is new -- so a restart appends rather than
     * duplicating or re-solving. */
    uint8_t *done = calloc(NG, 1);
    int ndone = 0;
    if (outpath) ndone = load_done(outpath, done);
    if (ndone) fprintf(stderr, "resume: %d opener%s already in %s\n",
                       ndone, ndone == 1 ? "" : "s", outpath);

    FILE *out = outpath ? fopen(outpath, "a") : NULL;
    if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
    if (out && !ndone) {
        fprintf(out, "word,total,expected,depth,seconds%s\n",
                ALLOW_UNSOLVED ? ",unsolved" : "");
        fflush(out);
    }

    /* NO DEFAULT OPENER, DELIBERATELY -- but no refusal either.  This program
     * exists to find good openers, so an opener literal here would be an answer
     * asserted rather than derived (what used to sit here was SALET, imported
     * from the 2315-answer problem, carrying a relevance it does not have).
     *
     * Sweeping instead picks no favourite at all: it examines EVERY opener, in
     * an order the program derives, and reports each one's unsolved count as it
     * lands.  So "whatever the starter actually is" is answered by the run, and
     * nothing is biased by the default. */
    if (!sweep && nopen == 0) {
        sweep = 1;
        fprintf(stderr, "no --opener given: ranking openers by the same rule every "
                        "other level uses (there is no default starter)\n");
    }

    if (!sweep) {
        G_OPENERS = nopen;
        Ctx *ctx = calloc(1, sizeof(Ctx));
        for (int i = 0; i < nopen; i++) {
            int g = -1;
            if (ALL_GUESSES) {
                /* Any string is legal here, and it need not be one of the root's
                 * canonical representatives -- so append it and use that slot. */
                if (strlen(openers[i]) == L && NROOTREPS < MAXREPS) {
                    for (int j = 0; j < L; j++)
                        ROOTREPS[NROOTREPS][j] = (uint8_t)(openers[i][j] - 'a');
                    g = NROOTREPS++;
                }
            } else
            for (int k = 0; k < NG; k++) if (!strcmp(GWORD[k], openers[i])) { g = k; break; }
            if (g < 0) { fprintf(stderr, "%s is not a legal guess\n", openers[i]); continue; }
            if (done[g]) {
                fprintf(stderr, "%s already in %s -- skipping\n", opener_name(g), outpath);
                continue;
            }
            /* Escalate the cap one guess at a time up to --depth-max, so the
             * run reports the MINIMUM FEASIBLE depth as well as the total.
             * NOTE what that is and is not: f(S,d) is non-increasing in d, so a
             * still-deeper cap may admit a LOWER total by letting one answer run
             * long to save guesses elsewhere.  The number is optimal SUBJECT TO
             * the depth reported, not an unconstrained minimum. */
            double s0 = now_s();
            int used = depthmax;
            long long total = solve_escalating(g, depth, depthmax, ctx, &used, 1);
            double dt = now_s() - s0;
            if (total < INF) {
                long long un = UNS(total), gs = GUESSES(total);
                /* Averaged over ALL answers, not just the solved ones: every
                 * answer was charged for each guess actually played on its path,
                 * including the ones that ran out of budget.  Dividing by the
                 * solved count would attribute their guesses to somebody else. */
                printf("%s  total=%lld  unsolved=%lld  avg-played=%.5f  d=%d"
                       "  (%.1fs, %lld nodes)\n",
                       opener_name(g), gs, un, (double)gs / NSTR,
                       used, dt, ctx->nodes);
                /* The progress counter is supposed to decide every answer
                 * exactly once and agree with the result.  Say so either way,
                 * rather than leaving a plausible-looking bar unchecked. */
                if (TOPK == 1) {
                    long long dec = G_SOLVED + G_UNRESOLVED;
                    if (dec != NSTR || G_UNRESOLVED != un)
                        printf("  WARNING: progress accounting decided %lld answers "
                               "(expected %ld) with %lld unsolved (result says %lld)\n",
                               dec, NSTR, G_UNRESOLVED, un);
                    else
                        printf("  progress accounting balances: %lld solved + %lld "
                               "unsolved = %ld\n", G_SOLVED, G_UNRESOLVED, NSTR);
                }
                if (un > 0 && !ALL_GUESSES) {
                    State rt; root_state(&rt);
                    report_unsolved(&rt, g, used, total, ctx);
                } else if (un > 0) {
                    /* The unsolved WALK still indexes atoms by a word ordinal,
                     * which a generated representative does not have.  The COUNT
                     * above is exact either way; only the examples are missing. */
                    printf("  %lld unsolved (listing not available under "
                           "--guess-space all)\n", un);
                }
            }
            fflush(stdout);
            if (out) {
                if (total >= INF) fprintf(out, "%s,,,,%.1f\n", opener_name(g), dt);
                else fprintf(out, "%s,%lld,%.5f,%d,%.1f,%lld\n",
                             opener_name(g), GUESSES(total),
                             (double)GUESSES(total) / NSTR,
                             used, dt, UNS(total));
                fflush(out);
            }
        }
        free(ctx);
    } else {
        /* Visit openers in ASCENDING root lower bound -- derived and named, so a
         * run stopped early has examined the most promising openers rather than
         * the alphabetically first ones. */
        /* Ordered by the SAME rule the per-node loop uses: sum of squares under
         * --topk, lower bound for the exact search.  Openers whose bound already
         * rules them out are dropped either way. */
        GuessKey *ord = malloc(sizeof(GuessKey) * NG);
        int nord = 0;
        /* The root is the most symmetric state there is, so --by-class collapses
         * the opener list hardest here: the 12972 words fall into the integer
         * partitions of 5 that any word realises. */
        int *cand = malloc(sizeof(int) * NG);
        int ncand = 0;
        if (ALL_GUESSES) {
            for (int i = 0; i < NROOTREPS; i++) cand[ncand++] = i;
            fprintf(stderr, "guess-space all: %d root guess classes\n", ncand);
        } else if (BY_CLASS) {
            State rt; root_state(&rt);
            Sym sy; build_sym(&rt, &sy);
            GuessKey *tmp = malloc(sizeof(GuessKey) * NG);
            for (int g = 0; g < NG; g++) {
                tmp[g].key = (long long)canon_guess(GCODE[g], &sy);
                tmp[g].g = g;
            }
            qsort(tmp, NG, sizeof(GuessKey), cmp_guesskey);
            for (int i = 0; i < NG; i++)
                if (i == 0 || tmp[i].key != tmp[i - 1].key) cand[ncand++] = tmp[i].g;
            free(tmp);
            fprintf(stderr, "by-class: %d openers collapse to %d class%s\n",
                    NG, ncand, ncand == 1 ? "" : "es");
        } else {
            for (int g = 0; g < NG; g++) cand[ncand++] = g;
        }
        {
            State atb[NPAT]; uint8_t okb[NPAT]; Guess q; char nm[L + 1];
            for (int ci = 0; ci < ncand; ci++) {
                int g = cand[ci];
                opener_guess(g, atb, okb, &q, nm);
                long long lb = root_lb(&q, depth);
                if (lb >= INF && !ALLOW_UNSOLVED) continue;
                ord[nord].key = (TOPK > 0) ? root_ssq(&q) : lb;
                ord[nord].g = g;
                nord++;
            }
        }
        free(cand);
        qsort(ord, nord, sizeof(GuessKey), cmp_guesskey);
        /* THE ROOT IS A BRANCHING POINT LIKE ANY OTHER.  --topk restricts the
         * guesses considered at EVERY branching point, and the first guess is not
         * special -- so -k 1 examines exactly ONE opener, the best by the same
         * sum-of-squares rule every other level uses, not all 12972.  Sweeping
         * the whole list under a beam would apply the beam everywhere except
         * where it is most expensive.  (solver/README.md says this for optturns;
         * it is the same rule here.)
         *
         * The consequence is a weaker claim, deliberately: the winner is the best
         * of the K openers EXAMINED, not the best of all NG -- which is exactly
         * what lets a small K finish. */
        if (TOPK > 0 && TOPK < nord) {
            fprintf(stderr, "topk %d: examining %d opener%s, not all %d "
                    "(the root is a branching point too)\n",
                    TOPK, TOPK, TOPK == 1 ? "" : "s", nord);
            nord = TOPK;
        }
        if (nord)
            /* NB the COMPLETION order will not match this: the sweep is an
             * omp for over the openers, so they finish as threads free up. */
            fprintf(stderr, "sweep: %d opener%s by ascending %s (first %s, key %lld)"
                    " -- completions arrive out of order, %d at a time\n",
                    nord, nord == 1 ? "" : "s",
                    TOPK > 0 ? "root sum of squares" : "root lower bound",
                    opener_name(ord[0].g), ord[0].key,
#ifdef _OPENMP
                    omp_get_max_threads()
#else
                    1
#endif
                    );
        else
            fprintf(stderr, "sweep order: no opener can solve within depth %d\n", depth);

        G_OPENERS = nord;

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
            for (int i = 0; i < nord; i++) {
                int g = ord[i].g;
                if (done[g]) continue;          /* already in the CSV */
                double s0 = now_s();
                int used = depthmax;
                /* Quiet here: with many openers in flight the per-cap chatter
                 * would interleave into noise.  The depth actually reached is on
                 * the result line and in the CSV instead. */
                long long total = solve_escalating(g, depth, depthmax, ctx, &used, 0);
                double dt = now_s() - s0;
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    completed++;
                    double el = now_s() - sw;
                    if (total >= INF)
                        printf("[%7.0fs] %5d/%d  %s  INFEASIBLE d>%d  %7.1fs\n",
                               el, completed, nord, opener_name(g), depthmax, dt);
                    else {
                        long long un = UNS(total), gs = GUESSES(total);
                        printf("[%7.0fs] %5d/%d  %s  total=%lld  unsolved=%lld"
                               "  avg=%.5f  d=%d  %7.1fs\n",
                               el, completed, nord, opener_name(g), gs, un,
                               (double)gs / NSTR, used, dt);
                    }
                    fflush(stdout);
                    if (out) {
                        if (total >= INF) fprintf(out, "%s,,,,%.1f\n", opener_name(g), dt);
                        else fprintf(out, "%s,%lld,%.5f,%d,%.1f,%lld\n",
                                     opener_name(g), GUESSES(total),
                                     (double)GUESSES(total) / NSTR,
                                     used, dt, UNS(total));
                        fflush(out);
                    }
                }
            }
            free(ctx);
        }
        free(ord);
    }
    if (out) fclose(out);
    free(done);
    if (ttsave) tt_save(ttsave, ttbits);
    return 0;
}
