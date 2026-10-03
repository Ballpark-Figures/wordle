"""The 80,000 Hours pages shown in the sponsor read's browser window (scenes 21-23).

One place for every page's screenshot, address and tab title, and for the window
they sit in, so the two scenes cannot drift apart.

The screenshots are `web_media/80k_*.png`, 1920x1080, light scheme, made by
`assets/web_shots.py` (recipes `80k_*`). Tab titles are the pages' own headlines;
`browser.py` cuts a long one to the tab with an ellipsis, as Chrome does.
"""
from pathlib import Path

from bpkfigures.browser import browser_window

MEDIA = Path(__file__).resolve().parent / "web_media"

# a 16:9 page plus browser.py's tab strip + toolbar is 0.6085 x its width tall, so
# 13.2 wide is 8.03 tall: centred, 0.47 of light blue above and below
WIN_W = 13.2

# screenshot -> (address, tab title)
PAGES = {
    "80k_doctor":   ("80000hours.org/articles/how-many-lives-does-a-doctor-save-part-1",
                     "How many lives does a doctor save? (Part 1)"),
    "80k_problems": ("80000hours.org/career-guide/world-problems",
                     "How we rank the world’s most pressing problems (and why)"),
    "80k_elie":     ("80000hours.org/podcast/episodes/elie-hassenfeld-givewell-critiques-and-lessons",
                     "#153 – Elie Hassenfeld on two big-picture critiques of GiveWell’s approach"),
    "80k_oster":    ("80000hours.org/podcast/episodes/emily-oster-pregnancy-parenting-careers",
                     "#178 – Emily Oster on what the evidence actually says about pregnancy and parenting"),
    "80k_silver":   ("80000hours.org/podcast/episodes/nate-silver-effective-altruism-sbf-art-of-risk",
                     "#204 – Nate Silver on making sense of SBF, and his biggest critiques of effective altruism"),
    # the address as Chrome shows it: the full tracked link, scheme hidden
    "80k_guide":    ("80000hours.org/gettheguide/?utm_source=youtube&utm_campaign=2026-80KMAR-ballpark&utm_medium=sponsorship",
                     "Get the career guide"),
}


def _image(name):
    return str(MEDIA / f"{name}.png")


def window(name):
    """The browser window, showing page `name`, centred on the frame."""
    url, title = PAGES[name]
    return browser_window(url, title, image=_image(name), width=WIN_W)


def swipe(win, name):
    """The window's page slides left to page `name` (an Animation; the caller's
    play sets its run_time)."""
    url, title = PAGES[name]
    return win.swipe_to(_image(name), url, title)
