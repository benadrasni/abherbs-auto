"""Unauthenticated reads of the public catalog. No writes, no Admin SDK."""

import urllib.parse

from . import httputil

RTDB = "https://abherbs-backend.firebaseio.com"


def get(path):
    parts = [urllib.parse.quote(part, safe="") for part in path.strip("/").split("/")]
    url = RTDB.rstrip("/") + "/" + "/".join(parts) + ".json"
    return httputil.get_json(url)


def plants_to_update():
    payload = get("plants_to_update") or {}
    names = payload.get("list") or []
    if isinstance(names, dict):
        items = sorted(
            ((int(k) if str(k).isdigit() else k, v) for k, v in names.items() if k != "count"),
            key=lambda item: item[0],
        )
        names = [value for _, value in items]
    count = payload.get("count")
    if count is None:
        count = len(names)
    return {"count": int(count), "list": list(names)}


def next_id(catalog=None):
    catalog = catalog or plants_to_update()
    return int(catalog["count"])


def catalog_id(name, catalog=None):
    catalog = catalog or plants_to_update()
    try:
        return catalog["list"].index(name)
    except ValueError:
        return None


def sister_names(genus, exclude, catalog=None):
    """Latin names in the live catalog that share `genus`."""
    if not genus:
        return []
    catalog = catalog or plants_to_update()
    prefix = genus.strip() + " "
    skip = (exclude or "").strip()
    names = []
    for name in catalog.get("list") or []:
        if name.startswith(prefix) and name != skip:
            names.append(name)
    return names


def _sister_row(name, header, v2):
    header = header or {}
    v2 = v2 or {}
    return {
        "name": name,
        "color": list(header.get("filterColor") or []),
        "habitat": list(header.get("filterHabitat") or []),
        "height_from": v2.get("heightFrom"),
        "height_to": v2.get("heightTo"),
        "flowering_from": v2.get("floweringFrom"),
        "flowering_to": v2.get("floweringTo"),
    }


def sister_traits(genus, exclude, catalog=None, limit=5, include_english=False):
    """Best-guess traits from a few live congeners. Network; empty on failure."""
    catalog = catalog or plants_to_update()
    rows = []
    for name in sister_names(genus, exclude, catalog)[:limit]:
        plant_id = catalog_id(name, catalog)
        header = None
        v2 = None
        if plant_id is not None:
            header = get("plants_headers/%s" % plant_id)
        v2 = get("plants_v2/" + name)
        if header or v2:
            row = _sister_row(name, header, v2)
            if include_english:
                row["en"] = get("translations/en/" + name) or {}
            rows.append(row)
    return rows
