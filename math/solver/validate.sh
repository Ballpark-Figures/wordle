#!/bin/bash
# Reproduce Table 1 of Bertsimas & Paskov, "An Exact and Interpretable Solution
# to Wordle". Their published averages are exact integers over 2315; this checks
# the integer totals, so a pass is a bit-for-bit reproduction, not a rounding
# coincidence. Run from math/ :  bash solver/validate.sh
set -u
cd "$(dirname "$0")/.."

# Parallel list + case, NOT `declare -A`: macOS ships bash 3.2 (2007, the last
# GPLv2 release), which has no associative arrays. Under `set -u` that fails as
# "salet: unbound variable" pointing at the declare line itself, which reads as
# a solver bug rather than a shell-version one. Keep this file bash-3.2 clean --
# validation has to give the same answer on the Mac and on WSL.
WORDS="salet reast trace crate slate"
expected_for() {
    case "$1" in
        salet) echo 7920 ;;
        reast) echo 7923 ;;
        trace) echo 7926 ;;
        crate) echo 7926 ;;
        slate) echo 7928 ;;
        *)     echo "" ;;
    esac
}

# tee rather than capture, so a long run shows progress instead of going silent
tmp=$(mktemp)
./solver/optturns --tt-bits 25 \
    --opener salet --opener reast --opener trace --opener crate --opener slate \
    2>/dev/null | tee "$tmp"
out=$(cat "$tmp"); rm -f "$tmp"

fail=0
for w in $WORDS; do
    want=$(expected_for "$w")
    got=$(echo "$out" | awk -v w="$w" '$1==w {for(i=1;i<=NF;i++) if($i ~ /^total=/) {sub("total=","",$i); print $i}}')
    if [ "$got" = "$want" ]; then
        echo "PASS $w = $got"
    else
        echo "FAIL $w = ${got:-<none>} (expected $want)"
        fail=1
    fi
done
exit $fail
