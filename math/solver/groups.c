/* groups.c -- see groups.h.  One definition of the firing condition, compiled
 * into every solver that has one. */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "groups.h"

int8_t GRAYS[NPAT], GREENS[NPAT], YELLOWS[NPAT];
int8_t NONGRAY[NPAT];
Group  GRP[MAXGROUP];
char   GSPEC[MAXGROUP][64];
int    NGROUP;

static int      EXG[MAXEXTRA], EXY[MAXEXTRA], NEXTRA;
static uint8_t *VPOS;                /* nwords * WORDLEN */
static char   (*WORDS)[WBUF];




/* A pattern is base 3 with 0 = grey (math/wordle.py), so the grey count is the
 * number of zero trits.  Which end is most significant does not matter to a
 * count, so nothing here depends on the encoding's orientation. */
/* Which POSITIONS of each guess word hold a vowel.  A greyed-vowel count is by
 * position, so a doubled vowel grey twice counts twice -- which is what the
 * board shows. */

void groups_build_vpos(char (*words)[WBUF], int nwords) {
    WORDS = words;
    VPOS = malloc((size_t)nwords * WORDLEN);
    for (int g = 0; g < nwords; g++)
        for (int i = 0; i < WORDLEN; i++)
            VPOS[(size_t)g * WORDLEN + i] =
                strchr(VOWELS, words[g][i]) != NULL;
}

/* For one opener, how many GREY tiles sit on a vowel, per pattern code.
 * wordle.py puts position 0 in the MOST significant trit, so this cannot use the
 * repeated %% 3 a count gets away with. */
static void build_gvow(int opener, int8_t *out) {
    const uint8_t *vp = VPOS + (size_t)opener * WORDLEN;
    int pw[WORDLEN];
    pw[WORDLEN - 1] = 1;
    for (int i = WORDLEN - 2; i >= 0; i--) pw[i] = pw[i + 1] * 3;
    for (int code = 0; code < NPAT; code++) {
        int n = 0;
        for (int i = 0; i < WORDLEN; i++)
            if (vp[i] && (code / pw[i]) % 3 == 0) n++;
        out[code] = (int8_t)n;
    }
}

/* For one opener, how many MATCHED tiles (green or yellow, i.e. NON-grey) sit on
 * a vowel of the opener, per pattern code -- the vowels the guess got RIGHT (in
 * the answer), which is the complement of build_gvow over this opener's vowel
 * positions.  Counted by POSITION, y a vowel, so it depends on the opener too. */
static void build_mvow(int opener, int8_t *out) {
    const uint8_t *vp = VPOS + (size_t)opener * WORDLEN;
    int pw[WORDLEN];
    pw[WORDLEN - 1] = 1;
    for (int i = WORDLEN - 2; i >= 0; i--) pw[i] = pw[i + 1] * 3;
    for (int code = 0; code < NPAT; code++) {
        int n = 0;
        for (int i = 0; i < WORDLEN; i++)
            if (vp[i] && (code / pw[i]) % 3 != 0) n++;
        out[code] = (int8_t)n;
    }
}

void groups_build_tiles(void) {
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
        /* WHICH positions were matched, green and yellow alike.  Position 0 is
         * the MOST significant trit (wordle.py), so the bit for position i is
         * read from trit WORDLEN-1-i -- the trap `secondword.py`'s tile_at
         * documents, and the reason this is built here rather than per caller. */
        int mask = 0, cc = code;
        for (int i = WORDLEN - 1; i >= 0; i--) {
            if (cc % 3) mask |= 1 << i;
            cc /= 3;
        }
        NONGRAY[code] = (int8_t)mask;
    }
}

/* ---- THE FIRING CONDITION, as a PARTITION INTO GROUPS --------------------
 * This started as "at least N greys, play this word"; became "at least N greys
 * OR this composition" when two greys with three YELLOWS turned out to be
 * nothing like two greys with three GREENS; and is now the general form: the
 * reply's bucket SELECTS the word.  A separate word for five, four and three
 * greys is `--group e5 --group e4 --group e3`, and the single-word rules are the
 * one-group case, unchanged.
 *
 * A GROUP SPEC is terms joined by '+':  g<N> greys >= N,  e<N> greys == N,
 * <G>g<Y>y that exact composition.  GROUPS MUST BE DISJOINT -- a reply in two
 * groups would have two predetermined words and no rule for choosing -- and
 * anything in no group DECLINES to the follow-up.
 *
 * math/secondword.py builds the same partition and the same canonical label in
 * Python; tools/checksecondword.py diffs the two, label included.  THE LABEL IS
 * A FUNCTION OF THE PARTITION, not of how it was typed: the specs are sorted,
 * so two spellings of one rule cannot make two filenames -- and therefore cannot
 * make two tables a reader would have to tell apart by hand. */

static int cmp_spec(const void *a, const void *b) {
    return strcmp((const char *)a, (const char *)b);
}

static int atom_key(const Atom *a) {
    /* ONE ENTRY PER KIND -- a new atom must extend this or `order[a->kind]`
     * reads off the end, which is exactly what `nz` did: the term came out as
     * `nz01_e3` instead of `e3_nz01` because the key was garbage. */
    static const int order[6] = {0, 1, 2, 3, 4, 5};
    return order[a->kind] * 1000 + a->a * 10 + a->b;
}

static int cmp_atom(const void *x, const void *y) {
    return atom_key((const Atom *)x) - atom_key((const Atom *)y);
}

static int cmp_term(const void *x, const void *y) {
    const Term *a = x, *b = y;
    return a->key - b->key;
}

static int parse_atom(const char *text, Atom *out) {
    size_t len = strlen(text);
    int n, g, y;
    snprintf(out->text, sizeof out->text, "%s", text);
    if (text[0] == 'g' && len > 1 && strspn(text + 1, "0123456789") == len - 1) {
        out->kind = 0; out->a = atoi(text + 1); out->b = 0; return 1;
    }
    if (text[0] == 'e' && len > 1 && strspn(text + 1, "0123456789") == len - 1) {
        out->kind = 1; out->a = atoi(text + 1); out->b = 0; return 1;
    }
    if (text[0] == 'm' && text[1] == 'v' && len > 2
            && strspn(text + 2, "0123456789") == len - 2) {
        out->kind = 4; out->a = atoi(text + 2); out->b = 0; return 1;
    }
    if (text[0] == 'v' && len > 1 && strspn(text + 1, "0123456789") == len - 1) {
        out->kind = 3; out->a = atoi(text + 1); out->b = 0; return 1;
    }
    if (text[0] == 'n' && text[1] == 'z' && len > 2
            && strspn(text + 2, "01234") == len - 2) {
        int mask = 0, ok = 1;
        for (size_t i = 2; i < len; i++) {
            int bit = 1 << (text[i] - '0');
            if (mask & bit) ok = 0;            /* a repeated position is a typo */
            mask |= bit;
        }
        if (!ok) return 0;
        out->kind = 5; out->a = mask; out->b = 0;
        /* CANONICAL TEXT: the digits ascending, so `nz20` and `nz02` are one
         * group with one name rather than two spellings of it. */
        char d[WORDLEN + 3];
        size_t k = 0;
        d[k++] = 'n'; d[k++] = 'z';
        for (int i = 0; i < WORDLEN; i++)
            if (mask & (1 << i)) d[k++] = (char)('0' + i);
        d[k] = 0;
        snprintf(out->text, sizeof out->text, "%s", d);
        return 1;
    }
    if (sscanf(text, "%dg%dy", &g, &y) == 2 && g + y <= WORDLEN) {
        out->kind = 2; out->a = g; out->b = y; return 1;
    }
    (void)n;
    return 0;
}

/* Parse a group spec into its TERMS and its canonical text.  Atoms sort within a
 * term and terms within a group, so `v1_e3` and `e3_v1` are one name; a repeated
 * atom or term is refused.  No mask is built here: a v<N> atom counts greyed
 * VOWELS and so depends on the opener's letters. */
static int parse_group(const char *spec, Group *out) {
    out->nterm = 0;
    const char *p = spec;
    while (*p) {
        const char *end = strchr(p, '+');
        size_t len = end ? (size_t)(end - p) : strlen(p);
        if (len == 0 || len >= sizeof out->t[0].text || out->nterm >= 8) return 0;
        char text[48];
        memcpy(text, p, len); text[len] = 0;
        Term *t = &out->t[out->nterm];
        t->natom = 0;
        char *save = NULL, *tok = strtok_r(text, "_", &save);
        while (tok) {
            if (t->natom >= 6) return 0;
            if (!parse_atom(tok, &t->at[t->natom])) return 0;
            for (int i = 0; i < t->natom; i++)
                if (!strcmp(t->at[i].text, t->at[t->natom].text)) return 0;
            t->natom++;
            tok = strtok_r(NULL, "_", &save);
        }
        if (!t->natom) return 0;
        qsort(t->at, (size_t)t->natom, sizeof t->at[0], cmp_atom);
        size_t n = 0;
        for (int i = 0; i < t->natom; i++)
            n += (size_t)snprintf(t->text + n, sizeof t->text - n, "%s%s",
                                  i ? "_" : "", t->at[i].text);
        t->key = atom_key(&t->at[0]);
        for (int i = 0; i < out->nterm; i++)
            if (!strcmp(out->t[i].text, t->text)) return 0;   /* repeated term */
        out->nterm++;
        p = end ? end + 1 : p + len;
    }
    if (!out->nterm) return 0;
    qsort(out->t, (size_t)out->nterm, sizeof out->t[0], cmp_term);
    size_t n = 0;
    for (int i = 0; i < out->nterm; i++)
        n += (size_t)snprintf(out->text + n, sizeof out->text - n, "%s%s",
                              i ? "+" : "", out->t[i].text);
    return 1;
}

/* One group's mask FOR ONE OPENER.  `gvow` is that opener's greyed-vowel count
 * per code; the rest of the atoms are opener-independent. */
void groups_mask_for(const Group *g, const int8_t *gvow,
                           const int8_t *mvow, uint8_t *out) {
    for (int c = 0; c < NPAT; c++) {
        int hit = 0;
        for (int ti = 0; ti < g->nterm && !hit; ti++) {
            int all = 1;
            for (int ai = 0; ai < g->t[ti].natom && all; ai++) {
                const Atom *a = &g->t[ti].at[ai];
                switch (a->kind) {
                case 0: all = GRAYS[c] >= a->a; break;
                case 1: all = GRAYS[c] == a->a; break;
                case 2: all = GREENS[c] == a->a && YELLOWS[c] == a->b; break;
                case 3: all = gvow[c] == a->a; break;
                case 4: all = mvow[c] == a->a; break;    /* matched vowels */
                default: all = NONGRAY[c] == a->a; break; /* kind 5: which tiles */
                }
            }
            hit = all;
        }
        out[c] = (uint8_t)hit;
    }
}

/* Resolve the groups given on the command line -- plus the --min-grays/--fire
 * sugar, which is the one-group case -- into GFIRE/GSPEC and the label. */
void groups_resolve(int min_grays, char *label, size_t lsz) {
    if (NGROUP == 0) {                          /* the sugar: one group */
        char spec[64];
        int n = snprintf(spec, sizeof spec, "g%d", min_grays);
        for (int i = 1; i < NEXTRA; i++)        /* insertion sort, tiny */
            for (int j = i; j > 0 && (EXG[j - 1] > EXG[j]
                     || (EXG[j - 1] == EXG[j] && EXY[j - 1] > EXY[j])); j--) {
                int t = EXG[j]; EXG[j] = EXG[j - 1]; EXG[j - 1] = t;
                t = EXY[j]; EXY[j] = EXY[j - 1]; EXY[j - 1] = t;
            }
        int prev_g = -1, prev_y = -1;
        for (int e = 0; e < NEXTRA; e++) {
            int g = EXG[e], y = EXY[e];
            if (g + y > WORDLEN) {
                fprintf(stderr, "(%d green, %d yellow) is more than %d tiles\n",
                        g, y, WORDLEN);
                exit(1);
            }
            if (WORDLEN - g - y >= min_grays) continue;   /* already covered */
            if (g == prev_g && y == prev_y) continue;     /* a repeat is one */
            prev_g = g; prev_y = y;
            n += snprintf(spec + n, sizeof spec - (size_t)n, "+%dg%dy", g, y);
        }
        snprintf(GSPEC[NGROUP++], sizeof GSPEC[0], "%s", spec);
    }
    /* CANONICALISE EACH SPEC FIRST, THEN SORT.  Sorting the typed text would
     * order the groups differently from Python, which sorts what the specs MEAN
     * -- and the label is what names the file. */
    for (int i = 0; i < NGROUP; i++) {
        if (!parse_group(GSPEC[i], &GRP[i])) {
            fprintf(stderr, "cannot read the group '%s': an atom is g<N>, e<N>, "
                    "v<N>, mv<N> or <G>g<Y>y, joined by _ within a term and by + "
                    "between terms\n", GSPEC[i]);
            exit(1);
        }
        snprintf(GSPEC[i], sizeof GSPEC[0], "%s", GRP[i].text);
    }
    qsort(GSPEC, (size_t)NGROUP, sizeof GSPEC[0], cmp_spec);
    int kept = 0;
    for (int i = 0; i < NGROUP; i++) {
        if (i && !strcmp(GSPEC[i], GSPEC[kept - 1])) continue;   /* a repeat */
        /* compact in place; a same-size buffer copy is memmove, not a %s
         * snprintf -- which gcc flags as a -Wformat-truncation false positive */
        if (kept != i) memmove(GSPEC[kept], GSPEC[i], sizeof GSPEC[0]);
        parse_group(GSPEC[kept], &GRP[kept]);
        kept++;
    }
    NGROUP = kept;
    size_t n = 0;
    for (int i = 0; i < NGROUP; i++)
        n += (size_t)snprintf(label + n, lsz - n, "%s%s", i ? "." : "", GSPEC[i]);

    /* WITHOUT A VOWEL ATOM the masks are the same for every opener, so the
     * structural checks can be made HERE -- before anything is loaded -- rather
     * than in the opener loop.  With one they cannot: a v<N> group means
     * different replies for different openers, and disjointness is then a fact
     * about the opener.  Python splits it the same way, so both refuse the same
     * conditions at the same moment. */
    int has_v = 0;
    for (int i = 0; i < NGROUP && !has_v; i++)
        for (int t = 0; t < GRP[i].nterm && !has_v; t++)
            for (int a = 0; a < GRP[i].t[t].natom && !has_v; a++)
                if (GRP[i].t[t].at[a].kind == 3 || GRP[i].t[t].at[a].kind == 4)
                    has_v = 1;                 /* greyed OR matched vowels: per opener */
    if (!has_v) {
        int8_t zero[NPAT];
        uint8_t m[MAXGROUP][NPAT], covered[NPAT];
        for (int c = 0; c < NPAT; c++) { zero[c] = 0; covered[c] = 0; }
        for (int i = 0; i < NGROUP; i++) {
            groups_mask_for(&GRP[i], zero, zero, m[i]);
            for (int j = 0; j < i; j++)
                for (int c = 0; c < NPAT; c++)
                    if (m[i][c] && m[j][c]) {
                        fprintf(stderr, "the groups '%s' and '%s' overlap: a reply "
                                "in both would have two predetermined words and no "
                                "rule for choosing\n", GSPEC[j], GSPEC[i]);
                        exit(1);
                    }
            for (int c = 0; c < NPAT; c++) covered[c] |= m[i][c];
        }
        int all = 1;
        for (int c = 0; c < NPAT; c++) all &= covered[c];
        if (all) {
            fprintf(stderr, "this condition fires on EVERY reply, which is a "
                    "blind two-word opening rather than a rule that chooses when "
                    "to commit\n");
            exit(1);
        }
    }
}



/* ---- the public surface ------------------------------------------------- */

void groups_add(const char *spec) {
    if (NGROUP >= MAXGROUP) {
        fprintf(stderr, "at most %d groups\n", MAXGROUP);
        exit(1);
    }
    snprintf(GSPEC[NGROUP++], sizeof GSPEC[0], "%s", spec);
}

void groups_add_fire(int greens, int yellows) {
    if (NEXTRA >= MAXEXTRA) {
        fprintf(stderr, "at most %d --fire compositions\n", MAXEXTRA);
        exit(1);
    }
    EXG[NEXTRA] = greens;
    EXY[NEXTRA] = yellows;
    NEXTRA++;
}

/* Does any group key on the OPENER'S LETTERS?  A condition of grey counts and
 * compositions alone has one mask for every opener, which is what lets a caller
 * build it once; a v<N> or mv<N> atom makes it per opener. */
int groups_opener_dependent(void) {
    for (int i = 0; i < NGROUP; i++)
        for (int t = 0; t < GRP[i].nterm; t++)
            for (int a = 0; a < GRP[i].t[t].natom; a++)
                if (GRP[i].t[t].at[a].kind == 3 || GRP[i].t[t].at[a].kind == 4)
                    return 1;
    return 0;
}

/* THE --by-grays CROSS PRODUCTS, defined ONCE.  The two splits have DIFFERENT
 * bounds and it is not obvious which from the flag name alone, which is exactly
 * why this cannot live in two places:
 *
 *   --split-vowels          a reply with n greys has at most n GREYED vowels,
 *                           so j runs 0..n
 *   --split-matched-vowels  it has 5-n MATCHED tiles, so j runs 0..5-n -- and at
 *                           n = 5 there are none at all, so that grey count
 *                           stays the single group `e5` rather than `e5_mv0`
 *
 * Combinations an opener cannot produce (mv2 against a one-vowel word) are
 * simply groups that never fire.  Getting the bound wrong does not fail: it
 * produces a DIFFERENT CANONICAL LABEL for the same strategy, so one solver's
 * table stops matching the other's name. */
void groups_add_by_grays(int from, int split_v, int split_mv, int split_nz) {
    for (int n = WORDLEN; n >= from; n--) {
        char spec[24];
        /* WHICH tiles were matched: one group per SET of non-grey positions of
         * the right size.  n greys leaves WORDLEN-n matched, so e5 has the one
         * empty set and needs no atom, e4 has 5 singletons and e3 has 10 pairs
         * -- 16 groups at --by-grays 3, against 3 without the split. */
        if (split_nz) {
            int want = WORDLEN - n;
            if (want == 0) {
                snprintf(spec, sizeof spec, "e%d", n);
                groups_add(spec);
                continue;
            }
            for (int mask = 0; mask < (1 << WORDLEN); mask++) {
                int pop = 0;
                for (int i = 0; i < WORDLEN; i++) if (mask & (1 << i)) pop++;
                if (pop != want) continue;
                int k = snprintf(spec, sizeof spec, "e%d_nz", n);
                for (int i = 0; i < WORDLEN; i++)
                    if (mask & (1 << i)) k += snprintf(spec + k, sizeof spec - k, "%d", i);
                groups_add(spec);
            }
            continue;
        }
        if (!split_v && !split_mv) {
            snprintf(spec, sizeof spec, "e%d", n);
            groups_add(spec);
            continue;
        }
        int hi = split_mv ? WORDLEN - n : n;
        if (hi == 0) {                     /* nothing to split on: one group */
            snprintf(spec, sizeof spec, "e%d", n);
            groups_add(spec);
            continue;
        }
        for (int j = 0; j <= hi; j++) {
            snprintf(spec, sizeof spec, "e%d_%sv%d", n, split_mv ? "m" : "", j);
            groups_add(spec);
        }
    }
}

void groups_vowel_counts(int opener, int8_t *gvow, int8_t *mvow) {
    build_gvow(opener, gvow);
    build_mvow(opener, mvow);
}
