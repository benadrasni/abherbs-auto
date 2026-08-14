"""NatureGate / Luontoportti English morphology. No Firebase.

Search by scientific name only. An article mention of another species
is not a hit. Pages are a Next.js app; species text comes from
/_next/data/{buildId}/en/t/{id}.json.
"""

import re

from . import botanical
from . import httputil

HOME = "https://luontoportti.com"
SEARCH = HOME + "/api/taxonomy_find"
PAGE = HOME + "/en/t/%s"
DATA = HOME + "/_next/data/%s/en/t/%s.json"


def pick_hit(payload, accepted_name):
    want = (accepted_name or "").lower().strip()
    if not want:
        return None
    for item in (payload or {}).get("taxonomy_find") or []:
        if item.get("match_type") != "scientific_name":
            continue
        tax = item.get("taxonomy") or {}
        name = (tax.get("scientific_name") or "").lower().strip()
        if name == want:
            return tax
    return None


def english_article(page):
    tax = ((page or {}).get("pageProps") or {}).get("data") or {}
    tax = tax.get("taxonomy_by_pk") or tax
    for item in tax.get("taxonomy_articles") or []:
        if (item.get("language") or "").lower() == "en" and item.get("article"):
            return item
    return None


def extract_text(page, accepted_name):
    tax = ((page or {}).get("pageProps") or {}).get("data") or {}
    tax = tax.get("taxonomy_by_pk") or {}
    article = english_article(page)
    if not article:
        return None
    body = botanical.html_to_text(article.get("article") or "")
    if not body:
        return None
    head = " ".join(
        part
        for part in (
            tax.get("common_name") or "",
            tax.get("scientific_name") or accepted_name,
        )
        if part
    )
    return (head + "\n" + body).strip()


def _build_id(html):
    match = re.search(r'"buildId"\s*:\s*"([^"]+)"', html or "")
    return match.group(1) if match else None


def search(accepted_name):
    params = [
        ("matchType", "scientific_name"),
        ("searchTerm", accepted_name),
        ("limit", "10"),
        ("offset", "0"),
    ]
    payload = httputil.get_json(
        SEARCH + "?" + httputil.urlencode(params),
        headers={"Accept-Language": "en"},
    )
    return pick_hit(payload, accepted_name)


def fetch_page(taxon_id):
    html = httputil.get_text(PAGE % taxon_id)
    build_id = _build_id(html)
    if not build_id:
        return None
    return httputil.get_json(DATA % (build_id, taxon_id))


def fetch(accepted_name):
    tax = search(accepted_name)
    if not tax or not tax.get("id"):
        return None
    page = fetch_page(tax["id"])
    extract = extract_text(page, accepted_name)
    if not extract:
        return None
    return {
        "id": "luontoportti",
        "name": "NatureGate / Luontoportti",
        "url": PAGE % tax["id"],
        "extract": extract,
    }
