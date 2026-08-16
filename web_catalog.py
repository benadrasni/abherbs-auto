"""Slim website catalog: id, plate, and sourced labels.

Published at web/catalog/{id} and web/labels/{lang}/{id}. Does not talk
to Firebase. Do not invert search_v3; labels come from translations only.
"""

from catalog_indexes import SEARCH_LANGUAGES, header_at


CATALOG_NODE = "web/catalog"
LABELS_NODE = "web/labels"

# Website UI languages that are not in the app search index.
EXTRA_WEB_LANGUAGES = ("ar", "fa", "he", "hi", "pa")
LABEL_LANGUAGES = frozenset(SEARCH_LANGUAGES + EXTRA_WEB_LANGUAGES)


def derived_illustration_url(header_url):
    """Same derivation as web illustrationFromHeaderUrl()."""
    if not header_url:
        return ""
    parts = str(header_url).split("/")
    if len(parts) < 3:
        return str(header_url)
    return "%s/%s.webp" % ("/".join(parts[:3]), parts[2])


def illustration_url(plants_v2_record, header):
    record = plants_v2_record or {}
    if record.get("illustrationUrl"):
        return record["illustrationUrl"]
    return derived_illustration_url((header or {}).get("url"))


def sourced_label(entry):
    if not isinstance(entry, dict):
        return ""
    label = entry.get("label")
    if not isinstance(label, str):
        return ""
    return label.strip()


def skip_label_language(language):
    if not language or not isinstance(language, str):
        return True
    if language == "la" or language.endswith("-GT"):
        return True
    for char in "./#$[]":
        if char in language:
            return True
    return False


def entry_from_parts(plant_id, name, header=None, plants_v2_record=None):
    header = header or {}
    return {
        "id": int(plant_id),
        "name": header.get("name") or name,
        "family": header.get("family") or "",
        "url": header.get("url") or "",
        "illustrationUrl": illustration_url(plants_v2_record, header),
    }


def entry_from_packet(packet):
    job = packet.get("job") or {}
    header = packet.get("plants_header") or {}
    v2 = packet.get("plants_v2") or {}
    plant_id = job.get("id")
    if plant_id is None:
        raise ValueError("packet has no numeric id")
    name = job.get("accepted_name") or header.get("name") or v2.get("name") or ""
    return entry_from_parts(plant_id, name, header, v2)


def labels_from_translations(translations):
    """Return {lang: label} for sourced vernaculars only."""
    labels = {}
    for language, payload in (translations or {}).items():
        if skip_label_language(language):
            continue
        label = sourced_label(payload)
        if label:
            labels[language] = label
    return labels


def labels_from_packet(packet):
    return labels_from_translations(packet.get("translations") or {})


def catalog_patch(packet):
    return {
        "plant_id": int(packet["job"]["id"]),
        "entry": entry_from_packet(packet),
        "labels": labels_from_packet(packet),
    }


def _plant_id_for(index, name, plants_v2_record, warnings=None):
    """Website / search id is the plants_to_update list index.

    plants_v2.id should match. When it does not, keep the list index so a
    corrupt v2 id cannot overwrite another plant or drop this one.
    """
    plant_id = int(index)
    record = plants_v2_record or {}
    if record.get("id") is not None and int(record["id"]) != plant_id:
        if warnings is not None:
            warnings.append(
                "plants_v2 id %s != list index %s (%s)"
                % (record.get("id"), plant_id, name)
            )
    return plant_id


def slim_plants_v2(raw):
    """Keep only id + illustrationUrl from a plants_v2 dump."""
    slim = {}
    for name, record in (raw or {}).items():
        if not isinstance(record, dict):
            continue
        slim[name] = {
            "id": record.get("id"),
            "illustrationUrl": record.get("illustrationUrl") or "",
        }
    return slim


def summarize(catalog, labels, expected=None):
    entries = catalog or {}
    missing_name = []
    missing_family = []
    missing_plate = []
    for token, entry in entries.items():
        if not entry.get("name"):
            missing_name.append(token)
        if not entry.get("family"):
            missing_family.append(token)
        if not entry.get("illustrationUrl"):
            missing_plate.append(token)
    en = (labels or {}).get("en") or {}
    return {
        "entries": len(entries),
        "expected": expected,
        "covers_expected": expected is None or len(entries) >= int(expected),
        "label_languages": sorted(labels or {}),
        "english_labels": len(en),
        "missing_name": missing_name,
        "missing_family": missing_family,
        "missing_illustration": missing_plate,
    }


def build_catalog(plant_names, headers, plants_v2=None, translations=None):
    """Build {id: entry} and {lang: {id: label}} from a catalog dump."""
    plants_v2 = plants_v2 or {}
    translations = translations or {}
    catalog = {}
    labels = {}
    warnings = []

    for index, name in enumerate(plant_names or []):
        header = header_at(headers, index)
        v2 = plants_v2.get(name) or {}
        if not header and not v2:
            warnings.append("missing web catalog source %s (%s)" % (index, name))
            continue
        plant_id = _plant_id_for(index, name, v2, warnings)
        token = str(plant_id)
        catalog[token] = entry_from_parts(plant_id, name, header, v2)
        for language, plants in translations.items():
            if skip_label_language(language) or not isinstance(plants, dict):
                continue
            label = sourced_label(plants.get(name))
            if not label:
                continue
            bucket = labels.get(language)
            if bucket is None:
                bucket = {}
                labels[language] = bucket
            bucket[token] = label

    return catalog, labels, warnings
