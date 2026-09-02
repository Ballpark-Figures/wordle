#!/bin/sh
# Build the solvers from the single optturns.c.  Run from math/solver/.
#
#   sh build.sh           -- optturns (normal Wordle) + hardturns (hard mode)
#   sh build.sh 7         -- optturns7, the 7-letter solver
#   sh build.sh 4 6 7 8   -- several lengths at once
#
# HARD and WORDLEN are both COMPILE-TIME constants, so each binary keeps its hot
# loops free of the other configurations' branches while all of them stay one
# source of truth.  Separate output names also mean a 7-letter binary can be
# built while a 5-letter sweep is running.
#
# WHY ONE BINARY PER LENGTH.  Every array bound in the solver derives from
# NPAT = 3**WORDLEN (243 at 5 letters, 177147 at 11).  As a compile-time literal
# those fold into the addressing; as a runtime variable they would cost an
# indirection in the innermost partition loop, which is the whole program.
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
BASE="-O3 -march=native -funroll-loops"

if [ $# -eq 0 ]; then
  gcc $BASE $OMP -o optturns  optturns.c
  gcc $BASE $OMP -DHARDMODE -o hardturns optturns.c
  # pairsplit is the PAIR-OPENER screen: no search, no TT, just the joint-split
  # score for every unordered pair of guesses. Separate program because it shares
  # nothing with the solver but the .npy loader.
  gcc $BASE $OMP -o pairsplit pairsplit.c
  # strturns is the W -> S cell: the same objective over ALL 26**5 strings as
  # answers. Separate program because it shares no data structure with the
  # solver -- no pattern matrix and no candidate list, since neither survives
  # 11,881,376 answers; the candidate set is carried as CONSTRAINTS instead.
  gcc $BASE $OMP -o strturns strturns.c
  # strguess is the S -> A and S -> W cells: EVERY 26**5 string is a legal guess,
  # the answers are a word list.  Separate again because the guess side has no
  # matrix and no 16-bit index -- patterns are computed inline over 11881376
  # ordinals.
  gcc $BASE $OMP -o strguess strguess.c
  # antistall is ANTIWORDLE's stalling endgame -- the reverse objective, so it
  # shares no search code with the solver: no depth cap, a maximum rather than a
  # minimum, and no constraint struct at all, since with the answer fixed each
  # guess's effect precomputes to a bitset and the state reduces to the legal set.
  # Single-threaded, so no OpenMP.
  gcc $BASE -o antistall antistall.c
  echo "built ./optturns, ./hardturns, ./pairsplit, ./strturns, ./strguess and ./antistall  (5 letters)"
  exit 0
fi

WORDS_DIR="../data/shared/words/hello"

for L in "$@"; do
  case "$L" in
    4|5|6|7|8|9|10|11) ;;
    *) echo "build.sh: unsupported length '$L' (4..11; NPAT table in optturns.c)" >&2
       exit 1 ;;
  esac

  g="$WORDS_DIR/len$L/guess.txt"
  a="$WORDS_DIR/len$L/mystery.txt"
  if [ ! -f "$g" ] || [ ! -f "$a" ]; then
    echo "build.sh: missing $g or $a -- run \`python3 build_wordlists.py\` from math/" >&2
    exit 1
  fi

  # MAXG/MAXA are sized from the ACTUAL lists rather than set to the maximum
  # across all lengths: they bound the per-thread arena (lbg + ord + leg + mark
  # scale with MAXG, buf + tbuf with MAXA), so an 8-letter figure carried into
  # the 4-letter binary would cost memory for nothing.  The slack absorbs a
  # --guess-list/--answer-list that is a subset, never a superset.
  ng=$(grep -c . "$g")
  na=$(grep -c . "$a")
  maxg=$((ng + 16))
  maxa=$((na + 16))

  gcc $BASE $OMP -DWORDLEN="$L" -DMAXG="$maxg" -DMAXA="$maxa" \
      -o "optturns$L" optturns.c
  echo "built ./optturns$L  ($L letters, MAXG=$maxg, MAXA=$maxa, NPAT=$(awk "BEGIN{print 3^$L}"))"
done
