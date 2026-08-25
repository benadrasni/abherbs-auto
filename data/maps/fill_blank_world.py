#!/usr/bin/env python3
"""Colour ingest/data/maps/blank_world.svg by ISO / WCVP-style codes.

    python3 fill_blank_world.py \\
        --codes de,fr,ru-sib,cn-xj \\
        --introduced gb,ru-fe,us-or,ca-on \\
        --out /tmp/plant.svg

Codes are CSS classes on the base map: country (de), US state (us-or),
Canadian province (ca-on), Chinese province (cn-xj), Russia WCVP L2
(ru-eu / ru-sib / ru-fe; or ru for the whole country; ru-sak / ru-mag
for Sakhalin / Magadan; au-tas / au-maq / au-qld for Tasmania / Macquarie /
Queensland / NSW / NT / SA / WA; ar-s / br-s / br-c / br-se for Argentina South / Brazil South / West-Central / Southeast). Native areas
use the botanical olive; --introduced paints a second colour (terracotta).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "blank_world.svg"

DEFAULT_FILL = "#7a9855"
DEFAULT_STROKE = "#5e7840"
DEFAULT_INTRODUCED = "#c17a3a"
DEFAULT_INTRODUCED_STROKE = "#8f5528"
DEFAULT_OCEAN = "#c0dde5"
DEFAULT_LAND = "#ffffff"


def parse_codes(raw: str) -> list[str]:
    codes = []
    for part in re.split(r"[\s,]+", raw.strip()):
        if not part:
            continue
        codes.append(part.strip().lower().replace("_", "-"))
    return codes


def _paint_style(style: str, fill: str, stroke: str) -> str:
    style = re.sub(r"fill\s*:\s*[^;]+;?", "", style)
    style = re.sub(r"stroke\s*:\s*[^;]+;?", "", style)
    extra = f"fill:{fill};stroke:{stroke};"
    style = style.strip().strip(";")
    return f"{style};{extra}" if style else extra


def _paint_tag(tag: str, fill: str, stroke: str) -> str:
    painted = f"fill:{fill};stroke:{stroke}"
    if re.search(r'\bstyle="', tag):
        return re.sub(
            r'\bstyle="([^"]*)"',
            lambda m: f'style="{_paint_style(m.group(1), fill, stroke)}"',
            tag,
            count=1,
        )
    if tag.endswith("/>"):
        return tag[:-2] + f' style="{painted}"/>'
    if tag.endswith(">"):
        return tag[:-1] + f' style="{painted}">'
    return tag


def _paint_codes(svg: str, codes: list[str], fill: str, stroke: str) -> tuple[str, int]:
    painted = 0
    wanted = set(codes)

    def paint_if_class(m: re.Match) -> str:
        nonlocal painted
        tokens = m.group(1).split()
        if wanted.isdisjoint(tokens):
            return m.group(0)
        painted += 1
        return _paint_tag(m.group(0), fill, stroke)

    def paint_if_id(m: re.Match) -> str:
        nonlocal painted
        painted += 1
        return _paint_tag(m.group(0), fill, stroke)

    svg = re.sub(r'<[^>]*\bclass="([^"]*)"[^>]*>', paint_if_class, svg)
    for code in codes:
        # Exact Wikimedia ids only (US-OR, CN-XJ). Do not substring-match
        # us-az when the code is az (Azerbaijan).
        svg = re.sub(
            rf'<[^>]*\bid="{re.escape(code.upper())}"[^>]*>',
            paint_if_id,
            svg,
        )
    return svg, painted


def _css_block(codes: list[str], fill: str, stroke: str) -> str:
    sels = []
    for c in codes:
        sels.append(f".{c}")
        sels.append(f"#{c.upper()}")
    return f"""
{', '.join(sels)} {{
  fill: {fill};
  stroke: {stroke};
}}
"""


def _legend(native: str, introduced: str) -> str:
    return f"""
  <g id="legend" font-family="Helvetica, Arial, sans-serif" font-size="26" fill="#3d4a38">
    <rect x="72" y="1238" width="26" height="18" rx="2" fill="{native}" stroke="#5e7840" stroke-width="0.8"/>
    <text x="108" y="1254">Native</text>
    <rect x="72" y="1276" width="26" height="18" rx="2" fill="{introduced}" stroke="#8f5528" stroke-width="0.8"/>
    <text x="108" y="1292">Introduced</text>
  </g>
"""


def apply(
    codes: list[str],
    *,
    fill: str = DEFAULT_FILL,
    stroke: str = DEFAULT_STROKE,
    ocean: str = DEFAULT_OCEAN,
    land: str = DEFAULT_LAND,
    base: Path = BASE,
    introduced: list[str] | None = None,
    introduced_fill: str = DEFAULT_INTRODUCED,
    introduced_stroke: str = DEFAULT_INTRODUCED_STROKE,
    legend: bool = False,
) -> str:
    svg = base.read_text(encoding="utf-8")
    extra = f"""
.oceanxx {{ fill: {ocean} !important; }}
.landxx {{ fill: {land}; }}
"""
    svg, n_native = _paint_codes(svg, codes, fill, stroke)
    extra += _css_block(codes, fill, stroke)
    n_intro = 0
    if introduced:
        svg, n_intro = _paint_codes(svg, introduced, introduced_fill, introduced_stroke)
        extra += _css_block(introduced, introduced_fill, introduced_stroke)
    if "</style>" not in svg:
        raise SystemExit("base map has no </style>")
    svg = svg.replace("</style>", extra + "\n</style>", 1)
    if legend and introduced:
        mark = "</svg>"
        at = svg.rfind(mark)
        if at < 0:
            raise SystemExit("base map has no </svg>")
        svg = svg[:at] + _legend(fill, introduced_fill) + svg[at:]
    print(f"painted {n_native} native tags, {n_intro} introduced tags")
    return svg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--codes", required=True, help="native class names (comma/space)")
    p.add_argument("--introduced", default="", help="introduced class names")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--fill", default=DEFAULT_FILL)
    p.add_argument("--stroke", default=DEFAULT_STROKE)
    p.add_argument("--introduced-fill", default=DEFAULT_INTRODUCED)
    p.add_argument("--introduced-stroke", default=DEFAULT_INTRODUCED_STROKE)
    p.add_argument("--ocean", default=DEFAULT_OCEAN)
    p.add_argument("--land", default=DEFAULT_LAND)
    p.add_argument("--base", type=Path, default=BASE)
    p.add_argument("--legend", action="store_true", help="draw Native / Introduced key")
    args = p.parse_args()
    codes = parse_codes(args.codes)
    intro = parse_codes(args.introduced)
    if not codes:
        raise SystemExit("no codes")
    svg = apply(
        codes,
        fill=args.fill,
        stroke=args.stroke,
        ocean=args.ocean,
        land=args.land,
        base=args.base,
        introduced=intro or None,
        introduced_fill=args.introduced_fill,
        introduced_stroke=args.introduced_stroke,
        legend=args.legend,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(f"wrote {args.out} ({len(codes)} native, {len(intro)} introduced)")


if __name__ == "__main__":
    main()
