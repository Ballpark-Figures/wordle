"""The video's LETTER TIER LIST -- a hand-made ranking, recorded, not computed.

    E
    ARTS
    L
    IONC
    DP
    HUBMGY
    FKWV
    XZJQ

Best tier first, so `TIERS[0]` is the top and `TIERS[-1]` is the bottom. This is
the user's own ranking (2026-09-10), kept here verbatim so the notebooks and any
tool read ONE copy of it rather than each pasting their own. Nothing in this
module ranks anything or derives a tier: it is the record plus set lookups. If
the ranking changes, change it HERE.

The tiers partition the alphabet -- every letter in exactly one -- which is
asserted at import, so a typo that drops or doubles a letter fails loudly rather
than quietly shrinking a set some condition then filters on.

    >>> sorted(bottom(1))              # the last tier
    ['j', 'q', 'x', 'z']
    >>> sorted(bottom(2))              # the last two, unioned
    ['f', 'j', 'k', 'q', 'v', 'w', 'x', 'z']
    >>> tier_of('e'), tier_of('q')
    (0, 7)
"""
import string

TIERS = ("E", "ARTS", "L", "IONC", "DP", "HUBMGY", "FKWV", "XZJQ")

# tier index (0 = best) of every letter, and the check that it IS a partition.
TIER_OF = {c.lower(): i for i, t in enumerate(TIERS) for c in t}
_flat = "".join(TIERS).lower()
assert len(_flat) == len(set(_flat)), "a letter appears in two tiers"
assert set(_flat) == set(string.ascii_lowercase), "the tiers do not cover the alphabet"

# HARD MODE's list (scene 19za) -- the user's cuts (2026-10-03) on the greedy order in
# data/shared/tiers/order_r1_top1000_hardturns.csv, within-tier order as that file
# ranks them. Recorded, not computed, exactly as TIERS is.
HARD_TIERS = ("E", "ATSR", "L", "NIOC", "PD", "HUBMGY", "FKWV", "XZJQ")
_hflat = "".join(HARD_TIERS).lower()
assert len(_hflat) == len(set(_hflat)), "a letter appears in two hard tiers"
assert set(_hflat) == set(string.ascii_lowercase), "the hard tiers do not cover the alphabet"


def tier_of(letter):
    """The tier index of `letter`, 0 = best."""
    return TIER_OF[letter.lower()]


def tier(i):
    """The letters of tier `i` as a lowercase set (negative indexes from the bottom)."""
    return set(TIERS[i].lower())


def bottom(n=1):
    """The letters of the WORST `n` tiers, unioned."""
    if not 1 <= n <= len(TIERS):
        raise ValueError(f"n must be 1..{len(TIERS)}, not {n}")
    return set("".join(TIERS[-n:]).lower())


def top(n=1):
    """The letters of the BEST `n` tiers, unioned."""
    if not 1 <= n <= len(TIERS):
        raise ValueError(f"n must be 1..{len(TIERS)}, not {n}")
    return set("".join(TIERS[:n]).lower())
