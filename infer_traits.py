"""Infer 4-step traits, height, flowering, toxicity from text and congeners.

Color / habitat / petal still require a guess with evidence. Empty stays empty.
"""

import re

COLOR_WORDS = {
    1: ("white", "whitish", "cream", "creamy", "ivory", "cream-white", "off-white"),
    2: ("yellow", "yellowish", "gold", "golden", "orange"),
    3: ("red", "reddish", "pink", "crimson", "scarlet", "rose", "magenta"),
    4: ("blue", "bluish", "purple", "violet", "lilac", "lavender", "indigo"),
    5: ("green", "greenish", "yellow-green", "yellowish-green", "green-yellow"),
}

COLOR_QIDS = {
    "Q23444": 1,  # white
    "Q943": 2,  # yellow
    "Q39338": 2,  # orange
    "Q3142": 3,  # red
    "Q429220": 3,  # pink
    "Q1088": 4,  # blue
    "Q3257809": 4,  # purple
    "Q428124": 4,  # violet
    "Q3133": 5,  # green
}

HABITAT_WORDS = {
    1: (
        "meadow", "meadows", "grassland", "grasslands", "pasture", "pastures",
        "lawn", "lawns", "prairie", "prairies", "roadside", "roadsides",
        "scrub",
    ),
    2: (
        "garden", "gardens", "cultivated", "cultivation", "ornamental",
        "planted", "hedge", "hedgerow", "hedgerows", "horticulture",
    ),
    3: (
        "wetland", "wetlands", "marsh", "marshes", "bog", "bogs", "swamp",
        "swamps", "pond", "aquatic", "stream", "river",
    ),
    4: (
        "forest", "forests", "woodland", "woodlands", "woods",
        "understorey", "understory",
    ),
    5: ("rock", "rocky", "alpine", "scree", "cliff", "outcrop"),
    6: ("tree", "shrub", "woody", "deciduous tree", "evergreen tree"),
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

SEASONS = {
    "early spring": (3, 4),
    "late spring": (5, 6),
    "in spring": (3, 5),
    "spring": (3, 5),
    "early summer": (6, 7),
    "late summer": (8, 9),
    "in summer": (6, 8),
    "summer": (6, 8),
    "early autumn": (9, 10),
    "late autumn": (10, 11),
    "in autumn": (9, 11),
    "autumn": (9, 11),
    "in fall": (9, 11),
    "fall": (9, 11),
}

FAMILY_PETAL = {
    "asteraceae": (3, 0.8, "composite family (many florets)"),
    "brassicaceae": (1, 0.75, "mustard family typically 4 petals"),
    "fabaceae": (4, 0.75, "pea family zygomorphic"),
    "lamiaceae": (4, 0.75, "mint family zygomorphic"),
    "orchidaceae": (4, 0.85, "orchid zygomorphic"),
    "plantaginaceae": (4, 0.65, "plantain/figwort allies often zygomorphic"),
    "orobanchaceae": (4, 0.7, "broomrape family zygomorphic"),
    "sapindaceae": (2, 0.6, "maples typically 5-petaled"),
    "rosaceae": (2, 0.5, "rose family typically 5 petals"),
    "liliaceae": (3, 0.8, "lily family typically 6 tepals"),
}

CONFIDENCE_OK = 0.55

HEIGHT_UNITS = {
    "m": 100, "meter": 100, "meters": 100, "metre": 100, "metres": 100,
    "cm": 1, "centimetre": 1, "centimetres": 1, "centimeter": 1, "centimeters": 1,
    "ft": 30, "foot": 30, "feet": 30,
    "in": 3, "inch": 3, "inches": 3,
}

HEIGHT_SKIP = re.compile(
    r"\b(leaf|leaves|seed|seeds|fruit|capsule|trunk|diameter|wide|width|"
    r"long|thick|petiole|inflorescence|achene|samara)\b",
    re.I,
)
HEIGHT_KEEP = re.compile(
    r"\b(tall|height|high|stems?|grows?|growing|reaches?|reaching|plant)\b",
    re.I,
)
FLOWER_NEAR = re.compile(
    r"\b(bloom|blooms|blooming|flower|flowers|flowering|inflorescence|florets?)\b",
    re.I,
)
MARKING_NEAR = re.compile(
    r"\b(lines?|veins?|veined|markings?|marked|spots?|dots?|blotches|reticulat\w*)\b",
    re.I,
)

RANGE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:to|[–\-]|—)\s*(\d+(?:\.\d+)?)\s*"
    r"(metres?|meters?|m|centimetres?|centimeters?|cm|feet|foot|ft|inches|inch|in)\b",
    re.I,
)
SINGLE_HEIGHT_RE = re.compile(
    r"(?:growing to|grows? to|reaches?|reaching|up to|to)\s+"
    r"(\d+(?:\.\d+)?)\s*"
    r"(metres?|meters?|m|centimetres?|centimeters?|cm|feet|foot|ft)\b",
    re.I,
)


def _text_blob(resolved, wikipedia):
    parts = [resolved.get("lifeform") or ""]
    if wikipedia:
        parts.append(wikipedia.get("extract") or "")
    return " ".join(parts)


def _axis(values, confidence, evidence):
    unique = sorted(set(values))
    return {
        "values": unique,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "ok": bool(unique) and confidence >= CONFIDENCE_OK,
    }


def _flower_windows(text):
    lower = text.lower()
    windows = []
    for match in re.finditer(
        r".{0,80}\b(flowers?|blossoms?|inflorescence|florets?|corolla|petals?)\b.{0,220}",
        lower,
    ):
        windows.append(match.group(0))
    return windows or [lower]


def infer_color(text, color_qids=None):
    values = []
    evidence = []
    confidence = 0.0
    for qid in color_qids or []:
        code = COLOR_QIDS.get(qid)
        if code:
            values.append(code)
            evidence.append("wikidata P462 %s" % qid)
            confidence = max(confidence, 0.8)
    windows = _flower_windows(text)
    for flower_window in windows:
        if "yellow-green" in flower_window or "yellowish-green" in flower_window:
            values.extend([2, 5])
            evidence.append("text: yellow-green flowers")
            confidence = max(confidence, 0.8)
        for code, words in COLOR_WORDS.items():
            for word in words:
                if word in ("yellow", "green") and "yellow-green" in flower_window:
                    continue
                if word == "pale":
                    continue
                if not re.search(r"\b%s\b" % re.escape(word), flower_window):
                    continue
                if code == 2 and re.search(r"white ray|white petals", flower_window):
                    evidence.append("ignored disc yellow next to white rays")
                    continue
                if code == 3 and re.search(r"tipped red|tinged red|red-tipped", flower_window):
                    evidence.append("ignored red tips on otherwise white rays")
                    continue
                if code == 5 and re.search(r"\b(dark |pale )?green (leaves|leaf|foliage)\b", flower_window):
                    evidence.append("ignored green leaves next to flowers")
                    continue
                if re.search(
                    r"\b%s\b.{0,20}\b(lines?|veins?|veined|markings?|spots?|dots?)\b"
                    % re.escape(word),
                    flower_window,
                ) or re.search(
                    r"\b(lined|veined|marked)\s+(with\s+)?\b%s\b" % re.escape(word),
                    flower_window,
                ):
                    evidence.append("ignored %s markings" % word)
                    continue
                values.append(code)
                evidence.append("text: %s" % word)
                confidence = max(confidence, 0.7)
    return _axis(values, confidence, evidence)


def infer_habitat(text, lifeform=""):
    values = []
    evidence = []
    confidence = 0.0
    blob = ("%s %s" % (lifeform, text)).lower()
    if re.search(r"\b(tree|shrub)\b", (lifeform or "").lower()) or re.search(
        r"\bdeciduous tree\b|\bevergreen tree\b|\bis a [\w\s]{0,20}tree\b",
        blob,
    ):
        values.append(6)
        evidence.append("lifeform/text: tree or shrub")
        confidence = max(confidence, 0.85)
    for code, words in HABITAT_WORDS.items():
        if code == 6:
            continue
        for word in words:
            if re.search(r"\b%s\b" % re.escape(word), blob):
                values.append(code)
                evidence.append("text: %s" % word)
                confidence = max(confidence, 0.65 if code != 2 else 0.6)
    return _axis(values, confidence, evidence)


def infer_petal(text, family=""):
    values = []
    evidence = []
    confidence = 0.0
    lower = text.lower()
    if re.search(r"\b(zygomorphic|bilabiate|labellum|pea-like)\b", lower):
        return _axis([4], 0.85, ["text: zygomorphic / labellum"])
    if re.search(r"\b(capitulum|pseudanthium|ray floret|disc floret|composite)\b", lower):
        values.append(3)
        evidence.append("text: composite inflorescence")
        confidence = 0.8
    if re.search(r"\b(four[- ]petals?|4[- ]petals?|tetramerous)\b", lower):
        values.append(1)
        evidence.append("text: four petals")
        confidence = max(confidence, 0.85)
    if re.search(r"\b(five[- ]petals?|5[- ]petals?|pentamerous)\b", lower):
        values.append(2)
        evidence.append("text: five petals")
        confidence = max(confidence, 0.85)
    if re.search(r"\b(many petals|numerous petals|many[- ]petaled)\b", lower):
        values.append(3)
        evidence.append("text: many petals")
        confidence = max(confidence, 0.8)
    family_key = (family or "").lower()
    if family_key in FAMILY_PETAL and not values:
        code, fam_conf, note = FAMILY_PETAL[family_key]
        values.append(code)
        evidence.append(note)
        confidence = fam_conf
    return _axis(values, confidence, evidence)


def _to_cm(amount, unit):
    factor = HEIGHT_UNITS.get((unit or "").lower())
    if not factor:
        return None
    return int(round(float(amount) * factor))


def _height_score(window, low_cm, high_cm):
    if high_cm is None or high_cm <= 0 or high_cm > 15000:
        return -100
    if low_cm is not None and low_cm > high_cm:
        return -100
    score = 0
    if HEIGHT_KEEP.search(window):
        score += 4
    if HEIGHT_SKIP.search(window) and not HEIGHT_KEEP.search(window):
        score -= 6
    if high_cm < 5:
        score -= 4
    return score


def _unit_rank(unit):
    key = (unit or "").lower()
    if key in (
        "m", "meter", "meters", "metre", "metres",
        "cm", "centimetre", "centimetres", "centimeter", "centimeters",
    ):
        return 0
    return 1


def infer_height(text):
    candidates = []
    for match in RANGE_RE.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        window = text[start:end]
        low = _to_cm(match.group(1), match.group(3))
        high = _to_cm(match.group(2), match.group(3))
        if low is None or high is None:
            continue
        score = _height_score(window, low, high)
        if score >= 0:
            candidates.append((score, _unit_rank(match.group(3)), low, high, match.group(0)))
    for match in SINGLE_HEIGHT_RE.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 30)
        window = text[start:end]
        cm = _to_cm(match.group(1), match.group(2))
        if cm is None:
            continue
        score = _height_score(window, cm, cm)
        if score >= 0:
            candidates.append((score, _unit_rank(match.group(2)), cm, cm, match.group(0)))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda item: (-item[0], item[1], -item[3]))
    _, _, low, high, evidence = candidates[0]
    return low, high, evidence


def _month(token):
    return MONTHS.get((token or "").lower())


def infer_flowering(text):
    months = []
    snippets = []
    for match in re.finditer(
        r"(?:blooms?|flowers?|flowering)\s+from\s+([A-Za-z]+)\s+to\s+([A-Za-z]+)",
        text,
        re.I,
    ):
        start, end = _month(match.group(1)), _month(match.group(2))
        if start and end:
            months.extend([start, end])
            snippets.append(match.group(0))
    for match in re.finditer(
        r"(?:blooms?|flowers?|flowering)\s+(?:in\s+)?([A-Za-z]+)\s+and\s+([A-Za-z]+)",
        text,
        re.I,
    ):
        start, end = _month(match.group(1)), _month(match.group(2))
        if start and end:
            months.extend([start, end])
            snippets.append(match.group(0))
    for match in re.finditer(
        r"\b([A-Za-z]{3,9})\s*[–\-]\s*([A-Za-z]{3,9})\b",
        text,
    ):
        start, end = _month(match.group(1)), _month(match.group(2))
        window_start = max(0, match.start() - 40)
        window = text[window_start:match.end() + 10]
        if start and end and FLOWER_NEAR.search(window):
            months.extend([start, end])
            snippets.append(match.group(0))
    if months:
        return min(months), max(months), "; ".join(snippets[:3])
    lower = text.lower()
    for phrase, span in SEASONS.items():
        if re.search(r"\b%s\b" % re.escape(phrase), lower):
            if phrase in ("spring", "summer", "autumn", "fall") and not FLOWER_NEAR.search(lower):
                continue
            return span[0], span[1], phrase
    return None, None, None


def infer_toxicity(text):
    lower = text.lower()
    if re.search(r"\b(deadly|highly toxic|extremely toxic|fatal)\b", lower):
        return 2, "text: highly toxic"
    if re.search(r"\b(poisonous|toxic|toxicity|if eaten|vomiting)\b", lower):
        return 1, "text: poisonous/toxic"
    return 0, "default 0 (no poison signal)"


def _color_qids(resolved):
    if resolved.get("color_qids"):
        return resolved["color_qids"]
    wikidata = ((resolved.get("sources") or {}).get("wikidata")) or {}
    return wikidata.get("color_qids") or []


def _wd_height(resolved):
    if resolved.get("height_from_cm") is not None:
        return (
            resolved.get("height_from_cm"),
            resolved.get("height_to_cm"),
            "wikidata P2048",
        )
    wikidata = ((resolved.get("sources") or {}).get("wikidata")) or {}
    if wikidata.get("height_from_cm") is not None:
        return (
            wikidata.get("height_from_cm"),
            wikidata.get("height_to_cm") or wikidata.get("height_from_cm"),
            "wikidata P2048",
        )
    return None, None, None


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    if len(values) % 2:
        return int(values[mid])
    return int(round((values[mid - 1] + values[mid]) / 2.0))


def majority_codes(lists):
    """Codes that appear in a strict majority of non-empty lists."""
    lists = [list(item) for item in lists if item]
    if not lists:
        return []
    counts = {}
    for item in lists:
        for code in set(item):
            counts[code] = counts.get(code, 0) + 1
    n = len(lists)
    picked = sorted(code for code, count in counts.items() if count * 2 > n)
    if picked:
        return picked
    best = max(counts.values())
    return sorted(code for code, count in counts.items() if count == best)


def apply_sisters(traits, sisters):
    """Fill gaps from live congeners. Does not override a text/Wikidata hit."""
    sisters = list(sisters or [])
    if not sisters:
        return traits
    names = [item.get("name") or "congener" for item in sisters]
    note = "median/majority of %s" % ", ".join(names[:4])

    if not (traits.get("color") or {}).get("values"):
        colors = majority_codes(item.get("color") or [] for item in sisters)
        if colors:
            traits["color"] = _axis(colors, 0.5, [note])

    if not (traits.get("habitat") or {}).get("values"):
        habitats = majority_codes(item.get("habitat") or [] for item in sisters)
        if habitats:
            traits["habitat"] = _axis(habitats, 0.5, [note])

    if traits.get("height_from") is None:
        lows = [item["height_from"] for item in sisters if item.get("height_from") is not None]
        highs = [item["height_to"] for item in sisters if item.get("height_to") is not None]
        if lows and highs:
            traits["height_from"] = _median(lows)
            traits["height_to"] = _median(highs)
            traits["height_evidence"] = note

    if traits.get("flowering_from") is None:
        starts = [
            item["flowering_from"]
            for item in sisters
            if item.get("flowering_from") is not None
        ]
        ends = [
            item["flowering_to"]
            for item in sisters
            if item.get("flowering_to") is not None
        ]
        if starts and ends:
            traits["flowering_from"] = _median(starts)
            traits["flowering_to"] = _median(ends)
            traits["flowering_evidence"] = note
    return traits


def _mark_filled(axis):
    if axis.get("values"):
        axis["ok"] = True
    return axis


def infer(resolved, wikipedia=None, sisters=None):
    wiki = wikipedia or {}
    text = _text_blob(resolved, wiki)
    color = infer_color(text, _color_qids(resolved))
    habitat = infer_habitat(text, resolved.get("lifeform") or "")
    petal = infer_petal(text, resolved.get("family") or "")
    height_from, height_to, height_ev = infer_height(text)
    if height_from is None:
        height_from, height_to, height_ev = _wd_height(resolved)
    flower_from, flower_to, flower_ev = infer_flowering(text)
    toxicity, tox_ev = infer_toxicity(text)
    traits = {
        "color": color,
        "habitat": habitat,
        "petal": petal,
        "height_from": height_from,
        "height_to": height_to,
        "height_evidence": height_ev,
        "flowering_from": flower_from,
        "flowering_to": flower_to,
        "flowering_evidence": flower_ev,
        "toxicity_class": toxicity,
        "toxicity_evidence": tox_ev,
    }
    apply_sisters(traits, sisters)
    _mark_filled(traits["color"])
    _mark_filled(traits["habitat"])
    _mark_filled(traits["petal"])
    return traits
