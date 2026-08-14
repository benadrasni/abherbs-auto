"""botanicalillustrations.org — search, species gallery, HD plate URL.

HTTP only (HTTPS times out). No public API. No Firebase.
"""

import re
import time
from html import unescape
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from . import httputil

BASE = "http://www.botanicalillustrations.org/"
SKIP_RANKS = (" forma ", " variety ", " subspecies ", " subsp.", " var.", " f. ")


def search_url(name):
    return BASE + "search.php?" + httputil.urlencode(
        {"input": name, "mobile": "0", "uhd": "0", "size": "0"}
    )


def species_url(species_id):
    return BASE + "species.php?" + httputil.urlencode(
        {"id_species": str(species_id), "mobile": "0", "uhd": "0"}
    )


def illustration_page_url(illustration_id):
    return BASE + "illustration.php?" + httputil.urlencode(
        {
            "id_illustration": str(illustration_id),
            "mobile": "0",
            "uhd": "0",
            "size": "0",
        }
    )


def _abs(href):
    return urljoin(BASE, href)


def parse_search(html, wanted_name):
    """Return accepted-species hits: id, label, plate_count."""
    soup = BeautifulSoup(html, "html.parser")
    wanted = wanted_name.strip().lower()
    hits = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "species.php" not in href or "id_species=" not in href:
            continue
        query = parse_qs(urlparse(href).query)
        if "id_species" not in query:
            continue
        species_id = int(query["id_species"][0])
        text = unescape(anchor.get_text(" ", strip=True))
        if not text:
            continue
        entry = hits.setdefault(
            species_id, {"id_species": species_id, "label": "", "plate_count": 0}
        )
        lower = " %s " % text.lower()
        if any(token in lower for token in SKIP_RANKS):
            continue
        count_match = re.search(
            r"\[(?:<strong>)?(\d+)(?:</strong>)?\]", str(anchor), re.I
        )
        if count_match:
            entry["plate_count"] = max(entry["plate_count"], int(count_match.group(1)))
            continue
        if wanted in text.lower() and (
            not entry["label"] or len(text) < len(entry["label"])
        ):
            entry["label"] = text
    ranked = [
        item
        for item in hits.values()
        if wanted in (item["label"] or "").lower()
    ]
    ranked.sort(key=lambda item: (-item["plate_count"], item["id_species"]))
    return ranked


def pick_species(hits):
    return hits[0] if hits else None


def parse_species_gallery(html):
    """Illustration candidates from a species.php page."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen = set()
    for image in soup.find_all("img"):
        src = image.get("src") or ""
        if "ILLUSTRATIONS_thumbnails" not in src:
            continue
        filename = src.rsplit("/", 1)[-1]
        if filename.startswith("0."):
            continue
        illustration_id = os_stem(filename)
        if not illustration_id.isdigit() or illustration_id in seen:
            continue
        seen.add(illustration_id)
        title = image.get("title") or ""
        candidates.append(
            {
                "id_illustration": int(illustration_id),
                "title": title,
                "thumbnail": _abs(src),
                "score": score_plate(title),
            }
        )
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "illustration.php" not in href or "id_illustration=" not in href:
            continue
        query = parse_qs(urlparse(href).query)
        if "id_illustration" not in query:
            continue
        illustration_id = query["id_illustration"][0]
        if illustration_id in seen or not illustration_id.isdigit():
            continue
        seen.add(illustration_id)
        candidates.append(
            {
                "id_illustration": int(illustration_id),
                "title": anchor.get_text(" ", strip=True),
                "thumbnail": "",
                "score": 0,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["id_illustration"]))
    return candidates


def os_stem(filename):
    return filename.rsplit(".", 1)[0]


def score_plate(title):
    text = title.lower()
    score = 0
    if any(word in text for word in ("color", "colour", "hand-col", "painted")):
        score += 3
    # 19th-century floras that tend to be clean color plates
    for flora in (
        "curtis",
        "engl. bot",
        "fl. dan",
        "flora dan",
        "engl bot",
        "sv. bot",
        "fl. bat",
        "kerner",
    ):
        if flora in text:
            score += 4
    if any(word in text for word in ("woodblock", "woodcut", "fig.", "t. ")):
        score += 1
    if "[" in title and "]" in title:
        score -= 2
    if any(word in text for word in ("outline", "analytic", "fruct. sem")):
        score -= 2
    return score


def parse_hd_src(html):
    soup = BeautifulSoup(html, "html.parser")
    for image in soup.find_all("img"):
        src = image.get("src") or ""
        classes = " ".join(image.get("class") or [])
        if "ILLUSTRATIONS_HD" in src or "illustration_100" in classes:
            return _abs(src)
    match = re.search(r'(ILLUSTRATIONS_HD[A-Za-z0-9_./-]+\.(?:jpg|jpeg|png))', html, re.I)
    if match:
        return _abs(match.group(1))
    return None


class Client:
    def __init__(self, sleep_s=1.0, opener=None):
        self.sleep_s = sleep_s
        self._last = 0
        self.opener = opener or httputil.get_text

    def _get(self, url):
        if self.sleep_s:
            wait = self.sleep_s - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
        text = self.opener(url)
        self._last = time.time()
        return text

    def search(self, name):
        return parse_search(self._get(search_url(name)), name)

    def gallery(self, species_id):
        return parse_species_gallery(self._get(species_url(species_id)))

    def hd_url(self, illustration_id):
        return parse_hd_src(self._get(illustration_page_url(illustration_id)))

    def candidates(self, name, limit=8):
        hits = self.search(name)
        picked = pick_species(hits)
        if not picked:
            return {"species": None, "plates": []}
        plates = self.gallery(picked["id_species"])[:limit]
        return {"species": picked, "plates": plates}
