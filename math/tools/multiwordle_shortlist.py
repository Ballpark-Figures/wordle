"""Stage 2 of an opener sweep: cut a shortlist out of a stage-1 screen.

    python3 tools/multiwordle_shortlist.py --from SWEEP.csv --se 10 --out LIST.txt
    python3 tools/multiwordle_shortlist.py --from SWEEP.csv --top 200 --out LIST.txt

Or let the sweep wrapper do both steps in one command:

    bash solver/run-multiwordle-sweep.sh -k 1 -t 10000 --seed 1 \\
        --shortlist-from data/shared/multiwordle/sweep_k1_t1000_s0_guess.csv

WHY A SECOND STAGE EXISTS.  A wide sweep at small -t estimates every word to
within its own standard error, and over 12972 words the best-looking mean belongs
to whichever word drew the kindest sample -- so the head of a screen is biased
optimistic and cannot be read as a winner.  Re-running a SHORTLIST at large -t
gives the survivors estimates precise enough to separate, and a word that leads
both stages has been asked twice.

THE CUT IS A NET, NOT A VERDICT -- KEEP IT GENEROUS.  --se N keeps every word
whose mean is within N standard errors of the best word's, using the BEST word's
standard error by default (--own-se uses each word's own, which is slightly more
permissive since the losers' errors are larger).  A tight cut risks discarding
the true best word on one unlucky sample; that error is unrecoverable, while an
over-wide cut only costs time.  10 SE at t=1000 is a deliberately wide net.

USE A DIFFERENT --seed FOR STAGE 2.  The draw stream is seeded per word, so a
stage-2 run at the SAME seed replays stage 1's games as its first -t of them --
re-using the very sample that chose the shortlist, and carrying its selection
bias forward.  A fresh seed makes stage 2 an independent test of stage 1's claim.

ORDER.  The shortlist is written best-first by stage-1 mean, so a stage-2 run
that is stopped early has examined the most promising words rather than an
alphabetical prefix.  That ordering is a convenience only: every word still gets
the same trials and the same games, so nothing about it favours a word.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep_shortlist import main, read_sweep, shortlist  # noqa: E402,F401

# The cut logic moved to tools/sweep_shortlist.py when the single-board sweep
# became a second caller of it -- one implementation, two front ends.  This CLI
# is unchanged: --from/--out/--se/--top/--own-se all behave exactly as before,
# and the columns are now found by NAME in the header rather than by position,
# which every sweep CSV here already satisfies.  `read_sweep` and `shortlist` are
# re-exported so an importer of this module keeps working.

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], prog="tools/multiwordle_shortlist.py"))
