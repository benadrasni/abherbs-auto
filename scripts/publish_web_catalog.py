"""Build the slim website catalog from a dump or live RTDB. Writes only with --apply."""

import argparse
import json
import os
import sys

from catalog import refresh as refresh_indexes
from catalog import web_catalog
from sources import catalog_rest


def _write_json(path, payload):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def fetch_live(dest):
    """Download the public nodes needed to rebuild web/catalog + web/labels."""
    os.makedirs(os.path.join(dest, "translations"), exist_ok=True)
    plants = catalog_rest.plants_to_update()
    _write_json(os.path.join(dest, "plants_to_update.json"), plants)
    headers = catalog_rest.get("plants_headers", timeout=180)
    _write_json(os.path.join(dest, "plants_headers.json"), headers)
    plants_v2 = web_catalog.slim_plants_v2(catalog_rest.get("plants_v2", timeout=300) or {})
    _write_json(os.path.join(dest, "plants_v2.json"), plants_v2)
    for language in sorted(web_catalog.LABEL_LANGUAGES):
        payload = catalog_rest.get("translations/" + language, timeout=180)
        if payload:
            _write_json(os.path.join(dest, "translations", language + ".json"), payload)
    return dest


def build_from_dir(input_dir):
    catalog = refresh_indexes.load_catalog(input_dir, ("web",))
    built, labels, warnings = web_catalog.build_catalog(
        catalog["plant_names"],
        catalog.get("headers"),
        catalog.get("plants_v2") or {},
        catalog.get("translations") or {},
    )
    summary = web_catalog.summarize(built, labels, expected=len(catalog["plant_names"]))
    summary["warnings"] = warnings
    summary["plants"] = len(catalog["plant_names"])
    return built, labels, summary


def print_summary(summary):
    print("plants: %s" % summary.get("plants"))
    print("web catalog: %s" % summary["entries"])
    print("covers expected: %s" % summary["covers_expected"])
    print("english labels: %s" % summary["english_labels"])
    langs = summary.get("label_languages") or []
    print("label languages: %s" % (",".join(langs) if langs else "(none)"))
    print("missing name: %s" % len(summary.get("missing_name") or []))
    print("missing family: %s" % len(summary.get("missing_family") or []))
    print("missing illustration: %s" % len(summary.get("missing_illustration") or []))
    for token in (summary.get("missing_illustration") or [])[:12]:
        print("  no plate: id %s" % token)
    for warning in summary.get("warnings") or []:
        print("  warning: %s" % warning)


def _init_admin():
    import firebase_admin
    from firebase_admin import credentials

    import constants

    if not firebase_admin._apps:
        cred = credentials.Certificate(constants.certificate_firebase)
        firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Rebuild web/catalog and web/labels. Default is dry-run."
    )
    parser.add_argument(
        "--input-dir",
        help="Directory with plants_to_update.json, plants_headers.json, "
             "plants_v2.json, translations/",
    )
    parser.add_argument(
        "--from-live",
        action="store_true",
        help="Download the public catalog into --input-dir (or a temp dir)",
    )
    parser.add_argument(
        "--output-dir",
        help="Write web_catalog_new.json and web_labels_new/ here",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Replace live web/catalog and web/labels (explicit Firebase write)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    input_dir = args.input_dir
    if args.from_live:
        if not input_dir:
            import tempfile

            input_dir = tempfile.mkdtemp(prefix="web_catalog_")
        print("fetching live catalog into %s" % os.path.abspath(input_dir))
        fetch_live(input_dir)
    if not input_dir:
        print("need --input-dir or --from-live", file=sys.stderr)
        return 2

    catalog, labels, summary = build_from_dir(input_dir)
    print_summary(summary)

    if args.output_dir:
        refresh_indexes.write_result(
            args.output_dir,
            {
                "web_catalog": catalog,
                "web_labels": labels,
                "warnings": summary.get("warnings") or [],
            },
        )
        print("wrote %s" % os.path.abspath(args.output_dir))

    if not args.apply:
        print("dry-run (Firebase untouched). Pass --apply to write web/catalog and web/labels.")
        return 0 if summary["covers_expected"] else 1

    if not summary["covers_expected"]:
        print("refusing --apply: catalog does not cover the plant list", file=sys.stderr)
        return 2
    if summary.get("missing_name"):
        print("refusing --apply: catalog rows missing names", file=sys.stderr)
        return 2

    _init_admin()
    from catalog import publish

    result = publish.apply_web_catalog(catalog, labels)
    print("applied web/catalog (%s) and web/labels (%s languages)" % (
        result["entries"],
        len(result["label_languages"]),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
