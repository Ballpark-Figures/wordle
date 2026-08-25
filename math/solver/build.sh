#!/bin/sh
# Build both solvers from the single optturns.c.  Run from math/solver/.
#
#   optturns   -- normal Wordle (HARD 0)
#   hardturns  -- hard mode, "any revealed hints must be used" (HARD 1)
#
# HARD is a compile-time constant, so each binary keeps its hot loops free of
# the other mode's branches while both stay one source of truth.  Two output
# names also mean hardturns can be built while an optturns sweep is running.
set -e
gcc -O3 -march=native -funroll-loops -fopenmp -o optturns  optturns.c
gcc -O3 -march=native -funroll-loops -fopenmp -DHARDMODE -o hardturns optturns.c
echo "built ./optturns and ./hardturns"
