#!/bin/bash
# Mechanically enforce the SOLVER-side conventions, the way `render --check`
# lints the scene side.  Run it from math/ (or anywhere):
#
#     bash solver/checkconventions.sh
#
# WHY THIS EXISTS.  Every rule it checks was already written down in prose and
# violated anyway, in a single day (2026-09-01): a solver shipped with no
# wrapper, so a bare invocation printed its answer and saved NOTHING and a day of
# multi-hour runs was lost; another had an opener literal as its no-arguments
# default, asserting an answer inside the program meant to derive one.  Prose in
# a 127 KB rules file did not prevent either.  A check that fails does.
#
# Exit status is nonzero if anything fails, so it works as a gate.  Run it
# alongside solver/validate.sh, tools/checkpatterns.py, tools/checkstrspace.py
# and tools/checkstrturns.py.

set -u
MATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MATH" || exit 1

fail=0
bad() { echo "  FAIL: $*"; fail=1; }

# ---------------------------------------------------------------- 1. wrappers
# A solver binary is not a deliverable until something knows how to RUN it with
# its output going somewhere durable.
echo "1. every solver binary has a wrapper"
bins=$(sed -n '/^if \[ \$# -eq 0 \]/,/^fi/p' solver/build.sh \
       | grep -o '\-o [a-z0-9]*' | awk '{print $2}' | sort -u)
for b in $bins; do
    if grep -lq "solver/$b\b" solver/run-*.sh 2>/dev/null; then
        echo "   ok   $b -> $(grep -l "solver/$b\b" solver/run-*.sh | xargs -n1 basename | tr '\n' ' ')"
    else
        bad "$b has no run-*.sh wrapper -- a bare invocation is the only way to run it"
    fi
done

# ------------------------------------------------------------- 2. wrappers save
echo "2. every wrapper persists its results"
for w in solver/run-*.sh; do
    n=$(basename "$w")
    grep -q -- '--out' "$w" || bad "$n does not pass --out"
    grep -q 'tee'        "$w" || bad "$n does not tee a log"
done
[ "$fail" -eq 0 ] && echo "   ok   all $(ls solver/run-*.sh | wc -l | tr -d ' ') wrappers pass --out and tee"

# --------------------------------------------------- 3. no domain answers in code
# A five-letter lowercase string literal that is a LEGAL GUESS is almost
# certainly an answer typed into a program whose job is to derive one.  This is
# the check that would have caught `openers[nopen++] = "salet"`.
# NARROWED to lines that also mention a guess-shaped identifier.  Plain
# five-letter word literals are common as display labels -- pairsplit.c prints
# "pairs", "quads", "quint" -- and flagging those is noise.  The hazard is a word
# literal reaching the SOLVER, so require the line to talk about openers or
# guesses as well.
echo "3. no legal-guess word is fed to the solver as a literal"
hits=$(grep -n '"[a-z][a-z][a-z][a-z][a-z]"' solver/*.c 2>/dev/null \
       | grep -i 'opener\|guess\|gword\|answer\|default' \
       | grep -v 'printf\|fprintf\|not a legal\|%s')
found=0
if [ -n "$hits" ]; then
    echo "$hits" | while IFS= read -r line; do
        w=$(echo "$line" | grep -o '"[a-z][a-z][a-z][a-z][a-z]"' | head -1 | tr -d '"')
        grep -qx "$w" data/shared/words/guess.txt || continue
        echo "  FAIL: \"$w\" is a legal guess, fed to the solver as a literal"
        echo "         $line"
    done
    for l in $(echo "$hits" | grep -o '"[a-z][a-z][a-z][a-z][a-z]"' | tr -d '"' | sort -u); do
        grep -qx "$l" data/shared/words/guess.txt && found=1
    done
fi
[ "$found" -eq 1 ] && fail=1
[ "$found" -eq 0 ] && echo "   ok   no word literal reaches a guess or opener"

# ------------------------------------------------ 4. no silent discard of results
# A solver that can run for hours must not print its answer and save nothing.
echo "4. every solver either defaults an output path or refuses without one"
for c in solver/*.c; do
    n=$(basename "$c")
    grep -q -- '"--out"' "$c" || continue          # not a result-producing solver
    if grep -q 'save NOTHING\|outpath = ' "$c"; then
        echo "   ok   $n requires or defaults --out"
    else
        bad "$n takes --out but neither defaults it nor refuses without it"
    fi
done

# --------------------------------------------------------- 5. wrappers are sane
# NB the executable bit is deliberately NOT checked: the house form is
# `bash solver/run-*.sh`, so it carries no meaning and demanding it would fail
# four wrappers that work perfectly well.
echo "5. wrappers parse"
for w in solver/run-*.sh; do
    n=$(basename "$w")
    bash -n "$w" 2>/dev/null || bad "$n is not valid bash"
done
echo "   ok   $(ls solver/run-*.sh | wc -l | tr -d ' ') wrappers parse"

# ------------------------------------------------- 6. every solver is parallel
# A new solver written by copying a sibling's shape inherits its wrapper, its --out
# insistence and its comment style -- and then quietly does NOT inherit the one
# thing that is a compile FLAG rather than code. antiexpect shipped as the only one
# of nine built without $OMP, ran the full problem on one of eighteen cores, and was
# handed over as "ready" with nobody noticing until it was asked about directly.
#
# Nothing in the source shows it: the file looks like its siblings. Only the build
# line differs, so only a check on the build line catches it.
#
# A genuinely single-threaded tool is allowed -- mark its line `# NO-OMP:` with the
# reason, and this passes. What is not allowed is silence.
echo "6. every solver is built with OpenMP, or says why not"
ompfail=0
while IFS= read -r line; do
    case "$line" in
        *'$OMP'*) continue ;;                 # parallel: fine
        *'NO-OMP:'*) continue ;;              # deliberate and stated: fine
    esac
    b=$(echo "$line" | grep -o '\-o [a-z0-9]*' | awk '{print $2}')
    [ -n "$b" ] || continue
    bad "$b is built without \$OMP and without a '# NO-OMP: <reason>' note"
    ompfail=1
done <<EOF
$(sed -n '/^if \[ \$# -eq 0 \]/,/^fi/p' solver/build.sh | grep '^ *gcc ')
EOF
[ "$ompfail" -eq 0 ] && echo "   ok   every solver in build.sh is parallel or explains itself"

# ------------------------------------- 7. no wrapper clobbers a shell built-in
# `GROUPS` is a bash BUILT-IN ARRAY of the user's group ids.  Assigning to it
# writes element 0 and reading `$GROUPS` back gives a gid -- 20 (`staff`) on
# macOS -- so a wrapper that used it for its own list silently built its command
# line out of a group number.  It looks exactly like a quoting bug and cost half
# an hour.  The others here are the same shape: assign them and the shell's own
# behaviour changes under you.
echo "7. no wrapper assigns a shell built-in variable"
builtin_re='^[[:space:]]*(GROUPS|SECONDS|RANDOM|LINENO|PWD|OLDPWD|IFS|PPID|UID|EUID|BASH_[A-Z]*|FUNCNAME|HOSTNAME|SHLVL|OPTARG|OPTIND|REPLY|HISTFILE)='
if grep -nE "$builtin_re" solver/run-*.sh >/dev/null 2>&1; then
    grep -nE "$builtin_re" solver/run-*.sh
    bad "a wrapper assigns a shell built-in variable (see the lines above)"
else
    echo "   ok   no wrapper assigns one"
fi

echo
if [ "$fail" -eq 0 ]; then echo "all solver conventions hold"; else echo "CONVENTION FAILURES -- see above"; fi
exit $fail
