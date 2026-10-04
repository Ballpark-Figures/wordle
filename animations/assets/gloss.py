"""A dictionary definition under a word — "n. Obsolete variant of rote" — one
crisp_text per hand-broken line, left-aligned. EVERY definition in the video goes
through here (scenes 06 and 08), so they all look alike.

    g = gloss(["n. Obsolete", "variant of rote"], 28, italic=["rote"])
    g.next_to(word, DOWN, buff=0.15, aligned_edge=LEFT)

THE PART OF SPEECH IS ALWAYS ITALIC, and this function does it — a caller cannot
forget it. Any leading "n.", "v.", "adj." … on the first line is set italic
(user's call, 2026-09-29: 08's TARSE definition was built by hand and lost its
italic "n"). `italic` adds further whole words, as the Doc italicises them.

Extracted from scene 06 when scene 08 (TARSE's definition) became the second user.
"""
import re

from config import *

GLOSS_LINE_BUFF = 0.1
PARTS_OF_SPEECH = ("n", "v", "adj", "adv", "pron", "prep", "conj", "interj")
_POS = re.compile(rf"^({'|'.join(PARTS_OF_SPEECH)})\.")


def gloss(lines, font_size, italic=(), color=WHITE):
    """A definition, one crisp_text per line, left-aligned. The first line's leading
    part of speech is set italic, and so is every whole word in `italic`."""
    def slices(line, first):
        s = {f"[{m.start()}:{m.end()}]": ITALIC for it in italic
             for m in re.finditer(rf"\b{re.escape(it)}\b", line)}
        m = _POS.match(line) if first else None
        if m:
            s[f"[{m.start(1)}:{m.end(1)}]"] = ITALIC
        return s
    # Lines sit on BASELINES a fixed pitch apart, not stacked by bounding box: a line
    # with descenders or parentheses has a taller box, so arrange(DOWN) spaced the
    # lines unevenly. The pitch is a line holding both an ascender and a descender,
    # plus the buff, which is what arrange gave a typical line.
    pitch = crisp_text("Hg", font_size=font_size).height + GLOSS_LINE_BUFF
    out = VGroup()
    for i, l in enumerate(lines):
        t = crisp_text(l, font_size=font_size, color=color, t2s=slices(l, i == 0))
        place_on_baseline(t, (0, -i * pitch), string=l)
        out.add(t.shift(LEFT * t.get_left()[0]))
    return out
