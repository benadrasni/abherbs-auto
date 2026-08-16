"""Publish a validated job packet to GCS + RTDB. Only when explicitly asked."""

import json
import os
import time
from datetime import date

import apg_tree
import constants
import incremental_indexes
import storage_make_public
import storage_upload_file
import validate
import web_catalog


def load_packet(job_dir):
    def read(name):
        with open(os.path.join(job_dir, name), encoding="utf-8") as handle:
            return json.load(handle)

    translations = {}
    tdir = os.path.join(job_dir, "translations")
    if os.path.isdir(tdir):
        for filename in os.listdir(tdir):
            if filename.endswith(".json"):
                translations[filename[:-5]] = read(os.path.join("translations", filename))
    return {
        "dir": job_dir,
        "job": read("job.json"),
        "plants_v2": read("plants_v2.json"),
        "plants_header": read("plants_header.json"),
        "synonyms": read("synonyms.json"),
        "translations": translations,
    }


def refuse(packet):
    report = validate.validate(packet)
    if packet.get("job", {}).get("already_in_catalog"):
        report["ok"] = False
        report["errors"] = list(report.get("errors") or []) + ["already in catalog"]
    return report


def _official_files(packet):
    media_dir = os.path.join(packet["dir"], "media")
    names = [os.path.basename(packet["plants_v2"]["illustrationUrl"])]
    for url in packet["plants_v2"].get("photoUrls") or []:
        names.append(os.path.basename(url))
    files = []
    for name in names:
        path = os.path.join(media_dir, name)
        if os.path.isfile(path):
            files.append((path, name, False))
        thumb = os.path.join(media_dir, constants.thumbdir, name)
        if os.path.isfile(thumb):
            files.append((thumb, name, True))
    return files


def upload_media(packet):
    folder = packet["job"]["folder"]
    dest = "photos/" + folder + "/"
    for path, name, is_thumb in _official_files(packet):
        remote = dest + (constants.thumbdir + "/" if is_thumb else "") + name
        storage_upload_file.upload_blob(
            constants.bucket_name, path, remote, "image/webp"
        )
        storage_make_public.make_blob_public(constants.bucket_name, remote)


def apply_indexes_live(packet):
    from firebase_admin import db

    patch = incremental_indexes.build_patch(packet)
    plant_id = str(patch["plant_id"])
    for key, delta in (patch.get("counts") or {}).items():
        ref = db.reference("counts_4_v2/" + key)
        current = ref.get() or 0
        ref.set(int(current) + int(delta))
        db.reference("lists_4_v2/" + key).update({plant_id: 1})
    for language, payload in (patch.get("search") or {}).items():
        for name, value in payload.items():
            db.reference("search_v3/%s/%s" % (language, name)).update(value)
    for name, value in (patch.get("search_photo") or {}).items():
        if name == "m":
            db.reference("search_photo/m").update(value)
        else:
            db.reference("search_photo/" + name).set(value)
    db.reference("versions/db_update").set(date.today().isoformat())
    return patch


def _add_apg_live(path, plant_id, rank=None):
    from firebase_admin import db

    db.reference(path + "/list/" + plant_id).set(1)
    listing = db.reference(path + "/list").get() or {}
    db.reference(path + "/count").set(len(listing))
    if rank and not db.reference(path + "/type").get():
        db.reference(path + "/type").set(rank)


def apply_apg_live(packet):
    from firebase_admin import db

    path = apg_tree.ordered_path((packet.get("plants_v2") or {}).get("APGIV") or {})
    plant_id = str(packet["job"]["id"])
    current = "APG IV_v3"
    created = []
    walked = []
    for rank, name in path:
        rel = None
        snapshot = None
        if rank in apg_tree.NESTED_RANKS:
            snapshot = db.reference(current).get() or {}
            if isinstance(snapshot, dict):
                rel = apg_tree.choose_child(snapshot, name, rank)
        if not rel:
            parent_keys = db.reference(current).get(shallow=True) or {}
            if not (isinstance(parent_keys, dict) and name in parent_keys):
                db.reference(current + "/" + name).update(
                    {"type": rank, "count": 0, "list": {}}
                )
                created.append(name)
            rel = [name]
        for index, step in enumerate(rel):
            current = current + "/" + step
            step_rank = rank
            if snapshot is not None:
                node = snapshot
                for part in rel[: index + 1]:
                    node = (node or {}).get(part) or {}
                step_rank = node.get("type") or rank
            _add_apg_live(current, plant_id, step_rank)
            walked.append((step_rank, step))
    return {"created": created, "path": walked}


def write_records(packet):
    from firebase_admin import db

    job = packet["job"]
    latin = job["accepted_name"]
    plant_id = str(job["id"])
    db.reference("plants_v2/" + latin).update(packet["plants_v2"])
    db.reference("plants_headers/" + plant_id).update(packet["plants_header"])
    if packet.get("synonyms"):
        db.reference("synonyms/" + latin).update(packet["synonyms"])
    for language, payload in (packet.get("translations") or {}).items():
        db.reference("translations/%s/%s" % (language, latin)).update(payload)
    db.reference("plants_to_update/list").update({int(job["id"]): latin})
    db.reference("plants_to_update/count").set(int(job["id"]) + 1)
    write_web_catalog(packet)
    today = date.today().isoformat()
    db.reference("lists_custom/new/%s/list" % today).update({plant_id: 1})
    db.reference("lists_custom/new/%s/time" % today).set(-int(time.time() * 1000))
    apply_apg_live(packet)


def write_web_catalog(packet):
    """One-plant web catalog + sourced labels. Same readable `web` tree as UI strings."""
    from firebase_admin import db

    plant_id = str(packet["job"]["id"])
    db.reference(web_catalog.CATALOG_NODE + "/" + plant_id).update(
        web_catalog.entry_from_packet(packet)
    )
    for language, label in web_catalog.labels_from_packet(packet).items():
        db.reference("%s/%s/%s" % (web_catalog.LABELS_NODE, language, plant_id)).set(label)


def write_web_labels(plant_id, translations):
    """Update sourced labels for an existing catalog id (later-language publishes)."""
    from firebase_admin import db

    token = str(plant_id)
    for language, label in web_catalog.labels_from_translations(translations).items():
        db.reference("%s/%s/%s" % (web_catalog.LABELS_NODE, language, token)).set(label)


def apply_web_catalog(catalog, labels):
    """Replace web/catalog and web/labels. Does not touch web/{lang} UI strings."""
    from firebase_admin import db

    if not catalog:
        raise ValueError("refusing to apply empty web catalog")
    db.reference(web_catalog.CATALOG_NODE).set(catalog)
    db.reference(web_catalog.LABELS_NODE).set(labels or {})
    return {
        "entries": len(catalog),
        "label_languages": sorted(labels or {}),
    }


def publish(packet):
    report = refuse(packet)
    if not report["ok"]:
        return report
    upload_media(packet)
    write_records(packet)
    patch = apply_indexes_live(packet)
    report["published"] = True
    report["filter_keys"] = len(patch.get("counts") or {})
    return report
