#!/usr/bin/env python3
"""PIL geometry for plates: letterbox, cream edges, signature, scan pad.

Try this before another image_edit when the problem is white bars, a burnt
frame, lighter/darker corners, or a huge signature. Labels, restacked parts,
and colour still need Imagine.
"""

import argparse
import os
import sys

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

INGEST = os.path.expanduser("~/whatsthatflower/ingest")
JOBS = os.path.expanduser("~/whatsthatflower/plants/_jobs")
if INGEST not in sys.path:
    sys.path.insert(0, INGEST)

from plant import media  # noqa: E402


def slug(name):
    return name.strip().replace(" ", "_")


def job_dir(name):
    return os.path.join(JOBS, slug(name))


def media_dir(name):
    return os.path.join(job_dir(name), "media")


def _iter_num(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    if not stem.startswith("iter"):
        return None
    try:
        return int(stem[4:])
    except ValueError:
        return None


def latest_iter(directory):
    found = []
    if not os.path.isdir(directory):
        return None
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        num = _iter_num(path)
        if num is not None:
            found.append((num, path))
    if not found:
        return None
    found.sort()
    return found[-1][1]


def next_iter_path(directory):
    current = latest_iter(directory)
    num = _iter_num(current) if current else 0
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "iter%d.jpg" % ((num or 0) + 1))


def default_src(directory):
    """Latest Imagine iter, else padded scan, else official plate."""
    path = latest_iter(directory)
    if path:
        return path
    for name in (
        "illustration_raw_23.jpg",
        "illustration_raw.jpg",
        "illustration_imagine.jpg",
    ):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    if not os.path.isdir(directory):
        return None
    for name in sorted(os.listdir(directory)):
        if name.endswith("@1600.webp"):
            return os.path.join(directory, name)
    return None


def official_dest(name):
    stem = slug(name)
    return os.path.join(media_dir(name), stem + ".webp")


def load_rgb(path):
    if not path or not os.path.isfile(path):
        raise SystemExit("missing image %s" % path)
    return media.as_rgb(media.apply_exif(Image.open(path)))


def save_iter(image, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    rgb = media.as_rgb(image)
    rgb.save(path, "JPEG", quality=95)
    return path


def resolve_paths(args, write=True):
    src = args.src
    out = args.out
    directory = media_dir(args.job) if args.job else None
    if args.job and not src:
        src = default_src(directory)
    if not src:
        raise SystemExit("give an image path or --job")
    if write and not out:
        if args.job:
            out = next_iter_path(directory)
        else:
            raise SystemExit("give -o/--out or --job")
    return src, out


def maybe_install(args, image_path):
    if not args.install:
        return None
    if not args.job:
        raise SystemExit("--install needs --job")
    dest = official_dest(args.job)
    written = media.import_imagine_result(image_path, dest)
    print("installed", written)
    return written


def cmd_detect(args):
    src, _out = resolve_paths(args, write=False)
    image = load_rgb(src)
    _cropped, bars = media.crop_letterbox(image)
    left, top, right, bottom = bars
    width, height = image.size
    print("src", src)
    print("size", width, height)
    print("letterbox L%d T%d R%d B%d" % (left, top, right, bottom))
    if bars == (0, 0, 0, 0):
        print("letterbox none")
    mark = media.extract_signature(image)
    if mark is None:
        print("signature none-or-unsafe")
    else:
        print("signature", mark.size)
    return 0


def cmd_prepare(args):
    src = args.src
    out = args.out
    if args.job:
        directory = media_dir(args.job)
        if not src:
            for name in ("illustration_raw.jpg", "illustration_raw_23.jpg"):
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    src = candidate
                    break
        if not out:
            if latest_iter(directory) is None:
                out = os.path.join(directory, "illustration_raw_23.jpg")
            else:
                out = next_iter_path(directory)
    if not src or not out:
        raise SystemExit("prepare needs an image path or --job with illustration_raw.jpg")
    image = Image.open(src)
    prepared = media.prepare_scan(image)
    save_iter(prepared, out)
    print("prepare", src, "->", out, prepared.size)
    maybe_install(args, out)
    return 0


def cmd_letterbox(args):
    src, out = resolve_paths(args)
    image = load_rgb(src)
    fixed, bars = media.letterbox_fix(image)
    if bars == (0, 0, 0, 0):
        print("letterbox none", src)
        if args.out or args.install:
            save_iter(image, out)
            print("wrote", out, image.size)
            maybe_install(args, out)
        return 0
    save_iter(fixed, out)
    print(
        "letterbox L%d T%d R%d B%d %s -> %s %sx%s"
        % (bars[0], bars[1], bars[2], bars[3], src, out, fixed.size[0], fixed.size[1])
    )
    maybe_install(args, out)
    return 0


def cmd_edges(args):
    src, out = resolve_paths(args)
    image = load_rgb(src)
    fixed = media.edges_fix(image)
    save_iter(fixed, out)
    print("edges", src, "->", out, fixed.size)
    maybe_install(args, out)
    return 0


def cmd_signature(args):
    if not args.source_from:
        raise SystemExit("signature needs --from DONOR")
    src, out = resolve_paths(args)
    target = load_rgb(src)
    donor = load_rgb(args.source_from)
    try:
        fixed = media.stamp_signature(target, donor)
    except ValueError as err:
        raise SystemExit(str(err))
    save_iter(fixed, out)
    print("signature", src, "from", args.source_from, "->", out, fixed.size)
    maybe_install(args, out)
    return 0


def cmd_install(args):
    src, _out = resolve_paths(args, write=False)
    if not args.job:
        raise SystemExit("install needs --job")
    args.install = True
    maybe_install(args, src)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="PIL letterbox / cream edges / signature / scan pad"
    )
    parser.add_argument(
        "command",
        choices=("detect", "prepare", "letterbox", "edges", "signature", "install"),
    )
    parser.add_argument("src", nargs="?", help="Image to fix (default: latest iter of --job)")
    parser.add_argument("-o", "--out", help="JPEG output (default: next iter of --job)")
    parser.add_argument("--job", help="Catalog slug or Latin name")
    parser.add_argument(
        "--from",
        dest="source_from",
        help="Donor plate with a correctly sized signature (signature command)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Write official WebPs from the result",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    commands = {
        "detect": cmd_detect,
        "prepare": cmd_prepare,
        "letterbox": cmd_letterbox,
        "edges": cmd_edges,
        "signature": cmd_signature,
        "install": cmd_install,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
