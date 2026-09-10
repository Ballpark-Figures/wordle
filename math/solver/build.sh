#!/bin/sh
# Build the solvers from the single optturns.c.  Run from math/solver/.
#
#   sh build.sh           -- optturns (normal Wordle), hardturns (hard mode),
#                            mmturns (Mastermind peg feedback), ultraturns
#                            (ultra hard mode: guesses must stay consistent)
#                            and wturns (weighted answers)
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
  # mmturns is the same objective under MASTERMIND's peg-count feedback --
  # (blacks, whites) instead of Wordle's per-tile colouring -- which is a pure
  # remap of the SAME pattern matrix, so it is a third compile-time mode of this
  # one source rather than a program of its own. 20 outcomes, not 238.
  gcc $BASE $OMP -DMASTERMIND -o mmturns optturns.c
  # ultraturns is "ultra hard mode": a legal guess must itself be CONSISTENT with
  # every clue so far -- stricter than hard mode, which only forces greens in
  # place and yellows somewhere.  Another compile-time mode of this one source
  # (-DULTRA), carrying the accumulated consistency constraint as extra TT state
  # exactly as hard mode carries its own.
  gcc $BASE $OMP -DULTRA -o ultraturns optturns.c
  # wturns is the WEIGHTED objective: the answers carry a weight and the total
  # is sum of w_a x (guesses spent on a) rather than a plain count.  A fifth
  # compile-time mode of this one source (-DWEIGHTED), because it is the same
  # search under a different cost -- and with every weight 1 it reproduces
  # optturns exactly, which is the differential test checkweighted.py runs.
  gcc $BASE $OMP -DWEIGHTED -o wturns optturns.c
  # pairsplit is the PAIR-OPENER screen: no search, no TT, just the joint-split
  # score for every unordered pair of guesses. Separate program because it shares
  # nothing with the solver but the .npy loader.
  gcc $BASE $OMP -o pairsplit pairsplit.c
  # secondword picks the best PREDETERMINED second word for every opener -- the
  # word minimising the expected answers left, over the replies showing at least
  # --min-grays greys.  Separate program because it is pairsplit's inner loop
  # under a different QUESTION: the answers are filtered by the opener's reply
  # before they are bucketed, the walk is over ORDERED (g1, g2), and the result
  # is one argmin per opener rather than a global ranking -- so it shares the
  # .npy loader and the run-histogram trick and nothing else.
  gcc $BASE $OMP -o secondword secondword.c
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
  # greens is the SEA OF GREENS badge: the most answers winnable with no yellow
  # tile, over strategies that still win every answer within the cap.  Separate
  # program because the OBJECTIVE differs -- a maximum with a hard feasibility
  # side-condition, not a minimum of a sum -- so it shares the loader, the table
  # and the arena with optturns but none of the search.  Same reason antistall
  # is its own file.
  gcc $BASE $OMP -o greens greens.c
  # antistall is ANTIWORDLE's stalling endgame -- the reverse objective, so it
  # shares no search code with the solver: no depth cap, a maximum rather than a
  # minimum, and no constraint struct at all, since with the answer fixed each
  # guess's effect precomputes to a bitset and the state reduces to the legal set.
  # --longest parallelises over ANSWERS, which are independent searches sharing
  # only the incumbent and the (self-verifying) table, so it wants OpenMP.
  gcc $BASE $OMP -o antistall antistall.c
  # antiexpect maximises EXPECTED turns: a strategy played without knowing the
  # answer, so its state carries BOTH the legal set and the still-possible answers.
  # A different objective from antistall's per-answer maximum, hence its own program.
  gcc $BASE $OMP -o antiexpect antiexpect.c
  # eldrowmax is the LONGEST CONSISTENT CHAIN: every word played must itself still
  # be a possible answer, which is a strictly tighter rule than antistall's
  # antiwordle legality.  Its own file rather than a mode of antistall.c because
  # the state is the CANDIDATE SET and a move is (word, feedback), so neither the
  # per-guess delta table nor either of antistall's two bounds survives the change
  # -- it shares the loader, the table and the arena and none of the search.
  gcc $BASE $OMP -o eldrowmax eldrowmax.c
  echo "built ./optturns, ./hardturns, ./mmturns, ./ultraturns, ./pairsplit, ./secondword, ./strturns, ./strguess, ./greens, ./antistall, ./antiexpect and ./eldrowmax  (5 letters)"
  exit 0
fi

WORDS_DIR="../data/shared/words/hello"

for L in "$@"; do
  case "$L" in
    3|4|5|6|7|8|9|10|11) ;;
    *) echo "build.sh: unsupported length '$L' (3..11; a new length needs a P3_<L> entry in optturns.c)" >&2
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
