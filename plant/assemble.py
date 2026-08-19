"""Build a local add-species job packet. No Firebase writes."""

import json
import os
from datetime import date

from plant import common_names
import constants
from sources import catalog_rest


def slug(latin_name):
    return latin_name.replace(" ", "_")


def jobs_root():
    return os.path.join(constants.plantsdir, "_jobs")


def job_dir(latin_name):
    return os.path.join(jobs_root(), slug(latin_name))


def german_label(name):
    return common_names.display_name(name, "de")


def common_name(name, language):
    return common_names.display_name(name, language)


def is_synonym_label(name, synonyms):
    for item in synonyms:
        synonym = item.get("name") if isinstance(item, dict) else item
        if synonym and synonym.startswith(name):
            return True
    return False


def translations_from_wikidata(resolved):
    """Wikidata labels/aliases and Wikipedia titles. Never invent a vernacular."""
    return common_names.translations_from_sources(resolved)


def build_records(resolved, plant_id, already_in_catalog):
    latin = resolved["accepted_name"]
    folder = resolved["folder"]
    prefix = resolved["photo_prefix"]
    illustration = "%s/%s.webp" % (folder, latin.replace(" ", "_"))
    header_url = "%s/%s1.webp" % (folder, prefix)

    plants_v2 = {
        "APGIV": resolved.get("apg") or {},
        "id": plant_id,
        "name": latin,
        "wikiName": resolved.get("wiki_name") or latin,
        "illustrationUrl": illustration,
        "photoUrls": [],
        "sourceUrls": [],
        "wikilinks": resolved.get("wikilinks") or {},
    }
    if resolved.get("author"):
        plants_v2["author"] = resolved["author"]
    if resolved.get("ipni_id"):
        plants_v2["ipniId"] = resolved["ipni_id"]
    if resolved.get("gbif_id"):
        plants_v2["gbifId"] = int(resolved["gbif_id"]) if str(resolved["gbif_id"]).isdigit() else resolved["gbif_id"]
    if resolved.get("usda_id"):
        plants_v2["usdaId"] = resolved["usda_id"]
    if resolved.get("freebase_id"):
        plants_v2["freebaseId"] = resolved["freebase_id"]

    header = {
        "family": resolved.get("family") or "",
        "name": latin,
        "url": header_url,
        "filterColor": [],
        "filterHabitat": [],
        "filterPetal": [],
        "filterDistribution": list(resolved.get("l2") or []),
    }

    synonyms = {"ipni": []}
    for item in resolved.get("synonyms") or []:
        synonyms["ipni"].append(
            {
                "name": item.get("name"),
                "author": item.get("authors") or "",
                "suffix": "",
                "href": "/taxon/urn:lsid:ipni.org:names:%s" % item["ipni_id"]
                if item.get("ipni_id")
                else "",
            }
        )

    needs = []
    if not header["filterDistribution"]:
        needs.append("distribution")
    needs.extend(["color", "habitat", "petal"])
    if already_in_catalog:
        needs.append("already_in_catalog")

    status = "needs_review" if needs else "draft"
    job = {
        "query": resolved.get("query"),
        "accepted_name": latin,
        "id": plant_id,
        "already_in_catalog": already_in_catalog,
        "status": status,
        "needs": needs,
        "warnings": list(resolved.get("warnings") or []),
        "date": date.today().isoformat(),
        "folder": folder,
        "photo_prefix": prefix,
        "lifeform": resolved.get("lifeform") or "",
        "qid": resolved.get("qid"),
    }
    return {
        "job": job,
        "plants_v2": plants_v2,
        "plants_header": header,
        "synonyms": synonyms,
        "translations": translations_from_wikidata(resolved),
        "resolved": resolved,
    }


def write_json(path, payload):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_review(path, packet):
    job = packet["job"]
    v2 = packet["plants_v2"]
    header = packet["plants_header"]
    lines = [
        "# %s" % job["accepted_name"],
        "",
        "- status: %s" % job["status"],
        "- id: %s" % job["id"],
        "- already in catalog: %s" % job["already_in_catalog"],
        "- family: %s" % header.get("family"),
        "- IPNI: %s" % v2.get("ipniId"),
        "- GBIF: %s" % v2.get("gbifId"),
        "- Wikidata: %s" % job.get("qid"),
        "- distribution L2: %s" % header.get("filterDistribution"),
        "- color: %s" % header.get("filterColor"),
        "- habitat: %s" % header.get("filterHabitat"),
        "- petal: %s" % header.get("filterPetal"),
        "- height: %s–%s cm" % (v2.get("heightFrom"), v2.get("heightTo")),
        "- flowering: %s–%s" % (v2.get("floweringFrom"), v2.get("floweringTo")),
        "- toxicityClass: %s" % v2.get("toxicityClass"),
        "- illustration: %s" % (job.get("illustration") or {}),
        "- photos: %s" % (job.get("photos") or {}),
        "",
        "## Photos",
    ]
    for item in (job.get("photos") or {}).get("chosen") or []:
        lines.append(
            "- %s: %s (%s) %s"
            % (
                item.get("role"),
                item.get("title") or item.get("filename"),
                item.get("license") or "license?",
                item.get("source_url") or "",
            )
        )
    if not (job.get("photos") or {}).get("chosen"):
        lines.append("- (none yet)")
    traits = job.get("traits") or {}
    if traits:
        lines.append("")
        lines.append("## Traits")
        for axis in ("color", "habitat", "petal"):
            info = traits.get(axis) or {}
            lines.append(
                "- %s: %s (confidence %s) %s"
                % (
                    axis,
                    info.get("values"),
                    info.get("confidence"),
                    "; ".join(info.get("evidence") or []),
                )
            )
        if traits.get("height_from") is not None:
            lines.append(
                "- height: %s–%s cm — %s"
                % (
                    traits.get("height_from"),
                    traits.get("height_to"),
                    traits.get("height_evidence") or "guess",
                )
            )
        if traits.get("flowering_from") is not None:
            lines.append(
                "- flowering: %s–%s — %s"
                % (
                    traits.get("flowering_from"),
                    traits.get("flowering_to"),
                    traits.get("flowering_evidence") or "guess",
                )
            )
    lines.append("")
    lines.append("## Needs")
    for item in job.get("needs") or []:
        lines.append("- %s" % item)
    lines.append("")
    lines.append("## Warnings")
    if job.get("warnings"):
        for item in job["warnings"]:
            lines.append("- %s" % item)
    else:
        lines.append("- none")
    sourced = job.get("sourced_names") or {}
    lines.append("")
    lines.append("## Common names")
    lines.append(
        "Sourced only. Never translate the English name; if a language has no source, omit label (the app shows Latin)."
    )
    if sourced:
        for lang in sorted(sourced):
            parts = [
                "%s (%s)" % (item.get("name"), item.get("source"))
                for item in sourced[lang]
            ]
            lines.append("- %s: %s" % (lang, "; ".join(parts)))
    else:
        lines.append("- (none yet; use Latin)")
    from sources import botanical

    resolved = packet.get("resolved") or {}
    hints = botanical.hints_for(
        job.get("accepted_name") or header.get("name"),
        family=header.get("family"),
        lifeform=job.get("lifeform") or "",
        native_l2=resolved.get("native_l2"),
        native_l3=resolved.get("native_l3"),
    )
    if hints:
        lines.append("")
        lines.append("## Botanical sources")
        for hint in hints:
            mark = "reliable" if hint.get("reliable") else hint.get("fetch") or "manual"
            lines.append(
                "- [%s] %s: %s — %s"
                % (mark, hint["name"], hint.get("url") or "", hint.get("notes") or "")
            )
    lines.append("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def assemble(resolved, dest=None, catalog=None):
    latin = resolved["accepted_name"]
    dest = dest or job_dir(latin)
    os.makedirs(os.path.join(dest, "media"), exist_ok=True)
    os.makedirs(os.path.join(dest, "translations"), exist_ok=True)

    try:
        catalog = catalog or catalog_rest.plants_to_update()
        existing_id = catalog_rest.catalog_id(latin, catalog)
        if existing_id is None:
            plant_id = catalog_rest.next_id(catalog)
            already = False
        else:
            plant_id = existing_id
            already = True
    except Exception as exc:
        plant_id = None
        already = False
        resolved.setdefault("warnings", []).append("catalog rest: %s" % exc)

    packet = build_records(resolved, plant_id, already)
    write_json(os.path.join(dest, "job.json"), packet["job"])
    write_json(os.path.join(dest, "plants_v2.json"), packet["plants_v2"])
    write_json(os.path.join(dest, "plants_header.json"), packet["plants_header"])
    write_json(os.path.join(dest, "synonyms.json"), packet["synonyms"])
    write_json(os.path.join(dest, "resolved.json"), resolved)
    for lang, entry in packet["translations"].items():
        write_json(os.path.join(dest, "translations", lang + ".json"), entry)
    write_review(os.path.join(dest, "review.md"), packet)
    packet["dir"] = dest
    return packet


def apply_inference(packet, traits, english):
    """Write inferred traits and English draft onto the packet."""
    header = packet["plants_header"]
    v2 = packet["plants_v2"]
    job = packet["job"]
    needs = [item for item in job.get("needs") or [] if item not in ("color", "habitat", "petal")]

    job["traits"] = {
        "color": traits.get("color"),
        "habitat": traits.get("habitat"),
        "petal": traits.get("petal"),
        "height_from": traits.get("height_from"),
        "height_to": traits.get("height_to"),
        "height_evidence": traits.get("height_evidence"),
        "flowering_from": traits.get("flowering_from"),
        "flowering_to": traits.get("flowering_to"),
        "flowering_evidence": traits.get("flowering_evidence"),
        "toxicity_class": traits.get("toxicity_class"),
    }
    for axis, key in (("color", "filterColor"), ("habitat", "filterHabitat"), ("petal", "filterPetal")):
        info = traits.get(axis) or {}
        values = list(info.get("values") or [])
        header[key] = values
        if not values:
            needs.append(axis)
    if traits.get("height_from") is None:
        needs.append("height")
    if traits.get("flowering_from") is None:
        needs.append("flowering")

    if traits.get("height_from") is not None:
        v2["heightFrom"] = traits["height_from"]
    if traits.get("height_to") is not None:
        v2["heightTo"] = traits["height_to"]
    if traits.get("flowering_from") is not None:
        v2["floweringFrom"] = traits["flowering_from"]
    if traits.get("flowering_to") is not None:
        v2["floweringTo"] = traits["flowering_to"]
    if traits.get("toxicity_class") is not None:
        v2["toxicityClass"] = traits["toxicity_class"]

    if english:
        translations = packet.setdefault("translations", {})
        existing = translations.get("en") or {}
        existing.update(
            (key, value)
            for key, value in english.items()
            if value and not str(key).startswith("_")
        )
        translations["en"] = existing
        missing = english.get("_draft_missing") or []
        if missing:
            job.setdefault("warnings", []).append(
                "english incomplete: %s" % ", ".join(missing)
            )

    job["needs"] = needs
    job["status"] = "needs_review" if needs else "draft"
    return packet
