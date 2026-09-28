"""The Wordle board — a 6x5 grid of tiles, and the three motions the real game has.

    board = get_board()                      # 6 rows of 5, all empty
    board.type_word(scene, 0, "trace", 1.0)  # letters pop in, left to right
    board.reveal(scene, 0, 0, 1.6)           # the flip cascade, scored by pattern code
    board.bounce(scene, 3, 1.0)              # the winning row's jump

Handles: `.tiles[r][c]` (Square), `.letters[r][c]` (Text or None), `.rows[r]` (VGroup).

COLOURS COME FROM config.py, never from here — `TILE_EMPTY_BORDER`, `TILE_STATE`, …
so the authentic palette can be swapped for brand accents in one place.

THE FLIP IS A HEIGHT SQUASH, and that is a modelling choice worth knowing. Real
Wordle rotates each tile about its horizontal axis, swapping colour at the midpoint.
A 2D Mobject has no rotateX, so `TileFlip` drives the height by |cos| and swaps the
colour as it passes zero — visually identical for a flat tile, and composable in a
LaggedStart so the cascade overlaps the way the real one does. It is a custom
Animation rather than updaters because an updater's lambda cannot be pickled, which
would break the scene's snapshot cache.

A KEYBOARD is not built yet. When one is wanted it belongs here as an option on
`get_board`, not as a second asset — the two share the letter-state bookkeeping.
"""
import numpy as np

from config import *

TILE = 0.9            # side of one tile
GAP = 0.1             # space between tiles
COLS = 5
ROWS = 6
STROKE = 2.5
LETTER_FRAC = 0.58    # letter height as a fraction of the tile


class TileFlip(Animation):
    """One tile's scored reveal: squash to nothing, change colour, come back.

    `alpha` drives the height by |cos(pi*alpha)|, so it reaches zero exactly at the
    half-way point — which is where the fill is swapped, hiding the change the way
    the real flip does.
    """

    def __init__(self, tile, letter, fill, **kwargs):
        self.tile, self.letter, self.fill = tile, letter, fill
        self.h_tile = tile.height
        self.h_letter = letter.height if letter is not None else 0.0
        self.center = tile.get_center()
        self._swapped = False
        group = VGroup(tile) if letter is None else VGroup(tile, letter)
        super().__init__(group, **kwargs)

    def interpolate_mobject(self, alpha):
        a = self.rate_func(alpha)
        scale = max(abs(np.cos(np.pi * a)), 1e-3)
        if a >= 0.5 and not self._swapped:      # past the midpoint: the tile has
            self._swapped = True                # turned over, so show the new face
            self.tile.set_fill(self.fill, opacity=1.0).set_stroke(self.fill, STROKE)
        self.tile.stretch_to_fit_height(self.h_tile * scale)
        self.tile.move_to(self.center)
        if self.letter is not None and self.h_letter:
            self.letter.stretch_to_fit_height(self.h_letter * scale)
            self.letter.move_to(self.center)


class TilePop(Animation):
    """A letter landing in its tile: it appears, and the tile springs and settles.

    `sin(pi*alpha)` is 0 at both ends and 1 in the middle, so the tile returns to
    exactly its own size without the caller doing arithmetic — the same reasoning as
    `there_and_back` in `bounce`.
    """

    def __init__(self, tile, letter, bump=0.10, **kwargs):
        self.tile, self.letter, self.bump = tile, letter, bump
        self.t_h, self.t_w = tile.height, tile.width
        self.l_h, self.l_w = letter.height, letter.width
        self.center = tile.get_center()
        super().__init__(VGroup(tile, letter), **kwargs)

    def interpolate_mobject(self, alpha):
        # Visibility is driven by ALPHA, not set in begin(): an AnimationGroup —
        # which LaggedStart is — calls begin() on EVERY member up front, so
        # revealing there made all five letters of a word appear at once, at the
        # moment the first one was typed. A member that has not reached its lag
        # offset yet sits at alpha 0, which is exactly "not typed".
        self.letter.set_opacity(1.0 if alpha > 0 else 0.0)
        if alpha > 0:
            self.tile.set_stroke(TILE_FILLED_BORDER, STROKE)
        s = 1 + self.bump * np.sin(np.pi * self.rate_func(alpha))
        self.tile.stretch_to_fit_height(self.t_h * s) \
                 .stretch_to_fit_width(self.t_w * s).move_to(self.center)
        self.letter.stretch_to_fit_height(self.l_h * s) \
                   .stretch_to_fit_width(self.l_w * s).move_to(self.center)


class WordleBoard(VGroup):
    def __init__(self, rows=ROWS, cols=COLS, **kwargs):
        super().__init__(**kwargs)
        self.n_rows, self.n_cols = rows, cols
        self.tiles = [[self._tile() for _ in range(cols)] for _ in range(rows)]
        self.letters = [[None] * cols for _ in range(rows)]
        self.rows = []
        for r in range(rows):
            row = VGroup(*self.tiles[r]).arrange(RIGHT, buff=GAP)
            self.rows.append(row)
        VGroup(*self.rows).arrange(DOWN, buff=GAP)
        self.add(*self.rows)

    def _tile(self):
        return Square(side_length=TILE, stroke_width=STROKE,
                      stroke_color=TILE_EMPTY_BORDER,
                      fill_color=TILE_EMPTY_FILL, fill_opacity=1.0)

    def _letter(self, ch, tile):
        t = crisp_text(ch.upper(), color=TILE_TEXT, weight=BOLD)
        # Sized off the tile's CURRENT height, not TILE, so a letter typed into a
        # board that has been shrunk (scene 03's growing column) fits its tile.
        # Identical to TILE * LETTER_FRAC on an unscaled board.
        t.scale_to_fit_height(tile.height * LETTER_FRAC)
        t.move_to(tile.get_center())
        return t

    # ── typing ────────────────────────────────────────────────────────────────
    def type_word(self, scene, row, word, run_time, per_letter=None, key_gap=None):
        """Type `word` into `row`, one letter at a time, left to right.

        TWO WAYS TO TIME IT. By default `run_time` is the whole word and the pops
        overlap (below). With `key_gap`, the PACE of typing and the LOOK of a letter
        landing come apart — a slower typist, not a slow-motion one: `run_time` is
        then ONE letter's pop and `key_gap` the seconds between keystrokes, so a
        letter lands the same way however far apart the keys are. That is the one
        reason for a second timing knob here.

        ONE PLAY for the whole word, not two per letter, and that is what makes
        `run_time` mean what it says. manim rounds every play up to a whole frame,
        so ten little plays round ten times: MEASURED at 60fps, a word asked to take
        0.65s actually took 0.749s — 15% long, and enough to leave a length-matched
        typing bed ending before the letters stop. One LaggedStart rounds once.

        `per_letter(i, ch, at)` fires for each letter with its OFFSET IN SECONDS from
        the start of the word, so the scene can place a sound precisely with
        `self.sfx(name, at=offset)` rather than relying on when the call happens.
        The asset owns no sound policy; the scene does.
        """
        n = max(len(word), 1)
        if key_gap is None:
            lag, total = 1.0 / n, run_time
            at = lambda i: i * run_time / (2 * n - 1)
        else:
            # member duration d = total / (1 + (n-1)*lag) = run_time, starts i*key_gap
            lag, total = key_gap / run_time, run_time + (n - 1) * key_gap
            at = lambda i: i * key_gap
        # lag_ratio 1/n — the pops OVERLAP, which is the look: each letter starts
        # while the previous is still springing, so a typed word reads as one quick
        # gesture rather than five separate stamps. Deliberate, and NOT to be
        # "fixed" into lag_ratio 1.0 (which spaces them evenly and reads stiffer).
        #
        # The consequence to keep in mind is that the letters finish EARLY: manim
        # starts member i at i * lag_ratio * d, so with n=5 the last letter lands at
        # roughly 0.44 of run_time, not at the end. A "sequence" typing bed must be
        # cut to about that, or it plays on after the word already looks typed.
        for i, ch in enumerate(word):
            tile = self.tiles[row][i]
            letter = self._letter(ch, tile)
            letter.set_opacity(0)              # TilePop reveals it on its turn
            self.letters[row][i] = letter
            self.add(letter)
            scene.add(letter)
            if per_letter is not None:
                # The letter's REAL landing time under the overlap, not run_time/n.
                # manim gives each member d = run_time / (1 + (n-1)*lag_ratio) and
                # starts member i at i*lag_ratio*d; at lag_ratio 1/n that reduces to
                # i * run_time / (2n - 1). Using the even spacing instead fired every
                # cue progressively later than the letter it belonged to.
                per_letter(i, ch, at(i))
        pops = [TilePop(self.tiles[row][i], self.letters[row][i])
                for i in range(len(word))]
        scene.play(LaggedStart(*pops, lag_ratio=lag), run_time=total)

    # ── scoring ───────────────────────────────────────────────────────────────
    def reveal(self, scene, row, code, run_time, lag_ratio=0.45, cols=None):
        """Flip `row` to its scored colours. `code` is a wordle.pattern integer.

        POSITION 0 IS THE MOST SIGNIFICANT TRIT of that code — the same convention
        `secondword.py` documents, and the one that silently reverses a row if you
        decode it the other way round.

        `lag_ratio=0` is the QUICK SCORE — all five tiles flip together, which is how
        scene 03 scores a long run of guesses. Each tile still squashes about its own
        centre, so it reads as five simultaneous flips, not the row flipping as one.

        `cols` flips only those positions (in the order given), for a beat that
        scores a row a tile or two at a time — scene 02 explains E, then D, then
        the rest. Pass the SAME full-row code every time; the positions select from
        it, so no caller ever decodes a code itself. None flips the whole row.
        """
        trits = [(code // 3 ** (self.n_cols - 1 - i)) % 3 for i in range(self.n_cols)]
        if cols is None:
            cols = range(self.n_cols)
        flips = [TileFlip(self.tiles[row][i], self.letters[row][i], TILE_STATE[trits[i]])
                 for i in cols]
        scene.play(LaggedStart(*flips, lag_ratio=lag_ratio), run_time=run_time)

    # ── growing past six rows ──────────────────────────────────────────────────
    def add_row(self, scene, run_time, height, center=ORIGIN):
        """Append an empty row, shrinking the whole board so it stays `height` tall.

        For a column of guesses longer than a game (scene 03). The existing rows
        shrink and re-centre while the new row fades in at its final size, in ONE
        play. The new row is built directly at its end pose — it is not on screen
        yet — so it never has to be counter-animated against the shrink.

        Tile and gap keep their RATIO, so the board is the same shape at every size.
        Stroke width does not scale (manim strokes are in pixels); fine at the sizes
        used, but a very long column would read heavy.
        """
        pitch = self.tiles[0][0].width * (1 + GAP / TILE)   # tile + gap, current
        gap = pitch - self.tiles[0][0].width
        last = self.rows[-1]
        row = VGroup(*[self._tile() for _ in range(self.n_cols)])
        row.scale(self.tiles[0][0].width / TILE)             # match current size
        row.arrange(RIGHT, buff=gap).next_to(last, DOWN, buff=gap)
        grown = VGroup(*self.rows, row)
        f = height / grown.height
        c = grown.get_center()
        row.scale(f, about_point=c).shift(center - c)
        # BEHIND the existing rows while they shrink: they start larger and overlap
        # the new row's pose until the shrink finishes, so it emerges from under
        # them. Restored afterwards (nothing overlaps then, so no pop), so the row
        # stacks normally in anything later — a rearrange, say.
        row.set_z_index(-1)
        scene.play(self.animate.scale(f, about_point=c).shift(center - c),
                   FadeIn(row), run_time=run_time)
        row.set_z_index(0)
        self.tiles.append(list(row))
        self.letters.append([None] * self.n_cols)
        self.rows.append(row)
        self.add(row)
        self.n_rows += 1

    # ── the win ───────────────────────────────────────────────────────────────
    def bounce(self, scene, row, run_time, height=0.35, lag_ratio=0.12):
        """The winning row's jump — each tile up and back, staggered.

        ONE animation with `there_and_back`, NOT a Succession of up-then-down.
        `.animate` fixes its target when it is CONSTRUCTED, so a down-shift built
        alongside the up-shift takes the ORIGINAL position as its reference and
        targets `y - height` — landing the row a whole `height` below where it
        started. `there_and_back` ends its rate function at 0, so the row returns
        to exactly its starting position by construction rather than by arithmetic.
        """
        ups = []
        for i in range(self.n_cols):
            parts = [self.tiles[row][i]]
            if self.letters[row][i] is not None:
                parts.append(self.letters[row][i])
            ups.append(VGroup(*parts).animate(rate_func=there_and_back)
                       .shift(UP * height))
        scene.play(LaggedStart(*ups, lag_ratio=lag_ratio), run_time=run_time)


def get_board(**kwargs):
    return WordleBoard(**kwargs)


def get_scored_row(word, code):
    """One already-scored row, static: `word`'s tiles in their final colours with
    the letters on top — exactly what `type_word` + `reveal` leave behind, built
    directly. `code` is a wordle.pattern integer (position 0 most significant)."""
    row = WordleBoard(rows=1, cols=len(word))
    trits = [(code // 3 ** (row.n_cols - 1 - i)) % 3 for i in range(row.n_cols)]
    for i, (ch, t) in enumerate(zip(word, trits)):
        tile = row.tiles[0][i]
        tile.set_fill(TILE_STATE[t], opacity=1.0).set_stroke(TILE_STATE[t], STROKE)
        letter = row._letter(ch, tile)
        row.letters[0][i] = letter
        row.add(letter)
    return row
