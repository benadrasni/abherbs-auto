"""Classify live English inflorescence text onto plants_v2.inflorescenceType.

Dry-run by default. Writes a local mapping, then --apply patches live
plants_v2/{name}/inflorescenceType only (no other fields).

Usage (from ingest, venv python):
  python -m scripts.fill_inflorescence_type
  python -m scripts.fill_inflorescence_type --apply
"""

from __future__ import print_function

import argparse
import json
import os
import sys
from collections import Counter

import constants
from plant.inflorescence_type import TYPES, classify
from sources import catalog_rest


def mapping_path():
    return os.path.join(constants.plantsdir, "_jobs", "_inflorescence_type", "mapping.json")


def load_english_inflorescences():
    print("fetching translations/en …")
    payload = catalog_rest.get("translations/en", timeout=180) or {}
    out = {}
    for name, row in payload.items():
        if not isinstance(row, dict):
            continue
        text = row.get("inflorescence") or ""
        if isinstance(text, str):
            out[name] = text
    return out


def build_mapping(catalog, english):
    names = list(catalog.get("list") or [])
    rows = []
    for name in names:
        text = english.get(name) or ""
        types = classify(text)
        rows.append({"name": name, "inflorescenceType": types, "text": text})
    return rows


def print_stats(rows):
    counts = Counter()
    empty = 0
    multi = 0
    for row in rows:
        types = row["inflorescenceType"]
        if not types:
            empty += 1
            continue
        if len(types) > 1:
            multi += 1
        counts[types[0]] += 1
    print("plants: %s" % len(rows))
    print("with type: %s" % (len(rows) - empty))
    print("empty: %s" % empty)
    print("multiple: %s" % multi)
    print("primary:")
    for key in TYPES:
        n = counts.get(key, 0)
        if n:
            print("  %s: %s" % (key, n))
    leftover = sorted(counts.keys() - set(TYPES))
    for key in leftover:
        print("  %s: %s" % (key, counts[key]))


def save_mapping(rows):
    path = mapping_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    slim = [{"name": row["name"], "inflorescenceType": row["inflorescenceType"]} for row in rows]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(slim, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("wrote %s" % path)
    return path


def apply_mapping(rows):
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import db

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})

    chunk = 400
    written = 0
    for start in range(0, len(rows), chunk):
        batch = {}
        for row in rows[start : start + chunk]:
            path = "plants_v2/%s/inflorescenceType" % row["name"]
            batch[path] = row["inflorescenceType"]
        db.reference().update(batch)
        written += len(batch)
        print("wrote %s / %s" % (written, len(rows)))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write plants_v2.inflorescenceType")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    catalog = catalog_rest.plants_to_update()
    english = load_english_inflorescences()
    rows = build_mapping(catalog, english)
    print_stats(rows)
    save_mapping(rows)
    missing_en = [row["name"] for row in rows if not (english.get(row["name"]) or "").strip()]
    if missing_en:
        print("no English inflorescence: %s" % len(missing_en))
        for name in missing_en[:12]:
            print("  %s" % name)
    if not args.apply:
        print("Firebase untouched. Re-run with --apply to write inflorescenceType.")
        return 0
    apply_mapping(rows)
    print("applied inflorescenceType on %s plants" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
