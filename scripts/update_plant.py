"""Dump live English/filters and botanical-source hints for a catalog species.

Does not write Firebase. Rewrite English, then apply with
scripts.apply_accuracy_patches (filter keys are a remove-old/add-new diff).

Usage (from ingest, venv python):
  python -m scripts.update_plant "Genus epithet"
  python -m scripts.update_plant 56
  python -m scripts.update_plant 56 "Arnica montana" --no-fetch
"""

from __future__ import print_function

import argparse
import os
import sys

import constants
from plant import assemble
from sources import botanical
from sources import catalog_rest
from sources import wikipedia as wiki_api
from sources import wcvp


def slug(latin):
    return (latin or "").replace(" ", "_")


def job_dir(plant_id, latin):
    return os.path.join(
        constants.plantsdir,
        "_jobs",
        "_update",
        "%s_%s" % (plant_id, slug(latin)),
    )


def parse_item(token):
    text = str(token).strip()
    if text.isdigit():
        return int(text)
    return text


def _catalog_id_ci(name, catalog):
    idx = catalog_rest.catalog_id(name, catalog)
    if idx is not None:
        return idx
    want = (name or "").strip().lower()
    if not want:
        return None
    for i, live in enumerate(catalog.get("list") or []):
        if (live or "").lower() == want:
            return i
    return None


def resolve_catalog(item, catalog, lookup=None):
    """Map a Latin name or plants_to_update index to the live catalog key.

    Keeps the Firebase key even when WCVP accepts a different binomial.
    lookup is wcvp.lookup (injectable for tests).
    """
    names = list(catalog.get("list") or [])
    if isinstance(item, int):
        if 0 <= item < len(names):
            return {"id": item, "name": names[item], "query": item}
        return None

    name = (item or "").strip()
    if not name:
        return None
    idx = _catalog_id_ci(name, catalog)
    if idx is not None:
        return {"id": idx, "name": names[idx], "query": name}

    finder = lookup or wcvp.lookup
    try:
        row = finder(name)
    except Exception:
        row = None
    if not row:
        return None
    for candidate in (row.get("accepted_name"), row.get("query_name")):
        if not candidate or candidate == name:
            continue
        idx = _catalog_id_ci(candidate, catalog)
        if idx is not None:
            hit = {
                "id": idx,
                "name": names[idx],
                "query": name,
                "wcvp_accepted": row.get("accepted_name"),
            }
            if names[idx] != row.get("accepted_name"):
                hit["note"] = (
                    "catalog key is not the WCVP accepted name; do not rename"
                )
            return hit
    return None


def _wcvp_brief(row):
    if not row:
        return None
    return {
        "query_name": row.get("query_name"),
        "query_status": row.get("query_status"),
        "accepted_name": row.get("accepted_name"),
        "author": row.get("author"),
        "rank": row.get("rank"),
        "status": row.get("status"),
        "family": row.get("family"),
        "genus": row.get("genus"),
        "lifeform": row.get("lifeform"),
        "l2": list(row.get("l2") or []),
        "native_l2": list(row.get("native_l2") or []),
        "introduced_l2": list(row.get("introduced_l2") or []),
        "native_l3": list(row.get("native_l3") or []),
        "introduced_l3": list(row.get("introduced_l3") or []),
    }


def fetch_extracts(latin, family, lifeform, native_l2, native_l3, wikipedia_url=None):
    extracts = []
    try:
        extracts.extend(
            botanical.fetch_for(
                latin,
                family=family,
                lifeform=lifeform,
                native_l2=native_l2,
                native_l3=native_l3,
            )
            or []
        )
    except Exception as exc:
        extracts.append({"id": "botanical", "error": str(exc)})
    title = wiki_api.title_from_url(wikipedia_url) or latin
    try:
        wiki = wiki_api.fetch_extract(title)
    except Exception as exc:
        wiki = None
        extracts.append({"id": "wikipedia", "error": str(exc)})
    if wiki:
        extracts.append(
            {
                "id": "wikipedia",
                "name": "English Wikipedia",
                "url": wiki.get("url") or wikipedia_url,
                "title": wiki.get("title") or title,
                "extract": wiki.get("extract") or "",
            }
        )
    return extracts


def dump_one(item, catalog, fetch=True, lookup=None):
    resolved = resolve_catalog(item, catalog, lookup=lookup)
    if not resolved:
        return {"ok": False, "query": item, "error": "not in plants_to_update"}

    latin = resolved["name"]
    plant_id = resolved["id"]
    dest = job_dir(plant_id, latin)
    finder = lookup or wcvp.lookup
    try:
        wcvp_row = finder(latin)
    except Exception:
        wcvp_row = None

    v2 = catalog_rest.get("plants_v2/" + latin) or {}
    header = catalog_rest.get("plants_headers/%s" % plant_id) or {}
    english = catalog_rest.get("translations/en/" + latin) or {}
    brief = _wcvp_brief(wcvp_row)
    family = (header.get("family") or (brief or {}).get("family") or "")
    lifeform = (v2.get("lifeform") or (brief or {}).get("lifeform") or "")
    native_l2 = (brief or {}).get("native_l2") or []
    native_l3 = (brief or {}).get("native_l3") or []

    hints = botanical.hints_for(
        latin,
        family=family,
        lifeform=lifeform,
        native_l2=native_l2,
        native_l3=native_l3,
    )

    live = {
        "id": plant_id,
        "name": latin,
        "query": resolved.get("query"),
        "plants_v2": v2,
        "header": header,
        "translations_en": english,
        "wcvp": brief,
    }
    accepted = (brief or {}).get("accepted_name") or resolved.get("wcvp_accepted")
    if accepted and accepted != latin:
        live["wcvp_accepted"] = accepted
        live["note"] = resolved.get("note") or (
            "catalog key is not the WCVP accepted name; do not rename"
        )
    elif resolved.get("note"):
        live["note"] = resolved["note"]

    assemble.write_json(os.path.join(dest, "_live.json"), live)
    assemble.write_json(os.path.join(dest, "_hints.json"), hints)
    extracts = []
    if fetch:
        extracts = fetch_extracts(
            latin,
            family,
            lifeform,
            native_l2,
            native_l3,
            wikipedia_url=english.get("wikipedia"),
        )
        assemble.write_json(os.path.join(dest, "_extracts.json"), extracts)

    return {
        "ok": True,
        "id": plant_id,
        "name": latin,
        "dir": dest,
        "resolved": resolved,
        "live": live,
        "hints": hints,
        "extracts": extracts,
    }


def print_dump(report):
    if not report.get("ok"):
        print("skip %s: %s" % (report.get("query"), report.get("error")))
        return
    live = report["live"]
    header = live.get("header") or {}
    v2 = live.get("plants_v2") or {}
    brief = live.get("wcvp") or {}
    print("==== %s (%s) ====" % (report["name"], report["id"]))
    if live.get("note"):
        print("  note: %s" % live["note"])
    if brief:
        print(
            "  WCVP: %s %s %s %s"
            % (
                brief.get("accepted_name"),
                brief.get("author") or "",
                brief.get("status") or "",
                brief.get("rank") or "",
            )
        )
        print(
            "  WCVP l2 native %s introduced %s"
            % (brief.get("native_l2"), brief.get("introduced_l2"))
        )
    print(
        "  live color %s habitat %s petal %s"
        % (
            header.get("filterColor"),
            header.get("filterHabitat"),
            header.get("filterPetal"),
        )
    )
    print("  live distribution %s" % header.get("filterDistribution"))
    print(
        "  live height %s–%s flowering %s–%s toxicityClass %s"
        % (
            v2.get("heightFrom"),
            v2.get("heightTo"),
            v2.get("floweringFrom"),
            v2.get("floweringTo"),
            v2.get("toxicityClass"),
        )
    )
    for hint in report.get("hints") or []:
        mark = "reliable" if hint.get("reliable") else hint.get("fetch") or "manual"
        print(
            "  [%s] %s: %s"
            % (mark, hint.get("name"), hint.get("url") or "")
        )
    if report.get("extracts"):
        print(
            "  extracts: %s"
            % ", ".join(
                item.get("id") or "?"
                for item in report["extracts"]
                if not item.get("error")
            )
        )
    print("  wrote %s" % os.path.abspath(report["dir"]))


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Dump live English/filters and botanical source hints."
    )
    parser.add_argument(
        "items",
        nargs="+",
        help="Latin name(s) or plants_to_update indexes",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip latin-lookup downloads and Wikipedia extract",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    catalog = catalog_rest.plants_to_update()
    reports = []
    missing = 0
    for raw in args.items:
        report = dump_one(
            parse_item(raw),
            catalog,
            fetch=not args.no_fetch,
        )
        print_dump(report)
        reports.append(report)
        if not report.get("ok"):
            missing += 1
    if missing:
        print(
            "not in catalog (use /add-plant, or /rename-plant if the key moved): %s"
            % missing
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
