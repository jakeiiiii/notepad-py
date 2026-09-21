#!/usr/bin/env python3
"""Draws the NotepadClone icon and writes every format the project needs.

    pip install pillow
    python tools/make_icon.py

Outputs (all committed, so the build does not need Pillow):
    assets/icon.png    512 px master image
    assets/icon.ico    Windows executable icon
    assets/icon.icns   macOS app icon
    assets/icon_b64.txt  128 px PNG as base64, pasted into ICON_PNG in notepadClone.py
"""
import base64
import io
import os
import textwrap

from PIL import Image, ImageDraw

S = 1024  # drawn large, then downsampled for smooth edges
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

BACKGROUND_TOP = (45, 140, 235)
BACKGROUND_BOTTOM = (20, 84, 184)
PAPER = (255, 255, 255)
PAPER_SHADOW = (10, 50, 120, 70)
BINDING = (38, 50, 72)
RING = (176, 190, 210)
LINE = (170, 196, 232)
PENCIL_BODY = (255, 193, 47)
PENCIL_SIDE = (240, 160, 20)
PENCIL_WOOD = (250, 222, 180)
PENCIL_TIP = (52, 60, 80)
ERASER = (240, 110, 120)


def draw_icon() -> Image.Image:
    # Rounded-square background with a vertical gradient
    gradient = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        gradient.putpixel(
            (0, y), tuple(round(a + (b - a) * t) for a, b in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM))
        )
    gradient = gradient.resize((S, S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(gradient, (0, 0), mask)

    # Paper with a soft drop shadow
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((262, 232, 782, 872), radius=44, fill=PAPER_SHADOW)
    icon.alpha_composite(shadow)
    d = ImageDraw.Draw(icon)
    d.rounded_rectangle((242, 200, 762, 840), radius=44, fill=PAPER)

    # Binding strip and rings
    d.rounded_rectangle((242, 200, 762, 300), radius=44, fill=BINDING)
    d.rectangle((242, 256, 762, 300), fill=BINDING)
    for x in range(312, 740, 95):
        d.rounded_rectangle((x - 17, 150, x + 17, 262), radius=17, fill=RING)

    # Text lines
    for i, width in enumerate((400, 400, 330, 400, 250)):
        y = 380 + i * 84
        d.rounded_rectangle((302, y, 302 + width, y + 30), radius=15, fill=LINE)

    # Pencil, drawn upright on its own layer and then rotated into place
    pencil = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    p = ImageDraw.Draw(pencil)
    cx, top, bottom, half = S // 2, 250, 700, 46
    p.rounded_rectangle((cx - half, top, cx + half, top + 70), radius=20, fill=ERASER)
    p.rectangle((cx - half, top + 56, cx + half, top + 92), fill=RING)
    p.rectangle((cx - half, top + 92, cx + half, bottom), fill=PENCIL_BODY)
    p.rectangle((cx + 10, top + 92, cx + half, bottom), fill=PENCIL_SIDE)
    p.polygon([(cx - half, bottom), (cx + half, bottom), (cx, bottom + 120)], fill=PENCIL_WOOD)
    p.polygon([(cx - 17, bottom + 76), (cx + 17, bottom + 76), (cx, bottom + 120)], fill=PENCIL_TIP)
    pencil = pencil.rotate(-38, resample=Image.BICUBIC, center=(cx, S // 2))
    icon.alpha_composite(pencil, (170, 110))
    return icon


def main():
    os.makedirs(ASSETS, exist_ok=True)
    master = draw_icon()

    master.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS, "icon.png"), optimize=True)
    master.save(
        os.path.join(ASSETS, "icon.ico"),
        sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
    )
    master.save(os.path.join(ASSETS, "icon.icns"))

    buf = io.BytesIO()
    small = master.resize((128, 128), Image.LANCZOS)
    small = small.quantize(colors=128, method=Image.Quantize.FASTOCTREE)  # small PNG-8 with alpha
    small.save(buf, "PNG", optimize=True)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    with open(os.path.join(ASSETS, "icon_b64.txt"), "w", newline="\n") as f:
        f.write("\n".join(textwrap.wrap(encoded, 96)) + "\n")
    print(f"embedded PNG: {buf.tell():,} bytes -> {len(encoded):,} base64 characters")


if __name__ == "__main__":
    main()
