"""Screenshot the multi-Wordle games' BOARD pages, for scene 16's browser mock.

    .venv/bin/python animations/assets/web_shots.py            # every game
    .venv/bin/python animations/assets/web_shots.py octordle   # just one
    .venv/bin/python animations/assets/web_shots.py --list     # the recipes

Drives the Google Chrome already installed on this machine through Playwright
(`channel="chrome"`), so no browser is downloaded. Each game lands on a menu, and the
board only exists after clicking into it, which is why a plain `chrome --screenshot`
cannot reach it: every recipe below is a URL plus the clicks that get to the board.

Output: `animations/assets/web_media/<game>.png`, 1920x1080, dark colour scheme
requested (a site with no dark mode, like Dordle, stays light). A screenshot is a
POINT-IN-TIME capture of a live site — today's puzzle, today's layout — so re-running
replaces it; nothing here is computed. The sites change, so a recipe that stops
finding its click target FAILS LOUDLY rather than saving the menu under the board's
name.

macOS only in practice (it needs Chrome.app); `pip install playwright` is the one
dependency.
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "web_media"
VIEW = {"width": 1920, "height": 1080}
SETTLE_MS = 4000      # after load / after each click: these are JS apps with animations

# game -> (url, [click steps]). A step is a Playwright locator description:
#   ("text", "Play")        the first visible element whose text is exactly that
#   ("frame", url_part)     switch into the iframe whose url contains url_part
GAMES = {
    # the itch.io page, as a browser shows it; the game is an iframe inside it.
    # (Loaded on its own, the iframe draws in the top-left of a blank white page.)
    "dordle":       ("https://zaratustra.itch.io/dordle",
                     [("frame", "itch.zone"), ("text", "daily")]),
    # Play is a link to #/classic, and its click is intercepted, so load the route directly
    "quordle":      ("https://www.merriam-webster.com/games/quordle/#/classic", []),
    "octordle":     ("https://www.britannica.com/games/octordle",
                     [("text", "Play")]),
    "sedecordle":   ("https://www.sedecordle.com/",
                     [("text", "Daily game")]),
    "duotrigordle": ("https://duotrigordle.com/",
                     [("text", "Daily Duotrigordle")]),
    "sexaginta":    ("https://sexaginta-quattuordle.pages.dev/",
                     [("text", "daily")]),
}


def _run(game, url, steps, browser, full_page=False):
    ctx = browser.new_context(viewport=VIEW, color_scheme="dark")
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(SETTLE_MS)
        scope = page
        for kind, arg in steps:
            if kind == "frame":
                frames = [f for f in page.frames if arg in f.url]
                if not frames:
                    raise RuntimeError(f"no iframe matching {arg!r}")
                scope = frames[0]
            elif kind == "text":
                loc = scope.get_by_text(arg, exact=True).locator("visible=true").first
                loc.click(timeout=15000)
                page.wait_for_timeout(SETTLE_MS)
            else:
                raise ValueError(kind)
        OUT.mkdir(exist_ok=True)
        path = OUT / f"{game}.png"
        page.screenshot(path=str(path), full_page=full_page)
        print(f"  ok   {game:13s} {path.relative_to(OUT.parent.parent)}")
        return True
    except Exception as e:
        print(f"  FAIL {game:13s} {type(e).__name__}: {str(e).splitlines()[0]}")
        return False
    finally:
        ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("games", nargs="*", help=f"subset of: {' '.join(GAMES)}")
    ap.add_argument("--full-page", action="store_true",
                    help="capture the whole scrolling page, not just the 1080px window")
    ap.add_argument("--list", action="store_true", help="print the recipes and stop")
    a = ap.parse_args()
    if a.list:
        for g, (u, s) in GAMES.items():
            print(f"{g:13s} {u}  {s}")
        return
    bad = [g for g in a.games if g not in GAMES]
    if bad:
        sys.exit(f"unknown game(s): {bad}; known: {list(GAMES)}")
    todo = a.games or list(GAMES)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ok = [_run(g, *GAMES[g], browser, a.full_page) for g in todo]
        browser.close()
    if not all(ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
