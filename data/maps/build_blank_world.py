#!/usr/bin/env python3
"""Build ingest/data/maps/blank_world.svg from Wikimedia blanks.

Sources (CC0):
  BlankMap-World US and Canada Subdivisions.svg  (BlankMap-World + US/CA ADM1)
  BlankMap-World-2009.svg                        (China ADM1 in the same coords)

Result is a Robinson world map (2754×1398) with CSS classes matching
WCVP/POWO grain: ISO 3166-1 countries, US states, Canadian provinces,
Chinese provinces, and Russia split at WCVP level-2 (European / Siberia /
Far East). Metropolitan France is .fr (not Guiana/Réunion).
European Netherlands is .nl. Norway .no excludes Svalbard (.sj).
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "blank_world.svg"

UA = "What'sThatFlowerBot/1.0 (plant catalog; distribution maps)"
USCA_URL = "https://upload.wikimedia.org/wikipedia/commons/0/05/BlankMap-World_US_and_Canada_Subdivisions.svg"
Y2009_URL = "https://upload.wikimedia.org/wikipedia/commons/6/63/BlankMap-World-2009.svg"

# Same matrix the USCA file uses to drop 2009-space US states onto BlankMap-World.
CN_TRANSFORM = "matrix(0.33602544,0,0,0.33641033,85.633863,-35.418248)"

STYLE = r"""
/*
 * blank_world.svg — What's that flower distribution base
 *
 * Robinson world, 2754×1398. Fill by CSS class (ISO 3166-1 / 3166-2, lowercase):
 *
 *   .de            Germany
 *   .fr            metropolitan France only
 *   .nl            European Netherlands only
 *   .no            Norway without Svalbard
 *   .sj            Svalbard
 *   .gb            United Kingdom
 *   .ru            Russia (whole country; parent of the three WCVP L2 parts)
 *   .ru-eu         European Russia (WCVP L2 14: RUC/RUE/RUN/RUS/RUW + Kaliningrad + Crimea)
 *   .ru-sib        Siberia (WCVP L2 30: West Siberia–Yakutia, including Arctic YAK)
 *   .ru-fe         Russian Far East (WCVP L2 31: Amur, Primorye, Khabarovsk, Magadan, Kamchatka, Sakhalin, Kurils)
 *   .us-or         Oregon    (parent .us = all states)
 *   .ca-ab         Alberta   (parent .ca = all provinces + territories)
 *   .cn-xj         Xinjiang  (parent .cn = all mainland provinces + HK/MO)
 *   .nz-s          New Zealand South Island + Stewart I. (WCVP NZS; parent .nz = both)
 *
 * Example:
 *   .us-or, .ca-on, .cn-xj, .ru-sib, .de { fill: #7a9855; stroke: #5e7840; }
 *
 * Russia is not federal subjects: WCVP lists L2 14 / 30 / 31, not oblasts.
 * North Caucasus (WCVP L3 NCS, L2 33) sits in the European Russia polygon;
 * paint .ge/.am/.az for the rest of the Caucasus.
 */

.circlexx, .subxx, .unxx, .noxx { opacity: 0; }
.limitxx { opacity: 0; }

.landxx {
  fill: #ffffff;
  stroke: #b7c4c9;
  stroke-width: 0.45;
  fill-rule: evenodd;
}

.coastxx {
  stroke: #b7c4c9;
  stroke-width: 0.35;
}

.oceanxx {
  opacity: 1;
  fill: #c0dde5;
  stroke: none;
}

.antxx {
  fill: #ffffff;
  stroke: #b7c4c9;
}

/* US / Canada / China ADM1 overlays: nonzero fill (evenodd punches them out).
   No !important — colouring a state/province must be able to override this. */
.us, .ca, .cn {
  fill: #ffffff;
  stroke: #b7c4c9;
  stroke-width: 0.35;
  fill-rule: nonzero;
}

svg {
  background-color: #c0dde5;
}
"""


def fetch(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 100_000:
        return dest.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return data.decode("utf-8")


def extract_group(src: str, group_id: str) -> str:
    token = f'id="{group_id}"'
    at = src.find(token)
    if at < 0:
        raise SystemExit(f"missing id={group_id}")
    start = src.rfind("<g", 0, at)
    pos = start
    depth = 0
    while pos < len(src):
        nxt_open = src.find("<g", pos)
        nxt_close = src.find("</g>", pos)
        if nxt_close < 0:
            raise SystemExit(f"unclosed group {group_id}")
        if nxt_open >= 0 and nxt_open < nxt_close and src[nxt_open : nxt_open + 3] in (
            "<g ",
            "<g>",
            "<g\n",
            "<g\t",
        ):
            depth += 1
            pos = nxt_open + 2
            continue
        if nxt_open >= 0 and nxt_open < nxt_close:
            pos = nxt_open + 2
            continue
        depth -= 1
        pos = nxt_close + 4
        if depth == 0:
            return src[start:pos]
    raise SystemExit(f"unclosed group {group_id}")


def add_iso_classes(svg: str) -> str:
    """Add lowercase us-xx / ca-xx classes on US and Canadian ADM1."""

    def us_repl(m: re.Match) -> str:
        ident = m.group(1)
        rest = m.group(2)
        code = ident.lower()  # US-OR -> us-or
        extra = f"us {code}"
        if re.search(r'\bclass="', rest):
            tagged = re.sub(
                r'\bclass="([^"]*)"',
                lambda c: f'class="{c.group(1)} {extra}"',
                rest,
                count=1,
            )
            return f'id="{ident}"{tagged}>'
        return f'id="{ident}" class="{extra}"{rest}>'

    svg = re.sub(r'id="(US-[A-Z]{2})"([^>]*)>', us_repl, svg)

    def ca_repl(m: re.Match) -> str:
        ident = m.group(1)
        rest = m.group(2)
        code = ident.lower()
        extra = f"ca {code}"
        if re.search(r'\bclass="', rest):
            tagged = re.sub(
                r'\bclass="([^"]*)"',
                lambda c: f'class="{c.group(1)} {extra}"',
                rest,
                count=1,
            )
            return f'id="{ident}"{tagged}>'
        return f'id="{ident}" class="{extra}"{rest}>'

    svg = re.sub(r'id="(CA-[A-Z]{2})"([^>]*)>', ca_repl, svg)
    return svg


def tag_new_zealand_islands(svg: str) -> str:
    """Expose WCVP NZS / NZN as .nz-s / .nz-n without filling the other island."""
    svg = svg.replace(
        'id="New_Zealand_Stewart_Island"\n       d="',
        'id="New_Zealand_Stewart_Island"\n       class="nz-s"\n       d="',
        1,
    )
    svg = svg.replace(
        'id="New_Zealand_South_Island"\n       d="',
        'id="New_Zealand_South_Island"\n       class="nz-s"\n       d="',
        1,
    )
    svg = svg.replace(
        'id="New_Zealand_North_Island"\n       d="',
        'id="New_Zealand_North_Island"\n       class="nz-n"\n       d="',
        1,
    )
    return svg


def class_cn_chunk(chunk: str) -> str:
    """Drop the leftover BlankMap China outline; tag provinces."""

    # path2708 is the un-split China outline — would paint all of China.
    chunk = re.sub(
        r'<path\b[^>]*\bid="path2708"[^/]*/>',
        "",
        chunk,
        count=1,
        flags=re.S,
    )

    def cn_tag(m: re.Match) -> str:
        tag, attrs, ident = m.group(1), m.group(2), m.group(3)
        parts = ident.lower().split("-")
        extra = f"cn {'-'.join(parts[:2])}"
        if re.search(r'\bclass="', attrs):
            attrs = re.sub(
                r'\bclass="([^"]*)"',
                lambda c: f'class="{c.group(1)} {extra}"',
                attrs,
                count=1,
            )
        else:
            attrs = f' class="{extra}"' + attrs
        return f"<{tag}{attrs}>"

    chunk = re.sub(
        r'<([a-zA-Z]+)([^>]*\bid="(CN-[^"]+)"[^>]*)>',
        cn_tag,
        chunk,
    )
    chunk = chunk.replace('<g id="CN">', '<g id="cn-adm1" class="cn">', 1)
    chunk = chunk.replace('class="HK"', 'class="HK hk cn"', 1)
    chunk = re.sub(
        r'class="cn mo"',
        'class="cn mo"',
        chunk,
        count=1,
    )
    return chunk


def retarget_france_netherlands_norway(svg: str) -> str:
    """Make .fr / .nl / .no match WCVP country lists, not overseas bits."""

    # Svalbard: drop inherited Norway class, expose .sj
    svg = svg.replace(
        'id="xv"        class="landxx coastxx no xv"',
        'id="xv"        class="landxx coastxx sj xv"',
    )
    svg = svg.replace(
        'class="landxx coastxx no xv"',
        'class="landxx coastxx sj xv"',
    )

    # France overseas: strip .fr so colouring France does not fill Guiana etc.
    # Metro stays class "fr frx" on #frx. Do not use \byt\b — that hits ca-yt.
    def _drop_fr(match: re.Match) -> str:
        return match.group(0).replace(" fr ", " ").replace(" fr\"", '"')

    svg = re.sub(
        r'class="[^"]*\bfr\b[^"]*\b(?:gf|re|gp|mq)\b[^"]*"',
        _drop_fr,
        svg,
    )
    svg = re.sub(
        r'class="[^"]*\b(?:gf|re|gp|mq)\b[^"]*\bfr\b[^"]*"',
        _drop_fr,
        svg,
    )
    svg = svg.replace(" eu fr yt\"", ' eu yt"')
    svg = svg.replace(" eu fr yt ", " eu yt ")

    # Parent #fr still has no land class; fill .fr only hits .frx + metro paths.
    # Parent #nl contains nlx (metro) and bq (Caribbean). .nl is already on both
    # in some versions; keep .nl on #nlx only.
    svg = svg.replace(
        'id="nlx"        class="landxx coastxx eu nl nlx"',
        'id="nlx"        class="landxx coastxx eu nl nlx"',
    )
    # Caribbean Netherlands should not pick up .nl when we colour the Netherlands.
    svg = re.sub(
        r'(id="bq"[^>]*class="[^"]*)\bnl\b',
        r"\1",
        svg,
    )
    return svg


def replace_style(svg: str) -> str:
    start = svg.find("<style")
    end = svg.find("</style>")
    if start < 0 or end < 0:
        raise SystemExit("no style block")
    # keep the opening tag
    open_end = svg.find(">", start) + 1
    return svg[:open_end] + "\n" + STYLE + "\n" + svg[end:]


def hide_old_china_outline(svg: str) -> str:
    """Old #cn / #cnx is the un-split country. Hide it; provinces replace it."""
    svg = re.sub(
        r'id="cn"(?=\s+class="landxx)',
        'id="cn-outline"',
        svg,
        count=1,
    )
    svg = re.sub(
        r'(id="cn-outline"[^>]*class="[^"]*)\bcn\b',
        r"\1cn-outline",
        svg,
        count=1,
    )
    svg = re.sub(
        r'(id="cnx"[^>]*class="[^"]*)\bcn\b',
        r"\1cn-outline",
        svg,
        count=1,
    )
    # hide leftover outline via CSS — append before </style>
    svg = svg.replace(
        "</style>",
        "\n.cn-outline, #cn-outline, #cnx { display: none; }\n</style>",
        1,
    )
    return svg


def insert_china(svg: str, cn_group: str) -> str:
    wrapped = (
        f'<g id="cn" class="cn" transform="{CN_TRANSFORM}">\n'
        f"{cn_group}\n"
        f"</g>\n"
    )
    # place just before the old China outline
    mark = 'id="cn-outline"'
    at = svg.find(mark)
    if at < 0:
        mark = 'id="cn"'
        at = svg.find(mark)
    start = svg.rfind("<g", 0, at)
    return svg[:start] + wrapped + svg[start:]


def mark_us_ca_parents(svg: str) -> str:
    svg = svg.replace(
        'id="g12842"',
        'id="us" class="us"',
        1,
    )
    svg = svg.replace(
        'id="g11139"',
        'id="ca" class="ca"',
        1,
    )
    return svg


# --- Russia WCVP L2 split -------------------------------------------------
# Robinson canvas is 2754×1398. A meridian is not a vertical line, so the
# Far East cut is a stepped polygon: Amur/Primorye in the south, Magadan/
# Kamchatka/Chukotka in the north, Yakutia (WCVP Siberia) kept in .ru-sib.
#
# x≈1720 ≈ 60°E through the Perm–Yekaterinburg belt (Europe / Siberia).
# Left-edge wrap (x < 420) is Chukotka east of 180°.
RU_URALS_X = 1720
RU_FE_WRAP_X = 420
# Western edge of Far East, south → north (y down): (x, y)
RU_FE_EDGE = (
    (2135, 1398),  # ~128°E at mid-latitudes: Amur / Primorye / S Khabarovsk
    (2135, 270),   # ~50°N
    (2180, 200),   # ~58°N — step east so central Yakutia stays Siberia
    (2235, 140),   # ~67°N
    (2290, 0),     # Arctic: New Siberian Is. stay sib; Wrangel / Chukotka → fe
)

# Named crumbs that are not classified by start-x alone.
RU_SPECIAL = {
    "Russia_Kaliningrad": "ru-eu",
    "Russia_Sakhalin": "ru-fe",
    "xq": "ru-eu",  # Crimea: WCVP L3 KRY is Eastern Europe (L2 14)
}


def _poly_points(pairs: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pairs)


def _fe_edge_x(y: float) -> float:
    """Western x of the Far East clip at canvas y (interpolated)."""
    pts = RU_FE_EDGE
    if y >= pts[0][1]:
        return pts[0][0]
    if y <= pts[-1][1]:
        return pts[-1][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y1 <= y <= y0:
            if y0 == y1:
                return x1
            t = (y0 - y) / (y0 - y1)
            return x0 + t * (x1 - x0)
    return pts[-1][0]


def classify_russia(x: float, y: float) -> str:
    if x < RU_FE_WRAP_X:
        return "ru-fe"
    if x < RU_URALS_X:
        return "ru-eu"
    if x >= _fe_edge_x(y):
        return "ru-fe"
    return "ru-sib"


def _path_start(attrs: str) -> tuple[float, float] | None:
    m = re.search(r'\bd="[mM]\s+([0-9.]+),([0-9.]+)', attrs)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def _russia_clip_defs() -> str:
    urals = RU_URALS_X
    wrap = RU_FE_WRAP_X
    # 1 px overlap hides a grey seam when adjacent parts share a fill.
    eu_rect = (
        f'<rect x="{wrap}" y="0" width="{urals - wrap + 1}" height="1398"/>'
    )
    sib = [(urals - 1, 0)]
    sib.extend((x, y) for x, y in reversed(RU_FE_EDGE))
    sib.append((urals - 1, 1398))
    fe = list(RU_FE_EDGE) + [(2754, 0), (2754, 1398)]
    wrap_rect = f'<rect x="0" y="0" width="{wrap}" height="1398"/>'
    return (
        "\n"
        '  <clipPath id="clip-ru-eu" clipPathUnits="userSpaceOnUse">'
        f"{eu_rect}</clipPath>\n"
        '  <clipPath id="clip-ru-sib" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(sib)}"/></clipPath>\n'
        '  <clipPath id="clip-ru-fe" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(fe)}"/>{wrap_rect}</clipPath>\n'
    )


def split_russia(svg: str) -> str:
    """Split #ru into .ru-eu / .ru-sib / .ru-fe matching WCVP L2 14 / 30 / 31."""

    group = extract_group(svg, "ru")
    mainland = re.search(
        r'<path\s+id="path2924"[\s\S]*?/>',
        group,
    )
    if not mainland:
        raise SystemExit("Russia mainland path2924 missing")
    d_attr = re.search(r'\bd="([^"]+)"', mainland.group(0))
    if not d_attr:
        raise SystemExit("path2924 has no d")
    d = d_attr.group(1)

    copies = []
    for region, clip in (
        ("ru-eu", "clip-ru-eu"),
        ("ru-sib", "clip-ru-sib"),
        ("ru-fe", "clip-ru-fe"),
    ):
        copies.append(
            f'    <path\n'
            f'       id="{region}-mainland"\n'
            f'       class="landxx eaeu ru {region}"\n'
            f'       clip-path="url(#{clip})"\n'
            f'       d="{d}" />'
        )
    new_mainland = "\n".join(copies)

    def retag(m: re.Match) -> str:
        tag = m.group(0)
        ident_m = re.search(r'\bid="([^"]+)"', tag)
        ident = ident_m.group(1) if ident_m else ""
        if ident == "path2924":
            return new_mainland
        start = _path_start(tag)
        if ident in RU_SPECIAL:
            region = RU_SPECIAL[ident]
        elif start:
            region = classify_russia(*start)
        else:
            region = "ru-eu"
        extra = f"landxx eaeu ru {region}"
        if ident == "xq":
            extra += " xq"
        if re.search(r'\bclass="', tag):
            tag = re.sub(r'\bclass="[^"]*"', f'class="{extra}"', tag, count=1)
        elif tag.endswith("/>"):
            tag = tag[:-2] + f' class="{extra}"/>'
        elif tag.endswith(">"):
            tag = tag[:-1] + f' class="{extra}">'
        return tag

    new_group = re.sub(r"<path\b[\s\S]*?/>", retag, group)
    new_group = new_group.replace(
        'id="ru"\n     class="landxx coastxx eaeu ru"',
        'id="ru"\n     class="ru"',
        1,
    )
    svg = svg.replace(group, new_group, 1)

    clips = _russia_clip_defs()
    if re.search(r"<defs\b[^>]*/>", svg):
        svg = re.sub(r"<defs\b[^>]*/>", f"<defs id='defs3059'>{clips}</defs>", svg, count=1)
    else:
        svg = svg.replace("</defs>", clips + "</defs>", 1)
    return svg


def main() -> None:
    cache = Path("/tmp")
    usca = fetch(USCA_URL, cache / "BlankMap-World-USCA.svg")
    y2009 = fetch(Y2009_URL, cache / "BlankMap-World-2009.svg")
    cn = class_cn_chunk(extract_group(y2009, "CN"))

    svg = usca
    svg = replace_style(svg)
    svg = add_iso_classes(svg)
    svg = retarget_france_netherlands_norway(svg)
    svg = tag_new_zealand_islands(svg)
    svg = hide_old_china_outline(svg)
    svg = insert_china(svg, cn)
    svg = mark_us_ca_parents(svg)
    svg = split_russia(svg)
    # Overlay paths ship with inline grey; make the default white so they
    # match .landxx. fill_blank_world.py then overwrites selected fills.
    svg = svg.replace("fill:#c0c0c0", "fill:#ffffff")

    # Title
    svg = svg.replace(
        "<title",
        "<title id='title-blank-world'>What's that flower — blank world (countries + US/CA/CN + RU WCVP L2)</title>\n  <title",
        1,
    )

    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
