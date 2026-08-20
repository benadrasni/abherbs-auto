"""Dump essential live catalog nodes to ~/whatsthatflower/backup/{stamp}/.

Does not dump users/, observations/, or credits. Re-run anytime:

    python -m scripts.backup_catalog
"""

import argparse
import json
import os
import shutil
from datetime import datetime, timezone

WHOLE_NODES = (
    ("plants_v2", "plants_v2.json"),
    ("plants_headers", "plants_headers.json"),
    ("plants_to_update", "plants_to_update.json"),
    ("families_to_update", "families_to_update.json"),
    ("synonyms", "synonyms.json"),
    ("translations_taxonomy", "translations_taxonomy.json"),
    ("search_photo", "search_photo.json"),
    ("counts_4_v2", "counts_4_v2.json"),
    ("lists_4_v2", "lists_4_v2.json"),
    ("lists_custom", "lists_custom.json"),
    ("APG IV_v3", "apg_iv_v3.json"),
    ("web/catalog", "web_catalog.json"),
    ("versions", "versions.json"),
    ("settings", "settings.json"),
    ("promotions", "promotions.json"),
)

SPLIT_NODES = (
    ("translations", "translations"),
    ("translations_new", "translations_new"),
    ("search_v3", "search_v3"),
    ("web/labels", "web_labels"),
)


def _init_admin():
    import firebase_admin
    from firebase_admin import credentials

    import constants

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})
    from firebase_admin import db

    return db


def _write_json(path, payload):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    return os.path.getsize(path)


def _count(payload):
    if payload is None:
        return 0
    if isinstance(payload, dict):
        return len(payload)
    if isinstance(payload, list):
        return sum(1 for item in payload if item is not None)
    return 1


def default_dest():
    import constants

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
    workspace = os.path.abspath(os.path.join(constants.plantsdir, os.pardir))
    return os.path.join(workspace, "backup", stamp)


def backup(dest):
    import constants

    db = _init_admin()
    os.makedirs(dest, exist_ok=True)
    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "database": "https://abherbs-backend.firebaseio.com",
        "skipped": ["users", "observations", "credits", "users_photo_search"],
        "nodes": {},
    }

    for path, filename in WHOLE_NODES:
        payload = db.reference(path).get()
        if payload is None:
            manifest["nodes"][path] = {"file": filename, "keys": 0, "bytes": 0, "missing": True}
            print("skip missing %s" % path, flush=True)
            continue
        size = _write_json(os.path.join(dest, filename), payload)
        manifest["nodes"][path] = {"file": filename, "keys": _count(payload), "bytes": size}
        print("wrote %s keys=%s bytes=%s" % (filename, manifest["nodes"][path]["keys"], size), flush=True)

    for path, dirname in SPLIT_NODES:
        payload = db.reference(path).get()
        if not isinstance(payload, dict) or not payload:
            manifest["nodes"][path] = {"dir": dirname, "keys": 0, "bytes": 0, "missing": True}
            print("skip missing %s" % path, flush=True)
            continue
        total = 0
        children = {}
        for child, value in payload.items():
            filename = os.path.join(dirname, "%s.json" % child.replace("/", "_"))
            size = _write_json(os.path.join(dest, filename), value)
            total += size
            children[child] = {"file": filename, "keys": _count(value), "bytes": size}
        manifest["nodes"][path] = {
            "dir": dirname,
            "children": len(children),
            "keys": _count(payload),
            "bytes": total,
        }
        print("wrote %s/ children=%s bytes=%s" % (dirname, len(children), total), flush=True)

    workspace = os.path.abspath(os.path.join(constants.plantsdir, os.pardir))
    rules = os.path.join(workspace, "app", "firebase", "database.rules.json")
    if os.path.isfile(rules):
        shutil.copy2(rules, os.path.join(dest, "database.rules.json"))
        manifest["nodes"]["database.rules"] = {
            "file": "database.rules.json",
            "bytes": os.path.getsize(os.path.join(dest, "database.rules.json")),
        }

    _write_json(os.path.join(dest, "MANIFEST.json"), manifest)
    print("backup %s" % dest, flush=True)
    return manifest


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Backup essential RTDB catalog nodes.")
    parser.add_argument(
        "--dest",
        default=None,
        help="Directory to write. Default: ~/whatsthatflower/backup/{UTC stamp}",
    )
    return parser.parse_args(argv)


def main(argv=None):
    import sys

    args = parse_args(argv if argv is not None else sys.argv[1:])
    dest = os.path.abspath(args.dest or default_dest())
    backup(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
