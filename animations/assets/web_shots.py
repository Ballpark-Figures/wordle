"""Screenshot the pages shown in browser mocks: the multi-Wordle games' BOARD pages
(scene 16), the 80,000 Hours pages of the sponsor read (scenes 21-23), and NYT
Wordle's own Settings panel with Hard Mode switched on (THM).

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
its own (the recipe's options dict, which can also set a page zoom and a
full-page capture).

A recipe with `shot` steps saves THOSE, as `<game>_<name>.png`, and no final
screenshot -- several states of one page from one session. `box` steps write
`<game>_boxes.json`: each named element's box in SCREENSHOT PIXELS (zoom applied),
`[left, top, right, bottom]`, so a scene can aim at it without eyeballing.

A screenshot is a
POINT-IN-TIME capture of a live site — today's puzzle, today's layout — so re-running
replaces it; nothing here is computed. The sites change, so a recipe that stops
finding its click target FAILS LOUDLY rather than saving the menu under the board's
name.

macOS only in practice (it needs Chrome.app); `pip install playwright` is the one
dependency.
"""
import argparse
import json
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

# game -> (url, [click steps], {options}). A step is a Playwright locator description:
#   ("text", "Play")        the first visible element whose text is exactly that
#   ("frame", url_part)     switch into the iframe whose url contains url_part
#   ("click", css)          click the first visible element matching a CSS selector
#   ("key", "Escape")       press a key
#   ("hide", css)           hide every element matching a CSS selector (display: none)
#   ("shot", name)          save a screenshot now, as <game>_<name>.png
#   ("box", css, name)      record that element's box, into <game>_boxes.json
# options (all optional) are `_run`'s: scheme ("dark"), zoom (1.0), full_page (False)
# the 80,000 Hours pages are captured ZOOMED, as Chrome's page zoom would show them:
# laid out in a 1920/ZOOM-wide window and captured at ZOOM x the pixel density, so
# the PNG is still 1920 wide but the site's text column fills more of it
ZOOM_80K = 1.5
LIGHT_80K = {"scheme": "light", "zoom": ZOOM_80K}
# the multi-Wordle board pages (scene 16) are zoomed the same way, so the boards
# fill more of the small windows in the 3x2 variants grid
ZOOM_MULTI = {"zoom": 1.25}

GAMES = {
    # the itch.io page, as a browser shows it; the game is an iframe inside it.
    # (Loaded on its own, the iframe draws in the top-left of a blank white page.)
    "dordle":       ("https://zaratustra.itch.io/dordle",
                     [("frame", "itch.zone"), ("text", "daily")], ZOOM_MULTI),
    # Play is a link to #/classic, and its click is intercepted, so load the route directly
    "quordle":      ("https://www.merriam-webster.com/games/quordle/#/classic", [], ZOOM_MULTI),
    "octordle":     ("https://www.britannica.com/games/octordle",
                     [("text", "Play")], ZOOM_MULTI),
    "sedecordle":   ("https://www.sedecordle.com/",
                     [("text", "Daily game")], ZOOM_MULTI),
    "duotrigordle": ("https://duotrigordle.com/",
                     [("text", "Daily Duotrigordle")], ZOOM_MULTI),
    "sexaginta":    ("https://sexaginta-quattuordle.pages.dev/",
                     [("text", "daily")], ZOOM_MULTI),
    # the sponsor read (80,000 Hours): plain pages, no clicks, LIGHT scheme -- the
    # site as a visitor normally sees it
    "80k_home":     ("https://80000hours.org/", [], LIGHT_80K),   # scene 21's opening page
    "80k_doctor":   ("https://80000hours.org/articles/how-many-lives-does-a-doctor-save-part-1/",
                     [], LIGHT_80K),
    "80k_problems": ("https://80000hours.org/career-guide/world-problems/", [], LIGHT_80K),
    "80k_podcast":  ("https://80000hours.org/podcast/", [], LIGHT_80K),   # scene 21c
    "80k_elie":     ("https://80000hours.org/podcast/episodes/elie-hassenfeld-givewell-critiques-and-lessons/",
                     [], LIGHT_80K),
    "80k_oster":    ("https://80000hours.org/podcast/episodes/emily-oster-pregnancy-parenting-careers/",
                     [], LIGHT_80K),
    "80k_silver":   ("https://80000hours.org/podcast/episodes/nate-silver-effective-altruism-sbf-art-of-risk/",
                     [], LIGHT_80K),
    # the sign-up page the read's link lands on (the sponsorship's own tracked URL);
    # the WHOLE page, since scene 23 scrolls down it
    "80k_guide":    ("https://80000hours.org/gettheguide/?utm_source=youtube&utm_campaign=2026-80KMAR-ballpark&utm_medium=sponsorship",
                     [], {**LIGHT_80K, "full_page": True}),
    # scene 25: an empty Wordle board, then CEART typed one letter at a time (a shot
    # after each key, so the typing is the real page's own states). Same opening
    # steps and ad-slot hiding as the "wordle" recipe below.
    "ceart":        ("https://www.nytimes.com/games/wordle/index.html",
                     [("click", '[data-testid="Play"]'), ("key", "Escape"),
                      ("hide", '[class*="Ad-module_adContainer"]'),
                      ("shot", "0"),
                      ("key", "c"), ("shot", "1"), ("key", "e"), ("shot", "2"),
                      ("key", "a"), ("shot", "3"), ("key", "r"), ("shot", "4"),
                      ("key", "t"), ("shot", "5")],
                     {"zoom": ZOOM_80K}),
    # NYT Wordle, dark, three states for THM's click on Hard Mode: the game page, the
    # Settings panel open (Hard Mode off), and Hard Mode on. Play, then Escape closes
    # the how-to-play modal. The logged-out page has an ad slot across the top --
    # empty, as ads are blocked -- and it is HIDDEN (user's call), so the layout
    # closes up as if there were no ad. Zoomed like the 80k pages.
    "wordle":       ("https://www.nytimes.com/games/wordle/index.html",
                     [("click", '[data-testid="Play"]'), ("key", "Escape"),
                      ("hide", '[class*="Ad-module_adContainer"]'),
                      ("box", '[data-testid="settings-button"]', "gear"),
                      ("shot", "game"),
                      ("click", '[data-testid="settings-button"]'),
                      ("box", '[aria-label="Hard Mode"][role="switch"]', "hard_mode"),
                      ("shot", "settings"),
                      ("click", '[aria-label="Hard Mode"][role="switch"]'),
                      ("shot", "hard")],
                     {"zoom": ZOOM_80K}),
    # the bonus video's variants, each as its site first shows it (light where the
    # site has no dark mode; Wikipedia in its normal light scheme)
    "lingo_wiki":   ("https://en.wikipedia.org/wiki/Lingo_(American_game_show)",
                     [("hide", "#siteNotice")], LIGHT_80K),   # a campaign banner, hidden
    "absurdle":     ("https://qntm.org/files/absurdle/absurdle.html", [], {"zoom": ZOOM_80K}),
    # its home page (the daily game's card): the game page itself did not load in
    # the headless browser (2026-10-11), with or without its how-to-play closed
    "letroso":      ("https://letroso.com/en", [], {"zoom": ZOOM_80K}),
    "foximax":      ("https://foximax.com/", [("text", "Close")], {"zoom": ZOOM_80K}),
    "nerdle":       ("https://www.nerdlegame.com/", [("text", "play 8-digit classic"),
                                                     ("text", "play now"),
                                                     ("hide", ".triangle-new")],
                     {"zoom": ZOOM_80K}),                     # the game, its hint bubble hidden
}


def _run(game, url, steps, browser, full_page=False, view=VIEW, scheme="dark", zoom=1.0):
    # zoom: lay the page out in a window 1/zoom the size, at zoom x the pixel
    # density, so the capture keeps `view`'s pixel size with everything bigger
    css = {"width": round(view["width"] / zoom), "height": round(view["height"] / zoom)}
    ctx = browser.new_context(viewport=css, device_scale_factor=zoom,
                              color_scheme=scheme)
    ctx.route("**/*", _block_ads)
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(SETTLE_MS)
        scope = page
        shots, boxes = [], {}
        for kind, arg, *more in steps:
            if kind == "frame":
                frames = [f for f in page.frames if arg in f.url]
                if not frames:
                    raise RuntimeError(f"no iframe matching {arg!r}")
                scope = frames[0]
            elif kind == "text":
                loc = scope.get_by_text(arg, exact=True).locator("visible=true").first
                loc.click(timeout=15000)
                page.wait_for_timeout(SETTLE_MS)
            elif kind == "click":
                scope.locator(arg).locator("visible=true").first.click(timeout=15000)
                page.wait_for_timeout(SETTLE_MS)
            elif kind == "key":
                page.keyboard.press(arg)
                page.wait_for_timeout(SETTLE_MS)
            elif kind == "hide":
                if scope.locator(arg).count() == 0:
                    raise RuntimeError(f"nothing to hide matching {arg!r}")
                scope.add_style_tag(content=f"{arg} {{ display: none !important; }}")
                page.wait_for_timeout(1000)
            elif kind == "shot":
                OUT.mkdir(exist_ok=True)
                path = OUT / f"{game}_{arg}.png"
                page.screenshot(path=str(path), full_page=full_page)
                shots.append(path)
            elif kind == "box":
                r = scope.locator(arg).locator("visible=true").first.bounding_box(timeout=15000)
                if r is None:
                    raise RuntimeError(f"no box for {arg!r}")
                boxes[more[0]] = [round(v * zoom, 1) for v in
                                  (r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"])]
            else:
                raise ValueError(kind)
        OUT.mkdir(exist_ok=True)
        if not shots:
            path = OUT / f"{game}.png"
            page.screenshot(path=str(path), full_page=full_page)
            shots.append(path)
        if boxes:
            path = OUT / f"{game}_boxes.json"
            path.write_text(json.dumps(boxes, indent=2) + "\n")
            shots.append(path)
        for path in shots:
            print(f"  ok   {game:13s} {path.relative_to(OUT.parent.parent)}")
        # the address and tab title a browser mock shows, read off the live page
        print(f"       {'':13s} url {page.url}   title {page.title()!r}")
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
        for g, (u, s, *opts) in GAMES.items():
            print(f"{g:13s} {u}  {s}  {opts[0] if opts else ''}")
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
            url, steps, *opts = GAMES[g]
            opts = dict(opts[0]) if opts else {}
            full = a.full_page or opts.pop("full_page", False)
            ok.append(_run(g, url, steps, browser, full,
                           {"width": w, "height": h}, **opts))
        browser.close()
    if not all(ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
