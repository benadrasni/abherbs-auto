"""Add a species: dry-run packet by default. No Firebase writes unless --publish (not yet)."""

import argparse
import os
import sys

from catalog import apg_tree
from plant import assemble
from plant import common_names
from plant import draft_text
from plant import fetch_media
from catalog import incremental_indexes
from plant import infer_traits
from plant import media
from plant import resolve
from plant import validate
from sources import botanical
from sources import catalog_rest
from sources import wikipedia as wiki_api


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Prepare a plant job packet. Default is dry-run (no Firebase)."
    )
    parser.add_argument("name", nargs="?", help="Accepted Latin name or a synonym")
    parser.add_argument(
        "--job-dir",
        help="Output directory (default: ~/whatsthatflower/plants/_jobs/{slug})",
    )
    parser.add_argument(
        "--wcvp-db",
        help="Override WCVP sqlite path",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Write GCS + RTDB (explicit; default is dry-run)",
    )
    parser.add_argument("--skip-media", action="store_true", help="Metadata only")
    parser.add_argument("--skip-illustration", action="store_true", help="Photos only")
    parser.add_argument("--illustration", help="Local illustration file")
    parser.add_argument("--illustration-id", type=int, help="botanicalillustrations.org id")
    parser.add_argument("--photos", help="Local photo directory (otherwise Commons, then GBIF)")
    parser.add_argument(
        "--imagine-illustration",
        help="Install a Grok Imagine edit of illustration_raw.jpg as the official WebP",
    )
    return parser.parse_args(argv)


def run_dry(
    name,
    job_dir=None,
    wcvp_db=None,
    skip_media=False,
    skip_illustration=False,
    illustration=None,
    illustration_id=None,
    photos=None,
    imagine_illustration=None,
):
    resolved = resolve.resolve(name, wcvp_db=wcvp_db)
    wiki_title = wiki_api.title_from_url((resolved.get("wikipedia") or {}).get("en"))
    wikipedia = None
    try:
        wikipedia = wiki_api.fetch_extract(wiki_title or resolved["accepted_name"])
    except Exception as exc:
        resolved.setdefault("warnings", []).append("wikipedia: %s" % exc)
    packet = assemble.assemble(resolved, dest=job_dir)
    sisters = []
    try:
        sisters = catalog_rest.sister_traits(
            resolved.get("genus"),
            resolved.get("accepted_name"),
            include_english=True,
        )
    except Exception as exc:
        packet["job"].setdefault("warnings", []).append("sisters: %s" % exc)
    traits = infer_traits.infer(resolved, wikipedia, sisters=sisters)
    habitat_codes = (traits.get("habitat") or {}).get("values") or []
    extra_sources = []
    try:
        extra_sources = botanical.fetch_for(
            resolved.get("accepted_name"),
            genus=resolved.get("genus"),
            family=resolved.get("family"),
            lifeform=resolved.get("lifeform"),
            native_l2=resolved.get("native_l2"),
            native_l3=resolved.get("native_l3"),
        )
    except Exception as exc:
        packet["job"].setdefault("warnings", []).append("botanical: %s" % exc)
    common_names.apply_to_packet(packet, extra_sources)
    english = draft_text.draft_english(
        wikipedia,
        resolved=resolved,
        sisters=sisters,
        habitat_codes=habitat_codes,
        extra_sources=extra_sources,
    )
    assemble.apply_inference(packet, traits, english)
    dest = packet["dir"]
    for lang, entry in (packet.get("translations") or {}).items():
        assemble.write_json(os.path.join(dest, "translations", lang + ".json"), entry)
    if not skip_media:
        if skip_illustration:
            illustration_info = {"ok": False, "warning": "skipped"}
        else:
            illustration_info = fetch_media.fetch_illustration(
                packet["job"]["accepted_name"],
                dest,
                illustration_file=illustration,
                illustration_id=illustration_id,
            )
        sitelink = (resolved.get("wikilinks") or {}).get("commons")
        photo_info = fetch_media.fetch_photos(
            packet["job"]["accepted_name"],
            dest,
            photo_dir=photos,
            lifeform=packet["job"].get("lifeform") or "",
            prefix=packet["job"].get("photo_prefix") or "xx",
            commons_sitelink=sitelink,
        )
        fetch_media.apply_to_packet(packet, illustration_info, photo_info)
        if imagine_illustration:
            dest_ill = media.plate_legacy_path(
                os.path.join(dest, "media"),
                packet["job"]["accepted_name"],
            )
            media.import_imagine_result(imagine_illustration, dest_ill)
            imagine_copy = os.path.join(dest, "media", "illustration_imagine.webp")
            media.import_imagine_result(imagine_illustration, imagine_copy)
            packet["job"].setdefault("illustration", {})["ok"] = True
            packet["job"]["illustration"]["cleaner"] = "imagine"
    report = validate.validate(packet)
    packet["job"]["validation"] = report
    if not report["ok"]:
        packet["job"]["status"] = "needs_review"
    assemble.write_json(os.path.join(dest, "job.json"), packet["job"])
    assemble.write_json(os.path.join(dest, "plants_v2.json"), packet["plants_v2"])
    assemble.write_json(os.path.join(dest, "plants_header.json"), packet["plants_header"])
    assemble.write_review(os.path.join(dest, "review.md"), packet)
    if packet["job"].get("id") is not None:
        patch = incremental_indexes.build_patch(packet)
        assemble.write_json(os.path.join(dest, "index_patch.json"), patch)
        assemble.write_json(
            os.path.join(dest, "apg_patch.json"),
            apg_tree.patch_from_packet(packet),
        )
        packet["index_patch"] = patch
    return packet


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if not args.name:
        print("usage: add_species.py \"Latin name\"", file=sys.stderr)
        return 2
    packet = run_dry(
        args.name,
        job_dir=args.job_dir,
        wcvp_db=args.wcvp_db,
        skip_media=args.skip_media,
        skip_illustration=args.skip_illustration,
        illustration=args.illustration,
        illustration_id=args.illustration_id,
        photos=args.photos,
        imagine_illustration=args.imagine_illustration,
    )
    job = packet["job"]
    print("name: %s" % job["accepted_name"])
    print("id: %s" % job["id"])
    print("status: %s" % job["status"])
    print("family: %s" % packet["plants_header"].get("family"))
    print("l2: %s" % packet["plants_header"].get("filterDistribution"))
    print(
        "traits: color=%s habitat=%s petal=%s height=%s–%s flowering=%s–%s"
        % (
            packet["plants_header"].get("filterColor"),
            packet["plants_header"].get("filterHabitat"),
            packet["plants_header"].get("filterPetal"),
            packet["plants_v2"].get("heightFrom"),
            packet["plants_v2"].get("heightTo"),
            packet["plants_v2"].get("floweringFrom"),
            packet["plants_v2"].get("floweringTo"),
        )
    )
    validation = job.get("validation") or {}
    if validation:
        print("validation: %s" % ("ok" if validation.get("ok") else "errors"))
        for item in validation.get("errors") or []:
            print("  error: %s" % item)
    photos = job.get("photos") or {}
    if photos:
        print("photos: %s %s" % (photos.get("status"), photos.get("roles")))
    print("warnings: %s" % len(job.get("warnings") or []))
    for warning in job.get("warnings") or []:
        print("  %s" % warning)
    print("wrote %s" % os.path.abspath(packet["dir"]))
    if args.publish:
        import firebase_admin
        from firebase_admin import credentials
        import constants
        from catalog import publish

        report = publish.refuse(packet)
        if not report["ok"]:
            print("publish refused:")
            for item in report["errors"]:
                print("  %s" % item)
            return 2
        if not firebase_admin._apps:
            cred = credentials.Certificate(constants.certificate_firebase)
            firebase_admin.initialize_app(cred, {"databaseURL": constants.databaseURL})
        result = publish.publish(packet)
        print("published: %s" % result.get("published"))
        return 0
    print(
        "Firebase untouched. Next: python -m catalog.promote --patch %s/index_patch.json"
        % packet["dir"]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
