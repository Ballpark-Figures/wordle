#!/bin/sh
# Build the exact-turns solver. Run from math/solver/.
set -e
gcc -O3 -march=native -funroll-loops -fopenmp -o optturns optturns.c
echo "built ./optturns"
