#!/bin/bash
# Enumerate the FREE-STANDING GREEN TEMPLATES that pin a single word --
# attached, with live output in this terminal.
#
#     bash solver/run-green-templates.sh                   # from math/, or anywhere
#     bash solver/run-green-templates.sh --pool guesses
#     bash solver/run-green-templates.sh --greens 3
#     bash solver/run-green-templates.sh --letters vowels
#     bash solver/run-green-templates.sh --pool guesses --letters consonants
#     bash solver/run-green-templates.sh --top 200      # longer printed table
#     bash solver/run-green-templates.sh --top all      # print every row
#     bash solver/run-green-templates.sh --positions 1-3
#     bash solver/run-green-templates.sh --sort zipf
#     bash solver/run-green-templates.sh --pool guesses --require any
#
# THE TWO CASES ASKED FOR:
#
#     bash solver/run-green-templates.sh --pool answers     # unique among the 2315
#     bash solver/run-green-templates.sh --pool guesses     # unique among the 12972,
#                                                           # and that word is an answer
#
# WHAT THIS COMPUTES, precisely:
#
#   A TEMPLATE is N positions and a letter for each -- `.a..e` means "position 2
#   is a, position 5 is e".  This enumerates every one of them (C(5,N) position
#   sets x 26^N letter assignments) and reports those matching EXACTLY ONE word.
#
#   THE GREENS ARE FREE-STANDING, NOT A GUESS'S FEEDBACK.  The other positions
#   are entirely UNCONSTRAINED: the template asserts nothing about them, so there
#   are no greys, no yellows and no repeated-letter rule, and wordle.pattern is
#   not involved.  "A real board showing exactly N greens" is a DIFFERENT and
#   smaller question -- that board also carries the guess's greys and yellows.
#
#   FIVE AXES, ALL PART OF THE QUESTION.  --pool says which list uniqueness is
#   judged over: `answers` (the 2315 curated answers) or `guesses` (all 12972
#   legal words).  Those are different quantities -- `guesses` is strictly
#   harder, since every answer is a legal guess, so pinning one word of 12972
#   necessarily pins one of 2315.  --require is a SEPARATE axis and changes no
#   count: `answer` keeps only the rows whose word is a mystery answer, `any`
#   keeps them all, exactly as run-maxbucket.sh's --rank restricts its rows.
#   --greens is part of the question too: a 2-green result and a 3-green result
#   are different quantities and get different files.
#
#   --letters IS A THIRD ROW FILTER, and it also changes no count.  `all` is the
#   26; `vowels` keeps only the templates whose every green is a vowel;
#   `consonants` only those whose every green is a consonant.  Y IS A VOWEL HERE
#   AND IS NOT A CONSONANT, so the two sets partition the alphabet (6 + 20 = 26)
#   -- proved on every run, not assumed.  THE VOWEL AND CONSONANT ROWS DO NOT SUM
#   TO THE `all` ROWS: a template mixing the two classes (`.a..t`) is homogeneous
#   under neither and appears only under `all`, and the mixed ones are the bulk.
#
#   --positions IS A THIRD ROW FILTER: `all` is every C(5,N) position set,
#   `1-3` keeps only the templates greening positions 1 and 3.  1-indexed and
#   hyphen-joined, written exactly as the CSV's own `positions` column reads
#   back.  IT MUST NAME EXACTLY --greens POSITIONS -- `--positions 1-3` with
#   `--greens 2` agrees, with `--greens 3` it does not, and the tool REFUSES
#   rather than reinterpret one flag in the light of the other.
#
#   --top IS PRESENTATION ONLY: how many rows to print, an integer or `all`.  It
#   never touches the FILE, which always holds every row whatever --top says, and
#   it is not in the stem for that reason.  It lengthens the two summary lists
#   too.  The default is 50.
#
#   --sort IS NOT A RESTRICTION and is not part of the question: it reorders the
#   very same rows.  `template` is position-then-letter (the deterministic
#   default); `zipf` is DESCENDING word frequency, most common word first.  A TIE
#   FALLS BACK TO THE `template` ORDER (position set, then letters), so tied rows
#   keep exactly the relative order the default sort would give them and the file
#   stays deterministic -- ties are common, since one word is often pinned by
#   several templates and they all carry its one frequency.  It is in the filename anyway,
#   because two runs differing only in it would write different bytes under one
#   name.
#
#   EVERY ROW CARRIES ITS WORD'S ZIPF, SOURCED AND NEVER RECOMPUTED -- read from
#   the committed data/shared/words/guess_by_freq.txt via
#   build_freq_wordlist.load_zipf, the module that owns that file's format.  zipf
#   is log10(occurrences per billion): 4.0 is about 10 per million, 3.0 about 1
#   per million, and 0.00 is a REAL VALUE meaning wordfreq's "large" list does
#   not have the word at all, which is true of thousands of the 12972.  Nothing
#   in the run imports wordfreq.
#
#   Nothing searches or samples: a pure function of the committed word lists, so
#   it is exact, has no standard error, and a re-run reproduces its file byte for
#   byte.  It reads no pattern matrix, so it runs on a fresh clone.
#
#   THE GATE IS BUILT IN and always runs: the whole result is recomputed
#   EXHAUSTIVELY from the STRINGS by a dict of letter tuples (no codes, no
#   bincount, no index arithmetic) and demanded equal template for template;
#   sampled rows are re-verified by scanning the entire pool with plain string
#   comparison; under --pool guesses the survivors must be a subset of the
#   answer-pool ones; and the FINAL row set -- after both filters -- is
#   re-derived straight from that string-built reference and demanded equal, so
#   the filter chain is checked too.  A coverage tally FAILS if nothing was
#   pinned, if the guess pool never dropped a template the answer pool would have
#   kept, or if a --letters or --positions restriction dropped nothing.  Every
#   pinned word must carry a zipf, and a zipf sort is checked to be a PERMUTATION
#   of the rows and genuinely non-increasing.  It exits nonzero rather
#   than reporting.  An EMPTY result after the filters is a legitimate RESULT and
#   is still written, so the emptiness is on the record.
#
# USE THIS RATHER THAN CALLING tools/green_templates.py DIRECTLY.  The tool
# refuses to run without --out and refuses to pick any of the axes for you; this
# forwards them all EXPLICITLY, so each decision has one owner, and it tees a log
# naming the run.
#
# Outputs
# data/shared/greentemplates/green_g<N>_<pool>_<require>[_<letters>][_p<positions>][_zipf].csv,
# columns template,positions,letters,word,zipf -- positions 1-indexed and
# hyphen-joined.  Each optional suffix appears only when that axis is set away
# from its unrestricted default, so the files already on disk keep the names they
# had and their meaning is unchanged; every file also carries a machine-readable
# `# settings greens=... pool=... require=... letters=... positions=... sort=...`
# line, so it says what it is regardless of its name.  Log under
# data/local/greentemplates/.

set -u

MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults a HUMAN reads, forwarded explicitly -- never ones the program falls
# back on: tools/green_templates.py refuses to run if any is missing.
GREENS=2
POOL=answers
REQUIRE=answer
LETTERS=all
POSITIONS=all
SORT=template
# PRESENTATION ONLY -- --top never changes the FILE, which always holds every
# row, so it is deliberately NOT in the stem.  `all` prints the lot.
TOP=50

while [ $# -gt 0 ]; do
    case "$1" in
        --greens)  GREENS="$2";  shift 2 ;;
        --pool)    POOL="$2";    shift 2 ;;
        --require) REQUIRE="$2"; shift 2 ;;
        --letters)   LETTERS="$2";   shift 2 ;;
        --positions) POSITIONS="$2"; shift 2 ;;
        --sort)      SORT="$2";      shift 2 ;;
        --top)     TOP="$2";     shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

case "$POOL" in
    answers|guesses) ;;
    *) echo "--pool must be 'answers' (the 2315) or 'guesses' (the 12972)" >&2
       exit 1 ;;
esac
case "$REQUIRE" in
    answer|any) ;;
    *) echo "--require must be 'answer' (keep only rows whose word is a mystery answer) or 'any'" >&2
       exit 1 ;;
esac
case "$LETTERS" in
    all|vowels|consonants) ;;
    *) echo "--letters must be 'all' (the 26), 'vowels' (aeiouy -- y IS a vowel) or 'consonants' (the other 20 -- y is NOT one)" >&2
       exit 1 ;;
esac
case "$TOP" in
    all) ;;
    ''|*[!0-9]*) echo "--top must be a non-negative integer or 'all'" >&2; exit 1 ;;
esac
case "$SORT" in
    template|zipf) ;;
    *) echo "--sort must be 'template' (position then letter) or 'zipf' (descending word frequency, most common first)" >&2
       exit 1 ;;
esac
case "$POSITIONS" in
    all|*[!0-9-]*) [ "$POSITIONS" = all ] || {
        echo "--positions must be 'all' or 1-indexed positions joined by hyphens, e.g. 1-3" >&2
        exit 1 ; } ;;
esac
case "$GREENS" in
    ''|*[!0-9]*) echo "--greens must be a positive integer" >&2; exit 1 ;;
esac
if [ "$GREENS" -lt 1 ] || [ "$GREENS" -gt 5 ]; then
    echo "--greens must be between 1 and 5" >&2
    exit 1
fi

cd "$MATH" || exit 1

PY=../.venv/bin/python
[ -x "$PY" ] || { echo "no venv python at $PY" >&2; exit 1; }

# The letters suffix appears only when the greens are RESTRICTED: an
# unrestricted run keeps the name it always had, and since that name never meant
# anything else, no file's meaning changes under anyone's feet.  The CSV carries
# a `# settings` line naming every axis, so it self-describes either way.
STEM=green_g${GREENS}_${POOL}_${REQUIRE}
[ "$LETTERS" = all ]   || STEM=${STEM}_${LETTERS}
[ "$POSITIONS" = all ] || STEM=${STEM}_p${POSITIONS}
[ "$SORT" = template ] || STEM=${STEM}_${SORT}
OUT=data/shared/greentemplates/${STEM}.csv

MARKER="green_templates.py --pool $POOL --require $REQUIRE --letters $LETTERS --positions $POSITIONS --sort $SORT --greens $GREENS"
RUNNING=$(pgrep -f -- "$MARKER" 2>/dev/null | tr '\n' ' ')
if [ -n "$RUNNING" ]; then
    echo "REFUSING: the same run is already going (pid $RUNNING)." >&2
    echo "  Two copies would write $OUT at once." >&2
    exit 1
fi

LOC=data/local/greentemplates
mkdir -p "$LOC" data/shared/greentemplates

# BSD date has no -Is; this form works on both macOS and Linux.
echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] green-templates: greens=$GREENS pool=$POOL require=$REQUIRE letters=$LETTERS positions=$POSITIONS sort=$SORT" \
    | tee -a "$LOC/${STEM}.log"

"$PY" -u tools/green_templates.py --pool "$POOL" --require "$REQUIRE" \
    --letters "$LETTERS" --positions "$POSITIONS" --sort "$SORT" \
    --greens "$GREENS" --top "$TOP" --out "$OUT" 2>&1 \
    | tee -a "$LOC/${STEM}.log"
