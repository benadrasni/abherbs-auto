#!/usr/bin/env python3
"""Contact sheet of official @400 (400×600) plates for a batch review."""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

JOBS = os.path.expanduser("~/whatsthatflower/plants/_jobs")
COLS = 5
GAP = 12
LABEL_H = 28
CELL_W, CELL_H = 400, 600


def slug(name):
    return name.strip().replace(" ", "_")


def font():
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.isfile(path):
            return ImageFont.truetype(path, 14)
    return ImageFont.load_default()


def load_plate(name):
    stem = slug(name)
    path = os.path.join(JOBS, stem, "media", stem + "@400.webp")
    if not os.path.isfile(path):
        raise SystemExit("missing %s" % path)
    im = Image.open(path).convert("RGB")
    if im.size != (CELL_W, CELL_H):
        im = im.resize((CELL_W, CELL_H), Image.Resampling.LANCZOS)
    return im


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="JPEG path for the contact sheet")
    parser.add_argument(
        "--names",
        nargs="+",
        required=True,
        help='Latin names, e.g. "Andromeda polifolia"',
    )
    parser.add_argument(
        "--indexes",
        nargs="*",
        type=int,
        help="Optional plants_to_update indexes, same order as --names",
    )
    args = parser.parse_args()
    names = args.names
    indexes = args.indexes or []
    if indexes and len(indexes) != len(names):
        raise SystemExit("--indexes must match --names length")

    cols = min(COLS, len(names))
    rows = (len(names) + cols - 1) // cols
    cell_h = CELL_H + LABEL_H
    width = cols * CELL_W + (cols + 1) * GAP
    height = rows * cell_h + (rows + 1) * GAP
    sheet = Image.new("RGB", (width, height), (40, 38, 34))
    draw = ImageDraw.Draw(sheet)
    face = font()

    for i, name in enumerate(names):
        row, col = divmod(i, cols)
        im = load_plate(name)
        x = GAP + col * (CELL_W + GAP)
        y = GAP + row * (cell_h + GAP)
        sheet.paste(im, (x, y))
        if indexes:
            caption = "%d  %s" % (indexes[i], name)
        else:
            caption = name
        draw.rectangle((x, y + CELL_H, x + CELL_W, y + CELL_H + LABEL_H), fill=(28, 26, 24))
        draw.text((x + 6, y + CELL_H + 6), caption, fill=(230, 224, 210), font=face)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    sheet.save(args.out, "JPEG", quality=90)
    print(args.out, sheet.size)


if __name__ == "__main__":
    sys.exit(main() or 0)
