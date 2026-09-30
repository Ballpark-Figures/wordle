/* groups.h -- the FIRING CONDITION, shared by every second-word solver.
 *
 * ONE DEFINITION OF WHAT A GROUP IS.  `secondword` picks each group's word by a
 * one-ply proxy and `secondexact` solves for it exactly, but they must agree
 * exactly on WHICH REPLIES each group covers and on what the partition is
 * CALLED -- otherwise a table written by one and read by the other means two
 * different strategies under one filename.  So the grammar, the canonical label
 * and the per-opener masks live here and nowhere else.
 *
 * THE GRAMMAR.  An ATOM is one condition on a reply; a TERM is a CONJUNCTION of
 * atoms (joined by `_`); a GROUP is a UNION of terms (joined by `+`); a
 * PARTITION is groups joined by `.`.  So `e3_v1` is "exactly three greys AND
 * exactly one greyed vowel".
 *
 *     g<N>        greys >= N
 *     e<N>        greys == N exactly
 *     v<N>        exactly N GREYED vowels        (depends on the opener)
 *     mv<N>       exactly N MATCHED vowels       (depends on the opener)
 *     <G>g<Y>y    exactly that (greens, yellows) composition
 *
 * Y IS ALWAYS A VOWEL.  One vowel set, not a flag, stamped into every table.
 *
 * THE VOWEL ATOMS DEPEND ON THE OPENER'S LETTERS, so a group's MASK is built per
 * opener (`groups_mask_for`) while its SPEC and the label are opener-independent
 * (`groups_resolve`).  A condition with no vowel atom has the same mask for
 * every opener, which is what lets the callers check disjointness once up front.
 */
#ifndef GROUPS_H
#define GROUPS_H

#include <stdint.h>
#include <stddef.h>

#define NPAT  243
#define WBUF  8
#define WORDLEN 5
#define VOWELS "aeiouy"
#define MAXGROUP 32
#define MAXEXTRA 32

typedef struct { int kind, a, b; char text[16]; } Atom;
typedef struct { int natom; Atom at[6]; int key; char text[48]; } Term;
typedef struct { int nterm; Term t[8]; char text[64]; } Group;

extern int8_t GRAYS[NPAT], GREENS[NPAT], YELLOWS[NPAT];
extern int8_t NONGRAY[NPAT];        /* bitmask of the non-grey POSITIONS */
extern Group  GRP[MAXGROUP];
extern char   GSPEC[MAXGROUP][64];
extern int    NGROUP;

/* OPT-IN: accept a partition covering EVERY reply (e.g. e0.e1.e2.e3.e4.e5).
 * Off by default, and only `secondexact --every-reply` sets it: with a word per
 * grey count the reply still CHOOSES the word, so it is not the blind two-word
 * opening the refusal exists to catch.  secondword never sets it. */
extern int    GROUPS_EVERY_REPLY;

/* Call once, in this order, before anything else here. */
void groups_build_tiles(void);
void groups_build_vpos(char (*words)[WBUF], int nwords);

/* Add a group spec, or a --fire composition for the one-group sugar. */
void groups_add(const char *spec);
void groups_add_fire(int greens, int yellows);

/* The --by-grays cross products: e5..e<from>, optionally crossed with the greyed
 * or matched vowel count.  The two splits have different bounds (see groups.c),
 * which is why this is here and not in each caller. */
void groups_add_by_grays(int from, int split_v, int split_mv, int split_nz);

/* Canonicalise everything added (plus the --min-grays sugar when no --group was
 * given), fill GRP/GSPEC/NGROUP and write the canonical label.  Refuses an
 * unreadable spec, a redundant term, an overlap and a condition covering every
 * reply -- the last two only when no vowel atom makes them opener-dependent. */
void groups_resolve(int min_grays, char *label, size_t lsz);

/* Does any group key on the opener's letters?  If not, one mask serves them all. */
int groups_opener_dependent(void);

/* One group's mask against one opener, and the two per-opener vowel counts it
 * needs.  `gvow`/`mvow` are NPAT scratch arrays the caller owns. */
void groups_vowel_counts(int opener, int8_t *gvow, int8_t *mvow);
void groups_mask_for(const Group *g, const int8_t *gvow, const int8_t *mvow,
                     uint8_t *out);

#endif
