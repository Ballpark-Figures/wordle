"""Cached YouTube stats for the mock youtube_card pages (scene 09a).

A copy of hangman/animations/assets/youtube_data.py with this video's id list.

SOURCED from the `analytics` service's Neon DB (tracked/pinned videos): the `videos`
table (title, publish date, duration) joined to the latest `samples` row (cumulative
`view_count`). `build()` queries the DB and writes the COMMITTED `youtube_cache.json`;
the scene reads it via `get()` — which imports only `json`, so the manim RENDER never
needs psycopg / DB access / network (the house "cache, don't compute at render"
pattern; a render on any machine just reads the committed cache).

Numbers are a POINT-IN-TIME snapshot: to refresh, re-run `build()` with DB access
(the analytics venv has psycopg + `analytics/.env` has DATABASE_URL) and commit the
updated cache. Every displayed number is SOURCED — the raw values + sample timestamp
are kept in the cache for provenance; formatting only reshapes them YouTube-style.

  refresh:  <umbrella>/analytics/.venv/bin/python animations/assets/youtube_data.py
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

CACHE = Path(__file__).resolve().parent / "youtube_cache.json"
_ANALYTICS = Path(__file__).resolve().parents[3] / "analytics"

# tracked videos to cache: short scene key -> YouTube video id
VIDEOS = {"hangman": "ApdLgfgfh5o"}   # Ballpark Figures — "I Tried to Solve Hangman"


def _fmt_views(n):
    """1234 -> '1.2K', 12345 -> '12K', 7325604 -> '7.3M' (YouTube-style)."""
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            q = n / div
            head = f"{q:.1f}".rstrip("0").rstrip(".") if q < 10 else str(int(q))
            return head + suf
    return str(int(n))


def _fmt_duration(seconds):
    """1170 -> '19:30'; over an hour -> 'h:mm:ss'."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_age(published):
    """A tz-aware publish datetime -> 'N years/months/… ago' as of now (build time)."""
    days = (datetime.now(timezone.utc) - published).days
    for unit, span in (("year", 365), ("month", 30), ("week", 7), ("day", 1)):
        if days >= span:
            k = days // span
            return f"{k} {unit}{'s' if k != 1 else ''} ago"
    return "today"


def build():
    """Query the analytics DB for each tracked video and write the cache. Needs DB
    access (run with the analytics venv). Returns the written data."""
    if str(_ANALYTICS) not in sys.path:
        sys.path.insert(0, str(_ANALYTICS))
    import os
    from bpkanalytics import config, db

    config.load_dotenv()
    conn = db.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    media = Path(__file__).resolve().parent / "youtube_media"
    out = {}
    for key, vid in VIDEOS.items():
        cur.execute(
            """
            select v.title, v.published_at, v.duration_seconds, c.title,
                   s.view_count, s.observed_at
            from videos v
            join channels c on c.channel_id = v.channel_id
            left join lateral (
                select view_count, observed_at from samples
                where video_id = v.video_id order by observed_at desc limit 1
            ) s on true
            where v.video_id = %s
            """,
            (vid,),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"video {vid!r} ({key}) not found in the analytics DB")
        title, published, dur, channel, views, observed = row
        out[key] = {
            "video_id": vid,
            "title": title,
            "channel": channel,
            "duration": _fmt_duration(dur),
            "meta": f"{_fmt_views(views)} views · {_fmt_age(published)}",
            # provenance — the raw sourced values + when they were sampled
            "source": {
                "view_count": views,
                "published_at": published.isoformat(),
                "duration_seconds": dur,
                "sampled_at": observed.isoformat() if observed else None,
            },
        }
        # pre-masked images committed under youtube_media/ (rounded thumbnail,
        # circle-cropped avatar), produced by youtube_media/fetch.py.
        for field, suffix in (("thumbnail", "thumb"), ("avatar", "avatar")):
            rel = f"youtube_media/{key}_{suffix}.png"
            out[key][field] = rel if (media / f"{key}_{suffix}.png").exists() else None
    conn.close()
    CACHE.write_text(json.dumps(out, indent=1))
    return out


def get(key):
    """Card kwargs (title, channel, meta, duration, thumbnail, avatar) for `key`,
    read from the cache. Image paths are resolved to absolute (per machine)."""
    d = json.loads(CACHE.read_text())[key]
    out = {k: d[k] for k in ("title", "channel", "meta", "duration")}
    for field in ("thumbnail", "avatar"):
        rel = d.get(field)
        out[field] = str(CACHE.parent / rel) if rel else None
    return out


if __name__ == "__main__":
    data = build()
    print(f"wrote {CACHE.name}: {len(data)} video(s)")
    for key, v in data.items():
        print(f"  {key}: {v['title']!r} | {v['channel']} | {v['meta']} | {v['duration']}")
        print(f"      source: {v['source']}")
