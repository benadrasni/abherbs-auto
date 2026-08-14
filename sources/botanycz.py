"""BOTANY.cz species pages. No Firebase.

Latin slug /cs/{genus-epithet}/ is the usual hit. English /en/ exists
for some species only; try it first. 404 is normal.
"""

from . import botanical
from . import httputil

HOME = "https://botany.cz"


def config():
    for item in botanical.load():
        if item.get("id") == "botanycz":
            return item
    return {"id": "botanycz", "name": "BOTANY.cz"}


def urls(accepted_name):
    slug = botanical._parts(accepted_name)["latin_dash"]
    if not slug:
        return []
    return [
        "%s/en/%s/" % (HOME, slug),
        "%s/cs/%s/" % (HOME, slug),
    ]


def fetch(accepted_name):
    source = config()
    for url in urls(accepted_name):
        try:
            html = botanical._decode(httputil.get_bytes(url))
        except Exception:
            continue
        extract = botanical.extract_page(html, source, accepted_name)
        if extract:
            return {
                "id": "botanycz",
                "name": source.get("name") or "BOTANY.cz",
                "url": url,
                "extract": extract,
            }
    return None
