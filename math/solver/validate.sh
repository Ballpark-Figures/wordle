#!/bin/bash
# Reproduce Table 1 of Bertsimas & Paskov, "An Exact and Interpretable Solution
# to Wordle". Their published averages are exact integers over 2315; this checks
# the integer totals, so a pass is a bit-for-bit reproduction, not a rounding
# coincidence. Run from math/ :  bash solver/validate.sh
set -u
cd "$(dirname "$0")/.."

declare -A EXPECT=( [salet]=7920 [reast]=7923 [trace]=7926 [crate]=7926 [slate]=7928 )

# tee rather than capture, so a long run shows progress instead of going silent
tmp=$(mktemp)
./solver/optturns --tt-bits 25 \
    --opener salet --opener reast --opener trace --opener crate --opener slate \
    2>/dev/null | tee "$tmp"
out=$(cat "$tmp"); rm -f "$tmp"

fail=0
for w in salet reast trace crate slate; do
    got=$(echo "$out" | awk -v w="$w" '$1==w {for(i=1;i<=NF;i++) if($i ~ /^total=/) {sub("total=","",$i); print $i}}')
    if [ "$got" = "${EXPECT[$w]}" ]; then
        echo "PASS $w = $got"
    else
        echo "FAIL $w = ${got:-<none>} (expected ${EXPECT[$w]})"
        fail=1
    fi
done
exit $fail
