"""Remembered botanical web sources for English drafting.

The registry is ingest/data/botanical_sources.json: libraries (hosts)
plus works (floras, garden sites, name tables). Add a work when a site
proves useful; later jobs reuse it. No Firebase.
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


FAMILY_ALIASES = {
    "labiatae": "lamiaceae",
    "cruciferae": "brassicaceae",
    "umbelliferae": "apiaceae",
    "compositae": "asteraceae",
    "gramineae": "poaceae",
    "leguminosae": "fabaceae",
    "palmae": "arecaceae",
    "aceraceae": "sapindaceae",
    "hippocastanaceae": "sapindaceae",
    "agavaceae": "asparagaceae",
}


def load_registry(path=None):
    with open(path or REGISTRY, encoding="utf-8") as handle:
        return json.load(handle)


def load(path=None):
    return list(load_registry(path).get("sources") or [])


def libraries(path=None):
    return dict(load_registry(path).get("libraries") or {})


def save(sources, path=None, registry=None):
    dest = path or REGISTRY
    if registry is not None:
        payload = registry
    elif os.path.isfile(dest):
        payload = load_registry(dest)
    else:
        payload = {}
    payload["sources"] = sources
    with open(dest, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
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


def _norm_family(name):
    token = re.sub(r"[^a-z]", "", (name or "").lower())
    return FAMILY_ALIASES.get(token, token)


def url_for(source, accepted_name, volume=None):
    source = source or {}
    if volume:
        if volume.get("record"):
            return volume["record"]
        bid = volume.get("bibdigital_id")
        cite = source.get("cite") or ""
        if bid and "{bibdigital_id}" in cite:
            return cite.format(bibdigital_id=bid)
    template = source.get("url") or ""
    if not template:
        return None
    if "{" not in template:
        return template
    try:
        return template.format(**_parts(accepted_name))
    except KeyError:
        return source.get("home")


def pick_volume(source, family=None):
    """Volume that lists this family, else None (use the series hub)."""
    volumes = [
        item
        for item in (source or {}).get("volumes") or []
        if item.get("vascular") is not False
    ]
    if not volumes or not family:
        return None
    want = _norm_family(family)
    if not want:
        return None
    for volume in volumes:
        names = [_norm_family(item) for item in volume.get("families") or []]
        if want in names:
            return volume
        covers = volume.get("covers") or ""
        for token in re.split(r"[–—,;/()]+", covers):
            if _norm_family(token) == want:
                return volume
    return None


def _distribution(accepted_name, native_l2=None, native_l3=None):
    if native_l2 is not None or native_l3 is not None:
        return list(native_l2 or []), [str(code).upper() for code in (native_l3 or [])]
    if not accepted_name:
        return [], []
    try:
        from . import wcvp

        row = wcvp.lookup(accepted_name, include_introduced=False)
    except Exception:
        row = None
    if not row:
        return [], []
    return list(row.get("native_l2") or []), [
        str(code).upper() for code in (row.get("native_l3") or [])
    ]


def applies(
    source,
    accepted_name=None,
    genus=None,
    family=None,
    lifeform=None,
    native_l2=None,
    native_l3=None,
):
    when = (source or {}).get("when") or {}
    if when.get("always"):
        return True
    genus = (genus or _parts(accepted_name)["genus"] or "").lower()
    family = _norm_family(family)
    lifeform = (lifeform or "").lower()
    matched = False
    needed = False
    genera = [item.lower() for item in when.get("genera") or []]
    families = [_norm_family(item) for item in when.get("families") or []]
    lifeforms = [item.lower() for item in when.get("lifeforms") or []]
    if genera:
        needed = True
        if genus in genera:
            matched = True
    if families:
        needed = True
        if family in families:
            matched = True
    if lifeforms:
        needed = True
        if any(token in lifeform for token in lifeforms):
            matched = True
    wanted_l2 = when.get("wcvp_l2") or []
    wanted_l3 = [str(code).upper() for code in (when.get("l3") or [])]
    if wanted_l2 or wanted_l3:
        needed = True
        have_l2, have_l3 = _distribution(accepted_name, native_l2, native_l3)
        if wanted_l2 and set(int(code) for code in wanted_l2).intersection(have_l2):
            matched = True
        if wanted_l3 and set(wanted_l3).intersection(have_l3):
            matched = True
    return matched if needed else False


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


def hints_for(
    accepted_name,
    genus=None,
    family=None,
    lifeform=None,
    sources=None,
    native_l2=None,
    native_l3=None,
):
    """Sources an editor should open for this plant, with a concrete URL when known."""
    hints = []
    have_l2, have_l3 = _distribution(accepted_name, native_l2, native_l3)
    for source in sources or load():
        if source.get("fetch") == "pipeline" or source.get("kind") == "library":
            continue
        if not applies(
            source,
            accepted_name,
            genus,
            family,
            lifeform,
            native_l2=have_l2,
            native_l3=have_l3,
        ):
            continue
        volume = pick_volume(source, family)
        url = url_for(source, accepted_name, volume=volume) or source.get("home")
        name = source["name"]
        notes = source.get("notes") or ""
        if volume:
            name = "%s %s" % (source["name"], volume.get("vol") or "")
            covers = volume.get("covers") or ""
            if covers:
                notes = covers
            bid = volume.get("bibdigital_id")
            cite = source.get("cite") or ""
            if bid and "{bibdigital_id}" in cite:
                url = cite.format(bibdigital_id=bid)
        hints.append(
            {
                "id": source["id"],
                "name": name.strip(),
                "url": url,
                "fetch": source.get("fetch"),
                "reliable": bool(source.get("reliable")),
                "notes": notes,
                "good_for": list(source.get("roles") or source.get("good_for") or []),
                "volume": (volume or {}).get("vol"),
            }
        )
    hints.sort(key=lambda item: (0 if item.get("reliable") else 1, item["name"]))
    return hints


def fetch_for(
    accepted_name,
    genus=None,
    family=None,
    lifeform=None,
    sources=None,
    native_l2=None,
    native_l3=None,
):
    """Download Latin-name lookup pages. Failures are skipped."""
    found = []
    have_l2, have_l3 = _distribution(accepted_name, native_l2, native_l3)
    for source in sources or load():
        if source.get("kind") == "library":
            continue
        if not applies(
            source,
            accepted_name,
            genus,
            family,
            lifeform,
            native_l2=have_l2,
            native_l3=have_l3,
        ):
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
