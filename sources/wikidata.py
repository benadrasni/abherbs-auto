"""Wikidata search + EntityData parse. No Firebase."""

from . import httputil
from . import ipni_overrides

SEARCH_URL = "https://www.wikidata.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

PID_IPNI = "P961"
PID_GBIF = "P846"
PID_USDA = "P1772"
PID_FREEBASE = "P646"
PID_TAXON_NAME = "P225"
PID_PARENT = "P171"
PID_RANK = "P105"
PID_HEIGHT = "P2048"
PID_COLOR = "P462"
PID_IUCN = "P141"

# Wikidata quantity units → centimetres
HEIGHT_UNIT_CM = {
    "Q11573": 100.0,  # metre
    "Q174728": 1.0,  # centimetre
    "Q3716": 30.48,  # foot
    "Q218593": 2.54,  # inch
}


def search(name, limit=5):
    params = httputil.urlencode(
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "type": "item",
            "format": "json",
            "limit": str(limit),
        }
    )
    payload = httputil.get_json(SEARCH_URL + "?" + params)
    hits = []
    for item in payload.get("search") or []:
        hits.append(
            {
                "qid": item.get("id"),
                "label": item.get("label") or "",
                "description": item.get("description") or "",
            }
        )
    return hits


def pick_taxon(name, hits):
    """Prefer an exact label match whose description looks like a taxon."""
    wanted = name.strip().lower()
    exact = [hit for hit in hits if hit["label"].strip().lower() == wanted]
    pool = exact or hits
    for hit in pool:
        desc = hit["description"].lower()
        if "species" in desc or "plant" in desc or "taxon" in desc:
            return hit
    return pool[0] if pool else None


def fetch_entity(qid):
    payload = httputil.get_json(ENTITY_URL.format(qid=qid))
    entities = payload.get("entities") or {}
    if qid in entities:
        return entities[qid]
    if entities:
        return next(iter(entities.values()))
    raise KeyError("no entity for %s" % qid)


def _string_claim(claims, pid):
    block = claims.get(pid) or []
    if not block:
        return None
    snak = block[0].get("mainsnak") or {}
    datavalue = snak.get("datavalue") or {}
    value = datavalue.get("value")
    if isinstance(value, dict):
        return value.get("id") or value.get("text")
    return value


def _item_ids(claims, pid):
    ids = []
    for claim in claims.get(pid) or []:
        snak = claim.get("mainsnak") or {}
        value = (snak.get("datavalue") or {}).get("value")
        if isinstance(value, dict) and value.get("id"):
            ids.append(value["id"])
    return ids


def _quantity_number(raw):
    if raw is None:
        return None
    try:
        return float(str(raw).replace("+", ""))
    except ValueError:
        return None


def _quantity_cm(value):
    if not isinstance(value, dict):
        return None
    unit = (value.get("unit") or "").rsplit("/", 1)[-1]
    factor = HEIGHT_UNIT_CM.get(unit)
    if not factor:
        return None

    def as_cm(key):
        number = _quantity_number(value.get(key))
        if number is None:
            return None
        return int(round(number * factor))

    low = as_cm("lowerBound")
    high = as_cm("upperBound")
    mid = as_cm("amount")
    if low is not None and high is not None:
        return low, high
    if mid is not None:
        return mid, mid
    return None


def _height_cm(claims):
    lows = []
    highs = []
    for claim in claims.get(PID_HEIGHT) or []:
        snak = claim.get("mainsnak") or {}
        pair = _quantity_cm((snak.get("datavalue") or {}).get("value"))
        if not pair:
            continue
        lows.append(pair[0])
        highs.append(pair[1])
    if not lows:
        return None, None
    return min(lows), max(highs)


def parse_entity(entity):
    qid = entity.get("id")
    claims = entity.get("claims") or {}
    sitelinks = entity.get("sitelinks") or {}
    labels = {}
    for lang, item in (entity.get("labels") or {}).items():
        labels[lang] = item.get("value")
    aliases = {}
    for lang, items in (entity.get("aliases") or {}).items():
        aliases[lang] = [item.get("value") for item in items if item.get("value")]

    wikilinks = {"data": "https://www.wikidata.org/wiki/" + qid}
    wikipedia = {}
    for key, link in sitelinks.items():
        url = link.get("url")
        if not url:
            continue
        if key == "commonswiki":
            wikilinks["commons"] = url
        elif key == "specieswiki":
            wikilinks["species"] = url
        elif key.endswith("wiki") and not key.endswith("wikiquote"):
            lang = key[: -len("wiki")]
            wikipedia[lang] = url

    ipni_id = ipni_overrides.apply(_string_claim(claims, PID_IPNI))
    height_from_cm, height_to_cm = _height_cm(claims)
    return {
        "qid": qid,
        "labels": labels,
        "aliases": aliases,
        "wikilinks": wikilinks,
        "wikipedia": wikipedia,
        "ipni_id": ipni_id,
        "gbif_id": _string_claim(claims, PID_GBIF),
        "usda_id": _string_claim(claims, PID_USDA),
        "freebase_id": _string_claim(claims, PID_FREEBASE),
        "taxon_name": _string_claim(claims, PID_TAXON_NAME) or labels.get("en") or labels.get("mul"),
        "parent_qids": _item_ids(claims, PID_PARENT),
        "rank_qid": (_item_ids(claims, PID_RANK) or [None])[0],
        "color_qids": _item_ids(claims, PID_COLOR),
        "iucn_qid": (_item_ids(claims, PID_IUCN) or [None])[0],
        "height_from_cm": height_from_cm,
        "height_to_cm": height_to_cm,
    }


def lookup(name):
    hits = search(name)
    picked = pick_taxon(name, hits)
    if not picked:
        return None
    return parse_entity(fetch_entity(picked["qid"]))
