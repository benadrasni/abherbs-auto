"""Classify a plant inflorescence paragraph into legend type keys.

Language-independent keys stored on plants_v2.inflorescenceType (array).
Primary type is first. Empty means none of the 17 diagrams apply
(solitary flower, catkin, unnamed cluster).
"""

TYPES = (
    "raceme",
    "spike",
    "spadix",
    "corymb",
    "umbel",
    "compound_umbel",
    "capitulum",
    "head",
    "panicle",
    "compound_spike",
    "cyme",
    "helicoid",
    "rhipidium",
    "scorpioid",
    "scorpioid_thyrse",
    "dichasial_thyrse",
    "double_scorpioid_thyrse",
)

# Longer phrases must appear before the shorter ones they contain.
SYNONYMS = {
    "raceme": ("racemes", "raceme", "strapce", "strapcovit", "strapec", "hrozen", "hrozny", "traube"),
    "spike": ("spikes", "spike", "spicate", "klasy", "klasovit", "klas", "ähre"),
    "spadix": ("spadices", "spadix", "šúľky", "šúľok", "šúľka", "palice", "kolben"),
    "corymb": ("corymbs", "corymb", "chocholíky", "chocholík", "doldentraube"),
    "umbel": ("umbels", "umbellate", "umbel", "okolíčk", "okolíky", "okolík", "dolde"),
    "compound_umbel": (
        "compound umbels",
        "compound umbel",
        "secondary umbels",
        "umbellules",
        "umbellule",
        "zložený okolík",
        "zložené okolíky",
        "složený okolík",
        "složené okolíky",
        "doppeldolde",
    ),
    "capitulum": (
        "flowering heads",
        "flowering head",
        "flower-heads",
        "flower-head",
        "flower heads",
        "flower head",
        "capitula",
        "capitulum",
        "capitules",
        "capitule",
        "úbory",
        "úborov",
        "úbor",
        "körbchen",
    ),
    "head": ("spherical head", "globose head", "dense head", "heads", "head", "hlávky", "hlávka", "köpfchen"),
    "panicle": ("panicles", "paniculate", "panicle", "metliny", "metlina", "laty", "lata", "rispe"),
    "compound_spike": (
        "compound spikes",
        "compound spike",
        "zložený klas",
        "zložené klasy",
        "složený klas",
        "zusammengesetzte ähre",
    ),
    "cyme": ("dichasium", "dichasia", "cymose", "cymes", "cyme", "vidlice", "vidlica", "vidlan", "vrcholíky", "vrcholík"),
    "helicoid": ("helicoid cymes", "helicoid cyme", "helicoid", "bostryx", "skrutec", "šroubel", "schraubel"),
    "rhipidium": ("rhipidia", "rhipidium", "vejáriky", "vejárik", "vějířek", "fächel"),
    "scorpioid": (
        "scorpioid cymes",
        "scorpioid cyme",
        "scorpioid",
        "cincinnus",
        "závinky",
        "závinkov",
        "závinok",
        "závinek",
        "vijany",
        "vijan",
        "wickel",
    ),
    "scorpioid_thyrse": ("scorpioid thyrsus", "scorpioid thyrse", "thyrsus", "thyrse", "wickel-zymus"),
    "dichasial_thyrse": ("dichasial thyrsus", "dichasial thyrse", "thyrsoid", "dichasialer zymus"),
    "double_scorpioid_thyrse": (
        "double scorpioid thyrse",
        "double scorpioid thyrsus",
        "dvojzávinok",
        "dvojitý vijan",
        "doppelwickel",
    ),
}

_SPECIFIC_DROPS = (
    ("compound_umbel", ("umbel",)),
    ("compound_spike", ("spike",)),
    ("double_scorpioid_thyrse", ("scorpioid_thyrse", "scorpioid", "cyme")),
    ("scorpioid_thyrse", ("scorpioid", "cyme")),
    ("dichasial_thyrse", ("cyme",)),
    ("helicoid", ("cyme",)),
    ("rhipidium", ("cyme",)),
    ("scorpioid", ("cyme",)),
    ("capitulum", ("head",)),
)


def normalize(value):
    text = (value or "").replace("<b>", " ").replace("</b>", " ")
    out = []
    prev_space = False
    for ch in text.lower():
        if ch in "‐‑‒–—―":
            ch = "-"
        if ch.isspace():
            if prev_space:
                continue
            prev_space = True
            out.append(" ")
            continue
        prev_space = False
        out.append(ch)
    return "".join(out).strip()


def _is_letter(ch):
    return ch.isalpha()


def _leftover(hay, end):
    n = 0
    while end + n < len(hay) and _is_letter(hay[end + n]):
        n += 1
    return n, hay[end : end + n]


def _term_hit(hay, term):
    needle = normalize(term)
    if len(needle) < 4:
        return None
    best = None
    start = 0
    while start <= len(hay) - len(needle):
        at = hay.find(needle, start)
        if at < 0:
            break
        before = hay[at - 1] if at else ""
        if before and _is_letter(before):
            start = at + 1
            continue
        after = hay[at + len(needle) :]
        if after.startswith("-like") or after.startswith(" like"):
            start = at + 1
            continue
        extra, extra_text = _leftover(hay, at + len(needle))
        if extra_text.startswith("like"):
            start = at + 1
            continue
        adjectival = extra_text in (
            "ose",
            "ous",
            "ate",
            "late",
            "ovej",
            "ový",
            "ová",
            "ových",
            "ového",
            "ovým",
        ) or extra_text.startswith("ovit")
        if extra <= 2:
            score = float(len(needle))
        elif adjectival:
            score = len(needle) * 0.7
        else:
            score = len(needle) * 0.45
        whole = extra <= 2
        if score >= 2.5 and (
            best is None
            or (whole and not best[2])
            or (whole == best[2] and (score > best[0] or (score == best[0] and at < best[1])))
        ):
            best = (score, at, whole)
        start = at + 1
    return best


def classify(text, labels=None):
    """Return legend keys for this paragraph, primary first."""
    hay = normalize(text)
    if not hay:
        return []
    found = {}
    for key in TYPES:
        terms = list(SYNONYMS.get(key) or ())
        label = (labels or {}).get(key) if labels else None
        if label and len(label) >= 4:
            terms.append(label)
        for term in terms:
            hit = _term_hit(hay, term)
            if not hit:
                continue
            score, at, whole = hit
            prev = found.get(key)
            if prev is None or (whole and not prev[2]) or (
                whole == prev[2] and (score > prev[0] or (score == prev[0] and at < prev[1]))
            ):
                found[key] = (score, at, whole)
    keys = sorted(
        found,
        key=lambda key: (not found[key][2], -found[key][0], found[key][1], TYPES.index(key)),
    )
    drop = set()
    for specific, generics in _SPECIFIC_DROPS:
        if specific in found:
            drop.update(generics)
    return [key for key in keys if key not in drop]
