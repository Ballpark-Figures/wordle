#!/bin/bash
# Sweep every OPENER through single-board wordle games, attached, live output.
#
#     # STAGE 1: a wide screen, every one of the 12972 openers, 100 games each
#     bash solver/run-wordle-sweep.sh --fallback answer -t 100          # from math/
#     bash solver/run-wordle-sweep.sh --fallback guess  -t 100
#
#     # ... or the top N two-word openings of an existing ranking, same cascade
#     bash solver/run-wordle-sweep.sh --fallback answer -t 100 \
#         --openings-from data/shared/singletons/pair_singletons.csv --top 10000
#
#     # ... or that rule with the opening ABANDONED once 2 or fewer words remain
#     bash solver/run-wordle-sweep.sh --fallback answer -t 100 --pair-adaptive 2 \
#         --openings-from data/shared/singletons/pair_singletons.csv --top 10000 \
#         --both-orders
#
#     # STAGE 2: re-run only the words the screen left standing, at a FRESH seed
#     bash solver/run-wordle-sweep.sh --fallback answer -t 1000 --seed 1 \
#         --shortlist-from data/shared/wordlesim/sweep_answer_t100_s0_guess.csv
#
# WHAT THIS MEASURES:
#
#   Every word of the list opens -t games.  The word is played on turn 1 and the
#   FOLLOW-UP plays the rest -- a random word still consistent with every reply,
#   drawn from the 2315 answers (--fallback answer) or the 12972 legal guesses
#   (--fallback guess).  Each word gets a mean number of guesses AND a win rate
#   (the fraction of games finished within six), each with a standard error.
#
#   THE FOLLOW-UP IS PART OF THE QUESTION.  "Which opener is best" has a different
#   answer under each, because the opener is feeding a different player.  So it is
#   required, it is in the filename, and the two sweeps are two different screens.
#   The hidden answer is drawn from the 2315 either way.
#
#   COMMON RANDOM NUMBERS: every opener faces the IDENTICAL -t answers (the draw
#   stream is re-seeded per word and kept separate from the follow-up's pick
#   stream), so differences between words are far less noisy than their individual
#   standard errors suggest.  A sweep cell and a run-wordle-sim.sh run at the same
#   seed are therefore different samples and will not match to the last digit.
#
# TWO-WORD (OR LONGER) OPENINGS: --openings-from RANKING.csv --top N takes the top
# N openings off an existing ranking and sweeps those, with the same cascade after.
# The words are played BLIND in order, so the second is played even when the first
# already narrowed the answer to one -- that is what makes a multi-word opening a
# bet.  A game the FIRST word wins ends there, so no opening is charged for a guess
# after the answer is found.
#
#   IT IS A SCREEN OF A RANKING BUILT FOR A DIFFERENT QUESTION.  84,129,906 pairs
#   cannot be simulated, so a pair run examines the head of
#   data/shared/singletons/pair_singletons.csv, which ranks pairs by how many
#   answers a blind opening isolates to a SINGLETON.  That ranking is exhaustive
#   (its head is exact), but it is not this objective: a pair below --top is never
#   examined at all, and nothing here shows the two agree inside it.  Report such a
#   run as "the best of the N screened", NEVER "the best pair".
#
# --pair-adaptive N ABANDONS THE OPENING once the follow-up is down to N or fewer
# words, and it is the SAME RULE the exact solver already carries
# (optturns --pair-list --pair-adaptive N; math/data/shared/PAIRS.md states it and
# holds the exact results).  N = 0 is pure blind, N = 1 names the one survivor,
# N = 2 settles a two-way split by naming one -- which costs 1.5 guesses on
# average against the blind word's 2, so it is a strict gain per bucket.
#
#   N IS PART OF THE OBJECTIVE, not a knob: 0, 1 and 2 are three different games
#   whose numbers are not comparable, so N is in the filename.  PAIRS.md explains
#   why it stops being interesting at 3 (three named in order cost 6, and so does
#   a perfect three-way split).
#
#   NOT UNDER --rank win_rate: the chooser minimises expected GUESSES, which is
#   the wrong criterion there, so a win-rate run takes the ranking file's own
#   ordering unless --best-order is passed explicitly.  An arbitrary ordering that
#   is known to be arbitrary beats one optimised for a different question.
#
#   ORDER MATTERS UNDER IT, and the default answer is to work out the BEST
#   ordering of each set exactly before any games are played
#   (tools/order_openings.py) and sweep only that one -- half the work on pairs, a
#   sixth on triples, and nothing given up, because the orderings of a set differ
#   only where the switch fires and every one of those cases has a closed-form
#   cost at N <= 2.  --all-orders sweeps them all instead, which is how that claim
#   is checked.  The old note follows, and still says why doing neither is wrong:
#
#   ORDER MATTERS UNDER IT, which is the whole reason --both-orders exists.  A
#   blind opening's partition cannot depend on play order, so the pair rankings
#   enumerate each pair ONCE; this rule keys on what the FIRST word alone leaves,
#   so `a b` and `b a` are different strategies.  PAIRS.md measured it: the
#   winning pair never moved with N, but the winning ORDER did.  Starting a
#   cascade with --pair-adaptive and without --both-orders is therefore REFUSED --
#   it would examine one ordering of each pair and never say so.
#
#   The COUNT is the follow-up's own: live answers under --fallback answer, live
#   legal words under --fallback guess.  That is the one place this differs from
#   the exact solver, which only ever counts answers -- a player drawing from the
#   12972 cannot know that two ANSWERS remain.
#
# THE TRIAL LADDER: 100, 200, 300, 500, 1000, 2000, 3000, 5000, ... (user's call,
# 2026-09-08).  Give -t on the first pass; on a --shortlist-from pass, OMIT it and
# the wrapper takes the next rung above the source sweep's own -t, and the next
# SEED above its seed.  Both are echoed and both are in the filename, so a derived
# run says exactly what it did.  Deriving them is not a convenience: passing the
# source's seed again would replay the very games that chose the shortlist, and
# the 1-2-3-5 ladder narrows the field in smaller steps than a straight x10, which
# is what a screen that keeps 95% of its field at t=100 actually needs.  Pass -t
# or --seed explicitly to override either.
#
# THE HEAD OF A SWEEP IS A SHORTLIST, NOT A WINNER.  With 12972 words at -t games
# each, the best-looking mean belongs to whichever word drew the kindest sample,
# and at t=100 that noise dwarfs one word's standard error.  The sound use is
# staged: screen wide and cheap, cut a generous shortlist, re-run the survivors
# larger and at a fresh seed, repeat.  A word leading every stage is a finding.
#
#   --shortlist-from SWEEP.csv does the next stage in one command: it cuts a word
#   list from that sweep (--se N standard errors of the best word's, DEFAULT 5;
#   or --shortlist-top N) and sweeps only those words.  USE A FRESH --seed WITH
#   IT: the draw stream is seeded per word, so stage 2 at the same seed replays
#   stage 1's games as its first -t, re-using the sample that chose the shortlist.
#   The wrapper warns.  It REFUSES a shortlist cut from a sweep run under the
#   OTHER follow-up, which would screen one player and test another.
#
# TWO NUMBERS, SO TWO POSSIBLE SHORTLISTS.  --shortlist-value mean (the default,
# lower is better) or win_rate (higher is better) says which column the cut ranks
# on; they need not agree.  It lands in the shortlist's name, so a stage-2 file
# always records which screen chose its words.
#
# PROGRESS PRINTING TIGHTENS AS THE FIELD NARROWS, one rung per pass:
#
#   pass     1    2    3    4    5    6    7    8   9+
#   every  100   50   30   20   10    5    3    2    1  opening(s)
#
# The pass is read off the source sweep's own name -- each one is a shortlist of
# the one before, so the nesting counts them -- and --progress overrides it.  It
# gates a print only, so it changes neither the games nor the filename.
#
# USE THIS RATHER THAN CALLING tools/wordle_sweep.py DIRECTLY.  It sets --out so
# the rows outlive the terminal, names the file after every parameter that defines
# the sweep, and tees a log.  The sweep is RESUMABLE per word, so a Ctrl-C costs
# at most the word in flight and re-running the same command picks up where it
# stopped.
#
# WHY THE DEFAULT CUT IS 5 STANDARD ERRORS (user's call, 2026-09-08).  It started
# at 10, multiwordle's default, and MEASURED on the first pass that was too wide to
# screen: at t=100 a word's standard error is ~0.10, so ten of them span a full
# guess and the cut kept 12367 of 12972 words under the answer follow-up (12911
# under guess).  5 SE keeps the net generous while actually narrowing the field.
# The cut is in every filename, so stages cut differently can never be confused.
# NOTE this is the WORDLE wrapper's default; multiwordle's wrapper keeps its own
# 10, and tools/sweep_shortlist.py -- shared by both -- is unchanged.  Each wrapper
# carries a default a human reads, rather than a shared one that moves under them.
#
# Each (follow-up, t, seed, word list) is a different sweep and gets its own file.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

T=""
SEEDGIVEN=0
FALLBACK=""
SEED=0
WORDS="guess"
LIMIT=""
WIN=6
PROGRESS=""
SHORTFROM=""
# 5 standard errors: generous, but narrow enough to screen.  See the note above.
SHORTSE=5
SHORTTOP=""
SHORTVALUE="mean"
OPENFROM=""
OPENTOP=""
RANK=""
BOTHORDERS=0
ALLORDERS=0
BESTORDER=-1        # -1 = decide from --pair-adaptive; 0/1 = the user said so
ADAPT=0
SECONDFROM=""
DRYRUN=0
ROOT=""
PASSNO=1
# Which pass this is; a run with no --shortlist-from is the first.
STAGE=1

while [ $# -gt 0 ]; do
    case "$1" in
        -t|--trials)        T="$2";          shift 2 ;;
        --fallback)         FALLBACK="$2";   shift 2 ;;
        --seed)             SEED="$2"; SEEDGIVEN=1; shift 2 ;;
        --words)            WORDS="$2";      shift 2 ;;
        --limit)            LIMIT="$2";      shift 2 ;;
        --win-within)       WIN="$2";        shift 2 ;;
        --progress)         PROGRESS="$2";   shift 2 ;;
        --shortlist-from)   SHORTFROM="$2";  shift 2 ;;
        --se)               SHORTSE="$2";    shift 2 ;;
        --shortlist-top)    SHORTTOP="$2";   shift 2 ;;
        --shortlist-value)  SHORTVALUE="$2"; shift 2 ;;
        --openings-from)    OPENFROM="$2";   shift 2 ;;
        --top)              OPENTOP="$2";    shift 2 ;;
        --both-orders)      BOTHORDERS=1;    shift 1 ;;
        --all-orders)       ALLORDERS=1;     shift 1 ;;
        --best-order)       BESTORDER=1;     shift 1 ;;
        --no-best-order)    BESTORDER=0;     shift 1 ;;
        --pair-adaptive)    ADAPT="$2";      shift 2 ;;
        --second-from)      SECONDFROM="$2"; shift 2 ;;
        --rank)             RANK="$2";       shift 2 ;;
        --dry-run)          DRYRUN=1;        shift 1 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$T" in
    '') ;;      # may be derived from --shortlist-from below
    *[!0-9]*|0) echo "-t must be a positive number (games per word)" >&2; exit 1 ;;
esac

# The next rung of the 1-2-3-5 ladder strictly above $1.
next_t() {
    d=100
    while [ "$d" -le 100000000 ]; do
        for m in 1 2 3 5; do
            v=$((m * d))
            if [ "$v" -gt "$1" ]; then echo "$v"; return; fi
        done
        d=$((d * 10))
    done
    echo $(($1 * 10))
}
case "$FALLBACK" in
    answer|guess) ;;
    '') echo "--fallback is required: 'answer' or 'guess', which random word the" >&2
        echo "  opener hands the rest of the game to.  It is part of the question." >&2
        exit 1 ;;
    *) echo "--fallback must be 'answer' or 'guess'" >&2; exit 1 ;;
esac
case "$SEED" in
    ''|*[!0-9]*) echo "--seed must be a non-negative number" >&2; exit 1 ;;
esac
case "$ADAPT" in
    ''|*[!0-9]*) echo "--pair-adaptive must be a non-negative number of words" >&2
                 exit 1 ;;
esac
# --second-from names a strategy, so it is validated here and lands in the stem.
# It is REFUSED alongside --pair-adaptive: both are rules for the second word,
# and whatever the combination would mean it is a THIRD strategy needing its own
# name.  The threshold comes off the table's OWN stamp rather than being retyped
# -- one owner for the objective, and a table that cannot say what it is gets
# refused by tools/secondword.py before any games are played.
MINGRAYS=0
if [ -n "$SECONDFROM" ]; then
    if [ "$ADAPT" != 0 ]; then
        echo "--second-from and --pair-adaptive are two different rules for the" >&2
        echo "  second word; pick one." >&2
        exit 1
    fi
fi
# ONE FLAG, ONE MEANING.  Ranking by win rate and CUTTING by win rate are the
# same decision -- a cascade that cut on one and reported the other would be
# neither -- so --rank sets both, and it is in the stem because a win-rate
# cascade and a mean cascade off the same root are two different experiments.
case "$RANK" in
    ''|mean) RANK=mean ;;
    win_rate) SHORTVALUE=win_rate ;;
    *) echo "--rank must be 'mean' or 'win_rate'" >&2; exit 1 ;;
esac
case "$SHORTVALUE" in
    mean|win_rate) ;;
    *) echo "--shortlist-value must be 'mean' or 'win_rate'" >&2; exit 1 ;;
esac

cd "$MATH" || exit 1

# -t is required on a FIRST pass; a later pass derives it from its source.
if [ -z "$T" ] && [ -z "$SHORTFROM" ]; then
    echo "-t is required on a first pass (games per opening); a --shortlist-from" >&2
    echo "  pass may omit it and take the next rung of the 1-2-3-5 ladder." >&2
    exit 1
fi

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }
[ -f data/local/patterns/patterns.npy ] || {
    echo "no data/local/patterns/patterns.npy -- run '$PY build_patterns.py' first" >&2
    exit 1; }
if [ "$FALLBACK" = guess ]; then
    [ -f data/local/patterns/patterns_full.npy ] || {
        echo "the guess follow-up needs the square guess x guess matrix." >&2
        echo "  Build it with '$PY build_patterns.py --full' (~18s, 168 MB)." >&2
        exit 1; }
fi

OUTDIR=data/shared/wordlesim
LOC=data/local/wordlesim
mkdir -p "$OUTDIR" "$LOC"

if [ -n "$OPENFROM" ]; then
    [ -z "$SHORTFROM" ] || {
        echo "--openings-from starts a new cascade; --shortlist-from continues one." >&2
        echo "  Pass only one." >&2; exit 1; }
    [ "$WORDS" = "guess" ] || {
        echo "--openings-from replaces --words; pass only one" >&2; exit 1; }
    [ -f "$OPENFROM" ] || { echo "no such ranking: $OPENFROM" >&2; exit 1; }
    case "$OPENTOP" in
        ''|*[!0-9]*|0) echo "--openings-from needs --top N: how much of the" >&2
                       echo "  ranking to examine.  Everything below N is never" >&2
                       echo "  looked at, so the number is part of the result." >&2
                       exit 1 ;;
    esac
    # ORDER.  A ranking lists each SET once, correctly for a blind opening.  Under
    # an adaptive rule each ordering is its own strategy, and there are three
    # honest things to do about it, all of them explicit:
    #
    #   --best-order  (the default when adaptive)  work out the best ordering of
    #                 each set EXACTLY, before any games, and sweep only that one.
    #                 tools/order_openings.py explains why that is exact rather
    #                 than a screen; it costs a pair sweep half and a triple sweep
    #                 five sixths of its work, with nothing given up.
    #   --all-orders  sweep every ordering (2 for a pair, 6 for a triple).  The
    #                 slow way, and the way to CHECK the fast one.
    #   --both-orders the pair-only spelling of --all-orders, kept because the
    #                 committed pair runs were named with it.
    #
    # Sweeping one arbitrary ordering is the option NOT offered: it would examine
    # half the strategies and say nothing about which half.
    OPENFLAGS="--from $OPENFROM --top $OPENTOP"
    LISTNAME="openings_$(basename "$OPENFROM" .csv)_top${OPENTOP}"
    if [ "$BOTHORDERS" = 1 ] || [ "$ALLORDERS" = 1 ]; then
        BESTORDER=0
        if [ "$ALLORDERS" = 1 ]; then
            OPENFLAGS="$OPENFLAGS --all-orders"; LISTNAME="${LISTNAME}_allorders"
        else
            OPENFLAGS="$OPENFLAGS --both-orders"; LISTNAME="${LISTNAME}_bothorders"
        fi
    elif [ "$BESTORDER" = -1 ]; then
        # not asked for either way: order only earns the work when it can matter,
        # and only when the chooser is answering the question being asked.
        #
        # NOT UNDER --rank win_rate (user's call, 2026-09-08).  order_openings.py
        # picks the ordering with the lowest EXPECTED GUESSES; under a win-rate
        # ranking that is the wrong criterion, so it would quietly build the whole
        # cascade on mean-best orderings.  Better to take the ranking file's own
        # ordering -- arbitrary, and SAID to be arbitrary -- than to apply a
        # chooser that optimises something else.  --best-order still forces it on
        # for anyone who wants exactly that.
        if [ "$ADAPT" != 0 ] && [ "$RANK" = mean ]; then BESTORDER=1; else BESTORDER=0; fi
    fi
    if [ "$BESTORDER" = 1 ] && [ "$RANK" != mean ]; then
        echo "NOTE: --best-order chooses the ordering with the lowest EXPECTED" >&2
        echo "  GUESSES, but this run ranks on $RANK.  The orderings will be" >&2
        echo "  mean-best, not $RANK-best." >&2
    fi
    WORDS="$OUTDIR/$LISTNAME.txt"
    "$PY" tools/opening_list.py $OPENFLAGS --out "$WORDS" || exit 1
    ROOT=$(basename "$WORDS" .txt | sed 's/^openings_//')
    PASSNO=1
    if [ "$BESTORDER" = 1 ]; then
        # The best ordering depends on the follow-up (which pool the switch counts)
        # and on N, so both are in the name: these are different questions.
        ORDERED="$OUTDIR/${LISTNAME}_bestorder_${FALLBACK}_adapt${ADAPT}.txt"
        "$PY" tools/order_openings.py --from "$WORDS" --fallback "$FALLBACK" \
            --pair-adaptive "$ADAPT" --out "$ORDERED" || exit 1
        WORDS="$ORDERED"
        ROOT=$(basename "$WORDS" .txt | sed 's/^openings_//')
    fi
    # the stem records adapt separately, so strip it (and any cut suffix) here
    ROOT=$(echo "$ROOT" | sed -E 's/(_se[0-9]+|_adapt[0-9]+)+$//')
fi

# STAGE 1 OVER A PLAIN WORD LIST: the lineage root is the LIST.  It used to be
# left empty, which put a double underscore in the stem and -- the part that
# mattered -- gave `--words guess` and `--words mystery` THE SAME FILENAME, so a
# mystery sweep would resume from a guess sweep's rows and silently mix two word
# lists into one file.  Nothing on disk carries the empty form: every committed
# single-word sweep predates the lineage scheme entirely.
if [ -z "$SHORTFROM" ] && [ -z "$OPENFROM" ] && [ -z "$ROOT" ]; then
    ROOT=$(basename "$WORDS" .txt)
fi

if [ -n "$SHORTFROM" ]; then
    [ -f "$SHORTFROM" ] || { echo "no such sweep: $SHORTFROM" >&2; exit 1; }
    [ "$WORDS" = "guess" ] || {
        echo "--shortlist-from replaces --words; pass only one" >&2; exit 1; }
    SRCSTEM=$(basename "$SHORTFROM" .csv)
    # A screen run under one follow-up cannot choose the words for the other:
    # the opener is feeding a different player, so the ranking does not carry.
    SRCFB=$(sed -n 's/^# wordle opener sweep:.*follow-up \([a-z]*\),.*/\1/p' "$SHORTFROM" | head -1)
    if [ -n "$SRCFB" ] && [ "$SRCFB" != "$FALLBACK" ]; then
        echo "REFUSING: $SRCSTEM was swept under the '$SRCFB' follow-up, but this" >&2
        echo "  run uses '$FALLBACK'.  That would screen one player and test" >&2
        echo "  another; the ranking does not carry between them." >&2
        exit 1
    fi
    # Prefer the source's own lineage header; fall back to unpicking its stem.
    # THE STRATEGY IS A PROPERTY OF THE CASCADE, NOT OF ONE COMMAND, and that
    # applies to --pair-adaptive exactly as it does to --rank.  It did not, and
    # the consequence was silent: pass 1 of the win-rate cascades ran adaptive
    # and every later pass ran BLIND on the shortlist the adaptive pass had
    # chosen, because the flag was simply absent from the later commands.  The
    # filenames stayed honest (no _adapt2), but the cascade was two strategies.
    SRCADAPT=$(sed -n 's/^# settings .*pair_adaptive=\([0-9]*\).*/\1/p' "$SHORTFROM" | head -1)
    if [ -n "$SRCADAPT" ] && [ "$ADAPT" = 0 ] && [ "$SRCADAPT" != 0 ]; then
        ADAPT="$SRCADAPT"
        echo "pair-adaptive: inherited $ADAPT from the source"
    fi
    # THE SECOND-WORD TABLE IS A PROPERTY OF THE CASCADE TOO.  Same scar, same
    # cure: a pass that dropped it would screen one strategy and test another on
    # the shortlist the first had chosen, and the stem would not even say so.
    SRCSECOND=$(sed -n 's/^# settings .*second_table=\([^ ]*\).*/\1/p' "$SHORTFROM" | head -1)
    if [ -n "$SRCSECOND" ] && [ "$SRCSECOND" != "-" ]; then
        if [ -z "$SECONDFROM" ]; then
            SECONDFROM="$SRCSECOND"
            echo "second-word table: inherited $SECONDFROM from the source"
        elif [ "$SECONDFROM" != "$SRCSECOND" ]; then
            echo "REFUSING: $SRCSTEM was swept with the table $SRCSECOND, but this" >&2
            echo "  pass was given $SECONDFROM.  A cascade is ONE strategy all the" >&2
            echo "  way down; two tables would splice two of them together." >&2
            exit 1
        fi
    elif [ -n "$SECONDFROM" ] && [ -n "$SRCSECOND" ]; then
        echo "REFUSING: $SRCSTEM was swept WITHOUT a second-word table, so its" >&2
        echo "  shortlist was chosen under a different strategy from this one." >&2
        exit 1
    fi
    SRCRANK=$(sed -n 's/^# settings .*rank=\([a-z_]*\).*/\1/p' "$SHORTFROM" | head -1)
    if [ -n "$SRCRANK" ] && [ "$RANK" = mean ]; then
        # the cascade's ranking is a property of the CASCADE, not of one command
        RANK="$SRCRANK"
        [ "$RANK" = mean ] || { SHORTVALUE=win_rate
            echo "ranking: inherited $RANK from the source"; }
    fi
    ROOT=$(sed -n 's/^# lineage root=\([^ ]*\) .*/\1/p' "$SHORTFROM" | head -1)
    SRCPASS=$(sed -n 's/^# lineage .*pass=\([0-9][0-9]*\) .*/\1/p' "$SHORTFROM" | head -1)
    if [ -z "$ROOT" ]; then
        ROOT=$(echo "$SRCSTEM" | sed -n 's/.*_openings_//p' \
               | sed -E 's/(_se[0-9]+|_adapt[0-9]+)+$//')
        # an old nested stem counts its own passes: one per `shortlist_`, plus one
        SRCPASS=$(echo "$SRCSTEM" | grep -o shortlist | wc -l | tr -d " ")
        SRCPASS=$((SRCPASS + 1))
    fi
    [ -n "$ROOT" ] || { echo "cannot work out the lineage root of $SRCSTEM" >&2; exit 1; }
    PASSNO=$((SRCPASS + 1))
    CUTNAME="se${SHORTSE}"
    CUT="--se ${SHORTSE}"
    if [ -n "$SHORTTOP" ]; then
        CUT="--top $SHORTTOP"; CUTNAME="top$SHORTTOP"
    fi
    if [ "$SHORTVALUE" != mean ]; then
        CUT="$CUT --value $SHORTVALUE --maximise"
        CUTNAME="${CUTNAME}-win"
    fi
    WORDS="$OUTDIR/shortlist_${FALLBACK}_${ROOT}_p${PASSNO}_$CUTNAME.txt"
    "$PY" tools/sweep_shortlist.py --from "$SHORTFROM" $CUT --out "$WORDS" \
        || exit 1
    # WHICH PASS THIS IS, read off the source's own name: a stage-1 sweep is over a
    # word list, and every later one is over a shortlist cut from the stage before,
    # so the nesting in the stem counts the passes.  Stage 1 has no source at all.
    # ONE pass number, not two.  This used to count `shortlist_` occurrences in
    # the source's name, which the bounded stems no longer contain -- so a pass-9
    # run announced "pass 2" and printed on the pass-2 interval while writing p9.
    # PASSNO is derived once, above, from the source's lineage header.
    STAGE=$PASSNO
    # A later stage at the earlier seed replays the games that chose the
    # shortlist.  Loud, not fatal: it is a judgement about what the run means.
    # FROM THE FILE'S OWN HEADER, not its name.  Its first line reads
    #   # wordle opener sweep: 5000 trials per word, follow-up answer, seed 7
    # which is true whatever the naming scheme happens to be this week -- and the
    # naming scheme HAS changed twice, breaking a name-parser both times.  The
    # stem fallbacks below cover files written before the header existed: first
    # the current `..._p<pass>_t<T>_s<SEED>` tail, then the old nested form, whose
    # figures sit right after `sweep_<follow-up>_` (anchored, because a nested
    # stem holds one `_t` per ancestor and the oldest is LAST).
    SRCT=$(sed -n 's/^# wordle opener sweep: \([0-9][0-9]*\) trials.*/\1/p' "$SHORTFROM" | head -1)
    SRCSEED=$(sed -n 's/^# wordle opener sweep: .*seed \([0-9][0-9]*\).*/\1/p' "$SHORTFROM" | head -1)
    if [ -z "$SRCT" ]; then
        SRCT=$(echo "$SRCSTEM" | sed -n 's/.*_p[0-9][0-9]*_t\([0-9][0-9]*\)_s[0-9][0-9]*$/\1/p')
        SRCSEED=$(echo "$SRCSTEM" | sed -n 's/.*_p[0-9][0-9]*_t[0-9][0-9]*_s\([0-9][0-9]*\)$/\1/p')
    fi
    if [ -z "$SRCT" ]; then
        SRCT=$(echo "$SRCSTEM" | sed -n 's/^sweep_[a-z][a-z]*_t\([0-9][0-9]*\)_s[0-9].*/\1/p')
        SRCSEED=$(echo "$SRCSTEM" | sed -n 's/^sweep_[a-z][a-z]*_t[0-9][0-9]*_s\([0-9][0-9]*\)_.*/\1/p')
    fi
    # Derive the next pass's trials and seed from the source, unless given.
    if [ -z "$T" ]; then
        [ -n "$SRCT" ] || { echo "cannot read -t from $SRCSTEM; pass -t" >&2; exit 1; }
        T=$(next_t "$SRCT")
        echo "trials: $SRCT in $SRCSTEM, so this pass runs -t $T (the 1-2-3-5 ladder)"
    fi
    if [ "$SEEDGIVEN" = 0 ] && [ -n "$SRCSEED" ]; then
        SEED=$((SRCSEED + 1))
        echo "seed: $SRCSEED in the source, so this pass uses --seed $SEED"
    fi
    if [ "$SRCSEED" = "$SEED" ]; then
        echo "WARNING: this stage is using seed $SEED, the same seed as $SRCSTEM." >&2
        echo "  The draw stream is seeded per word, so its first $T games REPLAY" >&2
        echo "  that stage's games -- re-using the very sample that chose the" >&2
        echo "  shortlist.  Pass a fresh --seed for an independent test." >&2
    fi
fi

# HOW OFTEN TO PRINT A PROGRESS LINE, by pass (user's call, 2026-09-08): 100, 50,
# 30, 20, 10, 5, 3, 2, then every opening.  A wide stage-1 screen would drown the
# terminal one word at a time, but a later pass is short and slow per opening, and
# each one is worth watching.  --progress still overrides it.  This is cosmetic:
# it gates a print and nothing else, so it touches neither the games nor the
# filename.
if [ -z "$PROGRESS" ]; then
    # A `case` rather than an array: macOS ships bash 3.2, and the repo's scripts
    # have to run identically on both machines.
    case "$STAGE" in
        1) PROGRESS=100 ;;
        2) PROGRESS=50 ;;
        3) PROGRESS=30 ;;
        4) PROGRESS=20 ;;
        5) PROGRESS=10 ;;
        6) PROGRESS=5 ;;
        7) PROGRESS=3 ;;
        8) PROGRESS=2 ;;
        *) PROGRESS=1 ;;
    esac
fi
echo "pass $STAGE: a progress line every $PROGRESS word(s)"

# THE NAME IS BOUNDED, and this is a scar: every pass used to nest its entire
# ancestry, so by pass 6 the stem was over 255 bytes and macOS refused to create
# the file -- after the shortlist had been cut and the run had started.  A stem
# now carries the LINEAGE ROOT plus the pass number, which is constant size, and
# the full chain lives in each CSV's own `# lineage` header line: root, pass, and
# the immediate source, whose header names its own source in turn.
#
# The root is read from the source's header when it has one, and otherwise
# RECOVERED from an old nested stem -- everything after `openings_`, with the
# accumulated `_se<N>`/`_adapt<N>` suffixes stripped -- so the cascades already in
# flight under the old names continue without being restarted.
if [ -n "$SECONDFROM" ]; then
    [ -f "$SECONDFROM" ] || { echo "no such second-word table: $SECONDFROM" >&2
                              echo "  Build one: bash solver/run-second-word.sh" >&2
                              exit 1; }
    # THE CONDITION'S OWN NAME, not a threshold: a table whose groups key on
    # anything but the grey count carries no min_grays at all.
    MINGRAYS=$(sed -n 's/^# settings .*fire=\([^ ]*\).*/\1/p' "$SECONDFROM" | head -1)
    [ -n "$MINGRAYS" ] || MINGRAYS=g$(sed -n 's/^# settings .*min_grays=\([0-9]*\).*/\1/p' "$SECONDFROM" | head -1)
    [ "$MINGRAYS" != "g" ] || { echo "$SECONDFROM carries no '# settings' stamp, so it" >&2
                                echo "  cannot say which condition it was built under." >&2
                                exit 1; }
fi
STEM="sweep_${FALLBACK}_${ROOT}_p${PASSNO}_t${T}_s${SEED}"
# The threshold is the objective, so it is in the name -- and a cascade under a
# table is a different experiment from a blind one off the same root and pass.
[ -z "$SECONDFROM" ] || STEM="${STEM}_${MINGRAYS}"
# N is part of the objective, so it is in the name; 0 keeps the blind stem every
# earlier sweep already used.
[ "$ADAPT" = 0 ] || STEM="${STEM}_adapt${ADAPT}"
[ "$RANK" = mean ] || STEM="${STEM}_win"
[ -n "$LIMIT" ] && STEM="${STEM}_lim${LIMIT}"
[ "$WIN" = 6 ] || STEM="${STEM}_w${WIN}"
OUT="$OUTDIR/$STEM.csv"

# A name that cannot be created is worse than a name that is ugly: the old scheme
# got all the way through cutting the shortlist and starting the run before the
# open() failed.  255 bytes is the macOS/Linux per-component limit; refuse early
# and say so, rather than discover it at the first write.
NAMELEN=${#STEM}
if [ "$NAMELEN" -gt 200 ]; then
    echo "REFUSING: the output name is $NAMELEN characters, near the 255-byte" >&2
    echo "  filename limit: $STEM" >&2
    echo "  The lineage should be root+pass, so something is accumulating." >&2
    exit 1
fi

# --dry-run stops HERE: everything above is resolution (which list, which trials,
# which seed, which file), and everything below starts a run.  It exists because
# checking that the wrapper's own plumbing works must not cost anybody a sweep --
# a partial CSV from a "quick check" is indistinguishable from a real result that
# died, and the user runs the computations here.
if [ "$DRYRUN" = 1 ]; then
    echo "dry run: would write $OUT"
    echo "  words   $WORDS"
    echo "  lineage root $ROOT, pass $PASSNO"
    echo "  trials  $T   seed $SEED   follow-up $FALLBACK   pair-adaptive $ADAPT   rank $RANK"
    [ -z "$SECONDFROM" ] || echo "  second  $SECONDFROM (fires on $MINGRAYS)"
    echo "  progress every $PROGRESS opening(s)"
    exit 0
fi

# Shared refuse-if-something-else-writes-this-file guard.  Its second check is
# by process NAME, which is "python" here, so only the output-file half applies.
. "$(dirname "${BASH_SOURCE[0]}")/_guard.sh"
guard_output wordle_sweep.py "$OUT" || exit 1

FLAGS="-t $T --fallback $FALLBACK --seed $SEED --words $WORDS --win-within $WIN --out $OUT"
FLAGS="$FLAGS --root $ROOT --pass $PASSNO"
[ -n "$SHORTFROM" ] && FLAGS="$FLAGS --source $(basename "$SHORTFROM")"
[ "$ADAPT" = 0 ] || FLAGS="$FLAGS --pair-adaptive $ADAPT"
[ -z "$SECONDFROM" ] || FLAGS="$FLAGS --second-from $SECONDFROM"
[ "$RANK" = mean ] || FLAGS="$FLAGS --rank $RANK"
[ -n "$LIMIT" ] && FLAGS="$FLAGS --limit $LIMIT"
FLAGS="$FLAGS --progress $PROGRESS"

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] wordle opener sweep $STEM" \
    | tee -a "$LOC/$STEM.log"

"$PY" -u tools/wordle_sweep.py $FLAGS 2>&1 | tee -a "$LOC/$STEM.log"
