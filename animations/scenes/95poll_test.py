"""SCRATCH — the mock YouTube poll (bpkfigures.youtube_poll), for checking the
design before it goes into scene 09.

  a poll_dk — full-screen dark-mode poll post
  b poll_lt — full-screen light-mode poll post

Each is a `@still` (a series of images, no animation between them).
Render:  render 95 all   /   render 95a --fast
"""
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from config import *
from bpkfigures.youtube_card import youtube_poll
from assets.poll_data import get as poll_get

# SOURCED by hand from a screenshot of the live poll — see assets/poll_cache.json
POLL = poll_get("wordle")


class PollTest(WordleScene):

    # a : full-screen dark-mode poll
    @still
    def poll_dk(self):
        self.add(youtube_poll(**POLL, width=12.0, dark=True, page=True))

    # b : full-screen light-mode poll
    @still
    def poll_lt(self):
        self.add(youtube_poll(**POLL, width=12.0, dark=False, page=True))
