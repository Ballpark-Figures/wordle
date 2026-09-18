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
                      stroke_color=TILE_EMPTY_BORDER, fill_opacity=0)

    def _letter(self, ch, tile):
        t = crisp_text(ch.upper(), color=TILE_TEXT, weight=BOLD)
        t.scale_to_fit_height(TILE * LETTER_FRAC)
        t.move_to(tile.get_center())
        return t

    # ── typing ────────────────────────────────────────────────────────────────
    def type_word(self, scene, row, word, run_time, per_letter=None):
        """Type `word` into `row`, one letter at a time, left to right.

        ONE run_time covers the whole word; each letter gets an equal share, split
        between its pop out and back. `per_letter(i, ch)` fires as each letter lands
        — the hook the SCENE uses to make a sound, so this asset owns no sound
        policy and the two typing-sound approaches can be swapped without touching
        the board.
        """
        share = run_time / max(len(word), 1)
        for i, ch in enumerate(word):
            tile = self.tiles[row][i]
            letter = self._letter(ch, tile)
            self.letters[row][i] = letter
            self.add(letter)
            if per_letter is not None:
                per_letter(i, ch)
            tile.set_stroke(TILE_FILLED_BORDER, STROKE)
            scene.add(letter)
            scene.play(tile.animate.scale(1.10), letter.animate.scale(1.10),
                       run_time=share * 0.45)
            scene.play(tile.animate.scale(1 / 1.10), letter.animate.scale(1 / 1.10),
                       run_time=share * 0.55)

    # ── scoring ───────────────────────────────────────────────────────────────
    def reveal(self, scene, row, code, run_time, lag_ratio=0.45):
        """Flip `row` to its scored colours. `code` is a wordle.pattern integer.

        POSITION 0 IS THE MOST SIGNIFICANT TRIT of that code — the same convention
        `secondword.py` documents, and the one that silently reverses a row if you
        decode it the other way round.
        """
        trits = [(code // 3 ** (self.n_cols - 1 - i)) % 3 for i in range(self.n_cols)]
        flips = [TileFlip(self.tiles[row][i], self.letters[row][i], TILE_STATE[t])
                 for i, t in enumerate(trits)]
        scene.play(LaggedStart(*flips, lag_ratio=lag_ratio), run_time=run_time)

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
