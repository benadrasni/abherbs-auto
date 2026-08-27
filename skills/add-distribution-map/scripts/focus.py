"""Crop the Robinson world map when a range sits on one continent or island.

The blank canvas is 2754×1398. Continent boxes are the landmass on that
canvas (not a tight crop around the painted countries). Island boxes come
from the polygon itself, then padded and centered.
"""

from __future__ import annotations

CANVAS_W, CANVAS_H = 2754.0, 1398.0

# Content boxes on the 2754×1398 Robinson canvas (not including the
# Hawaii inset, which sits below y=1398).
CONTINENT_BOX: dict[str, tuple[float, float, float, float]] = {
    # minx, miny, maxx, maxy
    "europe": (1190, 95, 1745, 505),
    "africa": (1085, 360, 1760, 1035),
    "asia": (1485, 20, 2545, 820),
    "north_america": (20, 5, 1270, 840),
    "south_america": (470, 545, 1065, 1220),
    "oceania": (1780, 670, 2685, 1190),
}

# Classes that are a single island / small island country. A range that
# uses only classes from one group is framed on that island.
ISLAND_GROUPS: dict[str, frozenset[str]] = {
    "iceland": frozenset({"is"}),
    "svalbard": frozenset({"sj"}),
    "faroe": frozenset({"fo"}),
    "greenland": frozenset({"gl"}),
    "britain": frozenset({"gb"}),
    "ireland": frozenset({"ie"}),
    "british_isles": frozenset({"gb", "ie"}),
    "cyprus": frozenset({"cy"}),
    "canaries": frozenset({"es-cny"}),
    "balearics": frozenset({"es-bal"}),
    "malta": frozenset({"mt"}),
    "taiwan": frozenset({"tw"}),
    "japan": frozenset({"jp"}),
    "philippines": frozenset({"ph"}),
    "sri_lanka": frozenset({"lk"}),
    "maldives": frozenset({"mv"}),
    "madagascar": frozenset({"mg"}),
    "cape_verde": frozenset({"cv"}),
    "mauritius": frozenset({"mu"}),
    "reunion": frozenset({"re"}),
    "seychelles": frozenset({"sc"}),
    "hawaii": frozenset({"us-hi"}),
    "new_zealand": frozenset({"nz"}),
    "fiji": frozenset({"fj"}),
    "new_caledonia": frozenset({"nc"}),
    "samoa": frozenset({"ws", "as"}),
    "cuba": frozenset({"cu"}),
    "jamaica": frozenset({"jm"}),
    "hispaniola": frozenset({"ht", "do"}),
    "puerto_rico": frozenset({"pr"}),
    "falklands": frozenset({"fk"}),
    "south_georgia": frozenset({"gs"}),
}

# Precomputed polygon boxes (Chrome getBBox). Hawaii is an inset below
# the main canvas.
ISLAND_BOX: dict[str, tuple[float, float, float, float]] = {
    "is": (1178.0, 135.7, 1240.6, 159.4),
    "sj": (1379.6, 38.9, 1488.7, 79.5),
    "fo": (1228.0, 145.0, 1248.0, 160.0),  # approx; refined if measured
    "gl": (967.9, 23.9, 1275.4, 187.7),
    "gb": (1260.6, 179.9, 1323.1, 267.6),
    "ie": (1243.3, 223.8, 1273.0, 255.4),
    "cy": (1533.5, 387.8, 1553.6, 403.5),
    "es-cny": (1169.7, 446.2, 1204.4, 459.4),
    "es-bal": (1315.0, 352.1, 1336.9, 364.3),
    "tw": (2182.9, 479.8, 2208.8, 508.4),
    "jp": (2223.8, 305.7, 2317.0, 488.6),
    "ph": (2192.0, 521.4, 2265.6, 654.9),
    "lk": (1907.7, 613.6, 1925.2, 647.4),
    "mg": (1625.2, 802.2, 1683.0, 919.9),
    "nz": (2405.5, 996.2, 2576.9, 1136.6),
    "us-hi": (52.3, 1610.1, 158.2, 1693.9),
}

EUROPE = frozenset(
    """
    ad al at ba be bg by ch cy cz de dk ee es es-bal fi fo fr gb gr hr hu ie is
    it li lt lu lv md me mk mt nl no pl pt ro rs ru-eu se si sj sk sm tr ua
    va xk xq
    """.split()
)
AFRICA = frozenset(
    """
    ao bf bi bj bw cd cf cg ci cm cv dj dz eg eh er es-cny et ga gh gm gn gq gw
    ke km lr ls ly ma mg ml mr mu mw mz na ne ng re rw sc sd sh sl sn so
    ss st sz td tg tn tz ug za zm zw
    """.split()
)
ASIA = frozenset(
    """
    ae af am az bd bh bn bt cn-ah cn-bj cn-cq cn-fj cn-gd cn-gs cn-gx
    cn-gz cn-ha cn-hb cn-he cn-hi cn-hl cn-hn cn-jl cn-js cn-jx cn-ln
    cn-nm cn-nx cn-qh cn-sc cn-sd cn-sh cn-sn cn-sx cn-tj cn-xj cn-xz
    cn-yn cn-zj cn ge id il in iq ir jo jp kg kh kp kr kw kz la lb lk mm
    mn my np om ph pk qa ru-fe ru-sib sa sg sy th tj tl tm tw uz vn ye
    """.split()
)
NORTH_AMERICA = frozenset(
    """
    ag aw bb bm bq bs bz ca-ab ca-bc ca-mb ca-nb ca-nl ca-ns ca-nt ca-nu
    ca-on ca-pe ca-qc ca-sk ca-yt ca cr cu cw do gd gl gt hn ht jm kn ky
    lc mx ni pa pr sv tc tt us-ak us-al us-ar us-az us-ca us-co us-ct
    us-dc us-de us-fl us-ga us-hi us-ia us-id us-il us-in us-ks us-ky
    us-la us-ma us-md us-me us-mi us-mn us-mo us-ms us-mt us-nc us-nd
    us-ne us-nh us-nj us-nm us-nv us-ny us-oh us-ok us-or us-pa us-ri
    us-sc us-sd us-tn us-tx us-ut us-va us-vt us-wa us-wi us-wv us-wy
    us vc vg
    """.split()
)
SOUTH_AMERICA = frozenset(
    """
    ar bo br cl co ec fk gf gy pe py sr uy ve
    """.split()
)
OCEANIA = frozenset(
    """
    as au ck fj fm gu ki mh mp nc nr nu nz pf pg pn pw sb tk to tv um vu
    wf ws
    """.split()
)
ANTARCTICA = frozenset("aq bv gs hm tf".split())

_ISLAND_CLASS = {c for g in ISLAND_GROUPS.values() for c in g}


def continent_of(cls: str) -> str | None:
    token = cls.lower().replace("_", "-")
    if token.startswith("us-") or token.startswith("ca-") or token.startswith("cn-"):
        if token.startswith("cn-"):
            return "asia"
        return "north_america"
    if token in EUROPE:
        return "europe"
    if token in AFRICA:
        return "africa"
    if token in ASIA:
        return "asia"
    if token in NORTH_AMERICA:
        return "north_america"
    if token in SOUTH_AMERICA:
        return "south_america"
    if token in OCEANIA:
        return "oceania"
    if token in ANTARCTICA:
        return "antarctica"
    return None


def _union_boxes(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[2] for b in boxes)
    maxy = max(b[3] for b in boxes)
    return minx, miny, maxx, maxy


def fit_viewbox(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    *,
    pad: float = 0.08,
    min_span: float = 0.0,
) -> tuple[float, float, float, float]:
    """Return (x, y, w, h) with padding. Does not stretch to the world aspect."""
    w = max(maxx - minx, 1.0)
    h = max(maxy - miny, 1.0)
    cx, cy = minx + w / 2.0, miny + h / 2.0
    w *= 1.0 + 2.0 * pad
    h *= 1.0 + 2.0 * pad
    if min_span:
        w = max(w, min_span)
        h = max(h, min_span)
    return cx - w / 2.0, cy - h / 2.0, w, h


def choose_focus(classes: list[str]) -> dict | None:
    """Return {kind, name, box} or None for a full-world map."""
    tokens = [c.lower().replace("_", "-") for c in classes if c]
    if not tokens:
        return None
    painted = frozenset(tokens)

    island_hits = [name for name, group in ISLAND_GROUPS.items() if painted <= group]
    if island_hits:
        island_hits.sort(key=lambda n: len(ISLAND_GROUPS[n]))
        name = island_hits[0]
        boxes = [ISLAND_BOX[c] for c in painted if c in ISLAND_BOX]
        if not boxes:
            return None
        minx, miny, maxx, maxy = _union_boxes(boxes)
        x, y, w, h = fit_viewbox(minx, miny, maxx, maxy, pad=0.35, min_span=180)
        return {"kind": "island", "name": name, "viewbox": (x, y, w, h)}

    continents = {continent_of(c) for c in painted}
    continents.discard(None)
    if len(continents) == 1:
        name = continents.pop()
        if name == "antarctica":
            return None
        box = CONTINENT_BOX.get(name)
        if not box:
            return None
        x, y, w, h = fit_viewbox(*box, pad=0.08, min_span=0)
        return {"kind": "continent", "name": name, "viewbox": (x, y, w, h)}
    return None


def apply_focus(svg: str, classes: list[str]) -> tuple[str, dict | None]:
    focus = choose_focus(classes)
    if not focus:
        return svg, None
    x, y, w, h = focus["viewbox"]
    svg = _zoom_transform(svg, x, y, w, h)
    zoom = min(CANVAS_W / w, CANVAS_H / h)
    stroke = max(0.12, 0.45 / zoom)
    svg = svg.replace(
        "</style>",
        f"\n.landxx, .coastxx, .antxx {{ stroke-width: {stroke:.3f}; }}\n</style>",
        1,
    )
    return svg, focus


def _zoom_transform(svg: str, x: float, y: float, w: float, h: float) -> str:
    """Scale so (x,y,w,h) fills the canvas; neighbouring land stays in frame."""
    scale = min(CANVAS_W / w, CANVAS_H / h)
    cx, cy = x + w / 2.0, y + h / 2.0
    tr = (
        "translate(%.3f %.3f) scale(%.5f) translate(%.3f %.3f)"
        % (CANVAS_W / 2.0, CANVAS_H / 2.0, scale, -cx, -cy)
    )
    start = svg.find("<svg")
    if start < 0:
        return svg
    open_end = svg.find(">", start)
    if open_end < 0:
        return svg
    svg = (
        svg[: open_end + 1]
        + '\n<g id="focus-zoom" transform="%s">\n' % tr
        + svg[open_end + 1 :]
    )
    svg = svg.replace("</svg>", "</g>\n</svg>", 1)
    return svg
