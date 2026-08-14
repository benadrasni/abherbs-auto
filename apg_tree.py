"""Incremental APG IV_v3 insert. Pure tree mutation, no Firebase."""

META = frozenset(("type", "count", "list", "freebase"))

# Ranks that may sit under extra taxa (tribe, section) already in the live tree.
NESTED_RANKS = frozenset((
    "Subfamilia", "Tribus", "Subtribus",
    "Genus", "Subgenus",
    "Supersectio", "Sectio", "Subsectio",
    "Serie", "Subserie",
))


def ordered_path(apg_map):
    """Superregnum → … → lowest rank from a plants_v2 APGIV map."""
    items = []
    for key, value in (apg_map or {}).items():
        if "_" not in str(key) or not value:
            continue
        number, rank = str(key).split("_", 1)
        try:
            index = int(number)
        except ValueError:
            continue
        items.append((index, rank, value))
    items.sort(reverse=True)
    return [(rank, value) for _, rank, value in items]


def apg_map_from_path(path):
    """Rebuild a plants_v2 APGIV map from a Superregnum → leaf walk."""
    result = {}
    for index, (rank, name) in enumerate(reversed(list(path or []))):
        result["%02d_%s" % (index, rank)] = name
    return result


def _type_matches(node, rank):
    if not isinstance(node, dict):
        return False
    node_type = node.get("type")
    return node_type is None or node_type == rank


def find_named(node, name, rank, path=None):
    """Relative paths under node to children named `name` with a matching type."""
    path = path or []
    hits = []
    if not isinstance(node, dict):
        return hits
    for key, child in node.items():
        if key in META or not isinstance(child, dict):
            continue
        child_path = path + [key]
        if key == name and _type_matches(child, rank):
            hits.append(child_path)
        hits.extend(find_named(child, name, rank, child_path))
    return hits


def _score(node, rel):
    current = node
    for step in rel:
        current = current[step]
    children = sum(1 for key in current if key not in META)
    return (
        len(current.get("list") or {}),
        children,
        1 if current.get("freebase") else 0,
        len(rel),
    )


def pick_existing(hits, node):
    """Prefer the richest namesake (most plants, then children, then freebase)."""
    if not hits:
        return None
    return max(hits, key=lambda rel: _score(node, rel))


def choose_child(node, name, rank):
    """Pick a relative path to an existing name/rank, or None."""
    return pick_existing(find_named(node, name, rank), node)


def _touch(node, rank, token):
    if "type" not in node or not node.get("type"):
        node["type"] = rank
    node.setdefault("list", {})
    node["list"][str(token)] = 1
    node["count"] = len(node["list"])


def apply_plant(tree, apg_map, plant_id):
    """Add plant_id along the APG path, reusing nested taxa when they exist.

    Live trees often have extra ranks (Tribus, Sectio) that plants_v2.APGIV
    omits. If Familia already contains Digitalideae/Digitalis, a Genus=Digitalis
    step lands there instead of creating a sibling genus.

    When several namesakes exist, the richest node wins (list size, children,
    freebase), so a thin stray genus does not beat the classified one.

    Returns {created: [names], path: [(rank, name), ...]} for the walk used.
    """
    path = ordered_path(apg_map)
    created = []
    walked = []
    node = tree
    token = str(plant_id)
    for rank, name in path:
        rel = choose_child(node, name, rank)
        if not rel:
            node[name] = {"type": rank, "count": 0, "list": {}}
            created.append(name)
            rel = [name]
        for index, step in enumerate(rel):
            child = node[step]
            step_rank = child.get("type") or (rank if index == len(rel) - 1 else rank)
            _touch(child, step_rank, token)
            walked.append((child.get("type") or step_rank, step))
            node = child
    return {"created": created, "path": walked}


def patch_from_packet(packet):
    apg = (packet.get("plants_v2") or {}).get("APGIV") or {}
    return {
        "plant_id": (packet.get("job") or {}).get("id"),
        "path": ordered_path(apg),
        "apg": apg,
    }
