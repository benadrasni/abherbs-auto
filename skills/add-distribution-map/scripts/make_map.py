#!/usr/bin/env python3
"""Build native/introduced distribution WebPs for catalog species.

    ingest/.venv/bin/python make_map.py "Arctium tomentosum" "Acer campestre"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
INGEST = Path.home() / "whatsthatflower" / "ingest"
JOBS = Path.home() / "whatsthatflower" / "plants" / "_jobs"
MAPS = INGEST / "data" / "maps"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
WIDTH, HEIGHT = 2754, 1398

sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(INGEST))
sys.path.insert(0, str(MAPS))

from l3_map import classes_for_l3  # noqa: E402
from fill_blank_world import (  # noqa: E402
    DEFAULT_INTRODUCED,
    DEFAULT_INTRODUCED_STROKE,
    apply,
)
from focus import apply_focus  # noqa: E402
from sources import wcvp  # noqa: E402


def slug(name: str) -> str:
    return name.strip().replace(" ", "_")


def lookup_areas(name: str) -> dict:
    hit = wcvp.lookup(name, include_introduced=True)
    if not hit:
        parts = name.split()
        if len(parts) >= 2:
            rest = " ".join(parts[1:])
            for alt in ("%s × %s" % (parts[0], rest), "%s x %s" % (parts[0], rest)):
                hit = wcvp.lookup(alt, include_introduced=True)
                if hit:
                    break
    if not hit:
        # Catalog keys sometimes keep a hybrid sign that WCVP treats as
        # the uncrossed binomial (e.g. Dahlia × pinnata → Dahlia pinnata).
        collapsed = " ".join(
            p for p in name.replace("×", " ").split() if p.lower() != "x"
        )
        if collapsed != name.strip():
            hit = wcvp.lookup(collapsed, include_introduced=True)
    if not hit:
        raise SystemExit("WCVP miss: %s" % name)
    native, n_miss = classes_for_l3(hit.get("native_l3") or [])
    intro, i_miss = classes_for_l3(hit.get("introduced_l3") or [])
    intro = [c for c in intro if c not in native]
    return {
        "query": name,
        "accepted": hit.get("accepted_name") or hit.get("query_name"),
        "native": native,
        "introduced": intro,
        "unmapped_native": n_miss,
        "unmapped_introduced": i_miss,
        "native_l3": hit.get("native_l3") or [],
        "introduced_l3": hit.get("introduced_l3") or [],
    }


def screenshot(svg_path: Path, png_path: Path) -> None:
    if not os.path.isfile(CHROME):
        raise SystemExit("Chrome not found at %s" % CHROME)
    # Ocean-coloured letterbox so a cropped viewBox still fills 2754×1398.
    html_path = svg_path.with_suffix(".html")
    svg = svg_path.read_text(encoding="utf-8")
    html_path.write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
        "html,body{margin:0;background:#c0dde5;width:%dpx;height:%dpx;overflow:hidden}"
        "svg{width:%dpx;height:%dpx;display:block}"
        "</style></head><body>%s</body></html>"
        % (WIDTH, HEIGHT, WIDTH, HEIGHT, svg),
        encoding="utf-8",
    )
    subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=%d,%d" % (WIDTH, HEIGHT),
            "--screenshot=%s" % png_path,
            html_path.resolve().as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    html_path.unlink(missing_ok=True)


def to_webp(png_path: Path, webp_path: Path) -> None:
    from PIL import Image

    im = Image.open(png_path).convert("RGB")
    if im.size != (WIDTH, HEIGHT):
        im = im.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    im.save(webp_path, "WEBP", quality=90, method=6)


def build_one(name: str, replace: bool) -> Path:
    stem = slug(name)
    media = JOBS / stem / "media"
    media.mkdir(parents=True, exist_ok=True)
    webp = media / ("%s_distribution.webp" % stem)
    if webp.is_file() and not replace:
        print("skip (exists) %s" % webp)
        return webp

    areas = lookup_areas(name)
    if not areas["native"] and not areas["introduced"]:
        raise SystemExit("no mappable areas for %s" % name)
    if areas["native"]:
        svg_text = apply(
            areas["native"],
            introduced=areas["introduced"] or None,
            legend=False,
        )
    else:
        svg_text = apply(
            areas["introduced"],
            fill=DEFAULT_INTRODUCED,
            stroke=DEFAULT_INTRODUCED_STROKE,
        )

    painted = list(areas["native"]) + [c for c in areas["introduced"] if c not in areas["native"]]
    svg_text, focus = apply_focus(svg_text, painted)
    areas["focus"] = None
    if focus:
        areas["focus"] = {"kind": focus["kind"], "name": focus["name"]}

    svg_path = media / ("%s_distribution.svg" % stem)
    json_path = media / ("%s_distribution.json" % stem)
    png_path = media / ("%s_distribution.png" % stem)
    svg_path.write_text(svg_text, encoding="utf-8")
    json_path.write_text(json.dumps(areas, indent=2, ensure_ascii=False) + "\n")
    screenshot(svg_path, png_path)
    to_webp(png_path, webp)
    png_path.unlink(missing_ok=True)
    print("wrote %s" % webp)
    if areas.get("focus"):
        print("  focus %s:%s" % (areas["focus"]["kind"], areas["focus"]["name"]))
    if areas["unmapped_native"] or areas["unmapped_introduced"]:
        print(
            "  unmapped L3 native=%s introduced=%s"
            % (areas["unmapped_native"], areas["unmapped_introduced"])
        )
    return webp


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("names", nargs="+", help='Latin names, e.g. "Arctium tomentosum"')
    p.add_argument("--replace", action="store_true")
    args = p.parse_args()
    for name in args.names:
        build_one(name.strip(), args.replace)


if __name__ == "__main__":
    main()
