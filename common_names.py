"""Sourced vernacular names. Never invent a translation of the English name."""

import re
from urllib.parse import unquote, urlparse

from sources import wikipedia as wiki_api


BOTANY_FIELDS = (
    ("česká jména", "cs"),
    ("české jména", "cs"),
    ("české mená", "cs"),
    ("slovenská jména", "sk"),
    ("slovenské jména", "sk"),
    ("slovenská mená", "sk"),
    ("slovenské mená", "sk"),
    ("english names", "en"),
    ("common names", "en"),
)


def normalize(name):
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def display_name(name, language):
    text = (name or "").strip()
    if not text:
        return ""
    if language == "de":
        if " " in text:
            return text[0].lower() + text[1:]
        return text
    return text.lower()


def is_latinish(name, latin, synonyms=None):
    token = normalize(name)
    if not token:
        return True
    if token == normalize(latin):
        return True
    for item in synonyms or []:
        synonym = item.get("name") if isinstance(item, dict) else item
        if synonym and token == normalize(synonym):
            return True
        if synonym and token.startswith(normalize(synonym) + " "):
            return True
    bits = (latin or "").split()
    if len(bits) >= 2 and token == normalize(" ".join(bits[:2])):
        return True
    genus = bits[0].lower() if bits else ""
    first = (name or "").strip().split()
    return bool(genus and len(first) >= 2 and first[0].lower() == genus)


def language_from_wikipedia_url(url):
    host = (urlparse(url or "").netloc or "").lower()
    if not host.endswith("wikipedia.org"):
        return None
    sub = host.split(".")[0]
    if sub in ("www", "simple", "species"):
        return None
    return sub


def _add(bucket, lang, name, source, latin, synonyms):
    if not lang or is_latinish(name, latin, synonyms):
        return
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    if not cleaned:
        return
    key = (lang, normalize(cleaned))
    if key in bucket["_seen"]:
        return
    bucket["_seen"].add(key)
    bucket.setdefault(lang, []).append({"name": cleaned, "source": source})


def from_wikidata(resolved):
    latin = (resolved or {}).get("accepted_name") or ""
    synonyms = (resolved or {}).get("synonyms") or []
    bucket = {"_seen": set()}
    for lang, label in ((resolved or {}).get("labels") or {}).items():
        _add(bucket, lang, label, "wikidata", latin, synonyms)
    for lang, aliases in ((resolved or {}).get("aliases") or {}).items():
        for alias in aliases or []:
            _add(bucket, lang, alias, "wikidata", latin, synonyms)
    bucket.pop("_seen", None)
    return bucket


def from_wikipedia_titles(resolved):
    latin = (resolved or {}).get("accepted_name") or ""
    synonyms = (resolved or {}).get("synonyms") or []
    bucket = {"_seen": set()}
    for url in ((resolved or {}).get("wikipedia") or {}).values():
        lang = language_from_wikipedia_url(url)
        title = wiki_api.title_from_url(url)
        _add(bucket, lang, title, "wikipedia", latin, synonyms)
    bucket.pop("_seen", None)
    return bucket


def _split_cited_names(blob):
    cleaned = re.sub(r"\([^)]*\)", ",", blob or "")
    names = []
    for part in re.split(r"[,;]", cleaned):
        item = part.strip(" .;")
        if not item or item.isdigit():
            continue
        if len(item) < 3:
            continue
        names.append(item)
    return names


def from_botanycz_extract(extract):
    """Czech/Slovak (and occasional English) names from a BOTANY.cz page."""
    bucket = {"_seen": set()}
    text = extract or ""
    for marker, lang in BOTANY_FIELDS:
        match = re.search(
            marker + r"\s*:\s*(.+?)(?:\n|$)",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        for name in _split_cited_names(match.group(1)):
            _add(bucket, lang, name, "botany.cz", "", [])
    bucket.pop("_seen", None)
    return bucket


def collect(resolved, extra_sources=None):
    """All vernacular names that a source actually printed."""
    latin = (resolved or {}).get("accepted_name") or ""
    synonyms = (resolved or {}).get("synonyms") or []
    bucket = {"_seen": set()}
    for group in (from_wikidata(resolved), from_wikipedia_titles(resolved)):
        for lang, items in group.items():
            for item in items:
                _add(bucket, lang, item["name"], item["source"], latin, synonyms)
    for source in extra_sources or []:
        if (source or {}).get("id") == "botanycz":
            for lang, items in from_botanycz_extract(source.get("extract") or "").items():
                for item in items:
                    _add(bucket, lang, item["name"], item["source"], latin, synonyms)
        if (source or {}).get("id") == "eppo":
            for lang, values in ((source.get("names") or {})).items():
                for name in values or []:
                    _add(bucket, lang, name, "eppo", latin, synonyms)
    bucket.pop("_seen", None)
    return bucket


def allowed_set(sourced, lang, latin):
    names = {normalize(latin)} if latin else set()
    for item in (sourced or {}).get(lang) or []:
        names.add(normalize(item.get("name")))
    return names


def unsourced_names(translations, sourced, latin):
    """Labels/names that are not Latin and not in the sourced list."""
    issues = []
    for lang, entry in (translations or {}).items():
        if not entry or lang.endswith("-GT"):
            continue
        allowed = allowed_set(sourced, lang, latin)
        values = [entry.get("label")] + list(entry.get("names") or [])
        for value in values:
            if not value or normalize(value) in allowed:
                continue
            issues.append((lang, value))
    return issues


def translations_from_sources(resolved):
    """Wikidata + Wikipedia-title names and Wikipedia URLs. No invented names."""
    sourced = collect(resolved)
    wikipedia = (resolved or {}).get("wikipedia") or {}
    languages = list(
        dict.fromkeys(list(sourced.keys()) + list(wikipedia.keys()))
    )
    translations = {}
    for lang in languages:
        entry = {}
        names = []
        for item in sourced.get(lang) or []:
            formatted = display_name(item["name"], lang)
            if formatted and formatted not in names:
                names.append(formatted)
        if names:
            entry["label"] = names[0]
            extra = names[1:]
            if extra:
                entry["names"] = extra
        if lang in wikipedia:
            entry["wikipedia"] = wikipedia[lang]
        if entry:
            translations[lang] = entry
    return translations


def apply_to_packet(packet, extra_sources=None):
    """Merge flora names into the packet. Does not invent translations."""
    job = packet.setdefault("job", {})
    resolved = packet.get("resolved") or {
        "accepted_name": job.get("accepted_name"),
        "labels": {},
        "aliases": {},
        "wikipedia": {},
        "synonyms": (packet.get("synonyms") or {}).get("ipni") or [],
    }
    sourced = collect(resolved, extra_sources=extra_sources)
    job["sourced_names"] = sourced
    translations = packet.setdefault("translations", {})
    latin = job.get("accepted_name") or resolved.get("accepted_name") or ""
    for lang, items in sourced.items():
        formatted = []
        for item in items:
            name = display_name(item["name"], lang)
            if name and name not in formatted:
                formatted.append(name)
        if not formatted:
            continue
        entry = translations.setdefault(lang, {})
        label = entry.get("label")
        if not label or is_latinish(label, latin):
            entry["label"] = formatted[0]
        extras = list(entry.get("names") or [])
        current = {normalize(entry.get("label") or "")}
        for name in extras:
            current.add(normalize(name))
        for name in formatted:
            key = normalize(name)
            if not key or key in current:
                continue
            extras.append(name)
            current.add(key)
        if extras:
            entry["names"] = extras
    issues = unsourced_names(translations, sourced, latin)
    if issues:
        job.setdefault("warnings", []).append(
            "unsourced common names: "
            + ", ".join("%s=%s" % (lang, name) for lang, name in issues)
        )
    return sourced
