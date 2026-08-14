"""GBIF species match. No Firebase."""

from . import httputil

MATCH_URL = "https://api.gbif.org/v1/species/match"
OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"


def match(name):
    url = MATCH_URL + "?" + httputil.urlencode({"name": name})
    payload = httputil.get_json(url)
    if not payload or payload.get("matchType") == "NONE":
        return None
    return {
        "usage_key": payload.get("usageKey") or payload.get("speciesKey"),
        "scientific_name": payload.get("scientificName"),
        "canonical_name": payload.get("canonicalName"),
        "rank": payload.get("rank"),
        "status": payload.get("status"),
        "confidence": payload.get("confidence"),
        "match_type": payload.get("matchType"),
        "kingdom": payload.get("kingdom"),
        "order": payload.get("order"),
        "family": payload.get("family"),
        "genus": payload.get("genus"),
        "accepted_usage_key": payload.get("acceptedUsageKey") or payload.get("speciesKey"),
    }


def license_ok(license_value):
    from . import commons

    text = (license_value or "").strip()
    if text.startswith("http"):
        return commons.license_ok_url(text)
    return commons.license_ok(text)


def media_search(name, limit=40):
    """Still images from GBIF/iNat with a free license (no NC/ND)."""
    payload = httputil.get_json(
        OCCURRENCE_URL
        + "?"
        + httputil.urlencode(
            {
                "scientificName": name,
                "mediaType": "StillImage",
                "limit": str(min(limit, 100)),
            }
        )
    )
    files = []
    seen = set()
    for record in payload.get("results") or []:
        key = record.get("key")
        for media in record.get("media") or []:
            url = media.get("identifier") or media.get("references") or ""
            if not url or url in seen:
                continue
            license_value = media.get("license") or ""
            if not license_ok(license_value):
                continue
            mime = (media.get("format") or "image/jpeg").lower()
            if not mime.startswith("image/"):
                continue
            seen.add(url)
            files.append(
                {
                    "title": media.get("title")
                    or "%s GBIF %s" % (record.get("scientificName") or name, key),
                    "url": url,
                    "descriptionurl": "https://www.gbif.org/occurrence/%s" % key if key else url,
                    "mime": mime,
                    "width": 0,
                    "height": 0,
                    "license": license_value,
                    "license_ok": True,
                    "description": media.get("description") or "",
                    "object_name": "",
                    "categories": "",
                    "artist": media.get("rightsHolder") or "",
                    "source": "gbif",
                    "role_hint": None,
                    "score": 1,
                }
            )
    return files
