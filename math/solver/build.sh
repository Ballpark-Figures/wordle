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

# OpenMP wiring differs by toolchain, so probe rather than assume.  On WSL /
# Linux `gcc` is real GCC and a bare -fopenmp is all it takes.  On macOS `gcc`
# is an Apple clang shim that ships NO OpenMP runtime at all -- it needs
# Homebrew's libomp, which is keg-only, so its include/lib paths have to be
# named explicitly.  Getting this wrong fails at the FIRST compile with
# "clang: error: unsupported option '-fopenmp'", not at link time.
OMP="-fopenmp"
if ! gcc -fopenmp -E -x c /dev/null >/dev/null 2>&1; then
  omp_prefix=$(brew --prefix libomp 2>/dev/null || true)
  if [ -z "$omp_prefix" ] || [ ! -d "$omp_prefix" ]; then
    echo "build.sh: this toolchain has no OpenMP support." >&2
    echo "  macOS: brew install libomp" >&2
    echo "  Linux: install a real gcc (Apple's clang shim will not do)" >&2
    exit 1
  fi
  OMP="-Xpreprocessor -fopenmp -I$omp_prefix/include -L$omp_prefix/lib -lomp"
fi

# $OMP is deliberately unquoted -- it is a multi-word flag list on macOS.
gcc -O3 -march=native -funroll-loops $OMP -o optturns  optturns.c
gcc -O3 -march=native -funroll-loops $OMP -DHARDMODE -o hardturns optturns.c
echo "built ./optturns and ./hardturns"
