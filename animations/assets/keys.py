"""Keystroke sounds for typing on the Wordle board — one sound per letter.

Extracted from scene 97 when scene 02 became the second scene to type words: the
map is a video-wide convention (the same letter makes the same sound in EVERY
scene, the way one physical key would), so it lives in one place.

    board.type_word(scene, row, word, rt, per_letter=key_cues(scene))

ONE KEYSTROKE PER LETTER OF THE ALPHABET, the way a real keyboard behaves: the
same letter always makes the same sound, so a letter recurring across guesses
sounds like the same physical key being hit again.

The source yields 25 separable presses against 26 letters, so exactly one pair
has to share — Q and Z, the two rarest, chosen so the doubling is the least
likely to be audible.
"""

KEY_SOUNDS = [f"key{i:02d}" for i in range(1, 26)]
_Q = ord("q") - ord("a")

# Letters whose assigned key did not sit right, SWAPPED with another letter's. A
# swap rather than a reassignment, so every letter still owns exactly one sound —
# the rejected one just moves to a letter that is rarely typed.
#   s <-> j : S's original key19 was disliked; J absorbs it.
KEY_SWAPS = [("s", "j")]


def _build_key_map():
    m = {}
    for c in "abcdefghijklmnopqrstuvwxyz":
        m[c] = KEY_SOUNDS[_Q if c == "z" else ord(c) - ord("a")]
    for a, b in KEY_SWAPS:
        m[a], m[b] = m[b], m[a]
    return m


KEY_MAP = _build_key_map()


def key_for(ch):
    """The keystroke sound for a letter. Q and Z share; every other letter is its own."""
    return KEY_MAP[ch.lower()]


def key_cues(scene):
    """A `per_letter` callback for `WordleBoard.type_word` firing each letter's key.

    `at` places the cue at the letter's own moment — the word is ONE play, so the
    call order alone would stack every cue at its start.
    """
    def per_letter(i, ch, at):
        scene.sfx(key_for(ch), at=at)
    return per_letter


# THE DELETE KEY (scene 19c's backspace): one physical key, so ONE sound for every
# press. All 25 captures already belong to letters, so it borrows the one Q and Z
# share — the two rarest letters, so the doubling is the least likely to be heard.
BACKSPACE = KEY_SOUNDS[_Q]


def backspace_cues(scene):
    """A `per_press` callback for `WordleBoard.delete_word`: the delete key on
    every press, at the press's own moment."""
    def per_press(i, at):
        scene.sfx(BACKSPACE, at=at)
    return per_press
