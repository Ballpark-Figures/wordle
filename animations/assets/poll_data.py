"""Cached YouTube community-poll results for the mock poll (bpkfigures.youtube_poll).

SOURCED by hand: YouTube's Data API has NO community-post / poll endpoint, so the
values in the COMMITTED `poll_cache.json` were transcribed from a screenshot of the
live poll (the `source` field says when). Nothing here computes anything; `get()`
reads the cache and resolves the avatar path. To refresh, re-screenshot the poll and
edit the cache by hand.
"""
from pathlib import Path
import json

CACHE = Path(__file__).resolve().parent / "poll_cache.json"


def get(key):
    """youtube_poll kwargs (channel, age, question, votes, options, likes, avatar)."""
    d = json.loads(CACHE.read_text())[key]
    out = {k: d[k] for k in ("channel", "age", "question", "votes", "likes")}
    out["options"] = [tuple(o) for o in d["options"]]
    out["avatar"] = str(CACHE.parent / d["avatar"]) if d.get("avatar") else None
    return out
