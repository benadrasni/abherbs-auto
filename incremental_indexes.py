"""Build a one-plant index patch. Does not write Firebase."""

import catalog_indexes
import web_catalog


def filter_patch(plant_id, header):
    keys = catalog_indexes.matching_keys(header)
    token = str(plant_id)
    return {
        "counts": {key: 1 for key in keys},
        "lists": {key: {token: 1} for key in keys},
    }


def search_patch(plant_id, translations, latin_name, synonyms=None):
    """translations is {lang: {label, names}}."""
    search = {}
    warnings = []
    plant_ids = {latin_name: plant_id}
    allowed = set(catalog_indexes.SEARCH_LANGUAGES)
    for language, payload in (translations or {}).items():
        if language.endswith("-GT"):
            continue
        if language != "la" and language not in allowed:
            continue
        language_map, language_warnings = catalog_indexes.build_search_language(
            plant_ids, {latin_name: payload or {}}
        )
        if language_map:
            search[language] = language_map
        warnings.extend(language_warnings)

    latin_map = {}
    catalog_indexes._add_search_hit(latin_map, latin_name, plant_id, True, warnings)
    for synonym in synonyms or []:
        name = synonym.get("name") if isinstance(synonym, dict) else synonym
        if name and "." not in name:
            catalog_indexes._add_search_hit(latin_map, name, plant_id, False, warnings)
    search["la"] = latin_map
    return {"search": search, "warnings": warnings}


def photo_patch(latin_name, synonyms=None, freebase_id=None):
    photo = {latin_name.lower(): {"count": 1, "path": latin_name}}
    for synonym in synonyms or []:
        name = synonym.get("name") if isinstance(synonym, dict) else synonym
        if not name:
            continue
        key = name.lower()
        if key not in photo and "." not in name:
            photo[key] = {"count": 1, "path": latin_name}
    if freebase_id:
        token = str(freebase_id).strip()
        token = token[token.rfind("/") + 1:]
        if token:
            photo.setdefault("m", {})[token] = {"count": 1, "path": latin_name}
    return photo


def build_patch(packet):
    job = packet["job"]
    header = packet["plants_header"]
    plant_id = job["id"]
    latin = job["accepted_name"]
    translations = packet.get("translations") or {}
    synonyms = (packet.get("synonyms") or {}).get("ipni") or []
    v2 = packet.get("plants_v2") or {}
    filters = filter_patch(plant_id, header)
    search = search_patch(plant_id, translations, latin, synonyms)
    photo = photo_patch(latin, synonyms, v2.get("freebaseId"))
    web = web_catalog.catalog_patch(packet)
    return {
        "plant_id": plant_id,
        "name": latin,
        "counts": filters["counts"],
        "lists": filters["lists"],
        "search": search["search"],
        "search_photo": photo,
        "web_entry": web["entry"],
        "web_labels": web["labels"],
        "warnings": search["warnings"],
        "filter_key_count": len(filters["counts"]),
    }
