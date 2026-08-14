"""Fill a job packet with illustration + role-ordered photos. No Firebase."""

import os
import shutil
import urllib.request

import media
import photo_roles
from sources import botanical_illustrations
from sources import commons
from sources import gbif
from sources.httputil import USER_AGENT


def _download(url, dest):
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as incoming:
        with open(dest, "wb") as outgoing:
            outgoing.write(incoming.read())
    return dest


def local_photo_files(directory):
    files = []
    if not directory or not os.path.isdir(directory):
        return files
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        lower = name.lower()
        if "illustration" in lower:
            continue
        if not lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")):
            continue
        files.append({"path": path, "title": name, "description": name, "source_url": ""})
    return files


def fetch_illustration(name, dest_dir, illustration_file=None, illustration_id=None, client=None):
    media_dir = os.path.join(dest_dir, "media")
    os.makedirs(media_dir, exist_ok=True)
    cleaned = os.path.join(media_dir, name.replace(" ", "_") + ".webp")
    raw = os.path.join(media_dir, "illustration_raw.jpg")
    result = {
        "ok": False,
        "path": cleaned,
        "source_url": "",
        "id_illustration": illustration_id,
        "candidates": [],
        "warning": "",
    }
    if illustration_file:
        src = illustration_file
        result["source_url"] = illustration_file
        if not illustration_file.lower().endswith(".webp"):
            shutil.copyfile(illustration_file, raw)
            src = raw
        media.clean_illustration(src, os.path.join(media_dir, "illustration_pil.webp"))
        media.clean_illustration(src, cleaned)
        media.write_imagine_prompt(os.path.join(media_dir, "illustration_imagine_prompt.txt"), name)
        result["ok"] = os.path.isfile(cleaned)
        result["cleaner"] = "pil"
        return result

    client = client or botanical_illustrations.Client()
    if illustration_id:
        hd = client.hd_url(illustration_id)
        result["candidates"] = [{"id_illustration": illustration_id, "hd": hd}]
    else:
        found = client.candidates(name, limit=8)
        result["species"] = found.get("species")
        result["candidates"] = found.get("plates") or []
        if not result["candidates"]:
            result["warning"] = "no botanicalillustrations.org plate"
            return result
        illustration_id = result["candidates"][0]["id_illustration"]
        result["id_illustration"] = illustration_id
        hd = client.hd_url(illustration_id)
    if not hd:
        result["warning"] = "no HD url for illustration %s" % illustration_id
        return result
    _download(hd, raw)
    pil_path = os.path.join(media_dir, "illustration_pil.webp")
    media.clean_illustration(raw, pil_path)
    media.clean_illustration(raw, cleaned)
    media.write_imagine_prompt(os.path.join(media_dir, "illustration_imagine_prompt.txt"), name)
    result["ok"] = os.path.isfile(cleaned)
    result["cleaner"] = "pil"
    result["raw"] = raw
    result["source_url"] = botanical_illustrations.illustration_page_url(illustration_id)
    result["hd_url"] = hd
    return result


def _remote_candidate(item):
    return {
        "path": "",
        "url": item.get("url") or "",
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "object_name": item.get("object_name") or "",
        "categories": item.get("categories") or "",
        "source_url": item.get("descriptionurl") or "",
        "license": item.get("license") or "",
        "role_hint": item.get("role_hint"),
        "score": item.get("score") or 0,
        "source": item.get("source") or "",
        "width": item.get("width") or 0,
        "height": item.get("height") or 0,
    }


def collect_remote_photos(name, commons_sitelink=None):
    """Commons role categories first, GBIF/iNat CC-BY/CC0 to fill holes."""
    candidates = [_remote_candidate(item) for item in commons.collect(name, sitelink=commons_sitelink)]
    packed = photo_roles.pack(candidates)
    if packed.get("status") == "ok":
        return candidates
    seen = {item.get("url") for item in candidates}
    for item in gbif.media_search(name, limit=40):
        if item.get("url") in seen:
            continue
        if not commons.matches_species(item, name):
            continue
        seen.add(item.get("url"))
        candidates.append(_remote_candidate(item))
    return candidates


def fetch_photos(
    name,
    dest_dir,
    photo_dir=None,
    lifeform="",
    prefix="xx",
    commons_sitelink=None,
):
    media_dir = os.path.join(dest_dir, "media")
    thumbs = os.path.join(media_dir, ".thumbnails")
    os.makedirs(thumbs, exist_ok=True)
    if photo_dir:
        candidates = local_photo_files(photo_dir)
    else:
        candidates = collect_remote_photos(name, commons_sitelink=commons_sitelink)
    packed = photo_roles.pack(candidates, lifeform=lifeform)
    written = []
    for index, item in enumerate(packed["photos"], start=1):
        src = item.get("path")
        if not src:
            ext = os.path.splitext(item.get("url") or "x.jpg")[1] or ".jpg"
            src = os.path.join(media_dir, "download_%s%s" % (index, ext))
            _download(item["url"], src)
        dest = os.path.join(media_dir, "%s%s.webp" % (prefix, index))
        thumb = os.path.join(thumbs, "%s%s.webp" % (prefix, index))
        media.process_photo(src, dest, thumb)
        written.append(
            {
                "role": item.get("role"),
                "filename": os.path.basename(dest),
                "source_url": item.get("source_url") or "",
                "title": item.get("title") or "",
                "license": item.get("license") or "",
                "source": item.get("source") or "",
                "note": item.get("note") or "",
            }
        )
    packed["written"] = written
    return packed


def apply_to_packet(packet, illustration, photos):
    v2 = packet["plants_v2"]
    header = packet["plants_header"]
    job = packet["job"]
    folder = job.get("folder") or ""
    sources = list(v2.get("sourceUrls") or [])
    photo_urls = []
    for item in photos.get("written") or []:
        photo_urls.append("%s/%s" % (folder, item["filename"]))
        if item.get("source_url"):
            sources.append(item["source_url"])
    v2["photoUrls"] = photo_urls
    if photo_urls:
        header["url"] = photo_urls[0]
    if illustration.get("source_url"):
        sources.insert(0, illustration["source_url"])
    v2["sourceUrls"] = list(dict.fromkeys(sources))
    job["illustration"] = {
        "ok": illustration.get("ok"),
        "id": illustration.get("id_illustration"),
        "warning": illustration.get("warning") or "",
    }
    job["photos"] = {
        "status": photos.get("status"),
        "reason": photos.get("reason") or "",
        "roles": [item.get("role") for item in photos.get("written") or []],
        "chosen": photos.get("written") or [],
        "skipped": photos.get("skipped") or [],
    }
    if not illustration.get("ok"):
        job["status"] = "needs_review"
        job.setdefault("needs", []).append("illustration")
    if photos.get("status") != "ok":
        job["status"] = "needs_review"
        job.setdefault("needs", []).append("photos")
    return packet
