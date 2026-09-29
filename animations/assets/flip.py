"""Flip anything into anything — the Wordle tile's squash, generalised.

    scene.play(Flip(old, new, run_time=0.4))                 # one thing into another
    Flip(old_row, new_row, parts=(row_parts(old_row), row_parts(new_row)),
         travel=True)                                        # a word, tile by tile,
                                                             # while it moves
    flip(scene, [(old_word, new_word), ...], run_time=1.0)   # several, cleaned up

Each part of `old` squashes flat about its own centre (height as |cos(pi*a)|); at
its midpoint it vanishes and the matching part of `new` grows back from flat.
Either may be any mobject — a tile, a letter, a glyph, a scored row, a whole word —
and they need not look alike: that is the point. board.TileFlip and
pigpen.GlyphFlip are the same motion specialised to one change each; new code
should use this.

PARTS flip one after another, left to right, lag_ratio apart (LaggedStart's
schedule) — a word's tiles. Without parts the whole thing flips at once.

TRAVEL: `new` is placed where it will END. Without travel, old flips in place and
new appears in place (they should coincide). With travel=True the whole thing
also slides and resizes, smoothly and as one, from old's box to new's box while
its parts flip — so a row can change colouring and move to a new slot at once.
The row's motion is one continuous transform; only the squash is per part.

NOTHING IS HIDDEN BY TOUCHING OPACITY OUTSIDE THE ANIMATION. Every frame each part
is rebuilt from a snapshot taken at the start (become), then transformed, then the
face not showing is set transparent — so a LaggedStart calling begin() early
cannot leave anything half-shown (board.TilePop's reason), and the old parts end
exactly as they started (hidden) for the caller to remove.

USE `flip()` TO PLAY THEM, not scene.play on the raw animations. play() adds each
animation's wrapper group to the scene, and a wrapper keeps whatever it holds on
screen after the caller removes the real mobject — which left old tiles behind as
ghosts in scene 06 (2026-09-28). `flip()` removes the wrappers and the old things
and leaves exactly the new ones on screen. For the same reason, a Flip joining a
larger play goes through `flip(..., extra=...)`.
"""
import numpy as np

from config import *


def _hide(mob):
    for m in mob.family_members_with_points():
        m.set_fill(opacity=0.0, family=False)
        m.set_stroke(opacity=0.0, family=False)


class Flip(Animation):
    """`old` turns over into `new` — see the module docstring."""

    def __init__(self, old, new, parts=None, lag_ratio=0.25, travel=False, **kwargs):
        self.old, self.new, self.travel = old, new, travel
        olds, news = parts if parts is not None else ([old], [new])
        self.pairs = list(zip(olds, news))
        self.snap = [(o.copy(), n.copy()) for o, n in self.pairs]
        self.c_old, self.c_new = old.get_center(), new.get_center()
        self.w_old, self.w_new = old.width, new.width
        k = len(self.pairs)
        self.d = 1.0 / (1 + (k - 1) * lag_ratio)          # one part's share of time
        self.starts = [i * lag_ratio * self.d for i in range(k)]
        super().__init__(Group(old, new), **kwargs)

    def _frame(self, a):
        """Where the whole thing is at `a`: (centre, scale for old, scale for new)."""
        if not self.travel:
            return None
        c = self.c_old + (self.c_new - self.c_old) * a
        w = self.w_old + (self.w_new - self.w_old) * a
        return c, w / self.w_old, w / self.w_new

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        frame = self._frame(a)
        for (o, n), (o0, n0), t0 in zip(self.pairs, self.snap, self.starts):
            ai = min(max((a - t0) / self.d, 0.0), 1.0)
            s = max(abs(np.cos(np.pi * ai)), 1e-3)
            o.become(o0)
            n.become(n0)
            if frame is not None:
                c, k_old, k_new = frame
                o.scale(k_old, about_point=self.c_old).shift(c - self.c_old)
                n.scale(k_new, about_point=self.c_new).shift(c - self.c_new)
            if ai < 0.5:
                o.stretch(s, 1)
                _hide(n)
            else:
                n.stretch(s, 1)
                _hide(o)


def flip(scene, flips, run_time, extra=()):
    """Play `flips` (Flip animations) and `extra` animations together, then clean
    up: every Flip's old and every wrapper off the scene, every new on it."""
    news = [f.new for f in flips]
    scene.add(*news)
    scene.play(*flips, *extra, run_time=run_time)
    scene.remove(*[f.mobject for f in flips], *[f.old for f in flips])
    scene.add(*news)


def row_parts(row):
    """A scored row's (board.get_scored_row) or a decoded word's (PigpenWord) tiles,
    each grouped with the letter on it, in order — the parts a word flips by."""
    tiles = row.tiles[0] if isinstance(row.tiles[0], list) else row.tiles
    faces = row.letters[0] if isinstance(row.letters[0], list) else row.letters
    return [VGroup(t, f) for t, f in zip(tiles, faces)]
