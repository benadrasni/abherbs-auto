"""Classify plant photos into gallery slots.

Order: flower/inflorescence, leaf, fruit, whole plant, trunk (woody), flower detail.
"""

import os
import re

ROLES = (
    "flower",
    "leaf",
    "fruit",
    "habit",
    "trunk",
    "flower_detail",
)

KEYWORDS = {
    "flower_detail": (
        "detail", "throat", "labellum", "close-up", "closeup", "macro",
        "dissect", "floret",
    ),
    "flower": (
        "flower", "flowers", "blossom", "bloom", "inflorescence", "capitulum",
        "raceme", "spike", "umbel", "cyme", "panicle", "head",
    ),
    "leaf": ("leaf", "leaves", "foliage", "frond"),
    "fruit": ("fruit", "fruits", "berry", "berries", "capsule", "achene", "pod", "seed"),
    "habit": ("habit", "whole plant", "in situ", "growth habit"),
    "trunk": ("trunk", "bark", "bole", "stem bark"),
}

SLOT_ORDER = ("flower", "leaf", "fruit", "habit", "trunk", "flower_detail")
MIN_PHOTOS = 3
MAX_PHOTOS = 5


def _blob(file_info):
    parts = [
        file_info.get("title") or "",
        file_info.get("description") or "",
        file_info.get("object_name") or "",
        file_info.get("categories") or "",
        file_info.get("path") or "",
        os.path.basename(file_info.get("path") or file_info.get("url") or ""),
    ]
    return " ".join(parts).lower()


def classify(file_info):
    if file_info.get("role_hint") in ROLES:
        return file_info["role_hint"]
    name = os.path.basename(file_info.get("path") or file_info.get("title") or "")
    match = re.match(r"^(\d+)-(flower|leaf|fruit|habit|trunk|flower_detail)\b", name, re.I)
    if match:
        return match.group(2).lower()
    text = _blob(file_info)
    for role in ("flower_detail", "flower", "fruit", "leaf", "trunk", "habit"):
        for keyword in KEYWORDS[role]:
            if re.search(r"\b%s\b" % re.escape(keyword), text):
                return role
    return None


def is_woody(lifeform, habitats=None):
    text = (lifeform or "").lower()
    if any(word in text for word in ("tree", "shrub", "woody")):
        return True
    return 6 in (habitats or [])


def pack(files, lifeform="", habitats=None):
    """Pick 3–5 files in the fixed role order. Photo 1 is always flower."""
    woody = is_woody(lifeform, habitats)
    buckets = {role: [] for role in ROLES}
    unused = []
    for item in files:
        role = classify(item)
        copy = dict(item)
        copy["role"] = role
        if role in buckets:
            buckets[role].append(copy)
        else:
            unused.append(copy)
    for role in buckets:
        buckets[role].sort(key=lambda item: -int(item.get("score") or 0))

    slots = []
    flower = (buckets["flower"] or buckets["flower_detail"])[:1]
    if not flower:
        return {
            "photos": [],
            "status": "needs_review",
            "reason": "no flower or inflorescence photo",
            "unused": files,
            "skipped": ["fruit"] if not buckets["fruit"] else [],
        }
    flower[0]["role"] = "flower"
    slots.append(flower[0])

    skipped = []
    for role in ("leaf", "fruit", "habit"):
        if buckets[role]:
            slots.append(buckets[role][0])
        elif role == "fruit":
            skipped.append("fruit")
    if woody and buckets["trunk"] and len(slots) < MAX_PHOTOS:
        slots.append(buckets["trunk"][0])
    if len(slots) < MAX_PHOTOS and buckets["flower_detail"]:
        extra = buckets["flower_detail"][0]
        if extra is not flower[0]:
            slots.append(extra)

    if len(slots) < MIN_PHOTOS and len(buckets["flower"]) > 1:
        extra = dict(buckets["flower"][1])
        extra["role"] = "flower"
        extra["note"] = "second flower used to reach minimum"
        slots.append(extra)

    if len(slots) < MIN_PHOTOS:
        return {
            "photos": slots,
            "status": "needs_review",
            "reason": "fewer than %s usable photos" % MIN_PHOTOS,
            "unused": unused,
            "skipped": skipped,
        }

    return {
        "photos": slots[:MAX_PHOTOS],
        "status": "ok",
        "reason": "",
        "unused": unused,
        "skipped": skipped,
    }
