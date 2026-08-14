"""English Wikipedia extracts and sections. No Firebase."""

import re
from urllib.parse import unquote

from . import httputil

API = "https://en.wikipedia.org/w/api.php"


def title_from_url(url):
    if not url:
        return None
    slug = url.rstrip("/").split("/")[-1]
    return unquote(slug).replace("_", " ")


def fetch_extract(title):
    if not title:
        return None
    payload = httputil.get_json(
        API
        + "?"
        + httputil.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "exsectionformat": "wiki",
                "redirects": "1",
                "titles": title,
                "format": "json",
                "formatversion": "2",
            }
        )
    )
    pages = ((payload.get("query") or {}).get("pages")) or []
    if not pages:
        return None
    page = pages[0]
    if page.get("missing"):
        return None
    extract = page.get("extract") or ""
    resolved = page.get("title") or title
    return {
        "title": resolved,
        "extract": extract,
        "url": "https://en.wikipedia.org/wiki/" + resolved.replace(" ", "_"),
    }


def split_sections(extract):
    """Return {lead: text, sections: {name: text}} from explaintext wiki headings."""
    if not extract:
        return {"lead": "", "sections": {}}
    parts = re.split(r"\n==+\s*([^=]+?)\s*==+\n", "\n" + extract)
    # parts[0] is empty/lead prefix; then name, body, name, body...
    lead = parts[0].strip()
    if lead.startswith("\n"):
        lead = lead[1:]
    # First chunk before first heading is the lead (may include title line)
    if parts and not parts[0].strip().startswith("=="):
        lead = parts[0].strip()
    else:
        lead = ""
    sections = {}
    names = parts[1::2]
    bodies = parts[2::2]
    for name, body in zip(names, bodies):
        sections[name.strip()] = body.strip()
    return {"lead": lead, "sections": sections}


def sentences(text):
    chunks = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def sentences_matching(text, keywords):
    hits = []
    for sentence in sentences(text):
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            hits.append(sentence)
    return hits
