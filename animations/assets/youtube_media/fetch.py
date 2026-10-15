"""Fetch + pre-process images for the mock YouTube UI, into committed PNGs beside
this file: for each VIDEOS entry its rounded thumbnail (<key>_thumb.png) and its
channel's avatar (<key>_avatar.png); for each CHANNELS entry just the avatar. Masked
so manim's ImageMobject shows them directly (rounded corners / circle crop). Run with
the RENDER venv (it ships Pillow):

    .venv/bin/python animations/assets/youtube_media/fetch.py [key ...]

With keys, only those entries are fetched (every other image stays as committed).

The avatar URL comes from the YouTube Data API (`channels.list` by handle),
`videos.list` for thumbnails, authenticated with the `YOUTUBE_API_KEY` in
`analytics/.env` — the same route as hangman's youtube_media/fetch.py. Refresh
rarely. Keep VIDEOS in step with assets/youtube_data.VIDEOS.
"""
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

OUT = Path(__file__).resolve().parent
_ENV = Path(__file__).resolve().parents[4] / "analytics" / ".env"
CHANNELS = {"bpk": "@BPKFigures"}   # key -> channel handle
VIDEOS = {"hangman": "ApdLgfgfh5o",   # key -> video id (Ballpark Figures, "I Tried to Solve Hangman")
          "rasmussen": "zoh5eLOjwHA",  # Ellie Rasmussen, "You should play Wordle wrong" (bonus video)
          "pokecheese": "dCUvQ7HIDmA"}  # Pokecheese, the "Broken" Wordle strategy video (bonus video)


def _api_key():
    for line in _ENV.read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "YOUTUBE_API_KEY":
            return v.strip().strip('"').strip("'")
    raise RuntimeError(f"YOUTUBE_API_KEY not found in {_ENV}")


def _api(endpoint, **params):
    params["key"] = _api_key()
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as r:
        return json.load(r)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return r.read()


def _best(thumbnails):
    for size in ("maxres", "standard", "high", "medium", "default"):
        if size in thumbnails:
            return thumbnails[size]["url"]
    raise RuntimeError("no thumbnail sizes returned")


def _rounded(img, frac=0.045):
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, w - 1, h - 1], radius=int(min(w, h) * frac), fill=255)
    img.putalpha(mask)
    return img


def _open(data):
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _circle(img):
    img = ImageOps.fit(img, (min(img.size),) * 2)     # center-crop to square
    s = img.size[0]
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=255)
    img.putalpha(mask)
    return img


if __name__ == "__main__":
    import sys
    # optional keys: fetch just those, leaving every other committed image untouched
    only = set(sys.argv[1:])
    for key, handle in CHANNELS.items():
        if only and key not in only:
            continue
        items = _api("channels", part="snippet", forHandle=handle).get("items") or []
        if not items:
            raise RuntimeError(f"no channel found for handle {handle!r}")
        chan = items[0]["snippet"]
        avatar = _circle(_open(_get(_best(chan["thumbnails"]))))
        avatar.save(OUT / f"{key}_avatar.png")
        print(f"{key}: {chan['title']!r} -> {key}_avatar.png {avatar.size}")
    for key, vid in VIDEOS.items():
        if only and key not in only:
            continue
        v = _api("videos", part="snippet", id=vid)["items"][0]["snippet"]
        chan = _api("channels", part="snippet", id=v["channelId"])["items"][0]["snippet"]
        thumb = _rounded(_open(_get(_best(v["thumbnails"]))))
        thumb.save(OUT / f"{key}_thumb.png")
        avatar = _circle(_open(_get(_best(chan["thumbnails"]))))
        avatar.save(OUT / f"{key}_avatar.png")
        print(f"{key}: {v['title']!r} -> {key}_thumb.png {thumb.size}, {key}_avatar.png {avatar.size}")
