/* secondword -- the best PREDETERMINED second word for every opener.
 *
 * THE QUANTITY, and math/secondword.py states it as the source of truth.  For an
 * opener g1, take the answers whose reply to g1 FIRES THE RULE -- a set of
 * (greens, yellows) compositions, of which --min-grays N is the sugar for "at
 * least N greys" -- group them by that reply, and for each candidate g2 score
 *
 *     score(g1, g2) = sum over JOINT (reply to g1, reply to g2) buckets of n^2
 *     expected      = score / (number of qualifying answers)
 *
 * which is the expected number of ANSWERS still consistent after both words,
 * conditional on the opener's reply having fired the rule, the answer uniform
 * over the answer list.  ANSWER-WEIGHTED: a reply 300 answers produce counts 300
 * times against one that 2 produce.  Emit the argmin, ties on the LOWEST GUESS
 * INDEX, and record how many words attained it.
 *
 * IT IS pairsplit's ssq RESTRICTED TO THE QUALIFYING ROWS, so the inner loop is
 * pairsplit's and is borrowed deliberately: for a fixed g1 the qualifying answers
 * are reordered ONCE into contiguous runs, one per g1-bucket, and each g2 is then
 * histogrammed run by run into a 243-entry counter (972 bytes, L1-resident),
 * cleared through a touched-list rather than a memset.
 *
 * WHAT IS NOT INHERITED FROM pairsplit, having enumerated them one by one:
 *
 *   - the answers are FILTERED before they are bucketed (its runs cover all NA);
 *   - the walk is over ORDERED (g1, g2), not unordered pairs: the filter depends
 *     on g1, so (a, b) and (b, a) are different questions here and both are
 *     needed;
 *   - g2 == g1 is skipped -- a repeat reproduces the reply already seen;
 *   - there is no heap and no --top: the result is one ROW PER OPENER, an argmin,
 *     not a global ranking, so nothing is cut and nothing is lost to a cap;
 *   - --metric, --extend, --disjoint, --min-letters and the parent machinery do
 *     not apply and are absent rather than carried over unused.
 *
 * THE POOLS ARE PART OF THE QUESTION and land in the output's stamp: --openers
 * says which words get a row, --seconds which words may BE the second word.  The
 * two shipped variants are both-the-12972 and both-the-2315, and their numbers
 * must never share a table -- the second is a strictly smaller strategy space.
 *
 * --min-grays IS REQUIRED.  It IS the objective: a >= 3 table and a >= 4 table
 * pick different words, so defaulting it would make one silently the other.
 *
 * Build:  see build.sh          Run:  bash solver/run-second-word.sh  (from math/)
 * NEVER a bare ./secondword -- the wrapper sets --out, names the file after the
 * threshold and the pools, and tees a log.
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
#define WORDLEN 5

static int      NG, NA;
static uint8_t *PAT;                 /* NG * NA, row-major */
static char   (*GWORD)[WBUF];
static int8_t   GRAYS[NPAT];         /* grey-tile count of every pattern code */
static int8_t   GREENS[NPAT], YELLOWS[NPAT];
static uint8_t  FIRE[NPAT];          /* does this reply fire the rule? */
#define MAXEXTRA 32
static int      EXG[MAXEXTRA], EXY[MAXEXTRA], NEXTRA;

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

/* A pattern is base 3 with 0 = grey (math/wordle.py), so the grey count is the
 * number of zero trits.  Which end is most significant does not matter to a
 * count, so nothing here depends on the encoding's orientation. */
static void build_grays(void) {
    for (int code = 0; code < NPAT; code++) {
        int c = code, n = 0, g = 0, y = 0;
        for (int i = 0; i < WORDLEN; i++) {
            int t = c % 3;
            if (t == 0) n++; else if (t == 2) g++; else y++;
            c /= 3;
        }
        GRAYS[code] = (int8_t)n;
        GREENS[code] = (int8_t)g;
        YELLOWS[code] = (int8_t)y;
    }
}

/* ---- THE FIRING CONDITION, as a SET OF COMPOSITIONS ----------------------
 * "At least N greys" was the first shape of this rule and is still the common
 * case, but it cannot express the thing that matters: two greys with three
 * YELLOWS is nearly uninformative, while two greys with three GREENS has pinned
 * three positions, and those two replies do not belong on the same side of the
 * line just because they have the same grey count.  So the condition is a set of
 * (greens, yellows) compositions, and --min-grays is sugar for "every
 * composition with at least N greys".  math/secondword.py states it and computes
 * the same set in Python; tools/checksecondword.py diffs the two, label included.
 *
 * THE LABEL IS A FUNCTION OF THE SET, NOT OF HOW IT WAS TYPED: an --fire already
 * covered by the threshold is dropped and the rest are sorted, so two spellings
 * of one rule cannot produce two filenames -- and therefore cannot produce two
 * tables that a reader would have to tell apart by hand. */
static void build_fire(int min_grays, char *label, size_t lsz) {
    for (int i = 1; i < NEXTRA; i++)             /* insertion sort, tiny */
        for (int j = i; j > 0 && (EXG[j - 1] > EXG[j]
                 || (EXG[j - 1] == EXG[j] && EXY[j - 1] > EXY[j])); j--) {
            int t = EXG[j]; EXG[j] = EXG[j - 1]; EXG[j - 1] = t;
            t = EXY[j]; EXY[j] = EXY[j - 1]; EXY[j - 1] = t;
        }
    for (int code = 0; code < NPAT; code++)
        FIRE[code] = GRAYS[code] >= min_grays;
    int n = snprintf(label, lsz, "g%d", min_grays);
    int prev_g = -1, prev_y = -1;
    for (int e = 0; e < NEXTRA; e++) {
        int g = EXG[e], y = EXY[e];
        if (g + y > WORDLEN) {
            fprintf(stderr, "(%d green, %d yellow) is more than %d tiles\n",
                    g, y, WORDLEN);
            exit(1);
        }
        if (WORDLEN - g - y >= min_grays) continue;   /* already fires */
        if (g == prev_g && y == prev_y) continue;     /* a repeat is one entry */
        prev_g = g; prev_y = y;
        for (int code = 0; code < NPAT; code++)
            if (GREENS[code] == g && YELLOWS[code] == y) FIRE[code] = 1;
        n += snprintf(label + n, lsz - (size_t)n, "+%dg%dy", g, y);
    }
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
    if (!data) { fprintf(stderr, "out of memory for the pattern matrix\n"); exit(1); }
    if (fread(data, 1, nbytes, f) != nbytes) { fprintf(stderr, "short read\n"); exit(1); }
    fclose(f);
    return data;
}

static int find_word(char (*list)[WBUF], int n, const char *w) {
    for (int i = 0; i < n; i++) if (!strcmp(list[i], w)) return i;
    return -1;
}

/* Read a word list and turn it into indices into the full guess list, refusing a
 * word that is not a legal guess: a typo'd pool file would otherwise silently
 * shrink the question being asked. */
static int *load_pool(const char *path, int *count, const char *what) {
    char (*rw)[WBUF] = malloc(sizeof(char[WBUF]) * 20000);
    int nr = load_words(path, rw);
    int *out = malloc(sizeof(int) * nr);
    for (int i = 0; i < nr; i++) {
        int g = find_word(GWORD, NG, rw[i]);
        if (g < 0) {
            fprintf(stderr, "--%s word %s is not one of the %d legal guesses\n",
                    what, rw[i], NG);
            exit(1);
        }
        out[i] = g;
    }
    free(rw);
    *count = nr;
    return out;
}

typedef struct {
    int32_t opener, second, nq, nbuckets, ties;
    int64_t score;
} Row;

int main(int argc, char **argv) {
    const char *datadir = "data", *outpath = NULL, *patpath = NULL;
    const char *openpath = NULL, *secondpath = NULL;
    /* The stamp's pool NAMES.  "all" is what an unrestricted run is called --
     * deliberately not the name of a word list, since a bare run has not been
     * told which list it is standing in for, and a reader that asked for a named
     * pool should refuse it rather than assume.  The wrapper always passes both
     * explicitly. */
    const char *opennm = "all", *secondnm = "all";
    int min_grays = -1, threads = 0, limit = 0, printlabel = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--out") && i + 1 < argc) outpath = argv[++i];
        else if (!strcmp(argv[i], "--data") && i + 1 < argc) datadir = argv[++i];
        else if (!strcmp(argv[i], "--patterns") && i + 1 < argc) patpath = argv[++i];
        /* Which words get a ROW.  Pointed at mystery.txt this is the answers-only
         * variant's opener half; the pattern matrix is unchanged, so the score
         * still measures the same answer set. */
        else if (!strcmp(argv[i], "--openers") && i + 1 < argc) openpath = argv[++i];
        /* Which words may BE the second word -- the other half of that variant. */
        else if (!strcmp(argv[i], "--seconds") && i + 1 < argc) secondpath = argv[++i];
        /* The NAMES the stamp records for those two pools, so a reader can refuse
         * a table built over a different question rather than misread it. */
        else if (!strcmp(argv[i], "--openers-name") && i + 1 < argc) opennm = argv[++i];
        else if (!strcmp(argv[i], "--seconds-name") && i + 1 < argc) secondnm = argv[++i];
        else if (!strcmp(argv[i], "--min-grays") && i + 1 < argc) min_grays = atoi(argv[++i]);
        /* --fire G,Y adds one COMPOSITION to the firing condition, on top of the
         * --min-grays threshold: `--min-grays 3 --fire 0,3` fires on everything
         * with three or more greys AND on the three-yellow two-grey reply. */
        else if (!strcmp(argv[i], "--fire") && i + 1 < argc) {
            if (NEXTRA >= MAXEXTRA) {
                fprintf(stderr, "at most %d --fire compositions\n", MAXEXTRA);
                return 1;
            }
            if (sscanf(argv[++i], "%d,%d", &EXG[NEXTRA], &EXY[NEXTRA]) != 2) {
                fprintf(stderr, "--fire takes GREENS,YELLOWS, e.g. --fire 0,3\n");
                return 1;
            }
            NEXTRA++;
        }
        /* Resolve the firing condition and print its canonical name, so the
         * wrapper can name the file without re-deriving the rule in shell. */
        else if (!strcmp(argv[i], "--print-label")) printlabel = 1;
        else if (!strcmp(argv[i], "--threads") && i + 1 < argc) threads = atoi(argv[++i]);
        /* PRICING ONLY: score the first N openers and stop.  The result is a
         * PREFIX of the table, never the table, so the stamp's opener pool is
         * renamed -- a reader asking for the real pool then refuses it instead of
         * running a strategy on a table missing most of its openers. */
        else if (!strcmp(argv[i], "--limit") && i + 1 < argc) limit = atoi(argv[++i]);
        else { fprintf(stderr, "unknown arg: %s\n", argv[i]); return 1; }
    }
    if (!outpath && !printlabel) {
        fprintf(stderr, "secondword needs --out FILE -- a run that prints its "
                        "answer and saves NOTHING is a run lost.\n"
                        "Use the wrapper: bash solver/run-second-word.sh\n");
        return 1;
    }
    if (min_grays < 0) {
        fprintf(stderr, "--min-grays N is REQUIRED: it is the objective, not a "
                        "knob.\nA >= 3 table and a >= 4 table pick different "
                        "words and describe different strategies.\n");
        return 1;
    }
    if (min_grays > WORDLEN) {
        fprintf(stderr, "--min-grays %d is impossible: a reply has %d tiles\n",
                min_grays, WORDLEN);
        return 1;
    }
    char firelabel[128];
    build_grays();
    build_fire(min_grays, firelabel, sizeof firelabel);
    if (printlabel) { printf("%s\n", firelabel); return 0; }

    char path[1024];
    GWORD = malloc(sizeof(char[WBUF]) * 20000);
    snprintf(path, sizeof path, "%s/shared/words/guess.txt", datadir);
    NG = load_words(path, GWORD);
    if (patpath) snprintf(path, sizeof path, "%s", patpath);
    else         snprintf(path, sizeof path, "%s/local/patterns/patterns.npy", datadir);
    int r, c;
    PAT = load_npy(path, &r, &c);
    NA = c;
    if (r != NG) { fprintf(stderr, "pattern rows %d != guesses %d\n", r, NG); return 1; }
    fprintf(stderr, "loaded %d guesses x %d answers\n", NG, NA);

    int nopen = 0, nsec = 0;
    int *openers = openpath ? load_pool(openpath, &nopen, "openers") : NULL;
    int *seconds = secondpath ? load_pool(secondpath, &nsec, "seconds") : NULL;
    if (!openers) {
        openers = malloc(sizeof(int) * NG);
        for (int g = 0; g < NG; g++) openers[nopen++] = g;
    }
    if (!seconds) {
        seconds = malloc(sizeof(int) * NG);
        for (int g = 0; g < NG; g++) seconds[nsec++] = g;
    }
    char openlabel[128];
    if (limit > 0 && limit < nopen) {
        nopen = limit;
        snprintf(openlabel, sizeof openlabel, "%s-limit%d", opennm, limit);
        fprintf(stderr, "*** --limit %d: a PREFIX of the table, for pricing -- "
                        "stamped as pool '%s' so nothing reads it as the table "
                        "***\n", limit, openlabel);
    } else {
        snprintf(openlabel, sizeof openlabel, "%s", opennm);
    }
    fprintf(stderr, "openers: %d (%s)   second words: %d (%s)   fires on: %s\n",
            nopen, openlabel, nsec, secondnm, firelabel);

#ifdef _OPENMP
    if (threads > 0) omp_set_num_threads(threads);
    int nth = omp_get_max_threads();
#else
    int nth = 1;
#endif
    fprintf(stderr, "threads: %d\n", nth);

    Row *rows = malloc(sizeof(Row) * nopen);
    double t0 = now_s(), last = t0;
    int64_t done = 0;

#ifdef _OPENMP
#pragma omp parallel
#endif
    {
        int      *cnt   = calloc(NPAT, sizeof(int));
        int      *touch = malloc(sizeof(int) * NPAT);      /* g1 buckets kept */
        int      *tin   = malloc(sizeof(int) * NPAT);      /* g2 patterns, inner */
        uint16_t *ord   = malloc(sizeof(uint16_t) * NA);   /* qualifying answers */
        int      *rs    = malloc(sizeof(int) * (NPAT + 1));
        int      *rl    = malloc(sizeof(int) * (NPAT + 1));
        int      *fill  = malloc(sizeof(int) * (NPAT + 1));

        /* Every opener costs the same -- nq x nsec, and nq varies only mildly --
         * so a static split is fine; dynamic is kept for the tail. */
#ifdef _OPENMP
#pragma omp for schedule(dynamic, 8)
#endif
        for (int oi = 0; oi < nopen; oi++) {
            int g1 = openers[oi];
            const uint8_t *row1 = PAT + (size_t)g1 * NA;

            /* Bucket the QUALIFYING answers by g1 once, into contiguous runs.
             * Everything below the threshold is dropped here and never seen
             * again: those are the games the rule does not fire in. */
            int nb = 0, nq = 0;
            for (int a = 0; a < NA; a++) {
                if (!FIRE[row1[a]]) continue;
                nq++;
                if (cnt[row1[a]]++ == 0) touch[nb++] = row1[a];
            }
            int acc = 0;
            for (int k = 0; k < nb; k++) {
                rs[k] = acc; rl[k] = cnt[touch[k]]; acc += rl[k];
            }
            for (int k = 0; k < nb; k++) { cnt[touch[k]] = k; fill[k] = rs[k]; }
            for (int a = 0; a < NA; a++) {
                if (!FIRE[row1[a]]) continue;
                ord[fill[cnt[row1[a]]]++] = (uint16_t)a;
            }
            for (int k = 0; k < nb; k++) cnt[touch[k]] = 0;

            int32_t best = -1, ties = 0;
            int64_t best_score = 0;
            /* Nothing qualifies: there is no case to choose a word for, so
             * there is nothing to minimise and the row is left empty. */
            int nloop = nq ? nsec : 0;
            for (int sj = 0; sj < nloop; sj++) {
                int g2 = seconds[sj];
                if (g2 == g1) continue;        /* a repeat cannot split anything */
                const uint8_t *row2 = PAT + (size_t)g2 * NA;
                int64_t ssq = 0;
                for (int k = 0; k < nb; k++) {
                    int s = rs[k], e = s + rl[k], nt = 0;
                    for (int i = s; i < e; i++) {
                        int p = row2[ord[i]];
                        if (cnt[p]++ == 0) tin[nt++] = p;
                    }
                    for (int i = 0; i < nt; i++) {
                        int p = tin[i];
                        int64_t v = cnt[p];
                        ssq += v * v;
                        cnt[p] = 0;
                    }
                }
                /* Ties are REAL -- the objective is an integer sum over a fixed
                 * denominator -- so they are COUNTED, and the winner is the
                 * lowest guess index, the repo's one tie-break.  The pool is
                 * walked in its own order, which need not be index order, so the
                 * `<` on index is explicit rather than implied by arrival. */
                if (best < 0 || ssq < best_score) {
                    best = g2; best_score = ssq; ties = 1;
                } else if (ssq == best_score) {
                    ties++;
                    if (g2 < best) best = g2;
                }
            }

            rows[oi].opener   = g1;
            rows[oi].second   = best;
            rows[oi].score    = best < 0 ? 0 : best_score;
            rows[oi].nq       = nq;
            rows[oi].nbuckets = nb;
            rows[oi].ties     = ties;

#ifdef _OPENMP
#pragma omp atomic
#endif
            done++;
            if ((done & 15) == 0) {
                double n2 = now_s();
                if (n2 - last >= 1.0) {
#ifdef _OPENMP
#pragma omp critical (progress)
#endif
                    {
                        if (n2 - last >= 1.0) {
                            last = n2;
                            double el = n2 - t0, frac = (double)done / nopen;
                            fprintf(stderr, "  %lld/%d openers  %.1f%%  (%.0fs, "
                                    "eta %.1f min)\n", (long long)done, nopen,
                                    100.0 * frac, el,
                                    frac > 0 ? (el / frac - el) / 60.0 : 0.0);
                            fflush(stderr);
                        }
                    }
                }
            }
        }
        free(cnt); free(touch); free(tin); free(ord); free(rs); free(rl); free(fill);
    }

    FILE *f = fopen(outpath, "w");
    if (!f) { fprintf(stderr, "cannot write %s\n", outpath); return 1; }
    fprintf(f, "# secondword: the best PREDETERMINED second word per opener -- "
               "the word minimising the\n# expected number of ANSWERS still "
               "consistent after both, over the cases where the\n# opener's reply "
               "shows at least %d grey tiles.  math/secondword.py states it.\n",
            min_grays);
    fputs("# expected = score / qualifying, and score is an INTEGER sum of "
          "squared joint-bucket sizes,\n# so ties are real ties: `ties` counts "
          "the words attaining the minimum, and the winner\n# among them is the "
          "lowest guess index.  An empty `second` means no answer gives this\n"
          "# opener a firing reply, so there is nothing to choose and the rule "
          "never fires.\n", f);
    fputs("# It is ONE PLY: what is left after two guesses, never what the game "
          "goes on to cost.\n", f);
    fprintf(f, "# settings min_grays=%d fire=%s openers=%s seconds=%s answers=%d "
               "second_pool=%d\n", min_grays, firelabel, openlabel, secondnm,
            NA, nsec);
    fputs("opener,second,expected,score,qualifying,buckets,ties\n", f);
    int64_t noq = 0, tied = 0;
    for (int oi = 0; oi < nopen; oi++) {
        Row *v = &rows[oi];
        if (v->second < 0) {
            noq++;
            fprintf(f, "%s,,,,%d,%d,0\n", GWORD[v->opener], v->nq, v->nbuckets);
            continue;
        }
        if (v->ties > 1) tied++;
        fprintf(f, "%s,%s,%.6f,%lld,%d,%d,%d\n", GWORD[v->opener],
                GWORD[v->second], (double)v->score / (double)v->nq,
                (long long)v->score, v->nq, v->nbuckets, v->ties);
    }
    fclose(f);
    fprintf(stderr, "%d openers in %.1fs -- %lld with no qualifying answer, "
            "%lld with a tied second word\n", nopen, now_s() - t0,
            (long long)noq, (long long)tied);
    fprintf(stderr, "wrote %s\n", outpath);
    return 0;
}
