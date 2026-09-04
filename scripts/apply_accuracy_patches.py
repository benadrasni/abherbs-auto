"""Patch live plants_v2 / translations/en / headers for accuracy fixes.

Does not call publish.publish() and does not touch plants_to_update.
Filter index changes are a remove-old / add-new diff so counts do not double.

Usage (from ingest, venv python):
  python -m scripts.apply_accuracy_patches --dir DIR            # dry-run
  python -m scripts.apply_accuracy_patches --dir DIR --apply    # write live
"""

from __future__ import print_function

import argparse
import json
import os
import sys
from datetime import date

from catalog import catalog_indexes
import constants


def load_patches(folder):
    patches = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as handle:
            patch = json.load(handle)
        patch["_path"] = path
        patches.append(patch)
    return patches


LIVE_EN_KEEP = ("trivia", "herbalism")


def carry_live_optional_fields(live_en, new_en, fields=LIVE_EN_KEEP):
    """Keep live English optional fields on a full translations/en replace."""
    if new_en is None:
        return new_en
    out = dict(new_en)
    live = live_en or {}
    for field in fields:
        value = live.get(field)
        if value:
            out[field] = value
    return out


def carry_live_trivia(live_en, new_en):
    """Keep live English trivia on a full translations/en replace."""
    return carry_live_optional_fields(live_en, new_en, fields=("trivia",))


def search_names(translation):
    names = set()
    if not translation:
        return names
    label = translation.get("label")
    if label:
        names.add(label.lower())
    extra = translation.get("names") or []
    if isinstance(extra, dict):
        extra = list(extra.values())
    for name in extra:
        if name:
            names.add(name.lower())
    return names


def init_firebase():
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})
    from firebase_admin import db

    return db


def plan_patch(db, patch):
    plant_id = int(patch["id"])
    latin = patch["name"]
    token = str(plant_id)
    live_header = db.reference("plants_headers/" + token).get() or {}
    live_v2 = db.reference("plants_v2/" + latin).get() or {}
    live_en = db.reference("translations/en/" + latin).get() or {}

    new_header = dict(live_header)
    new_header.update(patch.get("header") or {})
    old_keys = set(catalog_indexes.matching_keys(live_header)) if live_header else set()
    new_keys = set(catalog_indexes.matching_keys(new_header)) if new_header else set()

    old_names = search_names(live_en)
    new_en = patch.get("translations_en")
    if new_en is not None:
        new_en = carry_live_optional_fields(live_en, new_en)
    new_names = search_names(new_en) if new_en is not None else old_names

    return {
        "id": plant_id,
        "token": token,
        "name": latin,
        "live_header": live_header,
        "new_header": new_header,
        "live_v2": live_v2,
        "v2_updates": patch.get("plants_v2") or {},
        "live_en": live_en,
        "new_en": new_en,
        "keys_add": sorted(new_keys - old_keys),
        "keys_remove": sorted(old_keys - new_keys),
        "names_add": sorted(new_names - old_names),
        "names_remove": sorted(old_names - new_names),
        "label_old": live_en.get("label"),
        "label_new": (new_en or {}).get("label") if new_en is not None else live_en.get("label"),
        "changelog": patch.get("changelog") or [],
    }


def print_plan(plan):
    print("==== %s (%s) ====" % (plan["name"], plan["id"]))
    for line in plan["changelog"]:
        print("  -", line)
    if plan["v2_updates"]:
        print("  plants_v2:", plan["v2_updates"])
    header_delta = {
        key: plan["new_header"].get(key)
        for key in ("filterColor", "filterHabitat", "filterPetal", "filterDistribution")
        if plan["live_header"].get(key) != plan["new_header"].get(key)
    }
    if header_delta:
        print("  header:", header_delta)
    print("  filter keys +%s -%s" % (len(plan["keys_add"]), len(plan["keys_remove"])))
    if plan["names_add"] or plan["names_remove"]:
        print("  search names +%s -%s" % (plan["names_add"], plan["names_remove"]))
    if plan["label_old"] != plan["label_new"]:
        print("  web label: %r -> %r" % (plan["label_old"], plan["label_new"]))
    for field in LIVE_EN_KEEP:
        if (plan["live_en"] or {}).get(field):
            print("  %s: kept" % field)


def apply_plan(db, plan):
    latin = plan["name"]
    token = plan["token"]
    plant_id = plan["id"]

    if plan["v2_updates"]:
        db.reference("plants_v2/" + latin).update(plan["v2_updates"])

    header_delta = {
        key: plan["new_header"][key]
        for key in ("filterColor", "filterHabitat", "filterPetal", "filterDistribution")
        if key in plan["new_header"] and plan["live_header"].get(key) != plan["new_header"].get(key)
    }
    if header_delta:
        db.reference("plants_headers/" + token).update(header_delta)

    if plan["new_en"] is not None:
        db.reference("translations/en/" + latin).set(plan["new_en"])

    for key in plan["keys_remove"]:
        listing = db.reference("lists_4_v2/" + key).get() or {}
        if catalog_indexes.listing_has_token(listing, token):
            db.reference("lists_4_v2/%s/%s" % (key, token)).delete()
            current = db.reference("counts_4_v2/" + key).get() or 0
            db.reference("counts_4_v2/" + key).set(max(0, int(current) - 1))

    for key in plan["keys_add"]:
        current = db.reference("counts_4_v2/" + key).get() or 0
        db.reference("counts_4_v2/" + key).set(int(current) + 1)
        db.reference("lists_4_v2/" + key).update({token: 1})

    for name in plan["names_remove"]:
        if catalog_indexes.is_illegal_search_key(name):
            continue
        db.reference("search_v3/en/%s/list/%s" % (name, token)).delete()

    for name in plan["names_add"]:
        if catalog_indexes.is_illegal_search_key(name):
            continue
        db.reference("search_v3/en/%s/list" % name).update({token: 1})

    if plan["label_old"] != plan["label_new"]:
        if plan["label_new"]:
            db.reference("web/labels/en/" + token).set(plan["label_new"])
        else:
            db.reference("web/labels/en/" + token).delete()

    return {
        "id": plant_id,
        "name": latin,
        "keys_add": len(plan["keys_add"]),
        "keys_remove": len(plan["keys_remove"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    patches = load_patches(args.dir)
    if not patches:
        print("no patches in", args.dir, file=sys.stderr)
        return 1

    db = init_firebase()
    plans = [plan_patch(db, patch) for patch in patches]
    for plan in plans:
        print_plan(plan)

    if not args.apply:
        print("dry-run only; pass --apply to write")
        return 0

    reports = []
    for plan in plans:
        reports.append(apply_plan(db, plan))
    db.reference("versions/db_update").set(date.today().isoformat())
    print("applied", len(reports), "plants; versions/db_update set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
