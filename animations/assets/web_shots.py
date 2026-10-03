"""Screenshot the pages shown in browser mocks: the multi-Wordle games' BOARD pages
(scene 16) and the 80,000 Hours pages of the sponsor read (scenes 21-22).

    .venv/bin/python animations/assets/web_shots.py            # every game
    .venv/bin/python animations/assets/web_shots.py octordle   # just one
    .venv/bin/python animations/assets/web_shots.py --list     # the recipes

Drives the Google Chrome already installed on this machine through Playwright
(`channel="chrome"`), so no browser is downloaded. Each game lands on a menu, and the
board only exists after clicking into it, which is why a plain `chrome --screenshot`
cannot reach it: every recipe below is a URL plus the clicks that get to the board.

Output: `animations/assets/web_media/<game>.png`, 1920x1080 unless `--size` says
otherwise (scene 16 uses 1920x1490), dark colour scheme
requested (a site with no dark mode, like Dordle, stays light) unless a recipe names
its own scheme as a third field. A screenshot is a
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
SETTLE_MS = 4000

# Requests to these hosts are dropped, so no ad lands in a screenshot (a real ad
# would put a third party's creative in the video). Substring match on the host.
AD_HOSTS = ("doubleclick", "googlesyndication", "googleadservices", "adservice",
            "amazon-adsystem", "adnxs", "rubiconproject", "pubmatic", "openx",
            "criteo", "taboola", "outbrain", "moatads", "teads", "casalemedia",
            "33across", "sharethrough", "indexww", "adsrvr", "smartadserver",
            "gumgum", "media.net", "yieldmo", "triplelift", "lijit", "sovrn",
            "adform", "springserve", "pubnation", "kargo", "connatix", "freestar",
            "googletagservices", "securepubads", "ad-delivery", "adsafeprotected")


def _block_ads(route):
    host = route.request.url.split("/")[2] if "://" in route.request.url else ""
    if any(a in host for a in AD_HOSTS):
        return route.abort()
    return route.continue_()      # after load / after each click: these are JS apps with animations

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
    # the sponsor read (80,000 Hours): plain pages, no clicks, LIGHT scheme -- the
    # site as a visitor normally sees it
    "80k_doctor":   ("https://80000hours.org/articles/how-many-lives-does-a-doctor-save-part-1/",
                     [], "light"),
    "80k_problems": ("https://80000hours.org/career-guide/world-problems/", [], "light"),
    "80k_elie":     ("https://80000hours.org/podcast/episodes/elie-hassenfeld-givewell-critiques-and-lessons/",
                     [], "light"),
    "80k_oster":    ("https://80000hours.org/podcast/episodes/emily-oster-pregnancy-parenting-careers/",
                     [], "light"),
    "80k_silver":   ("https://80000hours.org/podcast/episodes/nate-silver-effective-altruism-sbf-art-of-risk/",
                     [], "light"),
    # the sign-up page the read's link lands on (the sponsorship's own tracked URL)
    "80k_guide":    ("https://80000hours.org/gettheguide/?utm_source=youtube&utm_campaign=2026-80KMAR-ballpark&utm_medium=sponsorship",
                     [], "light"),
}


def _run(game, url, steps, browser, full_page=False, view=VIEW, scheme="dark"):
    ctx = browser.new_context(viewport=view, color_scheme=scheme)
    ctx.route("**/*", _block_ads)
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
    ap.add_argument("--size", default="1920x1080",
                    help="browser viewport WxH in px (default 1920x1080); scene 16's "
                         "windows use 1920x1490")
    ap.add_argument("--full-page", action="store_true",
                    help="capture the whole scrolling page, not just the 1080px window")
    ap.add_argument("--list", action="store_true", help="print the recipes and stop")
    a = ap.parse_args()
    if a.list:
        for g, (u, s, *sc) in GAMES.items():
            print(f"{g:13s} {u}  {s}  {sc[0] if sc else 'dark'}")
        return
    bad = [g for g in a.games if g not in GAMES]
    if bad:
        sys.exit(f"unknown game(s): {bad}; known: {list(GAMES)}")
    todo = a.games or list(GAMES)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        w, h = (int(x) for x in a.size.lower().split("x"))
        ok = []
        for g in todo:
            url, steps, *scheme = GAMES[g]
            ok.append(_run(g, url, steps, browser, a.full_page,
                           {"width": w, "height": h}, *scheme))
        browser.close()
    if not all(ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
