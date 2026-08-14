"""TDWG level-3 → level-2 map from ingest/tdwg.csv.

Matches add_plant.add_plant_header: while reading the file, the current L2
code is remembered and applied to following L3 rows. Names are keyed with
the first 20 characters of the area name (POWO scrape leftover) and also
by the 3-letter L3 code.
"""

import os

_CACHE = None


def _csv_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "tdwg.csv")


def load(path=None):
    global _CACHE
    if path is None and _CACHE is not None:
        return _CACHE

    by_code = {}
    by_name = {}
    l2_code = None
    filepath = path or _csv_path()
    with open(filepath, encoding="utf-8") as handle:
        for line in handle:
            items = [part.strip() for part in line.split(",")]
            if len(items) < 4:
                continue
            level = items[1]
            if level == "L2":
                l2_code = int(items[2])
            elif level == "L3" and l2_code is not None:
                code = items[2]
                name = items[3]
                by_code[code.upper()] = l2_code
                by_name[name[:20]] = l2_code
                by_name[name.lower()[:20]] = l2_code

    mapping = {"by_code": by_code, "by_name": by_name}
    if path is None:
        _CACHE = mapping
    return mapping


def l2_for_l3_code(code, mapping=None):
    if not code:
        return None
    mapping = mapping or load()
    return mapping["by_code"].get(str(code).strip().upper())


def l2_for_l3_name(name, mapping=None):
    if not name:
        return None
    mapping = mapping or load()
    stripped = name.strip()
    return mapping["by_name"].get(stripped[:20]) or mapping["by_name"].get(
        stripped.lower()[:20]
    )


def l2_codes_for_l3(values, mapping=None):
    """Map a mix of L3 codes and names to sorted unique L2 ints. Skip unknowns."""
    mapping = mapping or load()
    result = []
    seen = set()
    for value in values:
        l2 = l2_for_l3_code(value, mapping)
        if l2 is None:
            l2 = l2_for_l3_name(value, mapping)
        if l2 is None or l2 in seen:
            continue
        seen.add(l2)
        result.append(l2)
    result.sort()
    return result
