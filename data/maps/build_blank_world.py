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

import math
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
 *   .ru-sak        Sakhalin (WCVP SAK; parent .ru-fe = all of L2 31)
 *   .ru-mag        Magadan + Chukotka (WCVP MAG; parent .ru-fe = all of L2 31)
 *   .us-or         Oregon    (parent .us = all states)
 *   .ca-ab         Alberta   (parent .ca = all provinces + territories)
 *   .cn-xj         Xinjiang  (parent .cn = all mainland provinces + HK/MO)
 *   .nz-s          New Zealand South Island + Stewart I. (WCVP NZS; parent .nz = both)
 *   .au-tas        Tasmania (WCVP TAS; parent .au = mainland + Tasmania)
 *   .au-maq        Macquarie Island (WCVP MAQ; parent .au = mainland Australia)
 *   .au-qld        Queensland (WCVP QLD; parent .au = mainland + Tasmania)
 *   .au-nsw        New South Wales (WCVP NSW)
 *   .au-nt         Northern Territory (WCVP NTA)
 *   .au-sa         South Australia (WCVP SOA)
 *   .au-wa         Western Australia (WCVP WAU)
 *   .id-jw         Java (WCVP JAW; parent .id = all of Indonesia)
 *   .ar-s          Argentina South (WCVP AGS: Neuquén–Tierra del Fuego; parent .ar = whole country)
 *   .br-s          Brazil South (WCVP BZS: Paraná, Santa Catarina, Rio Grande do Sul; parent .br = whole country)
 *   .br-c          Brazil West-Central (WCVP BZC: Mato Grosso, Mato Grosso do Sul, Goiás, DF)
 *   .br-se         Brazil Southeast (WCVP BZL: Minas Gerais, Espírito Santo, Rio, São Paulo)
 *   .cl-eas        Easter Island (WCVP EAS; parent .cl = mainland Chile)
 *   .es            mainland Spain (WCVP SPA; not Balearics / Canaries)
 *   .es-bal        Balearic Islands (WCVP BAL)
 *   .es-cny        Canary Islands (WCVP CNY)
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


def tag_tasmania(svg: str) -> str:
    """Expose WCVP TAS as .au-tas without filling mainland Australia."""
    svg = svg.replace(
        'id="Australia_Tasmania"\n       d="',
        'id="Australia_Tasmania"\n       class="au-tas"\n       d="',
        1,
    )
    return svg


def tag_macquarie(svg: str) -> str:
    """Expose WCVP MAQ as .au-maq without filling mainland Australia."""
    svg = svg.replace(
        'id="Australia_Macquarie_Island"\n       d="',
        'id="Australia_Macquarie_Island"\n       class="au-maq"\n       d="',
        1,
    )
    # The Wikimedia crumb is ~2 px; a small circle is the same grain as
    # Easter Island so MAQ-only introduced ranges stay visible.
    crumb = (
        'id="Australia_Macquarie_Island"\n'
        '       class="au-maq"\n'
        '       d="m 2332,1162 c -0.96,0.47 -1.28,2.76 -0.64,2.42 0.62,-0.33 0.43,-1.84 0.64,-2.42" />'
    )
    marker = crumb + (
        '\n    <circle\n'
        '       id="au-maq-"\n'
        '       class="landxx coastxx au-maq"\n'
        '       r="4"\n'
        '       cy="1163"\n'
        '       cx="2332" />'
    )
    if 'id="au-maq-"' not in svg:
        svg = svg.replace(crumb, marker, 1)
    return svg


def tag_java(svg: str) -> str:
    """Expose WCVP JAW as .id-jw without filling the rest of Indonesia."""
    svg = svg.replace(
        'id="Indonesia_Java"\n       d="',
        'id="Indonesia_Java"\n       class="id-jw"\n       d="',
        1,
    )
    return svg


def tag_easter_island(svg: str) -> str:
    """Expose WCVP EAS as .cl-eas without filling mainland Chile."""
    svg = svg.replace(
        'id="Chile_Easter_Island"\n       r="0.5"',
        'id="Chile_Easter_Island"\n       class="landxx coastxx cl-eas"\n       r="4.5"',
        1,
    )
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

    # Spain: parent #es must not carry .es, or Balearics/Canaries inherit
    # mainland fill (same pattern as #fr / #frx).
    svg = svg.replace(
        'id="es"\n     class="landxx coastxx eu es"',
        'id="es"\n     class="landxx coastxx eu"',
    )
    svg = svg.replace(
        'id="es" class="landxx coastxx eu es"',
        'id="es" class="landxx coastxx eu"',
    )
    for name in ("Spain_Ibiza", "Spain_Formentera", "Spain_Majorca", "Spain_Menorca"):
        svg = re.sub(
            rf'(id="{name}"\s*)(d=)',
            rf'\1class="landxx es-bal"\n       \2',
            svg,
            count=1,
        )
    for name in (
        "path5984",
        "path5986",
        "path5988",
        "path5990",
        "path5992",
        "path5994",
        "path5996",
    ):
        svg = re.sub(
            rf'(id="{name}"\s*)(d=)',
            rf'\1class="landxx es-cny"\n       \2',
            svg,
            count=1,
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
    "Russia_Sakhalin": "ru-sak",  # overlay only; ru-fe must not paint SAK
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


# --- Magadan + Chukotka (WCVP MAG) ---------------------------------------
# Parent .ru-fe stays all of L2 31. MAG is Magadan Oblast + Chukotka; Kamchatka
# / Koryak (KAM), Khabarovsk, Amur, Primorye, Kurils stay .ru-fe only.
# South edge ~59°N on the Okhotsk coast (y≈193). Wrap x<420 is Chukotka
# east of 180°. Same grain as .ru-sak: MAG-only must not fill all of L2 31.
MAG_OKHOTSK_Y = 193.0  # ~59°N Magadan / Khabarovsk
MAG_WRAP_X = RU_FE_WRAP_X
# Clockwise on the main canvas (right of 180°): FE west edge down to 59°N,
# east along Okhotsk, then NE around Penzhina / Koryak so Kamchatka stays out.
MAG_POLY = (
    (2290.0, 0.0),     # Arctic FE / sib corner
    (2235.0, 140.0),   # FE edge ~67°N
    (2186.4, 193.0),   # FE edge ~59°N
    (2260.0, 193.0),   # Okhotsk west of Kamchatka
    (2300.0, 175.0),   # toward Penzhina
    (2360.0, 165.0),   # Penzhina Bay MAG / KAM
    (2480.0, 150.0),   # Chukotka south of Koryak
    (2620.0, 138.0),   # eastern Chukotka
    (2754.0, 125.0),   # 180°E
    (2754.0, 0.0),
)


def _point_in_poly(x: float, y: float, pts: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xint = (x1 - x0) * (y - y0) / (y1 - y0 + 0.0) + x0
            if x < xint:
                inside = not inside
    return inside


def in_magadan(x: float, y: float) -> bool:
    if x < MAG_WRAP_X:
        return True
    return _point_in_poly(x, y, MAG_POLY)


def _magadan_clip_def() -> str:
    wrap = f'<rect x="0" y="0" width="{MAG_WRAP_X}" height="1398"/>'
    return (
        "\n"
        '  <clipPath id="clip-ru-mag" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(list(MAG_POLY))}"/>{wrap}</clipPath>\n'
    )


def split_magadan(svg: str) -> str:
    """Expose WCVP MAG as .ru-mag without filling the rest of Russian Far East."""
    if 'id="ru-mag-mainland"' in svg:
        svg = re.sub(
            r'\n    <path\n       id="ru-mag-mainland"[\s\S]*?/>',
            "",
            svg,
            count=1,
        )
        svg = re.sub(
            r'\n  <clipPath id="clip-ru-mag"[^>]*>.*?</clipPath>',
            "",
            svg,
            count=1,
        )
        # Drop a previous ru-mag token from crumb classes, then re-apply.
        svg = re.sub(r'(class="[^"]*) ru-mag\b', r"\1", svg)

    fe = re.search(
        r'<path\n       id="ru-fe-mainland"\n       class="[^"]*"\n       clip-path="[^"]*"\n       d="([^"]+)" />',
        svg,
    )
    if not fe:
        raise SystemExit("ru-fe-mainland missing; split_russia first")
    overlay = (
        f'    <path\n'
        f'       id="ru-mag-mainland"\n'
        f'       class="landxx eaeu ru ru-fe ru-mag"\n'
        f'       clip-path="url(#clip-ru-mag)"\n'
        f'       d="{fe.group(1)}" />'
    )
    svg = svg.replace(fe.group(0), fe.group(0) + "\n" + overlay, 1)

    def tag_crumb(m: re.Match) -> str:
        tag = m.group(0)
        if re.search(r'\bid="ru-(?:eu|sib|fe|mag)-mainland"', tag):
            return tag
        if "ru-fe" not in (re.search(r'\bclass="([^"]*)"', tag).group(1) if re.search(r'\bclass="([^"]*)"', tag) else ""):
            return tag
        start = _path_start(tag)
        if not start or not in_magadan(*start):
            return tag
        return re.sub(
            r'\bclass="([^"]*)"',
            lambda cm: f'class="{cm.group(1)} ru-mag"' if "ru-mag" not in cm.group(1).split() else cm.group(0),
            tag,
            count=1,
        )

    group = extract_group(svg, "ru")
    new_group = re.sub(r"<path\b[\s\S]*?/>", tag_crumb, group)
    svg = svg.replace(group, new_group, 1)

    clip = _magadan_clip_def()
    if "</defs>" in svg:
        svg = svg.replace("</defs>", clip + "</defs>", 1)
    else:
        svg = re.sub(
            r"<defs\b[^>]*/>",
            f"<defs id='defs3059'>{clip}</defs>",
            svg,
            count=1,
        )
    return svg


# --- Argentina South (WCVP AGS) ------------------------------------------
# Parent #ar stays the whole country (AGE / AGW). AGS is Neuquén, Río Negro,
# Chubut, Santa Cruz, Tierra del Fuego. Northern edge ≈ Río Colorado:
# Andes / Mendoza–Neuquén ~36.2°S, Atlantic / Buenos Aires–Río Negro ~41°S.
# Canvas y from the Argentina mainland path (north y≈887 ~22°S, south y≈1149
# ~52°S Strait of Magellan; Tierra del Fuego is a separate path).
AR_S_WEST = (796.0, 1010.0)
AR_S_EAST = (868.0, 1048.0)


def _argentina_south_clip_def() -> str:
    wx, wy = AR_S_WEST
    ex, ey = AR_S_EAST
    # Half-plane south of the Colorado line; 1 px extra so the seam is covered.
    pts = [
        (0, 1398),
        (0, wy),
        (wx, wy),
        (ex, ey),
        (2754, ey),
        (2754, 1398),
    ]
    return (
        "\n"
        '  <clipPath id="clip-ar-s" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(pts)}"/></clipPath>\n'
    )


def split_argentina_south(svg: str) -> str:
    """Expose WCVP AGS as .ar-s without filling the rest of Argentina."""
    if 'id="ar-s"' in svg:
        # Rebuild: drop a previous overlay + clip before inserting again.
        svg = re.sub(
            r'\n  <g\n     id="ar-s"[\s\S]*?</g>(?=\n  <g\n     id=")',
            "",
            svg,
            count=1,
        )
        svg = re.sub(
            r'\n  <clipPath id="clip-ar-s"[^>]*>.*?</clipPath>',
            "",
            svg,
            count=1,
        )

    group = extract_group(svg, "ar")
    copies = []
    for m in re.finditer(r"<path\b[\s\S]*?/>", group):
        tag = m.group(0)
        ident_m = re.search(r'\bid="([^"]+)"', tag)
        ident = ident_m.group(1) if ident_m else "crumb"
        d_m = re.search(r'\bd="([^"]+)"', tag)
        if not d_m:
            continue
        copies.append(
            f'    <path\n'
            f'       id="ar-s-{ident}"\n'
            f'       class="landxx ar-s"\n'
            f'       d="{d_m.group(1)}" />'
        )
    overlay = (
        '  <g\n'
        '     id="ar-s"\n'
        '     class="ar-s"\n'
        '     clip-path="url(#clip-ar-s)">\n'
        + "\n".join(copies)
        + "\n  </g>\n"
    )
    svg = svg.replace(group, group.rstrip() + "\n" + overlay, 1)
    clip = _argentina_south_clip_def()
    if "</defs>" in svg:
        svg = svg.replace("</defs>", clip + "</defs>", 1)
    else:
        svg = re.sub(
            r"<defs\b[^>]*/>",
            f"<defs id='defs3059'>{clip}</defs>",
            svg,
            count=1,
        )
    return svg


# --- Queensland (WCVP QLD) -----------------------------------------------
# Parent .au stays mainland + Tasmania. QLD-only must not fill NSW/VIC/WA/NT/SA.
# Wikimedia BlankMap-World Robinson, central meridian 11°E, 2754×1398.
_ROBINSON = (
    (0, 1.0000, 0.0000),
    (5, 0.9986, 0.0620),
    (10, 0.9954, 0.1240),
    (15, 0.9900, 0.1860),
    (20, 0.9822, 0.2480),
    (25, 0.9730, 0.3100),
    (30, 0.9600, 0.3720),
    (35, 0.9427, 0.4340),
    (40, 0.9216, 0.4958),
    (45, 0.8962, 0.5571),
    (50, 0.8679, 0.6176),
    (55, 0.8350, 0.6769),
    (60, 0.7986, 0.7346),
    (65, 0.7597, 0.7903),
    (70, 0.7186, 0.8435),
    (75, 0.6732, 0.8936),
    (80, 0.6213, 0.9394),
    (85, 0.5722, 0.9761),
    (90, 0.5322, 1.0000),
)
_ROBINSON_LON0 = 11.0
_ROBINSON_X0 = 1377.0
_ROBINSON_Y0 = 699.0
_ROBINSON_R = 1398.0 / (2.0 * 1.3523)


def _robinson_interp(lat: float) -> tuple[float, float]:
    a = abs(lat)
    if a >= 90:
        return _ROBINSON[-1][1], _ROBINSON[-1][2]
    for (lat0, x0, y0), (lat1, x1, y1) in zip(_ROBINSON, _ROBINSON[1:]):
        if lat0 <= a <= lat1:
            t = (a - lat0) / (lat1 - lat0)
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
    return _ROBINSON[-1][1], _ROBINSON[-1][2]


def robinson_xy(lon: float, lat: float) -> tuple[float, float]:
    """SVG user-space on blank_world.svg (Robinson, 11°E)."""
    xf, yf = _robinson_interp(lat)
    lam = math.radians(lon - _ROBINSON_LON0)
    x = _ROBINSON_X0 + 0.8487 * _ROBINSON_R * xf * lam
    y = _ROBINSON_Y0 - 1.3523 * _ROBINSON_R * yf if lat >= 0 else _ROBINSON_Y0 + 1.3523 * _ROBINSON_R * yf
    return x, y


# WCVP QLD: 138°E (NT/SA), 26°S then 141°E to 29°S (NSW), Coral Sea, Torres Strait.
QLD_GEO = (
    (138.0, -9.0),
    (138.0, -12.0),
    (138.0, -16.0),
    (138.0, -20.0),
    (138.0, -24.0),
    (138.0, -26.0),
    (141.0, -26.0),
    (141.0, -29.2),
    (146.0, -29.2),
    (151.0, -29.2),
    (155.6, -29.2),
    (155.6, -24.0),
    (155.6, -18.0),
    (155.6, -12.0),
    (155.6, -9.0),
    (150.0, -9.0),
    (144.0, -9.0),
)


def _queensland_clip_def() -> str:
    pts = [robinson_xy(lon, lat) for lon, lat in QLD_GEO]
    return (
        "\n"
        '  <clipPath id="clip-au-qld" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(pts)}"/></clipPath>\n'
    )


def split_queensland(svg: str) -> str:
    """Expose WCVP QLD as .au-qld without filling the rest of Australia."""
    if 'id="au-qld"' in svg:
        svg = re.sub(
            r'\n  <g\n     id="au-qld"[\s\S]*?</g>\n',
            "",
            svg,
            count=1,
        )
        svg = re.sub(
            r'\n  <clipPath id="clip-au-qld"[^>]*>.*?</clipPath>',
            "",
            svg,
            count=1,
        )

    group = extract_group(svg, "au")
    skip = {"Australia_Tasmania", "Australia_Macquarie_Island", "au-maq-"}
    copies = []
    for m in re.finditer(r"<(?:path|circle)\b[\s\S]*?/>", group):
        tag = m.group(0)
        ident_m = re.search(r'\bid="([^"]+)"', tag)
        ident = ident_m.group(1) if ident_m else "crumb"
        if ident in skip:
            continue
        d_m = re.search(r'\bd="([^"]+)"', tag)
        if d_m:
            copies.append(
                f'    <path\n'
                f'       id="au-qld-{ident}"\n'
                f'       class="landxx au-qld"\n'
                f'       d="{d_m.group(1)}" />'
            )
            continue
        cx = re.search(r'\bcx="([^"]+)"', tag)
        cy = re.search(r'\bcy="([^"]+)"', tag)
        rr = re.search(r'\br="([^"]+)"', tag)
        if cx and cy and rr:
            copies.append(
                f'    <circle\n'
                f'       id="au-qld-{ident}"\n'
                f'       class="landxx au-qld"\n'
                f'       r="{rr.group(1)}"\n'
                f'       cy="{cy.group(1)}"\n'
                f'       cx="{cx.group(1)}" />'
            )
    overlay = (
        '  <g\n'
        '     id="au-qld"\n'
        '     class="au-qld"\n'
        '     clip-path="url(#clip-au-qld)">\n'
        + "\n".join(copies)
        + "\n  </g>\n"
    )
    svg = svg.replace(group, group.rstrip() + "\n" + overlay, 1)
    clip = _queensland_clip_def()
    if "</defs>" in svg:
        svg = svg.replace("</defs>", clip + "</defs>", 1)
    else:
        svg = re.sub(
            r"<defs\b[^>]*/>",
            f"<defs id='defs3059'>{clip}</defs>",
            svg,
            count=1,
        )
    return svg


def _clip_def(clip_id: str, geo: tuple[tuple[float, float], ...]) -> str:
    pts = [robinson_xy(lon, lat) for lon, lat in geo]
    return (
        "\n"
        f'  <clipPath id="{clip_id}" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(pts)}"/></clipPath>\n'
    )


def split_clipped_overlay(
    svg: str,
    *,
    parent_id: str,
    overlay_id: str,
    clip_id: str,
    geo: tuple[tuple[float, float], ...],
    skip_ids: set[str] | None = None,
) -> str:
    """Copy a country group, clip to `geo`, expose as overlay_id."""
    skip_ids = skip_ids or set()
    if re.search(rf'\bid="{re.escape(overlay_id)}"', svg):
        old = extract_group(svg, overlay_id)
        svg = svg.replace(old, "", 1)
        svg = re.sub(
            rf'\n  <clipPath id="{re.escape(clip_id)}"[^>]*>.*?</clipPath>',
            "",
            svg,
            count=1,
        )

    group = extract_group(svg, parent_id)
    copies = []
    for m in re.finditer(r"<(?:path|circle)\b[\s\S]*?/>", group):
        tag = m.group(0)
        ident_m = re.search(r'\bid="([^"]+)"', tag)
        ident = ident_m.group(1) if ident_m else "crumb"
        if ident in skip_ids:
            continue
        d_m = re.search(r'\bd="([^"]+)"', tag)
        if d_m:
            copies.append(
                f'    <path\n'
                f'       id="{overlay_id}-{ident}"\n'
                f'       class="landxx {overlay_id}"\n'
                f'       d="{d_m.group(1)}" />'
            )
            continue
        cx = re.search(r'\bcx="([^"]+)"', tag)
        cy = re.search(r'\bcy="([^"]+)"', tag)
        rr = re.search(r'\br="([^"]+)"', tag)
        if cx and cy and rr:
            copies.append(
                f'    <circle\n'
                f'       id="{overlay_id}-{ident}"\n'
                f'       class="landxx {overlay_id}"\n'
                f'       r="{rr.group(1)}"\n'
                f'       cy="{cy.group(1)}"\n'
                f'       cx="{cx.group(1)}" />'
            )
    overlay = (
        f'  <g\n'
        f'     id="{overlay_id}"\n'
        f'     class="{overlay_id}"\n'
        f'     clip-path="url(#{clip_id})">\n'
        + "\n".join(copies)
        + "\n  </g>\n"
    )
    svg = svg.replace(group, group.rstrip() + "\n" + overlay, 1)
    clip = _clip_def(clip_id, geo)
    if "</defs>" in svg:
        svg = svg.replace("</defs>", clip + "</defs>", 1)
    else:
        svg = re.sub(
            r"<defs\b[^>]*/>",
            f"<defs id='defs3059'>{clip}</defs>",
            svg,
            count=1,
        )
    return svg


# WCVP NSW: 141°E (SA), QLD border ~29°S, Murray/Cape Howe so Victoria stays out.
# Overlap neighbours by ~0.6° so clip edges do not flash white.
NSW_GEO = (
    (140.4, -28.6),
    (154.2, -28.6),
    (154.2, -37.7),
    (150.0, -37.7),
    (147.0, -36.0),
    (144.5, -34.2),
    (141.0, -34.0),
    (140.4, -33.9),
)
# WCVP NTA: 129°E (WA) – 138°E (QLD), 26°S (SA).
NTA_GEO = (
    (128.3, -10.5),
    (138.7, -10.5),
    (138.7, -26.5),
    (128.3, -26.5),
)
# WCVP SOA: 129°E (WA) – 141°E (NSW/VIC), 26°S (NT).
# East of 141°E only north of the Murray so western Victoria stays unpainted.
SOA_GEO = (
    (128.3, -25.5),
    (141.5, -25.5),
    (141.5, -33.8),
    (141.0, -34.0),
    (141.0, -38.6),
    (128.3, -38.6),
)
# WCVP WAU: west of 129°E.
WAU_GEO = (
    (112.4, -13.5),
    (129.7, -13.5),
    (129.7, -35.6),
    (112.4, -35.6),
)
_AU_SKIP = {"Australia_Tasmania", "Australia_Macquarie_Island", "au-maq-"}


def split_australia_states(svg: str) -> str:
    """NSW / NT / SA / WA clips so a missing VIC does not fill the mainland."""
    svg = split_clipped_overlay(
        svg, parent_id="au", overlay_id="au-nsw", clip_id="clip-au-nsw",
        geo=NSW_GEO, skip_ids=_AU_SKIP,
    )
    svg = split_clipped_overlay(
        svg, parent_id="au", overlay_id="au-nt", clip_id="clip-au-nt",
        geo=NTA_GEO, skip_ids=_AU_SKIP,
    )
    svg = split_clipped_overlay(
        svg, parent_id="au", overlay_id="au-sa", clip_id="clip-au-sa",
        geo=SOA_GEO, skip_ids=_AU_SKIP,
    )
    svg = split_clipped_overlay(
        svg, parent_id="au", overlay_id="au-wa", clip_id="clip-au-wa",
        geo=WAU_GEO, skip_ids=_AU_SKIP,
    )
    return svg


def tag_norfolk(svg: str) -> str:
    """Visible Norfolk Island marker (WCVP NFK); do not fill mainland Australia."""
    if 'id="nf-marker"' in svg:
        return svg
    crumb = (
        'id="nf_"\n'
        '         class="subxx au nf"\n'
        '         r="4"\n'
        '         cy="933"\n'
        '         cx="2549" />'
    )
    marker = crumb + (
        '\n      <circle\n'
        '         id="nf-marker"\n'
        '         class="landxx coastxx nf"\n'
        '         r="4"\n'
        '         cy="933"\n'
        '         cx="2549" />'
    )
    if crumb in svg:
        svg = svg.replace(crumb, marker, 1)
    return svg


# --- Brazil South (WCVP BZS) ---------------------------------------------
# Parent .br stays the whole country (BZC / BZE / BZL / BZN). BZS is Paraná,
# Santa Catarina, Rio Grande do Sul. North edge: Paranapanema (~22.5°S)
# then SE to the PR–SP coastal border (~25.3°S, 48°W) so São Paulo city
# and Rio stay out.
BZS_GEO = (
    (-58.5, -22.52),
    (-47.9, -22.52),
    (-47.9, -25.30),
    (-46.5, -25.30),
    (-46.5, -34.50),
    (-58.5, -34.50),
)


def _brazil_south_clip_def() -> str:
    pts = [robinson_xy(lon, lat) for lon, lat in BZS_GEO]
    return (
        "\n"
        '  <clipPath id="clip-br-s" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{_poly_points(pts)}"/></clipPath>\n'
    )


def split_brazil_south(svg: str) -> str:
    """Expose WCVP BZS as .br-s without filling the rest of Brazil."""
    if 'id="br-s"' in svg:
        svg = re.sub(
            r'\n  <g\n     id="br-s"[\s\S]*?</g>(?=\n  <g\n     id=")',
            "",
            svg,
            count=1,
        )
        svg = re.sub(
            r'\n  <clipPath id="clip-br-s"[^>]*>.*?</clipPath>',
            "",
            svg,
            count=1,
        )

    group = extract_group(svg, "br")
    copies = []
    for m in re.finditer(r"<path\b[\s\S]*?/>", group):
        tag = m.group(0)
        ident_m = re.search(r'\bid="([^"]+)"', tag)
        ident = ident_m.group(1) if ident_m else "crumb"
        d_m = re.search(r'\bd="([^"]+)"', tag)
        if not d_m:
            continue
        copies.append(
            f'    <path\n'
            f'       id="br-s-{ident}"\n'
            f'       class="landxx br-s"\n'
            f'       d="{d_m.group(1)}" />'
        )
    overlay = (
        '  <g\n'
        '     id="br-s"\n'
        '     class="br-s"\n'
        '     clip-path="url(#clip-br-s)">\n'
        + "\n".join(copies)
        + "\n  </g>\n"
    )
    svg = svg.replace(group, group.rstrip() + "\n" + overlay, 1)
    clip = _brazil_south_clip_def()
    if "</defs>" in svg:
        svg = svg.replace("</defs>", clip + "</defs>", 1)
    else:
        svg = re.sub(
            r"<defs\b[^>]*/>",
            f"<defs id='defs3059'>{clip}</defs>",
            svg,
            count=1,
        )
    return svg


# WCVP BZC: Mato Grosso, Mato Grosso do Sul, Goiás, DF. Keep Pará/Tocantins
# (BZN) and Bahia (BZE) out.
BZC_GEO = (
    (-61.6, -7.3),
    (-50.3, -7.3),
    (-50.3, -12.5),
    (-45.9, -12.5),
    (-45.9, -19.5),
    (-50.9, -19.5),
    (-50.9, -24.1),
    (-58.2, -24.1),
    (-58.2, -18.0),
    (-61.6, -18.0),
)
# WCVP BZL: Minas Gerais, Espírito Santo, Rio de Janeiro, São Paulo.
# North-east cut keeps Bahia (BZE) out; south edge is BZS (Paranapanema).
BZL_GEO = (
    (-51.1, -14.2),
    (-46.2, -14.2),
    (-46.2, -16.0),
    (-40.5, -16.0),
    (-40.5, -18.0),
    (-39.5, -18.0),
    (-39.5, -23.4),
    (-44.2, -23.4),
    (-44.2, -25.3),
    (-53.1, -25.3),
    (-53.1, -19.8),
    (-51.1, -19.8),
)


def split_brazil_west_central(svg: str) -> str:
    """Expose WCVP BZC as .br-c without filling Amazonia / Nordeste."""
    return split_clipped_overlay(
        svg, parent_id="br", overlay_id="br-c", clip_id="clip-br-c", geo=BZC_GEO,
    )


def split_brazil_southeast(svg: str) -> str:
    """Expose WCVP BZL as .br-se without filling Amazonia / Nordeste."""
    return split_clipped_overlay(
        svg, parent_id="br", overlay_id="br-se", clip_id="clip-br-se", geo=BZL_GEO,
    )


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
    svg = tag_tasmania(svg)
    svg = tag_macquarie(svg)
    svg = tag_java(svg)
    svg = tag_easter_island(svg)
    svg = split_argentina_south(svg)
    svg = split_brazil_south(svg)
    svg = split_brazil_west_central(svg)
    svg = split_brazil_southeast(svg)
    svg = split_queensland(svg)
    svg = split_australia_states(svg)
    svg = tag_norfolk(svg)
    svg = hide_old_china_outline(svg)
    svg = insert_china(svg, cn)
    svg = mark_us_ca_parents(svg)
    svg = split_russia(svg)
    svg = split_magadan(svg)
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
