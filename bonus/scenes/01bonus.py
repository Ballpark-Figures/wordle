"""BONUS video graphics — no script. Each graphic is one @still method, added on
request ("make a table of ..."), and renders as one PNG.

Render from bonus/scenes/ with --stills so it lands in DaVinci:

    render 01a --stills

That copies the PNG to <repo>/edit_clips_bonus/ and imports it into the `Bonus`
bin of the open DaVinci project; a re-render refreshes it in place, including any
copy already on the timeline. The main video's edit_clips/ and bins are untouched.

Every number shown is READ from the pipeline's committed files, never typed in.

BEAT MAP (one line per graphic, in the video's order; [NOT BUILT] slots raise
until built, so every letter is fixed from the start):
  a   part1 — title card "Part 1: Wordle"
  b   antiwordle — title card "Antiwordle"
  c   antiwordle_chain — the 16-word antiwordle chain (scene 03's) as one giant scored board
  d   color_groups — title card "Color Groups"
  e   optimal_strategy — title card "The Optimal Strategy"
  f   word_list_changes — title card "Word List Changes"
  g   alphabet_tier_list — title card "Alphabet Tier List"
  h   vowels — title card "Vowels"
  i   speedrunning — title card "Speedrunning"
  j   multi_word_openers — title card "Multi-Word Openers"
  k   ledge_pawns — LEDGE PAWNS ROCKY THUMB scored as FALSE/SALLE/SALVE all score it, the three words beside it (scene 15r's layout)
  l   pokecheese — Pokecheese's video on YouTube's dark watch page + the citation footnote
  m   multiwordle — title card "Multiwordle"
  n   multi_openers — table: best 1/2/3-word opener + average misses per k, best of every race (scene 16's chart rule)
  o   multi_openers_answers — the same, answers-only races
  p   more_color_groups — title card "More Color Groups"
  q   casework_tree — TRINE (3.606637, the best casework result): its 17 reply cases in scene 18's tree pieces
  r   hard_mode — title card "Hard Mode"
  s   part2 — title card "Part 2: Variants"
  t   sea_of_greens — title card "Sea of Greens"
  u   sea_of_greens_page — the Sea of Greens badge page in a browser window (scene 25a's)
  v   greens_all_grey — the may-lose 6-guess, full-width strategy's all-grey path (BOOBY), as a board
  w   greens_uncapped — the uncapped strategy's all-grey path and longest path, two columns
  x   wordle_in_one — title card "Wordle in One"
  y   wordle_in_one_page — Wordle in One in a browser window (scene 25b's)
  z   in_one_table — Wordle in One games per colour combination (answers-only guesses) + total, scene 17's combo table, no bars
  za  hard_to_guess — title card "Hard-to-Guess Words"
  zb  adversarial — the adversarial search's top letter patterns and words, hangman's two tables in the Wordle look
  zc  changing_word_lists — title card "Changing Word Lists"
  zd  list_grid — 3x3 grid, guess list x answer list: best opener, average, exact or k, one cell Impossible
  ze  lingo — title card "Lingo"
  zf  lingo_page — the Lingo (American game show) Wikipedia page in a browser window
  zg  lingo_table — Lingo 5-letter (answers only, 5 guesses): best opener per starting letter, two halves
  zh  lingo6_table — Lingo 6-letter (answers only, 5 guesses): best opener per starting letter, two halves
  zi  other_languages — title card "Other Languages"
  zj  languages_table — best opener + average per language (answers only, k = 30)
  zk  mastermind_rules — title card "Mastermind Rules"
  zl  absurdle — title card "Absurdle"
  zm  absurdle_page — Absurdle in a browser window
  zn  absurdle_sequence — the 4-guess Absurdle win as a board, options left beside each row
  zo  letroso — title card "Letroso"
  zp  letroso_page — Letroso's home page in a browser window
  zq  letroso_table — top 10 Letroso first guesses by average options left
  zr  foximax — title card "Foximax"
  zs  foximax_page — Foximax in a browser window
  zt  foximax_histogram — words per game over 1,000,000 simulated Foximax games, horizontal bars
  zu  nerdle — title card "Nerdle"
  zv  nerdle_page — Nerdle's classic game in a browser window
  zw  nerdle_symbols — each symbol's share of the 17,723 answer equations containing it
  zx  nerdle_openers — 48-32=16 above the pair 47-11=36, 2*029=58, typed tile rows
  zy  bad_wordle — title card "Bad Wordle"
  zz  rasmussen — Ellie Rasmussen's video on YouTube's dark watch page (scene 09a's)
  zza vowelless — every legal guess with no AEIOUY, typed rows
  zzb eight_words — the 8-word no-shared-letter solution, typed rows (EXEEM or EXEME)
  zzc vowelless_triples — the 10 triples of the vowel-less words, letters shared within a triple in red
  zzd answers_from_combos — title card "Answers from Color Combos"
  zze conclusion — title card "Conclusion"
  zzf today_board — channel post, not in the video: NEWER WORDY VIDEO HOURS AFTER scored against TODAY, TODAY unscored

EVERY bonus still is on BOARD_NAVY (user's call, 2026-10-10: the main video is
almost all navy), hence the WordleBoardScene base.

REUSE MAP — every kind of still copies the MAIN VIDEO's own version of it.
Before the FIRST still of a new kind, find that version in animations/scenes/ and
add a line here; every later still of the kind follows the line.
  table      -> animations/assets/navy_table.py `navy_table`: scenes 10/14/19's
                convention (no card, white title, bold white heads, faint white
                stripes on the navy), collected into one function. NOT
                bpkfigures.table.get_table, which is the cream-card table.
  browser    -> bpkfigures/browser.py `browser_window` at scene 24/25's width
                (WIN_W 13.2); page screenshots from animations/assets/web_shots.py
                recipes into assets/web_media/ (scene 25's REUSE MAP).
  title card -> yahtzee/animations/scenes/00transitions.py `_card` (Wordle has no
                title cards): crisp_text BOLD, built at TITLE_BASE_FS and scaled by
                TITLE_SCALE (so it never wraps), centred. WHITE, not yahtzee's
                black, because it sits on navy: the main video's titles on navy
                are white (08histogram.py's heading).
  board      -> animations/assets/board.py `get_scored_row` rows, as scene 03 and
                today_board; a long chain sized as scene 03a's finished column.
"""
import csv
import re
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import *
from assets.navy_table import navy_table

MATH = Path(__file__).resolve().parents[2] / "math"
DATA = Path(__file__).resolve().parents[2] / "math" / "data" / "shared"

# title cards: yahtzee 00transitions' values, carried over verbatim
TITLE_BASE_FS = 20     # built at this (under the crisp_text wrap threshold)...
TITLE_SCALE = 3.0      # ...then scaled to its final size

CHAIN_MARGIN = 0.4     # scene 03's COLUMN_MARGIN: space above and below the 16-row column
WEB_MEDIA = Path(__file__).resolve().parents[2] / "animations" / "assets" / "web_media"
WIN_W = 13.2           # scene 24/25's browser window width
# (screenshot, address, the page's own tab title) -- scene 25's BADGE and IN_ONE
PAGE_BADGE = ("sea_of_greens", "nytimes.com/games/wordle/2026-07-10",
              "Friday, July 10, 2026 Wordle puzzle — The New York Times")
PAGE_IN_ONE = ("wordle_in_one_puzzle",
               "nytimes.com/games/bonus/wordle-in-one/standard/2026-10-07-8",
               "Wednesday, October 7, 2026 Wordle in 1 — Bonus Puzzles — The New York Times")
TRINE_CSV = DATA / "secondexact" / ("exact_e3_nz01.e3_nz02.e3_nz03.e3_nz04.e3_nz12."
    "e3_nz13.e3_nz14.e3_nz23.e3_nz24.e3_nz34.e4_nz0.e4_nz1.e4_nz2.e4_nz3.e4_nz4.e5_k200_3group2dec.csv")
TREE_COLS = 6          # q: cases per row of the grid
TREE_ROW_W = 1.9       # q: a pattern / word row's width
TREE_OPENER_W = 3.2    # q: TRINE's row at the top (18's SLANT is row_width() ~ 3.3)
TREE_LINK = 0.3        # q: pattern row to second word (18's RCA_LINK 0.35, tighter)
TREE_LINK3 = 0.45      # q: second word to third word, room for the label
TREE_LABEL_FS = 18     # q: "1 matched" on a third-word branch (no precedent)
TREE_LABEL_BUFF = 0.1  # q: the label's gap right of the branch line
TREE_CARD_FS = 22      # q: the decline case's RCA card text (18's MARKER_FS 30)
TREE_COL_GAP = 0.45
TREE_ROW_GAP = 0.45
TREE_TOP = 0.45        # q: TRINE / the average from the frame's top / bottom
TREE_GAP = 0.4         # q: the grid's clearance under TRINE and above the average
GREENS_D6_TREE = DATA / "greens" / "trees_d6_k13000" / "booby.txt.gz"
GREENS_UNCAPPED_TREE = DATA / "greens" / "trees_uncapped" / "booby.txt.gz"
PATH_COL_GAP = 1.5     # w: between the two path columns
IN_ONE_CSV = DATA / "singletons" / "wordle_in_one_breakdown.csv"   # guesses = the 2315 answers
# z: scene 17's table of combinations, its values
CC_TITLE_Y = 3.85      # 17's TITLE_Y
CC_TOP_ROW_Y = 3.1     # 17's TOP_ROW_Y
CC_ROW_TILE = 0.25     # 17's ROW_TILE
CC_ROW_PITCH = 0.34    # 17's ROW_PITCH
CC_GROUP_GAP = 0.16    # 17's GROUP_GAP, between gray-count groups
CC_VAL_GAP = 0.6       # 17's VAL_GAP
CC_BOTTOM = 0.3        # z: the total row's clearance above the frame's bottom
TABLE_TILE_H = 0.5     # a tile row inside a table (row pitch 0.72)
# zd: (guess list, answer list) -> (file, how it was found); 0 Answers, 1 Guesses,
# 2 All Letter Combos. The widest beam with a result in each cell; None = Impossible
# (no run: answer words as guesses cannot reach every string).
GRID_CELLS = {
    (0, 0): ("ansturns/opener_totals.csv", "Exact"),
    (1, 0): ("optturns/opener_totals.csv", "Exact"),
    (2, 0): ("strguess/opener_totals_mystery_d6_k100.csv", "k = 100"),
    (0, 1): ("ansall/optimal_d7_k100.csv", "k = 100"),
    (1, 1): ("allwords/opener_totals_k1.csv", "k = 1"),
    (2, 1): ("strguess/opener_totals_guess_d7_k20.csv", "k = 20"),
    (0, 2): None,
    (1, 2): ("strturns/opener_totals_d9-30_k1_cls.csv", "k = 1"),
    (2, 2): ("strsts/opener_totals_d30_k1_sn512.csv", "k = 1"),
}
HEADER_SIZE = 28       # the video's table heads (scene 10's)
GRID_VAL_FS = 30       # zd: a cell's average (scene 10's CELL_SIZE)
GRID_NOTE_FS = 22      # zd: "Exact" / "k = 100" under it (no precedent)
GRID_COL_W = 3.6       # zd: column pitch
GRID_ROW_H = 2.0       # zd: row pitch (a cell: tiles, average, note)
GRID_X, GRID_Y = 1.6, -0.4   # zd: the middle cell's centre
GRID_INNER = 0.12      # zd: between a cell's three lines
GRID_HEAD_GAP = 0.35   # zd: the column heads above the top row
GRID_LABEL_GAP = 0.3   # zd: the row labels left of the first column
GRID_AXIS_GAP = 0.35   # zd: "Answer List" / "Guess List" beyond the heads / labels
STRIPE_OVERHANG = 0.5  # 14's / 19's STRIPE_PAD
# the live pages, captured by web_shots.py; addresses and tab titles read off them
PAGE_LINGO = ("lingo_wiki", "en.wikipedia.org/wiki/Lingo_(American_game_show)", "Lingo (American game show) - Wikipedia")
PAGE_ABSURDLE = ("absurdle", "qntm.org/files/absurdle/absurdle.html", "Absurdle @ Things Of Interest")
PAGE_LETROSO = ("letroso", "letroso.com/en", "Letroso")
PAGE_FOXIMAX = ("foximax", "foximax.com", "FoxiMax")
PAGE_NERDLE = ("nerdle", "nerdlegame.com", "Nerdle - daily number puzzles, brain-teasers & math games")
LANG_CSV = DATA / "langans" / "topk30_len5_ascii.csv"   # widest finished k (k50: header only)
LANG_NAMES = {"ca": "Catalan", "cs": "Czech", "de": "German", "en": "English",
              "es": "Spanish", "fi": "Finnish", "fr": "French", "it": "Italian",
              "nb": "Norwegian", "nl": "Dutch", "pl": "Polish", "pt": "Portuguese",
              "sv": "Swedish"}
ABSURDLE_TXT = DATA / "absurdle" / "one_shortest_solution.txt"
ABS_COUNT_FS = 48      # zn: the options-left numbers beside the board's rows
ABS_COUNT_GAP = 1.0    # zn: board to the numbers
ABS_HEAD_GAP = 0.45    # zn: "Options Left" above the board's top
# zq: fingerprint fa3d3ea0526042a0 == the current lists (checked 2026-10-11)
LETROSO_RANK = DATA / "letroso" / "root_rank_lengths.csv.gz"
LETROSO_TOP = 10
FOXIMAX_CSV = DATA / "foximax" / "t1000000_s0.csv"     # the largest run (seed 0)
FOXIMAX_GAMES = 1_000_000
FOX_LEN = 7.0          # zt: the axis the bars stand on (vertical here)
FOX_H = 9.0            # zt: the longest bar
FOX_TITLE_DROP = 0.4   # zt: the chart sits this far below centre, room for the title
FOX_TITLE_GAP = 0.5    # zt: get_histogram's title gap
NERDLE_SOLVE = DATA / "nerdle" / "solve_w8_k1.csv"
NERDLE_PAIRS = DATA / "nerdle" / "pairs_w8_n30000_incumbents.csv"
NERDLE_TILE_H = 1.1    # zx: a row's height (the board's tile is ~1.0)
NERDLE_ROW_GAP = 0.12  # zx: between the pair's rows (the board's GAP-ish)
NERDLE_BLOCK_GAP = 1.0 # zx: the single opener to the pair
EIGHT_CSV = DATA / "disjoint" / "disjoint_full_k8.csv"
BW_TILE_H = 0.8        # zzb/zzc: a typed row's height
BW_ROW_GAP = 0.12      # zzb/zzc: between rows (the board's spacing, roughly)
BW_OR_GAP = 0.35       # zzc: "or" between EXEEM and EXEME
BW_TRI_H = 0.55        # zzd: a row in a triple
BW_TRI_GAP = 0.08      # zzd: between a triple's rows
BW_GRID_GAP = 0.6      # zzd: between triples
FOOTNOTE_FS = 24       # a one-line footnote under a still (navy_table's NOTE_SIZE)
FOOTNOTE_GAP = 0.3     # the clearance above it
BOARD_SIDE_X = 4.0     # scene 15's: how far left the board moves for a column of words beside it


def _on_row(mob, text, x, y, size):
    """Sit a label on its row by its text BASELINE, the row's visual middle (half the
    cap height above the baseline) at y, so "2,106" and "465" share one line."""
    cap = crisp_text("H", font_size=size).height
    return place_on_baseline(mob, (x, y - cap / 2), string=text)


def _tile_word(s, height=None, colors=None):
    """A word or a letter pattern ("F__FF") as one typed board row, `_` an untouched
    tile, at TABLE_TILE_H tall: get_typed_row's look."""
    from assets.board import TILE_FILLED_BORDER, STROKE, WordleBoard
    row = WordleBoard(rows=1, cols=len(s))
    for i, ch in enumerate(s.lower()):
        if ch != "_":
            tile = row.tiles[0][i]
            tile.set_stroke(TILE_FILLED_BORDER, STROKE)
            if ch.isalnum():
                letter = row._letter(ch, tile, color=(colors or {}).get(i, TILE_TEXT))
            else:
                # a symbol (- = * /) at the scale a capital letter gets, centred: the
                # board's fit-to-height would blow a short glyph like "-" up to fill it
                from assets.board import LETTER_FRAC
                ref = crisp_text("H", weight=BOLD)
                letter = crisp_text(ch, color=TILE_TEXT, weight=BOLD)
                letter.scale(tile.height * LETTER_FRAC / ref.height).move_to(tile.get_center())
            row.letters[0][i] = letter
            row.add(letter)
    from assets.strategy_tree import stroke
    row.scale((height or TABLE_TILE_H) / row.height)
    for t in row.tiles[0]:                          # 12's rule: borders thin with the tiles
        t.set_stroke(width=stroke(row))
    return row


def _vowelless():
    """Every legal guess with no A, E, I, O, U or Y, by tools/disjoint_words.py's own
    `vowels_in` -- the five its docstring names."""
    sys.path.insert(0, str(MATH / "tools"))
    from disjoint_words import vowels_in
    guesses = [w.strip() for w in open(DATA / "words" / "guess.txt") if w.strip()]
    words = sorted(w for w in guesses if not vowels_in(w))
    assert words == ["crwth", "cwtch", "grrls", "grrrl", "phpht"], words
    return words


def _tree_lines(path):
    import gzip
    with gzip.open(path, "rt") as f:
        return [l.strip() for l in f if l.strip()]


def _all_grey_line(path):
    """The tree line with the longest run of all-grey replies from the start (the
    all-grey path: grey, grey, ... then whatever the line does next)."""
    def run(l):
        n = 0
        for p in l.split()[3::2]:
            if p != "bbbbb":
                break
            n += 1
        return n
    return max(_tree_lines(path), key=run)


class Bonus(WordleBoardScene):
    def setup_scene(self):
        pass

    def _title_card(self, name):
        """A title card: yahtzee 00transitions' `_card`, in white on the navy."""
        self.add(crisp_text(name, font_size=TITLE_BASE_FS, color=WHITE,
                            weight="BOLD").scale(TITLE_SCALE).move_to(ORIGIN))

    def _browser(self, image, url, title):
        """A page in a browser window, as scene 25 builds it: its width and aspect,
        a screenshot from animations/assets/web_media/."""
        from bpkfigures.browser import browser_window
        self.add(browser_window(url, title, image=str(WEB_MEDIA / f"{image}.png"),
                                width=WIN_W, aspect=9 / 16))

    def _lingo_table(self, length):
        """One title over two navy tables (A-M, N-Z): each letter's best opener(s) by
        total guesses (ties all listed, as tools/lingo_report.py does) and the
        average; a letter whose every opener is INFEASIBLE says so."""
        rows = []
        for letter in "abcdefghijklmnopqrstuvwxyz":
            f = DATA / "lingo" / f"len{length}_d5_ans" / f"{letter}_totals.csv"
            if not f.exists():
                continue                      # no answer word starts with it
            got = [r for r in csv.DictReader(l for l in open(f) if not l.startswith("#"))]
            ok = [r for r in got if r["total"]]
            if not ok:
                rows.append([letter.upper(), "none within 5", ""])
                continue
            best = min(int(r["total"]) for r in ok)
            tied = [r for r in ok if int(r["total"]) == best]
            rows.append([letter.upper(), ", ".join(r["word"].upper() for r in tied),
                         f"{float(tied[0]['expected']):.2f}"])
        title = crisp_text(f"Lingo: {length}-Letter Answers", font_size=FONT_SIZE_LG, color=WHITE)
        title.to_edge(UP, buff=0.6)
        half = (len(rows) + 1) // 2
        top = title.get_bottom()[1] - 0.6
        heads = ["Letter", "Best Opener", "Average"]
        r = config.frame_x_radius
        a = navy_table(heads, rows[:half], region=(-r, 0), top=top)
        b = navy_table(heads, rows[half:], region=(0, r), top=top)
        # both halves at the smaller of their two fits (same text size), tops aligned
        sa, sb = a.header.height, b.header.height
        if sa > sb:
            a[0].scale(sb / sa, about_edge=UP)
        elif sb > sa:
            b[0].scale(sa / sb, about_edge=UP)
        b[0].align_to(a[0], UP)
        pair = VGroup(a[0], b[0])                # re-centred in the space under the title
        bottom = -config.frame_y_radius + 0.4
        pair.shift(UP * ((top + bottom) / 2 - pair.get_center()[1]))
        self.add(title, a, b)

    def _youtube(self, key, note=None):
        """A video on YouTube's dark watch page, as scene 09a builds it: title, channel,
        views and age from assets/youtube_data's committed cache (the analytics DB);
        thumbnail and avatar from assets/youtube_media."""
        from bpkfigures.youtube_card import youtube_watch
        from assets.youtube_data import get as yt_get
        page = youtube_watch(**yt_get(key), dark=True)
        self.add(page)
        if note:
            # the page shrinks (about its top) to leave the note its own strip below
            t = crisp_text(note, font_size=FOOTNOTE_FS, color=WHITE).to_edge(DOWN, buff=0.3)
            room = t.get_top()[1] + FOOTNOTE_GAP
            # the page's full-frame background stays; only what sits on it shrinks
            bg = [m for m in page if isinstance(m, Rectangle)
                  and abs(m.width - config.frame_width) < 1e-6]
            content = Group(*[m for m in page if m not in bg])
            if content.get_bottom()[1] < room:
                top = config.frame_y_radius
                content.scale((top - room) / (top - content.get_bottom()[1]),
                              about_point=[0, top, 0])
            self.add(t)

    def _not_built(self, what):
        raise NotImplementedError(f"bonus still not built yet: {what}")

    # a : title card
    @still
    def part1(self):
        self._title_card('Part 1: Wordle')

    # b : title card
    @still
    def antiwordle(self):
        self._title_card('Antiwordle')

    # c : the 16-word antiwordle chain as one giant board — scene 03a's end state
    @still
    def antiwordle_chain(self):
        from assets import game_data
        from assets.board import GAP, get_scored_row

        game = game_data.load("antiwordle")       # scene 03's chain, same cache
        rows = VGroup(*[get_scored_row(g["word"], g["code"]) for g in game["guesses"]])
        rows.arrange(DOWN, buff=GAP)
        # 03's finished column: the full frame height less CHAIN_MARGIN top and bottom
        rows.scale_to_fit_height(config.frame_height - 2 * CHAIN_MARGIN).move_to(ORIGIN)
        self.add(rows)

    # d : title card
    @still
    def color_groups(self):
        self._title_card('Color Groups')

    # e : title card
    @still
    def optimal_strategy(self):
        self._title_card('The Optimal Strategy')

    # f : title card
    @still
    def word_list_changes(self):
        self._title_card('Word List Changes')

    # g : title card
    @still
    def alphabet_tier_list(self):
        self._title_card('Alphabet Tier List')

    # h : title card
    @still
    def vowels(self):
        self._title_card('Vowels')

    # i : title card
    @still
    def speedrunning(self):
        self._title_card('Speedrunning')

    # j : title card
    @still
    def multi_word_openers(self):
        self._title_card('Multi-Word Openers')

    # k : LEDGE PAWNS ROCKY THUMB scored in the colouring FALSE, SALLE and SALVE all
    #     give, on the left; the three words typed on the right — scene 15r's layout
    @still
    def ledge_pawns(self):
        sys.path.insert(0, str(MATH))
        from wordle import pattern
        from assets.board import GAP, WordleBoard, get_scored_row, get_typed_row

        opener = ["ledge", "pawns", "rocky", "thumb"]   # scene 15's finished climb
        bucket = ["false", "salle", "salve"]            # its one unsolved bucket (15's NB)
        codes = [pattern(g, bucket[0]) for g in opener]
        for w in bucket[1:]:                            # the point of the still: one colouring
            assert [pattern(g, w) for g in opener] == codes, w
        # 15's board: six one-row boards at the board's spacing, the unused rows
        # empty, moved BOARD_SIDE_X to the left (15q)
        rows = [get_scored_row(g, c) for g, c in zip(opener, codes)]
        rows += [WordleBoard(rows=1, cols=5) for _ in range(6 - len(rows))]
        board = VGroup(*rows).arrange(DOWN, buff=GAP).move_to(ORIGIN)
        board.shift(LEFT * BOARD_SIDE_X)
        # 15r: the words typed at the board's size and spacing, centred between the
        # board and the frame's right edge
        words = VGroup(*[get_typed_row(w) for w in bucket]).arrange(DOWN, buff=GAP)
        words.move_to(RIGHT * (board.get_right()[0] + config.frame_x_radius) / 2)
        self.add(board, words)

    # l : Pokecheese's "Broken" Wordle strategy video on YouTube's dark watch page
    #      (scene 09a's), the user's footnote at the bottom
    @still
    def pokecheese(self):
        self._youtube("pokecheese", note="*I couldn't actually find his citation")

    # m : title card
    @still
    def multiwordle(self):
        self._title_card('Multiwordle')

    # n : table — the best 1/2/3-word opener and its average misses at each k, every race
    @still
    def multi_openers(self):
        from assets import multi_plot_data as mp
        self._opener_table(mp.FIELDS, "Best Multiwordle Openers")

    def _opener_table(self, fields, title):
        """Scene 16's chart rule (multi_plot_data.best_opener) at every k where the
        1-, 2- and 3-word lines were all raced: each cell the winning opener and its
        average misses, an unfinished race's leader marked *."""
        from assets import multi_plot_data as mp
        rows, marked = [], False
        for k in mp.POWERS:
            best = [mp.best_opener(k, fields[n]) for n in (1, 2, 3)]
            if not all(best):
                continue
            row = [str(k)]
            for b in best:
                marked |= b["unfinished"]
                row += [b["opening"].upper() + ("*" if b["unfinished"] else ""),
                        f"{b['misses']:.2f}"]
            rows.append(row)
        self.add(navy_table(["Wordles", "1 Word", "Misses", "2 Words", "Misses",
                             "3 Words", "Misses"], rows, title=title,
                            note="*race still running: the leader so far" if marked else None))

    # o : table — the same, every opener drawn from the 2315 answers
    @still
    def multi_openers_answers(self):
        from assets import multi_plot_data as mp
        self._opener_table(mp.ANSWER_FIELDS, "Best Multiwordle Openers (Answers Only)")

    # p : title card
    @still
    def more_color_groups(self):
        self._title_card('More Color Groups')

    # q : the best casework strategy on disk, TRINE (3.606637), as a grid of its 17
    #     reply cases in scene 18's tree pieces, with its average guesses
    @still
    def casework_tree(self):
        from assets.branch import branch_line, mid_tile
        from assets import strategy_tree as st

        rows = [r for r in csv.DictReader(l for l in open(TRINE_CSV) if not l.startswith("#"))
                if r["opener"] == "trine"]
        second = {r["fires"]: r["second"] for r in rows if r["cut"] != "third"}
        third = {}
        for r in rows:
            if r["cut"] == "third":
                case, m = r["fires"].split("|m")
                third[case] = (int(m), r["second"])
        mean = float(rows[0]["expected"])
        # the cases in reading order: declined (<= 2 greys: 18's "ccc.." row), then 5
        # greys, then 4 and 3 greys by which tiles came back coloured
        order = ["decline", "e5"] + sorted((c for c in second if c.startswith("e4")),
                                           key=lambda c: c) \
            + sorted((c for c in second if c.startswith("e3")), key=lambda c: c)
        assert len(order) == 17 and set(order[1:]) == set(second), order

        def kinds(case):
            if case == "decline":
                return "ccc.."
            nz = case.split("_nz")[1] if "_nz" in case else ""
            return "".join("c" if str(i) in nz else "g" for i in range(5))

        w = TREE_ROW_W
        cells = []
        for case in order:
            pat = st.pattern_row(kinds(case), w)
            parts = [pat]
            if case == "decline":
                card = st.rca_card(pat.get_bottom() + DOWN * TREE_LINK, font_size=TREE_CARD_FS)
                parts += [branch_line(mid_tile(pat), card.get_center()), card]
            else:
                wd = st.word_row(second[case], w).next_to(pat, DOWN, buff=TREE_LINK)
                parts += [branch_line(mid_tile(pat), mid_tile(wd)), wd]
                if case in third:
                    m, word3 = third[case]
                    t3 = st.word_row(word3, w).next_to(wd, DOWN, buff=TREE_LINK3)
                    lab = crisp_text(f"{m} matched", font_size=TREE_LABEL_FS, color=WHITE)
                    mid = (wd.get_bottom() + t3.get_top()) / 2
                    lab.next_to([mid_tile(wd)[0], mid[1], 0], RIGHT, buff=TREE_LABEL_BUFF)
                    parts += [branch_line(mid_tile(wd), mid_tile(t3)), t3, lab]
            cells.append(VGroup(*parts))
        grid = VGroup()
        for start in range(0, len(cells), TREE_COLS):
            line = VGroup(*cells[start:start + TREE_COLS])
            line.arrange(RIGHT, buff=TREE_COL_GAP, aligned_edge=UP)
            grid.add(line)
        grid.arrange(DOWN, buff=TREE_ROW_GAP)
        opener = st.word_row("trine", TREE_OPENER_W).to_edge(UP, buff=TREE_TOP)
        avg = crisp_text(f"Average Guesses: {mean:.2f}", font_size=FONT_SIZE_MD, color=WHITE)
        avg.to_edge(DOWN, buff=TREE_TOP)
        top, bottom = opener.get_bottom()[1] - TREE_GAP, avg.get_top()[1] + TREE_GAP
        grid.scale(min(1.0, (top - bottom) / grid.height,
                       (config.frame_width - 0.6) / grid.width))
        grid.move_to([0, (top + bottom) / 2, 0])
        self.add(opener, grid, avg)

    # r : title card
    @still
    def hard_mode(self):
        self._title_card('Hard Mode')

    # s : title card
    @still
    def part2(self):
        self._title_card('Part 2: Variants')

    # t : title card
    @still
    def sea_of_greens(self):
        self._title_card('Sea of Greens')

    # u : the Sea of Greens badge page in a browser window, as scene 25a shows it
    @still
    def sea_of_greens_page(self):
        self._browser(*PAGE_BADGE)

    # v : the main Sea of Greens strategy's all-grey path (may-lose, 6 guesses, full
    #     width: BOOBY, tied with BOOZY on 1176 badges, the one whose tree was kept)
    @still
    def greens_all_grey(self):
        from assets.board import GAP
        line = _all_grey_line(GREENS_D6_TREE)
        board = VGroup(*self._path_rows(line)).arrange(DOWN, buff=GAP).move_to(ORIGIN)
        self.add(board)

    def _path_rows(self, line):
        """A greens tree line -> its scored rows, the last (the answer) all green."""
        from assets.board import get_scored_row
        t = line.split()
        words, pats = t[2::2], t[3::2]
        code = lambda p: sum({"b": 0, "y": 1, "g": 2}[c] * 3 ** (4 - i) for i, c in enumerate(p))
        assert words[-1] == t[0] and len(words) == int(t[1]) == len(pats) + 1, line
        return [get_scored_row(w, code(p)) for w, p in zip(words, pats)] + \
               [get_scored_row(words[-1], 242)]

    # w : the uncapped Sea of Greens strategy (BOOBY): its all-grey path (19 guesses)
    #     beside its longest path (22; four answers tie, PARRY the first in the tree)
    @still
    def greens_uncapped(self):
        from assets.board import GAP
        lines = [l for l in _tree_lines(GREENS_UNCAPPED_TREE)]
        longest = max(lines, key=lambda l: int(l.split()[1]))   # first of the ties
        cols = [VGroup(*self._path_rows(l)).arrange(DOWN, buff=GAP)
                for l in (_all_grey_line(GREENS_UNCAPPED_TREE), longest)]
        h = config.frame_height - 2 * CHAIN_MARGIN          # 03's finished column
        s = h / max(c.height for c in cols)
        for c in cols:
            c.scale(s)
        VGroup(*cols).arrange(RIGHT, buff=PATH_COL_GAP, aligned_edge=UP).move_to(ORIGIN)
        self.add(*cols)

    # x : title card
    @still
    def wordle_in_one(self):
        self._title_card('Wordle in One')

    # y : Wordle in One in a browser window, as scene 25b shows it
    @still
    def wordle_in_one_page(self):
        self._browser(*PAGE_IN_ONE)

    # z : Wordle in One games by colour combination (answers-only guesses), scene 17's
    #     table of combinations without its bars, a total at the bottom
    @still
    def in_one_table(self):
        from assets import color_combos_data
        from assets.colorings import GRID_BUFF, tile

        def combo(g, y, b):                       # 17's `_combo`: no gap between colours
            t = VGroup(*[tile(k, CC_ROW_TILE) for k in [2] * g + [1] * y + [0] * b])
            return t.arrange(RIGHT, buff=CC_ROW_TILE * GRID_BUFF)

        with open(IN_ONE_CSV) as f:
            games = {(int(r["greens"]), int(r["yellows"]), int(r["grays"])): int(r["games_nowin"])
                     for r in csv.DictReader(l for l in f if not l.startswith("#"))}
        order = [tuple(int(ch) for ch in k) for k in color_combos_data.load()["rows"]]
        # every combination with a game is a row (17's 19 leave out 4G1Y, impossible,
        # and the all-green win, which is no puzzle)
        assert {c for c, n in games.items() if n} <= set(order), games
        title = crisp_text("Wordle in One Games", color=WHITE, font_size=FONT_SIZE_LG)
        title.move_to([0, CC_TITLE_Y, 0])
        combo_w = combo(5, 0, 0).width
        col_w = crisp_text(f"{sum(games.values()):,}", font_size=FONT_SIZE_SM, weight=BOLD).width
        left = -(combo_w + CC_VAL_GAP + col_w) / 2                  # 17's `_table_xs`
        cx = left + combo_w + CC_VAL_GAP + col_w / 2
        block = VGroup()
        y = 0.0
        for i, c in enumerate(order):
            if i and c[2] != order[i - 1][2]:
                y -= CC_GROUP_GAP                                   # 17's group gap
            row = combo(*c)
            row.shift([left - row.get_left()[0], y - row.get_y(), 0])
            val = crisp_text(f"{games[c]:,}", color=WHITE, font_size=FONT_SIZE_SM)
            block.add(row, _on_row(val, f"{games[c]:,}", cx, y, FONT_SIZE_SM))
            y -= CC_ROW_PITCH
        y -= CC_GROUP_GAP
        label = crisp_text("Total", color=WHITE, font_size=FONT_SIZE_SM, weight=BOLD)
        _on_row(label, "Total", left + combo_w / 2, y, FONT_SIZE_SM)
        total = crisp_text(f"{sum(games.values()):,}", color=WHITE, font_size=FONT_SIZE_SM,
                           weight=BOLD)
        _on_row(total, f"{sum(games.values()):,}", cx, y, FONT_SIZE_SM)
        block.add(label, total)
        top, bottom = CC_TOP_ROW_Y + CC_ROW_TILE / 2, -config.frame_y_radius + CC_BOTTOM
        block.scale(min(1.0, (top - bottom) / block.height), about_point=[0, block.get_top()[1], 0])
        block.shift(UP * (top - block.get_top()[1]))
        self.add(title, block)

    # za : title card
    @still
    def hard_to_guess(self):
        self._title_card('Hard-to-Guess Words')

    # zb : the adversarial search's result as hangman's two tables (Common Letter
    #      Patterns, Common Words), in the Wordle look: navy tables, tile rows
    @still
    def adversarial(self):
        import math
        from assets import adversarial_data
        d = adversarial_data.load()

        def sig2(x):                                     # hangman's `_sig2`
            dp = 1 - math.floor(math.log10(abs(x)))
            return f"{x:.{max(dp, 0)}f}"

        pats = navy_table(["Pattern", "Multiplier"],
                          [[_tile_word(p["pattern"]), f"{p['multiplier']:.1f}"]   # hangman's `_mult`
                           for p in d["patterns"]],
                          title="Common Letter Patterns", region=(-config.frame_x_radius, 0))
        words = navy_table(["Word", "Frequency"],
                           [[_tile_word(w["word"]), sig2(w["pct"]) + "%"] for w in d["words"]],
                           title="Common Words", region=(0, config.frame_x_radius))
        h = min(pats.title.height, words.title.height)   # side by side: one title size
        for t in (pats.title, words.title):
            t.scale(h / t.height, about_edge=UP)
        self.add(pats, words)

    # zc : title card
    @still
    def changing_word_lists(self):
        self._title_card('Changing Word Lists')

    # zd : the 3 x 3 grid -- guess list (rows) x answer list (columns), each of the
    #      2315 answers, the 12972 legal words, all 26^5 letter strings -- with each
    #      cell's best opener, its average guesses, and whether it is exact or a beam
    @still
    def list_grid(self):
        from bpkfigures.table import row_stripes
        names = ["Answers", "Guesses", "All Letter Combos"]
        cells = {}
        for (g, a), spec in GRID_CELLS.items():
            if spec is None:
                cells[g, a] = VGroup(crisp_text("Impossible", font_size=GRID_VAL_FS, color=WHITE))
                continue
            path, how = spec
            rows = [r for r in csv.DictReader(l for l in open(DATA / path) if not l.startswith("#"))
                    if r["expected"] and r.get("unsolved", "0") in ("", "0")]
            best = min(rows, key=lambda r: float(r["expected"]))
            cells[g, a] = VGroup(_tile_word(best["word"]),
                                 crisp_text(f"{float(best['expected']):.2f}", font_size=GRID_VAL_FS,
                                            color=WHITE),
                                 crisp_text(how, font_size=GRID_NOTE_FS, color=WHITE)
                                 ).arrange(DOWN, buff=GRID_INNER)
        xs = [(c - 1) * GRID_COL_W + GRID_X for c in range(3)]
        ys = [(1 - r) * GRID_ROW_H + GRID_Y for r in range(3)]
        for (g, a), m in cells.items():
            m.move_to([xs[a], ys[g], 0])
        heads = VGroup(*[crisp_text(n, font_size=HEADER_SIZE, color=WHITE, weight=BOLD)
                         .move_to([xs[c], ys[0] + GRID_ROW_H / 2 + GRID_HEAD_GAP, 0])
                         for c, n in enumerate(names)])
        labels = VGroup(*[crisp_text(n, font_size=HEADER_SIZE, color=WHITE, weight=BOLD)
                          for n in names])
        for r, lab in enumerate(labels):
            lab.move_to([0, ys[r], 0]).align_to([xs[0] - GRID_COL_W / 2 - GRID_LABEL_GAP, 0, 0], RIGHT)
        left = labels.get_left()[0] - STRIPE_OVERHANG
        right = xs[2] + GRID_COL_W / 2
        stripes = row_stripes(ys, left, right, GRID_ROW_H)
        across = crisp_text("Answer List", font_size=FONT_SIZE_MD, color=WHITE)
        across.next_to(heads, UP, buff=GRID_AXIS_GAP)
        down = crisp_text("Guess List", font_size=FONT_SIZE_MD, color=WHITE).rotate(PI / 2)
        down.next_to(labels, LEFT, buff=GRID_AXIS_GAP)
        grid = VGroup(stripes, heads, labels, across, down, *cells.values())
        fit_to_frame(grid.move_to(ORIGIN), buff=0.35)
        self.add(grid)

    # ze : title card
    @still
    def lingo(self):
        self._title_card('Lingo')

    # zf : the Lingo (American game show) Wikipedia page in a browser window (assets/web_shots.py recipe)
    @still
    def lingo_page(self):
        self._browser(*PAGE_LINGO)

    # zg : Lingo, 5-letter answers only, 5 guesses: each starting letter's best
    #      opener(s) (exact ties all shown) and average guesses
    @still
    def lingo_table(self):
        self._lingo_table(5)

    # zh : Lingo, 6-letter answers only, 5 guesses: each starting letter's best
    #      opener(s) (exact ties all shown) and average guesses
    @still
    def lingo6_table(self):
        self._lingo_table(6)

    # zi : title card
    @still
    def other_languages(self):
        self._title_card('Other Languages')

    # zj : each language's best opener and average guesses, answers only (the
    #      widest finished beam, k = 30, so an upper bound -- the note says so)
    @still
    def languages_table(self):
        rows = [r for r in csv.DictReader(open(LANG_CSV))]
        self.add(navy_table(
            ["Language", "Best Opener", "Average"],
            [[LANG_NAMES[r["lang"]], r["opener"].upper(), f"{float(r['expected_guesses']):.2f}"]
             for r in sorted(rows, key=lambda r: LANG_NAMES[r["lang"]])],
            title="Best Openers by Language",
            note="Answers only; best of the top 30 openers (k = 30), accents removed"))

    # zk : title card
    @still
    def mastermind_rules(self):
        self._title_card('Mastermind Rules')

    # zl : title card
    @still
    def absurdle(self):
        self._title_card('Absurdle')

    # zm : Absurdle in a browser window (assets/web_shots.py recipe)
    @still
    def absurdle_page(self):
        self._browser(*PAGE_ABSURDLE)

    # zn : the committed 4-guess Absurdle win (AESIR YAULD TENCH WHOOP) as a board,
    #      the candidates left after each guess beside its row
    @still
    def absurdle_sequence(self):
        sys.path.insert(0, str(MATH))
        from wordle import pattern
        from assets.board import GAP, get_scored_row
        steps = []
        for line in open(ABSURDLE_TXT):
            t = line.split()
            if len(t) >= 2 and re.fullmatch(r"[a-z]{5}", t[0]) and re.fullmatch(r"[.yG]{5}", t[1]):
                steps.append((t[0], t[1], t[2] if t[2] != "WIN" else None))
        answer = steps[-1][0]
        rows = []
        for word, pat, left in steps:
            code = sum({".": 0, "y": 1, "G": 2}[c] * 3 ** (4 - i) for i, c in enumerate(pat))
            assert code == pattern(word, answer), (word, pat)   # the file's replies, re-derived
            rows.append(get_scored_row(word, code))
        board = VGroup(*rows).arrange(DOWN, buff=GAP)
        counts = VGroup()
        for row, (_, _, left) in zip(rows, steps):
            if left is not None:
                n = crisp_text(f"{int(left):,}", font_size=ABS_COUNT_FS, color=WHITE)
                counts.add(_on_row(n, f"{int(left):,}", 0, row.get_y(), ABS_COUNT_FS))
        head = crisp_text("Options Left", font_size=HEADER_SIZE, color=WHITE, weight=BOLD)
        cx = board.get_right()[0] + ABS_COUNT_GAP + max(head.width, counts.width) / 2
        for n in counts:                                 # each stays on its row; x only
            n.set_x(cx)
        head.move_to([cx, board.get_top()[1] + ABS_HEAD_GAP, 0])
        VGroup(board, counts, head).move_to(ORIGIN)
        self.add(board, counts, head)

    # zo : title card
    @still
    def letroso(self):
        self._title_card('Letroso')

    # zp : Letroso's home page in a browser window (assets/web_shots.py recipe)
    @still
    def letroso_page(self):
        self._browser(*PAGE_LETROSO)

    # zq : Letroso's top 10 first guesses by the average number of answers still
    #      possible after them (the cached root ranking; each answer length weighted
    #      equally -- the note says so)
    @still
    def letroso_table(self):
        import gzip
        with gzip.open(LETROSO_RANK, "rt") as f:
            head = [l for l in f if l.startswith("#")]
        with gzip.open(LETROSO_RANK, "rt") as f:
            rows = list(csv.DictReader(l for l in f if not l.startswith("#")))[:LETROSO_TOP]
        assert any("prior=lengths" in l for l in head), head
        self.add(navy_table(
            ["Rank", "First Guess", "Options Left"],
            [[r["rank"], r["guess"].upper(), f"{float(r['score']):.1f}"] for r in rows],
            title="Best Letroso Starters",
            note="Average answers still possible after the first guess (every word length equally likely)"))

    # zr : title card
    @still
    def foximax(self):
        self._title_card('Foximax')

    # zs : Foximax in a browser window (assets/web_shots.py recipe)
    @still
    def foximax_page(self):
        self._browser(*PAGE_FOXIMAX)

    # zt : Foximax, the largest simulation (1,000,000 games): how many games end
    #      with each number of words, horizontal bars in 08's light blue
    @still
    def foximax_histogram(self):
        from bpkfigures.histogram import get_histogram
        counts = {}
        for line in open(FOXIMAX_CSV):
            m = re.match(r"#\s+(\d+) words\s+(\d+)\s+[\d.]+%", line)
            if m:
                counts[int(m.group(1))] = int(m.group(2))
        total = sum(counts.values())
        assert total == FOXIMAX_GAMES, total
        labels = {}
        for k, c in counts.items():
            pct = 100 * c / total
            labels[k] = f"{pct:.1f}%" if pct >= 1 else f"{pct:.2g}%"
        plot = get_histogram(None, counts=counts, is_vertical=True, width=FOX_LEN, height=FOX_H,
                             bar_color=BG_COLOR, ink_color=WHITE, bar_labels=labels,
                             bar_label_color=WHITE, x_tick_step=1,
                             title="FoxiMax: Words per Game")
        # horizontal mode centres the title on the axis (here the left edge): put
        # the chart in the middle and the title over the whole frame
        title = plot.title_text
        body = VGroup(*[m for m in plot if m is not title])
        body.move_to(ORIGIN).shift(DOWN * FOX_TITLE_DROP)
        title.move_to([0, body.get_top()[1] + FOX_TITLE_GAP, 0], aligned_edge=DOWN)
        fit_to_frame(plot, buff=0.4)
        self.add(plot)

    # zu : title card
    @still
    def nerdle(self):
        self._title_card('Nerdle')

    # zv : Nerdle's classic game in a browser window (assets/web_shots.py recipe)
    @still
    def nerdle_page(self):
        self._browser(*PAGE_NERDLE)

    # zw : each Nerdle symbol and the share of answer equations containing it
    #      (tools/nerdle_symbols.py's count, over the 17,723 answers)
    @still
    def nerdle_symbols(self):
        sys.path.insert(0, str(MATH))
        sys.path.insert(0, str(MATH / "tools"))
        from nerdle_symbols import counts, load_set
        words = load_set("answers", 8)
        _, has, _ = counts(words, 8)
        n = len(words)
        order = sorted(has, key=lambda c: (-has[c], c))
        self.add(navy_table(
            ["Symbol", "Equations Containing It"],
            [[c, f"{100 * has[c] / n:.1f}%"] for c in order],
            title="Nerdle Symbols",
            note=f"Share of the {n:,} possible answers"))

    # zx : Nerdle's single best opener (48-32=16, the k=1 solve) and, below it,
    #      the best pair found (47-11=36, 2*029=58), as typed tile rows
    @still
    def nerdle_openers(self):
        one = next(csv.DictReader(l for l in open(NERDLE_SOLVE) if not l.startswith("#")))["opener"]
        last = list(csv.DictReader(open(NERDLE_PAIRS)))[-1]          # the final incumbent
        assert (one, last["first"], last["second"]) == ("48-32=16", "47-11=36", "2*029=58")
        top = _tile_word(one, NERDLE_TILE_H)
        pair = VGroup(_tile_word(last["first"], NERDLE_TILE_H),
                      _tile_word(last["second"], NERDLE_TILE_H)).arrange(DOWN, buff=NERDLE_ROW_GAP)
        VGroup(top, pair).arrange(DOWN, buff=NERDLE_BLOCK_GAP).move_to(ORIGIN)
        self.add(top, pair)

    # zy : title card
    @still
    def bad_wordle(self):
        self._title_card('Bad Wordle')

    # zz : Ellie Rasmussen's "You should play Wordle wrong" on YouTube's dark watch
    #      page, as scene 09a shows the Hangman video (stats: assets/youtube_data)
    @still
    def rasmussen(self):
        self._youtube("rasmussen")

    # zza : every legal guess with no A, E, I, O, U or Y (tools/disjoint_words.py's rule),
    #       a column of typed rows
    @still
    def vowelless(self):
        words = _vowelless()
        col = VGroup(*[_tile_word(w, BW_TILE_H) for w in words]).arrange(DOWN, buff=BW_ROW_GAP)
        self.add(col.move_to(ORIGIN))

    # zzb : the 8-word bad-Wordle solution (8 legal guesses, no letter in common, an
    #       answer among them): disjoint_full_k8.csv's one set; slot 6 is EXEEM or EXEME
    @still
    def eight_words(self):
        slots = [r for r in csv.DictReader(l for l in open(EIGHT_CSV) if not l.startswith("#"))]
        assert len({r["set"] for r in slots}) == 1 and len(slots) == 8, slots
        rows = VGroup()
        for r in slots:
            alts = r["words"].split("|")
            row = _tile_word(alts[0], BW_TILE_H)
            if len(alts) > 1:                     # the same letters, either word
                extra = VGroup()
                for w in alts[1:]:
                    extra.add(crisp_text("or", font_size=FONT_SIZE_MD, color=WHITE),
                              _tile_word(w, BW_TILE_H))
                row = VGroup(row, *extra).arrange(RIGHT, buff=BW_OR_GAP)
            rows.add(row)
        rows.arrange(DOWN, buff=BW_ROW_GAP, aligned_edge=LEFT)   # first words in one column
        rows.move_to(ORIGIN)
        rows.shift(LEFT * rows[0].get_center()[0])   # the column centred; "or EXEME" hangs right
        self.add(rows)

    # zzc : all 10 triples of the 5 vowel-less words, 04's grid; a letter in more
    #       than one word of its triple is red
    @still
    def vowelless_triples(self):
        from itertools import combinations
        from assets.groups import grid_cells
        words = _vowelless()
        groups = []
        for tri in combinations(words, 3):
            col = VGroup()
            for w in tri:
                others = set("".join(x for x in tri if x != w))
                col.add(_tile_word(w, BW_TRI_H, {i: LIGHT_RED for i, c in enumerate(w) if c in others}))
            groups.append(col.arrange(DOWN, buff=BW_TRI_GAP))
        assert len(groups) == 10
        w, h = groups[0].width, groups[0].height
        for g, (cx, cy) in zip(groups, grid_cells(len(groups))):
            g.move_to([cx * (w + BW_GRID_GAP), cy * (h + BW_GRID_GAP), 0])
        grid = VGroup(*groups)
        fit_to_frame(grid.move_to(ORIGIN), buff=0.4)
        self.add(grid)

    # zzd : title card
    @still
    def answers_from_combos(self):
        self._title_card('Answers from Color Combos')

    # zze : title card
    @still
    def conclusion(self):
        self._title_card('Conclusion')

    # zzf : channel post (not in the video) — five guesses scored against TODAY, then TODAY typed, unscored
    @still
    def today_board(self):
        sys.path.insert(0, str(MATH))
        from wordle import pattern
        from assets.board import GAP, get_scored_row, get_typed_row

        self.camera.background_color = BOARD_NAVY
        answer = "today"
        guesses = ["newer", "wordy", "video", "hours", "after"]
        rows = [get_scored_row(g, pattern(g, answer)) for g in guesses]
        rows.append(get_typed_row(answer))
        board = VGroup(*rows).arrange(DOWN, buff=GAP).scale(1.2).move_to(ORIGIN)
        self.add(board)
