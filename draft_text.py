"""Draft short English species-page sections from several sources.

Wikipedia first, then unused sentences, then conservative genus/family
fallbacks informed by sister catalog texts. Does not invent a silent
default for a field with no support.

Common names in other languages are not drafted here. They must come
from a source (see common_names.py); never translate the English name.
"""

import re

from sources import wikipedia as wiki_api

MANDATORY = (
    "description",
    "flower",
    "inflorescence",
    "fruit",
    "leaf",
    "stem",
    "habitat",
)

FIELD_KEYWORDS = {
    "flower": (
        "flower", "flowers", "blossom", "bloom", "corolla", "tepal", "tepals",
        "petal", "petals",
    ),
    "inflorescence": (
        "inflorescence", "cluster", "capitulum", "corymb", "raceme",
        "umbel", "cyme", "panicle", "pseudanthium", "spike", "spikes",
        "floral stem", "flowered",
    ),
    "fruit": (
        "fruit", "fruits", "samara", "achene", "berry", "berries",
        "capsule", "pod", "seed", "seeds",
    ),
    "leaf": ("leaf", "leaves", "foliage", "rosette", "blade", "blades"),
    "stem": (
        "stem", "stems", "trunk", "bark", "shoot", "rhizome",
        "unbranched", "erect",
    ),
    "habitat": (
        "habitat", "native", "naturalized", "woodland", "woodlands",
        "forest", "forests", "meadow", "meadows", "grassland", "grasslands",
        "garden", "gardens", "cultivated", "rocky", "rock", "scrub",
        "pasture", "clearing", "grows",
    ),
}

# Same codes as infer_traits / the 4-step filter.
HABITAT_CODE_WORDS = {
    1: (
        "meadow", "meadows", "grassland", "grasslands", "pasture",
        "pastures", "lawn", "lawns", "prairie", "prairies",
    ),
    2: (
        "garden", "gardens", "cultivated", "cultivation", "ornamental",
        "award of garden merit",
    ),
    3: (
        "wetland", "wetlands", "marsh", "marshes", "bog", "bogs",
        "swamp", "pond", "aquatic",
    ),
    4: (
        "forest", "forests", "woodland", "woodlands", "woods",
        "understorey", "understory", "glade", "glades",
    ),
    5: ("rock", "rocky", "alpine", "scree", "cliff", "outcrop", "scrub"),
    6: ("tree", "shrub", "woody"),
}

SKIP_SECTIONS = (
    "references", "further reading", "external links", "see also",
    "gallery", "notes", "bibliography", "etymology", "uses", "culinary",
    "culinary uses", "in culture", "culture", "toxicity", "toxicity in pets",
    "medical", "other",
)

NOISE = {
    "fruit": (
        "virus", "bulblet", "bulblets", "grow plants from seed",
        "instead of",
    ),
    "flower": (
        "bible", "virgin", "fresco", "iconography", "annunciation",
        "fleur de", "symbol of", "symbolizes", "sacred to",
    ),
}

MAX_SENTENCES = {
    "description": 4,
    "flower": 4,
    "inflorescence": 4,
    "fruit": 4,
    "leaf": 4,
    "stem": 4,
    "habitat": 4,
}

MAX_CHARS = {
    "description": 900,
    "flower": 720,
    "inflorescence": 640,
    "fruit": 560,
    "leaf": 720,
    "stem": 640,
    "habitat": 720,
}

GENUS_FRUIT = {
    "lilium": "Fruit a 3-parted capsule.",
    "digitalis": "Fruit a capsule with numerous small seeds.",
    "fritillaria": "Fruit a capsule.",
    "tulipa": "Fruit a capsule.",
}

FAMILY_FRUIT = {
    "liliaceae": "Fruit a capsule.",
    "plantaginaceae": "Fruit a capsule.",
}


def _join(chunks, limit=2, max_chars=320):
    picked = []
    length = 0
    for sentence in chunks:
        if not sentence or sentence in picked:
            continue
        extra = len(sentence) + (1 if picked else 0)
        if picked and length + extra > max_chars:
            break
        picked.append(sentence)
        length += extra
        if len(picked) >= limit:
            break
    return " ".join(picked) if picked else None


def _noisy(field, sentence):
    lower = sentence.lower()
    return any(token in lower for token in NOISE.get(field) or ())


def _usable(field, sentence, used):
    if not sentence or sentence in used:
        return False
    if _noisy(field, sentence):
        return False
    if len(sentence) < 12:
        return False
    return True


def _matches(sentence, keywords):
    lower = sentence.lower()
    return any(keyword in lower for keyword in keywords)


def _section_pool(wikipedia):
    split = wiki_api.split_sections((wikipedia or {}).get("extract") or "")
    lead = split["lead"]
    sections = split["sections"]
    description_body = sections.get("Description") or ""
    ecology = sections.get("Ecology") or ""
    distribution = (
        sections.get("Distribution")
        or sections.get("Distribution and habitat")
        or ""
    )
    other = []
    for name, body in sections.items():
        if name.lower() in SKIP_SECTIONS:
            continue
        if name in ("Description", "Ecology", "Distribution", "Distribution and habitat"):
            continue
        other.append(body)
    return {
        "lead": lead,
        "description": description_body,
        "ecology": ecology,
        "distribution": distribution,
        "other": "\n".join(other),
    }


def _pick(field, texts, used):
    keywords = FIELD_KEYWORDS[field]
    hits = []
    for text in texts:
        for sentence in wiki_api.sentences(text or ""):
            if _usable(field, sentence, used) and _matches(sentence, keywords):
                hits.append(sentence)
    return _join(
        hits,
        limit=MAX_SENTENCES[field],
        max_chars=MAX_CHARS[field],
    )


def _sister_fruit(sisters):
    texts = []
    for item in sisters or []:
        english = item.get("en") if isinstance(item, dict) else None
        if not english:
            continue
        fruit = english.get("fruit") or ""
        if fruit:
            texts.append(fruit.lower())
    if len(texts) < 2:
        return None
    if not all("capsule" in text for text in texts):
        return None
    if any("3-parted" in text or "3-valved" in text for text in texts):
        return "Fruit a 3-parted capsule."
    if any("beak" in text for text in texts):
        return "Beaked capsule containing numerous small seeds."
    return "Fruit a capsule."


def _family_or_genus_fruit(resolved, sisters):
    hint = _sister_fruit(sisters)
    if hint:
        return hint
    genus = ((resolved or {}).get("genus") or "").lower()
    if genus in GENUS_FRUIT:
        return GENUS_FRUIT[genus]
    family = ((resolved or {}).get("family") or "").lower()
    return FAMILY_FRUIT.get(family)


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _overlaps_description(sentence, description):
    if not sentence or not description:
        return False
    sentence_n = _normalize(sentence)
    description_n = _normalize(description)
    if sentence_n in description_n or description_n in sentence_n:
        return True
    stop = {
        "the", "a", "an", "it", "is", "in", "to", "of", "and", "or", "for",
        "with", "from", "on", "as", "by", "its", "this", "that", "are",
    }
    words = [word for word in re.findall(r"[a-z0-9]+", sentence_n) if word not in stop]
    described = set(
        word for word in re.findall(r"[a-z0-9]+", description_n) if word not in stop
    )
    if len(words) >= 5:
        shared = sum(1 for word in words if word in described)
        if shared / float(len(words)) >= 0.7:
            return True
    return False


def _trim_against_description(text, description):
    kept = [
        sentence
        for sentence in wiki_api.sentences(text or "")
        if not _overlaps_description(sentence, description)
    ]
    return " ".join(kept) if kept else None


def _codes_in_sentence(sentence, codes):
    lower = (sentence or "").lower()
    hit = []
    for code in codes:
        if any(word in lower for word in HABITAT_CODE_WORDS.get(int(code), ())):
            hit.append(int(code))
    return hit


def _draft_habitat(pool, extra_texts, description, codes, used):
    """Pick habitat sentences that support the filterHabitat codes."""
    codes = [int(code) for code in (codes or []) if str(code).isdigit() or isinstance(code, int)]
    texts = [
        pool.get("ecology") or "",
        pool.get("distribution") or "",
        pool.get("other") or "",
        pool.get("lead") or "",
        pool.get("description") or "",
    ]
    texts.extend(extra_texts or [])
    scored = []
    for text in texts:
        for sentence in wiki_api.sentences(text):
            if _overlaps_description(sentence, description):
                continue
            if _noisy("habitat", sentence):
                continue
            if codes:
                hit = _codes_in_sentence(sentence, codes)
                if not hit:
                    continue
                scored.append((len(hit), sentence, hit))
            elif _matches(sentence, FIELD_KEYWORDS["habitat"]):
                scored.append((1, sentence, []))
    scored.sort(key=lambda item: -item[0])
    picked = []
    covered = set()
    for _, sentence, hit in scored:
        if sentence in picked or sentence in used:
            continue
        if codes and hit and covered.issuperset(hit) and picked:
            continue
        picked.append(sentence)
        covered.update(hit)
        if len(picked) >= MAX_SENTENCES["habitat"]:
            break
        if codes and covered.issuperset(codes):
            break
    return _join(
        picked,
        limit=MAX_SENTENCES["habitat"],
        max_chars=MAX_CHARS["habitat"],
    )


def _lifeform_stem(resolved):
    lifeform = ((resolved or {}).get("lifeform") or "").lower()
    if "tree" in lifeform:
        return "Woody tree."
    if "shrub" in lifeform:
        return "Woody shrub."
    if "bulb" in lifeform:
        return "Leafy floral stem arising from a bulb."
    if lifeform:
        return "Herbaceous %s." % lifeform
    return None


def draft_english(wikipedia, resolved=None, sisters=None, habitat_codes=None, extra_sources=None):
    """Return translations/en body fields + sourceUrls."""
    wiki = wikipedia or {}
    resolved = resolved or {}
    pool = _section_pool(wiki)
    used = set()
    fields = {}
    sources = []
    extra_texts = []
    if wiki.get("url"):
        sources.append(wiki["url"])
    for item in extra_sources or []:
        if item.get("extract"):
            extra_texts.append(item["extract"])
        if item.get("url"):
            sources.append(item["url"])

    # Specific fields first so "bears several flowers" is not stolen by flower.
    field_texts = {
        "inflorescence": [pool["description"], pool["lead"], pool["other"]] + extra_texts,
        "fruit": [pool["description"], pool["lead"], pool["other"]] + extra_texts,
        "leaf": [pool["description"], pool["lead"]] + extra_texts,
        "stem": [pool["description"], pool["lead"]] + extra_texts,
        "flower": [pool["description"], pool["lead"]] + extra_texts,
    }
    for field, texts in field_texts.items():
        value = _pick(field, texts, used)
        if value:
            fields[field] = value
            used.update(wiki_api.sentences(value))

    desc_bits = []
    desc_bits.extend(wiki_api.sentences(pool["lead"])[:4])
    desc_bits.extend(wiki_api.sentences(pool["description"])[:4])
    fields["description"] = _join(
        desc_bits, limit=MAX_SENTENCES["description"], max_chars=MAX_CHARS["description"]
    )
    habitat = _draft_habitat(
        pool,
        extra_texts,
        fields.get("description") or "",
        habitat_codes,
        used,
    )
    if habitat:
        fields["habitat"] = habitat

    leftover = []
    for text in (
        pool["description"],
        pool["lead"],
        pool["ecology"],
        pool["distribution"],
    ) + tuple(extra_texts):
        leftover.extend(wiki_api.sentences(text or ""))
    for field in MANDATORY:
        if fields.get(field):
            continue
        keywords = FIELD_KEYWORDS.get(field) or ()
        extra = [
            sentence
            for sentence in leftover
            if _usable(field, sentence, used) and _matches(sentence, keywords)
        ]
        if not extra:
            extra = [
                sentence
                for sentence in leftover
                if _usable(field, sentence, set()) and _matches(sentence, keywords)
            ]
        value = _join(extra, limit=1, max_chars=MAX_CHARS[field])
        if value:
            fields[field] = value

    if fields.get("habitat") and fields.get("description"):
        trimmed = _trim_against_description(fields["habitat"], fields["description"])
        if trimmed:
            fields["habitat"] = trimmed
        else:
            fields.pop("habitat", None)

    if not fields.get("fruit"):
        fallback = _family_or_genus_fruit(resolved, sisters)
        if fallback:
            fields["fruit"] = fallback
            sources.append("genus/family fruit type from catalog congeners")
    if not fields.get("stem"):
        fallback = _lifeform_stem(resolved)
        if fallback:
            fields["stem"] = fallback
            sources.append("WCVP lifeform")

    result = {key: value for key, value in fields.items() if value}
    if sources:
        result["sourceUrls"] = list(dict.fromkeys(sources))
    if wiki.get("url"):
        result["wikipedia"] = wiki["url"]
    missing = [field for field in MANDATORY if not result.get(field)]
    if missing:
        result["_draft_missing"] = missing
    return result
