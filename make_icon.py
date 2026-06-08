"""Generate jans.icns and the full iconset from scratch using Pillow."""
import math
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ORANGE = (224, 122, 62)   # #e07a3e
WHITE  = (255, 255, 255)
SIZE   = 1024

ICONSET_SIZES = [16, 32, 64, 128, 256, 512, 1024]


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Squircle background (rounded square, radius ≈ 22% like macOS)
    r = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=ORANGE)

    # Subtle inner shadow at bottom for depth
    for i in range(int(size * 0.04)):
        alpha = int(40 * (1 - i / (size * 0.04)))
        draw.rounded_rectangle(
            [i, i, size - 1 - i, size - 1 - i],
            radius=max(r - i, 0),
            outline=(0, 0, 0, alpha),
            width=1,
        )

    # "j" glyph — try SF Pro Display Bold, fall back to system fonts
    font_candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Arial.ttf",
    ]
    font = None
    font_size = int(size * 0.72)
    for path in font_candidates:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                continue

    text = "j"
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size - tw) / 2 - bbox[0]
        y = (size - th) / 2 - bbox[1] - int(size * 0.04)  # slight upward nudge
        draw.text((x, y), text, font=font, fill=WHITE)
    else:
        # Fallback: draw a thick "j" shape manually
        cx, cy = size // 2, size // 2
        sw = max(int(size * 0.13), 4)
        # vertical bar
        draw.rounded_rectangle(
            [cx - sw // 2, int(size * 0.18), cx + sw // 2, int(size * 0.72)],
            radius=sw // 2, fill=WHITE
        )
        # hook at bottom
        hook_r = int(size * 0.18)
        draw.arc(
            [cx - hook_r - sw // 2, int(size * 0.54),
             cx + hook_r - sw // 2 + sw, int(size * 0.54) + hook_r * 2],
            start=0, end=200, fill=WHITE, width=sw
        )
        # dot above bar
        dot_r = sw * 0.65
        draw.ellipse(
            [cx - dot_r, int(size * 0.1) - dot_r,
             cx + dot_r, int(size * 0.1) + dot_r],
            fill=WHITE
        )

    return img


def main():
    out_dir = Path(__file__).parent
    iconset = out_dir / "jans.iconset"
    iconset.mkdir(exist_ok=True)

    master = make_icon(SIZE)

    for s in ICONSET_SIZES:
        img = master.resize((s, s), Image.LANCZOS)
        img.save(iconset / f"icon_{s}x{s}.png")
        if s <= 512:
            img2x = master.resize((s * 2, s * 2), Image.LANCZOS)
            img2x.save(iconset / f"icon_{s}x{s}@2x.png")

    # iconutil expects specific names
    renames = {
        "icon_16x16.png":     "icon_16x16.png",
        "icon_16x16@2x.png":  "icon_16x16@2x.png",
        "icon_32x32.png":     "icon_32x32.png",
        "icon_32x32@2x.png":  "icon_32x32@2x.png",
        "icon_128x128.png":   "icon_128x128.png",
        "icon_128x128@2x.png":"icon_128x128@2x.png",
        "icon_256x256.png":   "icon_256x256.png",
        "icon_256x256@2x.png":"icon_256x256@2x.png",
        "icon_512x512.png":   "icon_512x512.png",
        "icon_512x512@2x.png":"icon_512x512@2x.png",
    }

    icns_path = out_dir / "jans.icns"
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("iconutil error:", result.stderr)
    else:
        print(f"Created {icns_path}")
        print(f"Iconset at {iconset}")


if __name__ == "__main__":
    main()
