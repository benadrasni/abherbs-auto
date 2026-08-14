"""Remembered botanical web sources for English drafting.

The registry is ingest/data/botanical_sources.json. Add a source there
when a site proves useful for a plant; later jobs reuse it. No Firebase.
"""

import json
import os
import re
from html.parser import HTMLParser

from . import httputil

REGISTRY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "botanical_sources.json",
)

_SKIP_TAGS = {"script", "style", "noscript", "svg"}
_BREAK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "td", "th"}


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self.skip += 1
        elif tag in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self.skip:
            self.skip -= 1
        elif tag in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def load(path=None):
    with open(path or REGISTRY, encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload.get("sources") or [])


def save(sources, path=None):
    dest = path or REGISTRY
    with open(dest, "w", encoding="utf-8") as handle:
        json.dump({"sources": sources}, handle, indent=2)
        handle.write("\n")


def _parts(accepted_name):
    bits = (accepted_name or "").split()
    genus = bits[0] if bits else ""
    epithet = bits[1] if len(bits) > 1 else ""
    return {
        "latin": (accepted_name or "").strip(),
        "latin_plus": "+".join(bits[:2]),
        "latin_plus_lower": "+".join(bit.lower() for bit in bits[:2]),
        "latin_under": "_".join(bits[:2]),
        "latin_dash": "-".join(bit.lower() for bit in bits[:2]),
        "genus": genus,
        "genus_lower": genus.lower(),
        "epithet": epithet,
        "epithet_lower": epithet.lower(),
    }


def url_for(source, accepted_name):
    template = (source or {}).get("url") or ""
    if not template or "{" not in template:
        return template or None
    return template.format(**_parts(accepted_name))


def applies(source, accepted_name=None, genus=None, family=None, lifeform=None):
    when = (source or {}).get("when") or {}
    if when.get("always"):
        return True
    genus = (genus or _parts(accepted_name)["genus"] or "").lower()
    family = (family or "").lower()
    lifeform = (lifeform or "").lower()
    genera = [item.lower() for item in when.get("genera") or []]
    families = [item.lower() for item in when.get("families") or []]
    lifeforms = [item.lower() for item in when.get("lifeforms") or []]
    if genera and genus in genera:
        return True
    if families and family in families:
        return True
    if lifeforms and any(token in lifeform for token in lifeforms):
        return True
    return False


def html_to_text(html):
    parser = _HTMLText()
    parser.feed(html or "")
    text = " ".join(parser.parts)
    text = re.sub(r"\[\d+(?:\s*,\s*\d+)*\]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def clip_extract(text, source):
    if not text:
        return ""
    lower = text.lower()
    start = 0
    for marker in source.get("start_at") or []:
        index = lower.find(marker.lower())
        if index >= 0:
            start = index
            break
    cut = len(text)
    for marker in source.get("stop_at") or []:
        index = lower.find(marker.lower(), start)
        if index > start + 40:
            cut = min(cut, index)
    return text[start:cut].strip()


def looks_like_hit(text, accepted_name):
    if not text or len(text) < 80:
        return False
    lower = text.lower()
    latin = (accepted_name or "").lower()
    if latin and latin in lower:
        return True
    bits = latin.split()
    return len(bits) >= 2 and bits[0] in lower and bits[1] in lower


def extract_page(html, source, accepted_name):
    text = html_to_text(html)
    if not looks_like_hit(text, accepted_name):
        return None
    clipped = clip_extract(text, source) or text
    return clipped[:8000]


def _decode(raw):
    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def hints_for(accepted_name, genus=None, family=None, lifeform=None, sources=None):
    """Sources an editor should open for this plant, with a concrete URL when known."""
    hints = []
    for source in sources or load():
        if source.get("fetch") == "pipeline":
            continue
        if not applies(source, accepted_name, genus, family, lifeform):
            continue
        hints.append(
            {
                "id": source["id"],
                "name": source["name"],
                "url": url_for(source, accepted_name) or source.get("home"),
                "fetch": source.get("fetch"),
                "reliable": bool(source.get("reliable")),
                "notes": source.get("notes") or "",
                "good_for": list(source.get("good_for") or []),
            }
        )
    hints.sort(key=lambda item: (0 if item.get("reliable") else 1, item["name"]))
    return hints


def fetch_for(accepted_name, genus=None, family=None, lifeform=None, sources=None):
    """Download Latin-name lookup pages. Failures are skipped."""
    found = []
    for source in sources or load():
        if not applies(source, accepted_name, genus, family, lifeform):
            continue
        kind = source.get("fetch")
        if kind == "search" and source.get("id") == "luontoportti":
            from . import luontoportti

            try:
                item = luontoportti.fetch(accepted_name)
            except Exception:
                continue
            if item:
                found.append(item)
            continue
        if kind == "search" and source.get("id") == "botanycz":
            from . import botanycz

            try:
                item = botanycz.fetch(accepted_name)
            except Exception:
                continue
            if item:
                found.append(item)
            continue
        if kind == "search" and source.get("id") == "eppo":
            from . import eppo

            try:
                item = eppo.fetch(accepted_name)
            except Exception:
                continue
            if item:
                found.append(item)
            continue
        if kind != "latin":
            continue
        url = url_for(source, accepted_name)
        if not url:
            continue
        try:
            html = _decode(httputil.get_bytes(url))
        except Exception:
            continue
        extract = extract_page(html, source, accepted_name)
        if not extract:
            continue
        found.append(
            {
                "id": source["id"],
                "name": source["name"],
                "url": url,
                "extract": extract,
            }
        )
    return found


def remember(entry, path=None):
    """Add or replace a source in the registry by id. Returns the saved list."""
    if not entry or not entry.get("id") or not entry.get("name"):
        raise ValueError("source needs id and name")
    dest = path or REGISTRY
    sources = load(dest) if os.path.isfile(dest) else []
    updated = []
    replaced = False
    for item in sources:
        if item.get("id") == entry["id"]:
            merged = dict(item)
            merged.update(entry)
            updated.append(merged)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(entry)
    save(updated, dest)
    return updated
