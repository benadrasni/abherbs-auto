"""Patch live translations/sk for accuracy-review Slovak drafts.

Does not call publish.publish() and does not touch plants_v2 or filter indexes.
Search name changes are a remove-old / add-new diff.

Usage (from ingest, venv python):
  python apply_slovak_translations.py --dir DIR
  python apply_slovak_translations.py --dir DIR --apply
"""

from __future__ import print_function

import argparse
import json
import os
import sys
from datetime import date

import catalog_indexes
import constants

BODY = (
    "description",
    "flower",
    "inflorescence",
    "fruit",
    "leaf",
    "stem",
    "habitat",
)


def load_drafts(folder):
    drafts = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        stem = name[:-5]
        plant_id, latin = stem.split("_", 1)
        latin = latin.replace("_", " ")
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        missing = [field for field in BODY if not (payload.get(field) or "").strip()]
        if missing:
            raise SystemExit("%s missing body fields: %s" % (name, missing))
        if not payload.get("label"):
            raise SystemExit("%s missing label" % name)
        drafts.append({
            "id": int(plant_id),
            "name": latin,
            "payload": payload,
            "_path": path,
        })
    return drafts


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


def merged_sk(live, draft):
    out = dict(live or {})
    extra = draft.get("names") or []
    if isinstance(extra, dict):
        extra = [value for value in extra.values() if value]
    else:
        extra = [name for name in extra if name]
    out["label"] = draft["label"]
    out["names"] = extra
    if draft.get("sourceUrls") is not None:
        out["sourceUrls"] = draft.get("sourceUrls") or []
    for field in BODY:
        out[field] = draft[field]
    if draft.get("wikipedia"):
        out["wikipedia"] = draft["wikipedia"]
    elif "wikipedia" in draft and draft.get("wikipedia") in (None, ""):
        out.pop("wikipedia", None)
    if draft.get("toxicity"):
        out["toxicity"] = draft["toxicity"]
    elif "toxicity" in draft and draft.get("toxicity") in (None, ""):
        out.pop("toxicity", None)
    return out


def plan_one(db, draft):
    latin = draft["name"]
    token = str(draft["id"])
    live = db.reference("translations/sk/" + latin).get() or {}
    new = merged_sk(live, draft["payload"])
    old_names = search_names(live)
    new_names = search_names(new)
    return {
        "id": draft["id"],
        "token": token,
        "name": latin,
        "live": live,
        "new": new,
        "names_add": sorted(new_names - old_names),
        "names_remove": sorted(old_names - new_names),
        "label_old": live.get("label"),
        "label_new": new.get("label"),
        "had_live": bool(live),
    }


def print_plan(plan):
    print("==== %s (%s) ====" % (plan["name"], plan["id"]))
    if not plan["had_live"]:
        print("  new SK node")
    if plan["label_old"] != plan["label_new"]:
        print("  label: %r -> %r" % (plan["label_old"], plan["label_new"]))
    if plan["names_add"] or plan["names_remove"]:
        print("  search names +%s -%s" % (plan["names_add"], plan["names_remove"]))


def apply_plan(db, plan):
    latin = plan["name"]
    token = plan["token"]
    db.reference("translations/sk/" + latin).set(plan["new"])
    for name in plan["names_remove"]:
        if catalog_indexes.is_illegal_search_key(name):
            continue
        db.reference("search_v3/sk/%s/list/%s" % (name, token)).delete()
    for name in plan["names_add"]:
        if catalog_indexes.is_illegal_search_key(name):
            continue
        db.reference("search_v3/sk/%s/list" % name).update({token: 1})
    if plan["label_old"] != plan["label_new"] and plan["label_new"]:
        db.reference("web/labels/sk/" + token).set(plan["label_new"])
    return plan["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    drafts = load_drafts(args.dir)
    if not drafts:
        print("no drafts in", args.dir, file=sys.stderr)
        return 1

    db = init_firebase()
    plans = [plan_one(db, draft) for draft in drafts]
    for plan in plans:
        print_plan(plan)
    print("plants", len(plans))

    if not args.apply:
        print("dry-run only; pass --apply to write")
        return 0

    for plan in plans:
        apply_plan(db, plan)
    db.reference("versions/db_update").set(date.today().isoformat())
    print("applied", len(plans), "SK plants; versions/db_update set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
