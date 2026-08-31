"""Rebuild 4-step filter, name-search, and photo-search indexes.

Port of Refresher.java. Same keys and value shapes. Does not talk to Firebase.
"""

COLOR_IDS = (None, "1", "2", "3", "4", "5")
HABITAT_IDS = (None, "1", "2", "3", "4", "5", "6")
PETAL_IDS = (None, "1", "2", "3", "4")
DISTRIBUTION_IDS = (
    None,
    "10", "11", "12", "13", "14",
    "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "30", "31", "32", "33", "34", "35", "36", "37", "38",
    "40", "41", "42", "43",
    "50", "51",
    "60", "61", "62", "63",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
    "80", "81", "82", "83", "84", "85",
    "90", "91",
)

SEARCH_LANGUAGES = (
    "bg", "cs", "da", "de", "en", "es", "et", "fi", "fr", "hr", "hu", "it",
    "ja", "ko", "lt", "lv", "nl", "no", "pl", "pt", "ro", "ru", "sk", "sl",
    "sr", "sv", "uk", "zh",
)

ILLEGAL_SEARCH_CHARS = frozenset("./#$[]")

PHOTO_TAXON_TYPES = frozenset((
    "Ordo", "Genus", "Familia", "Subfamilia", "Subgenus",
    "Tribus", "Subtribus", "Sectio", "Subsectio", "Serie", "Subserie",
))

APG_META_KEYS = frozenset(("type", "count", "list", "freebase"))

FILTER_KEY_COUNT = (
    len(COLOR_IDS) * len(HABITAT_IDS) * len(PETAL_IDS) * len(DISTRIBUTION_IDS)
)


def filter_key(color, habitat, petal, distribution):
    return "_".join((
        "" if color is None else str(color),
        "" if habitat is None else str(habitat),
        "" if petal is None else str(petal),
        "" if distribution is None else str(distribution),
    ))


def generate_filter_keys():
    keys = []
    for color in COLOR_IDS:
        for habitat in HABITAT_IDS:
            for petal in PETAL_IDS:
                for distribution in DISTRIBUTION_IDS:
                    keys.append(filter_key(color, habitat, petal, distribution))
    return keys


def as_int_set(values):
    if not values:
        return set()
    if isinstance(values, dict):
        values = values.values()
    result = set()
    for value in values:
        if value is None or value == "":
            continue
        result.add(int(value))
    return result


def listing_ids(listing):
    """Plant id strings present in a lists_4_v2 value.

    Firebase turns a dense consecutive-integer map into a JSON array of
    1 / null. Treat both shapes the same.
    """
    if not listing:
        return set()
    if isinstance(listing, dict):
        return {str(key) for key, value in listing.items() if value}
    if isinstance(listing, list):
        return {str(index) for index, value in enumerate(listing) if value}
    return set()


def listing_has_token(listing, token):
    return str(token) in listing_ids(listing)


def header_values(header):
    if not header:
        return set(), set(), set(), set()
    return (
        as_int_set(header.get("filterColor")),
        as_int_set(header.get("filterHabitat")),
        as_int_set(header.get("filterPetal")),
        as_int_set(header.get("filterDistribution")),
    )


def matches_filter(header, key):
    parts = key.split("_")
    if len(parts) != 4:
        return False
    colors, habitats, petals, distributions = header_values(header)
    color, habitat, petal, distribution = parts
    if color and int(color) not in colors:
        return False
    if habitat and int(habitat) not in habitats:
        return False
    if petal and int(petal) not in petals:
        return False
    if distribution and int(distribution) not in distributions:
        return False
    return True


def _axis_options(values, allowed):
    options = [None]
    for value in sorted(values):
        token = str(value)
        if token in allowed:
            options.append(token)
    return options


def matching_keys(header):
    colors, habitats, petals, distributions = header_values(header)
    keys = []
    for color in _axis_options(colors, COLOR_IDS):
        for habitat in _axis_options(habitats, HABITAT_IDS):
            for petal in _axis_options(petals, PETAL_IDS):
                for distribution in _axis_options(distributions, DISTRIBUTION_IDS):
                    keys.append(filter_key(color, habitat, petal, distribution))
    return keys


def header_at(headers, index):
    if headers is None:
        return None
    if isinstance(headers, list):
        if 0 <= index < len(headers):
            return headers[index]
        return None
    return headers.get(str(index), headers.get(index))


def build_counts_and_lists(plant_names, headers):
    """Return (counts, lists, warnings).

    counts includes every Cartesian key (zeros included).
    lists omits empty maps.
    Plant ids are string keys, values are 1.
    """
    keys = generate_filter_keys()
    counts = {key: 0 for key in keys}
    lists = {}
    warnings = []

    for index, name in enumerate(plant_names):
        header = header_at(headers, index)
        if not header:
            warnings.append("missing header %s (%s)" % (index, name))
            continue
        for key in matching_keys(header):
            counts[key] = counts[key] + 1
            plant_list = lists.get(key)
            if plant_list is None:
                plant_list = {}
                lists[key] = plant_list
            plant_list[str(index)] = 1

    return counts, lists, warnings


def is_illegal_search_key(name):
    if not name:
        return True
    for char in name:
        if char in ILLEGAL_SEARCH_CHARS:
            return True
    return False


def _add_search_hit(search_map, name, plant_id, is_label, warnings):
    if name is None:
        return
    key = name.lower()
    if is_illegal_search_key(key):
        warnings.append("illegal search key %r for plant %s" % (key, plant_id))
        return
    entry = search_map.get(key)
    if entry is None:
        entry = {"list": {}}
        if is_label:
            entry["is_label"] = True
        search_map[key] = entry
    elif is_label and "is_label" not in entry:
        # Java only sets is_label when it creates the entry.
        pass
    entry["list"][str(plant_id)] = 1


def _translation_names(plant):
    names = plant.get("names")
    if not names:
        return []
    if isinstance(names, dict):
        items = sorted(names.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]))
        return [item[1] for item in items]
    return list(names)


def build_search_language(plant_ids, translations):
    """Build search_new/{lang} from one translations/{lang} map."""
    search_map = {}
    warnings = []
    if not translations:
        return search_map, warnings

    for latin_name, plant in translations.items():
        if latin_name not in plant_ids:
            continue
        if not isinstance(plant, dict):
            warnings.append("non-object translation for %s" % latin_name)
            continue
        plant_id = plant_ids[latin_name]
        label = plant.get("label")
        if label:
            _add_search_hit(search_map, label, plant_id, True, warnings)
        for extra in _translation_names(plant):
            if extra:
                _add_search_hit(search_map, extra, plant_id, False, warnings)

    return search_map, warnings


def build_search_all_languages(plant_names, translations_by_lang, languages=SEARCH_LANGUAGES):
    plant_ids = {}
    for index, name in enumerate(plant_names):
        plant_ids[name] = index

    search = {}
    warnings = []
    for language in languages:
        language_map, language_warnings = build_search_language(
            plant_ids, translations_by_lang.get(language)
        )
        search[language] = language_map
        warnings.extend("%s: %s" % (language, warning) for warning in language_warnings)
    return search, warnings


def _plant_synonyms(plant):
    if not plant:
        return []
    names = plant.get("synonyms")
    if not names:
        return []
    if isinstance(names, dict):
        items = sorted(names.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]))
        return [item[1] for item in items]
    return list(names)


def build_search_latin(plant_names, plants_v2):
    search_map = {}
    warnings = []
    plants_v2 = plants_v2 or {}

    for index, catalog_name in enumerate(plant_names):
        plant = plants_v2.get(catalog_name) or {}
        label = plant.get("name") or catalog_name
        _add_search_hit(search_map, label, index, True, warnings)
        for synonym in _plant_synonyms(plant):
            if synonym == "":
                warnings.append("empty synonym for %s" % catalog_name)
            if synonym and "." in synonym:
                continue
            _add_search_hit(search_map, synonym, index, False, warnings)

    return search_map, warnings


def _as_int(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return int(round(float(value)))


def _freebase_tokens(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = str(value).split(",")
    tokens = []
    for item in items:
        if not item:
            continue
        text = str(item).strip()
        tokens.append(text[text.rfind("/") + 1:])
    return tokens


def _ensure_freebase_map(photo_search):
    freebase_map = photo_search.get("m")
    if freebase_map is None:
        freebase_map = {}
        photo_search["m"] = freebase_map
    return freebase_map


def parse_apg_iv(taxon, node, photo_search, path):
    if not isinstance(node, dict):
        return

    item = {}
    desired = False
    freebase_ids = []

    for key, value in node.items():
        if key == "type":
            desired = value in PHOTO_TAXON_TYPES
        elif key == "count":
            item["count"] = _as_int(value)
        elif key == "list":
            item["path"] = path + "list"
        elif key == "freebase":
            freebase_ids.extend(_freebase_tokens(value))
        else:
            parse_apg_iv(key, value, photo_search, path + key + "/")

    if desired:
        photo_search[taxon.lower()] = item
        if freebase_ids:
            freebase_map = _ensure_freebase_map(photo_search)
            for token in freebase_ids:
                freebase_map[token] = item


def build_photo_search(plant_names, plants_v2, apg_iv):
    photo_search = {}
    warnings = []
    plants_v2 = plants_v2 or {}

    if apg_iv:
        parse_apg_iv("", apg_iv, photo_search, "APG IV_v3/")

    for catalog_name in plant_names:
        entry = {"count": 1, "path": catalog_name}
        photo_search[catalog_name.lower()] = entry

        plant = plants_v2.get(catalog_name)
        if not plant:
            warnings.append("missing plants_v2 %s" % catalog_name)
            continue

        freebase_id = plant.get("freebaseId")
        if freebase_id:
            freebase_map = _ensure_freebase_map(photo_search)
            for token in _freebase_tokens(freebase_id):
                freebase_map[token] = entry

        for synonym in _plant_synonyms(plant):
            if not synonym:
                continue
            key = synonym.lower()
            if key not in photo_search:
                photo_search[key] = {"count": 1, "path": catalog_name}

    return photo_search, warnings
