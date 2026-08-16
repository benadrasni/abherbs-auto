"""Local rebuild of Refresher.java indexes plus the slim website catalog.

Reads a catalog dump from disk and writes counts/lists/search/photo JSON
and web_catalog_new / web_labels_new. Does not import firebase_admin and
does not write to Realtime Database.
"""

import argparse
import json
import os
import sys

import catalog_indexes
import web_catalog


STAGES = ("counts", "search", "photo", "web")


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, payload):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))


def normalize_plant_list(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if not isinstance(raw, dict):
        raise ValueError("plants_to_update must be a list or object")
    if "list" in raw:
        return normalize_plant_list(raw["list"])
    items = []
    for key, value in raw.items():
        if key == "count":
            continue
        items.append((int(key) if str(key).isdigit() else key, value))
    items.sort(key=lambda item: item[0])
    return [value for _, value in items]


def load_translations(input_dir):
    bundled = os.path.join(input_dir, "translations.json")
    if os.path.isfile(bundled):
        payload = _load_json(bundled)
        if not isinstance(payload, dict):
            raise ValueError("translations.json must be an object of language -> plants")
        return payload

    directory = os.path.join(input_dir, "translations")
    translations = {}
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if not name.endswith(".json"):
                continue
            language = name[:-5]
            translations[language] = _load_json(os.path.join(directory, name))
    return translations


def load_catalog(input_dir, stages):
    catalog = {}
    plants_path = os.path.join(input_dir, "plants_to_update.json")
    if not os.path.isfile(plants_path):
        raise FileNotFoundError("missing %s" % plants_path)
    catalog["plant_names"] = normalize_plant_list(_load_json(plants_path))

    if "counts" in stages:
        headers_path = os.path.join(input_dir, "plants_headers.json")
        if not os.path.isfile(headers_path):
            raise FileNotFoundError("missing %s" % headers_path)
        catalog["headers"] = _load_json(headers_path)

    if "search" in stages or "photo" in stages or "web" in stages:
        plants_v2_path = os.path.join(input_dir, "plants_v2.json")
        catalog["plants_v2"] = _load_json(plants_v2_path) if os.path.isfile(plants_v2_path) else {}

    if "search" in stages or "web" in stages:
        catalog["translations"] = load_translations(input_dir)

    if "web" in stages:
        headers_path = os.path.join(input_dir, "plants_headers.json")
        if "headers" not in catalog:
            if not os.path.isfile(headers_path):
                raise FileNotFoundError("missing %s" % headers_path)
            catalog["headers"] = _load_json(headers_path)

    if "photo" in stages:
        apg_path = os.path.join(input_dir, "apg_iv_v3.json")
        if not os.path.isfile(apg_path):
            raise FileNotFoundError("missing %s" % apg_path)
        catalog["apg_iv"] = _load_json(apg_path)

    return catalog


def refresh(catalog, stages):
    result = {"warnings": []}

    if "counts" in stages:
        counts, lists, warnings = catalog_indexes.build_counts_and_lists(
            catalog["plant_names"], catalog["headers"]
        )
        result["counts"] = counts
        result["lists"] = lists
        result["warnings"].extend(warnings)

    if "search" in stages:
        search, warnings = catalog_indexes.build_search_all_languages(
            catalog["plant_names"], catalog.get("translations") or {}
        )
        latin, latin_warnings = catalog_indexes.build_search_latin(
            catalog["plant_names"], catalog.get("plants_v2") or {}
        )
        search["la"] = latin
        result["search"] = search
        result["warnings"].extend(warnings)
        result["warnings"].extend(latin_warnings)

    if "photo" in stages:
        photo, warnings = catalog_indexes.build_photo_search(
            catalog["plant_names"],
            catalog.get("plants_v2") or {},
            catalog.get("apg_iv"),
        )
        result["photo"] = photo
        result["warnings"].extend(warnings)

    if "web" in stages:
        catalog_map, labels, warnings = web_catalog.build_catalog(
            catalog["plant_names"],
            catalog.get("headers"),
            catalog.get("plants_v2") or {},
            catalog.get("translations") or {},
        )
        result["web_catalog"] = catalog_map
        result["web_labels"] = labels
        result["warnings"].extend(warnings)

    return result


def write_result(output_dir, result):
    os.makedirs(output_dir, exist_ok=True)

    if "counts" in result:
        _write_json(os.path.join(output_dir, "counts_new.json"), result["counts"])
        _write_json(os.path.join(output_dir, "lists_new.json"), result["lists"])

    if "search" in result:
        search_dir = os.path.join(output_dir, "search_new")
        for language, payload in result["search"].items():
            _write_json(os.path.join(search_dir, language + ".json"), payload)

    if "photo" in result:
        _write_json(os.path.join(output_dir, "search_photo_new.json"), result["photo"])

    if "web_catalog" in result:
        _write_json(os.path.join(output_dir, "web_catalog_new.json"), result["web_catalog"])
        labels_dir = os.path.join(output_dir, "web_labels_new")
        for language, payload in (result.get("web_labels") or {}).items():
            _write_json(os.path.join(labels_dir, language + ".json"), payload)

    summary = {
        "count_keys": len(result["counts"]) if "counts" in result else None,
        "list_keys": len(result["lists"]) if "lists" in result else None,
        "search_languages": sorted(result["search"].keys()) if "search" in result else None,
        "photo_keys": len(result["photo"]) if "photo" in result else None,
        "web_entries": len(result["web_catalog"]) if "web_catalog" in result else None,
        "web_label_languages": (
            sorted((result.get("web_labels") or {}).keys())
            if "web_catalog" in result
            else None
        ),
        "warning_count": len(result["warnings"]),
        "warnings": result["warnings"],
        "firebase_writes": False,
    }
    _write_json(os.path.join(output_dir, "summary.json"), summary)
    return summary


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Rebuild catalog indexes locally. Never writes to Firebase."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory with plants_to_update.json, plants_headers.json, "
             "plants_v2.json, translations/, apg_iv_v3.json",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for counts_new.json, lists_new.json, search_new/, "
             "search_photo_new.json, web_catalog_new.json, web_labels_new/",
    )
    parser.add_argument(
        "--only",
        choices=STAGES,
        action="append",
        help="Build one stage (repeatable). Default: all stages.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    stages = tuple(args.only) if args.only else STAGES
    catalog = load_catalog(args.input_dir, stages)
    result = refresh(catalog, stages)
    summary = write_result(args.output_dir, result)
    summary["plants"] = len(catalog["plant_names"])

    print("plants: %s" % summary["plants"])
    if summary["count_keys"] is not None:
        print("count keys: %s" % summary["count_keys"])
        print("list keys: %s" % summary["list_keys"])
    if summary["search_languages"] is not None:
        print("search languages: %s" % ",".join(summary["search_languages"]))
    if summary["photo_keys"] is not None:
        print("photo keys: %s" % summary["photo_keys"])
    if summary.get("web_entries") is not None:
        print("web catalog: %s" % summary["web_entries"])
        langs = summary.get("web_label_languages") or []
        if langs:
            print("web label languages: %s" % ",".join(langs))
    print("warnings: %s" % summary["warning_count"])
    for warning in summary["warnings"]:
        print("  %s" % warning)
    print("wrote %s (Firebase untouched)" % os.path.abspath(args.output_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
