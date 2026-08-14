"""Copy staging indexes to live nodes. Default is dry-run. No write unless --apply."""

import argparse
import json
import os
import sys
from datetime import date

STAGING_TO_LIVE = (
    ("counts_new", "counts_4_v2"),
    ("lists_new", "lists_4_v2"),
    ("search_new", "search_v3"),
    ("search_photo_new", "search_photo"),
)


def load_patch(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def summarize(patch):
    search = patch.get("search") or {}
    return {
        "plant": patch.get("name"),
        "id": patch.get("plant_id"),
        "filter_keys": patch.get("filter_key_count") or len(patch.get("counts") or {}),
        "search_languages": sorted(search.keys()),
        "photo_keys": len(patch.get("search_photo") or {}),
    }


def _init_admin():
    import firebase_admin
    from firebase_admin import credentials

    import constants

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})


def apply_patch_staging(patch):
    """Merge a one-plant patch into *_new only. Does not touch live indexes."""
    from firebase_admin import db

    _init_admin()
    plant_id = str(patch["plant_id"])
    for key, delta in (patch.get("counts") or {}).items():
        ref = db.reference("counts_new/" + key)
        current = ref.get() or 0
        ref.set(int(current) + int(delta))
        db.reference("lists_new/" + key).update({plant_id: 1})

    for language, payload in (patch.get("search") or {}).items():
        for name, value in payload.items():
            db.reference("search_new/%s/%s" % (language, name)).update(value)

    for name, value in (patch.get("search_photo") or {}).items():
        if name == "m":
            db.reference("search_photo_new/m").update(value)
        else:
            db.reference("search_photo_new/" + name).set(value)


def apply_patch_admin(patch):
    """Admin SDK merge of a one-plant patch into staging, then copy to live."""
    from firebase_admin import db

    apply_patch_staging(patch)
    for staging, live in STAGING_TO_LIVE:
        staged = db.reference(staging).get()
        if staged is not None:
            db.reference(live).update(staged if isinstance(staged, dict) else {".value": staged})

    db.reference("versions/db_update").set(date.today().isoformat())


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Promote staging catalog indexes. Default: dry-run, no Firebase."
    )
    parser.add_argument("--patch", help="index_patch.json from add_species")
    parser.add_argument("--apply", action="store_true", help="Write Firebase (explicit)")
    parser.add_argument(
        "--staging-only",
        action="store_true",
        help="With --apply, write *_new only (do not copy staging to live)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if not args.patch:
        print("usage: promote_indexes.py --patch /path/to/index_patch.json", file=sys.stderr)
        return 2
    patch = load_patch(args.patch)
    summary = summarize(patch)
    print("plant: %s (id %s)" % (summary["plant"], summary["id"]))
    print("filter keys: %s" % summary["filter_keys"])
    print("search languages: %s" % ",".join(summary["search_languages"]))
    print("photo keys: %s" % summary["photo_keys"])
    if not args.apply:
        print("dry-run (Firebase untouched). Pass --apply to write.")
        return 0
    if args.staging_only:
        apply_patch_staging(patch)
        print("applied staging *_new only; live indexes untouched")
        return 0
    apply_patch_admin(patch)
    print("applied staging + live copy; versions/db_update set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
