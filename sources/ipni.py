"""IPNI name search. No Firebase."""

from . import httputil
from . import ipni_overrides

SEARCH_URL = "https://www.ipni.org/api/1/search"


def search(name, per_page=5):
    url = SEARCH_URL + "?" + httputil.urlencode(
        {"q": name, "perPage": str(per_page)}
    )
    payload = httputil.get_json(url)
    results = []
    for item in payload.get("results") or []:
        ipni_id = ipni_overrides.apply(item.get("id"))
        results.append(
            {
                "ipni_id": ipni_id,
                "name": item.get("name"),
                "authors": item.get("authors"),
                "family": item.get("family"),
                "rank": item.get("rank"),
                "in_powo": bool(item.get("inPowo")),
                "fq_id": item.get("fqId"),
                "url": item.get("url"),
            }
        )
    return results


def lookup(name):
    results = search(name)
    wanted = name.strip().lower()
    exact = [row for row in results if (row.get("name") or "").strip().lower() == wanted]
    pool = exact or results
    in_powo = [row for row in pool if row.get("in_powo")]
    if in_powo:
        return in_powo[0]
    return pool[0] if pool else None
