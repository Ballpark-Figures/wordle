"""Make a SHARP channel avatar from the channel's own logo, not YouTube's 800-px copy.

The logo is drawn by manim (the umbrella's `logo.py`, scene `Logo`), so it can be
rendered at any resolution. This renders it at 4K and circle-crops it to the framing
YouTube uses for the avatar (the donut spans ~75% of the circle's diameter, centred
a touch below the middle, matching bpk_avatar.png), writing bpk_logo.png.

    .venv/bin/python animations/assets/youtube_media/logo_avatar.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "bpk_logo.png"
LOGO = Path(__file__).resolve().parents[4] / "logo.py"
DONUT_FRACTION = 0.75       # donut width / avatar diameter (read off bpk_avatar.png)
DONUT_CY_FRACTION = 0.52    # donut centre height / avatar diameter, from the top

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, "-m", "manim", "-s", "-qk", "--media_dir", tmp,
                        str(LOGO), "Logo"], check=True, capture_output=True)
        img = Image.open(next(Path(tmp).rglob("Logo*.png"))).convert("RGBA")
    # the donut is everything NOT the flat background colour
    bg = img.getpixel((0, 0))
    px = img.load()
    w, h = img.size
    xs, ys = [], []
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            if px[x, y][:3] != bg[:3]:
                xs.append(x); ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    d = int((x1 - x0) / DONUT_FRACTION)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left, top = int(cx - d / 2), int(cy - DONUT_CY_FRACTION * d)
    crop = img.crop((left, top, left + d, top + d))
    circ = Image.new("L", (d, d), 0)
    ImageDraw.Draw(circ).ellipse([0, 0, d - 1, d - 1], fill=255)
    crop.putalpha(circ)
    crop.save(OUT)
    print(f"wrote {OUT.name} {crop.size} (donut {x1 - x0}x{y1 - y0} px)")
