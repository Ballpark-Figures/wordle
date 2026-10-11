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
  n   multi_openers — table: best 1/2/3-word openers per number of wordles  [NOT BUILT]
  o   multi_openers_answers — table: best 1/2/3-word openers per number of wordles, answers only  [NOT BUILT]
  p   more_color_groups — title card "More Color Groups"
  q   casework_tree — tree: the better-than-SLANT-PRICE casework strategy, SLANT PRICE tree style, with its expected guesses  [NOT BUILT]
  r   hard_mode — title card "Hard Mode"
  s   part2 — title card "Part 2: Variants"
  t   sea_of_greens — title card "Sea of Greens"
  u   sea_of_greens_page — browser: the Sea of Greens page from the main video  [NOT BUILT]
  v   greens_all_grey — the all-grey path of the main Sea of Greens strategy  [NOT BUILT]
  w   greens_uncapped — the all-grey path and the longest path of the uncapped Sea of Greens strategy  [NOT BUILT]
  x   wordle_in_one — title card "Wordle in One"
  y   wordle_in_one_page — browser: Wordle in One from the main video  [NOT BUILT]
  z   in_one_table — table: Wordle in One games by colour combo, with a total, in 17's combo style without bars  [NOT BUILT]
  za  hard_to_guess — title card "Hard-to-Guess Words"
  zb  adversarial — adversarial search results, hangman-table style in Wordle colours  [NOT BUILT]
  zc  changing_word_lists — title card "Changing Word Lists"
  zd  list_grid — 3x3 grid of best openers and averages, exact vs k marked, one cell Impossible  [NOT BUILT]
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
BOARD_SIDE_X = 4.0     # scene 15's: how far left the board moves for a column of words beside it


class Bonus(WordleBoardScene):
    def setup_scene(self):
        pass

    def _title_card(self, name):
        """A title card: yahtzee 00transitions' `_card`, in white on the navy."""
        self.add(crisp_text(name, font_size=TITLE_BASE_FS, color=WHITE,
                            weight="BOLD").scale(TITLE_SCALE).move_to(ORIGIN))

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

    # n : NOT BUILT — table: best 1/2/3-word openers per number of wordles
    @still
    def multi_openers(self):
        self._not_built('table: best 1/2/3-word openers per number of wordles')

    # o : NOT BUILT — table: best 1/2/3-word openers per number of wordles, answers only
    @still
    def multi_openers_answers(self):
        self._not_built('table: best 1/2/3-word openers per number of wordles, answers only')

    # p : title card
    @still
    def more_color_groups(self):
        self._title_card('More Color Groups')

    # q : NOT BUILT — tree: the better-than-SLANT-PRICE casework strategy, SLANT PRICE tree style, with its expected guesses
    @still
    def casework_tree(self):
        self._not_built('tree: the better-than-SLANT-PRICE casework strategy, SLANT PRICE tree style, with its expected guesses')

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

    # u : NOT BUILT — browser: the Sea of Greens page from the main video
    @still
    def sea_of_greens_page(self):
        self._not_built('browser: the Sea of Greens page from the main video')

    # v : NOT BUILT — the all-grey path of the main Sea of Greens strategy
    @still
    def greens_all_grey(self):
        self._not_built('the all-grey path of the main Sea of Greens strategy')

    # w : NOT BUILT — the all-grey path and the longest path of the uncapped Sea of Greens strategy
    @still
    def greens_uncapped(self):
        self._not_built('the all-grey path and the longest path of the uncapped Sea of Greens strategy')

    # x : title card
    @still
    def wordle_in_one(self):
        self._title_card('Wordle in One')

    # y : NOT BUILT — browser: Wordle in One from the main video
    @still
    def wordle_in_one_page(self):
        self._not_built('browser: Wordle in One from the main video')

    # z : NOT BUILT — table: Wordle in One games by colour combo, with a total, in 17's combo style without bars
    @still
    def in_one_table(self):
        self._not_built("table: Wordle in One games by colour combo, with a total, in 17's combo style without bars")

    # za : title card
    @still
    def hard_to_guess(self):
        self._title_card('Hard-to-Guess Words')

    # zb : NOT BUILT — adversarial search results, hangman-table style in Wordle colours
    @still
    def adversarial(self):
        self._not_built('adversarial search results, hangman-table style in Wordle colours')

    # zc : title card
    @still
    def changing_word_lists(self):
        self._title_card('Changing Word Lists')

    # zd : NOT BUILT — 3x3 grid of best openers and averages, exact vs k marked, one cell Impossible
    @still
    def list_grid(self):
        self._not_built('3x3 grid of best openers and averages, exact vs k marked, one cell Impossible')

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
