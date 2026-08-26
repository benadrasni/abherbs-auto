"""Rename a live catalog species, including GCS photos.

Copies plants_v2, headers, translations, synonyms, search, APG, observations,
and photo objects. Does not rebuild 4-step filter indexes (those key by id).

Run from ingest:

  .venv/bin/python -m scripts.rename_plant "Acca sellowiana" "Feijoa sellowiana"
  .venv/bin/python -m scripts.rename_plant "Acca sellowiana" "Feijoa sellowiana" --apply
"""

import argparse
import os
import shutil
import sys
import urllib.request
from datetime import date
from urllib.parse import quote

import firebase_admin
from firebase_admin import credentials, db
from google.cloud import storage

import constants
from catalog import apg_tree
from plant import resolve as plant_resolve
from sources import gbif
from sources import wcvp

PHOTO_BUCKET = "https://storage.googleapis.com/abherbs-resources/"
APG_META = frozenset(("type", "count", "list", "freebase"))


def log(message):
    print(message, flush=True)


def init_firebase():
    if firebase_admin._apps:
        return
    cred = credentials.Certificate(constants.certificate_firebase)
    firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})


def slug(name):
    return name.replace(" ", "_")


def photo_prefix(name):
    return plant_resolve.photo_prefix(name)


def remap_filename(filename, old_name, new_name):
    old_slug = slug(old_name)
    new_slug = slug(new_name)
    old_pre = photo_prefix(old_name)
    new_pre = photo_prefix(new_name)
    if filename.startswith(old_slug):
        return new_slug + filename[len(old_slug) :]
    for index in range(1, 20):
        token = "%s%s.webp" % (old_pre, index)
        if filename == token:
            return "%s%s.webp" % (new_pre, index)
    return filename


def remap_relpath(rel, old_name, new_name):
    parts = rel.split("/")
    old_slug = slug(old_name)
    new_slug = slug(new_name)
    parts = [new_slug if part == old_slug else part for part in parts]
    if parts:
        parts[-1] = remap_filename(parts[-1], old_name, new_name)
    return "/".join(parts)


def apg_without_old_genus(apg_map, new_genus):
    ordered = apg_tree.ordered_path(apg_map)
    old_genus = None
    for rank, name in ordered:
        if rank == "Genus":
            old_genus = name
            break
    path = []
    for rank, name in ordered:
        if rank == "Subgenus" and name == new_genus:
            continue
        if rank == "Genus":
            path.append(("Genus", new_genus))
            # Nested ranks under the old genus (subgenus, section) stay only
            # when the genus itself does not change.
            if old_genus != new_genus:
                break
            continue
        path.append((rank, name))
    return apg_tree.apg_map_from_path(path)


def genus_parent_path(apg_map):
    parts = ["APG IV_v3"]
    old_genus = None
    for rank, name in apg_tree.ordered_path(apg_map):
        if rank == "Genus":
            old_genus = name
            break
        parts.append(name)
    return "/".join(parts), old_genus


def family_firebase_path(apg_map):
    parts = ["APG IV_v3"]
    for rank, name in apg_tree.ordered_path(apg_map):
        parts.append(name)
        if rank == "Familia":
            return "/".join(parts)
    return None


def existing_genus_firebase_path(family_path, family_node, genus):
    """Path of an already-catalogued Genus under this family, else None.

    Live trees nest genera under tribe or subfamily (Malva under Malveae)
    even when the source plant's APGIV omitted those ranks. Joining that
    node avoids a sibling duplicate and keeps search_photo genus tokens.
    """
    if not family_path or not genus:
        return None
    rel = apg_tree.choose_child(family_node, genus, "Genus")
    if not rel:
        return None
    return "%s/%s" % (family_path, "/".join(rel))


def all_genus_firebase_paths(family_path, family_node, genus):
    """Every Genus namesake under the family, richest first."""
    if not family_path or not genus or not isinstance(family_node, dict):
        return []
    hits = apg_tree.find_named(family_node, genus, "Genus")
    ranked = sorted(hits, key=lambda rel: apg_tree._score(family_node, rel), reverse=True)
    return ["%s/%s" % (family_path, "/".join(rel)) for rel in ranked if rel]


def resolve_move_paths(family_path, family_node, apg_parent, old_genus, new_genus):
    """Live old/new genus paths. Prefer nested namesakes over APGIV siblings.

    A brand-new genus is created as a sibling of the live old genus, not at
    the APGIV parent. Live trees often insert a subtribe (Malinae under
    Maleae) that plants_v2.APGIV omitted; using the APGIV parent would put
    Aria next to Malinae instead of next to Sorbus.
    """
    existing_new = existing_genus_firebase_path(family_path, family_node, new_genus)
    existing_old = existing_genus_firebase_path(family_path, family_node, old_genus)
    old_path = existing_old or (
        "%s/%s" % (apg_parent, old_genus) if apg_parent and old_genus else None
    )
    if existing_new:
        new_path = existing_new
    elif old_path and new_genus:
        new_path = "%s/%s" % (old_path.rsplit("/", 1)[0], new_genus)
    elif apg_parent and new_genus:
        new_path = "%s/%s" % (apg_parent, new_genus)
    else:
        new_path = None
    others = [
        path
        for path in all_genus_firebase_paths(family_path, family_node, old_genus)
        if path != old_path
    ]
    return {
        "old_path": old_path,
        "new_path": new_path,
        "other_old_paths": others,
        "reused_new": bool(existing_new),
        "reused_old": bool(existing_old),
    }


def divergent_ancestor_paths(old_path, new_path):
    """Old-genus ancestors that are not on the new genus path (nearest first).

    After an empty old genus is deleted, those tribe/subtribe nodes still list
    this plant. The first common ancestor is excluded so higher ranks keep it.
    """
    new_prefixes = set()
    new_parts = new_path.split("/")
    for end in range(1, len(new_parts) + 1):
        new_prefixes.add("/".join(new_parts[:end]))
    old_parts = old_path.split("/")
    out = []
    for end in range(len(old_parts) - 1, 1, -1):
        ancestor = "/".join(old_parts[:end])
        if ancestor == "APG IV_v3":
            break
        if ancestor in new_prefixes:
            break
        out.append(ancestor)
    return out


def strip_token_from_divergent_ancestors(old_path, new_path, token, apply):
    """Drop plant id from old-path-only ancestors; delete a node if its list empties."""
    token = str(token)
    deleted = []
    for ancestor in divergent_ancestor_paths(old_path, new_path):
        node = db.reference(ancestor).get() or {}
        listing = dict(node.get("list") or {})
        if token not in listing and token not in {str(key) for key in listing}:
            continue
        remaining = {key: value for key, value in listing.items() if str(key) != token}
        if remaining:
            log("APG remove %s from %s (%s left)" % (token, ancestor, len(remaining)))
            if apply:
                db.reference("%s/list/%s" % (ancestor, token)).delete()
                db.reference("%s/count" % ancestor).set(len(remaining))
        else:
            log("APG delete empty %s" % ancestor)
            deleted.append(ancestor)
            if apply:
                db.reference(ancestor).delete()
    return deleted


def add_token_up_tree(leaf_path, token, apply):
    """Add plant id to ancestor lists until one already contains it."""
    parts = leaf_path.split("/")
    token = str(token)
    added = []
    for end in range(len(parts) - 1, 1, -1):
        ancestor = "/".join(parts[:end])
        if ancestor == "APG IV_v3":
            break
        node = db.reference(ancestor).get() or {}
        listing = dict(node.get("list") or {})
        if token in listing or str(token) in {str(key) for key in listing}:
            break
        listing[token] = 1
        log("APG add %s to %s (count %s)" % (token, ancestor, len(listing)))
        added.append(ancestor)
        if apply:
            db.reference("%s/list/%s" % (ancestor, token)).set(1)
            db.reference("%s/count" % ancestor).set(len(listing))
    return added


def adjust_synonyms(synonyms, old_name, new_name, old_author, old_ipni):
    ipni = []
    for item in (synonyms or {}).get("ipni") or []:
        if not isinstance(item, dict):
            continue
        if item.get("name") == new_name and not item.get("suffix"):
            continue
        ipni.append(item)
    names = {(item.get("name"), item.get("suffix") or "") for item in ipni}
    if (old_name, "") not in names:
        href = ""
        if old_ipni:
            href = "/taxon/urn:lsid:ipni.org:names:%s" % old_ipni
        ipni.insert(
            0,
            {
                "name": old_name,
                "author": old_author or "",
                "suffix": "",
                "href": href,
            },
        )
    return {"ipni": ipni}


def compact_synonym_names(plant, synonyms, old_name, new_name):
    names = []
    seen = set()
    for item in (synonyms.get("ipni") or [])[:12]:
        name = item.get("name")
        if not name or item.get("suffix") or name == new_name:
            continue
        if name not in seen:
            seen.add(name)
            names.append(name)
    existing = plant.get("synonyms") or []
    if isinstance(existing, dict):
        existing = list(existing.values())
    for name in existing:
        if name and name != new_name and name not in seen:
            names.append(name)
            seen.add(name)
    if old_name not in seen:
        names.insert(0, old_name)
    return names[:8]


def catalog_folder(plant):
    illustration = plant.get("illustrationUrl") or ""
    parts = illustration.split("/")
    if len(parts) >= 3:
        return "/".join(parts[:3])
    photos = plant.get("photoUrls") or []
    if photos:
        return "/".join(str(photos[0]).split("/")[:3])
    return ""


def remapped_catalog_folder(plant, old_name, new_name):
    folder = catalog_folder(plant)
    if not folder:
        return ""
    return remap_relpath(folder, old_name, new_name)


def should_delete_old_gcs_folder(plant, old_name, new_name):
    """False when photos already live under the accepted-name slug."""
    old_folder = catalog_folder(plant)
    return bool(old_folder) and old_folder != remapped_catalog_folder(
        plant, old_name, new_name
    )


def copy_gcs_catalog(bucket, plant, old_name, new_name, apply):
    folder = catalog_folder(plant)
    prefix = "photos/%s/" % folder
    blobs = list(bucket.list_blobs(prefix=prefix))
    planned = []
    for blob in blobs:
        dest = "photos/" + remap_relpath(blob.name[len("photos/") :], old_name, new_name)
        planned.append((blob.name, dest, blob.size))
    for src, dest, size in planned:
        if src == dest:
            log("GCS keep %s (%s)" % (src, size))
            continue
        log("GCS %s -> %s (%s)" % (src, dest, size))
        if apply:
            source = bucket.blob(src)
            bucket.copy_blob(source, bucket, dest)
            copied = bucket.blob(dest)
            try:
                copied.make_public()
            except Exception as exc:
                log("  make_public skipped: %s" % exc)
    return planned


def copy_gcs_observations(bucket, old_name, new_name, apply):
    old_slug = slug(old_name)
    new_slug = slug(new_name)
    planned = []
    for blob in bucket.list_blobs(prefix="observations/"):
        if "/%s/" % old_slug not in blob.name:
            continue
        dest = blob.name.replace("/%s/" % old_slug, "/%s/" % new_slug)
        planned.append((blob.name, dest, blob.size))
        log("GCS obs %s -> %s (%s)" % (blob.name, dest, blob.size))
        if apply:
            bucket.copy_blob(bucket.blob(blob.name), bucket, dest)
            try:
                bucket.blob(dest).make_public()
            except Exception as exc:
                log("  make_public skipped: %s" % exc)
    return planned


def public_object_url(object_name):
    """GCS public URL. Percent-encode hybrid × and other non-ASCII in the path."""
    return PHOTO_BUCKET + quote(object_name, safe="/@")


def verify_public(object_names):
    failures = []
    for name in object_names:
        url = public_object_url(name)
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
            if status >= 400:
                with urllib.request.urlopen(url, timeout=30) as response:
                    status = response.status
            if status >= 400:
                failures.append((name, status))
            log("HTTP %s %s" % (status, name))
        except Exception as exc:
            failures.append((name, str(exc)))
            log("HTTP fail %s %s" % (name, exc))
    return failures


def copy_keyed_tree(root, old_name, new_name, apply, delete_old=False):
    languages = db.reference(root).get(shallow=True) or {}
    moved = []
    for language in languages:
        if any(char in language for char in "./#$[]"):
            continue
        payload = db.reference("%s/%s/%s" % (root, language, old_name)).get()
        if not payload:
            continue
        moved.append(language)
        log("%s/%s  %s -> %s" % (root, language, old_name, new_name))
        if apply:
            existing = db.reference("%s/%s/%s" % (root, language, new_name)).get()
            if existing:
                raise SystemExit("%s/%s/%s already exists" % (root, language, new_name))
            db.reference("%s/%s/%s" % (root, language, new_name)).set(payload)
            if delete_old:
                db.reference("%s/%s/%s" % (root, language, old_name)).delete()
    return moved


def delete_keyed_tree(root, old_name, languages):
    for language in languages:
        log("delete %s/%s/%s" % (root, language, old_name))
        db.reference("%s/%s/%s" % (root, language, old_name)).delete()


def rewrite_observation(obs, old_name, new_name):
    if not isinstance(obs, dict):
        return obs
    out = dict(obs)
    if out.get("plant") == old_name:
        out["plant"] = new_name
    paths = out.get("photoPaths")
    if isinstance(paths, list):
        out["photoPaths"] = [
            remap_relpath(path, old_name, new_name) if isinstance(path, str) else path
            for path in paths
        ]
    elif isinstance(paths, dict):
        out["photoPaths"] = {
            key: remap_relpath(path, old_name, new_name)
            if isinstance(path, str)
            else path
            for key, path in paths.items()
        }
    return out


def move_observation_index(kind, old_name, new_name, apply):
    """kind is observations/public or observations/by users/{uid}."""
    payload = db.reference("%s/by plant/%s" % (kind, old_name)).get()
    if not payload:
        return 0
    log("obs %s/by plant %s -> %s" % (kind, old_name, new_name))
    listing = payload.get("list") or payload
    if apply:
        if isinstance(listing, dict):
            rewritten = {
                key: rewrite_observation(value, old_name, new_name)
                for key, value in listing.items()
            }
            db.reference("%s/by plant/%s" % (kind, new_name)).set({"list": rewritten} if "list" in payload else rewritten)
        else:
            db.reference("%s/by plant/%s" % (kind, new_name)).set(
                rewrite_observation(payload, old_name, new_name)
            )
        db.reference("%s/by plant/%s" % (kind, old_name)).delete()
    return 1


def patch_observation_rows(old_name, new_name, apply):
    moved = 0
    public = db.reference("observations/public/by plant/%s" % old_name).get()
    rows = []
    if public:
        listing = public.get("list") or {}
        for key, obs in listing.items():
            rows.append(("public", key, obs))
    users = db.reference("observations/by users").get(shallow=True) or {}
    for uid in users:
        node = db.reference("observations/by users/%s/by plant/%s" % (uid, old_name)).get()
        if not node:
            continue
        listing = node.get("list") or {}
        for key, obs in listing.items():
            rows.append((uid, key, obs))
    seen_dates = set()
    for owner, obs_id, obs in rows:
        obs = rewrite_observation(obs, old_name, new_name)
        millis = None
        if isinstance(obs.get("date"), dict):
            millis = obs["date"].get("time")
        if millis is None and str(obs_id).split("_")[-1].isdigit():
            millis = int(str(obs_id).split("_")[-1])
        if owner == "public" and millis is not None:
            path = "observations/public/by date/list/%s" % millis
            log("obs public by date %s" % millis)
            if apply:
                db.reference(path).set(obs)
            seen_dates.add(("public", millis))
        if owner != "public":
            path = "observations/by users/%s/by date/list/%s" % (owner, obs_id)
            log("obs user %s by date %s" % (owner, obs_id))
            if apply:
                current = db.reference(path).get()
                if current:
                    db.reference(path).set(rewrite_observation(current, old_name, new_name))
        moved += 1
    moved += move_observation_index("observations/public", old_name, new_name, apply)
    for uid in users:
        moved += move_observation_index(
            "observations/by users/%s" % uid, old_name, new_name, apply
        )
    return moved


def plan_search_photo_updates(
    photo,
    old_name,
    new_name,
    apg_genus_path,
    old_genus_remaining=None,
    deleted_apg_paths=None,
):
    """Remap species paths and genus tokens. Does not rewrite other plants' APG paths."""
    old_genus = old_name.split()[0]
    new_genus = new_name.split()[0]
    deleted_list_paths = set()
    for path in deleted_apg_paths or []:
        if path.endswith("/list"):
            deleted_list_paths.add(path)
        else:
            deleted_list_paths.add(path + "/list")
    planned = {}

    def put(key, value):
        planned[key] = value

    def consider(key, value):
        if not isinstance(value, dict):
            return
        path = value.get("path") or ""
        if path == old_name:
            put(key, dict(value, path=new_name))
        elif path in deleted_list_paths:
            put(key, {"count": 1, "path": new_name})

    for key, value in photo.items():
        if key == "m":
            continue
        consider(key, value)
    m = photo.get("m") if isinstance(photo.get("m"), dict) else {}
    for token, value in m.items():
        consider("m/%s" % token, value)

    put(new_name.lower(), {"count": 1, "path": new_name})
    put(old_name.lower(), {"count": 1, "path": new_name})

    if old_genus == new_genus:
        return list(planned.items())

    old_key = old_genus.lower()
    new_key = new_genus.lower()
    old_entry = photo.get(old_key) if isinstance(photo.get(old_key), dict) else None
    if old_genus_remaining == 0:
        put(old_key, {"count": 1, "path": new_name})
    elif old_genus_remaining is not None and old_entry:
        put(old_key, dict(old_entry, count=old_genus_remaining))

    old_genus_list_path = (old_entry or {}).get("path") if old_entry else None
    if old_genus_list_path:
        for token, value in m.items():
            if not isinstance(value, dict) or value.get("path") != old_genus_list_path:
                continue
            if old_genus_remaining == 0:
                put("m/%s" % token, {"count": 1, "path": new_name})
            elif old_genus_remaining is not None:
                put("m/%s" % token, dict(value, count=old_genus_remaining))

    new_list_path = (apg_genus_path + "/list") if apg_genus_path else None
    new_entry = photo.get(new_key) if isinstance(photo.get(new_key), dict) else None
    if new_entry and new_list_path and (new_entry.get("path") or "") == new_list_path:
        put(new_key, dict(new_entry, count=(new_entry.get("count") or 0) + 1))
        for token, value in m.items():
            if isinstance(value, dict) and value.get("path") == new_list_path:
                put(
                    "m/%s" % token,
                    dict(value, count=(value.get("count") or 0) + 1),
                )
    elif new_list_path:
        put(new_key, {"count": 1, "path": new_list_path})
    return list(planned.items())


def update_search_photo(
    old_name,
    new_name,
    apg_genus_path,
    apply,
    old_genus_remaining=None,
    deleted_apg_paths=None,
):
    photo = db.reference("search_photo").get() or {}
    updates = plan_search_photo_updates(
        photo,
        old_name,
        new_name,
        apg_genus_path,
        old_genus_remaining=old_genus_remaining,
        deleted_apg_paths=deleted_apg_paths,
    )
    for key, value in updates:
        log("search_photo/%s = %s" % (key, value))
        if apply:
            db.reference("search_photo/%s" % key).set(value)
    return updates


def update_latin_search(plant_id, old_name, new_name, apply):
    old_key = old_name.lower()
    new_key = new_name.lower()
    log("search_v3/la/%s is_label remove" % old_key)
    log("search_v3/la/%s is_label true" % new_key)
    if apply:
        db.reference("search_v3/la/%s/is_label" % old_key).delete()
        db.reference("search_v3/la/%s" % old_key).update({"list": {str(plant_id): 1}})
        db.reference("search_v3/la/%s" % new_key).update(
            {"is_label": True, "list": {str(plant_id): 1}}
        )


def _collect_apg_paths(prefix, node):
    paths = [prefix]
    if not isinstance(node, dict):
        return paths
    for key, child in node.items():
        if key in APG_META or not isinstance(child, dict):
            continue
        paths.extend(_collect_apg_paths("%s/%s" % (prefix, key), child))
    return paths


def _strip_id_from_apg_children(node_path, node, token, apply):
    """Remove plant id from nested taxa. Delete a nested node when its list is empty."""
    deleted = []
    if not isinstance(node, dict):
        return deleted
    token = str(token)
    for key, child in list(node.items()):
        if key in APG_META or not isinstance(child, dict):
            continue
        child_path = "%s/%s" % (node_path, key)
        deleted.extend(_strip_id_from_apg_children(child_path, child, token, apply))
        child_list = dict(child.get("list") or {})
        if token not in child_list:
            continue
        remaining = {k: v for k, v in child_list.items() if str(k) != token}
        if remaining:
            log("APG remove %s from %s (%s left)" % (token, child_path, len(remaining)))
            if apply:
                db.reference("%s/list/%s" % (child_path, token)).delete()
                db.reference("%s/count" % child_path).set(len(remaining))
        else:
            log("APG delete empty %s" % child_path)
            deleted.append(child_path)
            if apply:
                db.reference(child_path).delete()
    return deleted


def _list_without_token(listing, token):
    token = str(token)
    return {key: value for key, value in dict(listing or {}).items() if str(key) != token}


def drop_stray_old_genera(paths, token, new_path, apply):
    """Delete leftover old-genus namesakes (APGIV often omits Subfamilia)."""
    deleted = []
    token = str(token)
    for stray in paths:
        node = db.reference(stray).get() or {}
        remaining = _list_without_token(node.get("list"), token)
        if len(remaining) == len(dict(node.get("list") or {})):
            continue
        if remaining:
            log("APG remove %s from stray %s (%s left)" % (token, stray, len(remaining)))
            if apply:
                db.reference("%s/list/%s" % (stray, token)).delete()
                db.reference("%s/count" % stray).set(len(remaining))
            continue
        log("APG delete empty stray genus %s" % stray)
        deleted.extend(_collect_apg_paths(stray, node))
        if apply:
            db.reference(stray).delete()
        deleted.extend(strip_token_from_divergent_ancestors(stray, new_path, token, apply))
    return deleted


def move_apg(plant, plant_id, new_genus, apply):
    parent, old_genus = genus_parent_path(plant.get("APGIV") or {})
    if not old_genus:
        raise SystemExit("plants_v2 APGIV has no Genus")
    token = str(plant_id)
    family_path = family_firebase_path(plant.get("APGIV") or {})
    family_node = db.reference(family_path).get() or {} if family_path else {}
    resolved = resolve_move_paths(
        family_path, family_node, parent, old_genus, new_genus
    )
    old_path = resolved["old_path"]
    new_path = resolved["new_path"]
    result = {
        "new_path": new_path,
        "old_path": old_path,
        "old_remaining": None,
        "deleted_paths": [],
        "skipped": False,
        "reused": resolved["reused_new"],
    }
    if old_genus == new_genus:
        log("APG skip; genus unchanged %s" % old_path)
        result["skipped"] = True
        result["new_path"] = old_path
        return result

    old_node = db.reference(old_path).get() or {}
    remaining_list = _list_without_token(old_node.get("list"), token)
    remaining = len(remaining_list)
    result["old_remaining"] = remaining

    new_node = db.reference(new_path).get() or {}
    new_list = dict(new_node.get("list") or {})
    new_list[token] = 1

    if resolved["reused_new"]:
        log("APG reuse existing genus %s" % new_path)
    if resolved["reused_old"] and old_path != "%s/%s" % (parent, old_genus):
        log("APG reuse existing old genus %s" % old_path)
    log("APG add %s to %s (count %s)" % (token, new_path, len(new_list)))
    add_token_up_tree(new_path, token, apply)
    if remaining == 0:
        log("APG delete empty genus %s" % old_path)
        result["deleted_paths"] = _collect_apg_paths(old_path, old_node)
    else:
        log("APG remove %s from %s (%s left)" % (token, old_path, remaining))

    if apply:
        db.reference(new_path).update(
            {
                "type": new_node.get("type") or "Genus",
                "count": len(new_list),
                "list": new_list,
            }
        )
        if remaining == 0:
            db.reference(old_path).delete()
        else:
            db.reference("%s/list/%s" % (old_path, token)).delete()
            db.reference("%s/count" % old_path).set(remaining)

    if remaining == 0:
        result["deleted_paths"].extend(
            strip_token_from_divergent_ancestors(old_path, new_path, token, apply)
        )
    if remaining > 0:
        result["deleted_paths"] = _strip_id_from_apg_children(
            old_path, old_node, token, apply
        )
    result["deleted_paths"].extend(
        drop_stray_old_genera(resolved["other_old_paths"], token, new_path, apply)
    )
    return result


def rename_local_job(old_name, new_name, apply):
    old_dir = os.path.join(constants.plantsdir, "_jobs", slug(old_name))
    new_dir = os.path.join(constants.plantsdir, "_jobs", slug(new_name))
    if not os.path.isdir(old_dir):
        log("no local job %s" % old_dir)
        return
    log("local job %s -> %s" % (old_dir, new_dir))
    if not apply:
        return
    if os.path.isdir(new_dir):
        log("  target job exists; leaving both")
        return
    shutil.copytree(old_dir, new_dir)
    media_dir = os.path.join(new_dir, "media")
    if os.path.isdir(media_dir):
        for name in os.listdir(media_dir):
            renamed = remap_filename(name, old_name, new_name)
            if renamed != name:
                os.rename(os.path.join(media_dir, name), os.path.join(media_dir, renamed))
    plate_path = os.path.join(new_dir, "plate.json")
    if os.path.isfile(plate_path):
        import json

        with open(plate_path, encoding="utf-8") as handle:
            plate = json.load(handle)
        plate["accepted_name"] = new_name
        plate["wcvp_note"] = "renamed catalog key to WCVP accepted %s" % new_name
        with open(plate_path, "w", encoding="utf-8") as handle:
            json.dump(plate, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    shutil.rmtree(old_dir)


def build_new_plant(old, old_name, new_name, wcvp_row, gbif_row):
    plant = dict(old)
    plant["name"] = new_name
    if wcvp_row.get("author"):
        plant["author"] = wcvp_row["author"]
    if wcvp_row.get("ipni_id"):
        plant["ipniId"] = wcvp_row["ipni_id"]
    if gbif_row and gbif_row.get("status") == "ACCEPTED" and gbif_row.get("usage_key"):
        plant["gbifId"] = int(gbif_row["usage_key"])
    plant["wikiName"] = new_name
    plant["APGIV"] = apg_without_old_genus(old.get("APGIV") or {}, new_name.split()[0])
    if old.get("illustrationUrl"):
        plant["illustrationUrl"] = remap_relpath(
            old["illustrationUrl"], old_name, new_name
        )
    plant["photoUrls"] = [
        remap_relpath(url, old_name, new_name) for url in (old.get("photoUrls") or [])
    ]
    return plant


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Rename a live catalog plant + GCS.")
    parser.add_argument("old_name")
    parser.add_argument("new_name")
    parser.add_argument("--apply", action="store_true", help="Write Firebase and GCS.")
    parser.add_argument(
        "--keep-old-gcs",
        action="store_true",
        help="Leave the old catalog photo folder in place.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    old_name = args.old_name.strip()
    new_name = args.new_name.strip()
    apply = args.apply
    log("rename %r -> %r  apply=%s" % (old_name, new_name, apply))

    wcvp_row = wcvp.lookup(new_name)
    if not wcvp_row or (wcvp_row.get("status") or "").lower() != "accepted":
        raise SystemExit("WCVP has no accepted name %r" % new_name)
    if wcvp_row.get("accepted_name") != new_name:
        raise SystemExit(
            "WCVP accepted name is %r, not %r"
            % (wcvp_row.get("accepted_name"), new_name)
        )
    gbif_row = None
    try:
        gbif_row = gbif.match(new_name)
    except Exception as exc:
        log("gbif lookup failed: %s" % exc)

    init_firebase()
    old = db.reference("plants_v2/%s" % old_name).get()
    if not old:
        raise SystemExit("plants_v2/%s missing" % old_name)
    if db.reference("plants_v2/%s" % new_name).get():
        raise SystemExit("plants_v2/%s already exists" % new_name)
    plant_id = old.get("id")
    if plant_id is None:
        raise SystemExit("plants_v2 record has no id")
    header = db.reference("plants_headers/%s" % plant_id).get() or {}
    synonyms_old = db.reference("synonyms/%s" % old_name).get() or {}

    plant = build_new_plant(old, old_name, new_name, wcvp_row, gbif_row)
    synonyms = adjust_synonyms(
        synonyms_old,
        old_name,
        new_name,
        old.get("author"),
        old.get("ipniId"),
    )
    plant["synonyms"] = compact_synonym_names(old, synonyms, old_name, new_name)
    header = dict(header)
    header["name"] = new_name
    if header.get("url"):
        header["url"] = remap_relpath(header["url"], old_name, new_name)

    log("id %s author %s ipni %s gbif %s" % (
        plant_id, plant.get("author"), plant.get("ipniId"), plant.get("gbifId")
    ))
    log("folder %s" % catalog_folder(plant))
    log("illustration %s" % plant.get("illustrationUrl"))
    log("photos %s" % plant.get("photoUrls"))
    log("APGIV %s" % plant.get("APGIV"))

    bucket = storage.Client(constants.project).bucket(constants.bucket_name)
    copied = copy_gcs_catalog(bucket, old, old_name, new_name, apply)
    copy_gcs_observations(bucket, old_name, new_name, apply)

    if apply:
        failures = verify_public([dest for _, dest, _ in copied])
        if failures:
            raise SystemExit("new GCS objects not public: %s" % failures)

        db.reference("plants_v2/%s" % new_name).set(plant)
        db.reference("plants_headers/%s" % plant_id).update(header)
        db.reference("plants_to_update/list/%s" % plant_id).set(new_name)
        db.reference("synonyms/%s" % new_name).set(synonyms)
        db.reference("web/catalog/%s" % plant_id).update(
            {
                "id": int(plant_id),
                "name": new_name,
                "family": header.get("family") or "",
                "url": header.get("url") or "",
                "illustrationUrl": plant.get("illustrationUrl") or "",
            }
        )
        translated = copy_keyed_tree("translations", old_name, new_name, True)
        translated_new = copy_keyed_tree("translations_new", old_name, new_name, True)
        apg_result = move_apg(old, plant_id, new_name.split()[0], True)
        genus_path = None if apg_result["skipped"] else apg_result["new_path"]
        update_search_photo(
            old_name,
            new_name,
            genus_path,
            True,
            old_genus_remaining=apg_result["old_remaining"],
            deleted_apg_paths=apg_result["deleted_paths"],
        )
        update_latin_search(plant_id, old_name, new_name, True)
        patch_observation_rows(old_name, new_name, True)
        db.reference("versions/db_update").set(date.today().isoformat())
        delete_keyed_tree("translations", old_name, translated)
        delete_keyed_tree("translations_new", old_name, translated_new)
        db.reference("plants_v2/%s" % old_name).delete()
        db.reference("synonyms/%s" % old_name).delete()
        rename_local_job(old_name, new_name, True)
        if not args.keep_old_gcs and should_delete_old_gcs_folder(
            old, old_name, new_name
        ):
            old_folder = catalog_folder(old)
            log("delete GCS photos/%s/" % old_folder)
            for blob in bucket.list_blobs(prefix="photos/%s/" % old_folder):
                log("  delete %s" % blob.name)
                blob.delete()
        elif not args.keep_old_gcs:
            log(
                "GCS catalog folder unchanged %s; skip delete"
                % catalog_folder(old)
            )
        log("done")
        check = db.reference("plants_v2/%s" % new_name).get() or {}
        gone = db.reference("plants_v2/%s" % old_name).get()
        listed = db.reference("plants_to_update/list/%s" % plant_id).get()
        log("verify name=%s gone_old=%s list=%s" % (check.get("name"), gone, listed))
    else:
        apg_result = move_apg(old, plant_id, new_name.split()[0], False)
        genus_path = None if apg_result["skipped"] else apg_result["new_path"]
        update_search_photo(
            old_name,
            new_name,
            genus_path,
            False,
            old_genus_remaining=apg_result["old_remaining"],
            deleted_apg_paths=apg_result["deleted_paths"],
        )
        update_latin_search(plant_id, old_name, new_name, False)
        log("dry-run skips walking every translations language")
        log("dry-run only; pass --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
