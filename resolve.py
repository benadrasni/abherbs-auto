"""Resolve a Latin name to catalog fields. No Firebase writes."""

import constants
from sources import gbif
from sources import ipni
from sources import wcvp
from sources import wikidata


def photo_prefix(latin_name):
    parts = latin_name.split()
    if not parts:
        return "xx"
    first = parts[0][0].lower()
    last = parts[-1][0].lower()
    return first + last


def storage_folder(order, family, latin_name):
    return "/".join([order, family, latin_name.replace(" ", "_")])


def apg_path(order, family, genus):
    """Familia + Genus plus the hardcoded APG IV spine for this order."""
    path = {}
    rank = 0
    path["%02d_Genus" % rank] = genus
    rank += 1
    if family:
        path["%02d_Familia" % rank] = family
        rank += 1
    if order in constants.apgiv_names and order in constants.apgiv_values:
        names = list(reversed(constants.apgiv_names[order].split("/")))
        values = list(reversed(constants.apgiv_values[order].split("/")))
        for name, value in zip(names, values):
            path["%02d_%s" % (rank, name)] = value
            rank += 1
    elif order:
        path["%02d_Ordo" % rank] = order
    return path


def _warnings_for(wcvp_row, wd, gbif_row, ipni_row):
    warnings = []
    if not wcvp_row:
        warnings.append("wcvp: name not found")
    elif not wcvp_row.get("l2"):
        warnings.append("wcvp: empty distribution")
    if not wd:
        warnings.append("wikidata: no entity")
    if not gbif_row:
        warnings.append("gbif: no match")
    if not ipni_row and not (wcvp_row and wcvp_row.get("ipni_id")):
        warnings.append("ipni: no id")
    return warnings


def resolve(name, wcvp_db=None):
    latin = name.strip()
    wcvp_row = wcvp.lookup(latin, db_path=wcvp_db)
    if wcvp_row:
        latin = wcvp_row["accepted_name"]

    wd = None
    try:
        wd = wikidata.lookup(latin)
    except Exception as exc:
        wd = {"_error": str(exc)}

    gbif_row = None
    try:
        gbif_row = gbif.match(latin)
    except Exception as exc:
        gbif_row = {"_error": str(exc)}

    ipni_row = None
    try:
        ipni_row = ipni.lookup(latin)
    except Exception as exc:
        ipni_row = {"_error": str(exc)}

    wd_ok = wd if wd and "_error" not in wd else None
    gbif_ok = gbif_row if gbif_row and "_error" not in gbif_row else None
    ipni_ok = ipni_row if ipni_row and "_error" not in ipni_row else None

    family = (
        (wcvp_row or {}).get("family")
        or (gbif_ok or {}).get("family")
        or ""
    )
    order = (gbif_ok or {}).get("order") or ""
    genus = (
        (wcvp_row or {}).get("genus")
        or (gbif_ok or {}).get("genus")
        or (latin.split()[0] if latin else "")
    )
    author = (
        (wcvp_row or {}).get("author")
        or (ipni_ok or {}).get("authors")
        or ""
    )
    ipni_id = (
        (wcvp_row or {}).get("ipni_id")
        or (ipni_ok or {}).get("ipni_id")
        or (wd_ok or {}).get("ipni_id")
        or ""
    )
    gbif_id = (wd_ok or {}).get("gbif_id") or (
        str((gbif_ok or {}).get("usage_key") or "") or None
    )
    usda_id = (wd_ok or {}).get("usda_id")
    freebase_id = (wd_ok or {}).get("freebase_id")
    qid = (wd_ok or {}).get("qid")
    l2 = list((wcvp_row or {}).get("l2") or [])
    lifeform = (wcvp_row or {}).get("lifeform") or ""

    warnings = _warnings_for(wcvp_row, wd_ok, gbif_ok, ipni_ok)
    if wd and "_error" in wd:
        warnings.append("wikidata: %s" % wd["_error"])
    if gbif_row and "_error" in gbif_row:
        warnings.append("gbif: %s" % gbif_row["_error"])
    if ipni_row and "_error" in ipni_row:
        warnings.append("ipni: %s" % ipni_row["_error"])
    if not order:
        warnings.append("order unknown; APG path will be incomplete")

    wikilinks = (wd_ok or {}).get("wikilinks") or {}
    if qid and "data" not in wikilinks:
        wikilinks["data"] = "https://www.wikidata.org/wiki/" + qid

    return {
        "query": name.strip(),
        "accepted_name": latin,
        "author": author,
        "family": family,
        "order": order,
        "genus": genus,
        "ipni_id": ipni_id,
        "gbif_id": gbif_id,
        "usda_id": usda_id,
        "freebase_id": freebase_id,
        "qid": qid,
        "lifeform": lifeform,
        "l2": l2,
        "native_l2": list((wcvp_row or {}).get("native_l2") or []),
        "wikilinks": wikilinks,
        "wikipedia": (wd_ok or {}).get("wikipedia") or {},
        "labels": (wd_ok or {}).get("labels") or {},
        "aliases": (wd_ok or {}).get("aliases") or {},
        "synonyms": (wcvp_row or {}).get("synonyms") or [],
        "apg": apg_path(order, family, genus),
        "folder": storage_folder(order or "Unknown", family or "Unknown", latin),
        "photo_prefix": photo_prefix(latin),
        "wiki_name": latin,
        "warnings": warnings,
        "sources": {
            "wcvp": wcvp_row,
            "wikidata": wd_ok,
            "gbif": gbif_ok,
            "ipni": ipni_ok,
        },
    }
