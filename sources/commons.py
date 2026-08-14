"""Wikimedia Commons photo picker. Category-first, license-filtered. No Firebase."""

import re
from urllib.parse import unquote

from . import httputil

API = "https://commons.wikimedia.org/w/api.php"

ALLOWED_LICENSE_PREFIXES = (
    "cc by",
    "cc-by",
    "cc0",
    "public domain",
    "pd",
    "pdm",
    "no restrictions",
)
DENIED_TOKENS = ("nc", "nd", "fair use", "nonfree", "non-free")

ALLOWED_MIMES = (
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
)

REJECT_TITLE = (
    "herbarium", "specimen", "range map", "distribution map",
    "microscopic", "stomata", "epidermis", "pollen", "chromosome",
    "illustration", "engraving", "woodcut", "lithograph", "drawing of",
    "diagram", "logo", "coat of arms", "svg", "map of",
    "cultivar", "low quality",
)

SKIP_SUBCAT = (
    "cultivar", "herbarium", "specimen", "range map", "maps",
    "illustration", "in art", "microscopic", "pollen",
    "low quality", "diseases", "animals with", "people with",
    "by country", "by month", "(text)", "quality images",
    "places named", "seedling", "non-native",
)

ROLE_HINTS = (
    ("trunk", ("bark", "trunk", "bole")),
    ("flower", ("flower", "inflorescence", "blossom")),
    ("leaf", ("leaf", "leaves", "foliage")),
    ("fruit", ("fruit", "seed")),
    ("habit", ("habitat", "(habit)")),
)

MIN_SIDE = 400


def license_ok(short_name):
    if not short_name:
        return False
    text = short_name.strip().lower().replace("_", " ")
    if "nc" in text.split() or "-nc" in text or " nd" in text or "-nd" in text:
        return False
    if any(token in text for token in DENIED_TOKENS):
        return False
    return any(text.startswith(prefix) or prefix in text for prefix in ALLOWED_LICENSE_PREFIXES)


def license_ok_url(url):
    if not url:
        return False
    text = url.lower()
    if "by-nc" in text or "by-nd" in text or "/nc/" in text:
        return False
    if "publicdomain" in text or "/zero/" in text or "cc0" in text:
        return True
    if "creativecommons.org/licenses/by" in text:
        return True
    return False


def strip_html(text):
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _meta(ext, key):
    block = (ext or {}).get(key) or {}
    return strip_html(block.get("value") or "")


def parse_query(payload):
    pages = (payload.get("query") or {}).get("pages") or {}
    files = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        ext = info.get("extmetadata") or {}
        license_name = _meta(ext, "LicenseShortName")
        files.append(
            {
                "title": page.get("title") or "",
                "url": info.get("url") or "",
                "descriptionurl": info.get("descriptionurl") or "",
                "mime": info.get("mime") or "",
                "width": info.get("width") or 0,
                "height": info.get("height") or 0,
                "license": license_name,
                "license_ok": license_ok(license_name),
                "description": _meta(ext, "ImageDescription"),
                "object_name": _meta(ext, "ObjectName"),
                "categories": _meta(ext, "Categories"),
                "artist": _meta(ext, "Artist"),
                "source": "commons",
            }
        )
    return files


def _query(params):
    return httputil.get_json(API + "?" + httputil.urlencode(params))


def page_exists(title):
    payload = _query({"action": "query", "format": "json", "titles": title})
    pages = (payload.get("query") or {}).get("pages") or {}
    return not any(page.get("missing") is not None or int(key) < 0 for key, page in pages.items())


def category_from_sitelink(sitelink):
    if not sitelink:
        return None
    slug = unquote(sitelink.rstrip("/").split("/")[-1]).replace("_", " ")
    if slug.lower().startswith("category:"):
        return "Category:" + slug.split(":", 1)[1]
    return None


def resolve_category(name, sitelink=None):
    titled = category_from_sitelink(sitelink)
    if titled and page_exists(titled):
        return titled
    fallback = "Category:" + name
    if page_exists(fallback):
        return fallback
    return None


def list_subcats(title):
    payload = _query(
        {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": title,
            "cmtype": "subcat",
            "cmlimit": "100",
        }
    )
    return [
        item.get("title") or ""
        for item in (payload.get("query") or {}).get("categorymembers") or []
    ]


def skip_subcat(title):
    text = title.lower()
    return any(token in text for token in SKIP_SUBCAT)


def role_for_category(title):
    if skip_subcat(title):
        return None
    text = title.lower()
    for role, hints in ROLE_HINTS:
        if any(hint in text for hint in hints):
            return role
    return None


def rejected_title(title, description=""):
    blob = ("%s %s" % (title or "", description or "")).lower()
    if "'" in (title or "") or "\u2018" in blob or "cultivar" in blob:
        return True
    return any(token in blob for token in REJECT_TITLE)


def usable(item):
    if not item.get("license_ok"):
        return False
    if (item.get("mime") or "") not in ALLOWED_MIMES:
        return False
    if not item.get("url"):
        return False
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    if min(width, height) < MIN_SIDE:
        return False
    if rejected_title(item.get("title") or "", item.get("description") or ""):
        return False
    return True


def score_file(item, latin):
    score = 0
    title = (item.get("title") or "").lower()
    if latin.lower() in title:
        score += 5
    width = int(item.get("width") or 0)
    if width >= 2000:
        score += 3
    elif width >= 1000:
        score += 2
    elif width >= 600:
        score += 1
    if "jpeg" in (item.get("mime") or ""):
        score += 1
    if item.get("role_hint"):
        score += 2
    return score


def category_files(title, limit=25):
    params = {
        "action": "query",
        "format": "json",
        "generator": "categorymembers",
        "gcmtitle": title,
        "gcmtype": "file",
        "gcmlimit": str(min(limit, 50)),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|ImageDescription|ObjectName|Categories",
    }
    out = []
    while True:
        payload = _query(params)
        out.extend(parse_query(payload))
        cont = payload.get("continue") or {}
        if "gcmcontinue" not in cont or len(out) >= limit:
            break
        params["gcmcontinue"] = cont["gcmcontinue"]
    return out[:limit]


def search(name, limit=20):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": name,
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|ImageDescription|ObjectName|Categories",
    }
    return parse_query(_query(params))


def allowed(files):
    return [item for item in files if usable(item)]


def normalize_latin(name):
    return re.sub(r"[^a-z]+", " ", (name or "").lower()).strip()


def matches_species(item, latin):
    """Require the binomial on the file. Stops 'Digitalis fruit' matching Eucomis."""
    wanted = normalize_latin(latin)
    if not wanted:
        return False
    blob = normalize_latin(
        " ".join(
            [
                item.get("title") or "",
                item.get("categories") or "",
                item.get("object_name") or "",
                item.get("description") or "",
            ]
        )
    )
    return wanted in blob


def _add(files, seen, item, role_hint, latin):
    title = item.get("title") or ""
    if not title or title in seen:
        return
    item = dict(item)
    item["role_hint"] = role_hint
    item["source"] = "commons"
    if not usable(item):
        return
    if not matches_species(item, latin):
        return
    item["score"] = score_file(item, latin)
    seen.add(title)
    files.append(item)


def collect(name, sitelink=None, per_role=12):
    """Gather licensed Commons photos, preferring role subcategories."""
    files = []
    seen = set()
    category = resolve_category(name, sitelink)
    if category:
        for sub in list_subcats(category):
            role = role_for_category(sub)
            if not role:
                continue
            for item in category_files(sub, per_role):
                _add(files, seen, item, role, name)
        for item in category_files(category, 24):
            _add(files, seen, item, None, name)

    have = {item.get("role_hint") for item in files if item.get("role_hint")}
    for role, query in (
        ("flower", "%s flower" % name),
        ("leaf", "%s leaf" % name),
        ("fruit", "%s fruit" % name),
        ("habit", "%s habitat" % name),
        ("trunk", "%s bark" % name),
    ):
        if role in have:
            continue
        for item in search(query, limit=8):
            _add(files, seen, item, role, name)

    if not files:
        for item in search(name, limit=24):
            _add(files, seen, item, None, name)

    files.sort(key=lambda item: -item.get("score", 0))
    return files
