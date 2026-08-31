"""Remove leftover lists_4_v2 ids that no longer match plant headers.

Does not change counts_4_v2: those already match headers. Caused by
apply_accuracy_patches treating Firebase array-shaped lists as dicts, so
keys_remove decremented the count and left the list row.

Usage (from ingest, venv python):
  python -m scripts.repair_filter_lists            # dry-run
  python -m scripts.repair_filter_lists --apply    # write live
"""

from __future__ import print_function

import argparse
import sys
from collections import defaultdict
from datetime import date

from catalog import catalog_indexes
from sources import catalog_rest


def listing_memberships(lists):
    actual = defaultdict(set)
    for key, listing in (lists or {}).items():
        for token in catalog_indexes.listing_ids(listing):
            actual[token].add(key)
    return actual


def find_extras(names, headers, lists):
    actual = listing_memberships(lists)
    extras = []
    for index, name in enumerate(names):
        header = catalog_indexes.header_at(headers, index)
        if not header:
            continue
        expected = set(catalog_indexes.matching_keys(header))
        leftover = sorted(actual.get(str(index), set()) - expected)
        for key in leftover:
            extras.append({"id": index, "name": name, "key": key})
    return extras


def init_firebase():
    import firebase_admin
    from firebase_admin import credentials
    import constants

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})
    from firebase_admin import db

    return db


def apply_extras(db, extras):
    by_key = defaultdict(list)
    for row in extras:
        by_key[row["key"]].append(str(row["id"]))
    for key, tokens in sorted(by_key.items()):
        payload = {token: None for token in tokens}
        db.reference("lists_4_v2/" + key).update(payload)
        print("removed", len(tokens), "from", key)
    return len(extras)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    print("fetching live catalog...", flush=True)
    catalog = catalog_rest.plants_to_update()
    names = catalog.get("list") or []
    headers = catalog_rest.get("plants_headers") or []
    lists = catalog_rest.get("lists_4_v2") or {}
    extras = find_extras(names, headers, lists)

    by_key = defaultdict(list)
    by_plant = defaultdict(list)
    for row in extras:
        by_key[row["key"]].append(row["id"])
        by_plant[(row["id"], row["name"])].append(row["key"])

    print("plants with leftover list rows:", len(by_plant))
    print("leftover memberships:", len(extras))
    for key in sorted(by_key):
        print("  %s: %s" % (key, len(by_key[key])))
    for (plant_id, name), keys in sorted(by_plant.items()):
        print("  %s %s %s" % (plant_id, name, keys))

    if not extras:
        print("nothing to repair")
        return 0
    if not args.apply:
        print("dry-run only; pass --apply to write")
        return 0

    db = init_firebase()
    apply_extras(db, extras)
    db.reference("versions/db_update").set(date.today().isoformat())
    print("applied", len(extras), "list deletes; versions/db_update set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
