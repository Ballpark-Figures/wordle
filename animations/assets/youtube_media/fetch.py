"""Fetch + pre-process channel avatars for the mock YouTube UI, into committed PNGs
beside this file (<key>_avatar.png), circle-cropped so manim's ImageMobject shows
them directly. Run with the RENDER venv (it ships Pillow):

    .venv/bin/python animations/assets/youtube_media/fetch.py

The avatar URL comes from the YouTube Data API (`channels.list` by handle),
authenticated with the `YOUTUBE_API_KEY` in `analytics/.env` — the same route as
hangman's youtube_media/fetch.py. Refresh rarely; an avatar changes seldom.
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


def _circle(img):
    img = ImageOps.fit(img, (min(img.size),) * 2)     # center-crop to square
    s = img.size[0]
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=255)
    img.putalpha(mask)
    return img


if __name__ == "__main__":
    for key, handle in CHANNELS.items():
        items = _api("channels", part="snippet", forHandle=handle).get("items") or []
        if not items:
            raise RuntimeError(f"no channel found for handle {handle!r}")
        chan = items[0]["snippet"]
        avatar = _circle(Image.open(io.BytesIO(_get(_best(chan["thumbnails"])))).convert("RGBA"))
        avatar.save(OUT / f"{key}_avatar.png")
        print(f"{key}: {chan['title']!r} -> {key}_avatar.png {avatar.size}")
