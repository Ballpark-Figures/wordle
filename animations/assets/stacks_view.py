"""The camera, emphasis and callouts for a WordStacks histogram — shared by scenes 01
and 08 (extracted from 01intro.py when 08 became the second user; 01's behaviour is
unchanged).

    class Scene08(StacksView, MovingCameraScene, WordleBoardScene):
        def __init__(self, **kw):
            super().__init__(camera_class=StacksCamera, **kw)
        def _callout_row(self, word):          # REQUIRED: the word a callout shows
            return ...

    self.stacks, self.view, self.callouts = WordStacks(...), (l, b, w, s), []
    self._apply_view(self.view)
    self._move_view(to_view, run_time=2.0, whoosh=True, dim=1.0, weights={...},
                    appear=["salet"], callout_alpha={"qajaq": 0.0})

A VIEW is (frame left, frame bottom, frame width, squash). `_move_view` interpolates
left and bottom linearly and width and squash geometrically, and rebuilds the stacks
every frame from it. Frames are anchored bottom-left, so a zoom keeps the
histogram's corner steady rather than swinging round a centre. A move to the SAME
view is how emphasis changes and callouts appear while the camera is still.

EMPHASIS is per word (`weights`, which FADE) or, for a bar-mode histogram, a lit
LEVEL per bar (`level`, an array over `stacks.bar_bins`), which RISES and FALLS
continuously, every bar moving in step, the way a growing bar does.

CALLOUTS — a word, joined to its word in the histogram by a white line, sized in
SCREEN terms (a fraction of the frame width) so it stays legible through any zoom.
Two placements, per callout:
  - above (01's): the line rises CALLOUT_LIFT of the frame from the word's top edge,
    leaning `CALLOUT_DX[word]` of the frame sideways, and the callout sits on its tip;
  - pinned (08's): `_callout_spec(word)` returns `pinned(fx, fy, ...)`, putting a point of the
    callout (its `attach`) at that fraction of the frame, and the line runs to a
    chosen point of the word's slice (its `anchor`: the side facing the callout, or
    the centre). The spec is all numbers, so `_move_view(retarget=...)` can glide a
    callout from one placement to another while the camera moves.
Either way the callout GROWS in: the line draws out and the word grows from its tip.

Hooks a scene may override:
  _callout_row(word)          the mobject a callout shows (REQUIRED)
  _callout_stroke(row, w)     restyle a callout's strokes for frame width w (strokes
                              are in world units, so they thin as the camera zooms out)
  _place_overlay()            called every frame of a move, after the view is applied,
                              to re-place anything else sized in screen terms
"""
import numpy as np

from config import *
from assets.board import TILE
from assets.word_stacks import WORD_W
from bpkfigures.sfx import sfx_path, wav_info

ASPECT = 16 / 9
FRAME_W = 16.0
CALLOUT_W = 0.12              # a callout word's width, as a fraction of frame width
CALLOUT_LIFT = 0.05           # line length, as a fraction of frame height
CALLOUT_GROW = 0.3            # seconds for a callout (line + word) to grow in
TILE_OVER_WORD = TILE / WORD_W   # a scored row's height over its width
LINE_STROKE = 3.0             # line width as it would be in a 16-wide frame
PING_SFX = "notify-app-03"    # a word emphasised / called out
PING_GAIN = -6.0              # dB — played quieter than the library's level
WHOOSH_SFX = "whoosh"         # under every camera move
WHOOSH_GAIN = -8.0            # dB — played quieter than the library's level
WHOOSH_PEAK = 0.5             # s into the whoosh file where it is loudest (MEASURED
                              # at import: -4.4 dB at 0.4s, -4.2 at 0.6s); a move's
                              # whoosh is placed to peak at the move's midpoint, its
                              # fastest moment, since every move eases in and out

_SIDES = {"bottom": (0.0, -1.0), "top": (0.0, 1.0), "left": (-1.0, 0.0),
          "right": (1.0, 0.0)}


def pinned(fx, fy, attach="bottom", anchor="edge", w=CALLOUT_W, x=None):
    """A pinned callout: its `attach` side ("bottom", "top", "left", "right") sits at
    (fx, fy) of the frame, `w` of the frame wide; its line runs to the slice's side
    facing it (`anchor="edge"`) or to the slice's centre (`anchor="center"`). `x`, a
    world x, moves the line's end sideways to exactly there (a value on the axis)."""
    a = np.array(_SIDES[attach])
    b = -a if anchor == "edge" else np.zeros(2)
    return {"at": np.array([fx, fy], float), "attach": a, "anchor": b, "w": float(w),
            "x": np.nan if x is None else float(x)}


def _lerp_spec(s0, s1, u):
    return {k: s0[k] + (s1[k] - s0[k]) * u for k in s0}


class StacksView:
    CALLOUT_DX = {}               # above-callouts: sideways lean, fraction of frame width
    CALLOUT_AT = {}               # pinned callouts: word -> pinned(...)

    # ── hooks ─────────────────────────────────────────────────────────────────
    def _callout_row(self, word):
        raise NotImplementedError

    def _callout_spec(self, word):
        """`word`'s pinned placement, or None for an above-callout. A scene should
        override this to read a MODULE constant: a class attribute is invisible to
        the snapshot digest, so editing one would not re-render."""
        return self.CALLOUT_AT.get(word)

    def _callout_stroke(self, row, w):
        pass

    def _place_overlay(self):
        pass

    # ── the view ──────────────────────────────────────────────────────────────
    def _set_frame(self, left, bottom, w):
        f = self.camera.frame
        f.stretch_to_fit_width(w).stretch_to_fit_height(w / ASPECT)
        f.move_to([left + w / 2, bottom + w / ASPECT / 2, 0])

    def _apply_view(self, v):
        left, bottom, w, s = v
        self._set_frame(left, bottom, w)
        self.stacks.set_state(squash=s)

    @staticmethod
    def _lerp_view(fr, to, u):
        """The view part-way from `fr` to `to`: left and bottom linearly, width and
        squash geometrically."""
        lin = lambda a, b: a + (b - a) * u
        geo = lambda a, b: float(np.exp(lin(np.log(a), np.log(b))))
        return (lin(fr[0], to[0]), lin(fr[1], to[1]), geo(fr[2], to[2]),
                geo(fr[3], to[3]))

    # ── callout geometry ──────────────────────────────────────────────────────
    def _callout_geom(self, word, view, spec=None):
        """(anchor, target, attach, width) of `word`'s callout at `view`: the line
        runs from `anchor` on the word to `target`, where the full-size callout's
        `attach` point sits (a vector in half-sizes of the callout: (0, -1) is its
        bottom-centre); `width` is the full-size callout's width. `spec` is a
        pinned() placement, or None for an above-callout."""
        left, bottom, w, s = view
        h = w / ASPECT
        l, b, r, t = self.stacks.word_box(word, squash=s)
        cx, cy = (l + r) / 2, (b + t) / 2
        if spec is not None:
            target = np.array([left + spec["at"][0] * w, bottom + spec["at"][1] * h, 0])
            anchor = np.array([cx + spec["anchor"][0] * (r - l) / 2,
                               cy + spec["anchor"][1] * (t - b) / 2, 0.0])
            if not np.isnan(spec["x"]):
                anchor[0] = spec["x"]
            return anchor, target, spec["attach"], spec["w"] * w
        anchor = np.array([cx, t, 0.0])
        target = anchor + UP * CALLOUT_LIFT * h + RIGHT * self.CALLOUT_DX.get(word, 0) * w
        return anchor, target, np.array(_SIDES["bottom"]), CALLOUT_W * w

    def _callout_fits(self, word, view, spec=None):
        """True once `word` AND its full-size callout are both inside `view`."""
        left, bottom, w, s = view
        h = w / ASPECT
        l, b, r, t = self.stacks.word_box(word, squash=s)
        _, (tx, ty, _), att, cw = self._callout_geom(word, view, spec)
        ch = cw * TILE_OVER_WORD
        mx, my = tx - att[0] * cw / 2, ty - att[1] * ch / 2        # its centre
        box = (mx - cw / 2, my - ch / 2, mx + cw / 2, my + ch / 2)
        return (left <= min(l, box[0]) and max(r, box[2]) <= left + w
                and bottom <= min(b, box[1]) and max(t, box[3]) <= bottom + h)

    # ── callouts ──────────────────────────────────────────────────────────────
    def _callout(self, word):
        """Build a callout for `word`, not yet grown in, and register it."""
        row = self._callout_row(word)
        line = Line(ORIGIN, UP, color=WHITE)
        spec = self._callout_spec(word)
        c = {"word": word, "row": row, "line": line, "g": 0.0, "a": 1.0,
             "spec": None if spec is None else dict(spec)}
        self.callouts.append(c)
        self.add(line, row)
        return c

    def _place_callouts(self):
        """Put every callout in place at the current view.

        `g` grows it in: the line draws out from the word and the full-size callout
        GROWS FROM THE LINE'S TIP along with it, both at once. `a` scales the whole
        callout's opacity."""
        f = self.camera.frame
        w = f.width
        view = (f.get_left()[0], f.get_bottom()[1], w, self.stacks.squash)
        for c in self.callouts or []:
            row, line, g = c["row"], c["line"], c["g"]
            anchor, target, att, cw = self._callout_geom(c["word"], view, c["spec"])
            tip = anchor + (target - anchor) * max(g, 1e-3)
            line.put_start_and_end_on(anchor, tip)
            line.set_stroke(WHITE, width=LINE_STROKE * w / FRAME_W,
                            opacity=c["a"] if g > 0 else 0.0)
            row.scale_to_fit_width(cw * max(g, 1e-2))
            self._callout_stroke(row, w)
            row.move_to(tip - np.array([att[0] * row.width / 2,
                                        att[1] * row.height / 2, 0]))
            row.set_opacity(c["a"] if g > 0 else 0.0)

    def _drop_callouts(self, words):
        """Remove the named callouts (faded out already) from the scene."""
        keep = []
        for c in self.callouts or []:
            if c["word"] in words:
                self.remove(c["row"], c["line"])
            else:
                keep.append(c)
        self.callouts = keep

    # ── moving ────────────────────────────────────────────────────────────────
    def _move_view(self, to, run_time, letters=None, dim=None, weights=None,
                   appear=(), present=(), callout_alpha=None, extra=(),
                   rate_func=smooth, whoosh=False, level=None, retarget=None,
                   fade_time=None):
        """Animate the view (and optionally letter opacity / emphasis) to `to`.

        `appear` words get their callout THE MOMENT THEY ARE ON SCREEN — the first
        point on this move's path where the word and its full-size callout both fit —
        with PING_SFX at that instant; the word lights up as its callout grows in over
        CALLOUT_GROW seconds. `present` callouts are created already fully grown (for
        words off screen, waiting to be revealed). `callout_alpha` fades every
        callout on screen to that opacity — or, as a {word: opacity} dict, only the
        callouts it names — over the whole move, or over its first `fade_time`
        seconds. `retarget` {word: pinned(...)} glides pinned callouts to new
        placements. `level` moves a bar-mode histogram's lit level to that array,
        every bar in step. `whoosh` plays WHOOSH_SFX with its loudest moment at the
        move's midpoint.

        The stacks are rebuilt every frame from the interpolated view. The updater
        is REMOVED before returning, so nothing unpicklable reaches the snapshot."""
        if whoosh:
            self.sfx(WHOOSH_SFX, at=max(0.0, run_time / 2 - WHOOSH_PEAK),
                     gain=WHOOSH_GAIN)
        fr = self.view
        l0, d0 = self.stacks.letter_opacity, self.stacks.dim
        l1 = l0 if letters is None else letters
        d1 = d0 if dim is None else dim
        w1 = weights or {}
        w0 = self.stacks.weights_of(w1)
        v0 = (np.zeros(len(self.stacks.bar_bins)) if self.stacks.level is None
              else self.stacks.level.copy())
        lit0 = self.stacks.weights_of(appear)   # an appearing word never dims below this
        # the play's clock: eased value u <-> seconds in
        ts = np.linspace(0, 1, 2001)
        us = np.array([rate_func(a) for a in ts])
        enter = {}
        for word in appear:
            self._callout(word)
            spec = self._callout_spec(word)
            u_in = next((u for u in np.linspace(0, 1, 401)
                         if self._callout_fits(word, self._lerp_view(fr, to, u), spec)),
                        1.0)
            enter[word] = min(float(np.interp(u_in, us, ts)) * run_time,
                              run_time - CALLOUT_GROW)
            self.sfx(PING_SFX, at=enter[word], gain=PING_GAIN)
        for word in present:
            self._callout(word)["g"] = 1.0
        a0 = {c["word"]: c["a"] for c in self.callouts or []}
        if callout_alpha is None:
            a1 = {}
        elif isinstance(callout_alpha, dict):
            a1 = dict(callout_alpha)
        else:
            a1 = {wd: callout_alpha for wd in a0}
        specs = {c["word"]: (dict(c["spec"]), retarget[c["word"]])
                 for c in self.callouts or [] if retarget and c["word"] in retarget}
        t = ValueTracker(0)

        def upd(m):
            u = t.get_value()
            secs = float(np.interp(u, us, ts)) * run_time
            self._apply_view(self._lerp_view(fr, to, u))
            wts = {w: w0[w] + (w1[w] - w0[w]) * u for w in w1}
            if level is not None:
                m.set_state(level=v0 + (np.asarray(level) - v0) * u)
            fa = u if fade_time is None else float(np.clip(secs / fade_time, 0, 1))
            for c in self.callouts or []:
                if c["word"] in enter:
                    c["g"] = float(np.clip((secs - enter[c["word"]]) / CALLOUT_GROW, 0, 1))
                    wts[c["word"]] = max(wts.get(c["word"], lit0[c["word"]]), c["g"])
                if c["word"] in a1:
                    c["a"] = a0[c["word"]] + (a1[c["word"]] - a0[c["word"]]) * fa
                if c["word"] in specs:
                    c["spec"] = _lerp_spec(*specs[c["word"]], u)
            m.set_state(letters=l0 + (l1 - l0) * u, dim=d0 + (d1 - d0) * u, weights=wts)
            m.refresh(self.camera.frame)
            self._place_callouts()
            self._place_overlay()

        self.stacks.add_updater(upd)
        self.play(t.animate.set_value(1), *extra, run_time=run_time,
                  rate_func=rate_func)
        self.stacks.remove_updater(upd)
        self.remove(t)
        self.view = to
        # let a callout's ping RING OUT inside this beat: one that starts late in the
        # move would otherwise run into the trailing hold, which the stitch trims and
        # the edit covers with a silent still
        if enter:
            tail = max(enter.values()) + wav_info(sfx_path(PING_SFX))[0] - run_time
            if tail > 0:
                self.wait(tail)
