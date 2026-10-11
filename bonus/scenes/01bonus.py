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
  l   pokecheese — browser: Pokecheese video, with '*I couldn't actually find his citation' at the bottom  [NOT BUILT]
  m   multiwordle — title card "Multiwordle"
  n   multi_openers — table: best 1/2/3-word opener + average misses per k, best of every race (scene 16's chart rule)
  o   multi_openers_answers — the same, answers-only races
  p   more_color_groups — title card "More Color Groups"
  q   casework_tree — TRINE (3.606637, the best casework result): its 17 reply cases in scene 18's tree pieces  [DRAFT, not staged]
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
  zf  lingo_page — browser: the Lingo Wikipedia page  [NOT BUILT]
  zg  lingo_table — table: best opener and average per starting letter, Lingo  [NOT BUILT]
  zh  lingo6_table — table: the same for 6-letter Lingo  [NOT BUILT]
  zi  other_languages — title card "Other Languages"
  zj  languages_table — table: best opener and average per language  [NOT BUILT]
  zk  mastermind_rules — title card "Mastermind Rules"
  zl  absurdle — title card "Absurdle"
  zm  absurdle_page — browser: Absurdle  [NOT BUILT]
  zn  absurdle_sequence — a winning 4-word Absurdle sequence with the options left at each step  [NOT BUILT]
  zo  letroso — title card "Letroso"
  zp  letroso_page — browser: Letroso  [NOT BUILT]
  zq  letroso_table — table: top Letroso starters by average remaining options  [NOT BUILT]
  zr  foximax — title card "Foximax"
  zs  foximax_page — browser: Foximax  [NOT BUILT]
  zt  foximax_histogram — horizontal-bar histogram of word counts from the Foximax analysis  [NOT BUILT]
  zu  nerdle — title card "Nerdle"
  zv  nerdle_page — browser: Nerdle  [NOT BUILT]
  zw  nerdle_symbols — table: symbols with % of equations containing them  [NOT BUILT]
  zx  nerdle_openers — 48-32=16, and below it the pair 47-11=36 and 2*029=58  [NOT BUILT]
  zy  bad_wordle — title card "Bad Wordle"
  zz  rasmussen — browser: Ellie Rasmussen's 'You should play Wordle wrong' video  [NOT BUILT]
  zza vowelless — list of every word with no A, E, I, O, U or Y  [NOT BUILT]
  zzb eight_words — our 8-word solution with no letters in common  [NOT BUILT]
  zzc vowelless_triples — all 10 triples of the 5 vowel-less words, shared letters in red  [NOT BUILT]
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
BOARD_SIDE_X = 4.0     # scene 15's: how far left the board moves for a column of words beside it


def _on_row(mob, text, x, y, size):
    """Sit a label on its row by its text BASELINE, the row's visual middle (half the
    cap height above the baseline) at y, so "2,106" and "465" share one line."""
    cap = crisp_text("H", font_size=size).height
    return place_on_baseline(mob, (x, y - cap / 2), string=text)


def _tile_word(s):
    """A word or a letter pattern ("F__FF") as one typed board row, `_` an untouched
    tile, at TABLE_TILE_H tall: get_typed_row's look."""
    from assets.board import TILE_FILLED_BORDER, STROKE, WordleBoard
    row = WordleBoard(rows=1, cols=len(s))
    for i, ch in enumerate(s.lower()):
        if ch != "_":
            tile = row.tiles[0][i]
            tile.set_stroke(TILE_FILLED_BORDER, STROKE)
            letter = row._letter(ch, tile)
            row.letters[0][i] = letter
            row.add(letter)
    from assets.strategy_tree import stroke
    row.scale(TABLE_TILE_H / row.height)
    for t in row.tiles[0]:                          # 12's rule: borders thin with the tiles
        t.set_stroke(width=stroke(row))
    return row


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

    # l : NOT BUILT — browser: Pokecheese video, with '*I couldn't actually find his citation' at the bottom
    @still
    def pokecheese(self):
        self._not_built("browser: Pokecheese video, with '*I couldn't actually find his citation' at the bottom")

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

    # zf : NOT BUILT — browser: the Lingo Wikipedia page
    @still
    def lingo_page(self):
        self._not_built('browser: the Lingo Wikipedia page')

    # zg : NOT BUILT — table: best opener and average per starting letter, Lingo
    @still
    def lingo_table(self):
        self._not_built('table: best opener and average per starting letter, Lingo')

    # zh : NOT BUILT — table: the same for 6-letter Lingo
    @still
    def lingo6_table(self):
        self._not_built('table: the same for 6-letter Lingo')

    # zi : title card
    @still
    def other_languages(self):
        self._title_card('Other Languages')

    # zj : NOT BUILT — table: best opener and average per language
    @still
    def languages_table(self):
        self._not_built('table: best opener and average per language')

    # zk : title card
    @still
    def mastermind_rules(self):
        self._title_card('Mastermind Rules')

    # zl : title card
    @still
    def absurdle(self):
        self._title_card('Absurdle')

    # zm : NOT BUILT — browser: Absurdle
    @still
    def absurdle_page(self):
        self._not_built('browser: Absurdle')

    # zn : NOT BUILT — a winning 4-word Absurdle sequence with the options left at each step
    @still
    def absurdle_sequence(self):
        self._not_built('a winning 4-word Absurdle sequence with the options left at each step')

    # zo : title card
    @still
    def letroso(self):
        self._title_card('Letroso')

    # zp : NOT BUILT — browser: Letroso
    @still
    def letroso_page(self):
        self._not_built('browser: Letroso')

    # zq : NOT BUILT — table: top Letroso starters by average remaining options
    @still
    def letroso_table(self):
        self._not_built('table: top Letroso starters by average remaining options')

    # zr : title card
    @still
    def foximax(self):
        self._title_card('Foximax')

    # zs : NOT BUILT — browser: Foximax
    @still
    def foximax_page(self):
        self._not_built('browser: Foximax')

    # zt : NOT BUILT — horizontal-bar histogram of word counts from the Foximax analysis
    @still
    def foximax_histogram(self):
        self._not_built('horizontal-bar histogram of word counts from the Foximax analysis')

    # zu : title card
    @still
    def nerdle(self):
        self._title_card('Nerdle')

    # zv : NOT BUILT — browser: Nerdle
    @still
    def nerdle_page(self):
        self._not_built('browser: Nerdle')

    # zw : NOT BUILT — table: symbols with % of equations containing them
    @still
    def nerdle_symbols(self):
        self._not_built('table: symbols with % of equations containing them')

    # zx : NOT BUILT — 48-32=16, and below it the pair 47-11=36 and 2*029=58
    @still
    def nerdle_openers(self):
        self._not_built('48-32=16, and below it the pair 47-11=36 and 2*029=58')

    # zy : title card
    @still
    def bad_wordle(self):
        self._title_card('Bad Wordle')

    # zz : NOT BUILT — browser: Ellie Rasmussen's 'You should play Wordle wrong' video
    @still
    def rasmussen(self):
        self._not_built("browser: Ellie Rasmussen's 'You should play Wordle wrong' video")

    # zza : NOT BUILT — list of every word with no A, E, I, O, U or Y
    @still
    def vowelless(self):
        self._not_built('list of every word with no A, E, I, O, U or Y')

    # zzb : NOT BUILT — our 8-word solution with no letters in common
    @still
    def eight_words(self):
        self._not_built('our 8-word solution with no letters in common')

    # zzc : NOT BUILT — all 10 triples of the 5 vowel-less words, shared letters in red
    @still
    def vowelless_triples(self):
        self._not_built('all 10 triples of the 5 vowel-less words, shared letters in red')

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
