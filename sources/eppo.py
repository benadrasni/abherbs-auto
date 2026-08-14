"""EPPO Global Database vernacular names. No Firebase.

Search by preferred scientific name, then read the Common names table
on https://gd.eppo.int/taxon/{code}. A miss is normal.
"""

import html
import re

from . import httputil

HOME = "https://gd.eppo.int"
SEARCH = HOME + "/ajax/search"
TAXON = HOME + "/taxon/%s"

# EPPO table uses English language names; strip parenthetical variants.
LANG = {
    "english": "en",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "italian": "it",
    "dutch": "nl",
    "portuguese": "pt",
    "swedish": "sv",
    "japanese": "ja",
    "russian": "ru",
    "danish": "da",
    "norwegian": "no",
    "finnish": "fi",
    "turkish": "tr",
    "hebrew": "he",
    "afrikaans": "af",
    "persian": "fa",
    "polish": "pl",
    "malay": "ms",
    "hungarian": "hu",
    "bashkir": "ba",
    "bulgarian": "bg",
    "catalan": "ca",
    "croatian": "hr",
    "czech": "cs",
    "estonian": "et",
    "greek": "el",
    "latvian": "lv",
    "lithuanian": "lt",
    "norwegian bokmål": "nb",
    "romanian": "ro",
    "serbian": "sr",
    "slovak": "sk",
    "slovene": "sl",
    "slovenian": "sl",
    "ukrainian": "uk",
    "chinese": "zh",
    "korean": "ko",
    "albanian": "sq",
}

_TABLE = re.compile(
    r'id="tbcommon".*?</table>',
    re.I | re.S,
)
_ROW = re.compile(
    r"<tr>\s*<td>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
    re.I | re.S,
)
_TAG = re.compile(r"<[^>]+>")


def language_code(label):
    raw = (label or "").strip().lower()
    raw = re.sub(r"\s*\([^)]*\)\s*", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return LANG.get(raw)


def pick_hit(payload, accepted_name):
    want = (accepted_name or "").strip().lower()
    if not want:
        return None
    exact = []
    for item in payload or []:
        if (item.get("t") or "").lower() != "plant":
            continue
        if item.get("sc") is False:
            continue
        if not item.get("e"):
            continue
        name = (item.get("f") or "").strip().lower()
        if name == want:
            exact.append(item)
    preferred = [item for item in exact if item.get("p")]
    pool = preferred or exact
    return pool[0] if pool else None


def parse_names(page, accepted_name=None):
    table = _TABLE.search(page or "")
    if not table:
        return {}
    latin = (accepted_name or "").strip().lower()
    names = {}
    for match in _ROW.finditer(table.group(0)):
        vernacular = html.unescape(_TAG.sub("", match.group(1))).strip()
        lang = language_code(_TAG.sub("", match.group(2)))
        if not vernacular or not lang:
            continue
        if latin and vernacular.lower() == latin:
            continue
        bucket = names.setdefault(lang, [])
        if vernacular not in bucket:
            bucket.append(vernacular)
    return names


def search(accepted_name):
    params = httputil.urlencode(
        {
            "k": accepted_name,
            "s": "2",
            "m": "1",
            "t": "1",
            "l": "la",
        }
    )
    return httputil.get_json(
        SEARCH + "?" + params,
        headers={
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
    )


def fetch(accepted_name):
    try:
        payload = search(accepted_name)
    except Exception:
        return None
    hit = pick_hit(payload, accepted_name)
    if not hit:
        return None
    url = TAXON % hit["e"]
    try:
        html = httputil.get_text(url)
    except Exception:
        return None
    names = parse_names(html, accepted_name)
    if not names:
        return None
    return {
        "id": "eppo",
        "name": "EPPO Global Database",
        "url": url,
        "code": hit["e"],
        "names": names,
    }
