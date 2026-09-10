/* optturns.c -- exact minimum expected turns for Wordle, per first guess,
 * with optional extraction of the full optimal decision tree.
 *
 * Objective (integer, not float): minimise TOTAL guesses summed over all 2315
 * answers.  Bertsimas & Paskov's Table 1 is exactly this integer over 2315 --
 * SALET = 7920, REAST = 7923, TRACE = CRATE = 7926, SLATE = 7928 -- so the
 * solver works in integers throughout and comparisons are exact.
 *
 *   f(S, d) = min total guesses to identify every word in S, d guesses left
 *           = min over g of  |S| + sum_{p != ALL_GREEN, S_p != 0} f(S_p, d-1)
 *
 * (every word in S pays for this guess -> |S|; the all-green bucket, nonempty
 * iff g is itself in S, needs nothing further.)
 *
 * Differences from the paper's section 2.2, all of which make this faster:
 *   - opt 3: the paper precomputes |A|*243*2315 = 6.0e9 booleans (~6 GB).  We
 *     reuse the repo's patterns.npy (12972 x 2315 uint8, 30 MB) and get the
 *     successor bucket by counting-sort on a single row.  Fits in cache.
 *   - opt 4: the paper's bound LB = (2|S|-1)/|S| is 2.000 at the root.  A guess
 *     yields <= 243 patterns, so at most 242^(k-1) words can be resolved at
 *     cost exactly k; the resulting greedy bound is 6701/2315 = 2.895 at the
 *     root.  Much tighter, prunes far harder.
 *   - the paper describes no transposition table.  Deep states recur constantly
 *     across different openers; the shared TT is what makes the full sweep over
 *     all 12972 openers affordable at all.
 *   - early exit: when best == LB(|S|,d) the state is provably done, so we stop
 *     scanning actions immediately.  Very frequent for small |S|.
 *
 * Exactness note: no beta is ever inherited from the parent.  f(S_p, d-1) must
 * be exact because it is SUMMED, not compared -- so every memoised value is a
 * true optimum and is safe to reuse anywhere.  Pruning happens only *within* a
 * state, against that state's own incumbent.
 *
 * Hot-loop notes (these dominate runtime; see git history for the slow version):
 *   - the per-guess partition NEVER memsets the 243-entry counter array.  It
 *     records which patterns it touched and clears only those, so scoring a
 *     guess costs O(n) rather than O(243 + n).  For the small deep states that
 *     make up most of the tree this was a ~50x saving on the inner loop.
 *   - TT counters are per-thread and folded into the globals once per opener.
 *     As shared globals they were a false-sharing hotspot on every probe.
 *   - the TT is 2-way set associative: slot 0 keeps whichever entry cost the
 *     most nodes to compute, slot 1 takes the most recent.  Replace-always let
 *     a 3-candidate leaf evict a 200-candidate node worth seconds of work.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <ctype.h>
#include <math.h>            /* fabs, for the kth-random cross-check */
#include <sys/stat.h>
#ifdef _OPENMP
#include <omp.h>
#endif

/* WORD LENGTH is a COMPILE-TIME constant, exactly like HARD below: build.sh
 * emits one binary per length (optturns = 5, optturns7 = 7, ...), so every array
 * bound here folds to a literal and the hot loops keep the shape they had when
 * 5 was hardcoded.  -DWORDLEN=N is the only thing that varies. */
#ifndef WORDLEN
#define WORDLEN 5
#endif
/* 3**WORDLEN, as an integer constant expression -- array sizes need one and the
 * preprocessor cannot compute a power, so it is a lookup by token paste. */
#define P3_3 27
#define P3_4 81
#define P3_5 243
#define P3_6 729
#define P3_7 2187
#define P3_8 6561
#define P3_9 19683
#define P3_10 59049
#define P3_11 177147
#define _P3CAT(a, b) a##b
#define _P3(n) _P3CAT(P3_, n)
/* The base-3 ENCODING space of the stored matrix: always 3**WORDLEN, whatever
 * feedback the binary then interprets it as.  patterns.npy holds these codes and
 * its dtype is chosen from this number, so it stays fixed under -DMASTERMIND. */
#define NPAT_FULL  _P3(WORDLEN)

/* MASTERMIND is a COMPILE-TIME constant, exactly like HARD and WORDLEN:
 * build.sh emits `mmturns` from this same file with -DMASTERMIND.  The
 * codebreaker's feedback becomes Mastermind's PEG COUNTS -- (blacks, whites),
 * i.e. how many letters are right in place and how many are right in the wrong
 * place -- instead of Wordle's per-tile colouring.
 *
 * WHY NO NEW FEEDBACK CODE.  The peg counts are a FUNCTION of the Wordle
 * pattern: blacks is the number of GREENS, and whites is the number of YELLOWS,
 * because Wordle's yellow rule hands out exactly min(guess_c, answer_c) - green_c
 * copies of each letter and that sums to the white-peg count.  So the feedback
 * is a 3**WORDLEN -> NPAT remap applied ONCE to the loaded matrix (mm_remap),
 * and every hot loop below is untouched.  tools/checkmastermind.py is the gate
 * that holds that identity to an independent from-the-strings computation.
 *
 * WHY IT IS A DIFFERENT PROBLEM, not a variant.  Peg feedback is far COARSER:
 * 20 outcomes at 5 letters against Wordle's 238.  Bins are much larger, trees
 * much deeper, the counting lower bound much weaker.  Do not compare an mmturns
 * total with an optturns one -- they are optima of different games. */
#ifdef MASTERMIND
#if defined(HARDMODE)
#error "MASTERMIND and HARDMODE are incompatible: hard mode's rule is stated in \
per-tile colours (repeat greens in place, replay yellows), which peg counts do \
not report.  Build them as separate binaries."
#endif
/* The feedback space: every (blacks, whites) with blacks + whites <= WORDLEN,
 * LESS the single impossible pair (WORDLEN-1, 1).  With WORDLEN-1 exact matches
 * the two words differ in one position only, so the guess letter x there is
 * matched against answer letter y != x; every other copy of x is already
 * consumed by an exact match, so min(guess_x, answer_x) contributes nothing
 * extra and whites is forced to 0.  That leaves (L+1)(L+2)/2 - 1 codes: 20 at
 * WORDLEN 5.  (As with 243-vs-238, some of the rest may be unreachable on a
 * given word list; they are simply array slots that never fill.) */
#define NPAT       (((WORDLEN) + 1) * ((WORDLEN) + 2) / 2 - 1)
/* mm_code() below enumerates blacks ascending, so the win (WORDLEN, 0) -- the
 * only pair with blacks == WORDLEN -- is LAST and ALL_GREEN keeps its meaning
 * as NPAT - 1.  Nothing that tests `p == ALL_GREEN` needs to change. */
#define ALL_GREEN  (NPAT - 1)
/* "b3w1" and a NUL; two digits each is room to spare at any supported length. */
#define PATSTR_BUF 8
#else
#define NPAT       NPAT_FULL
#define ALL_GREEN  (NPAT - 1)
#define PATSTR_BUF (WORDLEN + 1)
#endif

/* One pattern code AS STORED.  0..242 fits uint8 at WORDLEN 5 -- which is what
 * keeps the existing 12972x2315 patterns.npy, every Zobrist key and every tt.bin
 * bit-identical -- while 6..10 need uint16 and 11 needs uint32.
 * build_patterns.py applies the SAME rule and load_npy checks the two agree.
 * Keyed off NPAT_FULL, not NPAT: -DMASTERMIND narrows the codes the solver USES
 * but reads the very same file, so the on-disk dtype must not move under it. */
#if NPAT_FULL <= 256
typedef uint8_t pat_t;
#define PAT_NPY "u1"
#elif NPAT_FULL <= 65536
typedef uint16_t pat_t;
#define PAT_NPY "u2"
#else
typedef uint32_t pat_t;
#define PAT_NPY "u4"
#endif
/* Longest word plus its NUL. */
#define WBUF       ((WORDLEN < 7) ? 8 : 16)
/* MAXG bounds the GUESS list.  12972 at 5 letters, but hello wordl's 8-letter
 * dictionary is 29765, so build.sh passes -DMAXG sized from the actual list.
 * It costs per-thread arena (lbg + ord + leg + mark), so it is not simply set
 * to the maximum across all lengths. */
#ifndef MAXG
#define MAXG       13000
#endif
/* MAXA bounds the ANSWER set.  It is 13000, not 2315, because --answer-list can
 * make every legal guess a possible answer (the all-words sweep).  Sizing it up
 * cannot change any existing result: LBTAB is only read at n <= NA, and the
 * Zobrist keys are drawn for a < NA, so the first NA values are identical
 * whatever MAXA is.  It costs ~0.9 MB more per-thread arena (buf + tbuf), which
 * validate.sh reproducing all five totals confirms is all it costs. */
#ifndef MAXA
#define MAXA       13000
#endif
/* MAXD bounds --depth, and hard mode ESCALATES the cap per opener until the
 * opener solves (see solve_escalating), so it needs headroom well past 6.  Cost
 * is ~194 KB of per-thread arena per level: 20 levels is ~3.9 MB per thread,
 * ~78 MB across 20 threads.  Normal mode never escalates and is unaffected. */
#ifndef MAXD
#define MAXD       20
#endif
#define INF        1000000000

/* HARD is a COMPILE-TIME constant, not a runtime flag: build.sh emits two
 * binaries from this one file, `optturns` (HARD 0) and `hardturns` (HARD 1).
 * Every `if (HARD)` below folds away at -O3, so the normal-mode binary is
 * byte-for-byte the solver it always was -- no branch, no extra indirection in
 * the hot loops -- while both modes keep a single source of truth. */
#ifdef HARDMODE
#define HARD 1
#else
#define HARD 0
#endif
/* Same shape as HARD, for the same reason: a compile-time 0 in every binary but
 * `mmturns`, so the salt term below folds away and existing snapshots stay
 * valid. */
#ifdef MASTERMIND
#define MM 1
#else
#define MM 0
#endif

/* ULTRA ("ultra hard mode"): a legal guess must itself be CONSISTENT with every
 * clue so far -- i.e. it must still be a word the answer could be.  This is
 * STRICTER than hard mode, which only forces greens to be repeated in place and
 * yellow letters to reappear somewhere; ultra mode also honours greys (exact
 * counts, forbidden positions) and yellow POSITION exclusions.  build.sh emits
 * `ultraturns` from this same file with -DULTRA.
 *
 * Like hard mode the accumulated requirement is REAL EXTRA STATE, not a function
 * of the candidate set S: two lines reaching the same S can have eliminated
 * DIFFERENT guess-only words, so their legal-guess sets differ and the constraint
 * is hashed into the TT key.  See the ULTRA branch of the constraint block below
 * for the representation and why (position masks + per-letter lo/hi counts) is
 * EXACT for filtering words. */
#ifdef ULTRA
#define ULT 1
#else
#define ULT 0
#endif

/* WEIGHTED: the answers carry a WEIGHT and the objective is the weighted total
 * sum over answers of  w_a * (guesses spent on a)
 * instead of the plain count.  build.sh emits `wturns` from this file with
 * -DWEIGHTED; every `if (WGT)` and `#if WGT` folds away in the other binaries,
 * so `optturns` keeps the code it has always had.
 *
 * WHY IT EXISTS.  The adversarial search (`math/freq_search.py`) tunes a weight
 * per candidate word to maximise what a GREEDY guesser spends.  Asking what an
 * OPTIMAL guesser spends against those same weights is this objective, and it
 * is the same shape as the ordinary sweep -- minimise a total over the answers,
 * subject to resolving every answer within --depth -- so it is a mode of this
 * file rather than a solver of its own.
 *
 * IT IS STILL AN INTEGER OBJECTIVE, and that is deliberate.  The weights are
 * required to be dyadic (k / 2^m) and are scaled by their common denominator on
 * load, so every total is an exact integer and every comparison is exact -- the
 * property the whole solver rests on.  A float weight would be REFUSED, not
 * rounded: rounding would silently change the objective.
 *
 * THE ANSWER LIST MUST BE SORTED BY WEIGHT DESCENDING and the loader refuses one
 * that is not.  The lower bound (build_lvl / wlb below) assigns the shallowest
 * levels to the heaviest answers, and it gets every bucket already in that order
 * for free ONLY because the answer INDEX order is weight-descending and every
 * partition here is stable.  `tools/freqweights.py` writes both files that way.
 */
#ifdef WEIGHTED
#define WGT 1
#else
#define WGT 0
#endif

/* MM_MODE: peg feedback, as a compile-time 0/1 so a runtime refusal can name it
 * in the same expression as HARD/ULT/WGT rather than needing its own #ifdef. */
#ifdef MASTERMIND
#define MM_MODE 1
#else
#define MM_MODE 0
#endif
#if ULT && defined(HARDMODE)
#error "ULTRA and HARDMODE are incompatible: ultra mode restricts guesses to \
words consistent with EVERY clue, a strict superset of hard mode's rule.  Build \
them as separate binaries."
#endif
#if ULT && defined(MASTERMIND)
#error "ULTRA and MASTERMIND are incompatible: consistency is defined by per-tile \
colours, which peg counts do not report."
#endif

/* USE_CONS: the modes that carry an accumulated CONSTRAINT down the recursion as
 * extra TT state and restrict the legal guesses to it -- hard mode and ultra
 * mode.  Normal and Mastermind do not, so this folds to a compile-time 0 in
 * `optturns`/`mmturns` and every constraint branch below disappears at -O3,
 * leaving those binaries bit-for-bit what they were. */
#define USE_CONS (HARD || ULT)

static int      NG, NA;
/* Salts the TT key with the identity of the GUESS SET (see --guess-list).  It is
 * 0 for the full 12972-word list, which leaves every hash bit-identical to what
 * it has always been -- so an existing tt.bin stays valid.  A restricted list
 * sets it, so a snapshot taken under one guess set cannot be silently reused
 * under another: the same candidate set genuinely has a different optimum when
 * the legal guesses differ, and a shared key would return that wrong value. */
static uint64_t GSALT = 0;

/* --phantom-final: allow ANSWERS THAT ARE NOT LEGAL GUESSES.
 *
 * Every other mode requires the answer set to sit inside the guess set, so the
 * last guess of every line is the answer itself and costs 1.  When the answer
 * set is the LARGER of the two (2315 guesses against all 12972 words, say),
 * most answers can never be played.  The scoring rule for those is "narrow the
 * candidate set down to that one word, then add one" -- a PHANTOM final guess
 * standing in for the naming move the guess list cannot make.
 *
 * That is the SAME arithmetic the guessable answers already get (`n == 1`
 * returns 1 either way), so the recursion needs no new accounting: an answer
 * inside the guess set is still won by being played, an answer outside it is
 * won one guess after it becomes the only candidate.  What DOES change is a
 * handful of shortcuts that assume `ANS2G[a] >= 0`; each is guarded below.
 *
 * It is OPT-IN because the "answer %s not a legal guess" check it relaxes is
 * the guard that catches a mistyped --answer-list.  Off, every existing
 * invocation is bit-identical; on, ANS2G may hold -1. */
static int PHANTOM = 0;

/* --topk: at every branching point consider only the K guesses that split the
 * candidate set most evenly (smallest sum of squared bin sizes), instead of all
 * NG of them.  0 = unlimited = the exact solver.
 *
 * THIS MAKES THE RESULT AN UPPER BOUND, NOT AN OPTIMUM.  The search space is a
 * strict subset, so what comes back is a real, achievable strategy that may not
 * be the best one.  It is weakly monotone in K -- a larger K can only match or
 * improve the total -- and K = 0 recovers exactness.  Report these numbers as
 * "best found within top-K branching", NEVER as "the optimum".
 *
 * INFEASIBLE means something weaker here too: "not solvable within the depth cap
 * USING ONLY THESE K GUESSES PER NODE", which is not evidence about the problem.
 *
 * Candidates (the words still in S) are added when n <= TOPK, so the answer is
 * always playable in a small state and a tight K degrades the total gracefully
 * rather than manufacturing spurious infeasibility. */
static int TOPK = 0;
static pat_t   *PAT;             /* NG * NA, row-major: PAT[g*NA + a] */
static uint64_t ZOB0[MAXA], ZOB1[MAXA];
static int      ANS2G[MAXA];
static char   (*GWORD)[WBUF];
static char   (*AWORD)[WBUF];
static int      LBTAB[MAXD][MAXA + 1];

#if WGT
/* --weights: WEIGHT[a] is answer a's weight, already multiplied by WSCALE so it
 * is an exact integer.  WTOTAL is their sum, and is the denominator of every
 * reported average -- the weighted analogue of NA.
 *
 * WSALT hashes the weight VECTOR into the TT key.  A state's value here is a
 * function of its candidate SET (the set determines which weights), so the set
 * is still a sufficient key WITHIN one run -- but two runs with different
 * weights agree on every key while meaning different objectives, exactly the
 * hazard MASTERMIND's unconditional salt exists for.  So it is salted
 * unconditionally too, and a foreign tt.bin fails verification instead of
 * answering. */
static long long WEIGHT[MAXA];
static long long WTOTAL = 0;
static long long WSCALE = 1;
static uint64_t  WSALT  = 0;

/* LVL[d][r] = the search level (1-based) the counting bound assigns to the
 * r-th HEAVIEST answer of a state with d guesses left; 0 means r is past the
 * capacity of d levels, i.e. the state is infeasible at that depth.
 *
 * It is build_lb's schedule, unrolled per rank instead of summed per count:
 * level 1 holds 1 answer (the guess itself), level k holds BRANCH^(k-1).  With
 * every weight 1 it reproduces LBTAB exactly -- sum over r < n of LVL[d][r] ==
 * LBTAB[d][n] -- which is what lets uniform weights reproduce optturns and is
 * checked by tools/checkweighted.py.
 *
 * Per-RANK is what keeps the hot loop O(n): a bucket's bound can be accumulated
 * as the bucket is counted (the r-th arrival into a bucket is its r-th heaviest,
 * because the state is weight-ordered), instead of needing the finished bucket. */
static int LVL[MAXD][MAXA + 1];
#endif

/* AW(a): answer a's weight -- a compile-time 1 outside weighted mode, so every
 * cost expression below folds back to the count it has always been. */
#if WGT
#define AW(a)   WEIGHT[a]
#define AVGDEN  ((double)WTOTAL)
#else
#define AW(a)   1
#define AVGDEN  ((double)NA)
#endif

/* --------------------------------------------------------------- hard mode
 *
 * Hard mode ("any revealed hints must be used in subsequent guesses") is the
 * NYT rule: a green must be repeated in its position, and a yellow letter must
 * appear SOMEWHERE in the guess -- including, legally, the same square it was
 * yellow on.  Greys impose nothing, so an all-black pattern constrains nothing.
 *
 * The accumulated requirement is therefore just:
 *     green[i]  -- the letter that position i is pinned to, or -1
 *     minc[c]   -- how many copies of letter c the guess must contain
 * both monotone down a line of play.  Call that pair the CONSTRAINT, `Cons`.
 *
 * The constraint is REAL EXTRA STATE, not a function of the candidate set S.
 * S determines an upper bound on it -- a green at i means every word in S has
 * that letter at i -- but not the converse: the words in S can happen to share
 * a letter that was never revealed, and hard mode does not pin an unrevealed
 * letter.  Two lines reaching the same S with different revealed hints have
 * genuinely different legal-guess sets, so `Cons` is hashed into the TT key.
 *
 * The legal set L is a pure function of `Cons`, and candidates are always
 * legal (S subset of L): a word consistent with all feedback necessarily has
 * the greens in place and at least the revealed counts.  So a state can always
 * fall back on guessing one of its own candidates, which is what keeps the
 * n == 1, n == 2 and depth-normalisation shortcuts below valid in hard mode.
 *
 * L is materialised on demand by intersecting precomputed bitsets, and only on
 * a TT MISS -- a hit never needs it.  `Cons` itself is 31 bytes and travels
 * down the recursion by value, so the cheap path stays cheap.
 */

#define BSW  ((MAXG + 63) / 64)          /* bitset words spanning all guesses */

#if ULT
/* ULTRA mode's constraint is the FULL Wordle-consistency of a word: a legal
 * guess must reproduce every clue exactly.  That is captured EXACTLY by
 *     allow[i]  -- the set of letters the answer may hold at position i
 *     lo[c],hi[c] -- bounds on how many copies of c the answer holds
 * and nothing else.  Why exact: against a single clue (g, p) a word w satisfies
 * pattern(g, w) == p iff (a) w[i] == g[i] at greens and w[i] != g[i] elsewhere,
 * and (b) count_c(w) == green+yellow copies when g has a grey copy of c, else
 * count_c(w) >= that many -- because Wordle hands out yellows left-to-right by
 * count, so the yellow/grey split of a repeated letter is a pure function of the
 * answer's count.  Both parts are position masks + count bounds, and the
 * conjunction of clues is their intersection (masks AND, lo = max, hi = min).
 * NB the "repeated-letter trap" that strspace.py guards is a fact about
 * ENUMERATING reachable patterns, not about FILTERING words, and does not arise
 * here: we partition the real answers by the real pattern matrix and use the
 * constraint only to pick legal guesses. */
typedef struct {
    uint32_t allow[WORDLEN];             /* bit c set = letter c permitted at position i */
    uint8_t  lo[26];                     /* answer holds >= lo[c] copies of c */
    uint8_t  hi[26];                     /* answer holds <= hi[c] copies (WORDLEN = no cap) */
} Cons;
#define ALLOW_ALL  ((1u << 26) - 1)
#else
typedef struct {
    int8_t  green[WORDLEN];              /* pinned letter 0..25, or -1 */
    uint8_t minc[26];                    /* required occurrences of each letter */
} Cons;
#endif

static uint64_t BS_POS[WORDLEN][26][BSW];      /* guesses with letter c at position i */
static uint64_t BS_CNT[26][WORDLEN + 1][BSW];  /* guesses containing >= k copies of c */
static uint64_t BS_ALL[BSW];             /* every legal guess; NG..MAXG-1 clear */

/* "nothing known yet": no greens, no required letters.  Built at startup rather
 * than brace-initialized, because the green[] array is WORDLEN long. */
static Cons CONS_NONE;

static void cons_none_init(void) {
#if ULT
    for (int i = 0; i < WORDLEN; i++) CONS_NONE.allow[i] = ALLOW_ALL;
    for (int c = 0; c < 26; c++) { CONS_NONE.lo[c] = 0; CONS_NONE.hi[c] = WORDLEN; }
#else
    memset(&CONS_NONE, 0, sizeof CONS_NONE);
    for (int i = 0; i < WORDLEN; i++) CONS_NONE.green[i] = -1;
#endif
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

#if ULT
/* Fold the feedback (g, p) into a parent constraint (ULTRA: full consistency). */
static void cons_apply(Cons *out, const Cons *in, int g, int p) {
    int present[26] = { 0 };            /* green+yellow copies of c in THIS guess */
    int greyc[26]   = { 0 };            /* grey copies of c in THIS guess */
    *out = *in;
    /* position 0 is the MSB, so the divisor starts at 3^(WORDLEN-1) */
    for (int i = 0, div = NPAT / 3; i < WORDLEN; i++, div /= 3) {
        int t = (p / div) % 3;                        /* 0 = b, 1 = y, 2 = g */
        int c = GWORD[g][i] - 'a';
        if (t == 2) out->allow[i] = 1u << c;          /* green: answer holds c here */
        else        out->allow[i] &= ~(1u << c);      /* yellow/grey: not here */
        if (t == 0) greyc[c]++; else present[c]++;    /* grey vs green|yellow */
    }
    for (int c = 0; c < 26; c++) {
        int m = present[c];
        if (m > out->lo[c]) out->lo[c] = (uint8_t)m;              /* >= m copies */
        if (greyc[c] && m < out->hi[c]) out->hi[c] = (uint8_t)m;  /* grey caps at exactly m */
    }
}

/* Expand a constraint into the ascending list of guesses it permits (ULTRA). */
static int cons_legal(const Cons *C, uint16_t *out) {
    uint64_t m[BSW];
    memcpy(m, BS_ALL, sizeof m);
    for (int i = 0; i < WORDLEN; i++) {
        uint32_t a = C->allow[i];
        if (a == ALLOW_ALL) continue;                 /* every letter allowed here */
        uint64_t pm[BSW] = { 0 };
        for (int c = 0; c < 26; c++)
            if (a & (1u << c))
                for (int w = 0; w < BSW; w++) pm[w] |= BS_POS[i][c][w];
        for (int w = 0; w < BSW; w++) m[w] &= pm[w];
    }
    for (int c = 0; c < 26; c++) {
        int lo = C->lo[c], hi = C->hi[c];
        if (lo > 0)        for (int w = 0; w < BSW; w++) m[w] &= BS_CNT[c][lo][w];
        if (hi < WORDLEN)  for (int w = 0; w < BSW; w++) m[w] &= ~BS_CNT[c][hi + 1][w];
    }
    int n = 0;
    for (int w = 0; w < BSW; w++) {
        uint64_t x = m[w];
        while (x) {
            int b = __builtin_ctzll(x);
            x &= x - 1;
            out[n++] = (uint16_t)((w << 6) + b);
        }
    }
    return n;
}

/* Mixed into the TT key so ultra-mode entries can never be confused with
 * normal-, hard- or Mastermind-mode ones -- a distinct salt from hard mode's,
 * so a tt.bin loaded into the wrong binary fails verification and recomputes. */
static inline uint64_t cons_hash(const Cons *C) {
    uint64_t h = 0xB5297A4D2A1F3C6DULL;               /* ultra-mode salt */
    for (int i = 0; i < WORDLEN; i++)
        h = (h ^ (uint64_t)C->allow[i]) * 0x100000001B3ULL;
    for (int c = 0; c < 26; c++) {
        h = (h ^ (uint64_t)C->lo[c]) * 0x100000001B3ULL;
        h = (h ^ (uint64_t)C->hi[c]) * 0x100000001B3ULL;
    }
    return h;
}
#else
/* Fold the feedback (g, p) into a parent constraint. */
static void cons_apply(Cons *out, const Cons *in, int g, int p) {
    int req[26] = { 0 };
    *out = *in;
    /* position 0 is the MSB, so the divisor starts at 3^(WORDLEN-1) */
    for (int i = 0, div = NPAT / 3; i < WORDLEN; i++, div /= 3) {
        int t = (p / div) % 3;                        /* 0 = b, 1 = y, 2 = g */
        int c = GWORD[g][i] - 'a';
        if (t == 2) { out->green[i] = (int8_t)c; req[c]++; }
        else if (t == 1) req[c]++;
    }
    for (int c = 0; c < 26; c++)
        if (req[c] > out->minc[c]) out->minc[c] = (uint8_t)req[c];
}

/* Expand a constraint into the ascending list of guesses it permits. */
static int cons_legal(const Cons *C, uint16_t *out) {
    uint64_t m[BSW];
    memcpy(m, BS_ALL, sizeof m);
    for (int i = 0; i < 5; i++) {
        int c = C->green[i];
        if (c >= 0) for (int w = 0; w < BSW; w++) m[w] &= BS_POS[i][c][w];
    }
    for (int c = 0; c < 26; c++) {
        int k = C->minc[c];
        if (k) for (int w = 0; w < BSW; w++) m[w] &= BS_CNT[c][k][w];
    }
    int n = 0;
    for (int w = 0; w < BSW; w++) {
        uint64_t x = m[w];
        while (x) {
            int b = __builtin_ctzll(x);
            x &= x - 1;
            out[n++] = (uint16_t)((w << 6) + b);
        }
    }
    return n;
}

/* Mixed into the TT key so hard-mode entries can never be confused with
 * normal-mode ones -- including across a tt.bin snapshot loaded into the wrong
 * binary, which then simply fails verification and costs a recompute. */
static inline uint64_t cons_hash(const Cons *C) {
    uint64_t h = 0x243F6A8885A308D3ULL;               /* hard-mode salt */
    for (int i = 0; i < WORDLEN; i++)
        h = (h ^ (uint64_t)(uint8_t)(C->green[i] + 1)) * 0x100000001B3ULL;
    for (int c = 0; c < 26; c++)
        h = (h ^ (uint64_t)C->minc[c]) * 0x100000001B3ULL;
    return h;
}
#endif

/* ---------------------------------------------------------------- helpers */

static uint64_t splitmix64(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

/* ------------------------------------------------- Mastermind peg feedback */
/* Only compiled into `mmturns`.  The whole of -DMASTERMIND is these two
 * functions plus the NPAT/ALL_GREEN redefinition above: one remap of the loaded
 * matrix, and a printable name for a code. */

/* The dense code for (blacks, whites), or -1 if the pair cannot occur.
 * Blacks ascending, whites ascending within it, skipping (WORDLEN-1, 1) -- so
 * the win (WORDLEN, 0) lands last and equals NPAT - 1.  This is the ONE place
 * the ordering is defined; mm_remap and pat_str both go through it. */
#ifdef MASTERMIND
static int mm_code(int b, int w) {
    if (b < 0 || w < 0 || b + w > WORDLEN) return -1;
    if (b == WORDLEN - 1 && w == 1) return -1;
    int k = 0;
    for (int bb = 0; bb <= WORDLEN; bb++)
        for (int ww = 0; ww + bb <= WORDLEN; ww++) {
            if (bb == WORDLEN - 1 && ww == 1) continue;
            if (bb == b && ww == w) return k;
            k++;
        }
    return -1;
}

static void mm_pair(int code, int *b, int *w) {
    int k = 0;
    for (int bb = 0; bb <= WORDLEN; bb++)
        for (int ww = 0; ww + bb <= WORDLEN; ww++) {
            if (bb == WORDLEN - 1 && ww == 1) continue;
            if (k++ == code) { *b = bb; *w = ww; return; }
        }
    *b = -1; *w = -1;
}
#endif

static void pat_str(int code, char *out) {
#ifdef MASTERMIND
    int b, w;
    mm_pair(code, &b, &w);
    snprintf(out, PATSTR_BUF, "b%dw%d", b, w);
#else
    /* base-3, position 0 = MSB */
    for (int i = WORDLEN - 1; i >= 0; i--) { out[i] = "byg"[code % 3]; code /= 3; }
    out[WORDLEN] = 0;
#endif
}

#ifdef MASTERMIND
/* Rewrite the whole NG x NA matrix from base-3 Wordle codes to peg codes, ONCE,
 * before anything reads it.  blacks = trits equal to 2, whites = trits equal to
 * 1 -- see the identity argued at the -DMASTERMIND block above.
 *
 * A code the base-3 space contains but the peg space cannot (4 greens + 1
 * yellow, unreachable in Wordle too) would map to -1; it is a hard error rather
 * than a clamp, because silently folding it into a real bin would corrupt every
 * partition downstream. */
static int mm_remap(pat_t *pat, int ng, int na) {
    int map[NPAT_FULL];
    for (int p = 0; p < NPAT_FULL; p++) {
        int b = 0, w = 0, q = p;
        for (int i = 0; i < WORDLEN; i++, q /= 3) {
            int t = q % 3;
            if (t == 2) b++;
            else if (t == 1) w++;
        }
        map[p] = mm_code(b, w);
    }
    size_t n = (size_t)ng * (size_t)na;
    for (size_t i = 0; i < n; i++) {
        int c = map[pat[i]];
        if (c < 0) {
            fprintf(stderr, "mastermind: pattern code %d has no peg code\n", (int)pat[i]);
            return -1;
        }
        pat[i] = (pat_t)c;
    }
    if (map[NPAT_FULL - 1] != ALL_GREEN) {
        fprintf(stderr, "mastermind: the all-green code does not map to ALL_GREEN\n");
        return -1;
    }
    fprintf(stderr, "mastermind: peg feedback, %d outcomes (blacks, whites); "
            "win is b%dw0 = %d\n", NPAT, WORDLEN, ALL_GREEN);
    return 0;
}
#endif

/* Pattern-INDEXED scratch (NPAT ints per slot, plus one for the start[] sentinel).
 *
 * At 5 letters an int[243] on the stack is 972 B and nobody noticed.  At 11 it is
 * 692 KB, and emit_tree -- which holds three of them -- is RECURSIVE, so the
 * stack is simply not an option any more.  Allocating per call instead leaves
 * every dense `for (p = 0; p < NPAT; p++)` loop below exactly as it was, which
 * matters because that loop order is what fixes the ORDER OF LINES in an emitted
 * tree file: sparsifying it would rewrite committed 5-letter trees.  The cost is
 * one calloc against work that is O(NA) or a whole subtree, so it is noise.
 *
 * calloc zeroes, which is what the callers' opening memset did. */
static int *pat_scratch(int nslots) {
    int *p = calloc((size_t)nslots * (size_t)(NPAT + 1), sizeof(int));
    if (!p) { fprintf(stderr, "out of memory: %d-slot pattern scratch\n", nslots); exit(1); }
    return p;
}
#define PSLOT(base, i) ((base) + (size_t)(i) * (size_t)(NPAT + 1))

/* --------------------------------------------------------------- loading */

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
    /* The dtype must match pat_t exactly -- a uint16 matrix read as uint8 would
     * not fail, it would return confidently wrong patterns. */
    if (!strstr(hdr, PAT_NPY)) {
        fprintf(stderr, "pattern matrix dtype is not %s (WORDLEN %d): %s\n",
                PAT_NPY, WORDLEN, hdr);
        exit(1);
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

/* ------------------------------------------------------------ lower bound */

/* Branching factor for the counting bound, MEASURED rather than assumed.
 *
 * 3^5 = 243 is the ENCODING space; only 238 of those are attainable (four greens
 * plus a yellow cannot occur -- the fifth letter is green or grey, never yellow).
 * But what any REAL guess achieves is lower still: 149 non-winning bins against
 * the 2315 mystery answers, 211 against all 12972 words.
 *
 * Over-stating the branching UNDER-states the bound, so the old literal 242 was
 * VALID, merely slack. This is the largest value that is still sound, and it is
 * sound for every sub-state too: for S contained in A, a guess's patterns on S
 * are a subset of its patterns on A, so bins(g,S) <= bins(g,A) <= BRANCH.
 *
 * Measured, not hardcoded, because the right constant depends on the ANSWER SET
 * -- a literal would be wrong for one of the two. O(NG*NA), well under a second.
 *
 * This tightens LBTAB everywhere it is read, which matters most INSIDE solve():
 * pass 1 bounds every candidate guess with it, so a tighter table prunes guesses
 * at every node rather than only screening openers at the root. */
/* Visit order for --optimal-only's exact path.  0 = ascending root lower bound
 * (the default, and the only order under which an LB skip also proves the TAIL
 * is worse); 1 = ascending sum of squared bin sizes, the same split-quality
 * heuristic --sweep and --topk use.
 *
 * WHY OFFER THE SECOND.  The tail proof is worth having only when the bound is
 * tight enough to fire.  It is a counting bound and runs ~11-14% under the true
 * optimum, so on a wide problem almost every opener bounds below the incumbent,
 * nothing is skipped, and the ordering's only remaining job is to find a good
 * incumbent EARLY -- which is exactly what sum of squares is for.  That matters
 * most when the run will be stopped before it finishes. */
static int ORDER_SSQ = 0;

/* --order bisect: DISPATCH order only -- the list is still sorted by the split
 * score, but it is then walked ends, median, quartiles, odd eighths and so on,
 * so a STOPPED run holds a stratified sample of the whole difficulty range
 * instead of a prefix of the easy end.  That is what makes a partial sweep's
 * percentiles and histogram mean something, and it is the ONLY thing it buys.
 *
 * IT IS OPT-IN, AND MUST STAY OPT-IN.  It costs real time: cheap openers are no
 * longer front-loaded and the SECOND opener dispatched is the worst-partitioned
 * word in the list, so the incumbent that drives every lower-bound cutoff
 * arrives late.  It was written for the HARD-MODE sweep, where the partial
 * distribution is the thing being read while the run is in flight; it was then
 * hardcoded into every sweep path, which quietly made every other run slower
 * and made three separate headers describe an order the code was not using.
 * Default OFF: ascending split score, best splitters first. */
static int ORDER_BISECT = 0;

/* Was --order given at all?  Only used to decide whether to warn about a value
 * the chosen path cannot honour -- never to change what runs. */
static int order_set = 0;

/* --print-openers: print a line for EVERY opener --optimal-only examines, not
 * only the ones that improve on the incumbent.  Off by default, so the existing
 * allwords / ansall logs stay byte-identical -- and because at 12972 openers in
 * ascending-LB order the improvements ARE the interesting subset, while a small
 * --topk run wants to see all K.  The CSV has always held every solved opener;
 * this only closes the gap between the file and the terminal. */
static int PRINT_OPENERS = 0;

static int BRANCH = NPAT - 1;

static int measure_branching(void) {
    int *seen = pat_scratch(1), best = 1;
    for (int g = 0; g < NG; g++) {
        memset(seen, 0, (size_t)(NPAT + 1) * sizeof(int));
        int k = 0;
        const pat_t *row = PAT + (size_t)g * NA;
        for (int a = 0; a < NA; a++)
            if (!seen[row[a]]) { seen[row[a]] = 1; k++; }
        if (seen[ALL_GREEN]) k--;          /* the win RESOLVES, it does not branch */
        if (k > best) best = k;
    }
    free(seen);
    return best;
}

static void build_lb(void) {
    for (int d = 0; d < MAXD; d++)
        for (int n = 0; n <= NA; n++) LBTAB[d][n] = INF;
    for (int d = 0; d < MAXD; d++) {
        LBTAB[d][0] = 0;
        for (int n = 1; n <= NA; n++) {
            long long rem = n, total = 0, cap = 1;
            int ok = 0;
            for (int k = 1; k <= d; k++) {
                long long take = rem < cap ? rem : cap;
                total += take * k;
                rem -= take;
                if (rem == 0) { ok = 1; break; }
                if (cap < MAXA) cap *= BRANCH;
            }
            LBTAB[d][n] = ok ? (int)total : INF;
        }
    }
}

#if WGT
/* The counting bound as a per-RANK level schedule -- see LVL's comment above.
 * Same capacity argument as build_lb: with at most BRANCH non-winning bins per
 * guess, level 1 resolves 1 answer, level k at most BRANCH^(k-1). */
static void build_lvl(void) {
    for (int d = 0; d < MAXD; d++) {
        for (int r = 0; r <= NA; r++) LVL[d][r] = 0;
        long long cap = 1;
        int r = 0;
        for (int k = 1; k <= d && r < NA; k++) {
            for (long long t = 0; t < cap && r < NA; t++) LVL[d][r++] = k;
            if (cap < MAXA) cap *= BRANCH;
        }
    }
}

/* Weighted lower bound for a state, given its members in weight-DESCENDING
 * order (which every state here is -- see the WEIGHTED block at the top).
 *
 * SOUND: any strategy assigns each answer a depth, and the capacity argument
 * bounds how many answers can sit at each depth.  Among all capacity-feasible
 * assignments the cheapest puts the largest weights at the smallest depths --
 * a rearrangement argument -- which is exactly LVL.  So this is <= the true
 * value of the state, for every strategy, and never cuts a real optimum. */
static inline int wlb(const uint16_t *S, int n, int d) {
    if (n <= 0) return 0;
    if (d >= MAXD) d = MAXD - 1;
    if (d < 1 || LVL[d][n - 1] == 0) return INF;
    long long t = 0;
    for (int i = 0; i < n; i++) t += WEIGHT[S[i]] * LVL[d][i];
    return (int)t;
}

static inline long long wsum_of(const uint16_t *S, int n) {
    long long t = 0;
    for (int i = 0; i < n; i++) t += WEIGHT[S[i]];
    return t;
}
#endif

/* The bound for a whole state.  Outside weighted mode this is the LBTAB lookup
 * it has always been; the arguments it does not use fold away. */
#if WGT
#define STATE_LB(S, n, d)  wlb((S), (n), (d))
#define STATE_W(S, n)      wsum_of((S), (n))
#define ALL_W              WTOTAL
#else
#define STATE_LB(S, n, d)  LBTAB[(d)][(n)]
#define STATE_W(S, n)      (n)
#define ALL_W              NA
#endif

#if WGT
/* Read `--weights FILE`: one `<word> <weight>` per line, `#` comments ignored.
 *
 * WEIGHTS ARE EXACT RATIONALS, NOT FLOATS.  A weight is `A` or `A/B` with B a
 * power of two; every weight is then multiplied by the largest B seen, so the
 * whole objective is an exact integer and no comparison anywhere is a float
 * comparison.  Anything else is REFUSED rather than rounded -- rounding would
 * silently change the objective, which is the one thing this file must never
 * do quietly.
 *
 * Three properties are CHECKED, not assumed, because each one silently produces
 * a wrong answer rather than an error:
 *   - the words must match the answer list POSITION FOR POSITION (the same
 *     byte-for-byte rule --patterns and --answer-list already carry);
 *   - every weight must be strictly positive (a zero-weight answer would cost
 *     nothing yet still branch the search -- topk.py drops such words, so they
 *     must not be in the list at all);
 *   - the weights must be NON-INCREASING, which is what makes the lower bound's
 *     "shallowest levels to the heaviest answers" hold for every bucket. */
static int load_weights(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 1; }
    long long num[MAXA], den[MAXA], maxden = 1;
    char word[256];
    int n = 0;
    char line[512];
    while (fgets(line, sizeof line, f)) {
        char *s = line;
        while (*s == ' ' || *s == '\t') s++;
        if (*s == '#' || *s == '\n' || *s == '\0') continue;
        long long a = 0, b = 1;
        if (sscanf(s, "%255s %lld/%lld", word, &a, &b) < 2) {
            fprintf(stderr, "weights: cannot parse line: %s", line);
            fclose(f); return 1;
        }
        if (n >= MAXA) { fprintf(stderr, "weights: more than MAXA (%d) lines\n", MAXA); fclose(f); return 1; }
        if (b <= 0 || (b & (b - 1)) != 0) {
            fprintf(stderr, "weights: %s has denominator %lld, not a power of two -- "
                    "the solver is exact in integers and will not round it\n", word, b);
            fclose(f); return 1;
        }
        if (a <= 0) {
            fprintf(stderr, "weights: %s has weight %lld/%lld; every weight must be > 0 "
                    "(drop zero-weight words from the answer list instead)\n", word, a, b);
            fclose(f); return 1;
        }
        if ((int)strlen(word) != WORDLEN || strcmp(word, AWORD[n]) != 0) {
            fprintf(stderr, "weights: line %d is %s but answer %d is %s -- the weights "
                    "file must match the answer list position for position\n",
                    n + 1, word, n, AWORD[n]);
            fclose(f); return 1;
        }
        num[n] = a; den[n] = b;
        if (b > maxden) maxden = b;
        n++;
    }
    fclose(f);
    if (n != NA) {
        fprintf(stderr, "weights: %d lines but %d answers\n", n, NA);
        return 1;
    }
    WSCALE = maxden;
    WTOTAL = 0;
    for (int a = 0; a < NA; a++) {
        WEIGHT[a] = num[a] * (WSCALE / den[a]);
        WTOTAL += WEIGHT[a];
        if (a > 0 && WEIGHT[a] > WEIGHT[a - 1]) {
            fprintf(stderr, "weights: %s (%lld) is heavier than %s (%lld) before it -- "
                    "the answer list must be sorted by weight DESCENDING, or the lower "
                    "bound is wrong.  tools/freqweights.py writes it that way.\n",
                    AWORD[a], WEIGHT[a], AWORD[a - 1], WEIGHT[a - 1]);
            return 1;
        }
    }
    /* Every total the solver forms is at most WTOTAL * MAXD, and INF is the
     * sentinel for "no solution", so the two must not meet.  Refuse rather than
     * silently wrap -- a wrapped total would look like a very good opener. */
    if (WTOTAL > (long long)(INF - 1) / MAXD) {
        fprintf(stderr, "weights: total %lld x MAXD %d reaches the INF sentinel; "
                "use a coarser scale\n", WTOTAL, MAXD);
        return 1;
    }
    /* The --topk / --order ssq score packs into (score << 20 | guess index). */
    if ((long long)NA * WTOTAL > (1LL << 42)) {
        fprintf(stderr, "weights: NA x total (%lld) would overflow the packed "
                "split-quality key\n", (long long)NA * WTOTAL);
        return 1;
    }
    WSALT = 0x9E3779B97F4A7C15ULL;
    for (int a = 0; a < NA; a++)
        WSALT = (WSALT ^ (uint64_t)WEIGHT[a]) * 0x100000001B3ULL;
    fprintf(stderr, "weights: %d answers, scale %lld, total %lld (%.6f), "
            "max %lld, salt %016llx\n",
            NA, WSCALE, WTOTAL, (double)WTOTAL / (double)WSCALE, WEIGHT[0],
            (unsigned long long)WSALT);
    return 0;
}
#endif

/* ------------------------------------------------- transposition table */

/* 32 bytes; two per 64-byte bucket, so a probe touches exactly one cache line */
typedef struct { uint64_t h0, h1x; int32_t val, d; uint32_t work, pad; } Entry;

static Entry   *TT;
static uint64_t TT_BUCKETS;
static long long g_probe = 0, g_hit = 0, g_fill = 0;
static size_t   TT_SLOTS = 0;

static size_t TT_BYTES = 0;

/* --tt-bits 0 runs with NO transposition table at all.  It exists for the
 * memory-starved phase where another solver owns the RAM; it is enormously
 * slower, because deep states recur constantly and every recurrence is then
 * recomputed from scratch.  A small table (--tt-bits 24 = 512 MB) is worth
 * orders of magnitude over none. */
static int TT_OFF = 0;

/* Load a table snapshot. Entries are self-verifying -- h1x carries h1 XORed
 * with the payload -- so a snapshot taken from a RUNNING solver is safe:
 * anything caught mid-write fails the check on lookup and is treated as a
 * miss, never a wrong value. A size mismatch means a different --tt-bits. */
static int tt_load(const char *path, size_t bytes) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "tt-load: cannot open %s\n", path); return -1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    if ((size_t)sz != bytes) {
        fprintf(stderr, "tt-load: %s is %ld bytes, expected %zu -- wrong --tt-bits?\n",
                path, sz, bytes);
        fclose(f);
        return -1;
    }
    rewind(f);
    double t0 = now_s();
    size_t got = 0;
    while (got < bytes) {
        size_t n = fread((char *)TT + got, 1, bytes - got, f);
        if (n == 0) { fprintf(stderr, "tt-load: short read at %zu\n", got); fclose(f); return -1; }
        got += n;
    }
    fclose(f);
    size_t live = 0;                    /* so occupancy starts from the truth */
    for (size_t i = 0; i < TT_SLOTS; i++)
        if (TT[i].h0 || TT[i].h1x) live++;
    g_fill = (long long)live;
    fprintf(stderr, "TT: loaded %s in %.1fs, %zu/%zu slots live (%.2f%%)\n",
            path, now_s() - t0, live, TT_SLOTS, 100.0 * live / TT_SLOTS);
    return 0;
}

static void tt_save(const char *path) {
    if (TT_OFF) { fprintf(stderr, "tt-save: no table to save (--tt-bits 0)\n"); return; }
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "tt-save: cannot write %s\n", path); return; }
    double t0 = now_s();
    size_t put = 0;
    while (put < TT_BYTES) {
        size_t n = fwrite((char *)TT + put, 1, TT_BYTES - put, f);
        if (n == 0) { fprintf(stderr, "tt-save: short write at %zu\n", put); break; }
        put += n;
    }
    fclose(f);
    fprintf(stderr, "TT: saved %.2f GB to %s in %.1fs\n", put / 1e9, path, now_s() - t0);
}

static void tt_init(int bits, const char *loadpath) {
    if (bits <= 0) {
        TT_OFF = 1;
        fprintf(stderr, "TT: DISABLED (--tt-bits 0) -- no memoisation\n");
        return;
    }
    if (bits < 2) bits = 2;
    TT_BUCKETS = (uint64_t)1 << (bits - 1);
    size_t bytes = (size_t)TT_BUCKETS * 2 * sizeof(Entry);
    TT_BYTES = bytes;
    TT = aligned_alloc(64, bytes);
    if (!TT) { fprintf(stderr, "cannot allocate %.2f GB TT\n", bytes / 1e9); exit(1); }
    TT_SLOTS = (size_t)TT_BUCKETS * 2;
    fprintf(stderr, "TT: 2^%d entries (%llu buckets x2), %.2f GB\n",
            bits, (unsigned long long)TT_BUCKETS, bytes / 1e9);
    if (!loadpath || tt_load(loadpath, bytes) != 0) {
        if (loadpath) fprintf(stderr, "TT: starting cold instead\n");
        memset(TT, 0, bytes);
    }
}

/* In hard mode the constraint is part of the state, so it is part of the key
 * (see the hard-mode block above).  `ch` is 0 in normal mode, leaving the hash
 * bit-identical to what it has always been. */
static inline void hash_state(const uint16_t *S, int n, int d, uint64_t ch,
                              uint64_t *h0, uint64_t *h1) {
    uint64_t a = (uint64_t)d * 0x9E3779B97F4A7C15ULL;
    uint64_t b = (uint64_t)d * 0xC2B2AE3D27D4EB4FULL;
    for (int i = 0; i < n; i++) { a ^= ZOB0[S[i]]; b ^= ZOB1[S[i]]; }
#if WGT
    /* The weight vector is part of the objective, so it is part of the key --
     * see WSALT.  Unconditional in this binary, so a table made under one set of
     * weights fails verification under another instead of answering. */
    a ^= WSALT;
    b ^= WSALT * 0xC2B2AE3D27D4EB4FULL;
#endif
    *h0 = a ^ ch ^ GSALT;
    *h1 = b ^ (ch * 0xD6E8FEB86659FD93ULL) ^ (GSALT * 0x9E3779B97F4A7C15ULL);
}

/* h1 is stored XORed with the payload, so a write torn by a concurrent writer
 * fails verification instead of returning a wrong value. */
static inline uint64_t tt_payload(int val, int d, int bestg) {
    return ((uint64_t)(uint32_t)val << 32) ^ (uint64_t)(uint32_t)d
         ^ ((uint64_t)(uint32_t)bestg << 16);
}

static inline int tt_get(uint64_t h0, uint64_t h1, int d, int *val, int *bestg) {
    if (TT_OFF) return 0;
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++) {
        Entry e = b[j];
        if (e.h0 == h0 && e.d == d
            && (e.h1x ^ tt_payload(e.val, e.d, (int)e.pad)) == h1) {
            *val = e.val;
            if (bestg) *bestg = (int)e.pad;
            return 1;
        }
    }
    return 0;
}

/* slot 0 keeps the costliest entry, slot 1 takes the most recent */
static inline void tt_put(uint64_t h0, uint64_t h1, int d, int val, int bestg,
                          uint32_t work, long long *fills) {
    if (TT_OFF) return;
    Entry e;
    e.h0 = h0; e.val = val; e.d = d; e.work = work; e.pad = (uint32_t)bestg;
    e.h1x = h1 ^ tt_payload(val, d, bestg);
    Entry *b = &TT[(h0 & (TT_BUCKETS - 1)) * 2];
    for (int j = 0; j < 2; j++)
        if (b[j].h0 == h0 && b[j].d == d) { b[j] = e; return; }
    if (b[0].h0 == 0 && b[0].h1x == 0) { b[0] = e; (*fills)++; return; }
    if (b[1].h0 == 0 && b[1].h1x == 0) { b[1] = e; (*fills)++; return; }
    if (work >= b[0].work) { b[1] = b[0]; b[0] = e; }
    else                     b[1] = e;
}

/* ------------------------------------------------------ per-thread arena */

typedef struct {
    uint16_t buf[MAXD][MAXA];
    uint16_t tbuf[MAXD][MAXA];     /* separate scratch for tree extraction */
    int      cnt[MAXD][NPAT];      /* invariant: all zero between uses */
    int      kof[MAXD][NPAT];      /* pattern -> compact bucket index */
    int      lbg[MAXD][MAXG];
    int64_t  ord[MAXD][MAXG];
    uint16_t leg[MAXD][MAXG];      /* hard mode: guesses this state may play */
    int32_t  mark[MAXD][MAXG];     /* --topk: stamped membership, no clearing */
    int32_t  tag[MAXD];            /* current stamp value per depth */
#if WGT
    /* per-pattern weighted accumulators, filled during the SAME counting pass
     * that fills cnt[] -- invariant: all zero between uses, like cnt[] */
    long long wlbp[MAXD][NPAT];    /* bucket's weighted lower bound */
    long long wsp[MAXD][NPAT];     /* bucket's summed weight */
#endif
    long long nodes, probe, hit, fill;
} Ctx;

static int cmp_i64(const void *a, const void *b) {
    int64_t x = *(const int64_t *)a, y = *(const int64_t *)b;
    return (x > y) - (x < y);
}

/* ---------------------------------------------------------------- solver */

static int solve(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx);

/* Cost of playing guess g at state S.  Returns INF if it cannot finish, or if
 * it provably cannot beat `best` (then the value is a bound, not the true cost
 * -- callers only use it to improve `best`, never to memoise).
 *
 * The caller is responsible for g being legal; in hard mode it comes from the
 * state's legal list.  Each successor bucket inherits the constraint extended
 * by the (g, pattern) feedback that produced it. */
static int eval_guess(const uint16_t *S, int n, int d, int g, int best,
                      const Cons *C, Ctx *ctx) {
    int *cnt = ctx->cnt[d], *kof = ctx->kof[d];
    uint16_t *buf = ctx->buf[d];
    const pat_t *row = PAT + (size_t)g * NA;
    /* indexed by BUCKET ORDINAL, not by pattern: nb <= n <= NA <= MAXA */
    int bp[MAXA], bcnt[MAXA], bstart[MAXA], bfill[MAXA], nb = 0;

    for (int i = 0; i < n; i++) {
        int p = row[S[i]];
        if (cnt[p]++ == 0) bp[nb++] = p;
    }
    /* snapshot counts and restore cnt[] to all-zero immediately, so every path
     * below is free to return without leaving the arena dirty */
    for (int k = 0; k < nb; k++) { bcnt[k] = cnt[bp[k]]; cnt[bp[k]] = 0; }

    /* largest bucket first: the biggest subproblem settles the bound earliest */
    for (int i = 1; i < nb; i++) {
        int tp = bp[i], tc = bcnt[i], j = i - 1;
        while (j >= 0 && bcnt[j] < tc) { bp[j + 1] = bp[j]; bcnt[j + 1] = bcnt[j]; j--; }
        bp[j + 1] = tp; bcnt[j + 1] = tc;
    }
    for (int k = 0; k < nb; k++) kof[bp[k]] = k;

    int acc = 0;
    for (int k = 0; k < nb; k++) { bstart[k] = acc; bfill[k] = acc; acc += bcnt[k]; }
    for (int i = 0; i < n; i++) buf[bfill[kof[row[S[i]]]]++] = S[i];

    int lbrest = 0;
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN) continue;
        int v = STATE_LB(buf + bstart[k], bcnt[k], d - 1);
        if (v >= INF) return INF;
        lbrest += v;
    }

    /* every candidate still alive pays for this guess: the COUNT outside
     * weighted mode, their summed WEIGHT inside it */
    int total = (int)STATE_W(S, n);
    for (int k = 0; k < nb; k++) {
        if (bp[k] == ALL_GREEN) continue;
        int own = STATE_LB(buf + bstart[k], bcnt[k], d - 1);
        lbrest -= own;
        if (total + lbrest + own >= best) return INF;
        Cons kid;
        if (USE_CONS) cons_apply(&kid, C, g, bp[k]);
        int v = solve(buf + bstart[k], bcnt[k], d - 1, USE_CONS ? &kid : C, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest >= best) return INF;
    }
    return total;
}

static int solve(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx) {
    if (n == 1) return (int)AW(S[0]);
    if (d <= 1) return INF;
    if (n == 2) {
        /* Guess either candidate: 1 if it is the answer, 2 if it is the other.
         * Weighted, that is w_first + 2 * w_second, so the HEAVIER one is played
         * first -- and S[0] is the heavier, the state being weight-ordered.
         * With every weight 1 this is the 3 it has always been. */
        if (!PHANTOM || ANS2G[S[0]] >= 0 || ANS2G[S[1]] >= 0)
            return (int)(AW(S[0]) + 2 * AW(S[1]));
        /* Under --phantom-final NEITHER may be played, so the pair has to be
         * SPLIT by some third guess and each half then costs its own phantom
         * naming move: 2 (the splitter, charged to both) + 1 + 1 = 4.  No guess
         * can do better -- one guess cannot resolve either candidate when
         * neither is playable -- so the first separating guess proves the value
         * and there is nothing to search.  Hard mode falls through to the
         * general search instead, since there the legal set is constrained;
         * it never reaches here anyway, its answers all being legal guesses. */
        if (!USE_CONS) {
            for (int g = 0; g < NG; g++)
                if (PAT[(size_t)g * NA + S[0]] != PAT[(size_t)g * NA + S[1]]) return 4;
            return INF;                         /* no guess separates the two */
        }
    }

    /* Depth normalisation: every guess in an optimal line strictly shrinks the
     * candidate set, so n candidates are always resolved within n guesses --
     * beyond that the budget cannot bind and f(S,d) == f(S,n).  Collapsing the
     * key raises the TT hit rate for small sets reached with lots of budget.
     * Holds in hard mode too: a candidate is always a legal guess, so guessing
     * candidates one at a time resolves n of them in at most n turns.  And
     * under --phantom-final, where that is no longer true: any splitting guess
     * drops the largest bucket to n-1, so f(n) <= 1 + f(n-1) = n still, and a
     * state with no splitting guess at all is INF at every depth. */
    if (d > n) d = n;

    int lb0 = STATE_LB(S, n, d);
    if (lb0 >= INF) return INF;

    uint64_t h0, h1;
    hash_state(S, n, d, USE_CONS ? cons_hash(C) : 0, &h0, &h1);
    int cached, cachedg;
    ctx->probe++;
    if (tt_get(h0, h1, d, &cached, &cachedg)) { ctx->hit++; return cached; }

    /* Only now, past the TT, is the legal set worth materialising. */
    uint16_t *leg = ctx->leg[d];
    int nleg = USE_CONS ? cons_legal(C, leg) : NG;

    long long nodes0 = ctx->nodes++;
    int best = INF, bestg = -1;
    /* what every alive candidate pays for one guess here: n, or their weight */
    long long WS = STATE_W(S, n);

    /* d == 2 closed form: the only finisher is a guess whose non-green buckets
     * are all singletons, costing 2n - (1 if g is itself in S). */
    if (d == 2) {
        int *cnt = ctx->cnt[d];
        for (int pass = 0; pass < 2; pass++) {
            int lim = (pass == 0) ? n : nleg;
            for (int t = 0; t < lim; t++) {
                int g = (pass == 0) ? ANS2G[S[t]] : (USE_CONS ? (int)leg[t] : t);
                if (g < 0) continue;            /* --phantom-final: unplayable candidate */
                const pat_t *row = PAT + (size_t)g * NA;
                /* Count every element -- never break early.  bp[] must end up
                 * holding EVERY touched pattern or the clear loop below leaks
                 * counters into the next call and corrupts the arena. */
                int bp[MAXA], nb = 0, dup = 0;   /* bucket ordinal, nb <= n */
                for (int i = 0; i < n; i++) {
                    int p = row[S[i]];
                    if (cnt[p]++ == 0) bp[nb++] = p;
                    else if (p != ALL_GREEN) dup = 1;
                }
                int green = cnt[ALL_GREEN] > 0;
                for (int k = 0; k < nb; k++) cnt[bp[k]] = 0;
                if (dup) continue;
                /* Cost is 2 * WS minus the winner's own second guess, which it
                 * does not pay -- so the best finisher is the HEAVIEST candidate
                 * that splits the rest into singletons.  Pass 0 walks the
                 * candidates in weight-descending order, so its first success IS
                 * that one; and any non-candidate scores a strictly worse 2 * WS,
                 * so a pass-0 hit ends the scan.  With every weight 1 this is the
                 * 2n-1 / 2n it has always been. */
                if (green) {
                    if (!WGT) { best = (int)(2 * WS) - 1; bestg = g; goto d2done; }
                    if (pass == 0) { best = (int)(2 * WS - AW(S[t])); bestg = g; goto d2done; }
                    continue;              /* weighted: pass 0 already scored it */
                }
                if (2 * WS < best) { best = (int)(2 * WS); bestg = g; }
            }
        }
    d2done:
        tt_put(h0, h1, d, best, bestg, 1, &ctx->fill);
        return best;
    }

    /* pass 1: per-guess lower bound from its partition profile.  When --topk is
     * on this also records the SUM OF SQUARED BIN SIZES, the split-quality score
     * the K survivors are chosen by -- computed from the same counts, so it is
     * nearly free and costs the exact path nothing. */
    int *cnt = ctx->cnt[d], *lbg = ctx->lbg[d];
    int64_t *ssq = ctx->ord[d];                  /* reused as (ss << 20 | g) */
    int bestlb = INF, bestlb_g = -1, bestlb_in = 0, nss = 0;
    for (int t = 0; t < nleg; t++) {
        int g = USE_CONS ? (int)leg[t] : t;
        const pat_t *row = PAT + (size_t)g * NA;
        int bp[MAXA], nb = 0;                    /* bucket ordinal, nb <= n */
#if WGT
        /* The r-th answer to arrive in a bucket is that bucket's r-th HEAVIEST,
         * the state being weight-ordered -- so the bucket's weighted bound and
         * summed weight both accumulate DURING the counting pass and the loop
         * stays O(n), exactly as the unweighted one is. */
        long long *wlbp = ctx->wlbp[d], *wsp = ctx->wsp[d];
        for (int i = 0; i < n; i++) {
            int p = row[S[i]], r = cnt[p]++;
            if (r == 0) bp[nb++] = p;
            wlbp[p] += WEIGHT[S[i]] * LVL[d - 1][r];
            wsp[p]  += WEIGHT[S[i]];
        }
        int lv = (int)WS, dead = 0, ing = 0;
        int64_t ss = 0;
        for (int k = 0; k < nb; k++) {
            int p = bp[k], c = cnt[p];
            if (p == ALL_GREEN) { ing = 1; continue; }
            /* Split quality, weighted: the expected number of candidate WORDS
             * still alive, sum over losing bins of (bin size x bin weight).
             * The WIN is excluded -- topk.py's rule, so that a guess which could
             * BE the answer beats an equally-splitting outside word.  (The
             * unweighted score below includes it, as it always has.) */
            if (TOPK > 0) ss += (int64_t)c * wsp[p];
            if (c == n) { dead = 1; break; }             /* guess reveals nothing */
            if (LVL[d - 1][c - 1] == 0) { dead = 1; break; }
            lv += (int)wlbp[p];
        }
        for (int k = 0; k < nb; k++) { cnt[bp[k]] = 0; wlbp[bp[k]] = 0; wsp[bp[k]] = 0; }
#else
        for (int i = 0; i < n; i++) {
            int p = row[S[i]];
            if (cnt[p]++ == 0) bp[nb++] = p;
        }
        int lv = n, dead = 0, ing = 0;
        int64_t ss = 0;
        for (int k = 0; k < nb; k++) {
            int p = bp[k], c = cnt[p];
            if (TOPK > 0) ss += (int64_t)c * c;
            if (p == ALL_GREEN) { ing = 1; continue; }
            if (c == n) { dead = 1; break; }             /* guess reveals nothing */
            int v = LBTAB[d - 1][c];
            if (v >= INF) { dead = 1; break; }
            lv += v;
        }
        for (int k = 0; k < nb; k++) cnt[bp[k]] = 0;
#endif
        lbg[g] = dead ? INF : lv;
        if (!dead) {
            if (TOPK > 0) ssq[nss++] = (ss << 20) | (int64_t)g;
            if (lv < bestlb || (lv == bestlb && ing && !bestlb_in)) {
                bestlb = lv; bestlb_g = g; bestlb_in = ing;
            }
        }
    }
    if (bestlb_g < 0) { tt_put(h0, h1, d, INF, -1, 1, &ctx->fill); return INF; }

    /* ---- --topk: keep only the K most evenly-splitting guesses -------------
     * Ordered by ASCENDING sum of squares, so the evenest split ranks first.
     * The survivors are then re-keyed by lower bound, because that is the better
     * order to SEARCH in even though split quality is what SELECTS them. */
    if (TOPK > 0) {
        qsort(ssq, nss, sizeof(int64_t), cmp_i64);
        int K = (TOPK < nss) ? TOPK : nss;
        int32_t *mark = ctx->mark[d], tag = ++ctx->tag[d];
        for (int i = 0; i < K; i++) {
            int g = (int)(ssq[i] & 0xFFFFF);
            mark[g] = tag;
            ssq[i] = ((int64_t)lbg[g] << 20) | (int64_t)g;
        }
        /* A tight K can leave every word in S unplayable, which would report
         * INFEASIBLE for a state that is perfectly solvable.  Below the cutoff
         * the candidates are cheap to add, so add them and let the total degrade
         * gracefully instead. */
        if (n <= TOPK)
            for (int i = 0; i < n; i++) {
                int g = ANS2G[S[i]];
                if (g < 0) continue;            /* --phantom-final: unplayable candidate */
                if (mark[g] != tag && lbg[g] < INF) {
                    mark[g] = tag;
                    ssq[K++] = ((int64_t)lbg[g] << 20) | (int64_t)g;
                }
            }
        qsort(ssq, K, sizeof(int64_t), cmp_i64);

        int seed = (int)(ssq[0] & 0xFFFFF);
        int v0 = eval_guess(S, n, d, seed, INF, C, ctx);
        if (v0 < best) { best = v0; bestg = seed; }
        if (best > lb0)
            for (int i = 1; i < K; i++) {
                if ((int)(ssq[i] >> 20) >= best) break;   /* sorted: none left can win */
                int g = (int)(ssq[i] & 0xFFFFF);
                int v = eval_guess(S, n, d, g, best, C, ctx);
                if (v < best) { best = v; bestg = g; }
                if (best <= lb0) break;                   /* provably optimal */
            }
        long long workk = ctx->nodes - nodes0;
        tt_put(h0, h1, d, best, bestg,
               workk > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)workk, &ctx->fill);
        return best;
    }

    /* seed the incumbent with the most promising guess; only guesses whose
     * bound still undercuts it are worth sorting or exploring at all */
    int v0 = eval_guess(S, n, d, bestlb_g, INF, C, ctx);
    if (v0 < best) { best = v0; bestg = bestlb_g; }

    if (best > lb0) {
        int64_t *ord = ctx->ord[d];
        int m = 0;
        /* iterate the legal list, not 0..NG: lbg[] was only written for legal
         * guesses this call, so anything else is a stale value from a previous
         * state at this depth */
        for (int t = 0; t < nleg; t++) {
            int g = USE_CONS ? (int)leg[t] : t;
            if (lbg[g] < best && g != bestlb_g)
                ord[m++] = ((int64_t)lbg[g] << 20) | (int64_t)g;
        }
        qsort(ord, m, sizeof(int64_t), cmp_i64);
        for (int i = 0; i < m; i++) {
            if ((int)(ord[i] >> 20) >= best) break;   /* sorted: none left can win */
            int g = (int)(ord[i] & 0xFFFFF);
            int v = eval_guess(S, n, d, g, best, C, ctx);
            if (v < best) { best = v; bestg = g; }
            if (best <= lb0) break;                   /* provably optimal */
        }
    }

    long long work = ctx->nodes - nodes0;
    tt_put(h0, h1, d, best, bestg,
           work > 0xFFFFFFFFLL ? 0xFFFFFFFFu : (uint32_t)work, &ctx->fill);
    return best;
}

/* --------------------------------------------------------- tree extraction */

/* Optimal guess at S.  Fast path is the TT slot written by solve(); if that has
 * been evicted, rescan for a guess achieving the known value (eval_guess with
 * bound v+1 returns v exactly when g is optimal, else INF). */
static int best_move(const uint16_t *S, int n, int d, const Cons *C, Ctx *ctx) {
    /* A candidate is normally always legal, so playing one resolves n <= 2.
     * Under --phantom-final take whichever of the two IS legal; when neither is,
     * fall through and search for the separating guess solve() priced at 4.
     * n == 1 with no legal naming move returns -1: emit_tree reads that as the
     * phantom final and writes the line itself. */
    if (n == 1) return ANS2G[S[0]];
    if (n == 2) {
        if (ANS2G[S[0]] >= 0) return ANS2G[S[0]];
        if (ANS2G[S[1]] >= 0) return ANS2G[S[1]];
    }
    int v = solve(S, n, d, C, ctx);
    if (v >= INF) return -1;
    if (d > n) d = n;
    uint64_t h0, h1;
    hash_state(S, n, d, USE_CONS ? cons_hash(C) : 0, &h0, &h1);
    int val, bg;
    if (tt_get(h0, h1, d, &val, &bg) && bg >= 0 && val == v) return bg;
    uint16_t *leg = ctx->leg[d];
    int nleg = USE_CONS ? cons_legal(C, leg) : NG;
    for (int pass = 0; pass < 2; pass++) {
        int lim = (pass == 0) ? n : nleg;
        for (int t = 0; t < lim; t++) {
            int g = (pass == 0) ? ANS2G[S[t]] : (USE_CONS ? (int)leg[t] : t);
            if (g < 0) continue;                /* --phantom-final: unplayable candidate */
            if (eval_guess(S, n, d, g, v + 1, C, ctx) == v) return g;
        }
    }
    return -1;
}

/* Emit one line per answer: "<answer> <nguesses> <g1> <p1> <g2> <p2> ... <answer>"
 * The final guess always equals the answer, so each line is a complete replay. */
static int emit_tree(FILE *out, const uint16_t *S, int n, int d,
                     char *path, int plen, int ply, const Cons *C, Ctx *ctx) {
    /* --phantom-final: the set is down to one word that cannot be played.  The
     * scoring charges one more guess for naming it, so write the answer itself
     * as that final guess -- which keeps the line a complete replay ending
     * all-green, exactly the invariant checktrees.py verifies.  The only thing
     * it is not is a LEGAL guess, and only on the last move of such a line. */
    if (n == 1 && ANS2G[S[0]] < 0) {
        fprintf(out, "%s %d %.*s%s\n", AWORD[S[0]], ply + 1, plen, path, AWORD[S[0]]);
        return 0;
    }
    int g = best_move(S, n, d, C, ctx);
    if (g < 0) return -1;
    const char *gw = GWORD[g];

    int *sc = pat_scratch(3);
    int *cnt = PSLOT(sc, 0), *start = PSLOT(sc, 1), *fill = PSLOT(sc, 2);
    uint16_t *buf = ctx->tbuf[d];
    const pat_t *row = PAT + (size_t)g * NA;
    for (int i = 0; i < n; i++) cnt[row[S[i]]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, (size_t)NPAT * sizeof(int));
    for (int i = 0; i < n; i++) buf[fill[row[S[i]]]++] = S[i];

    if (cnt[ALL_GREEN] > 0) {                    /* guess is itself the answer */
        int a = buf[start[ALL_GREEN]];
        fprintf(out, "%s %d %.*s%s\n", AWORD[a], ply + 1, plen, path, gw);
    }
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        char ps[PATSTR_BUF];
        pat_str(p, ps);
        int add = snprintf(path + plen, 4096 - plen, "%s %s ", gw, ps);
        Cons kid;
        if (USE_CONS) cons_apply(&kid, C, g, p);
        if (emit_tree(out, buf + start[p], cnt[p], d - 1, path, plen + add, ply + 1,
                      USE_CONS ? &kid : C, ctx) < 0) {
            free(sc);
            return -1;
        }
    }
    free(sc);
    return 0;
}

/* ------------------------------------------------------------ root driver */

static int solve_opener(int g, int depth, Ctx *ctx) {
    uint16_t root[MAXA];
    int *sc = pat_scratch(3);
    int *cnt = PSLOT(sc, 0), *start = PSLOT(sc, 1), *fill = PSLOT(sc, 2);
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, (size_t)NPAT * sizeof(int));
    for (int a = 0; a < NA; a++) root[fill[row[a]]++] = (uint16_t)a;

    int total = (int)ALL_W;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        Cons kid;                                /* the opener itself is unconstrained */
        if (USE_CONS) cons_apply(&kid, &CONS_NONE, g, p);
        int v = solve(root + start[p], cnt[p], depth - 1, USE_CONS ? &kid : &CONS_NONE, ctx);
        if (v >= INF) { free(sc); return INF; }
        total += v;
    }
    free(sc);
    return total;
}

/* Solve `g` at the SMALLEST cap that admits a solution, starting at `dmin` and
 * raising it one guess at a time up to `dmax`.
 *
 * This is the hard-mode answer to a problem normal mode does not have: there,
 * every opener wins within 6 by following SALET's tree afterwards, so one fixed
 * cap suffices.  Hard mode has no such escape -- the follow-up must keep reusing
 * the revealed hints -- so a fixed cap simply returns NOTHING for the openers it
 * cannot fit, which is exactly the data we want.  Escalating instead yields both
 * the total AND the number of guesses that opener actually requires.
 *
 * NOTE what this does and does not compute.  It returns the minimum total at the
 * FIRST feasible cap.  Because f(S,d) is non-increasing in d, a still-deeper cap
 * may admit a LOWER total -- letting one answer run long to save guesses
 * elsewhere.  So `*used` is the minimum feasible DEPTH and the total is optimal
 * SUBJECT TO that depth; it is not, in general, the unconstrained minimum
 * expected guesses.  Establishing that needs a separate stabilisation pass, for
 * which the per-opener (total, depth) recorded in the CSV is the seed. */
static int solve_escalating(int g, int dmin, int dmax, Ctx *ctx, int *used) {
    for (int d = dmin; d <= dmax; d++) {
        double t0 = now_s();
        int total = solve_opener(g, d, ctx);
        if (total < INF) { *used = d; return total; }
        /* Report each rejected cap as it falls.  Proving infeasibility at a
         * too-tight cap can take a long time, and without this the escalation is
         * silent for as long as it takes -- which reads as a hang rather than as
         * progress.  Every caller is sequential (the single-opener loop, and the
         * optimal-only probe, which runs before the parallel region opens), so
         * this cannot interleave with another thread's output. */
        if (d < dmax)
            printf("%s  INFEASIBLE at depth %d  (%.1fs) -- escalating to %d\n",
                   GWORD[g], d, now_s() - t0, d + 1);
        else
            printf("%s  INFEASIBLE at depth %d  (%.1fs) -- that was --depth-max\n",
                   GWORD[g], d, now_s() - t0);
        fflush(stdout);
    }
    *used = 0;
    return INF;
}

/* --------------------------------------------- root branch-and-bound (--optimal-only)
 *
 * For finding THE optimal opener and nothing else.  A full sweep spends nearly
 * all its time proving exact totals for openers that were never going to win;
 * this proves the winner instead, and merely bounds everyone else.
 *
 * CUTOFF is "provably worse than the bound" -- a real answer to the only
 * question being asked, distinct from INF ("cannot solve within the cap"). */
#define CUTOFF (INF - 1)

/* The opener's root lower bound: no search at all, O(NA).
 *
 * Every answer costs the opener itself (NA), plus at least LBTAB[d-1][|P|] for
 * each surviving partition P.  Since the sweep visits openers in ASCENDING LB,
 * the first opener whose LB exceeds the incumbent proves every opener after it
 * is worse too -- so the tail is discarded wholesale, without being solved. */
static int root_lb(int g, int depth) {
    int *cnt = pat_scratch(1);
    const pat_t *row = PAT + (size_t)g * NA;
#if WGT
    /* Answer indices ARE weight-descending, so the r-th answer landing in a
     * bucket is that bucket's r-th heaviest and the bound accumulates in the
     * same single pass the counts do. */
    long long *wl = calloc((size_t)NPAT + 1, sizeof(long long));
    if (!wl) { fprintf(stderr, "root_lb: out of memory\n"); exit(1); }
    for (int a = 0; a < NA; a++) {
        int p = row[a], r = cnt[p]++;
        wl[p] += WEIGHT[a] * LVL[depth - 1][r];
    }
    long long lb = ALL_W;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        if (LVL[depth - 1][cnt[p] - 1] == 0) { free(cnt); free(wl); return INF; }
        lb += wl[p];
    }
    free(cnt); free(wl);
    return (int)lb;
#else
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int lb = NA;
    for (int p = 0; p < NPAT; p++) {
        if (p == ALL_GREEN || cnt[p] == 0) continue;
        int v = LBTAB[depth - 1][cnt[p]];
        if (v >= INF) { free(cnt); return INF; }
        lb += v;
    }
    free(cnt);
    return lb;
#endif
}

/* Exact total if it is <= `bound`, CUTOFF if provably above it, INF if the
 * opener cannot solve within `depth`.
 *
 * The bound lives ONLY at this level, between the root's partitions.  It is
 * deliberately NOT passed into solve(): those values are memoised, and the
 * exactness note at the top of this file is explicit that a beta inherited from
 * a parent would store a bound where an exact value belongs and poison every
 * later query.  Cutting between root partitions changes nothing that is stored.
 *
 * Partitions are solved LARGEST FIRST so the costliest subproblem gets the first
 * chance to blow the budget, before the cheap ones have been paid for.
 *
 * TIES SURVIVE.  The test is `> bound`, never `>=`: an opener whose true total
 * equals the incumbent always satisfies partial + lbrest <= true total <= bound,
 * so it is never cut and is still reported. */
static int solve_opener_bounded(int g, int depth, Ctx *ctx, int bound) {
    uint16_t root[MAXA];
    int *sc = pat_scratch(3);
    int *cnt = PSLOT(sc, 0), *start = PSLOT(sc, 1), *fill = PSLOT(sc, 2);
    const pat_t *row = PAT + (size_t)g * NA;
    for (int a = 0; a < NA; a++) cnt[row[a]]++;
    int acc = 0;
    for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
    start[NPAT] = acc;
    memcpy(fill, start, (size_t)NPAT * sizeof(int));
    for (int a = 0; a < NA; a++) root[fill[row[a]]++] = (uint16_t)a;

    int ps[MAXA], np = 0;                        /* bucket ordinal, np <= NA */
    for (int p = 0; p < NPAT; p++)
        if (p != ALL_GREEN && cnt[p] > 0) ps[np++] = p;
    for (int i = 1; i < np; i++) {                  /* insertion sort, np <= 242 */
        int key = ps[i], j = i - 1;
        while (j >= 0 && cnt[ps[j]] < cnt[key]) { ps[j + 1] = ps[j]; j--; }
        ps[j + 1] = key;
    }

    int lbrest = 0;
    for (int i = 0; i < np; i++) {
        int v = STATE_LB(root + start[ps[i]], cnt[ps[i]], depth - 1);
        if (v >= INF) return INF;
        lbrest += v;
    }

    int total = (int)ALL_W;
    if (total + lbrest > bound) return CUTOFF;
    for (int i = 0; i < np; i++) {
        int p = ps[i];
        lbrest -= STATE_LB(root + start[p], cnt[p], depth - 1);
        Cons kid;
        if (USE_CONS) cons_apply(&kid, &CONS_NONE, g, p);
        int v = solve(root + start[p], cnt[p], depth - 1, USE_CONS ? &kid : &CONS_NONE, ctx);
        if (v >= INF) return INF;
        total += v;
        if (total + lbrest > bound) return CUTOFF;
    }
    return total;
}

/* ------------------------------------------------------- PAIR OPENERS ----
 *
 * Cost of committing to the pair (g1, g2) played BLIND: both words fixed in
 * advance, g2 NOT chosen in response to g1's feedback.
 *
 * ORDER MATTERS, so (a,b) and (b,a) are DIFFERENT candidates and both must be
 * evaluated.  The joint partition itself is order-independent -- which is why
 * the sum-of-squares screen emits each pair once -- but the COST is not:
 *
 *   - the answer equal to g1 wins at guess 1 and never plays g2, so it costs 1
 *     rather than 2.  Playing the answer-word first is worth exactly 1, which
 *     is measurable: parse+clint is 8325 against clint+parse's 8326.
 *   - under --pair-early-finish the asymmetry is much larger, because the rule
 *     keys on singleton buckets of the FIRST word's partition.
 *
 * --pair-early-finish: when g1 alone has already narrowed the field to ONE
 * answer, say that answer at guess 2 instead of playing g2 blindly.  Those
 * answers cost 2 rather than 3.  Nothing else changes -- the joint buckets of
 * every other answer are untouched -- so the two models differ by exactly the
 * number of non-winning singleton g1-buckets whose answer is not g2 itself.
 *
 * THE ACCOUNTING, in the two-level form the early-finish rule requires:
 *
 *     total = NA                        guess 1, paid by every answer
 *           + for each non-winning g1-bucket B:
 *               1              if |B| == 1 and early-finish  (say it)
 *               |B|            otherwise                     (play g2)
 *           + for each g2 sub-bucket that is not an outright win:
 *               solve(sub-bucket, depth - 2)
 *
 * Returns CUTOFF if provably worse than `bound`, INF if it cannot finish within
 * the cap.  The bound NEVER enters solve(): those values are memoised and must
 * stay exact, so cutting happens only between root sub-buckets.  TIES SURVIVE --
 * every test is `> bound`, never `>=`. */
/* --pair-adaptive N: when g1 ALONE has already cut the field to N or fewer
 * answers, abandon the blind second word and play optimally from there.
 *
 *   N = 0  pure blind -- g2 is always played (the default)
 *   N = 1  if one answer remains, say it at guess 2                 (cost 2)
 *   N = 2  if two remain, guess them in order                       (cost 2 + 3)
 *
 * Both special cases are the SAME rule, which is why this is one knob and not
 * two: solve() on a 1-answer set returns 1, and on a 2-answer set returns 3
 * (name one, and if wrong name the other) -- exactly "guess both in order", and
 * provably the best either set admits.  So the adaptive branch is just the
 * ordinary optimal continuation with depth-1 guesses left, in place of the blind
 * expansion with depth-2 left.
 *
 * This is a STRICT improvement per bucket, never a trade: blind play of g2 on a
 * tiny bucket can only match the optimum, and usually loses to it -- on a 2-set
 * it costs 6 when g2 separates them and 7 when it does not, against 5. */
static int PAIR_ADAPT = 0;

typedef struct { int start, len, d; } SubJob;

static int cmp_subjob(const void *a, const void *b) {
    const SubJob *x = a, *y = b;                 /* largest first */
    return (y->len > x->len) - (y->len < x->len);
}

static int solve_pair_bounded(int g1, int g2, int depth, Ctx *ctx, int bound) {
    const pat_t *r1 = PAT + (size_t)g1 * NA;
    const pat_t *r2 = PAT + (size_t)g2 * NA;

    int *cnt1 = calloc(NPAT, sizeof(int));
    int *kof1 = calloc(NPAT, sizeof(int));
    int *cnt2 = calloc(NPAT, sizeof(int));
    int *kof2 = calloc(NPAT, sizeof(int));
    int *k1   = malloc(sizeof(int) * NPAT);
    int *k2   = malloc(sizeof(int) * NPAT);
    int *st1  = malloc(sizeof(int) * (NPAT + 1));
    int *fl1  = malloc(sizeof(int) * (NPAT + 1));
    int *fl2  = malloc(sizeof(int) * (NPAT + 1));
    uint16_t *ord = malloc(sizeof(uint16_t) * NA);
    uint16_t *buf = malloc(sizeof(uint16_t) * NA);
    SubJob   *job = malloc(sizeof(SubJob) * (NA + 1));
    if (!cnt1 || !buf || !job) { fprintf(stderr, "out of memory in solve_pair_bounded\n"); exit(1); }

    /* ---- level 1: partition the answers by g1 */
    int nk1 = 0;
    for (int a = 0; a < NA; a++)
        if (cnt1[r1[a]]++ == 0) k1[nk1++] = r1[a];
    int acc = 0;
    for (int i = 0; i < nk1; i++) {
        st1[i] = acc; fl1[i] = acc; acc += cnt1[k1[i]]; kof1[k1[i]] = i;
    }
    for (int a = 0; a < NA; a++) ord[fl1[kof1[r1[a]]]++] = (uint16_t)a;

    int total = NA;                  /* guess 1, everyone */
    int njob = 0, bufn = 0, rc;

    for (int i = 0; i < nk1; i++) {
        int p1 = k1[i], s = st1[i], n1 = cnt1[p1];
        if (p1 == ALL_GREEN) continue;                  /* won at guess 1, costs 1 */

        if (PAIR_ADAPT > 0 && n1 <= PAIR_ADAPT) {
            /* drop the blind word: solve this bucket outright, depth-1 left.
             * Copied into buf so every job indexes one array. */
            memcpy(buf + bufn, ord + s, sizeof(uint16_t) * n1);
            job[njob].start = bufn; job[njob].len = n1; job[njob].d = depth - 1;
            njob++; bufn += n1;
            continue;
        }

        total += n1;                                    /* guess 2, this bucket */
        int nk2 = 0;
        for (int t = s; t < s + n1; t++)
            if (cnt2[r2[ord[t]]]++ == 0) k2[nk2++] = r2[ord[t]];
        int off = bufn;
        for (int j = 0; j < nk2; j++) { kof2[k2[j]] = j; fl2[j] = off; off += cnt2[k2[j]]; }
        for (int t = s; t < s + n1; t++) buf[fl2[kof2[r2[ord[t]]]]++] = ord[t];

        int base = bufn;
        for (int j = 0; j < nk2; j++) {
            int n2 = cnt2[k2[j]];
            if (k2[j] != ALL_GREEN) {                   /* else won at guess 2 */
                job[njob].start = base; job[njob].len = n2; job[njob].d = depth - 2;
                njob++;
            }
            base += n2;
            cnt2[k2[j]] = 0;
        }
        bufn = off;
    }

    qsort(job, njob, sizeof(SubJob), cmp_subjob);

    int lbrest = 0;
    for (int i = 0; i < njob; i++) {
        int v = LBTAB[job[i].d][job[i].len];
        if (v >= INF) { rc = INF; goto done; }
        lbrest += v;
    }
    if (total + lbrest > bound) { rc = CUTOFF; goto done; }

    for (int i = 0; i < njob; i++) {
        lbrest -= LBTAB[job[i].d][job[i].len];
        int v = solve(buf + job[i].start, job[i].len, job[i].d, &CONS_NONE, ctx);
        if (v >= INF) { rc = INF; goto done; }
        total += v;
        if (total + lbrest > bound) { rc = CUTOFF; goto done; }
    }
    rc = total;

done:
    free(cnt1); free(kof1); free(cnt2); free(kof2); free(k1); free(k2);
    free(st1); free(fl1); free(fl2); free(ord); free(buf); free(job);
    return rc;
}

/* Cost of committing to the BLIND triple (g1, g2, g3), the direct generalisation
 * of solve_pair_bounded.  Each word is fixed in advance; none is chosen from the
 * previous one's feedback.
 *
 * The accounting has one more early-win term than the pair case, and the same
 * trap: an answer that wins at guess 1 never plays g2 OR g3, and one that wins at
 * guess 2 never plays g3, so charging every answer 3 for the opening overstates
 * the total by up to 3.
 *
 *   total = NA                            guess 1, everyone
 *         + (NA - won1)                   guess 2, everyone still playing
 *         + (NA - won1 - won2)            guess 3, everyone still playing
 *         + sum solve(bucket, depth - 3)  over buckets still unresolved
 *
 * --pair-adaptive N applies at BOTH branch points, which is what makes it the
 * same rule rather than a new one: if g1 alone leaves N or fewer answers, drop
 * g2 AND g3 and solve with depth-1 left; else if g1+g2 leave N or fewer, drop g3
 * and solve with depth-2 left; else play all three. */
static int solve_triple_bounded(int g1, int g2, int g3, int depth, Ctx *ctx, int bound) {
    const pat_t *r1 = PAT + (size_t)g1 * NA;
    const pat_t *r2 = PAT + (size_t)g2 * NA;
    const pat_t *r3 = PAT + (size_t)g3 * NA;

    int *c1 = calloc(NPAT, sizeof(int)), *k1 = malloc(sizeof(int) * NPAT);
    int *o1 = calloc(NPAT, sizeof(int)), *s1 = malloc(sizeof(int) * (NPAT + 1));
    int *f1 = malloc(sizeof(int) * (NPAT + 1));
    int *c2 = calloc(NPAT, sizeof(int)), *k2 = malloc(sizeof(int) * NPAT);
    int *o2 = calloc(NPAT, sizeof(int)), *f2 = malloc(sizeof(int) * (NPAT + 1));
    int *c3 = calloc(NPAT, sizeof(int)), *k3 = malloc(sizeof(int) * NPAT);
    int *o3 = calloc(NPAT, sizeof(int)), *f3 = malloc(sizeof(int) * (NPAT + 1));
    uint16_t *ord = malloc(sizeof(uint16_t) * NA);
    uint16_t *mid = malloc(sizeof(uint16_t) * NA);
    uint16_t *buf = malloc(sizeof(uint16_t) * NA);
    SubJob   *job = malloc(sizeof(SubJob) * (NA + 1));
    if (!c1 || !buf || !job) { fprintf(stderr, "out of memory in solve_triple_bounded\n"); exit(1); }

    int n1k = 0;
    for (int a = 0; a < NA; a++) if (c1[r1[a]]++ == 0) k1[n1k++] = r1[a];
    int acc = 0;
    for (int i = 0; i < n1k; i++) { s1[i] = acc; f1[i] = acc; acc += c1[k1[i]]; o1[k1[i]] = i; }
    for (int a = 0; a < NA; a++) ord[f1[o1[r1[a]]]++] = (uint16_t)a;

    int total = NA;                       /* guess 1, everyone */
    int njob = 0, bufn = 0, midn = 0, rc;

    for (int i = 0; i < n1k; i++) {
        int p1 = k1[i], st = s1[i], n1 = c1[p1];
        if (p1 == ALL_GREEN) continue;                       /* won at guess 1 */
        if (PAIR_ADAPT > 0 && n1 <= PAIR_ADAPT) {            /* drop g2 and g3 */
            memcpy(buf + bufn, ord + st, sizeof(uint16_t) * n1);
            job[njob].start = bufn; job[njob].len = n1; job[njob].d = depth - 1;
            njob++; bufn += n1;
            continue;
        }
        total += n1;                                         /* guess 2 here */

        /* split this g1-bucket by g2, into mid[] */
        int n2k = 0;
        for (int t = st; t < st + n1; t++)
            if (c2[r2[ord[t]]]++ == 0) k2[n2k++] = r2[ord[t]];
        int off = midn;
        for (int j = 0; j < n2k; j++) { o2[k2[j]] = j; f2[j] = off; off += c2[k2[j]]; }
        for (int t = st; t < st + n1; t++) mid[f2[o2[r2[ord[t]]]]++] = ord[t];

        int base = midn;
        for (int j = 0; j < n2k; j++) {
            int p2 = k2[j], n2 = c2[p2], mst = base;
            base += n2;
            c2[p2] = 0;
            if (p2 == ALL_GREEN) continue;                   /* won at guess 2 */
            if (PAIR_ADAPT > 0 && n2 <= PAIR_ADAPT) {        /* drop g3 */
                memcpy(buf + bufn, mid + mst, sizeof(uint16_t) * n2);
                job[njob].start = bufn; job[njob].len = n2; job[njob].d = depth - 2;
                njob++; bufn += n2;
                continue;
            }
            total += n2;                                     /* guess 3 here */

            int n3k = 0;
            for (int t = mst; t < mst + n2; t++)
                if (c3[r3[mid[t]]]++ == 0) k3[n3k++] = r3[mid[t]];
            int off3 = bufn;
            for (int j3 = 0; j3 < n3k; j3++) { o3[k3[j3]] = j3; f3[j3] = off3; off3 += c3[k3[j3]]; }
            for (int t = mst; t < mst + n2; t++) buf[f3[o3[r3[mid[t]]]]++] = mid[t];

            int b3 = bufn;
            for (int j3 = 0; j3 < n3k; j3++) {
                int n3 = c3[k3[j3]];
                if (k3[j3] != ALL_GREEN) {                   /* else won at guess 3 */
                    job[njob].start = b3; job[njob].len = n3; job[njob].d = depth - 3;
                    njob++;
                }
                b3 += n3;
                c3[k3[j3]] = 0;
            }
            bufn = off3;
        }
        midn = off;
    }

    qsort(job, njob, sizeof(SubJob), cmp_subjob);

    int lbrest = 0;
    for (int i = 0; i < njob; i++) {
        int v = LBTAB[job[i].d][job[i].len];
        if (v >= INF) { rc = INF; goto done; }
        lbrest += v;
    }
    if (total + lbrest > bound) { rc = CUTOFF; goto done; }
    for (int i = 0; i < njob; i++) {
        lbrest -= LBTAB[job[i].d][job[i].len];
        int v = solve(buf + job[i].start, job[i].len, job[i].d, &CONS_NONE, ctx);
        if (v >= INF) { rc = INF; goto done; }
        total += v;
        if (total + lbrest > bound) { rc = CUTOFF; goto done; }
    }
    rc = total;

done:
    free(c1); free(k1); free(o1); free(s1); free(f1);
    free(c2); free(k2); free(o2); free(f2);
    free(c3); free(k3); free(o3); free(f3);
    free(ord); free(mid); free(buf); free(job);
    return rc;
}

static int write_tree(const char *dir, int g, int depth, Ctx *ctx) {
    char cmd[1200];
    snprintf(cmd, sizeof cmd, "gzip -1 > '%s/%s.txt.gz'", dir, GWORD[g]);
    int rc = 0;

    /* popen/pclose fork a gzip child. When many openers finish in quick
     * succession -- e.g. the Lingo per-letter sweeps, where each opener solves
     * in milliseconds -- concurrent popen() calls across OpenMP threads leak one
     * thread's still-open pipe fd into another thread's forked child, so that
     * gzip never sees EOF and pclose() hangs forever in wait4(): a deadlock that
     * looks like a random crash/stall late in a sweep. The normal 12972 sweep
     * almost never hits it only because its openers take minutes, so two popens
     * rarely overlap. Serialise the whole popen..pclose so at most one gzip pipe
     * is ever open. Tree emission is pure I/O (every value is already memoised),
     * so this costs nothing measurable even on the 20-thread sweep, and the
     * emitted trees are byte-identical. */
#pragma omp critical(treewrite)
    {
        FILE *out = popen(cmd, "w");
        if (!out) {
            rc = -1;
        } else {
            int *sc = pat_scratch(3);
            int *cnt = PSLOT(sc, 0), *start = PSLOT(sc, 1), *fill = PSLOT(sc, 2);
            uint16_t *buf = ctx->tbuf[depth];
            const pat_t *row = PAT + (size_t)g * NA;
            for (int a = 0; a < NA; a++) cnt[row[a]]++;
            int acc = 0;
            for (int p = 0; p < NPAT; p++) { start[p] = acc; acc += cnt[p]; }
            start[NPAT] = acc;
            memcpy(fill, start, (size_t)NPAT * sizeof(int));
            for (int a = 0; a < NA; a++) buf[fill[row[a]]++] = (uint16_t)a;

            char path[4096];
            if (cnt[ALL_GREEN] > 0) fprintf(out, "%s 1 %s\n", GWORD[g], GWORD[g]);
            for (int p = 0; p < NPAT && rc == 0; p++) {
                if (p == ALL_GREEN || cnt[p] == 0) continue;
                char ps[PATSTR_BUF];
                pat_str(p, ps);
                int plen = snprintf(path, sizeof path, "%s %s ", GWORD[g], ps);
                Cons kid;
                if (USE_CONS) cons_apply(&kid, &CONS_NONE, g, p);
                rc = emit_tree(out, buf + start[p], cnt[p], depth - 1, path, plen, 1,
                               USE_CONS ? &kid : &CONS_NONE, ctx);
            }
            pclose(out);
            free(sc);
        }
    }
    return rc;
}

static int find_word(char (*list)[WBUF], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* ======================================================= --kth-random =======
 *
 * THE QUESTION.  What does ONE random guess cost, played at turn K of an
 * otherwise perfect game?  Guesses 1..K-1 follow the committed OPTIMAL TREE in
 * `--tree-file`; guess K is a word drawn UNIFORMLY FROM ALL NG LEGAL WORDS,
 * consistent with the replies or not; and from turn K+1 the search plays
 * optimally again.
 *
 * IT IS EXACT, NOT SAMPLED.  Every (answer, random word) pair is enumerated --
 * NA x NG of them -- so the result is an INTEGER total over that grid and the
 * mean is that total over the grid size, exactly as every other total here is
 * an integer over 2315.  There is no seed and no standard error, and a re-run
 * reproduces the file byte for byte.
 *
 * THE CAP IS PART OF THE OBJECTIVE AND IT IS COUNTED FROM THE START OF THE
 * GAME.  The continuation must resolve every remaining candidate within
 * `--depth - K` further guesses, so the whole game fits in `--depth`.  A random
 * guess spends a turn without necessarily buying anything, so INFEASIBLE IS AN
 * EXPECTED RESULT here in a way it is not for the plain sweep -- and an
 * infeasible bucket has NO OPTIMUM AT ALL, not merely a large one.  Those pairs
 * are therefore COUNTED, EXCLUDED from the mean, and reported; the run also
 * prints the sound LOWER BOUND that charges each of them `--depth + 1`, which
 * is the least a game that cannot finish inside the cap can cost.  Read `mean`
 * as "optimal expected guesses CONDITIONAL on the game being winnable within
 * --depth"; when `infeasible_pairs` is 0 the two coincide and it is simply the
 * expected guesses.
 *
 * WHAT THE ANSWER DEPENDS ON, stated because it is not obvious.  At K = 2 the
 * level-1 states are the OPENER's own partition, so nothing but the opener
 * matters.  At K >= 3 they are the nodes of ONE optimal tree, and an optimal
 * tree is NOT UNIQUE -- ties fall to whichever minimiser the emitting run
 * happened to keep.  So the quantity is "under the optimal strategy THIS TREE
 * FILE records", which is why the tree is an explicit input read from the
 * committed artifact rather than re-derived here: a fresh best_move() walk
 * consults the transposition table and can legitimately return a different,
 * equally optimal guess, which would make the number depend on search history.
 *
 * K = 1 REFUSES A TREE FILE.  With no prefix to play there is no opener, and
 * the answer is a property of the word lists alone -- it is the mean over all
 * NG openers of that opener's own optimal total, i.e. the whole `--sweep` CSV
 * averaged.  Accepting a tree there would file an opener-independent number
 * under an opener's name.  (It is also the free whole-program gate: k=1 must
 * reproduce the committed opener_totals.csv exactly.)
 */

/* ---- word -> index, so a tree file can be read without an O(n) scan per token */
typedef struct { int *slot; size_t mask; char (*list)[WBUF]; } WIndex;

static uint64_t w_fnv(const char *s) {
    uint64_t h = 1469598103934665603ULL;
    while (*s) { h ^= (unsigned char)*s++; h *= 1099511628211ULL; }
    return h;
}

static void windex_build(WIndex *ix, char (*list)[WBUF], int n) {
    size_t m = 1;
    while (m < (size_t)n * 2) m <<= 1;
    ix->slot = malloc(sizeof(int) * m);
    if (!ix->slot) { fprintf(stderr, "out of memory: word index\n"); exit(1); }
    ix->mask = m - 1;
    ix->list = list;
    for (size_t i = 0; i < m; i++) ix->slot[i] = -1;
    for (int i = 0; i < n; i++) {
        size_t j = w_fnv(list[i]) & ix->mask;
        while (ix->slot[j] >= 0) j = (j + 1) & ix->mask;
        ix->slot[j] = i;
    }
}

static int windex_find(const WIndex *ix, const char *w) {
    size_t j = w_fnv(w) & ix->mask;
    while (ix->slot[j] >= 0) {
        if (!strcmp(ix->list[ix->slot[j]], w)) return ix->slot[j];
        j = (j + 1) & ix->mask;
    }
    return -1;
}

/* Inverse of pat_str: "bygbb" -> its base-3 code, position 0 the MOST
 * significant trit.  Returns -1 for anything that is not exactly WORDLEN
 * characters of b/y/g, so a malformed tree line is REFUSED rather than folded
 * into bucket 0 -- which would silently merge two different states.
 *
 * NOTE the `!s[i]` test comes FIRST: strchr("byg", 0) finds the terminator and
 * returns a NON-null pointer, so a short string would otherwise read as a run
 * of `b`s. */
static int pat_code(const char *s) {
    int code = 0;
    for (int i = 0; i < WORDLEN; i++) {
        const char *p;
        if (!s[i] || !(p = strchr("byg", s[i]))) return -1;
        code = code * 3 + (int)(p - "byg");
    }
    return s[WORDLEN] ? -1 : code;
}

/* One answer's line of the tree, cut down to the prefix --kth-random needs. */
typedef struct {
    int a;                 /* answer index */
    int n;                 /* guesses this answer's line spends */
    int g[MAXD];           /* guess index played at each of the first KPRE plies */
    int p[MAXD];           /* the pattern code each of those drew */
} TreeLine;

/* One node of the tree at ply K-1: the candidates still alive when the random
 * guess is played. */
typedef struct { uint16_t *S; int n; } KState;

/* Read `file` (gzipped or not) into one TreeLine per answer, keeping the first
 * `kpre` (guess, pattern) pairs of each.
 *
 * The gzip route mirrors write_tree's own `popen("gzip -1 > ...")` rather than
 * linking zlib for one reader. */
static int read_tree_lines(const char *file, int kpre, TreeLine *out,
                           const WIndex *gix, const WIndex *aix) {
    size_t len = strlen(file);
    int gz = len > 3 && !strcmp(file + len - 3, ".gz");
    FILE *f;
    if (gz) {
        char cmd[4200];
        snprintf(cmd, sizeof cmd, "gzip -dc '%s'", file);
        f = popen(cmd, "r");
    } else {
        f = fopen(file, "r");
    }
    if (!f) { fprintf(stderr, "cannot read tree file %s\n", file); return -1; }

    char *seen = calloc((size_t)NA, 1);
    char line[8192];
    int nl = 0, rc = 0;
    while (rc == 0 && fgets(line, sizeof line, f)) {
        char *save = NULL;
        char *tok = strtok_r(line, " \t\r\n", &save);
        if (!tok) continue;
        int a = windex_find(aix, tok);
        if (a < 0) {
            fprintf(stderr, "tree line names %s, which is not an answer word\n", tok);
            rc = -1; break;
        }
        if (seen[a]) { fprintf(stderr, "tree file lists %s twice\n", tok); rc = -1; break; }
        seen[a] = 1;
        tok = strtok_r(NULL, " \t\r\n", &save);
        int n = tok ? atoi(tok) : 0;
        if (n < 1 || n > MAXD - 1) {
            fprintf(stderr, "tree line for %s claims %d guesses\n", AWORD[a], n);
            rc = -1; break;
        }
        TreeLine *t = &out[nl++];
        t->a = a; t->n = n;
        /* the line is g1 p1 g2 p2 ... gN: N guesses and N-1 patterns */
        for (int ply = 0; ply < n; ply++) {
            char *gw = strtok_r(NULL, " \t\r\n", &save);
            char *ps = NULL;
            if (!gw) { fprintf(stderr, "tree line for %s ends early\n", AWORD[a]); rc = -1; break; }
            if (ply < n - 1) {
                ps = strtok_r(NULL, " \t\r\n", &save);
                if (!ps) { fprintf(stderr, "tree line for %s ends early\n", AWORD[a]); rc = -1; break; }
            }
            if (ply >= kpre) continue;          /* past the prefix we need */
            /* The LAST guess of a line carries no pattern -- it is the answer.
             * That only happens inside the prefix for a line that finishes early
             * (n <= kpre), which is never grouped into a state, so a missing
             * pattern is recorded as -1 rather than refused.  A line still LIVE
             * at guess K has n >= K, hence a pattern at every ply below kpre. */
            int g = windex_find(gix, gw);
            int p = ps ? pat_code(ps) : -1;
            if (g < 0 || (ps && p < 0)) {
                fprintf(stderr, "tree line for %s: unreadable guess/pattern '%s %s'\n",
                        AWORD[a], gw, ps ? ps : "(none)");
                rc = -1; break;
            }
            t->g[ply] = g; t->p[ply] = p;
        }
    }
    if (gz) pclose(f); else fclose(f);
    free(seen);
    if (rc) return -1;
    if (nl != NA) {
        fprintf(stderr, "tree file covers %d answers, not %d\n", nl, NA);
        return -1;
    }
    return nl;
}

static int KPRE_CMP = 0;                        /* prefix length cmp_treeline reads */

/* Order lines by their PATTERN prefix, then by answer index so the sort is
 * total and the grouping deterministic.  Patterns alone identify the node: the
 * guess at every ply is a function of the path above it, which is what makes a
 * tree a STRATEGY -- and group_states() ASSERTS that rather than assuming it. */
static int cmp_treeline(const void *x, const void *y) {
    const TreeLine *a = x, *b = y;
    for (int i = 0; i < KPRE_CMP; i++)
        if (a->p[i] != b->p[i]) return a->p[i] < b->p[i] ? -1 : 1;
    return (a->a > b->a) - (a->a < b->a);
}

/* Turn the tree lines into the level-(kpre) states, checking as it goes.
 *
 * THREE CHECKS, ALL ALWAYS ON, because this is the one place a misread tree
 * would produce a plausible wrong number rather than an error:
 *   1. every line plays the SAME opener, and every line in a group plays the
 *      same guess at every ply -- i.e. the file is one strategy, not a
 *      per-answer fabrication;
 *   2. the group EQUALS the set of answers consistent with its prefix,
 *      recomputed by filtering all NA answers through the pattern matrix, so
 *      the state is the CANDIDATE SET and not merely the answers the file
 *      happened to list together;
 *   3. every listed member survives that filter. */
static int group_states(TreeLine *lines, int nl, int kpre, KState **out_states,
                        int *out_nstate, long long *out_early_score,
                        int *out_early_count, int *out_live, int *out_opener) {
    KPRE_CMP = kpre;
    long long early_score = 0;
    int early_count = 0, live = 0;

    int opener = lines[0].g[0];
    for (int i = 1; i < nl; i++)
        if (lines[i].g[0] != opener) {
            fprintf(stderr, "tree opens with both %s and %s -- not one strategy\n",
                    GWORD[opener], GWORD[lines[i].g[0]]);
            return -1;
        }

    TreeLine *live_lines = malloc(sizeof(TreeLine) * (size_t)nl);
    for (int i = 0; i < nl; i++) {
        if (lines[i].n <= kpre) { early_score += lines[i].n; early_count++; }
        else live_lines[live++] = lines[i];
    }
    qsort(live_lines, (size_t)live, sizeof(TreeLine), cmp_treeline);

    int cap = 64, ns = 0;
    KState *st = malloc(sizeof(KState) * (size_t)cap);
    char *mark = malloc((size_t)NA);
    size_t plen = sizeof(int) * (size_t)kpre;
    int i = 0;
    while (i < live) {
        int j = i + 1;
        while (j < live && memcmp(live_lines[i].p, live_lines[j].p, plen) == 0) j++;

        for (int t = i + 1; t < j; t++)
            for (int ply = 0; ply < kpre; ply++)
                if (live_lines[t].g[ply] != live_lines[i].g[ply]) {
                    fprintf(stderr, "tree is not a strategy: two answers share the "
                            "pattern prefix but play %s and %s at ply %d\n",
                            GWORD[live_lines[i].g[ply]], GWORD[live_lines[t].g[ply]], ply + 1);
                    return -1;
                }

        memset(mark, 0, (size_t)NA);
        int nfilt = 0;
        for (int a = 0; a < NA; a++) {
            int ok = 1;
            for (int ply = 0; ply < kpre && ok; ply++)
                if (PAT[(size_t)live_lines[i].g[ply] * NA + a] != live_lines[i].p[ply]) ok = 0;
            if (ok) { mark[a] = 1; nfilt++; }
        }
        if (nfilt != j - i) {
            fprintf(stderr, "state at ply %d holds %d tree lines but %d answers are "
                    "consistent with its prefix\n", kpre, j - i, nfilt);
            return -1;
        }
        if (ns == cap) { cap *= 2; st = realloc(st, sizeof(KState) * (size_t)cap); }
        st[ns].n = j - i;
        st[ns].S = malloc(sizeof(uint16_t) * (size_t)(j - i));
        for (int t = i; t < j; t++) {
            if (!mark[live_lines[t].a]) {
                fprintf(stderr, "tree lists %s in a state its own prefix excludes\n",
                        AWORD[live_lines[t].a]);
                return -1;
            }
            st[ns].S[t - i] = (uint16_t)live_lines[t].a;
        }
        /* solve() hashes a state by XOR, so order cannot change a value -- but
         * ascending members make the emitted buckets deterministic. */
        for (int x = 1; x < st[ns].n; x++)
            for (int y = x; y > 0 && st[ns].S[y] < st[ns].S[y - 1]; y--) {
                uint16_t tmp = st[ns].S[y];
                st[ns].S[y] = st[ns].S[y - 1];
                st[ns].S[y - 1] = tmp;
            }
        ns++;
        i = j;
    }
    free(live_lines);
    free(mark);
    *out_states = st; *out_nstate = ns;
    *out_early_score = early_score; *out_early_count = early_count;
    *out_live = live; *out_opener = opener;
    return 0;
}

/* THE POOL THE RANDOM GUESS COMES FROM IS PART OF THE OBJECTIVE, so it has no
 * default and lands in every filename.  Two very different experiments:
 *
 *   all         uniform over ALL NG legal words, consistent with the replies or
 *               not.  At k=1 that makes the answer the mean over every possible
 *               starting word -- the whole --sweep CSV averaged.
 *   compatible  uniform over the words still CONSISTENT with every reply, which
 *               is the candidate set itself.  At k=1 that is the 2315 answers,
 *               so the answer is the sweep averaged over just the answer words.
 *
 * THE SECOND POOL MAKES THE OBJECTIVE RATIONAL RATHER THAN INTEGER, and that is
 * not a presentational detail.  Under `all` every answer draws from the same NG
 * words, so the experiment is a rectangle and the total is an integer over
 * NA x NG.  Under `compatible` each answer draws from ITS OWN state, and states
 * have different sizes -- so answer a carries weight 1/|S_a| and the mean is a
 * sum of fractions whose denominators are the state sizes.  There is no small
 * common denominator (the sizes run to 221), so the summary reports the value in
 * long double and the per-state file `--kth-states` holds the INTEGERS it was
 * summed from; tools/checkkthrandom.py rebuilds the exact Fraction from those
 * and requires the two to agree.  The integer grid columns of the summary are
 * written only under `all`, where they mean something, and left BLANK under
 * `compatible` rather than filled with a number of a different kind. */
#define POOL_ALL 0
#define POOL_COMPATIBLE 1

/* Per-thread partition scratch.  Pattern-indexed and kept ZERO between uses --
 * the same invariant Ctx->cnt keeps -- so only the patterns actually seen are
 * ever touched and a 6-candidate state does not pay a memset of NPAT. */
typedef struct { int *cnt, *start, *fill, *seen; uint16_t *buf; } KScratch;

static int kth_random(const char *treefile, int K, int depth, const char *outpath,
                      int pool, const char *statepath) {
    int kpre = K - 1;
    int dres = depth - K;                       /* guesses left AFTER the random one */
    const char *poolname = pool == POOL_ALL ? "all" : "compatible";

    KState *states = NULL;
    int nstate = 0, early_count = 0, live = 0, opener = -1;
    long long early_score = 0;

    if (kpre == 0) {
        states = malloc(sizeof(KState));
        states[0].n = NA;
        states[0].S = malloc(sizeof(uint16_t) * (size_t)NA);
        for (int a = 0; a < NA; a++) states[0].S[a] = (uint16_t)a;
        nstate = 1; live = NA;
    } else {
        WIndex gix, aix;
        windex_build(&gix, GWORD, NG);
        windex_build(&aix, AWORD, NA);
        TreeLine *lines = malloc(sizeof(TreeLine) * (size_t)NA);
        if (!lines) { fprintf(stderr, "out of memory: tree lines\n"); return 1; }
        if (read_tree_lines(treefile, kpre, lines, &gix, &aix) < 0) return 1;
        if (group_states(lines, NA, kpre, &states, &nstate, &early_score,
                         &early_count, &live, &opener) < 0) return 1;
        free(lines); free(gix.slot); free(aix.slot);
    }

    int maxn = 0;
    for (int s = 0; s < nstate; s++) if (states[s].n > maxn) maxn = states[s].n;
    fprintf(stderr, "kth-random: opener %s  k=%d  depth=%d  pool=%s\n",
            opener >= 0 ? GWORD[opener] : "(none -- k=1 has no prefix)", K, depth,
            poolname);
    fprintf(stderr, "kth-random: %d states at ply %d; %d answers still live "
            "(largest state %d), %d finished earlier\n",
            nstate, kpre, live, maxn, early_count);
    fprintf(stderr, "kth-random: %d further guesses allowed after the random one\n", dres);
    fflush(stderr);

    FILE *sf = NULL;
    if (statepath) {
        sf = fopen(statepath, "w");
        if (!sf) { fprintf(stderr, "cannot write %s\n", statepath); return 1; }
        /* THE EXACT RECORD.  n = candidates in the state, m = words the random
         * guess is drawn from, u = summed optimal continuation over the feasible
         * non-winning buckets, infeasible = (answer, word) pairs the cap rules
         * out.  Every column an integer, so the rational mean above can be
         * rebuilt exactly from this file however it was printed. */
        fprintf(sf, "state,n,m,u,infeasible\n");
    }

    int nth = 1;
#ifdef _OPENMP
    nth = omp_get_max_threads();
#endif
    Ctx **ctxs = calloc((size_t)nth, sizeof(Ctx *));
    KScratch *scr = calloc((size_t)nth, sizeof(KScratch));
    for (int t = 0; t < nth; t++) {
        ctxs[t] = calloc(1, sizeof(Ctx));
        scr[t].cnt   = calloc((size_t)NPAT + 1, sizeof(int));
        scr[t].start = calloc((size_t)NPAT + 1, sizeof(int));
        scr[t].fill  = calloc((size_t)NPAT + 1, sizeof(int));
        scr[t].seen  = calloc((size_t)NPAT + 1, sizeof(int));
        scr[t].buf   = malloc(sizeof(uint16_t) * (size_t)MAXA);
        if (!ctxs[t] || !scr[t].buf) { fprintf(stderr, "out of memory: thread state\n"); return 1; }
    }

    /* The ANSWER-weighted accounting, which both pools share.  Each answer
     * carries weight 1 and spreads it evenly over the m words its own pool
     * offers, so a state contributes with denominator m -- and under `all`,
     * where every m is NG, that collapses to the plain integer grid below. */
    long double wnum = (long double)early_score;   /* summed score, feasible only */
    long double wden = (long double)early_count;   /* summed weight, feasible only */
    long double winf = 0.0L;                       /* summed weight, infeasible */
    long long feas_extra = 0, infeas_pairs = 0;    /* exact, meaningful under `all` */
    double t0 = now_s();
    long long done = 0, work = 0;
    for (int s = 0; s < nstate; s++)
        work += (long long)states[s].n * (pool == POOL_ALL ? NG : states[s].n);
    int step = nstate > 200 ? nstate / 100 : 1;

    for (int s = 0; s < nstate; s++) {
        const uint16_t *S = states[s].S;
        int n = states[s].n;
        int m = (pool == POOL_ALL) ? NG : n;
        long long fe = 0, ip = 0;
#ifdef _OPENMP
#pragma omp parallel for schedule(dynamic, 32) reduction(+:fe,ip)
#endif
        for (int j = 0; j < m; j++) {
            /* `all` walks the guess list; `compatible` walks the state's own
             * members, which have to cross into GUESS space first -- an answer
             * index would read the wrong row of PAT and score a different game. */
            int r = (pool == POOL_ALL) ? j : ANS2G[S[j]];
            int tid = 0;
#ifdef _OPENMP
            tid = omp_get_thread_num();
#endif
            Ctx *ctx = ctxs[tid];
            KScratch *k = &scr[tid];
            const pat_t *row = PAT + (size_t)r * NA;
            int nseen = 0;
            for (int i = 0; i < n; i++) {
                int p = row[S[i]];
                if (k->cnt[p]++ == 0) k->seen[nseen++] = p;
            }
            int acc = 0;
            for (int t = 0; t < nseen; t++) {
                int p = k->seen[t];
                k->start[p] = acc; k->fill[p] = acc; acc += k->cnt[p];
            }
            for (int i = 0; i < n; i++) k->buf[k->fill[row[S[i]]]++] = S[i];
            for (int t = 0; t < nseen; t++) {
                int p = k->seen[t];
                int mm = k->cnt[p];
                k->cnt[p] = 0;                  /* restore the zero invariant */
                if (p == ALL_GREEN) continue;   /* the random word WAS the answer */
                /* dres == 0 leaves no guess to name anything, so every bucket
                 * not already won is infeasible.  solve() would answer 1 for a
                 * singleton at any depth, which is exactly wrong here. */
                int v = (dres <= 0) ? INF
                                    : solve(k->buf + k->start[p], mm, dres, &CONS_NONE, ctx);
                if (v >= INF) ip += mm; else fe += v;
            }
        }
        feas_extra += fe;
        infeas_pairs += ip;
        long long pairs = (long long)n * m;
        wnum += (long double)((long long)K * (pairs - ip) + fe) / (long double)m;
        wden += (long double)(pairs - ip) / (long double)m;
        winf += (long double)ip / (long double)m;
        if (sf) fprintf(sf, "%d,%d,%d,%lld,%lld\n", s, n, m, fe, ip);
        done += pairs;

        if (s % step == 0 || s == nstate - 1) {
            double el = now_s() - t0;
            fprintf(stderr, "[%7.1fs] state %d/%d  n=%-4d  %5.1f%% of the answer-work  "
                    "eta %5.1f min\n", el, s + 1, nstate, n,
                    100.0 * done / (work ? work : 1),
                    done ? el / done * (work - done) / 60.0 : 0.0);
            fflush(stderr);
        }
    }
    if (sf) fclose(sf);

    long long g_nodes = 0;
    for (int t = 0; t < nth; t++) {
        g_probe += ctxs[t]->probe; g_hit += ctxs[t]->hit; g_fill += ctxs[t]->fill;
        g_nodes += ctxs[t]->nodes;
    }

    /* --- the accounting, stated in full -------------------------------------
     * A pair (answer a, random word r) scores:
     *   a finished inside K-1 guesses  -> its own line length (r is never played)
     *   r IS a's word                  -> K
     *   otherwise                      -> K + a's depth in the optimal tree of
     *                                     its bucket under the cap `dres`
     * and summing that last term over a whole bucket is exactly solve()'s value
     * for it.  So every live pair pays K, and the feasible ones add their
     * bucket's total; the all-green bucket adds nothing, the game being over.
     *
     * A pair the cap rules out has NO optimum, so it leaves the mean entirely --
     * but it cannot cost less than depth+1 either, which is what makes lb_mean a
     * SOUND LOWER BOUND on the unconditional mean rather than a guess at one. */
    double mean = wden > 0 ? (double)(wnum / wden) : 0.0;
    double lb_mean = (double)((wnum + (long double)(depth + 1) * winf) / (long double)NA);
    double pct_inf = (double)(100.0L * winf / (long double)NA);
    long long won_at_k = live;                  /* one r per live answer: its own word */

    /* Under `all` the same quantities are exact integers over the NA x NG grid.
     * Computing them BOTH ways and requiring they agree makes the rectangular
     * case a standing check on the rational one, for free. */
    long long total_pairs = (long long)NA * NG;
    long long live_pairs  = (long long)live * NG;
    long long feas_pairs  = total_pairs - infeas_pairs;
    long long feas_total  = early_score * NG
                          + (long long)K * (live_pairs - infeas_pairs) + feas_extra;
    long long lb_total    = feas_total + (long long)(depth + 1) * infeas_pairs;
    if (pool == POOL_ALL) {
        double exact = (double)feas_total / (double)feas_pairs;
        if (fabs(exact - mean) > 1e-9) {
            fprintf(stderr, "kth-random: the weighted mean %.12f disagrees with the "
                    "exact integer mean %.12f -- the two accountings have parted "
                    "company\n", mean, exact);
            return 1;
        }
        mean = exact;
        lb_mean = (double)lb_total / (double)total_pairs;
        pct_inf = 100.0 * infeas_pairs / total_pairs;
    }

    printf("k=%d  depth=%d  pool=%s  opener=%s\n", K, depth, poolname,
           opener >= 0 ? GWORD[opener] : "-");
    if (pool == POOL_ALL)
        printf("      total=%lld  mean=%.6f  over %lld feasible pairs of %lld\n",
               feas_total, mean, feas_pairs, total_pairs);
    else
        printf("      mean=%.6f  over %.4Lf of the 2315 answers' weight\n", mean, wden);
    if (winf > 0)
        printf("      INFEASIBLE within %d: %.4f%% of the weight -- so the "
               "unconditional mean is >= %.6f\n", depth, pct_inf, lb_mean);
    else
        printf("      no infeasible pair, so the mean is unconditional\n");
    printf("      won at guess %d: %lld answers;  finished before it: %d answers\n",
           K, won_at_k, early_count);
    printf("      (%.1fs, %lld nodes, TT %.2f%% hit)\n", now_s() - t0, g_nodes,
           100.0 * g_hit / (g_probe ? g_probe : 1));
    fflush(stdout);

    if (outpath) {
        int fresh = 1;
        FILE *rf = fopen(outpath, "r");
        if (rf) { fresh = fgetc(rf) == EOF; fclose(rf); }
        FILE *out = fopen(outpath, "a");
        if (!out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (fresh)
            fprintf(out, "opener,k,depth,pool,pct_infeasible,mean,lb_mean,won_at_k,"
                         "early_answers,states,pairs,feasible_pairs,infeasible_pairs,"
                         "total,lb_total,seconds\n");
        fprintf(out, "%s,%d,%d,%s,%.6f,%.6f,%.6f,%lld,%d,%d,",
                opener >= 0 ? GWORD[opener] : "-", K, depth, poolname,
                pct_inf, mean, lb_mean, won_at_k, early_count, nstate);
        /* The integer grid columns mean something only on the rectangle, so
         * under `compatible` they are left BLANK rather than filled with a
         * number of a different kind -- the same convention an INFEASIBLE sweep
         * row uses. tools/checkkthrandom.py rebuilds the exact value from the
         * per-state file instead. */
        if (pool == POOL_ALL)
            fprintf(out, "%lld,%lld,%lld,%lld,%lld,", total_pairs, feas_pairs,
                    infeas_pairs, feas_total, lb_total);
        else
            fprintf(out, ",,,,,");
        fprintf(out, "%.1f\n", now_s() - t0);
        fclose(out);
    }
    return 0;
}

/* Has this (k, depth, pool) already been written?  One invocation computes ONE
 * cell, so a run whose row is already on file has nothing to do -- and
 * recomputing it would append a duplicate rather than resume. */
static int kth_already_done(const char *outpath, int K, int depth, const char *poolname) {
    FILE *f = fopen(outpath, "r");
    if (!f) return 0;
    char line[512];
    int found = 0;
    while (fgets(line, sizeof line, f)) {
        char w[64], p[32];
        int k, d;
        if (sscanf(line, "%63[^,],%d,%d,%31[^,],", w, &k, &d, p) == 4
            && k == K && d == depth && !strcmp(p, poolname)) { found = 1; break; }
    }
    fclose(f);
    return found;
}

/* Emit one index of the difficulty-sorted list into the dispatch order, unless
 * it has already been emitted. Out-of-range indices clamp: rounding at deep
 * levels can land on NG. */
static void bisect_emit(int64_t *out, int *m, unsigned char *seen,
                        const int64_t *sorted, long long idx) {
    if (idx < 0) idx = 0;
    if (idx >= NG) idx = NG - 1;
    if (seen[idx]) return;
    seen[idx] = 1;
    out[(*m)++] = sorted[idx];
}

/* Sweep order: the difficulty-sorted opener list, dispatched straight down by
 * DEFAULT, or BISECTED when a caller asks for it (`--order bisect`).
 *
 * The list is sorted by fewest expected survivors (sum of squared pattern-class
 * sizes, ties by guess index) either way; the option changes only the order that
 * sorted list is DISPATCHED in -- ends first, then the median, then the
 * quartiles, then the odd eighths, and so on.
 *
 * WHY ANYONE WOULD WANT IT. Straight best-first order makes every partial result biased: the solved
 * subset is always the easy end, so percentiles over it are meaningless, the
 * histogram's hard tail stays empty until the run is nearly over, and the worst
 * list churns constantly because the bad openers all arrive last. Bisection
 * makes the solved set a STRATIFIED SAMPLE of the whole difficulty range at
 * every moment -- lower variance than a random shuffle for the same purpose,
 * and deterministic, so a restart reproduces the order with no seed to carry.
 *
 * WHAT IT COSTS. Best-first front-loaded cheap openers, so completions came
 * fast early and the TT warmed on shared deep states first. Bisection mixes
 * pathological openers in from the start, so early throughput is much lower and
 * the second word dispatched is the worst-partitioned opener in the list. The
 * TT half of that argument is weaker than it looks: hits are dominated by
 * INTRA-word reuse, and a table at 0.01%% occupancy still returned 67%% hits.
 *
 * Already-solved openers keep their slot in the ORDER (the bisection is over
 * the whole list, so the sequence does not shift as the CSV fills) but are
 * skipped at dispatch by the done[] test in the sweep loop -- counted, not
 * redone.
 *
 * Levels run to 2^20 > 2*NG, by which point consecutive rounded indices differ
 * by less than 1 and every index has been emitted; the trailing loop is a
 * belt-and-braces fill in case that ever stops holding. */
/* `bisect`: dispatch order for the difficulty-sorted opener list.
 *   1 -- BISECTION (ends, median, quartiles ...), OPT-IN via `--order bisect`
 *        and today asked for by the hard-mode sweep alone: a stopped run then
 *        holds a stratified sample of the whole difficulty range rather than a
 *        prefix of the easy end (see the block comment above).  Only worth its
 *        cost while somebody is READING that partial distribution as the run
 *        goes.  Refused alongside --topk.
 *   0 -- straight ASCENDING sum of squares (best splitters first).  THIS IS THE
 *        DEFAULT for every caller; the bisection is requested with --order
 *        bisect and nowhere assumes it.  It is what --topk needs (it examines
 *        only the first K and therefore wants the K BEST, not the bisection's
 *        {easiest, HARDEST, ...}), and it is what any run that will be judged on
 *        its incumbent needs, since it finds a good bound first.
 *
 * A CALLER MUST PASS ITS OWN CHOICE THROUGH -- do NOT hardcode 1 here again.
 * Bisection was added for the hard-mode sweep and then wired into both call
 * sites unconditionally, so every other sweep silently got a dispatch order
 * chosen for somebody else's reporting problem while three wrapper headers went
 * on describing ascending order.  One caller's need is one caller's flag.
 */
static int64_t *sweep_order(int bisect) {
    int64_t *ord = malloc(sizeof(int64_t) * NG);
    for (int g = 0; g < NG; g++) {
        const pat_t *row = PAT + (size_t)g * NA;
        int *cnt = pat_scratch(1);
        int64_t ss = 0;
#if WGT
        /* Weighted split quality: sum over LOSING bins of bin size x bin weight
         * -- the expected number of candidate WORDS still alive, which is
         * topk.py's ranking rule and therefore the one the guesser this is
         * measured against uses.  The WIN is excluded so an opener that could BE
         * the answer is not penalised for it.  (Unweighted, below, is the sum of
         * squared bin sizes including the win, unchanged.) */
        long long *ws = calloc((size_t)NPAT + 1, sizeof(long long));
        if (!ws) { fprintf(stderr, "sweep_order: out of memory\n"); exit(1); }
        for (int a = 0; a < NA; a++) { cnt[row[a]]++; ws[row[a]] += WEIGHT[a]; }
        for (int p = 0; p < NPAT; p++)
            if (p != ALL_GREEN) ss += (int64_t)cnt[p] * ws[p];
        free(ws);
#else
        for (int a = 0; a < NA; a++) cnt[row[a]]++;
        for (int p = 0; p < NPAT; p++) ss += (int64_t)cnt[p] * cnt[p];
#endif
        free(cnt);
        ord[g] = (ss << 20) | (int64_t)g;
    }
    qsort(ord, NG, sizeof(int64_t), cmp_i64);
    if (!bisect) return ord;                       /* ascending ss: best first */

    int64_t *out = malloc(sizeof(int64_t) * NG);
    unsigned char *seen = calloc((size_t)NG, 1);
    if (!out || !seen) { fprintf(stderr, "sweep_order: out of memory\n"); exit(1); }
    int m = 0;

    bisect_emit(out, &m, seen, ord, 0);           /* easiest */
    bisect_emit(out, &m, seen, ord, NG - 1);      /* hardest */
    for (int k = 1; k <= 20 && m < NG; k++) {
        long long den = 1LL << k;
        for (long long i = 0; i < den / 2 && m < NG; i++) {
            long long num = 2 * i + 1;            /* the ODD 2^-k fractions */
            bisect_emit(out, &m, seen, ord,
                        ((long long)NG * num + den / 2) / den);
        }
    }
    for (int i = 0; i < NG && m < NG; i++) bisect_emit(out, &m, seen, ord, i);

    free(seen);
    free(ord);
    return out;
}

int main(int argc, char **argv) {
    const char *datadir = "data";
    const char *openers[64];
    int nopen = 0;
    int kthk = 0;                       /* --kth-random K: 0 means the mode is off */
    const char *treefile = NULL;        /* the committed optimal tree it plays first */
    const char *poolname = NULL;        /* --random-pool: where the random guess comes from */
    const char *kthstates = NULL;       /* --kth-states: the per-state integers, exactly */
    const char *outpath = NULL, *treedir = NULL;
    const char *ttload = NULL, *ttsave = NULL, *guesslist = NULL;
    const char *answerlist = NULL, *patpath = NULL;
    int optonly = 0, uselength = 0;
    const char *pairlist = NULL, *triplelist = NULL;
    const char *weightsfile = NULL;
    int depth = 6, ttbits = 28, threads = 0, sweep = 0, depthmax = -1;
    int depth_set = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--opener") && i + 1 < argc) {
            if (nopen < 64) openers[nopen++] = argv[++i]; else i++;
        }
        else if (!strcmp(argv[i], "--sweep")) sweep = 1;
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--trees") && i + 1 < argc) treedir = argv[++i];
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) { depth = atoi(argv[++i]); depth_set = 1; }
        else if (!strcmp(argv[i], "--depth-max") && i + 1 < argc) depthmax = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-bits") && i + 1 < argc) ttbits = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tt-load") && i + 1 < argc) ttload = argv[++i];
        else if (!strcmp(argv[i], "--tt-save") && i + 1 < argc) ttsave = argv[++i];
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--guess-list") && i + 1 < argc) guesslist = argv[++i];
        else if (!strcmp(argv[i], "--answer-list") && i + 1 < argc) answerlist = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        else if (!strcmp(argv[i], "--weights") && i + 1 < argc) weightsfile = argv[++i];
        else if (!strcmp(argv[i], "--pair-list") && i + 1 < argc) pairlist = argv[++i];
        else if (!strcmp(argv[i], "--triple-list") && i + 1 < argc) triplelist = argv[++i];
        else if (!strcmp(argv[i], "--pair-adaptive") && i + 1 < argc) PAIR_ADAPT = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--kth-random") && i + 1 < argc) kthk = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--tree-file") && i + 1 < argc) treefile = argv[++i];
        else if (!strcmp(argv[i], "--random-pool") && i + 1 < argc) poolname = argv[++i];
        else if (!strcmp(argv[i], "--kth-states") && i + 1 < argc) kthstates = argv[++i];
        /* kept as the N=1 alias so runs already launched with it keep working */
        else if (!strcmp(argv[i], "--pair-early-finish")) PAIR_ADAPT = 1;
        else if (!strcmp(argv[i], "--optimal-only")) optonly = 1;
        else if (!strcmp(argv[i], "--print-openers")) PRINT_OPENERS = 1;
        else if (!strcmp(argv[i], "--phantom-final")) PHANTOM = 1;
        else if (!strcmp(argv[i], "--order") && i + 1 < argc) {
            const char *o = argv[++i];
            order_set = 1;
            if (!strcmp(o, "ssq")) { ORDER_SSQ = 1; ORDER_BISECT = 0; }
            else if (!strcmp(o, "lb")) { ORDER_SSQ = 0; ORDER_BISECT = 0; }
            /* `bisect` is the ssq SORT with the bisection DISPATCH on top -- one
             * name for the pair, because bisecting the lower-bound order would
             * throw away the one thing that order is for (the first opener
             * bounding above the incumbent proves the whole tail is worse). */
            else if (!strcmp(o, "bisect")) { ORDER_SSQ = 1; ORDER_BISECT = 1; }
            else { fprintf(stderr, "--order must be lb, ssq or bisect\n"); return 1; }
        }
        /* --length L selects the hello wordl lists and the matching pattern
         * matrix for that length.  It does NOT change WORDLEN -- that is fixed
         * when the binary is compiled -- it only asserts the two agree, so
         * `optturns7 --length 6` fails loudly instead of reading a 6-letter list
         * into a 7-letter solver. */
        else if (!strcmp(argv[i], "--length") && i + 1 < argc) {
            int want = atoi(argv[++i]);
            if (want != WORDLEN) {
                fprintf(stderr, "--length %d but this binary is WORDLEN %d "
                        "-- use ./optturns%d (sh build.sh %d)\n",
                        want, WORDLEN, want, want);
                return 1;
            }
            uselength = 1;
        }
        else if ((!strcmp(argv[i], "--topk") || !strcmp(argv[i], "-k")) && i + 1 < argc)
            TOPK = atoi(argv[++i]);
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }

    /* --print-openers only has anything to add on the --optimal-only path; the
     * plain --sweep already prints every opener.  Say so rather than accepting
     * it silently, so a run that asked for more output and got none knows why. */
    if (PRINT_OPENERS && !optonly)
        fprintf(stderr, "note: --print-openers only affects --optimal-only; "
                "the plain sweep already prints every opener\n");

    /* --order lb selects a SORT that only the --optimal-only path has (it is
     * what lets a cutoff prove the whole tail is worse).  The plain sweep always
     * walks the split-score sort, so `lb` there is a silent no-op -- name it,
     * rather than let a run believe it asked for something. */
    if (sweep && !optonly && ORDER_SSQ == 0 && !ORDER_BISECT && order_set)
        fprintf(stderr, "note: --order lb has no effect on the plain --sweep "
                "(no lower-bound walk there); dispatching in split-score order\n");

    /* --topk keeps the K BEST splitters; bisection deliberately dispatches
     * {easiest, HARDEST, median, ...}.  Combining them would examine K openers
     * spread across the difficulty range and report the winner as though it were
     * the best of the K best -- a wrong claim under a right-looking flag.  This
     * exact combination shipped once, and at K=2 it examined the single WORST
     * opener in the list. */
    if (ORDER_BISECT && TOPK > 0) {
        fprintf(stderr, "--order bisect cannot be combined with --topk: bisection "
                "dispatches {easiest, hardest, median, ...} while --topk means the "
                "K BEST splitters, so the K examined would not be the top K\n");
        return 1;
    }

    /* ---------------------------------------------- --kth-random validation
     *
     * The mode plays a committed optimal tree, then one uniformly random word,
     * then optimal play again -- so every one of these refusals is about a flag
     * that would make one of those three clauses untrue while the output still
     * called itself the same quantity. */
    if (kthk > 0) {
        if (USE_CONS || MM_MODE || WGT) {
            fprintf(stderr, "--kth-random is normal-mode only: the tree it plays is a "
                    "normal-mode tree and the continuation is the plain guess count, "
                    "so hard/ultra/mastermind/weighted would each be a different game "
                    "wearing this one's name\n");
            return 1;
        }
        if (sweep || nopen || pairlist || triplelist || optonly || PHANTOM) {
            fprintf(stderr, "--kth-random is its own driver: it cannot be combined with "
                    "--sweep, --opener, --pair-list, --triple-list, --optimal-only or "
                    "--phantom-final\n");
            return 1;
        }
        if (TOPK > 0) {
            fprintf(stderr, "--kth-random cannot be combined with --topk: the whole "
                    "question is what OPTIMAL play costs after the random guess, and a "
                    "beam would report an upper bound under an exact-sounding name\n");
            return 1;
        }
        /* THE CAP IS THE OBJECTIVE HERE and it is counted from the START of the
         * game, so a depth-6 pass and a depth-7 pass are different quantities
         * and INFEASIBLE is an expected result.  Inheriting a default would make
         * that choice silently; the wrapper carries one a human reads and passes
         * it explicitly. */
        if (!depth_set) {
            fprintf(stderr, "--kth-random: --depth is required -- the cap is counted "
                    "from the start of the game and IS part of the objective, so each "
                    "depth is a different quantity.  Use solver/run-kth-random.sh.\n");
            return 1;
        }
        if (kthk > depth) {
            fprintf(stderr, "--kth-random %d exceeds --depth %d: the random guess would "
                    "be played past the cap, so no game could contain it\n", kthk, depth);
            return 1;
        }
        /* k=1 plays NO prefix, so there is no opener and the answer is a
         * property of the word lists alone.  Taking a tree there would file an
         * opener-independent number under an opener's name. */
        if (kthk == 1 && treefile) {
            fprintf(stderr, "--kth-random 1 plays no guess before the random one, so it "
                    "has no opener and --tree-file cannot affect it.  Drop the flag: the "
                    "k=1 answer is the mean of every opener's own optimal total\n");
            return 1;
        }
        /* THE POOL IS PART OF THE OBJECTIVE, so there is nothing honest to
         * default to: `all` and `compatible` are two different experiments whose
         * k=1 answers already differ (3.62590 against 3.60730).  The wrapper
         * carries a default a human reads and forwards it explicitly. */
        if (!poolname) {
            fprintf(stderr, "--kth-random needs --random-pool all|compatible: where the "
                    "random guess is drawn from IS the experiment, and the two give "
                    "different numbers.  Use solver/run-kth-random.sh.\n");
            return 1;
        }
        if (strcmp(poolname, "all") && strcmp(poolname, "compatible")) {
            fprintf(stderr, "--random-pool must be 'all' (every legal word) or "
                    "'compatible' (only words still consistent with the replies), "
                    "not '%s'\n", poolname);
            return 1;
        }
        if (kthk > 1 && !treefile) {
            fprintf(stderr, "--kth-random %d needs --tree-file: the first %d guesses ARE "
                    "the committed optimal tree, and at k>=3 an optimal tree is not "
                    "unique, so which one is an input and not a detail\n", kthk, kthk - 1);
            return 1;
        }
    }

#ifdef MASTERMIND
    /* THE CAP IS PART OF THE OBJECTIVE, AND HERE IT BINDS.  Peg feedback has 20
     * outcomes where Wordle's colouring has 238, so the branching that makes
     * `--depth 6` slack for optturns is simply not available: a depth-6 pass and
     * a depth-8 pass are different quantities, not a fast and a slow route to
     * one answer.  Inheriting optturns' default 6 would make that choice
     * silently, so mmturns refuses to run without an explicit --depth and every
     * depth gets its own CSV. */
    if (!depth_set) {
        fprintf(stderr, "mmturns: --depth is required -- the cap IS the objective "
                "under peg feedback, so each depth is a different quantity\n");
        return 1;
    }
#else
    (void)depth_set;
#endif

#if WGT
    /* --weights IS the objective here, so there is no default and no fallback:
     * a weighted binary run without weights would silently be the unweighted
     * solver wearing a different name. */
    if (!weightsfile) {
        fprintf(stderr, "wturns: --weights FILE is required -- the weights ARE the "
                "objective, so there is nothing sensible to default to.  Use "
                "solver/run-wturns-sweep.sh.\n");
        return 1;
    }
    /* THE CAP IS PART OF THE OBJECTIVE.  A weighted optimum may deliberately
     * spend a deeper line on a light answer to shorten a heavy one, so a
     * depth-6 pass and a depth-7 pass are different quantities, not a fast and
     * a slow route to one answer, and INFEASIBLE is an expected result.
     * Inheriting optturns' default 6 would make that choice silently. */
    if (!depth_set) {
        fprintf(stderr, "wturns: --depth is required -- the cap is part of the "
                "weighted objective, so each depth is a different quantity\n");
        return 1;
    }
    /* Both would need their own weighted accounting (they still charge NA per
     * guess); refusing beats reporting a wrong number under a right-looking
     * name. */
    if (PHANTOM) {
        fprintf(stderr, "wturns: --phantom-final is not supported in weighted mode\n");
        return 1;
    }
    if (pairlist || triplelist) {
        fprintf(stderr, "wturns: --pair-list / --triple-list are not supported in "
                "weighted mode (their cost accounting is still unweighted)\n");
        return 1;
    }
#else
    if (weightsfile) {
        fprintf(stderr, "--weights needs the WEIGHTED build (wturns); this binary "
                "minimises the plain guess count\n");
        return 1;
    }
#endif

    /* Ultra mode, like hard mode and Mastermind, has genuine INFEASIBLE openers
     * (the legal set is restricted to consistent guesses, so "follow SALET's
     * tree afterwards" is illegal), so the cap BINDS and is part of the
     * objective -- a depth-6 pass and a depth-7 pass are different quantities.
     * It refuses to run without an explicit --depth and every depth gets its own
     * CSV.  It does NOT escalate: the cap is pinned to --depth (see below). */
    if (ULT && !depth_set) {
        fprintf(stderr, "ultraturns: --depth is required -- in ultra hard mode the "
                "cap binds and is part of the objective (INFEASIBLE is an expected "
                "result), so each depth is a different quantity\n");
        return 1;
    }

    /* Hard mode escalates by default; normal and ULTRA mode keep ONE fixed cap.
     * (Ultra could escalate like hard, but pinning the cap keeps every opener
     * under the same constraint and matches the "cap is the objective" rule.) */
    if (depthmax < 0) depthmax = HARD ? MAXD - 1 : depth;
    if (depthmax < depth) depthmax = depth;
    if (depthmax > MAXD - 1) {
        fprintf(stderr, "--depth-max %d exceeds MAXD-1 (%d); raise MAXD and rebuild\n",
                depthmax, MAXD - 1);
        return 1;
    }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * MAXG);
    AWORD = malloc(sizeof(char[WBUF]) * MAXA);
    if (uselength) snprintf(path, sizeof path, "%s/shared/words/hello/len%d/guess.txt",
                            datadir, WORDLEN);
    else           snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    /* --answer-list replaces the ANSWER set (the thing the total is summed over).
     * Pointed at guess.txt it makes every legal guess a possible answer, which
     * needs the SQUARE pattern matrix -- hence --patterns alongside it. */
    if (answerlist)     snprintf(path, sizeof path, "%s", answerlist);
    else if (uselength) snprintf(path, sizeof path, "%s/shared/words/hello/len%d/mystery.txt",
                                 datadir, WORDLEN);
    else                snprintf(path, sizeof path, "%s/shared/words/mystery.txt", datadir);
    NA = load_words(path, AWORD);
    if (NA > MAXA) { fprintf(stderr, "answer list has %d words, MAXA is %d\n", NA, MAXA); return 1; }
    if (patpath)        snprintf(path, sizeof path, "%s", patpath);
    else if (uselength) snprintf(path, sizeof path, "%s/local/patterns/patterns_len%d.npy",
                                 datadir, WORDLEN);
    else                snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    if (r != NG || c != NA) {
        fprintf(stderr, "pattern matrix %dx%d != words %dx%d\n", r, c, NG, NA);
        return 1;
    }
#ifdef MASTERMIND
    /* BEFORE anything reads PAT: --guess-list compaction, measure_branching,
     * build_lb and every partition loop all see peg codes from here on. */
    if (mm_remap(PAT, NG, NA) != 0) return 1;
#endif
    cons_none_init();

    /* A list of the wrong length is the likeliest mistake when the binary is
     * length-specific: load_words TRUNCATES to WORDLEN, so 6-letter words read
     * into the 5-letter binary would silently become their first 5 letters and
     * every result would be quietly wrong.  Check rather than truncate. */
    for (int i = 0; i < NG; i++) {
        if ((int)strlen(GWORD[i]) != WORDLEN) {
            fprintf(stderr, "guess list holds a %d-letter word (%s) but this binary "
                    "is WORDLEN %d -- wrong list, or wrong binary\n",
                    (int)strlen(GWORD[i]), GWORD[i], WORDLEN);
            return 1;
        }
    }
    for (int i = 0; i < NA; i++) {
        if ((int)strlen(AWORD[i]) != WORDLEN) {
            fprintf(stderr, "answer list holds a %d-letter word (%s) but this binary "
                    "is WORDLEN %d -- wrong list, or wrong binary\n",
                    (int)strlen(AWORD[i]), AWORD[i], WORDLEN);
            return 1;
        }
    }
    if (NG > MAXG) { fprintf(stderr, "guess list has %d words, MAXG is %d\n", NG, MAXG); return 1; }

    fprintf(stderr, "loaded %d guesses x %d answers (%d letters)\n", NG, NA, WORDLEN);

    /* --guess-list restricts the LEGAL GUESSES to the words in FILE, compacting
     * GWORD and the pattern matrix down to just those rows.  Every guess loop in
     * the solver enumerates 0..NG-1, and --sweep iterates the same range, so
     * shrinking NG here restricts BOTH the follow-up guesses and the set of
     * openers swept -- with no change to any hot loop.
     *
     * The answers are untouched: the objective is still the total over all NA
     * answers, we are only changing what may be PLAYED.  Pointing this at
     * mystery.txt gives the answers-only variant.
     *
     * Resolve every source row against the ORIGINAL list BEFORE overwriting any
     * of it -- compacting in place while still looking words up would let a
     * lookup miss a word whose slot had already been reused. */
    if (guesslist) {
        char (*rw)[WBUF] = malloc(sizeof(char[WBUF]) * MAXG);
        int nr = load_words(guesslist, rw);
        if (nr < 1 || nr > MAXG) {
            fprintf(stderr, "--guess-list %s: %d words\n", guesslist, nr); return 1;
        }
        int *map = malloc(sizeof(int) * nr);
        for (int i = 0; i < nr; i++) {
            map[i] = find_word(GWORD, NG, rw[i]);
            if (map[i] < 0) {
                fprintf(stderr, "--guess-list word %s is not a legal guess\n", rw[i]);
                return 1;
            }
        }
        pat_t *np = malloc((size_t)nr * NA * sizeof(pat_t));
        if (!np) { fprintf(stderr, "out of memory compacting pattern matrix\n"); return 1; }
        for (int i = 0; i < nr; i++) {
            memcpy(np + (size_t)i * NA, PAT + (size_t)map[i] * NA, (size_t)NA * sizeof(pat_t));
            memcpy(GWORD[i], rw[i], WBUF);
        }
        free(map); free(rw); free(PAT);
        PAT = np;
        NG = nr;
        fprintf(stderr, "guess list: restricted to %d words from %s\n", nr, guesslist);
    }

    /* TT keys are comparable ONLY within one (guess set, answer set) pair, and
     * BOTH halves matter:
     *   - a different GUESS set gives the same candidate set a different optimum;
     *   - a different ANSWER set is worse still, because the Zobrist values are
     *     indexed by ANSWER INDEX, so index 7 is simply a different word and every
     *     key silently means something else.
     * Either way a foreign tt.bin would return confidently wrong values rather
     * than missing, so salt on both. Zero when both lists are the defaults, which
     * keeps the existing hashes bit-identical and existing snapshots valid. */
    /* TOPK belongs in the salt for the same reason the word lists do, and more
     * urgently: under --topk the stored values are the best found within the
     * restricted branching, NOT exact optima. A table from one K read by another
     * K -- or by the exact solver -- would return a confidently wrong value that
     * is merely an upper bound. Each K gets its own key space. */
    /* MASTERMIND belongs in it MOST of all: the word lists are identical, so a
     * peg-feedback table and a colour-feedback table would agree on every key
     * while meaning entirely different games.  Salting it UNCONDITIONALLY is
     * what makes an optturns tt.bin fail verification in mmturns instead of
     * answering. */
#if WGT
    if (load_weights(weightsfile)) return 1;
#endif

    if (guesslist || answerlist || TOPK > 0 || MM) {
        GSALT = 0xCBF29CE484222325ULL
              ^ ((uint64_t)NG * 0xD6E8FEB86659FD93ULL)
              ^ ((uint64_t)NA * 0x9E3779B97F4A7C15ULL)
              ^ ((uint64_t)(unsigned)TOPK * 0xA24BAED4963EE407ULL)
              ^ ((uint64_t)MM * 0xF1EA5EED7A9C1B4DULL);
        for (int i = 0; i < NG; i++)
            for (int j = 0; GWORD[i][j]; j++)
                GSALT = (GSALT ^ (uint8_t)GWORD[i][j]) * 0x100000001B3ULL;
        for (int i = 0; i < NA; i++)
            for (int j = 0; AWORD[i][j]; j++)
                GSALT = (GSALT ^ (uint8_t)AWORD[i][j]) * 0x100000001B3ULL;
        fprintf(stderr, "TT salt %016llx (%d guesses, %d answers)\n",
                (unsigned long long)GSALT, NG, NA);
    }

    for (int a = 0; a < NA; a++) {
        ANS2G[a] = find_word(GWORD, NG, AWORD[a]);
        if (ANS2G[a] < 0 && !PHANTOM) {
            fprintf(stderr, "answer %s not a legal guess "
                    "(pass --phantom-final to score it as narrow-to-one plus one)\n", AWORD[a]);
            return 1;
        }
    }
    if (PHANTOM) {
        int unplayable = 0;
        for (int a = 0; a < NA; a++) if (ANS2G[a] < 0) unplayable++;
        fprintf(stderr, "phantom-final: %d of %d answers are not legal guesses "
                "(scored as narrow-to-one plus one)\n", unplayable, NA);
    }
    uint64_t seed = 0xD1B54A32D192ED03ULL;
    for (int a = 0; a < NA; a++) { ZOB0[a] = splitmix64(&seed); ZOB1[a] = splitmix64(&seed); }

    if (USE_CONS) build_bitsets();
    fprintf(stderr, "mode: %s\n",
            ULT ? "ULTRA (guesses must stay consistent with every clue)"
                : HARD ? "HARD" : "normal");

    BRANCH = measure_branching();
    /* 3**L is the ENCODING space; exactly L of those codes are unreachable --
     * the "L-1 greens plus a yellow" ones, since if every other position is
     * green the remaining letter is either green or absent, never yellow.
     * So 238 of 243 at 5 letters, 77 of 81 at 4, 2180 of 2187 at 7.
     *
     * That subtraction is a fact about the BASE-3 COLOUR space and does NOT
     * carry to peg feedback, whose one impossible pair (L-1, 1) is already
     * excluded when the codes are enumerated -- so all NPAT of them are
     * attainable and there is nothing to subtract.  Carrying `NPAT - WORDLEN`
     * across made mmturns report "15 attainable of 20", which is both wrong and
     * self-contradictory beside a measured branching of 19. */
    fprintf(stderr, "branching: %d non-winning bins (max over %d guesses; %d attainable of %d)\n",
            BRANCH, NG, MM ? NPAT : NPAT - WORDLEN, NPAT);
    build_lb();
#if WGT
    build_lvl();
    /* The uniform identity that ties the weighted bound to the one optturns has
     * always used: with every weight 1, summing LVL over the first n ranks IS
     * LBTAB[d][n].  Checked here at every depth so a mis-built schedule fails at
     * startup rather than by quietly cutting a real optimum. */
    for (int d = 1; d < MAXD; d++) {
        long long t = 0;
        for (int n = 1; n <= NA; n++) {
            if (LVL[d][n - 1] == 0) {
                if (LBTAB[d][n] < INF) {
                    fprintf(stderr, "build_lvl: depth %d rank %d disagrees with LBTAB\n", d, n);
                    return 1;
                }
                break;
            }
            t += LVL[d][n - 1];
            if (LBTAB[d][n] != (int)t) {
                fprintf(stderr, "build_lvl: depth %d n %d gives %lld, LBTAB says %d\n",
                        d, n, t, LBTAB[d][n]);
                return 1;
            }
        }
    }
    {
        uint16_t *all = malloc(sizeof(uint16_t) * (size_t)NA);
        if (!all) { fprintf(stderr, "out of memory\n"); return 1; }
        for (int a = 0; a < NA; a++) all[a] = (uint16_t)a;
        int rl = wlb(all, NA, depth);
        free(all);
        fprintf(stderr, "root LB(d=%d, n=%d) = %d  (%.5f avg, weighted)\n",
                depth, NA, rl, (double)rl / AVGDEN);
    }
#else
    fprintf(stderr, "root LB(d=%d, n=%d) = %d  (%.5f avg)\n",
            depth, NA, LBTAB[depth][NA], (double)LBTAB[depth][NA] / AVGDEN);
#endif
    tt_init(ttbits, ttload);
    if (treedir) mkdir(treedir, 0755);

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    fprintf(stderr, "threads: %d\n", omp_get_max_threads());
#endif

    /* STATE THE DISPATCH ORDER IN THE LOG.  inflight.py and passes.py have to
     * reconstruct which opener each thread is on, which means reproducing this
     * order exactly -- so it has to be readable from the run's own output rather
     * than assumed.  A log with no `order:` line predates the flag and was
     * bisected; the tools treat it that way and say so.
     *
     * IT NAMES THE ORDER THAT WILL ACTUALLY RUN, not the flag as typed.  The two
     * paths do not offer the same choice: the plain sweep always sorts by split
     * score (only the dispatch varies), while --optimal-only sorts by root lower
     * bound unless asked otherwise.  Printing the raw flag would have reported
     * `lb` for a plain sweep that was about to walk the split-score order --
     * caught by tools/checkorder.py, which is the whole reason it compares the
     * logged name against the sequence the run then produced. */
    if (sweep) {
        const char *oname = ORDER_BISECT ? "bisect"
                          : (optonly ? (ORDER_SSQ || TOPK > 0 ? "ssq" : "lb") : "ssq");
        fprintf(stderr, "order: %s\n", oname);
    }

    if (kthk > 0) {
        if (!outpath) {
            fprintf(stderr, "--kth-random needs --out FILE: it computes ONE exact "
                    "number per k and a run that only printed it saves nothing.  "
                    "Use solver/run-kth-random.sh.\n");
            return 1;
        }
        if (kth_already_done(outpath, kthk, depth, poolname)) {
            fprintf(stderr, "resume: k=%d depth=%d pool=%s is already in %s -- "
                    "nothing to do\n", kthk, depth, poolname, outpath);
            return 0;
        }
        return kth_random(treefile, kthk, depth, outpath,
                          strcmp(poolname, "all") ? POOL_COMPATIBLE : POOL_ALL,
                          kthstates);
    }

    if (nopen > 0) {
        Ctx *ctx = calloc(1, sizeof(Ctx));
        for (int k = 0; k < nopen; k++) {
            int g = find_word(GWORD, NG, openers[k]);
            if (g < 0) { fprintf(stderr, "no such guess word: %s\n", openers[k]); return 1; }
            double t0 = now_s();
            int used = 0;
            int total = solve_escalating(g, depth, depthmax, ctx, &used);
            if (total < INF && treedir) write_tree(treedir, g, used, ctx);
            double dt = now_s() - t0;
            if (total >= INF)
                printf("%s  INFEASIBLE within %d guesses  (%.1fs)\n", openers[k], depthmax, dt);
            else
                printf("%s  total=%d  expected=%.5f  d=%d  (%.1fs, %lld nodes, TT %.3f%% hit)\n",
                       openers[k], total, (double)total / AVGDEN, used, dt, ctx->nodes,
                       100.0 * ctx->hit / (ctx->probe ? ctx->probe : 1));
            fflush(stdout);
        }
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    /* ------------------------------------------------- --optimal-only sweep */
    /* -------------------------------------------- TRIPLE-OPENER EVALUATION
     *
     * Same shape as the pair walk, with one difference that matters: each listed
     * triple expands to SIX ordered candidates, not two.  The screen scores
     * unordered sets -- a triple's joint partition cannot depend on play order --
     * but the COST can, so every permutation is a distinct candidate and all six
     * are evaluated.  Evaluating one ordering per triple would leave five of six
     * untried, a far bigger error than the pair case's one of two. */
    if (triplelist) {
        if (USE_CONS) {
            fprintf(stderr, "--triple-list is normal-mode only\n");
            return 1;
        }
        if (depth < 4) {
            fprintf(stderr, "--triple-list needs --depth 4 or more (three openers "
                    "plus at least one guess)\n");
            return 1;
        }
        FILE *tf = fopen(triplelist, "r");
        if (!tf) { fprintf(stderr, "cannot open %s\n", triplelist); return 1; }
        int cap = 1024, nt = 0;
        int *t1 = malloc(sizeof(int) * cap), *t2 = malloc(sizeof(int) * cap),
            *t3 = malloc(sizeof(int) * cap);
        char line[512];
        while (fgets(line, sizeof line, tf)) {
            char w1[64], w2[64], w3[64];
            if (sscanf(line, "%63[^,],%63[^,],%63[^,],", w1, w2, w3) != 3) continue;
            int a = find_word(GWORD, NG, w1), b = find_word(GWORD, NG, w2),
                c = find_word(GWORD, NG, w3);
            if (a < 0 || b < 0 || c < 0) continue;      /* header, or restricted out */
            if (nt == cap) {
                cap *= 2;
                t1 = realloc(t1, sizeof(int) * cap);
                t2 = realloc(t2, sizeof(int) * cap);
                t3 = realloc(t3, sizeof(int) * cap);
            }
            t1[nt] = a; t2[nt] = b; t3[nt] = c; nt++;
        }
        fclose(tf);
        if (!nt) { fprintf(stderr, "no usable triples in %s\n", triplelist); return 1; }

        static const int PERM[6][3] = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
        int ncand = 6 * nt;
        int *cA = malloc(sizeof(int) * ncand), *cB = malloc(sizeof(int) * ncand),
            *cC = malloc(sizeof(int) * ncand);
        for (int i = 0; i < nt; i++) {
            int w[3] = { t1[i], t2[i], t3[i] };
            for (int q = 0; q < 6; q++) {
                cA[6*i+q] = w[PERM[q][0]];
                cB[6*i+q] = w[PERM[q][1]];
                cC[6*i+q] = w[PERM[q][2]];
            }
        }
        fprintf(stderr, "triple list: %d triples from %s -> %d ordered candidates "
                "(adaptive %d)\n", nt, triplelist, ncand, PAIR_ADAPT);

        int incumbent = INF, nbest = 0;
        int *bA = malloc(sizeof(int) * ncand), *bB = malloc(sizeof(int) * ncand),
            *bC = malloc(sizeof(int) * ncand);
        char *done = calloc(ncand, 1);
        int ndone = 0;
        FILE *rf = outpath ? fopen(outpath, "r") : NULL;
        if (rf) {
            while (fgets(line, sizeof line, rf)) {
                char w1[64], w2[64], w3[64]; int tv;
                if (sscanf(line, "%63[^,],%63[^,],%63[^,],%d", w1, w2, w3, &tv) != 4) continue;
                int a = find_word(GWORD, NG, w1), b = find_word(GWORD, NG, w2),
                    c = find_word(GWORD, NG, w3);
                if (a < 0 || b < 0 || c < 0) continue;
                for (int i = 0; i < ncand; i++)
                    if (!done[i] && cA[i] == a && cB[i] == b && cC[i] == c)
                        { done[i] = 1; ndone++; break; }
                if (tv > 0 && tv < incumbent) incumbent = tv;
            }
            fclose(rf);
            if (ndone) fprintf(stderr, "resume: %d evaluated, incumbent %d\n", ndone, incumbent);
        }
        FILE *out = outpath ? fopen(outpath, "a") : NULL;
        if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (out && ndone == 0) fprintf(out, "word1,word2,word3,total,expected,seconds\n");

        int searched = 0, cut = 0, infeas = 0;
        double t0 = now_s(), last_report = t0;
        printf("triple-list: %d ordered candidates from %d triples, depth %d, "
               "adaptive %d\n", ncand, nt, depth, PAIR_ADAPT);
        fflush(stdout);

#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            Ctx *ctx = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
            for (int i = 0; i < ncand; i++) {
                if (done[i]) continue;
                int inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
                inc = incumbent;
                double s0 = now_s();
                int total = solve_triple_bounded(cA[i], cB[i], cC[i], depth, ctx, inc);
                double dt = now_s() - s0;
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    if (total >= INF)         infeas++;
                    else if (total == CUTOFF) cut++;
                    else {
                        searched++;
                        int better = total < incumbent, tied = total == incumbent;
                        if (better) { incumbent = total; nbest = 0; }
                        if (better || tied) {
                            bA[nbest] = cA[i]; bB[nbest] = cB[i]; bC[nbest] = cC[i];
                            nbest++;
                            printf("[%7.0fs] %s %s %s  total=%5d  avg=%.5f  %s  %7.1fs\n",
                                   now_s() - t0, GWORD[cA[i]], GWORD[cB[i]], GWORD[cC[i]],
                                   total, (double)total / AVGDEN, better ? "NEW BEST" : "TIED    ", dt);
                            if (out) {
                                fprintf(out, "%s,%s,%s,%d,%.5f,%.1f\n", GWORD[cA[i]],
                                        GWORD[cB[i]], GWORD[cC[i]], total,
                                        (double)total / AVGDEN, dt);
                                fflush(out);
                            }
                        }
                    }
                    int seen = searched + cut + infeas;
                    if (now_s() - last_report > 30.0) {
                        last_report = now_s();
                        double el = now_s() - t0;
                        printf("[%7.0fs] %6d/%d done (%d searched, %d cut, %d infeas)  "
                               "best=%d (avg %.5f)  eta %5.1fh\n",
                               el, seen, ncand, searched, cut, infeas, incumbent,
                               incumbent < INF ? (double)incumbent / AVGDEN : 0.0,
                               (el / (seen > 0 ? seen : 1)) * (ncand - seen) / 3600.0);
                    }
                    fflush(stdout);
                }
            }
            free(ctx);
        }

        double el = now_s() - t0;
        printf("\n=== BEST TRIPLE (of %d screened, all 6 orders, depth %d, adaptive %d) ===\n",
               nt, depth, PAIR_ADAPT);
        if (incumbent >= INF) {
            printf("NO TRIPLE in the list solves every answer within %d guesses.\n", depth);
        } else {
            printf("total=%d  expected=%.5f  over %d answers\n",
                   incumbent, (double)incumbent / AVGDEN, NA);
            printf("%d ordering%s attain it:", nbest, nbest == 1 ? "" : "s");
            for (int i = 0; i < nbest; i++)
                printf(" %s+%s+%s", GWORD[bA[i]], GWORD[bB[i]], GWORD[bC[i]]);
            printf("\n");
        }
        printf("searched %d, cut %d, infeasible %d, of %d ordered candidates in %.0fs\n",
               searched, cut, infeas, ncand, el);
        printf("NOTE: best of the %d triples SCREENED, by a GREEDY screen that can only "
               "reach a triple one of whose word PAIRS ranked highly. Not the optimal triple.\n", nt);
        if (out) fclose(out);
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    /* ---------------------------------------------- PAIR-OPENER EVALUATION
     *
     * Walk a list of candidate PAIRS -- produced by ./pairsplit, in ascending
     * joint sum-of-squares order -- against a running incumbent, and report the
     * pair with the lowest exact total.
     *
     * The claim this supports is narrower than the single-opener sweep's, and
     * the difference must survive into how the result is reported: the pair list
     * is a HEURISTIC screen, so the winner is the best of the pairs SCREENED,
     * not the optimal pair over all C(NG,2). Sum of squares proves nothing.
     *
     * Within that list, though, the evaluation is exact: every pair is either
     * solved exactly or proven worse than the incumbent, and ties are kept. */
    if (pairlist) {
        if (USE_CONS) {
            fprintf(stderr, "--pair-list is normal-mode only: in hard/ultra mode the "
                    "second word's legality depends on the first one's feedback, so a "
                    "BLIND pair is not a well-defined opening\n");
            return 1;
        }
        if (depth < 3) {
            fprintf(stderr, "--pair-list needs --depth 3 or more (two openers plus at "
                    "least one guess)\n");
            return 1;
        }
        FILE *pf = fopen(pairlist, "r");
        if (!pf) { fprintf(stderr, "cannot open %s\n", pairlist); return 1; }
        int cap = 1024, np = 0;
        int *p1 = malloc(sizeof(int) * cap), *p2 = malloc(sizeof(int) * cap);
        char line[256];
        while (fgets(line, sizeof line, pf)) {
            char w1[64], w2[64];
            if (sscanf(line, "%63[^,],%63[^,],", w1, w2) != 2) continue;
            int a = find_word(GWORD, NG, w1), b = find_word(GWORD, NG, w2);
            if (a < 0 || b < 0) continue;          /* the header lands here */
            if (np == cap) {
                cap *= 2;
                p1 = realloc(p1, sizeof(int) * cap);
                p2 = realloc(p2, sizeof(int) * cap);
            }
            p1[np] = a; p2[np] = b; np++;
        }
        fclose(pf);
        if (!np) { fprintf(stderr, "no usable pairs in %s\n", pairlist); return 1; }
        /* BOTH ORDERS.  The screen scores unordered pairs -- correctly, since the
         * joint partition cannot depend on order -- but the COST can, so each
         * listed pair becomes two candidates.  Ignoring this silently reports the
         * worse order whenever exactly one of the words is an answer. */
        int ncand = 2 * np;
        int *cA = malloc(sizeof(int) * ncand), *cB = malloc(sizeof(int) * ncand);
        for (int i = 0; i < np; i++) {
            cA[2*i] = p1[i];     cB[2*i] = p2[i];
            cA[2*i+1] = p2[i];   cB[2*i+1] = p1[i];
        }
        if (PAIR_ADAPT > 0)
            fprintf(stderr, "pair list: %d pairs from %s -> %d ordered candidates "
                    "(adaptive when g1 leaves %d or fewer)\n",
                    np, pairlist, ncand, PAIR_ADAPT);
        else
            fprintf(stderr, "pair list: %d pairs from %s -> %d ordered candidates (pure blind)\n",
                    np, pairlist, ncand);

        int incumbent = INF, nbest = 0;
        int *bestA = malloc(sizeof(int) * ncand), *bestB = malloc(sizeof(int) * ncand);
        char *done = calloc(ncand, 1);
        int ndone = 0;

        /* Resume, and seed the incumbent -- a good bound from a previous run
         * prunes immediately instead of being rediscovered. */
        FILE *rf = outpath ? fopen(outpath, "r") : NULL;
        if (rf) {
            while (fgets(line, sizeof line, rf)) {
                char w1[64], w2[64]; int t;
                if (sscanf(line, "%63[^,],%63[^,],%d", w1, w2, &t) != 3) continue;
                int a = find_word(GWORD, NG, w1), b = find_word(GWORD, NG, w2);
                if (a < 0 || b < 0) continue;
                for (int i = 0; i < ncand; i++)
                    if (!done[i] && cA[i] == a && cB[i] == b) { done[i] = 1; ndone++; break; }
                if (t > 0 && t < incumbent) incumbent = t;
            }
            fclose(rf);
            if (ndone) fprintf(stderr, "resume: %d evaluated, incumbent %d\n", ndone, incumbent);
        }
        FILE *out = outpath ? fopen(outpath, "a") : NULL;
        if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (out && ndone == 0) fprintf(out, "word1,word2,total,expected,seconds\n");

        int searched = 0, cut = 0, infeas = 0;
        double t0 = now_s(), last_report = t0;
        printf("pair-list: %d ordered candidates from %d pairs, depth %d, "
               "exact within the list, adaptive %d\n", ncand, np, depth, PAIR_ADAPT);
        fflush(stdout);

#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            Ctx *ctx = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
            for (int i = 0; i < ncand; i++) {
                if (done[i]) continue;
                int inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
                inc = incumbent;
                double s0 = now_s();
                int total = solve_pair_bounded(cA[i], cB[i], depth, ctx, inc);
                double dt = now_s() - s0;

#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    if (total >= INF)      infeas++;
                    else if (total == CUTOFF) cut++;
                    else {
                        searched++;
                        if (total < incumbent) {
                            incumbent = total;
                            nbest = 0; bestA[nbest] = cA[i]; bestB[nbest] = cB[i]; nbest++;
                            printf("[%7.0fs] %s %s  total=%5d  avg=%.5f  NEW BEST  %7.1fs\n",
                                   now_s() - t0, GWORD[cA[i]], GWORD[cB[i]], total,
                                   (double)total / AVGDEN, dt);
                            if (out) {
                                fprintf(out, "%s,%s,%d,%.5f,%.1f\n", GWORD[cA[i]],
                                        GWORD[cB[i]], total, (double)total / AVGDEN, dt);
                                fflush(out);
                            }
                        } else if (total == incumbent) {
                            bestA[nbest] = cA[i]; bestB[nbest] = cB[i]; nbest++;
                            printf("[%7.0fs] %s %s  total=%5d  avg=%.5f  TIED      %7.1fs\n",
                                   now_s() - t0, GWORD[cA[i]], GWORD[cB[i]], total,
                                   (double)total / AVGDEN, dt);
                            if (out) {
                                fprintf(out, "%s,%s,%d,%.5f,%.1f\n", GWORD[cA[i]],
                                        GWORD[cB[i]], total, (double)total / AVGDEN, dt);
                                fflush(out);
                            }
                        }
                    }
                    int seen = searched + cut + infeas;
                    if (now_s() - last_report > 30.0) {
                        last_report = now_s();
                        double el = now_s() - t0;
                        printf("[%7.0fs] %5d/%d done (%d searched, %d cut, %d infeas)  "
                               "best=%d (avg %.5f)  %.1f/min  eta %5.1fh\n",
                               el, seen, ncand, searched, cut, infeas, incumbent,
                               incumbent < INF ? (double)incumbent / AVGDEN : 0.0,
                               60.0 * seen / (el > 0 ? el : 1),
                               (el / (seen > 0 ? seen : 1)) * (ncand - seen) / 3600.0);
                    }
                    fflush(stdout);
                }
            }
            free(ctx);
        }

        double el = now_s() - t0;
        printf("\n=== BEST PAIR (of %d pairs screened, both orders, depth %d, adaptive %d) ===\n",
               np, depth, PAIR_ADAPT);
        if (incumbent >= INF) {
            printf("NO PAIR in the list solves every answer within %d guesses.\n", depth);
        } else {
            printf("total=%d  expected=%.5f  over %d answers\n",
                   incumbent, (double)incumbent / AVGDEN, NA);
            printf("%d pair%s attain it:", nbest, nbest == 1 ? "" : "s");
            for (int i = 0; i < nbest; i++) printf(" %s+%s", GWORD[bestA[i]], GWORD[bestB[i]]);
            printf("\n");
        }
        printf("searched %d, cut %d, infeasible %d, of %d ordered candidates in %.0fs\n",
               searched, cut, infeas, ncand, el);
        printf("NOTE: best of the %d pairs SCREENED by joint sum of squares, "
               "which is a heuristic -- not the optimal pair over all C(%d,2).\n", np, NG);
        if (out) fclose(out);
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    if (optonly) {
        if (!sweep) { fprintf(stderr, "--optimal-only requires --sweep\n"); return 1; }

        /* Screen at the CEILING, not the floor.  Openers escalate UPWARD from
         * --depth, so an opener that cannot fit the floor may still be perfectly
         * feasible deeper: rejecting it here on the floor's bound would discard
         * it before escalation ever gets a chance, which is precisely the case
         * this design exists to handle.  root_lb is monotone in depth, so the
         * ceiling's bound rejects only what can NEVER work.  It is looser, so
         * the initial cutoffs are weaker -- the re-bound after the first opener
         * tightens everything to the depth actually in force. */
        int *lb = malloc(sizeof(int) * NG);
#ifdef _OPENMP
#pragma omp parallel for schedule(static)
#endif
        for (int g = 0; g < NG; g++) lb[g] = root_lb(g, MAXD - 1);

        int64_t *ord = malloc(sizeof(int64_t) * NG);
        int nord = 0, nolb = 0;

        if (TOPK > 0 || ORDER_SSQ) {
            /* THE OPENER IS A BRANCHING POINT LIKE ANY OTHER.  --topk means the
             * top K by sum of squared bin sizes at EVERY branching point, and the
             * root is the first one -- so the sweep examines K openers, not all
             * NG of them.  K=1 checks exactly one starting word.
             *
             * The order is the sum-of-squares order and is NOT re-sorted by lower
             * bound: the selection rule and the visit order are the same thing
             * here, by definition of what was asked for.
             *
             * Consequence to state plainly: the winner is the best of the K
             * openers EXAMINED, not the best of all NG. That is a weaker claim
             * than the exact sweep makes, and it is the point -- it is what lets
             * a small K finish. */
            /* The dispatch order is whatever was ASKED for: ascending split
             * score by default (--order ssq, and the only thing --topk can mean),
             * bisected only under --order bisect, which is refused alongside
             * --topk above. */
            int64_t *so = sweep_order(ORDER_BISECT);
            /* --order ssq is the SAME ordering with no truncation: every opener
             * is still examined, so the result is exact -- only the visit order
             * changes.  --topk is what makes the claim weaker, not this. */
            int K = (TOPK > 0 && TOPK < NG) ? TOPK : NG;
            for (int i = 0; i < K; i++) {
                int g = (int)(so[i] & 0xFFFFF);
                if (lb[g] >= INF) { nolb++; continue; }
                /* the LB still rides in the high bits -- the per-opener skip
                 * reads it -- but the ARRAY stays in sum-of-squares order. */
                ord[nord++] = ((int64_t)lb[g] << 20) | (int64_t)g;
            }
            free(so);
            if (TOPK > 0)
                fprintf(stderr, "topk root: %d openers of %d examined (top %d by sum of squares), %d rejected by LB\n",
                        nord, NG, K, nolb);
            else
                fprintf(stderr, "ssq root: %d openers in sum-of-squares order, %d rejected outright by LB\n",
                        nord, nolb);
        } else {
            for (int g = 0; g < NG; g++) {
                if (lb[g] >= INF) { nolb++; continue; }   /* cannot fit the cap at all */
                ord[nord++] = ((int64_t)lb[g] << 20) | (int64_t)g;
            }
            qsort(ord, nord, sizeof(int64_t), cmp_i64);
            fprintf(stderr, "root LB screen: %d openers ranked, %d rejected outright\n",
                    nord, nolb);
        }

        /* Resume: an existing CSV seeds the incumbent, REBUILDS THE TIE LIST and
         * marks work done.  Seeding matters most -- a good bound from the previous
         * run prunes immediately instead of rediscovering it.
         *
         * THE TIE LIST HAS TO BE REBUILT, or a resumed run reports only the ties
         * found SINCE RESTARTING.  In the common case that is none at all: every
         * opener is cut against an incumbent that came off disk, so the run ends
         * printing "0 openers attain it" for the very value it is reporting as
         * best.  The number is right and the list is a lie, which is worse than
         * either being wrong.  `greens.c` carries this scar already; this path did
         * not.  MEASURED on a resumed wturns k=100 run: 76 cut, 0 searched, best
         * 49036860, "0 openers attain it".
         *
         * The comparison MUST be the in-run one -- shallower depth wins outright,
         * then lower total -- or the rebuilt list could be the ties of a row the
         * live search would not have accepted as leader.  Older CSVs predate the
         * depth column; those rows are read at the run's own --depth.
         *
         * NOT changed here: a resumed run does NOT adopt a shallower depth as its
         * new cap the way the live search does.  That interacts with the
         * first-opener escalation below and is a separate question; it is inert
         * wherever --depth is pinned, which is every --optimal-only sweep today. */
        int incumbent = INF;
        int best_depth = MAXD;
        char *done = calloc(NG, 1);
        int ndone = 0;
        /* NG, not nord: the file may hold more rows than this run will visit
         * (a --topk run resumed with a different K), and a tie list that
         * overflows its buffer is a far worse failure than a big allocation. */
        int *best = malloc(sizeof(int) * NG);
        int nbest = 0;
        FILE *rf = outpath ? fopen(outpath, "r") : NULL;
        if (rf) {
            char line[256];
            while (fgets(line, sizeof line, rf)) {
                char w[64]; int t, d;
                int nf = sscanf(line, "%63[^,],%d,%*[^,],%d", w, &t, &d);
                if (nf < 2) continue;
                int g = find_word(GWORD, NG, w);
                if (g >= 0 && !done[g]) { done[g] = 1; ndone++; }
                if (t <= 0) continue;                  /* an INFEASIBLE row */
                if (nf < 3) d = depth;                 /* CSV without the column */
                if (d < best_depth || (d == best_depth && t < incumbent)) {
                    best_depth = d; incumbent = t; nbest = 0;
                    if (g >= 0) best[nbest++] = g;
                } else if (d == best_depth && t == incumbent && g >= 0) {
                    best[nbest++] = g;
                }
            }
            fclose(rf);
            if (ndone)
                fprintf(stderr, "resume: %d searched, incumbent %d at depth %d, "
                        "%d opener%s tied\n", ndone, incumbent, best_depth,
                        nbest, nbest == 1 ? "" : "s");
        }
        FILE *out = outpath ? fopen(outpath, "a") : NULL;
        if (outpath && !out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
        if (out && ndone == 0) fprintf(out, "word,total,expected,depth,seconds\n");

        /* seen  = reached the critical section (searched + cut + infeasible)
         * lbskip = discarded by the root LB without any search, never reaches it
         * so processed = seen + lbskip, and the two must not be conflated. */
        int searched = 0, cut = 0, infeas = 0, seen = 0, lbskip = 0;
        double t0 = now_s(), last_report = t0;

        if (TOPK > 0)
            printf("optimal-only: top %d openers by sum of squared bins (of %d); best of these K, not of all %d\n",
                   nord, NG, NG);
        else if (ORDER_BISECT)
            printf("optimal-only: %d openers, split-score sort DISPATCHED BY BISECTION "
                   "(all %d examined; exact; a stopped run is a stratified sample, "
                   "NOT the best openers first)\n", nord, NG);
        else if (ORDER_SSQ)
            printf("optimal-only: %d openers in ascending split-score order, best splitters first "
                   "(all %d examined; exact)\n", nord, NG);
        else
            printf("optimal-only: %d openers by ascending root LB (min %d = %.5f avg)\n",
                   nord, nord ? (int)(ord[0] >> 20) : 0,
                   nord ? (double)(int)(ord[0] >> 20) / AVGDEN : 0.0);
        fflush(stdout);

        /* ---- DEPTH IS MEASURED FROM THE FIRST OPENER, NOT ASSUMED -----------
         * Solve the most promising opener at an ESCALATING cap starting at
         * --depth, take the cap it actually needed, and hold every remaining
         * opener to that same depth.  This replaces guessing whether 6 is
         * satisfiable: under --topk an INFEASIBLE at a fixed 6 would mostly be
         * an artifact of the restricted branching rather than a fact about the
         * problem, and a per-opener escalation would compare openers under
         * DIFFERENT constraints, which is not one objective.
         *
         * The floor is the requested --depth: if the first opener happens to
         * solve in fewer, we still allow the full budget, so no opener is held
         * to a tighter cap than asked for. */
        const int depth_floor = depth;   /* never ratchet below what was asked for */
        /* PINNED CAP.  When --depth-max equals --depth (its default in normal
         * mode) the caller has asked for ONE cap, not a search for the shallowest
         * one -- so the probe below is skipped entirely.  Two reasons it must be:
         * it would abort the whole run if the first opener happened to be
         * infeasible at that cap, and its whole purpose is to RAISE the cap,
         * which is precisely what a pinned run does not want.  Skipping it also
         * keeps depth == depth_floor, which is what keeps the LB skip live. */
        if (nord > 0 && depthmax > depth) {
            int g0 = (int)(ord[0] & 0xFFFFF);
            Ctx *c0 = calloc(1, sizeof(Ctx));
            double s0 = now_s();
            int used = 0;
            /* bounded by depthmax, not MAXD-1: --depth-max is the caller's
             * ceiling and this must not escalate past it. */
            int t0v = solve_escalating(g0, depth, depthmax, c0, &used);
            double dt0 = now_s() - s0;
            /* THE FIRST OPENER FAILING IS NOT A REASON TO ABORT THE RUN.  It
             * used to return 1 here, which threw away the whole sweep because one
             * word could not fit the ceiling -- while other openers reach it
             * perfectly well.  Under --topk that is worse still: an INFEASIBLE
             * there is frequently an artifact of the restricted branching rather
             * than a fact about the problem.
             *
             * So fall through with the cap set to the CEILING and let the walk
             * decide.  If genuinely nothing solves, the final report says exactly
             * that -- a real answer, and a far more useful one than an early exit.
             * The probe's only job is to pick the working cap; failing to solve
             * still answers that, with the ceiling. */
            int probe_ok = (t0v < INF);
            if (!probe_ok) {
                printf("%s  INFEASIBLE at every depth up to %d  (%.1fs) -- holding every "
                       "opener to %d and continuing with the rest\n",
                       GWORD[g0], depthmax, dt0, depthmax);
                depth = depthmax;
            }
            else if (used > depth) {
                printf("%s  needed depth %d (not %d); holding every opener to %d\n",
                       GWORD[g0], used, depth, used);
                depth = used;
                /* the LB values were computed at the OLD depth -- redo them, or
                 * every cutoff bound refers to a different cap.  Under --topk the
                 * SET and its ORDER are fixed by sum of squares, which does not
                 * depend on depth, so only the bounds are refreshed. */
                for (int g = 0; g < NG; g++) lb[g] = root_lb(g, depth);
                if (TOPK > 0 || ORDER_SSQ) {
                    for (int i = 0; i < nord; i++) {
                        int g = (int)(ord[i] & 0xFFFFF);
                        ord[i] = ((int64_t)lb[g] << 20) | (int64_t)g;
                    }
                    printf("re-bounded at depth %d: same %d openers, order unchanged\n",
                           depth, nord);
                } else {
                    nord = 0;
                    for (int g = 0; g < NG; g++)
                        if (lb[g] < INF) ord[nord++] = ((int64_t)lb[g] << 20) | (int64_t)g;
                    qsort(ord, nord, sizeof(int64_t), cmp_i64);
                    printf("re-ranked at depth %d: %d openers, min LB %d (%.5f avg)\n",
                           depth, nord, (int)(ord[0] >> 20), (double)(int)(ord[0] >> 20) / AVGDEN);
                }
            } else {
                printf("%s  solved at depth %d  total=%d  avg=%.5f  (%.1fs)\n",
                       GWORD[g0], used, t0v, (double)t0v / AVGDEN, dt0);
            }
            /* The screen ran at the CEILING; now that the working depth is known,
             * tighten every bound to it. */
            for (int q = 0; q < nord; q++) {
                int gg = (int)(ord[q] & 0xFFFFF);
                lb[gg] = root_lb(gg, depth);
                ord[q] = ((int64_t)lb[gg] << 20) | (int64_t)gg;
            }
            if (TOPK == 0) qsort(ord, nord, sizeof(int64_t), cmp_i64);
            if (probe_ok) {
                incumbent = t0v;
                nbest = 0; best[nbest++] = g0;
                done[g0] = 1;
                searched++;
                if (out) {
                    fprintf(out, "%s,%d,%.5f,%d,%.1f\n",
                            GWORD[g0], t0v, (double)t0v / AVGDEN, depth, dt0);
                    fflush(out);
                }
                printf("[%7.0fs] %s  total=%5d  avg=%.5f  FIRST (depth %d)  %7.1fs\n",
                       now_s() - t0, GWORD[g0], t0v, (double)t0v / AVGDEN, depth, dt0);
            } else {
                /* no incumbent to seed -- the walk starts unbounded, exactly as it
                 * would have if this opener had come up later in the order */
                done[g0] = 1;
                infeas++;
            }
            fflush(stdout);
            free(c0);
        }

#ifdef _OPENMP
#pragma omp parallel
#endif
        {
            Ctx *ctx = calloc(1, sizeof(Ctx));
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 1)
#endif
            for (int i = 0; i < nord; i++) {
                int g = (int)(ord[i] & 0xFFFFF);
                int mylb = (int)(ord[i] >> 20);
                if (done[g]) continue;
                int inc;
#ifdef _OPENMP
#pragma omp atomic read
#endif
                inc = incumbent;
                /* The LB skip compares TOTALS, so under the lexicographic
                 * objective it is only sound once no DEPTH improvement is still
                 * possible -- i.e. the leader already solves at the floor.  Above
                 * the floor an opener with a hopeless total could still win by
                 * finishing shallower, and skipping it would lose the answer.
                 *
                 * Even when it applies, the list is in sum-of-squares order under
                 * TOPK or --order ssq, so it says nothing about the openers AFTER
                 * it; only ascending-LB order makes it a proof about the tail.
                 * The skip itself stays SOUND in every order -- an opener whose
                 * own LB exceeds the incumbent cannot win -- it is only the
                 * "and therefore so is everything after" reading that needs the
                 * sort, and nothing here breaks early on it. */
                if (depth <= depth_floor && mylb > inc) {
#ifdef _OPENMP
#pragma omp atomic
#endif
                    lbskip++;
                    /* An LB-skipped opener never reaches the critical section
                     * below, so it prints nothing AND writes no CSV row -- it is
                     * the quietest of the four outcomes and the one most likely
                     * to be mistaken for an opener that was never examined.  Its
                     * bound is a real result about it ("cannot beat the
                     * incumbent, proved without searching"), so say so. */
                    if (PRINT_OPENERS)
#ifdef _OPENMP
#pragma omp critical
#endif
                        printf("[%7.0fs] %s  LB-SKIP (lb=%d exceeds %d)\n",
                               now_s() - t0, GWORD[g], mylb, inc);
                    continue;
                }
                /* ---- TRY EVERY DEPTH FROM THE FLOOR UP TO THE CURRENT BOUND --
                 * Each opener is attempted at 6 first, then 7, and so on up to
                 * the bound in force.  Solving at a SHALLOWER cap is the goal in
                 * its own right, and the first opener's requirement is not
                 * evidence about the rest -- it only sets the ceiling.
                 *
                 * A depth that CUTS ends the escalation for this opener: it
                 * cannot beat the incumbent at that cap, and going deeper to
                 * chase it would work against lowering the bound. That is a
                 * deliberate approximation -- f(S,d) is non-increasing in d, so
                 * a deeper cap COULD have beaten the incumbent -- and it is the
                 * price of driving the bound down. */
                double s0 = now_s();
                int total = INF, dused = 0;
                int cap;
#ifdef _OPENMP
#pragma omp atomic read
#endif
                cap = depth;
                for (int dd = depth_floor; dd <= cap; dd++) {
                    /* LEXICOGRAPHIC: depth first, total second.  An opener that
                     * resolves SHALLOWER than the leader wins outright however
                     * large its total, so no total-based cutoff may be applied to
                     * it -- pass INF.  Only at the leader's own depth does the
                     * total decide, and there the incumbent is a valid bound. */
                    total = solve_opener_bounded(g, dd, ctx, dd < cap ? INF : inc);
                    dused = dd;
                    if (total < INF) break;      /* solved, or cut, at this depth */
                }
                double dt = now_s() - s0;
#ifdef _OPENMP
#pragma omp critical
#endif
                {
                    g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                    ctx->probe = ctx->hit = ctx->fill = 0;
                    seen++;
                    double el = now_s() - t0;
                    double hit = 100.0 * g_hit / (g_probe ? g_probe : 1);
                    double occ = TT_SLOTS ? 100.0 * g_fill / (double)TT_SLOTS : 0.0;
                    if (total >= INF) {
                        infeas++;
                        printf("[%7.0fs] %s  INFEASIBLE within %d   lb=%d  %7.1fs\n",
                               el, GWORD[g], depth, mylb, dt);
                    } else if (total == CUTOFF) {
                        cut++;
                        /* A cut opener writes no CSV row -- the search was
                         * abandoned once it could not beat the incumbent, so it
                         * HAS no total.  Without this line it would vanish from
                         * a per-opener printout entirely, which is exactly the
                         * gap --print-openers exists to close. */
                        if (PRINT_OPENERS)
                            printf("[%7.0fs] %s  CUT (cannot beat %d)   lb=%d  %7.1fs\n",
                                   el, GWORD[g], incumbent, mylb, dt);
                    } else {
                        searched++;
                        if (out) {
                            fprintf(out, "%s,%d,%.5f,%d,%.1f\n",
                                    GWORD[g], total, (double)total / AVGDEN, dused, dt);
                            fflush(out);
                        }
                        /* Solved at a shallower cap than the bound in force, so
                         * the bound comes down and every later opener is held to
                         * it.  Ratchets one way only, and never below the
                         * requested --depth. */
                        /* LEXICOGRAPHIC COMPARISON: fewer guesses in the WORST
                         * case beats a lower total.  A word that finishes at a
                         * shallower depth wins outright even if its total is
                         * worse, so depth is tested before total. */
                        if (dused < depth) {
                            printf("[%7.0fs] %s  total=%5d  avg=%.5f  NEW BEST (depth %d, was %d)  %7.1fs\n",
                                   el, GWORD[g], total, (double)total / AVGDEN, dused, depth, dt);
                            depth = dused;            /* the bound IS the leader's depth */
                            incumbent = total;
                            nbest = 0; best[nbest++] = g;
                            for (int q = 0; q < nord; q++) {
                                int gg = (int)(ord[q] & 0xFFFFF);
                                lb[gg] = root_lb(gg, depth);
                                ord[q] = ((int64_t)lb[gg] << 20) | (int64_t)gg;
                            }
                        } else if (total < incumbent) {
                            incumbent = total;
                            nbest = 0; best[nbest++] = g;
                            printf("[%7.0fs] %s  total=%5d  avg=%.5f  NEW BEST  d=%d  lb=%d  %7.1fs  tt %.2f%%/%.2f%%\n",
                                   el, GWORD[g], total, (double)total / AVGDEN, dused, mylb, dt, hit, occ);
                        } else if (total == incumbent) {
                            best[nbest++] = g;
                            printf("[%7.0fs] %s  total=%5d  avg=%.5f  TIED      d=%d  lb=%d  %7.1fs  tt %.2f%%/%.2f%%\n",
                                   el, GWORD[g], total, (double)total / AVGDEN, dused, mylb, dt, hit, occ);
                        } else if (PRINT_OPENERS) {
                            /* Worse than the incumbent.  It still SOLVED and it
                             * still wrote a CSV row, so by default it printed
                             * nothing and the terminal showed fewer openers than
                             * the file held.  Same columns as the NEW BEST line,
                             * so the two read down one column. */
                            printf("[%7.0fs] %s  total=%5d  avg=%.5f            d=%d  lb=%d  %7.1fs  tt %.2f%%/%.2f%%\n",
                                   el, GWORD[g], total, (double)total / AVGDEN, dused, mylb, dt, hit, occ);
                        }
                    }
                    /* Heartbeat on WHICHEVER comes first, count or time.  A count
                     * alone goes silent for many minutes when openers are slow --
                     * which is exactly when you most need to see it moving, and is
                     * indistinguishable from a hang. */
                    if (seen % 100 == 0 || now_s() - last_report >= 30.0) {
                        last_report = now_s();
                        int gone = seen + lbskip, left = nord - gone;
                        printf("[%7.0fs] %5d/%d done (%d searched, %d cut, %d lb-skip, %d infeas)  best=%d (avg %.5f)  %.1f/min  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                               el, gone, nord, searched, cut, lbskip, infeas, incumbent,
                               incumbent < INF ? (double)incumbent / AVGDEN : 0.0,
                               gone / (el / 60.0),
                               (left > 0 && gone > 0) ? el / (double)gone * left / 3600.0 : 0.0,
                               hit, occ);
                    }
                    fflush(stdout);
                }
            }
            free(ctx);
        }

        double el = now_s() - t0;
        printf("\n=== OPTIMAL (guesses %d, answers %d, depth %d) ===\n", NG, NA, depth);
        if (incumbent >= INF) {
            printf("NO OPENER solves every answer within %d guesses.\n", depth);
            printf("%d rejected by lower bound, %d proved infeasible by search.\n", nolb, infeas);
        } else {
            printf("depth=%d (worst case), total=%d  expected=%.5f  over %d answers\n",
                   depth, incumbent, (double)incumbent / AVGDEN, NA);
            printf("%d opener%s attain it:", nbest, nbest == 1 ? "" : "s");
            for (int i = 0; i < nbest; i++) printf(" %s", GWORD[best[i]]);
            printf("\n");
        }
        printf("searched %d, cut %d, lb-skipped %d, infeasible %d, lb-rejected %d, of %d openers in %.0fs\n",
               searched, cut, lbskip, infeas, nolb, NG, el);
        if (out) fclose(out);
        if (ttsave) tt_save(ttsave);
        return 0;
    }

    if (!sweep) { fprintf(stderr, "nothing to do: pass --opener WORD or --sweep\n"); return 1; }
    if (!outpath) { fprintf(stderr, "--sweep needs --out FILE\n"); return 1; }

    char *done = calloc(NG, 1);
    int ndone = 0;
    FILE *rf = fopen(outpath, "r");
    if (rf) {
        char line[256];
        while (fgets(line, sizeof line, rf)) {
            char w[64];
            if (sscanf(line, "%63[^,],", w) != 1) continue;
            int g = find_word(GWORD, NG, w);
            if (g >= 0 && !done[g]) { done[g] = 1; ndone++; }
        }
        fclose(rf);
        fprintf(stderr, "resume: %d openers already done\n", ndone);
    }
    FILE *out = fopen(outpath, "a");
    if (!out) { fprintf(stderr, "cannot append to %s\n", outpath); return 1; }
    if (ndone == 0) fprintf(out, "word,total,expected,depth,seconds\n");

    /* Default ascending split score (best splitters first); bisection only when
     * --order bisect asked for it.  The order cannot change a total -- every
     * opener is examined either way -- it decides WHEN each lands, and therefore
     * what a stopped run holds and how early the incumbent prunes. */
    int64_t *ord = sweep_order(ORDER_BISECT);
    double t0 = now_s();
    int completed = 0;

#pragma omp parallel
    {
        Ctx *ctx = calloc(1, sizeof(Ctx));
#pragma omp for schedule(dynamic, 1)
        for (int i = 0; i < NG; i++) {
            int g = (int)(ord[i] & 0xFFFFF);
            if (done[g]) continue;
            double s0 = now_s();
            int used = 0;
            int total = solve_escalating(g, depth, depthmax, ctx, &used);
            int tree_ok = 1;
            if (total < INF && treedir) tree_ok = (write_tree(treedir, g, used, ctx) == 0);
            double dt = now_s() - s0;
#pragma omp critical
            {
                /* fold this thread's counters into the globals, then reset */
                g_probe += ctx->probe; g_hit += ctx->hit; g_fill += ctx->fill;
                ctx->probe = ctx->hit = ctx->fill = 0;

                if (total >= INF) fprintf(out, "%s,,,,%.1f\n", GWORD[g], dt);
                else              fprintf(out, "%s,%d,%.5f,%d,%.1f\n", GWORD[g], total,
                                          (double)total / AVGDEN, used, dt);
                fflush(out);
                completed++;
                double el = now_s() - t0;
                int left = NG - ndone - completed;
                double hit = 100.0 * g_hit / (g_probe ? g_probe : 1);
                double occ = TT_SLOTS ? 100.0 * g_fill / (double)TT_SLOTS : 0.0;
                if (total >= INF)
                    printf("[%7.0fs] %5d/%d  %s  INFEASIBLE d>%-2d          %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], depthmax, dt,
                           el / completed * left / 3600.0, hit, occ);
                else if (guesslist)
                    /* exp= is dropped for a restricted guess set: it is just
                     * total/2315, and the run is read for the OVERALL best
                     * rather than per-word averages.  The trailing tt %/%% is
                     * load-bearing -- report.py and ttscan.py parse it. */
                    printf("[%7.0fs] %5d/%d  %s  total=%5d  d=%d%s%s %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], total,
                           used, used > depth ? " *" : "  ",
                           tree_ok ? "" : " TREE-FAIL", dt,
                           el / completed * left / 3600.0, hit, occ);
                else
                    printf("[%7.0fs] %5d/%d  %s  total=%5d  exp=%.5f  d=%d%s%s %7.1fs  eta %5.1fh  tt %.2f%%/%.2f%%\n",
                           el, ndone + completed, NG, GWORD[g], total, (double)total / AVGDEN,
                           used, used > depth ? " *" : "  ",
                           tree_ok ? "" : " TREE-FAIL", dt,
                           el / completed * left / 3600.0, hit, occ);
                fflush(stdout);
            }
        }
        free(ctx);
    }
    fclose(out);
    if (ttsave) tt_save(ttsave);
    fprintf(stderr, "sweep complete in %.1fs\n", now_s() - t0);
    return 0;
}
