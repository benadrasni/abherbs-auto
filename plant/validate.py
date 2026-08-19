"""Validate a job packet before publish. No Firebase writes."""

from sources import tdwg

COLOR_OK = set(range(1, 6))
HABITAT_OK = set(range(1, 7))
PETAL_OK = set(range(1, 5))
KNOWN_L2 = set(tdwg.load()["by_code"].values())
MIN_PHOTOS = 3


def _axis_ok(values, allowed):
    return bool(values) and all(int(value) in allowed for value in values)


def validate(packet):
    """Return {ok, errors, warnings}."""
    errors = []
    warnings = list((packet.get("job") or {}).get("warnings") or [])
    job = packet.get("job") or {}
    header = packet.get("plants_header") or {}
    v2 = packet.get("plants_v2") or {}
    translations = packet.get("translations") or {}

    if not job.get("accepted_name"):
        errors.append("missing accepted_name")
    if job.get("id") is None:
        errors.append("missing numeric id")

    colors = header.get("filterColor") or []
    habitats = header.get("filterHabitat") or []
    petals = header.get("filterPetal") or []
    dists = header.get("filterDistribution") or []

    if not _axis_ok(colors, COLOR_OK):
        errors.append("filterColor missing or out of 1-5")
    if not _axis_ok(habitats, HABITAT_OK):
        errors.append("filterHabitat missing or out of 1-6")
    if not _axis_ok(petals, PETAL_OK):
        errors.append("filterPetal missing or out of 1-4")
    if not dists:
        errors.append("filterDistribution empty")
    else:
        for code in dists:
            if int(code) not in KNOWN_L2:
                errors.append("unknown TDWG L2 %s" % code)

    traits = job.get("traits") or {}
    for axis in ("color", "habitat", "petal"):
        info = traits.get(axis) or {}
        if info and not info.get("ok"):
            warnings.append("%s confidence %.2f below threshold" % (
                axis, float(info.get("confidence") or 0)
            ))

    photos = job.get("photos") or {}
    roles = photos.get("roles") or []
    if photos.get("status") != "ok" or len(roles) < MIN_PHOTOS:
        errors.append("need at least %s photos with a flower first" % MIN_PHOTOS)
    elif roles[0] not in ("flower", "inflorescence"):
        errors.append("photo 1 must be flower or inflorescence")

    illustration = job.get("illustration") or {}
    if not illustration.get("ok"):
        errors.append("illustration required")

    if not v2.get("ipniId"):
        warnings.append("missing ipniId")
    english = translations.get("en") or {}
    required = ("description", "flower", "inflorescence", "fruit", "leaf", "stem", "habitat")
    missing = [field for field in required if not english.get(field)]
    if missing:
        warnings.append("english incomplete: %s" % ", ".join(missing))

    sourced = job.get("sourced_names")
    if sourced is not None:
        from plant import common_names

        unsourced = common_names.unsourced_names(
            translations,
            sourced,
            job.get("accepted_name") or header.get("name") or "",
        )
        if unsourced:
            warnings.append(
                "unsourced common names: "
                + ", ".join("%s=%s" % (lang, name) for lang, name in unsourced)
            )

    if job.get("already_in_catalog"):
        warnings.append("already in plants_to_update")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
